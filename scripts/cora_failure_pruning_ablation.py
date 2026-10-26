"""Failure-derived pruning: on/off ablation at an equal budget of EXECUTED candidates (engineering, not frozen).

Tasks: fresh seeds (1000 to 1009; never looked at while building the pruning) of every development family of rule
languages version 2 (cora_neural_v2g2.families) and version 3 (cora_neural_v2g3.families_v3); held-out families are
never used. Expected outputs are read only to score. Each arm runs once, in its own process (no shared caches), at
the largest budget; coverage at the smaller budgets is read off the executed positions, which is exact because the
search is anytime and both arms make the same stream call. After the pruned arm, every pruned candidate is executed,
outside the timed arm, to confirm that none would have fit.

Usage: python THIS.py run OUT.jsonl [I/K]      one line per (task, arm), resumable; shard I of K
       python THIS.py one FAMILY SEED ARM       one arm as one JSON line on stdout (called by run)
       python THIS.py summary OUT.jsonl [...]   summary on stdout; ablation_summary.json beside the first file
"""
import json
import os
import statistics as st
import subprocess
import sys
import time
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g3 import delta as D                                  # noqa: E402
from cora_neural_v2g3 import families_v3 as F3                           # noqa: E402
from cora_neural_prune import search as PS                               # noqa: E402

SEEDS, BUDGET, BUDGETS, CPU_CAP_S = tuple(range(1000, 1010)), 3000, (300, 1000, 3000), 1500.0
FAMS = [("version 2", f) for f in F.names("dev")] + [("version 3", f) for f, v in F3.FAMILIES.items() if v[0] == "dev"]


def one(fam, seed, arm):
    src = "version 2" if fam in F.FAMILIES else "version 3"
    head = {"family": fam, "seed": seed, "source": src, "arm": arm, "budget": BUDGET}
    made = (F.make_task if fam in F.FAMILIES else F3.make_task)(fam, seed)
    if made is None:
        return dict(head, generated=False)
    task, exp = made
    exp = exp if isinstance(exp, list) else [exp]
    r = PS.search(task, BUDGET, prune=(arm == "on"), keep=10 ** 6, cpu_cap_s=CPU_CAP_S, record_pruned=(arm == "on"))
    ok = [len(p) == len(exp) and all(np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(p, exp))
          for p in r["predictions"]]
    i = ok.index(True) if True in ok else None
    out = dict(head, generated=True, n_train=len(task["train"]),
               first_correct_at=None if i is None else r["pred_at"][i],
               first_correct_cpu=None if i is None else r["pred_cpu"][i],
               first_correct_native=None if i is None else r["pred_native"][i], correct_flags=ok,
               **{k: r[k] for k in ("n_candidates", "stream_read", "n_pruned", "pruned", "learned", "native_runs",
                                    "first_fit_at", "first_fit_cpu", "pred_at", "pred_native", "pred_cpu",
                                    "n_distinct_predictions", "class_candidates", "class_sha", "cpu_s",
                                    "cpu_truncated")})
    if arm == "on":
        c0, fits = time.process_time(), 0
        for p in r["pruned_programs"]:
            fits += D.fits(D.deltas(p, task["train"], stop_early=False), len(task["train"]))
        out["pruned_fit_check"] = {"checked": len(r["pruned_programs"]), "fit": int(fits),
                                   "cpu_s": round(time.process_time() - c0, 3)}
    return out


def run(path, shard="0/1"):
    i, k = map(int, shard.split("/"))
    done = set()
    if os.path.exists(path):
        for line in open(path):
            d = json.loads(line)
            done.add((d["family"], d["seed"], d["arm"]))
    jobs = [(f, s) for s in SEEDS for _, f in FAMS]
    for j, (fam, seed) in enumerate(jobs):
        if j % k != i:
            continue
        for arm in ("off", "on"):
            if (fam, seed, arm) in done:
                continue
            p = subprocess.run([sys.executable, os.path.abspath(__file__), "one", fam, str(seed), arm],
                               capture_output=True, text=True, timeout=4 * 3600)
            try:
                d = json.loads(p.stdout.strip().splitlines()[-1])
            except (IndexError, ValueError):
                d = {"family": fam, "seed": seed, "arm": arm, "error": (p.stderr or "")[-600:]}
            with open(path, "a") as fh:
                fh.write(json.dumps(d) + "\n")


def _med(xs):
    return st.median(xs) if xs else None


