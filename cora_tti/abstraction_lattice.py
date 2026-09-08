"""LAS-v1: mechanical abstraction lattice over discovered source programs.

The previous experiment used one hand-authored anti-unification per group and
found that grouping by family generalized every terminal position, recreating
the search space. The question now is whether the system can SELECT the level of
abstraction from source-side evidence instead of a researcher choosing it.

THE LATTICE
    A discovered two-block program has eligible terminal positions: for each
    block a partition, zero or more predicates, and a key feature. A candidate
    abstraction is a MASK over those positions: each is either kept CONSTANT or
    promoted to a typed enumerable SLOT.

    For a group of programs, a mask is admissible only if every member agrees on
    every position the mask keeps constant. So the admissible masks for a group
    are exactly the supersets of its DISAGREEMENT SET, and the minimal element is
    what anti-unification produces. anti_unify's answer is therefore ONE point in
    this lattice and is treated as a candidate, never as the optimum.

    Induced Lookup tables are never freed as enumerable terminals. They stay
    induced from the target's own demonstrations by the existing scoped fitter.

THE SLOT-NAMESPACE ADAPTER
    meta_ast.anti_unify assigns slots ?0, ?1, ... which collide with the induced
    table slots already named ?0 .. ?{blocks-1} in open constructive schemas.
    Verified: free_slot_types then reports the partition and predicate slots as
    Map[FeatureValue,Colour], and instantiating one would overwrite a table.

    This module does not rely on a string workaround. It builds abstractions
    directly, reserving the table-slot identifiers and drawing abstraction slots
    from a DISJOINT offset range. Table-slot identities are never altered, so a
    concept instantiated at every abstraction slot is byte-identical to the
    concrete member it came from. Differential tests check exactly that.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402

LATTICE_VERSION = "abstraction_lattice:v1"

#: abstraction slots start here, far above any table slot, so the two namespaces
#: are disjoint by construction rather than by convention
ABSTRACTION_SLOT_OFFSET = 100

#: position kinds and the declared slot type each promotes to
POSITION_TYPES = {"partition": "PartitionExpr", "predicate": "Predicate",
                  "feature": "FeatureExpr"}


def positions_of(blocks) -> list:
    """Eligible terminal positions of a block list, in canonical order.

    Each is (kind, block_index, sub_index). Lookup tables are NOT positions.
    """
    out = []
    for block_index, (_partition, selects, _feature) in enumerate(blocks):
        out.append(("partition", block_index, 0))
        for select_index in range(len(selects)):
            out.append(("predicate", block_index, select_index))
        out.append(("feature", block_index, 0))
    return out


def value_at(blocks, position):
    kind, block_index, sub_index = position
    partition, selects, feature = blocks[block_index]
    if kind == "partition":
        return partition
    if kind == "predicate":
        return selects[sub_index]
    return feature


def compatible(group_blocks) -> bool:
    """Members must share one position layout to be masked together."""
    if not group_blocks:
        return False
    first = positions_of(group_blocks[0])
    return all(positions_of(b) == first for b in group_blocks)


def disagreement(group_blocks) -> frozenset:
    """Positions where the members do not all agree. The minimal admissible
    mask, and exactly what anti-unification would free."""
    base = positions_of(group_blocks[0])
    return frozenset(p for p in base
                     if len({value_at(b, p) for b in group_blocks}) > 1)


@dataclass(frozen=True)
class Abstraction:
    """One point of the lattice: a schema with a declared set of typed slots."""
    name: str
    schema: tuple
    mask: frozenset                  # positions promoted to slots
    n_blocks: int
    slot_types: dict                 # abstraction slot -> declared type
    member_digests: tuple
    source_episodes: tuple
    group_key: str

    def expansion(self) -> int:
        total = 1
        for slot_type in self.slot_types.values():
            total *= max(1, len(M.slot_domain(slot_type)))
        return total

    def mdl(self) -> int:
        return CV.mdl(self.schema)

    def instantiations(self):
        """Every legal binding of the abstraction slots, deterministic order.
        Values come only from the existing vocabulary domains."""
        slots = sorted(self.slot_types, key=lambda s: int(s[1:]))
        domains = [tuple(M.slot_domain(self.slot_types[s])) for s in slots]
        for binding in itertools.product(*domains):
            yield M.instantiate(self.schema, dict(zip(slots, binding)))

    def digest(self) -> str:
        return hashlib.sha256(CV.canonical(self.schema).encode()).hexdigest()

    def to_json(self) -> dict:
        return {"name": self.name, "group_key": self.group_key,
                "mask": sorted(list(p) for p in self.mask),
                "n_blocks": self.n_blocks,
                "slot_types": dict(sorted(self.slot_types.items())),
                "abstraction_slots": len(self.slot_types),
                "expansion": self.expansion(), "mdl": self.mdl(),
                "members": len(self.member_digests),
                "member_digests": [d[:16] for d in self.member_digests],
                "source_episodes": list(self.source_episodes),
                "canonical": CV.canonical(self.schema),
                "digest": self.digest()}


def build(name: str, group_blocks: list, mask: frozenset, member_digests,
          source_episodes, group_key: str) -> Optional[Abstraction]:
    """Construct the abstraction for one group and one admissible mask.

    Constants come from the group, which is why the mask must cover every
    disagreement. Abstraction slots are drawn from the disjoint offset range and
    the table slots keep their canonical identifiers.
    """
    if not compatible(group_blocks):
        return None
    if not mask:
        return None                                  # at least one abstracted
    if not (disagreement(group_blocks) <= mask):
        return None                                  # a constant would be ambiguous
    reference = group_blocks[0]
    n_blocks = len(reference)
    slot_types, counter = {}, ABSTRACTION_SLOT_OFFSET
    blocks = []
    for block_index, (partition, selects, feature) in enumerate(reference):
        new_partition = partition
        if ("partition", block_index, 0) in mask:
            new_partition = f"?{counter}"
            slot_types[new_partition] = POSITION_TYPES["partition"]
            counter += 1
        new_selects = []
        for select_index, predicate in enumerate(selects):
            if ("predicate", block_index, select_index) in mask:
                name_ = f"?{counter}"
                slot_types[name_] = POSITION_TYPES["predicate"]
                counter += 1
                new_selects.append(name_)
            else:
                new_selects.append(predicate)
        new_feature = feature
        if ("feature", block_index, 0) in mask:
            new_feature = f"?{counter}"
            slot_types[new_feature] = POSITION_TYPES["feature"]
            counter += 1
        blocks.append((new_partition, tuple(new_selects), new_feature))
    schema = _schema_from(blocks)
    #  the table slots must be untouched and correctly typed
    types = M.free_slot_types(schema)
    for index in range(n_blocks):
        if types.get(f"?{index}") != "Map[FeatureValue,Colour]":
            return None
    for slot, declared in slot_types.items():
        if types.get(slot) != declared:
            return None
    return Abstraction(name=name, schema=schema, mask=frozenset(mask),
                       n_blocks=n_blocks, slot_types=slot_types,
                       member_digests=tuple(member_digests),
                       source_episodes=tuple(sorted(set(source_episodes))),
                       group_key=group_key)


def _schema_from(blocks) -> tuple:
    stages = []
    for index, (partition, selects, feature) in enumerate(blocks):
        stages.append(("Partition", (partition,)))
        for predicate in selects:
            stages.append(("Select", (predicate,)))
        stages.append(("Map", (("Key", (feature,)), ("Lookup", (f"?{index}",)))))
        stages.append(("Paint", ()))
    return ("Compose", tuple(stages))


def lattice_for(group_blocks: list, member_digests, source_episodes,
                group_key: str, max_expansion: int) -> list:
    """Every admissible mask for one group, capped by expansion size.

    The masks are the supersets of the disagreement set, so the minimal element
    is the anti-unification and the maximal frees every position.
    """
    if not compatible(group_blocks):
        return []
    base = positions_of(group_blocks[0])
    required = disagreement(group_blocks)
    optional = [p for p in base if p not in required]
    out = []
    for extra_count in range(len(optional) + 1):
        for extra in itertools.combinations(optional, extra_count):
            mask = frozenset(required | set(extra))
            if not mask:
                continue
            name = f"{group_key}|m{len(mask)}:{_mask_tag(mask, base)}"
            abstraction = build(name, group_blocks, mask, member_digests,
                                source_episodes, group_key)
            if abstraction is None:
                continue
            if abstraction.expansion() > max_expansion:
                continue
            out.append(abstraction)
    return sorted(out, key=lambda a: (a.expansion(), a.mdl(), a.digest()))


def _mask_tag(mask, base) -> str:
    return "".join("1" if p in mask else "0" for p in base)


def matched_control(learned: Abstraction, name: str) -> Optional[Abstraction]:
    """An unlearned abstraction with the SAME mask, therefore the same number of
    free positions and the same candidate-space cardinality, whose CONSTANT
    positions come from the first terminal in vocabulary order rather than from
    any source discovery."""
    v = CV.vocab()
    first = {"partition": v["partitions"][0], "predicate": v["predicates"][0],
             "feature": v["key_features"][0]}
    blocks = _concept_blocks(learned.schema)
    control_blocks = []
    for partition, selects, feature in blocks:
        control_blocks.append((
            partition if _is_slot(partition) else first["partition"],
            tuple(s if _is_slot(s) else first["predicate"] for s in selects),
            feature if _is_slot(feature) else first["feature"]))
    schema = _schema_from(control_blocks)
    types = M.free_slot_types(schema)
    slot_types = {s: t for s, t in types.items()
                  if t in M.ENUMERABLE_TYPES}
    control = Abstraction(name=name, schema=schema, mask=learned.mask,
                          n_blocks=learned.n_blocks, slot_types=slot_types,
                          member_digests=(), source_episodes=(),
                          group_key="matched_control")
    if control.expansion() != learned.expansion():
        return None
    return control


def _is_slot(value) -> bool:
    return isinstance(value, str) and value.startswith("?")


def _concept_blocks(schema) -> list:
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


def blocks_of_concrete(schema) -> list:
    return CV.blocks_from_ast(schema)


def round_trip(abstraction: Abstraction) -> bool:
    """Serialization must preserve the schema exactly."""
    restored = M.ast_from_json(M.ast_to_json(abstraction.schema))
    return CV.canonical(restored) == CV.canonical(abstraction.schema)


def code_hash() -> str:
    return hashlib.sha256((ROOT / "cora_tti" / "abstraction_lattice.py").read_bytes()).hexdigest()
