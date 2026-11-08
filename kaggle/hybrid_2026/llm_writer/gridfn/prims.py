"""The fixed primitive library of the grid-function language (gridfn-1): pure Python on lists, no imports.

Conventions. A grid is a list of rows, each row a list of ints; g[r][c] is row r, column c, counted from the top-left
cell (0, 0). Primitives never change their arguments: every grid or list they return is new. An object is a list of
(row, col) cells in reading order (row by row, left to right). A direction is a (dr, dc) pair (UP = (-1, 0), ...)
or one of the names "up", "down", "left", "right", "up_left", "up_right", "down_left", "down_right". Arguments are
checked; a bad argument raises PrimError, which the interpreter reports as a RuntimeFault naming the primitive.

Every primitive is registered with its signature, a one-line meaning (the language card is generated from these),
its card section, whether it maps a grid (first argument) to a grid (used by ablations: "replace the call by its
input"), and its cost weight in interpreter steps per cell of its arguments and result.

Intermediate grids may be larger than the 30 x 30 output limit, up to MAX_DIM x MAX_DIM, and may hold any int; only
the final output must be 1..30 x 1..30 with colours 0..9.
"""

MAX_DIM = 100                      # largest side of any grid a primitive accepts or makes
MAX_CELLS = 40000                  # largest cell list a primitive accepts


class PrimError(Exception):
    """A bad argument or an impossible request; the message names the problem."""


class Prim:
    __slots__ = ("name", "fn", "sig", "doc", "section", "grid_op", "weight", "cost")

    def __init__(self, name, fn, sig, doc, section, grid_op, weight, cost):
        self.name, self.fn, self.sig, self.doc = name, fn, sig, doc
        self.section, self.grid_op, self.weight, self.cost = section, grid_op, weight, cost


REGISTRY = {}                      # name -> Prim, in card order
SECTIONS = ("grid", "transform", "colour", "object", "draw", "pattern", "motion")


def prim(sig, doc, section, grid_op=False, weight=1, cost=None):
    """Register a primitive. Its interpreter cost is BASE_STEPS + weight * (cells of its arguments and result) / 4
    steps, or `cost(args, kw)` extra steps for the few whose work grows faster than their arguments; weights are
    calibrated so that a step costs about as much CPU time as an interpreted step (about 0.2 microseconds)."""
    def deco(fn):
        REGISTRY[fn.__name__] = Prim(fn.__name__, fn, sig, doc, section, grid_op, weight, cost)
        return fn
    return deco


BASE_STEPS = 20


def _dims(g):
    try:
        return len(g), len(g[0])
    except (TypeError, IndexError, KeyError):
        return 1, 1


# ------------------------------------------------------------------ constants
UP, DOWN, LEFT, RIGHT = (-1, 0), (1, 0), (0, -1), (0, 1)
UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT = (-1, -1), (-1, 1), (1, -1), (1, 1)
DIRS4 = (UP, DOWN, LEFT, RIGHT)
DIRS8 = (UP, DOWN, LEFT, RIGHT, UP_LEFT, UP_RIGHT, DOWN_LEFT, DOWN_RIGHT)
CONSTANTS = {"UP": UP, "DOWN": DOWN, "LEFT": LEFT, "RIGHT": RIGHT, "UP_LEFT": UP_LEFT, "UP_RIGHT": UP_RIGHT,
             "DOWN_LEFT": DOWN_LEFT, "DOWN_RIGHT": DOWN_RIGHT, "DIRS4": DIRS4, "DIRS8": DIRS8}
DIR_NAMES = {"up": UP, "down": DOWN, "left": LEFT, "right": RIGHT, "up_left": UP_LEFT, "up_right": UP_RIGHT,
             "down_left": DOWN_LEFT, "down_right": DOWN_RIGHT}
N4 = DIRS4
N8 = DIRS8


# ------------------------------------------------------------------ argument checks
def _int(x, what):
    t = type(x)
    if t is int:
        return x
    if t is bool:
        return int(x)
    raise PrimError(f"{what} must be an int, got {_tname(x)}")


def _tname(x):
    return {list: "list", tuple: "tuple", int: "int", bool: "bool", float: "float", str: "string", dict: "dict",
            set: "set", type(None): "None"}.get(type(x), "value")


def _grid(g, what="grid"):
    """(height, width) of a valid grid argument, else PrimError."""
    if type(g) not in (list, tuple) or not g:
        raise PrimError(f"{what} must be a non-empty list of rows, got {_tname(g)}")
    if len(g) > MAX_DIM:
        raise PrimError(f"{what} has {len(g)} rows (at most {MAX_DIM})")
    w = None
    for row in g:
        if type(row) not in (list, tuple) or not row:
            raise PrimError(f"{what} must be a list of non-empty rows")
        if w is None:
            w = len(row)
            if w > MAX_DIM:
                raise PrimError(f"{what} has {w} columns (at most {MAX_DIM})")
        elif len(row) != w:
            raise PrimError(f"{what} is not rectangular (rows of length {w} and {len(row)})")
        for v in row:
            if type(v) is not int:
                if type(v) is bool:
                    continue
                raise PrimError(f"{what} cells must be ints, found {_tname(v)}")
    return len(g), w


