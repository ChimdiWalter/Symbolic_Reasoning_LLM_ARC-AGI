"""Hole-directed construction of object-level candidate operations.

A hole is a list of (input grid, target grid) pairs (the growth controller's typed holes: the demonstrations, or the
demonstrations composed with one invertible G0 operation). For each view the step:

1. OBJECT CORRESPONDENCE. Every input grid is segmented (scene.py). An input object is CHANGED when any of its
   cells differs in the target; a target cell is APPEARED when it differs from the input and belongs to no input
   object. For every changed object the edits that explain its fate are bound from the pair (bind_edits: each edit
   type with its parameters read off the target, kept when its writes agree with the target and its vacated cells are
   background there). The hole has an object correspondence under the view when every changed object of every pair
   is explained by at least one edit and every appeared cell is written by some bound edit.
2. EDITS. The hole's single-rule edits are those bound for every changed object of every pair (a changed object
   whose differing cells are all written by other objects' bound edits is not required to have its own edit).
3. SELECTION. Predicates are the atoms seen in the scenes, their negations, and conjunctions of two atoms (scene.py).
   A predicate is admissible for an edit when it holds on every required object and the edit is consistent on every
   object it selects (an unchanged selected object must be a no-op under the edit).
4. COMPOSE AND VERIFY. Each (predicate, edit) is an operation (edits.ObjOp, form paint); it is kept only when it maps
   every hole input to its target exactly. When no single rule verifies, two-rule first-match lists are tried
   (e1 on the objects a first predicate separates, e2 on the rest). Whole-output forms (crop to the selected object,
   token, count, symmetry completion) are tried on every hole as well.
   Leave-one-out: a paint candidate passes when its edit is proposed by the changed objects of at least two pairs,
   so that its parameters are recoverable with any one pair left out; the whole-output forms bind their parameters
   in every pair. Candidates are ordered by the number of verified candidates that agree with them on the hole's
   test inputs (largest group first, as CORA ranks agreeing programs), then by simplicity (rules, atoms, edit
   order); at most MAX_CANDS are returned per hole.
Every segmentation, edit application and operation application is counted in edits.COUNTS.
"""
import itertools

from objgrow import scene as SC, edits as ED

MAX_CANDS = 8
MAX_ATOM_PAIRS = 600
MAX_OPS_PER_HOLE = 20000
MAX_TWO_RULE_EDITS = 10
SMALL_GRID = 400
WINDOW = 4
EDIT_ORDER = ("delete", "recolor", "recolor_attr", "recolor_table", "move", "gravitate", "shift", "extend",
              "connect", "fill_holes", "fill_box", "hollow", "outline", "outbox", "mirror", "rot", "scale",
              "duplicate", "mirror_copy")


# ------------------------------------------------------------------ pair analysis
def consistent(writes, vacate, o, y, bg, strict=True):
    """Writes agree with the target; vacated cells of o not re-written are background in the target. Strict (for
    binding an edit from a pair): every write must land inside the grid, so that a move off the grid is not taken
    for a deletion."""
    H, W = len(y), len(y[0])
    wp = set()
    for v, (i, j) in writes:
        if 0 <= i < H and 0 <= j < W:
            if y[i][j] != v:
                return False
            wp.add((i, j))
        elif strict:
            return False
    if vacate:
        for i, j in o.cells:
            if (i, j) not in wp and y[i][j] != bg:
                return False
    return True


def edit_ok(e, o, s, x, y):
    w = ED.apply_edit(e, o, s, x)
    return w is not None and consistent(w, ED.edit_vacates(e), o, y, s.bg)


def write_cells(w, H, W):
    return {(i, j) for _, (i, j) in w if 0 <= i < H and 0 <= j < W}


GROWTH = ("scale", "extend", "connect", "fill_holes", "fill_box", "outline", "outbox", "duplicate", "mirror_copy")


