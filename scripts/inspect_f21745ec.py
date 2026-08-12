#!/usr/bin/env python3
"""Inspect f21745ec to understand what reconstruction is needed."""
import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.reasoning_engine import _extract_objects_with_properties, _classify_kept_removed, _get_property_value

base = Path(__file__).resolve().parent.parent
with open(base / "data/arc/arc-agi_training_challenges.json") as f:
    tasks = json.load(f)
with open(base / "data/arc/arc-agi_training_solutions.json") as f:
    solutions = json.load(f)

tid = "f21745ec"
task = tasks[tid]
for i, ex in enumerate(task["train"]):
    inp = np.array(ex["input"])
    out = np.array(ex["output"])
    objs = _extract_objects_with_properties(inp)
    result = _classify_kept_removed(objs, inp, out)
    kept_idx, rem_idx = result

    print(f"\nTrain {i}: input {inp.shape}, output {out.shape}")
    print(f"  Kept objects: {len(kept_idx)}, Removed: {len(rem_idx)}")

    # What does the output look like for removed object regions?
    for ri in rem_idx:
        obj = objs[ri]
        out_vals = out[obj["mask"]]
        unique_out = np.unique(out_vals)
        print(f"  Removed obj {ri}: area={obj['area']}, color={obj['primary_color']}, "
              f"output_vals_at_mask={unique_out}")

    # Check: does the output differ from input only at removed objects?
    diff = inp != out
    diff_at_removed = np.zeros_like(diff)
    for ri in rem_idx:
        diff_at_removed |= objs[ri]["mask"]

    extra_diff = diff & ~diff_at_removed
    if np.any(extra_diff):
        print(f"  OUTPUT DIFFERS FROM INPUT OUTSIDE REMOVED OBJECTS!")
        rows, cols = np.where(extra_diff)
        for r, c in zip(rows[:10], cols[:10]):
            print(f"    ({r},{c}): inp={inp[r,c]} -> out={out[r,c]}")
    else:
        print(f"  Output only differs at removed object locations")

    # What's at removed locations in output?
    for ri in rem_idx:
        obj = objs[ri]
        r1, c1, r2, c2 = obj["bbox"]
        print(f"  Removed obj {ri} bbox: ({r1},{c1})-({r2},{c2})")
        print(f"    Input region:")
        print(inp[r1:r2+1, c1:c2+1])
        print(f"    Output region:")
        print(out[r1:r2+1, c1:c2+1])

# Also check: are there same-shape filter tasks where output has ALL removed objects
# replaced with a SPECIFIC color (not 0)?
print("\n\n=== Scanning for non-zero replacement patterns ===")
count_recolor_remove = 0
for tid2 in sorted(tasks.keys()):
    task2 = tasks[tid2]
    pairs = [(np.array(ex["input"]), np.array(ex["output"])) for ex in task2["train"]]
    if len(pairs) < 3:
        continue
    if not all(i.shape == o.shape for i, o in pairs):
        continue

    replacement_colors = set()
    valid = True
    for inp, out in pairs:
        objs = _extract_objects_with_properties(inp)
        result = _classify_kept_removed(objs, inp, out)
        if result is None:
            valid = False
            break
        kept_idx, rem_idx = result

        # Check if kept objects are unchanged
        kept_ok = all(np.array_equal(inp[objs[ki]["mask"]], out[objs[ki]["mask"]]) for ki in kept_idx)
        if not kept_ok:
            valid = False
            break

        # Check what removed objects become
        for ri in rem_idx:
            out_vals = out[objs[ri]["mask"]]
            unique = np.unique(out_vals)
            if len(unique) == 1 and unique[0] != 0:
                replacement_colors.add(int(unique[0]))
            elif len(unique) == 1 and unique[0] == 0:
                pass  # normal zero-out
            else:
                valid = False
                break
        if not valid:
            break

    if valid and replacement_colors:
        if len(replacement_colors) == 1:
            rc = list(replacement_colors)[0]
            count_recolor_remove += 1
            if count_recolor_remove <= 10:
                print(f"  {tid2}: removed objects replaced with color {rc}")

print(f"\nTotal tasks with non-zero replacement: {count_recolor_remove}")
