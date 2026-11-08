"""Per-object edits, whole-output forms, and the object-level operation (a Grid -> Grid production).

An EDIT maps one object o (with its scene and the current grid) to its WRITES, a set of (colour, cell) to paint, and
says whether o's own cells are VACATED (covered with the background) first. Every edit is a typed arc-dsl
expression over o (text in EDIT_EXPR); the implementation calls arc-dsl's object functions where they exist and
plain cell arithmetic otherwise. Edits (name, parameters):
    delete                       cover(I, o)
    recolor c                    recolor(c, o)                              c a colour 0..9
    recolor_attr a               recolor(a(o), o)                           a: adjacent | enclosing | enclosed |
                                                                            nearest | nearest_diff | largest |
                                                                            smallest | size | count | holes
    recolor_table k table        recolor(table[k(o)], o)                    k: size | colour | holes | size_rank |
                                                                            height | width | n_colours | shape;
                                                                            the table is learned from the hole
    shift (di, dj)               shift(o, (di, dj))                         |di|, |dj| at most 30
    move d stop                  move o in direction d (U D L R) until the border or until blocked by a
                                 non-background cell; moves are sequential, nearest to the target wall first
    gravitate which              shift(o, gravitate(o, target)): toward the nearest object (which: nearest |
                                 nearest_diff) until adjacent
    mirror k                     hmirror | vmirror | dmirror | cmirror of o in place
    rot k                        o rotated by k quarter turns in place (anchored at its upper-left corner)
    scale k                      upscale(o, k) anchored at its upper-left corner, k in {2, 3}
    extend d stop                o plus rays from its cells in direction d (U D L R, V = up and down, H = left
                                 and right, UL UR DL DR, X = the four diagonals, P = the four orthogonals) to the
                                 border, until blocked (the next cell is not background) or until near (the ray
                                 cell is 8-adjacent to another object's cell)
    fill_box c                   o plus the rest of its bounding box in colour c (c a colour or "self")
    connect which                o plus the straight line to the nearest object in the same row or column
    fill_holes c                 o plus its enclosed cells in colour c (c a colour or "self")
    hollow                       o minus its interior (cells whose in-grid 4-neighbours are all in o)
    outline c                    o plus its 8-adjacent background cells in colour c
    outbox c                     o plus the ring around its bounding box in colour c
    duplicate (di, dj)           o plus shift(o, (di, dj))
    mirror_copy k side           o plus its mirror image placed next to it (k: h | v; side: + | -)

A FORM says how an operation builds its output from the selected objects S of the input grid I under a view:
    paint      paint(cover(I, merge(S)) if any edit vacates else I, merge(writes of every selected object))
               (rules are a first-match list of (predicate, edit); an object takes the first rule whose predicate
               holds; two writes of different colours to one cell make the result undefined)
    crop       subgrid(o, I) for the single selected object o (undefined unless exactly one is selected)
    token      canvas(colour of the selected objects, (h, w))   (undefined unless they share one colour)
    count      canvas(c, (1, n)) or (n, 1), n = number of selected objects, c a colour or "self"
    symfill    whole-grid symmetry completion: every cell of colour c takes the value of its image under a
               symmetry k (h | v | d | c | r180); undefined if the image is out of range or also of colour c
The operation's specification is a JSON object (form, view, rules, params); its identifier (sid) is the canonical
text of that specification; its grammar head is "f:obj_" + the first 10 hex digits of the sid's sha256.
"""
import hashlib
import json

from objgrow import scene as SC
from a2 import arcdsl as D

DIRS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
EXT_DIRS = {"U": ((-1, 0),), "D": ((1, 0),), "L": ((0, -1),), "R": ((0, 1),), "V": ((-1, 0), (1, 0)),
            "H": ((0, -1), (0, 1)), "UL": ((-1, -1),), "UR": ((-1, 1),), "DL": ((1, -1),), "DR": ((1, 1),),
            "X": ((-1, -1), (-1, 1), (1, -1), (1, 1)), "P": ((-1, 0), (1, 0), (0, -1), (0, 1))}
