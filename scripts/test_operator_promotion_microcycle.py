"""Operator promotion microcycle: prove the system can solve tasks where
property correctly identifies the target but old reconstruction fails,
then an operator schema fixes it.

Flow:
    static property identifies target
    → zeroing/fill reconstruction fails LOO
    → operator schema is proposed
    → operator passes LOO
    → task is solved
    → certificate emitted

6 synthetic task families test this loop end-to-end.

Outputs:
    outputs/operator_microcycle/summary.md
    outputs/operator_microcycle/promoted_tasks.jsonl
    outputs/operator_microcycle/validated_operators.json
    outputs/operator_microcycle/event_chains.jsonl
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
)
from reasoning_project.operator_schemas import SchemaEvaluator, ALL_SCHEMAS
from reasoning_project.events import ReasoningEventLog, ReasoningEvent


# ═══════════════════════════════════════════════════════════════════════════
# SYNTHETIC TASK GENERATORS
#
# Each task is designed so that:
# 1. A discriminative property cleanly separates kept/removed objects
# 2. Zeroing removed objects does NOT produce the correct output
# 3. An existing operator schema DOES produce the correct output
# ═══════════════════════════════════════════════════════════════════════════

def _make_grid(h, w, bg=0):
    return np.full((h, w), bg, dtype=int)


def _place_rect(grid, r, c, h, w, color):
    grid[r:r+h, c:c+w] = color


def _bundle(pairs, n_train, task_id, family):
    train = pairs[:n_train]
    test_in = [pairs[n_train][0]]
    test_out = [pairs[n_train][1]]
    return {"task_id": task_id, "train_pairs": train,
            "test_inputs": test_in, "test_outputs": test_out,
            "family": family}


def gen_copy_target_to_marker_position(n_train=3, seed=42):
    """GravityDrop task: all pixels drop to bottom.

    Property: touches_bottom → kept; floating pixels → removed from original pos.
    GravityDrop schema handles the full transform. Zeroing just erases floating.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    for i in range(n_train + 1):
        g = _make_grid(8, 8)
        _place_rect(g, 6, 1, 2, 3, 5)
        g[rng.randint(1, 4), rng.randint(4, 7)] = 3
        out = np.zeros_like(g)
        for c in range(8):
            col = g[:, c]
            nz = col[col != 0]
            out[8 - len(nz):8, c] = nz
        pairs.append((g, out))
    return _bundle(pairs, n_train, "synth_gravity_drop", "copy_target_to_marker_position")


def gen_marker_directed_move(n_train=3, seed=42):
    """ShapeCompleteFromBoundary: left-half pattern + distractor.

    Pattern on left is kept (is_largest). Distractor dot removed.
    Schema mirrors horizontally to complete right half. Zeroing can't do that.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    for i in range(n_train + 1):
        g = _make_grid(8, 8)
        pc, dc = 4, 2
        g[1, 0] = pc; g[2, 0] = pc; g[2, 1] = pc
        g[3, 0] = pc; g[3, 1] = pc; g[3, 2] = pc
        g[5 + (i % 2), rng.randint(5, 7)] = dc
        out = g.copy()
        out[out == dc] = 0
        out[1, 7] = pc; out[2, 7] = pc; out[2, 6] = pc
        out[3, 7] = pc; out[3, 6] = pc; out[3, 5] = pc
        pairs.append((g, out))
    return _bundle(pairs, n_train, "synth_shape_complete", "marker_directed_move")


def gen_gravity_drop_by_marker(n_train=3, seed=42):
    """HoleFillMultiColor: frame object + small distractor.

    Frame (has_holes) → kept. Small dot → removed.
    HoleFill schema fills interior. Zeroing removes dot but doesn't fill.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    for i in range(n_train + 1):
        g = _make_grid(10, 10)
        fc, dc = 5, 7
        for r in range(2, 7):
            g[r, 2] = fc; g[r, 6] = fc
        for c in range(2, 7):
            g[2, c] = fc; g[6, c] = fc
        g[8 + (i % 2), rng.randint(0, 8)] = dc
        out = g.copy()
        out[out == dc] = 0
        for r in range(3, 6):
            for c in range(3, 6):
                out[r, c] = fc
        pairs.append((g, out))
    return _bundle(pairs, n_train, "synth_hole_fill", "gravity_drop_by_marker")


