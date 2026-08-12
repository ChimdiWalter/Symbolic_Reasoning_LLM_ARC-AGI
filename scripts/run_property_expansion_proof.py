"""Property expansion proof-of-mechanism experiment.

Creates synthetic ARC-like tasks where the discriminative property is
genuinely outside the base property language. Tests whether
PropertyExpansionEngine (via SelectorInventor) can find the property
when base search cannot.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    PYTHONPATH=src python3.11 scripts/run_property_expansion_proof.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _add_relational_properties as _add_rel_props_raw,
    _classify_kept_removed,
    _find_discriminative_property_extended,
)


def _add_relational_properties(objects, grid):
    if grid is not None:
        h, w = grid.shape[:2]
        _add_rel_props_raw(objects, grid, h, w)
    return objects
from reasoning_project.property_expansion import PropertyExpansionEngine
from reasoning_project.selector_invention import SelectorInventor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "full_novel_reasoning_pipeline_v2" / "failure_driven_adaptergenesis_v2_2026_06_21"


# ---------------------------------------------------------------------------
# Synthetic task generators
# ---------------------------------------------------------------------------

def _make_grid(h: int, w: int, bg: int = 0) -> np.ndarray:
    return np.full((h, w), bg, dtype=int)


def _place_object(grid: np.ndarray, r: int, c: int, shape: np.ndarray) -> np.ndarray:
    g = grid.copy()
    for dr in range(shape.shape[0]):
        for dc in range(shape.shape[1]):
            if shape[dr, dc] != 0:
                rr, cc = r + dr, c + dc
                if 0 <= rr < g.shape[0] and 0 <= cc < g.shape[1]:
                    g[rr, cc] = shape[dr, dc]
    return g


def _remove_object(grid: np.ndarray, r: int, c: int, shape: np.ndarray) -> np.ndarray:
    g = grid.copy()
    for dr in range(shape.shape[0]):
        for dc in range(shape.shape[1]):
            if shape[dr, dc] != 0:
                rr, cc = r + dr, c + dc
                if 0 <= rr < g.shape[0] and 0 <= cc < g.shape[1]:
                    g[rr, cc] = 0
    return g


def generate_between_markers_task(seed: int = 0) -> Dict[str, Any]:
    """Object between two unique-color markers is kept; others removed.

    Property: is_between_two_markers — not in base property list.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    marker_color = 9

    for _ in range(3):
        h, w = 12, 12
        inp = _make_grid(h, w)

        # Place two markers (single pixels)
        m1_r, m1_c = rng.randint(1, 4), rng.randint(1, 4)
        m2_r, m2_c = rng.randint(7, 10), rng.randint(7, 10)
        inp[m1_r, m1_c] = marker_color
        inp[m2_r, m2_c] = marker_color

        # Place 3-4 objects
        obj_shape = np.array([[1, 1], [1, 0]], dtype=int)
        obj_colors = rng.choice([2, 3, 4, 5], size=4, replace=False)

        positions = [
            (rng.randint(0, 2), rng.randint(6, 9)),       # top-right (not between)
            ((m1_r + m2_r) // 2, (m1_c + m2_c) // 2),     # between markers (keep)
            (rng.randint(8, 10), rng.randint(0, 3)),       # bottom-left (not between)
            (rng.randint(0, 2), rng.randint(0, 3)),        # top-left (not between)
        ]

        for i, (pr, pc) in enumerate(positions):
            colored = obj_shape * obj_colors[i]
            inp = _place_object(inp, pr, pc, colored)

        # Output: keep only the object between markers
        out = inp.copy()
        for i, (pr, pc) in enumerate(positions):
            if i != 1:  # remove non-between objects
                colored = obj_shape * obj_colors[i]
                out = _remove_object(out, pr, pc, colored)

        pairs.append((inp, out))

    # Test pair
    test_inp = pairs[0][0].copy()
    test_out = pairs[0][1].copy()

    return {
        "task_id": "synthetic_between_markers",
        "property": "is_between_two_markers",
        "train_pairs": pairs,
        "test_inputs": [test_inp],
        "test_outputs": [test_out],
    }


def generate_color_matches_marker_task(seed: int = 10) -> Dict[str, Any]:
    """Object whose color matches a single-pixel marker elsewhere is kept.

    Property: is_object_whose_color_matches_external_marker.
    """
    rng = np.random.RandomState(seed)
    pairs = []

    for pair_idx in range(3):
        h, w = 10, 10
        inp = _make_grid(h, w)

        target_color = rng.choice([2, 3, 4, 5])
        other_colors = [c for c in [2, 3, 4, 5] if c != target_color]

        # Place marker pixel in corner
        inp[0, 0] = target_color

        # Place objects
        obj = np.array([[1, 1], [1, 1]], dtype=int)
        positions = [(2, 2), (2, 6), (6, 2), (6, 6)]
        colors = [target_color] + list(rng.choice(other_colors, 3, replace=False))
        rng.shuffle(colors)

        target_positions = []
        for i, (pr, pc) in enumerate(positions[:len(colors)]):
            inp = _place_object(inp, pr, pc, obj * colors[i])
            if colors[i] == target_color:
                target_positions.append(i)

        out = inp.copy()
        for i, (pr, pc) in enumerate(positions[:len(colors)]):
            if i not in target_positions:
                out = _remove_object(out, pr, pc, obj * colors[i])

        pairs.append((inp, out))

    return {
        "task_id": "synthetic_color_matches_marker",
        "property": "is_object_whose_color_matches_external_marker",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
    }


def generate_repeated_motif_change_task(seed: int = 20) -> Dict[str, Any]:
    """In a tiled 2x2 pattern, the cell that differs from the motif is kept.

    Property: is_repeated_motif_cell_that_changes.
    """
    rng = np.random.RandomState(seed)
    pairs = []

    for pair_idx in range(3):
        h, w = 8, 8
        motif = rng.randint(1, 5, size=(4, 4))

        inp = _make_grid(h, w)
        # Tile 2x2
        for tr in range(2):
            for tc in range(2):
                inp[tr*4:(tr+1)*4, tc*4:(tc+1)*4] = motif

        # Change one cell
        change_tr = rng.randint(0, 2)
        change_tc = rng.randint(0, 2)
        cr, cc = change_tr * 4 + rng.randint(0, 4), change_tc * 4 + rng.randint(0, 4)
        original_val = inp[cr, cc]
        new_val = (original_val % 8) + 1
        inp[cr, cc] = new_val

        # Output: only the changed quadrant
        out = _make_grid(h, w)
        out[change_tr*4:(change_tr+1)*4, change_tc*4:(change_tc+1)*4] = \
            inp[change_tr*4:(change_tr+1)*4, change_tc*4:(change_tc+1)*4]

        pairs.append((inp, out))

    return {
        "task_id": "synthetic_motif_change",
        "property": "is_repeated_motif_cell_that_changes",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
    }


def generate_gap_region_task(seed: int = 30) -> Dict[str, Any]:
    """Object inside a region delimited by gaps in lines is kept.

    Property: is_inside_region_defined_by_gap.
    """
    rng = np.random.RandomState(seed)
    pairs = []

    for pair_idx in range(3):
        h, w = 12, 12
        inp = _make_grid(h, w)

        # Horizontal line with gap
        line_r = 5
        gap_start = rng.randint(3, 7)
        gap_end = gap_start + 2
        for c in range(w):
            if c < gap_start or c >= gap_end:
                inp[line_r, c] = 7  # gray line

        # Place objects above and below line
        obj = np.array([[1, 1], [1, 0]], dtype=int)
        positions_above = [(2, rng.randint(1, 4)), (2, rng.randint(6, 9))]
        positions_below = [(8, rng.randint(1, 4)), (8, rng.randint(6, 9))]
        colors = rng.choice([2, 3, 4, 5], 4, replace=False)

        all_pos = positions_above + positions_below
        for i, (pr, pc) in enumerate(all_pos):
            inp = _place_object(inp, pr, pc, obj * colors[i])

        # Output: keep only objects below the line (inside the gap-delimited region)
        out = inp.copy()
        for i, (pr, pc) in enumerate(positions_above):
            out = _remove_object(out, pr, pc, obj * colors[i])

        pairs.append((inp, out))

    return {
        "task_id": "synthetic_gap_region",
        "property": "is_inside_region_defined_by_gap",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
    }


def generate_line_endpoint_task(seed: int = 40) -> Dict[str, Any]:
    """Object at the endpoint of a line extending from a marker is kept.

    Property: is_endpoint_of_line_extension.
    """
    rng = np.random.RandomState(seed)
    pairs = []

    for pair_idx in range(3):
        h, w = 10, 10
        inp = _make_grid(h, w)

        # Marker at left edge
        marker_r = rng.randint(3, 7)
        inp[marker_r, 0] = 9

        # Line extending right from marker
        line_end = rng.randint(5, 8)
        for c in range(1, line_end):
            inp[marker_r, c] = 8

        # Object at line endpoint (keep this one)
        obj = np.array([[1, 1], [1, 0]], dtype=int)
        endpoint_pos = (marker_r - 1, line_end)
        endpoint_color = rng.choice([2, 3, 4, 5])
        inp = _place_object(inp, *endpoint_pos, obj * endpoint_color)

        # Other objects not at endpoints
        other_positions = [(1, 1), (1, 7), (8, 7)]
        other_colors = rng.choice([c for c in [2, 3, 4, 5] if c != endpoint_color], 3, replace=False)
        for i, (pr, pc) in enumerate(other_positions):
            inp = _place_object(inp, pr, pc, obj * other_colors[i])

        # Output: keep only endpoint object
        out = inp.copy()
        for i, (pr, pc) in enumerate(other_positions):
            out = _remove_object(out, pr, pc, obj * other_colors[i])

        pairs.append((inp, out))

    return {
        "task_id": "synthetic_line_endpoint",
        "property": "is_endpoint_of_line_extension",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
    }


def generate_arrow_aligned_task(seed: int = 50) -> Dict[str, Any]:
    """Object aligned with direction an arrow points is kept.

    Property: is_aligned_with_arrow_direction.
    """
    rng = np.random.RandomState(seed)
    pairs = []

    for pair_idx in range(3):
        h, w = 12, 12
        inp = _make_grid(h, w)

        # Right-pointing arrow at center-left
        arrow = np.array([
            [0, 0, 1, 0],
            [1, 1, 1, 1],
            [0, 0, 1, 0],
        ], dtype=int) * 8
        arrow_r, arrow_c = 4, 1
        inp = _place_object(inp, arrow_r, arrow_c, arrow)

        # Object to the right of arrow (aligned) — keep
        obj = np.array([[1, 1], [1, 0]], dtype=int)
        aligned_color = rng.choice([2, 3, 4, 5])
        aligned_pos = (4, 8)
        inp = _place_object(inp, *aligned_pos, obj * aligned_color)

        # Objects not in arrow direction — remove
        other_positions = [(0, 1), (9, 8), (9, 1)]
        other_colors = rng.choice([c for c in [2, 3, 4, 5] if c != aligned_color], 3, replace=False)
        for i, (pr, pc) in enumerate(other_positions):
            inp = _place_object(inp, pr, pc, obj * other_colors[i])

        out = inp.copy()
        for i, (pr, pc) in enumerate(other_positions):
            out = _remove_object(out, pr, pc, obj * other_colors[i])

        pairs.append((inp, out))

    return {
        "task_id": "synthetic_arrow_aligned",
        "property": "is_aligned_with_arrow_direction",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
    }


TASK_GENERATORS = [
    generate_between_markers_task,
    generate_color_matches_marker_task,
    generate_repeated_motif_change_task,
    generate_gap_region_task,
    generate_line_endpoint_task,
    generate_arrow_aligned_task,
]


# ---------------------------------------------------------------------------
# Novelty guard: verify base search does NOT solve
# ---------------------------------------------------------------------------

def base_search_solves(train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> bool:
    """Check if base _find_discriminative_property_extended finds the answer."""
    result = _find_discriminative_property_extended(train_pairs)
    return result is not None


def expansion_search_solves(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Tuple[bool, Optional[str]]:
    """Check if PropertyExpansionEngine finds a discriminative property."""
    engine = PropertyExpansionEngine()

    object_trace = {}
    failure_trace = {"properties_tried": []}

    results = engine.find_discriminative_property(
        train_pairs, object_trace, failure_trace,
    )

    if results:
        best = results[0]
        if best["score"] >= 1.0:
            return True, best["name"]

    # Also try SelectorInventor directly
    inventor = SelectorInventor()
    per_pair = inventor.infer_targets_from_change(train_pairs)
    if per_pair:
        singles = inventor.search_single_properties(per_pair)
        for sc in singles:
            if sc.train_fit_score >= 1.0:
                return True, sc.selector_expression

        conjs = inventor.search_conjunctions(per_pair)
        for sc in conjs:
            if sc.train_fit_score >= 1.0:
                return True, sc.selector_expression

        negs = inventor.search_negations(per_pair)
        for sc in negs:
            if sc.train_fit_score >= 1.0:
                return True, sc.selector_expression

        markers = inventor.search_marker_frame_anchor_relations(per_pair)
        for sc in markers:
            if sc.train_fit_score >= 1.0:
                return True, sc.selector_expression

    return False, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT, exist_ok=True)

    print("Property Expansion Proof-of-Mechanism")
    print("=" * 60)

    tasks = []
    for gen in TASK_GENERATORS:
        try:
            task = gen()
            tasks.append(task)
            print(f"  Generated: {task['task_id']} (property: {task['property']})")
        except Exception as e:
            print(f"  Failed to generate from {gen.__name__}: {e}")

    # Save generated tasks
    tasks_json = []
    for t in tasks:
        record = {
            "task_id": t["task_id"],
            "property": t["property"],
            "n_train": len(t["train_pairs"]),
            "train_shapes": [
                {"input": list(inp.shape), "output": list(out.shape)}
                for inp, out in t["train_pairs"]
            ],
        }
        tasks_json.append(record)

    tasks_path = OUT / "property_expansion_proof_tasks.json"
    with open(tasks_path, "w") as f:
        json.dump(tasks_json, f, indent=2)
    print(f"\nSaved task metadata to {tasks_path}")

    # Run experiment
    results = []
    for task in tasks:
        task_id = task["task_id"]
        prop = task["property"]
        train_pairs = task["train_pairs"]

        print(f"\n--- {task_id} ---")

        # Step 1: Novelty guard — base search should NOT solve
        base_solves = base_search_solves(train_pairs)
        print(f"  Base search solves: {base_solves}")
        if base_solves:
            print(f"  REJECTED: task is too easy for novelty guard")
            results.append({
                "task_id": task_id,
                "property": prop,
                "base_search_solves": True,
                "expansion_solves": "N/A",
                "property_used": "N/A",
                "novel_guard_passed": False,
            })
            continue

        # Step 2: Expansion search
        exp_solves, exp_prop = expansion_search_solves(train_pairs)
        print(f"  Expansion search solves: {exp_solves}")
        if exp_solves:
            print(f"  Property found: {exp_prop}")

        results.append({
            "task_id": task_id,
            "property": prop,
            "base_search_solves": False,
            "expansion_solves": exp_solves,
            "property_used": exp_prop if exp_prop else "",
            "novel_guard_passed": True,
        })

    # Write results CSV
    csv_path = OUT / "property_expansion_proof_results.csv"
    if results:
        keys = list(results[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
    print(f"\nSaved results to {csv_path}")

    # Summary
    novel_tasks = [r for r in results if r.get("novel_guard_passed")]
    n_novel = len(novel_tasks)
    n_expansion_solves = sum(1 for r in novel_tasks if r.get("expansion_solves"))
    n_base_too_easy = sum(1 for r in results if r.get("base_search_solves"))

    md_path = OUT / "property_expansion_proof_summary.md"
    with open(md_path, "w") as f:
        f.write("# Property Expansion Proof-of-Mechanism\n\n")
        f.write(f"**Date:** 2026-06-21\n\n")
        f.write("## Results\n\n")
        f.write("| Metric | Count |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Tasks generated | {len(results)} |\n")
        f.write(f"| Rejected (base search solves) | {n_base_too_easy} |\n")
        f.write(f"| Novel tasks (guard passed) | {n_novel} |\n")
        f.write(f"| Expansion solves novel tasks | {n_expansion_solves} |\n\n")

        if n_novel > 0 and n_expansion_solves > 0:
            f.write("## Property Expansion Is Necessary\n\n")
            f.write(f"PropertyExpansionEngine solves {n_expansion_solves}/{n_novel} "
                    f"tasks that base property search cannot.\n\n")
            f.write("### Tasks Where Expansion Succeeds\n\n")
            f.write("| Task | Target Property | Found Property |\n")
            f.write("|------|----------------|----------------|\n")
            for r in novel_tasks:
                if r.get("expansion_solves"):
                    f.write(f"| {r['task_id']} | {r['property']} | {r['property_used']} |\n")
        elif n_novel > 0:
            f.write("## Property Expansion Not Proven\n\n")
            f.write("PropertyExpansionEngine could not solve any novel tasks.\n")
            f.write("The generated properties are genuinely outside both the base\n")
            f.write("AND expanded property languages.\n")
        else:
            f.write("## No Novel Tasks\n\n")
            f.write("All generated tasks were solvable by base property search.\n")
            f.write("Need harder synthetic tasks.\n")

    print(f"Saved summary to {md_path}")
    print(f"\nNovel tasks: {n_novel}, Expansion solves: {n_expansion_solves}")


if __name__ == "__main__":
    main()
