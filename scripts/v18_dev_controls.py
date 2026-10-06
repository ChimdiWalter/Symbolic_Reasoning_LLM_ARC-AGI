"""Item-2 v1.8 erratum 01: development rates of every arm with the
erratum code, a regression check of the main arm against the stored
development audit, and the 3x-budget K* arm (the new witness leg A) on the
8 engine-subset tasks. DEVELOPMENT ONLY. Writes
outputs/tti/v18_dev_controls.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
import v18_corpus as CORPUS                                       # noqa: E402

OUT = os.path.join(HERE, "outputs", "tti", "v18_dev_controls.json")
STORED = os.path.join(HERE, "outputs", "tti", "v18_dev_rows.jsonl")
BASELINE_3X_BUDGET_S = 24.0


def useful(rec, held):
    import numpy as np
    if not rec.get("selected"):
        return False
    pred = P._evaluate(rec["selected_fitted"], held[0])
    return bool(pred is not None and np.array_equal(pred, held[1]))


def main():
    started = time.time()
    tasks = CORPUS.tasks(CORPUS.DEV_BASE, 40)
    stored = {json.loads(l)["seed"]: json.loads(l) for l in open(STORED)}
    rows = []
    for i, t in enumerate(tasks):
        j = (i + 1) % len(tasks)
        while tasks[j]["digest"] == t["digest"]:
            j = (j + 1) % len(tasks)
        donor = P.build_input(tasks[j]["train"])["failure"]
        row = {"i": i, "seed": t["seed"], "family": t["family"], "donor_seed": tasks[j]["seed"], "arms": {}}
        for arm in P.ARMS:
            rec = P.solve(t["train"], arm,
                          donor_failure=donor if arm in ("SHUFFLED_FRONTIER", "SHUFFLED_COORDINATES") else None)
            row["arms"][arm] = {"class": rec["class"], "proposals": rec["proposals"],
                                "verified_by_depth": rec.get("verified_by_depth"),
                                "level": (rec.get("selection") or {}).get("level"),
                                "selected": rec["selected"]["canonical"] if rec.get("selected") else None,
                                "useful": useful(rec, t["held"]), "seconds": rec["seconds"]}
        old = stored[t["seed"]]["arms"]["FAILURE_CONDITIONED"]
        row["fc_regression_equal"] = (row["arms"]["FAILURE_CONDITIONED"]["selected"] ==
                                      (old["selected"]["canonical"] if old.get("selected") else None)
                                      and row["arms"]["FAILURE_CONDITIONED"]["proposals"] == old["proposals"])
        if i < 8:
            run = X.run_reasoner(t["train"], (), budget_s=BASELINE_3X_BUDGET_S)
            row["baseline_3x"] = {"accepted": run["accepted"], "heldout_exact": X.predict_exact(run, *t["held"]),
                                  "seconds": run["seconds"], "loadavg": [round(x, 2) for x in os.getloadavg()]}
        rows.append(row)
        print(f"task {i} seed {t['seed']} fc_regression_equal={row['fc_regression_equal']} "
              f"{time.time() - started:.0f}s", flush=True)
    summary = {"tasks": len(rows), "fc_regression_equal": sum(r["fc_regression_equal"] for r in rows),
               "useful": {a: sum(1 for r in rows if r["arms"][a]["useful"]) for a in P.ARMS},
               "classes": {a: {c: sum(1 for r in rows if r["arms"][a]["class"] == c)
                               for c in sorted({r["arms"][a]["class"] for r in rows})} for a in P.ARMS},
               "discordant_vs_FC": {a: [sum(1 for r in rows if r["arms"]["FAILURE_CONDITIONED"]["useful"]
                                            and not r["arms"][a]["useful"]),
                                        sum(1 for r in rows if r["arms"][a]["useful"]
                                            and not r["arms"]["FAILURE_CONDITIONED"]["useful"])]
                                    for a in P.ARMS if a != "FAILURE_CONDITIONED"},
               "baseline_3x_engine_subset": [r["baseline_3x"] for r in rows if "baseline_3x" in r],
               "seconds": round(time.time() - started, 1), "development_only": True,
               "proposer_sha256": P.proposer_sha256()}
    with open(OUT, "w") as handle:
        handle.write(json.dumps({"summary": summary, "rows": rows}, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
