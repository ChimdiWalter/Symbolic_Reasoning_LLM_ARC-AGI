"""K2.2: the closed constructor meta-language.

Seven families, frozen by docs/CORA_LEVEL4_STEPB_DESIGN.md section K2.2:
select, project, reindex, aggregate, combine, embed, reduce. Each schema
below is a formal pattern over TYPE VARIABLES. A type variable carries a
capability REQUIREMENT (data, see kinds.satisfies); a schema is well formed
on a tuple of types exactly when every variable's requirement holds and
every ground argument type exists in the type universe. That is the whole
well-formedness rule. No function in this module inspects a type's name.

Argument modes
    value      an evaluated sub-term or a fitted induced value
    expr       a contextual expression, passed UNEVALUATED (as Key/Lookup
               are inside Map_V1 in the frozen runtime)
    terminal   a literal from a frozen finite vocabulary

Every semantics function receives ``(ctx, binding, *values)`` and touches
values only through the uniform accessors in ``kinds``; it may return None
(undefined), never raise for a typed input.

The universe is not listed anywhere: it is the closure of the types the
frozen registry mentions, plus the parameter types of k2_slots, under the
result types of well-formed instantiations (collections nest once).
"""
from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from typing import Callable, Optional

from level4_blind_runtime import runtime as V
from level4_blind_runtime import search as SEARCH

from . import kinds as K
from . import k2_slots as S

DESIGN = "docs/CORA_LEVEL4_STEPB_DESIGN.md"


# --------------------------------------------------------------------------
# type expressions (data)
# --------------------------------------------------------------------------

def var(name):
    return ("var", name)


def atom(name):
    return ("atom", name)


def set_of(inner):
    return ("set", inner)


def expr_of(a, b):
    return ("expr", a, b)


def substitute(texpr, binding: dict) -> V.Type:
    head = texpr[0]
    if head == "var":
        return binding[texpr[1]]
    if head == "atom":
        return V.T(texpr[1])
    if head == "set":
        return V.T("Set", substitute(texpr[1], binding))
    if head == "expr":
        return V.T("Expr", substitute(texpr[1], binding),
                   substitute(texpr[2], binding))
    raise ValueError(head)


def texpr_to_str(texpr) -> str:
    head = texpr[0]
    if head in ("var", "atom"):
        return texpr[1]
    if head == "set":
        return f"Set[{texpr_to_str(texpr[1])}]"
    return f"Expr[{texpr_to_str(texpr[1])},{texpr_to_str(texpr[2])}]"


@dataclass(frozen=True)
class Arg:
    role: str
    texpr: tuple
    mode: str                      # value | expr | terminal


@dataclass(frozen=True)
class TypeVar:
    name: str
    requires: tuple                # tuple of alternatives (frozensets)


@dataclass(frozen=True)
class Schema:
    schema_id: str
    family: str
    section: str
    type_vars: tuple
    args: tuple
    result: tuple
    semantics: Callable
    note: str = ""
    cost: int = 1

    def canonical(self) -> dict:
        return {"schema_id": self.schema_id, "family": self.family,
                "type_variables": [{"name": v.name,
                                    "requires": [sorted(a) for a in v.requires]}
                                   for v in self.type_vars],
                "arguments": [{"role": a.role, "type": texpr_to_str(a.texpr),
                               "mode": a.mode} for a in self.args],
                "result": texpr_to_str(self.result), "cost": self.cost}


def req(*alternatives):
    return tuple(frozenset(a.split()) for a in alternatives)


# --------------------------------------------------------------------------
# bindings and kinds at execution time
# --------------------------------------------------------------------------

class Binding:
    def __init__(self, types: dict, resolver):
        self.types = dict(types)
        self._resolve = resolver

    def kind(self, name) -> K.Kind:
        return self._resolve(self.types[name])

    def elem_kind(self, name) -> Optional[K.Kind]:
        kind = self.kind(name)
        return self._resolve(kind.element) if kind.element is not None else None

    def kind_of_type(self, t) -> K.Kind:
        return self._resolve(t)


# --------------------------------------------------------------------------
# semantics, one function per schema, capability-generic
# --------------------------------------------------------------------------

def _elements_with_kind(items, b, name):
    """The members of a Set[<var>] argument and the element kind. The value
    of a collection-typed argument is its member tuple by representation."""
    return tuple(items), b.kind(name)


