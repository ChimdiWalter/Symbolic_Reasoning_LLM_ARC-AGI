"""Bounded relational completion of typed object-rule sketches, with two interchangeable backends over ONE encoding:
SWI-Prolog with CLP(FD) (`prolog.py`) and an ordinary bounded enumeration (`solve_enum` here). Demonstrations only.

FACTS (permissible observations of the demonstrations under one object view, all read from native CORA):
- objects of each demonstration input (`cora_neural_v2g3.scene.native_objects`) and their observed FATE
  (`scene.fate`: unchanged, recoloured(c), moved(dr, dc), deleted, other) in the demonstration output;
- for every selector of the domain, the objects it picks (`scene.selections`: native CORA runs `(rule SEL (delete))`,
  so selector semantics are never re-implemented); selectors with identical picks on every demonstration form one
  class, searched once and expanded back into all its members after the search (members may differ on a test input);
- for every action of the domain, its effect on each object when applied by `(rule (true) ACTION)` (native
  execution, then `scene.fate` per object); an action whose effect reaches cells outside the objects and their move
  destinations is not object-local and is left out of the encoding;
- integer feature values of every object (native feature functions, `features.FEATURE_REGISTRY`) and relation
  facts between objects (native relation functions), for threshold and relational selectors;
- the changed cells that no input object (or observed move destination) covers: if any exist, no program of the
  fragment can reproduce the demonstrations (PROVED_UNSAT_IN_ENCODING, with that trace).

RESTRICTED RULE AST (Python tuples here, Prolog terms there; nothing in it is ever called as code):
  selector  := ("true",) | ("s", i) | ("and", S, S) | ("thr", feature, ge|le, v) | ("ex", relation, ("s", i))
  action    := ("keep",) | ("delete",) | ("recolor", c) | ("translate", dr, dc) | ("a", j)
  program   := ("prog", [("rule", selector, action), ...], keep|delete)   # first matching rule, else default
  holes     := ("h", "sel", DOMAIN) | ("h", "act", DOMAIN) | ("h", "colour") | ("h", "vec", R) | ("h", "default")
               | ("h", "int", lo, hi) (a threshold value)
A completion fills every hole once for ALL demonstrations (one shared rule; no per-example constants). Both backends
enumerate structural choices in domain order and integer choices in ascending lexicographic order, so they produce
the same solutions in the same order when neither hits a limit (tested).

STATUSES: FIT_FOUND (complete=False when a cap or limit stopped the search after a solution),
NO_FIT_IN_ENUMERATED_DOMAIN (an exhausted domain that was truncated by a cap), PROVED_UNSAT_IN_ENCODING (exhausted
untruncated domains: no completion of THIS sketch in THIS encoding; not a statement about the language),
BUDGET_EXHAUSTED (a limit before any solution; a timeout is not unsatisfiability), UNSUPPORTED_CONSTRUCT (the sketch
or puzzle is outside the fragment), EXECUTION_ERROR (a backend or observation failure).

Every solution is LOWERED to a CORA program and executed by the existing executor; only those executions produce
fits and test predictions (the encoding is checked, not trusted).
"""
import itertools
from dataclasses import dataclass, field

import numpy as np

from cora_neural_v2.rast import N, to_sexpr
from llm_writer.search.common import cpu_now

STATUSES = ("FIT_FOUND", "NO_FIT_IN_ENUMERATED_DOMAIN", "PROVED_UNSAT_IN_ENCODING", "BUDGET_EXHAUSTED",
            "UNSUPPORTED_CONSTRUCT", "EXECUTION_ERROR")
THR_FEATS = ("size", "bbox_height", "bbox_width", "hole_count", "size_rank", "size_rank_reversed",
             "color_frequency_rank", "count_of_same_shape", "count_of_same_color", "containment_depth")
RELATIONS = ("adjacent", "contains", "inside", "same_color", "same_shape", "same_size")
OPS = {"ge": ">=", "le": "<="}
MAX_OBJECTS = 60
MAX_SEL_CLASSES = 150
MAX_ACT_CLASSES = 80
K_AND = 12
K_EX = 12
DEFAULTS = ("keep", "delete")


class Unsupported(Exception):
    pass


# ------------------------------------------------------------------ facts
def _fate(o_cells, A, B, bg):
    from cora_neural_v2g3 import scene as SC
    return SC.fate(o_cells, A, B, bg)


def _fate_term(f):
    kind, colour, vec = f
    if kind == "recoloured":
        return ("recoloured", int(colour))
    if kind == "moved":
        return ("moved", int(vec[0]), int(vec[1]))
    return (kind,)


