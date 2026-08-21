"""Type-directed enumeration, slot learning and routing for CORA V2.

One enumerator serves every family.  It is handed a goal type and a set of
allowed productions and it grows well-typed ASTs; it has no idea whether the
program it is building will turn out to be a fill, a stamp or a lattice
extension.  Induced values are left as typed holes and fitted afterwards by
learners registered against the slot's TYPE, so adding a learner makes that
type available to every schema at once.

The router only chooses which productions and how much budget; it never
returns a program, and it recomputes its evidence from whatever pairs it is
given -- which is what keeps a leave-one-out fold on the same branch as the
full-data run.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import meta_v2 as V

# --------------------------------------------------------------------------
# preregistered configuration
# --------------------------------------------------------------------------

MAX_DEPTH = 4
MAX_SEMANTIC_CLASSES_PER_TYPE = 64
MAX_CANDIDATES = 8
#: Bounded frontier per depth: the preregistered ordering ranks candidates
#: BEFORE evaluation, which requires materialising a bounded set of them.
FRONTIER_CAP = 60000


def budget_s() -> float:
    try:
        return float(os.environ.get("ARC_META_BUDGET_S", "8"))
    except ValueError:
        return 8.0


# --------------------------------------------------------------------------
# slot learners, keyed by TYPE
# --------------------------------------------------------------------------

@dataclass
class LearnedValue:
    """A fitted slot value plus the evidence that justifies trusting it."""
    value: object
    support: int = 0
    observations: int = 0
    fold_coverable: bool = False
    conflicts: int = 0
    cost: int = 0

    def as_dict(self) -> dict:
        return {"support": self.support, "observations": self.observations,
                "fold_coverable": self.fold_coverable,
                "conflicts": self.conflicts, "cost": self.cost}


def _changed(grid_in, grid_out):
    return {(r, c) for r in range(grid_in.shape[0])
            for c in range(grid_in.shape[1])
            if int(grid_in[r, c]) != int(grid_out[r, c])}


def learn_feature_colour_map(ast, pairs, slot) -> Optional[LearnedValue]:
    """Fit key -> colour under whatever sets the AST already selects.

    Runs the AST's own prefix to obtain the sets, so this learner works for
    any schema that reaches a Colourise node -- it does not assume which
    partition or predicate produced them.
    """
    prefix = _resolved_of_type(ast, V.REGIONS) or _prefix_before_slot(ast, slot)
    if prefix is None:
        return None
    feature = _terminal_of_type(ast, V.FEATURE_EXPR)
    if feature is None or str(feature).startswith("?"):
        return None
    table: dict = {}
    seen: dict = {}
    conflicts = 0
    observations = 0
    for index, (grid_in, grid_out) in enumerate(pairs):
        if grid_in.shape != grid_out.shape:
            return None
        sets = V._eval(prefix, V.Ctx(grid_in))
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
                conflicts += 1
                return None
            table[key] = colour
            seen.setdefault(key, set()).add(index)
            covered |= set(cells)
            observations += 1
        if covered != changed:
            return None
    if not table:
        return None
    coverable = all(len(seen[k]) >= 2 for k in table)
    if not coverable:
        return None
    return LearnedValue(
        value=tuple(sorted(table.items(), key=lambda kv: repr(kv[0]))),
        support=min(len(v) for v in seen.values()),
        observations=observations, fold_coverable=True,
        conflicts=conflicts, cost=len(table))


def learn_colour_bijection(ast, pairs, slot) -> Optional[LearnedValue]:
    """Fit the recolouring between a SOURCE entity and its produced instances.

    The frozen intent is a correspondence between the template the AST has
    already selected and the instances that appear in the output, not a
    comparison of identical grid coordinates.  The source entity is obtained
    by running the AST's own resolved prefix, so this learner uses the typed
    context rather than raw pixels, and works for any schema that reaches a
    Recolour node.
    """
    prefix = _prefix_before_slot(ast, slot)
    if prefix is None:
        return None
    mapping: dict = {}
    seen: dict = {}
    observations = 0
    for index, (grid_in, grid_out) in enumerate(pairs):
        if grid_in.shape != grid_out.shape:
            return None
        source = V._eval(prefix, V.Ctx(grid_in))
        if source is None:
            return None
        entity = source if isinstance(source, frozenset) else (
            source[0] if source else None)
        if not entity:
            return None
        template = V.patch_of(entity, grid_in)
        # every instance of the template's shape in the output, wherever it
        # sits, gives one witnessed colour correspondence
        h, w = grid_out.shape
        th, tw = template.shape
        for r in range(h - th + 1):
            for c in range(w - tw + 1):
                window = grid_out[r:r + th, c:c + tw]
                mask = template != 0
                if not mask.any():
                    continue
                if not (window[mask] != V._background(grid_in)).all():
                    continue
                shape_matches = True
                local: dict = {}
                for rr in range(th):
                    for cc in range(tw):
                        if not mask[rr, cc]:
                            continue
                        src, dst = int(template[rr, cc]), int(window[rr, cc])
                        if local.get(src, dst) != dst:
                            shape_matches = False
                            break
                        local[src] = dst
                    if not shape_matches:
                        break
                if not shape_matches or not local:
                    continue
                for src, dst in local.items():
                    if mapping.get(src, dst) != dst:
                        continue                # a different instance: skip
                    mapping[src] = dst
                    seen.setdefault(src, set()).add(index)
                    observations += 1
    if not mapping or len(set(mapping.values())) != len(mapping):
        return None                             # not injective
    if any(len(seen[k]) < 2 for k in mapping):
        return None
    return LearnedValue(
        value=tuple(sorted(mapping.items())),
        support=min(len(v) for v in seen.values()),
        observations=observations, fold_coverable=True, cost=len(mapping))


def learn_transform(ast, pairs, slot) -> Optional[LearnedValue]:
    """Pick the one D4 element that explains every witnessed instance.

    Preregistered as INDUCED, so the element is inferred rather than
    enumerated: a candidate survives only when the transformed source
    appears in the output on every demonstration.
    """
    prefix = _prefix_before_slot(ast, slot)
    if prefix is None:
        return None
    survivors = list(V.D4)
    observations = 0
    for grid_in, grid_out in pairs:
        source = V._eval(prefix, V.Ctx(grid_in))
        entity = source if isinstance(source, frozenset) else (
            source[0] if source else None)
        if not entity:
            return None
        template = V.patch_of(entity, grid_in)
        still: list = []
        for spec in survivors:
            moved = V.apply_d4(template, spec)
            if _appears_in(moved, grid_out, V._background(grid_in)):
                still.append(spec)
                observations += 1
        survivors = still
        if not survivors:
            return None
    if len(survivors) != 1:
        return None                             # ambiguous: refuse to guess
    return LearnedValue(value=tuple(survivors[0]), support=len(pairs),
                        observations=observations, fold_coverable=True, cost=1)


def _appears_in(patch, grid, background) -> bool:
    h, w = grid.shape
    ph, pw = patch.shape
    if ph > h or pw > w:
        return False
    mask = patch != 0
    if not mask.any():
        return False
    for r in range(h - ph + 1):
        for c in range(w - pw + 1):
            window = grid[r:r + ph, c:c + pw]
            if np.array_equal(window[mask], patch[mask]):
                return True
    return False


def learn_anchor(ast, pairs, slot) -> Optional[LearnedValue]:
    """Infer a placement offset from host and marker geometry.

    Absolute task coordinates are forbidden by the preregistration, so the
    offset is expressed relative to the source entity's own origin and must
    be the same relative displacement on every demonstration.
    """
    prefix = _prefix_before_slot(ast, slot)
    if prefix is None:
        return None
    offsets: Optional[set] = None
    observations = 0
    for grid_in, grid_out in pairs:
        source = V._eval(prefix, V.Ctx(grid_in))
        entity = source if isinstance(source, frozenset) else (
            source[0] if source else None)
        if not entity:
            return None
        template = V.patch_of(entity, grid_in)
        r0, c0 = V.origin_of(entity)
        here = set()
        h, w = grid_out.shape
        ph, pw = template.shape
        mask = template != 0
        for r in range(h - ph + 1):
            for c in range(w - pw + 1):
                window = grid_out[r:r + ph, c:c + pw]
                if np.array_equal(window[mask], template[mask]):
                    here.add((r - r0, c - c0))
                    observations += 1
        offsets = here if offsets is None else (offsets & here)
        if not offsets:
            return None
    non_trivial = sorted(o for o in offsets if o != (0, 0))
    if len(non_trivial) != 1:
        return None
    return LearnedValue(value=tuple(non_trivial[0]), support=len(pairs),
                        observations=observations, fold_coverable=True, cost=1)


def learn_sequence_rule(ast, pairs, slot) -> Optional[LearnedValue]:
    """Infer a constant step from at least two witnessed positions."""
    steps: Optional[set] = None
    for grid_in, grid_out in pairs:
        entities = V._multicolour_components(grid_in)
        if len(entities) < 2:
            return None
        origins = sorted(V.origin_of(e) for e in entities)
        deltas = {(b[0] - a[0], b[1] - a[1])
                  for a, b in zip(origins, origins[1:])}
        if len(deltas) != 1:
            return None
        steps = deltas if steps is None else (steps & deltas)
        if not steps:
            return None
    if not steps or len(steps) != 1:
        return None
    return LearnedValue(value=tuple(next(iter(steps))), support=len(pairs),
                        observations=len(pairs), fold_coverable=True, cost=1)


def learn_lattice(ast, pairs, slot) -> Optional[LearnedValue]:
    """Infer translation vectors from the input's own periodicity.

    A vector counts only when the non-background content agrees with itself
    under that shift wherever both cells are known, on EVERY demonstration,
    so a fold re-derives the same vectors from its own inputs.
    """
    candidates: Optional[set] = None
    for grid_in, grid_out in pairs:
        if grid_in.shape != grid_out.shape:
            return None
        h, w = grid_in.shape
        bg = V._background(grid_in)
        here = set()
        for dr in range(0, min(h, 12)):
            for dc in range(-min(w, 12) + 1, min(w, 12)):
                if dr == 0 and dc <= 0:
                    continue
                agree = conflict = 0
                for r in range(h):
                    for c in range(w):
                        rr, cc = r + dr, c + dc
                        if not (0 <= rr < h and 0 <= cc < w):
                            continue
                        a, b = int(grid_in[r, c]), int(grid_in[rr, cc])
                        if a == bg or b == bg:
                            continue
                        if a == b:
                            agree += 1
                        else:
                            conflict += 1
                if conflict == 0 and agree >= 3:
                    here.add((dr, dc))
        candidates = here if candidates is None else (candidates & here)
        if not candidates:
            return None
    if not candidates:
        return None
    best = sorted(candidates, key=lambda v: (abs(v[0]) + abs(v[1]), v))[:2]
    return LearnedValue(value=tuple(best), support=len(pairs),
                        observations=len(pairs), fold_coverable=True,
                        cost=len(best))


SLOT_LEARNERS: dict = {
    V.FEATURE_COLOUR_MAP: learn_feature_colour_map,
    V.COLOUR_BIJECTION: learn_colour_bijection,
    V.TRANSFORM: learn_transform,
    V.ANCHOR: learn_anchor,
    V.LATTICE: learn_lattice,
    V.SEQUENCE_RULE: learn_sequence_rule,
}


def register_slot_learner(slot_type: str, learner) -> None:
    SLOT_LEARNERS[slot_type] = learner


def _resolved_of_type(ast, wanted_type):
    """The outermost slot-free sub-AST whose RESULT TYPE is ``wanted_type``.

    Type-directed, so a learner finds its inputs wherever the schema puts
    them: as a child, as a sibling, or several levels up.  This is what lets
    one learner serve pipelines it was not written against.
    """
    found = []

    def walk(node):
        if not V._is_ast(node):
            return
        production = V.PRODUCTIONS.get(node[0])
        if production and production.result_type == wanted_type \
                and not V.free_slot_types(node):
            found.append(node)
            return                        # outermost match wins
        for arg in node[1]:
            walk(arg)

    walk(ast)
    return found[0] if found else None


def _terminal_of_type(ast, wanted_type):
    """The first resolved terminal argument of ``wanted_type`` anywhere."""
    result = []

    def walk(node):
        if not V._is_ast(node) or result:
            return
        production = V.PRODUCTIONS.get(node[0])
        for index, arg in enumerate(node[1]):
            if V._is_ast(arg):
                walk(arg)
            elif production and index < len(production.arg_types) \
                    and production.arg_types[index] == wanted_type \
                    and not (isinstance(arg, str) and arg.startswith("?")):
                result.append(arg)
                return

    walk(ast)
    return result[0] if result else None


def _prefix_before_slot(ast, slot):
    """The entity or region source the slot's learner should run on."""
    for wanted in (V.ENTITY, V.REGIONS, V.ENTITIES):
        found = _resolved_of_type(ast, wanted)
        if found is not None:
            return found
    return None


