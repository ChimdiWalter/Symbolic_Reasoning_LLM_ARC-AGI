"""Real ARC pilot v1 feasibility: positive control of the CORA harness.

  python scripts/pilot_v1_positive_control.py INDEX   (one synthetic task per process)

Runs cora_pilot.reasoner.run_cora, unchanged and under the isolation hook,
on a synthetic v1.9 DEVELOPMENT task (outputs/tti/v19_dev_corpus.json),
where the constructive grammar applies by construction and the held-out
pair is known. It checks that the harness itself can reach activation; it
is not part of any frozen result and reads no ARC data.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def main(index: int) -> None:
    corpus = json.load(open(os.path.join(HERE, "outputs", "tti", "v19_dev_corpus.json")))
    t = corpus["tasks"][index]
    task = {"train": [{"input": a, "output": b} for a, b in t["train"]], "test": [{"input": t["held"][0]}]}
    key = "k%012x" % index
    d = tempfile.mkdtemp(prefix="pilot_pc_")
    bundle = os.path.join(d, "bundle.json")
    json.dump({"format": "cora-real-arc-pilot-bundle/1", "tasks": {key: task}}, open(bundle, "w"))
    from cora_pilot import isolation as ISO
    ISO.install(bundle)
    json.load(open(bundle))
    from cora_pilot import reasoner as RS
    row = RS.run_cora(key, task, None)
    held = t["held"][1]
    out = {"index": index, "family": t.get("family"), "path_class": row["path_class"],
           "activated": row["activated"], "fc": row["fc"]["class"], "level": row["fc"].get("level"),
           "gates": row.get("gates"), "loo": (row.get("loo") or {}).get("folds_success"),
           "prediction_correct": row.get("cora_prediction") == [held] if row["activated"] else None,
           "with_e_correct": (row.get("with_e") or {}).get("predictions") == [held],
           "kstar_prime_alone_correct": (row.get("kstar_prime_alone") or {}).get("predictions") == [held],
           "restored": row["restored"], "snapshot_equal": row["snapshot_equal"], "seconds": row["seconds"],
           "isolation_problems": ISO.audit_log(ISO.report())}
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main(int(sys.argv[1]))
