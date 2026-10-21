"""ncv2-g4 inversion: build rules from object correspondences instead of searching for them. Demonstrations only.

1. **Native feature tables.** Every object of every demonstration input (one view), with every registered integer,
   boolean or colour feature, computed by `expressions._feature_value`, the function native tests evaluate with.
2. **Selector induction**, smallest first, for each change group (scene.py: the objects with one fate):
   - `(true)`, and single tests `(test f CMP v)`, CMP in ==, !=, <, >, <=, >=, over the values observed in the tables;
   - then, only if no single test separates the group, `(and p q)` of two single tests that each pick a superset of
     the group;
   - then `(exists REL (test g == v))` over every registered relation, with boolean or colour inner tests.
   A group can carry don't-care objects (construct.py: objects on which a rule would write nothing or only what the
   output already has); a selector may pick them or not.
   Tables PROPOSE; native execution (scene.selections) CONFIRMS every selector kept, so a disagreement between the
   tables and native semantics can never produce a selector.
3. **Group inversion.** For a group and a confirmed selector, actions of the group's fate, with parameters taken from
   the members' observed deltas:
   - recoloured: the constant colour; `color_of` every candidate reference; most / least common colour; ncv2-g2's
     induced feature maps;
   - moved: the constant vector; `(scaled DIR (feature f))` when every member moved along one direction by its own
     value of f; ncv2-g2's relational moves;
   - deleted: `delete`.
   A rule is kept only if its execution, alone, fixes every changed cell of every member and breaks no cell, in every
   demonstration (a local forward check).
4. **Composition.** One kept rule per group (at most 3 groups), in every order, executed. Every program that fits
   every demonstration is a candidate; several selectors or parameters per group give rival readings.
5. **Parameter leave-one-out** (`rederived`): whether inversion on each n-1 subset of the demonstrations derives the
   same program again. Selection uses it as fold-local stability.
"""
import itertools

import numpy as np

from cora_neural_v2.rast import ASTError, N
from cora_neural_v2g2 import search as S2
from cora_neural_v2g3 import delta as D
from cora_neural_v2g3 import scene as SC

CMPS = ("==", "!=", "<", ">", "<=", ">=")
SKIP_FEATURES = {"bbox", "centroid", "shape_sig", "shape_sig_normalized", "vector_to_nearest", "aspect_ratio", "density"}
DIR_UNIT = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
MAX_SEL_PER_GROUP = 4
MAX_RULES_PER_GROUP = 4
_OPS = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, "<": lambda a, b: a < b, ">": lambda a, b: a > b,
        "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b}


def feature_tables(train, view):
    """[ [ {feature: value} per object ] per demonstration ], with native's own feature values."""
    from geocat_arc.object_reasoning.expressions import _feature_value
    from geocat_arc.object_reasoning import features as F
    from geocat_arc.object_reasoning.segmentation import background_for, segment
    from geocat_arc.object_reasoning.types import GridContext, SegmentationVariant as SV
    from geocat_arc.perception.grid import Grid
    if not F.FEATURE_REGISTRY:
        F.register_builtin_features()
    names = sorted(set(F.FEATURE_REGISTRY) - SKIP_FEATURES)
    out = []
    for a, _ in train:
        g = Grid(np.asarray(a, dtype=np.int32))
        bg = background_for(g, SV(view))
        objs = segment(g, SV(view), bg)
        ctx = GridContext(grid=g, objects=objs, background=bg, pair_index=0, role="input", variant=SV(view))
        rows = []
        for o in objs:
            row = {}
            for f in names:
                try:
                    v = _feature_value(f, o, ctx)
                except Exception:                                   # noqa: BLE001 (undefined for this object)
                    continue
                if isinstance(v, (bool, np.bool_)):
                    row[f] = bool(v)
                elif isinstance(v, (int, np.integer)) or (isinstance(v, float) and float(v).is_integer()):
                    row[f] = int(v)
            rows.append(row)
        out.append(rows)
    return out


def _table_picks(tables, f, cmp, v):
    op = _OPS[cmp]
    picks = []
    for rows in tables:
        s = set()
        for j, row in enumerate(rows):
            if f in row and isinstance(row[f], bool) == isinstance(v, bool):
                try:
                    if op(row[f], v):
                        s.add(j)
                except TypeError:
                    pass
        picks.append(frozenset(s))
    return picks


def single_tests(tables):
    """{PRED node: table picks} for every (feature, comparison, observed value)."""
    vals = {}
    for rows in tables:
        for row in rows:
            for f, v in row.items():
                vals.setdefault(f, set()).add(v)
    out = {}
    for f, vs in sorted(vals.items()):
        for v in sorted(vs, key=repr):
            cmps = ("==", "!=") if isinstance(v, bool) or f == "color" else CMPS
            for cmp in cmps:
                if isinstance(v, bool) and cmp == "!=":
                    continue                                        # (test f != #t) is (test f == #f)
                out[N("test", (f, cmp, v))] = _table_picks(tables, f, cmp, v)
    return out


