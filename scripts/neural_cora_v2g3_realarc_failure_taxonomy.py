"""Phase 2: a descriptive failure taxonomy of the finished ncv2-g2 real-ARC check. It never changes or reruns the
frozen study, and it runs only after its `score` stage and the pre-registered analysis
(`scripts/neural_cora_v2g2_realarc_analysis.py`).

    python scripts/neural_cora_v2g3_realarc_failure_taxonomy.py   -> outputs/neural_cora_v2g2/realarc/failure_taxonomy.json

Two sides, kept apart:
- **solver side** (demonstrations and saved traces only): how many distinct readings fit (ambiguity), where
  candidates fail, and how much of the demonstrations' change the object view explains (scene.py: the share of
  changed cells on objects that are recoloured, moved or deleted, best view);
- **evaluator side, post hoc** (answers, or native's certified programs): correctness, expressivity and generator
  coverage (from the pre-registered analysis), and where native's certified program sits in ncv2-g2's own order
  (a structural match over up to 40,000 programs; nothing is executed for it).

One primary cause per task, the first that applies:
solved | E selection (a correct candidate retained, not attempted) | F underdetermined (several distinct fitting
readings, none correct) | fit_wrong (one fitting reading, wrong) | B language gap | C generator gap | D beyond budget
| then, with no certificate and no fit, by the change profile: unknown_object_explained (objects explain at least half
of the change, yet no rule was found) | A_additive (mostly new cells) | A_object_mismatch | A_mixed | A_shape_change. The taxonomy is descriptive; no solver-side feature is built from evaluator-side knowledge.
"""
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g2", "realarc")
CERTS = os.path.join(HERE, "outputs", "funnel_v0", "engine_realarc2x_native", "certificates")
REACH_LIMIT = 40000


def cohort():
    spec = importlib.util.spec_from_file_location("ra", os.path.join(HERE, "scripts", "neural_cora_v2g2_realarc_eval.py"))
    RA = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RA)
    return {t["task_id"]: t for t in RA.tasks()}


def change_profile(train):
    """Solver side: how the demonstrations' changed cells split, in the view that explains most of them:
    `explained` (on recoloured or deleted objects, or the source and destination of moved objects), `additive`
    (background turned colour, not explained by a move), `other` (on objects whose fate matches nothing). None for a
    shape change."""
    from cora_neural_v2 import search as G1S
    from cora_neural_v2g3 import scene as SC
    if not all(np.asarray(a).shape == np.asarray(b).shape for a, b in train):
        return None
    changed = sum(int((np.asarray(a) != np.asarray(b)).sum()) for a, b in train)
    if not changed:
        return {"explained": 1.0, "additive": 0.0, "other": 0.0}
    best = None
    for v in G1S.distinct_views({"train": train, "test_inputs": []}):
        sc = SC.analyse(train, v)
        if sc is None:
            continue
        tot = {"explained": 0, "additive": 0, "other": 0}
        for (a, b), objs, bg in zip(train, sc.objects, sc.background):
            A, B = np.asarray(a), np.asarray(b)
            diff = A != B
            expl, oth = np.zeros_like(diff), np.zeros_like(diff)
            for o in objs:
                if o.fate in ("recoloured", "deleted", "moved"):
                    for x in o.cells:
                        expl[x] = True
                    if o.fate == "moved":
                        for r, c in o.cells:
                            rr, cc = r + o.vector[0], c + o.vector[1]
                            if 0 <= rr < A.shape[0] and 0 <= cc < A.shape[1]:
                                expl[rr, cc] = True
                elif o.fate == "other":
                    for x in o.cells:
                        oth[x] = True
            tot["explained"] += int((diff & expl).sum())
            tot["other"] += int((diff & oth & ~expl).sum())
            tot["additive"] += int((diff & (A == bg) & ~expl).sum())
        share = {k: round(v / changed, 3) for k, v in tot.items()}
        if best is None or share["explained"] > best["explained"]:
            best = share
    return best


def agenda_position(task, cert):
    """Evaluator side, post hoc: the first position of `cert` in ncv2-g2's own order, or None within REACH_LIMIT."""
    from cora_neural_v2g2 import search as S2
    for n, (prog, _) in enumerate(S2.enumerate_programs(task, REACH_LIMIT), 1):
        if prog == cert:
            return n
    return None


