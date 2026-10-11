"""The reasoner side of the growth-repair pilot v2, per task (protocol
sections 6 to 8).

Phase B (instances): the failure evidence, extracted from the task's own
demonstrations by the reach v1 observation-only wrapper (cora_reach.instances)
during one identity-frame native induction, under the measurement's budget
and hard cap. Phase C (cora): the reach v1 measurement policy,
cora_reach.measure.run_task, frozen at c8d8e3a and used unchanged. The
deployable output follows pilot v1 section 7. Nothing here reads a target.
"""
from __future__ import annotations

import json
import os
import time

from cora_reach import instances as INST
from cora_reach import measure as M

VERSION = "real-arc-growth-pilot-v2"


def donor(keys, key) -> str:
    """The SHUFFLED_FAILURE donor: the next key in sorted order (cyclic)."""
    keys = sorted(keys)
    return keys[(keys.index(key) + 1) % len(keys)]


def run_instances(key, task, obj_dir, out_dir) -> dict:
    """Phase B: memorized pattern-fallback instances of one identity-frame
    induction on the demonstrations (budget 90 s, hard cap 450 s), written
    to out_dir/<key>.json; a capped extraction writes no instance."""
    HT = M._hard_timeout()
    train, _tests = M.arrays(task)
    M.clear_engine_caches()
    t0 = time.time()
    timeout = False
    try:
        with M.hard_cap(M.EXTRACT_CAP_S):
            _ind, inst = INST.extract(train, obj_dir, budget_s=M.BUDGET_S)
    except HT:
        inst, timeout = [], True
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{key}.json")
    with open(path + ".tmp", "w") as handle:
        json.dump({"instances": inst}, handle)
    os.replace(path + ".tmp", path)
    return {"key": key, "version": VERSION, "seconds": round(time.time() - t0, 3), "timeout": timeout,
            "instances": len(inst), "with_grid": sum(1 for i in inst if i.get("grid") is not None),
            "demos_with_instances": sorted({i["demo"] for i in inst if i.get("demo") is not None})}


def run_cora(key, task, ctx) -> dict:
    """Phase C: the frozen reach v1 policy on one pilot task."""
    row = M.run_task(key, task, ctx)
    row["pilot_version"] = VERSION
    return row


def system_attempts(native_row, cora_row, n_test) -> list:
    """The deployable output (pilot v1 section 7, unchanged): native
    attempts, with an activated CORA prediction taking attempt 2 when native
    has an attempt 1 for that test input, and attempt 1 otherwise."""
    a1 = (native_row or {}).get("attempt_1") or [None] * n_test
    a2 = (native_row or {}).get("attempt_2") or [None] * n_test
    cp = (cora_row or {}).get("cora_prediction") if (cora_row or {}).get("activated") else None
    out = []
    for i in range(n_test):
        if cp is not None and cp[i] is not None:
            out.append([a1[i], cp[i]] if a1[i] is not None else [cp[i], a2[i]])
        else:
            out.append([a1[i], a2[i]])
    return out


def compose(tasks, native_rows, cora_rows) -> dict:
    """Every arm's committed predictions, per key, before any target is read."""
    preds = {}
    for k, t in sorted(tasks.items()):
        n = len(t["test"])
        c = cora_rows.get(k) or {}
        nat = native_rows.get(k) or {}
        preds[k] = {
            "native": {"attempt_1": nat.get("attempt_1"), "attempt_2": nat.get("attempt_2")},
            "kalone": (c.get("kalone") or {}).get("predictions"),
            "cora_with_e": (c.get("with_e") or {}).get("predictions"),
            "activated": bool(c.get("activated")),
            "cora_prediction": c.get("cora_prediction"),
            "removed": (c.get("removed") or {}).get("predictions"),
            "matched": (c.get("matched") or {}).get("predictions"),
            "controls": {arm: (((c.get("controls") or {}).get(arm) or {}).get("with_e") or {}).get("predictions")
                         for arm in M.CONTROL_ARMS},
            "system": system_attempts(nat, c, n)}
    return preds
