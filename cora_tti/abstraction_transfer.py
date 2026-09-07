"""Prospective abstraction-transfer experiment: do source-derived abstractions
help the complete reasoner on separate tasks?

Hypothesis under test, stated before measurement:

    Do abstractions formed from discovered source programs improve correct
    target predictions or search efficiency more than retaining concrete
    schemas alone, and more than an unlearned control exposing the same
    hypothesis space?

Everything here uses existing components. No new solver, learner, induced type
or semantic constructor. The fitter, executor, acceptance rule and output
selection are identical across every policy.

WHAT THE EXISTING ANTI-UNIFIER SUPPORTS, MEASURED, NOT ASSUMED
    meta_ast.anti_unify assigns fresh slot names ?0, ?1, ... in traversal order.
    Our discovered structures are OPEN schemas whose Lookup arguments are
    already named ?0 and ?1. Anti-unifying them directly therefore COLLIDES:
    free_slot_types then reports the partition and predicate slots as
    Map[FeatureValue,Colour] (reading the Lookup positions), and instantiating
    an enumerable slot would overwrite a table slot and corrupt the program.
    Verified directly on library entries before this experiment was designed.

    The declared workaround is bookkeeping only, and it does not broaden the
    implementation: every Lookup argument is replaced by the literal () before
    anti-unification, so the inputs contain no slots at all; afterwards the
    created slots are renumbered above the block count and the Lookup arguments
    are restored to the canonical ?0 .. ?{blocks-1}. Types are then read from
    the grammar in the ordinary way, enumerable slots take values only from the
    existing legal vocabulary, and induced maps are fitted only from the
    current task's own demonstrations.

COST DISCIPLINE
    One unit is one candidate fit attempt against the target's demonstrations.
    A concept is NOT one unit: it expands into one unit per enumerable binding.
    Library lookups that fail are charged. Fallback search is charged.
    Acquisition charges EVERY source search, successful or not.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

EXPERIMENT_VERSION = "abstraction_transfer:v1"
POLICIES = ("A_ordinary", "B_concrete_then_ordinary",
            "C_concepts_then_ordinary", "D_control_then_ordinary")


# --------------------------------------------------------------------------
# abstraction: the declared, source-only rule
# --------------------------------------------------------------------------

def _table_free(schema):
    """Replace every Lookup argument with the literal (), so the AST contains
    no slot names for anti_unify to collide with."""
    stages = []
    for stage in schema[1]:
        if stage[0] == "Map":
            key_node, lookup_node = stage[1]
            stages.append(("Map", (key_node, ("Lookup", ((),)))))
        else:
            stages.append(stage)
    return ("Compose", tuple(stages))


def _restore_tables(schema, n_blocks: int):
    """Rename anti_unify's created slots above the block count and restore the
    canonical table slots ?0 .. ?{n_blocks-1}."""
    created = sorted({s for s in _slot_names(schema)}, key=lambda x: int(x[1:]))
    rename = {name: f"?{n_blocks + index}" for index, name in enumerate(created)}
    renamed = _rename_slots(schema, rename)
    stages, block = [], 0
    for stage in renamed[1]:
        if stage[0] == "Map":
            key_node, _lookup = stage[1]
            stages.append(("Map", (key_node, ("Lookup", (f"?{block}",)))))
            block += 1
        else:
            stages.append(stage)
    return ("Compose", tuple(stages)), rename


def _slot_names(node) -> set:
    out = set()
    if isinstance(node, str) and node.startswith("?"):
        return {node}
    if isinstance(node, tuple) and len(node) == 2 and isinstance(node[0], str) \
            and node[0] in M._OPS:
        for arg in node[1]:
            out |= _slot_names(arg)
    elif isinstance(node, tuple):
        for arg in node:
            out |= _slot_names(arg)
    return out


def _rename_slots(node, rename: dict):
    if isinstance(node, str) and node in rename:
        return rename[node]
    if isinstance(node, tuple) and len(node) == 2 and isinstance(node[0], str) \
            and node[0] in M._OPS:
        return (node[0], tuple(_rename_slots(a, rename) for a in node[1]))
    if isinstance(node, tuple):
        return tuple(_rename_slots(a, rename) for a in node)
    return node


@dataclass
class Concept:
    """A learned abstraction: a schema with typed enumerable slots free."""
    name: str
    schema: tuple
    n_blocks: int
    sources: tuple                 # the source episodes whose programs formed it
    member_digests: tuple          # the concrete structures generalized
    enumerable: dict = field(default_factory=dict)   # slot -> type
    induced: dict = field(default_factory=dict)

    def expansion(self) -> int:
        total = 1
        for slot_type in self.enumerable.values():
            total *= max(1, len(M.slot_domain(slot_type)))
        return total

    def instantiations(self):
        """Every legal binding of the enumerable slots, deterministic order."""
        slots = sorted(self.enumerable)
        domains = [tuple(M.slot_domain(self.enumerable[s])) for s in slots]
        for binding in itertools.product(*domains):
            yield M.instantiate(self.schema, dict(zip(slots, binding)))

    def to_json(self) -> dict:
        return {"name": self.name, "n_blocks": self.n_blocks,
                "sources": list(self.sources),
                "member_digests": [d[:16] for d in self.member_digests],
                "members": len(self.member_digests),
                "enumerable_slots": dict(self.enumerable),
                "induced_slots": dict(self.induced),
                "expansion": self.expansion(),
                "canonical": CV.canonical(self.schema)}


def abstract_group(name: str, schemas: list, sources: tuple) -> Optional[Concept]:
    """Anti-unify a group of discovered open schemas into one concept.

    Returns None when anti_unify finds nothing to abstract, which happens when
    the group has fewer than two members or the members are identical.
    """
    if len(schemas) < 2:
        return None
    n_blocks = len(CV.blocks_from_ast(schemas[0]))
    result = M.anti_unify([_table_free(s) for s in schemas])
    if result is None:
        return None
    generalized, _slots = result
    schema, _rename = _restore_tables(generalized, n_blocks)
    types = M.free_slot_types(schema)
    enumerable = {s: t for s, t in types.items() if t in M.ENUMERABLE_TYPES}
    induced = {s: t for s, t in types.items() if t in M.INDUCED_TYPES}
    if not enumerable:
        return None                     # nothing was generalized beyond tables
    return Concept(name=name, schema=schema, n_blocks=n_blocks, sources=sources,
                   member_digests=tuple(CV.digest(s) for s in schemas),
                   enumerable=enumerable, induced=induced)


def control_concept(learned: Concept, name: str) -> Concept:
    """The unlearned control: the SAME free slot positions and therefore the
    same hypothesis-space size, but every FIXED position filled from the first
    terminal in vocabulary order rather than from anything discovered.

    This separates "the learning chose useful terminals" from "the concept
    simply exposed more search choices"."""
    v = CV.vocab()
    first = {"PartitionExpr": v["partitions"][0], "Predicate": v["predicates"][0],
             "FeatureExpr": v["key_features"][0]}
    blocks = []
    for partition, selects, feature in _concept_blocks(learned.schema):
        blocks.append((
            partition if _is_slot(partition) else first["PartitionExpr"],
            tuple(s if _is_slot(s) else first["Predicate"] for s in selects),
            feature if _is_slot(feature) else first["FeatureExpr"]))
    schema = _concept_from_blocks(blocks)
    types = M.free_slot_types(schema)
    return Concept(name=name, schema=schema, n_blocks=learned.n_blocks,
                   sources=(), member_digests=(),
                   enumerable={s: t for s, t in types.items() if t in M.ENUMERABLE_TYPES},
                   induced={s: t for s, t in types.items() if t in M.INDUCED_TYPES})


