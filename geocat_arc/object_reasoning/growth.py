"""Generic object-growth geometry (Stage 2 round 2, DeltaType.GROW).

A GROW delta explains a matched (input, output) object pair where the output
contains every input cell (same colors) plus added cells.  The added cells
must be reproducible by one of the generic growth modes below — pure
functions of the object's cells and the grid frame, never of the task id.

Modes (GROW_MODES, preference order = listed order):
  fill_interior — added cells fill the object's enclosed interior holes.
  halo          — added cells are the object's adjacent ring (conn 4 or 8).
  ray           — added cells extrude the object's silhouette in one unit
                  direction for a fixed length or until the grid border.
  pattern       — exact added-cell pattern relative to the object's bbox
                  origin (constant fallback; legal but ParameterClass
                  CONSTANT, so it ranks last and is honestly flagged).

All functions are deterministic and side-effect free; cells are absolute
(row, col) -> color dicts, matching cell_colors_of()."""
from __future__ import annotations

from typing import Any, Optional

#: Growth-mode vocabulary (symbolic constants, JSON-native strings).
#: symmetry_complete (round 3): added cells complete the object's own
#: mirror symmetry — fully relational (no bound literals), so it survives
#: LOO where constant-pattern memorizations die.
#: periodic_self / periodic_bbox / frame_minority (round 19, EXTENSIONAL
#: PATTERN DERIVATION): every parameter is DERIVED from the object at render
#: time (its own internal period, its own bbox extent, its own minority-cell
#: count and colour) — the direct replacements for the constant `pattern`
#: memorizer that the R19 traces named.  Listed BEFORE `pattern` so the
#: relational spellings win the preference order; they are only ever
#: DETECTED when ARC_PATTERN_DERIVE=1 (see _pattern_derive_enabled).
#: cross_center / cavity_leak / ray_deflect (round 20, RAY/LINE EXTENSION):
#: the first GRID-AWARE growth modes.  They take the input grid and derive
#: the background from it at render time, which is what makes obstacle-
#: conditional stopping and background-only painting expressible at all.
#: Listed BEFORE `pattern` for the same reason as the round-19 modes, and
#: only ever DETECTED when ARC_RAY_EXT=1 (see _ray_ext_enabled).
GROW_MODES: tuple[str, ...] = ("fill_interior", "halo", "ray",
                               "symmetry_complete", "mirror_edge",
                               "periodic_self", "periodic_bbox",
                               "frame_minority", "cross_center",
                               "cavity_leak", "ray_deflect", "fill_holes",
                               "pattern")

#: Round-19 derived modes (the ARC_PATTERN_DERIVE-gated subset of GROW_MODES).
PATTERN_DERIVE_MODES: tuple[str, ...] = ("periodic_self", "periodic_bbox",
                                         "frame_minority")


def _pattern_derive_enabled() -> bool:
    """Round-19 env gate.  Read at call time (never cached) so the flag can
    be flipped inside a process; the OFF path costs one dict lookup and the
    derived modes are then never detected, induced, or emitted."""
    import os
    return os.environ.get("ARC_PATTERN_DERIVE", "") not in ("", "0")

#: Unit vectors for ray extrusion (axis directions from types.DIRECTIONS).
_UNIT: dict[str, tuple[int, int]] = {
    "up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1),
}


def interior_cells(cells: frozenset | set) -> set:
    """Enclosed interior of a cell set: bbox cells not in the set and not
    reachable from the bbox border via 4-connected flood over non-set cells
    (the mask-level generalization of ARCObject.holes)."""
    if not cells:
        return set()
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    r0, r1 = min(rows), max(rows)
    c0, c1 = min(cols), max(cols)
    empty = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
             if (r, c) not in cells}
    # flood from bbox-border empties; the unreached empties are interior
    frontier = [p for p in empty
                if p[0] in (r0, r1) or p[1] in (c0, c1)]
    outside = set(frontier)
    while frontier:
        r, c = frontier.pop()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            p = (nr, nc)
            if p in empty and p not in outside:
                outside.add(p)
                frontier.append(p)
    return empty - outside


def grow_fill_interior(cells: frozenset | set, color: int) -> dict:
    """Added cells for mode=fill_interior."""
    return {p: int(color) for p in interior_cells(cells)}


def grow_halo(cells: frozenset | set, color: int, conn: int,
              bounds: tuple[int, int]) -> dict:
    """Added cells for mode=halo: the in-bounds ring of cells adjacent
    (4- or 8-connected) to the object and not part of it."""
    h, w = bounds
    if conn == 4:
        offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
    else:
        offsets = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                        if (dr, dc) != (0, 0))
    ring = set()
    for r, c in cells:
        for dr, dc in offsets:
            p = (r + dr, c + dc)
            if p not in cells and 0 <= p[0] < h and 0 <= p[1] < w:
                ring.add(p)
    return {p: int(color) for p in ring}


def grow_ray(cells: frozenset | set, direction: str, color: int,
             length: Optional[int], bounds: tuple[int, int]) -> dict:
    """Added cells for mode=ray: extrude the object's silhouette ``length``
    steps in ``direction`` (None = until the grid border)."""
    if direction not in _UNIT:
        return {}
    dr, dc = _UNIT[direction]
    h, w = bounds
    steps = length if length is not None else max(h, w)
    added: dict = {}
    for r, c in cells:
        for i in range(1, steps + 1):
            p = (r + i * dr, c + i * dc)
            if not (0 <= p[0] < h and 0 <= p[1] < w):
                break
            if p not in cells:
                added[p] = int(color)
    return added


def _mirror_fn(axis: str, r0: int, r1: int, c0: int, c1: int):
    """Cell -> mirrored cell across the bbox axis (types.AXES vocabulary)."""
    if axis == "horizontal":      # mirror across the horizontal midline
        return lambda r, c: (r0 + r1 - r, c)
    if axis == "vertical":
        return lambda r, c: (r, c0 + c1 - c)
    if axis == "diag_main":       # square bboxes only (checked by caller)
        return lambda r, c: (r0 + (c - c0), c0 + (r - r0))
    if axis == "diag_anti":
        return lambda r, c: (r0 + (c1 - c), c0 + (r1 - r))
    return None