class Facts:
    """The observations of one task under one view (demonstrations only)."""

    def __init__(self, task, view, sel_nodes, act_nodes, features=THR_FEATS, relations=RELATIONS):
        from cora_neural_v2g3 import scene as SC
        t0 = cpu_now()
        self.view = view
        train = task["train"]
        self.n_demos = len(train)
        for a, b in train:
            if np.asarray(a).shape != np.asarray(b).shape:
                raise Unsupported("a demonstration changes the grid shape (the object-rule fragment keeps it)")
        self.objects, self.fates, self.col1, self.uncovered, self.bg, self.natives = [], [], [], [], [], []
        self.ocolor = []
        for a, b in train:
            A, B = np.asarray(a), np.asarray(b)
            objs, bg = SC.native_objects(A, view)
            self.natives.append(objs)
            self.bg.append(bg)
            self.ocolor.append([int(o.color) for o in objs])
            cells = [frozenset(o.cells) for o in objs]
            fates = [_fate_term(_fate(o.cells, A, B, bg)) for o in objs]
            self.objects.append(cells)
            self.fates.append(fates)
            self.col1.append([(lambda cs: next(iter(cs)) if len(cs) == 1 else None)({int(A[x]) for x in c})
                              for c in cells])
            covered = set().union(*cells) if cells else set()
            for c, f in zip(cells, fates):
                if f[0] == "moved":
                    covered |= {(r + f[1], q + f[2]) for r, q in c}
            changed = set(zip(*np.nonzero(A != B)))
            self.uncovered.append(len({(int(r), int(q)) for r, q in changed} - covered))
        self.radius = max(max(np.asarray(a).shape) for a, _ in train) - 1
        self._selectors(task, sel_nodes)
        self._actions(task, act_nodes)
        self._features(task, features)
        self._relations(task, relations)
        self.cpu = cpu_now() - t0

    # selectors: classes of equal picks (native)
    def _selectors(self, task, sel_nodes):
        from cora_neural_v2g3 import scene as SC
        uniq, seen = [], set()
        for s in sel_nodes:
            k = to_sexpr(s)
            if k not in seen:
                seen.add(k)
                uniq.append(s)
        picks = SC.selections(self.view, uniq, task["train"]) if uniq else {}
        self.sel_classes, self.sel_members, self.picks, index = [], [], [], {}
        for s in uniq:
            p = picks.get(s)
            if p is None or any(x is None for x in p):
                continue
            key = tuple(tuple(sorted(x)) for x in p)
            if key not in index:
                if len(self.sel_classes) >= MAX_SEL_CLASSES:
                    self.sel_truncated = True
                    continue
                index[key] = len(self.sel_classes)
                self.sel_classes.append(s)
                self.sel_members.append([])
                self.picks.append([frozenset(x) for x in p])
            self.sel_members[index[key]].append(s)
        self.sel_truncated = getattr(self, "sel_truncated", False)
        self.sel_index = {to_sexpr(m): i for i, ms in enumerate(self.sel_members) for m in ms}

    # actions: native effect per object; object-local ones only
    def _actions(self, task, act_nodes):
        from cora_neural_v2g2 import grammar as G
        self.act_classes, self.act_members, self.afates, index = [], [], [], {}
        self.act_nonlocal = 0
        seen = set()
        for a in act_nodes:
            k = to_sexpr(a)
            if k in seen:
                continue
            seen.add(k)
            try:
                d = G.compile_program(N("program", (self.view, (N("rule", (N("true", ()), a)),), "keep",
                                                    N("same_as_input", ()))))
            except Exception:                              # noqa: BLE001 (an action that does not compile)
                continue
            sig, ok = [], True
            for di, (inp, _) in enumerate(task["train"]):
                A = np.asarray(inp)
                try:
                    out = G.run(d, inp)
                except Exception:                          # noqa: BLE001
                    out = None
                if out is None or np.asarray(out).shape != A.shape:
                    ok = False
                    break
                O = np.asarray(out)
                fates = [_fate_term(_fate(c, A, O, self.bg[di])) for c in self.objects[di]]
                covered = set().union(*self.objects[di]) if self.objects[di] else set()
                for c, f in zip(self.objects[di], fates):
                    if f[0] == "moved":
                        covered |= {(r + f[1], q + f[2]) for r, q in c}
                changed = {(int(r), int(q)) for r, q in zip(*np.nonzero(A != O))}
                if changed - covered:
                    ok = False
                    self.act_nonlocal += 1
                    break
                sig.append(tuple(fates))
            if not ok:
                continue
            key = tuple(sig)
            if key not in index:
                if len(self.act_classes) >= MAX_ACT_CLASSES:
                    self.act_truncated = True
                    continue
                index[key] = len(self.act_classes)
                self.act_classes.append(a)
                self.act_members.append([])
                self.afates.append([list(x) for x in sig])
            self.act_members[index[key]].append(a)
        self.act_truncated = getattr(self, "act_truncated", False)
        self.act_index = {to_sexpr(m): i for i, ms in enumerate(self.act_members) for m in ms}

    def _features(self, task, features):
        from geocat_arc.object_reasoning import features as F
        from geocat_arc.object_reasoning.types import GridContext
        from geocat_arc.object_reasoning.types import SegmentationVariant as SV
        from geocat_arc.perception.grid import Grid
        if not F.FEATURE_REGISTRY:
            F.register_builtin_features()
        self.feats = {}
        for f in features:
            spec = F.FEATURE_REGISTRY.get(f)
            if spec is None:
                continue
            vals, ok = [], True
            for di, (inp, _) in enumerate(task["train"]):
                ctx = GridContext(grid=Grid(np.asarray(inp, dtype=np.int32)), objects=self.natives[di],
                                  background=self.bg[di], pair_index=di, role="input", variant=SV(self.view))
                row = []
                for o in self.natives[di]:
                    try:
                        v = spec.fn(o, ctx)
                    except Exception:                      # noqa: BLE001
                        v = None
                    if isinstance(v, bool) or not isinstance(v, (int, np.integer)):
                        ok = False
                        break
                    row.append(int(v))
                if not ok:
                    break
                vals.append(row)
            if ok and any(vals):
                self.feats[f] = vals
        # table keys seen on the TEST INPUTS (inputs only), so a completed table covers every query object
        from cora_neural_v2g3 import scene as SC
        self.test_keys = {f: set() for f in self.feats}
        self.test_keys["color"] = set()
        for t in task["test_inputs"]:
            try:
                objs, bg = SC.native_objects(np.asarray(t), self.view)
            except Exception:                              # noqa: BLE001
                continue
            ctx = GridContext(grid=Grid(np.asarray(t, dtype=np.int32)), objects=objs, background=bg, pair_index=0,
                              role="input", variant=SV(self.view))
            for o in objs:
                self.test_keys["color"].add(int(o.color))
                for f in self.feats:
                    try:
                        v = F.FEATURE_REGISTRY[f].fn(o, ctx)
                    except Exception:                      # noqa: BLE001
                        continue
                    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
                        self.test_keys[f].add(int(v))

    def table_keys(self, f):
        """Keys a completed table needs: the values on the demonstration objects and on the test-input objects."""
        demo = {c for row in self.ocolor for c in row} if f == "color" else \
            {v for row in self.feats.get(f, []) for v in row}
        return tuple(sorted(demo | self.test_keys.get(f, set())))

    def _relations(self, task, relations):
        from geocat_arc.object_reasoning import features as F
        from geocat_arc.object_reasoning.types import GridContext
        from geocat_arc.object_reasoning.types import SegmentationVariant as SV
        from geocat_arc.perception.grid import Grid
        self.rels = {}
        if any(len(o) > MAX_OBJECTS for o in self.natives):
            return
        for r in relations:
            spec = F.RELATION_REGISTRY.get(r)
            if spec is None:
                continue
            per = []
            for di, (inp, _) in enumerate(task["train"]):
                ctx = GridContext(grid=Grid(np.asarray(inp, dtype=np.int32)), objects=self.natives[di],
                                  background=self.bg[di], pair_index=di, role="input", variant=SV(self.view))
                objs = self.natives[di]
                pairs = set()
                for i, a in enumerate(objs):
                    for j, b in enumerate(objs):
                        if i != j and a.id != b.id:
                            try:
                                if spec.fn(a, b, ctx):
                                    pairs.add((i, j))
                            except Exception:              # noqa: BLE001
                                pass
                per.append(pairs)
            self.rels[r] = per

    def summary(self):
        return {"view": self.view, "objects": [len(o) for o in self.objects], "uncovered": self.uncovered,
                "sel_classes": len(self.sel_classes), "act_classes": len(self.act_classes),
                "act_nonlocal": self.act_nonlocal, "features": sorted(self.feats), "relations": sorted(self.rels),
                "truncated": bool(self.sel_truncated or self.act_truncated), "cpu_s": round(self.cpu, 3)}

    def object_list(self):
        return [(d, o) for d in range(self.n_demos) for o in range(len(self.objects[d]))]


