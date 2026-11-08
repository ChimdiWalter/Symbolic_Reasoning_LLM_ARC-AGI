"""The object-level growth arms (5 to 8): the contract with the builder's frozen code in
`experiments/object_growth_20261105/` (amendment 2; FREEZE.json's `object_growth` slot pins its files).

Contract (the builder's `objgrow/arm.py`):
  ops_from_registry(registry_doc)          the operations of a registry.json document (its `registry` order);
  reuse_answers(task, ops, g0b)            G0 plus the operations, the base search, two attempts, with its process CPU;
  construction_answers(task, ops, g0b)     the base search with G0 plus the operations; on a failure, the controller's
                                           typed holes from the task's own demonstrations, the object-level
                                           constructor and the retry of at most 3 candidates that are exact on all
                                           demonstrations and accepted by the declared proposal heuristic (the edit
                                           bound in at least two demonstration pairs; whole-output forms flagged
                                           unconditionally; colour tables counting any pair with a constant
                                           recolouring; the builder's field named "loo" is this source proposal
                                           heuristic, not a withheld-pair reconstruction); the first fitting retry's
                                           two attempts; with its process CPU.
These functions never see a test output. Every call here passes this study's seed-independent grammar builder.
Registries: the builder's `runs/v2/<benchmark>/registry.json` (own holes), bound by digest to the freeze slot.
Shuffled registry (arm 6): the first |R(b)| operations of the other benchmarks' registries in
sha256("obj-shuffle:" + b + "|" + sid) order (shortfall recorded). Donor demonstrations (arm 8): the held task's
test inputs with the demonstrations of the next held task in sha256("obj-donor:" + id) order whose family differs
(Mini-ARC: the next task).
Source-half cost of the object route (charged to arms 5 and 7, scaled by the kernel's speed factor): study A's
controller CPU on every source task of the benchmark (the holes come from it) plus the builder's recorded
construction, gate and combined-check CPU for the registry, read from the frozen, packaged record
`feasibility/object_costs.json` (written on Athe by ngb/object_costs.py; amendment 3), so that a kernel never needs
study A's controller records.
"""
import hashlib
import importlib
import json
import os
import sys

from ngb import env as E, gate as GT, ops as OP
from ngrow import data as DT

CONFIG = os.path.join(E.STUDY, "config", "STUDY_CONFIG.json")
COSTS = os.path.join(E.STUDY, "feasibility", "object_costs.json")
_CACHE = {}


def spec():
    return E.load(CONFIG).get("object_growth") or {}


def available():
    s = spec()
    fr = E.load(GT.FREEZE) if os.path.exists(GT.FREEZE) else {}
    return bool(s.get("module") and s.get("functions") and s.get("registries")) and \
        bool((fr.get("object_growth") or {}).get("code_sha256"))


def folder():
    return os.path.join(E.REPO, spec()["folder"])


def _mod():
    if "mod" not in _CACHE:
        s = spec()
        os.environ.setdefault("OG_REPO", E.REPO)
        os.environ.setdefault("OG_STUDY", folder())
        if folder() not in sys.path:
            sys.path.insert(0, folder())
        _CACHE["mod"] = importlib.import_module(s["module"])
    return _CACHE["mod"]


def _g0b():
    if "g0b" not in _CACHE:
        _CACHE["g0b"] = OP.G0Builder()
    return _CACHE["g0b"]


def registry_path(bench):
    return os.path.join(E.REPO, spec()["registries"][bench])


def registry_doc(bench):
    """The registry document, bound by digest to the freeze slot."""
    rel = spec()["registries"][bench]
    want = ((E.load(GT.FREEZE).get("object_growth") or {}).get("files_sha256") or {}).get(rel)
    have = E.sha_file(registry_path(bench))
    if want is None or want != have:
        raise RuntimeError(f"registry for {bench} is not the frozen one ({rel})")
    return E.load(registry_path(bench))


def ops(bench):
    return list(getattr(_mod(), spec()["functions"]["ops"])(registry_doc(bench)))


def shuffled_ops(bench):
    want = len(ops(bench))
    pool = [(b2, o) for b2 in DT.BENCHMARKS if b2 != bench for o in ops(b2)]
    pool.sort(key=lambda x: hashlib.sha256(f"obj-shuffle:{bench}|{x[1].sid}".encode()).hexdigest())
    return [o for _, o in pool[:want]], {"wanted": want, "available": len(pool), "shortfall": max(0, want - len(pool))}


def union_ops():
    out, seen = [], set()
    for b in DT.BENCHMARKS:
        for o in ops(b):
            if o.sid not in seen:
                seen.add(o.sid)
                out.append(o)
    return out


def reuse(task, op_list):
    return getattr(_mod(), spec()["functions"]["reuse"])(task, op_list, _g0b())


def construct(task, op_list):
    return getattr(_mod(), spec()["functions"]["construction"])(task, op_list, _g0b())


def costs(bench):
    """The frozen cost record of one benchmark, bound by digest to the freeze."""
    rel = os.path.relpath(COSTS, E.REPO)
    want = GT.frozen_hash(rel)
    if want is None or E.sha_file(COSTS) != want:
        raise RuntimeError(f"{rel} is not the frozen cost record")
    rec = E.load(COSTS)["benchmarks"][bench]
    if rec["registry_sha256"] != E.sha_file(registry_path(bench)):
        raise RuntimeError(f"{bench}: the cost record was made from another registry")
    return rec


def source_cost(bench):
    """CPU-seconds, Athe-measured: controller on every source task plus the builder's registry costs."""
    return costs(bench)["source_cost_cpu_s"]


def donor_of(bench, tid, half="held"):
    rows = DT.half(half, (bench,))
    fam = {t: f for _, f, t in rows}
    order = sorted((t for _, _, t in rows), key=lambda t: hashlib.sha256(f"obj-donor:{t}".encode()).hexdigest())
    i = order.index(tid)
    for j in range(1, len(order)):
        c = order[(i + j) % len(order)]
        if fam[c] != fam[tid] or bench == "mini_arc":
            return c
    return None
