"""Failure-derived pruning (cora_neural_prune): soundness (every pruned candidate is executed here and must not fit),
determinism, and budget accounting. DEV families only; expected outputs are not used."""
import os
import sys
from collections import Counter

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402
from cora_neural_v2g2 import search as S2                                # noqa: E402
from cora_neural_v2g3 import delta as D                                  # noqa: E402
from cora_neural_v2g3 import families_v3 as F3                           # noqa: E402
from cora_neural_prune import prune as P                                 # noqa: E402
from cora_neural_prune import search as PS                               # noqa: E402

DEV2 = F.names("dev")
DEV3 = [k for k, v in F3.FAMILIES.items() if v[0] == "dev"]


def _task(fam, seed):
    made = (F.make_task if fam in F.FAMILIES else F3.make_task)(fam, seed)
    assert made is not None
    return made[0]


@pytest.mark.parametrize("fam,seed", [(DEV2[0], 0), (DEV2[1], 1), (DEV3[2], 1), (DEV3[4], 1)])
def test_pruned_candidates_never_fit(fam, seed):
    task = _task(fam, seed)
    r = PS.search(task, 400, prune=True, record_pruned=True)
    assert r["n_pruned"] == len(r["pruned_programs"]) > 0
    for prog in r["pruned_programs"]:
        assert not G.fit(prog, task["train"])[0], f"pruned a fitting candidate: {prog}"
        assert not D.fits(D.deltas(prog, task["train"], stop_early=False), len(task["train"]))


def test_family_key_only_takes_single_rule_local_programs():
    one = G.parse("(program S1 (list (rule (test is_line == #t) (recolor (color 3)))) keep (same_as_input))")
    two = G.parse("(program S1 (list (rule (test is_line == #t) (delete)) (rule (test size == 1) (delete))) keep (same_as_input))")
    assert P.family_key(one) == (one.args[0], one.args[1][0].args[0], ("recolor", 3)) and P.family_key(two) is None


def test_determinism_and_budget_accounting():
    task = _task(DEV2[2], 0)
    a, b = PS.search(task, 300, prune=True), PS.search(task, 300, prune=True)
    for k in ("cpu_s", "first_fit_cpu", "pred_cpu"):
        a.pop(k), b.pop(k)
    assert a == b
    assert a["n_candidates"] <= 300 and a["stream_read"] == a["n_candidates"] + a["n_pruned"]
    off = PS.search(task, 300, prune=False)
    assert off["n_pruned"] == 0 and off["native_runs"] == 0 and off["stream_read"] == off["n_candidates"] == 300
    assert off["class_sha"] == a["class_sha"]
    # same stream: every distinct prediction the pruned run found, the unpruned run found no earlier
    first_off = dict(zip(map(str, off["predictions"]), off["pred_at"]))
    for pr, at in zip(a["predictions"], a["pred_at"]):
        assert str(pr) not in first_off or at <= first_off[str(pr)]


def _in_class(prog):
    """The class the soundness argument covers, written out independently of prune.family_key: one plain rule, objects
    not picked kept, the input's frame, and a local action (delete, or recolour to a literal colour)."""
    if getattr(prog, "op", None) != "program" or len(prog.args) != 4:
        return False
    _, rules, default, render = prog.args
    if len(rules) != 1 or default != "keep" or getattr(render, "op", None) != "same_as_input":
        return False
    rule = rules[0]
    if rule.op != "rule" or len(rule.args) != 2:
        return False
    act = rule.args[1]
    if act.op == "delete":
        return not act.args
    return act.op == "recolor" and len(act.args) == 1 and getattr(act.args[0], "op", None) == "color"


def test_pruning_never_touches_programs_outside_the_class():
    """Multi-rule programs, bound rules, computed colours, delete-by-default and non-local actions (moves, copies,
    composites) are never pruned and never teach a constraint."""
    task = _task(DEV2[0], 0)
    kinds = Counter()
    for prog, _ in S2.enumerate_programs(task, 3000):
        inside = _in_class(prog)
        assert (P.family_key(prog) is not None) == inside
        multi = getattr(prog, "op", None) == "program" and len(prog.args) == 4 and len(prog.args[1]) > 1
        kinds["inside" if inside else "multi-rule" if multi else "other"] += 1
    assert kinds["inside"] and kinds["multi-rule"] and kinds["other"]
    r = PS.search(task, 400, prune=True, record_pruned=True)
    assert r["pruned_programs"] and all(_in_class(p) for p in r["pruned_programs"])
