"""Native-solver gap audit on the Kaggle committed run (leader-method audit, section 8).

  python scripts/native_gap_audit.py   -> outputs/kaggle_deploy/native_v1/gap_audit.json

Permitted data only:
- the competition's public stand-in arc-agi_test_challenges.json (training
  pairs and test inputs, no answers);
- native_v1's own run rows and submission.json.

No answer is read, so the audit says nothing about correctness. It
characterizes where the native solver produces no candidate, or a candidate
whose shape contradicts the shape rule the demonstrations imply.

Shape rule (demonstrations only):
- same: every output has its input's size;
- constant: every output has one fixed size, different from the inputs;
- scaled: output = input size times one fixed rational factor per axis;
- other: anything else.
"""
import json
import os
from collections import Counter
from fractions import Fraction

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(HERE, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1")


def dims(g):
    return (len(g), len(g[0]))


def shape_rule(task):
    pairs = [(dims(p["input"]), dims(p["output"])) for p in task["train"]]
    if all(i == o for i, o in pairs):
        return "same", None
    outs = {o for _, o in pairs}
    if len(outs) == 1:
        return "constant", next(iter(outs))
    fr = {(Fraction(o[0], i[0]), Fraction(o[1], i[1])) for i, o in pairs}
    if len(fr) == 1:
        return "scaled", next(iter(fr))
    return "other", None


def expected_shape(rule, param, test_input):
    h, w = dims(test_input)
    if rule == "same":
        return (h, w)
    if rule == "constant":
        return param
    if rule == "scaled":
        a, b = param
        return (h * a, w * b) if (h * a).denominator == 1 and (w * b).denominator == 1 else None
    return None


def main():
    ch = json.load(open(os.path.join(RUN, "comp", "arc-agi_test_challenges.json")))
    rows = {r["task_id"]: r for r in map(json.loads, open(os.path.join(RUN, "run", "progress.jsonl")))}
    by_rule = Counter()
    table = Counter()
    shape_check = Counter()
    near = []
    layers = Counter()
    for tid, task in ch.items():
        rule, param = shape_rule(task)
        by_rule[rule] += 1
        r = rows.get(tid, {})
        p = r.get("predictions") or {}
        a1 = p.get("attempt_1") or []
        real = [i for i, case in enumerate(task["test"]) if i < len(a1) and a1[i]]
        status = "certified" if r.get("solved") else ("candidate" if real else "no_candidate")
        table[(rule, status)] += 1
        if r.get("solved"):
            layers[str(r.get("layer"))] += 1
        for i in real:
            exp = expected_shape(rule, param, task["test"][i]["input"])
            if exp is not None:
                shape_check[(rule, "consistent" if dims(a1[i]) == tuple(exp) else "inconsistent")] += 1
        ns = r.get("near_solve") or {}
        if status == "no_candidate" and ns.get("best_train_pixel_acc") is not None:
            near.append(float(ns["best_train_pixel_acc"]))
    near.sort()
    out = {"tasks": len(ch), "shape_rule": dict(by_rule),
           "status_by_rule": {f"{a}|{b}": n for (a, b), n in sorted(table.items())},
           "certified_layers": dict(layers),
           "candidate_shape_vs_demo_rule": {f"{a}|{b}": n for (a, b), n in sorted(shape_check.items())},
           "no_candidate_near_solve_train_pixel_acc": {"n": len(near), "median": near[len(near) // 2] if near else None,
                                                        "share_ge_0.9": round(sum(x >= 0.9 for x in near) / len(near), 3) if near else None}}
    json.dump(out, open(os.path.join(HERE, "outputs", "kaggle_deploy", "native_v1", "gap_audit.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
