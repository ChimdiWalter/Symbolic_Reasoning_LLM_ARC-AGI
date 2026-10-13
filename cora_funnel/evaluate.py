"""Independent funnel evaluator: the only code here that reads held-out answers.

  python -m cora_funnel.evaluate --corpus dev60 [--mode native]
      -> outputs/funnel_v0/eval_<corpus>_<mode>.json   (per task + summary)

Answers:
- dev60: the pilot's evaluator-only key map, then the sha256-pinned
  ARC-AGI-2 training solutions (cora_pilot.bundle / cora_pilot.evaluator).
  The bundle hash is checked against the key map.
- c2dev, c3dev: the generator's held-out outputs, plus family labels.

Per task, in funnel order:
- S1 perception (observation): the native views coherent on the
  demonstrations;
- S3 generated: hypotheses enumerated, summed over the frames;
- S4 fit: train-exact candidate sets (all searches, phases, frames and the
  generative fallback);
- S5 certified: native acceptance, after leave-one-out by re-induction;
- S6 correct: the committed prediction against the answer;
- the certification audit:
  - a train-exact candidate that is correct on the held-out answer but was
    not certified (REJECTED_BUT_CORRECT);
  - certified but wrong (false acceptance);
  - the gate-off counterfactual: native's rank-1 train-exact candidate of
    the identity frame's first search. This is what OBJECT_GATE_OFF would
    submit; a measurement only, never a policy.

Primary category, mutually exclusive:
CERTIFIED_CORRECT, CERTIFIED_WRONG, REJECTED_BUT_CORRECT,
FIT_BUT_ALL_WRONG, NO_FIT_DEADLINE, NO_FIT_EXHAUSTED.
"""
import argparse
import collections
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "funnel_v0")


def answers(corpus):
    """{key: ([test outputs], family)}."""
    if corpus == "dev60":
        from cora_pilot import bundle as B
        from cora_pilot import evaluator as EV
        km = json.load(open(os.path.join(HERE, "records", "pilot_v1_evaluator", "dev_keymap.json")))
        bsha = hashlib.sha256(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json"), "rb").read()).hexdigest()
        if km["bundle_sha256"] != bsha:
            raise ValueError("dev bundle does not match the key map")
        sol = EV.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)
        return {k: (sol[v["task_id"]], v.get("stratum")) for k, v in km["keys"].items()}
    if corpus == "c2dev":
        d = json.load(open(os.path.join(HERE, "outputs", "hybrid_c2_dev", "dev_tasks.json")))
        return {k: ([p["output"] if isinstance(p, dict) else p[1] for p in t["test"]], t["family"]) for k, t in d.items()}
    if corpus == "c3dev":
        d = json.load(open(os.path.join(HERE, "outputs", "rep_growth_v0", "corpus.json")))["tasks"]
        return {t["id"]: ([b for _, b in t["heldout"]], t["family"]) for t in d if t["split"] == "dev"}
    raise ValueError(corpus)


def exact(preds, targets):
    return isinstance(preds, list) and len(preds) == len(targets) and all(p is not None and p == t for p, t in zip(preds, targets))