def _sibling_terminal(ast, slot, wanted_type):
    return _terminal_of_type(ast, wanted_type)


def free_slots(ast) -> tuple:
    return tuple(sorted(V.free_slot_types(ast)))


def _learner_key(slot_type, ast, slot):
    """What a learner's answer actually depends on: its typed inputs.

    Two candidates that present the same source sub-AST and the same
    terminal arguments to a learner must get the same value, so the answer
    is computed once per distinct input rather than once per candidate.
    """
    prefix = _prefix_before_slot(ast, slot)
    feature = _terminal_of_type(ast, V.FEATURE_EXPR)
    prefix_key = (json.dumps(V.to_json(prefix), sort_keys=True)
                  if prefix is not None else None)
    return (slot_type, prefix_key, feature)


def fit_slots(ast, pairs, memo=None):
    """Fill every induced slot by type, iterating to a fixed point."""
    types = V.free_slot_types(ast)
    pending = [s for s, t in types.items() if t in V.INDUCED_TYPES]
    unknown = [s for s, t in types.items() if t not in V.INDUCED_TYPES]
    if unknown:
        return None, {}
    if not pending:
        return ast, {}
    current = ast
    evidence: dict = {}
    while pending:
        progressed = False
        for slot in list(pending):
            learner = SLOT_LEARNERS.get(types[slot])
            if learner is None:
                return None, {}
            key = _learner_key(types[slot], current, slot)
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
            pending.remove(slot)
            progressed = True
        if not progressed:
            return None, {}
    return current, evidence