def sem_select_by_predicate(ctx, b, items, predicate):
    test = V.PREDICATE_VOCAB.get(predicate)
    if test is None or not items:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    kept = []
    for e in members:
        table = K.descriptors_of(e, ek, ctx.grid)
        if table is not None and test(table):
            kept.append(e)
    return K.collection(None, kept)


def _numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def sem_select_extremal(ctx, b, items, feature, extremum):
    if not items:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    scored = [(K.descriptor_of(e, ek, ctx.grid, feature), e) for e in members]
    scored = [(v, e) for v, e in scored if _numeric(v)]
    if not scored:
        return None
    pick = max if extremum == "max" else min
    best = pick(v for v, _ in scored)
    return K.collection(None, [e for v, e in scored if v == best])


def sem_project_feature(ctx, b, items, feature):
    if not items:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    values = [K.descriptor_of(e, ek, ctx.grid, feature) for e in members]
    return K.collection(None, values)


def sem_project_expr(ctx, b, items, expr_ast):
    if not items or expr_ast is None:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    values = []
    for e in members:
        cells = K.cells_of(e, ek)
        if not cells:
            continue
        values.append(V._eval(expr_ast, V.Ctx(ctx.grid, element=cells)))
    return K.collection(None, values)


def sem_project_cells(ctx, b, items):
    if not items:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    target = b.kind("C")
    out = [K.rebuild(target, K.coloured_cells(e, ek, ctx.grid)) for e in members]
    return K.collection(None, out)


def sem_reindex_elements(ctx, b, items, index_map):
    if not items or index_map is None:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    out = []
    for e in members:
        pairs = K.coloured_cells(e, ek, ctx.grid)
        if not pairs:
            continue
        out.append(K.rebuild(ek, S.apply_index_map(index_map, pairs),
                             fill=V.background(ctx.grid)))
    return K.collection(None, out)


def sem_reindex_value(ctx, b, value, index_map):
    if value is None or index_map is None:
        return None
    kind = b.kind("A")
    pairs = K.coloured_cells(value, kind, ctx.grid)
    if not pairs:
        return None
    return K.rebuild(kind, S.apply_index_map(index_map, pairs),
                     fill=V.background(ctx.grid))


def sem_aggregate_fold(ctx, b, items, set_op):
    if not items:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    cell_sets = [K.cells_of(e, ek) for e in members]
    if any(cs is None for cs in cell_sets):
        return None
    folded = frozenset.union(*cell_sets) if set_op == "union" \
        else frozenset.intersection(*cell_sets)
    if not folded:
        return None
    colours = {K.own_colour(e, ek, ctx.grid) for e in members}
    pairs_by_cell = {}
    for e in members:
        for cell, colour in K.coloured_cells(e, ek, ctx.grid):
            pairs_by_cell.setdefault(cell, colour)
    pairs = tuple((cell, pairs_by_cell[cell]) for cell in sorted(folded)
                  if cell in pairs_by_cell)
    if ek.has("colour") and len(colours) != 1:
        return None
    return K.rebuild(ek, pairs, fill=V.background(ctx.grid))


def sem_aggregate_extremum(ctx, b, items, feature, extremum):
    if not items:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    scored = [(K.descriptor_of(e, ek, ctx.grid, feature), e) for e in members]
    scored = [(v, e) for v, e in scored if _numeric(v)]
    if not scored:
        return None
    pick = max if extremum == "max" else min
    best = pick(v for v, _ in scored)
    winners = [e for v, e in scored if v == best]
    return winners[0] if len(winners) == 1 else None


def sem_aggregate_unique(ctx, b, items):
    members = tuple(items) if items else None
    return members[0] if members and len(members) == 1 else None


def sem_aggregate_scalar(ctx, b, items, extremum):
    if not items:
        return None
    members = [v for v in items if _numeric(v)]
    if not members:
        return None
    return (max if extremum == "max" else min)(members)


def sem_combine_pair(ctx, b, items, expr_ast):
    if not items or expr_ast is None:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    target = b.kind("P")
    out = []
    for e in members:
        cells = K.cells_of(e, ek)
        if not cells:
            continue
        value = V._eval(expr_ast, V.Ctx(ctx.grid, element=cells))
        if value is None:
            continue
        colour = K.own_colour(value, b.kind("B"), ctx.grid)
        if colour is None:
            continue
        out.append(K.rebuild(target, tuple((c, colour) for c in sorted(cells))))
    return K.collection(None, out)


