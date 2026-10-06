"""Item-2 v1.8 no-oracle proposer: tests (directive section 12).

Fixtures are the v1.7 development tasks (seed range 810,000,000), which the
proposer never saw during design. Engine tests are marked `engine`.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
from test_v17_compiler import fixture                             # noqa: E402

TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
M, MI = X._meta()


def task(i):
    schema, train, held = fixture(i)
    return schema, train, held


def proposal_set(inp, depth=2):
    return [p["canonical"] for p in P.propose(inp, depth)["proposals"]]


# 1. deterministic candidate generation
def test_generation_and_selection_are_deterministic():
    _, train, _ = task(1)
    a, b = P.build_input(train), P.build_input(train)
    assert X.canonical_json(a) == X.canonical_json(b)
    assert proposal_set(a) == proposal_set(b)
    r1, r2 = P.solve(train), P.solve(train)
    assert r1["selected"]["canonical"] == r2["selected"]["canonical"]
    assert r1["input_sha256"] == r2["input_sha256"] and r1["selection"] == r2["selection"]


# 2. no task-ID dependence: there is no task channel at all
def test_no_task_channel():
    import inspect
    _, train, _ = task(0)
    assert "task" not in " ".join(inspect.signature(P.solve).parameters)
    inp = P.build_input(train)
    assert "task" not in json.dumps(inp).lower()
    bad = dict(inp, task_id="t1")
    with pytest.raises(P.LeakageError):
        P.scan_input(bad)


# 3. demonstration-order invariance
def test_demonstration_order_invariance():
    _, train, _ = task(1)
    rev = list(reversed(train))
    assert sorted(proposal_set(P.build_input(train))) == sorted(proposal_set(P.build_input(rev)))
    assert P.solve(train)["selected"]["canonical"] == P.solve(rev)["selected"]["canonical"]


# 4. frontier perturbation changes proposals only through declared semantics
def test_frontier_perturbation_acts_only_through_declared_semantics():
    _, train, _ = task(1)
    inp = P.build_input(train)
    base = P.propose(inp, 2)["proposals"]
    recoded = copy.deepcopy(inp)
    for row in recoded["failure"]["frontier"]:
        if row["status"] == "CONFLICT":
            row["code"] = "scoped_fit_failed"
    assert [p["canonical"] for p in P.propose(recoded, 2)["proposals"]] == [p["canonical"] for p in base]
    top = base[0]["layers"][-1]
    demoted = copy.deepcopy(inp)
    demoted["failure"]["frontier"][top] = {"k": top, "status": "CONFLICT", "code": "slot_nonfunctional"}
    after = [p["canonical"] for p in P.propose(demoted, 2)["proposals"]]
    assert after == [p["canonical"] for p in base if p["layers"][-1] != top]


# 5. the target is absent from the proposer input
def test_target_absent_from_input_and_scanner_refuses_forbidden_content():
    schema, train, _ = task(0)
    inp = P.build_input(train)
    text = json.dumps(inp)
    assert P.canonical(schema) not in text and json.dumps(M.ast_to_json(schema)) not in text
    for key in ("target_schema", "seed", "family", "truth", "held_out", "solution"):
        with pytest.raises(P.LeakageError):
            P.scan_input(dict(inp, **{key: 1}))
    poisoned = copy.deepcopy(inp)
    poisoned["failure"]["frontier"][0]["code"] = "?0"
    with pytest.raises(P.LeakageError):
        P.scan_input(poisoned)
    nested = copy.deepcopy(inp)
    nested["failure"]["frontier"][5]["target"] = 1
    with pytest.raises(P.LeakageError):
        P.scan_input(nested)
    bad_grid = copy.deepcopy(inp)
    bad_grid["demonstrations"][0]["input"][0][0] = 11
    with pytest.raises(P.LeakageError):
        P.scan_input(bad_grid)
    for field, value in (("kstar_identity", "0" * 64), ("limits", {}), ("grammar", {})):
        with pytest.raises(P.LeakageError):
            P.scan_input(dict(inp, **{field: value}))


# 6. hidden output inaccessible: the held-out pair never reaches the proposer
def test_heldout_output_cannot_reach_the_proposer(monkeypatch):
    """(erratum 01, review minor 10) In real leave-one-out, fold i's proposer
    input does not change when demonstration i's output is replaced."""
    import numpy as np
    _, train, _ = task(0)
    calls = []
    _stub_engine(monkeypatch, calls)
    base = P.real_loo(train)
    for i in (0, 3):
        mutated = list(train)
        mutated[i] = (train[i][0], np.where(train[i][1] == 0, 1, 0))
        loo = P.real_loo(mutated)
        assert loo["folds"][i]["input_sha256"] == base["folds"][i]["input_sha256"]
        assert loo["folds"][i]["selected"] == base["folds"][i]["selected"]
        others = [f["input_sha256"] for k, f in enumerate(loo["folds"]) if k != i]
        assert others != [f["input_sha256"] for k, f in enumerate(base["folds"]) if k != i]


