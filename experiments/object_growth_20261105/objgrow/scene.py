"""Scenes: a grid segmented into objects under a declared view, with object features, relations and selection
predicates.

View (segmentation rule), each a typed arc-dsl expression over the input grid I:
    m4    objects(I, T, F, T)   one-colour, 4-connected, background excluded
    m8    objects(I, T, T, T)   one-colour, 8-connected
    x8    objects(I, F, T, T)   any-colour, 8-connected
    x4    objects(I, F, F, T)   any-colour, 4-connected
    col   fgpartition(I)         every non-background colour is one object, wherever its cells are
    cell  every non-background cell is its own object
    m4z, m8z, x8z, x4z, colz, cellz   the same six with the background fixed to colour 0 when the grid has it
Background = the grid's most common colour (arc-dsl's mostcolor, as in objects(..., without_bg=T)), or colour 0
for the z views (ARC's usual background; the most common colour is the object itself when an object is large).
An object is an arc-dsl object: a frozenset of (colour, (row, column)).

Features of an object o in a scene (all computed from the input grid; plain names, used by the selection
predicates): colour (its most common colour, ties to the smallest), size (cells), height, width, n_colours,
single (one cell), hline, vline, square (height equals width), border (touches the grid border), holes (count of
enclosed background regions; an enclosed region is a 4-connected component of the cells outside o that does not
reach the grid border when every other object is ignored), largest, smallest, size_unique, shape_unique (its
normalised shape occurs once), colour_unique (no other object has its colour), colour_mostcommon,
colour_leastcommon (among the scene's objects), adjacent colours (8-adjacent objects), enclosing (o lies in another
object's enclosed region), encloses (another object lies in o's enclosed region), topmost, bottommost, leftmost,
rightmost (extreme bounding box edge; several objects may tie), size_rank (0 = largest), surround4 and surround8
(the cells 4- or 8-adjacent to o, background included, all have one colour), filled (o fills its bounding box),
size_odd.

Selection predicates are atoms over these features, their negations, and conjunctions of two atoms.
"""
from cgrow import paths as _P                       # noqa: F401  (import paths)
from a2 import arcdsl as D

VIEWS = ("m4", "m8", "x8", "x4", "col", "cell", "m4z", "m8z", "x8z", "x4z", "colz", "cellz")
VIEW_ARGS = {"m4": (True, False), "m8": (True, True), "x8": (False, True), "x4": (False, False)}
VIEW_EXPR = {"m4": "objects(I, T, F, T)", "m8": "objects(I, T, T, T)", "x8": "objects(I, F, T, T)",
             "x4": "objects(I, F, F, T)", "col": "fgpartition(I)", "cell": "cells(I)",
             "m4z": "objects_bg0(I, T, F)", "m8z": "objects_bg0(I, T, T)", "x8z": "objects_bg0(I, F, T)",
             "x4z": "objects_bg0(I, F, F)", "colz": "fgpartition_bg0(I)", "cellz": "cells_bg0(I)"}
MAX_OBJS = 150
_DSL = {}


def dsl():
    if not _DSL:
        _DSL["d"] = D.load()[0]
    return _DSL["d"]


def bg_of(g):
    cnt = [0] * 10
    for r in g:
        for v in r:
            cnt[v] += 1
    return max(range(10), key=lambda c: (cnt[c], -c))


def view_bg(g, view):
    """The background of a view: the most common colour, or (views ending in z) colour 0 when the grid has it."""
    if view.endswith("z") and any(v == 0 for r in g for v in r):
        return 0
    return bg_of(g)


