"""CORA-FHR v1 tests (protocol section 8, step 8):
- deterministic enumeration;
- no cell literals;
- the extension form;
- operator recovery;
- the novelty classes (native and reach capabilities are not called novel);
- bridge restoration and extension removal;
- fold-locality;
- the tie abstention;
- solver blindness;
- the sealed final split.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_funnel import run as FR                                      # noqa: E402,F401  (sealed native flags)
from cora_fhr import ggrow as GG                                       # noqa: E402

S, T = GG.SOURCES.index, GG.TRANSFORMS.index


def _obj(cells, colour, shape, extra=()):
    G = np.zeros(shape, int)
    for p in cells:
        G[p] = colour
    for p, v in extra:
        G[p] = v
    return {p: colour for p in cells}, G


def test_enumeration_count_and_determinism():
    a = [GG.to_str(e) for e in GG.expressions()]
    b = [GG.to_str(e) for e in GG.expressions()]
    assert len(a) == 37750 == len(set(a)) and a == b
    assert sum(1 for e in a if e.startswith("d1|")) == 500 and sum(1 for e in a if e.startswith("d2|")) == 25000
    assert GG.grammar_identity() == GG.grammar_identity()


def test_no_cell_literals():
    allowed = {"shift", "ray", "reflect", "ring", "hull", "interior", "repeat", "unit", "size", "size_gap", "border",
               "obstacle", "N", "S", "E", "W", "NE", "NW", "SE", "SW", "H", "V", 4, 8}
    for t in GG.TRANSFORMS:
        assert set(t) <= allowed, t                     # every parameter is symbolic, from a finite domain


def test_extension_form():
    e = GG.make(("d2", S("self"), T(("reflect", "W")), T(("shift", "unit", "W"))))
    assert GG.load(GG.serialize(e)) == e and e["name"].startswith("fx_")
    bad = json.loads(GG.serialize(e))
    bad["expr"] = "d2|0|1|999"
    with pytest.raises(ValueError):
        GG.load(GG.canonical_json(bad))
    tampered = GG.serialize(e).replace(b"fx_", b"fy_")
    with pytest.raises(ValueError):
        GG.load(tampered)


@pytest.mark.parametrize("expr", [("d1", S("edge:S"), T(("ray", "S", "obstacle"))),
                                  ("d2", S("self"), T(("reflect", "E")), T(("shift", "unit", "E"))),
                                  ("u", S("part_minority"), *sorted((T(("ring", 8)), T(("hull",)))))])
def test_search_recovers_a_planted_operator(expr):
    insts = []
    for cells, shape in (({(2, 3), (3, 3), (3, 4)}, (11, 12)), ({(6, 7), (7, 7), (7, 8), (6, 8)}, (12, 12))):
        O, G = _obj(cells, 2, shape)
        O[sorted(O)[0]] = 5                             # a minority cell
        G[sorted(O)[0]] = 5
        insts.append((O, GG.evaluate(expr, GG.Ctx(O, G)), G))
    if not all(A for _O, A, _G in insts):
        pytest.skip("planted operator adds nothing on this toy")
    found, n, _tried = GG.search(insts)
    assert found is not None and n >= 1
    assert all(GG.evaluate(found, GG.Ctx(O, G)) == A for O, A, G in insts)


def test_native_and_reach_capabilities_are_not_novel():
    from cora_fhr import baseline as BL
    objs = [({(2, 3), (3, 3), (3, 4), (2, 5), (3, 5)}, (11, 11)), ({(6, 2), (7, 2), (7, 3)}, (11, 11))]

    def cls(expr):
        ins, cols = [], []
        for cells, shape in objs:
            O, G = _obj(cells, 2, shape)
            ins.append((O, GG.evaluate(expr, GG.Ctx(O, G)), G))
            cols.append(6)
        return BL.classify(ins, cols)["class"]
    assert cls(("d1", S("self"), T(("ring", 8)))) == "AVAILABLE_NATIVE"                 # native halo
    assert cls(("d1", S("edge:S"), T(("ray", "S", "border")))) == "AVAILABLE_NATIVE"    # native silhouette ray
    assert cls(("d2", S("self"), T(("hull",)), T(("ring", 8)))) == "AVAILABLE_REACH"     # reach bbox_ring


def test_bridge_restores_native_state_and_removal_is_clean():
    from cora_fhr import bridge as BR
    saved = BR.originals()
    e = GG.make(("d1", S("corners"), T(("ray", "NE", "obstacle"))))
    with BR.installed(e) as rec:
        assert e["name"] in BR.originals()[0] and not BR.restored()
        with pytest.raises(RuntimeError):
            with BR.installed(e):
                pass
    assert rec["restored"] and BR.restored(saved)
    with pytest.raises(KeyError):
        with BR.installed(e):
            raise KeyError("boom")
    assert BR.restored(saved) and all(a is b for a, b in zip(BR.originals(), saved))


def test_fold_locality(monkeypatch):
    """Each fold's construction sees only the remaining demonstrations, and the held-out pair's input only as an
    unlabelled input; its output reaches only the fold's exactness check."""
    from cora_fhr import measure as M
    train = [(np.full((3, 3), i), np.full((3, 3), 10 + i)) for i in range(3)]
    seen = []

    def fake_construct(arm, key, tr, inputs, dirs, donor_raw):
        seen.append(([int(a[0, 0]) for a, _b in tr], [int(b[0, 0]) for _a, b in tr], [int(x[0, 0]) for x in inputs]))
        return {"outcome": "NO_PROPOSAL"}, None
    monkeypatch.setattr(M, "construct_and_check", fake_construct)
    folds = M.loo("E", "k", train, None, {}, None)
    assert len(folds) == 3
    for i, (ins, outs, inputs) in enumerate(seen):
        assert i not in ins and 10 + i not in outs and inputs == [i]


