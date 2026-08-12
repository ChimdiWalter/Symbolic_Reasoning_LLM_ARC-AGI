#!/usr/bin/env python3
"""Evaluate a trained Grid-JEPA checkpoint on a bounded record set."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.neural.dataset import arc_tasks_to_records, build_synthetic_records, pad_grids
from reasoning_project.neural.grid_jepa import GridMaskSampler, load_grid_jepa_checkpoint
from reasoning_project.neural.grid_encoder import torch_available
from reasoning_project.utils import ensure_dir, utc_timestamp, write_json, write_text

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
    arc_cfg = dict(config.get("arc_eval", {}))
    if arc_cfg.get("enabled", False):
        arc_root = arc_cfg.get("arc_root", ROOT / "data" / "arc")
        splits = [str(split) for split in arc_cfg.get("splits", [arc_cfg.get("split", "evaluation")])]
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "neural"))
    args = parser.parse_args()

    config = _load_config(args.config)
    run_name = str(config.get("run_name", "grid_jepa_eval"))
    run_dir = ensure_dir(Path(args.output_dir) / run_name)
    device = str(config.get("device", "cuda" if torch_available() and torch.cuda.is_available() else "cpu"))
    if device == "cuda" and not (torch_available() and torch.cuda.is_available()):
        device = "cpu"

    model = load_grid_jepa_checkpoint(args.checkpoint, device=device).to(device)
    records = _build_records(config)
    sampler = GridMaskSampler(
        patch_size=int(config.get("patch_size", 2)),
        mask_ratio=float(config.get("mask_ratio", 0.3)),
        seed=int(config.get("seed", 0)),
    )
    batch = records[: min(int(config.get("batch_size", 8)), len(records))]
    input_grids = [record.input_grid for record in batch]
    output_grids = [record.output_grid for record in batch]
    input_padded, input_mask = pad_grids(input_grids)
    output_padded, output_mask = pad_grids(output_grids)
    target_mask = sampler.sample_batch(input_grids)
    with torch.no_grad():
        payload = model(
            torch.as_tensor(input_padded, dtype=torch.long, device=device),
            torch.as_tensor(input_mask, dtype=torch.bool, device=device),
            torch.as_tensor(target_mask, dtype=torch.bool, device=device),
            output_grids=torch.as_tensor(output_padded, dtype=torch.long, device=device),
            output_valid_mask=torch.as_tensor(output_mask, dtype=torch.bool, device=device),
        )
    summary = {
        "generated_at": utc_timestamp(),
        "device": device,
        "records_evaluated": len(batch),
        "loss": float(payload["loss"].detach().cpu()),
        "latent_loss": float(payload["latent_loss"].detach().cpu()),
        "pair_loss": float(payload["pair_loss"].detach().cpu()),
        "checkpoint": str(Path(args.checkpoint).resolve()),
    }
    write_json(run_dir / "config.json", config)
    write_text(run_dir / "command_log.txt", " ".join(sys.argv) + "\n")
    write_json(run_dir / "seed_list.json", {"seed": int(config.get("seed", 0))})
    write_json(
        run_dir / "resume_instructions.json",
        {
            "run_dir": str(run_dir),
            "rerun_command": f"python3.11 scripts/eval_grid_jepa.py --config {args.config} --checkpoint {args.checkpoint} --output-dir {args.output_dir}",
            "checkpoint_path": str(Path(args.checkpoint).resolve()),
        },
    )
    write_json(
        run_dir / "budget_log.json",
        {
            "device": device,
            "batch_size": len(batch),
            "patch_size": int(config.get("patch_size", 2)),
            "mask_ratio": float(config.get("mask_ratio", 0.3)),
        },
    )
    write_json(run_dir / "metrics.json", summary)
    with (run_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            if isinstance(value, (int, float, str, bool)):
                writer.writerow({"metric": key, "value": value})
    write_text(
        run_dir / "summary.md",
        "\n".join(
            [
                "# Grid JEPA Eval Summary",
                "",
                f"- device: `{device}`",
                f"- records evaluated: {len(batch)}",
                f"- loss: {summary['loss']}",
                f"- latent loss: {summary['latent_loss']}",
                f"- pair loss: {summary['pair_loss']}",
                f"- checkpoint: `{summary['checkpoint']}`",
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
                "budget_log.json",
                "metrics.json",
                "metrics.csv",
                "summary.md",
            ],
        },
    )


if __name__ == "__main__":
    main()