def _is_slot(value) -> bool:
    return isinstance(value, str) and value.startswith("?")


def _concept_blocks(schema) -> list:
    """Structural parse that tolerates slot-valued terminals."""
    out, stages, index = [], list(schema[1]), 0
    while index < len(stages):
        partition = stages[index][1][0]
        index += 1
        selects = []
        while index < len(stages) and stages[index][0] == "Select":
            selects.append(stages[index][1][0])
            index += 1
        key_node, _lookup = stages[index][1]
        out.append((partition, tuple(selects), key_node[1][0]))
        index += 2
    return out


def _concept_from_blocks(blocks) -> tuple:
    stages = []
    for index, (partition, selects, feature) in enumerate(blocks):
        stages.append(("Partition", (partition,)))
        for predicate in selects:
            stages.append(("Select", (predicate,)))
        stages.append(("Map", (("Key", (feature,)), ("Lookup", (f"?{index}",)))))
        stages.append(("Paint", ()))
    return ("Compose", tuple(stages))


# --------------------------------------------------------------------------
# one common target-time procedure, identical across policies
# --------------------------------------------------------------------------

def _score(program, heldout) -> dict:
    correct = defined = 0
    for grid_in, grid_out in heldout:
        rendered = M.evaluate(program, np.asarray(grid_in), MI.descriptors)
        if rendered is None:
            continue
        defined += 1
        correct += int(np.array_equal(rendered, np.asarray(grid_out)))
    return {"heldout_defined": defined, "heldout_total": len(heldout),
            "heldout_correct": defined == len(heldout) and correct == len(heldout)}