# ------------------------------------------------------------------ domains and sketches
def sel_domain(facts):
    """The declared selector shapes, in a fixed order: picked classes, thresholds, conjunctions, relational."""
    dom = [("s", i) for i in range(len(facts.sel_classes))]
    for f in sorted(facts.feats):
        vals = [v for row in facts.feats[f] for v in row]
        lo, hi = min(vals), max(vals)
        if hi > lo:
            for op in ("ge", "le"):
                dom.append(("thr", f, op, ("h", "int", lo, hi)))
    k = min(K_AND, len(facts.sel_classes))
    dom += [("and", ("s", i), ("s", j)) for i in range(k) for j in range(i + 1, k)]
    ke = min(K_EX, len(facts.sel_classes))
    dom += [("ex", r, ("s", j)) for r in sorted(facts.rels) for j in range(ke)]
    return dom


TABLE_FEATS = ("size", "size_rank", "size_rank_reversed", "bbox_height", "bbox_width", "hole_count",
               "count_of_same_shape", "count_of_same_color", "color_frequency_rank")
MAX_TABLE_KEYS = 6


def act_domain(facts):
    dom = [("keep",), ("delete",), ("recolor", ("h", "colour")), ("translate", ("h", "vec", facts.radius))]
    ck = facts.table_keys("color")
    if 1 < len(ck) <= MAX_TABLE_KEYS + 2:
        dom.append(("cmap", ("h", "table", "color", ck)))
    for f in TABLE_FEATS:
        if f in facts.feats:
            keys = facts.table_keys(f)
            if 1 < len(keys) <= MAX_TABLE_KEYS:
                dom.append(("fmap", f, ("h", "table", f, keys)))
    return dom + [("a", j) for j in range(len(facts.act_classes))]


