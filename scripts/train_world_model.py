"""Train the Slot Attention + GNS world model on ARC tasks."""
import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.neural.grid_encoder import torch_available

if not torch_available():
    print("ERROR: torch required for training")
    sys.exit(1)

import torch
from torch.optim import Adam
from torch.optim.lr_scheduler import CosineAnnealingLR

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.neural.slot_attention import GridSlotModel
from reasoning_project.neural.graph_network import WorldModel


def collate_pairs(tasks, max_pairs_per_task=4, max_grid_size=30):
    """Collate ARC task pairs into padded tensors."""
    input_grids, output_grids = [], []
    for task in tasks:
        for ex in task.train[:max_pairs_per_task]:
            inp = np.asarray(ex.input_grid, dtype=int)
            out = np.asarray(ex.output_grid, dtype=int)
            if inp.shape[0] > max_grid_size or inp.shape[1] > max_grid_size:
                continue
            if out.shape[0] > max_grid_size or out.shape[1] > max_grid_size:
                continue
            input_grids.append(inp)
            output_grids.append(out)

    if not input_grids:
        return None

    max_h_in = max(g.shape[0] for g in input_grids)
    max_w_in = max(g.shape[1] for g in input_grids)
    max_h_out = max(g.shape[0] for g in output_grids)
    max_w_out = max(g.shape[1] for g in output_grids)

    B = len(input_grids)
    inp_padded = np.zeros((B, max_h_in, max_w_in), dtype=int)
    inp_valid = np.zeros((B, max_h_in, max_w_in), dtype=bool)
    out_padded = np.zeros((B, max_h_out, max_w_out), dtype=int)
    out_valid = np.zeros((B, max_h_out, max_w_out), dtype=bool)

    for i, (ig, og) in enumerate(zip(input_grids, output_grids)):
        h_in, w_in = ig.shape
        inp_padded[i, :h_in, :w_in] = ig
        inp_valid[i, :h_in, :w_in] = True
        h_out, w_out = og.shape
        out_padded[i, :h_out, :w_out] = og
        out_valid[i, :h_out, :w_out] = True

    return {
        "input_grids": torch.tensor(inp_padded, dtype=torch.long),
        "input_valid": torch.tensor(inp_valid, dtype=torch.bool),
        "output_grids": torch.tensor(out_padded, dtype=torch.long),
        "output_valid": torch.tensor(out_valid, dtype=torch.bool),
    }


def make_batches(tasks, batch_size=32, max_grid_size=30):
    """Create mini-batches from all task training pairs."""
    all_pairs = []
    for task in tasks:
        for ex in task.train:
            inp = np.asarray(ex.input_grid, dtype=int)
            out = np.asarray(ex.output_grid, dtype=int)
            if (inp.shape[0] <= max_grid_size and inp.shape[1] <= max_grid_size and
                out.shape[0] <= max_grid_size and out.shape[1] <= max_grid_size):
                all_pairs.append((inp, out))

    rng = np.random.default_rng(42)
    indices = np.arange(len(all_pairs))
    rng.shuffle(indices)

    batches = []
    for start in range(0, len(indices), batch_size):
        batch_idx = indices[start:start + batch_size]
        batch_inputs = [all_pairs[i][0] for i in batch_idx]
        batch_outputs = [all_pairs[i][1] for i in batch_idx]

        max_h_in = max(g.shape[0] for g in batch_inputs)
        max_w_in = max(g.shape[1] for g in batch_inputs)
        max_h_out = max(g.shape[0] for g in batch_outputs)
        max_w_out = max(g.shape[1] for g in batch_outputs)

        B = len(batch_inputs)
        inp_p = np.zeros((B, max_h_in, max_w_in), dtype=int)
        inp_v = np.zeros((B, max_h_in, max_w_in), dtype=bool)
        out_p = np.zeros((B, max_h_out, max_w_out), dtype=int)
        out_v = np.zeros((B, max_h_out, max_w_out), dtype=bool)

        for i in range(B):
            h, w = batch_inputs[i].shape
            inp_p[i, :h, :w] = batch_inputs[i]
            inp_v[i, :h, :w] = True
            h, w = batch_outputs[i].shape
            out_p[i, :h, :w] = batch_outputs[i]
            out_v[i, :h, :w] = True

        batches.append({
            "input_grids": torch.tensor(inp_p, dtype=torch.long),
            "input_valid": torch.tensor(inp_v, dtype=torch.bool),
            "output_grids": torch.tensor(out_p, dtype=torch.long),
            "output_valid": torch.tensor(out_v, dtype=torch.bool),
        })

    return batches