# --------------------------------------------------------------------------
# type-directed enumeration
# --------------------------------------------------------------------------

@dataclass
class SearchStats:
    syntactic: int = 0
    typed: int = 0
    semantic_classes: int = 0
    intermediate_classes: int = 0
    intermediate_duplicates: int = 0
    rejected: int = 0
    max_depth: int = 0
    seconds: float = 0.0
    by_result_type: dict = field(default_factory=dict)
    routed_to: tuple = ()

    def as_dict(self) -> dict:
        """Honest names.  ``candidate_rejection_ratio`` is the share of
        typed candidates that failed to fit the demonstrations; it is NOT a
        deduplication measure.  ``intermediate_dedup_ratio`` is the share of
        candidates skipped because an equally cheap sub-program with the
        same behaviour had already been kept."""
        return {"syntactic_hypotheses": self.syntactic,
                "typed_hypotheses": self.typed,
                "semantic_classes": self.semantic_classes,
                "intermediate_classes": self.intermediate_classes,
                "intermediate_dedup_ratio": (
                    round(self.intermediate_duplicates / self.typed, 3)
                    if self.typed else 0.0),
                "candidate_rejection_ratio": (
                    round(self.rejected / self.typed, 3) if self.typed else 0.0),
                "max_depth": self.max_depth,
                "seconds": round(self.seconds, 3),
                "by_result_type": dict(self.by_result_type),
                "routed_to": list(self.routed_to)}