@dataclass
class Sketch:
    label: str
    rules: list                       # [("rule", selector-or-hole, action-or-hole)]
    default: object                   # "keep" | "delete" | ("h", "default")
    view: str
    seed: str = None
    holes: list = field(default_factory=list)

    def term(self):
        return ("sk", self.rules, self.default)


def domains(facts):
    return {"SEL": sel_domain(facts), "ACT": act_domain(facts)}


# ------------------------------------------------------------------ the Python evaluator of the rule AST
def sel_true(facts, s, d, o):
    t = s[0]
    if t == "true":
        return True
    if t == "s":
        return o in facts.picks[s[1]][d]
    if t == "and":
        return sel_true(facts, s[1], d, o) and sel_true(facts, s[2], d, o)
    if t == "thr":
        x = facts.feats[s[1]][d][o]
        return x >= s[3] if s[2] == "ge" else x <= s[3]
    if t == "ex":
        return any(sel_true(facts, s[2], d, o2) for (o1, o2) in facts.rels[s[1]][d] if o1 == o and o2 != o)
    raise ValueError(f"unknown selector {s!r}")


def act_ok(facts, a, d, o):
    f = facts.fates[d][o]
    t = a[0] if isinstance(a, tuple) else a
    if f[0] == "other":
        return False
    if t == "keep":
        return f[0] == "unchanged"
    if t == "delete":
        return f[0] == "deleted"
    if t == "recolor":
        if f[0] == "recoloured":
            return a[1] == f[1]
        return f[0] == "unchanged" and facts.col1[d][o] is not None and a[1] == facts.col1[d][o]
    if t == "translate":
        return f[0] == "moved" and (a[1], a[2]) == (f[1], f[2])
    if t == "a":
        return tuple(facts.afates[a[1]][d][o]) == tuple(f)
    if t in ("fmap", "cmap"):
        key = facts.ocolor[d][o] if t == "cmap" else facts.feats[a[1]][d][o]
        table = dict(a[-1])
        if key not in table:
            return False                                  # native raises: no entry for this value
        return act_ok(facts, ("recolor", table[key]), d, o)
    raise ValueError(f"unknown action {a!r}")


def first_fire(facts, rules, d, o):
    for k, r in enumerate(rules):
        if sel_true(facts, r[1], d, o):
            return k + 1, r[2]
    return 0, None


def consistent(facts, rules, default):
    for d, o in facts.object_list():
        k, a = first_fire(facts, rules, d, o)
        if not act_ok(facts, a if k else default, d, o):
            return False
    return True


# ------------------------------------------------------------------ ordinary bounded enumeration backend
def _slots(sk, doms):
    """Structural choice slots in Prolog's order: per rule its selector then its action, then the default."""
    slots = []
    for r in sk.rules:
        for part, dom in ((r[1], "SEL"), (r[2], "ACT")):
            if isinstance(part, tuple) and part[:2] in (("h", "sel"), ("h", "act")):
                slots.append(list(doms[part[2]]))
            else:
                slots.append([part])
    slots.append(list(DEFAULTS) if sk.default == ("h", "default") else [sk.default])
    return slots


def _fd_holes(x, out):
    """Integer holes in pre-order (Prolog's term_variables order): [(kind, info)]."""
    if isinstance(x, tuple):
        if len(x) >= 2 and x[0] == "h" and x[1] in ("colour", "vec", "int", "table"):
            out.append(x)
            return out
        for y in x:
            _fd_holes(y, out)
    elif isinstance(x, list):
        for y in x:
            _fd_holes(y, out)
    return out


def _ranges(holes):
    rs = []
    for h in holes:
        if h[1] == "colour":
            rs.append(range(0, 10))
        elif h[1] == "int":
            rs.append(range(h[2], h[3] + 1))
        elif h[1] == "table":
            rs += [range(0, 10)] * len(h[3])
        else:
            rs += [range(-h[2], h[2] + 1), range(-h[2], h[2] + 1)]
    return rs