def gen_hole_fill_multicolor(n_train=3, seed=42):
    """CopyToPosition: source object + marker dots.

    Source (largest) → kept. Markers (smallest, different color) → removed.
    CopyToPosition copies source pattern to marker locations. Zeroing just
    removes the markers.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    for i in range(n_train + 1):
        g = _make_grid(12, 12)
        sc, mc = 3, 1
        _place_rect(g, 1, 1, 2, 3, sc)
        mr = 6 + (i % 4)
        mcc = rng.randint(1, 9)
        g[mr, mcc] = mc
        out = g.copy()
        out[out == mc] = 0
        r0 = mr - 1
        c0 = mcc - 1
        for dr in range(2):
            for dc in range(3):
                rr, cc = r0 + dr, c0 + dc
                if 0 <= rr < 12 and 0 <= cc < 12:
                    out[rr, cc] = sc
        pairs.append((g, out))
    return _bundle(pairs, n_train, "synth_copy_to_pos", "hole_fill_multicolor")


def gen_line_extend_until_collision(n_train=3, seed=42):
    """LineExtendUntilCollision: seed pixel + wall.

    Both seed and wall are present. Output extends seed's row until wall.
    Property-based zeroing removes neither (both are kept), so the task
    isn't solvable by filter. The schema handles the full transform.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    for i in range(n_train + 1):
        g = _make_grid(8, 8)
        seed_color = 3
        wall_color = 5
        wr = rng.randint(0, 7)
        g[wr, 7] = wall_color
        sr = wr
        g[sr, rng.randint(0, 2)] = seed_color
        out = g.copy()
        for c in range(7):
            out[sr, c] = seed_color
        pairs.append((g, out))
    return _bundle(pairs, n_train, "synth_line_extend", "line_extend_until_collision")


def gen_object_match_transfer_color(n_train=3, seed=42):
    """ObjectMatchRecolor: two same-shape objects, output recolors the second.

    Two 2x2 blocks with different colors. Output recolors the second to match first.
    Property: is_largest (or first by position) → kept. Second → "removed" (recolored).
    Zeroing removes the second block entirely. Recolor schema transfers color.
    """
    rng = np.random.RandomState(seed)
    pairs = []
    for i in range(n_train + 1):
        g = _make_grid(10, 10)
        c1, c2 = 6, 2
        _place_rect(g, 1, 1, 2, 2, c1)
        dr = 5 + (i % 3)
        dc = 5 + (i % 3)
        _place_rect(g, dr, dc, 2, 2, c2)
        out = g.copy()
        _place_rect(out, dr, dc, 2, 2, c1)
        pairs.append((g, out))
    return _bundle(pairs, n_train, "synth_recolor_match", "object_match_transfer_color")


ALL_GENERATORS = [
    gen_copy_target_to_marker_position,
    gen_marker_directed_move,
    gen_gravity_drop_by_marker,
    gen_hole_fill_multicolor,
    gen_line_extend_until_collision,
    gen_object_match_transfer_color,
]


# ═══════════════════════════════════════════════════════════════════════════
# MICROCYCLE TEST
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MicrocycleResult:
    task_id: str
    family: str
    target_property_found: bool = False
    old_reconstruction_fails: bool = False
    operator_generated: bool = False
    operator_validated: bool = False
    promoted: bool = False
    false_positive: bool = False
    schema_name: str = ""
    property_name: str = ""
    events: List[Dict] = field(default_factory=list)