def segment_bg(g, bg, univalued, diagonal):
    """arc-dsl's objects(g, univalued, diagonal, without_bg=True) with the background given (same traversal)."""
    H, W = len(g), len(g[0])
    occupied = set()
    objs = set()
    for i0 in range(H):
        for j0 in range(W):
            if (i0, j0) in occupied or g[i0][j0] == bg:
                continue
            val = g[i0][j0]
            obj = set()
            stack = [(i0, j0)]
            occupied.add((i0, j0))
            while stack:
                i, j = stack.pop()
                v = g[i][j]
                obj.add((v, (i, j)))
                nbs = [(i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)]
                if diagonal:
                    nbs += [(i - 1, j - 1), (i - 1, j + 1), (i + 1, j - 1), (i + 1, j + 1)]
                for a, b in nbs:
                    if 0 <= a < H and 0 <= b < W and (a, b) not in occupied:
                        w = g[a][b]
                        if (w == val) if univalued else (w != bg):
                            occupied.add((a, b))
                            stack.append((a, b))
            objs.add(frozenset(obj))
    return frozenset(objs)


def segment(g, view):
    """arc-dsl objects of g under the view (frozenset of frozensets of (colour, (i, j))); None when over the cap."""
    bg = view_bg(g, view)
    base = view[:-1] if view.endswith("z") else view
    if base == "cell":
        objs = frozenset(frozenset({(v, (i, j))}) for i, r in enumerate(g) for j, v in enumerate(r) if v != bg)
    elif base == "col":
        cols = {v for r in g for v in r if v != bg}
        objs = frozenset(frozenset((v, (i, j)) for i, r in enumerate(g) for j, v in enumerate(r) if v == c)
                         for c in cols)
    elif view.endswith("z"):
        objs = segment_bg(g, bg, *VIEW_ARGS[base])
    else:
        u, d = VIEW_ARGS[base]
        objs = dsl()["objects"](g, u, d, True)
    if len(objs) > MAX_OBJS:
        return None
    return objs


class Obj:
    __slots__ = ("obj", "cells", "colour", "colours", "size", "box", "h", "w", "shape", "norm", "idx", "f",
                 "enclosed_cells")

    def __init__(self, obj, idx=0):
        self.obj = obj
        self.cells = frozenset(p for _, p in obj)
        cnt = {}
        for v, _ in obj:
            cnt[v] = cnt.get(v, 0) + 1
        self.colours = frozenset(cnt)
        self.colour = max(cnt, key=lambda c: (cnt[c], -c))
        self.size = len(obj)
        i0 = min(i for i, _ in self.cells)
        j0 = min(j for _, j in self.cells)
        i1 = max(i for i, _ in self.cells)
        j1 = max(j for _, j in self.cells)
        self.box = (i0, j0, i1, j1)
        self.h, self.w = i1 - i0 + 1, j1 - j0 + 1
        self.shape = frozenset((i - i0, j - j0) for i, j in self.cells)
        self.norm = frozenset((v, (i - i0, j - j0)) for v, (i, j) in obj)
        self.idx = idx
        self.f = {}
        self.enclosed_cells = frozenset()

    def key(self):
        return (self.box[0], self.box[1], -self.size, self.colour, self.box[2], self.box[3])


def enclosed(cells, H, W):
    """Cells outside `cells` not reachable from the grid border by 4-steps outside `cells` (every other object is
    ignored, so this is the object's own enclosed region)."""
    i0 = min(i for i, _ in cells)
    j0 = min(j for _, j in cells)
    i1 = max(i for i, _ in cells)
    j1 = max(j for _, j in cells)
    if i1 - i0 < 2 or j1 - j0 < 2:
        return frozenset()
    # flood inside the bounding box; the ring just outside the box is free, so start from every box edge cell
    seen = set()
    stack = [(i, j) for i in range(i0, i1 + 1) for j in (j0, j1) if (i, j) not in cells]
    stack += [(i, j) for j in range(j0, j1 + 1) for i in (i0, i1) if (i, j) not in cells]
    for p in stack:
        seen.add(p)
    while stack:
        i, j = stack.pop()
        for q in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if i0 <= q[0] <= i1 and j0 <= q[1] <= j1 and q not in cells and q not in seen:
                seen.add(q)
                stack.append(q)
    return frozenset((i, j) for i in range(i0 + 1, i1) for j in range(j0 + 1, j1)
                     if (i, j) not in cells and (i, j) not in seen)


