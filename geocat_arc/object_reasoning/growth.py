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
GROW_MODES: tuple[str, ...] = ("fill_interior", "halo", "ray",
                               "symmetry_complete", "mirror_edge", "pattern")

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


def detect_grow(in_cc: dict, out_cc: dict,
                bounds: tuple[int, int]) -> Optional[dict]:
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
