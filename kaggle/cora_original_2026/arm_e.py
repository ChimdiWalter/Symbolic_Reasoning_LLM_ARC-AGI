#!/usr/bin/env python3
"""Arm E of the real-task check (records/NEURAL_CORA_REALARC_G2G3G4_PROTOCOL_20261021.md): the CORA-ONLY-G3
competition configuration (CONFIG.md) on one task, run as the Kaggle notebook runs it, through the notebook's own
functions (cora_only.py):
- the sealed native v23 harness (the unchanged kaggle/native_v1 archive, sha-checked) on this task alone, one worker,
  the sealed flags and assets, `--emit-predictions`, a 900 s global budget (its per-task defaults apply);
- ncv2-g3 search (variant G3: 3,000 candidates, soft CPU cap 120 s) in an isolated child with the notebook's hard
  limits (300 CPU-s, 600 s wall);
- the "precision" attempt policy.
The runner calls `cora_only_g3(task, budget, cpu_cap_s)` with the task's inputs only ({"task_id", "train",
"test_inputs"}). The configuration is the notebook's, so `budget` and `cpu_cap_s` are recorded but not used: arm E
measures the competition configuration as it is.
"""
import hashlib
import importlib.util
import json
import os
import resource
import shutil
import tarfile
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
NATIVE_TAR = os.path.join(REPO, "kaggle", "native_v1", "arc_native_baseline_v1.tar.gz")
NATIVE_TAR_SHA = "4b320ba2fe92b12bcc4345ef4523ca45115f7694e3ab999dfea6b1cfe3c9a088"
CACHE = os.path.join(REPO, "outputs", "neural_cora_realarc_g2g3g4", "arm_e_work")
NATIVE_BUDGET_S = 900


def _cora_only():
    spec = importlib.util.spec_from_file_location("cora_only_arm_e", os.path.join(HERE, "cora_only.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _native_tree():
    """The sealed native tree, extracted once (atomically, so concurrent workers are safe)."""
    dest = os.path.join(CACHE, "native_v23")
    if os.path.isdir(os.path.join(dest, "geocat_arc")):
        return dest
    if hashlib.sha256(open(NATIVE_TAR, "rb").read()).hexdigest() != NATIVE_TAR_SHA:
        raise RuntimeError("the frozen native_v1 archive changed")
    os.makedirs(CACHE, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="native_", dir=CACHE)
    with tarfile.open(NATIVE_TAR) as t:
        t.extractall(tmp)
    try:
        os.rename(tmp, dest)
    except OSError:                                            # another worker extracted it first
        shutil.rmtree(tmp, ignore_errors=True)
    return dest


def cora_only_g3(task, budget, cpu_cap_s):
    co = _cora_only()
    tid = task.get("task_id", "task")
    tj = {"train": [{"input": a, "output": b} for a, b in task["train"]], "test": [{"input": x} for x in task["test_inputs"]]}
    tree = _native_tree()
    work = tempfile.mkdtemp(prefix=f"e_{tid}_", dir=CACHE)
    code = os.path.join(work, "solver")
    shutil.copytree(tree, code)
    data = os.path.join(code, "data", "arc")
    os.makedirs(data, exist_ok=True)
    json.dump({tid: tj}, open(os.path.join(data, "arc-agi_evaluation_challenges.json"), "w"))
    json.dump({}, open(os.path.join(data, "arc-agi_evaluation_solutions.json"), "w"))
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    w0 = time.time()
    man, errors = {}, []
    try:                                                       # each phase may fail alone; the policy still answers
        native_rows = co.run_native(code, os.path.join(work, "run"), NATIVE_BUDGET_S, 1, man)
    except Exception as e:                                     # noqa: BLE001
        native_rows, errors = {}, errors + [f"native: {type(e).__name__}: {str(e)[:200]}"]
    try:
        variant = co.VARIANTS["G3"]
        res = co.run_search(REPO, {tid: tj}, native_rows, "G3", time.time() + variant["wall"] + 120, 1,
                            os.path.join(work, "run"))
    except Exception as e:                                     # noqa: BLE001
        res, errors = {}, errors + [f"g3: {type(e).__name__}: {str(e)[:200]}"]
    sub, prov = co.merge({tid: tj}, native_rows, res, "precision")
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    g = res.get(tid, {})
    nrow = native_rows.get(tid) or {}
    p = nrow.get("predictions") or {}
    preds = []
    for grid in [(p.get("attempt_1") or [None])[0], (p.get("attempt_2") or [None])[0]] + list(g.get("predictions") or []):
        if co._valid(grid) and grid not in preds:
            preds.append(grid)
    shutil.rmtree(work, ignore_errors=True)
    native_fit = any((nrow.get(k) or {}).get("solved") for k in ("pipeline", "geocat", "object"))
    return {"attempts_by_test": [[e["attempt_1"], e["attempt_2"]] for e in sub[tid]],
            "predictions": preds[:50], "n_distinct_predictions": len(preds),
            "n_consistent": (g.get("n_consistent") or 0) + (1 if native_fit else 0),
            "n_candidates": g.get("n_candidates") or 0, "first_fit_at": g.get("first_fit_at"),
            "provenance": prov[tid], "g3_status": g.get("status"), "native_status": man.get("native_status"),
            "phase_errors": errors,
            "native_layer": nrow.get("layer"), "native_object_certified": co.object_certified(nrow),
            "cpu_s": round((ru1.ru_utime + ru1.ru_stime) - (ru0.ru_utime + ru0.ru_stime), 2),
            "wall_s": round(time.time() - w0, 1), "runner_budget": budget, "runner_cpu_cap_s": cpu_cap_s,
            "configuration": "CORA-ONLY-G3 (kaggle/cora_original_2026/CONFIG.md), policy precision"}