def grow_symmetry_complete(cell_colors: dict, axis: str) -> Optional[dict]:
    """Added cells that complete the object's mirror symmetry across its own
    bbox ``axis``: every existing cell is reflected; reflections landing on
    empty positions are added carrying the SOURCE cell's color.  Fully
    relational — no train-bound values.  None when the axis is undefined
    (diagonal on a non-square bbox) or the completion adds nothing."""
    if not cell_colors:
        return None
    rows = [r for r, _ in cell_colors]
    cols = [c for _, c in cell_colors]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    if axis in ("diag_main", "diag_anti") and (r1 - r0) != (c1 - c0):
        return None
    fn = _mirror_fn(axis, r0, r1, c0, c1)
    if fn is None:
        return None
    added: dict = {}
    for (r, c), col in sorted(cell_colors.items()):
        m = fn(r, c)
        if m not in cell_colors:
            added[m] = int(col)
    return added or None


def grow_mirror_edge(cell_colors: dict, direction: str,
                     bounds: tuple[int, int]) -> Optional[dict]:
    """Added cells = the object reflected across its own bbox edge in
    ``direction`` (half-shape doubling: a left half grows its right half).
    Colors carried from the source cells — fully relational.  None when any
    reflected cell falls out of bounds or the reflection adds nothing."""
    if not cell_colors or direction not in _UNIT:
        return None
    rows = [r for r, _ in cell_colors]
    cols = [c for _, c in cell_colors]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    h, w = bounds
    if direction == "up":
        fn = lambda r, c: (2 * r0 - 1 - r, c)      # noqa: E731
    elif direction == "down":
        fn = lambda r, c: (2 * r1 + 1 - r, c)      # noqa: E731
    elif direction == "left":
        fn = lambda r, c: (r, 2 * c0 - 1 - c)      # noqa: E731
    else:
        fn = lambda r, c: (r, 2 * c1 + 1 - c)      # noqa: E731
    added: dict = {}
    for (r, c), col in sorted(cell_colors.items()):
        m = fn(r, c)
        if not (0 <= m[0] < h and 0 <= m[1] < w):
            return None
        if m not in cell_colors:
            added[m] = int(col)
    return added or None


# ---------------------------------------------------------------------------
# ROUND 19: EXTENSIONAL PATTERN DERIVATION (ARC_PATTERN_DERIVE)
#
# The R19 traces found that 43% of divergent tasks fail because GROW falls
# back to mode=pattern, which stores LITERAL bbox-relative cell coordinates.
# Those constants fit the training pairs and die at LOO.  The three modes
# below compute the SAME cell sets from the object alone at render time, so
# a held-out pair with a different object gets a different (correct) answer.
# Every parameter here is a symbol (a direction) — never a cell list.
# ---------------------------------------------------------------------------

def self_period(cell_colors: dict, axis: str) -> Optional[int]:
    """The object's own internal period along ``axis`` ('v' rows | 'h' cols):
    the smallest p >= 1 such that translating the object by p agrees with
    itself EXACTLY over the intersection of the two bounding boxes —
    occupancy AND colour, so a cell present in one copy and absent in the
    other is a mismatch (that strictness is what rejects spurious short
    periods; traced on d8c310e9, whose true periods are 4 / 3 / 6).

    None when no period shorter than the object's own extent exists."""
    if not cell_colors:
        return None
    i = 0 if axis == "v" else 1
    rows = [r for r, _ in cell_colors]
    cols = [c for _, c in cell_colors]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    extent = (r1 - r0 + 1) if i == 0 else (c1 - c0 + 1)
    for p in range(1, extent):
        shifted = {}
        for (r, c), col in cell_colors.items():
            shifted[(r + p, c) if i == 0 else (r, c + p)] = col
        if i == 0:
            lo, hi = max(r0, r0 + p), min(r1, r1 + p)
            region = [(r, c) for r in range(lo, hi + 1)
                      for c in range(c0, c1 + 1)]
        else:
            lo, hi = max(c0, c0 + p), min(c1, c1 + p)
            region = [(r, c) for r in range(r0, r1 + 1)
                      for c in range(lo, hi + 1)]
        if not region:
            continue
        if any(k in cell_colors for k in region) and \
                all(cell_colors.get(k) == shifted.get(k) for k in region):
            return p
    return None


def grow_periodic(cell_colors: dict, direction: str, bounds: tuple[int, int],
                  period_src: str) -> Optional[dict]:
    """Added cells for the periodic-continuation modes: the object repeated
    in ``direction`` at a period DERIVED from the object, until the whole
    copy has left the grid.  Colours are carried from the source cells.

    period_src='self' — the object's own internal period along the axis
        (mode periodic_self; traced on d8c310e9, a horizontally periodic
        strip continued rightward to the border).
    period_src='bbox' — the object's own bbox extent along the axis
        (mode periodic_bbox; traced on 9b30e358, a block tiled upward).

    None when the period is undefined, the direction is unknown, or the
    continuation adds nothing."""
    if direction not in _UNIT or not cell_colors:
        return None
    dr, dc = _UNIT[direction]
    axis = "v" if dr else "h"
    if period_src == "self":
        period = self_period(cell_colors, axis)
    elif period_src == "bbox":
        vals = [c[0] if axis == "v" else c[1] for c in cell_colors]
        period = max(vals) - min(vals) + 1
    else:
        return None
    if not period or period < 1:
        return None
    h, w = bounds
    added: dict = {}
    limit = max(h, w) // period + 2
    for k in range(1, limit + 1):
        any_in_bounds = False
        for (r, c), col in cell_colors.items():
            nr, nc = r + dr * k * period, c + dc * k * period
            if 0 <= nr < h and 0 <= nc < w:
                any_in_bounds = True
                if (nr, nc) not in cell_colors:
                    added[(nr, nc)] = int(col)
        if not any_in_bounds:
            break
    return added or None


