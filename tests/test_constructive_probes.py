"""Frozen probe-set gates (Block B section 5)."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti import constructive_probes as CP   # noqa: E402


def _ev(ast, grid):
    """A trivial evaluator stand-in: ast is a callable in these tests."""
    return ast(grid)


def test_exact_count_and_ranges_from_manifest():
    config = CP.probe_config()
    grids = CP.probes()
    assert len(grids) == config["count"] == 16
    for grid in grids:
        assert config["min_size"] <= grid.shape[0] <= config["max_size"]
        assert config["min_size"] <= grid.shape[1] <= config["max_size"]


def test_deterministic_regeneration_and_stable_order():
    CP.probes.cache_clear()
    first = [g.copy() for g in CP.probes()]
    CP.probes.cache_clear()
    second = CP.probes()
    assert all(np.array_equal(a, b) for a, b in zip(first, second))
    manifest_a = CP.probe_manifest()
    CP.probes.cache_clear()
    assert CP.probe_manifest() == manifest_a


def test_grid_digests_stable_and_distinct():
    rows = CP.probe_manifest()["probes"]
    assert len({r["grid_digest"] for r in rows}) >= 14
    assert [r["index"] for r in rows] == list(range(16))


def test_probe_api_takes_no_target_or_task_parameters():
    banned = {"ast", "target", "digest", "family", "split", "task_id",
              "candidate", "model", "score"}
    for name, fn in vars(CP).items():
        if inspect.isfunction(fn) and not name.startswith("_"):
            params = set(inspect.signature(fn).parameters)
            assert not params & banned, f"{name} accepts {params & banned}"


def test_none_differs_from_grid_and_shapes_cannot_collide():
    fp_none = CP.fingerprint(lambda g: None, _ev)
    fp_grid = CP.fingerprint(lambda g: g, _ev)
    assert fp_none != fp_grid
    #  1x4 of zeros and 4x1 of zeros must not collide through flattening
    a = CP.fingerprint(lambda g: np.zeros((1, 4), int), _ev)
    b = CP.fingerprint(lambda g: np.zeros((4, 1), int), _ev)
    assert a != b


def test_single_cell_change_changes_fingerprint():
    base = CP.fingerprint(lambda g: np.zeros_like(g), _ev)

    def mutated(grid):
        out = np.zeros_like(grid)
        out[0, 0] = 5
        return out
    assert CP.fingerprint(mutated, _ev) != base


def test_fingerprint_independent_of_call_order_but_position_sensitive():
    """Same renderings give the same fingerprint; permuted renderings do not."""
    fp1 = CP.fingerprint(lambda g: g * 0 + g.shape[0], _ev)
    fp2 = CP.fingerprint(lambda g: g * 0 + g.shape[0], _ev)
    assert fp1 == fp2
    fp3 = CP.fingerprint(lambda g: g * 0 + g.shape[1], _ev)
    assert fp1 != fp3


def test_admission_path_propagates_errors_audit_path_records_them():
    def boom(grid):
        raise ValueError("x")
    try:
        CP.fingerprint(boom, _ev)
        raised = False
    except ValueError:
        raised = True
    assert raised, "admission fingerprinting must not swallow errors"
    digest, status = CP.fingerprint_with_diagnostics(boom, _ev)
    assert digest and all(s.startswith("ERROR:") for s in status)
