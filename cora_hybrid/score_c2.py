"""Evaluator-side score of the finished C2 CORA_ONLY arm. This measures
accuracy, not completion.

  python -m cora_hybrid.score_c2   -> outputs/hybrid_c2/cora_only_score.json

Reads the committed submission (outputs/hybrid_c2/native_run/working/) and
outputs/hybrid_c2/solutions.json, which only the evaluator reads. Reports,
per family:
- exact under the competition's two-attempt rule;
- attempt_1 exact;
- the harness's own per-task label from the run log (the layer that
  certified the task, or "unsolved").

A certified-but-wrong answer is counted as a harm. It scores the frozen
native output only: nothing is rerun or tuned.
"""
import collections
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C2 = os.path.join(HERE, "outputs", "hybrid_c2")


def main():
    sub = json.load(open(os.path.join(C2, "native_run", "working", "submission.json")))
    sol = json.load(open(os.path.join(C2, "solutions.json")))
    meta = json.load(open(os.path.join(C2, "manifest.json")))["task_meta"]
    log = open(os.path.join(C2, "native_run", "notebook.log")).read()
    label = {m.group(1): m.group(2) for m in re.finditer(r"\[harness\] \d+/\d+ (\S+) (\S+) \(", log)}
    rows, fam = [], collections.defaultdict(collections.Counter)
    for tid, outs in sorted(sol.items()):
        ent = sub.get(tid, [])
        ok_any = all(i < len(ent) and out in (ent[i].get("attempt_1"), ent[i].get("attempt_2")) for i, out in enumerate(outs))
        ok_1 = all(i < len(ent) and ent[i].get("attempt_1") == out for i, out in enumerate(outs))
        lab = label.get(tid, "missing")
        f = meta[tid]["family"] if isinstance(meta[tid], dict) else meta[tid]
        rows.append({"task": tid, "family": f, "label": lab, "exact_2attempt": ok_any, "exact_attempt1": ok_1})
        c = fam[f]
        c["tasks"] += 1
        c["exact_2attempt"] += ok_any
        c["certified"] += lab != "unsolved"
        c["certified_correct"] += lab != "unsolved" and ok_any
        c["certified_wrong"] += lab != "unsolved" and not ok_any
        c["uncertified_correct"] += lab == "unsolved" and ok_any
    tot = collections.Counter()
    for c in fam.values():
        tot.update(c)
    out = {"label": "C2 CORA_ONLY (SYNTHETIC; native v23 harness, frozen notebook); evaluator-side score",
           "total": dict(tot), "by_family": {k: dict(v) for k, v in sorted(fam.items())},
           "harness_labels": dict(collections.Counter(r["label"] for r in rows)), "tasks": rows}
    json.dump(out, open(os.path.join(C2, "cora_only_score.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("total", "harness_labels", "by_family")}, indent=1))


if __name__ == "__main__":
    main()
