"""Input pools of the study (written once, before the pilot): ARC training task ids only.

    python -m cas.pools OUT.json

Candidates: the campaign's S_train and S_select splits (both drawn from arc-agi_training_challenges.json; the 120
public evaluation tasks, ARC_eval_dev, are a different file and are never read here), minus every task S1 used (its
sources and its real previously solved tasks, read from S1's evaluator file), so that every task of this study is
new. Order: sha256("cas-pools-20261105|" + id). The first PILOT ids form the pilot pool (pilot only, excluded from the
study); the rest form the main pool.
"""
import hashlib
import json
import os
import sys

from cas import env as E                                                       # noqa: F401
from harness import data as HD                                                  # noqa: E402

SALT = "cas-pools-20261105"
PILOT = 100


def main(out):
    split_of = {}
    for split in ("S_train", "S_select"):
        for t in HD.split_ids(split):
            split_of[t] = split
    evald = set(HD.split_ids("ARC_eval_dev"))
    assert not (evald & set(split_of)), "an evaluation id in the training splits"
    s1 = E.load(os.path.join(E.S1_DIR, "evaluator_only", "TASKS_EVAL.json"))
    s1_ids = sorted({t["source"] for t in s1.values()})
    cand = sorted((t for t in split_of if t not in set(s1_ids)),
                  key=lambda t: hashlib.sha256((SALT + "|" + t).encode()).hexdigest())
    pilot, main_ = sorted(cand[:PILOT]), sorted(cand[PILOT:])
    h = lambda xs: hashlib.sha256(json.dumps(xs).encode()).hexdigest()   # noqa: E731
    doc = {"salt": SALT, "source_file": "arc-agi_training_challenges.json (splits S_train and S_select)",
           "excluded_s1_tasks": s1_ids, "n_candidates": len(cand), "pilot": pilot, "main": main_,
           "split_of": {t: split_of[t] for t in cand},
           "sha256": {"pilot": h(pilot), "main": h(main_), "excluded_s1_tasks": h(s1_ids)},
           "counts": {"S_train": sum(v == "S_train" for v in split_of.values()),
                      "S_select": sum(v == "S_select" for v in split_of.values()), "excluded_s1": len(s1_ids),
                      "pilot": len(pilot), "main": len(main_)},
           "evaluation_ids_overlap": 0}
    E.dump(out, doc)
    print(json.dumps(doc["counts"]))


if __name__ == "__main__":
    main(sys.argv[1])
