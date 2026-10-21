"""ncv2-g3 (engineering): scene fates, execution deltas and diagnostics, joint construction, evidence-aware selection,
two attempts over every test input, determinism, and parity with the unchanged ncv2-g2 agenda.

Only DEV-style tasks are used: hand-made grids, the ncv2-g2 DEV families, and test-local families defined here. The
ncv2-g2 HELDOUT families are spent (their frozen study is finished) and are not used. No answer is read by a solver:
expected outputs are compared here, in the test, after the search returns.
"""
import os
import sys
import zlib

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402
from cora_neural_v2g2 import search as S2                                # noqa: E402
from cora_neural_v2g3 import delta as D                                  # noqa: E402
from cora_neural_v2g3 import scene as SC                                 # noqa: E402
from cora_neural_v2g3 import search as S3                                # noqa: E402
from cora_neural_v2g3 import select as SEL                               # noqa: E402

TWO_RULE = F.P("(rule (test has_hole == #t) (delete)) (rule (test is_line == #t) (recolor (color 6)))")


def make(src, scene, seed, n_demos=3, n_tests=1):
    """A task from a program and a scene generator, as cora_neural_v2g2.families.make_task (test-local family)."""
    prog = G.parse(src)
    G.typecheck(prog)
    rng = np.random.default_rng(zlib.crc32(f"{src}|{seed}".encode()))
    pairs, tries = [], 0
    while len(pairs) < n_demos + n_tests and tries < 400:
        tries += 1
        g = scene(rng)
        if g is None:
            continue
        out = G.execute(prog, g)
        if out is None or (out.shape == g.shape and np.array_equal(out, g)):
            continue
        pairs.append((g.tolist(), out.tolist()))
    assert len(pairs) == n_demos + n_tests
    task = {"train": pairs[:n_demos], "test_inputs": [p[0] for p in pairs[n_demos:]]}
    return task, [np.asarray(p[1]) for p in pairs[n_demos:]]


# ------------------------------------------------------------------ scene
def test_fates_recolour_move_delete_unchanged():
    A = np.zeros((6, 6), dtype=int)
    A[0, 0:2] = 1
    A[2, 2] = 3
    A[4, 0] = 4
    A[5, 5] = 5
    B = np.zeros_like(A)
    B[0, 0:2] = 2                                      # recoloured 1 -> 2
    B[2, 4] = 3                                        # moved by (0, 2)
    B[5, 5] = 5                                        # unchanged; colour 4 deleted
    sc = SC.analyse([(A.tolist(), B.tolist())], "S1")
    by_colour = {int(A[next(iter(o.cells))]): o for o in sc.objects[0]}
    assert (by_colour[1].fate, by_colour[1].to_colour) == ("recoloured", 2)
    assert (by_colour[3].fate, by_colour[3].vector) == ("moved", (0, 2))
    assert by_colour[4].fate == "deleted" and by_colour[5].fate == "unchanged"
    assert ("recoloured", 2) in sc.groups and ("moved",) in sc.groups and ("deleted",) in sc.groups


def test_selections_come_from_native_execution():
    task, _ = make(F.P("(rule (test color == 2) (delete))"), lambda r: F.scene_dots(r, (2, 3)), 0)
    sel = SC.N("test", ("color", "==", 2))
    picks = SC.selections("S1", [sel], task["train"])[sel]
    for (a, _), p in zip(task["train"], picks):
        objs, _ = SC.native_objects(a, "S1")
        assert p == frozenset(j for j, o in enumerate(objs) if o.color == 2)


# ------------------------------------------------------------------ deltas and diagnostics
def test_identity_and_correct_program_deltas():
    task, _ = make(F.P("(rule (test color == 2) (recolor (color 4)))"), lambda r: F.scene_dots(r, (2, 3)), 1)
    ident = G.parse(F.P(""))
    ds = D.deltas(ident, task["train"])
    assert all(int(d.fixed.sum()) == 0 and int(d.broken.sum()) == 0 for d in ds)
    assert [int(d.remaining.sum()) for d in ds] == [int((np.asarray(a) != np.asarray(b)).sum()) for a, b in task["train"]]
    assert D.fits(D.deltas(G.parse(F.P("(rule (test color == 2) (recolor (color 4)))")), task["train"]), 3)