STOPS = ("blocked", "border", "near")
VACATES = {"delete", "shift", "move", "gravitate", "mirror", "rot", "scale", "hollow"}
MAX_SHIFT = 30
COUNTS = {"segment": 0, "edit": 0, "op": 0}
SCENE_MEMO = {}
MEMO_CAP = 3000


def reset_counts():
    for k in COUNTS:
        COUNTS[k] = 0
    SCENE_MEMO.clear()


def scene_of(g, view):
    """Scene of a grid under a view, memoised (bounded; a segmentation is charged once per distinct grid)."""
    k = (g, view)
    if k not in SCENE_MEMO:
        if len(SCENE_MEMO) >= MEMO_CAP:
            SCENE_MEMO.clear()
        COUNTS["segment"] += 1
        SCENE_MEMO[k] = SC.Scene.of(g, view)
    return SCENE_MEMO[k]


# ------------------------------------------------------------------ attributes (colour-valued)
def attribute(a, o, s):
    f = o.f
    if a == "adjacent":
        return f["adj_colours"][0] if len(f["adj_colours"]) == 1 else None
    if a == "enclosing":
        return f["enclosing_colours"][0] if len(f["enclosing_colours"]) == 1 else None
    if a == "enclosed":
        return f["enc_colours"][0] if len(f["enc_colours"]) == 1 else None
    if a in ("nearest", "nearest_diff"):
        q = s.nearest(o, same_colour=None if a == "nearest" else False)
        return q.colour if q is not None else None
    if a in ("largest", "smallest"):
        m = [q for q in s.objs if q.f[a]]
        return m[0].colour if len(m) == 1 else None
    if a == "size":
        return o.size if 0 <= o.size <= 9 else None
    if a == "count":
        return len(s.objs) if len(s.objs) <= 9 else None
    if a == "holes":
        return f["holes"] if f["holes"] <= 9 else None
    raise ValueError(a)


ATTRS = ("adjacent", "enclosing", "enclosed", "nearest", "nearest_diff", "largest", "smallest", "size", "count",
         "holes")
TABLE_KEYS = ("size", "colour", "holes", "size_rank", "height", "width", "n_colours", "shape")


def table_key(attr, o):
    """The value of an object attribute used as a colour-table key (shape: the normalised cell set, as text)."""
    if attr == "shape":
        return "shape:" + ",".join(f"{i}.{j}" for i, j in sorted(o.shape))
    return o.f[attr]


# ------------------------------------------------------------------ geometry helpers
def free(grid, p, own, bg):
    i, j = p
    return 0 <= i < len(grid) and 0 <= j < len(grid[0]) and (p in own or grid[i][j] == bg)


def move_vector(o, grid, bg, d, stop):
    """Shift of o in direction d: to the border (ignoring obstacles) or until blocked by a non-background cell."""
    di, dj = DIRS[d]
    H, W = len(grid), len(grid[0])
    if stop == "border":
        if d == "U":
            return (-o.box[0], 0)
        if d == "D":
            return (H - 1 - o.box[2], 0)
        if d == "L":
            return (0, -o.box[1])
        return (0, W - 1 - o.box[3])
    k = 0
    while k < max(H, W):
        nxt = [(i + di * (k + 1), j + dj * (k + 1)) for i, j in o.cells]
        if not all(free(grid, p, o.cells, bg) for p in nxt):
            break
        k += 1
    return (di * k, dj * k)


def gravitate_vector(o, target):
    """arc-dsl gravitate: the shift that brings o adjacent to target along the axis they share (None if none)."""
    dsl = SC.dsl()
    try:
        v = dsl["gravitate"](o.obj, target.obj)
    except Exception:                                            # noqa: BLE001
        return None
    return v