def main():
    from cora_neural_v2.rast import ASTError
    from cora_neural_v2g2 import grammar as G
    A = json.load(open(os.path.join(OUT, "analysis.json")))
    S = json.load(open(os.path.join(OUT, "score.json")))
    rows = {json.loads(l)["task_id"]: json.loads(l) for l in open(os.path.join(OUT, "rows_g.jsonl"))}
    scored = {r["task_id"]: r for r in S["tasks"]}
    tasks = cohort()
    per = []
    for a in A["tasks"]:
        t = a["task_id"]
        row, sc = rows[t], scored[t]
        task = {"task_id": t, "train": tasks[t]["train"], "test_inputs": tasks[t]["test_inputs"]}
        g2 = row["g2"]
        solver = {"fits": g2["n_consistent"], "distinct_readings": len(g2["predictions"]), "first_fit_at": g2["first_fit_at"],
                  "fail_demo": g2["state"]["fail_demo"], "change_profile": change_profile(task["train"])}
        post = {"pass2": a["correct"]["g2"], "coverage": sc["g2"]["correct_coverage"], "expressivity": a["expressivity"],
                "generator_coverage": a.get("generator_coverage"), "native_first": a["correct"]["native_first"]}
        cert_path = os.path.join(CERTS, f"{t}.json")
        if a["expressivity"] == "expressible" and a.get("generator_coverage") and not post["pass2"] and os.path.exists(cert_path):
            try:
                post["certificate_position"] = agenda_position(task, G.decompile(json.load(open(cert_path))["program"]))
            except ASTError:
                post["certificate_position"] = None
        if post["pass2"]:
            cause = "solved"
        elif post["coverage"]:
            cause = "E_selection"
        elif solver["fits"] and solver["distinct_readings"] >= 2:
            cause = "F_underdetermined"
        elif solver["fits"]:
            cause = "fit_wrong"
        elif a["expressivity"] == "not expressible":
            cause = "B_language"
        elif a["expressivity"] == "expressible" and not a.get("generator_coverage"):
            cause = "C_generator"
        elif a["expressivity"] == "expressible":
            cause = "D_beyond_budget"
        elif solver["change_profile"] is None:
            cause = "A_shape_change"
        elif solver["change_profile"]["explained"] >= 0.5:
            cause = "unknown_object_explained"          # objects explain the change, yet no rule was found
        elif solver["change_profile"]["additive"] >= 0.5:
            cause = "A_additive"                        # mostly new cells: lines, fills, copies, growth
        elif solver["change_profile"]["other"] >= 0.5:
            cause = "A_object_mismatch"                 # the objects change in ways no fate describes
        else:
            cause = "A_mixed"
        per.append({"task_id": t, "stratum": a["stratum"], "n_test": a["n_test"], "cause": cause, "solver_side": solver,
                    "evaluator_side_post_hoc": post})
    out = {"note": "descriptive, after the frozen decision; never changes it. Solver-side and evaluator-side fields are "
                   "kept apart; no evaluator-side knowledge becomes a solver feature.", "summary": {}, "tasks": per}
    for stratum in ("primary", "leftover"):
        P = [x for x in per if x["stratum"] == stratum]
        causes = {}
        for x in P:
            causes[x["cause"]] = causes.get(x["cause"], 0) + 1
        prof = [x["solver_side"]["change_profile"] for x in P if x["solver_side"]["change_profile"] is not None]
        out["summary"][stratum] = {"n": len(P), "causes": dict(sorted(causes.items(), key=lambda kv: -kv[1])),
                                   "shape_changing": sum(x["solver_side"]["change_profile"] is None for x in P),
                                   "change_profile_median": {k: float(np.median([p[k] for p in prof])) for k in
                                                             ("explained", "additive", "other")} if prof else None,
                                   "tasks_with_fits": sum(x["solver_side"]["fits"] > 0 for x in P),
                                   "certificate_positions": {x["task_id"]: x["evaluator_side_post_hoc"].get("certificate_position")
                                                             for x in P if "certificate_position" in x["evaluator_side_post_hoc"]}}
    json.dump(out, open(os.path.join(OUT, "failure_taxonomy.json"), "w"), indent=1)
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