def _instantiate(x, it):
    if isinstance(x, tuple):
        if len(x) >= 2 and x[0] == "h" and x[1] in ("colour", "int"):
            return next(it)
        if x and x[0] == "recolor" and len(x) == 2 and isinstance(x[1], tuple) and x[1][:2] == ("h", "colour"):
            return ("recolor", next(it))
        if x and x[0] == "translate" and len(x) == 2 and isinstance(x[1], tuple) and x[1][:2] == ("h", "vec"):
            return ("translate", next(it), next(it))
        if x and x[0] == "thr" and isinstance(x[3], tuple):
            return ("thr", x[1], x[2], next(it))
        if x and x[0] in ("fmap", "cmap") and isinstance(x[-1], tuple) and x[-1][:2] == ("h", "table"):
            return x[:-1] + (tuple((k, next(it)) for k in x[-1][3]),)
        return tuple(_instantiate(y, it) for y in x)
    if isinstance(x, list):
        return [_instantiate(y, it) for y in x]
    return x


def _vec_ok(holes, values):
    i = 0
    for h in holes:
        if h[1] == "vec":
            if values[i] == 0 and values[i + 1] == 0:
                return False
            i += 2
        elif h[1] == "table":
            i += len(h[3])
        else:
            i += 1
    return True


@dataclass
class Completion:
    status: str
    backend: str
    solutions: list = field(default_factory=list)     # ground ("prog", rules, default) terms, in order
    complete: bool = True
    reason: str = ""
    cpu_s: float = 0.0
    structures: int = 0
    trace: dict = None

    def as_dict(self):
        return {"status": self.status, "backend": self.backend, "n_solutions": len(self.solutions),
                "complete": self.complete, "reason": self.reason, "cpu_s": round(self.cpu_s, 4),
                "structures": self.structures, "solutions": [render(s) for s in self.solutions[:8]]}


def precheck(facts, sk):
    """UNSUPPORTED / PROVED_UNSAT shortcuts shared by both backends (None if the search must run)."""
    if any(facts.uncovered):
        tr = {"uncovered": facts.uncovered,
              "message": "changed cells lie outside every input object of this view: no object rule draws them"}
        return Completion("PROVED_UNSAT_IN_ENCODING", "precheck", reason="uncovered changes", trace=tr)
    return None


def solve_enum(facts, sk, max_sol=32, max_per=8, cpu_s=10.0):
    """Generate-and-test over the declared domains, same order as the Prolog backend; no propagation."""
    t0 = cpu_now()
    pre = precheck(facts, sk)
    if pre is not None:
        pre.backend = "enum"
        pre.cpu_s = cpu_now() - t0
        return pre
    doms = domains(facts)
    slots = _slots(sk, doms)
    sols, n_struct, capped = [], 0, False
    check = 0
    for choice in itertools.product(*slots):
        n_struct += 1
        rules = [("rule", choice[2 * i], choice[2 * i + 1]) for i in range(len(sk.rules))]
        default = choice[-1]
        holes = _fd_holes(rules, [])
        per = 0
        for values in itertools.product(*_ranges(holes)):
            check += 1
            if check % 256 == 0 and cpu_now() - t0 > cpu_s:
                return Completion("FIT_FOUND" if sols else "BUDGET_EXHAUSTED", "enum", sols, False,
                                  "cpu limit", cpu_now() - t0, n_struct)
            if holes and not _vec_ok(holes, values):
                continue
            g = _instantiate(rules, iter(values))
            if consistent(facts, g, default):
                sols.append(("prog", g, default))
                per += 1
                if len(sols) >= max_sol:
                    return Completion("FIT_FOUND", "enum", sols, False, "solution cap", cpu_now() - t0, n_struct)
                if per >= max_per:
                    capped = True
                    break
    truncated = facts.sel_truncated or facts.act_truncated
    if sols:
        return Completion("FIT_FOUND", "enum", sols, not capped, "per-structure cap" if capped else "",
                          cpu_now() - t0, n_struct)
    return Completion("NO_FIT_IN_ENUMERATED_DOMAIN" if truncated else "PROVED_UNSAT_IN_ENCODING", "enum", [], True,
                      "domain exhausted", cpu_now() - t0, n_struct)


def solve_exec(facts, sk, runner, max_sol=32, max_per=8, cpu_s=10.0):
    """The same enumeration as `solve_enum`, but every candidate is lowered (first member of each class) and run by
    the existing executor instead of checked against the facts: the executor's semantics, no fact model, the highest
    cost per candidate. Solutions are the candidates whose lowered program fits."""
    t0 = cpu_now()
    doms = domains(facts)
    slots = _slots(sk, doms)
    sols, n_struct, capped, n = [], 0, False, 0
    for choice in itertools.product(*slots):
        n_struct += 1
        rules = [("rule", choice[2 * i], choice[2 * i + 1]) for i in range(len(sk.rules))]
        default = choice[-1]
        holes = _fd_holes(rules, [])
        per = 0
        for values in itertools.product(*_ranges(holes)):
            n += 1
            if cpu_now() - t0 > cpu_s:
                return Completion("FIT_FOUND" if sols else "BUDGET_EXHAUSTED", "exec", sols, False, "cpu limit",
                                  cpu_now() - t0, n_struct)
            if holes and not _vec_ok(holes, values):
                continue
            g = ("prog", _instantiate(rules, iter(values)), default)
            progs = lower(facts, g, 1)
            if not progs:
                continue
            res, _ = runner.run(progs[0], origin="exec-backend", op=sk.label)
            if res.fits:
                sols.append(g)
                per += 1
                if len(sols) >= max_sol:
                    return Completion("FIT_FOUND", "exec", sols, False, "solution cap", cpu_now() - t0, n_struct)
                if per >= max_per:
                    capped = True
                    break
    truncated = facts.sel_truncated or facts.act_truncated
    if sols:
        return Completion("FIT_FOUND", "exec", sols, not capped, "per-structure cap" if capped else "",
                          cpu_now() - t0, n_struct)
    return Completion("NO_FIT_IN_ENUMERATED_DOMAIN" if truncated else "PROVED_UNSAT_IN_ENCODING", "exec", [], True,
                      "domain exhausted (executor)", cpu_now() - t0, n_struct)