def sem_combine_pair_const(ctx, b, items, colour_value):
    if not items or colour_value is None:
        return None
    members, ek = _elements_with_kind(items, b, "A")
    colour = K.own_colour(colour_value, b.kind("B"), ctx.grid)
    if colour is None:
        return None
    target = b.kind("P")
    out = []
    for e in members:
        cells = K.cells_of(e, ek)
        if cells:
            out.append(K.rebuild(target, tuple((c, colour) for c in sorted(cells))))
    return K.collection(None, out)


def sem_embed_context(ctx, b):
    return ctx.grid.copy()


def sem_embed_into_carrier(ctx, b, value, frame):
    if value is None or frame is None:
        return None
    pairs = S.value_pairs(value, b.kind("A"), ctx.grid)
    if not pairs:
        return None
    return S.apply_frame(frame, pairs, ctx.grid)


def sem_reduce_cardinality(ctx, b, items):
    return len(tuple(items)) if items else None


def sem_reduce_feature(ctx, b, value, feature):
    if value is None:
        return None
    return K.descriptor_of(value, b.kind("A"), ctx.grid, feature)


def sem_reduce_colour(ctx, b, value):
    if value is None:
        return None
    return K.own_colour(value, b.kind("A"), ctx.grid)


def sem_reduce_extent(ctx, b, value):
    if value is None:
        return None
    cells = K.extent_cells(value, b.kind("A"))
    if not cells:
        return None
    return K.rebuild(b.kind("C"), tuple((c, 0) for c in sorted(cells)))


# --------------------------------------------------------------------------
# the schemas
# --------------------------------------------------------------------------

CELLS = req("cells")
CELLS_OR_COLLECTION_OF_CELLS = req("cells", "collection elem:cells")
SCALAR = req("scalar")
COLOUR_SCALAR = req("scalar colour")
ONLY_SCALAR = req("only:scalar")
ONLY_CELLS = req("only:cells")
ONLY_CELLS_COLOUR = req("only:cells,colour")
CARRIER = req("carrier")
ANY_VALUE = req("cells", "scalar", "carrier")

