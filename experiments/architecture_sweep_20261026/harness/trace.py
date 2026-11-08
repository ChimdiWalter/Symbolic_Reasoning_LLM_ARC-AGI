"""Decision-trace logging contract (every family, every decision, one JSON line):

    state hash -> observed features -> available actions -> selected action -> executable change
               -> demonstration effects -> cost

    with DecisionLog(path, policy="A1-structured") as log:
        log.decision(state, selected, effect, scores=None)

Fields: policy, task_id, step, state_hash, observed (global feature vector, per-hypothesis digests: key prefix,
vs, acc, behaviour prefix), available (action names), selected, scores (the policy's per-action scores, if any),
change (new program keys/ops, or the attempt reordering), effects (status/accuracy of each new program on the
VISIBLE demonstrations; whether a new behaviour appeared), cost (executions requested, CPU s). No withheld or
hidden output, no answer path and no task-id lookup is ever written here.
"""
import json

from harness import actions as A
from harness import paths as P


class DecisionLog:
    def __init__(self, path, policy):
        self.path, self.policy, self.f, self.n = path, policy, None, 0

    def __enter__(self):
        self.f = P.open_allowed(self.path, mode="a")
        return self

    def __exit__(self, *exc):
        self.f.close()

    def decision(self, state, selected, effect, scores=None):
        acts = state.available()
        rec = {"policy": self.policy, "task_id": state.task.get("task_id"), "step": state.steps,
               "state_hash": state.hash(),
               "observed": {"glob": [round(float(v), 4) for v in state.global_features()],
                            "hyps": [[h.key[:10], int(h.vs), round(h.acc, 3), (h.qkey or "")[:8]] for h in state.hyps]},
               "available": [A.action_name(state, a) for a in acts], "selected": A.action_name(state, selected),
               "scores": None if scores is None else [round(float(s), 4) for s in scores],
               "change": {"new": [[x["key"][:10], x["op"]] for x in effect["new"]],
                          "attempts_before": [str(q)[:8] for q in effect["attempts_before"]],
                          "attempts_after": [str(q)[:8] for q in effect["attempts_after"]]},
               "effects": {"new_status": [[x["status"], x["acc"], x["vs"]] for x in effect["new"]],
                           "new_behaviour": effect["new_behaviour"]},
               "cost": {"n_exec": effect["n_exec"], "cpu_s": effect["cpu"]}}
        self.f.write(json.dumps(rec) + "\n")
        self.n += 1
        return rec