def test_mismatch_names_wrong_colours_and_objects():
    task, _ = make(F.P("(rule (test color == 2) (recolor (color 4)))"), lambda r: F.scene_dots(r, (2, 3)), 2)
    wrong = G.parse(F.P("(rule (test color == 2) (recolor (color 7)))"))
    rep = D.mismatch(wrong, task["train"], SC.analyse(task["train"], "S1"))
    assert all(r["shape_ok"] and r["wrong_colour"] == r["n_wrong"] > 0 for r in rep)
    assert all(set(r["expected_colours"]) == {4} and set(r["got_colours"]) == {7} for r in rep)
    assert all(r["objects"] and all(o["fate"] == "recoloured" for o in r["objects"]) for r in rep)


# ------------------------------------------------------------------ joint construction
@pytest.mark.parametrize("seed", [0, 1])
def test_joint_construction_reaches_a_two_rule_program(seed):
    task, (ans,) = make(TWO_RULE, F.scene_mixed, seed)
    g3 = S3.search(task, 1000)
    g2 = S3.search(task, 1000, use_joint=False)
    assert g3["first_fit_at"] is not None
    assert g2["first_fit_at"] is None or g3["first_fit_at"] < g2["first_fit_at"]
    assert any(np.array_equal(np.asarray(a), ans) for a in g3["attempts"])
    assert g3["origins"].get("joint", 0) > 0                   # constructed combinations were evaluated


def test_joint_off_is_the_ncv2_g2_agenda():
    task, _ = F.make_task("negated_selector_delete", 3)
    mine = S3.search(task, 3000, use_joint=False)
    theirs = S2.search(task, 3000)
    assert mine["programs"][:1] == theirs["programs"][:1] and mine["first_fit_at"] == theirs["first_fit_at"]


# ------------------------------------------------------------------ selection
def _cand(src, pred, at):
    return {"prog": G.parse(src), "preds": [np.asarray(pred)], "at": at, "origin": "test"}


def test_selection_prefers_a_supported_relational_rule_over_a_memorizing_table():
    A = [[[1, 0, 3], [0, 0, 0], [5, 0, 0]], [[1, 0, 3], [0, 0, 0], [0, 0, 0]], [[1, 0, 0], [0, 3, 0], [0, 0, 0]]]
    recol = {1: 2, 3: 4, 5: 6}                          # 1->2 and 3->4 seen in three demonstrations, 5->6 in one
    task = {"train": [(a, [[recol.get(v, v) for v in row] for row in a]) for a in A], "test_inputs": [A[0]]}
    table = _cand(F.P("(rule (true) (recolor (color_map (list (1 2) (3 4) (5 6)))))"), [[2]], 1)   # 5 seen once
    simple = _cand(F.P("(rule (test color == 1) (recolor (color 2)))"), [[3]], 40)
    assert SEL.literal_support(table["prog"], task["train"]) == pytest.approx(2 / 3)
    ranked, attempts = SEL.choose([table, simple], task)
    assert attempts[0] is not None and SEL.pred_key(attempts[0]["preds"]) == SEL.pred_key(simple["preds"])
    assert len(attempts) == 2 and SEL.pred_key(attempts[1]["preds"]) == SEL.pred_key(table["preds"])


def test_attempts_are_distinct_and_cover_every_test_input():
    task, answers = make(F.P("(rule (test color == 2) (recolor (color 4)))"), lambda r: F.scene_dots(r, (2, 3)), 4,
                         n_tests=2)
    r = S3.search(task, 600)
    assert len(r["attempts_by_test"]) == 2 and all(1 <= len(a) <= 2 for a in r["attempts_by_test"])
    assert r["attempts_by_test"][0][0] == r["attempts"][0]
    if len(r["attempts"]) == 2:
        assert r["attempts"][0] != r["attempts"][1]
    assert all(any(np.array_equal(np.asarray(g), ans) for g in a) for a, ans in zip(r["attempts_by_test"], answers))


def test_loo_stability_rederives_a_simple_rule():
    task, _ = F.make_task("negated_selector_delete", 5)
    r = S3.search(task, 400, select_cfg=SEL.SelectConfig(loo_budget=400))
    assert r["selection"] and r["selection"][0]["loo"] == pytest.approx(1.0)


# ------------------------------------------------------------------ determinism
def test_search_is_deterministic():
    task, _ = make(TWO_RULE, F.scene_mixed, 2)
    a, b = S3.search(task, 400), S3.search(task, 400)
    a.pop("cpu_s")
    b.pop("cpu_s")
    assert a == b