# ------------------------------------------------------------------ rendering, lowering
def render(x):
    """Compact text of a rule-AST term (the trace and report form)."""
    if isinstance(x, tuple):
        if not x:
            return "()"
        head = x[0]
        if head == "prog":
            return "prog([" + ", ".join(render(r) for r in x[1]) + f"], {x[2]})"
        return f"{head}(" + ", ".join(render(y) for y in x[1:]) + ")" if len(x) > 1 else str(head)
    if isinstance(x, list):
        return "[" + ", ".join(render(y) for y in x) + "]"
    return str(x)


def _lower_sel(facts, s, variant):
    t = s[0]
    if t == "true":
        return [N("true", ())]
    if t == "s":
        return facts.sel_members[s[1]][:variant]
    if t == "and":
        return [N("and", (a, b)) for a in _lower_sel(facts, s[1], 1) for b in _lower_sel(facts, s[2], 1)]
    if t == "thr":
        return [N("test", (s[1], OPS[s[2]], int(s[3])))]
    if t == "ex":
        return [N("exists", (s[1], m)) for m in _lower_sel(facts, s[2], 1)]
    raise ValueError(s)


def _lower_act(facts, a, variant):
    t = a[0]
    if t == "keep":
        return [N("keep", ())]
    if t == "delete":
        return [N("delete", ())]
    if t == "recolor":
        return [N("recolor", (N("color", (int(a[1]),)),))]
    if t == "translate":
        return [N("translate", (N("vec", (int(a[1]), int(a[2]))),))]
    if t == "a":
        return facts.act_members[a[1]][:variant]
    if t == "fmap":
        return [N("recolor", (N("feature_map", (a[1], tuple((int(k), int(c)) for k, c in a[2]))),))]
    if t == "cmap":
        return [N("recolor", (N("color_map", (tuple((int(k), int(c)) for k, c in a[1]),)),))]
    raise ValueError(a)


def lower(facts, sol, max_variants=4):
    """CORA programs for one ground solution: every combination of class members (selectors or actions with equal
    effects on the demonstrations, which may differ on a test input), at most `max_variants` programs."""
    _, rules, default = sol
    parts = []
    for r in rules:
        parts.append(_lower_sel(facts, r[1], max_variants))
        parts.append(_lower_act(facts, r[2], max_variants))
    out = []
    for combo in itertools.product(*parts):
        rr = tuple(N("rule", (combo[2 * i], combo[2 * i + 1])) for i in range(len(rules)))
        out.append(N("program", (facts.view, rr, default, N("same_as_input", ()))))
        if len(out) >= max_variants:
            break
    return out


# ------------------------------------------------------------------ seeds as terms; sketches from seeds
def seed_parts(prog):
    """(view, [(PRED, ACTION)], default) of a seed in the object-rule fragment, else raise Unsupported."""
    if not (isinstance(prog, N) and prog.op == "program"):
        raise Unsupported(f"program form {getattr(prog, 'op', type(prog).__name__)} is outside the fragment")
    view, rules, default, rend = prog.args
    if not (isinstance(rend, N) and rend.op == "same_as_input"):
        raise Unsupported(f"render {getattr(rend, 'op', rend)} (the fragment keeps the input canvas)")
    out = []
    for r in rules:
        if not (isinstance(r, N) and r.op == "rule"):
            raise Unsupported(f"rule form {getattr(r, 'op', r)} (bindings are outside the fragment)")
        out.append((r.args[0], r.args[1]))
    return view, out, default