def train_slot_attention_only(tasks, config, output_dir, device):
    """Phase 1: pretrain slot attention on input grid reconstruction."""
    output_dir = Path(output_dir) / "slot_pretrain"
    output_dir.mkdir(parents=True, exist_ok=True)

    model = GridSlotModel(
        num_slots=config.get("num_slots", 8),
        slot_dim=config.get("slot_dim", 64),
        hidden_dim=config.get("hidden_dim", 128),
        num_iterations=config.get("slot_iterations", 3),
        max_grid_size=config.get("max_grid_size", 30),
    ).to(device)

    optimizer = Adam(model.parameters(), lr=config.get("slot_lr", 4e-4))
    epochs = config.get("slot_epochs", 50)

    all_grids = []
    for task in tasks:
        for ex in task.train:
            g = np.asarray(ex.input_grid, dtype=int)
            if g.shape[0] <= 30 and g.shape[1] <= 30:
                all_grids.append(g)
        for ex in task.test:
            g = np.asarray(ex.input_grid, dtype=int)
            if g.shape[0] <= 30 and g.shape[1] <= 30:
                all_grids.append(g)

    print(f"Slot pretrain: {len(all_grids)} grids, {epochs} epochs")
    batch_size = config.get("batch_size", 32)
    rng = np.random.default_rng(42)

    metrics_log = []
    for epoch in range(epochs):
        indices = np.arange(len(all_grids))
        rng.shuffle(indices)
        epoch_loss = 0.0
        n_batches = 0

        for start in range(0, len(indices), batch_size):
            batch_idx = indices[start:start + batch_size]
            batch_grids = [all_grids[i] for i in batch_idx]

            max_h = max(g.shape[0] for g in batch_grids)
            max_w = max(g.shape[1] for g in batch_grids)
            B = len(batch_grids)
            padded = np.zeros((B, max_h, max_w), dtype=int)
            valid = np.zeros((B, max_h, max_w), dtype=bool)
            for i, g in enumerate(batch_grids):
                h, w = g.shape
                padded[i, :h, :w] = g
                valid[i, :h, :w] = True

            grids_t = torch.tensor(padded, dtype=torch.long, device=device)
            valid_t = torch.tensor(valid, dtype=torch.bool, device=device)

            result = model(grids_t, valid_t)
            loss = result["loss"]

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        avg_loss = epoch_loss / max(1, n_batches)
        metrics_log.append({"epoch": epoch, "loss": round(avg_loss, 4)})
        if epoch % 10 == 0 or epoch == epochs - 1:
            print(f"  Epoch {epoch}: loss={avg_loss:.4f}")

    torch.save({
        "model_state": model.state_dict(),
        "model_config": {
            "num_slots": config.get("num_slots", 8),
            "slot_dim": config.get("slot_dim", 64),
            "hidden_dim": config.get("hidden_dim", 128),
            "num_iterations": config.get("slot_iterations", 3),
            "max_grid_size": config.get("max_grid_size", 30),
        },
        "metrics": metrics_log,
    }, output_dir / "slot_model.pt")
    print(f"Saved slot model to {output_dir / 'slot_model.pt'}")

    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics_log, f, indent=2)

    return model


def make_task_conditioned_batches(tasks, max_grid_size=30):
    """Create per-task episode batches for task-conditioned training.

    Each episode: sample context pairs from a task, hold out one pair as target.
    This teaches the model to use demonstrations for in-context prediction.
    """
    episodes = []
    for task in tasks:
        valid_pairs = []
        for ex in task.train:
            inp = np.asarray(ex.input_grid, dtype=int)
            out = np.asarray(ex.output_grid, dtype=int)
            if (inp.shape[0] <= max_grid_size and inp.shape[1] <= max_grid_size and
                out.shape[0] <= max_grid_size and out.shape[1] <= max_grid_size):
                valid_pairs.append((inp, out))
        if len(valid_pairs) >= 2:
            episodes.append(valid_pairs)
    return episodes


