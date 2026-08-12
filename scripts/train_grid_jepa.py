#!/usr/bin/env python3
"""Train a small Grid-JEPA model on synthetic and optional local ARC pairs."""

from __future__ import annotations

import argparse
import csv
import json
import random
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.neural.dataset import arc_tasks_to_records, build_synthetic_records, pad_grids
from reasoning_project.neural.grid_jepa import GridJEPA, GridMaskSampler
from reasoning_project.neural.grid_encoder import torch_available
from reasoning_project.utils import (
    ensure_dir,
    log_progress,
    set_global_seed,
    utc_timestamp,
    update_run_state,
    write_json,
    write_text,
)

if torch_available():
    import torch
else:  # pragma: no cover
    torch = None


def _load_config(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_records(config: Dict[str, Any]) -> List[Any]:
    records = []
    if config.get("synthetic_suite"):
        records.extend(build_synthetic_records(dict(config["synthetic_suite"])))
    arc_cfg = dict(config.get("arc_pretrain", {}))
    if arc_cfg.get("enabled", False):
        arc_root = arc_cfg.get("arc_root", ROOT / "data" / "arc")
        splits = [str(split) for split in arc_cfg.get("splits", [arc_cfg.get("split", "training")])]
        max_tasks_by_split = dict(arc_cfg.get("max_tasks_per_split", {}))
        default_max_tasks = arc_cfg.get("max_tasks")
        for split in splits:
            tasks = load_arc_tasks(
                arc_root,
                split=split,
                max_tasks=max_tasks_by_split.get(split, default_max_tasks),
            )
            records.extend(arc_tasks_to_records(tasks))
    return [record for record in records if record.output_grid is not None]


def _split_records(records: List[Any], val_stride: int = 5) -> tuple[List[Any], List[Any]]:
    train = [record for index, record in enumerate(records) if index % val_stride != 0]
    val = [record for index, record in enumerate(records) if index % val_stride == 0]
    if not val:
        midpoint = max(1, len(records) // 5)
        val = records[:midpoint]
        train = records[midpoint:]
    return train, val


def _batch_loss(model: GridJEPA, batch: List[Any], sampler: GridMaskSampler, device: str) -> Dict[str, Any]:
    input_grids = [record.input_grid for record in batch]
    output_grids = [record.output_grid for record in batch]
    input_padded, input_mask = pad_grids(input_grids)
    output_padded, output_mask = pad_grids(output_grids)
    target_mask = sampler.sample_batch(input_grids)
    payload = model(
        torch.as_tensor(input_padded, dtype=torch.long, device=device),
        torch.as_tensor(input_mask, dtype=torch.bool, device=device),
        torch.as_tensor(target_mask, dtype=torch.bool, device=device),
        output_grids=torch.as_tensor(output_padded, dtype=torch.long, device=device),
        output_valid_mask=torch.as_tensor(output_mask, dtype=torch.bool, device=device),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "neural"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not torch_available():
        raise RuntimeError("train_grid_jepa.py requires torch in this environment")

    config = _load_config(args.config)
    run_name = str(config.get("run_name", "grid_jepa_smoke"))
    run_dir = ensure_dir(Path(args.output_dir) / run_name)
    checkpoint_path = run_dir / "checkpoint.pt"
    metrics_path = run_dir / "metrics.json"
    phase_state = {"phase": "setup", "step": 0}

    def _handle_signal(signum: int, _frame: Any) -> None:
        update_run_state(
            run_dir,
            run_name=run_name,
            status="interrupted",
            phase=phase_state["phase"],
            message=f"received signal {signum}",
            progress={"completed_steps": int(phase_state["step"])},
        )
        log_progress(
            run_dir,
            event="interrupted",
            phase=phase_state["phase"],
            message=f"received signal {signum}",
            data={"completed_steps": int(phase_state["step"])},
        )
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    set_global_seed(int(config.get("seed", 0)))
    random.seed(int(config.get("seed", 0)))
    torch.manual_seed(int(config.get("seed", 0)))

    device = str(config.get("device", "cuda" if torch.cuda.is_available() else "cpu"))
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    records = _build_records(config)
    if not records:
        raise ValueError("No input/output records were built for Grid-JEPA training")
    train_records, val_records = _split_records(records, val_stride=int(config.get("val_stride", 5)))
    model_config = {
        "hidden_dim": int(config.get("hidden_dim", 64)),
        "num_layers": int(config.get("num_layers", 2)),
        "num_heads": int(config.get("num_heads", 4)),
        "dropout": float(config.get("dropout", 0.1)),
        "max_grid_size": int(config.get("max_grid_size", 30)),
        "pair_prediction_weight": float(config.get("pair_prediction_weight", 0.5)),
    }
    model = GridJEPA(**model_config).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config.get("learning_rate", 1e-3)))
    sampler = GridMaskSampler(
        patch_size=int(config.get("patch_size", 2)),
        mask_ratio=float(config.get("mask_ratio", 0.3)),
        seed=int(config.get("seed", 0)),
    )

    start_step = 0
    history: List[Dict[str, float]] = []
    if args.resume and checkpoint_path.exists():
        package = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(package["model_state"])
        optimizer.load_state_dict(package["optimizer_state"])
        start_step = int(package.get("step", 0))
        history = list(package.get("history", []))

    max_steps = int(config.get("max_steps", 20))
    batch_size = int(config.get("batch_size", 8))
    command_text = " ".join(sys.argv)
    write_json(run_dir / "config.json", config)
    write_text(run_dir / "command_log.txt", command_text + "\n")
    write_json(run_dir / "seed_list.json", {"seed": int(config.get("seed", 0))})
    write_json(
        run_dir / "resume_instructions.json",
        {
            "run_dir": str(run_dir),
            "resume_command": f"python3.11 scripts/train_grid_jepa.py --config {args.config} --output-dir {args.output_dir} --resume",
            "checkpoint_path": str(checkpoint_path),
        },
    )
    write_json(
        run_dir / "budget_log.json",
        {
            "device": device,
            "batch_size": batch_size,
            "max_steps": max_steps,
            "patch_size": int(config.get("patch_size", 2)),
            "mask_ratio": float(config.get("mask_ratio", 0.3)),
            "pair_prediction_weight": float(config.get("pair_prediction_weight", 0.5)),
        },
    )
    update_run_state(
        run_dir,
        run_name=run_name,
        status="running",
        phase="setup",
        message="initialized grid JEPA run",
        progress={"resume_requested": bool(args.resume), "completed_steps": int(start_step), "max_steps": int(max_steps)},
    )
    log_progress(
        run_dir,
        event="start",
        phase="setup",
        message="initialized grid JEPA run",
        data={"resume_requested": bool(args.resume), "completed_steps": int(start_step), "max_steps": int(max_steps)},
    )

    try:
        phase_state["phase"] = "building_records"
        update_run_state(
            run_dir,
            run_name=run_name,
            status="running",
            phase=phase_state["phase"],
            message="records prepared",
            progress={
                "train_records": len(train_records),
                "val_records": len(val_records),
                "completed_steps": int(start_step),
                "max_steps": int(max_steps),
            },
        )
        log_progress(
            run_dir,
            event="records_ready",
            phase=phase_state["phase"],
            data={"train_records": len(train_records), "val_records": len(val_records)},
        )

        phase_state["phase"] = "training"
        if start_step > 0:
            log_progress(
                run_dir,
                event="resume",
                phase=phase_state["phase"],
                message="loaded training checkpoint",
                data={"start_step": int(start_step), "history_rows": len(history)},
            )
        for step in range(start_step, max_steps):
            batch = random.sample(train_records, k=min(batch_size, len(train_records)))
            model.train()
            payload = _batch_loss(model, batch, sampler, device)
            loss = payload["loss"]
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            model.update_target_encoder(momentum=float(config.get("ema_momentum", 0.99)))
            history.append(
                {
                    "step": float(step + 1),
                    "train_loss": float(payload["loss"].detach().cpu()),
                    "latent_loss": float(payload["latent_loss"].detach().cpu()),
                    "pair_loss": float(payload["pair_loss"].detach().cpu()),
                }
            )
            phase_state["step"] = step + 1
            torch.save(
                {
                    "step": step + 1,
                    "model_state": model.state_dict(),
                    "optimizer_state": optimizer.state_dict(),
                    "model_config": model_config,
                    "history": history,
                },
                checkpoint_path,
            )
            update_run_state(
                run_dir,
                run_name=run_name,
                status="running",
                phase=phase_state["phase"],
                message="training in progress",
                progress={
                    "completed_steps": int(step + 1),
                    "max_steps": int(max_steps),
                    "train_loss": float(history[-1]["train_loss"]),
                },
            )
            log_progress(
                run_dir,
                event="train_step",
                phase=phase_state["phase"],
                data={
                    "step": int(step + 1),
                    "max_steps": int(max_steps),
                    "train_loss": float(history[-1]["train_loss"]),
                    "latent_loss": float(history[-1]["latent_loss"]),
                    "pair_loss": float(history[-1]["pair_loss"]),
                },
            )

        phase_state["phase"] = "evaluating"
        model.eval()
        with torch.no_grad():
            val_payload = _batch_loss(model, val_records[: min(batch_size, len(val_records))], sampler, device)
        summary = {
            "generated_at": utc_timestamp(),
            "device": device,
            "torch_version": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "train_records": len(train_records),
            "val_records": len(val_records),
            "max_steps": max_steps,
            "final_train_loss": float(history[-1]["train_loss"]) if history else None,
            "final_val_loss": float(val_payload["loss"].detach().cpu()),
            "checkpoint_path": str(checkpoint_path),
        }
        write_json(metrics_path, summary)
        with (run_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["step", "train_loss", "latent_loss", "pair_loss"])
            writer.writeheader()
            for row in history:
                writer.writerow(row)
        write_text(
            run_dir / "summary.md",
            "\n".join(
                [
                    "# Grid JEPA Smoke Summary",
                    "",
                    f"- device: `{device}`",
                    f"- train records: {len(train_records)}",
                    f"- val records: {len(val_records)}",
                    f"- final train loss: {summary['final_train_loss']}",
                    f"- final val loss: {summary['final_val_loss']}",
                    f"- checkpoint: `{checkpoint_path}`",
                ]
            )
            + "\n",
        )
        write_json(
            run_dir / "manifest.json",
            {
                "run_dir": str(run_dir),
                "artifacts": [
                    "config.json",
                    "command_log.txt",
                    "seed_list.json",
                    "resume_instructions.json",
                    "run_state.json",
                    "status.txt",
                    "progress.jsonl",
                    "checkpoint.pt",
                    "metrics.json",
                    "metrics.csv",
                    "summary.md",
                    "budget_log.json",
                ],
            },
        )
        phase_state["phase"] = "completed"
        update_run_state(
            run_dir,
            run_name=run_name,
            status="completed",
            phase=phase_state["phase"],
            message="grid JEPA run completed",
            progress={"completed_steps": int(max_steps), "max_steps": int(max_steps)},
            extra={"artifacts_ready": True, "metrics_path": str(metrics_path)},
        )
        log_progress(
            run_dir,
            event="completed",
            phase=phase_state["phase"],
            data={"completed_steps": int(max_steps), "metrics_path": str(metrics_path)},
        )
    except BaseException as exc:
        update_run_state(
            run_dir,
            run_name=run_name,
            status="failed",
            phase=phase_state["phase"],
            message=f"{type(exc).__name__}: {exc}",
            progress={"completed_steps": int(phase_state["step"]), "max_steps": int(max_steps)},
        )
        log_progress(
            run_dir,
            event="failed",
            phase=phase_state["phase"],
            message=f"{type(exc).__name__}: {exc}",
            data={"completed_steps": int(phase_state["step"]), "max_steps": int(max_steps)},
        )
        raise


if __name__ == "__main__":
    main()
