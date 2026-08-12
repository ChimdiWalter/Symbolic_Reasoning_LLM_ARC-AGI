#!/usr/bin/env python3
"""Check how many tasks reach conjunction search and whether any conjunctions
could discriminate where single properties fail."""
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


def load_arc():
    base = Path(__file__).resolve().parent.parent
    with open(base / "data/arc/arc-agi_training_challenges.json") as f:
        tasks = json.load(f)
    with open(base / "data/arc/arc-agi_training_solutions.json") as f:
        solutions = json.load(f)
    return tasks, solutions


def check_conjunction_candidates():
    tasks, solutions = load_arc()
    adapter = GridDomainAdapter()
    all_props = adapter.property_names()

    same_shape_filter_tasks = 0
    single_prop_solved = 0
    conjunction_candidates = 0
    conjunction_found = []

    for tid in sorted(tasks.keys()):
        task = tasks[tid]
        train_pairs = [
            (np.array(ex["input"]), np.array(ex["output"]))
            for ex in task["train"]
        ]

        if len(train_pairs) < 3:
            continue

        # Check same shape
        all_same = all(i.shape == o.shape for i, o in train_pairs)
        if not all_same:
            continue

        # Check if classification works
        classifications = []
        valid = True
        for inp, out in train_pairs:
            objs = _extract_objects_with_properties(inp)
            result = _classify_kept_removed(objs, inp, out)
            if result is None:
                valid = False
                break
            classifications.append((objs, result))
        if not valid:
            continue

        same_shape_filter_tasks += 1

        # Check single property
        single_found = False
        for prop in all_props:
            for keep in [True, False]:
                ok = True
                for objs, (kept_idx, rem_idx) in classifications:
                    for ki in kept_idx:
                        if _get_property_value(objs[ki], prop) != keep:
                            ok = False
                            break
                    if not ok:
                        break
                    for ri in rem_idx:
                        if _get_property_value(objs[ri], prop) == keep:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    single_found = True
                    break
            if single_found:
                break

        if single_found:
            single_prop_solved += 1
            continue

        # No single property works — try conjunction
        for i, p1 in enumerate(all_props):
            for p2 in all_props[i+1:]:
                for keep_match in [True, False]:
                    ok = True
                    for objs, (kept_idx, rem_idx) in classifications:
                        for ki in kept_idx:
                            v = (_get_property_value(objs[ki], p1) and
                                 _get_property_value(objs[ki], p2))
                            if v != keep_match:
                                ok = False
                                break
                        if not ok:
                            break
                        for ri in rem_idx:
                            v = (_get_property_value(objs[ri], p1) and
                                 _get_property_value(objs[ri], p2))
                            if v == keep_match:
                                ok = False
                                break
                        if not ok:
                            break
                    if ok:
                        conjunction_candidates += 1
                        conjunction_found.append((tid, p1, p2, keep_match))
                        break
                if conjunction_found and conjunction_found[-1][0] == tid:
                    break
            if conjunction_found and conjunction_found[-1][0] == tid:
                break

    print(f"Same-shape filter-eligible tasks: {same_shape_filter_tasks}")
    print(f"Single property discriminates: {single_prop_solved}")
    print(f"Conjunction discriminates (new): {conjunction_candidates}")
    for tid, p1, p2, keep in conjunction_found:
        print(f"  {tid}: ({p1} AND {p2}), keep_when_match={keep}")


if __name__ == "__main__":
    check_conjunction_candidates()