def bind_edits(o, s, x, y, ys, appeared=None):
    """Edits (with parameters read off the target) that explain the object o's fate; each is non-trivial on o.
    `appeared` (the target's new non-background cells owned by no input object) restricts an UNCHANGED object to
    the growth edits that write at least one of them."""
    bg, H, W = s.bg, s.H, s.W
    out = {}

    def keep(e, writes):
        if writes is None or not consistent(writes, ED.edit_vacates(e), o, y, bg):
            return
        if appeared is not None:
            if e[0] not in GROWTH or not any((i, j) in appeared for _, (i, j) in writes):
                return
        out[e] = writes

    ycols = {y[i][j] for i, j in o.cells}
    if ycols == {bg}:
        keep(("delete",), frozenset())
    if len(ycols) == 1:
        c = next(iter(ycols))
        if c != o.colour or len(o.colours) > 1:
            # a constant recolouring, also when the constant happens to be this pair's background
            keep(("recolor", c), frozenset((c, p) for p in o.cells))
        if c != bg and (c != o.colour or len(o.colours) > 1):
            for a in ED.ATTRS:
                if ED.attribute(a, o, s) == c:
                    keep(("recolor_attr", a), frozenset((c, p) for p in o.cells))
    vs = set()
    if ys is not None:
        for b in ys.objs:
            if b.norm == o.norm:
                v = (b.box[0] - o.box[0], b.box[1] - o.box[1])
                if v != (0, 0):
                    vs.add(v)
    if not vs and H * W <= SMALL_GRID:
        for di in range(-WINDOW, WINDOW + 1):
            for dj in range(-WINDOW, WINDOW + 1):
                if (di, dj) != (0, 0):
                    vs.add((di, dj))
    for v in sorted(vs):
        keep(("shift", v[0], v[1]), ED.shifted(o, v))
    for d in "UDLR":
        for stop in ("blocked", "border"):
            v = ED.move_vector(o, x, bg, d, stop)
            if v != (0, 0):
                keep(("move", d, stop), ED.shifted(o, v))
    for which in ("nearest", "nearest_diff"):
        q = s.nearest(o, same_colour=None if which == "nearest" else False)
        if q is not None:
            v = ED.gravitate_vector(o, q)
            if v and v != (0, 0):
                keep(("gravitate", which), ED.shifted(o, v))
    for k in ("h", "v", "d", "c"):
        w = ED.inplace(o, k)
        if w != o.obj:
            keep(("mirror", k), w)
    for k in (1, 2, 3):
        w = ED.inplace(o, k)
        if w != o.obj:
            keep(("rot", k), w)
    for k in (2, 3):
        keep(("scale", k), ED.apply_edit(("scale", k), o, s, x))
    for d in ED.EXT_DIRS:
        for stop in ED.STOPS:
            w = o.obj | ED.rays(o, x, bg, d, stop)
            if w != o.obj:
                keep(("extend", d, stop), w)
    for which in ("same", "any"):
        w = ED.apply_edit(("connect", which), o, s, x)
        if w is not None and w != o.obj:
            keep(("connect", which), w)
    if o.enclosed_cells:
        cols = {y[i][j] for i, j in o.enclosed_cells}
        if len(cols) == 1:
            c = next(iter(cols))
            if c != bg:
                keep(("fill_holes", c), o.obj | frozenset((c, p) for p in o.enclosed_cells))
                if c == o.colour:
                    keep(("fill_holes", "self"), o.obj | frozenset((c, p) for p in o.enclosed_cells))
    if o.size < o.h * o.w:
        rest = [(i, j) for i in range(o.box[0], o.box[2] + 1) for j in range(o.box[1], o.box[3] + 1)
                if (i, j) not in o.cells]
        cols = {y[i][j] for i, j in rest}
        if len(cols) == 1:
            c = next(iter(cols))
            if c != bg:
                keep(("fill_box", c), o.obj | frozenset((c, p) for p in rest))
                if c == o.colour:
                    keep(("fill_box", "self"), o.obj | frozenset((c, p) for p in rest))
    inner = ED.interior(o, H, W)
    if inner:
        keep(("hollow",), frozenset((v, p) for v, p in o.obj if p not in inner))
    for name, ring in (("outline", ED.ring8(o, H, W)), ("outbox", ED.outbox_ring(o, H, W))):
        cells = [p for p in ring if x[p[0]][p[1]] == bg] if name == "outline" else list(ring)
        if cells:
            cols = {y[i][j] for i, j in cells}
            if len(cols) == 1:
                c = next(iter(cols))
                if c != bg:
                    keep((name, c), o.obj | frozenset((c, p) for p in cells))
    if all(y[i][j] == x[i][j] for i, j in o.cells):
        if ys is not None:
            for b in ys.objs:
                if b.norm == o.norm and b.cells != o.cells:
                    v = (b.box[0] - o.box[0], b.box[1] - o.box[1])
                    if any(x[i][j] != c for c, (i, j) in b.obj):
                        keep(("duplicate", v[0], v[1]), o.obj | ED.shifted(o, v))
        for k in ("h", "v"):
            for side in ("+", "-"):
                w = ED.apply_edit(("mirror_copy", k, side), o, s, x)
                if w is not None and any(0 <= i < H and 0 <= j < W and x[i][j] != c for c, (i, j) in w):
                    keep(("mirror_copy", k, side), w)
    return out