def _generate_negative_output(target_out, rng, all_episodes=None, episode_idx=None):
    """Generate a negative (wrong) output for contrastive training.

    Uses one of three strategies:
      (a) randomly permute colors in the correct output,
      (b) use a different task's output,
      (c) shuffle rows/columns.
    """
    strategy = rng.integers(0, 3)
    if strategy == 0:
        # (a) Randomly permute colors
        neg = target_out.copy()
        unique_colors = np.unique(neg)
        if len(unique_colors) > 1:
            perm = rng.permutation(unique_colors)
            color_map = dict(zip(unique_colors, perm))
            neg_flat = neg.flatten()
            for i in range(len(neg_flat)):
                neg_flat[i] = color_map[neg_flat[i]]
            neg = neg_flat.reshape(target_out.shape)
        else:
            # Fallback: flip values
            neg = (neg + rng.integers(1, 10)) % 10
        return neg
    elif strategy == 1 and all_episodes is not None and len(all_episodes) > 1:
        # (b) Use a different task's output
        other_idx = rng.integers(0, len(all_episodes))
        while other_idx == episode_idx and len(all_episodes) > 1:
            other_idx = rng.integers(0, len(all_episodes))
        other_pairs = all_episodes[other_idx]
        other_out = other_pairs[rng.integers(0, len(other_pairs))][1]
        # Resize to match target shape if needed
        H_t, W_t = target_out.shape
        H_o, W_o = other_out.shape
        neg = np.zeros_like(target_out)
        neg[:min(H_t, H_o), :min(W_t, W_o)] = other_out[:min(H_t, H_o), :min(W_t, W_o)]
        return neg
    else:
        # (c) Shuffle rows/columns
        neg = target_out.copy()
        if rng.random() < 0.5:
            neg = neg[rng.permutation(neg.shape[0]), :]
        else:
            neg = neg[:, rng.permutation(neg.shape[1])]
        return neg


