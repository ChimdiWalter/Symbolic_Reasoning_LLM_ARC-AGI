"""The independent evaluator of the Neural-CORA pilot v0. It is the first and only code that reads the answers.

    python -m cora_neural_v1.evaluate

It reads `outputs/neural_cora_v0/rows/*.jsonl` (predictions only) and `evaluator/*_answers.jsonl`.

**Metrics:** per arm, task-level exact pass@2, candidate coverage (a correct prediction among the distinct
demonstration-consistent predictions within budget), "found a consistent program", wrong first attempts, and CPU.

**Statistics:** paired exact McNemar tests (two-sided binomial on discordant tasks).

**The preregistered decision** (protocol section 6) is computed here; nothing in it is chosen after the answers are
read:
- PRIMARY: L1 vs C+ on the held-out families, pass@2.
- Learned weights must matter: L1 vs L0 and L1 vs L0s.
- Strong symbolic control (reported; needed for the strong claim): L1 vs C+H.
- Encoder ablation (reported): L1 vs L1h.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "neural_cora_v0_dev" if os.environ.get("NEURAL_CORA_DEV") else "neural_cora_v0")


def _r(p):
    return [json.loads(l) for l in open(p)]


def mcnemar(a, b):
    """Two-sided exact binomial test on discordant pairs; returns (a_only, b_only, p)."""
    ao = int(sum(1 for x, y in zip(a, b) if x and not y))
    bo = int(sum(1 for x, y in zip(a, b) if y and not x))
    n = ao + bo
    if n == 0:
        return ao, bo, 1.0
    k = min(ao, bo)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return ao, bo, min(1.0, 2 * p)


def _eq(p, ans):
    P = np.asarray(p)
    A = np.asarray(ans)
    return P.shape == A.shape and bool((P == A).all())


def evaluate_split(split):
    rows = _r(os.path.join(OUT, "rows", f"{split}.jsonl"))
    ans = {a["task_id"]: a for a in _r(os.path.join(OUT, "evaluator", f"{split}_answers.jsonl"))}
    assert len(rows) == len(ans) and all(r["task_id"] in ans for r in rows), "row/answer mismatch"
    arms = list(rows[0]["arms"].keys())
    res = {"n": len(rows), "arms": {}, "per_family": {}, "pass": {}}
    for arm in arms:
        p2, cov, found, wrong1, cpu = [], [], [], [], []
        for r in rows:
            a = r["arms"][arm]
            A = ans[r["task_id"]]["test_output"]
            att = a.get("attempts", [])
            p2.append(any(_eq(x, A) for x in att[:2]))
            preds = a.get("predictions", att)
            cov.append(any(_eq(x, A) for x in preds))
            found.append(len(att) > 0)
            wrong1.append(len(att) > 0 and not _eq(att[0], A))
            cpu.append(a.get("cpu_s", 0.0))
        res["pass"][arm] = p2
        res["arms"][arm] = {"pass@2": int(sum(p2)), "coverage": int(sum(cov)), "found_consistent": int(sum(found)),
                            "wrong_first_attempt": int(sum(wrong1)), "cpu_s_mean": round(float(np.mean(cpu)), 3)}
    fams = sorted({ans[r["task_id"]]["family"] for r in rows})
    for fam in fams:
        idx = [i for i, r in enumerate(rows) if ans[r["task_id"]]["family"] == fam]
        res["per_family"][fam] = {arm: int(sum(res["pass"][arm][i] for i in idx)) for arm in arms} | {"n": len(idx)}
    return res


def decide(h):
    P = h["pass"]
    tests = {}
    for a, b in (("L1", "C+"), ("L1", "L0"), ("L1", "L0s"), ("L1", "C+H"), ("L1", "L1h"), ("L1", "C0"), ("C+H", "C+")):
        if a in P and b in P:
            ao, bo, p = mcnemar(P[a], P[b])
            tests[f"{a} vs {b}"] = {"a_only": ao, "b_only": bo, "net": ao - bo, "p": round(p, 6)}
    primary = tests["L1 vs C+"]
    learned = tests["L1 vs L0"]["net"] > 0 and tests["L1 vs L0"]["p"] < 0.05 and \
        tests["L1 vs L0s"]["net"] > 0 and tests["L1 vs L0s"]["p"] < 0.05
    cov_l1, cov_cp = h["arms"]["L1"]["coverage"], h["arms"]["C+"]["coverage"]
    if primary["net"] > 0 and primary["p"] < 0.05 and learned:
        cls = "PERFORMANCE_ONLY"            # learned prior helps selected outputs; diagnosis not tested at this stage
        go = "GO (engineering: proceed to a separately eligible real cohort; diagnosis untested)"
    elif cov_l1 > cov_cp:
        cls, go = "CANDIDATES_ONLY", "NO-GO"
    else:
        cls, go = "NO_EXECUTABLE_GAIN", "NO-GO"
    strong = tests["L1 vs C+H"]["net"] > 0 and tests["L1 vs C+H"]["p"] < 0.05
    return {"tests": tests, "classification": cls, "decision": go, "learned_weights_matter": learned,
            "beats_strong_symbolic_control": strong,
            "encoder_matters_vs_hand_features": tests["L1 vs L1h"]["net"] > 0 and tests["L1 vs L1h"]["p"] < 0.05}


def main():
    out = {}
    for split in ("eval_heldout", "eval_iid"):
        if os.path.exists(os.path.join(OUT, "rows", f"{split}.jsonl")):
            out[split] = evaluate_split(split)
    out["decision"] = decide(out["eval_heldout"])
    for s in ("eval_heldout", "eval_iid"):
        if s in out:
            out[s].pop("pass")
    p = os.path.join(OUT, "evaluator", "pilot_v0_eval.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    sys.exit(main())
