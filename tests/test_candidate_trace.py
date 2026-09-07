"""Non-interference and data-access tests for the candidate-trace observer.

The observer must be additive: running it may not change baseline candidate
order, per-candidate fitting decisions, accepted programs, or any persistent
state, and its runtime cost must be measurable. It may never receive the
generating target.
"""
from __future__ import annotations

import ast as pyast
import copy
import inspect
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti import candidate_trace as CT                      # noqa: E402
from cora_tti import constructive_dataset as CD                 # noqa: E402
from cora_tti import constructive_v2c as V2C                    # noqa: E402
from cora_tti import constructive_vocabulary as CV              # noqa: E402
from cora_tti import meta_baseline as MB                        # noqa: E402
from cora_tti import scoped_slot_fitting as SF                  # noqa: E402

CONFIG = MB.BaselineConfig()


def _pairs(seed=7_400_000, family=(0, 0)):
    for attempt in range(300):
        s = seed + attempt * 7919
        schema = CD.sample_target(s, family)
        grid_seeds = [s * 97 + i for i in range(14)]
        concrete = V2C.instantiate_tables(schema, [CD.generate_grid(g) for g in grid_seeds[:6]])
        if concrete is None:
            continue
        pairs, _ = CD.render_demonstrations(concrete, grid_seeds, min_demos=3)
        if len(pairs) >= 3:
            return [(np.asarray(a), np.asarray(b)) for a, b in pairs]
    pytest.skip("no demonstrations generated")


# ------------------------------------------------------------ additivity ---

def test_observer_does_not_change_baseline_order_verdicts_or_programs():
    pairs = _pairs()
    before = MB.run_baseline(pairs, CONFIG)
    snapshot = copy.deepcopy(before.records)
    order_before = [r["index"] for r in before.records]
    triples_before = [tuple(r["triple"]) for r in before.records]
    verdicts_before = [(r["status"], r["code"]) for r in before.records]
    exact_before = [MB._canonical(s) for s, _ in before.exact]

    view = CT.observe(before)

    assert [r["index"] for r in before.records] == order_before
    assert [tuple(r["triple"]) for r in before.records] == triples_before
    assert [(r["status"], r["code"]) for r in before.records] == verdicts_before
    assert [MB._canonical(s) for s, _ in before.exact] == exact_before
    assert before.records == snapshot, "the observer mutated the trace"
    assert view.baseline_config_digest == before.config_digest

    #  and a second baseline run after observing is identical to the first
    after = MB.run_baseline(pairs, CONFIG)
    assert [(r["index"], tuple(r["triple"]), r["status"], r["code"])
            for r in after.records] == [(r["index"], tuple(r["triple"]), r["status"], r["code"])
                                        for r in before.records]
    assert after.config_digest == before.config_digest
    assert after.complete() == before.complete()


def test_observer_is_pure_and_deterministic():
    pairs = _pairs()
    trace = MB.run_baseline(pairs, CONFIG)
    a, b = CT.observe(trace), CT.observe(trace)
    assert a.digest() == b.digest()
    #  no file I/O and no fitting inside the observer's module-level code path
    source = (ROOT / "cora_tti" / "candidate_trace.py").read_text()
    tree = pyast.parse(source)
    called = {n.func.attr for n in pyast.walk(tree)
              if isinstance(n, pyast.Call) and isinstance(n.func, pyast.Attribute)}
    assert not (called & {"fit_outcome", "fit_induced_occurrences", "evaluate",
                          "run_baseline", "write_text", "open"}), called
    imported = set()
    for node in pyast.walk(tree):
        if isinstance(node, pyast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, pyast.Import):
            imported.update(a.name for a in node.names)
    assert not any("constructive_dataset" in m or "constructive_v2c" in m
                   for m in imported), imported


def test_observer_runtime_cost_is_measured_and_small():
    pairs = _pairs()
    started = time.perf_counter()
    trace = MB.run_baseline(pairs, CONFIG)
    baseline_seconds = time.perf_counter() - started
    view = CT.observe(trace)
    assert view.observation_seconds > 0
    #  the observation is a parse of records the baseline already produced
    assert view.observation_seconds < baseline_seconds, (
        view.observation_seconds, baseline_seconds)


