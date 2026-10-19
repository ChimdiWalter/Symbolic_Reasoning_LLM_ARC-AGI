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


def test_revision_controller_reads_only_observables_and_types():
    """Leakage: answer-like fields cannot change a decision. Type validity: every action is declared.
    Null case: a certified native run yields NONE. Engine errors are never reasoning actions."""
    from cora_fhr import revision_controller as RC
    base = {"native_accepted": False, "native_failure_stage": "matching", "native_error": False, "native_timeout": None,
            "evidence_views": {"S3": 4}, "evidence_cap": None, "proposal_outcome": "NO_PROPOSAL",
            "diag_support_ok": True, "diag_joint_fit": None, "diag_singly_expressible": True}
    leaky = dict(base, answer=[[1]], evaluator_only_funnel_category="FIT_BUT_ALL_WRONG", family="M3", truth="x")
    assert RC.decide(base) == RC.decide(leaky)
    assert RC.decide(base)["action"] == "CONSTRUCT_WITH_GUARD" and not RC.decide(base)["available"]
    assert RC.decide(dict(base, native_accepted=True))["action"] == "NONE"
    assert RC.decide(dict(base, native_error=True))["action"] == "ENGINE_ERROR"
    row = {"key": "t", "arms": {"A": {"run": {"accepted": False, "error": "hard_cap", "timeout": True, "failure_stage": None}},
                                "E": {"evidence": {"views": {}, "why_empty": None}, "outcome": "NO_PROPOSAL"}}}
    assert RC.decide(RC.state_from(row))["action"] == "RETRY_SEARCH"          # a resource cap is not an engine error
    assert RC.decide(dict(base, diag_support_ok=False))["action"] == "ABSTAIN_OR_REQUEST_EVIDENCE"
    for st in (base, dict(base, evidence_views={}), dict(base, evidence_views={}, native_failure_stage="loo"),
               dict(base, evidence_cap="extract_cap"), dict(base, diag_singly_expressible=False)):
        assert RC.decide(st)["action"] in RC.ACTIONS


def test_guarded_extension_form_search_and_restore():
    """Guard probe: the guarded format round-trips byte-exactly, is a separate format with v1 unchanged,
    reads only the object and scene, is found exactly when one guard splits a view into two jointly expressible
    groups, and installs and restores like v1."""
    from cora_fhr import bridge as BR
    from cora_fhr import ggrow_guard as GU
    ring, ray = ("d1", S("self"), T(("ring", 8))), ("d1", S("self"), T(("ray", "N", "border")))
    g = {"guard": ("colours", "eq", (1,)), "then": ring, "else": ray}
    ext = GU.make(g)
    assert ext["name"].startswith("fg_") and ext["format"] != GG.FORMAT
    assert GG.serialize(GG.load(GG.serialize(ext))) == GG.serialize(ext)
    assert sum(1 for _ in GG.expressions()) == 37750                  # v1 grammar untouched
    inst = []
    for k, (r, c, col) in enumerate([(3, 3, 1), (3, 9, 2), (8, 4, 1), (9, 10, 2)]):
        Gr = np.zeros((14, 14), int)
        O = {(r, c): col, (r, c + 1): col}
        for p, v in O.items():
            Gr[p] = v
        x = GG.Ctx(O, Gr)
        inst.append((O, GU.evaluate(g, x), Gr))
        assert GG.render(ext, O, Gr) == GU.evaluate(g, x)
    assert GG.search(inst)[0] is None                                   # no single v1 expression fits both kinds
    found = GU.search(inst)
    assert found and found[0]["guard"][0] in GU.FEATURES
    assert all(GU.evaluate({"guard": found[0]["guard"], "then": found[0]["then"], "else": found[0]["else"]},
                           GG.Ctx(O, Gr)) == set(A) for O, A, Gr in inst)
    saved = BR.originals()
    with BR.installed(ext) as rec:
        assert ext["name"] in BR.originals()[0]
    assert rec["restored"] and BR.restored(saved)


def test_contrast_arm_null_branch_and_separating_guard():
    """Contrast arm EGC: a null else branch adds nothing. The guard is learned from native's own
    memorized/explained labels (observable) and separates them; the then-branch fits the memorized objects only."""
    from cora_fhr import construct as CS
    from cora_fhr import ggrow_guard as GU
    ring_min = ("d1", S("part_minority"), T(("ring", 8)))
    halo = ("d1", S("self"), T(("ring", 8)))
    g = {"guard": ("n_colours", "eq", 2), "then": ring_min, "else": None}
    ext = GU.make(g)
    assert GG.serialize(GG.load(GG.serialize(ext))) == GG.serialize(ext) and "nothing" in GU.pretty(g)
    groups = {"S3": []}
    for d, (r, c, two) in enumerate([(2, 2, True), (2, 8, False), (8, 2, True), (8, 8, False), (5, 5, True), (11, 11, False)]):
        Gr = np.zeros((14, 14), int)
        O = {(r, c): 4, (r, c + 1): 7 if two else 4, (r + 1, c): 4}
        for p, v in O.items():
            Gr[p] = v
        x = GG.Ctx(O, Gr)
        A = GG.evaluate(ring_min if two else halo, x)
        groups["S3"].append((O, A, Gr, d % 3, 5, two))                # memorized = the two-colour kind
    assert GU.evaluate(g, GG.Ctx(groups["S3"][1][0], groups["S3"][1][2])) == set()
    prop = CS.propose_contrast(groups, classify=False)["proposals"]
    assert prop and prop[0]["guarded"] and prop[0]["negatives"] == 3
    best = GU.from_str(prop[0]["ext"]["expr"])
    for O, A, Gr, _d, _c, mem in groups["S3"]:
        got = GU.evaluate(best, GG.Ctx(O, Gr))
        assert got == (set(A) if mem else set())