PER_TYPE_CAP = 6000


def enumerate_asts(goal_type, allowed, depth, stats, deadline):
    """Every well-typed AST of ``goal_type`` within ``depth``.

    Bottom-up and memoised by (type, depth): a sub-expression is built once
    and reused by every parent that needs it, which is what keeps a typed
    space of this size searchable at all.  Purely type-directed, a
    production is tried because its result type unifies with the goal.
    """
    cache: dict = {}
    for ast in _asts_of_type(goal_type, depth, allowed, cache, stats,
                             deadline):
        yield ast


def _asts_of_type(wanted, depth, allowed, cache, stats, deadline):
    if depth <= 0:
        return []
    key = (wanted, depth)
    if key in cache:
        return cache[key]
    cache[key] = []                       # guard against left recursion
    out: list = []
    for name in sorted(allowed):
        production = V.PRODUCTIONS.get(name)
        if production is None or production.result_type != wanted:
            continue
        if time.monotonic() > deadline:
            break
        arg_options = []
        viable = True
        for arg_type in production.arg_types:
            options = _values_of_type(arg_type, depth - 1, allowed, cache,
                                      stats, deadline)
            if not options:
                viable = False
                break
            arg_options.append(options)
        if not viable:
            continue
        for combination in _product(arg_options):
            out.append((name, combination))
            stats.syntactic += 1
            if len(out) >= PER_TYPE_CAP:
                break
        if len(out) >= PER_TYPE_CAP:
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