# ---------------------------------------------------------- data access ---

def test_observer_api_cannot_receive_the_target():
    forbidden = {"schema", "target", "concrete", "digest", "family", "seed",
                 "regime", "split", "episode"}
    assert set(inspect.signature(CT.observe).parameters) == {"trace"}
    assert set(inspect.signature(CT.aggregate_view).parameters) == {"trace"}
    for fn in (CT.observe, CT.aggregate_view):
        assert not (set(inspect.signature(fn).parameters) & forbidden)


def test_records_carry_only_baseline_derived_fields():
    pairs = _pairs()
    view = CT.observe(MB.run_baseline(pairs, CONFIG))
    allowed = {"index", "partition", "predicate", "feature", "status", "code",
               "detail_class", "cells_covered", "cells_changed",
               "coverage_fraction", "conflict_block", "witnesses_seen",
               "witnesses_required", "missing"}
    for record in view.records:
        assert set(record.to_json()) == allowed
        assert record.partition in CV.vocab()["partitions"]
        assert record.predicate in CV.vocab()["predicates"]
        assert record.feature in CV.vocab()["key_features"]


# ------------------------------------------------------------- evidence ---

def test_unknown_is_explicit_and_never_a_default_number():
    pairs = _pairs()
    view = CT.observe(MB.run_baseline(pairs, CONFIG))
    for record in view.records:
        for name in CT.EXPECTED_FIELDS:
            value = getattr(record, name)
            if value is CT.UNKNOWN:
                assert name in record.missing
            else:
                assert name not in record.missing
    report = view.coverage_report()
    assert report["records"] == len(view.records)
    assert set(report["populated_fields"]) == set(CT.EXPECTED_FIELDS)


def test_association_is_recovered_where_the_aggregate_view_loses_it():
    """The point of the observer: the aggregate marginal can be constant while
    the candidate association is not."""
    pairs = _pairs()
    trace = MB.run_baseline(pairs, CONFIG)
    view = CT.observe(trace)
    aggregate = CT.aggregate_view(trace)
    #  every candidate keeps its own verdict
    assert len({(r.partition, r.predicate, r.feature) for r in view.records}) == len(view.records)
    #  the aggregate keeps at most one number per partition and per code
    assert len(aggregate["failures_by_partition"]) <= 4
    #  graded coverage evidence exists in the association and nowhere in the aggregate
    graded = [r.coverage_fraction for r in view.records if r.coverage_fraction is not CT.UNKNOWN]
    assert graded, "no graded coverage evidence was recovered"
    assert "coverage" not in json.dumps(aggregate)


def test_observer_cannot_turn_a_rejection_into_an_acceptance():
    pairs = _pairs()
    trace = MB.run_baseline(pairs, CONFIG)
    view = CT.observe(trace)
    accepted_codes = {r.status for r in view.records}
    assert accepted_codes <= {"EXACT_DEMONSTRATION_FIT", "CONSTRAINT_CONSISTENT_BINDING",
                              "FIT_FAILURE", "EXECUTION_ERROR", "RESOURCE_EXHAUSTED"}
    exact_in_view = sum(1 for r in view.records if r.status == "EXACT_DEMONSTRATION_FIT")
    assert exact_in_view == len(trace.exact)


def test_detail_parser_marks_unrecognized_forms_unknown():
    fake = type("T", (), {"records": [
        {"index": 0, "triple": ["colour_components", "all", "area"],
         "status": "FIT_FAILURE", "code": "scoped_fit_failed",
         "detail": "a form the parser has never seen"}],
        "config_digest": "x", "census": {}, "work_done": 1, "enumerated_total": 1})()
    view = CT.observe(fake)
    record = view.records[0]
    assert record.detail_class is None
    assert view.unparsed_details == 1
    assert set(record.missing) == set(CT.EXPECTED_FIELDS)
    assert record.coverage_fraction is CT.UNKNOWN
