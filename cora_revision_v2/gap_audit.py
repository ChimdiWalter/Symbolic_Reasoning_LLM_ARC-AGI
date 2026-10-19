"""Phase 0 gap audit: transformation types (DEVELOPMENT).

  python -m cora_revision_v2.gap_audit   -> outputs/cora_revision_v2/gap_audit_20261019.json

- OBSERVABLE: every one of the 240 stand-in tasks, from its TRAINING pairs only (no answers).
- FORENSIC (evaluator-only): the 58-task pool, including the test pair with its true answer.

Change types per pair: resize (the output shape differs); otherwise each changed cell is an addition
(background to colour), a deletion (colour to background) or a recolour (colour to another colour).
Additions are also split into single-colour and multi-colour.
"""
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_revision_v2")
STANDIN = os.path.join(HERE, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "comp", "arc-agi_test_challenges.json")


def pair_types(a, b):
    A, B = np.asarray(a), np.asarray(b)
    if A.shape != B.shape:
        return {"resize"}
    vals, cnt = np.unique(A, return_counts=True)
    bg = vals[int(np.argmax(cnt))]
    ch = A != B
    t = set()
    if (ch & (A == bg)).any():
        t.add("add_multicolour" if len(np.unique(B[ch & (A == bg)])) > 1 else "add")
    if (ch & (A != bg) & (B == bg)).any():
        t.add("delete")
    if (ch & (A != bg) & (B != bg)).any():
        t.add("recolour")
    return t or {"identity"}


def label(types):
    if "resize" in types:
        return "resize"
    core = {x.replace("_multicolour", "") for x in types} - {"identity"}
    if core == {"add"}:
        return "add_only_multicolour" if "add_multicolour" in types else "add_only"
    if len(core) == 1:
        return f"{next(iter(core))}_only"
    return "mixed:" + "+".join(sorted(core)) if core else "identity"


def main():
    os.makedirs(OUT, exist_ok=True)
    st = json.load(open(STANDIN))
    obs = {tid: label(set().union(*[pair_types(p["input"], p["output"]) for p in t["train"]])) for tid, t in st.items()}
    pool = json.load(open(os.path.join(HERE, "outputs", "cora_fhr", "standin58.json")))["tasks"]
    forensic = {tid: label(set().union(*[pair_types(a, b) for a, b in t["train"] + t["test"]])) for tid, t in pool.items()}
    res = {"observable_240_train_only": dict(collections.Counter(obs.values()).most_common()),
           "forensic_58_with_test_answer": dict(collections.Counter(forensic.values()).most_common()),
           "per_task_observable": obs}
    json.dump(res, open(os.path.join(OUT, "gap_audit_20261019.json"), "w"), indent=1)
    print("240 stand-in (training pairs only):", res["observable_240_train_only"])
    print("58 pool (forensic, with the test answer):", res["forensic_58_with_test_answer"])


if __name__ == "__main__":
    main()
