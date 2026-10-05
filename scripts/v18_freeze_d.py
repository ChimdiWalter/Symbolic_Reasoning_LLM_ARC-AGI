"""Item-2 v1.8: freeze v1.6's demonstration selector D for reuse.

Replays scripts/evaluate_v16_cfr.py's own path (the v1.5 corpus records,
first admissions, v1.6 development responses, the training groups whose
token pair is not held out, the D standardizer and C.fit), fits D only, and
checks the refit against the v1.6 report on the v1.6 test queries: D's
ambiguous, unseen and end-to-end accuracy, D's NLL, and P0_then_D's
ambiguous accuracy. Writes outputs/tti/v18_frozen_d.json only if every
number reproduces.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v16_cfr as C                             # noqa: E402

OUT = os.path.join(HERE, "outputs", "tti", "v18_frozen_d.json")


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def evaluator():
    spec = importlib.util.spec_from_file_location(
        "evaluate_v16_cfr", os.path.join(HERE, "scripts", "evaluate_v16_cfr.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    E = evaluator()
    with open(E.MANIFEST) as handle:
        man = json.load(handle)
    train_inc, _ = L.first_admissions(E.load(E.TRAIN_DIR))
    dev_groups = sorted((r["group"] for r in train_inc), key=lambda g: g["group_digest"])
    test_inc, _ = L.first_admissions(E.load(E.TEST_DIR))
    test_groups = sorted((r["group"] for r in test_inc), key=lambda g: g["group_digest"])
    with open(E.TRAIN_RESP) as handle:
        train_resp = json.load(handle)
    with open(E.TEST_RESP) as handle:
        test_resp = json.load(handle)
    qdev = C.build_queries(dev_groups, E.rmap(train_resp))
    qte = C.build_queries(test_groups, E.rmap(test_resp))
    keep = set(E.train_groups_of(dev_groups, qdev, man))
    qtr = [q for q in qdev if q["group"] in keep]
    train_pairs = {q["pair_key"] for q in qtr}
    std = S.standardizer_for(qtr, None)
    model, info = C.fit(queries=qtr, rows=C.d_rows(qtr, std))

    sc = C.score(model, qte, C.d_rows(qte, std), None)
    units = [s["units"] for s in sc]
    unseen = lambda q: q["pair_key"] not in train_pairs            # noqa: E731
    p0_keys = tuple(man["P0_keys"])
    if p0_keys != C.P0_KEYS:
        raise SystemExit(f"manifest P0 keys {p0_keys} differ from v16_cfr.P0_KEYS")
    p0d = [C.p0_units(q, q["delta"], p0_keys, fallback_units=u) for q, u in zip(qte, units)]
    got = {"D_accuracy_ambiguous": C.ambiguous_accuracy(qte, units),
           "D_accuracy_ambiguous_unseen": C.ambiguous_accuracy(qte, units, unseen),
           "D_end_to_end": C.end_to_end_accuracy(qte, units),
           "D_nll": round(sum(s["nll"] for s in sc) / len(sc), 6),
           "P0_then_D_accuracy_ambiguous": C.ambiguous_accuracy(qte, p0d)}
    with open(os.path.join(HERE, "outputs", "tti", "v16_cfr_report.json")) as handle:
        rep = json.load(handle)
    want = {"D_accuracy_ambiguous": rep["arms"]["D"]["accuracy_ambiguous"],
            "D_accuracy_ambiguous_unseen": rep["arms"]["D"]["accuracy_ambiguous_unseen"],
            "D_end_to_end": rep["arms"]["D"]["end_to_end"],
            "D_nll": rep["nll"]["D"],
            "P0_then_D_accuracy_ambiguous": rep["arms"]["P0_then_D"]["accuracy_ambiguous"]}
    reproduced = {k: got[k] == want[k] for k in want}
    print(json.dumps({"got": got, "want": want, "reproduced": reproduced,
                      "training_queries": len(qtr), "fit": info}, indent=1))
    if not all(reproduced.values()) or len(qtr) != rep["training_queries"]:
        raise SystemExit("D does not reproduce v1.6; not written")
    frozen = {"what": "v1.6 demonstration selector D, refit by v1.6's own path and frozen for v1.8",
              "tokens": [list(t) for t in model["tokens"]],
              "W": [[float(x) for x in row] for row in model["W"]], "dim": model["dim"],
              "standardizer": {"fields": list(std.fields), "order": list(std.order),
                               "index": list(std.index), "mean": std.mean, "std": std.std},
              "row_layout": "[1] + standardized D_RICH (inactive fields 0) + grammar state vector (5)",
              "fit_info": info, "lambda": C.LAMBDA, "training_queries": len(qtr),
              "training_groups": len(keep),
              "sources": {"v16_manifest_sha256": sha(E.MANIFEST),
                          "v16_dev_responses_sha256": sha(E.TRAIN_RESP),
                          "v16_test_responses_sha256": sha(E.TEST_RESP),
                          "v15_corpus_records": len(os.listdir(E.TRAIN_DIR)),
                          "evaluate_v16_cfr_sha256": sha(os.path.join(HERE, "scripts", "evaluate_v16_cfr.py")),
                          "v16_cfr_sha256": sha(os.path.join(HERE, "cora_arc2026", "v16_cfr.py")),
                          "v15_sel_sha256": sha(os.path.join(HERE, "cora_arc2026", "v15_sel.py"))},
              "reproduction_on_v16_test": {"got": got, "want": want}}
    with open(OUT, "w") as handle:
        handle.write(json.dumps(frozen, indent=1, sort_keys=True) + "\n")
    print("written", OUT, sha(OUT))


if __name__ == "__main__":
    main()
