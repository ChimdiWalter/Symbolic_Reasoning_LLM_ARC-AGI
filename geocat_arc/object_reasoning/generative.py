"""Round-17 generative-composite path (ARC_GENERATIVE).

Renderer + inducer for GenerativeProgram: segment the INPUT, apply a
generator per input object (from the GROW vocabulary — ray/halo/fill/
mirror_edge/symmetry_complete), paint ALL generators onto one canvas,
require pixel-exact match with the output on every train pair.

The path bypasses object-to-object correspondence entirely — designed
for FUSED-OUTPUT tasks where n input objects produce 1-2 giant output
objects (the generators' emissions merge).  Fusion-signature precondition
bounds cost: n_out < n_in on every pair for some variant.

Env-gated: ARC_GENERATIVE=1 (zero cost when off).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject

from .growth import (
    grow_fill_interior,
    grow_cavity_leak,
    grow_cross_center,
    grow_frame_minority,
    grow_ray_deflect,
    grow_halo,
    grow_mirror_edge,
    grow_periodic,
    grow_ray,
    grow_symmetry_complete,
    _pattern_derive_enabled,
    _ray_ext_enabled,
    _UNIT,
)
from .segmentation import (
    SEGMENTATION_TRIAL_ORDER,
    background_for,
    segment,
)
from .types import (
    GenerativeProgram,
    GridPair,
    SegmentationVariant,
    cell_colors_of,
)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _find_target_object(
    source_cells: frozenset,
    target_pred: dict,
    all_objects: list,
) -> Optional[ARCObject]:
    """Find the target object matching a relational predicate.

    target_pred types:
      {"type": "largest"}        - largest non-source object
      {"type": "color", "color": int}  - nearest object of given color
      {"type": "unique_color", "color": int} - the unique object of given color
    """
    ttype = target_pred.get("type", "largest")

    if ttype == "largest":
        candidates = [o for o in all_objects
                      if frozenset(o.cells) != source_cells]
        if not candidates:
            return None
        return max(candidates, key=lambda o: len(o.cells))

    target_color = target_pred.get("color", 0)

    if ttype == "color":
        candidates = [o for o in all_objects
                      if o.color == target_color
                      and frozenset(o.cells) != source_cells]
        if not candidates:
            return None
        # Nearest by Manhattan distance between centroids
        n_src = max(1, len(source_cells))
        src_r = sum(r for r, _ in source_cells) / n_src
        src_c = sum(c for _, c in source_cells) / n_src
        def _dist(o: ARCObject) -> float:
            tc = list(o.cells)
            n = max(1, len(tc))
            return abs(sum(r for r, _ in tc) / n - src_r) + \
                   abs(sum(c for _, c in tc) / n - src_c)
        return min(candidates, key=_dist)

    if ttype == "unique_color":
        candidates = [o for o in all_objects if o.color == target_color]
        if len(candidates) == 1:
            if frozenset(candidates[0].cells) == source_cells:
                return None
            return candidates[0]
        return None

    return None


def _compute_relational_direction(
    source_cells: frozenset,
    target_pred: dict,
    direction_mode: str,
    all_objects: list,
    self_obj: ARCObject,
) -> tuple[int, int]:
    """Compute a unit direction vector relative to a target object.

    direction_mode:
      "toward"        - toward the target (dominant axis)
      "away"          - away from the target
      "perpendicular" - 90-degree CW rotation of the toward direction

    Returns (dr, dc) as a cardinal unit vector, or (0, 0) if no valid
    target is found.
    """
    target_obj = _find_target_object(source_cells, target_pred,
                                     all_objects)
    if target_obj is None:
        return (0, 0)

    # Compute centroids
    n_src = max(1, len(source_cells))
    src_r = sum(r for r, _ in source_cells) / n_src
    src_c = sum(c for _, c in source_cells) / n_src
    tgt_cells = list(target_obj.cells)
    n_tgt = max(1, len(tgt_cells))
    tgt_r = sum(r for r, _ in tgt_cells) / n_tgt
    tgt_c = sum(c for _, c in tgt_cells) / n_tgt

    dr = tgt_r - src_r
    dc = tgt_c - src_c

    if abs(dr) < 1e-9 and abs(dc) < 1e-9:
        return (0, 0)

    # Primary direction along dominant axis
    if abs(dr) >= abs(dc):
        primary = (1 if dr > 0 else -1, 0)
    else:
        primary = (0, 1 if dc > 0 else -1)

    if direction_mode == "toward":
        return primary
    if direction_mode == "away":
        return (-primary[0], -primary[1])
    if direction_mode == "perpendicular":
        # 90-degree CW rotation: (dr, dc) -> (dc, -dr)
        perp = (primary[1], -primary[0])
        return perp if perp != (0, 0) else (0, 1)

    return (0, 0)


def _apply_generator(rule: dict, obj: ARCObject,
                     bounds: tuple[int, int],
                     grid_array: Optional[np.ndarray] = None,
                     include_source: bool = False,
                     all_objects: Optional[list] = None) -> dict:
    """Apply a single generator rule to an object, returning {cell: color}.

    The generator vocabulary mirrors growth.py's GROW_MODES plus
    round-17 extensions:
      ray, halo, fill_interior, mirror_edge, symmetry_complete,
      ray_until_obstacle, ray_through_absorbed, row_line, col_line,
      cross_line.

    When ``include_source`` is True, the generated cells also cover the
    object's own cells (used with delete_source programs so the emitting
    object gets repainted by its generator).
    """
    kind = rule["kind"]
    cells_fs = frozenset(obj.cells)
    cc = cell_colors_of(obj)
    h, w = bounds
    # When include_source, use empty set so generators paint over source
    skip_cells = frozenset() if include_source else cells_fs

    if kind == "ray":
        direction = rule["direction"]
        color = rule.get("color", obj.color)
        length = rule.get("length", None)  # None = to border
        return grow_ray(cells_fs, direction, int(color), length, bounds)

    if kind == "ray_until_obstacle":
        # Ray that stops at the first non-background cell (exclusive).
        direction = rule["direction"]
        color = rule.get("color", obj.color)
        bg = rule.get("bg", 0)
        dr, dc = _UNIT.get(direction, (0, 0))
        if (dr, dc) == (0, 0):
            return {}
        added: dict = {}
        for r0, c0 in cells_fs:
            r, c = r0 + dr, c0 + dc
            while 0 <= r < h and 0 <= c < w:
                if grid_array is not None and grid_array[r, c] != bg:
                    break
                if (r, c) in cells_fs:
                    break
                added[(r, c)] = int(color)
                r += dr
                c += dc
        return added

    if kind == "ray_through_absorbed":
        # R17b: ray goes through the FIRST non-background obstacle,
        # absorbing its color. Segment before obstacle = source color;
        # segment from obstacle onward to border = obstacle's color.
        direction = rule["direction"]
        color = rule.get("color", obj.color)
        bg = rule.get("bg", 0)
        dr, dc = _UNIT.get(direction, (0, 0))
        if (dr, dc) == (0, 0):
            return {}
        added_rta: dict = {}
        for r0, c0 in cells_fs:
            r, c = r0 + dr, c0 + dc
            cur_color = int(color)
            absorbed = False
            while 0 <= r < h and 0 <= c < w:
                if (r, c) in cells_fs:
                    r += dr
                    c += dc
                    continue
                if grid_array is not None and not absorbed:
                    cell_val = int(grid_array[r, c])
                    if cell_val != bg:
                        cur_color = cell_val
                        absorbed = True
                added_rta[(r, c)] = cur_color
                r += dr
                c += dc
        return added_rta

    if kind == "row_line":
        # Full row line through every row the object occupies.
        color = rule.get("color", obj.color)
        added = {}
        rows_occupied = sorted(set(r for r, _ in obj.cells))
        for r in rows_occupied:
            for c in range(w):
                if (r, c) not in skip_cells:
                    added[(r, c)] = int(color)
        return added

    if kind == "col_line":
        # Full column line through every column the object occupies.
        color = rule.get("color", obj.color)
        added = {}
        cols_occupied = sorted(set(c for _, c in obj.cells))
        for c in cols_occupied:
            for r in range(h):
                if (r, c) not in skip_cells:
                    added[(r, c)] = int(color)
        return added

    if kind == "cross_line":
        # Full row AND column lines (cross) through the object.
        color = rule.get("color", obj.color)
        added = {}
        rows_occupied = sorted(set(r for r, _ in obj.cells))
        cols_occupied = sorted(set(c for _, c in obj.cells))
        for r in rows_occupied:
            for c in range(w):
                if (r, c) not in skip_cells:
                    added[(r, c)] = int(color)
        for c in cols_occupied:
            for r in range(h):
                if (r, c) not in skip_cells:
                    added[(r, c)] = int(color)
        return added

    if kind == "halo":
        color = rule.get("color", obj.color)
        conn = rule.get("conn", 4)
        return grow_halo(cells_fs, int(color), conn, bounds)

    if kind == "fill_interior":
        color = rule.get("color", obj.color)
        return grow_fill_interior(cells_fs, int(color))

    if kind == "mirror_edge":
        direction = rule["direction"]
        return grow_mirror_edge(cc, direction, bounds) or {}

    if kind == "symmetry_complete":
        axis = rule["axis"]
        return grow_symmetry_complete(cc, axis) or {}

    # R19: extensional pattern DERIVATION — the generator counterparts of the
    # GROW modes in growth.py.  Every parameter is re-derived from the object
    # at render time, so these survive LOO where a stored cell list dies.
    if kind in ("periodic_self", "periodic_bbox"):
        return grow_periodic(
            cc, rule["direction"], bounds,
            "self" if kind == "periodic_self" else "bbox") or {}

    if kind == "frame_minority":
        return grow_frame_minority(cc, bounds) or {}

    # R22 (ARC_RAY_EXT): falsification-verified on census exemplars.
    # line_periodic (0a938d79): the object emits its FULL row/col line
    # (axis chosen by grid orientation), repeated FORWARD at period
    # 2 * |separation from the other seed| until the border.  Every
    # parameter derived at render time; forward-only is the verified
    # spelling (backward repeats were falsified against ground truth).
    if kind == "line_periodic":
        if all_objects is None or len(all_objects) < 2:
            return {}
        others = [o for o in all_objects if frozenset(o.cells) != cells_fs]
        if not others:
            return {}
        color = int(rule.get("color", obj.color))
        axis = "row" if h >= w else "col"
        def _pos(o):
            rs = [r for r, _ in o.cells]
            cs = [c for _, c in o.cells]
            return min(rs) if axis == "row" else min(cs)
        p_self = _pos(obj)
        p_other = min((_pos(o) for o in others),
                      key=lambda p: abs(p - p_self))
        sep = abs(p_other - p_self)
        if sep == 0:
            return {}
        period = 2 * sep
        added: dict = {}
        limit = h if axis == "row" else w
        k = p_self
        while k < limit:
            if axis == "row":
                for c in range(w):
                    if (k, c) not in skip_cells:
                        added[(k, c)] = color
            else:
                for r in range(h):
                    if (r, k) not in skip_cells:
                        added[(r, k)] = color
            k += period
        return added

    # path_two_anchor (992798f6): the path leaves THIS object with one
    # diagonal step toward the target object, runs straight along the
    # dominant axis, then approaches the target on a 45-degree diagonal;
    # endpoints excluded.  Geometry fully derived; colour induced.
    if kind == "path_two_anchor":
        if all_objects is None or len(all_objects) < 2:
            return {}
        others = [o for o in all_objects if frozenset(o.cells) != cells_fs]
        if not others:
            return {}
        color = int(rule.get("color", obj.color))
        def _center(o):
            rs = [r for r, _ in o.cells]
            cs = [c for _, c in o.cells]
            return (min(rs), min(cs))
        # CANONICAL ROLES (992798f6's falsified rule): the source is the
        # HIGHER-colour seed of the pair, the target the lower — computed
        # from the scene, independent of which object hosts the rule, so
        # a uniform generator renders one identical path from either host.
        pair = [obj, min(others, key=lambda o: abs(_center(o)[0]
                - _center(obj)[0]) + abs(_center(o)[1] - _center(obj)[1]))]
        pair.sort(key=lambda o: -o.color)
        src, tgt = pair[0], pair[1]
        r0, c0 = _center(src)
        r1, c1 = _center(tgt)
        dr, dc = r1 - r0, c1 - c0
        if dr == 0 and dc == 0:
            return {}
        sr = (dr > 0) - (dr < 0)
        sc = (dc > 0) - (dc < 0)
        cells: list = []
        r, c = r0 + sr, c0 + sc          # one diagonal step off the source
        cells.append((r, c))
        guard = h + w + 2
        if abs(dr) >= abs(dc):           # vertical-dominant
            while abs(r1 - r) > abs(c1 - c) and guard > 0:
                r += sr; cells.append((r, c)); guard -= 1
            while (r, c) != (r1, c1) and guard > 0:
                r += sr; c += sc
                if (r, c) != (r1, c1):
                    cells.append((r, c))
                guard -= 1
        else:
            while abs(c1 - c) > abs(r1 - r) and guard > 0:
                c += sc; cells.append((r, c)); guard -= 1
            while (r, c) != (r1, c1) and guard > 0:
                r += sr; c += sc
                if (r, c) != (r1, c1):
                    cells.append((r, c))
                guard -= 1
        ends = {(r0, c0), (r1, c1)}
        return {cell: color for cell in cells
                if cell not in ends and cell not in skip_cells
                and 0 <= cell[0] < h and 0 <= cell[1] < w}

    # R20 (ARC_RAY_EXT): the GRID-AWARE counterparts of the growth.py modes.
    # They need the scene, so they are undefined without ``grid_array``.
    if kind in ("cross_center", "cavity_leak", "ray_deflect"):
        if grid_array is None:
            return {}
        color = int(rule.get("color", obj.color))
        if kind == "cross_center":
            return grow_cross_center(cells_fs, grid_array, color) or {}
        if kind == "cavity_leak":
            return grow_cavity_leak(cells_fs, grid_array, color) or {}
        return grow_ray_deflect(cells_fs, grid_array, rule["direction"],
                                color) or {}

    # R2: relational ray — direction computed at render time from scene objects
    if kind == "ray_relational":
        if all_objects is None:
            return {}
        direction_mode = rule.get("direction_mode", "toward")
        target_pred = rule.get("target_pred", {"type": "largest"})
        color = rule.get("color", obj.color)
        bg = rule.get("bg", 0)
        stop = rule.get("stop", "grid_border")
        absorbed = rule.get("absorbed", False)

        dr, dc = _compute_relational_direction(
            cells_fs, target_pred, direction_mode, all_objects, obj)
        if (dr, dc) == (0, 0):
            return {}

        added_rel: dict = {}
        for r0, c0 in cells_fs:
            r, c = r0 + dr, c0 + dc
            cur_color = int(color)
            hit_obstacle = False
            while 0 <= r < h and 0 <= c < w:
                if (r, c) in cells_fs:
                    r += dr
                    c += dc
                    continue
                if grid_array is not None:
                    cell_val = int(grid_array[r, c])
                    if stop == "first_nonbg" and cell_val != bg:
                        break
                    if absorbed and not hit_obstacle and cell_val != bg:
                        cur_color = cell_val
                        hit_obstacle = True
                added_rel[(r, c)] = cur_color
                r += dr
                c += dc
        return added_rel

    # R18: learned generator (hypothesis-language expression from
    # generator_mining.py); zero cost when learned_generators.json absent.
    if kind == "learned_generator":
        from .generator_mining import _apply_learned_generator
        return _apply_learned_generator(rule, obj, bounds,
                                        grid_array=grid_array,
                                        include_source=include_source)

    return {}


def _object_sort_key(obj: ARCObject) -> tuple:
    """Deterministic painter's-order key: top-to-bottom, left-to-right by
    bbox origin, then by cell count (largest last)."""
    rows = [r for r, _ in obj.cells]
    cols = [c for _, c in obj.cells]
    return (min(rows), min(cols), len(obj.cells))


def _selector_matches(sel: dict, obj: ARCObject, bg: int) -> bool:
    """Check whether a selector dict matches an object.

    Supported selectors:
      {} (empty)          -> matches all objects
      {"color": c}        -> matches objects with majority color == c
      {"min_size": n}     -> matches objects with >= n cells
      {"not_background": True} -> matches objects whose color != bg
    All conditions in the dict are ANDed.
    """
    if not sel:
        return True
    if "color" in sel and obj.color != sel["color"]:
        return False
    if "min_size" in sel and len(obj.cells) < sel["min_size"]:
        return False
    if sel.get("not_background") and obj.color == bg:
        return False
    return True


def render_generative(program: GenerativeProgram,
                      input_grid: Grid) -> Grid:
    """Execute a GenerativeProgram: segment the input, apply generators
    per object, composite onto canvas, return result."""
    variant = program.seg_variant
    bg = background_for(input_grid, variant)
    objects = segment(input_grid, variant, bg)
    h, w = input_grid.height, input_grid.width
    bounds = (h, w)
    grid_array = input_grid.to_numpy()

    # Canvas: copy of input or blank
    if program.canvas_policy == "blank":
        canvas = np.full((h, w), program.background, dtype=np.int32)
    else:
        canvas = grid_array.copy()

    # Sort objects for deterministic painter's order
    sorted_objs = sorted(objects, key=_object_sort_key)

    # If delete_source: blank emitting objects' cells on the canvas first
    if getattr(program, "delete_source", False):
        for obj in sorted_objs:
            # Only delete objects that match at least one generator selector
            for sel, _rule in program.generators:
                if _selector_matches(sel, obj, bg):
                    for (r, c) in obj.cells:
                        canvas[r, c] = program.background
                    break

    # Apply generators in GENERATOR-FIRST order: each generator rule is
    # applied across ALL matching objects before the next generator.
    # This makes the generator list order the painter's priority:
    # later generators in the list paint ON TOP of earlier ones.
    incl_src = getattr(program, "delete_source", False)

    # R17b: track which source-object colors painted each cell for
    # intersection_color post-processing
    ic = getattr(program, "intersection_color", None)
    # cell -> set of source-object colors that painted it
    cell_painters: dict[tuple[int, int], set[int]] = {} if ic is not None else {}

    for sel, rule in program.generators:
        for obj in sorted_objs:
            if _selector_matches(sel, obj, bg):
                added = _apply_generator(rule, obj, bounds,
                                         grid_array=grid_array,
                                         include_source=incl_src,
                                         all_objects=sorted_objs)
                for (r, c), color in added.items():
                    if 0 <= r < h and 0 <= c < w:
                        canvas[r, c] = int(color)
                        if ic is not None:
                            cell_painters.setdefault((r, c), set()).add(
                                obj.color)

    # R17b intersection_color: cells painted by generators from objects
    # of DIFFERENT colors get repainted with the intersection color.
    if ic is not None:
        for (r, c), colors in cell_painters.items():
            if len(colors) > 1:
                canvas[r, c] = int(ic)

    return Grid(canvas)


# ---------------------------------------------------------------------------
# Inducer
# ---------------------------------------------------------------------------

#: Generator vocabulary for induction: each entry is a function that
#: proposes candidate generator rules for one object given the target.
#: Returns a list of candidate rules (dicts with "kind" + params).

_DIRECTIONS = ("up", "down", "left", "right")
_AXES = ("horizontal", "vertical", "diag_main", "diag_anti")

# Maximum generator combinations to try (MAX_ACTION_CANDIDATES discipline)
_MAX_GEN_COMBOS = 512


def _candidate_generators_for_object(
    obj: ARCObject,
    target: np.ndarray,
    bg_in: int,
    bounds: tuple[int, int],
    grid_array: Optional[np.ndarray] = None,
    all_objects: Optional[list] = None,
) -> list[dict]:
    """Propose candidate generator rules for one object that contribute
    pixels matching the target.  Each candidate is scored by pixel
    agreement BEFORE combination — prune early."""
    cells_fs = frozenset(obj.cells)
    cc = cell_colors_of(obj)
    candidates = []

    # Collect all non-background colors in the target that are near this
    # object (within a generous radius = max grid dimension)
    target_colors = set(int(c) for c in np.unique(target) if c != bg_in)
    obj_colors = set(cc.values())

    # Try colors: object's own color(s) first, then target colors
    try_colors = sorted(obj_colors) + sorted(target_colors - obj_colors)

    for color in try_colors:
        # Ray in each direction
        for direction in _DIRECTIONS:
            # To border
            added = grow_ray(cells_fs, direction, color, None, bounds)
            if added:
                score = sum(1 for (r, c), cl in added.items()
                            if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                            and target[r, c] == cl)
                if score > 0:
                    candidates.append((score, len(added),
                                       {"kind": "ray", "direction": direction,
                                        "color": color}))

            # Fixed-length rays: try a few lengths
            for length in range(1, max(bounds) + 1):
                added = grow_ray(cells_fs, direction, color, length, bounds)
                if not added:
                    break
                score = sum(1 for (r, c), cl in added.items()
                            if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                            and target[r, c] == cl)
                if score == len(added) and score > 0:
                    candidates.append((score, len(added),
                                       {"kind": "ray", "direction": direction,
                                        "color": color, "length": length}))
                    break  # first perfect-length is enough

        # Ray until obstacle (stops at first non-bg cell)
        if grid_array is not None:
            for direction in _DIRECTIONS:
                dr, dc = _UNIT.get(direction, (0, 0))
                if (dr, dc) == (0, 0):
                    continue
                added_ruo: dict = {}
                for r0, c0 in cells_fs:
                    r, c = r0 + dr, c0 + dc
                    while 0 <= r < bounds[0] and 0 <= c < bounds[1]:
                        if grid_array[r, c] != bg_in:
                            break
                        if (r, c) in cells_fs:
                            break
                        added_ruo[(r, c)] = int(color)
                        r += dr
                        c += dc
                if added_ruo:
                    score = sum(1 for (r, c), cl in added_ruo.items()
                                if target[r, c] == cl)
                    if score > 0:
                        candidates.append((score, len(added_ruo),
                                           {"kind": "ray_until_obstacle",
                                            "direction": direction,
                                            "color": color}))

        # R17b: ray through absorbed (absorbs first obstacle's color)
        if grid_array is not None:
            for direction in _DIRECTIONS:
                dr, dc = _UNIT.get(direction, (0, 0))
                if (dr, dc) == (0, 0):
                    continue
                added_rta: dict = {}
                for r0, c0 in cells_fs:
                    r, c = r0 + dr, c0 + dc
                    cur_color = int(color)
                    absorbed = False
                    while 0 <= r < bounds[0] and 0 <= c < bounds[1]:
                        if (r, c) in cells_fs:
                            r += dr
                            c += dc
                            continue
                        if not absorbed and grid_array[r, c] != bg_in:
                            cur_color = int(grid_array[r, c])
                            absorbed = True
                        added_rta[(r, c)] = cur_color
                        r += dr
                        c += dc
                if added_rta:
                    score = sum(1 for (r, c), cl in added_rta.items()
                                if target[r, c] == cl)
                    if score > 0:
                        candidates.append((score, len(added_rta),
                                           {"kind": "ray_through_absorbed",
                                            "direction": direction,
                                            "color": color}))

        # Halo
        for conn in (4, 8):
            added = grow_halo(cells_fs, color, conn, bounds)
            if added:
                score = sum(1 for (r, c), cl in added.items()
                            if target[r, c] == cl)
                if score > 0:
                    candidates.append((score, len(added),
                                       {"kind": "halo", "color": color,
                                        "conn": conn}))

        # Fill interior
        added = grow_fill_interior(cells_fs, color)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added),
                                   {"kind": "fill_interior", "color": color}))

    # Mirror edge (color-relational, no color param)
    for direction in _DIRECTIONS:
        added = grow_mirror_edge(cc, direction, bounds)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                        and target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added),
                                   {"kind": "mirror_edge",
                                    "direction": direction}))

    # Symmetry complete (color-relational)
    for axis in _AXES:
        added = grow_symmetry_complete(cc, axis)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                        and target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added),
                                   {"kind": "symmetry_complete",
                                    "axis": axis}))

    # R19 derived modes (ARC_PATTERN_DERIVE): periodic continuation and the
    # counted rectangular frame.  Colour-relational, no colour parameter.
    if _pattern_derive_enabled():
        for direction in _DIRECTIONS:
            for period_src in ("self", "bbox"):
                added = grow_periodic(cc, direction, bounds, period_src)
                if not added:
                    continue
                score = sum(1 for (r, c), cl in added.items()
                            if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                            and target[r, c] == cl)
                if score > 0:
                    candidates.append(
                        (score, len(added),
                         {"kind": f"periodic_{period_src}",
                          "direction": direction}))
        added = grow_frame_minority(cc, bounds)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                        and target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added),
                                   {"kind": "frame_minority"}))

    # R22 two-object modes (ARC_RAY_EXT): line_periodic + path_two_anchor.
    # Both need the other scene objects; proposed only when the gate is on
    # and the scene has at least two objects (their renderers return {}
    # otherwise, so this is a pure cost guard).
    if all_objects is not None and len(all_objects) >= 2 \
            and _ray_ext_enabled():
        r22_rules = [{"kind": k} for k in            # source-colour variants
                     ("line_periodic", "path_two_anchor")]
        r22_rules += [{"kind": k, "color": int(color)}
                      for color in try_colors
                      for k in ("line_periodic", "path_two_anchor")]
        for rule in r22_rules:
            added = _apply_generator(rule, obj, bounds,
                                     grid_array=grid_array,
                                     all_objects=all_objects)
            if not added:
                continue
            score = sum(1 for (r, c), cl in added.items()
                        if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                        and target[r, c] == cl)
            if score == len(added) and score > 0:
                candidates.append((score, len(added), rule))

    # R20 grid-aware modes (ARC_RAY_EXT): obstacle-conditional stopping and
    # background-only painting.  Undefined without a scene, so the whole
    # block is skipped when grid_array is None -- and never entered at all
    # when the gate is off.
    if grid_array is not None and _ray_ext_enabled():
        for color in try_colors:
            for kind, added in (
                    ("cross_center",
                     grow_cross_center(cells_fs, grid_array, color)),
                    ("cavity_leak",
                     grow_cavity_leak(cells_fs, grid_array, color))):
                if not added:
                    continue
                score = sum(1 for (r, c), cl in added.items()
                            if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                            and target[r, c] == cl)
                if score > 0:
                    candidates.append((score, len(added),
                                       {"kind": kind, "color": int(color)}))
            for direction in _DIRECTIONS:
                added = grow_ray_deflect(cells_fs, grid_array, direction,
                                         color)
                if not added:
                    continue
                score = sum(1 for (r, c), cl in added.items()
                            if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                            and target[r, c] == cl)
                if score > 0:
                    candidates.append((score, len(added),
                                       {"kind": "ray_deflect",
                                        "direction": direction,
                                        "color": int(color)}))

    # Row line (full row through object)
    for color in try_colors:
        rows_occupied = sorted(set(r for r, _ in obj.cells))
        added = {}
        for r in rows_occupied:
            for c in range(bounds[1]):
                if (r, c) not in cells_fs:
                    added[(r, c)] = int(color)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added),
                                   {"kind": "row_line", "color": color}))

    # Col line (full column through object)
    for color in try_colors:
        cols_occupied = sorted(set(c for _, c in obj.cells))
        added = {}
        for c in cols_occupied:
            for r in range(bounds[0]):
                if (r, c) not in cells_fs:
                    added[(r, c)] = int(color)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added),
                                   {"kind": "col_line", "color": color}))

    # Cross line (full row + column through object)
    for color in try_colors:
        rows_occupied = sorted(set(r for r, _ in obj.cells))
        cols_occupied = sorted(set(c for _, c in obj.cells))
        added = {}
        for r in rows_occupied:
            for c in range(bounds[1]):
                if (r, c) not in cells_fs:
                    added[(r, c)] = int(color)
        for c in cols_occupied:
            for r in range(bounds[0]):
                if (r, c) not in cells_fs:
                    added[(r, c)] = int(color)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added),
                                   {"kind": "cross_line", "color": color}))

    # R2: relational ray proposals (direction computed from scene objects)
    if all_objects is not None and len(all_objects) > 1:
        _DIR_MODES = ("toward", "away", "perpendicular")
        # Collect target colors from other objects
        other_colors = sorted(set(
            o.color for o in all_objects
            if frozenset(o.cells) != cells_fs))
        # Also try "largest" target
        target_preds: list[dict] = [{"type": "largest"}]
        for tc in other_colors:
            target_preds.append({"type": "color", "color": tc})

        for target_pred in target_preds:
            for dmode in _DIR_MODES:
                dr, dc = _compute_relational_direction(
                    cells_fs, target_pred, dmode, all_objects, obj)
                if (dr, dc) == (0, 0):
                    continue

                for color in try_colors[:4]:  # cap color sweep
                    for stop in ("grid_border", "first_nonbg"):
                        for absorbed in (False, True):
                            rule_rel = {
                                "kind": "ray_relational",
                                "direction_mode": dmode,
                                "target_pred": target_pred,
                                "color": color,
                                "bg": bg_in,
                                "stop": stop,
                                "absorbed": absorbed,
                            }
                            added = _apply_generator(
                                rule_rel, obj, bounds,
                                grid_array=grid_array,
                                include_source=False,
                                all_objects=all_objects)
                            if added:
                                score = sum(
                                    1 for (r, c), cl in added.items()
                                    if 0 <= r < bounds[0]
                                    and 0 <= c < bounds[1]
                                    and target[r, c] == cl)
                                if score > 0:
                                    candidates.append(
                                        (score, len(added), rule_rel))

    # R18: learned generators from learned_generators.json
    # Zero cost when the file is absent (empty list).
    _lg = _load_learned_generators_cached()
    for lg_rule in _lg:
        added = _apply_generator(lg_rule, obj, bounds,
                                 grid_array=grid_array,
                                 include_source=False,
                                 all_objects=all_objects)
        if added:
            score = sum(1 for (r, c), cl in added.items()
                        if 0 <= r < bounds[0] and 0 <= c < bounds[1]
                        and target[r, c] == cl)
            if score > 0:
                candidates.append((score, len(added), dict(lg_rule)))

    # Sort by score desc, then by fewer added cells (prefer simpler)
    candidates.sort(key=lambda x: (-x[0], x[1]))
    # Return top-K rules (drop scores)
    return [c[2] for c in candidates[:16]]


# R18: learned-generator loading.
# Unlike learned_verbs (which the engine loads once at startup via
# set_learned_verbs), learned generators are loaded lazily.  The
# engine sets ARC_LEARNED_GENERATORS_DIR to the run's output dir;
# without that env var set by the engine, nothing loads (zero cost).
_LEARNED_GENERATORS_CACHE: Optional[list[dict]] = None


def _reset_learned_generators_cache() -> None:
    """Reset the cache (for testing)."""
    global _LEARNED_GENERATORS_CACHE
    _LEARNED_GENERATORS_CACHE = None


def _load_learned_generators_cached() -> list[dict]:
    """Load learned generators from learned_generators.json if present.

    Requires ARC_LEARNED_GENERATORS_DIR env var pointing to the
    directory containing learned_generators.json.  Without it, returns
    empty (zero cost).  Cached for the duration of the process.
    """
    global _LEARNED_GENERATORS_CACHE
    if _LEARNED_GENERATORS_CACHE is not None:
        return _LEARNED_GENERATORS_CACHE

    _LEARNED_GENERATORS_CACHE = []

    lg_dir = os.environ.get("ARC_LEARNED_GENERATORS_DIR", "")
    if not lg_dir:
        return _LEARNED_GENERATORS_CACHE

    lg_path = Path(lg_dir) / "learned_generators.json"
    if not lg_path.exists():
        return _LEARNED_GENERATORS_CACHE

    try:
        from .generator_mining import load_admitted_generators, \
            hypothesis_to_generator_rule
        admitted = load_admitted_generators(lg_path)
        for gen in admitted:
            rule = hypothesis_to_generator_rule(gen.hypothesis)
            _LEARNED_GENERATORS_CACHE.append(rule)
    except Exception:
        pass

    return _LEARNED_GENERATORS_CACHE


def _fusion_signature(train_pairs: list[GridPair],
                      variant: SegmentationVariant) -> bool:
    """Check fusion precondition: n_out < n_in on every pair under this
    variant, and output grid same size as input."""
    for gi, go in train_pairs:
        if (gi.height, gi.width) != (go.height, go.width):
            return False
        bg_in = background_for(gi, variant)
        bg_out = background_for(go, variant)
        objs_in = segment(gi, variant, bg_in)
        objs_out = segment(go, variant, bg_out)
        if len(objs_out) >= len(objs_in):
            # R22 (ARC_RAY_EXT): EMISSION signature — the output ADDS
            # objects (lines/paths emitted from seeds).  The original
            # fusion class (n_out < n_in) is unchanged when the gate is
            # off; with it on, strictly-more objects on every pair also
            # qualifies (equality still rejects: nothing was created).
            if _ray_ext_enabled() and len(objs_out) > len(objs_in):
                continue
            return False
    return True


def _composite_matches(canvas: np.ndarray, target: np.ndarray) -> bool:
    """Pixel-exact match check."""
    return canvas.shape == target.shape and np.array_equal(canvas, target)


import time as _time


def _try_program(prog: GenerativeProgram,
                 train_pairs: list[GridPair]) -> bool:
    """Verify a GenerativeProgram is train-perfect on all pairs."""
    return all(_composite_matches(
        render_generative(prog, gi).to_numpy(), go.to_numpy())
        for gi, go in train_pairs)


def induce_generative_candidates(
    train_pairs: list[GridPair],
    deadline: Optional[float] = None,
) -> list[GenerativeProgram]:
    """Attempt generative-composite induction across segmentation variants.

    Returns a list of train-perfect GenerativeProgram candidates (may be
    empty).  Each candidate is verified on ALL train pairs.

    Strategy: for each seg variant with the fusion signature, try to find
    a UNIFORM generator rule (same rule for all objects) first, then try
    per-color-class generators, then greedy per-object assignment.
    Each strategy is tried with delete_source=False and True.
    """
    candidates: list[GenerativeProgram] = []

    def _deadline_ok():
        return deadline is None or _time.monotonic() < deadline

    for variant in SEGMENTATION_TRIAL_ORDER:
        if not _deadline_ok():
            break
        if not _fusion_signature(train_pairs, variant):
            continue

        # Gather per-pair object lists and targets
        pair_data = []
        for gi, go in train_pairs:
            bg_in = background_for(gi, variant)
            objs = sorted(segment(gi, variant, bg_in),
                          key=_object_sort_key)
            pair_data.append({
                "grid_in": gi,
                "grid_out": go,
                "bg_in": bg_in,
                "objects": objs,
                "target": go.to_numpy(),
                "bounds": (gi.height, gi.width),
                "grid_array": gi.to_numpy(),
            })

        # Determine canvas policy: try "over_input" first, then "blank"
        for canvas_policy in ("over_input", "blank"):
            for delete_source in (False, True):
                if not _deadline_ok():
                    break
                # STRATEGY 1: uniform generator (same rule for all objects)
                if not pair_data:
                    continue
                pd0 = pair_data[0]

                # Collect candidate rules from first pair's objects
                all_per_obj_rules = []
                for obj in pd0["objects"]:
                    rules = _candidate_generators_for_object(
                        obj, pd0["target"], pd0["bg_in"], pd0["bounds"],
                        grid_array=pd0["grid_array"],
                        all_objects=pd0["objects"])
                    all_per_obj_rules.append(rules)

                if not all_per_obj_rules:
                    continue

                # Try each candidate rule from the first object as a
                # uniform generator for ALL objects across ALL pairs
                for rule in all_per_obj_rules[0]:
                    prog = GenerativeProgram(
                        seg_variant=variant,
                        generators=[({}, rule)],
                        canvas_policy=canvas_policy,
                        background=pd0["bg_in"],
                        delete_source=delete_source,
                    )
                    if _try_program(prog, train_pairs):
                        candidates.append(prog)
                        if len(candidates) >= 4:
                            return candidates

                # STRATEGY 2: per-color-class generators
                # Group objects by color, assign one generator per class
                color_groups: dict[int, list] = {}
                for obj in pd0["objects"]:
                    color_groups.setdefault(obj.color, []).append(obj)

                if len(color_groups) <= 6:
                    per_class_candidates: dict[int, list[dict]] = {}
                    for color, objs_of_color in color_groups.items():
                        rules = _candidate_generators_for_object(
                            objs_of_color[0], pd0["target"],
                            pd0["bg_in"], pd0["bounds"],
                            grid_array=pd0["grid_array"],
                            all_objects=pd0["objects"])
                        per_class_candidates[color] = rules[:8]

                    color_keys = sorted(per_class_candidates.keys())
                    if color_keys:
                        rule_lists = [
                            per_class_candidates.get(c, [{}])
                            for c in color_keys]
                        import itertools
                        combos_tried = 0
                        for combo in itertools.product(*rule_lists):
                            if combos_tried >= _MAX_GEN_COMBOS:
                                break
                            combos_tried += 1
                            base_gens = list(zip(color_keys, combo))
                            # Try all permutations of generator order
                            # (painter's order matters at intersections);
                            # cap at 24 permutations (4! for <=4 classes)
                            perms = list(itertools.permutations(
                                base_gens))[:24]
                            for perm in perms:
                                generators = [
                                    ({"color": clr}, rule)
                                    for clr, rule in perm]
                                prog = GenerativeProgram(
                                    seg_variant=variant,
                                    generators=generators,
                                    canvas_policy=canvas_policy,
                                    background=pd0["bg_in"],
                                    delete_source=delete_source,
                                )
                                if _try_program(prog, train_pairs):
                                    candidates.append(prog)
                                    if len(candidates) >= 4:
                                        return candidates

                # STRATEGY 2b (R17b): per-color-class with intersection_color.
                # If Strategy 2 found no perfect program, check if a
                # per-color-class program is CLOSE (fails only at cells
                # where generators from different color classes overlap)
                # and adding an intersection_color would fix it.
                if len(color_groups) > 1 and len(candidates) == 0:
                    _try_intersection_color(
                        per_class_candidates, color_keys, rule_lists,
                        variant, canvas_policy, pd0, delete_source,
                        train_pairs, candidates)
                    if len(candidates) >= 4:
                        return candidates

                # STRATEGY 3: greedy per-object assignment
                greedy = _greedy_per_object_generators(
                    pair_data, train_pairs, canvas_policy, variant,
                    delete_source)
                if greedy is not None:
                    candidates.append(greedy)
                    if len(candidates) >= 4:
                        return candidates

    return candidates


def _try_intersection_color(
    per_class_candidates: dict[int, list[dict]],
    color_keys: list[int],
    rule_lists: list[list[dict]],
    variant: SegmentationVariant,
    canvas_policy: str,
    pd0: dict,
    delete_source: bool,
    train_pairs: list,
    candidates: list,
) -> None:
    """Strategy 2b (R17b): detect if adding an intersection_color to a
    per-color-class program would make it train-perfect.

    For each combo that ALMOST works (fails at < 20% of diff cells), check
    whether all failure cells share a single color in the target that is NOT
    any generator's color -> that's the intersection_color.  Cap: 64 combos.
    """
    import itertools
    combos_tried = 0
    for combo in itertools.product(*rule_lists):
        if combos_tried >= 64:
            break
        combos_tried += 1
        base_gens = list(zip(color_keys, combo))
        # Try only one canonical permutation (we test all intersection
        # colors so painter order at overlaps is replaced by ic)
        generators = [({"color": clr}, rule) for clr, rule in base_gens]
        for ic_perm in itertools.permutations(base_gens):
            generators = [({"color": clr}, rule) for clr, rule in ic_perm]
            prog_no_ic = GenerativeProgram(
                seg_variant=variant,
                generators=generators,
                canvas_policy=canvas_policy,
                background=pd0["bg_in"],
                delete_source=delete_source,
            )
            # Render on first pair and find the diff
            gi0, go0 = train_pairs[0]
            rendered0 = render_generative(prog_no_ic, gi0).to_numpy()
            target0 = go0.to_numpy()
            diff_mask = rendered0 != target0
            n_diff = int(diff_mask.sum())
            total_diff = max(1, int((target0 !=
                                     (gi0.to_numpy() if canvas_policy == "over_input"
                                      else np.full_like(target0, pd0["bg_in"])
                                      )).sum()))
            if n_diff == 0:
                # Already perfect, Strategy 2 should have caught it
                continue
            if n_diff > total_diff * 0.3:
                continue  # too far off
            # Check: do all wrong cells share a single target color?
            wrong_colors = set()
            for r in range(target0.shape[0]):
                for c in range(target0.shape[1]):
                    if diff_mask[r, c]:
                        wrong_colors.add(int(target0[r, c]))
            if len(wrong_colors) != 1:
                continue
            ic_color = wrong_colors.pop()
            if ic_color in color_keys:
                continue  # can't be an intersection color if it's a generator color
            # Try this intersection_color
            prog_ic = GenerativeProgram(
                seg_variant=variant,
                generators=generators,
                canvas_policy=canvas_policy,
                background=pd0["bg_in"],
                delete_source=delete_source,
                intersection_color=ic_color,
            )
            if _try_program(prog_ic, train_pairs):
                candidates.append(prog_ic)
                return
            break  # only try one permutation per combo for ic


def _greedy_per_object_generators(
    pair_data: list[dict],
    train_pairs: list["GridPair"],
    canvas_policy: str,
    variant: SegmentationVariant,
    delete_source: bool = False,
) -> Optional[GenerativeProgram]:
    """Strategy 3: assign the best generator to each object independently
    on the first pair, then verify across all pairs.

    For generalization: we try to express generator assignment as a RULE
    based on object features (color, position-class) rather than per-
    object indexing.  If that fails, we try direct per-object assignment
    as a fallback (which is position-dependent but still works for LOO
    if the object count is consistent).
    """
    pd0 = pair_data[0]
    objs0 = pd0["objects"]
    target0 = pd0["target"]
    bounds0 = pd0["bounds"]
    bg0 = pd0["bg_in"]

    if not objs0:
        return None

    # For each object in first pair, find its best generator
    best_rules: list[tuple[int, dict]] = []  # (obj_index, rule)
    for i, obj in enumerate(objs0):
        cands = _candidate_generators_for_object(obj, target0, bg0, bounds0,
                                                     grid_array=pd0["grid_array"],
                                                     all_objects=objs0)
        if not cands:
            return None  # can't explain this object
        best_rules.append((i, cands[0]))

    # Check if all objects get the same rule (already covered by Strategy 1)
    rule_sigs = [json.dumps(r, sort_keys=True) for _, r in best_rules]
    if len(set(rule_sigs)) == 1:
        return None  # Strategy 1 would have caught this

    # Try to generalize: group objects by rule and see if each group can
    # be identified by color
    rule_by_color: dict[int, list[dict]] = {}
    for i, rule in best_rules:
        obj = objs0[i]
        rule_by_color.setdefault(obj.color, []).append(rule)

    # Check if within each color class, all objects get the same rule
    color_consistent = True
    for color, rules in rule_by_color.items():
        sigs = [json.dumps(r, sort_keys=True) for r in rules]
        if len(set(sigs)) > 1:
            color_consistent = False
            break

    if color_consistent and len(rule_by_color) > 1:
        # Build per-color generators
        generators = []
        for color, rules in sorted(rule_by_color.items()):
            generators.append(({"color": color}, rules[0]))
        prog = GenerativeProgram(
            seg_variant=variant,
            generators=generators,
            canvas_policy=canvas_policy,
            background=bg0,
            delete_source=delete_source,
        )
        if _try_program(prog, train_pairs):
            return prog

    return None  # end _greedy_per_object_generators


# ---------------------------------------------------------------------------
# Stage-3: generative-composition patch inducer (ARC_GEN_COMPOSE)
# ---------------------------------------------------------------------------

def induce_gen_compose_patch(
    base_program,
    train_pairs: list[GridPair],
    deadline: Optional[float] = None,
) -> Optional["OverlayProgram"]:
    """Induce a generative PATCH for a base program's residual.

    Given a base object-program that gets most pixels right but misses
    some, find generators (from the generative vocabulary) that paint
    exactly the residual cells.  Returns an OverlayProgram(base, patch)
    if a train-perfect composition exists, else None.

    The key difference from the overlay path (which uses _induce_candidate
    for the patch) is that HERE the patch inducer is the generative
    vocabulary — lines, rays, halos, fills — which can produce the
    content the object inducer cannot.

    Fold-safe: called inside _induce_composed, so each LOO fold
    re-derives both base and patch from the fold's pairs.
    """
    from .types import OverlayProgram
    from .actions import render_program

    def _deadline_ok():
        return deadline is None or _time.monotonic() < deadline

    # Step 1: render base on each input, compute residuals
    residuals_per_pair: list[dict] = []  # {(r,c): target_color}
    for gi, go in train_pairs:
        if gi.height != go.height or gi.width != go.width:
            return None
        try:
            rendered = render_program(base_program, gi).to_numpy()
        except Exception:
            return None
        target = go.to_numpy()
        wrong = rendered != target
        if not wrong.any():
            return None  # base already perfect: no residual to patch
        residual = {}
        for r in range(target.shape[0]):
            for c in range(target.shape[1]):
                if wrong[r, c]:
                    residual[(r, c)] = int(target[r, c])
        residuals_per_pair.append(residual)

    if not residuals_per_pair:
        return None

    # Step 2: for each segmentation variant, segment the INPUT,
    # propose generators that match the residual cells, and try to
    # build a generative patch program.
    for variant in SEGMENTATION_TRIAL_ORDER:
        if not _deadline_ok():
            break

        # Gather per-pair data
        pair_data = []
        for idx, (gi, go) in enumerate(train_pairs):
            bg_in = background_for(gi, variant)
            objs = sorted(segment(gi, variant, bg_in),
                          key=_object_sort_key)
            pair_data.append({
                "grid_in": gi,
                "bg_in": bg_in,
                "objects": objs,
                "bounds": (gi.height, gi.width),
                "grid_array": gi.to_numpy(),
                "residual": residuals_per_pair[idx],
                "target": go.to_numpy(),
            })

        if not pair_data or not pair_data[0]["objects"]:
            continue

        pd0 = pair_data[0]
        h0, w0 = pd0["bounds"]
        residual0 = pd0["residual"]

        # Build a residual-only target for generator scoring:
        # nonzero at residual cells, zero elsewhere
        resid_target = np.zeros((h0, w0), dtype=np.int32)
        for (r, c), color in residual0.items():
            resid_target[r, c] = color

        # Generative patch uses blank canvas: we only want the
        # generators' output, overlaid on the base render.

        # STRATEGY 1: uniform generator across all objects
        all_per_obj_rules = []
        for obj in pd0["objects"]:
            rules = _candidate_generators_for_object(
                obj, resid_target, pd0["bg_in"], pd0["bounds"],
                grid_array=pd0["grid_array"],
                all_objects=pd0["objects"])
            all_per_obj_rules.append(rules)

        if not all_per_obj_rules:
            continue

        # Try each candidate from first object as uniform
        for rule in all_per_obj_rules[0][:8]:
            if not _deadline_ok():
                break
            patch = GenerativeProgram(
                seg_variant=variant,
                generators=[({}, rule)],
                canvas_policy="blank",
                background=0,
                delete_source=False,
            )
            overlay = OverlayProgram(base=base_program, patch=patch)
            if _train_perfect_overlay(overlay, train_pairs):
                return overlay

        # STRATEGY 2: per-color-class generators
        color_groups: dict[int, list] = {}
        for obj in pd0["objects"]:
            color_groups.setdefault(obj.color, []).append(obj)

        if len(color_groups) <= 6:
            per_class_cands: dict[int, list[dict]] = {}
            for color, objs_of_color in color_groups.items():
                rules = _candidate_generators_for_object(
                    objs_of_color[0], resid_target,
                    pd0["bg_in"], pd0["bounds"],
                    grid_array=pd0["grid_array"],
                    all_objects=pd0["objects"])
                per_class_cands[color] = rules[:6]

            color_keys = sorted(per_class_cands.keys())
            if color_keys:
                import itertools
                rule_lists = [
                    per_class_cands.get(c, [{}])
                    for c in color_keys]
                combos_tried = 0
                for combo in itertools.product(*rule_lists):
                    if combos_tried >= 128:
                        break
                    if not _deadline_ok():
                        break
                    combos_tried += 1
                    generators = [
                        ({"color": clr}, rule)
                        for clr, rule in zip(color_keys, combo)]
                    patch = GenerativeProgram(
                        seg_variant=variant,
                        generators=generators,
                        canvas_policy="blank",
                        background=0,
                        delete_source=False,
                    )
                    overlay = OverlayProgram(
                        base=base_program, patch=patch)
                    if _train_perfect_overlay(overlay, train_pairs):
                        return overlay

    return None  # end induce_gen_compose_patch


def _train_perfect_overlay(overlay, train_pairs: list[GridPair]) -> bool:
    """Check if an OverlayProgram is train-perfect on all pairs."""
    from .actions import render_program
    for gi, go in train_pairs:
        try:
            rendered = render_program(overlay, gi).to_numpy()
            target = go.to_numpy()
            if rendered.shape != target.shape:
                return False
            if not np.array_equal(rendered, target):
                return False
        except Exception:
            return False
    return True
