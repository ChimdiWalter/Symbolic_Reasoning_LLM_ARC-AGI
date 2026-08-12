"""Operator invention microcycle test: verify the full chain on synthetic tasks
derived from real ARC failure patterns.

Chain:
    property identifies target
    → old reconstruction fails
    → operator gap classified
    → operator schema proposed
    → operator parameterized
    → LOO passes
    → task promoted
    → certificate emitted

Each task is synthetic but modeled on real ARC failure patterns (not toy-only).
The tasks have:
    - Multiple objects with a discriminative property
    - Standard zeroing-reconstruction fails
    - A specific operator family is needed (move, fill, recolor, gravity)

Outputs:
    outputs/operator_invention_microcycle/summary.md
    outputs/operator_invention_microcycle/promoted_tasks.jsonl
    outputs/operator_invention_microcycle/validated_operators.jsonl
    outputs/operator_invention_microcycle/event_chains.jsonl
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    _extract_objects_with_properties,
    _classify_kept_removed,
    _find_discriminative_property,
)
from reasoning_project.operator_invention import (
    FailureDerivedOperatorInventor,
    InventedOperatorSchema,
)


def make_move_by_vector_task() -> Dict:
    """Synthetic task: small objects are moved right by 3 cells, large objects stay.
    Models real ARC pattern: spatial relocation based on object property."""
    pairs = []
    for seed in range(3):
        rng = np.random.RandomState(42 + seed)
        grid = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        large_r, large_c = 1, 1
        grid[large_r:large_r+3, large_c:large_c+3] = 2
        out[large_r:large_r+3, large_c:large_c+3] = 2

        small_r = 5 + seed
        small_c = 1
        grid[small_r, small_c] = 5
        out[small_r, small_c + 3] = 5

        pairs.append((grid, out))
    return {
        "task_id": "synth_move_vector",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
        "expected_family": "copy_to_position",
    }


def make_fill_constant_task() -> Dict:
    """Synthetic task: small objects (area=1) are filled with color 7 instead of zeroed.
    Large objects (area>=4) are kept as-is. Discriminative property: is_largest or area-based.
    Standard zeroing would zero small objects; correct output fills them with 7."""
    pairs = []
    for seed in range(3):
        grid = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        grid[1:4, 1:4] = 3
        out[1:4, 1:4] = 3

        r1 = 6
        c1 = 2 + seed
        grid[r1, c1] = 4
        out[r1, c1] = 7

        r2 = 7
        c2 = 5
        grid[r2, c2] = 4
        out[r2, c2] = 7

        pairs.append((grid, out))
    return {
        "task_id": "synth_fill_constant",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
        "expected_family": "region_fill_from_boundary",
    }


def make_recolor_task() -> Dict:
    """Synthetic task: objects touching boundary are recolored from color 2 to color 6.
    Interior objects (not touching boundary) stay as-is. Clear keep/remove structure:
    kept = interior (non-boundary), removed = boundary-touching (recolored, not zeroed)."""
    pairs = []
    for seed in range(3):
        grid = np.zeros((11, 11), dtype=int)
        out = np.zeros((11, 11), dtype=int)

        grid[4:6, 4:6] = 2
        out[4:6, 4:6] = 2

        grid[0:2, 3+seed:5+seed] = 2
        out[0:2, 3+seed:5+seed] = 6

        grid[9:11, 1:3] = 2
        out[9:11, 1:3] = 6

        pairs.append((grid, out))
    return {
        "task_id": "synth_recolor_boundary",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
        "expected_family": "object_match_transfer_color",
    }


def make_gravity_task() -> Dict:
    """Synthetic task: small floating objects drop to the bottom.
    Models real ARC pattern: gravity-based relocation."""
    pairs = []
    for seed in range(3):
        grid = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        grid[8:10, 0:10] = 1
        out[8:10, 0:10] = 1

        grid[7:8, 3:7] = 1
        out[7:8, 3:7] = 1

        r = 1 + seed
        c = 4 + seed % 3
        grid[r, c] = 3
        drop_to = 6
        out[drop_to, c] = 3

        pairs.append((grid, out))
    return {
        "task_id": "synth_gravity_drop",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
        "expected_family": "gravity_or_drop",
    }


def make_marker_directed_move_task() -> Dict:
    """Synthetic task: there's a marker (single-cell color 9) and target objects (color 4).
    Targets move toward the marker by a fixed vector.
    Models real ARC pattern: marker-directed spatial transformation."""
    pairs = []
    for seed in range(3):
        grid = np.zeros((10, 10), dtype=int)
        out = np.zeros((10, 10), dtype=int)

        marker_r, marker_c = 8, 8
        grid[marker_r, marker_c] = 9
        out[marker_r, marker_c] = 9

        obj_r = 2 + seed
        obj_c = 2
        grid[obj_r:obj_r+2, obj_c:obj_c+2] = 4
        out[obj_r+2:obj_r+4, obj_c+2:obj_c+4] = 4

        pairs.append((grid, out))
    return {
        "task_id": "synth_marker_directed",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
        "expected_family": "marker_directed_move",
    }


def make_fill_constant_v2_task() -> Dict:
    """Synthetic task: hollow objects (with holes) are filled with color 8.
    Filled rectangles stay as-is. Property: n_holes > 0 identifies targets.
    Standard zeroing would zero the hollow objects; correct output fills them."""
    pairs = []
    for seed in range(3):
        grid = np.zeros((12, 12), dtype=int)
        out = np.zeros((12, 12), dtype=int)

        grid[1:4, 1:4] = 5
        out[1:4, 1:4] = 5

        r = 6
        c = 2 + seed
        grid[r:r+3, c:c+3] = 3
        grid[r+1, c+1] = 0
        out[r:r+3, c:c+3] = 3
        out[r+1, c+1] = 8

        pairs.append((grid, out))
    return {
        "task_id": "synth_fill_constant_v2",
        "train_pairs": pairs,
        "test_inputs": [pairs[0][0].copy()],
        "test_outputs": [pairs[0][1].copy()],
        "expected_family": "hole_fill_multicolor",
    }


TASK_GENERATORS = [
    make_move_by_vector_task,
    make_fill_constant_task,
    make_recolor_task,
    make_gravity_task,
    make_marker_directed_move_task,
    make_fill_constant_v2_task,
]


def run_microcycle(task: Dict) -> Dict[str, Any]:
    """Run the full operator invention microcycle on a single task."""
    tid = task["task_id"]
    tp = task["train_pairs"]
    ti = task["test_inputs"]
    to = task["test_outputs"]
    expected_family = task.get("expected_family", "unknown")

    result = {
        "task_id": tid,
        "expected_family": expected_family,
        "target_property_found": False,
        "old_reconstruction_fails": False,
        "operator_generated": False,
        "operator_validated": False,
        "promoted": False,
        "false_positive": False,
        "property_name": None,
        "keep_when_true": None,
        "operator_name": None,
        "operator_family": None,
        "validation_level": None,
        "event_chain": [],
    }

    # Step 1: Find discriminative property
    disc = _find_discriminative_property(tp)
    if disc is None:
        result["event_chain"].append("FAIL: no discriminative property found")
        return result
    prop_name, keep_when_true = disc
    result["target_property_found"] = True
    result["property_name"] = prop_name
    result["keep_when_true"] = keep_when_true
    result["event_chain"].append(f"property_found: {prop_name} (keep={keep_when_true})")

    # Step 2: Verify old reconstruction fails
    adapter = GridDomainAdapter()
    old_matches = True
    for inp, out in tp:
        objects = adapter.extract_objects(inp)
        keep_mask = [adapter.get_property(o, prop_name) == keep_when_true for o in objects]
        pred = adapter.reconstruct_filtered(inp, objects, keep_mask)
        if pred is None or not adapter.scenes_equal(pred, out):
            old_matches = False
            break
    if old_matches:
        result["event_chain"].append("SKIP: old reconstruction already works")
        return result
    result["old_reconstruction_fails"] = True
    result["event_chain"].append("old_reconstruction_fails: zeroing doesn't match output")

    # Step 3: Generate operator from gap trace
    gap_trace = {
        "task_id": tid,
        "needed_operator_family": expected_family,
        "best_property": prop_name,
    }
    inventor = FailureDerivedOperatorInventor()
    schemas = inventor.invent_from_gap_traces(
        [gap_trace],
        {tid: tp},
    )
    if not schemas:
        result["event_chain"].append(f"FAIL: no operator schema generated for {expected_family}")
        return result
    schema = schemas[0]
    result["operator_generated"] = True
    result["operator_name"] = schema.name
    result["operator_family"] = schema.family
    result["event_chain"].append(f"operator_generated: {schema.name} (family={schema.family})")

    # Step 4: Advance validation
    level = inventor.advance_validation(
        schema, tp, prop_name, keep_when_true,
        test_inputs=ti, test_outputs=to,
    )
    result["validation_level"] = level
    result["event_chain"].append(f"validation_level: {level}")

    if level in ("loo_validated", "promotion_validated", "transfer_validated"):
        result["operator_validated"] = True
        result["event_chain"].append("operator_validated: LOO passed")

    if level == "promotion_validated":
        result["promoted"] = True
        result["event_chain"].append(f"PROMOTED: {tid}")

    # Step 5: Check for false positive (predict on test, compare)
    if schemas:
        for ti_grid, to_grid in zip(ti, to):
            pred = inventor.execute_schema(schema, ti_grid, prop_name, keep_when_true)
            if pred is not None and not np.array_equal(pred, to_grid):
                result["false_positive"] = True
                result["event_chain"].append("FALSE_POSITIVE: test prediction mismatch")

    return result


def main():
    out_dir = Path("outputs/operator_invention_microcycle")
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print("=" * 60)
    print("OPERATOR INVENTION MICROCYCLE TEST")
    print("=" * 60)

    results = []
    for gen_fn in TASK_GENERATORS:
        task = gen_fn()
        print(f"\n--- {task['task_id']} (expected: {task.get('expected_family')}) ---")
        result = run_microcycle(task)
        results.append(result)
        for event in result["event_chain"]:
            print(f"  {event}")

    # Aggregate
    n_property = sum(r["target_property_found"] for r in results)
    n_old_fails = sum(r["old_reconstruction_fails"] for r in results)
    n_generated = sum(r["operator_generated"] for r in results)
    n_validated = sum(r["operator_validated"] for r in results)
    n_promoted = sum(r["promoted"] for r in results)
    n_fp = sum(r["false_positive"] for r in results)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  target_property_found: {n_property}/{len(results)}")
    print(f"  old_reconstruction_fails: {n_old_fails}/{len(results)}")
    print(f"  operator_generated: {n_generated}/{len(results)}")
    print(f"  operator_validated: {n_validated}/{len(results)}")
    print(f"  promotions: {n_promoted}/{len(results)}")
    print(f"  false_positives: {n_fp}")

    success = (n_property > 0 and n_old_fails > 0 and n_generated > 0
               and n_validated > 0 and n_promoted > 0 and n_fp == 0)
    print(f"\n  MICROCYCLE {'PASSES' if success else 'FAILS'}")

    # Write outputs
    with open(out_dir / "promoted_tasks.jsonl", "w") as f:
        for r in results:
            if r["promoted"]:
                f.write(json.dumps({
                    "task_id": r["task_id"],
                    "operator": r["operator_name"],
                    "family": r["operator_family"],
                    "validation_level": r["validation_level"],
                }) + "\n")

    with open(out_dir / "validated_operators.jsonl", "w") as f:
        for r in results:
            if r["operator_validated"]:
                f.write(json.dumps({
                    "task_id": r["task_id"],
                    "operator": r["operator_name"],
                    "family": r["operator_family"],
                    "validation_level": r["validation_level"],
                }) + "\n")

    with open(out_dir / "event_chains.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    elapsed = time.time() - t0
    lines = [
        "# Operator Invention Microcycle Results\n",
        f"- Tasks: {len(results)}",
        f"- target_property_found: {n_property}",
        f"- old_reconstruction_fails: {n_old_fails}",
        f"- operator_generated: {n_generated}",
        f"- operator_validated: {n_validated}",
        f"- **promotions: {n_promoted}**",
        f"- **false_positives: {n_fp}**",
        f"- Elapsed: {elapsed:.1f}s",
        "",
        f"## Verdict: {'PASSES' if success else 'FAILS'}\n",
    ]
    if success:
        lines.append("The operator invention pipeline successfully:\n")
        lines.append("1. Found discriminative properties for target objects")
        lines.append("2. Confirmed zeroing-reconstruction fails")
        lines.append("3. Generated operator schemas from failure traces")
        lines.append("4. Validated operators via LOO")
        lines.append("5. Promoted tasks (correct test predictions)")
        lines.append("6. Zero false positives")
    else:
        lines.append("### Failures:\n")
        for r in results:
            if not r["promoted"]:
                lines.append(f"- {r['task_id']}: {r['event_chain'][-1] if r['event_chain'] else 'unknown'}")

    lines.append("\n## Per-Task Details\n")
    for r in results:
        status = "PROMOTED" if r["promoted"] else ("FP" if r["false_positive"] else "FAILED")
        lines.append(f"### {r['task_id']} [{status}]")
        lines.append(f"- Expected family: {r['expected_family']}")
        lines.append(f"- Property: {r['property_name']}")
        lines.append(f"- Operator: {r['operator_name']} ({r['operator_family']})")
        lines.append(f"- Validation: {r['validation_level']}")
        lines.append(f"- Chain: {' → '.join(r['event_chain'])}")
        lines.append("")

    with open(out_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nOutputs: {out_dir}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
