#!/usr/bin/env python3.11
"""Analyze the 28 rejected copy-to-position tasks to classify correspondence type.

For each rejected task:
1. Load the actual ARC task.
2. Extract objects using the discriminative property from the gap trace.
3. Use CorrespondenceInferer to propose correspondence rules.
4. Classify the correspondence type needed.
5. Report which rules are proposed, whether they are ambiguous, and whether
   object extraction finds the right number of objects.

Inputs:
  - outputs/operator_reasoning_phase/copy_to_position_real/rejected_tasks.jsonl
  - outputs/operator_gap_analysis/operator_gap_trace.csv
  - outputs/cache_fast/object_traces.jsonl

Outputs:
  - outputs/operator_reasoning_phase/correspondence/correspondence_failure_taxonomy.csv
  - outputs/operator_reasoning_phase/correspondence/correspondence_failure_taxonomy.md
  - outputs/operator_reasoning_phase/correspondence/correspondence_candidate_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Make the project importable
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.arc_adapter import load_arc_tasks
from reasoning_project.trace_operator_invention import (
    _extract_object_masks,
    _find_object_in_output,
)
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _get_property_value,
)
from reasoning_project.correspondence_inference import (
    CorrespondenceInferer,
    CorrespondenceRule,
)

# ───────────────────────────────────────────────────────────────────────────
# Correspondence type taxonomy
# ───────────────────────────────────────────────────────────────────────────

CORRESPONDENCE_TYPES = [
    "same_color",
    "same_shape",
    "same_size",
    "same_topology",
    "nearest_anchor",
    "order_preserving_row",
    "order_preserving_col",
    "ambiguous",
    "perception_failure",
    "not_copy_to_position",
    "unknown",
]


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

def _determine_keep_when_true(task, best_property: str) -> bool:
    """Determine the polarity of the selector property for this task."""
    ex0 = task.train[0]
    inp = ex0.input_grid
    out = ex0.output_grid
    if out is None:
        return True

    objects = _extract_objects_with_properties(inp)
    if len(objects) < 2:
        return True

    true_objs = [o for o in objects if _get_property_value(o, best_property)]
    false_objs = [o for o in objects if not _get_property_value(o, best_property)]

    if not true_objs or not false_objs:
        return True

    true_in_output = sum(
        1 for o in true_objs if np.any(out[o["mask"]] != 0)
    )
    false_in_output = sum(
        1 for o in false_objs if np.any(out[o["mask"]] != 0)
    )

    return false_in_output <= true_in_output


def _classify_correspondence(
    task,
    best_property: str,
    keep_when_true: bool,
    inferer: CorrespondenceInferer,
) -> Dict[str, Any]:
    """Classify the correspondence type needed for a single task.

    Returns a dict with:
      - n_objects, n_kept, n_removed (per first training pair)
      - rules_proposed: list of rule types found
      - best_rule: the best (lowest complexity) unambiguous rule, or None
      - is_ambiguous: whether all proposed rules are ambiguous
      - correspondence_type: final classified type
      - details: additional analysis info
    """
    result: Dict[str, Any] = {
        "n_objects": 0,
        "n_kept": 0,
        "n_removed": 0,
        "rules_proposed": [],
        "best_rule": None,
        "is_ambiguous": False,
        "correspondence_type": "unknown",
        "details": {},
    }

    # Analyze the first training pair for object extraction counts
    train_pairs: List[Tuple[np.ndarray, np.ndarray]] = []
    all_n_objects = []
    all_n_kept = []
    all_n_removed = []

    for ex in task.train:
        inp = ex.input_grid
        out = ex.output_grid
        if out is None:
            continue
        if inp.shape != out.shape:
            result["correspondence_type"] = "not_copy_to_position"
            result["details"]["reason"] = "input/output size mismatch"
            return result

        objects = _extract_objects_with_properties(inp)
        kept = [o for o in objects if _get_property_value(o, best_property) == keep_when_true]
        removed = [o for o in objects if _get_property_value(o, best_property) != keep_when_true]

        all_n_objects.append(len(objects))
        all_n_kept.append(len(kept))
        all_n_removed.append(len(removed))
        train_pairs.append((inp, out))

    if not train_pairs:
        result["correspondence_type"] = "perception_failure"
        result["details"]["reason"] = "no valid training pairs"
        return result

    result["n_objects"] = all_n_objects[0] if all_n_objects else 0
    result["n_kept"] = all_n_kept[0] if all_n_kept else 0
    result["n_removed"] = all_n_removed[0] if all_n_removed else 0

    # Check for perception failures
    if any(nr == 0 for nr in all_n_removed):
        result["correspondence_type"] = "perception_failure"
        result["details"]["reason"] = "no removed objects in some training pairs"
        return result

    if any(nk == 0 for nk in all_n_kept):
        result["correspondence_type"] = "perception_failure"
        result["details"]["reason"] = "no kept objects in some training pairs"
        return result

    # Extract objects from first pair to propose rules
    first_inp = train_pairs[0][0]
    first_objects = _extract_objects_with_properties(first_inp)
    first_removed = [o for o in first_objects if _get_property_value(o, best_property) != keep_when_true]
    first_kept = [o for o in first_objects if _get_property_value(o, best_property) == keep_when_true]

    src_sigs = inferer.extract_object_signatures(first_inp, first_removed)
    tgt_sigs = inferer.extract_object_signatures(first_inp, first_kept)

    candidate_rules = inferer.propose_rules(src_sigs, tgt_sigs)
    result["rules_proposed"] = [r.rule_type for r in candidate_rules]

    if not candidate_rules:
        result["correspondence_type"] = "unknown"
        result["details"]["reason"] = "no correspondence rules proposed"
        return result

    # Score each rule: check ambiguity and displacement consistency
    best_rule: Optional[CorrespondenceRule] = None
    best_score = -1.0
    all_ambiguous = True
    rule_details: List[Dict[str, Any]] = []

    for rule in candidate_rules:
        ambiguity = inferer.detect_ambiguity(rule, train_pairs, best_property)
        is_ambig = ambiguity["is_ambiguous"]

        # Check displacement consistency across training pairs
        disp_consistent = _check_displacement_consistency(
            rule, train_pairs, best_property, keep_when_true, inferer,
        )

        rule_info = {
            "rule_type": rule.rule_type,
            "complexity": rule.complexity,
            "is_ambiguous": is_ambig,
            "displacement_consistent": disp_consistent,
        }
        rule_details.append(rule_info)

        if not is_ambig:
            all_ambiguous = False
            score = 1.0 / (rule.complexity + 1)
            if disp_consistent:
                score += 10.0  # strongly prefer consistent rules
            if score > best_score:
                best_score = score
                best_rule = rule

    result["details"]["rule_details"] = rule_details
    result["is_ambiguous"] = all_ambiguous

    if all_ambiguous:
        result["correspondence_type"] = "ambiguous"
        result["best_rule"] = candidate_rules[0].rule_type if candidate_rules else None
        return result

    if best_rule is not None:
        result["best_rule"] = best_rule.rule_type
        result["correspondence_type"] = best_rule.rule_type
    else:
        # No unambiguous rule found, pick the first rule as a label
        result["best_rule"] = candidate_rules[0].rule_type
        result["correspondence_type"] = "ambiguous"

    return result


def _check_displacement_consistency(
    rule: CorrespondenceRule,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector_property: str,
    keep_when_true: bool,
    inferer: CorrespondenceInferer,
) -> bool:
    """Check whether relative displacements are consistent across all training pairs."""
    all_rel_disps: List[Tuple[int, int]] = []

    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        removed = [o for o in objects if _get_property_value(o, selector_property) != keep_when_true]
        kept = [o for o in objects if _get_property_value(o, selector_property) == keep_when_true]

        if not removed or not kept:
            return False

        src_sigs = inferer.extract_object_signatures(inp, removed)
        tgt_sigs = inferer.extract_object_signatures(inp, kept)

        matcher = inferer._get_matcher(rule.rule_type)
        if matcher is None:
            return False

        matches = matcher(src_sigs, tgt_sigs)
        if matches is None or len(matches) != len(src_sigs):
            return False

        src_masks = _extract_object_masks(inp, removed)
        for si, ti in matches:
            if si >= len(src_masks):
                return False
            mask = src_masks[si]
            result = _find_object_in_output(mask, inp * mask, inp, out, 0)
            if result is None:
                continue

            (dest_r, dest_c), sim = result
            src_rows, src_cols = np.where(mask)
            dest_centroid_r = float(dest_r + np.mean(src_rows) - src_rows.min())
            dest_centroid_c = float(dest_c + np.mean(src_cols) - src_cols.min())
            tgt_centroid = tgt_sigs[ti].centroid
            rel_disp = (
                int(round(dest_centroid_r)) - int(round(tgt_centroid[0])),
                int(round(dest_centroid_c)) - int(round(tgt_centroid[1])),
            )
            all_rel_disps.append(rel_disp)

    if not all_rel_disps:
        return False

    return len(set(all_rel_disps)) == 1


# ───────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze rejected CTP tasks to classify correspondence type.",
    )
    parser.add_argument(
        "--data-dir",
        default="data/arc",
        help="Root directory for ARC dataset (default: data/arc)",
    )
    parser.add_argument(
        "--rejected-tasks",
        default="outputs/operator_reasoning_phase/copy_to_position_real/rejected_tasks.jsonl",
        help="Path to rejected tasks JSONL",
    )
    parser.add_argument(
        "--gap-trace",
        default="outputs/operator_gap_analysis/operator_gap_trace.csv",
        help="Path to operator gap trace CSV",
    )
    parser.add_argument(
        "--object-traces",
        default="outputs/cache_fast/object_traces.jsonl",
        help="Path to object traces JSONL",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/operator_reasoning_phase/correspondence",
        help="Output directory",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / args.data_dir
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Load rejected tasks ----
    rejected_path = project_root / args.rejected_tasks
    rejected: Dict[str, str] = {}
    with open(rejected_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rejected[rec["task_id"]] = rec["reason"]
    print(f"Loaded {len(rejected)} rejected tasks from {rejected_path}")

    # ---- Load gap trace ----
    gap_trace_path = project_root / args.gap_trace
    gap_traces: Dict[str, Dict[str, str]] = {}
    with open(gap_trace_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            gap_traces[row["task_id"]] = dict(row)
    print(f"Loaded {len(gap_traces)} gap traces from {gap_trace_path}")

    # ---- Load object traces (optional enrichment) ----
    object_traces_path = project_root / args.object_traces
    object_traces: Dict[str, Dict[str, Any]] = {}
    if object_traces_path.exists():
        with open(object_traces_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                object_traces[rec["task_id"]] = rec
        print(f"Loaded {len(object_traces)} object traces from {object_traces_path}")
    else:
        print(f"  Object traces not found at {object_traces_path}, skipping.")

    # ---- Load ARC tasks ----
    print(f"Loading ARC tasks from {data_dir} ...")
    all_tasks = load_arc_tasks(str(data_dir), split="training")
    tasks_dict = {t.task_id: t for t in all_tasks}
    print(f"Loaded {len(tasks_dict)} ARC tasks.")

    # ---- Analyze each rejected task ----
    inferer = CorrespondenceInferer()
    taxonomy_rows: List[Dict[str, Any]] = []
    candidate_summary: Dict[str, Any] = {}

    for task_id, rejection_reason in sorted(rejected.items()):
        gap = gap_traces.get(task_id)
        if gap is None:
            print(f"  WARNING: {task_id} not in gap trace CSV, skipping.")
            continue

        task = tasks_dict.get(task_id)
        if task is None:
            print(f"  WARNING: {task_id} not found in ARC dataset, skipping.")
            continue

        best_property = gap.get("best_property", "")
        if not best_property:
            print(f"  WARNING: {task_id} has no best_property, skipping.")
            continue

        keep_when_true = _determine_keep_when_true(task, best_property)

        print(f"  Analyzing {task_id} (prop={best_property}, "
              f"keep={keep_when_true}) ...", end=" ")

        classification = _classify_correspondence(
            task, best_property, keep_when_true, inferer,
        )

        print(f"-> {classification['correspondence_type']} "
              f"(rules={classification['rules_proposed']})")

        taxonomy_rows.append({
            "task_id": task_id,
            "rejection_reason": rejection_reason,
            "n_objects": classification["n_objects"],
            "n_kept": classification["n_kept"],
            "n_removed": classification["n_removed"],
            "rules_proposed": ";".join(classification["rules_proposed"]),
            "best_rule": classification["best_rule"] or "",
            "is_ambiguous": classification["is_ambiguous"],
            "correspondence_type": classification["correspondence_type"],
        })

        candidate_summary[task_id] = {
            "rejection_reason": rejection_reason,
            "best_property": best_property,
            "keep_when_true": keep_when_true,
            "n_objects": classification["n_objects"],
            "n_kept": classification["n_kept"],
            "n_removed": classification["n_removed"],
            "rules_proposed": classification["rules_proposed"],
            "best_rule": classification["best_rule"],
            "is_ambiguous": classification["is_ambiguous"],
            "correspondence_type": classification["correspondence_type"],
            "details": classification["details"],
            "object_trace": object_traces.get(task_id, {}),
        }

    # ---- Write outputs ----

    # 1. CSV
    csv_path = output_dir / "correspondence_failure_taxonomy.csv"
    csv_fields = [
        "task_id", "rejection_reason", "n_objects", "n_kept", "n_removed",
        "rules_proposed", "best_rule", "is_ambiguous", "correspondence_type",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for row in taxonomy_rows:
            writer.writerow(row)
    print(f"\nWrote {len(taxonomy_rows)} rows to {csv_path}")

    # 2. JSON
    json_path = output_dir / "correspondence_candidate_summary.json"
    with open(json_path, "w") as f:
        json.dump(candidate_summary, f, indent=2, default=str)
    print(f"Wrote {json_path}")

    # 3. Markdown summary
    md_path = output_dir / "correspondence_failure_taxonomy.md"
    type_counts = Counter(r["correspondence_type"] for r in taxonomy_rows)
    total = len(taxonomy_rows)

    lines = [
        "# Correspondence Failure Taxonomy",
        "",
        f"**Total rejected tasks analyzed:** {total}",
        "",
        "## Correspondence Type Distribution",
        "",
        "| Correspondence Type | Count | % |",
        "|---|---|---|",
    ]
    for ctype, cnt in type_counts.most_common():
        pct = 100.0 * cnt / max(total, 1)
        lines.append(f"| {ctype} | {cnt} | {pct:.1f}% |")

    # Ambiguity stats
    n_ambiguous = sum(1 for r in taxonomy_rows if r["is_ambiguous"])
    lines.extend([
        "",
        "## Ambiguity Summary",
        "",
        f"- Tasks with all rules ambiguous: {n_ambiguous}/{total} "
        f"({100.0 * n_ambiguous / max(total, 1):.1f}%)",
        f"- Tasks with at least one unambiguous rule: {total - n_ambiguous}/{total}",
    ])

    # Object count distribution
    lines.extend([
        "",
        "## Object Count Distribution",
        "",
        "| Task | Objects | Kept | Removed | Best Rule | Type |",
        "|---|---|---|---|---|---|",
    ])
    for row in taxonomy_rows:
        lines.append(
            f"| {row['task_id']} | {row['n_objects']} | {row['n_kept']} | "
            f"{row['n_removed']} | {row['best_rule']} | "
            f"{row['correspondence_type']} |"
        )

    # Per-task details
    lines.extend([
        "",
        "## Per-Task Details",
        "",
    ])
    for row in taxonomy_rows:
        lines.append(f"### {row['task_id']}")
        lines.append(f"- **Rejection reason:** {row['rejection_reason']}")
        lines.append(f"- **Correspondence type:** {row['correspondence_type']}")
        lines.append(f"- **Objects:** {row['n_objects']} (kept={row['n_kept']}, "
                     f"removed={row['n_removed']})")
        lines.append(f"- **Rules proposed:** {row['rules_proposed']}")
        lines.append(f"- **Best rule:** {row['best_rule']}")
        lines.append(f"- **Ambiguous:** {row['is_ambiguous']}")
        lines.append("")

    # Analysis notes
    lines.extend([
        "## Analysis Notes",
        "",
        "Tasks classified as `same_color`, `same_shape`, `same_size`, or "
        "`same_topology` have a clear unambiguous correspondence rule that "
        "maps each source (removed) object to exactly one target (kept) object. "
        "These are strong candidates for the correspondence-based CTP operator.",
        "",
        "Tasks classified as `nearest_anchor` or `order_preserving_*` require "
        "spatial or ordering-based matching. These are fallback rules when "
        "structural matching (color/shape/size/topology) fails.",
        "",
        "Tasks classified as `ambiguous` have multiple valid correspondence "
        "rules but none that uniquely resolve every source-to-target mapping. "
        "These need either a tie-breaker strategy or a different operator family.",
        "",
        "Tasks classified as `perception_failure` indicate that the object "
        "extraction pipeline does not produce the expected kept/removed split. "
        "These require perception improvements before correspondence can be "
        "attempted.",
        "",
    ])

    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {md_path}")

    # ---- Final summary ----
    print(f"\n{'=' * 60}")
    print("CORRESPONDENCE TYPE SUMMARY")
    print("=" * 60)
    for ctype, cnt in type_counts.most_common():
        print(f"  {ctype:35s} {cnt:3d}  ({100.0 * cnt / max(total, 1):.0f}%)")
    print(f"  {'TOTAL':35s} {total:3d}")
    print(f"  {'AMBIGUOUS':35s} {n_ambiguous:3d}  ({100.0 * n_ambiguous / max(total, 1):.0f}%)")


if __name__ == "__main__":
    main()