def _cells(x, what="cells"):
    """A list of (row, col) int pairs (any order, duplicates kept) from a list, tuple or set of pairs."""
    if type(x) not in (list, tuple, set, frozenset):
        raise PrimError(f"{what} must be a list of (row, col) cells, got {_tname(x)}")
    if len(x) > MAX_CELLS:
        raise PrimError(f"{what} has {len(x)} cells (at most {MAX_CELLS})")
    out = []
    for p in x:
        if type(p) not in (tuple, list) or len(p) != 2:
            raise PrimError(f"{what} must hold (row, col) pairs, found {_tname(p)}")
        r, c = p
        if type(r) is not int or type(c) is not int:
            r, c = _int(r, f"{what} row"), _int(c, f"{what} column")
        out.append((r, c))
    return out


def _nonempty(cells, what):
    if not cells:
        raise PrimError(f"{what} is empty")
    return cells


def _dir(d, what="direction"):
    if type(d) is str:
        if d in DIR_NAMES:
            return DIR_NAMES[d]
        raise PrimError(f"{what} {d!r} is not one of {sorted(DIR_NAMES)}")
    if type(d) in (tuple, list) and len(d) == 2:
        dr, dc = _int(d[0], what), _int(d[1], what)
        if (dr, dc) != (0, 0) and -1 <= dr <= 1 and -1 <= dc <= 1:
            return dr, dc
    raise PrimError(f"{what} must be a (dr, dc) pair with values -1, 0 or 1, such as DOWN = (1, 0)")


def _colour_set(x, what):
    if x is None:
        return set()
    if type(x) in (int, bool):
        return {int(x)}
    if type(x) in (list, tuple, set, frozenset):
        return {_int(v, what) for v in x}
    raise PrimError(f"{what} must be a colour or a list of colours")


def _new(h, w, fill=0):
    if not (1 <= h <= MAX_DIM and 1 <= w <= MAX_DIM):
        raise PrimError(f"a {h} x {w} grid is outside 1..{MAX_DIM} on a side")
    return [[fill] * w for _ in range(h)]


def _rows(g):
    return [list(row) for row in g]


def _sorted_cells(cells):
    return sorted(set(cells))


def _box(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), min(cs), max(rs), max(cs)


def _most_common(counts):
    """The key with the largest count, ties to the smallest key."""
    best, bn = None, -1
    for k in sorted(counts):
        if counts[k] > bn:
            best, bn = k, counts[k]
    return best


# ------------------------------------------------------------------ grid
@prim("shape(g)", "(rows, columns) of g", "grid", weight=2)
def shape(g):
    return _grid(g)


@prim("new_grid(h, w, color=0)", "an h x w grid filled with color", "grid", weight=1)
def new_grid(h, w, color=0):
    return _new(_int(h, "h"), _int(w, "w"), _int(color, "color"))


def _deep(x, depth):
    if depth > 30:
        raise PrimError("value nested too deeply to copy")
    t = type(x)
    if t is list:
        return [_deep(v, depth + 1) for v in x]
    if t is tuple:
        return tuple(_deep(v, depth + 1) for v in x)
    if t is dict:
        return {k: _deep(v, depth + 1) for k, v in x.items()}
    if t is set:
        return set(x)
    return x


@prim("copy(g)", "an independent copy of g (any nested list); changing it never changes g", "grid", weight=4)
def copy(g):
    return _deep(g, 0)


@prim("crop(g, r0, c0, r1, c1)", "the part of g in rows r0..r1 and columns c0..c1 (inclusive, clipped to g)",
      "grid", grid_op=True, weight=1)
def crop(g, r0, c0, r1, c1):
    h, w = _grid(g)
    r0, c0, r1, c1 = (_int(v, "crop bound") for v in (r0, c0, r1, c1))
    r0, r1 = min(r0, r1), max(r0, r1)
    c0, c1 = min(c0, c1), max(c0, c1)
    r0, c0, r1, c1 = max(r0, 0), max(c0, 0), min(r1, h - 1), min(c1, w - 1)
    if r0 > r1 or c0 > c1:
        raise PrimError("the box lies outside the grid")
    return [list(g[r][c0:c1 + 1]) for r in range(r0, r1 + 1)]


@prim("paste(g, patch, r, c, transparent=None)", "copy of g with patch's top-left cell at (r, c); patch cells "
      "equal to transparent are skipped; parts outside g are dropped", "grid", grid_op=True, weight=2)
def paste(g, patch, r, c, transparent=None):
    h, w = _grid(g)
    ph, pw = _grid(patch, "patch")
    r, c = _int(r, "r"), _int(c, "c")
    skip = None if transparent is None else _int(transparent, "transparent")
    out = _rows(g)
    for i in range(ph):
        rr = r + i
        if 0 <= rr < h:
            prow, orow = patch[i], out[rr]
            for j in range(pw):
                cc = c + j
                if 0 <= cc < w:
                    v = int(prow[j])
                    if v != skip:
                        orow[cc] = v
    return out


@prim("trim(g, bg=0)", "the smallest box of g holding every cell that is not bg", "grid", grid_op=True, weight=3)
def trim(g, bg=0):
    h, w = _grid(g)
    bg = _int(bg, "bg")
    cells = [(r, c) for r in range(h) for c in range(w) if g[r][c] != bg]
    if not cells:
        raise PrimError("every cell is the background")
    r0, c0, r1, c1 = _box(cells)
    return [list(g[r][c0:c1 + 1]) for r in range(r0, r1 + 1)]


@prim("hconcat(a, b)", "a and b side by side (same number of rows)", "grid", weight=2)
def hconcat(a, b):
    ha, wa = _grid(a, "a")
    hb, wb = _grid(b, "b")
    if ha != hb:
        raise PrimError(f"a has {ha} rows and b has {hb}")
    _new(ha, wa + wb)
    return [list(x) + list(y) for x, y in zip(a, b)]