def grow_frame_minority(cell_colors: dict,
                        bounds: tuple[int, int]) -> Optional[dict]:
    """Added cells for mode=frame_minority: a SOLID rectangular ring around
    the object's bbox whose THICKNESS is the number of the object's
    minority-colour cells and whose colour IS that minority colour — both
    derived by counting, no literals (traced on 52fd389e: 1 minority cell ->
    thickness 1, 2 -> 2, 3 -> 3, verified on four objects).

    None unless the object has exactly two colours with an unambiguous
    minority, or when the ring would fall off the grid (undefined there
    rather than silently clipped — clipping would make the mode fit
    train pairs it cannot reproduce)."""
    if not cell_colors:
        return None
    counts: dict[int, int] = {}
    for col in cell_colors.values():
        counts[int(col)] = counts.get(int(col), 0) + 1
    if len(counts) != 2:
        return None
    ordered = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))
    (minor, n_minor), (major, n_major) = ordered[0], ordered[1]
    if n_minor >= n_major:
        return None                     # no unambiguous minority
    thickness = int(n_minor)
    rows = [r for r, _ in cell_colors]
    cols = [c for _, c in cell_colors]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    h, w = bounds
    added: dict = {}
    for r in range(r0 - thickness, r1 + thickness + 1):
        for c in range(c0 - thickness, c1 + thickness + 1):
            if r0 <= r <= r1 and c0 <= c <= c1:
                continue
            if not (0 <= r < h and 0 <= c < w):
                return None
            added[(r, c)] = int(minor)
    return added or None


# ---------------------------------------------------------------------------
# Round 20 (ARC_RAY_EXT): GRID-AWARE growth.
#
# Every mode above is a pure function of (cells, bounds).  The R20 traces
# showed that the census's "extension_beyond_objects" blocker is exactly the
# absence of the SCENE from this path: obstacle-conditional stopping and
# background-only painting are undefinable without the grid.  The three modes
# below take the input grid as an extra argument and derive the background
# from it at render time; every other parameter is a direction SYMBOL or a
# colour slot.  None of them stores a cell list.
# ---------------------------------------------------------------------------

#: Round-20 grid-aware modes (the ARC_RAY_EXT-gated subset of GROW_MODES).
RAY_EXT_MODES: tuple[str, ...] = ("cross_center", "cavity_leak",
                                  "ray_deflect")


def _ray_ext_enabled() -> bool:
    """Round-20 env gate.  Read at call time (never cached) so the flag can
    be flipped inside a process; the OFF path costs one dict lookup and the
    grid-aware modes are then never detected, induced, rendered, or
    enumerated."""
    import os
    return os.environ.get("ARC_RAY_EXT", "") not in ("", "0")


def as_rows(grid: Any) -> Optional[tuple]:
    """Normalize a grid (numpy array, Grid, or nested sequence) to a tuple of
    tuples of ints.  None passes through as None — the grid-aware modes are
    simply undefined without a scene."""
    if grid is None:
        return None
    if isinstance(grid, tuple) and grid and isinstance(grid[0], tuple):
        return grid
    rows = getattr(grid, "to_numpy", None)
    if rows is not None:
        grid = grid.to_numpy()
    try:
        return tuple(tuple(int(v) for v in row) for row in grid)
    except TypeError:
        return None


def grid_background(rows: tuple) -> int:
    """The grid's background = its most common colour (ties -> lowest).
    DERIVED from the scene at render time, so it is re-computed for the test
    input exactly as it was for the train inputs — never a stored literal."""
    counts: dict[int, int] = {}
    for row in rows:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    return min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def grow_cross_center(cells: frozenset | set, grid: Any,
                      color: int) -> Optional[dict]:
    """Added cells for mode=cross_center: the FULL grid row and FULL grid
    column through the object's bbox CENTRE cell, painting BACKGROUND cells
    only (the object itself and every other object survive underneath).

    Traced on 41e4d17e.  Zero geometric parameters — the centre is read off
    the object's own bbox.  None (undefined) when the bbox has an even
    extent on either axis, i.e. when "the centre" is not a single cell:
    guessing there would let the mode fit pairs it cannot reproduce."""
    rows = as_rows(grid)
    if rows is None or not cells:
        return None
    h, w = len(rows), len(rows[0])
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    if (r1 - r0) % 2 or (c1 - c0) % 2:
        return None
    cr, cc = (r0 + r1) // 2, (c0 + c1) // 2
    if not (0 <= cr < h and 0 <= cc < w):
        return None
    bg = grid_background(rows)
    added: dict = {}
    for c in range(w):
        if (cr, c) not in cells and rows[cr][c] == bg:
            added[(cr, c)] = int(color)
    for r in range(h):
        if (r, cc) not in cells and rows[r][cc] == bg:
            added[(r, cc)] = int(color)
    return added or None


def grow_cavity_leak(cells: frozenset | set, grid: Any,
                     color: int) -> Optional[dict]:
    """Added cells for mode=cavity_leak: every background cell strictly
    inside the object's bbox, PLUS a ray extruded outward from every GAP in
    the object's bbox outline until it leaves the grid or meets the object.

    Traced on 292dd178: an almost-closed outline whose interior fill LEAKS
    through its own opening to the border.  The leak's width IS the gap's
    width — both read off the object, no literals.  None (undefined) when
    the object has no bbox cavity at all."""
    rows = as_rows(grid)
    if rows is None or not cells:
        return None
    h, w = len(rows), len(rows[0])
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    bg = grid_background(rows)
    inner = {(r, c) for r in range(r0 + 1, r1) for c in range(c0 + 1, c1)
             if (r, c) not in cells and 0 <= r < h and 0 <= c < w
             and rows[r][c] == bg}
    if not inner:
        return None
    added = {p: int(color) for p in inner}

    def leak(start, step):
        r, c = start
        while 0 <= r < h and 0 <= c < w:
            if (r, c) in cells or rows[r][c] != bg:
                return
            added[(r, c)] = int(color)
            r, c = r + step[0], c + step[1]

    for c in range(c0, c1 + 1):
        if (r0, c) not in cells:
            leak((r0, c), (-1, 0))
        if (r1, c) not in cells:
            leak((r1, c), (1, 0))
    for r in range(r0, r1 + 1):
        if (r, c0) not in cells:
            leak((r, c0), (0, -1))
        if (r, c1) not in cells:
            leak((r, c1), (0, 1))
    return added or None