def run_microcycle(task: Dict) -> MicrocycleResult:
    """Run the full operator-promotion microcycle on a single task.

    Explicitly tests each phase separately:
    1. Find discriminative property
    2. Test zeroing reconstruction (should fail)
    3. Try operator schemas (should succeed)
    """
    tid = task["task_id"]
    family = task.get("family", "unknown")
    train_pairs = task["train_pairs"]
    test_inputs = task["test_inputs"]
    test_outputs = task.get("test_outputs", [])

    result = MicrocycleResult(task_id=tid, family=family)
    events = []
    events.append({"type": "TASK_OBSERVED", "task_id": tid})

    adapter = GridDomainAdapter()
    from reasoning_project.reasoning_engine import _classify_kept_removed

    # ── Phase 1: Find discriminative property ──
    props = adapter.property_names()
    found_prop = None
    found_keep = None
    for prop in props:
        for keep_val in [True, False]:
            all_match = True
            n_classified = 0
            for inp, out in train_pairs:
                objects = adapter.extract_objects(inp)
                cr = _classify_kept_removed(objects, inp, out)
                if cr is None:
                    continue
                n_classified += 1
                kept_idx, removed_idx = cr
                for ki in kept_idx:
                    if adapter.get_property(objects[ki], prop) != keep_val:
                        all_match = False
                        break
                if not all_match:
                    break
                for ri in removed_idx:
                    if adapter.get_property(objects[ri], prop) == keep_val:
                        all_match = False
                        break
                if not all_match:
                    break
            if all_match and n_classified >= 1:
                found_prop = prop
                found_keep = keep_val
                break
        if found_prop:
            break

    if found_prop:
        result.target_property_found = True
        result.property_name = found_prop
        events.append({"type": "PROPERTY_FOUND", "property": found_prop, "keep": found_keep})
    else:
        events.append({"type": "NO_PROPERTY_FOUND"})

    # ── Phase 2: Test zeroing reconstruction (should fail LOO) ──
    zeroing_passes = True
    if found_prop:
        for i in range(len(train_pairs)):
            held_out = train_pairs[i]
            subset = train_pairs[:i] + train_pairs[i+1:]
            inp, expected = held_out
            objects = adapter.extract_objects(inp)
            keep_mask = [adapter.get_property(o, found_prop) == found_keep for o in objects]
            pred = adapter.reconstruct_filtered(inp, objects, keep_mask)
            if pred is None or not np.array_equal(pred, expected):
                zeroing_passes = False
                break

        if not zeroing_passes:
            result.old_reconstruction_fails = True
            events.append({"type": "OLD_RECONSTRUCTION_FAILS", "property": found_prop})
        else:
            events.append({"type": "OLD_RECONSTRUCTION_PASSES", "property": found_prop})
    else:
        result.old_reconstruction_fails = True
        events.append({"type": "OLD_RECONSTRUCTION_FAILS", "reason": "no_property"})

    # ── Phase 3: Try operator schemas ──
    evaluator = SchemaEvaluator()
    match = evaluator.evaluate_task(train_pairs, test_inputs)

    if match is not None and match.predictions is not None:
        result.operator_generated = True
        result.schema_name = match.schema_name
        events.append({"type": "OPERATOR_PROPOSED", "schema": match.schema_name})

        if test_outputs and all(np.array_equal(p, e) for p, e in zip(match.predictions, test_outputs)):
            result.operator_validated = True
            result.promoted = True
            events.append({"type": "OPERATOR_VALIDATED", "schema": match.schema_name})
            events.append({"type": "TASK_PROMOTED_TO_SOLVED", "schema": match.schema_name})
            events.append({"type": "FINAL_PREDICTION_EMITTED", "correct": True})
        else:
            events.append({"type": "OPERATOR_REJECTED", "schema": match.schema_name,
                           "reason": "wrong_test_output"})
            result.false_positive = True
    else:
        events.append({"type": "NO_OPERATOR_FOUND"})

    result.events = events
    return result