@prim("vconcat(a, b)", "a above b (same number of columns)", "grid", weight=1)
def vconcat(a, b):
    ha, wa = _grid(a, "a")
    hb, wb = _grid(b, "b")
    if wa != wb:
        raise PrimError(f"a has {wa} columns and b has {wb}")
    _new(ha + hb, wa)
    return _rows(a) + _rows(b)


@prim("split_rows(g, n)", "g cut into n equal horizontal bands, top to bottom (a list of grids)", "grid", weight=2)
def split_rows(g, n):
    h, w = _grid(g)
    n = _int(n, "n")
    if n < 1 or h % n:
        raise PrimError(f"{h} rows cannot be cut into {n} equal bands")
    k = h // n
    return [_rows(g[i * k:(i + 1) * k]) for i in range(n)]


@prim("split_cols(g, n)", "g cut into n equal vertical bands, left to right (a list of grids)", "grid", weight=3)
def split_cols(g, n):
    h, w = _grid(g)
    n = _int(n, "n")
    if n < 1 or w % n:
        raise PrimError(f"{w} columns cannot be cut into {n} equal bands")
    k = w // n
    return [[list(row[i * k:(i + 1) * k]) for row in g] for i in range(n)]


def _runs(flags):
    """[(start, end)] of the maximal runs of False in flags (end exclusive)."""
    out, start = [], None
    for i, f in enumerate(flags + [True]):
        if not f and start is None:
            start = i
        elif f and start is not None:
            out.append((start, i))
            start = None
    return out


@prim("panels(g, color)", "the blocks of g between full rows and full columns of color, as rows of panels: "
      "p[i][j] is panel row i, panel column j", "grid", weight=4)
def panels(g, color):
    h, w = _grid(g)
    color = _int(color, "color")
    full_r = [all(v == color for v in g[r]) for r in range(h)]
    full_c = [all(g[r][c] == color for r in range(h)) for c in range(w)]
    rr, cc = _runs(full_r), _runs(full_c)
    if not rr or not cc:
        raise PrimError("no panel: every row or every column is a separator line")
    return [[[list(g[r][c0:c1]) for r in range(r0, r1)] for c0, c1 in cc] for r0, r1 in rr]


@prim("overlay(a, b, transparent=0)", "copy of a with every cell of b that is not transparent written on top "
      "(same shape)", "grid", grid_op=True, weight=3)
