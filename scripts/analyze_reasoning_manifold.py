#!/usr/bin/env python3
"""Analyze bounded latent candidate geometry from refinement outputs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.diagnostics.reasoning_manifold import summarize_reasoning_manifold
from reasoning_project.utils import ensure_dir, utc_timestamp, write_json, write_text


def _load_records(run_dir: Path) -> List[Dict[str, Any]]:
    return json.loads((run_dir / "refinement_records.json").read_text(encoding="utf-8"))


def _append_records(
    records: Sequence[Dict[str, Any]],
    by_method: Dict[str, Dict[str, Any]],
    *,
    success_only: bool = False,
) -> None:
    for record in records:
        method = str(record["method_name"])
        bucket = by_method.setdefault(method, {"success": [], "failure": [], "trajectories": [], "success_sources": []})
        top_candidates = list(record.get("top_candidates", []))
        if not top_candidates:
            continue
        top_embedding = top_candidates[0].get("embedding", [])
        evaluation = dict(record.get("evaluation", {}))
        exact_solved = float(evaluation.get("test_exact_task_accuracy", 0.0)) >= 1.0
        if exact_solved:
            bucket["success"].append(top_embedding)
            bucket["success_sources"].append(str(record.get("task_id", "")))
        elif not success_only:
            bucket["failure"].append(top_embedding)
        trajectory = dict(record.get("diagnostics", {})).get("trajectory_embeddings", [])
        if trajectory and not success_only:
            bucket["trajectories"].append(trajectory)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    config: Dict[str, Any] = {}
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    run_dir_value = args.run_dir or config.get("run_dir")
    if not run_dir_value:
        raise ValueError("analyze_reasoning_manifold.py requires --run-dir or --config with run_dir")
    run_dir = Path(run_dir_value)
    output_dir = ensure_dir(args.output_dir or config.get("output_dir") or run_dir / "reasoning_manifold")
    records = _load_records(run_dir)
    success_run_dirs = [Path(path) for path in config.get("success_run_dirs", [])]

    by_method: Dict[str, Dict[str, Any]] = {}
    _append_records(records, by_method, success_only=False)
    for success_run_dir in success_run_dirs:
        _append_records(_load_records(success_run_dir), by_method, success_only=True)

    summary = {"generated_at": utc_timestamp(), "by_method": {}}
    csv_rows: List[Dict[str, Any]] = []
    for method, payload in sorted(by_method.items()):
        trajectory = payload["trajectories"][0] if payload["trajectories"] else None
        if payload["success"] and payload["failure"]:
            metrics = summarize_reasoning_manifold(
                payload["success"],
                payload["failure"],
                trajectory_vectors=trajectory,
                k=3,
            )
        else:
            metrics = {
                "success_count": len(payload["success"]),
                "failure_count": len(payload["failure"]),
                "k": 3,
                "separability_score": 0.0,
                "failure_distance_mean": 0.0,
                "success_self_distance_mean": 0.0,
            }
            if trajectory is not None:
                metrics["trajectory_length"] = len(trajectory)
                metrics["divergence_step"] = None
        metrics["success_anchor_count"] = len(payload.get("success_sources", []))
        metrics["used_auxiliary_success"] = bool(success_run_dirs and payload.get("success"))
        summary["by_method"][method] = metrics
        csv_rows.append({"method": method, **metrics})

    write_json(output_dir / "config.json", config or {"run_dir": str(run_dir), "output_dir": str(output_dir)})
    write_text(output_dir / "command_log.txt", " ".join(sys.argv) + "\n")
    write_json(output_dir / "reasoning_manifold_summary.json", summary)
    with (output_dir / "reasoning_manifold_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        fieldnames = sorted({key for row in csv_rows for key in row}) or ["method"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
    write_text(
        output_dir / "reasoning_manifold_summary.md",
        "\n".join(
            ["# REMA-Inspired Reasoning Manifold Summary", ""]
            + [
                f"- {method}: separability={metrics['separability_score']:.3f}, failure_distance={metrics['failure_distance_mean']:.3f}, divergence_step={metrics.get('divergence_step')}"
                for method, metrics in sorted(summary["by_method"].items())
            ]
        )
        + "\n",
    )
    write_json(
        output_dir / "manifest.json",
        {
            "run_dir": str(run_dir),
            "artifacts": [
                "config.json",
                "command_log.txt",
                "reasoning_manifold_summary.json",
                "reasoning_manifold_summary.csv",
                "reasoning_manifold_summary.md",
            ],
        },
    )


if __name__ == "__main__":
    main()