def inplace(o, k):
    """Mirror or rotate o inside its bounding box (anchored at its upper-left corner)."""
    i0, j0, h, w = o.box[0], o.box[1], o.h, o.w
    out = set()
    for v, (i, j) in o.norm:
        if k == "h":
            a, b = h - 1 - i, j
        elif k == "v":
            a, b = i, w - 1 - j
        elif k == "d":
            a, b = j, i
        elif k == "c":
            a, b = w - 1 - j, h - 1 - i
        elif k == 1:
            a, b = j, h - 1 - i
        elif k == 2:
            a, b = h - 1 - i, w - 1 - j
        elif k == 3:
            a, b = w - 1 - j, i
        else:
            raise ValueError(k)
        out.add((v, (i0 + a, j0 + b)))
    return frozenset(out)


def rays(o, grid, bg, d, stop):
    """Ray cells from every cell of o in direction d: to the border, until blocked (the next cell is not
    background), or until near (the cell is 8-adjacent to a non-background cell outside o; that cell is kept)."""
    H, W = len(grid), len(grid[0])
    out = set()
    for di, dj in EXT_DIRS[d]:
        for v, (i, j) in o.obj:
            a, b = i + di, j + dj
            while 0 <= a < H and 0 <= b < W:
                if (a, b) in o.cells:
                    a, b = a + di, b + dj
                    continue
                if stop != "border" and grid[a][b] != bg:
                    break
                out.add((v, (a, b)))
                if stop == "near" and any(0 <= a + p < H and 0 <= b + q < W and (a + p, b + q) not in o.cells
                                          and grid[a + p][b + q] != bg for p in (-1, 0, 1) for q in (-1, 0, 1)):
                    break
                a, b = a + di, b + dj
    return frozenset(out)


def line_to(o, q):
    """Cells strictly between o and q when they share a row or column (the nearest such cells); else None."""
    best = None
    for i, j in o.cells:
        for a, b in q.cells:
            if i == a and j != b:
                lo, hi = min(j, b), max(j, b)
                cells = [(i, c) for c in range(lo + 1, hi)]
            elif j == b and i != a:
                lo, hi = min(i, a), max(i, a)
                cells = [(r, j) for r in range(lo + 1, hi)]
            else:
                continue
            if best is None or len(cells) < len(best):
                best = cells
    return best


def interior(o, H, W):
    out = set()
    for i, j in o.cells:
        nbs = [(i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)]
        if all(q in o.cells for q in nbs if 0 <= q[0] < H and 0 <= q[1] < W):
            out.add((i, j))
    return frozenset(out)


def ring8(o, H, W):
    out = set()
    for i, j in o.cells:
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                q = (i + di, j + dj)
                if q not in o.cells and 0 <= q[0] < H and 0 <= q[1] < W:
                    out.add(q)
    return frozenset(out)


def outbox_ring(o, H, W):
    i0, j0, i1, j1 = o.box
    out = set()
    for i in range(i0 - 1, i1 + 2):
        for j in (j0 - 1, j1 + 1):
            if 0 <= i < H and 0 <= j < W:
                out.add((i, j))
    for j in range(j0 - 1, j1 + 2):
        for i in (i0 - 1, i1 + 1):
            if 0 <= i < H and 0 <= j < W:
                out.add((i, j))
    return frozenset(out)


def shifted(o, v):
    di, dj = v
    return frozenset((c, (i + di, j + dj)) for c, (i, j) in o.obj)


