"""v1.9 supplementary development measurement: the REDUCED-DEMONSTRATION
false-acceptance control (DEVELOPMENT ONLY, the 30 audited tasks).

Why: on the development corpus, seven demonstrations pin down the held-out
behaviour of every verified candidate; the section-15 control and the wider
pool/transplant/BLIND rule (`v19_falseaccept_dev.py`) found 0 wrong
extensions in 30 tasks, so neither can measure a false-acceptance cost.
Here the engine sees fewer demonstrations, so extensions that verify them
yet generalize wrongly exist by construction of ambiguity.

Per task: S = training pairs 0..K-1 (K = 4); E = training pairs K..6 plus
the held-out pair. On S, the frozen v1.8 FAILURE_CONDITIONED machinery
gives a verified, deduplicated pool (MDL order) and a selection. Trials,
distinct by production name:
- WRONG: up to WRONG_FROM_POOL pool candidates whose fitter prediction
  (fitted on S) is wrong on some pair of E, then the selection on S if it
  is wrong there and not already taken;
- RIGHT: the selection on S when it is right on every pair of E.
Each trial's production is installed into K* and into K*' with training
pairs S. A false acceptance: accepted and the engine's prediction is wrong
on some pair of E. A true acceptance: accepted and right on every pair of E.

  worker <wid> | reset_claims | analyze
"""
import collections
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
import v19_repair_dev as RD                                       # noqa: E402

R = RD.R
K = 4
WRONG_FROM_POOL = 3
ROWS = os.path.join(RD.OUT, "v19_falseaccept_reduced_dev_rows.jsonl")
REPORT = os.path.join(RD.OUT, "v19_falseaccept_reduced_dev_report.json")
CLAIMS = os.path.join(RD.LOG, "falseaccept_reduced_claims.json")


def right_on(fitted, pairs):
    for a, b in pairs:
        pred = P._evaluate(fitted, a)
        if pred is None or not np.array_equal(pred, b):
            return False
    return True


def engine_on(run, pairs):
    return all(X.predict_exact(run, a, b) for a, b in pairs)


def trials(S, E):
    sem = P.Semantics(S)
    inp = P.build_input(S, sem)
    deadline = time.time() + P.LIMITS["wall_s"]
    verified = []
    for depth in P.LIMITS["depths"]:
        gen = P.propose(inp, depth, sem, deadline)
        verified = P.verify(gen["proposals"], sem, deadline)
        if verified:
            break
    pool = P.dedupe(verified, deadline)
    out, names = [], set()
    for rank, c in enumerate(pool):
        if sum(1 for t in out if t[0] == "WRONG") >= WRONG_FROM_POOL:
            break
        if not right_on(c["fitted"], E):
            pw = X.compile_extension(X.make_input(c["schema"]))
            if pw["name"] not in names:
                names.add(pw["name"])
                out.append(("WRONG", f"POOL_{rank}", pw))
    rec = P.solve(S, "FAILURE_CONDITIONED")
    if rec["class"] == "SELECTED":
        ps = P.compile_selected(rec)
        right = right_on(rec["selected_fitted"], E)
        if ps["name"] not in names:
            names.add(ps["name"])
            out.append(("RIGHT" if right else "WRONG", "SELECTION", ps))
    return out, len(pool), rec["class"]


def process(task):
    train = [RD.ungrid(p) for p in task["train"]]
    held = RD.ungrid(task["held"])
    S, E = train[:K], train[K:] + [held]
    tl, pool, cls = trials(S, E)
    row = {"index": task["index"], "pool": pool, "selection_class": cls, "trials": []}
    for kind, source, pw in tl:
        old = X.run_reasoner(S, (pw,))
        new = R.run_reasoner(S, (pw,))
        row["trials"].append({
            "kind": kind, "source": source, "production": pw["name"],
            "old": {"accepted": old["accepted"], "right_on_E": engine_on(old, E) if old["accepted"] else None,
                    "uses": bool(old["accepted"] and X.uses_extension(old["program"], pw))},
            "new": {"accepted": new["accepted"], "right_on_E": engine_on(new, E) if new["accepted"] else None,
                    "uses": bool(new["accepted"] and X.uses_extension(new["program"], pw)),
                    "restored": R.restored()}})
    return row


def worker(wid):
    items = RD.tasks()
    while True:
        j = RD.claim(CLAIMS, len(items))
        if j is None:
            break
        task, _diag = items[j]
        try:
            row = process(task)
        except Exception as exc:                              # noqa: BLE001
            import traceback
            row = {"index": task["index"], "status": "RUN_ERROR", "error": type(exc).__name__,
                   "trace": traceback.format_exc()[-2000:]}
        row["worker"] = wid
        RD.append(ROWS, row)
        print(f"{time.strftime('%H:%M:%S')} w{wid} task {row['index']} trials {len(row.get('trials', []))}",
              flush=True)


def analyze():
    allrows = RD.read_rows(ROWS)
    rows = [r for r in allrows if r.get("status") != "RUN_ERROR"]
    tr = [t for r in rows for t in r["trials"]]
    wrong = [t for t in tr if t["kind"] == "WRONG"]
    right = [t for t in tr if t["kind"] == "RIGHT"]

    def fa(side):
        return sum(1 for t in wrong if t[side]["accepted"] and not t[side]["right_on_E"])

    def ta(side):
        return sum(1 for t in right if t[side]["accepted"] and t[side]["right_on_E"])
    out = {"K": K, "tasks": len(rows), "errors": len(allrows) - len(rows),
           "trials": len(tr), "wrong_trials": len(wrong), "right_trials": len(right),
           "wrong_by_source": dict(collections.Counter(t["source"].split("_")[0] for t in wrong)),
           "false_accept_old": fa("old"), "false_accept_new": fa("new"),
           "new_only_false_accepts": [{"index": r["index"], "source": t["source"], "production": t["production"]}
                                      for r in rows for t in r["trials"] if t["kind"] == "WRONG"
                                      and t["new"]["accepted"] and not t["new"]["right_on_E"]
                                      and not (t["old"]["accepted"] and not t["old"]["right_on_E"])],
           "true_accept_old": ta("old"), "true_accept_new": ta("new"),
           "accepted_wrong_but_right_on_E": sum(1 for t in wrong for s in ("old", "new")
                                               if t[s]["accepted"] and t[s]["right_on_E"]),
           "restored_all": all(t["new"]["restored"] for t in tr)}
    json.dump(out, open(REPORT, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "worker":
        worker(int(sys.argv[2]))
    elif cmd == "reset_claims":
        done = sorted({i for i, (t, _) in enumerate(RD.tasks())
                       if t["index"] in {r["index"] for r in RD.read_rows(ROWS)}})
        json.dump(done, open(CLAIMS, "w"))
    elif cmd == "analyze":
        analyze()