def grow_ray_deflect(cells: frozenset | set, grid: Any, direction: str,
                     color: int) -> Optional[dict]:
    """Added cells for mode=ray_deflect: extrude the object's leading
    silhouette in ``direction``; a lane blocked by a non-background obstacle
    steps sideways along the obstacle's near face to the NEARER free side and
    continues from there.

    Traced on c87289bb.  The lateral step is the mode's only free choice and
    it is fully determined: the strictly-nearer side wins, and a TIE resolves
    to the POSITIVE lateral direction.  That tie rule was FALSIFIED into
    existence — the opposite spelling reproduces pairs 0/1 exactly and fails
    pairs 2/3, whose deflections are both ties.  Only parameter: a direction
    SYMBOL (plus the colour slot every GROW mode has)."""
    rows = as_rows(grid)
    if rows is None or not cells or direction not in _UNIT:
        return None
    dr, dc = _UNIT[direction]
    h, w = len(rows), len(rows[0])
    bg = grid_background(rows)
    step = dr + dc                       # +1 forward, -1 backward
    lane_axis = 1 if dr else 0           # lanes indexed by the OTHER axis
    # leading edge per lane
    lanes: dict[int, int] = {}
    for cell in cells:
        k, v = cell[lane_axis], cell[1 - lane_axis]
        if k not in lanes or step * v > step * lanes[k]:
            lanes[k] = v

    def at(k, v):
        return (v, k) if dr else (k, v)

    def free(p):
        return (0 <= p[0] < h and 0 <= p[1] < w
                and p not in cells and rows[p[0]][p[1]] == bg)

    def obstacle_span(p):
        """(lo, hi) lane-extent of the 4-connected non-bg component at p."""
        seen, stack = {p}, [p]
        while stack:
            q = stack.pop()
            for d in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                n = (q[0] + d[0], q[1] + d[1])
                if (0 <= n[0] < h and 0 <= n[1] < w and n not in seen
                        and n not in cells and rows[n[0]][n[1]] != bg):
                    seen.add(n)
                    stack.append(n)
        ks = [q[lane_axis] for q in seen]
        return min(ks), max(ks)

    lane_limit = w if dr else h
    added: dict = {}
    frontier = sorted(lanes.items())
    guard = 0
    while frontier and guard <= 4 * h * w:
        guard += 1
        k, v = frontier.pop()
        nv = v + step
        p = at(k, nv)
        if not (0 <= p[0] < h and 0 <= p[1] < w) or p in cells:
            continue
        if rows[p[0]][p[1]] == bg:
            if p not in added:
                added[p] = int(color)
                frontier.append((k, nv))
            continue
        lo, hi = obstacle_span(p)
        left_exit, right_exit = lo - 1, hi + 1
        d_left, d_right = k - left_exit, right_exit - k
        order = ([left_exit, right_exit] if d_left < d_right
                 else [right_exit, left_exit])
        for exit_k in order:
            if not (0 <= exit_k < lane_limit):
                continue
            lat = 1 if exit_k > k else -1
            walk, ok = k, True
            path = []
            while walk != exit_k:
                walk += lat
                q = at(walk, v)
                if not free(q):
                    ok = False
                    break
                path.append(q)
            if ok:
                for q in path:
                    added.setdefault(q, int(color))
                frontier.append((exit_k, v))
                break
    if guard > 4 * h * w:
        return None                      # non-terminating scene: undefined
    return added or None


def added_pattern(in_cells: frozenset | set, added: dict) -> tuple:
    """Canonical bbox-origin-relative encoding of an added-cell dict:
    sorted tuple of ((dr, dc), color) — hashable + JSON-round-trippable
    through the expression __tuple__ machinery."""
    rows = [r for r, _ in in_cells]
    cols = [c for _, c in in_cells]
    r0, c0 = min(rows), min(cols)
    return tuple(sorted(((int(r - r0), int(c - c0)), int(col))
                        for (r, c), col in added.items()))


def pattern_cells(in_cells: frozenset | set, pattern: Any,
                  color: Optional[int] = None) -> dict:
    """Inverse of added_pattern: absolute added cells for a pattern.

    Two encodings (round 4, color abstraction): entries are
    ((dr, dc), col) pairs when ``color`` is None (legacy colored pattern),
    or bare (dr, dc) offsets painted with ``color`` — the color-abstracted
    form whose color is a full expression slot at induction time (so
    appendage/growth color can be relational, e.g. the host's own color)."""
    rows = [r for r, _ in in_cells]
    cols = [c for _, c in in_cells]
    r0, c0 = min(rows), min(cols)
    out: dict = {}
    for entry in pattern:
        if color is None:
            (dr, dc), col = entry
        else:
            dr, dc = entry
            col = color
        out[(r0 + int(dr), c0 + int(dc))] = int(col)
    return out


def mask_pattern(in_cells: frozenset | set, added: dict) -> tuple:
    """Color-abstracted encoding: sorted tuple of bare (dr, dc) offsets."""
    rows = [r for r, _ in in_cells]
    cols = [c for _, c in in_cells]
    r0, c0 = min(rows), min(cols)
    return tuple(sorted((int(r - r0), int(c - c0)) for (r, c) in added))