def test_tie_abstention_detects_border_vs_obstacle():
    from cora_fhr import measure as M
    expr = ("d1", S("edge:S"), T(("ray", "S", "border")))
    groups = {"S1": []}
    for d, cells in enumerate(({(1, 2), (2, 2)}, {(2, 6), (2, 7)})):
        O, G = _obj(cells, 3, (10, 10))
        groups["S1"].append((O, GG.evaluate(expr, GG.Ctx(O, G)), G, d, 4))
    prop = {"view": "S1", "ext": GG.make(expr)}
    _O, test = _obj({(1, 4)}, 3, (10, 10), extra=(((7, 4), 9),))   # an obstacle below the object
    tie, n = M.ambiguous(prop, groups, [test])
    assert tie and n >= 2
    grows = test.copy()
    grows[2:, 4] = 4                                                # a prediction that grows the object
    assert M.ambiguous(prop, groups, [test], [grows])[0]
    still = test.copy()                                             # a prediction that grows nothing: no tie
    assert not M.ambiguous(prop, groups, [test], [still])[0]


def test_solver_view_and_corpus_are_blind_and_final_is_sealed(monkeypatch):
    from cora_fhr import corpus_c4 as C4
    task = {"family": "D1", "seed": 1, "truth": "x", "truth_pretty": "x", "train": [[[[0]], [[1]]]],
            "test": [[[[0]], [[7]]]]}
    v = C4.solver_view(task)
    assert set(v) == {"train", "test"} and all(set(p) == {"input"} for p in v["test"])
    assert "7" not in json.dumps(v)
    monkeypatch.delenv("CORA_FHR_FINAL_FREEZE", raising=False)
    with pytest.raises(SystemExit):
        C4.main(["final"])


def test_dev_corpus_hash_is_recorded():
    p = os.path.join(HERE, "outputs", "cora_fhr", "c4_dev.json")
    if not os.path.exists(p):
        pytest.skip("dev corpus not generated")
    assert hashlib.sha256(open(p, "rb").read()).hexdigest() == open(p + ".sha256").read().strip()


