"""Typed mutations of CORA programs (rast `N` trees and version 4 `G4Program`s). A mutation is data surgery on the
typed AST; the result is type-checked by CORA (`cora_neural_hybrid.execute.check`) and executed only by CORA's
interpreters. Mutation validity does not imply semantic correctness: every mutant is executed and scored.

Every position of a program has a type (from `cora_neural_v2.rast.SIGNATURES`), so a position is only ever replaced
by a value of its own type. Operator families (the fragment a repair targets):
- PARAMETER: a colour, offset, integer, symbol (axis, direction, ...), colour table or feature-map entry;
  COLOR / VEC / SCALAR / AXIS / ANGLE / DIR subtrees;
- SELECTOR: a PRED subtree (swapped for a selector of CORA's demonstration-derived library or of another recorded
  program), or a feature, comparator or value inside a test;
- TRANSFORM: an ACTION or REF subtree (operation substitution), a part kind of a part rule;
- OUTPUT: the RENDER (output canvas) or a REGION subtree, the constant output shape;
- REPRESENTATION: the object view;
- COMPOSE: short compositions: add a rule, drop a rule, swap two rules, wrap an action in `composite`, flip the
  default, a two-stage `seq`, add or drop a part/ray rule;
- SUBTREE: crossover: any typed subtree replaced by a same-typed subtree of another recorded program of the puzzle.
Donors come from the puzzle's own recorded programs and from CORA's demonstration-derived candidate lists
(`cora_neural_v2g2.search.selectors / actions / references / renders`). Demonstrations only.
"""
import numpy as np

from cora_neural_v2.rast import ANGLES, CMPS, SIGNATURES, SYMBOL_SETS, TYPES, N, to_sexpr
from cora_neural_v2g4 import parts as PT
from cora_neural_v2g4 import program as PG

FAMILIES = ("PARAMETER", "SELECTOR", "TRANSFORM", "OUTPUT", "REPRESENTATION", "COMPOSE", "SUBTREE")
INT_FEATS = ("color", "size", "bbox_height", "bbox_width", "hole_count", "enclosed_region_count", "size_rank",
             "size_rank_reversed", "color_frequency_rank", "count_of_same_shape", "count_of_same_color",
             "gap_to_nearest_row", "gap_to_nearest_col", "nearest_object_color", "containment_depth",
             "aligned_row_count", "aligned_col_count")
BOOL_FEATS = ("has_hole", "has_enclosed_region", "is_multicolor", "is_rectangle", "is_line", "touches_border",
              "is_unique_size", "is_unique_color", "is_unique_shape", "is_majority_shape", "is_container",
              "is_contained")
COLOR_INT_OPS = {"color", "nearest_of_color"}
UNITS = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))
TYPE_FAMILY = {"PRED": "SELECTOR", "ACTION": "TRANSFORM", "REF": "TRANSFORM", "COLOR": "PARAMETER",
               "VEC": "PARAMETER", "SCALAR": "PARAMETER", "AXIS": "PARAMETER", "ANGLE": "PARAMETER",
               "DIR": "PARAMETER", "ALIGN": "PARAMETER", "REGION": "OUTPUT", "RENDER": "OUTPUT", "RULE": "COMPOSE",
               "PROGRAM": "COMPOSE", "VIEW": "REPRESENTATION"}
DONOR_TYPES = ("PRED", "ACTION", "REF", "COLOR", "VEC", "SCALAR", "REGION", "RENDER", "RULE", "AXIS", "DIR",
               "ANGLE", "ALIGN")


# ------------------------------------------------------------------ positions and surgery
class Pos:
    __slots__ = ("path", "value", "kind", "parent", "rule", "in_pred")

    def __init__(self, path, value, kind, parent, rule, in_pred):
        self.path, self.value, self.kind, self.parent, self.rule, self.in_pred = path, value, kind, parent, rule, in_pred


def _walk(x, kind, path, parent, rule, in_pred, out):
    out.append(Pos(path, x, kind, parent, rule, in_pred))
    if not (isinstance(x, N) and x.op in SIGNATURES and x.op != "hole"):
        return
    _, kinds = SIGNATURES[x.op]
    if len(kinds) != len(x.args):
        return
    pred = in_pred or kind == "PRED"
    for i, (k, a) in enumerate(zip(kinds, x.args)):
        p = path + (i,)
        if k.startswith("list"):
            want = k.split(":", 1)[1]
            out.append(Pos(p, a, k, x.op, rule, pred))
            if isinstance(a, tuple):
                for j, e in enumerate(a):
                    r = j if x.op == "program" and want == "RULE" else rule
                    _walk(e, want, p + (j,), x.op, r, pred, out)
        elif k == "bindings":
            if isinstance(a, tuple):
                for j, b in enumerate(a):
                    if isinstance(b, tuple) and len(b) == 2:
                        _walk(b[1], "REF", p + (j, 1), x.op, rule, pred, out)
        elif k in TYPES:
            _walk(a, k, p, x.op, rule, pred, out)
        else:
            out.append(Pos(p, a, k, x.op, rule, pred))