def _hole_fill_observation(cells, added: dict):
    """GROW params for "the enclosed regions were filled", or None.

    Requires every added cell to lie in an enclosed region and every touched
    region to be filled solid with one colour.  ``hole_colors`` records the
    per-region (key -> colour) observations for each candidate key feature;
    the inducer merges them across members into one induced map."""
    class _Holder:
        __slots__ = ("cells",)

        def __init__(self, c):
            self.cells = frozenset(c)

    regions = enclosed_hole_regions(_Holder(cells))
    if not regions:
        return None
    remaining = dict(added)
    observed: dict = {f: {} for f in HOLE_FEATURES}
    for region in regions:
        got = {cell: remaining.pop(cell) for cell in region if cell in remaining}
        if not got:
            continue
        if len(got) != len(region):
            return None                      # partial fill: not this mode
        colors = set(got.values())
        if len(colors) != 1:
            return None                      # multicolour region
        col = int(next(iter(colors)))
        for feat in HOLE_FEATURES:
            table = observed.get(feat)
            if table is None:            # this key feature already conflicted
                continue
            key = hole_feature_value(region, feat)
            if table.get(key, col) != col:
                observed[feat] = None    # same key, two colours: not a function
            else:
                table[key] = col
    if remaining:
        return None                          # cells outside every region
    usable = tuple((f, tuple(sorted(m.items(), key=lambda kv: repr(kv[0]))))
                   for f in HOLE_FEATURES
                   for m in (observed.get(f),) if m)
    if not usable:
        return None
    # hashable + JSON-round-trippable: raw params feed signature keys
    return {"mode": "fill_holes", "hole_colors": usable}


def detect_grow(in_cc: dict, out_cc: dict,
                bounds: tuple[int, int],
                grid: Any = None) -> Optional[dict]:
    """Raw GROW params when out ⊇ in (cells AND colors preserved) with a
    non-empty exactly-reproducible addition; None otherwise.

    Round 4: a bbox-shifted superset (the object MOVED and grew) is also
    accepted — params then carry the translation as dr/dc and every mode is
    detected in the moved frame (render order: translate, then grow).

    Tries the generic modes in preference order and verifies each candidate
    reproduces the added set EXACTLY; the pattern fallback is exact by
    construction.  Deterministic (fixed mode/direction/conn order)."""
    if not in_cc or len(out_cc) <= len(in_cc):
        return None
    shift = (0, 0)
    contained = all(out_cc.get(cell) == col for cell, col in in_cc.items())
    if not contained:
        # translate+grow: candidate shifts map the input's first cell onto
        # every same-color output cell; the smallest shift (|dr|+|dc|, then
        # dr, dc — deterministic) whose moved copy is contained in the
        # output wins.  Growth may extend the bbox in any direction, so a
        # bbox-origin shift alone is NOT sufficient.
        (ar, ac), acol = sorted(in_cc.items())[0]
        candidates = sorted(
            ((r - ar, c - ac) for (r, c), col in out_cc.items()
             if col == acol),
            key=lambda v: (abs(v[0]) + abs(v[1]), v[0], v[1]))[:64]
        for dr, dc in candidates:
            if (dr, dc) == (0, 0):
                continue
            moved = {(r + dr, c + dc): col for (r, c), col in in_cc.items()}
            if all(out_cc.get(cell) == col for cell, col in moved.items()):
                shift = (dr, dc)
                in_cc = moved
                break
        else:
            return None
    added = {cell: col for cell, col in out_cc.items() if cell not in in_cc}
    cells = set(in_cc)

    def _modes() -> dict:
        colors = set(added.values())
        if len(colors) == 1:
            color = int(next(iter(colors)))
            if grow_fill_interior(cells, color) == added:
                return {"mode": "fill_interior", "color": color}
            for conn in (4, 8):
                if grow_halo(cells, color, conn, bounds) == added:
                    return {"mode": "halo", "color": color, "conn": conn}
            for direction in ("up", "down", "left", "right"):
                to_border = grow_ray(cells, direction, color, None, bounds)
                if to_border == added:
                    return {"mode": "ray", "direction": direction,
                            "color": color}
                if added and set(added) <= set(to_border):
                    dr, dc = _UNIT[direction]
                    # fixed length: max extrusion distance observed
                    dist = max(
                        min(abs(p[0] - q[0]) if dc == 0 else abs(p[1] - q[1])
                            for q in cells
                            if (dc == 0 and q[1] == p[1]) or
                               (dr == 0 and q[0] == p[0]))
                        for p in added
                        if any((dc == 0 and q[1] == p[1]) or
                               (dr == 0 and q[0] == p[0]) for q in cells))
                    if grow_ray(cells, direction, color, dist,
                                bounds) == added:
                        return {"mode": "ray", "direction": direction,
                                "color": color, "length": int(dist)}
        # Relational spellings (round 3) — tried BEFORE the constant-pattern
        # fallback; colors come from mirrored source cells, never literals.
        for axis in ("horizontal", "vertical", "diag_main", "diag_anti"):
            if grow_symmetry_complete(in_cc, axis) == added:
                return {"mode": "symmetry_complete", "axis": axis}
        for direction in ("up", "down", "left", "right"):
            if grow_mirror_edge(in_cc, direction, bounds) == added:
                return {"mode": "mirror_edge", "direction": direction}
        # Round 19 (ARC_PATTERN_DERIVE): derived spellings of what would
        # otherwise be memorized as a constant cell list.  Tried here — after
        # every pre-existing mode, before the pattern fallback — so the gate
        # can only ever REPLACE a constant-pattern memorization, never
        # displace an already-working relational mode.  Zero cost when off.
        if _pattern_derive_enabled():
            for direction in ("up", "down", "left", "right"):
                for period_src in ("self", "bbox"):
                    if grow_periodic(in_cc, direction, bounds,
                                     period_src) == added:
                        return {"mode": f"periodic_{period_src}",
                                "direction": direction}
            if grow_frame_minority(in_cc, bounds) == added:
                return {"mode": "frame_minority"}
        # Round 20 (ARC_RAY_EXT): grid-aware spellings.  Same placement
        # discipline as round 19 — after every pre-existing mode, before the
        # pattern fallback — so the gate can only ever REPLACE a constant
        # memorization, never displace a working relational mode.  Requires
        # a scene: without `grid` these modes are simply undefined, which is
        # also the zero-cost path for every caller that has no grid.
        # A SHIFTED object is excluded: the grid-aware modes read obstacles
        # off the input scene, where the object still sits at its original
        # position, so a moved frame would consult the wrong neighbourhood.
        if grid is not None and shift == (0, 0) and _ray_ext_enabled():
            colors3 = set(added.values())
            if len(colors3) == 1:
                col3 = int(next(iter(colors3)))
                if grow_cross_center(cells, grid, col3) == added:
                    return {"mode": "cross_center", "color": col3}
                if grow_cavity_leak(cells, grid, col3) == added:
                    return {"mode": "cavity_leak", "color": col3}
                for direction in ("up", "down", "left", "right"):
                    if grow_ray_deflect(cells, grid, direction,
                                        col3) == added:
                        return {"mode": "ray_deflect",
                                "direction": direction, "color": col3}
        # Expression-grammar round: the added cells are exactly this
        # object's enclosed regions, each one solid.  Recorded as the
        # per-region key->colour observation the inducer merges across
        # members into one induced map (no cell is stored).
        if _expr_grammar_enabled():
            obs = _hole_fill_observation(cells, added)
            if obs is not None:
                return obs
        colors2 = set(added.values())
        if len(colors2) == 1:
            # color-abstracted pattern (round 4): mask offsets + a color
            # SLOT — induction may fill it relationally (host color, maps)
            return {"mode": "pattern",
                    "pattern": mask_pattern(cells, added),
                    "color": int(next(iter(colors2)))}
        return {"mode": "pattern", "pattern": added_pattern(cells, added)}

    params = _modes()
    if shift != (0, 0):
        if params["mode"] == "pattern":
            # A MOVED object with an arbitrary added-cell pattern is a
            # matching artifact (an unrelated object glommed onto a moved
            # one — e.g. a merged multicolor scene), not growth: the 1-cell
            # "pattern" memorizer is MDL-cheaper than the true composed
            # program and would steal the canonical ranking (found via the
            # two-pass composition regression).  Only mode-detected growth
            # (fill/halo/ray/symmetry/mirror) may combine with motion.
            return None
        params["dr"], params["dc"] = int(shift[0]), int(shift[1])
    return params


