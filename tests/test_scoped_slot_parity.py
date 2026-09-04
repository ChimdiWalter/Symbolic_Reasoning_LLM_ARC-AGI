"""Single-block conservativity gate (protocol v2 section 11).

Over the COMPLETE family-(1,) baseline space (4 partitions x 5 predicates x
10 key features = 200 schemas) and deterministic demonstration sets, the
occurrence-scoped fitter must agree with the v1.1 learner: identical verdicts,
identical rendered behaviour, and no expansion of single-block reach. A
mismatch is a feasibility-gate failure, not a warning.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402


def _demo_sets(n_sets: int = 6, n_demos: int = 5) -> list:
    """Deterministic demonstration sets built by transforming generated grids
    with a fixed recolouring, so both fitters see identical evidence."""
    sets = []
    for s in range(n_sets):
        pairs = []
        for d in range(n_demos):
            grid = CD.generate_grid(50_000 + s * 101 + d)
            out = grid.copy()
            #  a simple, fitter-agnostic transformation: recolour by parity of
            #  the cell value, leaving background alone
            out[(grid % 2 == 1) & (grid > 0)] = 5
            out[(grid % 2 == 0) & (grid > 0)] = 7
            if not np.array_equal(out, grid):
                pairs.append((grid, out))
        if len(pairs) >= 3:
            sets.append(pairs)
    return sets


def _old_verdict(schema, pairs):
    fitted = MI.fit_induced_slots(schema, pairs)
    if fitted is None:
        return False, None
    if MI.observational_signature(fitted, pairs) is None:
        return False, None
    return True, fitted


def _new_verdict(schema, pairs):
    fitted, evidence = SF.fit_induced_occurrences(schema, pairs)
    return fitted is not None, fitted


@pytest.mark.parametrize("set_index", range(4))
def test_single_block_parity_over_full_baseline_space(set_index):
    demo_sets = _demo_sets()
    if set_index >= len(demo_sets):
        pytest.skip("fewer deterministic demo sets than parametrized")
    pairs = demo_sets[set_index]
    schemas = SF.baseline_single_block_schemas()
    assert len(schemas) == 200
    mismatches, old_ok, new_ok = [], 0, 0
    for schema in schemas:
        o_ok, o_fit = _old_verdict(schema, pairs)
        n_ok, n_fit = _new_verdict(schema, pairs)
        old_ok += o_ok
        new_ok += n_ok
        if o_ok != n_ok:
            mismatches.append((schema[1][0][1][0], schema[1][1][1][0],
                               schema[1][2][1][0][1][0], o_ok, n_ok))
            continue
        if o_ok and n_ok:
            for grid_in, grid_out in pairs:
                a = M.evaluate(o_fit, grid_in, MI.descriptors)
                b = M.evaluate(n_fit, grid_in, MI.descriptors)
                assert (a is None) == (b is None)
                if a is not None:
                    assert np.array_equal(a, b), "rendering divergence"
    assert not mismatches, (
        f"verdict divergence on {len(mismatches)} of 200 schemas "
        f"(old_ok={old_ok}, new_ok={new_ok}): {mismatches[:5]}")


def test_no_expansion_of_baseline_reach():
    """Aggregate across all demo sets: the scoped fitter must never succeed
    where the v1.1 learner fails, within family (1,)."""
    expansions = []
    for pairs in _demo_sets():
        for schema in SF.baseline_single_block_schemas():
            o_ok, _ = _old_verdict(schema, pairs)
            n_ok, _ = _new_verdict(schema, pairs)
            if n_ok and not o_ok:
                expansions.append(schema)
    assert not expansions, f"{len(expansions)} new-success/old-failure cases"


def test_fitter_identity_is_stable_and_recorded():
    a = SF.fitter_identity()
    assert a == SF.fitter_identity() and len(a) == 64
    report = SF.base_search_with_scoped_fitter(_demo_sets()[0])
    assert report["fitter"] == a[:16]
    assert report["enumerated"] == 200
