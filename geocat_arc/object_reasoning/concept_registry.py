"""Concepts: schemas the anti-unifier extracted from independent discoveries.

A concept is not written here and it is not written anywhere else.  It comes
into existence when two or more programs, discovered separately on separate
tasks, turn out to share machinery: the least general generalization of
their ASTs, with the positions where they disagreed left as typed slots.

Storing one is not the same as trusting one.  A concept starts
``provisional``; it earns ``independent-transfer`` only when a task that
played no part in creating it is solved by a program that instantiates it,
through the ordinary gate, and removing the concept removes that solve.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import meta_ast


@dataclass
class ConceptRecord:
    """One learned schema plus everything needed to distrust it."""
    name: str
    schema: tuple                       # AST with "?n" slots
    slots: tuple = ()                   # slot descriptors from anti-unification
    provenance: tuple = ()              # tasks whose programs produced it
    concept_class: str = ""             # shape of the machinery it captures
    status: str = "provisional"         # provisional | independent-transfer
    transfer_witnesses: tuple = ()      # tasks outside provenance it enabled
    search_stats: dict = field(default_factory=dict)
    falsification: dict = field(default_factory=dict)

    @property
    def digest(self) -> str:
        payload = json.dumps(meta_ast.ast_to_json(self.schema), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def free_slots(self) -> tuple:
        """Slot names in deterministic order."""
        names: list = []

        def walk(node):
            if isinstance(node, str) and node.startswith("?"):
                if node not in names:
                    names.append(node)
                return
            if isinstance(node, tuple) and len(node) == 2 \
                    and isinstance(node[0], str):
                for arg in node[1]:
                    walk(arg)

        walk(self.schema)
        return tuple(names)

    @property
    def signature(self) -> str:
        """Explicit typing of the free slots, e.g.
        ``(?0 : FeatureExpr, ?1 : Map[FeatureValue, Colour]) -> GridTransform``.
        Persisted so "typed grammar invention" is a checkable claim."""
        return meta_ast.type_signature(self.schema)

    @property
    def slot_types(self) -> dict:
        return meta_ast.free_slot_types(self.schema)

    def to_dict(self) -> dict:
        return {"name": self.name,
                "signature": self.signature,
                "slot_types": self.slot_types,
                "schema": meta_ast.ast_to_json(self.schema),
                "slots": list(self.slots),
                "free_slots": list(self.free_slots),
                "provenance": list(self.provenance),
                "concept_class": self.concept_class,
                "status": self.status,
                "transfer_witnesses": list(self.transfer_witnesses),
                "search_stats": dict(self.search_stats),
                "falsification": dict(self.falsification),
                "digest": self.digest}

    @staticmethod
    def from_dict(d: dict) -> "ConceptRecord":
        return ConceptRecord(
            name=d["name"],
            schema=_schema_from_json(d["schema"]),
            slots=tuple(d.get("slots", ())),
            provenance=tuple(d.get("provenance", ())),
            concept_class=d.get("concept_class", ""),
            status=d.get("status", "provisional"),
            transfer_witnesses=tuple(d.get("transfer_witnesses", ())),
            search_stats=dict(d.get("search_stats", {})),
            falsification=dict(d.get("falsification", {})))


def _schema_from_json(d):
    """Like ast_from_json but tolerates "?n" slot strings in argument slots."""
    if isinstance(d, str):
        return d
    if isinstance(d, dict) and "lit" in d:
        return meta_ast._tuplify(json.loads(d["lit"]))
    args = []
    for a in d["args"]:
        if isinstance(a, dict) and "slot" in a:
            args.append(a["slot"])
        elif isinstance(a, dict) and "op" in a:
            args.append(_schema_from_json(a))
        elif isinstance(a, dict) and "lit" in a:
            value = json.loads(a["lit"])
            # a slot round-trips as a plain "?n" string, not a JSON literal
            args.append(value if isinstance(value, str) and value.startswith("?")
                        else meta_ast._tuplify(value))
        else:
            args.append(a)
    return (d["op"], tuple(args))


class ConceptLibrary:
    """Append-only registry of learned schemas (JSON file)."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._concepts: dict = {}
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text())
                for name, d in stored.items():
                    self._concepts[name] = ConceptRecord.from_dict(d)
            except Exception:
                self._concepts = {}

    def __len__(self) -> int:
        return len(self._concepts)

    def concepts(self) -> list:
        return [self._concepts[n] for n in sorted(self._concepts)]

    def get(self, name: str) -> Optional[ConceptRecord]:
        return self._concepts.get(name)

    def register(self, concept: ConceptRecord) -> None:
        self._concepts[concept.name] = concept
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {n: c.to_dict() for n, c in sorted(self._concepts.items())},
            indent=1))

    def next_name(self) -> str:
        """Generated names only: a concept is identified, not christened."""
        return f"concept_{len(self._concepts) + 1:04d}"


def learn_concepts(programs_by_task: dict, library: ConceptLibrary,
                   min_provenance: int = 2) -> list:
    """Anti-unify independently discovered ASTs into schemas.

    ``programs_by_task`` maps task id -> discovered AST.  Every combination
    is not tried: ASTs are grouped by their operator skeleton first (cheap,
    deterministic), and a group of at least ``min_provenance`` tasks becomes
    one concept.  A generalization with no free slot is discarded -- if the
    discoveries were identical, nothing was abstracted.
    """
    if len(programs_by_task) < min_provenance:
        return []
    groups: dict = {}
    for task_id, ast in sorted(programs_by_task.items()):
        groups.setdefault(_skeleton(ast), []).append((task_id, ast))
    learned = []
    for skeleton, members in sorted(groups.items()):
        if len(members) < min_provenance:
            continue
        asts = [ast for _, ast in members]
        result = meta_ast.anti_unify(asts)
        if result is None:
            continue
        schema, slots = result
        existing = next((c for c in library.concepts()
                         if c.schema == schema), None)
        if existing is not None:
            continue
        concept = ConceptRecord(
            name=library.next_name(),
            schema=schema,
            slots=tuple(json.dumps(s, sort_keys=True) for s in slots),
            provenance=tuple(task_id for task_id, _ in members),
            concept_class=skeleton)
        library.register(concept)
        learned.append(concept)
    return learned


def _skeleton(ast) -> str:
    """Operator shape, ignoring every literal -- the grouping key."""
    op, args = ast
    parts = [op]
    for arg in args:
        if isinstance(arg, tuple) and len(arg) == 2 \
                and isinstance(arg[0], str) and arg[0] in meta_ast._OPS:
            parts.append(_skeleton(arg))
    return "(" + " ".join(parts) + ")"
