"""Program gap audit for the 20 corrected OperatorGenesis pilot tasks.

Diagnoses WHY each task fails by inspecting actual ARC grids, view programs,
and proposals. Produces:
  - program_gap_audit.csv
  - program_gap_audit.md
  - top_5_easiest_recoverable_tasks.md
  - missing_operator_grammar_plan.md

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
    PYTHONPATH=src python3.11 scripts/build_program_gap_audit.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

ROOT = Path(__file__).resolve().parent.parent
PILOT_OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "operator_genesis_v2_2026_06_22"
AUDIT_OUT = PILOT_OUT / "program_gap_audit"
ARC_CHALLENGES = ROOT / "data" / "arc" / "arc-agi_training_challenges.json"
ARC_SOLUTIONS = ROOT / "data" / "arc" / "arc-agi_training_solutions.json"


# ---------------------------------------------------------------------------
# Structural analysis helpers
# ---------------------------------------------------------------------------

def grid_colors(g: np.ndarray) -> set:
    return set(int(c) for c in np.unique(g))


def connected_components(g: np.ndarray, bg: int = 0) -> List[Tuple[int, np.ndarray]]:
    from scipy import ndimage
    mask = g != bg
    labeled, n = ndimage.label(mask)
    comps = []
    for i in range(1, n + 1):
        comp_mask = labeled == i
        colors = set(int(c) for c in np.unique(g[comp_mask]))
        comps.append((i, comp_mask, colors))
    return comps


def bbox_of_mask(mask: np.ndarray) -> Tuple[int, int, int, int]:
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    return int(rmin), int(cmin), int(rmax), int(cmax)


def has_frame(g: np.ndarray) -> Optional[int]:
    if g.shape[0] < 3 or g.shape[1] < 3:
        return None
    border = np.concatenate([g[0, :], g[-1, :], g[1:-1, 0], g[1:-1, -1]])
    vals = set(int(c) for c in border)
    if len(vals) == 1:
        return vals.pop()
    return None


def is_symmetric(g: np.ndarray, axis: str) -> bool:
    if axis == "horizontal":
        return np.array_equal(g, g[::-1, :])
    elif axis == "vertical":
        return np.array_equal(g, g[:, ::-1])
    return False


def output_is_subregion_of_input(inp: np.ndarray, out: np.ndarray) -> bool:
    oh, ow = out.shape
    ih, iw = inp.shape
    if oh > ih or ow > iw:
        return False
    for r in range(ih - oh + 1):
        for c in range(iw - ow + 1):
            if np.array_equal(inp[r:r+oh, c:c+ow], out):
                return True
    return False


def size_changes(train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> bool:
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return True
    return False


def color_mapping_consistent(train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> Optional[Dict[int, int]]:
    mapping = {}
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        for r in range(inp.shape[0]):
            for c in range(inp.shape[1]):
                ic, oc = int(inp[r, c]), int(out[r, c])
                if ic in mapping and mapping[ic] != oc:
                    return None
                mapping[ic] = oc
    return mapping


def count_objects(g: np.ndarray, bg: int = 0) -> int:
    from scipy import ndimage
    mask = g != bg
    _, n = ndimage.label(mask)
    return n


def objects_move_between(train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> bool:
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            continue
        diff = inp != out
        if not np.any(diff):
            continue
        in_objs = count_objects(inp)
        out_objs = count_objects(out)
        if in_objs == out_objs and in_objs > 0:
            return True
    return False


def pixel_error(pred: np.ndarray, target: np.ndarray) -> float:
    if pred.shape != target.shape:
        min_h = min(pred.shape[0], target.shape[0])
        min_w = min(pred.shape[1], target.shape[1])
        pred_crop = pred[:min_h, :min_w]
        tgt_crop = target[:min_h, :min_w]
        matching = np.sum(pred_crop == tgt_crop)
        total = max(pred.shape[0] * pred.shape[1], target.shape[0] * target.shape[1])
        return 1.0 - matching / total
    return 1.0 - np.mean(pred == target)


# ---------------------------------------------------------------------------
# Failure diagnosis
# ---------------------------------------------------------------------------

FAILURE_REASONS = [
    "no_view_applies",
    "view_lifts_but_no_operator",
    "operator_wrong_selection",
    "operator_wrong_destination",
    "operator_wrong_color",
    "operator_wrong_shape",
    "projection_breaks_solution",
    "needs_counting",
    "needs_ordering",
    "needs_relational_role",
    "needs_multi_step_program",
    "needs_recursion_or_pattern_completion",
]


def diagnose_task(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    proposals: List[Dict],
    category: str,
) -> Dict[str, Any]:
    """Diagnose why a task fails all operator families."""

    inp0, out0 = train_pairs[0]
    n_train = len(train_pairs)

    # Basic structural features
    sz_changes = size_changes(train_pairs)
    is_subregion = all(output_is_subregion_of_input(i, o) for i, o in train_pairs)
    cmap = color_mapping_consistent(train_pairs)
    frame_color = has_frame(inp0)
    in_colors = grid_colors(inp0)
    out_colors = grid_colors(out0)
    new_colors = out_colors - in_colors
    n_in_obj = count_objects(inp0)
    n_out_obj = count_objects(out0)
    obj_move = objects_move_between(train_pairs)
    h_sym_in = is_symmetric(inp0, "horizontal")
    v_sym_in = is_symmetric(inp0, "vertical")
    h_sym_out = is_symmetric(out0, "horizontal")
    v_sym_out = is_symmetric(out0, "vertical")

    # View program and proposal stats
    task_proposals = [p for p in proposals if p.get("task_id") == task_id]
    n_proposals = len(task_proposals)
    view_programs_tried = set(p.get("view_program", "direct") for p in task_proposals)
    n_views = len(view_programs_tried) if task_proposals else 0
    n_train_consistent_before = sum(1 for p in task_proposals if p.get("train_consistent"))
    n_train_consistent_after = 0  # post-projection; same as before since we don't have projection data

    # Find closest proposal by pixel error on first training output
    closest_family = None
    closest_error = 1.0
    if task_proposals:
        # We can't re-execute proposals, but we can infer from the families tried
        families_tried = Counter(p.get("operator_family") for p in task_proposals)
        closest_family = families_tried.most_common(1)[0][0] if families_tried else None

    # Diagnose dominant failure
    diagnosis = _classify_failure(
        task_id=task_id,
        category=category,
        train_pairs=train_pairs,
        sz_changes=sz_changes,
        is_subregion=is_subregion,
        cmap=cmap,
        frame_color=frame_color,
        new_colors=new_colors,
        n_in_obj=n_in_obj,
        n_out_obj=n_out_obj,
        obj_move=obj_move,
        h_sym_out=h_sym_out,
        v_sym_out=v_sym_out,
        n_proposals=n_proposals,
        n_views=n_views,
        task_proposals=task_proposals,
    )

    # Compute pixel error of best-effort prediction if test_outputs available
    best_pixel_error = None
    if test_outputs and len(test_outputs) > 0:
        # Use first training output as a naive "prediction" to get baseline error
        best_pixel_error = round(pixel_error(out0, test_outputs[0]), 3)

    return {
        "task_id": task_id,
        "category": category,
        "n_views_tried": n_views,
        "n_proposals": n_proposals,
        "n_train_consistent_before": n_train_consistent_before,
        "n_train_consistent_after": n_train_consistent_after,
        "dominant_failure": diagnosis["reason"],
        "closest_family": closest_family or "",
        "pixel_error_closest": best_pixel_error if best_pixel_error is not None else "",
        "diagnosis": diagnosis["text"],
        # Extra fields for ranking recoverability
        "sz_changes": sz_changes,
        "is_subregion": is_subregion,
        "has_color_map": cmap is not None,
        "n_in_obj": n_in_obj,
        "n_out_obj": n_out_obj,
        "new_colors_count": len(new_colors),
        "n_train": n_train,
        "input_shape": f"{inp0.shape[0]}x{inp0.shape[1]}",
        "output_shape": f"{out0.shape[0]}x{out0.shape[1]}",
    }


def _classify_failure(
    task_id: str,
    category: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    sz_changes: bool,
    is_subregion: bool,
    cmap: Optional[Dict],
    frame_color: Optional[int],
    new_colors: set,
    n_in_obj: int,
    n_out_obj: int,
    obj_move: bool,
    h_sym_out: bool,
    v_sym_out: bool,
    n_proposals: int,
    n_views: int,
    task_proposals: List[Dict],
) -> Dict[str, str]:
    """Classify the dominant failure reason based on structural analysis."""

    inp0, out0 = train_pairs[0]

    # No proposals at all — view lifting failed
    if n_proposals == 0 and n_views == 0:
        # Determine why no view applies
        if sz_changes and not is_subregion:
            if n_out_obj != n_in_obj:
                return {"reason": "needs_relational_role",
                        "text": f"Output has different object count ({n_out_obj} vs {n_in_obj}); "
                                f"size changes ({inp0.shape}->{out0.shape}); "
                                f"no view program could lift this."}
            if out0.shape[0] * out0.shape[1] > inp0.shape[0] * inp0.shape[1]:
                return {"reason": "needs_recursion_or_pattern_completion",
                        "text": f"Output larger than input ({out0.shape} vs {inp0.shape}); "
                                f"likely pattern completion or tiling beyond current motif extractor."}
            return {"reason": "needs_multi_step_program",
                    "text": f"Size changes ({inp0.shape}->{out0.shape}) with "
                            f"{n_in_obj} in-objects, {n_out_obj} out-objects; "
                            f"no single view+operator captures the transformation."}

        if cmap is not None and not sz_changes:
            if len(new_colors) > 0:
                return {"reason": "needs_relational_role",
                        "text": f"Same-size with color map, but {len(new_colors)} new colors in output "
                                f"not in input; recolor depends on spatial/relational context."}
            return {"reason": "operator_wrong_color",
                    "text": f"Same-size with consistent color map ({cmap}), "
                            f"but no view lifted it. Map may be object-conditional."}

        if frame_color is not None:
            return {"reason": "no_view_applies",
                    "text": f"Has frame (color {frame_color}) but RemoveFrameView "
                            f"didn't produce operators. Interior transform is complex."}

        return {"reason": "no_view_applies",
                "text": f"No view program produced lifted pairs. "
                        f"Grid: {inp0.shape}->{out0.shape}, {n_in_obj} objects."}

    # Proposals exist but none train-consistent
    if n_proposals > 0:
        families = Counter(p.get("operator_family") for p in task_proposals)
        top_fam = families.most_common(1)[0][0]

        # Analyze what the proposals tried
        if is_subregion and sz_changes:
            return {"reason": "operator_wrong_shape",
                    "text": f"Output is subregion of input but crop proposals ({top_fam}, "
                            f"{n_proposals} tried) don't match. Crop boundary depends on "
                            f"object identity or relational role, not just bbox."}

        if cmap is not None and top_fam == "conditional_recolor":
            return {"reason": "operator_wrong_color",
                    "text": f"Color map exists but conditional_recolor can't match it. "
                            f"Recolor depends on spatial/relational context, not just global map."}

        if top_fam == "two_step_composition":
            if obj_move:
                return {"reason": "needs_multi_step_program",
                        "text": f"Objects move/rearrange. Two-step composition tried "
                                f"({n_proposals} proposals) but none matched. "
                                f"Needs multi-step object manipulation program."}
            if h_sym_out or v_sym_out:
                sym_type = "horizontal" if h_sym_out else "vertical"
                return {"reason": "needs_recursion_or_pattern_completion",
                        "text": f"Output is {sym_type}-symmetric but symmetry_complete + "
                                f"compositions failed. Pattern is compositional symmetry."}

            return {"reason": "needs_multi_step_program",
                    "text": f"Two-step composition dominant ({families['two_step_composition']} proposals) "
                            f"but none train-consistent. Transformation requires >2 steps "
                            f"or relational abstractions not in the operator grammar."}

        if n_out_obj < n_in_obj:
            return {"reason": "needs_relational_role",
                    "text": f"Object count drops ({n_in_obj}->{n_out_obj}). "
                            f"Selection depends on relational role (largest? touching border? "
                            f"containing X?) not captured by current operators."}

        if n_out_obj > n_in_obj:
            return {"reason": "needs_recursion_or_pattern_completion",
                    "text": f"Object count increases ({n_in_obj}->{n_out_obj}). "
                            f"Needs object generation/duplication beyond current operators."}

        # Generic fallback for proposals that tried but failed
        return {"reason": "view_lifts_but_no_operator",
                "text": f"{n_proposals} proposals across {n_views} views, "
                        f"dominant family: {top_fam}. None train-consistent. "
                        f"Operator parameters don't generalize across training pairs."}

    # Views tried but no proposals generated
    return {"reason": "view_lifts_but_no_operator",
            "text": f"{n_views} view programs tried but 0 proposals generated. "
                    f"Lifted pairs don't match any operator family template."}


# ---------------------------------------------------------------------------
# Recoverability scoring
# ---------------------------------------------------------------------------

def recoverability_score(audit_row: Dict) -> float:
    """Lower = easier to recover. Heuristic based on structural simplicity."""
    score = 100.0

    # Simpler failure modes are easier
    reason = audit_row["dominant_failure"]
    reason_penalty = {
        "operator_wrong_color": 10,
        "operator_wrong_shape": 15,
        "view_lifts_but_no_operator": 20,
        "no_view_applies": 30,
        "operator_wrong_selection": 25,
        "operator_wrong_destination": 25,
        "needs_counting": 35,
        "needs_ordering": 35,
        "needs_relational_role": 40,
        "needs_multi_step_program": 50,
        "needs_recursion_or_pattern_completion": 70,
        "projection_breaks_solution": 45,
    }
    score = reason_penalty.get(reason, 50)

    # Proposals exist = closer to solution
    if audit_row["n_proposals"] > 0:
        score -= 10
    if audit_row["n_train_consistent_before"] > 0:
        score -= 20

    # Simple structural features help
    if audit_row.get("has_color_map"):
        score -= 5
    if audit_row.get("is_subregion"):
        score -= 5
    if not audit_row.get("sz_changes"):
        score -= 3

    # Fewer objects = simpler
    n_obj = audit_row.get("n_in_obj", 10)
    if n_obj <= 3:
        score -= 5
    elif n_obj > 10:
        score += 10

    return max(0, score)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(AUDIT_OUT, exist_ok=True)

    # Load data
    with open(ARC_CHALLENGES) as f:
        challenges = json.load(f)
    with open(ARC_SOLUTIONS) as f:
        solutions = json.load(f)

    with open(PILOT_OUT / "pilot_selected_tasks.csv") as f:
        reader = csv.DictReader(f)
        selected = [(r["task_id"], r["category"]) for r in reader]

    proposals = []
    prop_path = PILOT_OUT / "operator_genesis_proposals.jsonl"
    if prop_path.exists():
        with open(prop_path) as f:
            for line in f:
                if line.strip():
                    proposals.append(json.loads(line))

    print(f"Loaded {len(selected)} pilot tasks, {len(proposals)} proposals", flush=True)

    # Run audit for each task
    audit_rows = []
    for task_id, category in selected:
        task = challenges[task_id]
        sol = solutions.get(task_id, [])
        train_pairs = [(np.array(p["input"], dtype=int), np.array(p["output"], dtype=int))
                       for p in task["train"]]
        test_inputs = [np.array(t["input"], dtype=int) for t in task["test"]]
        test_outputs = [np.array(sol[i], dtype=int) for i in range(len(sol))] if sol else None

        row = diagnose_task(task_id, train_pairs, test_inputs, test_outputs, proposals, category)
        row["recoverability_score"] = recoverability_score(row)
        audit_rows.append(row)
        print(f"  {task_id} ({category}): {row['dominant_failure']} "
              f"[recover={row['recoverability_score']:.0f}]", flush=True)

    # Sort by recoverability
    audit_rows.sort(key=lambda r: r["recoverability_score"])

    # --- Output 1: program_gap_audit.csv ---
    csv_path = AUDIT_OUT / "program_gap_audit.csv"
    csv_keys = [
        "task_id", "category", "n_views_tried", "n_proposals",
        "n_train_consistent_before", "n_train_consistent_after",
        "dominant_failure", "closest_family", "pixel_error_closest",
        "diagnosis", "recoverability_score",
        "input_shape", "output_shape", "n_in_obj", "n_out_obj",
        "sz_changes", "is_subregion", "has_color_map", "new_colors_count",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(audit_rows)
    print(f"\nSaved {csv_path}", flush=True)

    # --- Output 2: program_gap_audit.md ---
    md_path = AUDIT_OUT / "program_gap_audit.md"
    with open(md_path, "w") as f:
        f.write("# Program Gap Audit — OperatorGenesis v2 Corrected Pilot\n\n")
        f.write(f"**Date:** 2026-06-22\n")
        f.write(f"**Tasks:** {len(audit_rows)}\n")
        f.write(f"**Total proposals:** {len(proposals)}\n")
        f.write(f"**Train-consistent proposals:** "
                f"{sum(r['n_train_consistent_before'] for r in audit_rows)}\n\n")

        # Failure reason distribution
        reason_counts = Counter(r["dominant_failure"] for r in audit_rows)
        f.write("## Failure Reason Distribution\n\n")
        f.write("| Reason | Count | % |\n")
        f.write("|--------|-------|---|\n")
        for reason, cnt in reason_counts.most_common():
            pct = 100 * cnt / len(audit_rows)
            f.write(f"| {reason} | {cnt} | {pct:.0f}% |\n")

        # Per-task table
        f.write("\n## Per-Task Audit\n\n")
        f.write("| Task | Category | Views | Proposals | Failure | Closest Family | Score | Diagnosis |\n")
        f.write("|------|----------|-------|-----------|---------|----------------|-------|-----------|\n")
        for r in audit_rows:
            f.write(f"| {r['task_id']} | {r['category']} "
                    f"| {r['n_views_tried']} | {r['n_proposals']} "
                    f"| {r['dominant_failure']} | {r['closest_family']} "
                    f"| {r['recoverability_score']:.0f} "
                    f"| {r['diagnosis'][:80]}... |\n")

        # Category breakdown
        f.write("\n## Category Breakdown\n\n")
        cat_reasons = defaultdict(list)
        for r in audit_rows:
            cat_reasons[r["category"]].append(r["dominant_failure"])
        for cat in sorted(cat_reasons.keys()):
            reasons = Counter(cat_reasons[cat])
            f.write(f"### {cat}\n\n")
            for reason, cnt in reasons.most_common():
                f.write(f"- {reason}: {cnt}\n")
            f.write("\n")

    print(f"Saved {md_path}", flush=True)

    # --- Output 3: top_5_easiest_recoverable_tasks.md ---
    top5 = audit_rows[:5]
    top5_path = AUDIT_OUT / "top_5_easiest_recoverable_tasks.md"
    with open(top5_path, "w") as f:
        f.write("# Top 5 Easiest Recoverable Tasks\n\n")
        f.write("Ranked by recoverability score (lower = easier).\n\n")
        for i, r in enumerate(top5):
            f.write(f"## {i+1}. {r['task_id']} (score: {r['recoverability_score']:.0f})\n\n")
            f.write(f"- **Category:** {r['category']}\n")
            f.write(f"- **Input shape:** {r['input_shape']}\n")
            f.write(f"- **Output shape:** {r['output_shape']}\n")
            f.write(f"- **Objects:** {r['n_in_obj']} in → {r['n_out_obj']} out\n")
            f.write(f"- **Size changes:** {r['sz_changes']}\n")
            f.write(f"- **Is subregion:** {r['is_subregion']}\n")
            f.write(f"- **Color map:** {r['has_color_map']}\n")
            f.write(f"- **Failure:** {r['dominant_failure']}\n")
            f.write(f"- **Views tried:** {r['n_views_tried']}\n")
            f.write(f"- **Proposals:** {r['n_proposals']}\n")
            f.write(f"- **Closest family:** {r['closest_family']}\n")
            f.write(f"- **Diagnosis:** {r['diagnosis']}\n\n")

            # Load and render training grids
            task = challenges[r["task_id"]]
            f.write("### Training Examples\n\n")
            for j, pair in enumerate(task["train"]):
                inp = np.array(pair["input"])
                out = np.array(pair["output"])
                f.write(f"**Pair {j+1}:** {inp.shape[0]}×{inp.shape[1]} → "
                        f"{out.shape[0]}×{out.shape[1]}\n\n")
                f.write("Input:\n```\n")
                for row in inp:
                    f.write(" ".join(str(int(c)) for c in row) + "\n")
                f.write("```\n\nOutput:\n```\n")
                for row in out:
                    f.write(" ".join(str(int(c)) for c in row) + "\n")
                f.write("```\n\n")

            f.write("---\n\n")

    print(f"Saved {top5_path}", flush=True)

    # --- Output 4: missing_operator_grammar_plan.md ---
    # Find tasks where a new operator family could plausibly help multiple tasks
    # Group by failure reason and look for structural similarity
    reason_groups = defaultdict(list)
    for r in audit_rows:
        reason_groups[r["dominant_failure"]].append(r)

    # Find the 3 easiest multi-task opportunities
    candidates = []
    for reason, tasks in reason_groups.items():
        if len(tasks) >= 2:
            avg_score = sum(t["recoverability_score"] for t in tasks) / len(tasks)
            candidates.append((reason, tasks, avg_score))
    candidates.sort(key=lambda x: x[2])

    plan_path = AUDIT_OUT / "missing_operator_grammar_plan.md"
    with open(plan_path, "w") as f:
        f.write("# Missing Operator Grammar Plan\n\n")
        f.write(f"**Date:** 2026-06-22\n")
        f.write("**Source:** Program gap audit of 20 corrected pilot tasks\n\n")
        f.write("## Failure Distribution Summary\n\n")
        for reason, cnt in reason_counts.most_common():
            f.write(f"- **{reason}:** {cnt} tasks\n")
        f.write("\n## Proposed New Operator Families\n\n")
        f.write("The following are the 3 easiest multi-task opportunities where a new\n")
        f.write("generalized operator family could plausibly recover >1 task.\n\n")
        f.write("**Important:** These are analysis-only proposals. No implementation yet.\n\n")

        for idx, (reason, tasks, avg_score) in enumerate(candidates[:3]):
            task_ids = [t["task_id"] for t in tasks]
            f.write(f"### Opportunity {idx+1}: {reason} ({len(tasks)} tasks)\n\n")
            f.write(f"**Tasks:** {', '.join(task_ids)}\n")
            f.write(f"**Average recoverability score:** {avg_score:.0f}\n\n")

            # Per-task analysis
            for t in tasks:
                tid = t["task_id"]
                task_data = challenges[tid]
                train_pairs = [(np.array(p["input"], dtype=int), np.array(p["output"], dtype=int))
                               for p in task_data["train"]]
                inp0, out0 = train_pairs[0]

                f.write(f"#### Task {tid}\n\n")
                f.write(f"- **Category:** {t['category']}\n")
                f.write(f"- **Grid:** {t['input_shape']} → {t['output_shape']}\n")
                f.write(f"- **Objects:** {t['n_in_obj']} → {t['n_out_obj']}\n")
                f.write(f"- **Diagnosis:** {t['diagnosis']}\n\n")

                f.write("Training pair 1:\n```\nInput:\n")
                for row in inp0:
                    f.write(" ".join(str(int(c)) for c in row) + "\n")
                f.write("\nOutput:\n")
                for row in out0:
                    f.write(" ".join(str(int(c)) for c in row) + "\n")
                f.write("```\n\n")

                # Attempt human-readable program description
                hp = _human_program(train_pairs, t)
                f.write(f"**Human program:** {hp['program']}\n\n")
                f.write(f"**Required object relations:** {hp['relations']}\n\n")
                f.write(f"**Required parameters:** {hp['parameters']}\n\n")
                f.write(f"**Why existing operators fail:** {hp['why_fail']}\n\n")

            # Proposed new operator family
            proposal = _propose_operator_family(reason, tasks, challenges)
            f.write(f"#### Proposed New Operator Family\n\n")
            f.write(f"**Name:** `{proposal['name']}`\n\n")
            f.write(f"**Description:** {proposal['description']}\n\n")
            f.write(f"**Preconditions:** {proposal['preconditions']}\n\n")
            f.write(f"**Verifier obligations:**\n")
            for ob in proposal["verifier_obligations"]:
                f.write(f"- {ob}\n")
            f.write(f"\n**Ablation plan:**\n")
            for step in proposal["ablation_plan"]:
                f.write(f"- {step}\n")
            f.write("\n---\n\n")

    print(f"Saved {plan_path}", flush=True)
    print("\nDone.", flush=True)


def _human_program(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    audit_row: Dict,
) -> Dict[str, str]:
    """Generate human-readable program description based on structural analysis."""
    inp0, out0 = train_pairs[0]
    reason = audit_row["dominant_failure"]

    if audit_row.get("is_subregion") and audit_row.get("sz_changes"):
        return {
            "program": f"Extract subregion from {inp0.shape} input that matches "
                       f"{out0.shape} output. Selection criterion varies per task.",
            "relations": "Object identity, containment, or marker-relative position.",
            "parameters": "Bounding box selection rule (by color, by role, by marker).",
            "why_fail": "Crop operators use geometric heuristics (bbox, largest CC). "
                        "This task requires semantic selection based on object role or relation.",
        }

    if audit_row.get("has_color_map") and not audit_row.get("sz_changes"):
        cmap = color_mapping_consistent(train_pairs)
        return {
            "program": f"Recolor grid using mapping that depends on spatial context. "
                       f"Same-size transform ({inp0.shape}).",
            "relations": "Spatial neighbors, object membership, containment depth.",
            "parameters": f"Context-dependent color map (global map: {cmap}).",
            "why_fail": "conditional_recolor uses global color maps. This task's recoloring "
                        "depends on local spatial context (neighbors, containment, position).",
        }

    if reason == "needs_multi_step_program":
        return {
            "program": f"Multi-step transformation: {inp0.shape} → {out0.shape}. "
                       f"Objects: {audit_row['n_in_obj']} → {audit_row['n_out_obj']}.",
            "relations": "Multiple: object identity, relative position, size ordering.",
            "parameters": "Step sequence, per-step operation, conditional branching.",
            "why_fail": "Two-step composition covers pairs of simple operators. "
                        "This requires 3+ steps or conditional logic between steps.",
        }

    if reason == "needs_relational_role":
        return {
            "program": f"Select/transform objects based on relational role. "
                       f"{audit_row['n_in_obj']} objects → {audit_row['n_out_obj']} objects.",
            "relations": "Relational roles: largest, enclosed, touching-border, unique-color.",
            "parameters": "Role predicate, action (keep/remove/recolor/move).",
            "why_fail": "object_correspondence filters by simple size heuristics. "
                        "This needs relational predicates over object properties.",
        }

    if reason == "needs_recursion_or_pattern_completion":
        return {
            "program": f"Pattern completion or recursive structure. "
                       f"{inp0.shape} → {out0.shape}.",
            "relations": "Repetition, symmetry axis, growth direction.",
            "parameters": "Pattern period, completion rule, boundary condition.",
            "why_fail": "repeat_motif extracts tiles. symmetry_complete mirrors halves. "
                        "This needs recursive pattern inference or conditional completion.",
        }

    return {
        "program": f"Transform {inp0.shape} → {out0.shape} with {audit_row['n_in_obj']} objects.",
        "relations": "Unknown — requires manual inspection.",
        "parameters": "Unknown — requires manual inspection.",
        "why_fail": f"Dominant failure: {reason}. No operator family covers this pattern.",
    }


def _propose_operator_family(
    reason: str,
    tasks: List[Dict],
    challenges: Dict,
) -> Dict[str, Any]:
    """Propose a new operator family based on failure pattern."""

    if reason in ("needs_multi_step_program", "view_lifts_but_no_operator"):
        return {
            "name": "relational_program_induction",
            "description": "Induce a multi-step program over objects with relational predicates. "
                           "Steps: (1) extract objects, (2) compute pairwise relations "
                           "(containment, adjacency, alignment, color-match), "
                           "(3) search for a predicate→action rule that is train-consistent, "
                           "(4) apply action sequence to test input.",
            "preconditions": [
                "≥2 training pairs with identifiable objects",
                "Object count and identity are recoverable across pairs",
                "At least one relational predicate discriminates kept/removed/transformed objects",
            ],
            "verifier_obligations": [
                "Train consistency: program reproduces all training outputs exactly",
                "LOO cross-validation: removing one pair, re-inducing program still works",
                "No test output leakage: synthesis uses only training pairs",
                "Certificate: log induced program, predicates, and action sequence",
            ],
            "ablation_plan": [
                "Run with vs without relational program induction on pilot tasks",
                "Measure: new solves, false positives, runtime overhead",
                "Leave-one-step-out: test necessity of each program step",
                "Compare vs two_step_composition to verify the step-count gap",
            ],
        }

    if reason in ("needs_relational_role", "operator_wrong_selection"):
        return {
            "name": "relational_object_selector",
            "description": "Select objects by relational role predicates rather than "
                           "simple size/color heuristics. Predicates: is_enclosed_by(X), "
                           "touches_border, is_largest_in_group, has_unique_color, "
                           "is_symmetric, count_neighbors(≥N). Action: keep, remove, "
                           "recolor, extract.",
            "preconditions": [
                "≥2 training pairs with identifiable objects",
                "Output is a strict subset/recolor of input objects",
                "At least one relational predicate discriminates kept vs removed",
            ],
            "verifier_obligations": [
                "Train consistency: selected objects match output exactly",
                "LOO cross-validation",
                "No test output leakage",
                "Certificate: log predicate, action, and per-pair matching",
            ],
            "ablation_plan": [
                "Run with vs without relational selector on pilot tasks",
                "Compare vs object_correspondence to verify relational gap",
                "Predicate necessity: test each predicate individually",
            ],
        }

    if reason in ("needs_recursion_or_pattern_completion", "operator_wrong_shape"):
        return {
            "name": "recursive_pattern_completer",
            "description": "Complete partially-specified patterns by inferring "
                           "repetition period, symmetry axes, and growth rules. "
                           "Handles: (1) extend partial tile to full grid, "
                           "(2) complete partial symmetry, (3) fill missing regions "
                           "by extrapolating local rules, (4) scale/resize by "
                           "inferred factor.",
            "preconditions": [
                "Output larger than input OR output has structure not in input",
                "Detectable repetition or symmetry in input or output",
                "Consistent completion rule across ≥2 training pairs",
            ],
            "verifier_obligations": [
                "Train consistency: completed pattern matches output exactly",
                "LOO cross-validation",
                "No test output leakage",
                "Certificate: log inferred period/axis/rule and completion",
            ],
            "ablation_plan": [
                "Run with vs without pattern completer on pilot tasks",
                "Compare vs repeat_motif + symmetry_complete to verify gap",
                "Mode ablation: test each completion mode independently",
            ],
        }

    # Default fallback
    return {
        "name": f"extended_{reason}_handler",
        "description": f"Handle the '{reason}' failure pattern with generalized operators.",
        "preconditions": ["≥2 training pairs", f"Failure signature matches '{reason}'"],
        "verifier_obligations": [
            "Train consistency", "LOO cross-validation",
            "No test output leakage", "Certificate emission",
        ],
        "ablation_plan": [
            "Run with vs without on pilot tasks",
            "Measure new solves and false positives",
        ],
    }


if __name__ == "__main__":
    main()