# 7. no persistent state
def test_no_persistent_state():
    from cora_arc2026 import v14_loc as L
    _, train, _ = task(1)

    def module_values():
        return {k: repr(v) for k, v in vars(P).items()
                if not callable(v) and not k.startswith("__") and type(v).__name__ != "module"
                and k != "_D_CACHE"}
    before = module_values()
    r1 = P.solve(train)
    L.clear_engine_caches()
    r2 = P.solve(train)
    assert module_values() == before
    assert r1["selected"]["canonical"] == r2["selected"]["canonical"]
    assert r1["selection"] == r2["selection"]


# 8. duplicate elimination
def test_duplicates_are_eliminated():
    _, train, _ = task(1)
    sem = P.Semantics(train)
    inp = P.build_input(train, sem)
    props = P.propose(inp, 2, sem)["proposals"]
    canon = [p["canonical"] for p in props]
    assert len(canon) == len(set(canon))
    assert all(len(set(p["layers"])) == len(p["layers"]) for p in props)
    verified = P.verify(props, sem)
    reps = P.dedupe(verified)
    assert len({c["fingerprint"] for c in reps}) == len(reps) <= len(verified)
    assert {P.behaviour(c["fitted"]) for c in verified} == {c["fingerprint"] for c in reps}


# the witness set: task-distribution grids on a reserved seed range
def test_witness_grids_are_fixed_and_separate_layers_the_probes_miss():
    import numpy as np
    g1, g2 = P.witness_grids(), P.witness_grids()
    assert len(g1) == P.WITNESS_GRIDS and all(np.array_equal(a, b) for a, b in zip(g1, g2))
    _, train, _ = task(0)
    rec = P.solve(train)
    fitted = rec["selected_fitted"]
    top = ("Compose", fitted[1][len(fitted[1]) // 2:])
    assert P.behaviour(fitted) != P.behaviour(top)


# 9. compiler compatibility
def test_every_proposal_types_and_the_selection_compiles():
    _, train, _ = task(1)
    inp = P.build_input(train)
    for depth in (2, 3):
        for p in P.propose(inp, depth)["proposals"]:
            X.type_check(p["schema"])
    rec = P.solve(train)
    prod = P.compile_selected(rec)
    assert X.load(X.serialize(prod)) == prod
    assert prod["blocks"] == len(rec["selected"]["layers"])


# 10. maximum-candidate enforcement
def test_candidate_cap_is_enforced(monkeypatch):
    _, train, _ = task(1)
    monkeypatch.setitem(P.LIMITS, "max_proposals", 3)
    inp = P.build_input(train)
    out = P.propose(inp, 2)
    assert len(out["proposals"]) == 3 and out["capped"]
    demo = P.propose_demo_only(P.Semantics(train), 2)
    assert len(demo["proposals"]) == 3 and demo["capped"]


# 11. fresh-process reproduction
def test_fresh_process_reproduces_the_selection():
    _, train, _ = task(1)
    want = P.solve(train)
    code = ("import sys, json; sys.path.insert(0, %r); sys.path.insert(0, %r); "
            "from cora_arc2026 import v18_proposer as P; from test_v17_compiler import fixture; "
            "s, t, h = fixture(1); r = P.solve(t); "
            "print(json.dumps([r['selected']['canonical'], r['input_sha256'], r['selection']]))"
            % (HERE, os.path.join(HERE, "tests")))
    env = dict(os.environ, PYTHONPATH=TTI, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                         timeout=900)
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got == [want["selected"]["canonical"], want["input_sha256"], want["selection"]]


def _stub_engine(monkeypatch, calls):
    def fake_run(pairs, prods=(), *a, **k):
        calls.append([p[0].tolist() for p in pairs])
        return {"accepted": False, "program": None, "apply_fn": None, "seconds": 0.0,
                "engine_dir_removed": True, "events": []}
    monkeypatch.setattr(X, "run_reasoner", fake_run)


# 12. fold-level proposal isolation
def test_each_fold_proposes_from_its_own_demonstrations_only(monkeypatch):
    _, train, _ = task(0)
    seen, calls = [], []
    real_solve = P.solve

    def spy(demos, arm="FAILURE_CONDITIONED", **kw):
        seen.append([d[0].tolist() for d in demos])
        return real_solve(demos, arm, **kw)
    monkeypatch.setattr(P, "solve", spy)
    _stub_engine(monkeypatch, calls)
    loo = P.real_loo(train)
    assert len(seen) == len(train) == len(loo["folds"])
    for i, demos in enumerate(seen):
        assert demos == [train[j][0].tolist() for j in range(len(train)) if j != i]
    assert len({f["input_sha256"] for f in loo["folds"]}) == len(train)
    assert all(f["class"] == "LOO_FAILURE" for f in loo["folds"] if f["proposer_class"] == "SELECTED")


# 13. the full-data proposal cannot leak into a fold
def test_full_data_proposal_cannot_leak_into_folds(monkeypatch):
    _, train, _ = task(0)
    calls = []
    _stub_engine(monkeypatch, calls)
    fresh = P.real_loo(train)
    P.solve(train)
    after = P.real_loo(train)
    key = lambda loo: [(f["input_sha256"], f["selected"], f["selection"]) for f in loo["folds"]]  # noqa: E731
    assert key(fresh) == key(after)


# 14. a replaced failure frontier destroys the failure-specific proposals
def test_controls_keep_the_mechanism_and_differ_only_in_the_tops():
    """(erratum 01, review B1) The G1 controls use the main arm's peeling rule,
    caps and selection; only the choice of top layers differs. They are not
    zero by construction."""
    _, train0, _ = task(0)
    _, train1, _ = task(1)
    sem = P.Semantics(train1)
    inp = P.build_input(train1, sem)
    own = [r["k"] for r in sorted((r for r in inp["failure"]["frontier"] if r["status"] == "PARTIAL"),
                                  key=lambda r: (-sum(r["covered"]), r["entries"], r["k"]))]
    for depth in (2, 3):
        fc = [p["canonical"] for p in P.propose(inp, depth, sem)["proposals"]]
        assert [p["canonical"] for p in P.propose(inp, depth, sem, tops=own)["proposals"]] == fc
    donor = P.build_input(train0)["failure"]
    trans = P.solve(train1, "SHUFFLED_FRONTIER", donor_failure=donor)
    blind = P.solve(train1, "BLIND")
    coords = P.solve(train1, "SHUFFLED_COORDINATES", donor_failure=donor)
    assert trans["class"] in P.FAILURE_CLASSES + ("SELECTED",) and blind["class"] in P.FAILURE_CLASSES + ("SELECTED",)
    assert sum(trans["proposals"].values()) + sum(blind["proposals"].values()) > 0
    assert coords["input_sha256"] == trans["input_sha256"]
    assert P.solve(train1, "BLIND")["selection"] == blind["selection"]


# 15. no Step-B dependency
def test_no_step_b_dependency():
    parent = os.path.dirname(HERE)
    forbidden = [os.path.join(parent, name) + os.sep for name in ("Reasoning_Project", "VDCG")]
    loaded = [m.__file__ for m in list(sys.modules.values()) if getattr(m, "__file__", None)]
    assert not any(f.startswith(root) for f in loaded for root in forbidden)
    assert not any(w in f for f in loaded for w in ("E_transfer", "Lockbox", "lockbox"))
    with open(P.__file__) as handle:
        text = handle.read()
    assert "Reasoning_Project/" not in text
    assert not any(w in text for w in ("VDCG", "E_transfer", "Lockbox", "lockbox"))


# failure classes: every proposer-level class is reachable
def test_proposer_failure_classes_are_reachable(monkeypatch):
    _, train, _ = task(1)
    assert P.solve(train, wall_s=0.0)["class"] == "RESOURCE_EXHAUSTED"
    assert P.solve(train, "PURE")["class"] == "SELECTION_ABSTAINED"
    donor = P.build_input(task(0)[1])["failure"]
    donor["frontier"][0]["seed"] = 1
    assert P.solve(train, "SHUFFLED_FRONTIER", donor_failure=donor)["class"] == "LEAKAGE_FAILURE"
    empty = P.build_input(train)["failure"]
    for row in empty["frontier"]:
        if row["status"] != "CONFLICT":
            for k in ("covered", "changed", "entries", "residual"):
                row.pop(k)
            row.update(status="CONFLICT", code="slot_nonfunctional")
    assert P.solve(train, "SHUFFLED_FRONTIER", donor_failure=empty)["class"] == "NO_PROPOSAL"
    with monkeypatch.context() as mp:
        mp.setattr(P, "verify", lambda props, sem, deadline=None: [])
        assert P.solve(train)["class"] == "NO_VERIFIABLE_PROPOSAL"
        mp.setitem(P.LIMITS, "max_proposals", 1)
        assert P.solve(train)["class"] == "PROPOSAL_LIMIT"
    with monkeypatch.context() as mp:
        def broken(indices, blocks=None):
            return ("Compose", (("Partition", ("colour_components",)), ("Paint", ())))
        mp.setattr(P, "compose", broken)
        assert P.solve(train)["class"] == "UNTYPEABLE_PROPOSAL"


def test_k_already_solves_on_a_single_layer_task():
    from cora_arc2026 import v15_sel as S
    schema = S.CV.ast_from_blocks([("colour_components", ("all",), "is_square")])
    seed = 810000100
    gs = [seed * 97 + k for k in range(30)]
    concrete = S.CD.instantiate_tables(schema, [S.CD.generate_grid(s) for s in gs[:6]])
    pairs, _ = S.CD.render_demonstrations(concrete, gs, min_demos=6)
    assert P.solve(pairs[:7])["class"] == "K_ALREADY_SOLVES"


def test_d_applies_only_to_key_feature_ties_and_matches_v16_on_one_position():
    _, train, _ = task(1)
    sem = P.Semantics(train)
    a = {"schema": P.compose([9, 83]), "mdl": (0,)}
    b = {"schema": P.compose([2, 83]), "mdl": (0,)}
    chosen, how = P.d_choice([a, b], sem)
    assert how in ("D", "D_TIE")
    d = P.frozen_d()
    from cora_arc2026 import scorer_fit as SFIT
    toks_a, toks_b = (P.S.CV.tokens_from_ast(c["schema"]) for c in (a, b))
    j = [i for i in range(len(toks_a)) if toks_a[i] != toks_b[i]][0]
    state = P.S.CV.GrammarState()
    for tok in toks_a[:j]:
        state = state.advance(tuple(tok))
    x = [1.0] + P.d_rich_row(sem) + SFIT.state_vector(state)
    tix = {tuple(t): i for i, t in enumerate(d["tokens"])}
    la = sum(w * v for w, v in zip(d["W"][tix[tuple(toks_a[j])]], x))
    lb = sum(w * v for w, v in zip(d["W"][tix[tuple(toks_b[j])]], x))
    if how == "D":
        assert (chosen is a) == (la > lb)
    other = {"schema": P.compose([19, 83]), "mdl": (0,)}           # differs in the predicate
    assert P.d_choice([a, other], sem)[1] == "D_NOT_APPLICABLE"


def test_s6_separation_law_and_its_downgrades(monkeypatch):
    _, train, _ = task(0)
    rec = P.solve(train)
    sep = P.separation(rec, train)
    assert sep["A_syntactic_absent"] and sep["B_outside_bounded_search"]
    assert sep["comparison_set"] > 0 and sep["C"] == "SEPARATED" and sep["new_capability"]
    assert sep["C_probes"] in ("SEPARATED", "DUPLICATE_EXISTING_SEMANTICS")
    sem = P.Semantics(train)
    row = next(r for r in P.frontier(sem) if r["status"] == "PARTIAL")
    ok, info = P.layer(sem, P.k_blocks()[row["k"]], [frozenset()] * len(train))
    table = tuple(sorted(info["constraints"].items(), key=lambda kv: repr(kv[0])))
    dup = P.behaviour(M.instantiate(P.compose([row["k"]]), {"?0": table}))
    forged = dict(rec, selected=dict(rec["selected"], fingerprint=dup))
    out = P.separation(forged, train)
    assert out["C"] == "DUPLICATE_EXISTING_SEMANTICS" and not out["new_capability"]
    monkeypatch.setattr(P, "frontier", lambda sem: [{"k": k, "status": "CONFLICT", "code": "slot_nonfunctional"}
                                                    for k in range(200)])
    down = P.separation(rec, train)
    assert down["C"] == "C_UNTESTABLE" and not down["new_capability"]


def test_compile_failure_is_classified(monkeypatch):
    _, train, held = task(0)
    rec = P.solve(train)

    def boom(inp):
        raise X.CompileError("UNTYPEABLE", "forced")
    monkeypatch.setattr(X, "compile_extension", boom)
    assert P.engine_stage(train, held, rec)["class"] == "COMPILE_FAILURE"


# engine integration: compile, install, rerun; real leave-one-out
@pytest.mark.engine
def test_engine_stage_and_real_loo_on_a_fixture():
    _, train, held = task(0)
    rec = P.solve(train)
    st = P.engine_stage(train, held, rec)
    assert st["class"] == "SUCCESS" and st["uses"] and not st["without"]["accepted"]
    loo = P.real_loo(train)
    assert len(loo["folds"]) == len(train)
    assert all("events" in f for f in loo["folds"] if f["proposer_class"] == "SELECTED")
    assert loo["folds_success"] >= 1
