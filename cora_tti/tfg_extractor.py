"""ARC Typed-Failure-Graph extractor: real search state -> ConcreteTFG (P2).

This is the bridge between the live engine and everything learned. It runs the
PUBLIC trace-instrumented search (level4_blind_runtime.stepA_trace_search — the
frozen search body with additive observer hooks) on a task's demonstration
pairs and, when the search fails, converts the mechanistic wreckage into the
domain-general TFG the localizer, GPN and reasoning world model consume:

    - demonstration evidence: per-pair delta / palette / shape signatures;
    - the FAILURE FRONTIER: candidates that typed and (partly) fitted but did
      not reproduce the demonstrations — for each, its root operation, surface
      size, outcome class, and (for executed-not-exact terms) a value
      signature of HOW its rendering differed;
    - slot evidence: which fits failed, per root operation;
    - resource evidence: truncation causes (deadline, caps) as cause nodes;
    - search statistics on the execution node.

Identity discipline: production names ARE language structure, not task
identity, and appear legitimately (Step A's frontier records carry frontier
ASTs for the same reason). In the operator-dropout training context the
withheld production cannot leak through here BY CONSTRUCTION: it is absent
from the crippled language, so no enumerated term can contain it. Task ids
and family labels never enter (the TFG constructor rejects them).

Nondeterminism boundary: how far enumeration gets before the deadline is
timing-dependent, so two extractions of the same failing task may differ in
WHICH frontier terms they carry (never in the demonstration evidence). That is
the same deadline boundary the whole project already accepts; consumers must
not assume digest-stability across runs, only within a serialized graph.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V                    # noqa: E402
from level4_blind_runtime import env as E                        # noqa: E402
from level4_blind_runtime import stepA_trace_search as TS        # noqa: E402

from cora_parent.tfg import ConcreteTFG, TFGEdge, TFGNode        # noqa: E402

#: outcomes that constitute the failure frontier, nearest-miss first
FRONTIER_OUTCOMES = ("executed_not_exact", "slot_fit_failed")
MAX_FRONTIER_TERMS = 12


def _palette(grid: np.ndarray) -> set:
    return set(int(v) for v in np.unique(grid))


def _canonical_ast(ast) -> str:
    return json.dumps(ast, sort_keys=True, default=list)


def _demo_nodes(pairs) -> tuple[list, list]:
    nodes, edges = [], []
    for index, (grid_in, grid_out) in enumerate(pairs):
        din = f"delta{index}"
        same_shape = grid_in.shape == grid_out.shape
        nodes.append(TFGNode(din, "delta_signature", "", {
            "same_shape": bool(same_shape),
            "shrinks": bool(grid_out.size < grid_in.size),
            "grows": bool(grid_out.size > grid_in.size)}))
        edges.append(TFGEdge(din, "blocks", "goal"))
        pin, pout = _palette(grid_in), _palette(grid_out)
        nodes.append(TFGNode(f"palette{index}", "palette_change", "", {
            "introduced": len(pout - pin), "removed": len(pin - pout),
            "n_in": len(pin), "n_out": len(pout)}))
        edges.append(TFGEdge(f"palette{index}", "observed_on", din))
        if same_shape:
            changed = int(np.count_nonzero(grid_in != grid_out))
            nodes.append(TFGNode(f"shape{index}", "shape_change", "", {
                "cells_changed": changed,
                "fraction_changed": round(changed / grid_in.size, 4)}))
            edges.append(TFGEdge(f"shape{index}", "observed_on", din))
    return nodes, edges


def _mismatch_signature(ast, pairs, env) -> Mapping[str, Any] | None:
    """HOW an executed-not-exact term differs from the target, on the first
    demonstration where it is defined: wrong shape, or cell disagreement.

    The observer records the SLOTTED surface AST, and a raw slot inside a
    higher-order position is outside the oracle's input domain (it raises;
    see the batched-executor suite) — so evaluation failures here degrade to
    "undefined" evidence rather than crashing the extraction."""
    for grid_in, grid_out in pairs:
        try:
            rendered = E.evaluate(ast, grid_in, env)
        except Exception:
            return {"defined": False}
        if rendered is None:
            continue
        if rendered.shape != grid_out.shape:
            return {"defined": True, "shape_matches": False,
                    "rendered_cells": int(rendered.size),
                    "target_cells": int(grid_out.size)}
        wrong = int(np.count_nonzero(rendered != grid_out))
        return {"defined": True, "shape_matches": True,
                "cells_wrong": wrong,
                "fraction_wrong": round(wrong / grid_out.size, 4),
                "palette_extra": len(_palette(rendered) - _palette(grid_out))}
    return {"defined": False}


def build_tfg(pairs, stats, observer: TS.TraceObserver, env,
              goal_type: str = "Grid",
              max_frontier_terms: int = MAX_FRONTIER_TERMS) -> ConcreteTFG:
    nodes = [TFGNode("goal", "goal", goal_type)]
    edges = []
    demo_nodes, demo_edges = _demo_nodes(pairs)
    nodes += demo_nodes
    edges += demo_edges

    #  outcome census over every candidate the search actually judged
    census: dict = {}
    for _, outcome in observer.candidates:
        census[outcome] = census.get(outcome, 0) + 1

    #  the frontier: nearest misses first (executed-not-exact, with a value
    #  signature of HOW they missed), then slot-fit failures as capped
    #  representatives — in this engine an unsolvable task's dominant frontier
    #  evidence IS slot_fit_failed (measured: 2736/2736 on the probe fixture),
    #  so demoting it to aggregates would empty the frontier exactly when the
    #  invention mechanism needs it most. Representatives prefer the smallest
    #  surface (nearest to the goal in program space); dedup by canonical AST.
    seen, taken = set(), 0
    slot_fail_by_op: dict = {}
    for ast, outcome in observer.candidates:
        if outcome == "slot_fit_failed":
            op = ast[0] if isinstance(ast, tuple) else str(ast)
            slot_fail_by_op[op] = slot_fail_by_op.get(op, 0) + 1

    def frontier_candidates():
        for ast, outcome in observer.candidates:
            if outcome == "executed_not_exact":
                yield 0, E.surface_nodes(ast, env), ast, outcome
        for ast, outcome in observer.candidates:
            if outcome == "slot_fit_failed":
                yield 1, E.surface_nodes(ast, env), ast, outcome

    for _, surface, ast, outcome in sorted(frontier_candidates(),
                                           key=lambda row: (row[0], row[1],
                                                            _canonical_ast(row[2]))):
        if taken >= max_frontier_terms:
            break
        key = _canonical_ast(ast)
        if key in seen:
            continue
        seen.add(key)
        op = ast[0] if isinstance(ast, tuple) else str(ast)
        node_id = f"frontier{taken}"
        nodes.append(TFGNode(node_id, "frontier_term",
                             str(E.type_of(ast, env) or ""),
                             {"op": op, "outcome": outcome,
                              "surface_nodes": surface,
                              "ast": key}))
        edges.append(TFGEdge(node_id, "fails", "goal"))
        if outcome == "executed_not_exact":
            signature = _mismatch_signature(ast, pairs, env)
            if signature is not None:
                sig_id = f"vsig{taken}"
                nodes.append(TFGNode(sig_id, "value_signature", "", signature))
                edges.append(TFGEdge(sig_id, "observed_on", node_id))
        taken += 1

    for index, (op, count) in enumerate(sorted(slot_fail_by_op.items())):
        node_id = f"slotfail{index}"
        nodes.append(TFGNode(node_id, "slot", "", {"op": op, "failures": count}))
        edges.append(TFGEdge(node_id, "fails", "goal"))

    for index, kind in enumerate(sorted(observer.truncations)):
        node_id = f"cause{index}"
        nodes.append(TFGNode(node_id, "cause", "", {"truncation": kind}))
        edges.append(TFGEdge(node_id, "blocks", "goal"))

    nodes.append(TFGNode("search", "execution", "", {
        "typed": int(stats.typed), "generated": int(stats.generated),
        "rejected": int(stats.rejected), "max_depth": int(stats.max_depth),
        "semantic_classes": int(stats.semantic_classes),
        "outcome_census": {k: census[k] for k in sorted(census)},
        "deadline_hit": bool(stats.seconds >= TS.budget_s() - 0.01)}))
    edges.append(TFGEdge("search", "fails", "goal"))
    return ConcreteTFG(goal_type, goal_type, nodes, edges)


def extract(pairs, env: E.LanguageEnv | None = None, budget_s: float = 2.0,
            goal=V.GRID, max_frontier_terms: int = MAX_FRONTIER_TERMS) -> dict:
    """Run the trace-instrumented search; on failure return the TFG.

    Returns {"solved": bool, "tfg": ConcreteTFG | None, "programs": ranked
    exact programs when solved, "stats": SearchStats}. The observer is always
    uninstalled afterwards, whatever happens."""
    env = env if env is not None else E.BASE_ENV
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in pairs]
    observer = TS.TraceObserver()
    TS.set_observer(observer)
    try:
        deadline = time.monotonic() + budget_s
        results, stats = TS.search(pairs, deadline=deadline, env=env)
    finally:
        TS.set_observer(None)
    if results:
        return {"solved": True, "tfg": None, "programs": results, "stats": stats}
    tfg = build_tfg(pairs, stats, observer, env, str(goal), max_frontier_terms)
    return {"solved": False, "tfg": tfg, "programs": [], "stats": stats}
