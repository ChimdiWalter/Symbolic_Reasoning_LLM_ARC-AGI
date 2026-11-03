"""Fitting programs -> ranked behaviours -> two attempts per query, and export in the score-first branch's format.

Selection rule (pre-declared for every CAST module; frozen 27 Oct before any evaluation run):
  1. Only programs that reproduce EVERY demonstration are candidates. Group them by their predictions on the queries
     (two programs that fit but disagree on a query stay separate behaviours).
  2. Non-vacuity: a query prediction equal to that query's input is dropped when every demonstration changes its
     input (the synthesis review's identity-attempt defect).
  3. Rank behaviours by: complete (no undetermined cell on any query) first; then leave-one-demonstration-out
     support (higher first); then group size (more agreeing programs first); then program cost (lower first); then
     enumeration order. Deterministic; no randomness; no answer access.
  4. Attempts per query: the first two distinct valid grids in that order.
Export (`to_program_candidates`) follows kaggle/hybrid_2026/llm_writer/program_candidates.py:
  {"per_test": [[{"grid", "tier", "score", "certified", "loo", "group_size", "program", "candidate"}, ...], ...],
   "n_programs", "n_fits", "n_groups", "failures"}; tier is "CAST_FIT" or "CAST_PARTIAL" (incomplete completion).
Whether the score-first entry imports these is the author's decision through the SUBMISSION_READY gate.
"""
import numpy as np

from . import grids as G


def _key(p):
    return None if p is None else (tuple(np.asarray(p).shape), np.asarray(p).tobytes())


def rank(fits, task):
    """fits: [{"program", "preds", "complete": [bool per query], "loo": float, "cost": float, "order": int}]"""
    every_changes = all(np.asarray(x).shape != np.asarray(y).shape or not np.array_equal(x, y)
                        for x, y in task["train"])
    groups = {}
    for f in fits:
        preds = []
        for q, p in zip(task["test_inputs"], f["preds"]):
            if p is None or not G.valid_grid(p):
                preds.append(None)
                continue
            if every_changes and np.asarray(p).shape == np.asarray(q).shape and np.array_equal(p, q):
                preds.append(None)                    # vacuous
                continue
            preds.append(p)
        k = tuple(_key(p) for p in preds)
        if all(x is None for x in k):
            continue
        g = groups.setdefault(k, {"preds": preds, "members": [], "complete": True, "loo": 0.0, "cost": 1e9,
                                  "order": 1e9})
        g["members"].append(f)
        g["complete"] = g["complete"] and all(f.get("complete", [True] * len(preds)))
        g["loo"] = max(g["loo"], f.get("loo", 0.0))
        g["cost"] = min(g["cost"], f.get("cost", 1.0))
        g["order"] = min(g["order"], f.get("order", 0))
    out = sorted(groups.values(), key=lambda g: (not g["complete"], -g["loo"], -len(g["members"]), g["cost"],
                                                  g["order"]))
    return out


def attempts(groups, n_queries):
    per = []
    for j in range(n_queries):
        atts, seen = [], set()
        for g in groups:
            p = g["preds"][j] if j < len(g["preds"]) else None
            k = _key(p)
            if p is None or k in seen:
                continue
            seen.add(k)
            atts.append(np.asarray(p).tolist())
            if len(atts) == 2:
                break
        per.append(atts)
    return per


def to_program_candidates(groups, n_queries, n_programs, failures=None, limit=2):
    per = [[] for _ in range(n_queries)]
    for gi, g in enumerate(groups):
        best = g["members"][0]
        for j in range(n_queries):
            p = g["preds"][j] if j < len(g["preds"]) else None
            if p is None or len(per[j]) >= limit or any(np.asarray(p).tolist() == x["grid"] for x in per[j]):
                continue
            per[j].append({"grid": np.asarray(p).tolist(), "tier": "CAST_FIT" if g["complete"] else "CAST_PARTIAL",
                           "score": round(float(len(per[j]) == 0) + g["loo"], 3), "certified": False,
                           "loo": round(float(g["loo"]), 3), "group_size": len(g["members"]),
                           "program": best["program"], "candidate": f"cast-{gi}"})
    return {"per_test": per, "n_programs": n_programs, "n_fits": sum(len(g["members"]) for g in groups),
            "n_groups": len(groups), "failures": failures or {}}