def components4(cells):
    cells = set(cells)
    n = 0
    while cells:
        n += 1
        stack = [cells.pop()]
        while stack:
            i, j = stack.pop()
            for q in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if q in cells:
                    cells.remove(q)
                    stack.append(q)
    return n


class Scene:
    """A grid under one view: objects with features and relations; None-safe through `Scene.of`."""

    def __init__(self, g, view, objs):
        self.g, self.view = g, view
        self.H, self.W = len(g), len(g[0])
        self.bg = view_bg(g, view)
        self.objs = sorted((Obj(o) for o in objs), key=Obj.key)
        for k, o in enumerate(self.objs):
            o.idx = k
        self.owner = {}
        for o in self.objs:
            for p in o.cells:
                self.owner[p] = o.idx
        self._features()

    @classmethod
    def of(cls, g, view):
        objs = segment(g, view)
        return None if objs is None else cls(g, view, objs)

    def _features(self):
        objs, H, W = self.objs, self.H, self.W
        if not objs:
            return
        sizes = [o.size for o in objs]
        shapes = [o.shape for o in objs]
        cols = [o.colour for o in objs]
        ccount = {c: cols.count(c) for c in set(cols)}
        most = max(ccount, key=lambda c: (ccount[c], -c))
        least = min(ccount, key=lambda c: (ccount[c], c))
        smax, smin = max(sizes), min(sizes)
        top = min(o.box[0] for o in objs)
        bottom = max(o.box[2] for o in objs)
        left = min(o.box[1] for o in objs)
        right = max(o.box[3] for o in objs)
        ranks = sorted(set(sizes), reverse=True)
        for o in objs:
            if o.size >= 4 and o.h >= 3 and o.w >= 3:
                o.enclosed_cells = enclosed(o.cells, H, W)
            f = o.f
            f["colour"], f["size"], f["height"], f["width"] = o.colour, o.size, o.h, o.w
            f["n_colours"] = len(o.colours)
            f["single"] = o.size == 1
            f["hline"] = o.h == 1 and o.w > 1
            f["vline"] = o.w == 1 and o.h > 1
            f["square"] = o.h == o.w
            f["border"] = o.box[0] == 0 or o.box[1] == 0 or o.box[2] == H - 1 or o.box[3] == W - 1
            f["holes"] = components4(o.enclosed_cells) if o.enclosed_cells else 0
            f["has_hole"] = f["holes"] > 0
            f["largest"] = o.size == smax
            f["smallest"] = o.size == smin
            f["size_unique"] = sizes.count(o.size) == 1
            f["shape_unique"] = shapes.count(o.shape) == 1
            f["colour_unique"] = ccount[o.colour] == 1
            f["colour_mostcommon"] = o.colour == most
            f["colour_leastcommon"] = o.colour == least
            f["topmost"] = o.box[0] == top
            f["bottommost"] = o.box[2] == bottom
            f["leftmost"] = o.box[1] == left
            f["rightmost"] = o.box[3] == right
            f["size_rank"] = ranks.index(o.size)
            f["filled"] = o.size == o.h * o.w
            f["size_odd"] = o.size % 2 == 1
        # relations: 8-adjacency, enclosure, the colours around the object (raw cells, background included)
        g = self.g
        for o in objs:
            nb = set()
            around4, around8 = set(), set()
            for i, j in o.cells:
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        q = (i + di, j + dj)
                        k = self.owner.get(q)
                        if k is not None and k != o.idx:
                            nb.add(k)
                        if q not in o.cells and 0 <= q[0] < H and 0 <= q[1] < W:
                            around8.add(g[q[0]][q[1]])
                            if di == 0 or dj == 0:
                                around4.add(g[q[0]][q[1]])
            o.f["surround4"] = len(around4) == 1
            o.f["surround8"] = len(around8) == 1
            o.f["adj_ids"] = sorted(nb)
            o.f["adj_colours"] = sorted({objs[k].colour for k in nb})
            o.f["adj_any"] = bool(nb)
            inner = set()
            if o.enclosed_cells:
                for p in o.enclosed_cells:
                    k = self.owner.get(p)
                    if k is not None and k != o.idx:
                        inner.add(k)
            o.f["enc_ids"] = sorted(inner)
            o.f["enc_colours"] = sorted({objs[k].colour for k in inner})
            o.f["encloses"] = bool(inner)
        for o in objs:
            o.f["enclosed_by"] = sorted(k for k in range(len(objs)) if o.idx in objs[k].f["enc_ids"])
            o.f["enclosed"] = bool(o.f["enclosed_by"])
            o.f["enclosing_colours"] = sorted({objs[k].colour for k in o.f["enclosed_by"]})

    def nearest(self, o, same_colour=None):
        """The nearest other object by Manhattan distance between cells (ties to the lower index); None if none."""
        best, bd = None, None
        for q in self.objs:
            if q.idx == o.idx or (same_colour is True and q.colour != o.colour) or \
                    (same_colour is False and q.colour == o.colour):
                continue
            d = min(abs(i - a) + abs(j - b) for i, j in o.cells for a, b in q.cells) if o.size * q.size <= 4000 \
                else abs(o.box[0] - q.box[0]) + abs(o.box[1] - q.box[1])
            if bd is None or d < bd:
                best, bd = q, d
        return best