SCHEMAS = (
    # ---- select: choose a sub-collection by a typed predicate -------------
    Schema("select.by_predicate", "select", "K2.2 select",
           (TypeVar("A", CELLS),),
           (Arg("source", set_of(var("A")), "value"),
            Arg("predicate", atom("Predicate"), "terminal")),
           set_of(var("A")), sem_select_by_predicate,
           "elements whose frozen descriptor table satisfies the predicate"),
    Schema("select.extremal", "select", "K2.2 select",
           (TypeVar("A", CELLS),),
           (Arg("source", set_of(var("A")), "value"),
            Arg("feature", atom("FeatureExpr"), "terminal"),
            Arg("direction", atom("Extremum"), "terminal")),
           set_of(var("A")), sem_select_extremal,
           "all elements attaining the extremal value of a feature"),
    # ---- project: { phi(x) : x in S } for a typed map phi ---------------
    Schema("project.feature", "project", "K2.2 project",
           (TypeVar("A", CELLS), TypeVar("S", ONLY_SCALAR)),
           (Arg("source", set_of(var("A")), "value"),
            Arg("feature", atom("FeatureExpr"), "terminal")),
           set_of(var("S")), sem_project_feature,
           "phi = a frozen descriptor"),
    Schema("project.expr", "project", "K2.2 project",
           (TypeVar("A", CELLS), TypeVar("B", SCALAR)),
           (Arg("source", set_of(var("A")), "value"),
            Arg("map", expr_of(var("A"), var("B")), "expr")),
           set_of(var("B")), sem_project_expr,
           "phi = a contextual expression of the frozen language"),
    Schema("project.cells", "project", "K2.2 project",
           (TypeVar("A", CELLS), TypeVar("C", ONLY_CELLS)),
           (Arg("source", set_of(var("A")), "value"),),
           set_of(var("C")), sem_project_cells,
           "phi = the cell set each element carries"),
    # ---- reindex: re-address under a structure-preserving map ------------
    Schema("reindex.elements", "reindex", "K2.2 reindex",
           (TypeVar("A", CELLS),),
           (Arg("source", set_of(var("A")), "value"),
            Arg("map", atom("IndexMap"), "value")),
           set_of(var("A")), sem_reindex_elements,
           "each element's cells under one lattice map (induced)"),
    Schema("reindex.value", "reindex", "K2.2 reindex",
           (TypeVar("A", CELLS),),
           (Arg("source", var("A"), "value"),
            Arg("map", atom("IndexMap"), "value")),
           var("A"), sem_reindex_value,
           "a value's cells under a lattice map (induced)"),
    # ---- aggregate: fold a collection under an associative operator ------
    Schema("aggregate.fold", "aggregate", "K2.2 aggregate",
           (TypeVar("A", CELLS),),
           (Arg("source", set_of(var("A")), "value"),
            Arg("operator", atom("SetOp"), "terminal")),
           var("A"), sem_aggregate_fold,
           "union / intersection of the elements' cells"),
    Schema("aggregate.extremum", "aggregate", "K2.2 aggregate",
           (TypeVar("A", CELLS),),
           (Arg("source", set_of(var("A")), "value"),
            Arg("feature", atom("FeatureExpr"), "terminal"),
            Arg("direction", atom("Extremum"), "terminal")),
           var("A"), sem_aggregate_extremum,
           "the unique element attaining a feature's extremum"),
    Schema("aggregate.unique", "aggregate", "K2.2 aggregate",
           (TypeVar("A", ANY_VALUE),),
           (Arg("source", set_of(var("A")), "value"),),
           var("A"), sem_aggregate_unique,
           "the sole element of a singleton collection"),
    Schema("aggregate.scalar", "aggregate", "K2.2 aggregate",
           (TypeVar("A", SCALAR),),
           (Arg("source", set_of(var("A")), "value"),
            Arg("direction", atom("Extremum"), "terminal")),
           var("A"), sem_aggregate_scalar,
           "max / min over scalars"),
    # ---- combine: merge a value with a parameter of compatible kind ------
    Schema("combine.pair", "combine", "K2.2 combine",
           (TypeVar("A", CELLS), TypeVar("B", COLOUR_SCALAR),
            TypeVar("P", ONLY_CELLS_COLOUR)),
           (Arg("source", set_of(var("A")), "value"),
            Arg("map", expr_of(var("A"), var("B")), "expr")),
           set_of(var("P")), sem_combine_pair,
           "each element paired with the colour an expression assigns it"),
    Schema("combine.pair_const", "combine", "K2.2 combine",
           (TypeVar("A", CELLS), TypeVar("B", COLOUR_SCALAR),
            TypeVar("P", ONLY_CELLS_COLOUR)),
           (Arg("source", set_of(var("A")), "value"),
            Arg("colour", var("B"), "value")),
           set_of(var("P")), sem_combine_pair_const,
           "each element paired with one colour (induced)"),
    # ---- embed: place a value into a carrier of the target kind ----------
    Schema("embed.context", "embed", "K2.2 embed",
           (TypeVar("C", CARRIER),),
           (), var("C"), sem_embed_context,
           "the identity embedding of the context carrier"),
    Schema("embed.into_carrier", "embed", "K2.2 embed",
           (TypeVar("A", CELLS_OR_COLLECTION_OF_CELLS), TypeVar("C", CARRIER)),
           (Arg("source", var("A"), "value"),
            Arg("frame", atom("Frame"), "value")),
           var("C"), sem_embed_into_carrier,
           "the value's coloured cells placed into a fresh carrier (induced frame)"),
    # ---- reduce: collapse a structured value to a summary ----------------
    Schema("reduce.cardinality", "reduce", "K2.2 reduce",
           (TypeVar("A", ANY_VALUE), TypeVar("S", ONLY_SCALAR)),
           (Arg("source", set_of(var("A")), "value"),),
           var("S"), sem_reduce_cardinality,
           "number of elements"),
    Schema("reduce.feature", "reduce", "K2.2 reduce",
           (TypeVar("A", CELLS), TypeVar("S", ONLY_SCALAR)),
           (Arg("source", var("A"), "value"),
            Arg("feature", atom("FeatureExpr"), "terminal")),
           var("S"), sem_reduce_feature,
           "one frozen descriptor of a value"),
    Schema("reduce.colour", "reduce", "K2.2 reduce",
           (TypeVar("A", CELLS), TypeVar("B", COLOUR_SCALAR)),
           (Arg("source", var("A"), "value"),),
           var("B"), sem_reduce_colour,
           "the single colour a value carries"),
    Schema("reduce.extent", "reduce", "K2.2 reduce",
           (TypeVar("A", CELLS), TypeVar("C", ONLY_CELLS)),
           (Arg("source", var("A"), "value"),),
           var("C"), sem_reduce_extent,
           "the bounding extent of a value's cells"),
)