# ------------------------------------------------------------------ edits
def apply_edit(e, o, s, grid):
    """Writes of edit e on object o (scene s of the INPUT grid; `grid` is the current grid for sequential moves),
    or None when undefined."""
    COUNTS["edit"] += 1
    k = e[0]
    bg = s.bg
    H, W = len(grid), len(grid[0])
    if k == "delete":
        return frozenset()
    if k == "recolor":
        return frozenset((e[1], p) for p in o.cells)
    if k == "recolor_attr":
        c = attribute(e[1], o, s)
        return None if c is None else frozenset((c, p) for p in o.cells)
    if k == "recolor_table":
        c = dict(e[2]).get(table_key(e[1], o))
        return None if c is None else frozenset((c, p) for p in o.cells)
    if k == "shift":
        return shifted(o, (e[1], e[2]))
    if k == "move":
        return shifted(o, move_vector(o, grid, bg, e[1], e[2]))
    if k == "gravitate":
        q = s.nearest(o, same_colour=None if e[1] == "nearest" else False)
        if q is None:
            return None
        v = gravitate_vector(o, q)
        return None if v is None else shifted(o, v)
    if k == "mirror":
        return inplace(o, e[1])
    if k == "rot":
        return inplace(o, e[1])
    if k == "scale":
        f = e[1]
        i0, j0 = o.box[0], o.box[1]
        if o.h * f > 30 or o.w * f > 30:
            return None
        return frozenset((v, (i0 + i * f + a, j0 + j * f + b)) for v, (i, j) in o.norm for a in range(f)
                         for b in range(f))
    if k == "extend":
        return o.obj | rays(o, grid, bg, e[1], e[2])
    if k == "connect":
        q = s.nearest(o, same_colour=True if e[1] == "same" else None)
        if q is None:
            return None
        cells = line_to(o, q)
        if cells is None:
            return None
        return o.obj | frozenset((o.colour, p) for p in cells)
    if k == "fill_holes":
        c = o.colour if e[1] == "self" else e[1]
        return o.obj | frozenset((c, p) for p in o.enclosed_cells)
    if k == "fill_box":
        c = o.colour if e[1] == "self" else e[1]
        i0, j0, i1, j1 = o.box
        return o.obj | frozenset((c, (i, j)) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)
                                 if (i, j) not in o.cells)
    if k == "hollow":
        inner = interior(o, H, W)
        return frozenset((v, p) for v, p in o.obj if p not in inner)
    if k == "outline":
        return o.obj | frozenset((e[1], p) for p in ring8(o, H, W) if grid[p[0]][p[1]] == bg)
    if k == "outbox":
        return o.obj | frozenset((e[1], p) for p in outbox_ring(o, H, W))
    if k == "duplicate":
        return o.obj | shifted(o, (e[1], e[2]))
    if k == "mirror_copy":
        m = inplace(o, e[1])
        if e[1] == "h":
            v = (o.h, 0) if e[2] == "+" else (-o.h, 0)
        else:
            v = (0, o.w) if e[2] == "+" else (0, -o.w)
        return o.obj | frozenset((c, (i + v[0], j + v[1])) for c, (i, j) in m)
    raise ValueError(e)


def edit_vacates(e):
    return e[0] in VACATES


