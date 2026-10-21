"""Phase B (21 October 2026): observable, demonstration-only diagnostics of the finished real-ARC cohort's failures.

Descriptive engineering on an EXPOSED cohort. It never reruns or rescores the frozen study, and it reads no test
output. For every primary task it measures, on the demonstrations:
- view sensitivity: the share of changed cells explained by object fates in each distinct view (best and worst);
- part-level change: changed input objects whose changed cells are a strict, non-empty part of the object;
- grouping: output objects that overlap two or more input objects;
- selector separability: for each change group (scene.py), does any existing ncv2-g2 selector pick exactly its
  objects in every demonstration (best view)? A group no selector separates points to a missing relational or
  feature description; a separable group with no fitting rule points to an operation, composition or search gap;
- additive cells (background turned colour), classified by the first test they pass:
  * ray: on the row or column of a same-coloured input cell, with every cell between them added or already that colour;
  * fill: inside the bounding box of an input object (interior or holes);
  * copy: part of a translated copy of an input object's colour pattern;
  * mirror: the mirror cell across the grid's vertical or horizontal centre line is that colour in the input;
  * other.
These tests distinguish explanations of the failure classes (records/NEURAL_CORA_G4_REALARC_FAILURE_ANALYSIS_20261021.md).
They are heuristics: passing one shows a pattern consistent with an explanation, not that the explanation is right.

    python scripts/neural_cora_g4_realarc_observables.py   -> outputs/neural_cora_v2g2/realarc/observables.json
"""
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g2", "realarc")


def cohort():
    spec = importlib.util.spec_from_file_location("ra", os.path.join(HERE, "scripts", "neural_cora_v2g2_realarc_eval.py"))
    RA = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RA)
    return {t["task_id"]: t for t in RA.tasks()}


def view_explained(train):
    from cora_neural_v2 import search as G1S
    from cora_neural_v2g3 import scene as SC
    changed = sum(int((np.asarray(a) != np.asarray(b)).sum()) for a, b in train)
    out = {}
    for v in G1S.distinct_views({"train": train, "test_inputs": []}):
        sc = SC.analyse(train, v)
        if sc is None or not changed:
            continue
        cov = 0
        for (a, b), objs in zip(train, sc.objects):
            A, B = np.asarray(a), np.asarray(b)
            m = np.zeros(A.shape, dtype=bool)
            for o in objs:
                if o.fate in ("recoloured", "deleted", "moved"):
                    for x in o.cells:
                        m[x] = True
                    if o.fate == "moved":
                        for r, c in o.cells:
                            rr, cc = r + o.vector[0], c + o.vector[1]
                            if 0 <= rr < A.shape[0] and 0 <= cc < A.shape[1]:
                                m[rr, cc] = True
            cov += int(((A != B) & m).sum())
        out[v] = round(cov / changed, 3)
    return out


def _ray(A, B, r, c, k):
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        rr, cc = r - dr, c - dc
        while 0 <= rr < A.shape[0] and 0 <= cc < A.shape[1]:
            if A[rr, cc] == k:
                return True
            if B[rr, cc] != k:
                break
            rr, cc = rr - dr, cc - dc
    return False


def separability(train):
    """(groups, groups some existing selector picks exactly) in the view that separates the most groups."""
    from cora_neural_v2 import search as G1S
    from cora_neural_v2g2 import search as S2
    from cora_neural_v2g3 import scene as SC
    ev = S2.evidence2(train)
    sels = [s for s, _, _ in S2.selectors(ev)]
    best = (0, 0)
    for v in G1S.distinct_views({"train": train, "test_inputs": []}):
        sc = SC.analyse(train, v)
        if sc is None or not sc.groups:
            continue
        picks = SC.selections(v, sels, train)
        groups = [m for k, m in sc.groups.items() if len(k) == 1]          # coarse groups: one per fate
        ok = sum(any(SC.separation(picks[s], m)[0] for s in sels) for m in groups)
        if (ok, -len(groups)) > (best[1], -best[0]) or best == (0, 0):
            best = (len(groups), ok)
    return best