def train_world_model(tasks, config, output_dir, device, slot_model=None):
    """Phase 2: train task-conditioned world model.

    Uses episodic training: for each task, use N-1 pairs as context and predict
    the held-out pair. This forces the model to learn in-context rule extraction.

    Includes contrastive loss: for each episode, generates a negative output and
    enforces a margin between positive and negative scores.
    """
    output_dir = Path(output_dir) / "world_model"
    output_dir.mkdir(parents=True, exist_ok=True)

    model = WorldModel(
        num_slots=config.get("num_slots", 8),
        slot_dim=config.get("slot_dim", 64),
        hidden_dim=config.get("hidden_dim", 128),
        gns_layers=config.get("gns_layers", 3),
        max_grid_size=config.get("max_grid_size", 30),
    ).to(device)

    if slot_model is not None:
        model.slot_model.load_state_dict(slot_model.state_dict())
        print("Initialized slot attention from pretrained checkpoint")

    optimizer = Adam(model.parameters(), lr=config.get("world_lr", 2e-4))
    epochs = config.get("world_epochs", 100)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

    episodes = make_task_conditioned_batches(tasks, config.get("max_grid_size", 30))
    print(f"World model: {len(episodes)} task episodes, {epochs} epochs")

    contrastive_weight = config.get("contrastive_weight", 0.3)
    contrastive_margin = config.get("contrastive_margin", 0.1)
    print(f"Contrastive loss: weight={contrastive_weight}, margin={contrastive_margin}")

    metrics_log = []
    best_loss = float("inf")

    model_config = {
        "num_slots": config.get("num_slots", 8),
        "slot_dim": config.get("slot_dim", 64),
        "hidden_dim": config.get("hidden_dim", 128),
        "gns_layers": config.get("gns_layers", 3),
        "max_grid_size": config.get("max_grid_size", 30),
    }

    for epoch in range(epochs):
        rng = np.random.default_rng(epoch)
        order = rng.permutation(len(episodes))

        epoch_loss = 0.0
        epoch_recon = 0.0
        epoch_input = 0.0
        epoch_contrastive = 0.0
        n = 0

        for ei in order:
            pairs = episodes[ei]
            hold_out_idx = rng.integers(0, len(pairs))
            context_pairs = [p for i, p in enumerate(pairs) if i != hold_out_idx]
            target_inp, target_out = pairs[hold_out_idx]

            task_emb = model._compute_task_embedding(context_pairs, device)

            H_in, W_in = target_inp.shape
            H_out, W_out = target_out.shape
            ig = torch.tensor(target_inp, dtype=torch.long, device=device).unsqueeze(0)
            iv = torch.ones(1, H_in, W_in, dtype=torch.bool, device=device)
            og = torch.tensor(target_out, dtype=torch.long, device=device).unsqueeze(0)
            ov = torch.ones(1, H_out, W_out, dtype=torch.bool, device=device)

            result = model(ig, iv, og, ov, task_embedding=task_emb)
            recon_loss = result["loss"]

            # --- Contrastive loss ---
            # Score the positive (correct) output
            output_logits = result["output_recon_logits"]  # (1, H_out, W_out, C)
            log_probs = torch.nn.functional.log_softmax(output_logits[0], dim=-1)
            target_clamped = og[0].clamp(0, log_probs.shape[-1] - 1)
            pos_ll = log_probs.gather(-1, target_clamped.unsqueeze(-1)).squeeze(-1)
            score_pos = pos_ll.mean()

            # Generate and score negative output
            neg_out = _generate_negative_output(
                target_out, rng, all_episodes=episodes, episode_idx=ei
            )
            neg_out_t = torch.tensor(neg_out, dtype=torch.long, device=device)
            neg_clamped = neg_out_t.clamp(0, log_probs.shape[-1] - 1)
            neg_ll = log_probs.gather(-1, neg_clamped.unsqueeze(-1)).squeeze(-1)
            score_neg = neg_ll.mean()

            # Margin loss: want score_pos > score_neg + margin
            contrastive_loss = torch.clamp(
                contrastive_margin - score_pos + score_neg, min=0.0
            )

            loss = recon_loss + contrastive_weight * contrastive_loss

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            epoch_loss += loss.item()
            epoch_recon += result["output_recon_loss"].item()
            epoch_input += result["input_recon_loss"].item()
            epoch_contrastive += contrastive_loss.item()
            n += 1

        scheduler.step()
        avg_loss = epoch_loss / max(1, n)
        avg_recon = epoch_recon / max(1, n)
        avg_input = epoch_input / max(1, n)
        avg_contrastive = epoch_contrastive / max(1, n)

        metrics_log.append({
            "epoch": epoch,
            "loss": round(avg_loss, 4),
            "output_recon_loss": round(avg_recon, 4),
            "input_recon_loss": round(avg_input, 4),
            "contrastive_loss": round(avg_contrastive, 4),
        })

        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save({
                "model_state": model.state_dict(),
                "model_config": model_config,
                "epoch": epoch,
                "best_loss": best_loss,
                "metrics": metrics_log,
            }, output_dir / "world_model_best.pt")

        if epoch % 10 == 0 or epoch == epochs - 1:
            print(f"  Epoch {epoch}: loss={avg_loss:.4f} recon={avg_recon:.4f} input={avg_input:.4f} contrastive={avg_contrastive:.4f}")

    torch.save({
        "model_state": model.state_dict(),
        "model_config": model_config,
        "epoch": epochs - 1,
        "best_loss": best_loss,
        "metrics": metrics_log,
    }, output_dir / "world_model_final.pt")

    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics_log, f, indent=2)

    print(f"Saved world model to {output_dir}")
    return model


