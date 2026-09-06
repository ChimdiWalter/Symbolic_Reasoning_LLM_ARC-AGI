"""Occurrence-scoped induced-slot fitting (protocol v2).

Protocol v1.1 fitted induced slots by TYPE: meta_ast.bound_values returns one
flat dictionary keyed by declared type, so several occurrences of
Map[FeatureValue,Colour] in one schema collapse onto the last occurrence. That
made requirement 5 satisfiable only when the schema reduced to a single
(partition, predicate, feature) triple, which is exactly the space the fixed
base search enumerates, so R5 success implied R4 failure and the v1.1 pilot
admitted nothing (see docs/CORA_TTI_CONSTRUCTIVE_V1_1_POSTMORTEM.md).

This module fits induced values by typed LEXICAL OCCURRENCE instead:

    (slot_name, ast_path, declared_type, local prefix, local key expression)
        -> fitted value

Occurrence identity comes only from the structured AST. Nothing here reads a
task id, family label, target digest, production name, generation split,
concrete generator table, or any hidden output.

FAIRNESS. This fitter is not a target-only privilege: protocol v2 requires the
fixed base search to fit its own 200 single-block candidates with this same
implementation. `fitter_identity()` returns the hash both paths record.

CONSERVATIVITY. On the single-block family (1,) the intended behaviour is
identical to the v1.1 learner, including its anti-memorization rule that a
table key must be witnessed by at least two demonstrations. Protocol v2 gates
on a differential parity suite over the complete 200-schema baseline space;
any expansion of single-block reach is a feasibility-gate failure, not a
feature.

SEALED ENGINE. This module is additive. It registers nothing, patches nothing,
and mutates no global registry. meta_induction.SLOT_LEARNERS,
meta_induction.fit_induced_slots and meta_induction.search keep their v1.1
behaviour exactly; callers opt in by calling this module directly.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402

#: minimum demonstrations witnessing a table key (v1.1 anti-memorization rule,
#: preserved so single-block behaviour is unchanged)
MIN_KEY_WITNESSES = 2

#: primary failure codes this fitter can report (frozen in the v2 manifest)
FIT_FAILURES = (
    "scoped_fit_failed",          # structure unusable / a block explains nothing
    "slot_unobservable",          # a slot has no visible constraining cell
    "slot_key_unobserved",        # a key never had a visible witness
    "slot_nonfunctional",         # one (slot, key) demanded two colours
    "region_colour_conflict",     # one visible region demanded two colours
    "final_execution_mismatch",   # instantiated schema did not replay exactly
)


@dataclass(frozen=True)
class ScopedSlotOccurrence:
    """One free induced slot, identified structurally."""
    slot_name: str
    declared_type: str
    ast_path: tuple            # canonical path from the root, e.g. (1, 'Map', 'Lookup')
    block_index: int           # execution order of the enclosing block
    local_prefix: tuple        # (partition, (predicate, ...)) of the enclosing block
    local_key_expression: str  # the Key feature of the enclosing block


def fitter_identity() -> str:
    """SHA-256 of this implementation; both the baseline and target paths
    record it so a target-only fitter cannot be introduced unnoticed."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# occurrence discovery
# --------------------------------------------------------------------------