def _values_of_type(slot_type, depth, allowed, cache, stats, deadline):
    if slot_type in V.TERMINAL_VOCAB:
        return list(V.TERMINAL_VOCAB[slot_type]())
    if slot_type in V.INDUCED_TYPES:
        return [f"?{slot_type}"]          # a typed hole for a learner
    return _asts_of_type(slot_type, depth, allowed, cache, stats, deadline)


def search(pairs, allowed=None, deadline=None, goal_type=V.GRID):
    """Discovered programs reproducing every demonstration, cheapest first."""
    stats = SearchStats()
    started = time.monotonic()
    own = started + budget_s()
    deadline = own if deadline is None else min(deadline, own)
    allowed = set(allowed or V.PRODUCTIONS)
    by_signature: dict = {}
    # Intermediate semantic cache: (result type, values produced on every
    # demonstration input) -> cheapest AST.  Sub-programs that behave
    # identically on the demonstrations are one hypothesis differently
    # spelled, so only the cheapest is extended.  This is what lets the
    # space grow without the frontier degenerating into brute force.
    intermediate: dict = {}
    learner_memo: dict = {}
    # Iterative deepening, as the preregistered enumeration order requires
    # (result_type, then ast_depth, then MDL, parameter_class,
    # value_bound_count, stable serialization).
    for depth in range(1, MAX_DEPTH + 1):
        if time.monotonic() > deadline or by_signature:
            break
        seen_this_depth = set()
        frontier = []
        for ast in enumerate_asts(goal_type, allowed, depth, stats, deadline):
            if time.monotonic() > deadline:
                break
            if V.ast_depth(ast) != depth:
                continue
            key_ast = json.dumps(V.to_json(ast), sort_keys=True)
            if key_ast in seen_this_depth:
                continue
            seen_this_depth.add(key_ast)
            frontier.append((ast, key_ast))
            if len(frontier) >= FRONTIER_CAP:
                break
        # rank the whole depth-frontier by the preregistered key BEFORE
        # evaluating, so cheaper and better-classed candidates are tried first
        frontier.sort(key=lambda item: (
            V.ast_nodes(item[0]),
            V.PARAMETER_CLASS_RANK.get(V.parameter_class(item[0]), 9),
            V.value_bound_count(item[0]),
            item[1]))
        for ast, key_ast in frontier:
            if time.monotonic() > deadline:
                break
            stats.typed += 1
            stats.max_depth = max(stats.max_depth, depth)
            behaviour = intermediate_signature(ast, pairs)
            if behaviour is not None:
                cache_key = (_result_type_of(ast), behaviour)
                kept = intermediate.get(cache_key)
                if kept is not None and V.ast_nodes(kept) <= V.ast_nodes(ast):
                    stats.intermediate_duplicates += 1
                    continue
                intermediate[cache_key] = ast
            complete, evidence = fit_slots(ast, pairs, memo=learner_memo)
            if complete is None:
                stats.rejected += 1
                continue
            signature = observational_signature(complete, pairs)
            if signature is None:
                stats.rejected += 1
                continue
            key = (goal_type, signature)
            previous = by_signature.get(key)
            if previous is None or \
                    V.ast_nodes(complete) < V.ast_nodes(previous[0]):
                by_signature[key] = (complete, evidence)
            if len(by_signature) >= MAX_SEMANTIC_CLASSES_PER_TYPE:
                break
    stats.seconds = time.monotonic() - started
    stats.semantic_classes = len(by_signature)
    stats.intermediate_classes = len(intermediate)
    stats.by_result_type[goal_type] = stats.typed
    ranked = sorted(by_signature.values(),
                    key=lambda ce: (V.ast_nodes(ce[0]),
                                    V.PARAMETER_CLASS_RANK.get(
                                        V.parameter_class(ce[0]), 9),
                                    V.value_bound_count(ce[0]),
                                    V.ast_depth(ce[0]),
                                    json.dumps(V.to_json(ce[0]), sort_keys=True)))
    return ranked[:MAX_CANDIDATES], stats