class Pair:
    """One hole pair under a view: the input scene, the changed and required objects, the bound edits."""

    def __init__(self, x, y, view):
        self.x, self.y, self.view = x, y, view
        self.s = ED.scene_of(x, view)
        self.same = (len(x), len(x[0])) == (len(y), len(y[0]))
        self.ys = None
        self.changed, self.required, self.bound, self.appeared, self.unexplained = [], [], {}, set(), set()
        self.explained_all = False
        if self.s is None:
            return
        if self.same:
            self.ys = ED.scene_of(y, view)
            H, W = self.s.H, self.s.W
            diff = {(i, j) for i in range(H) for j in range(W) if x[i][j] != y[i][j]}
            owned = set()
            for o in self.s.objs:
                if o.cells & diff:
                    self.changed.append(o.idx)
                owned |= o.cells
            self.appeared = diff - owned
            for o in self.s.objs:
                if o.idx in self.changed:
                    self.bound[o.idx] = bind_edits(o, self.s, x, y, self.ys)
                elif self.appeared:
                    es = bind_edits(o, self.s, x, y, self.ys, appeared=self.appeared)
                    if es:
                        self.bound[o.idx] = es
            written = set()
            for idx, es in self.bound.items():
                for w in es.values():
                    written |= write_cells(w, H, W)
            self.unexplained = self.appeared - written
            for idx in self.changed:
                o = self.s.objs[idx]
                others = set()
                for jdx, es in self.bound.items():
                    if jdx != idx:
                        for w in es.values():
                            others |= write_cells(w, H, W)
                if not (o.cells & diff) <= others:
                    self.required.append(idx)
            self.explained_all = all(self.bound[i] for i in self.changed) and not self.unexplained
            # proposers: the objects whose fate proposes an edit (changed ones; else the growing ones)
            self.proposers = list(self.required) if self.required else sorted(self.bound)

    def proposed(self):
        out = set()
        for es in self.bound.values():
            out |= set(es)
        return out


# ------------------------------------------------------------------ predicates
def predicates(scenes):
    atoms = SC.atom_space(scenes)
    out = [("true",)]
    out += [a for a in atoms if a != ("true",)]
    out += [("not", a) for a in atoms if a != ("true",) and a[0] not in ("size", "height", "width", "n_colours",
                                                                          "holes", "size_rank", "size_ge")]
    return out


def conjunctions(cov):
    """Conjunctions of two covering predicates (both must hold on every required object), bounded."""
    singles = [p for p in cov if p != ("true",)]
    out = []
    for a, b in itertools.combinations(singles, 2):
        if a[0] == "not" and b[0] == "not":
            continue
        out.append(("and", a, b))
        if len(out) >= MAX_ATOM_PAIRS:
            break
    return out


def edit_sort_key(e):
    k = EDIT_ORDER.index(e[0]) if e[0] in EDIT_ORDER else len(EDIT_ORDER)
    mag = sum(abs(v) for v in e[1:] if isinstance(v, int))
    return (k, mag, str(e))


def pred_size(p):
    if p[0] == "true":
        return 0
    if p[0] == "not":
        return 1 + pred_size(p[1])
    if p[0] == "and":
        return 1 + pred_size(p[1]) + pred_size(p[2])
    return 1


# ------------------------------------------------------------------ construction per view
def verify(op, pairs):
    for p in pairs:
        if ED.COUNTS["op"] > MAX_OPS_PER_HOLE:
            return False
        if op(p.x) != p.y:
            return False
    return True


def admissible(pred, e, pairs):
    """The predicate selects every required object, and the edit is consistent on every selected object (a
    required object through its bound edits; any other object as a no-op or a bound growth edit)."""
    for p in pairs:
        sel = [o for o in p.s.objs if SC.holds(o, pred)]
        sel_idx = {o.idx for o in sel}
        req = set(p.required)
        if not req <= sel_idx:
            return False
        for o in sel:
            if o.idx in req:
                if e not in p.bound[o.idx] and not (e[0] == "recolor_table" and edit_ok(e, o, p.s, p.x, p.y)):
                    return False
            elif e not in p.bound.get(o.idx, ()) and not edit_ok(e, o, p.s, p.x, p.y):
                return False
    return True