# ------------------------------------------------------------------ selection predicates
BOOL_ATOMS = ("single", "hline", "vline", "square", "border", "has_hole", "largest", "smallest", "size_unique",
              "shape_unique", "colour_unique", "colour_mostcommon", "colour_leastcommon", "topmost", "bottommost",
              "leftmost", "rightmost", "adj_any", "encloses", "enclosed", "filled", "surround4", "surround8",
              "size_odd")
VALUE_ATOMS = ("colour", "size", "height", "width", "n_colours", "holes", "size_rank")
REL_ATOMS = ("adj_colour", "enc_colour", "enclosing_colour")


def holds(o, atom):
    k = atom[0]
    f = o.f
    if k == "true":
        return True
    if k == "not":
        return not holds(o, atom[1])
    if k == "and":
        return holds(o, atom[1]) and holds(o, atom[2])
    if k in BOOL_ATOMS:
        return bool(f[k])
    if k in VALUE_ATOMS:
        return f[k] == atom[1]
    if k == "size_ge":
        return f["size"] >= atom[1]
    if k == "adj_colour":
        return atom[1] in f["adj_colours"]
    if k == "enc_colour":
        return atom[1] in f["enc_colours"]
    if k == "enclosing_colour":
        return atom[1] in f["enclosing_colours"]
    raise ValueError(atom)


def atom_space(scenes):
    """Finite atoms from the demonstration scenes (values seen there only), in a fixed order."""
    out = [("true",)]
    objs = [o for s in scenes for o in s.objs]
    for k in BOOL_ATOMS:
        out.append((k,))
    for k in VALUE_ATOMS:
        vals = sorted({o.f[k] for o in objs})
        if k == "size":
            vals = vals[:12]
        out += [(k, v) for v in vals]
    for v in sorted({o.f["size"] for o in objs})[:12]:
        if v > 1:
            out.append(("size_ge", v))
    for k, key in (("adj_colour", "adj_colours"), ("enc_colour", "enc_colours"),
                   ("enclosing_colour", "enclosing_colours")):
        out += [(k, c) for c in sorted({c for o in objs for c in o.f[key]})]
    return out


def atom_text(a):
    k = a[0]
    if k == "true":
        return "all objects"
    if k == "not":
        return "not (" + atom_text(a[1]) + ")"
    if k == "and":
        return atom_text(a[1]) + " and " + atom_text(a[2])
    if len(a) == 1:
        return k.replace("_", " ")
    return f"{k.replace('_', ' ')} = {a[1]}"