def edit_expr(e):
    k = e[0]
    if k == "delete":
        return "cover(I, o)"
    if k == "recolor":
        return f"recolor({e[1]}, o)"
    if k == "recolor_attr":
        return f"recolor({e[1]}_colour(o), o)"
    if k == "recolor_table":
        tbl = ", ".join(f"{a}: {c}" for a, c in e[2])
        return f"recolor(table[{e[1]}(o)], o) with table {{{tbl}}}"
    if k == "shift":
        return f"shift(o, ({e[1]}, {e[2]}))"
    if k == "move":
        return f"move_{e[1]}_{'to_border' if e[2] == 'border' else 'until_blocked'}(o)"
    if k == "gravitate":
        return f"shift(o, gravitate(o, {e[1]}_object(o)))"
    if k == "mirror":
        return {"h": "hmirror(o)", "v": "vmirror(o)", "d": "dmirror(o)", "c": "cmirror(o)"}[e[1]]
    if k == "rot":
        return f"rot{90 * e[1]}_in_place(o)"
    if k == "scale":
        return f"upscale(o, {e[1]})"
    if k == "extend":
        return f"combine(o, rays_{e[1]}_{'to_border' if e[2] == 'border' else 'until_blocked'}(o))"
    if k == "connect":
        return f"combine(o, connect(o, nearest_{e[1]}_object(o)))"
    if k == "fill_holes":
        return f"combine(o, recolor({'color(o)' if e[1] == 'self' else e[1]}, enclosed(o)))"
    if k == "fill_box":
        return f"combine(o, recolor({'color(o)' if e[1] == 'self' else e[1]}, delta(o)))"
    if k == "hollow":
        return "difference(o, interior(o))"
    if k == "outline":
        return f"combine(o, recolor({e[1]}, outline(o)))"
    if k == "outbox":
        return f"combine(o, recolor({e[1]}, outbox(o)))"
    if k == "duplicate":
        return f"combine(o, shift(o, ({e[1]}, {e[2]})))"
    if k == "mirror_copy":
        return f"combine(o, {'hmirror' if e[1] == 'h' else 'vmirror'}_copy_{e[2]}(o))"
    raise ValueError(e)


# ------------------------------------------------------------------ the operation
def _tuple_spec(x):
    """JSON-loaded specification parts back to hashable tuples (atoms and edits are tuples)."""
    if isinstance(x, list):
        return tuple(_tuple_spec(v) for v in x)
    return x


def canonical(spec):
    return json.dumps(spec, sort_keys=True, separators=(",", ":"), default=list)


class ObjOp:
    """One object-level operation: Grid -> Grid, built from its specification."""

    def __init__(self, spec):
        self.spec = {"form": spec["form"], "view": spec.get("view"), "rules": [[_tuple_spec(a), _tuple_spec(e)]
                                                                               for a, e in spec.get("rules", [])],
                     "params": dict(spec.get("params", {}))}
        self.sid = "OBJ:" + canonical(self.spec)
        self.head = "f:obj_" + hashlib.sha256(self.sid.encode()).hexdigest()[:10]
        self.param = False
        self.family = "OBJ"

    def thetas(self):
        return [()]

    def to_json(self):
        return {"sid": self.sid, "head": self.head, "spec": self.spec, "expr": self.expr()}

    @classmethod
    def from_json(cls, d):
        return cls(d["spec"])

    def expr(self):
        sp = self.spec
        f = sp["form"]
        if f == "symfill":
            return f"symmetry_completion(I, colour={sp['params']['colour']}, symmetry={sp['params']['kind']})"
        S = SC.VIEW_EXPR[sp["view"]]
        rules = sp["rules"]
        if f == "paint":
            parts = [f"{SC.atom_text(a)} -> {edit_expr(e)}" for a, e in rules]
            base = "cover(I, merge(S))" if any(edit_vacates(e) for _, e in rules) else "I"
            return f"S = {S}; paint({base}, merge(first-match rules [{'; '.join(parts)}] over S))"
        sel = f"sfilter({S}, {SC.atom_text(rules[0][0])})"
        if f == "crop":
            return f"subgrid(first({sel}), I)"
        if f == "token":
            return f"canvas(color(first({sel})), {tuple(sp['params']['shape'])})"
        if f == "count":
            c = sp["params"]["colour"]
            return f"canvas({'color(first(sel))' if c == 'self' else c}, {sp['params']['orient']}(size({sel})))"
        raise ValueError(f)

    def select(self, s):
        """[(object, edit)] under the first-match rules, in scene order."""
        out = []
        for o in s.objs:
            for a, e in self.spec["rules"]:
                if SC.holds(o, a):
                    out.append((o, e))
                    break
        return out

    def __call__(self, g):
        COUNTS["op"] += 1
        try:
            return self.run(g)
        except (IndexError, KeyError, ValueError, TypeError, ZeroDivisionError):
            return None

    def run(self, g):
        sp = self.spec
        f = sp["form"]
        if f == "symfill":
            return symfill(g, sp["params"]["colour"], sp["params"]["kind"])
        s = scene_of(g, sp["view"])
        if s is None:
            return None
        chosen = self.select(s)
        if f == "paint":
            return paint_form(g, s, chosen)
        if f == "crop":
            if len(chosen) != 1:
                return None
            o = chosen[0][0]
            i0, j0, i1, j1 = o.box
            return tuple(tuple(g[i][j0:j1 + 1]) for i in range(i0, i1 + 1))
        if f == "token":
            cols = {o.colour for o, _ in chosen}
            if len(cols) != 1:
                return None
            h, w = sp["params"]["shape"]
            c = cols.pop()
            return tuple(tuple(c for _ in range(w)) for _ in range(h))
        if f == "count":
            n = len(chosen)
            if n == 0 or n > 30:
                return None
            c = sp["params"]["colour"]
            if c == "self":
                cols = {o.colour for o, _ in chosen}
                if len(cols) != 1:
                    return None
                c = cols.pop()
            if sp["params"]["orient"] == "row":
                return (tuple(c for _ in range(n)),)
            return tuple((c,) for _ in range(n))
        raise ValueError(f)