def evaluate_world_model(model, tasks, output_dir, device, max_tasks=100):
    """Evaluate task-conditioned world model predictions on ARC tasks.

    Uses training examples as context demos, predicts on test examples.
    """
    output_dir = Path(output_dir) / "world_model_eval"
    output_dir.mkdir(parents=True, exist_ok=True)

    model.to(device)
    model.eval()

    results = []
    results_unconditioned = []
    for task in tasks[:max_tasks]:
        test_examples = task.test
        if not test_examples:
            continue

        train_pairs = []
        for ex in task.train:
            inp = np.asarray(ex.input_grid, dtype=int)
            out = np.asarray(ex.output_grid, dtype=int)
            if inp.shape[0] <= 30 and inp.shape[1] <= 30 and out.shape[0] <= 30 and out.shape[1] <= 30:
                train_pairs.append((inp, out))

        for ex in test_examples:
            inp = np.asarray(ex.input_grid, dtype=int)
            target = np.asarray(ex.output_grid, dtype=int)

            if inp.shape[0] > 30 or inp.shape[1] > 30:
                continue
            if target.shape[0] > 30 or target.shape[1] > 30:
                continue

            try:
                predicted = model.predict(inp, target.shape, device, train_pairs=train_pairs)
                exact = bool(np.array_equal(predicted, target))
                pixel_acc = float(np.mean(predicted == target)) if predicted.shape == target.shape else 0.0
            except Exception:
                exact = False
                pixel_acc = 0.0

            results.append({
                "task_id": task.task_id,
                "exact": exact,
                "pixel_accuracy": round(pixel_acc, 4),
            })

            try:
                pred_uncond = model.predict(inp, target.shape, device, train_pairs=None)
                exact_u = bool(np.array_equal(pred_uncond, target))
                pixel_u = float(np.mean(pred_uncond == target)) if pred_uncond.shape == target.shape else 0.0
            except Exception:
                exact_u = False
                pixel_u = 0.0
            results_unconditioned.append({
                "task_id": task.task_id,
                "exact": exact_u,
                "pixel_accuracy": round(pixel_u, 4),
            })

    n_exact = sum(r["exact"] for r in results)
    avg_pixel = np.mean([r["pixel_accuracy"] for r in results]) if results else 0.0
    n_exact_u = sum(r["exact"] for r in results_unconditioned)
    avg_pixel_u = np.mean([r["pixel_accuracy"] for r in results_unconditioned]) if results_unconditioned else 0.0

    summary = {
        "n_evaluated": len(results),
        "conditioned": {
            "n_exact": n_exact,
            "exact_rate": round(n_exact / max(1, len(results)), 4),
            "mean_pixel_accuracy": round(float(avg_pixel), 4),
        },
        "unconditioned": {
            "n_exact": n_exact_u,
            "exact_rate": round(n_exact_u / max(1, len(results_unconditioned)), 4),
            "mean_pixel_accuracy": round(float(avg_pixel_u), 4),
        },
    }

    with open(output_dir / "eval_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    with open(output_dir / "eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"Eval (conditioned): {n_exact}/{len(results)} exact, pixel_acc={avg_pixel:.4f}")
    print(f"Eval (unconditioned): {n_exact_u}/{len(results_unconditioned)} exact, pixel_acc={avg_pixel_u:.4f}")
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None, help="JSON config file")
    parser.add_argument("--arc-root", default="data/arc")
    parser.add_argument("--output-dir", default="outputs/neural/world_model")
    parser.add_argument("--device", default=None)
    parser.add_argument("--phase", choices=["slot", "world", "all", "eval"], default="all")
    parser.add_argument("--slot-checkpoint", default=None)
    parser.add_argument("--world-checkpoint", default=None)
    args = parser.parse_args()

    if args.config:
        with open(args.config) as f:
            config = json.load(f)
    else:
        config = {
            "num_slots": 8,
            "slot_dim": 64,
            "hidden_dim": 128,
            "slot_iterations": 3,
            "gns_layers": 3,
            "max_grid_size": 30,
            "batch_size": 32,
            "slot_lr": 4e-4,
            "slot_epochs": 50,
            "world_lr": 2e-4,
            "world_epochs": 100,
        }

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    tasks = load_arc_tasks(args.arc_root)
    print(f"Loaded {len(tasks)} ARC tasks")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    t0 = time.time()

    slot_model = None
    if args.phase in ("slot", "all"):
        slot_model = train_slot_attention_only(tasks, config, output_dir, device)

    if args.phase in ("world", "all"):
        if slot_model is None and args.slot_checkpoint:
            from reasoning_project.neural.slot_attention import load_slot_model_checkpoint
            slot_model = load_slot_model_checkpoint(args.slot_checkpoint, device)
        world_model = train_world_model(tasks, config, output_dir, device, slot_model)
        evaluate_world_model(world_model, tasks, output_dir, device)

    if args.phase == "eval":
        if args.world_checkpoint:
            from reasoning_project.neural.graph_network import load_world_model_checkpoint
            world_model = load_world_model_checkpoint(args.world_checkpoint, device)
        else:
            ckpt = output_dir / "world_model" / "world_model_best.pt"
            from reasoning_project.neural.graph_network import load_world_model_checkpoint
            world_model = load_world_model_checkpoint(ckpt, device)
        evaluate_world_model(world_model, tasks, output_dir, device)

    print(f"\nTotal time: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