TRUE = N("true", ())
_EXISTS_CACHE = {}
RUNS = {"native": 0}                     # native executions spent on construction (selector checks, local checks)


def _selections(view, sels, train):
    RUNS["native"] += len(sels) * len(train)
    return SC.selections(view, sels, train)


def _cost(pred):
    if pred.op == "true":
        return -1
    if pred.op == "test":
        f, cmp, v = pred.args
        return (0 if cmp == "==" else 1 if cmp == "!=" else 2) + (0 if isinstance(v, bool) or f == "color" else 0.5)
    if pred.op == "exists":
        return 3 + _cost(pred.args[1])
    if pred.op == "and":
        return 4 + _cost(pred.args[0]) + _cost(pred.args[1])
    return 0


def _separates(picks, members, may):
    """Exact (`may` None): the picks are the members. With `may` (don't-care objects per demonstration): every member
    and nothing outside members | may is picked, in every demonstration."""
    if may is None:
        return SC.separation(picks, members)[0]
    return all(p is not None for p in picks) and any(members) and \
        all(m <= p <= m | y for p, m, y in zip(picks, members, may))


def _exists_picks(view, train, tables):
    """Native picks of every (exists REL inner) candidate, computed once per (view, demonstrations)."""
    from geocat_arc.object_reasoning import features as F
    key = (view, repr(train))
    if key not in _EXISTS_CACHE:
        inner = [N("test", (f, "==", b)) for f in ("is_line", "is_rectangle", "has_hole", "touches_border",
                                                     "is_unique_color", "is_unique_size", "is_contained", "is_container")
                 for b in (True, False)]
        inner += [N("test", ("color", "==", c)) for c in sorted({r["color"] for rows in tables for r in rows if "color" in r})]
        cands = [N("exists", (rel, p)) for rel in sorted(F.RELATION_REGISTRY) for p in inner]
        if len(_EXISTS_CACHE) > 64:
            _EXISTS_CACHE.clear()
        _EXISTS_CACHE[key] = _selections(view, cands, train)
    return _EXISTS_CACHE[key]


def induce_selectors(view, train, tables, tests, members, may=None):
    """Native-confirmed selectors that pick exactly `members` (per-demonstration object index sets), cheapest first.
    With `may`, objects in it may be picked or not (see _separates)."""
    tests = {TRUE: [frozenset(range(len(rows))) for rows in tables], **tests}
    exact = [p for p, pk in tests.items() if _separates(pk, members, may)]
    if not exact:
        superset = [p for p, pk in tests.items() if all(m <= s for m, s in zip(members, pk))]
        superset.sort(key=_cost)
        for p, q in itertools.combinations(superset[:24], 2):
            inter = [a & b for a, b in zip(tests[p], tests[q])]
            if _separates(inter, members, may):
                exact.append(N("and", (p, q)))
    if not exact:
        picks = _exists_picks(view, train, tables)
        exact = [p for p in picks if _separates(picks[p], members, may)]
    exact.sort(key=_cost)
    confirmed = []
    if exact:
        native = _selections(view, exact[:3 * MAX_SEL_PER_GROUP], train)
        confirmed = [p for p in exact[:3 * MAX_SEL_PER_GROUP] if _separates(native[p], members, may)]
    return confirmed[:MAX_SEL_PER_GROUP]


def _local_ok(view, sel, act, train, member_cells):
    """The one-rule program fixes every changed member cell and breaks no cell, in every demonstration."""
    rule = S2.rule_node(sel, act)
    prog = N("program", (view, (rule,), "keep", N("same_as_input", ())))
    RUNS["native"] += len(train)
    try:
        ds = D.deltas(prog, train)
    except ASTError:
        return None
    for d, cells in zip(ds, member_cells):
        if not d.shape_ok or d.fixed is None or int(d.broken.sum()):
            return None
        if any(d.remaining[x] for x in cells):                    # a member cell that had to change is still wrong
            return None
    return rule


