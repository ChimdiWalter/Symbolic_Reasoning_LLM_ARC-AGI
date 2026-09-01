"""Differential + sharing tests for the batched executor. Zero mismatch is the bar."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V              # noqa: E402
from level4_blind_runtime import env as E                  # noqa: E402
from cora_tti import batched_executor as BX                # noqa: E402
from cora_tti import dropout_generator as DG               # noqa: E402


def rng(seed=0):
    return np.random.default_rng(seed)


def random_programs(n, seed=0):
    out, r = [], rng(seed)
    tries = 0
    while len(out) < n and tries < n * 60:
        tries += 1
        ast = DG.sample_ast(r, DG.GOAL, V.REGISTRY)
        if ast is not None:
            out.append(ast)
    return out


def test_differential_zero_mismatch_on_random_batch():
    programs = random_programs(120, seed=1)
    grids = [DG.random_grid(rng(100 + i)) for i in range(4)]
    report = BX.differential_check(programs, grids)
    assert report["mismatches"] == 0, report["first_mismatch"]
    assert report["checked"] == len(programs) * len(grids)
    assert report["defined"] > 0, "the batch must exercise defined programs"


def test_differential_covers_higher_order_pipelines():
    """Explicit higher-order pipelines (Map_V1 / Key / Lookup / Compose_V1).

    NOTE the domain boundary discovered by this suite's first version: a
    program with an UNFITTED slot inside a higher-order position (e.g.
    Lookup("?Map")) is outside the oracle's supported input domain —
    V.evaluate raises there, because real callers always run fit_slots first.
    The executor delegates those branches to the identical oracle callables,
    so the differential contract is defined over fitted programs only."""
    pipeline = ("PaintEach", (("Map_V1", (("Partition", ("colour_components",)),
                ("Compose_V1", (("Key", ("area",)), ("Lookup", ({1: 4, 2: 7},)))))),))
    select = ("PaintEach", (("Map_V1", (("Select",
              (("Partition", ("colour_components",)), "square")),
              ("Compose_V1", (("Key", ("colour",)), ("Lookup", ({3: 5},)))))),))
    grids = [DG.random_grid(rng(7 + i)) for i in range(5)]
    report = BX.differential_check([pipeline, select], grids)
    assert report["mismatches"] == 0, report["first_mismatch"]


def test_slot_in_generic_position_returns_none_like_oracle():
    #  a slot in a GENERIC (eagerly evaluated) position: both sides yield None
    slotted_generic = ("Select", (("Partition", ("colour_components",)), "?Predicate"))
    grid = DG.random_grid(rng(11))
    executor = BX.BatchedExecutor()
    #  oracle: generic branch returns None for '?' strings (no exception)
    assert E.evaluate(slotted_generic, grid, E.BASE_ENV) is None
    assert executor.evaluate(slotted_generic, grid) is None


def test_cache_sharing_reduces_work_and_preserves_results():
    """Many candidates sharing one port subterm: the shared Partition/Select
    spine must be computed once per grid, not once per candidate."""
    port = ("Partition", ("colour_components",))
    tables = [{k: (k % 9) + 1 for k in range(1, 4 + i % 3)} for i in range(80)]
    candidates = [("PaintEach", (("Map_V1", (port,
                   ("Compose_V1", (("Key", ("area",)), ("Lookup", (t,)))))),))
                  for t in tables]
    grids = [DG.random_grid(rng(200 + i)) for i in range(3)]

    executor = BX.BatchedExecutor()
    fast = executor.evaluate_batch(candidates, grids)
    #  identical to the oracle
    for p, row in zip(candidates, fast):
        for g, got in zip(grids, row):
            oracle = E.evaluate(p, g, E.BASE_ENV)
            assert (oracle is None) == (got is None)
            if oracle is not None:
                assert np.array_equal(oracle, got)
    #  the shared port was cached: hits must dominate misses
    assert executor.stats["hits"] > executor.stats["misses"]


def test_cache_never_leaks_between_different_grids():
    program = ("PaintEach", (("Map_V1", (("Partition", ("colour_components",)),
               ("Compose_V1", (("Key", ("colour",)),
                               ("Lookup", ({c: 9 for c in range(1, 10)},)))))),))
    g1 = np.zeros((5, 5), dtype=int); g1[1, 1] = 3
    g2 = np.zeros((5, 5), dtype=int); g2[2, 2] = 4
    executor = BX.BatchedExecutor()
    out1 = executor.evaluate(program, g1)
    out2 = executor.evaluate(program, g2)
    ref1, ref2 = E.evaluate(program, g1, E.BASE_ENV), E.evaluate(program, g2, E.BASE_ENV)
    assert (out1 is None) == (ref1 is None)
    assert (out2 is None) == (ref2 is None)
    if ref1 is not None and ref2 is not None:
        assert np.array_equal(out1, ref1) and np.array_equal(out2, ref2)
        assert not np.array_equal(out1, out2)


def test_reset_clears_state():
    executor = BX.BatchedExecutor()
    executor.evaluate(("Partition", ("colour_components",)),
                      DG.random_grid(rng(5)))
    assert executor.stats["misses"] >= 1
    executor.reset()
    assert executor.stats == {"hits": 0, "misses": 0, "delegated": 0}
    assert executor._memo == {}


def test_speedup_on_shared_structure_batch():
    """Wall-clock sanity: with heavy sharing the executor must beat the naive
    oracle loop. Threshold is deliberately conservative (loaded box)."""
    port = ("Select", (("Partition", ("colour_components",)), "all"))
    candidates = [("PaintEach", (("Map_V1", (port,
                   ("Compose_V1", (("Key", ("area",)),
                                   ("Lookup", ({j: (j % 9) + 1},)))))),))
                  for j in range(1, 61)]
    grids = [DG.random_grid(rng(300 + i)) for i in range(3)]
    t0 = time.perf_counter()
    for p in candidates:
        for g in grids:
            E.evaluate(p, g, E.BASE_ENV)
    naive = time.perf_counter() - t0
    executor = BX.BatchedExecutor()
    t0 = time.perf_counter()
    executor.evaluate_batch(candidates, grids)
    shared = time.perf_counter() - t0
    assert shared < naive, f"sharing must not be slower (naive {naive:.3f}s vs {shared:.3f}s)"