def paint_form(g, s, chosen):
    H, W, bg = s.H, s.W, s.bg
    out = [list(r) for r in g]
    vac = [o for o, e in chosen if edit_vacates(e)]
    for o in vac:
        for i, j in o.cells:
            out[i][j] = bg
    cur = tuple(tuple(r) for r in out)
    writes = {}
    # moves are sequential (nearest to the target wall first); every other edit reads the input scene
    moves = [(o, e) for o, e in chosen if e[0] in ("move", "gravitate")]
    others = [(o, e) for o, e in chosen if e[0] not in ("move", "gravitate")]
    for o, e in others:
        w = apply_edit(e, o, s, g)
        if w is None:
            return None
        for v, p in w:
            if 0 <= p[0] < H and 0 <= p[1] < W:
                if writes.get(p, v) != v:
                    return None
                writes[p] = v
    for p, v in writes.items():
        out[p[0]][p[1]] = v
    if moves:
        def order(oe):
            o, e = oe
            if e[0] == "move":
                return {"U": o.box[0], "D": -o.box[2], "L": o.box[1], "R": -o.box[3]}[e[1]]
            return 0
        for o, e in sorted(moves, key=order):
            cur = tuple(tuple(r) for r in out)
            w = apply_edit(e, o, s, cur)
            if w is None:
                return None
            for v, p in w:
                if 0 <= p[0] < H and 0 <= p[1] < W:
                    out[p[0]][p[1]] = v
    return tuple(tuple(r) for r in out)


def symfill(g, c, kind):
    H, W = len(g), len(g[0])
    out = [list(r) for r in g]
    for i in range(H):
        for j in range(W):
            if g[i][j] != c:
                continue
            if kind == "h":
                a, b = H - 1 - i, j
            elif kind == "v":
                a, b = i, W - 1 - j
            elif kind == "r180":
                a, b = H - 1 - i, W - 1 - j
            elif kind == "d":
                a, b = j, i
            elif kind == "c":
                a, b = W - 1 - j, H - 1 - i
            else:
                raise ValueError(kind)
            if not (0 <= a < H and 0 <= b < W) or g[a][b] == c:
                return None
            out[i][j] = g[a][b]
    return tuple(tuple(r) for r in out)


def production_fn(op):
    """The grammar production for an operation: (Grid) -> Grid, raising D.Bad when undefined (as structure_fn)."""
    def f(grid):
        if D.tag(grid) != "G":
            raise D.Bad("type")
        out = op(grid)
        if out is None or not D.valid(out) or D.tag(out) != "G":
            raise D.Bad("undefined")
        return out
    return f