def _actions_for(fate, members_objs, tables, ev, train):
    """Candidate actions for a group's fate, parameters from the members' observed deltas."""
    acts = []
    if fate == "deleted":
        return [N("delete", ())]
    if fate == "recoloured":
        cols = {o.to_colour for o in members_objs}
        if len(cols) == 1:
            acts.append(N("recolor", (N("color", (int(next(iter(cols))),)),)))
        refs = [r for r, _, _ in S2.references(ev)] + [N("nearest_of_color", (int(c),)) for c in sorted(ev["in_cols"])]
        acts += [N("recolor", (N("color_of", (r,)),)) for r in refs]
        acts += [N("recolor", (N("most_common_color", ()),)), N("recolor", (N("least_common_color", ()),))]
        acts += [a for a, _, _ in S2.feature_map_actions(train)]
        return acts
    if fate == "moved":
        vecs = {o.vector for o in members_objs}
        if len(vecs) == 1:
            acts.append(N("translate", (N("vec", tuple(int(x) for x in next(iter(vecs)))),)))
        for name, (ur, uc) in DIR_UNIT.items():                     # every member moved along DIR by its own f
            ks = []
            for o in members_objs:
                dr, dc = o.vector
                k = dr // ur if ur else dc // uc
                if k <= 0 or (dr, dc) != (k * ur, k * uc):
                    break
                ks.append((o, k))
            else:
                for f in sorted({f for rows in tables for r in rows for f in r if not isinstance(r[f], bool)}):
                    if all(tables[o.demo][o.index].get(f) == k for o, k in ks):
                        acts.append(N("translate", (N("scaled", (name, N("feature", (f,)))),)))
        acts += [a for a, _, kind in S2.actions(ev, train) if isinstance(a, N) and
                 (kind[0] if isinstance(kind, tuple) else kind) in ("move_rel", "move_rel2", "move_to")]
        return acts
    return acts


def invert(task, views=None):
    """[(program, info)] constructed by inversion, in construction order (cheapest selectors and parameters first)."""
    from cora_neural_v2 import search as G1S
    train = task["train"]
    if not all(np.asarray(a).shape == np.asarray(b).shape for a, b in train):
        return []
    ev = S2.evidence2(train)
    views = views or G1S.distinct_views(task)
    out, seen = [], set()
    for v in views:
        sc = SC.analyse(train, v)
        if sc is None:
            continue
        tables = feature_tables(train, v)
        tests = single_tests(tables)
        cache = {}
        # decompositions: every changed object in one group (one rule may produce several fates, e.g. a move that
        # clips at the edge); one group per fate; recolouring split by target colour (one constant per subgroup)
        coarse = [k for k in sc.groups if len(k) == 1 and k[0] in ("recoloured", "moved", "deleted")]
        fine = [k for k in coarse if k[0] != "recoloured"] + [k for k in sc.groups if len(k) == 2]
        decomps = ([[("changed",)]] if len(coarse) > 1 else []) + [coarse] + ([fine] if fine != coarse else [])
        if len(coarse) > 1:
            sc.groups[("changed",)] = [frozenset().union(*[sc.groups[k][i] for k in coarse]) for i in range(len(train))]
        for keys in decomps:
            group_rules = []
            for key in keys:
                if key not in cache:
                    cache[key] = _group_rules(v, train, sc, key, tables, tests, ev)
                if cache[key]:
                    group_rules.append(cache[key])
            if not group_rules or len(group_rules) > 3 or len(group_rules) < len(keys):
                continue
            best = [rs[0] for rs in group_rules]
            combos = [best] + [best[:g] + [r] + best[g + 1:] for g, rs in enumerate(group_rules) for r in rs[1:]]
            for combo in combos:                                   # the best rules, then one rival substituted
                for order in (combo, combo[::-1]) if len(combo) > 1 else (combo,):
                    prog = N("program", (v, tuple(order), "keep", N("same_as_input", ())))
                    if prog not in seen:
                        seen.add(prog)
                        out.append((prog, {"view": v, "groups": len(group_rules)}))
    return out


def _group_rules(v, train, sc, key, tables, tests, ev):
    members = sc.groups[key]
    objs = [o for demo in sc.objects for o in demo if o.index in members[o.demo]]
    member_cells = []
    for i, demo in enumerate(sc.objects):
        cells = set()
        for o in demo:
            if o.index in members[i]:
                cells |= set(o.cells)
                if o.fate == "moved":                              # the destination must be drawn too
                    cells |= {(r + o.vector[0], c + o.vector[1]) for r, c in o.cells}
        member_cells.append(cells)
    rules = []
    fates = sorted({o.fate for o in objs}) if key == ("changed",) else [key[0]]
    acts = [a for f in fates for a in _actions_for(f, [o for o in objs if o.fate == f], tables, ev, train)]
    if key == ("changed",):                                        # one action explaining every fate: try moves first
        acts = [a for a in acts if a.op == "translate"] + [a for a in acts if a.op != "translate"]
    for sel in induce_selectors(v, train, tables, tests, members):
        for act in dict.fromkeys(acts):
            r = _local_ok(v, sel, act, train, member_cells)
            if r is not None and r not in rules:
                rules.append(r)
            if len(rules) >= MAX_RULES_PER_GROUP:
                return rules
    return rules


def rederived(task, progs):
    """{program: share of the n-1 demonstration subsets from which inversion derives it again}."""
    train = task["train"]
    if len(train) < 3:
        return {p: None for p in progs}
    found = []
    for i in range(len(train)):
        red = {"train": train[:i] + train[i + 1:], "test_inputs": task["test_inputs"]}
        found.append({p for p, _ in invert(red)})
    return {p: sum(p in f for f in found) / len(found) for p in progs}