def test_v2_scene_reasoner_geometry_colour_and_ambiguity():
    """Reasoning v2: provenance geometry reproduces G-grow positions exactly; ORIGIN colouring (colour of the
    source cell) is found where no single-colour policy fits; the version space flags genuinely
    disagreeing hypotheses; only training pairs and test inputs are read."""
    import random
    from cora_revision_v2 import scene_reasoner as SR
    rng = random.Random(7)
    exprs = list(GG.expressions())
    for _ in range(300):
        Gr = np.zeros((12, 12), int)
        r, c = rng.randrange(2, 9), rng.randrange(2, 9)
        O = {(r, c): rng.randrange(1, 10), (r, c + 1): rng.randrange(1, 10), (r + 1, c): rng.randrange(1, 10)}
        for p, v in O.items():
            Gr[p] = v
        x = GG.Ctx(O, Gr)
        e = exprs[rng.randrange(len(exprs))]
        assert set(SR.geometry_prov(e, x)) == GG.evaluate(e, x)
    a1 = [[0] * 5, [0, 3, 0, 0, 0], [0] * 5, [0] * 5, [0] * 5]
    b1 = [[0] * 5, [0, 3, 3, 3, 3], [0] * 5, [0] * 5, [0] * 5]
    a2 = [[0] * 5, [0] * 5, [6, 0, 0, 0, 0], [0] * 5, [0] * 5]
    b2 = [[0] * 5, [0] * 5, [6, 6, 6, 6, 6], [0] * 5, [0] * 5]
    rec = SR.reason([(a1, b1), (a2, b2)], [[[0] * 5, [0] * 5, [0] * 5, [0, 0, 9, 0, 0], [0] * 5]])
    assert rec["n_hypotheses"] > 0 and rec.get("attempts")
    assert any(h_pol in ("ORIGIN", "OBJ_MAJ", "NEAREST") for h_pol in [rec["top"]["policy"]])   # colour from the object, not a constant
    assert any(p == [[0] * 5, [0] * 5, [0] * 5, [0, 0, 9, 9, 9], [0] * 5] for p in rec["attempts"][0])


def test_v2_fold_detail_and_diagnosis_tiers():
    """Reasoning v2 diagnosis: a fold that fails only because the held-out demonstration needs a table entry no other
    demonstration shows is UNSEEN_TABLE_KEY (evidence), reported with its test relevance and per-entry support; it
    leads to an EXPLORATORY (uncertified) attempt, while a fold that rebuilds a different unique answer is
    DISCOURAGED. Non-additive demonstrations route to the typed scene transformation. No answer is read."""
    from cora_revision_v2 import scene_reasoner as SR
    from cora_revision_v2 import diagnosis as DG
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    A = np.zeros((7, 7), int)
    A[1, 1] = 5
    A[4, 1] = A[4, 2] = 5
    A2 = np.zeros((7, 7), int)
    A2[2, 3] = 5
    objs = [GG.Ctx(o, A) for o in SR._objects(A.tolist(), V("S1"))]
    expr = next(e for e in GG.expressions() if all(SR.geometry_prov(e, x) for x in objs))
    h = {"view": "S1", "expr": expr, "policy": "TABLE:size", "table": {1: 2}, "const": None}
    assert SR._required_keys(h, A.tolist()) == {1, 2}
    det = SR._fold_detail([h], 1, [], False, (A.tolist(), A.tolist()), [A.tolist()])
    assert det["outcome"] == "UNPREDICTABLE" and det["cause"] == "UNSEEN_TABLE_KEY"
    assert det["missing_keys"] == ["2"] and det["test_needs_missing_key"]
    assert SR.table_support(h, [(A.tolist(), A.tolist()), (A2.tolist(), A2.tolist())], [A.tolist()]) == {"1": 2, "2": 1}
    rec = {"diagnosis": "FOLD_FRAGILITY", "attempts": [[A.tolist()]], "fold_detail": [det, {"outcome": "SUCCESS"}],
           "test_table_support": {"1": 2, "2": 1}}
    tr = [(A.tolist(), A.tolist()), (A2.tolist(), A2.tolist())]
    d = DG.diagnose(tr, [A.tolist()], rec)
    assert [x["label"] for x in d] == ["FOLD_FRAGILITY"] and d[0]["next_action"] == "EXPLORATORY_ATTEMPT"
    assert DG.decision(rec, d)["tier"] == "EXPLORATORY"
    rec["fold_detail"] = [{"outcome": "WRONG_UNIQUE"}, {"outcome": "SUCCESS"}]
    assert DG.decision(rec, DG.diagnose(tr, [A.tolist()], rec))["tier"] == "DISCOURAGED"
    B = A.copy()
    B[1, 1] = 3                                                       # a recolour: outside the additive class
    g = DG.diagnose([(A.tolist(), B.tolist())], [A.tolist()], {"diagnosis": "NO_CONSISTENT_HYPOTHESIS:GEOMETRY_GAP"})
    assert g[0]["next_action"] == "TYPED_SCENE_TRANSFORM" and "recolour" in g[0]["supports"]
    import inspect
    assert "answer" not in inspect.signature(DG.diagnose).parameters