def covering(preds, pairs):
    out = []
    for pred in preds:
        if all(SC.holds(p.s.objs[i], pred) for p in pairs for i in p.required):
            out.append(pred)
    return out


def table_edits(pairs):
    """Colour tables keyed by an attribute: one colour per key, consistent over every changed object that is
    recoloured; the table is an edit of its own."""
    out = []
    req = [(p, p.s.objs[i]) for p in pairs for i in p.required]
    if not req:
        return out
    for key in ED.TABLE_KEYS:
        table, ok = {}, True
        for p, o in req:
            cs = [e[1] for e in p.bound[o.idx] if e[0] == "recolor"]
            if len(cs) != 1:
                ok = False
                break
            k = ED.table_key(key, o)
            if table.get(k, cs[0]) != cs[0]:
                ok = False
                break
            table[k] = cs[0]
        if ok and len(set(table.values())) > 1:
            out.append(("recolor_table", key, tuple(sorted(table.items(), key=str))))
    return out


def paint_candidates(pairs, preds, why):
    """Single-rule and (when none verifies) two-rule paint operations, verified exactly. `why` (a dict) receives
    the reason class when nothing verifies: no_required_objects, no_common_edit, no_admissible_predicate,
    verification_failed."""
    view = pairs[0].view
    found = []
    req_objs = [(p, i) for p in pairs for i in p.required]
    grow_objs = [(p, i) for p in pairs for i in p.bound if i not in p.required]
    if not req_objs and not grow_objs:
        why["reason"] = "no_required_objects"
        return found
    if req_objs:
        # every changed object must be explained by the one edit
        common = None
        for p, i in req_objs:
            es = set(p.bound[i])
            common = es if common is None else common & es
        common = sorted(common or (), key=edit_sort_key)
        common += table_edits(pairs)
    else:
        # nothing changed, cells appeared: any growth edit some object proposes; the predicate picks the growers
        cnt = {}
        for p, i in grow_objs:
            for e in p.bound[i]:
                cnt[e] = cnt.get(e, 0) + 1
        common = sorted(cnt, key=lambda e: (-cnt[e], edit_sort_key(e)))
        req_objs = grow_objs
    why["common_edits"] = [str(e) for e in common[:6]]
    why["reason"] = "no_common_edit" if not common else "no_admissible_predicate"
    proposing = {}
    for e in common:
        proposing[e] = sum(1 for p in pairs if any(e in es or (e[0] == "recolor_table" and
                                                                any(f[0] == "recolor" for f in es))
                                                    for es in p.bound.values()))
    cov = covering(preds, pairs)
    cov_all = cov + conjunctions(cov)
    for e in common:
        for pred in cov_all:
            if ED.COUNTS["op"] > MAX_OPS_PER_HOLE:
                return found
            if not admissible(pred, e, pairs):
                continue
            op = ED.ObjOp({"form": "paint", "view": view, "rules": [[pred, e]]})
            if verify(op, pairs):
                found.append({"op": op, "loo": proposing[e] >= 2, "proposing": proposing[e],
                              "simplicity": (1, pred_size(pred), edit_sort_key(e))})
                break                     # the simplest admissible predicate for this edit
            why["reason"] = "verification_failed"
            why.setdefault("failed", []).append([SC.atom_text(pred), str(e)])
    if found:
        why["reason"] = "verified"
        return found
    # two rules: e1 on the objects a predicate separates, e2 on the rest (first-match)
    cnt = {}
    for p, i in req_objs:
        for e in p.bound[i]:
            cnt[e] = cnt.get(e, 0) + 1
    edits = sorted(cnt, key=lambda e: (-cnt[e], edit_sort_key(e)))[:MAX_TWO_RULE_EDITS]
    for e1, e2 in itertools.permutations(edits, 2):
        c1 = [(p, i) for p, i in req_objs if e1 in p.bound[i]]
        c2 = [(p, i) for p, i in req_objs if e2 in p.bound[i]]
        if len(c1) + len(c2) < len(req_objs) or not c1 or not c2:
            continue
        only1 = [(p, i) for p, i in c1 if e2 not in p.bound[i]]
        only2 = [(p, i) for p, i in c2 if e1 not in p.bound[i]]
        if not only1:
            continue
        for p1 in preds:
            if p1 == ("true",):
                continue
            if not all(SC.holds(p.s.objs[i], p1) for p, i in only1):
                continue
            if any(SC.holds(p.s.objs[i], p1) for p, i in only2):
                continue
            ok = True
            for p in pairs:
                for o in p.s.objs:
                    if SC.holds(o, p1):
                        if o.idx in p.bound:
                            ok = e1 in p.bound[o.idx]
                        else:
                            ok = edit_ok(e1, o, p.s, p.x, p.y)
                        if not ok:
                            break
                if not ok:
                    break
            if not ok:
                continue
            rest = [(p, i) for p, i in req_objs if not SC.holds(p.s.objs[i], p1)]
            for p2 in preds:
                if not all(SC.holds(p.s.objs[i], p2) for p, i in rest):
                    continue
                ok = True
                for p in pairs:
                    for o in p.s.objs:
                        if not SC.holds(o, p1) and SC.holds(o, p2):
                            if o.idx in p.bound:
                                ok = e2 in p.bound[o.idx]
                            else:
                                ok = edit_ok(e2, o, p.s, p.x, p.y)
                            if not ok:
                                break
                    if not ok:
                        break
                if not ok:
                    continue
                if ED.COUNTS["op"] > MAX_OPS_PER_HOLE:
                    return found
                op = ED.ObjOp({"form": "paint", "view": view, "rules": [[p1, e1], [p2, e2]]})
                if verify(op, pairs):
                    pr = min(proposing_count(e1, pairs), proposing_count(e2, pairs))
                    found.append({"op": op, "loo": pr >= 2, "proposing": pr,
                                  "simplicity": (2, pred_size(p1) + pred_size(p2), edit_sort_key(e1))})
                    break
                why["reason"] = "verification_failed"
            if found:
                break
        if found:
            break
    if found:
        why["reason"] = "verified_two_rules"
    return found


