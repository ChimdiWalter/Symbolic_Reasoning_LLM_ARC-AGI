"""K2.1 / K2.3: interface-directed candidate enumeration, uniform for
every interface.

An INTERFACE is a pair of types (a, b): the type a value already has, and
the type a derivation failed to reach. This module enumerates, for an
interface, every typed term over a fixed vocabulary that maps a port of
type ``a`` to a value of type ``b`` within frozen bounds. The interface is
the only input; nothing else about where the interface came from is known
here, and the same enumerator runs for every interface.

Two lanes share the enumerator and differ ONLY in the vocabulary:

    K2  vocabulary = the frozen constructor inventory (k2_inventory), plus
        the frozen registry's expression formers (productions whose result
        kind is ``expr``), so that expression-mode arguments can be filled
        exactly as the witness generator fills them. Label at generation:
        NEW_SEMANTIC_PRODUCTION.

    K1  vocabulary = the frozen registry itself; each term is paired with
        one member of the K1 guard-relaxation lattice that fits an induced
        slot the term actually carries. Label: SLOT_LEARNER_REPAIR.

Every parameter a term needs (a terminal from a frozen vocabulary, an
induced value) becomes a SLOT of the candidate, fitted per task by the
ordinary machinery: a candidate is a macro (``concept.Concept``) whose
slots are the port and its parameters in first-encounter order. Its cost
is 1, the frozen policy for every macro.

Nothing here reads a file, names a type, or inspects any statistic.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from level4_blind_runtime import runtime as V
from level4_blind_runtime import concept as C

from . import kinds as K
from . import k1_lattice as L
from . import k2_inventory as I
from . import witnesses as W

#: Frozen enumeration bounds. ``max_depth`` counts nesting of vocabulary
#: applications (a macro's elaboration, as the runtime measures depth);
#: ``per_type_cap`` mirrors the frozen search's own per-type cap.
BOUNDS = {"max_depth": 4, "per_type_cap": 4000}

LABELS = {"K2": "NEW_SEMANTIC_PRODUCTION", "K1": "SLOT_LEARNER_REPAIR"}

_PORT = ("#port",)


@dataclass(frozen=True)
class Entry:
    """One vocabulary member: a production name with its typed interface."""
    name: str
    arg_types: tuple
    result_type: V.Type


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    lane: str
    label: str
    interface: tuple                   # (str(a), str(b))
    schema: object                     # AST over the vocabulary with ?v slots
    slot_types: dict                   # slot -> V.Type
    port_slot: str
    learner_id: str                    # K1 only, else ""
    mdl: int

    def concept(self) -> C.Concept:
        return C.Concept(name=self.candidate_id, schema=self.schema,
                         slot_types=dict(self.slot_types), provenance=(),
                         source_hashes=(), result_type=V.T(*_split(self.interface[1])),
                         cost=1, status="candidate")

    def arg_types(self) -> tuple:
        return tuple(self.slot_types[s] for s in C.introduced_slots(self.schema))

    def canonical(self) -> str:
        return json.dumps({"lane": self.lane, "interface": list(self.interface),
                           "schema": V.to_json(self.schema),
                           "slots": {k: str(v) for k, v in self.slot_types.items()},
                           "learner": self.learner_id}, sort_keys=True)


def _split(text: str):
    """Rebuild a Type from its printed form (only for the result type)."""
    text = text.strip()
    if "[" not in text:
        return (text,)
    head, rest = text.split("[", 1)
    parts, depth, current = [], 0, ""
    for ch in rest[:-1]:
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        depth += ch == "["
        depth -= ch == "]"
        current += ch
    if current:
        parts.append(current)
    return (head,) + tuple(V.T(*_split(p)) for p in parts)


# --------------------------------------------------------------------------
# argument modes, by capability of the declared type
# --------------------------------------------------------------------------

def mode_of(t: V.Type):
    kind = K.kind_of(t, tuple(V.INDUCED_TYPES), tuple(V.TERMINAL_VALUES))
    if kind is None:
        return None
    if kind.has("expr"):
        return "expr"
    if kind.has("vocab"):
        return "terminal"
    if kind.has("induced"):
        return "induced"
    return "value"


def registry_entries() -> list:
    return [Entry(name, p.arg_types, p.result_type)
            for name, p in sorted(V.REGISTRY.items())]


def vocabulary(lane: str, instances) -> list:
    """K2: inventory instances + registry expression formers. K1: registry."""
    if lane == "K1":
        return registry_entries()
    out = [Entry(i.name, i.arg_types, i.result_type) for i in instances]
    for e in registry_entries():
        if mode_of(e.result_type) == "expr":
            out.append(e)
    return sorted(out, key=lambda e: e.name)


# --------------------------------------------------------------------------
# enumeration
# --------------------------------------------------------------------------

def _contains_port(term) -> bool:
    if term == _PORT:
        return True
    if isinstance(term, tuple) and len(term) == 2 and isinstance(term[1], tuple):
        return any(_contains_port(a) for a in term[1])
    return False


def _nodes(term) -> int:
    if not (isinstance(term, tuple) and len(term) == 2 and isinstance(term[1], tuple)):
        return 0
    return 1 + sum(_nodes(a) for a in term[1])


def _key(term) -> str:
    return json.dumps(term, sort_keys=True, default=list)


def enumerate_terms(a: V.Type, b: V.Type, vocab: list, bounds=None) -> tuple:
    """All port-bearing terms of type ``b`` over ``vocab`` from a port of
    type ``a``, canonical order (size, then serialization). Returns
    (terms, dropped_by_cap)."""
    bounds = dict(BOUNDS if bounds is None else bounds)
    cache: dict = {}
    dropped = {"n": 0}

    def terms(t: V.Type, depth: int) -> list:
        key = (str(t), depth)
        if key in cache:
            return cache[key]
        out = []
        if V.type_equal(t, a):
            out.append(_PORT)
        if depth > 0:
            for e in vocab:
                if not V.type_equal(e.result_type, t):
                    continue
                options = []
                viable = True
                for arg_type in e.arg_types:
                    mode = mode_of(arg_type)
                    if mode in ("terminal", "induced"):
                        options.append([("#param", str(arg_type))])
                    elif mode in ("value", "expr"):
                        values = terms(arg_type, depth - 1)
                        if not values:
                            viable = False
                            break
                        options.append(values)
                    else:
                        viable = False
                        break
                if not viable:
                    continue
                for combo in _product(options):
                    out.append((e.name, combo))
                    if len(out) >= bounds["per_type_cap"]:
                        dropped["n"] += 1
                        break
        cache[key] = out
        return out

    found = {}
    for term in terms(b, bounds["max_depth"]):
        if _contains_port(term):
            found.setdefault(_key(term), term)
    ordered = sorted(found.values(), key=lambda t: (_nodes(t), _key(t)))
    return tuple(ordered), dropped["n"]


def _product(option_lists):
    if not option_lists:
        yield ()
        return
    head, rest = option_lists[0], option_lists[1:]
    for value in head:
        for tail in _product(rest):
            yield (value,) + tail


# --------------------------------------------------------------------------
# terms to candidates (macros with typed slots)
# --------------------------------------------------------------------------

def _to_schema(term, a: V.Type):
    """Replace the port and parameters by ?v slots in first-encounter order."""
    slots: dict = {}
    port_slot = {"name": None}

    def walk(node):
        if node == _PORT:
            if port_slot["name"] is None:
                port_slot["name"] = f"?v{len(slots)}"
                slots[port_slot["name"]] = a
            return port_slot["name"]
        if isinstance(node, tuple) and node and node[0] == "#param":
            name = f"?v{len(slots)}"
            slots[name] = V.T(*_split(node[1]))
            return name
        return (node[0], tuple(walk(x) for x in node[1]))

    schema = walk(term)
    return schema, slots, port_slot["name"]


def _identifier(lane: str, canonical: str) -> str:
    return f"{lane}-" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _mdl(schema) -> int:
    if not (isinstance(schema, tuple) and len(schema) == 2):
        return 0
    return 1 + sum(_mdl(x) for x in schema[1])


def _learner_type() -> str:
    """The slot type the K1 lattice relaxes: the key the frozen learner is
    registered under (structural lookup, no type is named)."""
    from level4_blind_runtime import search as SEARCH
    keys = [k for k, v in SEARCH.SLOT_LEARNERS.items() if v is L.FROZEN_LEARNER]
    return keys[0]


def candidates_for(a: V.Type, b: V.Type, instances, bounds=None) -> tuple:
    """Every candidate for the interface (a, b), both lanes, canonical
    order. Returns (candidates, report)."""
    out = []
    report = {}
    # K2
    terms, dropped = enumerate_terms(a, b, vocabulary("K2", instances), bounds)
    report["K2"] = {"terms": len(terms), "dropped_by_cap": dropped}
    for term in terms:
        schema, slots, port = _to_schema(term, a)
        body = json.dumps({"lane": "K2", "schema": V.to_json(schema),
                           "slots": {k: str(v) for k, v in slots.items()},
                           "interface": [str(a), str(b)]}, sort_keys=True)
        out.append(Candidate(_identifier("K2", body), "K2", LABELS["K2"],
                             (str(a), str(b)), schema, slots, port, "",
                             _mdl(schema)))
    # K1: registry terms, paired with every lattice learner that fits a
    # slot the term carries (the learner's type is the slot's type)
    terms, dropped = enumerate_terms(a, b, vocabulary("K1", instances), bounds)
    learner_type = _learner_type()
    paired = 0
    lattice = L.lattice()
    for term in terms:
        schema, slots, port = _to_schema(term, a)
        if not any(str(t) == learner_type for t in slots.values()):
            continue
        for lattice_id, _dropped, _learner in lattice:
            body = json.dumps({"lane": "K1", "schema": V.to_json(schema),
                               "slots": {k: str(v) for k, v in slots.items()},
                               "interface": [str(a), str(b)],
                               "learner": lattice_id}, sort_keys=True)
            out.append(Candidate(_identifier("K1", body), "K1", LABELS["K1"],
                                 (str(a), str(b)), schema, slots, port,
                                 lattice_id, _mdl(schema)))
            paired += 1
    report["K1"] = {"terms": len(terms), "dropped_by_cap": dropped,
                    "paired_with_learners": paired}
    return tuple(out), report


# --------------------------------------------------------------------------
# behaviour over the frozen witness set (dedup fingerprint)
# --------------------------------------------------------------------------

def production_of(candidate: Candidate) -> V.Production:
    """A production evaluating the candidate on VALUES for every slot,
    for fingerprinting over the witness set."""
    concept = candidate.concept()

    def evaluate(ctx, *values):
        core = concept.elaborate(list(values))
        if core is None:
            return None
        return V._eval(core, ctx)
    return V.Production(candidate.candidate_id, candidate.arg_types(),
                        concept.result_type, evaluate, {}, cost=1)


def fingerprint(candidate: Candidate, witnesses, max_combos=24) -> str:
    production = production_of(candidate)
    rows = W.behaviour(production, candidate.arg_types(),
                       tuple("value" for _ in candidate.arg_types()),
                       witnesses, max_combos=max_combos)
    return W.fingerprint(rows)


def record(candidate: Candidate, fp: str) -> dict:
    return {"candidate_id": candidate.candidate_id, "lane": candidate.lane,
            "label": candidate.label,
            "interface": {"from": candidate.interface[0],
                          "to": candidate.interface[1]},
            "signature": " x ".join(str(t) for t in candidate.arg_types())
            + " -> " + candidate.interface[1],
            "schema": V.to_json(candidate.schema),
            "slot_types": {k: str(v) for k, v in candidate.slot_types.items()},
            "port_slot": candidate.port_slot,
            "learner": candidate.learner_id or None,
            "mdl": candidate.mdl,
            "behaviour_fingerprint": fp}