def term_of_seed(facts, parts):
    """The seed's rules as rule-AST terms over `facts` (its own selectors and actions are in the domains)."""
    _, rules, default = parts
    out = []
    for p, a in rules:
        si = facts.sel_index.get(to_sexpr(p))
        if si is None:
            raise Unsupported(f"selector {to_sexpr(p)[:60]} has no picks on some demonstration")
        if a.op in ("keep", "delete"):
            at = (a.op,)
        elif a.op == "recolor" and isinstance(a.args[0], N) and a.args[0].op == "color":
            at = ("recolor", int(a.args[0].args[0]))
        elif a.op == "translate" and isinstance(a.args[0], N) and a.args[0].op == "vec":
            at = ("translate", int(a.args[0].args[0]), int(a.args[0].args[1]))
        elif a.op == "recolor" and isinstance(a.args[0], N) and a.args[0].op == "feature_map" and \
                a.args[0].args[0] in facts.feats:
            at = ("fmap", a.args[0].args[0], tuple((int(k), int(c)) for k, c in a.args[0].args[1]))
        elif a.op == "recolor" and isinstance(a.args[0], N) and a.args[0].op == "color_map":
            at = ("cmap", tuple((int(k), int(c)) for k, c in a.args[0].args[0]))
        else:
            ai = facts.act_index.get(to_sexpr(a))
            if ai is None:
                raise Unsupported(f"action {to_sexpr(a)[:60]} is not object-local on the demonstrations")
            at = ("a", ai)
        out.append(("rule", ("s", si), at))
    return out, default


H_SEL, H_ACT = ("h", "sel", "SEL"), ("h", "act", "ACT")


def make_sketch(facts, rules, default, holes, seed=None):
    """The sketch of a seed's rules with the given holes: ("SEL", i), ("ACT", i), ("PARAM", i), ("DEFAULT", None),
    ("ADD", position) (a new rule with a selector hole and an action hole). None if a hole does not apply."""
    rr = [list(r) for r in rules]
    d = default
    add = None
    for kind, i in holes:
        if kind == "SEL":
            rr[i][1] = H_SEL
        elif kind == "ACT":
            rr[i][2] = H_ACT
        elif kind == "PARAM":
            a = rr[i][2]
            if a[0] == "recolor":
                rr[i][2] = ("recolor", ("h", "colour"))
            elif a[0] == "translate":
                rr[i][2] = ("translate", ("h", "vec", facts.radius))
            elif a[0] == "fmap":
                rr[i][2] = ("fmap", a[1], ("h", "table", a[1], facts.table_keys(a[1])))
            elif a[0] == "cmap":
                rr[i][2] = ("cmap", ("h", "table", "color", facts.table_keys("color")))
            else:
                return None
        elif kind == "DEFAULT":
            d = ("h", "default")
        elif kind == "ADD":
            add = i
    out = [tuple(r) for r in rr]
    if add is not None:
        out.insert(add, ("rule", H_SEL, H_ACT))
    return Sketch(label_of(holes), out, d, facts.view, seed, list(holes))


def lab(*parts):
    """Canonical label of a hole set ("SEL@1", "DEFAULT", ...): its parts sorted and joined by '+'."""
    return "+".join(sorted(parts))


def label_of(holes):
    return lab(*(f"{k}@{i}" if i is not None else k for k, i in holes))


def hole_sets(rules, focus=None, max_rules=4):
    """Hole sets in the fixed (blind) order: single holes, then pairs. Pairs use the first `max_rules` rules, or the
    implicated rules `focus` first when given."""
    k = len(rules)
    idx = list(range(k))
    if focus:
        idx = [i for i in focus if 0 <= i < k] + [i for i in idx if i not in focus]
    idx2 = idx[:max_rules]
    single = []
    for i in idx:
        single += [(("SEL", i),), (("PARAM", i),), (("ACT", i),)]
    single += [(("DEFAULT", None),), (("ADD", k),)]
    if k:
        single.append((("ADD", 0),))
    pairs = [(("SEL", i), ("ACT", i)) for i in idx2]
    pairs += [(("SEL", i), ("DEFAULT", None)) for i in idx2]
    pairs += [(("SEL", i), ("SEL", j)) for a, i in enumerate(idx2) for j in idx2[a + 1:]]
    pairs += [(("SEL", i), ("ACT", j)) for i in idx2 for j in idx2 if i != j]
    pairs += [(("ACT", i), ("ACT", j)) for a, i in enumerate(idx2) for j in idx2[a + 1:]]
    pairs += [(("ADD", k), ("DEFAULT", None))]
    return single + pairs


def seed_sketches(facts, rules, default, label="seed", focus=None, max_rules=4):
    """Typed sketches derived from one seed, in the fixed (blind) order."""
    out = []
    for hs in hole_sets(rules, focus, max_rules):
        sk = make_sketch(facts, rules, default, hs, label)
        if sk is not None:
            out.append(sk)
    return out


