"""Cluster rejected proposals by residual pattern to identify missing operator families.

Reads: rejected_proposals.csv from the residual analyzer
Outputs: missing_operator_clusters.md, missing_operator_clusters.csv
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

INPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/operator_coverage_gap_analysis"


RESIDUAL_TO_OPERATOR = {
    "needs_recolor": "select_then_recolor",
    "needs_translation": "select_then_translate",
    "needs_shape_completion_or_fill": "select_then_complete_shape",
    "needs_spatial_transform": "select_then_reflect_or_rotate",
    "needs_object_crop_or_extract": "select_then_crop_and_normalize",
    "needs_canvas_resize": "select_then_extract_subcanvas",
    "right_property_wrong_output_canvas": "select_then_crop_and_normalize",
    "wrong_object_selected": "relational_color_mapping",
    "needs_multi_step_composition": "multi_step_select_transform_compose",
    "correct": "no_operator_needed",
    "unknown": "unknown",
}

OPERATOR_DIFFICULTY = {
    "select_then_recolor": {
        "difficulty": "low",
        "reuse": "color_transfer.py, position_within_object_recolor.py",
        "verifiable": True,
        "description": "Select objects by property, then recolor based on learned color mapping",
    },
    "select_then_translate": {
        "difficulty": "medium",
        "reuse": "trace_operator_invention.py (copy_to_position)",
        "verifiable": True,
        "description": "Select objects by property, then move them by a learned displacement",
    },
    "select_then_complete_shape": {
        "difficulty": "medium",
        "reuse": "shape_completion.py",
        "verifiable": True,
        "description": "Select objects by property, then complete/extend their shape",
    },
    "select_then_reflect_or_rotate": {
        "difficulty": "medium",
        "reuse": "operators.py (reflect, rotate operators)",
        "verifiable": True,
        "description": "Select objects by property, then apply reflection or rotation",
    },
    "select_then_crop_and_normalize": {
        "difficulty": "low",
        "reuse": "crop_extract.py, reasoning_engine._apply_filter_extract",
        "verifiable": True,
        "description": "Select objects by property, crop to bounding box, normalize canvas",
    },
    "select_then_extract_subcanvas": {
        "difficulty": "medium",
        "reuse": "crop_extract.py",
        "verifiable": True,
        "description": "Select region and extract to smaller canvas",
    },
    "relational_color_mapping": {
        "difficulty": "high",
        "reuse": "correspondence_inference.py",
        "verifiable": True,
        "description": "Map colors between objects based on relational correspondence",
    },
    "multi_step_select_transform_compose": {
        "difficulty": "high",
        "reuse": "adaptive_loop.py iteration",
        "verifiable": True,
        "description": "Chain multiple select-then-transform steps",
    },
}


def load_rejected_proposals(input_dir: str) -> List[Dict[str, Any]]:
    path = os.path.join(input_dir, "rejected_proposals.csv")
    if not os.path.exists(path):
        print(f"  ERROR: {path} not found. Run analyze_rejected_executable_proposals.py first.")
        return []
    records = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["was_executable"] = row.get("was_executable", "False") == "True"
            row["train_consistent"] = row.get("train_consistent", "False") == "True"
            row["diff_cells"] = int(row.get("diff_cells", -1))
            row["diff_fraction"] = float(row.get("diff_fraction", -1))
            row["confidence"] = float(row.get("confidence", 0))
            records.append(row)
    return records


def cluster_by_residual(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    clusters = defaultdict(list)
    for r in records:
        if not r["was_executable"]:
            continue
        residual_class = r.get("residual_class", "unknown")
        operator = RESIDUAL_TO_OPERATOR.get(residual_class, "unknown")
        clusters[operator].append(r)
    return dict(clusters)


def write_cluster_csv(clusters: Dict[str, List[Dict]], output_dir: str):
    path = os.path.join(output_dir, "missing_operator_clusters.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "operator_family", "n_tasks", "n_proposals", "representative_task_ids",
            "failed_operators", "difficulty", "reuse_source", "verifiable",
        ])
        for op, records in sorted(clusters.items(), key=lambda x: -len(x[1])):
            if op in ("no_operator_needed", "unknown"):
                continue
            task_ids = sorted(set(r["task_id"] for r in records))
            failed_ops = sorted(set(r["operator_family"] for r in records if r["operator_family"]))
            info = OPERATOR_DIFFICULTY.get(op, {})
            writer.writerow([
                op,
                len(task_ids),
                len(records),
                ";".join(task_ids[:5]),
                ";".join(failed_ops[:5]),
                info.get("difficulty", "unknown"),
                info.get("reuse", "none"),
                info.get("verifiable", False),
            ])
    print(f"  Wrote {path}")


def write_cluster_md(clusters: Dict[str, List[Dict]], output_dir: str):
    path = os.path.join(output_dir, "missing_operator_clusters.md")
    lines = [
        "# Missing Operator Family Clusters\n\n",
        "Clustered by residual pattern from rejected executable proposals.\n\n",
    ]

    ranked = sorted(
        [(op, recs) for op, recs in clusters.items()
         if op not in ("no_operator_needed", "unknown")],
        key=lambda x: -len(set(r["task_id"] for r in x[1]))
    )

    lines.append("## Priority Ranking\n\n")
    lines.append("| Rank | Operator Family | Tasks | Proposals | Difficulty | Verifiable |\n")
    lines.append("|------|----------------|-------|-----------|------------|------------|\n")
    for i, (op, recs) in enumerate(ranked, 1):
        n_tasks = len(set(r["task_id"] for r in recs))
        info = OPERATOR_DIFFICULTY.get(op, {})
        lines.append(
            f"| {i} | {op} | {n_tasks} | {len(recs)} | "
            f"{info.get('difficulty', '?')} | {info.get('verifiable', '?')} |\n"
        )

    for op, recs in ranked:
        task_ids = sorted(set(r["task_id"] for r in recs))
        failed_ops = sorted(set(r["operator_family"] for r in recs if r["operator_family"]))
        info = OPERATOR_DIFFICULTY.get(op, {})

        lines.append(f"\n## {op}\n\n")
        lines.append(f"- **Tasks**: {len(task_ids)}\n")
        lines.append(f"- **Proposals**: {len(recs)}\n")
        lines.append(f"- **Representative task IDs**: {', '.join(task_ids[:5])}\n")
        lines.append(f"- **Failed operator families**: {', '.join(failed_ops[:5])}\n")
        lines.append(f"- **Estimated difficulty**: {info.get('difficulty', 'unknown')}\n")
        lines.append(f"- **Reuse source**: {info.get('reuse', 'none')}\n")
        lines.append(f"- **Verifiable with ProposalVerifier**: {info.get('verifiable', 'unknown')}\n")
        lines.append(f"- **Description**: {info.get('description', 'N/A')}\n")

        rejection_reasons = defaultdict(int)
        for r in recs:
            rejection_reasons[r.get("rejection_reason", "?")] += 1
        lines.append(f"\n### Rejection breakdown\n\n")
        for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
            lines.append(f"- {reason}: {count}\n")

    if "unknown" in clusters and clusters["unknown"]:
        unk = clusters["unknown"]
        lines.append(f"\n## Unknown / Unclassified\n\n")
        lines.append(f"- Tasks: {len(set(r['task_id'] for r in unk))}\n")
        lines.append(f"- Proposals: {len(unk)}\n")

    lines.append("\n## Implementation Recommendation\n\n")
    lines.append("Based on frequency and difficulty:\n\n")
    for i, (op, recs) in enumerate(ranked[:2], 1):
        n_tasks = len(set(r["task_id"] for r in recs))
        info = OPERATOR_DIFFICULTY.get(op, {})
        lines.append(f"{i}. **{op}** ({n_tasks} tasks, {info.get('difficulty', '?')} difficulty)\n")
        lines.append(f"   - Reuse: {info.get('reuse', 'none')}\n")
    lines.append("\nThese should be implemented first as they cover the most tasks with lowest effort.\n")

    with open(path, "w") as f:
        f.writelines(lines)
    print(f"  Wrote {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=INPUT_DIR)
    parser.add_argument("--output-dir", default=INPUT_DIR)
    args = parser.parse_args()

    print("=" * 60)
    print("  Missing Operator Family Clustering")
    print("=" * 60)

    records = load_rejected_proposals(args.input_dir)
    if not records:
        return

    exec_records = [r for r in records if r["was_executable"]]
    print(f"  Total records: {len(records)}")
    print(f"  Executable records: {len(exec_records)}")

    clusters = cluster_by_residual(records)
    print(f"\n  Clusters found:")
    for op, recs in sorted(clusters.items(), key=lambda x: -len(x[1])):
        n_tasks = len(set(r["task_id"] for r in recs))
        print(f"    {op}: {n_tasks} tasks, {len(recs)} proposals")

    os.makedirs(args.output_dir, exist_ok=True)
    write_cluster_csv(clusters, args.output_dir)
    write_cluster_md(clusters, args.output_dir)

    print(f"\n{'='*60}")
    print(f"  CLUSTERING COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
