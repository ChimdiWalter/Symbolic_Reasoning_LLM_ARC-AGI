#!/usr/bin/env python3
"""Debug conjunction search on f21745ec."""
import json
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter, StructuralReasoner, ReasoningMemory,
    _extract_objects_with_properties, _classify_kept_removed,
    _all_property_names, _get_property_value,
)


base = Path(__file__).resolve().parent.parent
with open(base / "data/arc/arc-agi_training_challenges.json") as f:
    tasks = json.load(f)
with open(base / "data/arc/arc-agi_training_solutions.json") as f:
    solutions = json.load(f)

tid = "f21745ec"
task = tasks[tid]
sol = solutions[tid]

train_pairs = [
    (np.array(ex["input"]), np.array(ex["output"]))
    for ex in task["train"]
]
test_inputs = [np.array(ex["input"]) for ex in task["test"]]
test_outputs = [np.array(s) for s in sol]

print(f"Task {tid}: {len(train_pairs)} train, {len(test_inputs)} test")
for i, (inp, out) in enumerate(train_pairs):
    print(f"  Train {i}: input {inp.shape}, output {out.shape}")

adapter = GridDomainAdapter()

# Check classification and conjunction
p1, p2 = "any_sym", "is_unique_shape"
keep_match = False

for i, (inp, out) in enumerate(train_pairs):
    objs = _extract_objects_with_properties(inp)
    result = _classify_kept_removed(objs, inp, out)
    print(f"\n  Train {i}: {len(objs)} objects")
    if result:
        kept_idx, rem_idx = result
        print(f"    kept={kept_idx}, removed={rem_idx}")
        for j, obj in enumerate(objs):
            v1 = _get_property_value(obj, p1)
            v2 = _get_property_value(obj, p2)
            conj = v1 and v2
            status = "KEPT" if j in kept_idx else "REMOVED"
            print(f"    obj {j}: {p1}={v1}, {p2}={v2}, conj={conj} -> {status}")
    else:
        print("    classification failed")

# Now test with StructuralReasoner
print("\n--- Testing StructuralReasoner ---")
memory = ReasoningMemory()
reasoner = StructuralReasoner(adapter, memory=memory)
result = reasoner.solve(train_pairs, test_inputs)

if result is not None:
    preds, meta = result
    print(f"Solved! meta={meta}")
    correct = all(np.array_equal(p, t) for p, t in zip(preds, test_outputs))
    print(f"Correct: {correct}")
else:
    print("Not solved by StructuralReasoner")

# Try conjunction directly
print("\n--- Testing conjunction directly ---")
from reasoning_project.reasoning_engine import _apply_filter

# Manually test: keep objects where NOT (any_sym AND is_unique_shape)
for i, (inp, out) in enumerate(train_pairs):
    objs = _extract_objects_with_properties(inp)
    keep_mask = [not (_get_property_value(o, p1) and _get_property_value(o, p2)) for o in objs]
    print(f"  Train {i}: keep_mask={keep_mask}")

    # Reconstruct
    result_grid = inp.copy()
    for obj, keep in zip(objs, keep_mask):
        if not keep:
            result_grid[obj["mask"]] = 0

    match = np.array_equal(result_grid, out)
    print(f"  Match: {match}")

# LOO validation
print("\n--- LOO validation ---")
for hold_out in range(len(train_pairs)):
    held_inp, held_out = train_pairs[hold_out]
    objs = _extract_objects_with_properties(held_inp)
    keep_mask = [not (_get_property_value(o, p1) and _get_property_value(o, p2)) for o in objs]

    if all(keep_mask) or not any(keep_mask):
        print(f"  LOO {hold_out}: FAIL (all same)")
        continue

    result_grid = held_inp.copy()
    for obj, keep in zip(objs, keep_mask):
        if not keep:
            result_grid[obj["mask"]] = 0

    match = np.array_equal(result_grid, held_out)
    print(f"  LOO {hold_out}: keep_mask={keep_mask} match={match}")

# Test prediction
print("\n--- Test prediction ---")
for i, (ti, to) in enumerate(zip(test_inputs, test_outputs)):
    objs = _extract_objects_with_properties(ti)
    keep_mask = [not (_get_property_value(o, p1) and _get_property_value(o, p2)) for o in objs]

    if all(keep_mask) or not any(keep_mask):
        print(f"  Test {i}: FAIL (all same)")
        continue

    result_grid = ti.copy()
    for obj, keep in zip(objs, keep_mask):
        if not keep:
            result_grid[obj["mask"]] = 0

    match = np.array_equal(result_grid, to)
    print(f"  Test {i}: keep_mask={keep_mask} match={match}")