def task_record(r, ans):
    ev = r["events"]
    sets = [e for e in ev if e["type"] in ("search", "generative") and e["n_programs"] > 0]
    cand_ok = [[exact(o, ans) for o in (e["outputs"] or [])] for e in sets]
    any_correct = any(any(c) for c in cand_ok)
    first = next((e for e in ev if e["type"] == "search" and e["frame"] == 0), None)
    gate_off = None
    if first is not None and first["n_programs"] > 0 and first["outputs"]:
        i = first["rank"][0] if first.get("rank") else 0
        gate_off = exact(first["outputs"][i], ans) if i < len(first["outputs"]) else None
    correct = bool(r["solved"]) and exact(r["predictions"], ans)
    if r["solved"]:
        cat = "CERTIFIED_CORRECT" if correct else "CERTIFIED_WRONG"
    elif sets:
        cat = "REJECTED_BUT_CORRECT" if any_correct else "FIT_BUT_ALL_WRONG"
    else:
        cat = "NO_FIT_DEADLINE" if (first is None or first["deadline_hit"]) else "NO_FIT_EXHAUSTED"
    # leave-one-out detail for the candidate sets: which folds failed, and whether each failed fold rebuilt anything
    loos = [e for e in ev if e["type"] == "loo"]
    folds = [e for e in ev if e["type"] == "fold"]
    return {"key": r["key"], "category": cat, "solved": bool(r["solved"]), "correct": correct,
            "n_coherent_views": r["perception"].get("n_coherent"), "coherent_views": r["perception"].get("coherent"),
            "hypotheses": sum(f["hypotheses"] for f in r["frames"]), "frames_run": len(r["frames"]),
            "candidate_sets": len(sets), "train_exact_candidates": sum(e["n_programs"] for e in sets),
            "correct_candidates": sum(sum(c) for c in cand_ok), "any_candidate_correct": any_correct,
            "gate_off_correct": gate_off, "partial_correct": exact(r.get("partial_predictions"), ans) if r.get("partial_predictions") else None,
            "first_search": None if first is None else {k: first[k] for k in ("n_programs", "stage", "fit_objects", "fit_pixels", "seg", "deadline_hit", "s")},
            "loo": [{k: e[k] for k in ("frame", "folds", "passed", "failed")} for e in loos],
            "folds_rebuilt": sum(f["n_programs"] > 0 for f in folds), "folds_total": len(folds),
            "folds_deadline": sum(f["deadline_hit"] for f in folds),
            "wall_s": r["wall_s"], "cpu_s": r["cpu_s"], "cpu_share": round(r["cpu_s"] / max(r["wall_s"], 1e-6), 2),
            "error": r.get("error")}


def summarize(recs, fam):
    n = len(recs)
    cats = collections.Counter(x["category"] for x in recs)
    fit = [x for x in recs if x["candidate_sets"]]
    s = {"tasks": n, "categories": dict(sorted(cats.items())),
         "S1_no_coherent_view": sum(1 for x in recs if x["n_coherent_views"] == 0),
         "S3_generated_any": sum(1 for x in recs if x["hypotheses"] > 0),
         "S4_train_exact_any": len(fit),
         "S5_certified": sum(x["solved"] for x in recs),
         "S6_correct": sum(x["correct"] for x in recs),
         "candidate_recall": sum(x["any_candidate_correct"] for x in recs),
         "loo_pass_given_fit": f"{sum(x['solved'] for x in fit)}/{len(fit)}",
         "correct_rejected": cats.get("REJECTED_BUT_CORRECT", 0), "incorrect_accepted": cats.get("CERTIFIED_WRONG", 0),
         "gate_off_correct": sum(1 for x in recs if x["gate_off_correct"]),
         "gate_off_wrong": sum(1 for x in recs if x["gate_off_correct"] is False),
         "partial_correct": sum(1 for x in recs if x["partial_correct"]),
         "wall_s_total": round(sum(x["wall_s"] for x in recs)), "cpu_s_total": round(sum(x["cpu_s"] for x in recs)),
         "errors": sum(1 for x in recs if x["error"]),
         # native budgets are wall-clock: a starved worker searches less, so deadline outcomes are confounded below 0.7
         "cpu_share_median": sorted(x["cpu_share"] for x in recs)[n // 2] if n else None,
         "cpu_starved_lt_0p7": sum(1 for x in recs if x["cpu_share"] < 0.7)}
    by = collections.defaultdict(collections.Counter)
    for x in recs:
        by[fam[x["key"]]][x["category"]] += 1
    s["by_family_or_stratum"] = {k: dict(v) for k, v in sorted(by.items(), key=lambda kv: str(kv[0]))}
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=("dev60", "c2dev", "c3dev"))
    ap.add_argument("--mode", default="native")
    a = ap.parse_args(argv)
    rows = [json.loads(l) for l in open(os.path.join(OUT, f"rows_{a.corpus}_{a.mode}.jsonl"))]
    key = answers(a.corpus)
    recs = [task_record(r, key[r["key"]][0]) for r in rows]
    fam = {k: v[1] for k, v in key.items()}
    s = summarize(recs, fam)
    json.dump({"corpus": a.corpus, "mode": a.mode, "summary": s, "tasks": recs}, open(os.path.join(OUT, f"eval_{a.corpus}_{a.mode}.json"), "w"), indent=1)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
