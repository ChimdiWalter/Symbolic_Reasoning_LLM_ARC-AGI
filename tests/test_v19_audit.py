"""Item-2 v1.9 engine acceptance stability audit: tests.

Fixtures are the v1.7 development tasks (seed range 810,000,000). Engine
tests are marked `engine`.
"""
from __future__ import annotations

import itertools
import os
import sys
import time

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_v19 import v19_audit as A                           # noqa: E402
from cora_v19 import v19_trace as TR                          # noqa: E402
from test_v17_compiler import FIXTURES, fixture                   # noqa: E402

M, MI = X._meta()
SF = X._sf()


# 1. the census is the fitter's constraint collection
def test_census_tables_equal_the_fitter_where_the_fitter_succeeds():
    for i in range(len(FIXTURES)):
        schema, train, _ = fixture(i)
        fitted, _ev = SF.fit_induced_occurrences(schema, train)
        assert fitted is not None
        inst = M.instantiate(schema, A.permissive_tables(schema, train))
        assert M.ast_to_json(inst) == M.ast_to_json(fitted)


def test_witness_refusals_show_a_single_witness_in_the_census():
    seen = 0
    for i in range(len(FIXTURES)):
        schema, train, _ = fixture(i)
        for size in (2, 3):
            for sub in itertools.islice(itertools.combinations(train, size), 12):
                fitted, ev = SF.fit_induced_occurrences(schema, list(sub))
                if fitted is None and "witnessed by" in (ev.get("detail") or ""):
                    c = A.census(schema, list(sub))
                    assert c["error"] is None
                    assert any(len(w) < 2 for w in c["witness"].values())
                    seen += 1
    assert seen > 0


def test_permissive_fit_on_all_pairs_reproduces_each_pair():
    for i in range(len(FIXTURES)):
        schema, train, _ = fixture(i)
        for j in range(len(train)):
            assert A.permissive_predicts(schema, train, train[j])
            assert A.needed_unwitnessed(schema, train, train[j]) == []


# 2. the tracer observes and restores
def _attrs():
    E, I, MI_, SF_ = TR._mods()
    return [E.induce_program, I.loo_validate, I._induce_composed, MI_.trigger_fires,
            MI_.search_with_concepts, SF_.fit_induced_occurrences]


def test_tracer_and_clock_shim_restore_everything():
    def clocks():
        return {n: m.time for n, m in list(sys.modules.items())
                if n.startswith("geocat_arc.") and m is not None and hasattr(m, "time")}
    before, snap, held = _attrs(), X.state_snapshot(), clocks()
    for clock in TR.CLOCKS:
        with TR.traced(clock) as tr:
            assert tr["clock"] == clock
            from geocat_arc.object_reasoning import inducer as I
            assert (I.time is time) == (clock == "WALL")
        assert _attrs() == before
        assert all(clocks()[n] is v for n, v in held.items())
    assert X.state_snapshot() == snap
    assert TR.untraced_identity()


def test_nested_trace_refused():
    with TR.traced():
        with pytest.raises(RuntimeError):
            with TR.traced():
                pass


# 3. reason-code rules
def _search(**kw):
    base = {"hits": [], "stats": {"hypotheses": 1}, "bindings_total": 1, "past_deadline": False,
            "fits": []}
    base.update(kw)
    return base


def test_search_code_branches():
    assert A._search_code(None) == "EXTENSION_NOT_VISIBLE:no_concept_search"
    assert A._search_code(_search(hits=[("x", ())])) is None
    assert A._search_code(_search(stats={"hypotheses": 0}, past_deadline=True)) == \
        "EXPRESSION_BUDGET_EXHAUSTED"
    assert A._search_code(_search()) == "EXTENSION_NOT_VISIBLE:no_fit_call"
    w = {"ok": False, "failure": "slot_key_unobserved",
         "detail": "block 0 key 3 witnessed by 1 < 2 demonstrations"}
    assert A._search_code(_search(fits=[w])) == "SLOT_FIT_FAILED:witness"
    h = {"ok": False, "failure": "slot_key_unobserved", "detail": "block 0 keys never visible: ['3']"}
    assert A._search_code(_search(fits=[h])) == "SLOT_FIT_FAILED:hidden_key"
    c = {"ok": False, "failure": "region_colour_conflict", "detail": "x"}
    assert A._search_code(_search(fits=[c])) == "SLOT_FIT_FAILED:region_colour_conflict"
    ok = {"ok": True, "failure": None, "detail": None}
    assert A._search_code(_search(fits=[ok])) == "TRAINING_PAIR_MISMATCH:observational_signature"


def test_every_code_prefix_is_in_the_taxonomy():
    for code in ("SLOT_FIT_FAILED:witness", "RANKED_BELOW_COMPETITOR", "EXPRESSION_BUDGET_EXHAUSTED",
                 "EXTENSION_NOT_VISIBLE:trigger", "SLOT_FIT_AMBIGUOUS:unseen_key",
                 "FINAL_EXECUTION_MISMATCH", "TRAINING_PAIR_MISMATCH:observational_signature",
                 "OTHER_EXPLICIT_REASON:ValueError"):
        assert code.split(":")[0] in A.REASON_CODES


# 4. stop rule and data boundary
def test_stop_prefix():
    import v19_audit_dev as D

    def row(i, cat):
        if cat is None:
            return {"index": i, "status": "NOT_SELECTED"}
        full = cat != "R"
        folds = [{"accepted": not (cat == "A" and k == 0)} for k in range(7)]
        return {"index": i, "status": "AUDITED", "audit": {"FULL": {"accepted": full}, "FOLDS": folds}}
    rows = [row(i, "A" if i % 2 else "B") for i in range(20)]
    assert D.stop_prefix(rows, 60) is None                  # fewer than 30 audited, prefix incomplete
    rows = [row(i, "A" if i % 2 else "B") for i in range(31)]
    assert D.stop_prefix(rows, 60) == 30                    # 30 audited, A 15 >= 12, B 15 >= 6
    rows = [row(i, None) for i in range(5)] + [row(i, "A" if i % 2 else "B") for i in range(5, 40)]
    assert D.stop_prefix(rows, 60) == 35                    # non-audited tasks do not count
    rows = [row(i, "B") for i in range(40)]
    assert D.stop_prefix(rows, 60) is None                  # A never reaches 12
    rows = [row(i, "B") for i in range(60)]
    assert D.stop_prefix(rows, 60) == 60


def test_driver_never_generates_the_reserved_range_and_never_feeds_the_schema():
    src = open(os.path.join(HERE, "scripts", "v19_audit_dev.py")).read()
    assert src.count("880_000_000") == 1                     # the reserved constant only
    assert "CORPUS.tasks(DEV_BASE" in src and "PROSPECTIVE_BASE_RESERVED" not in src.split("def prepare")[1]
    process_src = src.split("def process(task):")[1].split("def worker")[0]
    assert "schema" not in process_src


# 5. decisions are identical under tracing (engine)
@pytest.mark.engine
def test_traced_run_equals_untraced_run():
    schema, train, held = fixture(0)
    prod = X.compile_extension(X.make_input(schema))
    plain = X.run_reasoner(train, (prod,))
    traced = A.traced_run(train, prod, "WALL", held)
    assert traced["accepted"] == plain["accepted"]
    assert traced["events"] == plain["events"]
    if plain["accepted"]:
        import hashlib
        import json
        assert traced["program_sha"] == hashlib.sha256(
            json.dumps(plain["program"], sort_keys=True).encode()).hexdigest()[:16]
    assert TR.untraced_identity()