# ------------------------------------------------------------------ derivation traces
def derivation(facts, rules, default):
    """Goal/subgoal trace of a ground rule-AST program on the demonstrations: per object, the observed fate, the
    first rule whose selector holds (0 = the default) and whether the action's predicted fate equals the observed one;
    failures classified as over_select, under_select, default_deletes, wrong_param, wrong_kind, unexplainable."""
    rows, summary = [], {}
    for d, o in facts.object_list():
        f = facts.fates[d][o]
        k, a = first_fire(facts, rules, d, o)
        act = a if k else default
        ok = act_ok(facts, act, d, o)
        kind = None
        if not ok:
            if f[0] == "other":
                kind = "unexplainable"
            elif k == 0:
                kind = "under_select" if default == "keep" else "default_deletes"
            elif f[0] == "unchanged":
                kind = "over_select"
            else:
                pk = _pred_kind(facts, act, d, o)
                kind = "wrong_param" if pk == f[0] else "wrong_kind"
            summary[(k, kind)] = summary.get((k, kind), 0) + 1
        rows.append((d, o, f, k, int(ok), kind))
    return {"rows": rows, "summary": summary, "fits": not summary and not any(facts.uncovered),
            "uncovered": list(facts.uncovered)}


def _pred_kind(facts, act, d, o):
    t = act[0] if isinstance(act, tuple) else act
    if t == "keep":
        return "unchanged"
    if t == "delete":
        return "deleted"
    if t == "recolor":
        return "recoloured"
    if t == "translate":
        return "moved"
    if t == "a":
        return facts.afates[act[1]][d][o][0]
    if t in ("fmap", "cmap"):
        return "recoloured"
    return None


#: repair hypotheses per failure kind: {(hole kind): weight}; "rule" means the rule that fired
SUGGEST = {"over_select": {"SEL": 1.0, "SEL+DEFAULT": 0.3},
           "wrong_kind": {"ACT": 1.0, "SEL": 0.7, "SELACT": 0.3},
           "wrong_param": {"PARAM": 1.0, "ACT": 0.4, "SEL": 0.3},
           "under_select": {"ADD": 1.0, "DEFAULT": 0.6, "SEL*": 0.4},
           "default_deletes": {"DEFAULT": 1.0, "ADD": 0.5, "SEL*": 0.4},
           "unexplainable": {}}


def trace_suggest(trace, n_rules):
    """{hole-set label: weight} from a derivation trace (repair hypotheses, not proofs). SEL* spreads over every
    rule's selector."""
    w = {}

    def add(key, x):
        w[key] = w.get(key, 0.0) + x
    for (k, kind), n in trace["summary"].items():
        for h, x in SUGGEST.get(kind, {}).items():
            i = k - 1
            if h == "SEL" and k:
                add(f"SEL@{i}", n * x)
            elif h == "ACT" and k:
                add(f"ACT@{i}", n * x)
            elif h == "PARAM" and k:
                add(f"PARAM@{i}", n * x)
            elif h == "SELACT" and k:
                add(lab(f"SEL@{i}", f"ACT@{i}"), n * x)
            elif h == "SEL+DEFAULT" and k:
                add(lab(f"SEL@{i}", "DEFAULT"), n * x)
            elif h == "DEFAULT":
                add("DEFAULT", n * x)
            elif h == "ADD":
                add(f"ADD@{n_rules}", n * x)
                add("ADD@0", n * x * 0.8)
                add(lab(f"ADD@{n_rules}", "DEFAULT"), n * x * 0.5)
            elif h == "SEL*":
                for j in range(n_rules):
                    add(f"SEL@{j}", n * x / max(1, n_rules))
                    add(lab(f"SEL@{j}", "DEFAULT"), n * x / max(1, n_rules) / 2)
    # a pair of implicated single holes is implicated too
    singles = sorted(((v, key) for key, v in w.items() if "+" not in key), reverse=True)[:4]
    for a in range(len(singles)):
        for b in range(a + 1, len(singles)):
            add(lab(singles[a][1], singles[b][1]), (singles[a][0] + singles[b][0]) / 4)
    return w


def implicated_rules(trace):
    return sorted({k - 1 for (k, _kind) in trace["summary"] if k})


def order_sketches(sketches, weights):
    """Sketches implicated by the trace first (by weight), then the rest in blind order."""
    base = {id(s): j for j, s in enumerate(sketches)}
    return sorted(sketches, key=lambda s: (-weights.get(s.label, 0.0), base[id(s)]))


def compact(trace, facts, max_items=6):
    """A short text of a derivation trace for repair prompts or reports."""
    if not trace["summary"]:
        return "every object's observed fate is derived by the program" + (
            "" if not any(trace["uncovered"]) else f"; {sum(trace['uncovered'])} changed cells lie outside objects")
    lines = []
    for (k, kind), n in sorted(trace["summary"].items(), key=lambda t: -t[1]):
        who = f"rule {k}" if k else "the default"
        lines.append(f"{kind.replace('_', ' ')} at {who}: {n} object(s)")
    ex = [r for r in trace["rows"] if r[5]][:max_items]
    for d, o, f, k, _, kind in ex:
        cells = sorted(facts.objects[d][o])
        lines.append(f"  example {d + 1} object {o} (rows {cells[0][0]}-{cells[-1][0]}): observed {render(f)}, "
                     f"{'rule ' + str(k) if k else 'default'} fired: {kind}")
    return "\n".join(lines)
