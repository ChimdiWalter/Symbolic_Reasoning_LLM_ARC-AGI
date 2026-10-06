"""v1.9 supplementary development measurement: the false-acceptance control
with more trials (DEVELOPMENT ONLY, the 30 audited tasks).

Wrong extensions per task, in this order, distinct by production name:
- up to WRONG_FROM_POOL candidates of the FAILURE_CONDITIONED proposer's
  verified, deduplicated pool on the seven pairs, in MDL order, whose
  fitter prediction of the held-out pair is wrong;
- the SHUFFLED_FRONTIER (transplant; donor = the next development task by
  index, as in the prospective derangement) and BLIND selections, when
  selected and not useful (verified on the seven pairs, wrong on the
  held-out pair).
Each is installed into K* (old logic) and into K*' (K* + K*-4) on the seven
pairs; a false acceptance is an accepted run whose held-out prediction is
wrong. Rows: outputs/tti/v19_falseaccept_dev_rows.jsonl.

  worker <wid> | reset_claims | analyze
"""
import base64
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
import v18_prospective as PR18                                    # noqa: E402
import v19_repair_dev as RD                                       # noqa: E402

R = RD.R
WRONG_FROM_POOL = 3
ROWS = os.path.join(RD.OUT, "v19_falseaccept_dev_rows.jsonl")
REPORT = os.path.join(RD.OUT, "v19_falseaccept_dev_report.json")
CLAIMS = os.path.join(RD.LOG, "falseaccept_claims.json")


def wrong_set(train, held, donor_failure, selected_name):
    out = []
    names = {selected_name}
    sem = P.Semantics(train)
    inp = P.build_input(train, sem)
    deadline = time.time() + P.LIMITS["wall_s"]
    verified = []
    for depth in P.LIMITS["depths"]:
        gen = P.propose(inp, depth, sem, deadline)
        verified = P.verify(gen["proposals"], sem, deadline)
        if verified:
            break
    taken = 0
    for rank, c in enumerate(P.dedupe(verified, deadline)):
        if taken >= WRONG_FROM_POOL:
            break
        pred = P._evaluate(c["fitted"], held[0])
        if pred is None or not (pred.shape == held[1].shape and (pred == held[1]).all()):
            prod = X.compile_extension(X.make_input(c["schema"]))
            if prod["name"] not in names:
                names.add(prod["name"])
                out.append(("POOL", rank, prod))
                taken += 1
    for arm in ("SHUFFLED_FRONTIER", "BLIND"):
        rec = P.solve(train, arm, donor_failure=donor_failure if arm == "SHUFFLED_FRONTIER" else None)
        if rec["class"] == "SELECTED" and not PR18.heldout_exact(rec, held):
            prod = P.compile_selected(rec)
            if prod["name"] not in names:
                names.add(prod["name"])
                out.append((arm, None, prod))
    return out


def process(j, items):
    task, diag = items[j]
    train = [RD.ungrid(p) for p in task["train"]]
    held = RD.ungrid(task["held"])
    donor_task = items[(j + 1) % len(items)][0]
    donor = P.build_input([RD.ungrid(p) for p in donor_task["train"]])["failure"]
    prod = X.load(base64.b64decode(diag["production"]))
    row = {"index": task["index"], "category": diag["category"], "trials": []}
    for source, rank, pw in wrong_set(train, held, donor, prod["name"]):
        row["trials"].append({"source": source, "mdl_rank": rank, "production": pw["name"],
                              "old": RD.summarize(X.run_reasoner(train, (pw,)), held, pw),
                              "new": RD.summarize(R.run_reasoner(train, (pw,)), held, pw)})
    return row


def worker(wid):
    items = RD.tasks()
    while True:
        j = RD.claim(CLAIMS, len(items))
        if j is None:
            break
        try:
            row = process(j, items)
        except Exception as exc:                              # noqa: BLE001
            import traceback
            row = {"index": items[j][0]["index"], "status": "RUN_ERROR", "error": type(exc).__name__,
                   "trace": traceback.format_exc()[-2000:]}
        row["worker"] = wid
        RD.append(ROWS, row)
        print(f"{time.strftime('%H:%M:%S')} w{wid} task {row['index']} trials {len(row.get('trials', []))}",
              flush=True)


def analyze():
    rows = [r for r in RD.read_rows(ROWS) if r.get("status") != "RUN_ERROR"]
    trials = [t for r in rows for t in r["trials"]]
    fa = lambda w: w["accepted"] and not w["heldout_exact"]      # noqa: E731
    out = {"tasks": len(rows), "trials": len(trials),
           "by_source": dict(collections.Counter(t["source"] for t in trials)),
           "accepted_old": sum(1 for t in trials if t["old"]["accepted"]),
           "accepted_new": sum(1 for t in trials if t["new"]["accepted"]),
           "false_accept_old": sum(1 for t in trials if fa(t["old"])),
           "false_accept_new": sum(1 for t in trials if fa(t["new"])),
           "new_only_false_accepts": [{"index": r["index"], "source": t["source"], "production": t["production"]}
                                      for r in rows for t in r["trials"] if fa(t["new"]) and not fa(t["old"])],
           "errors": sum(1 for r in RD.read_rows(ROWS) if r.get("status") == "RUN_ERROR")}
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
