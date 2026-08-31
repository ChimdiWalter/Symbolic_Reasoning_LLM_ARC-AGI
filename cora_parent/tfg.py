"""Concrete Typed Failure Graph (TFG): the domain-general failure representation.

Implements cora_parent.interfaces.TypedFailureGraph as pure data with a canonical,
hash-stable serialization and a JSON round trip. Domain producers (the ARC extractor,
later a scientific-domain extractor) BUILD these; the localizer, GPN and reasoning
world model CONSUME them. This module performs no file I/O and knows nothing about any
particular task corpus.

Identity discipline: a TFG carries mechanistic evidence only. Attribute keys that
could smuggle identity ("task_id", "task", "family", "label", "source_token") are
rejected at construction time — the graph is anonymous by construction, matching the
blinding requirements of docs/CORA_DATA_ACCESS_DAG.md.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Hashable, Mapping, Sequence

from cora_parent.interfaces import TypedFailureGraph

#: Frozen node-kind vocabulary. Producers may use exactly these.
NODE_KINDS = (
    "frontier_term",     # a program node at the failure frontier
    "type",              # a domain type
    "goal",              # the goal type / target structure
    "value_signature",   # observed values of a frontier term on the demonstrations
    "delta_signature",   # observed input->output delta class
    "shape_change",      # cardinality / geometry change evidence
    "palette_change",    # symbol-set change evidence
    "relation_change",   # object/region relation change evidence
    "substructure",      # repeated substructure evidence
    "slot",              # a parameter slot (fit or unfit)
    "execution",         # a non-exact execution record
    "obligation",        # a verifier-derived proof obligation
    "cause",             # verifier failure class
)

#: Frozen edge-relation vocabulary.
EDGE_RELATIONS = (
    "has_type", "produces", "consumes", "blocks", "depends_on", "observed_on",
    "violates", "fits", "fails", "contains", "adjacent_to", "derived_from",
)

#: Attribute keys that would smuggle identity into an anonymous graph.
FORBIDDEN_ATTR_KEYS = ("task_id", "task", "family", "label", "source_token", "token")


class IdentityLeak(ValueError):
    """An attribute key that could carry task identity was rejected."""


def _check_attrs(attrs: Mapping[str, Any]) -> None:
    for key in attrs:
        lowered = key.lower()
        for banned in FORBIDDEN_ATTR_KEYS:
            if lowered == banned:
                raise IdentityLeak(f"attribute key {key!r} is forbidden in a TFG")


@dataclass(frozen=True)
class TFGNode:
    node_id: str
    kind: str
    type_str: str = ""
    attrs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in NODE_KINDS:
            raise ValueError(f"unknown TFG node kind {self.kind!r}")
        _check_attrs(self.attrs)


@dataclass(frozen=True)
class TFGEdge:
    src: str
    relation: str
    dst: str

    def __post_init__(self):
        if self.relation not in EDGE_RELATIONS:
            raise ValueError(f"unknown TFG edge relation {self.relation!r}")


class ConcreteTFG(TypedFailureGraph):
    """Immutable typed failure graph with canonical hashing."""

    def __init__(self, frontier_type: str, goal_type: str,
                 nodes: Sequence[TFGNode], edges: Sequence[TFGEdge]):
        ids = [n.node_id for n in nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate node ids")
        known = set(ids)
        for e in edges:
            if e.src not in known or e.dst not in known:
                raise ValueError(f"edge {e} references an unknown node")
        self._interface = (frontier_type, goal_type)
        self._nodes = tuple(sorted(nodes, key=lambda n: n.node_id))
        self._edges = tuple(sorted(edges, key=lambda e: (e.src, e.relation, e.dst)))

    # -- TypedFailureGraph interface ---------------------------------------
    def nodes(self) -> Sequence[Hashable]:
        return self._nodes

    def edges(self) -> Sequence[tuple[Hashable, str, Hashable]]:
        return tuple((e.src, e.relation, e.dst) for e in self._edges)

    def interface(self) -> tuple[str, str]:
        return self._interface

    def canonical(self) -> str:
        return json.dumps(self.to_json(), sort_keys=True)

    # -- serialization ------------------------------------------------------
    def to_json(self) -> dict:
        return {
            "interface": list(self._interface),
            "nodes": [{"id": n.node_id, "kind": n.kind, "type": n.type_str,
                       "attrs": dict(sorted(n.attrs.items()))} for n in self._nodes],
            "edges": [[e.src, e.relation, e.dst] for e in self._edges],
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "ConcreteTFG":
        nodes = [TFGNode(n["id"], n["kind"], n.get("type", ""),
                         dict(n.get("attrs", {}))) for n in data["nodes"]]
        edges = [TFGEdge(*e) for e in data["edges"]]
        return cls(data["interface"][0], data["interface"][1], nodes, edges)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    # -- convenience for consumers -----------------------------------------
    def nodes_of_kind(self, kind: str) -> Sequence[TFGNode]:
        return tuple(n for n in self._nodes if n.kind == kind)

    def neighbors(self, node_id: str) -> Sequence[tuple[str, str]]:
        out = [(e.relation, e.dst) for e in self._edges if e.src == node_id]
        out += [(e.relation, e.src) for e in self._edges if e.dst == node_id]
        return tuple(sorted(out))