def _result_type_of(ast):
    production = V.PRODUCTIONS.get(ast[0]) if V._is_ast(ast) else None
    return production.result_type if production else None


def intermediate_signature(ast, pairs):
    """What a sub-program PRODUCES on each demonstration input.

    Unlike the final-program signature this does not require the value to
    equal the target: it is the behaviour used for deduplication, which is
    what makes the cache meaningful rather than a rejection counter.
    """
    if V.free_slot_types(ast):
        return None                       # unresolved slots: nothing to run
    out = []
    for grid_in, _ in pairs:
        try:
            value = V._eval(ast, V.Ctx(np.asarray(grid_in)))
        except Exception:
            return None
        if value is None:
            return None
        out.append(_hashable(value))
    return tuple(out)


def _hashable(value):
    if isinstance(value, np.ndarray):
        return value.tobytes()
    if isinstance(value, (tuple, list)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, (frozenset, set)):
        return tuple(sorted(value))
    return value


def observational_signature(ast, pairs):
    """Rendered behaviour on every demonstration, or None if it ever misses."""
    out = []
    for grid_in, grid_out in pairs:
        rendered = V.evaluate(ast, grid_in)
        if rendered is None or not np.array_equal(rendered, grid_out):
            return None
        out.append(rendered.tobytes())
    return tuple(out)


# --------------------------------------------------------------------------
# router: chooses productions and budget, never a program
# --------------------------------------------------------------------------

#: Amendment (b) 2026-08-21: Compose appears in every list because it is the
#: only production yielding Function, which MapOver's frozen signature
#: requires.  Structural, not family-specific.
SUBGRAMMARS: dict = {
    "computed_set": ("Partition", "Select", "Key", "Lookup", "MapOver",
                     "Compose", "Paint", "PaintEach"),
    "template_placement": ("Entities", "Select", "Unique", "ArgMax",
                           "ArgMin", "Group", "Transform", "Recolour",
                           "Anchor", "Copy", "Overlay", "Compose"),
    "orbit_sequence": ("Orbits", "Order", "Propagate", "Repeat", "Paint",
                       "Overlay", "Compose"),
    "relational": ("Entities", "Pairs", "Select", "Unique", "Anchor",
                   "Copy", "Paint", "Compose"),
}

#: Preregistered router thresholds.
THRESHOLDS = {"background_change_fraction_min": 0.5,
              "repeated_shape_min_instances": 2,
              "orbit_evidence_min_vectors": 1,
              "panel_min_separators": 1}


