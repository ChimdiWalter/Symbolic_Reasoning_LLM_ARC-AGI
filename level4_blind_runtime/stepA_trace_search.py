"""Type-directed search for CORA V2.1.

One enumerator over the contract-derived registry, one slot-learner registry
keyed by type, deduplication AMONG EXACT-FIT candidates, and leave-one-out by
re-running the whole discovery on N-1 demonstrations.

The deduplication claim is deliberately narrow: ``observational_signature``
returns None unless a program already reproduces every demonstration, so
what is kept is the cheapest EXACT program, not a general intermediate
semantic cache. That is sufficient for this experiment and is not described
as more than it is.

Nothing here knows what an ARC task family is. A production is tried because
its result type matches the goal, and a slot is fitted because of its declared
type. Rules the contract marks inactive are not in the registry at all, so
they cannot be reached even by accident.

PROJECTED from meta_v21_search.py for the Level-4 blind environment by
scripts/cora_level4_build_blind_runtime.py. The body is unchanged except
for its imports, which are rewired to the blind runtime, so search policy,
slot learners, costs and budgets are identical to the frozen runtime.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import runtime as V
from . import env as E
# --- TRACE PROLOGUE BEGIN ---
# Inserted by scripts/cora_level4_build_trace_search.py. Everything below
# this comment and above the END marker is additive: it defines an observer
# and a way to install one. No name defined here is read by any line of the
# frozen body except through the ``_OBS`` calls, each of which is tagged
# ``# TRACE`` and returns None.


class _NullObserver:
    """The default: every hook is a no-op, so behaviour is the frozen one."""

    def term(self, wanted, depth, ast):
        pass

    def truncate(self, kind):
        pass

    def maybe_deadline(self, deadline):
        pass

    def candidate(self, ast, outcome):
        pass


class TraceObserver:
    """Records what arose. Appends only; no serialization while timed."""

    def __init__(self):
        self.terms = []
        self.truncations = set()
        self.candidates = []

    def term(self, wanted, depth, ast):
        self.terms.append((str(wanted), depth, ast))

    def truncate(self, kind):
        self.truncations.add(kind)

    def maybe_deadline(self, deadline):
        if time.monotonic() > deadline:
            self.truncations.add("deadline_depth_loop")

    def candidate(self, ast, outcome):
        self.candidates.append((ast, outcome))


_OBS = _NullObserver()


def set_observer(observer):
    """Install an observer for the next search; None restores the no-op."""
    global _OBS
    _OBS = observer if observer is not None else _NullObserver()
# --- TRACE PROLOGUE END ---


def budget_s() -> float:
    try:
        return float(os.environ.get("ARC_META_BUDGET_S", "8"))
    except ValueError:
        return 8.0


MAX_DEPTH = 5
PER_TYPE_CAP = 4000
MAX_CANDIDATES = 8


# --------------------------------------------------------------------------
# slot learners, keyed by declared type
# --------------------------------------------------------------------------

@dataclass
class LearnedValue:
    value: object
    support: int = 0
    observations: int = 0
    fold_coverable: bool = False
    cost: int = 0

    def as_dict(self) -> dict:
        return {"support": self.support, "observations": self.observations,
                "fold_coverable": self.fold_coverable, "cost": self.cost}


def _changed(grid_in, grid_out):
    return {(r, c) for r in range(grid_in.shape[0])
            for c in range(grid_in.shape[1])
            if int(grid_in[r, c]) != int(grid_out[r, c])}


def learn_feature_colour_map(ast, pairs, slot) -> Optional[LearnedValue]:
    """Fit the key-to-colour table under whatever the AST already selects.

    The set source and the feature are located BY TYPE inside the AST, so
    this learner is not tied to any particular pipeline shape. A key
    witnessed by a single demonstration is refused: the fold that holds that
    demonstration out could not refit it.
    """
    source = _resolved_of_type(ast, V.SET_REGION)
    feature = _terminal_of_type(ast, V.FEATURE_EXPR)
    if source is None or feature is None:
        return None
    table: dict = {}
    seen: dict = {}
    observations = 0
    for index, (grid_in, grid_out) in enumerate(pairs):
        if grid_in.shape != grid_out.shape:
            return None
        sets = V._eval(source, V.Ctx(grid_in))
        if not sets:
            return None
        changed = _changed(grid_in, grid_out)
        if not changed:
            return None
        covered = set()
        for cells in sets:
            touched = {cell for cell in cells if cell in changed}
            if not touched:
                continue
            if touched != set(cells):
                return None
            colours = {int(grid_out[r, c]) for r, c in cells}
            if len(colours) != 1:
                return None
            colour = colours.pop()
            key = V.descriptors(cells, grid_in).get(feature)
            if key is None:
                return None
            if table.get(key, colour) != colour:
                return None
            table[key] = colour
            seen.setdefault(key, set()).add(index)
            covered |= set(cells)
            observations += 1
        if covered != changed:
            return None
    if not table or any(len(seen[k]) < 2 for k in table):
        return None
    return LearnedValue(
        value=tuple(sorted(table.items(), key=lambda kv: repr(kv[0]))),
        support=min(len(v) for v in seen.values()),
        observations=observations, fold_coverable=True, cost=len(table))


SLOT_LEARNERS = {str(V.COLOUR_MAP): learn_feature_colour_map}


def _resolved_of_type(ast, wanted: V.Type):
    """Outermost slot-free sub-AST whose result type is ``wanted``."""
    found = []

    def walk(node):
        if not V.is_ast(node):
            return
        result = V.REGISTRY[node[0]].result_type
        if V.type_equal(result, wanted) and not V.free_slots(node):
            found.append(node)
            return
        for arg in node[1]:
            walk(arg)

    walk(ast)
    return found[0] if found else None


def _terminal_of_type(ast, wanted: V.Type):
    """First resolved terminal argument of ``wanted`` type, anywhere."""
    result = []

    def walk(node):
        if not V.is_ast(node) or result:
            return
        production = V.REGISTRY[node[0]]
        for arg, expected in zip(node[1], production.arg_types):
            if V.is_ast(arg):
                walk(arg)
            elif V.type_equal(expected, wanted) and \
                    not (isinstance(arg, str) and arg.startswith("?")):
                result.append(arg)
                return

    walk(ast)
    return result[0] if result else None


def fit_slots(ast, pairs, memo=None, env=None):
    """Fill induced slots by declared type, iterating to a fixed point.

    When an environment carrying learned concepts is supplied, the AST is a
    SURFACE program: it is elaborated into kernel productions, the ordinary
    learner runs on that elaboration, and the fitted values are substituted
    back into the surface program. No concept-specific learner exists.
    """
    if env is not None and env.concepts:
        core = E.expand(ast, env)
        if core is None:
            return None, {}
        fitted_core, evidence = fit_slots(core, pairs, memo)
        if fitted_core is None:
            return None, {}
        bindings = _recover_bindings(core, fitted_core)
        return E.instantiate(ast, bindings, env), evidence
    slots = V.free_slots(ast)
    if not slots:
        return ast, {}
    current = ast
    evidence: dict = {}
    pending = dict(slots)
    while pending:
        progressed = False
        for slot, slot_type in list(pending.items()):
            learner = SLOT_LEARNERS.get(str(slot_type))
            if learner is None:
                return None, {}
            key = (str(slot_type), json.dumps(V.to_json(current), sort_keys=True))
            if memo is not None and key in memo:
                learned = memo[key]
            else:
                learned = learner(current, pairs, slot)
                if memo is not None:
                    memo[key] = learned
            if learned is None:
                continue
            current = V.instantiate(current, {slot: learned.value})
            evidence[slot] = learned.as_dict()
            del pending[slot]
            progressed = True
        if not progressed:
            return None, {}
    return current, evidence


def _recover_bindings(before, after) -> dict:
    """Which value each slot received, read off the fitted elaboration."""
    bindings: dict = {}

    def walk(a, b):
        if isinstance(a, str) and a.startswith("?"):
            bindings[a] = b
            return
        if V.is_ast(a) and V.is_ast(b):
            for x, y in zip(a[1], b[1]):
                walk(x, y)

    walk(before, after)
    return bindings


# --------------------------------------------------------------------------
# enumeration
# --------------------------------------------------------------------------

@dataclass
class SearchStats:
    generated: int = 0
    typed: int = 0
    semantic_classes: int = 0
    rejected: int = 0
    max_depth: int = 0
    seconds: float = 0.0

    def as_dict(self) -> dict:
        return {"generated": self.generated, "typed_candidates": self.typed,
                "semantic_classes": self.semantic_classes,
                "rejected": self.rejected, "max_depth": self.max_depth,
                "seconds": round(self.seconds, 3)}


def _values_of_type(wanted: V.Type, depth, cache, stats, deadline, env):
    key = str(wanted)
    if key in V.TERMINAL_VALUES:
        return list(V.TERMINAL_VALUES[key])
    if key in V.INDUCED_TYPES:
        return [f"?{key}"]
    return _asts_of_type(wanted, depth, cache, stats, deadline, env)


def _asts_of_type(wanted: V.Type, depth, cache, stats, deadline, env):
    if depth <= 0:
        return []
    key = (str(wanted), depth)
    if key in cache:
        return cache[key]
    cache[key] = []
    out = []
    for name in sorted(env.names):
        if not V.type_equal(env.result_type(name), wanted):
            continue
        if time.monotonic() > deadline:
            _OBS.truncate("deadline_enumeration")  # TRACE
            break
        options = []
        viable = True
        for arg_type in env.arg_types(name):
            values = _values_of_type(arg_type, depth - 1, cache, stats,
                                     deadline, env)
            if not values:
                viable = False
                break
            options.append(values)
        if not viable:
            continue
        for combination in _product(options):
            out.append((name, combination))
            _OBS.term(wanted, depth, (name, combination))  # TRACE
            stats.generated += 1
            if len(out) >= PER_TYPE_CAP:
                _OBS.truncate("per_type_cap")  # TRACE
                break
        if len(out) >= PER_TYPE_CAP:
            _OBS.truncate("per_type_cap")  # TRACE
            break
    cache[key] = out
    return out


def _product(option_lists):
    if not option_lists:
        yield ()
        return
    head, rest = option_lists[0], option_lists[1:]
    for value in head:
        for tail in _product(rest):
            yield (value,) + tail


def observational_signature(ast, pairs, env=None):
    """Rendered behaviour, but only for programs that already fit exactly.

    Two exact programs necessarily render the same demonstration outputs, so
    this deduplicates among exact fits rather than among arbitrary
    sub-programs.
    """
    env = env if env is not None else E.BASE_ENV
    out = []
    for grid_in, grid_out in pairs:
        rendered = E.evaluate(ast, grid_in, env)
        if rendered is None or not np.array_equal(rendered, grid_out):
            return None
        out.append(rendered.tobytes())
    return tuple(out)


def search(pairs, deadline=None, goal=V.GRID, env=None):
    """Discovered programs reproducing every demonstration, cheapest first.

    Both experiment arms call this one function; only ``env`` differs.
    """
    env = env if env is not None else E.BASE_ENV
    stats = SearchStats()
    started = time.monotonic()
    own = started + budget_s()
    deadline = own if deadline is None else min(deadline, own)
    by_signature: dict = {}
    memo: dict = {}
    for depth in range(1, MAX_DEPTH + 1):
        _OBS.maybe_deadline(deadline)  # TRACE
        if time.monotonic() > deadline or by_signature:
            break
        cache: dict = {}
        frontier = []
        for ast in _asts_of_type(goal, depth, cache, stats, deadline, env):
            if E.surface_depth(ast, env) != depth:
                continue
            frontier.append(ast)
        frontier.sort(key=lambda a: (E.surface_nodes(a, env),
                                     E.surface_value_bound(a, env),
                                     json.dumps(E.to_json(a, env), sort_keys=True)))
        for ast in frontier:
            if time.monotonic() > deadline:
                _OBS.truncate("deadline_candidates")  # TRACE
                break
            if E.type_of(ast, env) is None:
                _OBS.candidate(ast, "typecheck_failed")  # TRACE
                continue
            stats.typed += 1
            _OBS.candidate(ast, "typed")  # TRACE
            stats.max_depth = max(stats.max_depth, depth)
            complete, evidence = fit_slots(ast, pairs, memo, env)
            if complete is None:
                _OBS.candidate(ast, "slot_fit_failed")  # TRACE
                stats.rejected += 1
                continue
            _OBS.candidate(ast, "slot_fit_ok")  # TRACE
            _OBS.term(goal, depth, complete)  # TRACE
            signature = observational_signature(complete, pairs, env)
            if signature is None:
                _OBS.candidate(ast, "executed_not_exact")  # TRACE
                stats.rejected += 1
                continue
            _OBS.candidate(ast, "exact")  # TRACE
            previous = by_signature.get(signature)
            if previous is None or E.surface_nodes(complete, env) < \
                    E.surface_nodes(previous[0], env):
                by_signature[signature] = (complete, evidence)
    stats.seconds = time.monotonic() - started
    stats.semantic_classes = len(by_signature)
    ranked = sorted(by_signature.values(),
                    key=lambda ce: (E.surface_nodes(ce[0], env),
                                    E.surface_value_bound(ce[0], env),
                                    json.dumps(E.to_json(ce[0], env), sort_keys=True)))
    return ranked[:MAX_CANDIDATES], stats


def loo_by_rediscovery(pairs, env=None):
    """Re-run the WHOLE discovery on N-1 pairs and predict the held-out one."""
    if len(pairs) < 2:
        return 0, 0
    passed = 0
    for held in range(len(pairs)):
        subset = [p for i, p in enumerate(pairs) if i != held]
        results, _ = search(subset, env=env)
        if not results:
            continue
        grid_in, grid_out = pairs[held]
        predicted = E.evaluate(results[0][0], grid_in,
                               env if env is not None else E.BASE_ENV)
        if predicted is not None and np.array_equal(predicted, grid_out):
            passed += 1
    return passed, len(pairs)