def occurrences(schema) -> list:
    """Every free induced-slot occurrence, in execution order.

    Structure is read from the AST itself: a block is Partition, zero or more
    Select stages, Map(Key, Lookup), Paint. A block with zero Select stages is
    simply a block whose filter sequence is empty; it is NOT rewritten into a
    hidden `all` predicate.
    """
    if not (isinstance(schema, tuple) and len(schema) == 2
            and schema[0] == "Compose"):
        return []
    found, stages = [], list(schema[1])
    index, block_index = 0, 0
    while index < len(stages):
        stage = stages[index]
        if not (isinstance(stage, tuple) and len(stage) == 2):
            return []
        if stage[0] != "Partition":
            return []
        partition = stage[1][0]
        index += 1
        predicates = []
        while index < len(stages) and stages[index][0] == "Select":
            predicates.append(stages[index][1][0])
            index += 1
        if index >= len(stages) or stages[index][0] != "Map":
            return []
        key_node, lookup_node = stages[index][1]
        if key_node[0] != "Key" or lookup_node[0] != "Lookup":
            return []
        feature = key_node[1][0]
        slot = lookup_node[1][0]
        if isinstance(slot, str) and slot.startswith("?"):
            declared = M.OP_SIGNATURES["Lookup"][0][0]
            found.append(ScopedSlotOccurrence(
                slot_name=slot, declared_type=declared,
                ast_path=(index, "Map", "Lookup"), block_index=block_index,
                local_prefix=(partition, tuple(predicates)),
                local_key_expression=feature))
        index += 1
        if index >= len(stages) or stages[index][0] != "Paint":
            return []
        index += 1
        block_index += 1
    return found


def _blocks(schema) -> list:
    """(partition, predicates, feature, slot_or_table) per block, in order."""
    out, stages = [], list(schema[1])
    index = 0
    while index < len(stages):
        partition = stages[index][1][0]
        index += 1
        predicates = []
        while index < len(stages) and stages[index][0] == "Select":
            predicates.append(stages[index][1][0])
            index += 1
        key_node, lookup_node = stages[index][1]
        out.append((partition, tuple(predicates), key_node[1][0],
                    lookup_node[1][0]))
        index += 2                       # Map, Paint
    return out


# --------------------------------------------------------------------------
# prefix execution: exact runtime semantics, no target information
# --------------------------------------------------------------------------

def _selected_sets(partition: str, predicates: Sequence[str],
                   grid: np.ndarray):
    builder = M.PARTITIONS.get(partition)
    if builder is None:
        return None
    sets = builder(grid)
    if sets is None:
        return None
    for predicate in predicates:            # applied in declared order
        test = M.PREDICATES.get(predicate)
        if test is None:
            return None
        sets = [s for s in sets if test(MI.descriptors(s, grid))]
    return list(sets)


# --------------------------------------------------------------------------
# the fitter
# --------------------------------------------------------------------------