def connect_segment(a_cells, b_cells,
                    bounds: tuple[int, int]) -> Optional[dict]:
    """M2 verb 1 geometry: the deterministic straight 1-wide segment
    between two objects — the cells strictly between their facing bbox
    edges, on the CENTER line of their projection overlap (ties round
    down).  Returns {cell: None} placeholders (color applied by caller)
    or None when the objects do not face each other on either axis or
    already touch.  Pure function of the two cell sets — fold-safe."""
    def rng(cells, i):
        vs = [c[i] for c in cells]
        return min(vs), max(vs)

    ar0, ar1 = rng(a_cells, 0); ac0, ac1 = rng(a_cells, 1)
    br0, br1 = rng(b_cells, 0); bc0, bc1 = rng(b_cells, 1)
    h, w = bounds
    # horizontal segment: row-projections overlap, column gap between them
    ro0, ro1 = max(ar0, br0), min(ar1, br1)
    if ro0 <= ro1:
        if ac1 < bc0 - 1:
            lo, hi = ac1 + 1, bc0 - 1
        elif bc1 < ac0 - 1:
            lo, hi = bc1 + 1, ac0 - 1
        else:
            lo = hi = None
        if lo is not None:
            row = (ro0 + ro1) // 2
            if 0 <= row < h:
                return {(row, c): None for c in range(lo, hi + 1)
                        if 0 <= c < w}
    # vertical segment: column-projections overlap, row gap between them
    co0, co1 = max(ac0, bc0), min(ac1, bc1)
    if co0 <= co1:
        if ar1 < br0 - 1:
            lo, hi = ar1 + 1, br0 - 1
        elif br1 < ar0 - 1:
            lo, hi = br1 + 1, ar0 - 1
        else:
            return None
        col = (co0 + co1) // 2
        if 0 <= col < w:
            return {(r, col): None for r in range(lo, hi + 1)
                    if 0 <= r < h}
    return None


def connect_l_path(a_cells, b_cells,
                   bounds: tuple[int, int],
                   turn: str = "h") -> Optional[dict]:
    """Round 22 (ARC_RAY_EXT): L-shaped Manhattan connector between two
    objects.  The path is an L (two axis-aligned legs meeting at a right
    angle) from the nearest point of A toward B, stopping one cell before
    B's nearest face.

    *turn* controls which leg comes first:
      "h" — horizontal leg from A's position to B's column, then vertical.
      "v" — vertical leg from A's position to B's row, then horizontal.

    Returns {cell: None} placeholders (color applied by caller) or None
    when the path is empty or the objects overlap/touch.
    Pure function of the two cell sets — fold-safe.
    Gated by ARC_RAY_EXT in all callers."""
    def center(cells):
        rs = [r for r, _ in cells]
        cs = [c for _, c in cells]
        return (min(rs) + max(rs)) // 2, (min(cs) + max(cs)) // 2

    h, w = bounds
    ar, ac = center(a_cells)
    br, bc = center(b_cells)
    if ar == br and ac == bc:
        return None

    out: dict = {}
    if turn == "h":
        # horizontal leg along A's row toward B's column
        c_step = 1 if bc > ac else -1
        for c in range(ac + c_step, bc + c_step, c_step):
            pos = (ar, c)
            if 0 <= pos[0] < h and 0 <= pos[1] < w and pos not in a_cells:
                out[pos] = None
        # vertical leg along B's column toward B's row (stop 1 before B)
        r_step = 1 if br > ar else -1
        for r in range(ar + r_step, br, r_step):
            pos = (r, bc)
            if 0 <= pos[0] < h and 0 <= pos[1] < w and pos not in b_cells:
                out[pos] = None
    elif turn == "v":
        # vertical leg along A's column toward B's row
        r_step = 1 if br > ar else -1
        for r in range(ar + r_step, br + r_step, r_step):
            pos = (r, ac)
            if 0 <= pos[0] < h and 0 <= pos[1] < w and pos not in a_cells:
                out[pos] = None
        # horizontal leg along B's row toward B's column (stop 1 before B)
        c_step = 1 if bc > ac else -1
        for c in range(ac + c_step, bc, c_step):
            pos = (br, c)
            if 0 <= pos[0] < h and 0 <= pos[1] < w and pos not in b_cells:
                out[pos] = None
    else:
        return None

    if not out:
        return None
    return out


