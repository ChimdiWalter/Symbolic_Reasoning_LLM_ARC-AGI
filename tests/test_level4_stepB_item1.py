"""Synthetic unit tests for Step-B item 1 (inventory, K1 lattice, witnesses,
audit). NOTHING here reads the sanitized corpus or any Step-A output; every
grid below is manufactured in this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from level4_blind_runtime import runtime as V              # noqa: E402
from level4_blind_runtime import search as SEARCH          # noqa: E402
from level4_stepB import kinds as K                        # noqa: E402
from level4_stepB import k2_slots as S                     # noqa: E402
from level4_stepB import k2_inventory as I                 # noqa: E402
from level4_stepB import k1_lattice as L                   # noqa: E402
from level4_stepB import witnesses as W                    # noqa: E402
from level4_stepB import install as N                     # noqa: E402

import importlib.util                                      # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "stepB_audit", ROOT / "scripts" / "cora_level4_stepB_audit.py")
AUDIT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AUDIT)


# --------------------------------------------------------------------------
# fixtures: a context grid the frozen vocabulary can segment
# --------------------------------------------------------------------------

def _context():
    g = np.zeros((7, 7), dtype=int)
    g[1, 1] = 3
    g[1, 2] = 3
    g[3, 3] = 5
    g[5, 1] = 7
    g[5, 5] = 7
    return g


def _regions():
    return V._colour_components(_context())


# --------------------------------------------------------------------------
# 1. the declared representation table matches the frozen runtime
# --------------------------------------------------------------------------

def test_representation_matches_runtime():
    ctx = V.Ctx(_context())
    sets = V.REGISTRY["Partition"].evaluate(ctx, "colour_components")
    assert isinstance(sets, tuple) and all(
        isinstance(s, frozenset) for s in sets)          # Set[Region]: cells
    ents = V.REGISTRY["Entities"].evaluate(ctx, "same_colour_4")
    assert all(isinstance(e, frozenset) for e in ents)    # Set[Entity]: cells
    expr = ("Compose_V1", (("Key", ("area",)), ("Lookup", (((1, 4), (2, 6)),))))
    coloured = V.REGISTRY["Map_V1"].evaluate(ctx, sets, expr)
    assert coloured and all(isinstance(c, tuple) and len(c) == 2
                            and isinstance(c[0], frozenset)
                            and isinstance(c[1], int) for c in coloured)
    grid = V.REGISTRY["PaintEach"].evaluate(ctx, coloured)
    assert isinstance(grid, np.ndarray)                   # Grid: carrier
    looked = V._lookup(V.Ctx(_context(), value=1), ((1, 4),))
    assert isinstance(looked, int)                        # Colour: scalar


# --------------------------------------------------------------------------
# 2. inventory: determinism, families, executability, result kinds
# --------------------------------------------------------------------------

def test_inventory_deterministic():
    a = json.dumps(I.inventory_record(), sort_keys=True, default=str)
    b = json.dumps(I.inventory_record(), sort_keys=True, default=str)
    assert a == b


def test_every_family_instantiates():
    record = I.inventory_record()
    by_family = {f: 0 for f in I.FAMILIES}
    for schema in record["schemas"]:
        by_family[schema["family"]] += \
            schema["counterfactual_applicability"]["count"]
    assert all(v > 0 for v in by_family.values()), by_family
    assert record["instance_count"] == len(record["instances"])


def _value_matches_kind(value, t, resolve):
    kind = resolve(t)
    if value is None:
        return True                     # undefined is always allowed
    if kind.has("collection"):
        return isinstance(value, tuple) and all(
            _value_matches_kind(v, kind.element, resolve) for v in value)
    if kind.has("carrier"):
        return isinstance(value, np.ndarray)
    if kind.has("colour") and kind.has("cells"):
        return isinstance(value, tuple) and isinstance(value[0], frozenset)
    if kind.has("cells"):
        return isinstance(value, frozenset)
    if kind.has("scalar"):
        return not isinstance(value, (np.ndarray, frozenset, dict))
    return True


def test_all_instances_execute_on_witnesses():
    resolve = I.resolver()
    types, instances = I.build()
    witnesses = W.witness_values(types, resolve)
    executed = 0
    defined_by_schema: dict = {}
    defined_instances = 0
    with N.installed(instances):
        for inst in instances:
            rows = W.behaviour(inst.production, inst.arg_types,
                               inst.arg_modes, witnesses, max_combos=6)
            assert rows, f"{inst.name}: no witness combination applicable"
            defined = sum(row["out"] is not None for row in rows)
            executed += len(rows)
            defined_instances += defined > 0
            defined_by_schema[inst.schema_id] = \
                defined_by_schema.get(inst.schema_id, 0) + defined
    # a partial operation may be undefined at SOME type (a carrier is rarely
    # monochrome, an intersection is often empty), but every SCHEMA must be
    # semantically alive somewhere on the witness set, and most instances too
    for schema_id, defined in defined_by_schema.items():
        assert defined > 0, f"{schema_id} undefined on every witness"
    assert defined_instances >= 0.8 * len(instances), \
        f"only {defined_instances}/{len(instances)} instances ever defined"
    assert executed > 1000


def test_instance_results_have_declared_kind():
    resolve = I.resolver()
    types, instances = I.build()
    witnesses = W.witness_values(types, resolve)
    with N.installed(instances):
        for inst in instances:
            rows_live = []
            for ctx, values in witnesses:
                options = [values.get(str(t), []) for t in inst.arg_types]
                if any(not o for o in options):
                    continue
                combo = tuple(o[0] for o in options)
                try:
                    out = inst.production.evaluate(V.Ctx(ctx.grid), *combo)
                except Exception as e:                    # noqa: BLE001
                    pytest.fail(f"{inst.name} raised {e!r}")
                rows_live.append(out)
            for out in rows_live:
                assert _value_matches_kind(out, inst.result_type, resolve), \
                    f"{inst.name} produced {type(out)} for {inst.result_type}"


# --------------------------------------------------------------------------
# 3. generic constructors reproduce baseline behaviour at the frozen types
# --------------------------------------------------------------------------

def test_select_matches_baseline():
    ctx = V.Ctx(_context())
    sets = tuple(_regions())
    types, instances = I.build()
    inst = {i.name: i for i in instances}
    with N.installed(instances):
        for predicate in V.TERMINAL_VALUES["Predicate"]:
            ours = inst["select.by_predicate@Region"].production.evaluate(
                ctx, sets, predicate)
            base = V.REGISTRY["Select"].evaluate(ctx, sets, predicate)
            assert ours == base, predicate


def test_extremum_and_unique_match_baseline():
    ctx = V.Ctx(_context())
    ents = tuple(V.SEGMENTATION_VOCAB["same_colour_4"](_context()))
    types, instances = I.build()
    inst = {i.name: i for i in instances}
    with N.installed(instances):
        for feature in ("area", "row_band", "col_band"):
            ours = inst["aggregate.extremum@Entity"].production.evaluate(
                ctx, ents, feature, "max")
            base = V.REGISTRY["ArgMax@Entity"].evaluate(ctx, ents, feature)
            assert ours == base, feature
            ours = inst["aggregate.extremum@Entity"].production.evaluate(
                ctx, ents, feature, "min")
            base = V.REGISTRY["ArgMin@Entity"].evaluate(ctx, ents, feature)
            assert ours == base, feature
        one = (ents[0],)
        assert inst["aggregate.unique@Entity"].production.evaluate(ctx, one) \
            == V.REGISTRY["Unique@Entity"].evaluate(ctx, one)
        assert inst["aggregate.unique@Entity"].production.evaluate(ctx, ents) \
            is None


def test_pair_and_embed_match_baseline():
    ctx = V.Ctx(_context())
    sets = tuple(_regions())
    expr = ("Compose_V1", (("Key", ("area",)), ("Lookup", (((1, 4), (2, 6)),))))
    types, instances = I.build()
    inst = {i.name: i for i in instances}
    pair_name = [i.name for i in instances if i.schema_id == "combine.pair"][0]
    with N.installed(instances):
        ours = inst[pair_name].production.evaluate(ctx, sets, expr)
        base = V.REGISTRY["Map_V1"].evaluate(ctx, sets, expr)
        assert ours == base
        frame = ("context_extent", None, "zero", (0, 0), "context_content", None)
        ours_grid = inst["embed.into_carrier@Set[Coloured],Grid"] \
            .production.evaluate(ctx, base, frame)
        base_grid = V.REGISTRY["PaintEach"].evaluate(ctx, base)
        assert np.array_equal(ours_grid, base_grid)


# --------------------------------------------------------------------------
# 4. K1 lattice
# --------------------------------------------------------------------------

def _k1_ast():
    return ("PaintEach", (("Map_V1", (
        ("Partition", ("colour_components",)),
        ("Compose_V1", (("Key", ("area",)), ("Lookup", ("?Map",)))))),))


def _k1_pairs():
    """Two demonstrations where every guard holds: full recolour by area."""
    out = []
    for shift in (0, 1):
        g = np.zeros((6, 6), dtype=int)
        g[1, 1 + shift] = 3                       # area 1
        g[3, 1] = 5
        g[3, 2] = 5                               # area 2
        o = g.copy()
        o[o == 3] = 8                             # area 1 -> 8
        o[o == 5] = 9                             # area 2 -> 9
        out.append((g, o))
    return out


def test_lattice_shape_and_guard_lines():
    triples = L.lattice()
    assert len(triples) == 31
    assert len({t[0] for t in triples}) == 31
    src = __import__("inspect").getsource(L.FROZEN_LEARNER)
    for name, line in L.GUARDS:
        assert line in src, (name, line)


def test_conservativity_all_31_agree_when_guards_hold():
    frozen = L.FROZEN_LEARNER(_k1_ast(), _k1_pairs(), "?Map")
    assert frozen is not None
    for lattice_id, dropped, learner in L.lattice():
        relaxed = learner(_k1_ast(), _k1_pairs(), "?Map")
        assert relaxed is not None, lattice_id
        assert relaxed.value == frozen.value, lattice_id


def _single_guard_case(name):
    pairs = [(g.copy(), o.copy()) for g, o in _k1_pairs()]
    if name == "same_shape":
        pairs = [(g, np.vstack([o, np.zeros((1, 6), dtype=int)]))
                 for g, o in pairs]
    elif name == "touched_is_whole":
        for g, o in pairs:
            o[3, 2] = 5                           # half the area-2 shape stays
    elif name == "single_colour":
        for g, o in pairs:
            g[3, 3] = 5                           # area-3 shape, 2/3 -> 9
            o[3, 3] = 9
            o[3, 2] = 4                           # minority colour
    elif name == "full_coverage":
        for g, o in pairs:
            o[5, 5] = 6                           # background change, no set
    elif name == "witnessed_twice":
        pairs = pairs[:1]
    return pairs


@pytest.mark.parametrize("guard", L.GUARD_NAMES)
def test_each_single_drop_is_not_vacuous(guard):
    pairs = _single_guard_case(guard)
    assert L.FROZEN_LEARNER(_k1_ast(), pairs, "?Map") is None, guard
    relaxed = L.make_learner(frozenset({guard}))(_k1_ast(), pairs, "?Map")
    assert relaxed is not None, f"dropping {guard} never admits anything"


# --------------------------------------------------------------------------
# 5. witnesses
# --------------------------------------------------------------------------

def test_witness_set_deterministic_and_covering():
    resolve = I.resolver()
    types = I.closure()
    a = W.witness_set(types, resolve)
    b = W.witness_set(types, resolve)
    assert W.sha256_of(a) == W.sha256_of(b)
    lo, hi = W.BOUNDS["side"]
    for entry in a["contexts"]:
        g = entry["grid"]["grid"]
        assert lo <= len(g) <= hi and lo <= len(g[0]) <= hi
    for t in types:
        assert any(entry["values"][str(t)] for entry in a["contexts"]), \
            f"type {t} has no witness anywhere"


def test_fingerprints_deterministic_and_discriminating():
    resolve = I.resolver()
    types, instances = I.build()
    witnesses = W.witness_values(types, resolve)
    inst = {i.name: i for i in instances}
    with N.installed(instances):
        def fp(name):
            i = inst[name]
            return W.fingerprint(W.behaviour(
                i.production, i.arg_types, i.arg_modes, witnesses, 8))
        assert fp("reduce.extent@Region,Region") == \
            fp("reduce.extent@Region,Region")
        assert fp("aggregate.fold@Region") != fp("select.by_predicate@Region")


# --------------------------------------------------------------------------
# 6. install/restore leaves the frozen runtime untouched
# --------------------------------------------------------------------------

def test_install_restores_everything():
    before = (dict(V.REGISTRY), dict(V.TERMINAL_VALUES),
              list(V.INDUCED_TYPES), dict(SEARCH.SLOT_LEARNERS), V._eval)
    types, instances = I.build()
    with N.installed(instances):
        assert len(V.REGISTRY) == len(before[0]) + len(instances)
        assert "IndexMap" in V.INDUCED_TYPES and "SetOp" in V.TERMINAL_VALUES
        assert V._eval is not before[4]
    assert dict(V.REGISTRY) == before[0]
    assert dict(V.TERMINAL_VALUES) == before[1]
    assert list(V.INDUCED_TYPES) == before[2]
    assert dict(SEARCH.SLOT_LEARNERS) == before[3]
    assert V._eval is before[4]


def test_frozen_search_still_solves_baseline_task_with_inventory_installed():
    pairs = [(g, o) for g, o in _k1_pairs()]
    baseline, _ = SEARCH.search(pairs)
    assert baseline, "baseline sanity: the frozen task must be solvable"
    types, instances = I.build()
    with N.installed(instances) as env:
        results, _ = SEARCH.search(pairs, env=env)
    assert results, "installing the inventory must not break discovery"
    rendered = V.evaluate(results[0][0], pairs[0][0]) \
        if not results[0][0][0].startswith("concept") else None


# --------------------------------------------------------------------------
# 7. slot learners fit synthetic demonstrations
# --------------------------------------------------------------------------

def test_learn_colour_and_index_map_and_frame():
    types, instances = I.build()
    inst = {i.name: i for i in instances}
    with N.installed(instances):
        # constant colour: every region painted 8
        g1 = _context()
        o1 = g1.copy()
        for cells in _regions():
            for r, c in cells:
                o1[r, c] = 8
        pair_const = [i.name for i in instances
                      if i.schema_id == "combine.pair_const"
                      and dict(i.binding)["A"] == "Region"][0]
        ast = (pair_const,
               (("Partition", ("colour_components",)), "?Colour"))
        learned = S.learn_colour(ast, [(g1, o1), (np.roll(g1, 1, 1),
                                                  np.roll(o1, 1, 1))], "?Colour")
        assert learned is not None and learned.value == 8
        # identity index map on an unchanged scene
        ast2 = ("reindex.elements@Region",
                (("Partition", ("colour_components",)), "?IndexMap"))
        learned2 = S.learn_index_map(ast2, [(g1, g1.copy())], "?IndexMap")
        assert learned2 is not None
        matrix, k, origin, offset = learned2.value
        assert matrix == (1, 0, 0, 1) and k == 1 and offset == (0, 0)
        # frame: output = the single shape's tight extent, context background
        g2 = np.zeros((5, 5), dtype=int)
        g2[1, 1] = 4
        g2[1, 2] = 4
        o2 = np.array([[4, 4]])
        ast3 = ("embed.into_carrier@Set[Region],Grid",
                (("Partition", ("colour_components",)), "?Frame"))
        learned3 = S.learn_frame(ast3, [(g2, o2)], "?Frame")
        assert learned3 is not None
        assert learned3.value[0] == "value_extent"


# --------------------------------------------------------------------------
# 8. the audit rejects injected forbidden shapes (negative controls)
# --------------------------------------------------------------------------

INJECTIONS = (
    ("field", "def wf(x):\n    if x.frontier_type == 1:\n        return 2\n",
     "FIELD_TOKEN"),
    ("io", "def wf(x):\n    return open('x').read()\n", "IO"),
    ("import", "import os\n", "IMPORT"),
    ("typename",
     "def sem_thing(ctx, b, v):\n    return 1 if 'Grid' == str(v) else 0\n",
     "TYPE_NAME_IN_CODE"),
)


@pytest.mark.parametrize("label,code,expected", INJECTIONS)
def test_audit_negative_controls(tmp_path, label, code, expected):
    bad = tmp_path / "k2_extra.py"
    bad.write_text(code)
    findings = AUDIT.audit_module(bad, AUDIT._universe_type_names())
    kinds_found = {f["kind"] for f in findings if f["level"] == "FAIL"}
    assert expected in kinds_found, (label, findings)


def test_audit_negative_control_semantic_lexeme(tmp_path):
    word = "til" + "e"                     # assembled to keep plaintext out
    bad = tmp_path / "k2_extra.py"
    bad.write_text(f"def sem_{word}_grid(ctx):\n    return None\n")
    findings = AUDIT.audit_module(bad, AUDIT._universe_type_names())
    assert any(f["kind"] == "SEMANTIC_LEXEME" and f["level"] == "FAIL"
               for f in findings)


def test_audit_passes_on_real_package():
    assert AUDIT.main(write=False) == 0
