"""Item-2 v1.9 repair K*-4 (installed-extension re-induction): tests.

Fixtures: the v1.7 development tasks (810M) and, for the engine tests, two
same-e folds from the v1.9 development diagnosis (870M, committed corpus
and rows). Engine tests are marked `engine`.
"""
from __future__ import annotations

import base64
import itertools
import json
import os
import sys
import types

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_v19 import v19_audit as A                           # noqa: E402
from cora_v19 import v19_repair as R                          # noqa: E402
from test_v17_compiler import FIXTURES, fixture                   # noqa: E402

M, MI = X._meta()
SF = X._sf()


def _funcs():
    I, MI_, _ = R._mods()
    return I.rank_candidates, I.rank_by_score, MI_.search_with_concepts


# 1. inertness and restoration
def test_patches_restored_and_snapshot_unchanged():
    before, snap = _funcs(), X.state_snapshot()
    for clauses in (("fit",), ("rank",), R.CLAUSES):
        with R.repaired(clauses) as info:
            assert info["clauses"] == clauses
            assert SF.MIN_KEY_WITNESSES == 2               # only inside an installed-concept search
        assert _funcs() == before
    assert X.state_snapshot() == snap
    assert R.restored()


def test_nested_activation_refused():
    with R.repaired():
        with pytest.raises(RuntimeError):
            with R.repaired():
                pass
    assert R.restored()


def test_rank_partition_inert_without_installation_and_stable_with_it():
    natives = [types.SimpleNamespace(concept=None, tag=i) for i in range(3)]
    ext = types.SimpleNamespace(concept="cx_test", tag="e")
    other = types.SimpleNamespace(concept="cx_other", tag="o")
    pool = [natives[0], other, ext, natives[1], natives[2]]
    assert X._STATE["overlay"] == ()
    assert R._partition(pool) is pool                      # nothing installed: the native list itself
    X._STATE["overlay"] = (types.SimpleNamespace(name="cx_test"),)
    try:
        out = R._partition(pool)
    finally:
        X._STATE["overlay"] = ()
    assert [p.tag for p in out] == ["e", 0, "o", 1, 2]     # installed first, native order kept


def test_repair_identity_is_deterministic_and_differs_from_kstar():
    assert R.repair_identity() == R.repair_identity()
    assert R.repair_identity() != X.k_identity()


# 2. the fitting clause
def _witness_refused_subset():
    for i in range(len(FIXTURES)):
        schema, train, _ = fixture(i)
        for size in (3, 4, 5):
            for sub in itertools.combinations(range(len(train)), size):
                pairs = [train[j] for j in sub]
                fitted, ev = SF.fit_induced_occurrences(schema, pairs)
                if fitted is None and "witnessed by" in (ev.get("detail") or ""):
                    SF.MIN_KEY_WITNESSES = 1
                    try:
                        ok, _ = SF.fit_induced_occurrences(schema, pairs)
                    finally:
                        SF.MIN_KEY_WITNESSES = 2
                    if ok is not None:
                        return schema, pairs
    return None


def test_fit_clause_admits_a_witness_refusal_inside_kstar_and_restores():
    found = _witness_refused_subset()
    assert found is not None
    schema, pairs = found
    prod = X.compile_extension(X.make_input(schema))
    with X.kstar():
        with X.install(prod):
            plain, _ = MI.search_with_concepts(pairs, X._STATE["overlay"])
    assert plain == []
    with R.repaired(("fit",)):
        with X.kstar():
            with X.install(prod):
                hits, _ = MI.search_with_concepts(pairs, X._STATE["overlay"])
                assert SF.MIN_KEY_WITNESSES == 2
    assert len(hits) == 1 and hits[0][0].name == prod["name"]
    assert R.restored()


def test_fit_clause_inert_for_native_concept_searches():
    with R.repaired(("fit",)):
        out = MI.search_with_concepts([], ())
    assert out[0] == []


# 3. engine: inert on K* alone; repairs the two diagnosed mechanisms
def _dev_case(code_prefix):
    corpus = json.load(open(os.path.join(HERE, "outputs", "tti", "v19_dev_corpus.json")))["tasks"]
    rows = [json.loads(line) for line in open(os.path.join(HERE, "outputs", "tti", "v19_dev_rows.jsonl"))]
    for r in sorted(rows, key=lambda r: r["index"]):
        if r.get("status") != "AUDITED" or r["index"] >= 30:
            continue
        for f in r["audit"]["FOLDS"]:
            codes = f["reason"]["codes"] if f.get("reason") else []
            if not f["accepted"] and codes and all(c.startswith(code_prefix) for c in codes):
                t = corpus[r["index"]]
                train = [(np.asarray(p[0]), np.asarray(p[1])) for p in t["train"]]
                sub = [train[k] for k in range(7) if k != f["fold"]]
                prod = X.load(base64.b64decode(r["production"]))
                return sub, train[f["fold"]], prod
    return None


@pytest.mark.engine
def test_kstar_alone_identical_under_the_repair():
    _, train, held = fixture(0)
    plain = X.run_reasoner(train, ())
    rep = R.run_reasoner(train, ())
    assert (plain["accepted"], plain["events"], plain["program"]) == \
        (rep["accepted"], rep["events"], rep["program"])
    assert R.restored()


@pytest.mark.engine
@pytest.mark.parametrize("code", ["SLOT_FIT_FAILED:witness", "RANKED_BELOW_COMPETITOR"])
def test_repair_accepts_a_diagnosed_rejection_with_the_heldout_exact(code):
    case = _dev_case(code)
    assert case is not None
    sub, held, prod = case
    old = X.run_reasoner(sub, (prod,))
    assert not old["accepted"]
    new = R.run_reasoner(sub, (prod,))
    assert new["accepted"] and X.uses_extension(new["program"], prod)
    assert X.predict_exact(new, *held)
    assert R.restored()