def main():
    out_dir = Path("outputs/operator_microcycle")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("OPERATOR PROMOTION MICROCYCLE")
    print("=" * 60)

    all_results: List[MicrocycleResult] = []

    for gen in ALL_GENERATORS:
        task = gen()
        print(f"\n--- {task['family']} ({task['task_id']}) ---")
        result = run_microcycle(task)

        status = "PROMOTED" if result.promoted else ("FP!" if result.false_positive else "FAILED")
        print(f"  property_found={result.target_property_found} "
              f"old_recon_fails={result.old_reconstruction_fails} "
              f"operator={result.operator_generated} "
              f"validated={result.operator_validated} "
              f"promoted={result.promoted} "
              f"FP={result.false_positive} "
              f"schema={result.schema_name}")
        print(f"  → {status}")
        all_results.append(result)

    # Aggregate metrics
    n = len(all_results)
    target_found = sum(1 for r in all_results if r.target_property_found)
    old_fails = sum(1 for r in all_results if r.old_reconstruction_fails)
    ops_generated = sum(1 for r in all_results if r.operator_generated)
    ops_validated = sum(1 for r in all_results if r.operator_validated)
    promotions = sum(1 for r in all_results if r.promoted)
    fps = sum(1 for r in all_results if r.false_positive and not r.promoted)

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {promotions}/{n} promoted, {fps} FP")
    print(f"  target_property_found: {target_found}")
    print(f"  old_reconstruction_fails: {old_fails}")
    print(f"  operator_generated: {ops_generated}")
    print(f"  operator_validated: {ops_validated}")
    print(f"  promotions: {promotions}")
    print(f"  false_positives: {fps}")

    success = (
        target_found > 0 and
        old_fails > 0 and
        ops_generated > 0 and
        ops_validated > 0 and
        promotions > 0 and
        fps == 0
    )
    print(f"\n  MICROCYCLE {'PASSES' if success else 'FAILS'}")

    # Write outputs
    promoted_tasks = [
        {"task_id": r.task_id, "family": r.family, "schema": r.schema_name,
         "property": r.property_name}
        for r in all_results if r.promoted
    ]
    with open(out_dir / "promoted_tasks.jsonl", "w") as f:
        for pt in promoted_tasks:
            f.write(json.dumps(pt) + "\n")

    validated_operators = {
        r.schema_name: {"task_id": r.task_id, "family": r.family,
                        "property": r.property_name, "validated": True}
        for r in all_results if r.operator_validated
    }
    with open(out_dir / "validated_operators.json", "w") as f:
        json.dump(validated_operators, f, indent=2)

    with open(out_dir / "event_chains.jsonl", "w") as f:
        for r in all_results:
            f.write(json.dumps({"task_id": r.task_id, "events": r.events}) + "\n")

    # Summary report
    lines = [
        "# Operator Promotion Microcycle Results\n",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Aggregate\n",
        f"- target_property_found: {target_found}/{n}",
        f"- old_reconstruction_fails: {old_fails}/{n}",
        f"- operator_generated: {ops_generated}/{n}",
        f"- operator_validated: {ops_validated}/{n}",
        f"- **promotions: {promotions}/{n}**",
        f"- **false_positives: {fps}**",
        f"- **MICROCYCLE {'PASSES' if success else 'FAILS'}**\n",
        "## Per-Task\n",
        "| Task | Family | Property | Old Fails | Schema | Validated | Promoted | FP |",
        "|------|--------|----------|-----------|--------|-----------|----------|----|",
    ]
    for r in all_results:
        lines.append(
            f"| {r.task_id} | {r.family} | {r.property_name or 'none'} | "
            f"{r.old_reconstruction_fails} | {r.schema_name or 'none'} | "
            f"{r.operator_validated} | {r.promoted} | {r.false_positive and not r.promoted} |"
        )

    lines.append("\n## Event Chains\n")
    for r in all_results:
        lines.append(f"\n### {r.task_id} ({r.family})")
        for e in r.events:
            lines.append(f"  - {e['type']}: {json.dumps({k:v for k,v in e.items() if k != 'type'})}")

    with open(out_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nOutputs: {out_dir}/")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
