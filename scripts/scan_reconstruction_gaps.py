#!/usr/bin/env python3
"""Scan for tasks where we can discriminate objects but reconstruction fails.
Categorize what reconstruction is needed to understand what primitives to add."""
import json, sys, numpy as np
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties, _classify_kept_removed,
    _all_property_names, _get_property_value, _apply_filter,
    _apply_recolor, _find_recolor_rule, _find_discriminative_property,
    _apply_filter_extract, _apply_filter_recolor,
    _find_discriminative_conjunction, solve_task_reasoning,
)

base = Path(__file__).resolve().parent.parent
with open(base / "data/arc/arc-agi_training_challenges.json") as f:
    tasks = json.load(f)
with open(base / "data/arc/arc-agi_training_solutions.json") as f:
    solutions = json.load(f)

# Category 1: Same shape, discriminable, but zero-out doesn't work
# What reconstruction WOULD work?

categories = Counter()
unsolved_discriminable = []

for tid in sorted(tasks.keys()):
    task = tasks[tid]
    sol = solutions[tid]
    pairs = [(np.array(ex["input"]), np.array(ex["output"])) for ex in task["train"]]
    test_inputs = [np.array(ex["input"]) for ex in task["test"]]
    test_outputs = [np.array(s) for s in sol]

    if len(pairs) < 3:
        continue

    # Already solved by reasoning engine?
    result = solve_task_reasoning(pairs, test_inputs)
    if result is not None:
        preds, meta = result
        if len(preds) == len(test_outputs) and all(
            np.array_equal(p, t) for p, t in zip(preds, test_outputs)):
            continue

    # Same shape?
    if not all(i.shape == o.shape for i, o in pairs):
        # Different shape — check if any property + extract works
        # Already covered by filter_then_extract
        continue

    # Can we classify kept/removed?
    classifications = []
    valid = True
    for inp, out in pairs:
        objs = _extract_objects_with_properties(inp)
        result = _classify_kept_removed(objs, inp, out)
        if result is None:
            valid = False
            break
        classifications.append((objs, result))
    if not valid:
        continue

    # Can we discriminate with a single property?
    prop_result = _find_discriminative_property(pairs)
    if prop_result is None:
        # Try conjunction
        conj_result = _find_discriminative_conjunction(pairs)
        if conj_result is None:
            categories["no_discriminator"] += 1
            continue
        else:
            categories["conjunction_only"] += 1

    # We CAN discriminate, but reconstruction failed. Why?
    # Check what changes happen beyond object removal
    diff_types = set()
    for inp, out, (objs, (kept_idx, rem_idx)) in zip(
        [i for i, o in pairs], [o for i, o in pairs], classifications
    ):
        # Are kept objects unchanged?
        for ki in kept_idx:
            inp_vals = inp[objs[ki]["mask"]]
            out_vals = out[objs[ki]["mask"]]
            if not np.array_equal(inp_vals, out_vals):
                diff_types.add("kept_recolored")
                break

        # Does background change?
        all_obj_mask = np.zeros_like(inp, dtype=bool)
        for obj in objs:
            all_obj_mask |= obj["mask"]
        bg_inp = inp[~all_obj_mask]
        bg_out = out[~all_obj_mask]
        if not np.array_equal(bg_inp, bg_out):
            diff_types.add("background_changed")

    cat = "+".join(sorted(diff_types)) if diff_types else "unknown"
    categories[cat] += 1
    if len(unsolved_discriminable) < 30:
        unsolved_discriminable.append((tid, cat, diff_types))

print("=== Reconstruction gap categories ===")
for cat, count in categories.most_common():
    print(f"  {cat}: {count}")

print(f"\n=== Sample unsolved discriminable tasks ===")
for tid, cat, diff in unsolved_discriminable:
    print(f"  {tid}: {cat}")

# Also: scan for tasks where output is a SUBSET of input objects (diff shape)
print("\n=== Different-shape tasks where output is object subset ===")
diff_shape_extract = 0
for tid in sorted(tasks.keys()):
    task = tasks[tid]
    sol = solutions[tid]
    pairs = [(np.array(ex["input"]), np.array(ex["output"])) for ex in task["train"]]

    if len(pairs) < 3:
        continue
    if all(i.shape == o.shape for i, o in pairs):
        continue

    # Check if any single-property extract works
    test_inputs = [np.array(ex["input"]) for ex in task["test"]]
    test_outputs = [np.array(s) for s in sol]

    result = solve_task_reasoning(pairs, test_inputs)
    if result is not None:
        preds, meta = result
        if len(preds) == len(test_outputs) and all(
            np.array_equal(p, t) for p, t in zip(preds, test_outputs)):
            continue

    # Try if conjunction extract works
    props = _all_property_names()
    for i_p, p1 in enumerate(props):
        for p2 in props[i_p+1:]:
            for keep in [True, False]:
                ok = True
                for inp, out in pairs:
                    objs = _extract_objects_with_properties(inp)
                    if len(objs) < 2:
                        ok = False
                        break
                    km = [(_get_property_value(o, p1) and _get_property_value(o, p2)) == keep for o in objs]
                    if all(km) or not any(km):
                        ok = False
                        break
                    pred = _apply_filter_extract(inp, objs, f"__dummy__", True)
                    # Can't use _apply_filter_extract with conjunction directly
                    # Manual extract
                    combined = np.zeros_like(inp, dtype=bool)
                    for obj, k in zip(objs, km):
                        if k:
                            combined |= obj["mask"]
                    rows, cols = np.where(combined)
                    if len(rows) == 0:
                        ok = False
                        break
                    r1, r2 = int(rows.min()), int(rows.max())
                    c1, c2 = int(cols.min()), int(cols.max())
                    cropped = np.zeros((r2-r1+1, c2-c1+1), dtype=inp.dtype)
                    crop_mask = combined[r1:r2+1, c1:c2+1]
                    cropped[crop_mask] = inp[r1:r2+1, c1:c2+1][crop_mask]
                    if not np.array_equal(cropped, out):
                        ok = False
                        break
                if ok:
                    diff_shape_extract += 1
                    if diff_shape_extract <= 10:
                        print(f"  {tid}: ({p1} AND {p2}), keep={keep}")
                    break
            if ok:
                break
        if ok:
            break

print(f"\nTotal conjunction-extract tasks: {diff_shape_extract}")