def proposing_count(e, pairs):
    return sum(1 for p in pairs if any(e in es for es in p.bound.values()))


def whole_candidates(pairs, preds):
    """Crop, token and count forms (output built from the selected objects, any output shape)."""
    found = []
    view = pairs[0].view
    xs_ys = [(p.x, p.y, p.s) for p in pairs]
    # crop
    targets = []
    for x, y, s in xs_ys:
        t = []
        for o in s.objs:
            i0, j0, i1, j1 = o.box
            if (o.h, o.w) == (len(y), len(y[0])) and tuple(tuple(x[i][j0:j1 + 1]) for i in range(i0, i1 + 1)) == y:
                t.append(o.idx)
        targets.append(t)
    if all(targets):
        for pred in preds + conjunctions([p for p in preds if all(any(SC.holds(s.objs[i], p) for i in t)
                                                                   for (x, y, s), t in zip(xs_ys, targets))]):
            ok = True
            for (x, y, s), t in zip(xs_ys, targets):
                sel = [o.idx for o in s.objs if SC.holds(o, pred)]
                if len(sel) != 1 or sel[0] not in t:
                    ok = False
                    break
            if ok:
                op = ED.ObjOp({"form": "crop", "view": view, "rules": [[pred, ("keep",)]]})
                if verify(op, pairs):
                    found.append({"op": op, "loo": True, "proposing": len(pairs),
                                  "simplicity": (1, pred_size(pred), (0, 0, "crop"))})
                    break
    # token and count: uniform targets
    uni = []
    for x, y, s in xs_ys:
        cols = {v for r in y for v in r}
        uni.append(next(iter(cols)) if len(cols) == 1 else None)
    if all(c is not None for c in uni):
        shapes = {(len(y), len(y[0])) for _, y, _ in xs_ys}
        if len(shapes) == 1:
            shape = next(iter(shapes))
            for pred in preds:
                ok = True
                for (x, y, s), c in zip(xs_ys, uni):
                    sel = [o for o in s.objs if SC.holds(o, pred)]
                    if not sel or {o.colour for o in sel} != {c}:
                        ok = False
                        break
                if ok:
                    op = ED.ObjOp({"form": "token", "view": view, "rules": [[pred, ("keep",)]],
                                   "params": {"shape": list(shape)}})
                    if verify(op, pairs):
                        found.append({"op": op, "loo": True, "proposing": len(pairs),
                                      "simplicity": (1, pred_size(pred), (0, 0, "token"))})
                        break
        for orient in ("row", "col"):
            ns = []
            for _, y, _ in xs_ys:
                if orient == "row" and len(y) == 1:
                    ns.append(len(y[0]))
                elif orient == "col" and len(y[0]) == 1:
                    ns.append(len(y))
                else:
                    ns = None
                    break
            if ns is None:
                continue
            for pred in preds:
                sels = []
                ok = True
                for (x, y, s), n in zip(xs_ys, ns):
                    sel = [o for o in s.objs if SC.holds(o, pred)]
                    if len(sel) != n:
                        ok = False
                        break
                    sels.append(sel)
                if not ok:
                    continue
                colour = None
                if len(set(uni)) == 1:
                    colour = uni[0]
                elif all({o.colour for o in sel} == {c} for sel, c in zip(sels, uni)):
                    colour = "self"
                if colour is None:
                    continue
                op = ED.ObjOp({"form": "count", "view": view, "rules": [[pred, ("keep",)]],
                               "params": {"colour": colour, "orient": orient}})
                if verify(op, pairs):
                    found.append({"op": op, "loo": True, "proposing": len(pairs),
                                  "simplicity": (1, pred_size(pred), (0, 0, "count"))})
                    break
    return found


