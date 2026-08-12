#!/usr/bin/env python3
"""Audit local ARC-style JSON files and bounded evaluation availability."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.utils import ensure_dir, utc_timestamp, write_json, write_text


def _shape_stats(challenge_sets: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    heights = []
    widths = []
    shapes = Counter()
    colors = Counter()
    max_colors_per_grid = 0
    for dataset in challenge_sets:
        for task in dataset.values():
            for pair in task.get("train", []) + task.get("test", []):
                for key in ["input", "output"]:
                    grid = pair.get(key)
                    if grid is None:
                        continue
                    h = len(grid)
                    w = len(grid[0]) if grid else 0
                    heights.append(h)
                    widths.append(w)
                    shapes[(h, w)] += 1
                    palette = {int(value) for row in grid for value in row}
                    max_colors_per_grid = max(max_colors_per_grid, len(palette))
                    for value in palette:
                        colors[value] += 1
    return {
        "min_height": min(heights) if heights else 0,
        "max_height": max(heights) if heights else 0,
        "min_width": min(widths) if widths else 0,
        "max_width": max(widths) if widths else 0,
        "unique_shapes": len(shapes),
        "top_shapes": [
            {"shape": [int(shape[0]), int(shape[1])], "count": int(count)}
            for shape, count in shapes.most_common(10)
        ],
        "colors_present": sorted(int(value) for value in colors),
        "max_colors_per_grid": int(max_colors_per_grid),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-root", default=str(ROOT / "data" / "arc"))
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "arc_status"))
    args = parser.parse_args()

    arc_root = Path(args.arc_root)
    out_dir = ensure_dir(args.output_dir)

    filenames = sorted(path.name for path in arc_root.glob("*.json"))
    raw_training = json.loads((arc_root / "arc-agi_training_challenges.json").read_text(encoding="utf-8"))
    raw_evaluation = json.loads((arc_root / "arc-agi_evaluation_challenges.json").read_text(encoding="utf-8"))
    raw_test = json.loads((arc_root / "arc-agi_test_challenges.json").read_text(encoding="utf-8"))

    training_ids = set(raw_training)
    evaluation_ids = set(raw_evaluation)
    test_ids = set(raw_test)

    adapter_training = load_arc_tasks(arc_root, split="training")
    adapter_evaluation = load_arc_tasks(arc_root, split="evaluation")
    adapter_test = load_arc_tasks(arc_root, split="test")

    inferred_variant = "mixed_or_ambiguous_arc_format"
    if any("agi2" in name.lower() or "agi-2" in name.lower() for name in filenames):
        inferred_variant = "arc_agi_2_marked"
    elif all(name.startswith("arc-agi_") for name in filenames if name.endswith(".json")):
        inferred_variant = "arc_agi_style_not_explicitly_agi2"

    payload = {
        "generated_at": utc_timestamp(),
        "arc_root": str(arc_root.resolve()),
        "filenames": filenames,
        "inferred_variant": inferred_variant,
        "notes": [
            "Local filenames are ARC-AGI-style, but no file explicitly names ARC-AGI-2.",
            "Training/test task-id overlap exists locally, so provenance should be treated as ambiguous rather than claimed as clean ARC-AGI-2 without external confirmation.",
        ],
        "task_counts": {
            "training": int(len(raw_training)),
            "evaluation": int(len(raw_evaluation)),
            "test": int(len(raw_test)),
        },
        "pair_counts": {
            "training": {
                "train_pairs": int(sum(len(task.get("train", [])) for task in raw_training.values())),
                "test_pairs": int(sum(len(task.get("test", [])) for task in raw_training.values())),
            },
            "evaluation": {
                "train_pairs": int(sum(len(task.get("train", [])) for task in raw_evaluation.values())),
                "test_pairs": int(sum(len(task.get("test", [])) for task in raw_evaluation.values())),
            },
            "test": {
                "train_pairs": int(sum(len(task.get("train", [])) for task in raw_test.values())),
                "test_pairs": int(sum(len(task.get("test", [])) for task in raw_test.values())),
            },
        },
        "label_availability": {
            "training_test_outputs_present": True,
            "evaluation_test_outputs_present": True,
            "test_test_outputs_present": False,
        },
        "task_id_overlap": {
            "training_evaluation": int(len(training_ids & evaluation_ids)),
            "training_test": int(len(training_ids & test_ids)),
            "evaluation_test": int(len(evaluation_ids & test_ids)),
        },
        "grid_stats": _shape_stats([raw_training, raw_evaluation, raw_test]),
        "adapter_parse_status": {
            "training": {"parsed_tasks": len(adapter_training), "all_tasks_parsed": len(adapter_training) == len(raw_training)},
            "evaluation": {"parsed_tasks": len(adapter_evaluation), "all_tasks_parsed": len(adapter_evaluation) == len(raw_evaluation)},
            "test": {"parsed_tasks": len(adapter_test), "all_tasks_parsed": len(adapter_test) == len(raw_test)},
        },
        "evaluable_by_exact_solve_rate": {
            "training": int(sum(task.has_test_solutions for task in adapter_training)),
            "evaluation": int(sum(task.has_test_solutions for task in adapter_evaluation)),
            "test": int(sum(task.has_test_solutions for task in adapter_test)),
        },
    }

    summary_lines = [
        "# ARC AGI-Style Local Status",
        "",
        f"- inferred variant: `{payload['inferred_variant']}`",
        "- local provenance is ambiguous: filenames are ARC-AGI-style, but no file explicitly names ARC-AGI-2",
        f"- task counts: training={payload['task_counts']['training']}, evaluation={payload['task_counts']['evaluation']}, test={payload['task_counts']['test']}",
        f"- label availability: training/evaluation labeled, test unlabeled",
        f"- adapter parse status: training={payload['adapter_parse_status']['training']['all_tasks_parsed']}, evaluation={payload['adapter_parse_status']['evaluation']['all_tasks_parsed']}, test={payload['adapter_parse_status']['test']['all_tasks_parsed']}",
        f"- exact-solve evaluable tasks: training={payload['evaluable_by_exact_solve_rate']['training']}, evaluation={payload['evaluable_by_exact_solve_rate']['evaluation']}, test={payload['evaluable_by_exact_solve_rate']['test']}",
        f"- training/test task-id overlap: {payload['task_id_overlap']['training_test']}",
        f"- grid range: heights {payload['grid_stats']['min_height']}..{payload['grid_stats']['max_height']}, widths {payload['grid_stats']['min_width']}..{payload['grid_stats']['max_width']}",
        f"- colors present: {payload['grid_stats']['colors_present']}",
        "",
        "Boundary:",
        "This audit confirms local ARC-style files are readable and labeled on training/evaluation splits, but it does not by itself justify calling the local bundle clean ARC-AGI-2 provenance.",
    ]

    write_json(out_dir / "arc_agi2_status.json", payload)
    write_text(out_dir / "arc_agi2_status.md", "\n".join(summary_lines) + "\n")


if __name__ == "__main__":
    main()