def positions(prog):
    """Every typed position. A G4Program's positions have paths starting with "view", "base" or ("rules", i)."""
    out = []
    if isinstance(prog, PG.G4Program):
        out.append(Pos(("view",), prog.view, "sym:VIEWS", "g4program", None, False))
        if prog.base is not None:
            sub = []
            _walk(prog.base, "PROGRAM", (), None, None, False, sub)
            for q in sub:
                q.path = ("base",) + q.path
            out += sub
        for i, r in enumerate(prog.rules):
            sub = []
            _walk(r.sel, "PRED", (), "rule", i, True, sub)
            for q in sub:
                q.path = ("rules", i, "sel") + q.path
                q.rule = i
            out += sub
            if isinstance(r, PG.PartRule):
                out.append(Pos(("rules", i, "kind"), r.kind, "part_kind", "part_rule", i, False))
            else:
                out.append(Pos(("rules", i, "dirs"), r.dirs, "dirs", "ray_rule", i, False))
                out.append(Pos(("rules", i, "stop"), r.stop, "stop", "ray_rule", i, False))
            out.append(Pos(("rules", i, "colour"), r.colour, "part_colour", type(r).__name__, i, False))
        return out
    _walk(prog, "PROGRAM", (), None, None, False, out)
    return out


def _replace_n(x, path, new):
    if not path:
        return new
    i, rest = path[0], path[1:]
    if isinstance(x, N):
        args = list(x.args)
        args[i] = _replace_n(args[i], rest, new)
        return N(x.op, tuple(args))
    if isinstance(x, tuple):
        items = list(x)
        items[i] = _replace_n(items[i], rest, new)
        return tuple(items)
    raise IndexError(path)


def replace(prog, path, new):
    """A copy of `prog` with the value at `path` replaced by `new`."""
    if not isinstance(prog, PG.G4Program):
        return _replace_n(prog, path, new)
    if path[0] == "view":
        return PG.make(new, prog.base, prog.rules)
    if path[0] == "base":
        return PG.make(prog.view, _replace_n(prog.base, path[1:], new), prog.rules)
    _, i, field = path[:3]
    rules = list(prog.rules)
    r = rules[i]
    if field == "sel":
        r = r._replace(sel=_replace_n(r.sel, path[3:], new))
    else:
        r = r._replace(**{field: new})
    rules[i] = r
    return PG.make(prog.view, prog.base, rules)


# ------------------------------------------------------------------ donors
def _type_of(node):
    if isinstance(node, N) and node.op in SIGNATURES:
        return SIGNATURES[node.op][0]
    return None