def symfill_candidates(hole):
    found = []
    xs = [x for x, _ in hole]
    if any((len(x), len(x[0])) != (len(y), len(y[0])) for x, y in hole):
        return found
    cols = None
    for x, y in hole:
        d = {x[i][j] for i in range(len(x)) for j in range(len(x[0])) if x[i][j] != y[i][j]}
        if len(d) != 1:
            return found
        cols = d if cols is None else cols & d
    if not cols:
        return found
    c = next(iter(cols))
    for kind in ("h", "v", "r180", "d", "c"):
        op = ED.ObjOp({"form": "symfill", "params": {"colour": c, "kind": kind}})
        if all(op(x) == y for x, y in hole):
            found.append({"op": op, "loo": True, "proposing": len(hole),
                          "simplicity": (1, 0, (0, 0, "symfill"))})
    return found


# ------------------------------------------------------------------ the hole
def hole_candidates(hole, test_inputs=(), views=SC.VIEWS):
    """hole: [(input grid, target grid)]. Returns (candidates, correspondence record)."""
    ED.reset_counts()
    rec = {"views": {}, "correspondence": None, "correspondence_partial": None, "n_pairs": len(hole)}
    cands = []
    for view in views:
        pairs = [Pair(x, y, view) for x, y in hole]
        if any(p.s is None for p in pairs):
            rec["views"][view] = {"skipped": "over the object cap"}
            continue
        same = all(p.same for p in pairs)
        n_changed = sum(len(p.changed) for p in pairs)
        n_expl = sum(1 for p in pairs for i in p.changed if p.bound[i])
        n_app = sum(len(p.appeared) for p in pairs)
        n_unexpl = sum(len(p.unexplained) for p in pairs)
        full = same and all(p.explained_all for p in pairs) and (n_changed + n_app) > 0
        partial = same and (n_expl > 0 or n_app > n_unexpl)
        rec["views"][view] = {"same_shape": same, "changed_objects": n_changed, "explained_objects": n_expl,
                              "appeared_cells": n_app, "unexplained_cells": n_unexpl, "full": full,
                              "partial": partial, "objects": [len(p.s.objs) for p in pairs]}
        if full:
            rec["correspondence"] = rec["correspondence"] or view
        if partial:
            rec["correspondence_partial"] = rec["correspondence_partial"] or view
        preds = predicates([p.s for p in pairs])
        got = []
        if same and (n_changed > 0 or n_app > 0):
            why = {}
            got += paint_candidates(pairs, preds, why)
            rec["views"][view]["why"] = why
        got += whole_candidates(pairs, preds)
        for c in got:
            c["view"] = view
        cands += got
    cands += symfill_candidates(hole)
    # group by test predictions (agreeing candidates), largest group first, then simplest
    seen, uniq = set(), []
    for c in cands:
        if c["op"].sid not in seen:
            seen.add(c["op"].sid)
            uniq.append(c)
    groups = {}
    for c in uniq:
        key = tuple(c["op"](t) for t in test_inputs) if test_inputs else ()
        c["pred_key"] = key
        groups[key] = groups.get(key, 0) + 1
    for c in uniq:
        c["group"] = groups[c["pred_key"]] if c["pred_key"] and all(v is not None for v in c["pred_key"]) else 0
    uniq.sort(key=lambda c: (-c["group"], c["simplicity"]))
    rec["n_verified"] = len(uniq)
    rec["n_loo"] = sum(1 for c in uniq if c["loo"])
    rec["counts"] = dict(ED.COUNTS)
    return uniq[:MAX_CANDS], rec
