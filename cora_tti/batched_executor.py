"""Semantics-preserving batched executor (phase P2; master plan §VI).

The competition workload evaluates THOUSANDS of candidate programs against the
same few demonstration grids, and those candidates share structure massively
(the same partition/select subterms appear under every candidate; plug-in
proposal reuses one port subterm across a whole vocabulary). The exact
interpreter recomputes every shared subterm per candidate. This module removes
that redundancy WITHOUT touching operator meaning:

  - the evaluation spine mirrors ``runtime._eval`` dispatch branch for branch
    (the higher-order special cases — Map_V1, Key, Lookup, Compose_V1 — are
    delegated to the very same production callables, which internally recurse
    through the untouched oracle evaluator);
  - results of eagerly-evaluated subterms are cached per (subterm, grid) at
    the top-level grid context only (element/value contexts are never cached:
    they are inner-loop states owned by the oracle's own code);
  - the CPU oracle ``env.evaluate`` remains the reference; the differential
    suite requires bit-identical agreement (None included) on randomized
    program/grid batches — zero mismatch tolerated.

This is the sharing layer of the §VI design. A tensorized kernel backend
(L4-class GPUs) can later replace individual production evaluations behind the
same interface; every such kernel inherits the same differential obligation.
The executor ACCELERATES; it never certifies (multi-fidelity rule VII).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V          # noqa: E402
from level4_blind_runtime import env as E              # noqa: E402

#: ops whose arguments are (partly) RAW ASTs in ``runtime._eval``; they are
#: delegated whole to the oracle's production callables and never memo-recursed
_HIGHER_ORDER = ("Map_V1", "Key", "Lookup", "Compose_V1")


def _ast_key(node) -> str:
    return json.dumps(node, sort_keys=True, default=list)


class BatchedExecutor:
    """Shared-subterm exact evaluation of many programs over a set of grids."""

    def __init__(self, env: E.LanguageEnv | None = None):
        self.env = env if env is not None else E.BASE_ENV
        self._grids: list[np.ndarray] = []
        self._memo: dict = {}
        self.stats = {"hits": 0, "misses": 0, "delegated": 0}

    # -- grid registration --------------------------------------------------
    def _grid_index(self, grid: np.ndarray) -> int:
        grid = np.asarray(grid)
        key = (grid.shape, grid.tobytes())
        for index, known in enumerate(self._grids):
            if (known.shape, known.tobytes()) == key:
                return index
        self._grids.append(grid)
        return len(self._grids) - 1

    # -- the memoizing spine (mirrors runtime._eval EXACTLY) ---------------
    def _eval_spine(self, node, ctx, grid_index: int, cacheable: bool):
        if not V.is_ast(node):
            return None
        op, args = node
        production = V.REGISTRY[op]
        if op in _HIGHER_ORDER:
            #  identical to runtime._eval's special branches: raw ASTs go to
            #  the oracle's own callables (their inner recursion is oracle code)
            self.stats["delegated"] += 1
            if op == "Map_V1":
                sets = (self._eval_spine(args[0], ctx, grid_index, cacheable)
                        if V.is_ast(args[0]) else args[0])
                return production.evaluate(ctx, sets, args[1])
            if op in ("Key", "Lookup"):
                return production.evaluate(ctx, args[0])
            return production.evaluate(ctx, args[0], args[1])       # Compose_V1
        key = None
        if cacheable:
            key = (grid_index, _ast_key(node))
            if key in self._memo:
                self.stats["hits"] += 1
                return self._memo[key]
            self.stats["misses"] += 1
        values = []
        for arg in args:
            if V.is_ast(arg):
                child = self._eval_spine(arg, ctx, grid_index, cacheable)
                if child is None:
                    if key is not None:
                        self._memo[key] = None
                    return None
                values.append(child)
            elif isinstance(arg, str) and arg.startswith("?"):
                if key is not None:
                    self._memo[key] = None
                return None
            else:
                values.append(arg)
        try:
            result = production.evaluate(ctx, *values)
        except Exception:
            result = None
        if key is not None:
            self._memo[key] = result
        return result

    # -- public API ---------------------------------------------------------
    def evaluate(self, program, grid) -> np.ndarray | None:
        """Exact equivalent of ``env.evaluate(program, grid, env)``."""
        core = E.expand(program, self.env)
        if core is None:
            return None
        grid = np.asarray(grid)
        index = self._grid_index(grid)
        #  cacheable: the TOP-LEVEL grid context only (element/value unset),
        #  exactly the Ctx the oracle builds in V.evaluate
        value = self._eval_spine(core, V.Ctx(grid), index, cacheable=True)
        return value if isinstance(value, np.ndarray) else None

    def evaluate_batch(self, programs: Sequence, grids: Sequence) -> list:
        """[[result for each grid] for each program]; identical to looping the
        oracle, minus the redundant recomputation of shared subterms."""
        return [[self.evaluate(p, g) for g in grids] for p in programs]

    def reset(self) -> None:
        self._grids.clear()
        self._memo.clear()
        self.stats = {"hits": 0, "misses": 0, "delegated": 0}


# --------------------------------------------------------------------------
# differential harness (the executor's standing obligation)
# --------------------------------------------------------------------------

def differential_check(programs: Sequence, grids: Sequence,
                       env: E.LanguageEnv | None = None) -> dict:
    """Compare the batched executor against the oracle on every (program, grid).

    Returns counts and the first mismatch (there must never be one). Used by
    the test suite and REQUIRED for any future accelerated backend."""
    env = env if env is not None else E.BASE_ENV
    executor = BatchedExecutor(env)
    checked = agree = defined = 0
    first_mismatch = None
    for p_index, program in enumerate(programs):
        for g_index, grid in enumerate(grids):
            oracle = E.evaluate(program, grid, env)
            fast = executor.evaluate(program, grid)
            checked += 1
            same = ((oracle is None and fast is None)
                    or (oracle is not None and fast is not None
                        and oracle.shape == fast.shape
                        and np.array_equal(oracle, fast)))
            agree += same
            defined += oracle is not None
            if not same and first_mismatch is None:
                first_mismatch = {"program_index": p_index, "grid_index": g_index}
    return {"checked": checked, "agree": agree, "defined": defined,
            "mismatches": checked - agree, "first_mismatch": first_mismatch,
            "cache": dict(executor.stats)}
