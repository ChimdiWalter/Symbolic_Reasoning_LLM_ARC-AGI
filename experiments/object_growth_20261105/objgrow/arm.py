"""The object-level step as an arm for another study: answers for one task from its demonstrations and test inputs.

    reuse_answers(task, ops)          G0 plus the given registry operations, the base search: two attempts
    construction_answers(task, ops)   the base search with G0 plus ops; on a failure, the controller's typed holes
                                      (identity plus the two best invertible decompositions), the object-level
                                      constructor, and the retry of its leave-one-out candidates (at most 3, as
                                      the gates' retry cap); the first fitting retry's two attempts are the answer

A task is {"train": [(input grid, output grid)], "test_inputs": [grid]} with tuple grids (ngrow.data.tasks gives
this form). Every result carries its process CPU (search, construction and retries) so that a matched static
control can be given the same CPU. These functions never open a test output and know nothing about splits: the
caller's study decides what tasks they see (held halves and the evaluation set stay closed in this study).
"""
import time

from objgrow import env as E, gates as GT, grow as GR
from ngrow import plugin as PL
from cgrow import controller as CT
from a2 import arcdsl as D

_SHARED = {}


def _shared(g0b):
    if "g0b" not in _SHARED:
        _SHARED["g0b"] = g0b or PL.G0Builder()
        _SHARED["fns"] = D.guarded(D.load()[0])
    return _SHARED["g0b"], _SHARED["fns"]


def ops_from_registry(registry_doc):
    """The operations of a registry.json document (its `registry` order)."""
    from objgrow import edits as ED
    return [ED.ObjOp.from_json(registry_doc["ops"][s]) for s in registry_doc["registry"]]


def reuse_answers(task, ops=(), g0b=None):
    g0b, _ = _shared(g0b)
    plug = GT.ObjPlugin(g0b, ops)
    r = plug.search(plug.g0(), task["train"], task["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
    return {"fit": r["fit"], "preds": r["preds"], "program": r["program"], "cpu_s": r["cpu_s"], "stage": "base"}


def construction_answers(task, ops=(), g0b=None, retries=GT.M_RETRIES):
    g0b, fns = _shared(g0b)
    t0 = time.process_time()
    plug = GT.ObjPlugin(g0b, ops)
    base = plug.search(plug.g0(), task["train"], task["test_inputs"], plug.BASE_BUDGET, plug.BASE_CPU, 2)
    out = {"fit": base["fit"], "preds": base["preds"], "program": base["program"], "stage": "base",
           "base_cpu_s": base["cpu_s"], "candidates": 0, "candidates_loo": 0, "retries": []}
    if not base["fit"] and len(task["train"]) >= 2:
        sks, _ = CT.sketches(task["train"], plug.g0())
        skd = [{"form": c["form"], "outer": c["outer"], "inner": c["inner"], "score": c["score"], "pairs": c["pairs"]}
               for c in sks]
        con = GR.construct_unit({"sketches": skd}, task, fns)
        out.update(candidates=len(con["candidates"]), candidates_loo=sum(1 for c in con["candidates"] if c["loo"]),
                   construction_cpu_s=con["construction_cpu_s"], counts=con["counts"])
        for c in [c for c in con["candidates"] if c["loo"]][:retries]:
            op = c["op"]
            r = plug.search(plug.with_structure(op), task["train"], task["test_inputs"], plug.BASE_BUDGET,
                            plug.BASE_CPU, 2)
            out["retries"].append({"sid": op.sid, "expr": op.expr(), "fit": r["fit"], "cpu_s": r["cpu_s"],
                                   "hole_rank": c["hole_rank"]})
            if r["fit"]:
                out.update(fit=True, preds=r["preds"], program=r["program"], stage="construction",
                           op=op.to_json())
                break
    out["cpu_s"] = round(time.process_time() - t0, 3)
    return out


if __name__ == "__main__":
    import json
    import sys
    from ngrow import data as DT
    bench, tid = sys.argv[1], sys.argv[2]
    src = {t for b, f, t in DT.half("source", (bench,))}
    if tid not in src:
        raise SystemExit("development runs use source tasks only")
    res = construction_answers(DT.tasks(bench)[tid])
    print(json.dumps({k: v for k, v in res.items() if k != "preds"}, default=str)[:1500])
