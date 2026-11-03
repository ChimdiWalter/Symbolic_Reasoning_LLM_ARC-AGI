#!/usr/bin/env python3
"""Score predictions on the ARC-AGI-2 public evaluation set, or compare a rerun with the expected predictions.

Standard library only. The solutions are not part of this release: they are competition data. Pass your own copy of
`arc-agi_evaluation_solutions.json`, from the data page of the Kaggle competition `arc-prize-2026-arc-agi-2`.

  python3 score_rehearsal.py --solutions PATH [--pred FILE ...]
      Scores each prediction file; by default the two files in expected_predictions/.
  python3 score_rehearsal.py --compare NEW_FILE [--pred EXPECTED_FILE]
      Compares a rerun's submission.json with an expected file, output by output; needs no solutions.
      Tasks missing from NEW_FILE (a run on fewer puzzles) are counted, not treated as differences.

Metric, as Kaggle's evaluation page states it: "For a given task output, any of the 2 predicted outputs matches the
ground truth exactly, you score 1 for that task test output, otherwise 0. The final score is the sum averaged of the
highest score per task output divided by the total number of task test outputs." That is `per_output`. Also given:
`task_mean`, the mean over puzzles of each puzzle's fraction of correct outputs, and `strict_tasks`, the puzzles with
every output correct. Only counts and output names (task id:test index) are printed, never a grid.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPECTED = {"O+ v2": os.path.join(HERE, "expected_predictions", "O_plus_v2_eval120_submission.json"),
            "H": os.path.join(HERE, "expected_predictions", "H_eval120_submission.json")}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def is_grid(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) and 1 <= len(r) <= 30 for r in g)
            and len({len(r) for r in g}) == 1
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


def check_solutions(sol):
    if not isinstance(sol, dict) or not sol:
        raise SystemExit("the solutions file is not a JSON object of task ids")
    for tid, outs in sol.items():
        if not isinstance(outs, list) or not outs or not all(is_grid(g) for g in outs):
            raise SystemExit(f"the solutions file has no list of grids for task {tid}")


def attempts(pred, tid, j):
    e = pred.get(tid) if isinstance(pred, dict) else None
    x = e[j] if isinstance(e, list) and j < len(e) and isinstance(e[j], dict) else {}
    return x.get("attempt_1"), x.get("attempt_2")


def score(pred, sol):
    correct, per_task, first = [], [], 0
    for tid in sorted(sol):
        ok = 0
        for j, truth in enumerate(sol[tid]):
            a1, a2 = attempts(pred, tid, j)
            if a1 == truth or a2 == truth:
                correct.append(f"{tid}:{j}")
                ok += 1
                first += a1 == truth
        per_task.append(ok / len(sol[tid]))
    n = sum(len(v) for v in sol.values())
    return {"outputs": n, "correct_outputs": len(correct), "per_output": round(len(correct) / n, 6),
            "tasks": len(sol), "task_mean": round(sum(per_task) / len(per_task), 6),
            "strict_tasks": sum(v == 1.0 for v in per_task), "correct_by_attempt_1": first,
            "tasks_missing_from_predictions": sum(1 for t in sol if t not in pred),
            "tasks_not_in_solutions": sum(1 for t in pred if t not in sol), "correct": correct}


def compare(new, exp):
    common = sorted(set(new) & set(exp))
    same, diff = 0, []
    for tid in common:
        a, b = new[tid], exp[tid]
        if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
            diff.append(f"{tid}:*")
            continue
        for j, (x, y) in enumerate(zip(a, b)):
            if x == y:
                same += 1
            else:
                diff.append(f"{tid}:{j}")
    return {"tasks_compared": len(common), "outputs_identical": same, "outputs_different": diff,
            "tasks_only_in_new": sorted(set(new) - set(exp)), "tasks_missing_from_new": len(set(exp) - set(new))}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--solutions", help="your copy of arc-agi_evaluation_solutions.json")
    ap.add_argument("--pred", action="append", help="a prediction file (submission.json format); repeatable")
    ap.add_argument("--compare", help="a rerun's submission.json, compared with the one --pred file")
    a = ap.parse_args()
    if a.compare:
        if not a.pred or len(a.pred) != 1:
            raise SystemExit("--compare NEW_FILE needs exactly one --pred EXPECTED_FILE")
        r = compare(load(a.compare), load(a.pred[0]))
        r["files_byte_identical"] = sha256_file(a.compare) == sha256_file(a.pred[0])
        print(json.dumps(r, indent=1))
        sys.exit(1 if r["outputs_different"] or r["tasks_only_in_new"] else 0)
    if not a.solutions:
        raise SystemExit("--solutions PATH is required for scoring (the file is not included in this release)")
    sol = load(a.solutions)
    check_solutions(sol)
    res = {}
    for name, path in ({p: p for p in a.pred} if a.pred else EXPECTED).items():
        pred = load(path)
        if not isinstance(pred, dict):
            raise SystemExit(f"{path} is not a submission.json object")
        res[name] = dict(score(pred, sol), file_sha256=sha256_file(path))
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