def summary(paths):
    rows = {}
    for path in paths:
        for line in open(path):
            d = json.loads(line)
            rows.setdefault((d["family"], d["seed"]), {})[d["arm"]] = d
    pairs = [(t, a["off"], a["on"]) for t, a in sorted(rows.items())
             if "off" in a and "on" in a and a["off"].get("generated") and a["on"].get("generated")]
    errors = sorted(t for t, a in rows.items() if any("error" in x for x in a.values()))
    out = {"tasks": len(pairs), "not_generated": sorted(t for t, a in rows.items()
                                                      if any(x.get("generated") is False for x in a.values())),
           "errors": errors, "by_source": dict(Counter(o["source"] for _, o, _ in pairs)),
           "stream_mismatch": [t for t, o, n in pairs if o["class_sha"] != n["class_sha"]],
           "cpu_truncated": [t for t, o, n in pairs if o["cpu_truncated"] or n["cpu_truncated"]]}

    def reached(d, key, b):
        v = d[key]
        return v is not None and v <= b

    cov = {}
    for b in BUDGETS:
        for key in ("first_fit_at", "first_correct_at"):
            off = sum(reached(o, key, b) for _, o, _ in pairs)
            on = sum(reached(n, key, b) for _, _, n in pairs)
            gains = [t for t, o, n in pairs if reached(n, key, b) and not reached(o, key, b)]
            losses = [t for t, o, n in pairs if reached(o, key, b) and not reached(n, key, b)]
            cov[f"{key}@{b}"] = {"off": off, "on": on, "gains": gains, "losses": losses}
    out["coverage"] = cov
    for key, ckey in (("first_fit_at", "first_fit_cpu"), ("first_correct_at", "first_correct_cpu")):
        both = [(t, o, n) for t, o, n in pairs if o[key] is not None and n[key] is not None]
        # the pruned arm's cost with every pick-set computation counted as one more executed candidate
        cons = [n[key] + n["first_correct_native"] / n["n_train"] for _, _, n in both] if key == "first_correct_at" else []
        out[key] = {"both_reached": len(both), "median_off": _med([o[key] for _, o, _ in both]),
                    "median_on": _med([n[key] for _, _, n in both]),
                    "earlier": sum(n[key] < o[key] for _, o, n in both),
                    "same": sum(n[key] == o[key] for _, o, n in both),
                    "later": sum(n[key] > o[key] for _, o, n in both),
                    "candidates_saved": sum(o[key] - n[key] for _, o, n in both),
                    "median_cpu_off": _med([o[ckey] for _, o, _ in both]),
                    "median_cpu_on": _med([n[ckey] for _, _, n in both]),
                    "cpu_on_more": sum(n[ckey] > o[ckey] for _, o, n in both),
                    "median_cost_on_counting_pick_sets": _med(cons)}
    out["cpu"] = {"total_off": round(sum(o["cpu_s"] for _, o, _ in pairs), 1),
                  "total_on": round(sum(n["cpu_s"] for _, _, n in pairs), 1),
                  "median_off": _med([o["cpu_s"] for _, o, _ in pairs]),
                  "median_on": _med([n["cpu_s"] for _, _, n in pairs])}
    pr = Counter()
    for _, _, n in pairs:
        pr.update(n["pruned"])
    out["pruning"] = {"pruned_total": sum(n["n_pruned"] for _, _, n in pairs), "by_reason": dict(pr),
                      "tasks_with_pruning": sum(n["n_pruned"] > 0 for _, _, n in pairs),
                      "native_runs": sum(n["native_runs"] for _, _, n in pairs),
                      "stream_read_on": sum(n["stream_read"] for _, _, n in pairs),
                      "executed_on": sum(n["n_candidates"] for _, _, n in pairs),
                      "pruned_checked": sum(n["pruned_fit_check"]["checked"] for _, _, n in pairs),
                      "pruned_that_fit": sum(n["pruned_fit_check"]["fit"] for _, _, n in pairs)}
    out["per_task"] = [{"family": t[0], "seed": t[1], "source": o["source"],
                        "first_fit": [o["first_fit_at"], n["first_fit_at"]],
                        "first_correct": [o["first_correct_at"], n["first_correct_at"]],
                        "cpu": [o["cpu_s"], n["cpu_s"]], "pruned": n["n_pruned"], "native_runs": n["native_runs"],
                        "class_candidates": o["class_candidates"]} for t, o, n in pairs]
    json.dump(out, open(os.path.join(os.path.dirname(paths[0]), "ablation_summary.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_task"}, indent=1))
    print("\n| family | seed | first fit off/on | first correct off/on | CPU s off/on | pruned | pick-set runs |")
    print("|---|---|---|---|---|---|---|")
    for r in out["per_task"]:
        print(f"| {r['family']} | {r['seed']} | {r['first_fit'][0]} / {r['first_fit'][1]} | "
              f"{r['first_correct'][0]} / {r['first_correct'][1]} | {r['cpu'][0]} / {r['cpu'][1]} | "
              f"{r['pruned']} | {r['native_runs']} |")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "one":
        print(json.dumps(one(sys.argv[2], int(sys.argv[3]), sys.argv[4])))
    elif cmd == "run":
        run(sys.argv[2], *sys.argv[3:4])
    elif cmd == "summary":
        summary(sys.argv[2:])