def fit_induced_occurrences(schema, pairs, require_exact_replay: bool = True) -> tuple:
    """Fit every induced-slot occurrence independently.

    Returns (instantiated_schema, evidence) on success, or (None, evidence)
    with evidence["failure"] set to a code from FIT_FAILURES.

    require_exact_replay=True is the ADMISSION path: no fit succeeds unless the
    instantiated schema reproduces every demonstration exactly. The False mode
    exists only for the requirement-7 baseline audit, which must ask what a
    baseline schema DOES on the frozen probes even when it does not replay the
    demonstrations exactly (v1.1 had this shape because its learner and its
    exactness check were separate steps). Target admission never uses it.
    """
    evidence: dict = {"fitter": fitter_identity()[:16], "slots": {}}
    occs = occurrences(schema)
    if not occs:
        evidence["failure"] = "scoped_fit_failed"
        evidence["detail"] = "no induced occurrences / unparsable structure"
        return None, evidence
    blocks = _blocks(schema)

    #  constraints[(block_index, key)] -> {colour}
    constraints: dict = {}
    #  witnesses[(block_index, key)] -> set of demonstration indices
    witnesses: dict = {}
    #  keys ever produced by a block, and keys ever visibly witnessed
    hidden: dict = {i: set() for i in range(len(blocks))}
    observed: dict = {i: set() for i in range(len(blocks))}
    owned_change: dict = {i: 0 for i in range(len(blocks))}

    for demo_index, (grid_in, grid_out) in enumerate(pairs):
        grid_in = np.asarray(grid_in)
        grid_out = np.asarray(grid_out)
        if grid_in.shape != grid_out.shape:
            evidence["failure"] = "scoped_fit_failed"
            evidence["detail"] = "shape change is outside this grammar"
            return None, evidence
        changed = {(r, c) for r in range(grid_in.shape[0])
                   for c in range(grid_in.shape[1])
                   if int(grid_in[r, c]) != int(grid_out[r, c])}
        if not changed:
            evidence["failure"] = "scoped_fit_failed"
            evidence["detail"] = "demonstration changes nothing"
            return None, evidence

        #  per-block selected sets under exact prefix semantics. A block with
        #  zero Select stages simply runs no filter; nothing is rewritten into
        #  an implicit `all` predicate.
        per_block = []
        for partition, predicates, feature, _slot in blocks:
            builder = M.PARTITIONS.get(partition)
            if builder is None:
                evidence["failure"] = "scoped_fit_failed"
                evidence["detail"] = f"unknown partition {partition}"
                return None, evidence
            raw = builder(grid_in)
            if not raw:                       # v1.1 parity: empty partition fails
                evidence["failure"] = "scoped_fit_failed"
                evidence["detail"] = f"partition {partition} produced no sets"
                return None, evidence
            sets = _selected_sets(partition, predicates, grid_in)
            if sets is None:
                evidence["failure"] = "scoped_fit_failed"
                evidence["detail"] = f"prefix undefined for {partition}"
                return None, evidence
            per_block.append(sets)

        #  LAST-WRITER OWNERSHIP: a cell selected by several blocks shows the
        #  highest-index block's colour, so that block owns it.
        owner: dict = {}
        for block_index, sets in enumerate(per_block):
            for cells in sets:
                for cell in cells:
                    owner[cell] = block_index

        covered = set()
        for block_index, sets in enumerate(per_block):
            feature = blocks[block_index][2]
            for cells in sets:
                visible = frozenset(cell for cell in cells
                                    if owner.get(cell) == block_index)
                touched = visible & changed
                if not touched:
                    if not visible:
                        #  fully overwritten here: the key is produced but not
                        #  observable in this demonstration
                        key = MI.descriptors(cells, grid_in).get(feature)
                        if key is not None:
                            hidden[block_index].add(key)
                    continue
                #  v1.1 parity rule: a touched region must change entirely
                if touched != visible:
                    evidence["failure"] = "region_colour_conflict"
                    evidence["detail"] = (f"block {block_index} region partially "
                                          "changed")
                    return None, evidence
                key = MI.descriptors(cells, grid_in).get(feature)
                if key is None:
                    evidence["failure"] = "scoped_fit_failed"
                    evidence["detail"] = f"feature {feature} undefined on a region"
                    return None, evidence
                colours = {int(grid_out[cell]) for cell in visible}
                if len(colours) != 1:
                    evidence["failure"] = "region_colour_conflict"
                    evidence["detail"] = (f"block {block_index} region demands "
                                          f"{sorted(colours)}")
                    return None, evidence
                colour = colours.pop()
                slot_key = (block_index, key)
                previous = constraints.get(slot_key)
                if previous is not None and previous != colour:
                    evidence["failure"] = "slot_nonfunctional"
                    evidence["detail"] = (f"block {block_index} key "
                                          f"{key!r} demands "
                                          f"{previous} and {colour}")
                    return None, evidence
                constraints[slot_key] = colour
                witnesses.setdefault(slot_key, set()).add(demo_index)
                observed[block_index].add(key)
                owned_change[block_index] += 1
                covered |= set(visible)

        #  v1.1 parity rule: the blocks must JOINTLY explain exactly the change
        if covered != changed:
            evidence["failure"] = "scoped_fit_failed"
            evidence["detail"] = (f"covered {len(covered)} != changed "
                                  f"{len(changed)}")
            return None, evidence

    #  ---- observability and identifiability ----
    for block_index in range(len(blocks)):
        keys = {key for (b, key) in constraints if b == block_index}
        if not keys:
            evidence["failure"] = "slot_unobservable"
            evidence["detail"] = f"block {block_index} has no visible constraint"
            return None, evidence
        #  a key the block WOULD paint but which is never visible anywhere
        #  cannot be identified from the demonstrations. Vacuous for a single
        #  block (nothing can overwrite it), so single-block parity is kept.
        if hidden[block_index] - observed[block_index]:
            evidence["failure"] = "slot_key_unobserved"
            evidence["detail"] = (f"block {block_index} keys never visible: "
                                  f"{sorted(map(repr, hidden[block_index] - observed[block_index]))[:3]}")
            return None, evidence
        if owned_change[block_index] == 0:
            evidence["failure"] = "slot_unobservable"
            evidence["detail"] = f"block {block_index} changes no owned cell"
            return None, evidence
        for key in keys:
            if len(witnesses[(block_index, key)]) < MIN_KEY_WITNESSES:
                evidence["failure"] = "slot_key_unobserved"
                evidence["detail"] = (f"block {block_index} key {key!r} witnessed "
                                      f"by {len(witnesses[(block_index, key)])} "
                                      f"< {MIN_KEY_WITNESSES} demonstrations")
                return None, evidence

    #  ---- canonical tables, one per occurrence ----
    bindings = {}
    for occurrence in occs:
        block_index = occurrence.block_index
        #  keys are the raw descriptor values, exactly as the v1.1 learner's own
        #  table dict keyed them (reference lookup semantics); the ordering rule
        #  is the v1.1 rule, repr-sorted
        table = tuple(sorted(
            ((key, colour)
             for (b, key), colour in constraints.items() if b == block_index),
            key=lambda kv: repr(kv[0])))
        bindings[occurrence.slot_name] = table
        evidence["slots"][occurrence.slot_name] = {
            "block_index": block_index,
            "ast_path": list(occurrence.ast_path),
            "local_prefix": [occurrence.local_prefix[0],
                             list(occurrence.local_prefix[1])],
            "key_expression": occurrence.local_key_expression,
            "entries": len(table)}

    instantiated = M.instantiate(schema, bindings)

    if not require_exact_replay:
        evidence["exact_replay"] = False
        evidence["constraint_only"] = True
        return instantiated, evidence

    #  ---- mandatory exact replay; no fit succeeds without it ----
    for grid_in, grid_out in pairs:
        rendered = M.evaluate(instantiated, np.asarray(grid_in), MI.descriptors)
        if rendered is None or not np.array_equal(rendered, np.asarray(grid_out)):
            evidence["failure"] = "final_execution_mismatch"
            return None, evidence
    evidence["exact_replay"] = True
    return instantiated, evidence