def find_part_window(src_cc: dict, orphan_cc: dict) -> Optional[dict]:
    """M2 verb 2 detection: is the orphan an exact color-matching subwindow
    of the source object?  Returns raw params {window: (wr, wc, wh, ww)
    relative to the source bbox, placement: (dr, dc) = orphan bbox origin
    minus source bbox origin} or None.  Deterministic: smallest (wr, wc)
    window wins."""
    if not src_cc or not orphan_cc:
        return None
    sr0 = min(r for r, _ in src_cc); sc0 = min(c for _, c in src_cc)
    orr = min(r for r, _ in orphan_cc); oc = min(c for _, c in orphan_cc)
    oh = max(r for r, _ in orphan_cc) - orr + 1
    ow = max(c for _, c in orphan_cc) - oc + 1
    rel_orphan = {(r - orr, c - oc): col for (r, c), col in orphan_cc.items()}
    sh = max(r for r, _ in src_cc) - sr0 + 1
    sw = max(c for _, c in src_cc) - sc0 + 1
    if oh > sh or ow > sw:
        return None
    rel_src = {(r - sr0, c - sc0): col for (r, c), col in src_cc.items()}
    for wr in range(sh - oh + 1):
        for wc in range(sw - ow + 1):
            window = {(r, c): rel_src.get((wr + r, wc + c))
                      for (r, c) in rel_orphan}
            if window == rel_orphan:
                return {"window": (wr, wc, oh, ow),
                        "placement": (orr - sr0, oc - sc0)}
    return None


def render_part(src_cc: dict, window, placement) -> dict:
    """Absolute cells of the copied part: the window of the source stamped
    at source-bbox-origin + placement."""
    sr0 = min(r for r, _ in src_cc); sc0 = min(c for _, c in src_cc)
    wr, wc, wh, ww = window
    dr, dc = placement
    out: dict = {}
    for (r, c), col in src_cc.items():
        rr, rc = r - sr0, c - sc0
        if wr <= rr < wr + wh and wc <= rc < wc + ww:
            out[(sr0 + dr + (rr - wr), sc0 + dc + (rc - wc))] = int(col)
    return out


# ---------------------------------------------------------------------------
# EXTRACT_PART helpers (round 15): input-grid sub-region extraction
# ---------------------------------------------------------------------------

def _dihedral_transform(arr: "np.ndarray", k: int, flip: bool) -> "np.ndarray":
    """Apply a dihedral transform: optional fliplr then rot90^k.
    k in 0..3, flip in {True, False} -> 8 transforms (D4 group).
    Returns a contiguous array."""
    import numpy as np
    a = np.asarray(arr)
    if flip:
        a = np.fliplr(a)
    a = np.rot90(a, k)
    return np.ascontiguousarray(a)


def _dihedral_inverse(arr: "np.ndarray", k: int, flip: bool) -> "np.ndarray":
    """Inverse of _dihedral_transform(arr, k, flip)."""
    import numpy as np
    a = np.asarray(arr)
    a = np.rot90(a, -k)
    if flip:
        a = np.fliplr(a)
    return np.ascontiguousarray(a)


def find_extract_region(grid: "np.ndarray",
                        orphan_cc: dict) -> "Optional[list[dict]]":
    """Round 15 EXTRACT_PART detection: is the orphan's pixel pattern an exact
    (or dihedral-transformed) sub-region of the input grid?

    Searches all 8 dihedral orientations of the orphan against the grid.
    Returns a list of candidate dicts (sorted: identity transform first,
    then by (k, flip, r0, c0)):
        {source_bbox: (r0, c0, r1, c1),  # in grid coords
         transform_k: int,                 # rot90 count applied to source to get orphan
         transform_flip: bool,             # fliplr before rot
         placement: (pr, pc)}              # orphan bbox origin
    or None if no match."""
    import numpy as np
    if not orphan_cc:
        return None
    # Build orphan patch as a dense array
    orr = min(r for r, _ in orphan_cc)
    oc = min(c for _, c in orphan_cc)
    oh = max(r for r, _ in orphan_cc) - orr + 1
    ow = max(c for _, c in orphan_cc) - oc + 1
    orphan_arr = np.full((oh, ow), -1, dtype=np.int32)
    for (r, c), col in orphan_cc.items():
        orphan_arr[r - orr, c - oc] = col
    orphan_mask = orphan_arr >= 0

    gh, gw = grid.shape
    candidates: list[dict] = []

    for k in range(4):
        for flip in (False, True):
            # The INVERSE transform maps the orphan back to how it sits in the
            # source grid.  So we transform the orphan by the INVERSE and slide
            # it over the grid looking for an exact match.
            inv_arr = _dihedral_inverse(orphan_arr, k, flip)
            inv_mask = inv_arr >= 0
            sh, sw = inv_arr.shape
            if sh > gh or sw > gw:
                continue
            for r0 in range(gh - sh + 1):
                for c0 in range(gw - sw + 1):
                    patch = grid[r0:r0 + sh, c0:c0 + sw]
                    if np.all((patch == inv_arr) | ~inv_mask):
                        candidates.append({
                            "source_bbox": (r0, c0, r0 + sh, c0 + sw),
                            "transform_k": k,
                            "transform_flip": flip,
                            "placement": (orr, oc),
                        })

    if not candidates:
        return None
    # Sort: identity first, then by coordinates
    candidates.sort(key=lambda c: (c["transform_k"] != 0 or c["transform_flip"],
                                   c["transform_k"], c["transform_flip"],
                                   c["source_bbox"]))
    return candidates


