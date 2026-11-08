"""From holes' candidate lists to a task's answer, as `objgrow.arm.construction_answers` does it: holes in rank
order, repeats dropped (the first copy kept), the multi-pair candidates in that order, the retry of the first at most
3 (the task searched again with G0 plus the candidate, A2's base search, two attempts); the first retry that fits
gives the answer. A retry is a pure function of (candidate, task) and is cached."""
import json
import os

from gcon import env as E
from objgrow import edits as ED, gates as GT

M_RETRIES = GT.M_RETRIES


def unit_candidates(tops):
    """tops: per hole (rank order) its candidate list, each candidate a dict with sid, spec, loo, ..."""
    seen, out = set(), []
    for rank, top in enumerate(tops):
        for c in top:
            if c["sid"] not in seen:
                seen.add(c["sid"])
                out.append(dict(c, hole_rank=rank))
    return out


class Retrier:
    def __init__(self, g0b, path=None):
        self.plug = GT.ObjPlugin(g0b)
        self.path = path
        self.cache = {}
        self.new = 0
        if path and os.path.exists(path):
            with open(E.check_read(path), encoding="utf-8") as f:
                for x in f:
                    if x.strip():
                        r = json.loads(x)
                        self.cache[(r["task"], r["sid"])] = r

    def seed(self, task_id, sid, res):
        self.cache.setdefault((task_id, sid), dict(res, task=task_id, sid=sid, seeded=True))

    def retry(self, task_id, task, sid, spec):
        k = (task_id, sid)
        if k not in self.cache:
            op = ED.ObjOp(spec)
            r = self.plug.search(self.plug.with_structure(op), task["train"], task["test_inputs"],
                                 self.plug.BASE_BUDGET, self.plug.BASE_CPU, 2)
            rec = {"task": task_id, "sid": sid, "fit": bool(r["fit"]), "preds": r["preds"], "program": r["program"],
                   "cpu_s": r["cpu_s"]}
            self.cache[k] = rec
            self.new += 1
            if self.path:
                with E.open_write(self.path, "a") as f:
                    f.write(json.dumps(rec, sort_keys=True, default=list) + "\n")
        return self.cache[k]


def answer(tops, task_id, task, retrier, retries=M_RETRIES):
    cands = unit_candidates(tops)
    out = {"fit": False, "preds": None, "program": None, "stage": "construction_none", "op": None,
           "candidates": len(cands), "candidates_loo": sum(1 for c in cands if c["loo"]), "retries": []}
    for c in [c for c in cands if c["loo"]][:retries]:
        r = retrier.retry(task_id, task, c["sid"], c["spec"])
        out["retries"].append({"sid": c["sid"], "fit": r["fit"], "hole_rank": c["hole_rank"]})
        if r["fit"]:
            out.update(fit=True, preds=r["preds"], program=r["program"], stage="construction", op=c["sid"])
            break
    return out