def task_observables(train):
    from cora_neural_v2g3 import scene as SC
    obs = {"views": view_explained(train), "part_level_objects": 0, "changed_objects": 0, "grouping_outputs": 0,
           "additive": {"ray": 0, "fill": 0, "copy": 0, "mirror": 0, "other": 0}}
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        objs, bg = SC.native_objects(A, "S1")
        outs, _ = SC.native_objects(B, "S1")
        diff = A != B
        cell_obj = {x: j for j, o in enumerate(objs) for x in o.cells}
        for o in objs:
            ch = sum(bool(diff[x]) for x in o.cells)
            if ch:
                obs["changed_objects"] += 1
                obs["part_level_objects"] += ch < len(o.cells)
        for o in outs:
            if len({cell_obj[x] for x in o.cells if x in cell_obj}) >= 2:
                obs["grouping_outputs"] += 1
        boxes = []
        for o in objs:
            rs, cs = zip(*o.cells)
            boxes.append((min(rs), max(rs), min(cs), max(cs)))
        copy_cells = set()
        for o in objs:                                  # translated copies of an input object's pattern in B
            cells = sorted(o.cells)
            if len(cells) > 64:
                continue
            (r0, c0), k = cells[0], int(A[cells[0]])
            for r, c in zip(*np.nonzero(B == k)):
                d = (int(r - r0), int(c - c0))
                if d == (0, 0):
                    continue
                dest = [(rr + d[0], cc + d[1]) for rr, cc in cells]
                if all(0 <= x < A.shape[0] and 0 <= y < A.shape[1] for x, y in dest) and \
                        all(B[p] == A[q] for p, q in zip(dest, cells)):
                    copy_cells.update(p for p in dest if A[p] == bg)
        for r, c in zip(*np.nonzero(diff & (A == bg))):
            k = int(B[r, c])
            if _ray(A, B, r, c, k):
                kind = "ray"
            elif any(r0 <= r <= r1 and c0 <= c <= c1 for r0, r1, c0, c1 in boxes):
                kind = "fill"
            elif (r, c) in copy_cells:
                kind = "copy"
            elif A[r, A.shape[1] - 1 - c] == k or A[A.shape[0] - 1 - r, c] == k:
                kind = "mirror"
            else:
                kind = "other"
            obs["additive"][kind] += 1
    return obs


def main():
    tax = {t["task_id"]: t for t in json.load(open(os.path.join(OUT, "failure_taxonomy.json")))["tasks"]}
    tasks = cohort()
    per = []
    for tid, t in tax.items():
        if t["stratum"] != "primary":
            continue
        o = task_observables(tasks[tid]["train"])
        v = list(o["views"].values())
        add = sum(o["additive"].values())
        n_groups, n_sep = separability(tasks[tid]["train"])
        per.append({"task_id": tid, "cause": t["cause"], "groups": n_groups, "groups_separable": n_sep,
                    "view_best": max(v) if v else None, "view_worst": min(v) if v else None,
                    "n_views": len(v), "part_level_share": round(o["part_level_objects"] / o["changed_objects"], 3) if o["changed_objects"] else None,
                    "grouping_outputs": o["grouping_outputs"], "additive_cells": add,
                    "additive_mix": {k: round(n / add, 3) for k, n in o["additive"].items()} if add else None})
    summary = {}
    for cause in sorted({p["cause"] for p in per}):
        P = [p for p in per if p["cause"] == cause]
        mix = [p["additive_mix"] for p in P if p["additive_mix"]]
        summary[cause] = {
            "n": len(P),
            "median_view_gap": float(np.median([p["view_best"] - p["view_worst"] for p in P if p["view_best"] is not None])) if P else None,
            "median_part_level_share": float(np.median([p["part_level_share"] for p in P if p["part_level_share"] is not None]))
            if any(p["part_level_share"] is not None for p in P) else None,
            "tasks_with_grouping_outputs": sum(p["grouping_outputs"] > 0 for p in P),
            "tasks_all_groups_separable": sum(p["groups"] > 0 and p["groups_separable"] == p["groups"] for p in P),
            "tasks_no_group_separable": sum(p["groups"] > 0 and p["groups_separable"] == 0 for p in P),
            "additive_mix_median": {k: float(np.median([m[k] for m in mix])) for k in ("ray", "fill", "copy", "mirror", "other")} if mix else None}
    out = {"note": "demonstrations only; descriptive heuristics on an exposed cohort; no test output read", "summary": summary, "tasks": per}
    json.dump(out, open(os.path.join(OUT, "observables.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