class Library:
    """Typed donors for one puzzle: CORA's demonstration-derived candidates and the recorded programs' subtrees."""

    def __init__(self, task, progs=(), max_per_type=400):
        from llm_writer.search.common import colours
        self.task = task
        self.colours = colours(task)
        self.pool = {t: [] for t in DONOR_TYPES}
        self.rules = []
        self.programs = []
        self.feature_values = {}
        seen = set()
        for p in progs:
            if isinstance(p, N) and p.op in ("program", "seq"):
                self.programs.append(p)
            for q in positions(p):
                t = q.kind if q.kind in TYPES else None
                if t in self.pool and isinstance(q.value, N):
                    k = (t, to_sexpr(q.value))
                    if k not in seen and len(self.pool[t]) < max_per_type:
                        seen.add(k)
                        self.pool[t].append(q.value)
                if isinstance(q.value, N) and q.value.op == "test" and len(q.value.args) == 3:
                    f, _, v = q.value.args
                    self.feature_values.setdefault(f, set()).add(v)
        self.lib = {t: [] for t in DONOR_TYPES}
        self.vectors = list(UNITS)
        self.out_shapes = sorted({tuple(np.asarray(b).shape) for _, b in task["train"]})
        try:
            self._cora_library()
        except Exception:                                  # noqa: BLE001 (an evidence failure leaves the pool donors)
            pass
        for c in self.colours:
            self.lib["COLOR"].append(N("color", (c,)))
            self.feature_values.setdefault("color", set()).add(c)
        self.lib["COLOR"] += [N("most_common_color", ()), N("least_common_color", ())]
        self.lib["VEC"] += [N("vec", v) for v in self.vectors]
        self.lib["SCALAR"] += [N("int", (k,)) for k in (1, 2, 3, 4)] + [N("size", ())]
        self.lib["AXIS"] += [N("axis", (a,)) for a in SYMBOL_SETS["AXES"]]
        self.lib["DIR"] += [N("dir", (d,)) for d in SYMBOL_SETS["DIRECTIONS"]]
        self.lib["ANGLE"] += [N("angle", (a,)) for a in ANGLES]
        self.lib["ALIGN"] += [N("align_mode", (a,)) for a in SYMBOL_SETS["ALIGNMENTS"]]

    def _cora_library(self):
        from cora_neural_v2.constraints import evidence
        from cora_neural_v2g2 import search as G2S
        train = self.task["train"]
        ev = evidence(train)
        self.lib["PRED"] = [s for s, _, _ in G2S.selectors(ev)]
        self.lib["ACTION"] = [a for a, _, _ in G2S.actions(ev, train) if isinstance(a, N)]
        self.lib["REF"] = [r for r, _, _ in G2S.references(ev)]
        self.lib["RENDER"] = [r for r, _ in G2S.renders(ev, train)]
        self.lib["REGION"] = [r.args[0] for r in self.lib["RENDER"] if r.op == "crop"]
        vecs = list(ev.get("vectors") or {})
        self.vectors = [tuple(v) for v in vecs] + [u for u in UNITS if u not in vecs]
        for s in self.lib["PRED"]:
            if s.op == "test" and len(s.args) == 3:
                self.feature_values.setdefault(s.args[0], set()).add(s.args[2])
        sizes = ev.get("sizes") or ()
        self.feature_values.setdefault("size", set()).update(int(k) for k in sizes if 1 <= k <= 30)

    def donors(self, t, rng, from_pool=None):
        """A random donor of type t: from the recorded programs (crossover) or CORA's library."""
        pool, lib = self.pool.get(t) or [], self.lib.get(t) or []
        if from_pool is True or (from_pool is None and pool and (not lib or rng.random() < 0.5)):
            return rng.choice(pool) if pool else None
        return rng.choice(lib) if lib else (rng.choice(pool) if pool else None)


# ------------------------------------------------------------------ literal alternatives
def _other(rng, options, cur):
    opts = [o for o in options if o != cur]
    return rng.choice(opts) if opts else None


def _alt_literal(q, rng, lib, prog):
    v, k = q.value, q.kind
    if k == "int":
        if q.parent in COLOR_INT_OPS:
            return _other(rng, lib.colours, v)
        if q.parent == "vec":
            comps = sorted({c for vec in lib.vectors for c in vec} | {v - 1, v + 1, v - 2, v + 2})
            return _other(rng, [c for c in comps if -29 <= c <= 29], v)
        if q.parent == "angle":
            return _other(rng, ANGLES, v)
        if q.parent == "constant_shape":
            dims = sorted({d for s in lib.out_shapes for d in s} | {max(1, v - 1), min(30, v + 1)})
            return _other(rng, dims, v)
        if q.parent == "quadrant":
            return _other(rng, (0, 1, 2, 3), v)
        lo = 0 if q.parent in ("int", "separator_cell", "extract_part") else -29
        return _other(rng, [x for x in (v - 2, v - 1, v + 1, v + 2) if lo <= x <= 30], v)
    if k.startswith("sym:"):
        return _other(rng, SYMBOL_SETS[k[4:]], v)
    if k == "cmp":
        return _other(rng, CMPS, v)
    if k == "feature":
        sib = _sibling_value(prog, q)
        if isinstance(sib, bool):
            return _other(rng, BOOL_FEATS, v)
        if isinstance(sib, int):
            return _other(rng, INT_FEATS, v)
        return None
    if k == "value":
        if isinstance(v, bool):
            return not v
        if isinstance(v, int):
            f = _sibling_feature(prog, q)
            seen = {x for x in lib.feature_values.get(f, ()) if isinstance(x, int) and not isinstance(x, bool)}
            return _other(rng, sorted(seen | {max(0, v - 1), v + 1}), v)
        return None
    if k == "values":
        vals = list(v)
        f = _sibling_feature(prog, q)
        pool = sorted(x for x in lib.feature_values.get(f, ()) if x not in vals and not isinstance(x, bool)) \
            if f else []
        if len(vals) > 1 and (not pool or rng.random() < 0.5):
            vals.pop(rng.randrange(len(vals)))
        elif pool:
            vals.append(rng.choice(pool))
        else:
            return None
        return tuple(vals)
    if k in ("pairs", "fpairs"):
        pairs = [tuple(p) for p in v]
        keys = [p[0] for p in pairs]
        roll = rng.random()
        missing = [c for c in lib.colours if c not in keys] if k == "pairs" else []
        if missing and roll < 0.4:
            pairs.append((rng.choice(missing), rng.choice(lib.colours)))
            pairs.sort()
        elif len(pairs) > 1 and roll < 0.55:
            pairs.pop(rng.randrange(len(pairs)))
        elif pairs:
            j = rng.randrange(len(pairs))
            new = _other(rng, lib.colours, pairs[j][1])
            if new is None:
                return None
            pairs[j] = (pairs[j][0], new)
        else:
            return None
        return tuple(pairs)
    if k == "part_kind":
        return _other(rng, PT.KINDS, v)
    if k == "part_colour":
        return _other(rng, list(lib.colours) + ["own"], v)
    if k == "stop":
        return _other(rng, ("obstacle", "through"), v)
    if k == "dirs":
        dirs = set(v)
        d = rng.choice(PG.DIRS8)
        if d in dirs and len(dirs) > 1:
            dirs.discard(d)
        else:
            dirs.add(d)
        return tuple(sorted(dirs))
    return None


