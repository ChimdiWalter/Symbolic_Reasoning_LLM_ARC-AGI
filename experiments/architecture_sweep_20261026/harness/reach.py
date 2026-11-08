"""Reachability audit (an evaluator-side diagnostic, never a deployed policy): within the declared menu and one step,
does any action reach exact withheld correctness? Each state is classified as
  base_correct        the proposer's own attempts are already correct (pass@2)
  ranking_gap         a correct behaviour is in memory: a COMMIT reaches it (a ranking/selection problem)
  construction_reach  only a constructive action (FILL / MUT / NEW) reaches it
  no_reach            nothing in the menu reaches it in one step (an action / representation gap)
Source splits use the stored labels; ARC_eval_dev is audited by `python -m harness.scorer --reach` (separate process).

    python -m harness.reach --ep runs/episodes_v1/data --out runs/episodes_v1/reach_source.json
"""
import argparse
import collections
import json
import os

from harness import episode_io as IO
from harness import paths as P


def classify(kinds, y2, base2):
    if base2:
        return "base_correct"
    if any(y and k == "COMMIT" for k, y in zip(kinds, y2)):
        return "ranking_gap"
    if any(y for y in y2):
        return "construction_reach"
    return "no_reach"


def audit(ep):
    out = {}
    for stage in ("S_train_syn", "S_select_syn", "S_train", "S_select"):
        d = os.path.join(ep, stage)
        if not os.path.isdir(d):
            continue
        S = [s for s in IO.load_stage(d, stage) if s["oc"] and s["oc"].get("rows")]
        cls, by_var, kinds_ok = collections.Counter(), {}, collections.Counter()
        for s in S:
            lab = IO.action_labels(s)
            ks = [a[0] for a in s["actions"]]
            c = classify(ks, lab["y2"] > 0, lab["base2"] > 0)
            cls[c] += 1
            by_var.setdefault(s["meta"]["variant"], collections.Counter())[c] += 1
            if c == "construction_reach":
                for k, y in zip(ks, lab["y2"]):
                    if y:
                        kinds_ok[k] += 1
        out[stage] = {"states": len(S), "classes": dict(cls), "by_variant": {k: dict(v) for k, v in by_var.items()},
                      "reaching_kinds": dict(kinds_ok),
                      "tasks_with_pstar": len({s["meta"]["task_id"] for s in S if s["meta"].get("has_pstar")})}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="runs/episodes_v1/data")
    ap.add_argument("--out", default="runs/episodes_v1/reach_source.json")
    a = ap.parse_args()
    ep = a.ep if os.path.isabs(a.ep) else os.path.join(P.EXP, a.ep)
    res = audit(ep)
    with P.open_allowed(os.path.join(P.EXP, a.out) if not os.path.isabs(a.out) else a.out, mode="w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: {"states": v["states"], "classes": v["classes"], "pstar_tasks": v["tasks_with_pstar"]}
                      for k, v in res.items()}, indent=1))


if __name__ == "__main__":
    main()