def test_amendment2_fold_semantics_are_scoped_to_folds(monkeypatch):
    """Ungated folds (proposed Amendment 2) switch native's gate off ONLY inside a fold run and restore it; the
    top-level gate is never touched; fold runs use the fold's own engine directory; fold records carry no
    certificate field."""
    from cora_fhr import measure as M
    monkeypatch.setattr(M, "FOLD_GATE", "ungated")
    monkeypatch.delenv("OBJECT_GATE_OFF", raising=False)
    seen = []

    def fake_object_run(task_id, train, tests, engine_dir, ext=None, budget_s=90.0):
        seen.append((task_id, engine_dir, os.environ.get("OBJECT_GATE_OFF")))
        return {"accepted": True, "uses": True, "predictions": [np.asarray(tests[0]).tolist()], "cpu_s": 0.0,
                "restored": True}, None

    def fake_construct(arm, key, tr, inputs, dirs, donor_raw):
        return {"selected": {}, "_sel": None, "_groups": None}, {"name": "fx_test"}
    monkeypatch.setattr(M, "object_run", fake_object_run)
    monkeypatch.setattr(M, "construct_and_check", fake_construct)
    monkeypatch.setattr(M, "tie_check", lambda rec, inputs, preds: False)
    train = [(np.full((3, 3), i), np.full((3, 3), i)) for i in range(3)]
    folds = M.loo("E", "k", train, None, {"loo": "/fold_dir"}, None)
    assert all(g == "1" and d == "/fold_dir" for _t, d, g in seen) and len(seen) == 3
    assert os.environ.get("OBJECT_GATE_OFF") is None                    # restored after every fold
    assert all("certified_by" not in f and f["fold_gate"] == "ungated" for f in folds)
    monkeypatch.setattr(M, "FOLD_GATE", "native")
    seen.clear()
    M.loo("E", "k", train, None, {"loo": "/fold_dir"}, None)
    assert all(g is None for _t, _d, g in seen)                          # frozen semantics: native's gate stays on


def test_d3_planted_union_collapses_to_the_constructed_operator():
    """D3's hull branch is vacuous on every object the generator makes (exactly one minority cell; the hull of
    one cell is that occupied cell, which finalize removes), so the planted union equals ring8[part_minority].
    With two minority cells whose bounding box holds a free cell outside their 8-ring, the two differ: the
    equivalence is a property of the D3 generator, not of the operators."""
    from cora_fhr import corpus_c4 as C4
    truth = C4.family_expr("D3", np.random.default_rng(0))
    learned = ("d1", GG.SOURCES.index("part_minority"), GG.TRANSFORMS.index(("ring", 8)))
    rng = np.random.default_rng(424242)
    n = 0
    for _ in range(300):
        H, W = (int(v) for v in rng.integers(10, 15, size=2))
        cols = tuple(int(v) for v in rng.choice(np.arange(1, 10), 4, replace=False))
        dm = C4._demo(rng, "D3", truth, cols, H, W, distractor=bool(rng.random() < 0.5))
        if dm is None:
            continue
        for o, a in dm[2]:
            x = GG.Ctx(o, dm[0])
            assert len(GG.source("part_minority", x)) == 1
            assert GG.evaluate(learned, x) == set(a) == GG.evaluate(truth, x)
            n += 1
    assert n >= 100
    O = {(2, 2): 5, (2, 3): 3, (2, 4): 3, (3, 4): 3, (4, 4): 5}         # minority 5 at (2,2) and (4,4)
    G = np.zeros((9, 9), int)
    for p, v in O.items():
        G[p] = v
    x = GG.Ctx(O, G)
    assert GG.evaluate(truth, x) - GG.evaluate(learned, x) == {(4, 2)}   # hull adds a free cell ring8 misses
