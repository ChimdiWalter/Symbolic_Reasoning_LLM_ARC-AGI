#!/usr/bin/env python3
"""Train perception heads on top of a frozen JEPA encoder.

Predicts task-level properties from JEPA embeddings:
- object_count (regression)
- layout_type (5-class: scattered, grid_of_cells, nested, linear, single_object)
- bg_is_zero (binary)
- has_separators (binary)
- has_containment (binary)

Ground truth labels are computed from the raw grids via rule-based analysis.
"""
from __future__ import annotations

import argparse
import json
import random
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.perception_bridge import (
    JEPAPerceptionGuide,
    _detect_containment,
    _detect_separators,
)
from reasoning_project.neural.grid_encoder import torch_available
from reasoning_project.utils import (
    ensure_dir,
    log_progress,
    set_global_seed,
    update_run_state,
    write_json,
    write_text,
)

if torch_available():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
else:
    raise RuntimeError("Perception head training requires torch")

from reasoning_project.neural.grid_jepa import GridJEPA, load_grid_jepa_checkpoint
from reasoning_project.perception_bridge import PerceptionHeads

from scipy import ndimage


def _compute_labels(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, float]:
    """Compute ground-truth perception labels from raw grids."""
    obj_counts = []
    bg_zero_votes = 0
    sep_votes = 0
    cont_votes = 0
    total = len(train_pairs)

    for inp, out in train_pairs:
        vals, counts = np.unique(inp, return_counts=True)
        bg = int(vals[np.argmax(counts)])
        if bg == 0:
            bg_zero_votes += 1

        mask = inp != bg
        _, n = ndimage.label(mask)
        obj_counts.append(n)

        if _detect_separators(inp, bg):
            sep_votes += 1
        if _detect_containment(inp, bg):
            cont_votes += 1

    mean_objects = float(np.mean(obj_counts)) if obj_counts else 0

    has_sep = sep_votes > total / 2
    has_cont = cont_votes > total / 2

    if has_sep:
        layout_idx = 1  # grid_of_cells
    elif has_cont:
        layout_idx = 2  # nested
    elif mean_objects <= 1.5:
        layout_idx = 4  # single_object
    elif mean_objects > 6:
        layout_idx = 0  # scattered
    else:
        layout_idx = 0  # scattered (default)

    return {
        "object_count": mean_objects,
        "layout_idx": float(layout_idx),
        "bg_is_zero": float(bg_zero_votes > total / 2),
        "has_separators": float(has_sep),
        "has_containment": float(has_cont),
    }


def _encode_tasks(
    jepa: GridJEPA,
    tasks: list,
    device: str,
) -> List[Tuple[np.ndarray, Dict[str, float]]]:
    """Encode all tasks with JEPA and compute labels."""
    encoded = []
    jepa.eval()
    jepa.to(device)

    for task in tasks:
        if len(task.train) < 2:
            continue

        pairs = [
            (np.asarray(ex.input_grid, dtype=int), np.asarray(ex.output_grid, dtype=int))
            for ex in task.train
            if ex.output_grid is not None
        ]
        if len(pairs) < 2:
            continue

        with torch.no_grad():
            embedding = jepa.encode_task_context(pairs, device=device)

        labels = _compute_labels(pairs)
        encoded.append((embedding, labels))

    return encoded


def _train_step(
    model: PerceptionHeads,
    batch_embeddings: torch.Tensor,
    batch_labels: Dict[str, torch.Tensor],
    optimizer: torch.optim.Optimizer,
) -> Dict[str, float]:
    """Single training step."""
    model.train()
    preds = model(batch_embeddings)

    loss_count = F.mse_loss(preds["object_count"].squeeze(), batch_labels["object_count"])
    loss_layout = F.cross_entropy(preds["layout_logits"], batch_labels["layout_idx"].long())
    loss_bg = F.binary_cross_entropy_with_logits(
        preds["bg_is_zero"].squeeze(), batch_labels["bg_is_zero"]
    )
    loss_sep = F.binary_cross_entropy_with_logits(
        preds["has_separators"].squeeze(), batch_labels["has_separators"]
    )
    loss_cont = F.binary_cross_entropy_with_logits(
        preds["has_containment"].squeeze(), batch_labels["has_containment"]
    )

    total_loss = loss_count + loss_layout + loss_bg + loss_sep + loss_cont

    optimizer.zero_grad()
    total_loss.backward()
    optimizer.step()

    return {
        "total_loss": float(total_loss.item()),
        "loss_count": float(loss_count.item()),
        "loss_layout": float(loss_layout.item()),
        "loss_bg": float(loss_bg.item()),
        "loss_sep": float(loss_sep.item()),
        "loss_cont": float(loss_cont.item()),
    }


