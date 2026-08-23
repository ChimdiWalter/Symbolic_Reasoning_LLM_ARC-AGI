"""Installing inventory productions into the (frozen, on-disk-untouched)
blind runtime, for execution and testing.

The frozen ``runtime._eval`` decides by production NAME which arguments are
contextual expressions passed unevaluated (Map_V1, Key, Lookup,
Compose_V1). Inventory productions declare that per argument instead
(``arg_modes``). This module swaps in an evaluator that honours the declared
modes for installed productions and defers to the frozen evaluator for
everything else, and it restores every table on exit. Nothing on disk
changes; the blind runtime's hashes stay valid.
"""
from __future__ import annotations

from contextlib import contextmanager

from level4_blind_runtime import runtime as V
from level4_blind_runtime import search as SEARCH
from level4_blind_runtime import env as E

from . import k2_slots as S

ARG_MODES: dict = {}
_ORIGINAL_EVAL = V._eval


def _eval_extended(node, ctx):
    if not V.is_ast(node):
        return None
    op, args = node
    modes = ARG_MODES.get(op)
    if modes is None:
        return _ORIGINAL_EVAL(node, ctx)
    production = V.REGISTRY[op]
    if len(args) != len(modes):
        return None
    values = []
    for arg, mode in zip(args, modes):
        if mode == "expr":
            if not V.is_ast(arg):
                return None
            values.append(arg)
        elif V.is_ast(arg):
            child = _eval_extended(arg, ctx)
            if child is None:
                return None
            values.append(child)
        elif isinstance(arg, str) and arg.startswith("?"):
            return None
        else:
            values.append(arg)
    try:
        return production.evaluate(ctx, *values)
    except Exception:
        return None


@contextmanager
def installed(instances, learners=None, terminals=None, induced=None):
    """Temporarily add productions, terminal vocabularies, induced types and
    slot learners to the blind runtime; restore everything afterwards."""
    learners = dict(S.INDUCED if learners is None else learners)
    terminals = dict(S.TERMINALS if terminals is None else terminals)
    induced = list(S.INDUCED if induced is None else induced)
    saved = (dict(V.REGISTRY), dict(V.TERMINAL_VALUES), list(V.INDUCED_TYPES),
             dict(SEARCH.SLOT_LEARNERS), dict(ARG_MODES), V._eval)
    try:
        for name, values in terminals.items():
            V.TERMINAL_VALUES.setdefault(name, tuple(values))
        for name in induced:
            if name not in V.INDUCED_TYPES:
                V.INDUCED_TYPES.append(name)
        for name, learner in learners.items():
            SEARCH.SLOT_LEARNERS.setdefault(name, learner)
        for inst in instances:
            V.REGISTRY[inst.name] = inst.production
            ARG_MODES[inst.name] = inst.arg_modes
        V._eval = _eval_extended
        yield E.LanguageEnv(base=dict(V.REGISTRY), label="K+K2")
    finally:
        V.REGISTRY.clear()
        V.REGISTRY.update(saved[0])
        V.TERMINAL_VALUES.clear()
        V.TERMINAL_VALUES.update(saved[1])
        V.INDUCED_TYPES[:] = saved[2]
        SEARCH.SLOT_LEARNERS.clear()
        SEARCH.SLOT_LEARNERS.update(saved[3])
        ARG_MODES.clear()
        ARG_MODES.update(saved[4])
        V._eval = saved[5]
