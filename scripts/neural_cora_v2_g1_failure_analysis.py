#!/usr/bin/env python3
"""POST-HOC, EVALUATOR-SIDE failure analysis of the CLOSED Neural-CORA v1 pilot (records/NEURAL_CORA_V2_G1_FAILURE_ANALYSIS_20261020.md).

    python scripts/neural_cora_v2_g1_failure_analysis.py

It does no training, runs no arm and retunes nothing. It reads the saved v1 models, held-out features, rows, the
primary-set file and the evaluator's answers file (the generating programs and test outputs), and reports:
1. for each rule of each generating program, the rank of its true selector and action under C+H, L1 and L1h, and
   the probability each gives to the right number of rules;
2. the order position at which each arm first produced the correct test output, split into one-rule and two-rule
   tasks.

Output: outputs/neural_cora_v2/g1_failure_analysis/component_ranks.json and first_correct_positions.json.
"""
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v1")
DST = os.path.join(HERE, "outputs", "neural_cora_v2", "g1_failure_analysis")


def _r(p):
    return [json.loads(l) for l in open(p)]


def component_ranks():
    import torch
    from cora_neural_v1 import prior as PR
    from cora_neural_v1 import space as SP
    from cora_neural_v1.ir import Hypothesis
    pub = _r(os.path.join(OUT, "corpus", "eval_heldout_public.jsonl"))
    ans = {a["task_id"]: a for a in _r(os.path.join(OUT, "evaluator", "eval_heldout_answers.jsonl"))}
    prim = json.load(open(os.path.join(OUT, "audit", "eval_heldout_primary.json")))
    X = {f: np.load(os.path.join(OUT, "features", f"eval_heldout_{f}.npy")) for f in ("qwen", "hand")}

    def load(name):
        ck = torch.load(os.path.join(OUT, "models", f"{name}.pt"), weights_only=False)
        m = PR.build_heads(ck["in_dim"], 20261019)
        m.load_state_dict(ck["state"])
        m.eval()
        return m, ck
    models = {n: load(n) for n in ("L1", "L1h")}

    def rank(scores, true):
        order = sorted(scores, key=lambda k: -scores[k])
        return order.index(true) + 1 if true in order else 99
    rows = collections.defaultdict(lambda: collections.defaultdict(list))
    for i, t in enumerate(pub):
        if not prim[t["task_id"]]["primary"]:
            continue
        a = ans[t["task_id"]]
        h = Hypothesis.from_dict(a["program"])
        two = len(h.rules) == 2
        doms = SP.domains(t["train"])
        arms = {"C+H": SP.heuristic_scores(doms, t["train"])}
        for n, (m, ck) in models.items():
            x = np.clip((X[ck["feat"]][i].astype(np.float32) - ck["mu"]) / ck["sd"], -8, 8)
            arms[n] = PR.head_scores(m, x, doms)
        for arm, sc in arms.items():
            n2 = sc["n_rules"]
            rows[arm]["p_two_rules|two" if two else "p_two_rules|one"].append(
                float(np.exp(n2[2]) / (np.exp(n2[1]) + np.exp(n2[2]))))
            for r in h.rules:
                rows[arm]["sel_rank"].append(rank(sc["selector"], r.selector))
                rows[arm]["act_rank"].append(rank(sc["action"], r.action))
                rows[arm][f"act_rank|{a['family']}"].append(rank(sc["action"], r.action))
    return {arm: {k: round(float(np.median(v)), 3) if "rank" in k else round(float(np.mean(v)), 3)
                  for k, v in sorted(d.items())} for arm, d in rows.items()}


def first_correct_positions():
    rows = _r(os.path.join(OUT, "rows", "eval_heldout.jsonl"))
    ans = {a["task_id"]: a for a in _r(os.path.join(OUT, "evaluator", "eval_heldout_answers.jsonl"))}
    prim = json.load(open(os.path.join(OUT, "audit", "eval_heldout_primary.json")))
    pos = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        if not prim[r["task_id"]]["primary"]:
            continue
        A = np.asarray(ans[r["task_id"]]["test_output"])
        two = len(ans[r["task_id"]]["program"]["rules"]) == 2
        for arm in ("C+H", "L1", "L1h"):
            a, p = r["arms"][arm], None
            for pr, at in zip(a["predictions"], a["pred_at"]):
                P = np.asarray(pr)
                if P.shape == A.shape and (P == A).all():
                    p = at
                    break
            pos[arm]["two" if two else "one"].append(p if p is not None else 10 ** 6)
    out = {}
    for arm, d in pos.items():
        out[arm] = {"run_budget": rows[0]["arms"][arm]["state"]["budget"]}
        for k, v in d.items():
            v = np.asarray(v)
            f = v < 10 ** 6
            out[arm][k] = {"n": int(len(v)), "found_within_run": int(f.sum()),
                           "median_pos_found": float(np.median(v[f])) if f.any() else None,
                           "p90_pos_found": float(np.percentile(v[f], 90)) if f.any() else None}
    return out


if __name__ == "__main__":
    os.makedirs(DST, exist_ok=True)
    cr, fp = component_ranks(), first_correct_positions()
    json.dump(cr, open(os.path.join(DST, "component_ranks.json"), "w"), indent=1)
    json.dump(fp, open(os.path.join(DST, "first_correct_positions.json"), "w"), indent=1)
    print(json.dumps({"component_ranks": {a: {k: v for k, v in d.items() if not k.startswith("act_rank|")}
                                          for a, d in cr.items()}, "first_correct_positions": fp}, indent=1))
