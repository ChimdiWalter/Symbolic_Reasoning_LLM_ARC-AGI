"""Memorized growth instances: the failure evidence for growth-relation
construction (docs/CORA_REAL_TASK_REACH_DEV_v1.md, section 4).

During one identity-frame native induction (native configuration: chain
flags, frozen library and learned verbs; no dihedral frames), every call of
correspondence.detect_grow that ends in the constant `pattern` fallback is
recorded: the input object's cells and colours, the output object's cells
and colours, the grid shape and the input grid. Observation only: the
wrapper returns the original result unchanged and is removed on exit.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time

import numpy as np


@contextlib.contextmanager
def observed():
    import geocat_arc.object_reasoning.correspondence as CO
    orig = CO.detect_grow
    seen = []

    def detect_grow(in_cc, out_cc, bounds, grid=None):
        res = orig(in_cc, out_cc, bounds, grid)
        if res is not None and res.get("mode") == "pattern":
            seen.append((in_cc, out_cc, bounds, grid))
        return res
    CO.detect_grow = detect_grow
    try:
        yield seen
    finally:
        CO.detect_grow = orig


def _grid_list(grid):
    if grid is None:
        return None
    if hasattr(grid, "to_numpy"):
        a = grid.to_numpy()
    else:
        a = np.asarray(grid)
    if a.ndim != 2:
        return None
    return a.astype(int).tolist()


def _cells(cc):
    return sorted([[int(r), int(c)], int(col)] for (r, c), col in cc.items())


def extract(train_pairs, obj_dir, budget_s=90.0):
    """(induction, unique instances) for one task's demonstrations."""
    from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
    from geocat_arc.object_reasoning.inducer import InductionConfig, induce_program
    from geocat_arc.object_reasoning.types import to_grid_pairs
    eng = ObjectReasoningEngine(obj_dir, use_library=True, config=InductionConfig(budget_s=budget_s))
    cfg = eng._config_with_library()
    with observed() as seen:
        ind = induce_program(to_grid_pairs(train_pairs), cfg)
    inputs = {hashlib.sha256(json.dumps(np.asarray(a).astype(int).tolist()).encode()).hexdigest(): d
              for d, (a, _b) in enumerate(train_pairs)}
    uniq = {}
    for in_cc, out_cc, bounds, grid in seen:
        key = (tuple(sorted(in_cc.items())), tuple(sorted(out_cc.items())))
        if key in uniq:
            continue
        g = _grid_list(grid)
        gh = hashlib.sha256(json.dumps(g).encode()).hexdigest() if g is not None else None
        uniq[key] = {"in": _cells(in_cc), "out": _cells(out_cc), "bounds": list(bounds),
                     "demo": inputs.get(gh), "grid": g}
    return ind, list(uniq.values())


def run_instances(key, task, obj_root, out_dir):
    from cora_pilot import native as N
    obj = N.prepare_object_dir(obj_root)
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in task["train"]]
    t0 = time.time()
    ind, inst = extract(train, obj)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{key}.json"), "w") as handle:
        json.dump({"instances": inst}, handle)
    demos = sorted({i["demo"] for i in inst if i["demo"] is not None})
    return {"key": key, "seconds": round(time.time() - t0, 2), "instances": len(inst),
            "demos_with_instances": demos, "n_train": len(train),
            "failure_stage": getattr(ind.failure_stage, "value", None), "accepted": bool(ind.accepted),
            "added_sizes": sorted(len(i["out"]) - len(i["in"]) for i in inst)[:40]}
