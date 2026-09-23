"""CORA meta-induction: repair a memorizing program by DISCOVERING a procedure.

A program that fits every demonstration yet fails leave-one-out re-induction
is usually not under-searched -- it is under-specified: some slot holds a
stored value that differs from example to example.  This module searches a
small combinator meta-language (``meta_ast``) for a composition that
recomputes such a slot from the input.

Two disciplines make the result meaningful rather than convenient:

* Nothing here is a named ARC transformation.  Every program is a Compose
  pipeline over generic primitives; any ARC-shaped abstraction is a
  composition the search found and the anti-unifier named.
* The trigger is computed from the demonstrations alone -- never from a
  leave-one-out verdict -- so an N-1 fold runs the identical procedure and
  must rediscover the program from its own evidence.

Candidates are proposed into the ordinary candidate pool.  Acceptance stays
where it has always been: the unchanged re-induction gate.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from . import meta_ast
from .meta_ast import Compose, Key, Lookup, Map, Paint, Partition, Select


def meta_induction_enabled() -> bool:
    """Env gate, read at call time like the other round gates."""
    return os.environ.get("ARC_META_INDUCTION", "") not in ("", "0")


def _budget_s() -> float:
    """Compute policy: the slice one task's expression phase may spend.

    Global and declared, so a gain can never be attributed to "they simply
    ran a second expensive search on the tasks that needed it".
    """
    try:
        return float(os.environ.get("ARC_META_BUDGET_S", "8"))
    except ValueError:
        return 8.0


# --------------------------------------------------------------------------
# primitive vocabulary: ways to carve a grid, and what may be known of a set
# --------------------------------------------------------------------------

def _components(mask: set) -> list:
    seen, out = set(), []
    for cell in sorted(mask):
        if cell in seen:
            continue
        comp, stack = {cell}, [cell]
        seen.add(cell)
        while stack:
            r, c = stack.pop()
            for nb in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if nb in mask and nb not in seen:
                    seen.add(nb)
                    comp.add(nb)
                    stack.append(nb)
        out.append(frozenset(comp))
    return out


def _background_colour(grid: np.ndarray) -> int:
    vals, counts = np.unique(grid, return_counts=True)
    return int(vals[int(np.argmax(counts))])


def partition_background_components(grid: np.ndarray) -> list:
    bg = _background_colour(grid)
    h, w = grid.shape
    return _components({(r, c) for r in range(h) for c in range(w)
                        if int(grid[r, c]) == bg})


def partition_enclosed_regions(grid: np.ndarray) -> list:
    h, w = grid.shape
    return [comp for comp in partition_background_components(grid)
            if not any(r in (0, h - 1) or c in (0, w - 1) for r, c in comp)]


def partition_colour_components(grid: np.ndarray) -> list:
    bg = _background_colour(grid)
    h, w = grid.shape
    out = []
    for colour in sorted({int(v) for v in np.unique(grid)} - {bg}):
        out.extend(_components({(r, c) for r in range(h) for c in range(w)
                                if int(grid[r, c]) == colour}))
    return out


def partition_separator_panels(grid: np.ndarray) -> list:
    h, w = grid.shape
    sep_rows = {r for r in range(h) if len({int(x) for x in grid[r, :]}) == 1}
    sep_cols = {c for c in range(w) if len({int(x) for x in grid[:, c]}) == 1}
    if not sep_rows and not sep_cols:
        return []

    def bands(n, seps):
        out, cur = [], []
        for i in range(n):
            if i in seps:
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(i)
        if cur:
            out.append(cur)
        return out

    row_bands = bands(h, sep_rows) or [list(range(h))]
    col_bands = bands(w, sep_cols) or [list(range(w))]
    return [frozenset((r, c) for r in rb for c in cb)
            for rb in row_bands for cb in col_bands]


PARTITIONS = {
    "enclosed_regions": partition_enclosed_regions,
    "background_components": partition_background_components,
    "colour_components": partition_colour_components,
    "separator_panels": partition_separator_panels,
}


def descriptors(cells: frozenset, grid: np.ndarray) -> dict:
    """Everything the meta-language may know about one cell set."""
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    r0, c0, r1, c1 = min(rows), min(cols), max(rows), max(cols)
    h, w = grid.shape
    bh, bw = r1 - r0 + 1, c1 - c0 + 1
    ring = set()
    for r, c in cells:
        for nb in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if nb not in cells and 0 <= nb[0] < h and 0 <= nb[1] < w:
                ring.add(int(grid[nb]))
    return {
        "area": len(cells),
        "hw": (bh, bw),
        "shape": tuple(sorted((r - r0, c - c0) for r, c in cells)),
        "is_rect": len(cells) == bh * bw,
        "is_square": bh == bw,
        "touches_border": r0 == 0 or c0 == 0 or r1 == h - 1 or c1 == w - 1,
        "neighbour_colours": tuple(sorted(ring)),
        "sole_neighbour_colour": (sorted(ring)[0] if len(ring) == 1 else None),
        "row_band": r0,
        "col_band": c0,
    }


PREDICATES = {
    "all": lambda d: True,
    "touching_border": lambda d: d["touches_border"],
    "not_touching_border": lambda d: not d["touches_border"],
    "rectangular": lambda d: d["is_rect"],
    "not_rectangular": lambda d: not d["is_rect"],
}

KEY_FEATURES = ("sole_neighbour_colour", "touches_border", "is_rect",
                "is_square", "area", "hw", "neighbour_colours", "shape",
                "row_band", "col_band")

meta_ast.register_vocabulary(PARTITIONS, PREDICATES, KEY_FEATURES)


# --------------------------------------------------------------------------
# the pre-LOO trigger
# --------------------------------------------------------------------------

def failure_signature(train_pairs) -> dict:
    """Evidence that a stored value may be standing in for a computation.

    Computed from the demonstrations ALONE -- no leave-one-out verdict is
    consulted -- so an N-1 fold computes the same signature from its own
    pairs and takes the same branch.  That identity is what keeps the
    complete learner reproducible inside every fold.
    """
    changed_counts = []
    additive = True
    for grid_in, grid_out in train_pairs:
        if grid_in.shape != grid_out.shape:
            additive = False
            continue
        changed_counts.append(int((grid_in != grid_out).sum()))
    return {"same_shape": all(i.shape == o.shape for i, o in train_pairs),
            "additive": additive,
            "changed_cells": changed_counts,
            "changed_varies_across_pairs": len(set(changed_counts)) > 1,
            "n_pairs": len(train_pairs)}


def trigger_fires(train_pairs) -> bool:
    """Route into the expression phase, or not.

    Deliberately cheap and demonstration-local: the phase costs a bounded
    slice, so the trigger only has to avoid spending it where the task
    shape rules the family out entirely.
    """
    if len(train_pairs) < 2:
        return False
    sig = failure_signature(train_pairs)
    return bool(sig["same_shape"] and sig["additive"]
                and all(n > 0 for n in sig["changed_cells"]))


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------

@dataclass
class SearchStats:
    """Compute actually spent, so a gain cannot be confused with a budget."""
    hypotheses: int = 0
    semantic_classes: int = 0
    seconds: float = 0.0
    trigger: bool = False

    def as_dict(self) -> dict:
        return {"hypotheses": self.hypotheses,
                "semantic_classes": self.semantic_classes,
                "seconds": round(self.seconds, 3),
                "trigger": self.trigger,
                "duplicate_ratio": (
                    round(1.0 - self.semantic_classes / self.hypotheses, 3)
                    if self.hypotheses else 0.0)}


def _induce_table(pairs, partition: str, predicate: str, feature: str):
    """Induce key -> colour, plus which pairs witness each key.

    A key witnessed by a single demonstration cannot be re-derived by the
    fold that holds that demonstration out; refusing those tables is how
    this search declines to memorize.
    """
    build = PARTITIONS[partition]
    test = PREDICATES[predicate]
    table: dict = {}
    seen: dict = {}
    for index, (grid_in, grid_out) in enumerate(pairs):
        if grid_in.shape != grid_out.shape:
            return None, None
        sets = build(grid_in)
        if not sets:
            return None, None
        changed = {(r, c) for r in range(grid_in.shape[0])
                   for c in range(grid_in.shape[1])
                   if int(grid_in[r, c]) != int(grid_out[r, c])}
        if not changed:
            return None, None
        covered = set()
        for cells in sets:
            desc = descriptors(cells, grid_in)
            if not test(desc):
                continue
            touched = {cell for cell in cells if cell in changed}
            if not touched:
                continue
            if touched != set(cells):
                return None, None
            colours = {int(grid_out[r, c]) for r, c in cells}
            if len(colours) != 1:
                return None, None
            colour = colours.pop()
            key = desc.get(feature)
            if key is None:
                return None, None
            if table.get(key, colour) != colour:
                return None, None
            table[key] = colour
            seen.setdefault(key, set()).add(index)
            covered |= set(cells)
        if covered != changed:
            return None, None
    if not table:
        return None, None
    return table, seen


def observational_signature(ast, pairs) -> Optional[tuple]:
    """Rendered behaviour on every demonstration input, or None if it errs.

    Two programs with the same signature are one hypothesis differently
    spelled; keeping only the cheapest is what stops a combinatorial pool
    from flooding the ranking.
    """
    out = []
    for grid_in, grid_out in pairs:
        rendered = meta_ast.evaluate(ast, grid_in, descriptors)
        if rendered is None or not np.array_equal(rendered, grid_out):
            return None
        out.append(rendered.tobytes())
    return tuple(out)


# --------------------------------------------------------------------------
# slot learners: one per INDUCED slot TYPE, dispatched generically
# --------------------------------------------------------------------------

def induce_feature_colour_map(ast, pairs, slot):
    """Fit a Map[FeatureValue, Colour] under whatever the AST already binds.

    Reads the partition, predicate and feature the schema has settled on --
    by TYPE, not by position in any particular pipeline -- so this learner
    applies to any schema that carries such a table.  Refuses a table whose
    key is witnessed by a single demonstration: a fold holding that pair
    out could not refit it, which is the memorization the gate rejects.
    """
    bound = meta_ast.bound_values(ast)
    partition = bound.get("PartitionExpr")
    predicate = bound.get("Predicate")
    feature = bound.get("FeatureExpr")
    if not (partition and predicate and feature):
        return None
    if any(str(v).startswith("?") for v in (partition, predicate, feature)):
        return None                      # an earlier slot is still open
    table, seen = _induce_table(pairs, partition, predicate, feature)
    if not table or any(len(seen[k]) < 2 for k in table):
        return None
    return tuple(sorted(table.items(), key=lambda kv: repr(kv[0])))


#: Slot type -> the procedure that fits it from the demonstrations.  A new
#: induced type (a colour bijection, a lattice, an anchor) becomes usable by
#: every existing and future concept the moment its learner is registered
#: here; no concept-specific search code is involved.
SLOT_LEARNERS: dict = {
    "Map[FeatureValue,Colour]": induce_feature_colour_map,
}


def register_slot_learner(slot_type: str, learner) -> None:
    """Install a learner for an induced slot type."""
    SLOT_LEARNERS[slot_type] = learner


def fit_induced_slots(ast, pairs):
    """Fill every slot whose value must be learned rather than enumerated.

    Dispatch is by slot TYPE through ``SLOT_LEARNERS``, and slots are fitted
    repeatedly until no further progress is made, so a schema with several
    induced slots (a transform AND a colour bijection, say) resolves as long
    as each learner's prerequisites are met by an earlier round.  Returns
    None when some induced slot cannot be fitted.
    """
    types = meta_ast.free_slot_types(ast)
    pending = [slot for slot, slot_type in types.items()
               if slot_type in meta_ast.INDUCED_TYPES]
    if not pending:
        return ast
    current = ast
    while pending:
        progressed = False
        for slot in list(pending):
            learner = SLOT_LEARNERS.get(types[slot])
            if learner is None:
                return None              # no learner registered for this type
            value = learner(current, pairs, slot)
            if value is None:
                continue                 # may become fittable after another
            current = meta_ast.instantiate(current, {slot: value})
            pending.remove(slot)
            progressed = True
        if not progressed:
            return None
    return current


def search_with_concepts(pairs, concepts, deadline: Optional[float] = None):
    """Instantiate learned schemas; no schema shape is assumed.

    Every free slot is typed by its position in the schema itself, its
    enumerable values come from the vocabulary, and induced values are
    fitted from the demonstrations.  The AST is then built by
    ``meta_ast.instantiate`` -- there is no hand-written reconstruction of
    any particular pipeline, so a template or lattice concept learned later
    runs through this same code unchanged.
    """
    stats = SearchStats(trigger=True)
    started = time.monotonic()
    if deadline is None:
        deadline = started + _budget_s()
    found: list = []
    for concept in concepts:
        types = meta_ast.free_slot_types(concept.schema)
        enumerable = sorted(slot for slot, kind in types.items()
                            if kind in meta_ast.ENUMERABLE_TYPES)
        domains = [meta_ast.slot_domain(types[slot]) for slot in enumerable]
        for binding in _product(domains):
            if time.monotonic() > deadline:
                stats.seconds = time.monotonic() - started
                stats.semantic_classes = len(found)
                return found, stats
            stats.hypotheses += 1
            partial = meta_ast.instantiate(
                concept.schema, dict(zip(enumerable, binding)))
            complete = fit_induced_slots(partial, pairs)
            if complete is None:
                continue
            if observational_signature(complete, pairs) is None:
                continue
            found.append((concept, complete))
        if found:
            break
    stats.seconds = time.monotonic() - started
    stats.semantic_classes = len(found)
    return found, stats


def _product(domains):
    """Deterministic cartesian product over slot domains."""
    if not domains:
        yield ()
        return
    head, rest = domains[0], domains[1:]
    for value in head:
        for tail in _product(rest):
            yield (value,) + tail


def search(pairs, deadline: Optional[float] = None,
           require_fold_coverable: bool = True):
    """Discovered ASTs reproducing every demonstration, cheapest first."""
    stats = SearchStats(trigger=True)
    started = time.monotonic()
    if deadline is None:
        deadline = started + _budget_s()
    by_signature: dict = {}

    def _finish():
        stats.seconds = time.monotonic() - started
        stats.semantic_classes = len(by_signature)
        return sorted(by_signature.values(),
                      key=lambda a: (meta_ast.ast_nodes(a), repr(a))), stats

    for partition in PARTITIONS:
        for predicate in PREDICATES:
            for feature in KEY_FEATURES:
                if time.monotonic() > deadline:
                    return _finish()
                stats.hypotheses += 1
                table, seen = _induce_table(pairs, partition, predicate,
                                            feature)
                if not table:
                    continue
                if require_fold_coverable and any(len(seen[k]) < 2
                                                  for k in table):
                    continue
                ast = Compose(
                    Partition(partition),
                    Select(predicate),
                    Map(Key(feature),
                        Lookup(tuple(sorted(table.items(),
                                            key=lambda kv: repr(kv[0]))))),
                    Paint())
                signature = observational_signature(ast, pairs)
                if signature is None:
                    continue
                previous = by_signature.get(signature)
                if previous is None or \
                        meta_ast.ast_nodes(ast) < meta_ast.ast_nodes(previous):
                    by_signature[signature] = ast
    return _finish()


# --------------------------------------------------------------------------
# the carried program
# --------------------------------------------------------------------------

@dataclass
class ComputedPatternProgram:
    """A discovered composition, carried like any other program class."""
    ast: tuple
    provenance: tuple = ()
    concept: Optional[str] = None          # set once a concept is learned

    program_class: str = "computed_pattern"

    @property
    def rules(self) -> list:
        return []

    @property
    def segmentation_variant(self):
        return None

    @property
    def library_operators_used(self) -> list:
        return []

    @property
    def grammar_concepts_used(self) -> list:
        used = meta_ast.concepts_used(self.ast)
        return ([self.concept] + used) if self.concept else used

    @property
    def program_depth(self) -> int:
        return 1

    @property
    def expression_size(self) -> int:
        return meta_ast.ast_nodes(self.ast)

    @property
    def value_bound_count(self) -> int:
        return meta_ast.value_bound_count(self.ast)

    @property
    def worst_parameter_class(self):
        """An induced table keyed on a COMPUTED descriptor.

        Above a stored constant (no cell is memorized and the key is
        recomputed per input), below a relational or plain feature
        spelling -- so the preference lattice still ranks a relational
        explanation first, as it should.
        """
        from .types import ParameterClass
        return ParameterClass.INDUCED_MAP

    def to_dict(self) -> dict:
        return {"program_class": "computed_pattern",
                "ast": meta_ast.ast_to_json(self.ast),
                "grammar_concepts_used": self.grammar_concepts_used,
                "concept": self.concept,
                "provenance": list(self.provenance)}

    @staticmethod
    def from_dict(d: dict) -> "ComputedPatternProgram":
        return ComputedPatternProgram(
            ast=meta_ast.ast_from_json(d["ast"]),
            provenance=tuple(d.get("provenance", ())),
            concept=d.get("concept"))

    def render_array(self, grid: np.ndarray) -> np.ndarray:
        out = meta_ast.evaluate(self.ast, np.asarray(grid), descriptors)
        if out is None:
            raise ValueError("computed pattern undefined on this input")
        return out


def induce_computed_candidates(train_pairs, deadline: Optional[float] = None,
                               concepts=(), concepts_only: bool = False):
    """Candidates for the ordinary pool -- proposal only, never acceptance.

    Returns [] when the trigger does not fire, so an untriggered task keeps
    its previous candidate stream and runtime exactly.
    """
    pairs = [(np.asarray(i), np.asarray(o)) for i, o in train_pairs]
    if not trigger_fires(pairs):
        return [], SearchStats(trigger=False)
    # Cooperative budget: the phase gets its declared slice, but never
    # outlives the induction that called it -- a fold whose parent budget is
    # nearly spent cannot start a fresh full-length search.
    own = time.monotonic() + _budget_s()
    deadline = own if deadline is None else min(deadline, own)
    if concepts:
        hits, stats = search_with_concepts(pairs, concepts, deadline=deadline)
        if hits:
            return [ComputedPatternProgram(ast=ast, concept=concept.name)
                    for concept, ast in hits], stats
        if concepts_only:
            return [], stats
    asts, stats = search(pairs, deadline=deadline)
    return [ComputedPatternProgram(ast=ast) for ast in asts], stats