def _node_at(prog, path):
    if isinstance(prog, PG.G4Program):
        if path[0] == "base":
            x, path = prog.base, path[1:]
        elif path[0] == "rules":
            x, path = prog.rules[path[1]].sel, path[3:]
        else:
            return prog.view
    else:
        x = prog
    for i in path:
        x = x.args[i] if isinstance(x, N) else x[i]
    return x


def _sibling_value(prog, q):
    try:
        parent = _node_at(prog, q.path[:-1])
        return parent.args[2] if isinstance(parent, N) and parent.op == "test" else None
    except (IndexError, TypeError, AttributeError):
        return None


def _sibling_feature(prog, q):
    try:
        parent = _node_at(prog, q.path[:-1])
        return parent.args[0] if isinstance(parent, N) and parent.op in ("test", "in_set") else None
    except (IndexError, TypeError, AttributeError):
        return None


def family_of(q):
    if q.kind in TYPES:
        return TYPE_FAMILY.get(q.kind)
    if q.kind == "sym:VIEWS":
        return "REPRESENTATION"
    if q.kind == "sym:DEFAULTS":
        return "COMPOSE"
    if q.kind in ("cmp", "feature", "value", "values") or q.in_pred:
        return "SELECTOR"
    if q.kind == "part_kind":
        return "TRANSFORM"
    if q.kind == "int" and q.parent == "constant_shape":
        return "OUTPUT"
    if q.kind.startswith("list"):
        return None
    return "PARAMETER"


# ------------------------------------------------------------------ compositions
def _rules_path(prog):
    """Path of the rule list of a `program` (or of a G4Program's base), or None."""
    if isinstance(prog, PG.G4Program):
        return ("base", 1) if isinstance(prog.base, N) and prog.base.op == "program" else None
    return (1,) if isinstance(prog, N) and prog.op == "program" else None


