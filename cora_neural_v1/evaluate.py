"""The independent evaluator of the Neural-CORA v1 pilot. It is the first and only code that reads the answers.

    python -m cora_neural_v1.evaluate

Inputs:
- `outputs/neural_cora_v1/rows/*.jsonl`: predictions only;
- `evaluator/*_answers.jsonl`: the answers;
- `audit/eval_heldout_primary.json`: the held-out primary set, fixed before any arm ran.

**Budgets.** Every typed arm ran once to B_MAX candidates. Its result at a smaller budget b is an exact truncation:
the predictions whose first appearance (`pred_at`) is at most b, in the same order, and the same two-attempt rule
(attempt 1 is the first distinct prediction, attempt 2 the next).

**Metrics per arm and budget:**
- exact pass@2;
- candidate coverage: the correct output among the distinct consistent predictions found within the budget;
- found a consistent program;
- wrong first attempt;
- abstention (no prediction);
- CPU.

**Statistics:**
- paired exact McNemar tests, two-sided binomial on the discordant tasks;
- Wilson 95% intervals for each rate.

**The preregistered gate G1** (records/NEURAL_CORA_V1_PILOT_PROTOCOL.md, section 7) is computed on the primary
held-out set. It is an intersection-union test: every condition must hold.
- L1@500 beats each of C+@1000, C+H@1000, L1h@500, L0@500 and L0s@500 (net > 0 and p < 0.05 for each).
- Harm: L1@500's wrong first attempts are at most C+H@1000's plus 5% of the tasks.
- Breadth: L1@500's net gain over C+H@1000 is positive in at least 3 of the 7 held-out families.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "neural_cora_v1_dev" if os.environ.get("NEURAL_CORA_DEV") else "neural_cora_v1")
BUDGETS = (100, 300, 500, 1000, 3000)
TYPED = ("C+", "C+H", "L0", "L0s", "L1", "L1h")
PRIMARY_TESTS = (("L1@500", "C+@1000"), ("L1@500", "C+H@1000"), ("L1@500", "L1h@500"), ("L1@500", "L0@500"),
                 ("L1@500", "L0s@500"))
SECONDARY_TESTS = (("L1@500", "C+@500"), ("L1@500", "C+H@500"), ("L1@1000", "C+H@1000"), ("L1@3000", "C+H@3000"),
                   ("L1h@500", "C+H@1000"), ("C+H@1000", "C+@1000"), ("L1@500", "C0"))


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


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def _eq(p, ans):
    P = np.asarray(p)
    A = np.asarray(ans)
    return P.shape == A.shape and bool((P == A).all())


def _at_budget(a, b):
    """Truncate one typed-arm result to budget b (exact)."""
    keep = [p for p, at in zip(a.get("predictions", []), a.get("pred_at", [])) if at <= b]
    return keep[:2], keep


def task_outcomes(row, A):
    """{arm@budget: {pass, cover, found, wrong1}} for one task."""
    o = {}
    for arm, a in row["arms"].items():
        if arm == "C0":
            att = a.get("attempts", [])
            o["C0"] = {"pass": any(_eq(x, A) for x in att[:2]), "cover": any(_eq(x, A) for x in att),
                       "found": bool(att), "wrong1": bool(att) and not _eq(att[0], A), "cpu_s": a.get("cpu_s", 0.0)}
            continue
        for b in BUDGETS:
            if b > a.get("state", {}).get("budget", a.get("n_candidates", 0)):   # never extrapolate past the run
                continue
            att, keep = _at_budget(a, b)
            frac = min(1.0, b / max(1, a.get("n_candidates", b)))
            o[f"{arm}@{b}"] = {"pass": any(_eq(x, A) for x in att), "cover": any(_eq(x, A) for x in keep),
                               "found": bool(att), "wrong1": bool(att) and not _eq(att[0], A),
                               "cpu_s": round(a.get("cpu_s", 0.0) * frac, 4)}
    return o


def summarize(rows, ans, keep=None):
    idx = [i for i, r in enumerate(rows) if keep is None or keep(r)]
    outs = [task_outcomes(rows[i], ans[rows[i]["task_id"]]["test_output"]) for i in idx]
    fams = [ans[rows[i]["task_id"]]["family"] for i in idx]
    arms = list(outs[0]) if outs else []
    res = {"n": len(idx), "arms": {}, "per_family": {}, "pass": {a: [o[a]["pass"] for o in outs] for a in arms}}
    for a in arms:
        k = int(sum(o[a]["pass"] for o in outs))
        res["arms"][a] = {"pass@2": k, "rate": round(k / max(1, len(outs)), 4), "wilson95": wilson(k, len(outs)),
                          "coverage": int(sum(o[a]["cover"] for o in outs)),
                          "found_consistent": int(sum(o[a]["found"] for o in outs)),
                          "abstained": int(sum(not o[a]["found"] for o in outs)),
                          "wrong_first_attempt": int(sum(o[a]["wrong1"] for o in outs)),
                          "cpu_s_mean": round(float(np.mean([o[a]["cpu_s"] for o in outs])), 4)}
    for f in sorted(set(fams)):
        j = [n for n, x in enumerate(fams) if x == f]
        res["per_family"][f] = {"n": len(j)} | {a: int(sum(outs[n][a]["pass"] for n in j)) for a in arms}
    res["_outs"], res["_fams"], res["_ids"] = outs, fams, [rows[i]["task_id"] for i in idx]
    return res


def tests(res, pairs):
    P, out = res["pass"], {}
    for a, b in pairs:
        if a in P and b in P:
            ao, bo, p = mcnemar(P[a], P[b])
            out[f"{a} vs {b}"] = {"a_only": ao, "b_only": bo, "net": ao - bo, "p": round(p, 6)}
    return out


def decide(res):
    """The preregistered G1 rule (protocol section 7), on the primary held-out set."""
    t = tests(res, PRIMARY_TESTS)
    sig = {k: v["net"] > 0 and v["p"] < 0.05 for k, v in t.items()}
    n = res["n"]
    harm_ok = res["arms"]["L1@500"]["wrong_first_attempt"] <= res["arms"]["C+H@1000"]["wrong_first_attempt"] + 0.05 * n
    fam_gain = {f: v["L1@500"] - v["C+H@1000"] for f, v in res["per_family"].items()}
    breadth_ok = sum(1 for g in fam_gain.values() if g > 0) >= 3
    go = all(sig.values()) and harm_ok and breadth_ok
    over_search = sig.get("L1@500 vs C+@1000", False) and sig.get("L1@500 vs L0@500", False) and \
        sig.get("L1@500 vs L0s@500", False)
    if go:
        cls = "G1_GO"
    elif over_search:
        cls = "LEARNED_OVER_PLAIN_SEARCH_ONLY"     # learning helps over C+, but not over C+H and/or L1h
    elif res["arms"]["L1@500"]["coverage"] > res["arms"]["C+@1000"]["coverage"]:
        cls = "CANDIDATES_ONLY"
    else:
        cls = "NO_LEARNING_GAIN"
    return {"tests": t, "significant": sig, "harm_ok": harm_ok, "family_net_gain_vs_CpH1000": fam_gain,
            "breadth_ok": breadth_ok, "classification": cls, "G1": "GO" if go else "NO-GO"}


def harms(res, a="L1@500", b="C+H@1000"):
    P, ids = res["pass"], res["_ids"]
    return {"gained": [ids[i] for i, (x, y) in enumerate(zip(P[a], P[b])) if x and not y],
            "lost": [ids[i] for i, (x, y) in enumerate(zip(P[a], P[b])) if y and not x]}


def main():
    out, task_rows = {}, []
    prim = json.load(open(os.path.join(OUT, "audit", "eval_heldout_primary.json")))
    for split in ("eval_heldout", "eval_iid"):
        p = os.path.join(OUT, "rows", f"{split}.jsonl")
        if not os.path.exists(p):
            continue
        rows = _r(p)
        ans = {a["task_id"]: a for a in _r(os.path.join(OUT, "evaluator", f"{split}_answers.jsonl"))}
        if os.environ.get("NEURAL_CORA_DEV") and os.environ.get("NEURAL_CORA_LIMIT"):   # engineering smoke test only
            ans = {k: v for k, v in ans.items() if k in {r["task_id"] for r in rows}}
        assert len(rows) == len(ans) and all(r["task_id"] in ans for r in rows), "row/answer mismatch"
        views = {"all": None}
        if split == "eval_heldout":
            views = {"primary": lambda r: prim[r["task_id"]]["primary"], "aliased": lambda r: not prim[r["task_id"]]["primary"],
                     "all": None}
        out[split] = {}
        for vname, keep in views.items():
            if keep is not None and not any(keep(r) for r in rows):
                out[split][vname] = {"n": 0}
                if split == "eval_heldout" and vname == "primary":
                    out["G1_decision"] = {"G1": "NOT EVALUABLE", "reason": "empty primary set"}
                continue
            res = summarize(rows, ans, keep)
            res["tests_primary_pairs"] = tests(res, PRIMARY_TESTS)
            res["tests_secondary"] = tests(res, SECONDARY_TESTS)
            res["harms_L1@500_vs_C+H@1000"] = harms(res)
            if split == "eval_heldout" and vname == "primary":
                out["G1_decision"] = decide(res)
            if vname == "all":                                         # every task once, with its primary flag
                for tid, fam, o in zip(res["_ids"], res["_fams"], res["_outs"]):
                    task_rows.append({"split": split, "task_id": tid, "family": fam,
                                      "primary": prim.get(tid, {}).get("primary") if split == "eval_heldout" else None,
                                      "outcomes": {a: {k: v for k, v in x.items() if k != "cpu_s"} for a, x in o.items()}})
            for k in ("_outs", "_fams", "_ids", "pass"):
                res.pop(k)
            out[split][vname] = res
    os.makedirs(os.path.join(OUT, "evaluator"), exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "evaluator", "pilot_v1_eval.json"), "w"), indent=1)
    with open(os.path.join(OUT, "evaluator", "task_level.jsonl"), "w") as f:
        for r in task_rows:
            f.write(json.dumps(r) + "\n")
    print(json.dumps(out.get("G1_decision", {}), indent=1))


if __name__ == "__main__":
    sys.exit(main())