# --------------------------------------------------------------------------
# key codec: typed, eval-free, reference semantics preserved
# --------------------------------------------------------------------------
#
# Constraint keys are the RAW descriptor values (ints, bools, None, nested
# tuples), used directly as dictionary keys exactly as the v1.1 learner used
# them, so lookup semantics are the reference semantics by construction (no
# Boolean/integer distinction is added or removed: Python's dict already treats
# True and 1 as one key, and no registered feature mixes the two). Serialization
# for evidence and audit uses the SAME typed JSON codec meta_ast uses for Lookup
# tables (json + tuple restoration); nothing is ever eval'd.

FIT_STATUSES = ("EXACT_DEMONSTRATION_FIT", "CONSTRAINT_CONSISTENT_BINDING",
                "FIT_FAILURE", "EXECUTION_ERROR", "RESOURCE_EXHAUSTED")


def encode_key(value) -> str:
    """Typed, canonical text for a descriptor value (tuples become JSON arrays)."""
    return json.dumps(value, default=list, sort_keys=True)


def decode_key(text: str):
    """Inverse of encode_key: JSON arrays become tuples again, so the decoded
    value is usable as a Lookup key with reference dict semantics."""
    return M._tuplify(json.loads(text))


def fitter_options(require_exact_replay: bool = True) -> dict:
    """Every scientific option the fitter runs under, recorded on both the
    baseline and the target path (hash equality alone is not fairness)."""
    return {"require_exact_replay": bool(require_exact_replay),
            "min_key_witnesses": MIN_KEY_WITNESSES,
            "cell_ownership": "last_writer",
            "touched_region_must_change_entirely": True,
            "blocks_must_jointly_cover_change": True,
            "key_codec": "raw_value_keys+typed_json"}


