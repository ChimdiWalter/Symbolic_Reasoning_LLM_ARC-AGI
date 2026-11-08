"""Scores and paired comparisons for A2 and A3 (after the eval stages; light CPU).

    python -m a2.score a2      -> a2/out/summary.json        python -m a2.score a3 -> a3/out/summary.json

S_select / S_train cohorts are scored with source labels (harness.data.source_labels). ARC_eval_dev predictions are
written per arm and scored by harness/scorer.py in a SEPARATE process (the only reader of evaluation answers).
Per arm: tasks, strict all-query solves (two attempts), per-output pass@2, demonstration-fit coverage, spurious fits
(fit but wrong), executor calls, CPU seconds; versus the baseline arm: gains, losses, exact McNemar p, and a
task-level bootstrap 95% interval of the solve-rate difference (tasks are the unit; outputs are not replicates).
"""
import collections
import json
import math
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP]
from harness import data as HD          # noqa: E402
from harness import paths as P          # noqa: E402
from a2 import runlog as RL             # noqa: E402

PY = "python3"
COHORTS = {"a2": [("S_select_A", "S_select"), ("S_select_B", "S_select"), ("E_trainU", "S_train"),
                  ("ARC_eval_dev", None)],
           "a3": [("canary", "S_train"), ("S_select", "S_select"), ("ARC_eval_dev", None)]}
BASE = {"a2": "lib_free", "a3": "fixed_views"}


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def boot(diff, n=4000, seed=7):
    rng = random.Random(seed)
    m = len(diff)
    if m == 0:
        return [0.0, 0.0]
    vals = sorted(sum(diff[rng.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return [round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n) - 1], 4)]


def score_source(recs, split):
    labels = HD.source_labels(split)
    out = {}
    for r in recs:
        truths = labels[r["task_id"]]
        preds = r.get("preds") or []
        per = []
        for j, y in enumerate(truths):
            atts = [p[j] for p in preds[:2] if p is not None and j < len(p)]
            per.append(any(a == y for a in atts))
        out[(r["arm"], r["task_id"])] = per
    return out


def score_eval_dev(fam, recs, outname="out"):
    out_dir = os.path.join(EXP, fam, outname)
    by_arm = collections.defaultdict(dict)
    for r in recs:
        preds = r.get("preds") or []
        n_out = len(HD.task_record(r["task_id"], "ARC_eval_dev")["test_inputs"])
        by_arm[r["arm"]][r["task_id"]] = [[p[j] if p is not None and j < len(p) else None for p in preds[:2]]
                                          for j in range(n_out)]
    out = {}
    for arm, pred in by_arm.items():
        pp = os.path.join(out_dir, f"pred_ARC_eval_dev_{arm}.json")
        sp = os.path.join(out_dir, f"score_ARC_eval_dev_{arm}.json")
        with P.open_allowed(pp, mode="w") as f:
            json.dump(pred, f)
        subprocess.run([PY, "-m", "harness.scorer", "--pred", pp, "--out", sp], cwd=EXP, check=True)
        with P.open_allowed(sp) as f:
            rows = json.load(f)["rows"]
        for tid, per in rows.items():
            out[(arm, tid)] = per
    return out


def table(recs, per, base):
    arms = sorted({r["arm"] for r in recs}, key=lambda a: (a != base, a))
    by = {(r["arm"], r["task_id"]): r for r in recs}
    tasks = sorted({r["task_id"] for r in recs if r["arm"] == base})
    res = {}
    for arm in arms:
        ts = [t for t in tasks if (arm, t) in by]
        solved = {t for t in ts if per.get((arm, t)) and all(per[(arm, t)])}
        bsolved = {t for t in ts if per.get((base, t)) and all(per[(base, t)])}
        outs = sum(len(per.get((arm, t), [])) for t in ts)
        ok = sum(sum(per.get((arm, t), [])) for t in ts)
        fit = sum(bool(by[(arm, t)]["fit"]) for t in ts)
        gains, losses = sorted(solved - bsolved), sorted(bsolved - solved)
        diff = [(t in solved) - (t in bsolved) for t in ts]
        res[arm] = {"tasks": len(ts), "solved": len(solved), "pass2_outputs": ok, "outputs": outs, "fit": fit,
                    "spurious_fit": fit - len({t for t in solved if by[(arm, t)]["fit"]}),
                    "mean_calls": round(sum(by[(arm, t)]["calls"] for t in ts) / max(1, len(ts))),
                    "cpu_s": round(sum(by[(arm, t)]["cpu_s"] for t in ts), 1),
                    "gains": gains, "losses": losses, "mcnemar_p": round(mcnemar(len(gains), len(losses)), 4),
                    "diff_ci95": boot(diff), "solved_ids": sorted(solved)}
    return res


def main(fam, outname="out"):
    out_dir = os.path.join(EXP, fam, outname)
    summary = {"family": fam.upper(), "base": BASE[fam], "cohorts": {}}
    for cohort, split in COHORTS[fam]:
        path = os.path.join(out_dir, f"eval_{cohort}.jsonl")
        recs = RL.read_jsonl(path)
        if not recs:
            continue
        per = score_eval_dev(fam, recs, outname) if split is None else score_source(recs, split)
        summary["cohorts"][cohort] = table(recs, per, BASE[fam])
        if fam == "a2":
            used = collections.defaultdict(set)
            for r in recs:
                if per.get((r["arm"], r["task_id"])) and all(per[(r["arm"], r["task_id"])]):
                    for d in r.get("lib_used") or []:
                        used[f"{r['arm']}:{d}"].add(r["task_id"])
            summary["cohorts"][cohort]["_library_use_in_correct_solutions"] = {k: sorted(v) for k, v in used.items()}
        if fam == "a3":
            by = {(r["arm"], r["task_id"]): r for r in recs}
            ev = {}
            for arm, row in summary["cohorts"][cohort].items():
                if arm.startswith("_"):
                    continue
                for t in row["gains"]:
                    ev[f"{arm}:{t}"] = {"win": by[(arm, t)]["win"], "fixed_views_fit": by[(BASE[fam], t)]["fit"],
                                        "fixed_views_reps": [x.get("rep") for x in by[(BASE[fam], t)]["log"]
                                                             if "rep" in x]}
            summary["cohorts"][cohort]["_gain_evidence"] = ev
    with P.open_allowed(os.path.join(out_dir, "summary.json"), mode="w") as f:
        json.dump(summary, f, indent=1)
    for c, rows in summary["cohorts"].items():
        print("==", c)
        for arm, r in rows.items():
            if not arm.startswith("_"):
                print(f"  {arm:17s} solved {r['solved']:3d}/{r['tasks']:3d} pass2 {r['pass2_outputs']}/{r['outputs']} "
                      f"fit {r['fit']} spur {r['spurious_fit']} +{len(r['gains'])} -{len(r['losses'])} "
                      f"p={r['mcnemar_p']} ci={r['diff_ci95']} calls={r['mean_calls']} cpu={r['cpu_s']}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
