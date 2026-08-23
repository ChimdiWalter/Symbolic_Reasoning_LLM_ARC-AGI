"""K1: the exhaustive guard-relaxation lattice of the frozen slot learner.

The frozen runtime has ONE induced-slot learner,
``search.learn_feature_colour_map``, with five explicit guards. Lane K1 of
the Step-B design is the lattice of guard relaxations: every non-empty
subset of the five guards dropped, 2^5 - 1 = 31 candidate learners, each
labelled SLOT_LEARNER_REPAIR. No guard is invented; nothing is added.

Relaxation semantics, fixed once per guard and identical for every subset:
wherever a guard HOLDS the relaxed learner computes exactly what the frozen
learner computes (conservativity, tested mechanically). Where a guard is
dropped and the guarded quantity is no longer forced, the quantity is the
one the guard would have validated:

    same_shape        dropped: cells are compared over the common index
                      domain of input and output (the only defined comparison)
    touched_is_whole  dropped: the colour witness of a set is its touched
                      cells rather than all its cells (equal when the guard holds)
    single_colour     dropped: a set's colour is the majority colour of its
                      witness cells; an exact tie is undefined (equal when
                      the guard holds)
    full_coverage     dropped: changed cells no set touches are ignored
    witnessed_twice   dropped: a key seen in one demonstration is accepted

The subsets are generated, ordered by (size, names); nothing is selected.
"""
from __future__ import annotations

import hashlib
import inspect
import itertools
from collections import Counter
from typing import Optional

from level4_blind_runtime import runtime as V
from level4_blind_runtime import search as SEARCH
from level4_blind_runtime.search import LearnedValue

#: The five guards, each with the frozen source line that implements it.
#: The unit tests verify every line is present, verbatim, in the frozen
#: learner's source, so the lattice axis cannot drift from the runtime.
GUARDS = (
    ("same_shape", "if grid_in.shape != grid_out.shape:"),
    ("touched_is_whole", "if touched != set(cells):"),
    ("single_colour", "if len(colours) != 1:"),
    ("full_coverage", "if covered != changed:"),
    ("witnessed_twice", "if not table or any(len(seen[k]) < 2 for k in table):"),
)
GUARD_NAMES = tuple(name for name, _ in GUARDS)
FROZEN_LEARNER = SEARCH.learn_feature_colour_map
FROZEN_LEARNER_SHA256 = hashlib.sha256(
    inspect.getsource(FROZEN_LEARNER).encode()).hexdigest()


def subsets():
    """All 31 non-empty guard subsets, canonical order."""
    out = []
    for size in range(1, len(GUARD_NAMES) + 1):
        for combo in itertools.combinations(GUARD_NAMES, size):
            out.append(frozenset(combo))
    return tuple(out)


def lattice_id(dropped: frozenset) -> str:
    return "K1:" + "+".join(sorted(dropped))


def _changed_common(grid_in, grid_out):
    h = min(grid_in.shape[0], grid_out.shape[0])
    w = min(grid_in.shape[1], grid_out.shape[1])
    return {(r, c) for r in range(h) for c in range(w)
            if int(grid_in[r, c]) != int(grid_out[r, c])}


def _majority(grid_out, witness):
    counts = Counter(int(grid_out[r, c]) for r, c in witness)
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def make_learner(dropped: frozenset):
    """The frozen learner with the named guards removed."""
    keep = {g: (g not in dropped) for g in GUARD_NAMES}

    def learner(ast, pairs, slot) -> Optional[LearnedValue]:
        source = SEARCH._resolved_of_type(ast, V.SET_REGION)
        feature = SEARCH._terminal_of_type(ast, V.FEATURE_EXPR)
        if source is None or feature is None:
            return None
        table: dict = {}
        seen: dict = {}
        observations = 0
        for index, (grid_in, grid_out) in enumerate(pairs):
            if keep["same_shape"] and grid_in.shape != grid_out.shape:
                return None
            sets = V._eval(source, V.Ctx(grid_in))
            if not sets:
                return None
            changed = _changed_common(grid_in, grid_out)
            if not changed:
                return None
            covered = set()
            h, w = grid_out.shape
            for cells in sets:
                touched = {cell for cell in cells if cell in changed}
                if not touched:
                    continue
                if keep["touched_is_whole"] and touched != set(cells):
                    return None
                witness = {(r, c) for r, c in cells if r < h and c < w} \
                    if keep["touched_is_whole"] else touched
                colours = {int(grid_out[r, c]) for r, c in witness}
                if keep["single_colour"] and len(colours) != 1:
                    return None
                colour = _majority(grid_out, witness)
                if colour is None:
                    return None
                key = V.descriptors(cells, grid_in).get(feature)
                if key is None:
                    return None
                if table.get(key, colour) != colour:
                    return None
                table[key] = colour
                seen.setdefault(key, set()).add(index)
                covered |= witness
                observations += 1
            if keep["full_coverage"] and covered != changed:
                return None
        if not table:
            return None
        if keep["witnessed_twice"] and any(len(seen[k]) < 2 for k in table):
            return None
        return LearnedValue(
            value=tuple(sorted(table.items(), key=lambda kv: repr(kv[0]))),
            support=min(len(v) for v in seen.values()),
            observations=observations,
            fold_coverable=all(len(v) >= 2 for v in seen.values()),
            cost=len(table))

    learner.__name__ = lattice_id(dropped)
    learner.dropped = dropped
    return learner


def lattice() -> list:
    """31 (id, dropped, learner) triples, canonical order."""
    return [(lattice_id(d), d, make_learner(d)) for d in subsets()]


def lattice_record() -> dict:
    return {
        "component": "K1 guard-relaxation lattice",
        "label": "SLOT_LEARNER_REPAIR",
        "frozen_learner": FROZEN_LEARNER.__name__,
        "frozen_learner_source_sha256": FROZEN_LEARNER_SHA256,
        "guards": [{"name": n, "frozen_source_line": line} for n, line in GUARDS],
        "relaxation_semantics": {
            "same_shape": "compare over the common index domain",
            "touched_is_whole": "colour witness = touched cells",
            "single_colour": "majority colour of the witness; tie undefined",
            "full_coverage": "uncovered changed cells ignored",
            "witnessed_twice": "single-demonstration keys accepted",
        },
        "conservativity": ("every relaxed learner returns the frozen "
                           "learner's table wherever all guards hold"),
        "candidates": [{"id": lattice_id(d), "dropped": sorted(d),
                        "size": len(d)} for d in subsets()],
        "count": len(subsets()),
        "generator_source_sha256": hashlib.sha256(
            inspect.getsource(make_learner).encode()).hexdigest(),
    }
