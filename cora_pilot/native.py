"""NATIVE_BASELINE (protocol section 6, step A): the sealed per-task entry.

harness.run_harness.run_one_task is the entry that produced the sealed
185/1000 (pipeline, GeoCat and object layers, hard-capped, LOO-certified
acceptance for GeoCat and object). It runs here exactly as in the sealed
v23 chain: the five chain flags (RUN_HISTORY 2026-08-19), the default caps
(pipeline 60 s cooperative / 150 s hard, GeoCat 120 s, object 90 s / 105 s
plus the frames allowance) and the frozen library in the object layer's
directory. The solution argument is None, so the layers run in submission
mode: nothing is scored, attempt 1 is the solving layer's render and
attempt 2 the object layer's best uncertified partial. The task identifier
the engine sees is the opaque key.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time

#: the sealed v23 chain flags (RUN_HISTORY 2026-08-19; cora_tti.full_engine_solver)
CHAIN_FLAGS = {"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
               "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"}
LIBRARY_SHA256 = "cdacd018da0bd9a3fa460c23beeff89fd5b0c5a85d70ecca276fe212df13ce03"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY = os.path.join(HERE, "library.json")


def environment_problems() -> list:
    problems = []
    for k, v in CHAIN_FLAGS.items():
        if os.environ.get(k) != v:
            problems.append(f"{k} is {os.environ.get(k)!r}, not {v!r}")
    for k in sorted(os.environ):
        if k.startswith("ARC_") and k not in CHAIN_FLAGS:
            problems.append(f"foreign {k}")
    if os.environ.get("PYTHONHASHSEED") != "0":
        problems.append("PYTHONHASHSEED is not 0")
    return problems


def prepare_object_dir(out_dir: str) -> str:
    """The object layer's directory with the frozen library, as in the
    sealed runs (the library is byte-identical from v20 to v23)."""
    obj = os.path.join(out_dir, "object")
    os.makedirs(obj, exist_ok=True)
    dst = os.path.join(obj, "library.json")
    with open(LIBRARY, "rb") as handle:
        data = handle.read()
    if hashlib.sha256(data).hexdigest() != LIBRARY_SHA256:
        raise ValueError("frozen library.json hash mismatch")
    if not os.path.exists(dst):
        with open(dst + ".tmp", "wb") as handle:
            handle.write(data)
        os.replace(dst + ".tmp", dst)
    return obj


def _grids(preds, n):
    out = [None] * n
    if isinstance(preds, list):
        for i in range(min(n, len(preds))):
            p = preds[i]
            out[i] = p if isinstance(p, list) else None
    return out


def run_native(key: str, task: dict, out_dir: str) -> dict:
    """One task through the sealed entry; returns the committed attempts and
    the layer record (no score: there is nothing to score against)."""
    from harness.run_harness import run_one_task
    obj = prepare_object_dir(out_dir)
    config = {"run_id": "real-arc-pilot-v1", "timeout_per_task": 60.0, "per_layer_timeout": 8.0,
              "submission_mode": True, "emit_predictions": True, "object_out_dir": obj}
    n = len(task["test"])
    t0 = time.time()
    rec = run_one_task((key, {"train": task["train"], "test": task["test"]}, None, config))
    preds = rec.get("predictions") or {}
    return {"key": key, "seconds": round(time.time() - t0, 3),
            "claimed": bool(rec.get("solved")), "origin": rec.get("origin"), "layer": rec.get("layer"),
            "attempt_1": _grids(preds.get("attempt_1"), n), "attempt_1_source": preds.get("attempt_1_source"),
            "attempt_2": _grids(preds.get("attempt_2"), n), "attempt_2_class": preds.get("attempt_2_class"),
            "errors": {name: (rec.get(name) or {}).get("error") for name in ("pipeline", "geocat", "object")},
            "layer_seconds": {name: (rec.get(name) or {}).get("elapsed_s")
                              for name in ("pipeline", "geocat", "object")}}


def clean_object_dir(out_dir: str) -> None:
    shutil.rmtree(os.path.join(out_dir, "object"), ignore_errors=True)