def overlay(a, b, transparent=0):
    ha, wa = _grid(a, "a")
    hb, wb = _grid(b, "b")
    if (ha, wa) != (hb, wb):
        raise PrimError(f"a is {ha}x{wa} and b is {hb}x{wb}")
    t = _int(transparent, "transparent")
    return [[int(y) if y != t else int(x) for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


@prim("shift_grid(g, dr, dc, fill=0)", "the content of g moved dr rows down and dc columns right; vacated cells "
      "get fill", "grid", grid_op=True, weight=4)
def shift_grid(g, dr, dc, fill=0):
    h, w = _grid(g)
    dr, dc, fill = _int(dr, "dr"), _int(dc, "dc"), _int(fill, "fill")
    out = _new(h, w, fill)
    for r in range(h):
        rr = r + dr
        if 0 <= rr < h:
            for c in range(w):
                cc = c + dc
                if 0 <= cc < w:
                    out[rr][cc] = int(g[r][c])
    return out


@prim("in_bounds(g, r, c)", "True if (r, c) is a cell of g", "grid", weight=2)
def in_bounds(g, r, c):
    h, w = _grid(g)
    return 0 <= _int(r, "r") < h and 0 <= _int(c, "c") < w


# ------------------------------------------------------------------ whole-grid transforms
@prim("flip_lr(g)", "mirror left-right (each row reversed)", "transform", grid_op=True, weight=1)
def flip_lr(g):
    _grid(g)
    return [list(row)[::-1] for row in g]


@prim("flip_ud(g)", "mirror top-bottom (row order reversed)", "transform", grid_op=True, weight=1)
def flip_ud(g):
    _grid(g)
    return [list(row) for row in g][::-1]


@prim("rot_cw(g)", "rotate 90 degrees clockwise", "transform", grid_op=True, weight=1)
def rot_cw(g):
    _grid(g)
    return [list(col) for col in zip(*g[::-1])]


@prim("rot_ccw(g)", "rotate 90 degrees counterclockwise", "transform", grid_op=True, weight=1)
def rot_ccw(g):
    _grid(g)
    return [list(col) for col in zip(*g)][::-1]


@prim("rot180(g)", "rotate 180 degrees", "transform", grid_op=True, weight=1)
def rot180(g):
    _grid(g)
    return [list(row)[::-1] for row in g][::-1]


@prim("transpose(g)", "mirror across the main diagonal: row i becomes column i", "transform", grid_op=True, weight=1)
def transpose(g):
    _grid(g)
    return [list(col) for col in zip(*g)]


@prim("anti_transpose(g)", "mirror across the other diagonal (top-right to bottom-left)", "transform", grid_op=True, weight=1)
def anti_transpose(g):
    _grid(g)
    return [list(col)[::-1] for col in zip(*g)][::-1]


@prim("tile(g, nr, nc)", "g repeated nr times downward and nc times across", "transform", grid_op=True, weight=1)
def tile(g, nr, nc):
    h, w = _grid(g)
    nr, nc = _int(nr, "nr"), _int(nc, "nc")
    _new(h * nr, w * nc)
    return [list(g[r % h]) * nc for r in range(h * nr)]


@prim("upscale(g, kr, kc=None)", "every cell becomes a kr x kc block (kc defaults to kr)", "transform", grid_op=True, weight=5)
def upscale(g, kr, kc=None):
    h, w = _grid(g)
    kr = _int(kr, "kr")
    kc = kr if kc is None else _int(kc, "kc")
    _new(h * kr, w * kc)
    return [[int(v) for v in g[r // kr] for _ in range(kc)] for r in range(h * kr)]


@prim("downscale(g, kr, kc=None)", "one cell per kr x kc block: the block's most common colour (ties: smallest)",
      "transform", grid_op=True, weight=13)
def downscale(g, kr, kc=None):
    h, w = _grid(g)
    kr = _int(kr, "kr")
    kc = kr if kc is None else _int(kc, "kc")
    if kr < 1 or kc < 1 or h % kr or w % kc:
        raise PrimError(f"a {h}x{w} grid has no whole {kr}x{kc} blocks")
    out = []
    for br in range(h // kr):
        row = []
        for bc in range(w // kc):
            counts = {}
            for r in range(br * kr, (br + 1) * kr):
                for c in range(bc * kc, (bc + 1) * kc):
                    v = int(g[r][c])
                    counts[v] = counts.get(v, 0) + 1
            row.append(_most_common(counts))
        out.append(row)
    return out


# ------------------------------------------------------------------ colours
@prim("colors(g)", "sorted list of the colours present in g", "colour", weight=5)
def colors(g):
    _grid(g)
    return sorted({int(v) for row in g for v in row})


@prim("count(g, color)", "number of cells of g with that colour", "colour", weight=3)
def count(g, color):
    _grid(g)
    color = _int(color, "color")
    return sum(1 for row in g for v in row if v == color)


@prim("color_counts(g)", "dict colour -> number of cells, for the colours present", "colour", weight=8)
def color_counts(g):
    _grid(g)
    counts = {}
    for row in g:
        for v in row:
            v = int(v)
            counts[v] = counts.get(v, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def _counts_except(g, ignore):
    _grid(g)
    skip = _colour_set(ignore, "ignore")
    counts = {}
    for row in g:
        for v in row:
            v = int(v)
            if v not in skip:
                counts[v] = counts.get(v, 0) + 1
    if not counts:
        raise PrimError("no colour left after ignoring")
    return counts


@prim("most_common_color(g, ignore=None)", "the most frequent colour (ties: smallest); ignore = a colour or a list "
      "of colours to leave out", "colour", weight=9)
def most_common_color(g, ignore=None):
    return _most_common(_counts_except(g, ignore))


@prim("least_common_color(g, ignore=None)", "the least frequent colour present (ties: smallest)", "colour", weight=9)
def least_common_color(g, ignore=None):
    counts = _counts_except(g, ignore)
    best, bn = None, None
    for k in sorted(counts):
        if bn is None or counts[k] < bn:
            best, bn = k, counts[k]
    return best


@prim("replace(g, old, new)", "copy of g where every cell of colour old becomes new", "colour", grid_op=True, weight=3)
def replace(g, old, new):
    _grid(g)
    old, new = _int(old, "old"), _int(new, "new")
    return [[new if v == old else int(v) for v in row] for row in g]


@prim("map_colors(g, mapping)", "copy of g where every colour k in the dict mapping becomes mapping[k]", "colour",
      grid_op=True, weight=5)
def map_colors(g, mapping):
    _grid(g)
    if type(mapping) is not dict:
        raise PrimError("mapping must be a dict such as {1: 2, 3: 4}")
    m = {_int(k, "mapping key"): _int(v, "mapping value") for k, v in mapping.items()}
    return [[m.get(int(v), int(v)) for v in row] for row in g]


@prim("cells_of(g, color)", "the cells of g with that colour, in reading order", "colour", weight=2)
def cells_of(g, color):
    h, w = _grid(g)
    color = _int(color, "color")
    return [(r, c) for r in range(h) for c in range(w) if g[r][c] == color]


@prim("most_common(values)", "the most frequent value of a list (ties: the one that comes first)", "colour", weight=7)
def most_common(values):
    if type(values) not in (list, tuple):
        raise PrimError("most_common takes a list")
    if not values:
        raise PrimError("the list is empty")
    counts, first = {}, {}
    for i, v in enumerate(values):
        try:
            counts[v] = counts.get(v, 0) + 1
        except TypeError:
            raise PrimError("values must be ints, tuples or strings") from None
        first.setdefault(v, i)
    return max(counts, key=lambda v: (counts[v], -first[v]))


# ------------------------------------------------------------------ objects
def _flood(cellset, start, steps):
    seen = {start}
    stack = [start]
    while stack:
        r, c = stack.pop()
        for dr, dc in steps:
            n = (r + dr, c + dc)
            if n in cellset and n not in seen:
                seen.add(n)
                stack.append(n)
    return seen


@prim("objects(g, diag=False, multicolor=False, bg=0)", "connected groups of cells that are not bg: same colour "
      "unless multicolor, diagonal neighbours joined if diag; ordered by their first cell; bg=None: no background",
      "object", weight=25)
def objects(g, diag=False, multicolor=False, bg=0):
    h, w = _grid(g)
    bgv = None if bg is None else _int(bg, "bg")
    steps = N8 if diag else N4
    seen = [[False] * w for _ in range(h)]
    out = []
    for r in range(h):
        for c in range(w):
            if seen[r][c] or (bgv is not None and g[r][c] == bgv):
                continue
            col = g[r][c]
            comp = [(r, c)]
            seen[r][c] = True
            stack = [(r, c)]
            while stack:
                y, x = stack.pop()
                for dr, dc in steps:
                    ny, nx = y + dr, x + dc
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny][nx]:
                        v = g[ny][nx]
                        if (bgv is not None and v == bgv) or (not multicolor and v != col):
                            continue
                        seen[ny][nx] = True
                        comp.append((ny, nx))
                        stack.append((ny, nx))
            out.append(sorted(comp))
    return out


@prim("components(cells, diag=False)", "the connected groups of a cell list (ordered by their first cell)",
      "object", weight=29)
def components(cells, diag=False):
    cs = set(_cells(cells))
    steps = N8 if diag else N4
    out, done = [], set()
    for p in sorted(cs):
        if p in done:
            continue
        comp = _flood(cs, p, steps)
        done |= comp
        out.append(sorted(comp))
    return out


@prim("bbox(cells)", "(r0, c0, r1, c1): the first and last row and column of the cells", "object", weight=7)
def bbox(cells):
    return _box(_nonempty(_cells(cells), "the cell list"))


@prim("color_of(g, cells)", "the most common colour of g on the cells (ties: smallest)", "object", weight=5)
def color_of(g, cells):
    h, w = _grid(g)
    counts = {}
    for r, c in _cells(cells):
        if 0 <= r < h and 0 <= c < w:
            v = int(g[r][c])
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        raise PrimError("no cell of the list lies in the grid")
    return _most_common(counts)


@prim("colors_in(g, cells)", "sorted list of the colours of g on the cells", "object", weight=5)
def colors_in(g, cells):
    h, w = _grid(g)
    return sorted({int(g[r][c]) for r, c in _cells(cells) if 0 <= r < h and 0 <= c < w})


@prim("crop_object(g, cells, bg=0)", "the cells' bounding box as a grid: the cells keep their colours, every other "
      "cell is bg", "object", weight=5)
def crop_object(g, cells, bg=0):
    h, w = _grid(g)
    cs = [(r, c) for r, c in _cells(cells) if 0 <= r < h and 0 <= c < w]
    _nonempty(cs, "the object (inside the grid)")
    bg = _int(bg, "bg")
    r0, c0, r1, c1 = _box(cs)
    out = _new(r1 - r0 + 1, c1 - c0 + 1, bg)
    for r, c in cs:
        out[r - r0][c - c0] = int(g[r][c])
    return out


@prim("normalize(cells)", "the cells moved so that their bounding box starts at (0, 0)", "object", weight=8)
def normalize(cells):
    cs = _nonempty(_cells(cells), "the cell list")
    r0, c0, _, _ = _box(cs)
    return _sorted_cells((r - r0, c - c0) for r, c in cs)


@prim("shift(cells, dr, dc)", "the cells moved dr rows down and dc columns right", "object", weight=6)
def shift(cells, dr, dc):
    dr, dc = _int(dr, "dr"), _int(dc, "dc")
    return _sorted_cells((r + dr, c + dc) for r, c in _cells(cells))


@prim("paint(g, cells, color)", "copy of g with the cells set to color (cells outside g are ignored)", "object",
      grid_op=True, weight=3)
def paint(g, cells, color):
    h, w = _grid(g)
    color = _int(color, "color")
    out = _rows(g)
    for r, c in _cells(cells):
        if 0 <= r < h and 0 <= c < w:
            out[r][c] = color
    return out


@prim("move(g, cells, dr, dc, bg=0)", "copy of g with the object (its colours) moved by (dr, dc); its old cells "
      "become bg", "object", grid_op=True, weight=4)
def move(g, cells, dr, dc, bg=0):
    h, w = _grid(g)
    dr, dc, bg = _int(dr, "dr"), _int(dc, "dc"), _int(bg, "bg")
    cs = [(r, c) for r, c in _cells(cells) if 0 <= r < h and 0 <= c < w]
    vals = [int(g[r][c]) for r, c in cs]
    out = _rows(g)
    for r, c in cs:
        out[r][c] = bg
    for (r, c), v in zip(cs, vals):
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            out[rr][cc] = v
    return out


@prim("copy_to(g, cells, dr, dc)", "copy of g with a copy of the object (its colours) drawn at offset (dr, dc); "
      "the original stays", "object", grid_op=True, weight=4)
def copy_to(g, cells, dr, dc):
    h, w = _grid(g)
    dr, dc = _int(dr, "dr"), _int(dc, "dc")
    cs = [(r, c) for r, c in _cells(cells) if 0 <= r < h and 0 <= c < w]
    out = _rows(g)
    for r, c in cs:
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            out[rr][cc] = int(g[r][c])
    return out


@prim("holes(cells)", "the cells enclosed by the object: inside its box, not in it, and cut off from the outside "
      "(4-neighbour moves)", "object", weight=9)
def holes(cells):
    cs = set(_nonempty(_cells(cells), "the object"))
    r0, c0, r1, c1 = _box(cs)
    outside = set()
    stack = [(r, c) for r in range(r0 - 1, r1 + 2) for c in (c0 - 1, c1 + 1)] + \
            [(r, c) for c in range(c0 - 1, c1 + 2) for r in (r0 - 1, r1 + 1)]
    for p in stack:
        outside.add(p)
    while stack:
        r, c = stack.pop()
        for dr, dc in N4:
            n = (r + dr, c + dc)
            if r0 - 1 <= n[0] <= r1 + 1 and c0 - 1 <= n[1] <= c1 + 1 and n not in outside and n not in cs:
                outside.add(n)
                stack.append(n)
    return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if (r, c) not in cs and
            (r, c) not in outside]


@prim("border(cells)", "the object's cells that have a neighbour (8 directions) outside the object", "object", weight=29)
def border(cells):
    cs = set(_cells(cells))
    return sorted(p for p in cs if any((p[0] + dr, p[1] + dc) not in cs for dr, dc in N8))


@prim("interior(cells)", "the object's cells that are not on its border", "object", weight=21)
def interior(cells):
    cs = set(_cells(cells))
    return sorted(p for p in cs if all((p[0] + dr, p[1] + dc) in cs for dr, dc in N8))


@prim("neighbors(cells, diag=False)", "the cells next to the object (4 sides, or 8 with diag) that are not in it; "
      "may lie outside the grid", "object", weight=15)
def neighbors(cells, diag=False):
    cs = set(_cells(cells))
    steps = N8 if diag else N4
    return sorted({(r + dr, c + dc) for r, c in cs for dr, dc in steps} - cs)


@prim("rect(r0, c0, r1, c1)", "every cell of the rectangle with corners (r0, c0) and (r1, c1)", "object", weight=1)
def rect(r0, c0, r1, c1):
    r0, c0, r1, c1 = (_int(v, "corner") for v in (r0, c0, r1, c1))
    r0, r1 = min(r0, r1), max(r0, r1)
    c0, c1 = min(c0, c1), max(c0, c1)
    if (r1 - r0 + 1) * (c1 - c0 + 1) > MAX_CELLS:
        raise PrimError("rectangle too large")
    return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


@prim("box_outline(r0, c0, r1, c1)", "the cells on the outline of that rectangle", "object", weight=2)
def box_outline(r0, c0, r1, c1):
    r0, c0, r1, c1 = (_int(v, "corner") for v in (r0, c0, r1, c1))
    r0, r1 = min(r0, r1), max(r0, r1)
    c0, c1 = min(c0, c1), max(c0, c1)
    if (r1 - r0 + 1) * (c1 - c0 + 1) > MAX_CELLS:
        raise PrimError("rectangle too large")
    out = []
    for r in range(r0, r1 + 1):
        if r == r0 or r == r1:
            out.extend((r, c) for c in range(c0, c1 + 1))
        else:
            out.append((r, c0))
            if c1 != c0:
                out.append((r, c1))
    return out


@prim("is_rectangle(cells)", "True if the cells fill their bounding box", "object", weight=8)
def is_rectangle(cells):
    cs = set(_nonempty(_cells(cells), "the cell list"))
    r0, c0, r1, c1 = _box(cs)
    return len(cs) == (r1 - r0 + 1) * (c1 - c0 + 1)


@prim("touches_border(g, cells)", "True if a cell lies on the edge of g", "object", weight=5)
def touches_border(g, cells):
    h, w = _grid(g)
    return any(r in (0, h - 1) or c in (0, w - 1) for r, c in _cells(cells))


@prim("adjacent(a, b, diag=False)", "True if a cell of a is next to (or on) a cell of b", "object", weight=14)
def adjacent(a, b, diag=False):
    sa, sb = set(_cells(a, "a")), set(_cells(b, "b"))
    steps = N8 if diag else N4
    return bool(sa & sb) or any((r + dr, c + dc) in sb for r, c in sa for dr, dc in steps)


@prim("same_shape(a, b)", "True if a and b are the same shape up to position", "object", weight=15)
def same_shape(a, b):
    return normalize(a) == normalize(b)


@prim("center(cells)", "(r, c): the middle of the cells' bounding box, rounded down", "object", weight=7)
def center(cells):
    r0, c0, r1, c1 = bbox(cells)
    return (r0 + r1) // 2, (c0 + c1) // 2


@prim("merge(objs)", "one object made of every cell of a list of objects", "object", weight=6)
def merge(objs):
    if type(objs) not in (list, tuple):
        raise PrimError("merge takes a list of objects")
    out = set()
    for o in objs:
        out.update(_cells(o, "object"))
    return sorted(out)


# ------------------------------------------------------------------ drawing
@prim("line(g, r0, c0, r1, c1, color)", "copy of g with a straight line (row, column or 45-degree diagonal) from "
      "(r0, c0) to (r1, c1), ends included", "draw", grid_op=True, weight=1)
def line(g, r0, c0, r1, c1, color):
    h, w = _grid(g)
    r0, c0, r1, c1 = (_int(v, "end point") for v in (r0, c0, r1, c1))
    color = _int(color, "color")
    dr, dc = r1 - r0, c1 - c0
    if not (dr == 0 or dc == 0 or abs(dr) == abs(dc)):
        raise PrimError("the two ends share no row, column or diagonal")
    n = max(abs(dr), abs(dc))
    sr, sc = (dr > 0) - (dr < 0), (dc > 0) - (dc < 0)
    out = _rows(g)
    for k in range(n + 1):
        r, c = r0 + k * sr, c0 + k * sc
        if 0 <= r < h and 0 <= c < w:
            out[r][c] = color
    return out


@prim("ray_cells(g, r, c, d, stop=False, bg=0)", "the cells from the one after (r, c) in direction d to the edge "
      "of g; with stop=True it ends before the first cell that is not bg", "draw", weight=2)
def ray_cells(g, r, c, d, stop=False, bg=0):
    h, w = _grid(g)
    r, c = _int(r, "r"), _int(c, "c")
    dr, dc = _dir(d)
    bg = _int(bg, "bg")
    out = []
    r, c = r + dr, c + dc
    while 0 <= r < h and 0 <= c < w:
        if stop and g[r][c] != bg:
            break
        out.append((r, c))
        r, c = r + dr, c + dc
    return out


@prim("ray(g, r, c, d, color, stop=False, bg=0)", "copy of g with ray_cells(g, r, c, d, stop, bg) painted color",
      "draw", grid_op=True, weight=2)
def ray(g, r, c, d, color, stop=False, bg=0):
    return paint(g, ray_cells(g, r, c, d, stop, bg), color)


@prim("rectangle(g, r0, c0, r1, c1, color, filled=True)", "copy of g with that rectangle painted (filled, or only "
      "its outline)", "draw", grid_op=True, weight=6)
def rectangle(g, r0, c0, r1, c1, color, filled=True):
    return paint(g, rect(r0, c0, r1, c1) if filled else box_outline(r0, c0, r1, c1), color)


@prim("flood_fill(g, r, c, color, diag=False)", "copy of g where the region of (r, c)'s colour connected to (r, c) "
      "becomes color", "draw", grid_op=True, weight=17)
def flood_fill(g, r, c, color, diag=False):
    h, w = _grid(g)
    r, c, color = _int(r, "r"), _int(c, "c"), _int(color, "color")
    if not (0 <= r < h and 0 <= c < w):
        raise PrimError(f"({r}, {c}) is outside the grid")
    old = g[r][c]
    region = cells_of(g, old)
    cs = _flood(set(region), (r, c), N8 if diag else N4)
    return paint(g, cs, color)


@prim("fill_enclosed(g, color, bg=0)", "copy of g where every bg cell that cannot reach the edge through bg cells "
      "(4-neighbour moves) becomes color", "draw", grid_op=True, weight=7)
def fill_enclosed(g, color, bg=0):
    h, w = _grid(g)
    color, bg = _int(color, "color"), _int(bg, "bg")
    out = _rows(g)
    seen = [[False] * w for _ in range(h)]
    stack = [(r, c) for r in range(h) for c in (0, w - 1) if g[r][c] == bg] + \
            [(r, c) for c in range(w) for r in (0, h - 1) if g[r][c] == bg]
    for r, c in stack:
        seen[r][c] = True
    while stack:
        r, c = stack.pop()
        for dr, dc in N4:
            y, x = r + dr, c + dc
            if 0 <= y < h and 0 <= x < w and not seen[y][x] and g[y][x] == bg:
                seen[y][x] = True
                stack.append((y, x))
    for r in range(h):
        for c in range(w):
            if g[r][c] == bg and not seen[r][c]:
                out[r][c] = color
    return out


# ------------------------------------------------------------------ patterns, symmetry, periodicity
def _find_cost(args, kw):
    if len(args) < 2:
        return 0
    (h, w), (ph, pw) = _dims(args[0]), _dims(args[1])
    return max(0, h - ph + 1) * max(0, w - pw + 1) * ph * pw * 3 // 4


@prim("find_pattern(g, patch, transparent=None)", "the top-left cells (r, c) where patch occurs in g; patch cells "
      "equal to transparent match anything", "pattern", weight=1, cost=_find_cost)
def find_pattern(g, patch, transparent=None):
    h, w = _grid(g)
    ph, pw = _grid(patch, "patch")
    t = None if transparent is None else _int(transparent, "transparent")
    need = [(i, j, patch[i][j]) for i in range(ph) for j in range(pw) if patch[i][j] != t]
    out = []
    for r in range(h - ph + 1):
        for c in range(w - pw + 1):
            if all(g[r + i][c + j] == v for i, j, v in need):
                out.append((r, c))
    return out


def _sym_maps(h, w):
    """Candidate symmetries as (name, map) on cells; mirrors on every axis, rotations about centres near the
    middle (doubled coordinates keep half-cell centres exact)."""
    out = []
    for a in range(1, 2 * w - 2):
        out.append(("mirror_lr", lambda r, c, a=a: (r, a - c)))
    for b in range(1, 2 * h - 2):
        out.append(("mirror_ud", lambda r, c, b=b: (b - r, c)))
    for d in range(-(w - 2), h - 1):
        out.append(("mirror_diag", lambda r, c, d=d: (c + d, r - d)))
    for s in range(1, h + w - 2):
        out.append(("mirror_anti", lambda r, c, s=s: (s - c, s - r)))
    k = 6
    for P in range(h - 1 - k, h - 1 + k + 1):
        for Q in range(w - 1 - k, w - 1 + k + 1):
            out.append(("rot180", lambda r, c, P=P, Q=Q: (P - r, Q - c)))
            if (P + Q) % 2 == 0:
                # doubled coordinates: (2r - P, 2c - Q) -> (2c - Q, P - 2r) for a clockwise quarter turn
                out.append(("rot90", lambda r, c, P=P, Q=Q: ((P + 2 * c - Q) // 2, (Q + P - 2 * r) // 2)))
    return out


def _symmetric_cost(args, kw):
    h, w = _dims(args[0]) if args else (1, 1)
    return h * w * (h + w)


@prim("fill_symmetric(g, unknown)", "copy of g where cells of colour unknown take the colour of their mirror or "
      "rotated image, under every symmetry (any axis or centre) that the other cells obey", "pattern", weight=2,
      cost=_symmetric_cost)
def fill_symmetric(g, unknown):
    h, w = _grid(g)
    if h > 30 or w > 30:
        raise PrimError("fill_symmetric works on grids of at most 30 x 30")
    u = _int(unknown, "unknown")
    out = _rows(g)
    known = [(r, c) for r in range(h) for c in range(w) if out[r][c] != u]
    if len(known) == h * w or not known:
        return out
    known.sort(key=lambda p: ((p[0] * 7919 + p[1] * 104729) % 1009, p))     # scattered: conflicts show early
    counts = {}
    for r, c in known:
        counts[out[r][c]] = counts.get(out[r][c], 0) + 1
    major = _most_common(counts)
    n_fg = len(known) - counts[major]
    need, need_fg = max(4, len(known) // 2), max(2, n_fg // 2)
    good = []
    for _name, f in _sym_maps(h, w):
        agree, agree_fg, ok = 0, 0, True
        for r, c in known:
            y, x = f(r, c)
            if (y, x) == (r, c) or not (0 <= y < h and 0 <= x < w):
                continue
            v = out[y][x]
            if v == u:
                continue
            if v != out[r][c]:
                ok = False
                break
            agree += 1
            if v != major:
                agree_fg += 1
        if ok and agree >= need and agree_fg >= need_fg:
            good.append((agree, len(good), f))
    good.sort(key=lambda t: (-t[0], t[1]))
    maps = [f for _, _, f in good]
    changed = True
    while changed and maps:
        changed = False
        for r in range(h):
            for c in range(w):
                if out[r][c] != u:
                    continue
                for f in maps:
                    y, x = f(r, c)
                    if 0 <= y < h and 0 <= x < w and out[y][x] != u:
                        out[r][c] = out[y][x]
                        changed = True
                        break
    return out


def _period_ok(g, pr, pc, u, h, w):
    tile = {}
    for r in range(h):
        for c in range(w):
            v = g[r][c]
            if v == u:
                continue
            k = (r % pr, c % pc)
            t = tile.get(k)
            if t is None:
                tile[k] = v
            elif t != v:
                return None
    return tile


@prim("period(g)", "(pr, pc): the smallest row and column periods of g (g[r][c] == g[r + pr][c] == "
      "g[r][c + pc]); (rows, columns) if none is smaller", "pattern", weight=5)
def period(g):
    h, w = _grid(g)
    g = _rows(g)
    pr = next(p for p in range(1, h + 1) if all(g[r] == g[r + p] for r in range(h - p)))
    pc = next(p for p in range(1, w + 1) if all(row[c] == row[c + p] for row in g for c in range(w - p)))
    return pr, pc


def _row_periods(g, u, h, w):
    out = []
    for p in range(1, h + 1):
        if all(a == b or a == u or b == u for r in range(h - p) for a, b in zip(g[r], g[r + p])):
            out.append(p)
    return out


def _periodic_cost(args, kw):
    h, w = _dims(args[0]) if args else (1, 1)
    return (h * h * w + h * w * w) // 2


@prim("fill_periodic(g, unknown)", "copy of g where cells of colour unknown are filled from the smallest repeating "
      "tile that the other cells agree with", "pattern", weight=2, cost=_periodic_cost)
def fill_periodic(g, unknown):
    h, w = _grid(g)
    u = _int(unknown, "unknown")
    g = _rows(g)
    pr_ok = _row_periods(g, u, h, w)
    pc_ok = _row_periods([list(col) for col in zip(*g)], u, w, h)
    for pr, pc in sorted(((a, b) for a in pr_ok for b in pc_ok), key=lambda t: (t[0] * t[1], t)):
        tile = _period_ok(g, pr, pc, u, h, w)
        if tile is not None and len(tile) == pr * pc:
            return [[tile[(r % pr, c % pc)] if g[r][c] == u else g[r][c] for c in range(w)] for r in range(h)]
    return g


# ------------------------------------------------------------------ motion
@prim("gravity(g, d, bg=0)", "copy of g where every cell that is not bg slides as far as it can in direction d "
      "(UP, DOWN, LEFT or RIGHT), keeping its order", "motion", grid_op=True, weight=4)
def gravity(g, d, bg=0):
    h, w = _grid(g)
    dr, dc = _dir(d)
    bg = _int(bg, "bg")
    if dr and dc:
        raise PrimError("gravity needs UP, DOWN, LEFT or RIGHT")
    out = _new(h, w, bg)
    if dc == 0:
        for c in range(w):
            col = [int(g[r][c]) for r in range(h) if g[r][c] != bg]
            rows = range(h - len(col), h) if dr > 0 else range(len(col))
            for r, v in zip(rows, col):
                out[r][c] = v
    else:
        for r in range(h):
            vals = [int(v) for v in g[r] if v != bg]
            cols = range(w - len(vals), w) if dc > 0 else range(len(vals))
            for c, v in zip(cols, vals):
                out[r][c] = v
    return out


@prim("slide_distance(g, cells, d, bg=0)", "how many steps the object can move in direction d before it would "
      "leave g or overlap a cell that is not bg", "motion", weight=5)
def slide_distance(g, cells, d, bg=0):
    h, w = _grid(g)
    dr, dc = _dir(d)
    bg = _int(bg, "bg")
    cs = set(_nonempty(_cells(cells), "the object"))
    k = 0
    while k <= MAX_DIM:
        nk = k + 1
        ok = True
        for r, c in cs:
            y, x = r + nk * dr, c + nk * dc
            if not (0 <= y < h and 0 <= x < w) or ((y, x) not in cs and g[y][x] != bg):
                ok = False
                break
        if not ok:
            return k
        k = nk
    return k


@prim("slide(g, cells, d, bg=0)", "copy of g with the object moved in direction d until it touches a cell that is "
      "not bg or the edge", "motion", grid_op=True, weight=5)
def slide(g, cells, d, bg=0):
    k = slide_distance(g, cells, d, bg)
    dr, dc = _dir(d)
    return move(g, cells, k * dr, k * dc, bg)
