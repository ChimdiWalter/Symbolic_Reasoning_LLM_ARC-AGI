"""Independent pool for the guarded-construction generalization test (DEVELOPMENT; exposed ARC-AGI-2 training tasks).

  python -m cora_fhr.corpus_standin   -> outputs/cora_fhr/standin58.json, standin58_perm.json, standin58_pool.json

The pool is fixed by rule, decided before any guarded run on it:
- every task the CORA_FHR_V1 committed rehearsal ran FHR on (`fhr == "ran"` in
  `outputs/kaggle_deploy/cora_fhr_v1/run_v1/fhr_rows.jsonl`): growth-shaped and not native-object-certified;
- minus every task that is also one of the 60 dev tasks (matched by the content of its training pairs).

Answers (test outputs) come only from the pinned ARC-AGI-2 training solutions and are stored for the evaluator.
`solver_view` passes training pairs and test inputs only.

The colour-relabelled twin applies a fixed permutation of colours 1-9 to every grid, with background 0 fixed.
The seed is sha256(task id). The permutation is generator metadata only (`_sigma`); no arm sees it.
"""
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")
REH = os.path.join(HERE, "outputs", "kaggle_deploy", "cora_fhr_v1", "run_v1", "fhr_rows.jsonl")
STANDIN = os.path.join(HERE, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "comp", "arc-agi_test_challenges.json")


def _hash_train(task):
    return hashlib.sha256(json.dumps([[p["input"], p["output"]] for p in task["train"]]).encode()).hexdigest()


def sigma_for(tid):
    rng = np.random.default_rng(int(hashlib.sha256(tid.encode()).hexdigest()[:8], 16))
    perm = [0] + [int(v) for v in rng.permutation(np.arange(1, 10))]
    return perm


def relabel(grid, perm):
    return [[perm[v] for v in row] for row in grid]


def main():
    from cora_pilot import bundle as B, evaluator as EV
    sol = EV.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)
    st = json.load(open(STANDIN))
    dev = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
    dev_hashes = {_hash_train(t) for t in dev.values()}
    ran = [json.loads(l)["key"] for l in open(REH) if json.loads(l).get("fhr") == "ran"]
    pool = sorted(t for t in ran if _hash_train(st[t]) not in dev_hashes)
    tasks, perm_tasks = {}, {}
    for tid in pool:
        t = st[tid]
        outs = sol[tid]
        tasks[tid] = {"family": "standin", "train": [[p["input"], p["output"]] for p in t["train"]],
                      "test": [[c["input"], o] for c, o in zip(t["test"], outs)]}
        s = sigma_for(tid)
        perm_tasks[tid + "_p"] = {"family": "standin_perm", "_sigma": s,
                                  "train": [[relabel(p["input"], s), relabel(p["output"], s)] for p in t["train"]],
                                  "test": [[relabel(c["input"], s), relabel(o, s)] for c, o in zip(t["test"], outs)]}
    json.dump({"pool_rule": "rehearsal fhr=='ran' minus dev60 overlaps", "tasks": tasks}, open(os.path.join(OUT, "standin58.json"), "w"))
    json.dump({"pool_rule": "colour-relabelled twin of standin58 (sigma seeded by sha256(task id))", "tasks": perm_tasks},
              open(os.path.join(OUT, "standin58_perm.json"), "w"))
    json.dump({"ran": len(ran), "dev60_overlap_removed": len(ran) - len(pool), "pool": pool},
              open(os.path.join(OUT, "standin58_pool.json"), "w"), indent=1)
    print(f"rehearsal ran {len(ran)}; dev60 overlaps removed {len(ran) - len(pool)}; pool {len(pool)}")


if __name__ == "__main__":
    main()