def fit_outcome(schema, pairs, *, require_exact_replay: bool = True,
                deadline=None) -> dict:
    """Structured fitting result with explicit, separated outcomes.

        EXACT_DEMONSTRATION_FIT       bindings found AND every demo replays exactly
        CONSTRAINT_CONSISTENT_BINDING bindings found; exact replay NOT required
                                      or not established (inspection only; never
                                      certifies or admits a target)
        FIT_FAILURE                   the declared fitter found no bindings (code)
        EXECUTION_ERROR               the fitter or evaluator raised (never
                                      converted into a scientific failure)
        RESOURCE_EXHAUSTED            the caller's deadline had already passed
    """
    result = {"fitter_identity": fitter_identity(),
              "options": fitter_options(require_exact_replay),
              "status": None, "code": None, "detail": "", "program": None,
              "evidence": {}}
    if deadline is not None and time.monotonic() > deadline:
        result.update(status="RESOURCE_EXHAUSTED", code="deadline_before_start")
        return result
    try:
        program, evidence = fit_induced_occurrences(
            schema, pairs, require_exact_replay=require_exact_replay)
    except Exception as error:                                    # noqa: BLE001
        result.update(status="EXECUTION_ERROR", code=type(error).__name__,
                      detail=repr(error)[:200])
        return result
    result["evidence"] = evidence
    if program is None:
        result.update(status="FIT_FAILURE", code=evidence.get("failure"),
                      detail=evidence.get("detail", ""))
        return result
    result["program"] = program
    result["status"] = ("EXACT_DEMONSTRATION_FIT" if evidence.get("exact_replay")
                        else "CONSTRAINT_CONSISTENT_BINDING")
    return result


# --------------------------------------------------------------------------
# fairness: the base search must use THIS fitter
# --------------------------------------------------------------------------

def baseline_single_block_schemas() -> list:
    """The complete family-(1,) product, built from the frozen terminals."""
    out = []
    for partition in sorted(M.PARTITIONS):
        for predicate in sorted(M.PREDICATES):
            for feature in M.KEY_FEATURES:
                out.append(("Compose", (
                    ("Partition", (partition,)),
                    ("Select", (predicate,)),
                    ("Map", (("Key", (feature,)), ("Lookup", ("?0",)))),
                    ("Paint", ()))))
    return out


def base_search_with_scoped_fitter(pairs) -> dict:
    """The fixed single-block search, fitted with the SAME scoped fitter.

    Two distinct pieces of evidence are recorded, never inferred from each
    other:
      exact   - schemas that fit AND replay every demonstration exactly
                (requirement 4 fixed-base failure, requirement 6 exclusion)
      fitted  - schemas whose occurrence constraints are satisfiable at all,
                including those that do not replay exactly; these are the
                candidates the requirement-7 frozen-probe witness-separation
                audit must compare against.
    """
    exact, fitted = [], []
    for schema in baseline_single_block_schemas():
        strict, _ = fit_induced_occurrences(schema, pairs)
        if strict is not None:
            exact.append((schema, strict))
            fitted.append((schema, strict))
            continue
        loose, _ = fit_induced_occurrences(schema, pairs,
                                           require_exact_replay=False)
        if loose is not None:
            fitted.append((schema, loose))
    return {"enumerated": len(baseline_single_block_schemas()),
            "fitted": len(fitted), "exact": len(exact),
            "exact_schemas": [s for s, _ in exact],
            "fitted_pairs": fitted,
            "fitter": fitter_identity()[:16]}