def failure_signature(pairs) -> dict:
    """The twelve preregistered demonstration-local measurements.

    Recomputed by every leave-one-out fold from its own pairs, so a fold
    takes the same branch as the full-data run.  No task identity, no
    leave-one-out verdict, no reference to the attempt being built.
    """
    same_shape = all(i.shape == o.shape for i, o in pairs)
    changed_counts, bg_fraction = [], []
    preserves, deletes, recolours = True, False, False
    component_deltas, repeated_shapes = [], 0
    template_evidence = orbit_evidence = alignment_evidence = 0
    panels_seen = False
    for grid_in, grid_out in pairs:
        entities_in = V._multicolour_components(grid_in)
        shapes = [V.descriptors(s, grid_in)["norm_shape"] for s in entities_in]
        repeated_shapes += len(shapes) - len(set(shapes))
        origins = sorted(V.origin_of(s) for s in entities_in)
        if len(origins) >= 2:
            deltas = {(b[0] - a[0], b[1] - a[1])
                      for a, b in zip(origins, origins[1:])}
            if len(deltas) == 1:
                alignment_evidence += 1
        if len(V._panels(grid_in)) > 1:
            panels_seen = True
        if grid_in.shape != grid_out.shape:
            continue
        bg = V._background(grid_in)
        changed = _changed(grid_in, grid_out)
        changed_counts.append(len(changed))
        entities_out = V._multicolour_components(grid_out)
        component_deltas.append(len(entities_out) - len(entities_in))
        if changed:
            on_bg = sum(1 for r, c in changed if int(grid_in[r, c]) == bg)
            bg_fraction.append(on_bg / len(changed))
            for r, c in changed:
                if int(grid_in[r, c]) != bg:
                    preserves = False
                    if int(grid_out[r, c]) == bg:
                        deletes = True
                    else:
                        recolours = True
        shapes_out = [V.descriptors(s, grid_out)["norm_shape"]
                      for s in entities_out]
        for shape in set(shapes):
            if shapes_out.count(shape) > shapes.count(shape):
                template_evidence += 1
        for dr in range(1, min(grid_in.shape[0], 8)):
            shifted_agree = True
            found = False
            for r in range(grid_in.shape[0] - dr):
                for c in range(grid_in.shape[1]):
                    a, b = int(grid_in[r, c]), int(grid_in[r + dr, c])
                    if a == bg or b == bg:
                        continue
                    found = True
                    if a != b:
                        shifted_agree = False
                        break
                if not shifted_agree:
                    break
            if found and shifted_agree:
                orbit_evidence += 1
                break
    return {
        "same_shape": same_shape,
        "changed_cell_count": changed_counts,
        "changed_on_background_fraction": (
            round(sum(bg_fraction) / len(bg_fraction), 3) if bg_fraction else 0.0),
        "preserves_nonbackground": preserves,
        "deletes_existing_cells": deletes,
        "recolours_existing_cells": recolours,
        "changed_component_count": component_deltas,
        "repeated_changed_shapes": repeated_shapes,
        "template_match_evidence": template_evidence,
        "translation_orbit_evidence": orbit_evidence,
        "pairwise_alignment_evidence": alignment_evidence,
        "panel_structure_evidence": panels_seen,
        "n_pairs": len(pairs),
    }


def route(pairs) -> tuple:
    """Which sub-grammars to search.  Never returns a program."""
    if len(pairs) < 2:
        return ()
    signature = failure_signature(pairs)
    if not signature["same_shape"]:
        return ()
    chosen = []
    if signature["changed_on_background_fraction"] >= \
            THRESHOLDS["background_change_fraction_min"]:
        chosen.append("computed_set")
    if signature["translation_orbit_evidence"] >= \
            THRESHOLDS["orbit_evidence_min_vectors"]:
        chosen.append("orbit_sequence")
    if signature["template_match_evidence"] >= 1 \
            or signature["repeated_changed_shapes"] >= \
            THRESHOLDS["repeated_shape_min_instances"] \
            or signature["panel_structure_evidence"]:
        chosen.append("template_placement")
    if signature["pairwise_alignment_evidence"] >= 1 \
            or signature["recolours_existing_cells"]:
        chosen.append("relational")
    return tuple(dict.fromkeys(chosen))


def routed_search(pairs, deadline=None):
    """Route, then search each allowed subset under its own budget slice.

    The preregistered router output is "allowed production subsets AND
    budget allocation".  Searching the UNION of the routed subsets instead
    multiplies the space by the cross-product of unrelated productions and
    spends the budget before the cheap answer is reached; allocating a slice
    per subset is the faithful reading and keeps each subset's space the
    size it was measured at.
    """
    routes = route(pairs)
    if not routes:
        return [], SearchStats()
    started = time.monotonic()
    own = started + budget_s()
    deadline = own if deadline is None else min(deadline, own)
    slice_s = max((deadline - started) / len(routes), 0.01)
    combined = SearchStats(routed_to=routes)
    best: list = []
    for index, name in enumerate(routes):
        allowed = set(SUBGRAMMARS.get(name, ()))
        if not allowed:
            continue
        slice_deadline = min(deadline, started + slice_s * (index + 1))
        results, stats = search(pairs, allowed=allowed,
                                deadline=slice_deadline)
        combined.syntactic += stats.syntactic
        combined.typed += stats.typed
        combined.rejected += stats.rejected
        combined.intermediate_classes += stats.intermediate_classes
        combined.intermediate_duplicates += stats.intermediate_duplicates
        combined.max_depth = max(combined.max_depth, stats.max_depth)
        for key, value in stats.by_result_type.items():
            combined.by_result_type[key] = \
                combined.by_result_type.get(key, 0) + value
        best.extend(results)
        if best:
            break                      # cheapest routed subset that answers
    combined.seconds = time.monotonic() - started
    combined.semantic_classes = len(best)
    return best[:MAX_CANDIDATES], combined