def _eval_accuracy(
    model: PerceptionHeads,
    embeddings: torch.Tensor,
    labels: Dict[str, torch.Tensor],
) -> Dict[str, float]:
    """Evaluate prediction accuracy."""
    model.eval()
    with torch.no_grad():
        preds = model(embeddings)

    count_mae = float(F.l1_loss(preds["object_count"].squeeze(), labels["object_count"]).item())
    layout_pred = preds["layout_logits"].argmax(dim=1)
    layout_acc = float((layout_pred == labels["layout_idx"].long()).float().mean().item())
    bg_pred = (torch.sigmoid(preds["bg_is_zero"].squeeze()) > 0.5).float()
    bg_acc = float((bg_pred == labels["bg_is_zero"]).float().mean().item())
    sep_pred = (torch.sigmoid(preds["has_separators"].squeeze()) > 0.5).float()
    sep_acc = float((sep_pred == labels["has_separators"]).float().mean().item())
    cont_pred = (torch.sigmoid(preds["has_containment"].squeeze()) > 0.5).float()
    cont_acc = float((cont_pred == labels["has_containment"]).float().mean().item())

    return {
        "count_mae": count_mae,
        "layout_acc": layout_acc,
        "bg_acc": bg_acc,
        "sep_acc": sep_acc,
        "cont_acc": cont_acc,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jepa-checkpoint", required=True,
                        help="Path to trained JEPA checkpoint")
    parser.add_argument("--arc-root", default=str(ROOT / "data" / "arc"),
                        help="Path to ARC dataset")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "neural" / "perception_heads"))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    set_global_seed(args.seed)
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    run_dir = ensure_dir(Path(args.output_dir))

    phase_state = {"phase": "setup", "step": 0}

    def _handle_signal(signum, _frame):
        update_run_state(run_dir, run_name="perception_heads", status="interrupted",
                         phase=phase_state["phase"],
                         message=f"received signal {signum}",
                         progress={"completed_steps": phase_state["step"]})
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Load frozen JEPA
    print(f"Loading JEPA from {args.jepa_checkpoint}")
    jepa = load_grid_jepa_checkpoint(args.jepa_checkpoint, device=device)
    jepa.eval()
    for p in jepa.parameters():
        p.requires_grad_(False)

    hidden_dim = jepa.hidden_dim
    input_dim = hidden_dim * 4  # encode_task_context returns hidden_dim * 4

    # Load ARC tasks
    print(f"Loading ARC tasks from {args.arc_root}")
    tasks = load_arc_tasks(args.arc_root, split="training")
    print(f"Loaded {len(tasks)} tasks")

    # Encode all tasks
    phase_state["phase"] = "encoding"
    print("Encoding tasks with JEPA...")
    encoded = _encode_tasks(jepa, tasks, device)
    print(f"Encoded {len(encoded)} tasks")

    # Split train/val
    random.shuffle(encoded)
    val_size = max(1, len(encoded) // 5)
    val_data = encoded[:val_size]
    train_data = encoded[val_size:]

    def _to_tensors(data):
        embs = torch.tensor(np.array([e for e, _ in data]), dtype=torch.float32, device=device)
        labs = {
            "object_count": torch.tensor([l["object_count"] for _, l in data], dtype=torch.float32, device=device),
            "layout_idx": torch.tensor([l["layout_idx"] for _, l in data], dtype=torch.float32, device=device),
            "bg_is_zero": torch.tensor([l["bg_is_zero"] for _, l in data], dtype=torch.float32, device=device),
            "has_separators": torch.tensor([l["has_separators"] for _, l in data], dtype=torch.float32, device=device),
            "has_containment": torch.tensor([l["has_containment"] for _, l in data], dtype=torch.float32, device=device),
        }
        return embs, labs

    train_embs, train_labels = _to_tensors(train_data)
    val_embs, val_labels = _to_tensors(val_data)

    # Build perception heads
    model = PerceptionHeads(input_dim=input_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    update_run_state(run_dir, run_name="perception_heads", status="running",
                     phase="training", message="starting training",
                     progress={"n_train": len(train_data), "n_val": len(val_data),
                               "epochs": args.epochs})
    log_progress(run_dir, event="start", phase="training",
                 data={"n_train": len(train_data), "n_val": len(val_data)})

    write_json(run_dir / "config.json", {
        "jepa_checkpoint": args.jepa_checkpoint,
        "arc_root": args.arc_root,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "seed": args.seed,
        "device": device,
        "input_dim": input_dim,
        "n_train": len(train_data),
        "n_val": len(val_data),
    })

    # Training loop
    phase_state["phase"] = "training"
    best_val_loss = float("inf")
    history = []
    n_train = train_embs.shape[0]

    for epoch in range(args.epochs):
        phase_state["step"] = epoch + 1
        perm = torch.randperm(n_train, device=device)
        epoch_losses = []

        for start in range(0, n_train, args.batch_size):
            end = min(start + args.batch_size, n_train)
            idx = perm[start:end]
            batch_embs = train_embs[idx]
            batch_labels = {k: v[idx] for k, v in train_labels.items()}

            losses = _train_step(model, batch_embs, batch_labels, optimizer)
            epoch_losses.append(losses["total_loss"])

        train_loss = float(np.mean(epoch_losses))
        val_metrics = _eval_accuracy(model, val_embs, val_labels)

        model.eval()
        with torch.no_grad():
            val_preds = model(val_embs)
            val_loss = float((
                F.mse_loss(val_preds["object_count"].squeeze(), val_labels["object_count"])
                + F.cross_entropy(val_preds["layout_logits"], val_labels["layout_idx"].long())
                + F.binary_cross_entropy_with_logits(val_preds["bg_is_zero"].squeeze(), val_labels["bg_is_zero"])
                + F.binary_cross_entropy_with_logits(val_preds["has_separators"].squeeze(), val_labels["has_separators"])
                + F.binary_cross_entropy_with_logits(val_preds["has_containment"].squeeze(), val_labels["has_containment"])
            ).item())

        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "val_loss": val_loss,
            **val_metrics,
        })

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            # Save perception heads + JEPA checkpoint together
            jepa_ckpt = torch.load(args.jepa_checkpoint, map_location=device, weights_only=False)
            jepa_ckpt["perception_heads"] = model.state_dict()
            jepa_ckpt["perception_config"] = {"input_dim": input_dim}
            torch.save(jepa_ckpt, run_dir / "jepa_with_perception.pt")

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"Epoch {epoch+1}/{args.epochs}  "
                  f"train={train_loss:.4f}  val={val_loss:.4f}  "
                  f"layout_acc={val_metrics['layout_acc']:.3f}  "
                  f"count_mae={val_metrics['count_mae']:.2f}  "
                  f"bg_acc={val_metrics['bg_acc']:.3f}")

    # Final report
    final = history[-1] if history else {}
    write_json(run_dir / "history.json", history)
    write_json(run_dir / "final_metrics.json", final)
    print(f"\nTraining complete. Best val loss: {best_val_loss:.4f}")
    print(f"Checkpoint saved to {run_dir / 'jepa_with_perception.pt'}")

    update_run_state(run_dir, run_name="perception_heads", status="completed",
                     phase="done", message="training complete",
                     progress={"best_val_loss": best_val_loss, **final})
    log_progress(run_dir, event="complete", phase="done",
                 data={"best_val_loss": best_val_loss, **final})


if __name__ == "__main__":
    main()
