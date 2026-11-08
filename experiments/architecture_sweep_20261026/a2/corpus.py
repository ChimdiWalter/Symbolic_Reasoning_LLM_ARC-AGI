"""A2 verified program corpus: arc-dsl solvers of S_train (induction) and S_select (selection only), translated to
the tree IR and kept only when the tree reproduces BOTH the original solvers.py function and every demonstration
and test output of the ARC-AGI-2 public-training copy of the task (source labels, role source_labels).

    python -m a2.corpus            -> a2/out/corpus.json (task -> tree, verification record)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP]
from harness import paths as P        # noqa: E402
from harness import data as HD         # noqa: E402
from a2 import arcdsl as D            # noqa: E402

OUT = os.path.join(HERE, "out")


def tree_to_json(t):
    return [t[0]] + [tree_to_json(c) for c in t[1:]]


def tree_from_json(j):
    return (j[0],) + tuple(tree_from_json(c) for c in j[1:])


def build():
    ids = {t: "S_train" for t in HD.split_ids("S_train")}
    ids.update({t: "S_select" for t in HD.split_ids("S_select")})
    trees, errors = D.translate_solvers(ids)
    labels = {**HD.source_labels("S_train"), **HD.source_labels("S_select")}
    dsl, consts, _, _ = D.load()
    ev = D.Evaluator(dsl, consts)
    rec = {}
    for tid, tree in sorted(trees.items()):
        task = HD.task_record(tid, ids[tid])
        pairs = list(task["train"]) + list(zip(task["test_inputs"], labels[tid]))
        orig = D.solver_function(tid)
        faithful, correct, err = True, True, None
        for x, y in pairs:
            X = D.to_grid(x)
            try:
                a = ev.run(tree, X)
            except Exception as e:                                      # noqa: BLE001
                a, err = None, f"tree: {type(e).__name__}"
            try:
                b = orig(X)
            except Exception as e:                                      # noqa: BLE001
                b, err = None, err or f"solver: {type(e).__name__}"
            faithful &= (a == b)
            correct &= (a == D.to_grid(y))
        rec[tid] = {"split": ids[tid], "faithful": faithful, "verified": faithful and correct, "error": err,
                    "size": D.size(tree), "prims": D.prim_count(tree), "tree": tree_to_json(tree)}
    return rec, errors


def main():
    t0 = time.process_time()
    rec, errors = build()
    os.makedirs(OUT, exist_ok=True)
    summ = {}
    for s in ("S_train", "S_select"):
        r = [v for v in rec.values() if v["split"] == s]
        summ[s] = {"translated": len(r), "faithful": sum(v["faithful"] for v in r),
                   "verified": sum(v["verified"] for v in r)}
    doc = {"arc_dsl_sha256": D.file_hashes(), "summary": summ, "untranslatable": errors, "tasks": rec,
           "cpu_s": round(time.process_time() - t0, 2)}
    with P.open_allowed(os.path.join(OUT, "corpus.json"), mode="w") as f:
        json.dump(doc, f)
    print(json.dumps({"summary": summ, "untranslatable": len(errors), "cpu_s": doc["cpu_s"]}))


if __name__ == "__main__":
    main()