FAMILIES = ("select", "project", "reindex", "aggregate", "combine",
            "embed", "reduce")


# --------------------------------------------------------------------------
# the type universe and the instantiation closure
# --------------------------------------------------------------------------

def parameter_types():
    terminals = tuple(V.TERMINAL_VALUES) + tuple(S.TERMINALS)
    induced = tuple(V.INDUCED_TYPES) + tuple(S.INDUCED)
    return terminals, induced


def resolver():
    terminals, induced = parameter_types()

    def resolve(t):
        return K.kind_of(t, induced, terminals)
    return resolve


def seed_types() -> list:
    """Every type the frozen registry mentions, plus the parameter atoms."""
    seen = {}

    def add(t):
        seen.setdefault(str(t), t)
        for a in t.args:
            add(a)
    for production in V.REGISTRY.values():
        for t in production.arg_types:
            add(t)
        add(production.result_type)
    # the goal type is whatever the frozen search targets by default
    add(inspect.signature(SEARCH.search).parameters["goal"].default)
    terminals, induced = parameter_types()
    for name in terminals + induced:
        add(V.T(name))
    return [seen[k] for k in sorted(seen)]


def _is_value_type(kind: Optional[K.Kind]) -> bool:
    return kind is not None and not (kind.caps & {"expr", "vocab", "induced"})


@dataclass(frozen=True)
class Instance:
    name: str
    schema_id: str
    binding: tuple                 # ((var, type_str), ...)
    arg_types: tuple
    arg_modes: tuple
    result_type: V.Type
    production: V.Production


def _bindings(schema: Schema, types: list, resolve):
    """Every assignment of the schema's type variables to universe types
    that satisfies the requirements, in canonical order."""
    candidates = []
    for tv in schema.type_vars:
        options = []
        for t in types:
            kind = resolve(t)
            if not _is_value_type(kind):
                continue
            ek = resolve(kind.element) if kind.element is not None else None
            if K.satisfies(K.derived_caps(kind, ek), tv.requires):
                options.append(t)
        candidates.append(options)
    out = []

    def rec(index, partial):
        if index == len(candidates):
            out.append(dict(partial))
            return
        for t in candidates[index]:
            partial[schema.type_vars[index].name] = t
            rec(index + 1, partial)
            del partial[schema.type_vars[index].name]
    rec(0, {})
    return out


def instantiations(schema: Schema, types: list, resolve) -> list:
    """Well-formed ground instances: requirements hold AND every argument
    type is a universe type AND the result is a value type."""
    universe = {str(t) for t in types}
    out = []
    for binding in _bindings(schema, types, resolve):
        arg_types = tuple(substitute(a.texpr, binding) for a in schema.args)
        if any(str(t) not in universe for t in arg_types):
            continue
        result = substitute(schema.result, binding)
        if not _is_value_type(resolve(result)):
            continue
        out.append((binding, arg_types, result))
    return out


def closure(max_rounds: int = 8):
    """The type universe closed under instantiation results."""
    resolve = resolver()
    types = seed_types()
    known = {str(t) for t in types}
    for _ in range(max_rounds):
        added = False
        for schema in SCHEMAS:
            for _, _, result in instantiations(schema, types, resolve):
                if str(result) not in known:
                    known.add(str(result))
                    types.append(result)
                    added = True
        types.sort(key=str)
        if not added:
            break
    return types


def instance_name(schema: Schema, binding: dict) -> str:
    if not schema.type_vars:
        return schema.schema_id
    return schema.schema_id + "@" + ",".join(
        str(binding[v.name]) for v in schema.type_vars)


def build() -> tuple:
    """(universe types, instances) — deterministic."""
    resolve = resolver()
    types = closure()
    instances = []
    for schema in SCHEMAS:
        for binding, arg_types, result in instantiations(schema, types, resolve):
            name = instance_name(schema, binding)
            bound = Binding(binding, resolve)

            def evaluate(ctx, *values, _s=schema, _b=bound):
                try:
                    return _s.semantics(ctx, _b, *values)
                except Exception:
                    return None
            production = V.Production(
                name, arg_types, result, evaluate,
                {"signature_text": " x ".join(str(t) for t in arg_types)
                 + (" -> " if arg_types else "-> ") + str(result),
                 "schema_id": schema.schema_id, "lane": "K2"},
                cost=schema.cost)
            instances.append(Instance(
                name, schema.schema_id,
                tuple((v.name, str(binding[v.name])) for v in schema.type_vars),
                arg_types, tuple(a.mode for a in schema.args), result,
                production))
    return types, instances