def _compose(prog, rng, lib, focus=None):
    ops = []
    if isinstance(prog, PG.G4Program):
        ops += ["g4_add", "g4_drop", "g4_swap"] if len(prog.rules) > 1 else ["g4_add"]
    rp = _rules_path(prog)
    if rp is not None:
        ops += ["add_rule", "drop_rule", "swap_rules", "composite"]
    if isinstance(prog, N) and prog.op == "program" and lib.programs:
        ops.append("seq")
    if not ops:
        return None, None
    op = rng.choice(ops)
    if op.startswith("g4_"):
        rules = list(prog.rules)
        if op == "g4_add":
            sel = lib.donors("PRED", rng) or N("true", ())
            rules.insert(rng.randrange(len(rules) + 1), PG.PartRule(sel, rng.choice(PT.KINDS), rng.choice(lib.colours)))
        elif op == "g4_drop":
            rules.pop(rng.randrange(len(rules)))
        else:
            i = rng.randrange(len(rules) - 1)
            rules[i], rules[i + 1] = rules[i + 1], rules[i]
        return PG.make(prog.view, prog.base, rules), op
    if op == "seq":
        other = rng.choice(lib.programs)
        stages = (prog, other) if rng.random() < 0.5 else (other, prog)
        return N("seq", (stages,)), op
    rules = list(_node_at(prog, rp))
    if op == "add_rule":
        if lib.pool["RULE"] and rng.random() < 0.5:
            r = rng.choice(lib.pool["RULE"])
        else:
            sel, act = lib.donors("PRED", rng), lib.donors("ACTION", rng)
            if sel is None or act is None:
                return None, None
            r = N("rule", (sel, act))
        at = rng.randrange(len(rules) + 1)
        rules.insert(at, r)
        return replace(prog, rp, tuple(rules)), f"add_rule@{at}"
    if not rules:
        return None, None
    i = focus if focus is not None and 0 <= focus < len(rules) else rng.randrange(len(rules))
    if op == "drop_rule":
        rules.pop(i)
        return replace(prog, rp, tuple(rules)), f"drop_rule@{i}"
    if op == "swap_rules":
        if len(rules) < 2:
            return None, None
        j = i + 1 if i + 1 < len(rules) else i - 1
        rules[i], rules[j] = rules[j], rules[i]
        return replace(prog, rp, tuple(rules)), f"swap_rules@{min(i, j)}"
    r = rules[i]
    if not (isinstance(r, N) and r.op in ("rule", "rule_with")):
        return None, None
    act = r.args[-1]
    extra = lib.donors("ACTION", rng)
    if extra is None:
        return None, None
    parts = (act.args[0] + (extra,)) if act.op == "composite" else (act, extra)
    r2 = N(r.op, r.args[:-1] + (N("composite", (tuple(parts),)),))
    rules[i] = r2
    return replace(prog, rp, tuple(rules)), f"composite@{i}"


# ------------------------------------------------------------------ one mutation
def propose(prog, family, rng, lib, focus=None, tries=12):
    """One typed mutant of `prog` in operator family `family` (optionally inside rule `focus`), or (None, None).
    The mutant is type-checked by CORA; at most `tries` attempts."""
    from cora_neural_hybrid import execute as EX
    pos = positions(prog)
    for _ in range(tries):
        try:
            child, label = _propose(prog, pos, family, rng, lib, focus)
        except (IndexError, TypeError, ValueError, AttributeError):
            child, label = None, None
        if child is None:
            continue
        try:
            ok = EX.check(child)[0]
        except Exception:                                  # noqa: BLE001
            ok = False
        if ok:
            return child, label
    return None, None


def _propose(prog, pos, family, rng, lib, focus):
    if family == "COMPOSE" and rng.random() < 0.8:
        return _compose(prog, rng, lib, focus)
    if family == "SUBTREE":
        cands = [q for q in pos if q.kind in lib.pool and lib.pool[q.kind] and isinstance(q.value, N)]
        if focus is not None:
            cands = [q for q in cands if q.rule == focus] or cands
        if not cands:
            return None, None
        q = rng.choice(cands)
        new = lib.donors(q.kind, rng, from_pool=True)
        if new is None or new == q.value:
            return None, None
        return replace(prog, q.path, new), f"SUBTREE:{q.kind}@{_ps(q.path)}"
    cands = [q for q in pos if family_of(q) == family]
    if focus is not None:
        cands = [q for q in cands if q.rule == focus] or cands
    if not cands:
        return None, None
    q = rng.choice(cands)
    if q.kind in TYPES and isinstance(q.value, N):
        # a typed subtree: half the time mutate a literal inside it, else swap it for a donor of the same type
        inner = [r for r in pos if r.path[:len(q.path)] == q.path and r.path != q.path and r.kind not in TYPES
                 and not r.kind.startswith("list")]
        if inner and rng.random() < 0.5:
            r = rng.choice(inner)
            new = _alt_literal(r, rng, lib, prog)
            if new is None:
                return None, None
            return replace(prog, r.path, new), f"{family}:{r.kind}@{_ps(r.path)}"
        new = lib.donors(q.kind, rng)
        if new is None or new == q.value:
            return None, None
        return replace(prog, q.path, new), f"{family}:{q.kind}@{_ps(q.path)}"
    new = _alt_literal(q, rng, lib, prog)
    if new is None:
        return None, None
    return replace(prog, q.path, new), f"{family}:{q.kind}@{_ps(q.path)}"


def _ps(path):
    return ".".join(str(p) for p in path)


def mutable(prog):
    """True for the program forms these operators cover (object programs, seq, version 4 part/ray programs)."""
    return isinstance(prog, PG.G4Program) or (isinstance(prog, N) and prog.op in ("program", "seq"))


__all__ = ["FAMILIES", "Library", "positions", "replace", "propose", "family_of", "mutable"]