def run_policy(policy: str, episode, budget: int, concrete_library, concepts,
               ordinary_space) -> dict:
    """Try the policy's prior phase, then fall back to ordinary search with the
    remaining budget. Programs already attempted are never re-attempted."""
    started = time.perf_counter()
    attempted, used = set(), 0
    phase_used = {"prior": 0, "fallback": 0}

    def attempt(schema):
        nonlocal used
        digest = CV.digest(schema)
        if digest in attempted:
            return None
        attempted.add(digest)
        used += 1
        outcome = SF.fit_outcome(schema, episode.pairs, require_exact_replay=True)
        return outcome if outcome["status"] == "EXACT_DEMONSTRATION_FIT" else None

    found, phase, source = None, None, None
    if policy != "A_ordinary":
        prior = []
        if policy == "B_concrete_then_ordinary":
            prior = [("entry", e["digest"], e["schema"]) for e in concrete_library]
        else:
            for concept in concepts:
                for instantiated in concept.instantiations():
                    prior.append(("concept", concept.name, instantiated))
        for kind, label, schema in prior:
            if used >= budget:
                break
            outcome = attempt(schema)
            phase_used["prior"] = used
            if outcome is not None:
                found, phase, source = (schema, outcome["program"]), "prior", label
                break
    if found is None:
        before = used
        for candidate in ordinary_space:
            if used >= budget:
                break
            outcome = attempt(FS.schema_of(candidate))
            if outcome is not None:
                found = (FS.schema_of(candidate), outcome["program"])
                phase, source = "fallback", "ordinary"
                break
        phase_used["fallback"] = used - before
    result = {"policy": policy, "solved": found is not None, "units": used,
              "prior_units": phase_used["prior"], "fallback_units": phase_used["fallback"],
              "phase": phase, "source": source,
              "seconds": round(time.perf_counter() - started, 3)}
    if found is not None:
        schema, program = found
        result["found_digest"] = CV.digest(schema)
        result["exact_ast_recovered"] = CV.digest(schema) == episode.target_digest
        result.update(_score(program, episode.heldout))
    return result


def experiment_code_hash() -> str:
    names = ("cora_tti/abstraction_transfer.py", "cora_tti/failure_signal_study.py",
             "cora_tti/scoped_slot_fitting.py", "cora_tti/meta_baseline.py")
    parts = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()