# --------------------------------------------------------------------------
# the machine-readable inventory record
# --------------------------------------------------------------------------

def _source_sha(fn) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()


def _requirement_width(tv: TypeVar, types, resolve) -> int:
    """How many universe types satisfy the variable's requirement alone."""
    count = 0
    for t in types:
        kind = resolve(t)
        if not _is_value_type(kind):
            continue
        ek = resolve(kind.element) if kind.element is not None else None
        if K.satisfies(K.derived_caps(kind, ek), tv.requires):
            count += 1
    return count


def inventory_record() -> dict:
    resolve = resolver()
    types, instances = build()
    terminals, induced = parameter_types()
    schemas = []
    for schema in SCHEMAS:
        ground = [i for i in instances if i.schema_id == schema.schema_id]
        induced_slots = sorted({str(t) for i in ground for t in i.arg_types
                                if str(t) in induced})
        terminal_slots = sorted({str(t) for i in ground for t in i.arg_types
                                 if str(t) in terminals})
        widths = {tv.name: _requirement_width(tv, types, resolve)
                  for tv in schema.type_vars}
        applicability = [dict(i.binding) for i in ground]
        requirement_space = 1
        for w in widths.values():
            requirement_space *= w
        schemas.append({
            "schema_id": schema.schema_id,
            "family": schema.family,
            "declared_type_variables": [
                {"name": tv.name, "requires": [sorted(a) for a in tv.requires],
                 "universe_types_satisfying": widths[tv.name]}
                for tv in schema.type_vars],
            "arity": len(schema.args),
            "argument_roles": [{"role": a.role, "type": texpr_to_str(a.texpr),
                                "mode": a.mode} for a in schema.args],
            "result_type_rule": texpr_to_str(schema.result),
            "induced_slot_types": induced_slots,
            "terminal_types": terminal_slots,
            "executable_semantics": {
                "function": schema.semantics.__name__,
                "source_sha256": _source_sha(schema.semantics)},
            "cost": schema.cost,
            "canonical_serialization": json.dumps(schema.canonical(),
                                                  sort_keys=True),
            "provenance": {"document": DESIGN, "section": schema.section},
            "note": schema.note,
            "counterfactual_applicability": {
                "well_formed_instantiations": applicability,
                "count": len(applicability),
                "requirement_space": requirement_space,
                "pruned_by_universe_membership":
                    requirement_space - len(applicability),
            },
        })
    return {
        "component": "K2.2 constructor inventory",
        "design": DESIGN,
        "families": list(FAMILIES),
        "well_formedness_rule": (
            "a schema is well formed on a binding iff every type variable's "
            "capability requirement holds (kinds.satisfies over structural "
            "capabilities) and every ground argument type is a universe "
            "type and the result is a value type; no other condition"),
        "type_universe": [str(t) for t in types],
        "terminal_types": {n: list(V.TERMINAL_VALUES.get(n, S.TERMINALS.get(n, ())))
                           for n in terminals},
        "induced_types": {n: ("frozen runtime learner" if n in V.INDUCED_TYPES
                              else S.INDUCED[n].__name__) for n in induced},
        "meta_families": {
            "IndexMap": {"matrices": [list(m) for m in S.MATRICES],
                         "dilations": list(S.DILATIONS),
                         "origin_rules": list(S.ORIGIN_RULES),
                         "offset": "fitted"},
            "Frame": {"shape_rules": list(S.SHAPE_RULES),
                      "origin_rules": list(S.ORIGIN_RULES),
                      "fill_rules": list(S.FILL_RULES),
                      "offset": "fitted", "constants": "fitted"},
            "Colour": {"value": "fitted constant"},
        },
        "schemas": schemas,
        "instances": [{"name": i.name, "schema_id": i.schema_id,
                       "binding": dict(i.binding),
                       "arg_types": [str(t) for t in i.arg_types],
                       "arg_modes": list(i.arg_modes),
                       "result_type": str(i.result_type)} for i in instances],
        "instance_count": len(instances),
    }