def render_extract_part(grid: "np.ndarray", source_bbox: tuple,
                        transform_k: int, transform_flip: bool,
                        placement: tuple) -> dict:
    """Render an EXTRACT_PART action: extract source_bbox from grid, apply
    dihedral transform, stamp at placement.  Returns {(r, c): color}."""
    import numpy as np
    r0, c0, r1, c1 = source_bbox
    patch = grid[r0:r1, c0:c1].copy()
    transformed = _dihedral_transform(patch, transform_k, transform_flip)
    th, tw = transformed.shape
    pr, pc = placement
    out: dict = {}
    for dr in range(th):
        for dc in range(tw):
            val = int(transformed[dr, dc])
            out[(pr + dr, pc + dc)] = val
    return out


def enclosed_hole_offsets(obj, gctx) -> tuple:
    """Bbox-origin-relative offsets of the cells this object encloses.

    Same topology as the ``enclosed_region_count`` feature: 4-connected
    components of non-object cells inside the bbox that cannot reach the
    bbox boundary ring.  Returned in the color-abstracted pattern encoding
    (bare offsets), so the GROW ``pattern`` slot can paint them with any
    COLOR expression.  Deterministic order; empty when nothing is enclosed.
    """
    cells = obj.cells
    if not cells:
        return ()
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    r0, c0, r1, c1 = min(rows), min(cols), max(rows) + 1, max(cols) + 1
    h, w = r1 - r0, c1 - c0
    if h <= 0 or w <= 0:
        return ()
    occupied = {(r - r0, c - c0) for r, c in cells}
    # flood the complement from a 1-cell pad ring: whatever it cannot reach
    # is enclosed
    reached = set()
    stack = [(-1, -1)]
    reached.add((-1, -1))
    while stack:
        r, c = stack.pop()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if -1 <= nr <= h and -1 <= nc <= w \
                    and (nr, nc) not in reached \
                    and (nr, nc) not in occupied:
                reached.add((nr, nc))
                stack.append((nr, nc))
    return tuple(sorted((r, c) for r in range(h) for c in range(w)
                        if (r, c) not in occupied and (r, c) not in reached))


def _expr_grammar_enabled() -> bool:
    """Expression-grammar round gate (same call-time-read idiom as
    ``_ray_ext_enabled``): with it off, computed-region patterns are never
    proposed, enumerated, or rendered."""
    import os
    return os.environ.get("ARC_EXPR_GRAMMAR", "") not in ("", "0")


def enclosed_hole_regions(obj) -> list:
    """The object's enclosed regions as absolute cell sets, in deterministic
    order (by top-left corner).  Same topology as ``enclosed_hole_offsets``,
    kept separate so each region can be treated as its own fill target."""
    cells = obj.cells
    if not cells:
        return []
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    r0, c0 = min(rows), min(cols)
    h, w = max(rows) + 1 - r0, max(cols) + 1 - c0
    occupied = {(r - r0, c - c0) for r, c in cells}
    reached = set()
    stack = [(-1, -1)]
    reached.add((-1, -1))
    while stack:
        r, c = stack.pop()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if -1 <= nr <= h and -1 <= nc <= w and (nr, nc) not in reached \
                    and (nr, nc) not in occupied:
                reached.add((nr, nc))
                stack.append((nr, nc))
    inside = {(r, c) for r in range(h) for c in range(w)
              if (r, c) not in occupied and (r, c) not in reached}
    regions = []
    seen: set = set()
    for cell in sorted(inside):
        if cell in seen:
            continue
        comp = {cell}
        seen.add(cell)
        stack = [cell]
        while stack:
            r, c = stack.pop()
            for nb in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if nb in inside and nb not in seen:
                    seen.add(nb)
                    comp.add(nb)
                    stack.append(nb)
        regions.append(frozenset((r + r0, c + c0) for r, c in comp))
    return sorted(regions, key=lambda s: min(s))


#: Region features a hole fill may key its colour on.  All are computed from
#: the region itself, so a fold that never saw the held-out object derives
#: the same key — the property that makes the induced map LOO-stable.
HOLE_FEATURES: tuple = ("area", "hw", "shape")


def hole_feature_value(region: frozenset, feature: str):
    """Deterministic key for one enclosed region."""
    rows = [r for r, _ in region]
    cols = [c for _, c in region]
    if feature == "area":
        return len(region)
    r0, c0 = min(rows), min(cols)
    if feature == "hw":
        return (max(rows) + 1 - r0, max(cols) + 1 - c0)
    if feature == "shape":
        return tuple(sorted((r - r0, c - c0) for r, c in region))
    raise ValueError(f"unknown hole feature {feature!r}")


def grow_fill_holes(obj, feature: str, mapping: dict) -> Optional[dict]:
    """Paint each enclosed region with ``mapping[key(region)]``.

    Regions and their keys are computed from the object at apply time; only
    the key->colour table is induced.  Returns None when the object encloses
    nothing (the mode is undefined there) and skips regions whose key is
    absent from the table (an unseen key contributes no cells rather than
    crashing a fold, matching the map-fallback rule)."""
    regions = enclosed_hole_regions(obj)
    if not regions:
        return None
    out: dict = {}
    for region in regions:
        key = hole_feature_value(region, feature)
        if key not in mapping:
            continue
        col = int(mapping[key])
        for cell in region:
            out[cell] = col
    return out or None