def test_v2_selection_family_guards_which_objects_act():
    """Typed scene transformation, first slice: a feature guard selects which objects a geometry acts on. The
    unguarded class cannot fit a task where only colour-1 objects grow; the selection family fits it, predicts the
    test, and the per-demonstration probe reports a selective fit. Only training pairs and test inputs are read."""
    from cora_revision_v2 import scene_reasoner as SR
    from cora_revision_v2 import selection as SEL
    from geocat_arc.object_reasoning.types import SegmentationVariant as V

    def mk(objs, H=8, W=10):
        A = np.zeros((H, W), int)
        for (r, c), v in objs:
            A[r, c] = v
        B = A.copy()
        for (r, c), v in objs:
            if v == 1:
                B[r, c + 1:] = np.where(B[r, c + 1:] == 0, v, B[r, c + 1:])
        return A.tolist(), B.tolist()
    train = [mk([((1, 2), 1), ((4, 5), 2), ((6, 1), 1)]), mk([((2, 4), 2), ((5, 3), 1)])]
    test_in, test_out = mk([((0, 1), 1), ((3, 6), 2), ((7, 2), 1)])
    assert SEL.demo_fits_selectively(train[0], V("S1"))
    base = SR.reason(train, [test_in])
    assert base["diagnosis"].startswith("NO_CONSISTENT_HYPOTHESIS") or test_out not in base["attempts"][0]
    rec = SR.reason(train, [test_in], families=("grow", "select"))
    assert rec["n_selective"] > 0 and rec["attempts"] and rec["attempts"][0][0] == test_out
    assert rec["n_hypotheses"] > base.get("n_hypotheses", 0)
    # the union can create disagreement: a base-family hypothesis that fits the demonstrations may predict differently,
    # which is why a revision family is applied where the diagnosis asks for it, not everywhere
    assert rec["diagnosis"] in ("MANY_CONSISTENT_DISAGREE", "FOLD_FRAGILITY", "CERTIFIED")


def test_v2_typed_scene_transformation_two_stage_decision_list():
    """Typed scene transformation, slice 2: stage 1 keeps, deletes or recolours whole objects by an ordered decision
    list with a default action (a value no rule names takes the default, so unseen colours do not block a
    prediction), and stage 2 is v2's growth on the stage-1 result. Here stage 2 is the identity."""
    from cora_revision_v2 import tst as T

    def mk(objs, H=8, W=8):
        A = np.zeros((H, W), int)
        B = np.zeros((H, W), int)
        for cells, v in objs:
            for c in cells:
                A[c] = v
        sizes = [len(c) for c, v in objs]
        for cells, v in objs:
            nv = 0 if v == 3 else (1 if len(cells) == max(sizes) else v)
            for c in cells:
                B[c] = nv
        return A.tolist(), B.tolist()
    train = [mk([([(0, 0), (0, 1), (0, 2)], 5), ([(3, 3)], 3), ([(6, 1), (6, 2)], 5)]),
             mk([([(1, 1), (2, 1), (3, 1), (4, 1)], 4), ([(5, 5), (5, 6)], 3), ([(7, 7)], 4)]),
             mk([([(2, 2), (2, 3)], 6), ([(0, 6)], 3), ([(5, 0), (5, 1), (5, 2)], 6)])]
    hyps, info = T.version_space(train)
    assert info["stage2"] == "identity" and hyps
    ti, to = mk([([(1, 4), (2, 4), (3, 4)], 2), ([(6, 6)], 3), ([(7, 0), (7, 1)], 2)])   # colour 2 never seen
    preds = {str(p) for p in (T.predict(h, ti) for h in hyps) if p is not None}
    assert preds == {str(to)}
    assert all(h["rule"]["feature"] == "decision_list" for h in hyps if T.predict(h, ti) is not None)
    assert T.version_space([(train[0][0], train[0][0])])[0] == []                       # no change: not this family
