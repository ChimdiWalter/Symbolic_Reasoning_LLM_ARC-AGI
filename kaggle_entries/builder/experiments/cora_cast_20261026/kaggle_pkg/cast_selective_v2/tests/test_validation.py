"""Required validation tests (CAST reliability directive, section 2) and deployment semantics for cast_selective_v2.
Passing them does not prove generalisation; they check that the validation procedure flags uncertainty."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cast_selective_v2 import evaluate, insert_attempt2  # noqa: E402


def T(pairs, queries):
    return {"train": [{"input": a, "output": b} for a, b in pairs], "test": [{"input": q} for q in queries]}


def rot270(x):
    return np.rot90(np.asarray(x), 3).tolist()


def _memoriser_module(task, reverse=False):
    """Injected test module: a memorising hypothesis (reproduces every demonstration; on an unseen input it returns
    the first demonstration's output), given three agreeing members so it ranks first, and the true rule
    (add 1 to every colour) as a single member."""
    demos = [(np.asarray(x), np.asarray(y)) for x, y in task["train"]]
    qs = [np.asarray(q) for q in task["test_inputs"]]

    def memo(q):
        for x, y in demos:
            if x.shape == q.shape and np.array_equal(x, q):
                return y
        return demos[0][1]
    mem = [memo(q) for q in qs]
    true = [q + 1 for q in qs]
    fits = [{"program": f"memorise#{k}", "preds": mem, "complete": [True] * len(qs), "cost": 1.0, "order": k}
            for k in range(3)]
    if all(np.array_equal(x + 1, y) for x, y in demos):
        fits.append({"program": "add_one", "preds": true, "complete": [True] * len(qs), "cost": 1.0, "order": 3})
    return fits


def test_fits_every_example_but_a_fold_mispredicts_the_held_out_pair(monkeypatch):
    from cast_selective_v2 import api
    monkeypatch.setitem(api.MODULES, "memo", _memoriser_module)
    monkeypatch.setattr(api, "ORDER", ("memo",))
    pairs = [([[c, 0], [0, c]], [[c + 1, 1], [1, c + 1]]) for c in (1, 2, 3)]
    rep = evaluate(T(pairs, [[[4, 0], [0, 4]]]))
    ev = rep["modules"]["memo"]
    assert ev["status"] == "EVIDENCE" and ev["v1_loo"] and not ev["genuine_loo"]   # v1's top-2 rule is fooled
    q = rep["queries"][0]
    assert q["accepted"]["B1"] is not None and q["accepted"]["B2"] is None and q["accepted"]["B3"] is None
    assert rep["union_disagreement"][0]                         # the two fitting hypotheses disagree on the query


def test_two_fitting_programs_disagree_on_the_query():
    pairs = [([[c, 0], [0, 0]], [[0, c], [0, 0]]) for c in (1, 2, 3)]
    rep = evaluate(T(pairs, [[[1, 2], [0, 0]]]))
    ev = rep["modules"]["l0"]
    assert ev["query_disagreement"][0]
    assert rep["queries"][0]["accepted"]["B3"] is None


def _scene(objs, h=9, w=9, bg=0):
    g = np.full((h, w), bg)
    for r, c, v in objs:
        g[r, c] = v
    return g


def test_validity_depends_on_the_object_representation():
    pairs = []
    for k in range(3):
        x = _scene([(1, 1, 2), (1, 2, 2), (2, 1, 2), (2, 2, 2), (5, 5 + k % 2, 3), (6, 5 + k % 2, 3), (7, 1 + k, 4)])
        y = x.copy()
        y[7, 1 + k] = 0                                       # delete the smallest object
        pairs.append((x.tolist(), y.tolist()))
    q = _scene([(1, 1, 2), (1, 2, 2), (2, 1, 2), (2, 2, 2), (5, 5, 4), (6, 6, 4), (8, 1, 4)])   # a diagonal pair
    rep = evaluate(T(pairs, [q.tolist()]))
    ev = rep["modules"]["m2"]
    assert ev["status"] == "EVIDENCE" and ev["query_disagreement"][0]
    assert rep["queries"][0]["accepted"]["B3"] is None


def _crop_task(bg, n_q=1):
    rng = np.random.default_rng(5)
    pairs = []
    for _ in range(3 + n_q):
        x = np.full((10, 10), bg)
        r, c, h, w = int(rng.integers(0, 6)), int(rng.integers(0, 6)), int(rng.integers(2, 4)), int(rng.integers(2, 5))
        x[r:r + h, c:c + w] = rng.integers(1, 7, size=(h, w))
        x[r, c] = 3 if bg != 3 else 2
        ys, xs = np.nonzero(x != bg)
        pairs.append((x.tolist(), x[ys.min():ys.max() + 1, xs.min():xs.max() + 1].tolist()))
    return pairs[:3], pairs[3:]


def test_rule_changes_output_dimensions_on_a_nonzero_background_with_two_queries():
    demos, held = _crop_task(bg=7, n_q=2)
    task = T(demos, [x for x, _ in held])
    rep = evaluate(task)
    assert rep["status"] == "OK" and len(rep["queries"]) == 2
    for q, (x, y) in zip(rep["queries"], held):
        assert q["accepted"]["B3"] == y and np.asarray(y).shape != np.asarray(x).shape
    neural = [[x, x] for x, _ in held]                        # duplicated neural attempts: tier 0 may fill attempt 2
    out = insert_attempt2(task, neural, "tier0", report=rep)
    assert [o[0] for o in out] == [x for x, _ in held] and [o[1] for o in out] == [y for _, y in held]


def test_spurious_feature_is_flagged_by_query_disagreement():
    pairs = []
    for k in range(3):                                         # every size-2 object is colour 3 in the demonstrations
        x = _scene([(1, 1 + k, 3), (1, 2 + k, 3), (5, 5, 6), (5, 6, 6), (6, 5, 6), (7, 1, 8)])
        y = x.copy()
        y[1, 1 + k] = y[1, 2 + k] = 5
        pairs.append((x.tolist(), y.tolist()))
    q = _scene([(1, 1, 3), (1, 2, 3), (1, 3, 3), (5, 5, 6), (5, 6, 6)])     # colour-3 object of size 3, size-2 colour 6
    rep = evaluate(T(pairs, [q.tolist()]))
    ev = rep["modules"]["m2"]
    assert ev["status"] == "EVIDENCE" and ev["query_disagreement"][0]
    assert rep["queries"][0]["accepted"]["B3"] is None


def test_timeout_inside_one_fold_abstains_and_keeps_neural_attempts():
    demos, held = _crop_task(bg=0)
    task = T(demos, [held[0][0]])
    rep = evaluate(task, fold_cpu_s=1e-5)
    assert rep["status"] == "TIMEOUT_IN_FOLD" and rep["queries"][0]["candidate"] is None
    neural = [[held[0][0], held[0][0]]]
    assert insert_attempt2(task, neural, "tier0", report=rep) == neural


def test_insufficient_validation_evidence_with_one_demonstration():
    rep = evaluate(T([([[1, 0], [0, 0]], [[0, 1], [0, 0]])], [[[2, 0], [0, 0]]]))
    assert any(m["status"] == "INSUFFICIENT_VALIDATION_EVIDENCE" for m in rep["modules"].values())
    assert all(rep["queries"][0]["accepted"][p] is None for p in ("B1", "B2", "B3"))


def test_attempt1_never_changes_and_tier0_only_fills_duplicates():
    demos, held = _crop_task(bg=0)
    task = T(demos, [held[0][0]])
    rep = evaluate(task)
    other = [[9]]
    out = insert_attempt2(task, [[held[0][0], other]], "tier0", report=rep)
    assert out == [[held[0][0], other]]                       # distinct neural attempts: tier 0 changes nothing
    out = insert_attempt2(task, [[other, other]], "tier1:B3", report=rep)
    assert out[0][0] == other and out[0][1] == held[0][1]
    assert insert_attempt2(task, [[other, other]], "bogus", report=rep) == [[other, other]]
