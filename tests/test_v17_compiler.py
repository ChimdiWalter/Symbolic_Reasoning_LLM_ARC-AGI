"""Tests of the v1.7 ConstructiveExtensionCompiler: the fifteen required
properties, metamorphic relations, and integration with the real engine
under K* on synthetic constructive fixtures (seed range 810,000,000, disjoint
from every corpus). Nothing here reads a protected file or an ARC answer.

Engine-integration tests are marked `engine`; they take a few minutes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_tti import constructive_dataset as CD                    # noqa: E402
from cora_tti import scoped_slot_fitting as SF                     # noqa: E402

M, MI = X._meta()
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
#: (seed, family) of the certifiable two-block fixtures found by
#: logs/v17/findfix.py; the schemas are regenerated here and checked against
#: logs/v17/fixtures.json
FIXTURES = ((810000100, "(1,0)"), (810004800, "(1,1)"))


def fixture(i):
    from cora_arc2026 import v15_sel as S
    seed, fam = FIXTURES[i]
    schema = CD.sample_target(seed, S.G.parse_family(fam))
    gs = [seed * 97 + k for k in range(30)]
    concrete = CD.instantiate_tables(schema, [CD.generate_grid(s) for s in gs[:6]])
    pairs, _ = CD.render_demonstrations(concrete, gs, min_demos=6)
    return schema, pairs[:7], pairs[7]


def prod_of(schema, **kw):
    return X.compile_extension(X.make_input(schema, **kw))


def single_block(partition="colour_components", predicate="all", feature="is_square", slot="?0"):
    return ("Compose", (("Partition", (partition,)), ("Select", (predicate,)),
                        ("Map", (("Key", (feature,)), ("Lookup", (slot,)))), ("Paint", ())))


def two_block(slots=("?a", "?b")):
    return ("Compose", (("Partition", ("colour_components",)),
                        ("Map", (("Key", ("is_square",)), ("Lookup", (slots[0],)))), ("Paint", ()),
                        ("Partition", ("background_components",)), ("Select", ("not_rectangular",)),
                        ("Map", (("Key", ("is_square",)), ("Lookup", (slots[1],)))), ("Paint", ())))


def test_fixtures_regenerate_exactly():
    rec = json.load(open(os.path.join(HERE, "logs", "v17", "fixtures.json")))
    for i, (seed, fam) in enumerate(FIXTURES):
        schema, train, held = fixture(i)
        assert M.ast_to_json(schema) == rec[i]["schema"] and rec[i]["seed"] == seed
        assert len(train) == 7


# 1. deterministic compilation (and 2. canonical serialization)
def test_compilation_is_deterministic_and_canonical():
    schema, _, _ = fixture(0)
    a, b = prod_of(schema), prod_of(schema)
    assert X.serialize(a) == X.serialize(b)
    raw = X.serialize(a)
    assert raw == json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")).encode()
    assert X.load(raw) == a and X.serialize(X.load(raw)) == raw
    assert a["name"].startswith("cx_") and a["compiler_sha256"] == X.compiler_sha256()
    assert a["k_identity"] == X.k_identity()


# 3. identical semantics after serialize/reload
def test_reloaded_production_has_identical_semantics():
    schema, train, held = fixture(0)
    p = prod_of(schema)
    q = X.load(X.serialize(p))
    with X.kstar():
        fa = MI.fit_induced_slots(X.ConceptView(p).schema, train)
        fb = MI.fit_induced_slots(X.ConceptView(q).schema, train)
    assert fa is not None and fa == fb
    ra = M.evaluate(fa, held[0], MI.descriptors)
    assert np.array_equal(ra, held[1])
    from geocat_arc.object_reasoning.meta_induction import ComputedPatternProgram
    from geocat_arc.object_reasoning.types import program_from_dict
    prog = ComputedPatternProgram(ast=fa, concept=p["name"])
    back = program_from_dict(json.loads(json.dumps(prog.to_dict())))
    assert np.array_equal(back.render_array(held[0]), ra)


# 4. correct typing
def test_signature_types_follow_the_frozen_positions():
    p = prod_of(two_block())
    assert p["signature"]["args"] == [["?s0", X.INDUCED_TYPE], ["?s1", X.INDUCED_TYPE]]
    assert p["signature"]["result"] == "Grid" and p["blocks"] == 2
    ast = ("Compose", (("Partition", ("?p",)), ("Select", ("?q",)),
                       ("Map", (("Key", ("?f",)), ("Lookup", ("?t",)))), ("Paint", ())))
    q = prod_of(ast)
    assert [t for _, t in q["signature"]["args"]] == ["PartitionExpr", "Predicate", "FeatureExpr", X.INDUCED_TYPE]
    assert q["enumerable_slots"] == ["?s0", "?s1", "?s2"] and q["induced_slots"] == ["?s3"]


# 5. malformed extension rejection, one per failure class
@pytest.mark.parametrize("mutate,code", [
    (lambda d: d.update(task_id="abc"), "MALFORMED_INPUT"),
    (lambda d: d.pop("provenance"), "MALFORMED_INPUT"),
    (lambda d: d["provenance"].update(family="symmetry"), "MALFORMED_INPUT"),
    (lambda d: d["provenance"].update(producer_sha256="nothex"), "MALFORMED_INPUT"),
    (lambda d: d.update(compiler_version="0.0"), "VERSION_MISMATCH"),
    (lambda d: d.update(k_identity="f" * 64), "K_IDENTITY_MISMATCH"),
    (lambda d: d.update(source_sha256="0" * 64), "SOURCE_HASH_MISMATCH"),
    (lambda d: d.update(declared_types={"input": "Grid", "output": "Set[Region]"}), "DECLARED_TYPE_MISMATCH"),
])
def test_input_contract_rejections(mutate, code):
    d = X.make_input(two_block())
    mutate(d)
    with pytest.raises(X.CompileError) as exc:
        X.compile_extension(d)
    assert exc.value.code == code


@pytest.mark.parametrize("ast,code", [
    (("Paint", ()), "UNTYPEABLE"),
    (("Compose", ()), "UNTYPEABLE"),
    (("Compose", (("Partition", ("colour_components",)), ("Map", (("Key", ("colour",)), ("Lookup", ("?a",)))))), "UNTYPEABLE"),
    (single_block(partition="nonsense"), "UNKNOWN_TERMINAL"),
    (single_block(feature="nonsense"), "UNKNOWN_TERMINAL"),
    (single_block(predicate="nonsense"), "UNKNOWN_TERMINAL"),
    (single_block(slot=((1, 2), (3, 4))), "LITERAL_INDUCED_SLOT"),
    (two_block(slots=("?a", "?a")), "DUPLICATE_SLOT"),
    (("Compose", tuple(st for k in range(5) for st in single_block(slot=f"?t{k}")[1])), "LIMIT_EXCEEDED"),
])
def test_typing_law_rejections(ast, code):
    sj = M.ast_to_json(ast)
    d = X.make_input(two_block())
    d["schema"], d["source_sha256"] = sj, X.schema_source_sha256(sj)
    with pytest.raises(X.CompileError) as exc:
        X.compile_extension(d)
    assert exc.value.code == code


def test_unparsable_schema_and_tampered_production():
    d = X.make_input(two_block())
    d["schema"] = {"op": "Compose"}
    d["source_sha256"] = X.schema_source_sha256(d["schema"])
    with pytest.raises(X.CompileError) as exc:
        X.compile_extension(d)
    assert exc.value.code == "UNPARSABLE_SCHEMA"
    p = prod_of(two_block())
    for field, value in (("name", "cx_" + "0" * 24), ("blocks", 3), ("source_sha256", "0" * 64)):
        bad = dict(p, **{field: value})
        with pytest.raises(X.CompileError) as exc:
            X.load(X.serialize(bad))
        assert exc.value.code == "TAMPERED_PRODUCTION"


def _forge(p, body):
    """A production whose name and source hash are recomputed from a
    modified body, as a forger would do (review finding B2)."""
    bb = X.canonical_json(body)
    return dict(p, body=body, source_sha256=X._sha(bb),
                name="cx_" + X._sha(b"cora-cx|" + bb + b"|" + X.canonical_json(p["signature"]))[:24])


# 5. (erratum 01) load rebuilds the production from its own body and
#    requires the compiler's own bytes; install goes through load
def test_load_rejects_every_tampered_field_and_every_forged_body():
    p = prod_of(two_block())
    body = json.loads(json.dumps(p["body"]))
    body["args"][0]["args"][0]["lit"] = '"\\u0063olour_components"'
    cases = [(dict(p, induced_slots=p["induced_slots"][:1]), "TAMPERED_PRODUCTION"),
             (dict(p, enumerable_slots=["?s0"]), "TAMPERED_PRODUCTION"),
             (dict(p, blocks=2.0), "TAMPERED_PRODUCTION"),
             (dict(p, compiler_version="1.7.1"), "VERSION_MISMATCH"),
             (dict(p, compiler_sha256="0" * 64), "VERSION_MISMATCH"),
             (dict(p, k_identity="0" * 64), "K_IDENTITY_MISMATCH"),
             (_forge(p, dict(p["body"], task_id="task-0042")), "TAMPERED_PRODUCTION"),
             (_forge(p, {"op": "Compose"}), "TAMPERED_PRODUCTION"),
             (_forge(p, body), "TAMPERED_PRODUCTION")]
    for bad, code in cases:
        with pytest.raises(X.CompileError) as exc:
            X.load(X.serialize(bad))
        assert exc.value.code == code, (code, exc.value.code)
    assert X.load(X.serialize(p)) == p
    with X.kstar():
        with pytest.raises(X.CompileError) as exc:
            with X.install(cases[6][0]):
                pass
        assert exc.value.code == "TAMPERED_PRODUCTION" and X._STATE["overlay"] == ()


# (erratum 01) the K* environment is enforced by kstar()
def test_kstar_refuses_a_foreign_arc_variable_or_another_hash_seed(monkeypatch):
    monkeypatch.setenv("ARC_DIHEDRAL_FRAMES", "1")
    with pytest.raises(X.CompileError) as exc:
        with X.kstar():
            pass
    assert exc.value.code == "KSTAR_ENVIRONMENT" and not X._STATE["active"]
    monkeypatch.delenv("ARC_DIHEDRAL_FRAMES")
    monkeypatch.setenv("PYTHONHASHSEED", "1")
    with pytest.raises(X.CompileError) as exc:
        with X.kstar():
            pass
    assert exc.value.code == "KSTAR_ENVIRONMENT" and not X._STATE["active"]


# (erratum 01) terminals must be vocabulary strings; no raw TypeError
def test_non_string_terminals_are_unknown_terminals():
    for kw in ({"partition": {"x": 1}}, {"partition": ["colour_components"]},
               {"predicate": {"x": 1}}, {"feature": 3}):
        with pytest.raises(X.CompileError) as exc:
            X.type_check(single_block(**kw))
        assert exc.value.code == "UNKNOWN_TERMINAL", kw


# 6. temporary install and exact restoration
def test_install_and_restoration_leave_no_residue():
    before = X.state_snapshot()
    icc, learner = MI.induce_computed_candidates, MI.SLOT_LEARNERS[X.INDUCED_TYPE]
    env = os.environ.get("ARC_META_INDUCTION")
    p = prod_of(two_block())
    with X.kstar():
        assert MI.induce_computed_candidates is not icc
        with X.install(p) as rec:
            assert [c.name for c in X._STATE["overlay"]] == [p["name"]]
        assert rec["snapshot_after"] == rec["snapshot_before"] and X._STATE["overlay"] == ()
    assert MI.induce_computed_candidates is icc and MI.SLOT_LEARNERS[X.INDUCED_TYPE] is learner
    assert os.environ.get("ARC_META_INDUCTION") == env and X.state_snapshot() == before


def test_install_requires_kstar_and_rejects_conflicts():
    p = prod_of(two_block())
    with pytest.raises(X.CompileError) as exc:
        with X.install(p):
            pass
    assert exc.value.code == "KSTAR_NOT_ACTIVE"
    with X.kstar():
        with pytest.raises(X.CompileError) as exc:
            with X.install(p, p):
                pass
        assert exc.value.code == "OVERLAY_CONFLICT"
        with X.install(p):
            with pytest.raises(X.CompileError):
                with X.install(p):
                    pass
    with pytest.raises(X.CompileError):
        with X.kstar():
            with X.kstar():
                pass


# 7. no state leakage between sequential extensions
def test_sequential_extensions_do_not_leak():
    s0, train0, _ = fixture(0)
    s1, _, _ = fixture(1)
    a, b = prod_of(s0), prod_of(s1)
    with X.kstar():
        with X.install(a):
            hits_a, _ = MI.induce_computed_candidates(train0)
        with X.install(b):
            hits_b, _ = MI.induce_computed_candidates(train0)
            assert [c.name for c in X._STATE["overlay"]] == [b["name"]]
    assert any(h.concept == a["name"] for h in hits_a)
    assert not any(h.concept == a["name"] for h in hits_b)


# 8. winning-program usage attribution (synthetic cases; engine case below)
def test_uses_extension_requires_both_label_and_structure():
    s0, train0, _ = fixture(0)
    p = prod_of(s0)
    with X.kstar():
        fitted = MI.fit_induced_slots(X.ConceptView(p).schema, train0)
    good = {"program_class": "computed_pattern", "ast": M.ast_to_json(fitted), "concept": p["name"]}
    assert X.uses_extension(good, p)
    assert not X.uses_extension(dict(good, concept="cx_other"), p)
    other = single_block(slot=((1, 2),))
    assert not X.uses_extension(dict(good, ast=M.ast_to_json(other)), p)
    assert X.uses_extension({"program_class": "framed", "frame": [1, False], "inner": good}, p)
    assert not X.uses_extension({"program_class": "object_program", "rules": []}, p)


# 10. task-ID invariance and 11. renamed-extension invariance and 12. order
def test_input_has_no_task_channel_and_renaming_is_invariant():
    assert "task_id" not in X.INPUT_KEYS and X.PROVENANCE_KEYS == {"producer_sha256", "evidence_sha256"}
    a = prod_of(two_block(("?a", "?b")))
    b = prod_of(two_block(("?zeta", "?q9")))
    c = prod_of(two_block(("?a", "?b")), producer_sha256="1" * 64, evidence_sha256="2" * 64)
    assert X.serialize(a) == X.serialize(b) == X.serialize(c)


def test_input_key_order_and_demonstration_order_do_not_matter():
    d = X.make_input(two_block())
    shuffled = json.loads(json.dumps({k: d[k] for k in reversed(list(d))}))
    assert X.serialize(X.compile_extension(shuffled)) == X.serialize(X.compile_extension(d))
    s0, train0, held = fixture(0)
    p = prod_of(s0)
    with X.kstar():
        fa = MI.fit_induced_slots(X.ConceptView(p).schema, train0)
        fb = MI.fit_induced_slots(X.ConceptView(p).schema, list(reversed(train0)))
    assert fa == fb


def test_block_order_is_not_a_symmetry():
    ast = two_block()
    stages = list(ast[1])
    swapped = ("Compose", tuple(stages[3:] + stages[:3]))
    assert prod_of(swapped)["name"] != prod_of(ast)["name"]


# 13. fresh-process reproduction
def test_fresh_process_reproduces_the_bytes():
    s0, _, _ = fixture(0)
    want = hashlib.sha256(X.serialize(prod_of(s0))).hexdigest()
    code = ("import sys,json,hashlib; sys.path.insert(0, %r); "
            "from cora_arc2026 import v17_compiler as X; M,_=X._meta(); "
            "rec=json.load(open(%r)); ast=M.ast_from_json(rec[0]['schema']); "
            "print(hashlib.sha256(X.serialize(X.compile_extension(X.make_input(ast)))).hexdigest())"
            % (HERE, os.path.join(HERE, "logs", "v17", "fixtures.json")))
    env = dict(os.environ, PYTHONPATH=TTI, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=600)
    assert out.stdout.strip().splitlines()[-1] == want


# 14. leave-one-out reconstruction isolation (no engine)
def test_adaptive_loo_gives_each_fold_only_its_own_pairs_and_a_fresh_compile():
    s0, train0, _ = fixture(0)
    seen, objs = [], []

    def propose(fold):
        seen.append(fold)
        p = prod_of(s0)
        objs.append(p)
        return p

    def fake_solve(pairs, prods):
        assert len(prods) == 1 and prods[0] is objs[-1] and pairs == seen[-1]
        return {"accepted": False, "program": None, "apply_fn": None}
    res = X.adaptive_loo(train0, propose, solve=fake_solve)
    assert len(res["folds"]) == len(train0) and not res["passed"]
    for i, fold in enumerate(seen):
        assert len(fold) == len(train0) - 1
        assert not any(a is train0[i][0] for a, _ in fold)
    assert len({id(o) for o in objs}) == len(objs)


# 15. not behaviourally equivalent to K under the declared bounded witness test
def test_witness_separation():
    s0, train0, _ = fixture(0)
    assert X.witness_separation(prod_of(s0), train0)["status"] == "SEPARATED"
    found = None
    for feature in ("is_square", "touches_border", "is_rect", "area"):
        for k in range(40):
            k_schema = single_block(partition="colour_components", predicate="all",
                                    feature=feature, slot="?0")
            gs = [(820000000 + k) * 97 + j for j in range(30)]
            concrete = CD.instantiate_tables(k_schema, [CD.generate_grid(s) for s in gs[:6]])
            if concrete is None:
                continue
            pairs, _ = CD.render_demonstrations(concrete, gs, min_demos=4)
            if len(pairs) >= 4 and SF.fit_induced_occurrences(k_schema, pairs)[0] is not None:
                found = (k_schema, pairs)
                break
        if found:
            break
    assert found is not None, "no single-block K-shaped target found in the frozen search"
    k_schema, pairs = found
    assert X.witness_separation(prod_of(k_schema), pairs)["status"] == "EQUIVALENT_TO_K"


# metamorphic, weak (review MINOR 6): on these 200 single-block schemas
# the two fitters agree for fixture 0, but every schema takes the delegation
# branch and most fit neither way. The inertness argument is
# test_engine_kstar_without_overlay_never_calls_the_learner.
def test_kstar_fitting_law_is_inert_on_k_shapes():
    _, train0, _ = fixture(0)
    schemas = SF.baseline_single_block_schemas()
    outside = [MI.fit_induced_slots(s, train0) for s in schemas]
    with X.kstar():
        inside = [MI.fit_induced_slots(s, train0) for s in schemas]
    assert outside == inside and len(schemas) == 200


# --------------------------------------------------------------------------
# engine integration (8. attribution, 9. ablation, 10. task id, 14. L leg)
# --------------------------------------------------------------------------

@pytest.mark.engine
@pytest.mark.parametrize("i", [0, 1])
def test_engine_paired_ablation(i):
    schema, train, held = fixture(i)
    p = prod_of(schema)
    before = X.state_snapshot()
    ab = X.paired_ablation(train, p, heldout=held)
    assert ab["verdict"] == "EXTENSION_NECESSARY_AND_USED", ab["verdict"]
    assert ab["with"]["heldout_exact"] and not ab["without"]["accepted"]
    assert "HYPOTHESIS_ACCEPTED" in ab["with"]["events"]
    assert ab["with"]["engine_dir_removed"] and ab["without"]["engine_dir_removed"]
    assert X.state_snapshot() == before


# (erratum 01) K*-2 is inert for K because K never reaches the learner:
# without an overlay the concept route is dormant
@pytest.mark.engine
def test_engine_kstar_without_overlay_never_calls_the_learner(monkeypatch):
    schema, train, _ = fixture(0)
    p = prod_of(schema)
    shape = X._shape_ops(M.ast_from_json(p["body"]))
    calls = []
    factory = X.kstar_learner_factory

    def spying_factory(orig):
        learner = factory(orig)

        def spy(ast, pairs, slot):
            calls.append(X._shape_ops(ast))
            return learner(ast, pairs, slot)
        return spy
    monkeypatch.setattr(X, "kstar_learner_factory", spying_factory)
    X.run_reasoner(train, ())
    assert calls == []
    X.run_reasoner(train, (p,))
    assert calls and all(c == shape for c in calls)


@pytest.mark.engine
def test_engine_task_id_invariance():
    schema, train, _ = fixture(0)
    p = prod_of(schema)
    a = X.run_reasoner(train, (p,), task_id="task")
    b = X.run_reasoner(train, (p,), task_id="a-different-id")
    assert a["accepted"] and a["program"] == b["program"]


@pytest.mark.engine
def test_engine_adaptive_loo_with_recompilation_in_every_fold():
    schema, train, _ = fixture(0)
    res = X.adaptive_loo(train, lambda fold: prod_of(schema))
    assert res["passed"], res["folds"]
