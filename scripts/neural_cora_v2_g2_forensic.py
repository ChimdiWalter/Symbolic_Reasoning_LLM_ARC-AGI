"""G2 forensic analysis: evaluator side, descriptive. Pre-registered before the G2 run in
records/NEURAL_CORA_V2_CONTROLS_AND_GO_GATES.md section 0. It never changes the frozen G2b decision.

    python scripts/neural_cora_v2_g2_forensic.py      # only after `neural_cora_v2_g2.py score`
        -> outputs/neural_cora_v2/g2/g2_forensic.json

It reports:
1. single-rule correct reach: for each diagnostic task with a SINGLE_RULE_EXISTS verdict, whether any kept fitting
   single-rule program (up to 20) predicts the correct test output. This is a lower bound, because only 20 fits are
   kept;
2. wrong predictions: tasks with attempts and none correct, and tasks with fits but no correct candidate.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v2", "g2")


def _eq(p, A):
    P = np.asarray(p)
    return P.shape == A.shape and bool((P == A).all())


def forensic(solve_rows, diag_rows, answers):
    reach = []
    for d in diag_rows:
        r = d["result"]
        if r["verdict"] != "SINGLE_RULE_EXISTS":
            continue
        A = np.asarray(answers[d["task_id"]])
        hit = next((f["program"] for f in r["fits"] if f["test_pred"] is not None and _eq(f["test_pred"], A)), None)
        reach.append({"task_id": d["task_id"], "kept_fits": len(r["fits"]), "correct_among_kept": hit is not None,
                      "a_correct_program": hit})
    wrong_attempts, fits_no_correct = [], []
    for s in solve_rows:
        r, A = s["result"], np.asarray(answers[s["task_id"]])
        if r["attempts"] and not any(_eq(p, A) for p in r["attempts"][:2]):
            wrong_attempts.append(s["task_id"])
        if r["n_consistent"] > 0 and not any(_eq(p, A) for p in r["predictions"]):
            fits_no_correct.append(s["task_id"])
    return {"single_rule_reach": {"n_single_rule_exists": len(reach),
                                  "n_correct_among_kept": sum(x["correct_among_kept"] for x in reach),
                                  "tasks": reach, "note": "lower bound: at most 20 fits are kept per task"},
            "wrong_attempts": {"n": len(wrong_attempts), "tasks": sorted(wrong_attempts)},
            "fits_but_no_correct_candidate": {"n": len(fits_no_correct), "tasks": sorted(fits_no_correct)},
            "note": "descriptive; pre-registered; does not change the frozen G2b decision"}


def main():
    if not os.path.exists(os.path.join(OUT, "g2_score.json")):
        sys.exit("run only after the G2 score stage (outputs/neural_cora_v2/g2/g2_score.json is missing)")
    from cora_funnel.evaluate import answers
    ans = {k: v[0][0] for k, v in answers("dev60").items()}          # the first test output, as G2 scores
    rows = lambda f: [json.loads(l) for l in open(os.path.join(OUT, f))] if os.path.exists(os.path.join(OUT, f)) else []  # noqa: E731
    res = forensic(rows("dev60_g1_solve.jsonl"), rows("dev60_g1_diag.jsonl"), ans)
    json.dump(res, open(os.path.join(OUT, "g2_forensic.json"), "w"), indent=1)
    print(json.dumps({k: (v["n"] if "n" in v else {a: b for a, b in v.items() if a.startswith("n_")})
                      for k, v in res.items() if isinstance(v, dict)}, indent=1))


if __name__ == "__main__":
    main()
