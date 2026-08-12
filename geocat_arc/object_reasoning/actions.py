"""Generic action primitives and the program executor (Sections 2.3 / 4.4).

Hard rule (Section 2.3): no action embeds task-specific constants at
definition time.  Constants enter ONLY as induced parameter expressions
evaluated per object at apply time.

Execution model: an ObjectCanvas of objects is transformed rule-by-rule,
then rendered.  render_program() is the ONLY execution path for accepted
programs (Requirement 4.4); engine.py wraps it as Solution.apply_fn.

Geometry conventions follow the existing categorical_dsl operators
(operators_spatial.Reflect / Rotate90, operators_basic.TranslateAll):
reflect axis "horizontal" = up/down flip, "vertical" = left/right flip;
rotation is clockwise in 90-degree steps anchored at the bbox top-left.
The implementations here re-state that geometry multicolor-aware (a
MultiColorObject keeps its per-cell colors through every transform, which
the plain operators cannot do), reusing perception.objects primitives
(translated / recolored / render_objects semantics) rather than new geometry.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject

from .expressions import DIRECTION_UNITS, EvalContext, EvalError, evaluate
from .features import register_builtin_features
from .segmentation import background_for, segment
from .types import (
    AXES,
    ActionRule,
    ComposedProgram,
    DeltaType,
    GridContext,
    MultiColorObject,
    ObjectProgram,
    cell_colors_of,
)


@dataclass
class ObjectCanvas:
    """Mutable execution state: the object set being transformed plus the
    output frame it will be rendered into.

    ``objects`` start as the segmented input objects; actions replace,
    remove, or append entries.  ``height``/``width``/``background`` describe
    the output frame (set from ObjectProgram.output_spec before rules run).
    ``crop_region`` is set by CROP_TO and consumed by render().
    """
    objects: list[ARCObject]
    height: int
    width: int
    background: int
    source_grid: Grid = None  # the input grid (for crop / cell lookups)
    crop_region: Optional[tuple[int, int, int, int]] = None
    #: (tile_h, tile_w) repetition of the cropped region (CROP_TO tiling for
    #: count-sized shrink outputs); None / (1, 1) = plain crop.
    tile_counts: Optional[tuple[int, int]] = None
    #: Round-12 FILL_LINE: cells painted onto the background layer (drawn
    #: before objects, so objects occlude them).  {(r,c): color}.
    background_cells: dict = field(default_factory=dict)


# Each primitive: (canvas, obj, action, ectx) -> list[ARCObject]
# = the objects that REPLACE ``obj`` on the canvas (empty list = delete;
# k+1 entries for copy-with-keep; identity list [obj] for keep).
ActionFn = Callable[[ObjectCanvas, ARCObject, ActionRule, EvalContext],
                    list[ARCObject]]


# ---------------------------------------------------------------------------
# Private geometry helpers (multicolor-aware object rebuilds)
# ---------------------------------------------------------------------------

def _bbox_of(cells) -> tuple[int, int, int, int]:
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return (min(rows), min(cols), max(rows) + 1, max(cols) + 1)


def _build_object(obj_id: int, cell_colors: dict[tuple[int, int], int]) -> ARCObject:
    """Rebuild an object from a per-cell color map (MultiColorObject iff the
    cells are not uniform in color)."""
    if not cell_colors:
        raise EvalError("action produced an empty object")
    cells = frozenset(cell_colors)
    colors = set(cell_colors.values())
    bbox = _bbox_of(cells)
    if len(colors) == 1:
        return ARCObject(id=obj_id, cells=cells, color=colors.pop(),
                         bounding_box=bbox)
    counts = Counter(cell_colors.values())
    majority = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return MultiColorObject(id=obj_id, cells=cells, color=majority,
                            bounding_box=bbox, cell_colors=dict(cell_colors))


def _map_cells(obj: ARCObject,
               fn: Callable[[int, int], tuple[int, int]]) -> ARCObject:
    """Apply a cell-coordinate map, carrying per-cell colors through."""
    return _build_object(obj.id, {fn(r, c): col
                                  for (r, c), col in cell_colors_of(obj).items()})


def _translated(obj: ARCObject, dr: int, dc: int) -> ARCObject:
    """perception's ARCObject.translated, made multicolor-aware."""
    if not isinstance(obj, MultiColorObject):
        return obj.translated(dr, dc)          # reuse perception primitive
    return _map_cells(obj, lambda r, c: (r + dr, c + dc))


def _eval_param(action: ActionRule, name: str, obj: ARCObject,
                ectx: EvalContext):
    if name not in action.params:
        raise EvalError(f"{action.delta_type.value} missing parameter "
                        f"expression {name!r}")
    return evaluate(action.params[name], obj, ectx)


def _fresh_id(canvas: ObjectCanvas, ectx: EvalContext) -> int:
    ids = [o.id for o in canvas.objects] + [o.id for o in ectx.grid_ctx.objects]
    return (max(ids) + 1) if ids else 0


# ---------------------------------------------------------------------------
# Primitives (generic, parameterized by expressions only)
# ---------------------------------------------------------------------------

def apply_keep(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
               ectx: EvalContext) -> list[ARCObject]:
    """Identity: object passes through unchanged."""
    return [obj]


def apply_delete(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                 ectx: EvalContext) -> list[ARCObject]:
    """Drop the object (returns [])."""
    return []


def apply_translate(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                    ectx: EvalContext) -> list[ARCObject]:
    """Translate by params['vector'] (VecExpr).  Uses ARCObject.translated;
    cells moving out of frame are clipped at render time, not here."""
    dr, dc = _eval_param(action, "vector", obj, ectx)
    return [_translated(obj, int(dr), int(dc))]


def apply_recolor(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                  ectx: EvalContext) -> list[ARCObject]:
    """Recolor to params['color'] (ColorExpr).  Uses ARCObject.recolored;
    MultiColorObject recolors all cells to the single evaluated color."""
    color = int(_eval_param(action, "color", obj, ectx))
    if isinstance(obj, MultiColorObject):
        return [ARCObject(id=obj.id, cells=obj.cells, color=color,
                          bounding_box=obj.bounding_box)]
    return [obj.recolored(color)]              # reuse perception primitive


def _NUMBERED_KEY(prefix: str, key: str) -> bool:
    """True for parameter names '<prefix><digits>' (copy lattice slots)."""
    return (key.startswith(prefix) and len(key) > len(prefix)
            and key[len(prefix):].isdigit())


def apply_copy(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
               ectx: EvalContext) -> list[ARCObject]:
    """Three generic placement modes (dispatch on the params present):

    1. 'targets' (PredExpr) [+ 'align' (AlignExpr)]: one copy per OTHER
       object satisfying the predicate, placed with the copy's bbox center
       (default) or bbox origin aligned to the target's — copy-at-markers.
    2. 'period' (VecExpr) [+ 'offset<i>' (VecExprs)]: placement lattice —
       copies at b + i*(dr,dc) for every base b in {(0,0)} U offsets while
       the copy still intersects the grid (periodic repetition until
       border; base offsets give zigzag/staggered lattices).
    3. 'ray<i>' (VecExprs): multi-ray repetition — for each ray vector,
       copies at j*ray for j = 1, 2, ... while inside the grid (diagonal /
       star emission from a seed).
    4. 'offset<i>' alone (no 'period'): one copy per offset vector.
    5. 'k' (ScalarExpr) + 'placement' (VecExpr, evaluated per copy index i
       in 0..k-1 with ectx.bindings['copy_index']=i): explicit displacements.

    Original kept iff params.get('keep_original') evaluates true (default:
    kept)."""
    keep = True
    if "keep_original" in action.params:
        keep = bool(evaluate(action.params["keep_original"], obj, ectx))
    out: list[ARCObject] = [obj] if keep else []
    next_id = _fresh_id(canvas, ectx)
    r0, c0, r1, c1 = obj.bounding_box

    if "targets" in action.params:
        pred = action.params["targets"]
        align = "bbox_center"
        if "align" in action.params:
            align = str(_eval_param(action, "align", obj, ectx))
        targets = [b for b in ectx.grid_ctx.objects
                   if b.id != obj.id and evaluate(pred, b, ectx)]
        if not targets:
            raise EvalError("copy: 'targets' predicate matches no object")
        targets.sort(key=lambda b: (b.bounding_box[0], b.bounding_box[1], b.id))
        h, w = r1 - r0, c1 - c0
        for i, b in enumerate(targets):
            b0, b1, b2, b3 = b.bounding_box
            if align == "bbox_origin":
                dr, dc = b0 - r0, b1 - c0
            elif align == "bbox_center":
                dr = b0 + ((b2 - b0) - h) // 2 - r0
                dc = b1 + ((b3 - b1) - w) // 2 - c0
            else:
                raise EvalError(f"copy: unknown alignment {align!r}")
            copy = _translated(obj, int(dr), int(dc))
            out.append(_build_object(next_id + i, cell_colors_of(copy)))
        return out

    ray_keys = sorted(k for k in action.params if _NUMBERED_KEY("ray", k))
    offset_keys = sorted(k for k in action.params if _NUMBERED_KEY("offset", k))
    if "period" in action.params or ray_keys or offset_keys:
        gh, gw = ectx.grid_ctx.grid.height, ectx.grid_ctx.grid.width

        def _inside(dr: int, dc: int) -> bool:
            return any(0 <= r + dr < gh and 0 <= c + dc < gw
                       for r, c in obj.cells)

        placements: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()

        def _add(dr: int, dc: int) -> None:
            if (dr, dc) != (0, 0) and (dr, dc) not in seen and _inside(dr, dc):
                seen.add((dr, dc))
                placements.append((dr, dc))

        offsets = [tuple(int(x) for x in
                         _eval_param(action, k, obj, ectx))
                   for k in offset_keys]
        if "period" in action.params:
            pr, pc = (int(x) for x in _eval_param(action, "period", obj, ectx))
            if (pr, pc) == (0, 0):
                raise EvalError("copy: zero 'period' vector")
            for br, bc in [(0, 0)] + offsets:
                i = 1 if (br, bc) == (0, 0) else 0
                while i <= gh + gw:
                    dr, dc = br + i * pr, bc + i * pc
                    if not _inside(dr, dc):
                        break
                    _add(dr, dc)
                    i += 1
        elif offsets:
            for dr, dc in offsets:
                _add(dr, dc)
        for key in ray_keys:
            rr, rc = (int(x) for x in _eval_param(action, key, obj, ectx))
            if (rr, rc) == (0, 0):
                raise EvalError(f"copy: zero ray vector for {key!r}")
            j = 1
            while j <= gh + gw:
                dr, dc = j * rr, j * rc
                if not _inside(dr, dc):
                    break
                _add(dr, dc)
                j += 1
        if not placements:
            raise EvalError("copy: lattice places no copy inside the grid")
        for i, (dr, dc) in enumerate(placements):
            copy = _translated(obj, dr, dc)
            out.append(_build_object(next_id + i, cell_colors_of(copy)))
        return out

    k = int(_eval_param(action, "k", obj, ectx)) if "k" in action.params else 1
    if k < 0:
        raise EvalError(f"copy: negative copy count {k}")
    for i in range(k):
        ectx.bindings["copy_index"] = i
        try:
            dr, dc = _eval_param(action, "placement", obj, ectx)
        finally:
            ectx.bindings.pop("copy_index", None)
        copy = _translated(obj, int(dr), int(dc))
        copy = _build_object(next_id + i, cell_colors_of(copy))
        out.append(copy)
    return out


def apply_move_to(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                  ectx: EvalContext) -> list[ARCObject]:
    """Absolute placement: translate so bbox origin lands on params['position']
    (VecExpr evaluated as (r0, c0))."""
    r0, c0 = _eval_param(action, "position", obj, ectx)
    return [_translated(obj, int(r0) - obj.bounding_box[0],
                        int(c0) - obj.bounding_box[1])]


def _as_unit(direction) -> tuple[int, int]:
    """Normalize a direction parameter value (str in DIRECTIONS or a vector)
    to a 4-connected unit step."""
    if isinstance(direction, str):
        if direction not in DIRECTION_UNITS:
            raise EvalError(f"unknown direction: {direction!r}")
        return DIRECTION_UNITS[direction]
    if isinstance(direction, (tuple, list)) and len(direction) == 2:
        dr, dc = int(direction[0]), int(direction[1])
        if (dr == 0) == (dc == 0):
            raise EvalError(f"direction vector must be axis-aligned and "
                            f"non-zero, got {(dr, dc)}")
        return ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
    raise EvalError(f"cannot interpret direction parameter: {direction!r}")


def _infer_direction(obj: ARCObject, target: ARCObject) -> tuple[int, int]:
    """Axis + sign of motion toward ``target``: prefer the axis with bbox
    overlap on the perpendicular (real gravity geometry), else the dominant
    centroid-delta axis.  Deterministic."""
    r0, c0, r1, c1 = obj.bounding_box
    R0, C0, R1, C1 = target.bounding_box
    col_overlap = min(c1, C1) > max(c0, C0)
    row_overlap = min(r1, R1) > max(r0, R0)
    (sr, sc), (tr, tc) = obj.centroid, target.centroid
    dr, dc = tr - sr, tc - sc
    if col_overlap and not row_overlap:
        return (1, 0) if dr > 0 else (-1, 0)
    if row_overlap and not col_overlap:
        return (0, 1) if dc > 0 else (0, -1)
    if col_overlap and row_overlap:
        raise EvalError("move_until_adjacent: objects already overlap")
    if abs(dr) >= abs(dc):
        return (1, 0) if dr > 0 else (-1, 0)
    return (0, 1) if dc > 0 else (0, -1)


def apply_move_until_adjacent(canvas: ObjectCanvas, obj: ARCObject,
                              action: ActionRule, ectx: EvalContext) -> list[ARCObject]:
    """Gravity-style motion: step along params['direction'] (DirectionExpr /
    unit VecExpr; inferred from geometry when absent) until 4-adjacent to the
    object referenced by params['target'] (RefExpr), or flush against the
    border when no target parameter is given.  Equivalent to
    translate(gap_closing_vector(...)) — provided as a primitive so the delta
    extractor can name gravity directly."""
    grid = ectx.grid_ctx.grid
    h, w = grid.height, grid.width

    target: Optional[ARCObject] = None
    if "target" in action.params:
        target = evaluate(action.params["target"], obj, ectx)

    if "direction" in action.params:
        unit = _as_unit(evaluate(action.params["direction"], obj, ectx))
    elif target is not None:
        unit = _infer_direction(obj, target)
    else:
        raise EvalError("move_until_adjacent needs a 'direction' and/or "
                        "'target' parameter")

    if target is None:
        # Border mode: closed-form flush translation (== vector_to_border).
        r0, c0, r1, c1 = obj.bounding_box
        dr = {-1: -r0, 1: h - r1, 0: 0}[unit[0]]
        dc = {-1: -c0, 1: w - c1, 0: 0}[unit[1]]
        return [_translated(obj, dr, dc)]

    target_cells = set(target.cells)

    def adjacent(cells) -> bool:
        return any((r + dr, c + dc) in target_cells
                   for r, c in cells
                   for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)))

    cells = set(obj.cells)
    if cells & target_cells:
        raise EvalError("move_until_adjacent: object overlaps target")
    total = (0, 0)
    for _ in range(h + w):
        if adjacent(cells):
            return [_translated(obj, *total)]
        nxt = {(r + unit[0], c + unit[1]) for r, c in cells}
        if any(not (0 <= r < h and 0 <= c < w) for r, c in nxt) \
                or nxt & target_cells:
            raise EvalError("move_until_adjacent: target never becomes "
                            "adjacent along this direction")
        cells = nxt
        total = (total[0] + unit[0], total[1] + unit[1])
    raise EvalError("move_until_adjacent: no adjacency within grid bounds")


def apply_scale(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                ectx: EvalContext) -> list[ARCObject]:
    """Integer scale of the object mask by params['factor'] (ScalarExpr);
    negative factor f means shrink by |f| (block-majority downsample).
    Anchored at bbox top-left."""
    f = int(_eval_param(action, "factor", obj, ectx))
    if f in (0, -1):
        raise EvalError(f"scale: undefined factor {f}")
    if f == 1:
        return [obj]
    r0, c0, _, _ = obj.bounding_box
    colors = cell_colors_of(obj)
    if f > 1:
        new_colors: dict[tuple[int, int], int] = {}
        for (r, c), col in colors.items():
            br, bc = r0 + (r - r0) * f, c0 + (c - c0) * f
            for i in range(f):
                for j in range(f):
                    new_colors[(br + i, bc + j)] = col
        return [_build_object(obj.id, new_colors)]
    # f <= -2: downsample by |f| with block-majority presence/color
    k = -f
    blocks: dict[tuple[int, int], list[int]] = {}
    for (r, c), col in colors.items():
        blocks.setdefault(((r - r0) // k, (c - c0) // k), []).append(col)
    new_colors = {}
    for (br, bc), cols in sorted(blocks.items()):
        if 2 * len(cols) >= k * k:  # majority-present (ties -> present)
            counts = Counter(cols)
            majority = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            new_colors[(r0 + br, c0 + bc)] = majority
    return [_build_object(obj.id, new_colors)]


def apply_reflect(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                  ectx: EvalContext) -> list[ARCObject]:
    """Reflect about params['axis'] (AxisExpr, str in types.AXES) within the
    object's bbox (same convention as categorical_dsl operators_spatial.
    Reflect: "horizontal" = up/down flip, "vertical" = left/right flip;
    diagonals transpose about the bbox top-left), then optional
    params['vector'] translation."""
    axis = _eval_param(action, "axis", obj, ectx)
    if axis not in AXES:
        raise EvalError(f"unknown axis: {axis!r}")
    r0, c0, r1, c1 = obj.bounding_box
    h, w = r1 - r0, c1 - c0
    if axis == "horizontal":
        out = _map_cells(obj, lambda r, c: (r0 + (h - 1 - (r - r0)), c))
    elif axis == "vertical":
        out = _map_cells(obj, lambda r, c: (r, c0 + (w - 1 - (c - c0))))
    elif axis == "diag_main":
        out = _map_cells(obj, lambda r, c: (r0 + (c - c0), c0 + (r - r0)))
    else:  # diag_anti
        out = _map_cells(obj, lambda r, c: (r0 + (w - 1 - (c - c0)),
                                            c0 + (h - 1 - (r - r0))))
    if "vector" in action.params:
        dr, dc = _eval_param(action, "vector", obj, ectx)
        out = _translated(out, int(dr), int(dc))
    return [out]


def apply_rotate(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                 ectx: EvalContext) -> list[ARCObject]:
    """Rotate by params['angle'] (AngleExpr, int in types.ANGLES) clockwise
    about the bbox top-left anchor (same convention as categorical_dsl
    operators_spatial.Rotate90), then optional params['vector'] translation."""
    angle = int(_eval_param(action, "angle", obj, ectx))
    if angle % 90 != 0:
        raise EvalError(f"rotate: unsupported angle {angle}")
    turns = (angle % 360) // 90
    out = obj
    for _ in range(turns):
        r0, c0, r1, c1 = out.bounding_box
        h = r1 - r0
        # 90 degrees clockwise: relative (i, j) -> (j, h - 1 - i)
        out = _map_cells(out, lambda r, c, r0=r0, c0=c0, h=h:
                         (r0 + (c - c0), c0 + (h - 1 - (r - r0))))
    if "vector" in action.params:
        dr, dc = _eval_param(action, "vector", obj, ectx)
        out = _translated(out, int(dr), int(dc))
    return [out]


def apply_paint(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                ectx: EvalContext) -> list[ARCObject]:
    """Template stamping: repaint the object's cells with the bbox-relative
    per-cell colors of params['source'] (RefExpr) — the source must have the
    IDENTICAL bbox-relative cell mask (translation-invariant), else EvalError.
    Position is unchanged; only colors are rewritten."""
    src = evaluate(action.params.get("source"), obj, ectx) \
        if "source" in action.params else None
    if src is None:
        raise EvalError("paint missing parameter expression 'source'")
    sr0, sc0 = src.bounding_box[:2]
    src_rel = {(r - sr0, c - sc0): col
               for (r, c), col in cell_colors_of(src).items()}
    r0, c0 = obj.bounding_box[:2]
    obj_rel = {(r - r0, c - c0) for r, c in obj.cells}
    if obj_rel != set(src_rel):
        raise EvalError("paint: source mask differs from object mask")
    return [_build_object(obj.id, {(r0 + dr, c0 + dc): col
                                   for (dr, dc), col in src_rel.items()})]


def apply_grow(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
               ectx: EvalContext) -> list[ARCObject]:
    """Grow the object (round 2): keep every cell and add the cells of one
    generic growth mode — params['mode'] (GrowModeExpr) plus, per mode:
    fill_interior: color; halo: color + conn (ScalarExpr 4|8);
    ray: color + direction (+ optional length, absent = to the grid border);
    pattern: a constant bbox-origin-relative added-cell PatternExpr."""
    from .growth import (grow_fill_interior, grow_halo, grow_mirror_edge,
                         grow_ray, grow_symmetry_complete, pattern_cells)
    mode = _eval_param(action, "mode", obj, ectx)
    cc = cell_colors_of(obj)
    if "vector" in action.params:      # translate+grow (round 4)
        dr, dc = _eval_param(action, "vector", obj, ectx)
        cc = {(r + int(dr), c + int(dc)): col for (r, c), col in cc.items()}
    cells = set(cc)
    bounds = (canvas.height, canvas.width)
    if mode == "fill_interior":
        color = int(_eval_param(action, "color", obj, ectx))
        added = grow_fill_interior(cells, color)
    elif mode == "halo":
        color = int(_eval_param(action, "color", obj, ectx))
        conn = int(_eval_param(action, "conn", obj, ectx)) \
            if "conn" in action.params else 4
        if conn not in (4, 8):
            raise EvalError(f"grow halo: bad connectivity {conn}")
        added = grow_halo(cells, color, conn, bounds)
    elif mode == "ray":
        color = int(_eval_param(action, "color", obj, ectx))
        direction = _eval_param(action, "direction", obj, ectx)
        length = int(_eval_param(action, "length", obj, ectx)) \
            if "length" in action.params else None
        if length is not None and length < 1:
            raise EvalError(f"grow ray: non-positive length {length}")
        added = grow_ray(cells, direction, color, length, bounds)
    elif mode == "symmetry_complete":
        axis = _eval_param(action, "axis", obj, ectx)
        added = grow_symmetry_complete(cc, axis)
        if added is None:
            raise EvalError(f"grow symmetry_complete: undefined for axis "
                            f"{axis!r} on this object")
    elif mode == "mirror_edge":
        direction = _eval_param(action, "direction", obj, ectx)
        added = grow_mirror_edge(cc, direction, bounds)
        if added is None:
            raise EvalError(f"grow mirror_edge: undefined for direction "
                            f"{direction!r} on this object")
    elif mode == "pattern":
        pattern = _eval_param(action, "pattern", obj, ectx)
        color = int(_eval_param(action, "color", obj, ectx)) \
            if "color" in action.params else None
        added = pattern_cells(cells, pattern, color)
    else:
        raise EvalError(f"grow: unknown mode {mode!r}")
    if not added:
        raise EvalError(f"grow {mode}: no cells added")
    merged = dict(cc)
    merged.update(added)
    return [_build_object(obj.id, merged)]


def apply_synth_copy(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                     ectx: EvalContext) -> list[ARCObject]:
    """AUTONOMOUS M2: apply a LEARNED verb (registered combinator chain) to
    self and stamp the image at params['placement'] (VecExpr), colored by
    params['color'] (ColorExpr) or carrying self's color.  params['verb']
    is a PatternExpr-carried name validated against the per-run registry."""
    from geocat_arc.object_reasoning.correspondence import LEARNED_VERBS
    from geocat_arc.object_reasoning.synth_verbs import apply_verb_chain
    verb = _eval_param(action, "verb", obj, ectx)
    name = verb[0] if isinstance(verb, (tuple, list)) else verb
    chain = LEARNED_VERBS.chain_of(str(name))
    if chain is None:
        raise EvalError(f"unknown learned verb {name!r}")
    cc = cell_colors_of(obj)
    img = apply_verb_chain(chain, set(cc))
    if not img:
        raise EvalError(f"learned verb {name!r} undefined on this object")
    dr, dc = _eval_param(action, "placement", obj, ectx)
    color = int(_eval_param(action, "color", obj, ectx)) \
        if "color" in action.params else obj.color
    r0 = obj.bounding_box[0]
    c0 = obj.bounding_box[1]
    part = {(r0 + int(dr) + r, c0 + int(dc) + c): color for (r, c) in img}
    return [obj, _build_object(_fresh_id(canvas, ectx), part)]


def apply_copy_part(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                    ectx: EvalContext) -> list[ARCObject]:
    """M2 verb 2: copy a subwindow of self elsewhere.  params: window
    (PatternExpr const 4-tuple (wr, wc, wh, ww) rel. to self bbox),
    placement (VecExpr rel. to self bbox origin).  Self passes through;
    the part joins the canvas."""
    from geocat_arc.object_reasoning.growth import render_part
    window = _eval_param(action, "window", obj, ectx)
    placement = _eval_param(action, "placement", obj, ectx)
    part = render_part(cell_colors_of(obj), tuple(window), tuple(placement))
    if not part:
        raise EvalError("copy_part: empty window")
    return [obj, _build_object(_fresh_id(canvas, ectx), part)]


def apply_connect(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                  ectx: EvalContext) -> list[ARCObject]:
    """M2 verb 1: draw the deterministic straight segment between self and
    params['target'] (RefExpr), colored by params['color'] (ColorExpr).
    Self passes through unchanged; the segment joins the canvas as a new
    object.  EvalError when the two objects do not face each other."""
    from geocat_arc.object_reasoning.growth import connect_segment
    target = evaluate(action.params.get("target"), obj, ectx) \
        if "target" in action.params else None
    if target is None:
        raise EvalError("connect missing parameter expression 'target'")
    color = int(_eval_param(action, "color", obj, ectx))
    seg = connect_segment(obj.cells, target.cells,
                          (canvas.height, canvas.width))
    if not seg:
        raise EvalError("connect: objects do not face each other")
    line = _build_object(_fresh_id(canvas, ectx),
                         {cell: color for cell in seg})
    return [obj, line]


def apply_extract_part(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                       ectx: EvalContext) -> list[ARCObject]:
    """Round 15: extract a sub-region of the INPUT GRID (identified by a
    relational source expression), optionally dihedral-transform it, and
    stamp at a placement.  Self passes through unchanged; the extracted
    region joins the canvas as a new object.

    params:
      source  (RegionExpr) -> (r0, c0, r1, c1) in input grid coords
      transform_k (ScalarExpr, 0..3) -> rot90 count
      transform_flip (ScalarExpr, 0 or 1) -> fliplr before rot
      placement (VecExpr) -> (dr, dc) relative to source bbox origin
    """
    from geocat_arc.object_reasoning.growth import render_extract_part
    source = _eval_param(action, "source", obj, ectx)
    source_bbox = tuple(int(x) for x in source)
    transform_k = int(_eval_param(action, "transform_k", obj, ectx)) \
        if "transform_k" in action.params else 0
    transform_flip = bool(int(_eval_param(action, "transform_flip", obj, ectx))) \
        if "transform_flip" in action.params else False
    placement = _eval_param(action, "placement", obj, ectx)
    if canvas.source_grid is None:
        raise EvalError("extract_part: no source grid on canvas")
    grid_arr = canvas.source_grid.to_numpy()
    part = render_extract_part(grid_arr, source_bbox, transform_k,
                               transform_flip, tuple(int(x) for x in placement))
    if not part:
        raise EvalError("extract_part: empty region")
    return [obj, _build_object(_fresh_id(canvas, ectx), part)]


def apply_fill_line(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                    ectx: EvalContext) -> list[ARCObject]:
    """Draw axis-aligned line(s) through the object's centroid.
    params['axis']: 'horizontal', 'vertical', or 'both' (cross).
    params['color']: ColorExpr for the line color.
    params['extent']: 'to_border' (full grid span) or 'to_object'
        (stop at the nearest other object's bbox edge along that axis).
    Lines are drawn on the canvas background layer (behind objects)."""
    axis_expr = action.params.get("axis")
    axis = axis_expr.args[0] if axis_expr is not None else "both"
    color = int(_eval_param(action, "color", obj, ectx))
    extent_expr = action.params.get("extent")
    extent = extent_expr.args[0] if extent_expr is not None else "to_border"
    cr, cc = obj.centroid
    cr, cc = int(round(cr)), int(round(cc))
    h, w = ectx.grid_ctx.grid.height, ectx.grid_ctx.grid.width
    new_cells = {}
    if axis in ("horizontal", "both"):
        for c in range(w):
            if (cr, c) not in obj.cells:
                new_cells[(cr, c)] = color
    if axis in ("vertical", "both"):
        for r in range(h):
            if (r, cc) not in obj.cells:
                new_cells[(r, cc)] = color
    if new_cells:
        canvas.background_cells.update(new_cells)
    return [obj]


def apply_crop_to(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                  ectx: EvalContext) -> list[ARCObject]:
    """Grid-level shrink action: sets canvas.crop_region to params['region']
    (RegionExpr) evaluated on the selected object; render() then returns
    source_grid.subgrid(crop_region), repeated (tile_h, tile_w) times when
    the optional params['tile_h'] / params['tile_w'] (ScalarExprs) are
    present (count-sized tiled shrink outputs).  Returns [obj]."""
    region = _eval_param(action, "region", obj, ectx)
    canvas.crop_region = tuple(int(x) for x in region)
    th = int(_eval_param(action, "tile_h", obj, ectx)) \
        if "tile_h" in action.params else 1
    tw = int(_eval_param(action, "tile_w", obj, ectx)) \
        if "tile_w" in action.params else 1
    if th < 1 or tw < 1:
        raise EvalError(f"crop_to: non-positive tile counts ({th}, {tw})")
    canvas.tile_counts = (th, tw)
    return [obj]


#: Dispatch: DeltaType -> primitive.  COMPOSITE is executed by applying its
#: parts in order (handled inside apply_action, not a table entry).
ACTION_DISPATCH: dict[DeltaType, ActionFn] = {
    DeltaType.KEEP: apply_keep,
    DeltaType.DELETE: apply_delete,
    DeltaType.TRANSLATE: apply_translate,
    DeltaType.RECOLOR: apply_recolor,
    DeltaType.COPY: apply_copy,
    DeltaType.MOVE_TO: apply_move_to,
    DeltaType.MOVE_UNTIL_ADJACENT: apply_move_until_adjacent,
    DeltaType.SCALE: apply_scale,
    DeltaType.REFLECT: apply_reflect,
    DeltaType.ROTATE: apply_rotate,
    DeltaType.PAINT: apply_paint,
    DeltaType.GROW: apply_grow,
    DeltaType.CONNECT: apply_connect,
    DeltaType.COPY_PART: apply_copy_part,
    DeltaType.SYNTH_COPY: apply_synth_copy,
    DeltaType.CROP_TO: apply_crop_to,
    DeltaType.FILL_LINE: apply_fill_line,
    DeltaType.EXTRACT_PART: apply_extract_part,
}

#: COMPOSITE param-key convention: "<index>:<delta_type>:<param_name>", e.g.
#: {"0:translate:vector": VecExpr, "1:recolor:color": ColorExpr}.  This keeps
#: ActionRule.params a flat dict[str, Expr] (full JSON round-trip through the
#: existing ActionRule serialization) while encoding an ordered part list.
_COMPOSITE_KEY = re.compile(r"^(\d+):([a-z_]+):([a-z_]+)$")


def apply_action(canvas: ObjectCanvas, obj: ARCObject, action: ActionRule,
                 ectx: EvalContext) -> list[ARCObject]:
    """Uniform entry point: dispatch on action.delta_type (COMPOSITE applies
    its parts in order, threading the object through).  Raises
    expressions.EvalError upward on undefined parameters — the caller
    (render_program / inducer) treats that as a failed hypothesis."""
    if action.delta_type is DeltaType.COMPOSITE:
        parts: dict[int, tuple[str, dict]] = {}
        for key, expr in action.params.items():
            m = _COMPOSITE_KEY.match(key)
            if not m:
                raise EvalError(f"COMPOSITE param key {key!r} does not match "
                                f"'<index>:<delta_type>:<param_name>'")
            idx, delta_name, param_name = int(m.group(1)), m.group(2), m.group(3)
            entry = parts.setdefault(idx, (delta_name, {}))
            if entry[0] != delta_name:
                raise EvalError(f"COMPOSITE part {idx} names two delta types "
                                f"({entry[0]!r}, {delta_name!r})")
            entry[1][param_name] = expr
        if not parts:
            raise EvalError("COMPOSITE action with no parts")
        current = [obj]
        for idx in sorted(parts):
            delta_name, params = parts[idx]
            try:
                sub = ActionRule(delta_type=DeltaType(delta_name),
                                 params=params,
                                 parameter_class=action.parameter_class)
            except ValueError:
                raise EvalError(f"COMPOSITE part {idx}: unknown delta type "
                                f"{delta_name!r}") from None
            if sub.delta_type is DeltaType.COMPOSITE:
                raise EvalError("COMPOSITE parts may not nest")
            current = [replacement
                       for o in current
                       for replacement in apply_action(canvas, o, sub, ectx)]
        return current

    fn = ACTION_DISPATCH.get(action.delta_type)
    if fn is None:
        raise EvalError(f"no primitive for delta type {action.delta_type!r}")
    return fn(canvas, obj, action, ectx)


def render(canvas: ObjectCanvas) -> Grid:
    """Materialize the canvas: crop_region if set, else paint objects over a
    (height x width) background frame in canvas.objects order (later objects
    overwrite earlier on overlap), honoring MultiColorObject cell colors.
    Same paint semantics as perception.objects.render_objects, extended with
    per-cell colors."""
    if canvas.crop_region is not None:
        if canvas.source_grid is None:
            raise EvalError("crop_region set but canvas has no source_grid")
        h, w = canvas.source_grid.height, canvas.source_grid.width
        r0, c0, r1, c1 = canvas.crop_region
        r0, c0 = max(0, r0), max(0, c0)
        r1, c1 = min(h, r1), min(w, c1)
        if r0 >= r1 or c0 >= c1:
            raise EvalError(f"empty crop region {canvas.crop_region}")
        cropped = canvas.source_grid.subgrid((r0, c0, r1, c1))
        if canvas.tile_counts and canvas.tile_counts != (1, 1):
            th, tw = canvas.tile_counts
            return Grid(np.tile(cropped.to_numpy(), (th, tw)))
        return cropped
    if canvas.height <= 0 or canvas.width <= 0:
        raise EvalError(f"degenerate output frame "
                        f"{canvas.height}x{canvas.width}")
    data = np.full((canvas.height, canvas.width), canvas.background,
                   dtype=np.int32)
    for (r, c), color in canvas.background_cells.items():
        if 0 <= r < canvas.height and 0 <= c < canvas.width:
            data[r, c] = color
    for obj in canvas.objects:
        for (r, c), color in cell_colors_of(obj).items():
            if 0 <= r < canvas.height and 0 <= c < canvas.width:
                data[r, c] = color
    return Grid(data)


def _grid_anchor(input_grid: Grid, objects: list[ARCObject]) -> ARCObject:
    """Binding for grid-level expressions (output_spec background/region/
    fill): the first segmented object, or a trivial 1-cell object on empty
    grids so const/most_common_color expressions still evaluate."""
    if objects:
        return objects[0]
    return ARCObject(id=-1, cells=frozenset({(0, 0)}),
                     color=input_grid.cell(0, 0), bounding_box=(0, 0, 1, 1))


def render_program(program: ObjectProgram, input_grid: Grid) -> Grid:
    """THE executor (Requirement 4.4): Segment(variant) -> for each object,
    apply the FIRST rule whose selector matches (default_action otherwise)
    -> render per output_spec.  Pure function of (program, input_grid);
    raises EvalError if any expression is undefined on this input (callers
    convert to a failed attempt, never a crash).

    Self-sufficient (Requirement 4.2): a FRESH process deserializing a
    program from JSON must be able to execute it, so the feature/relation
    registries are populated here (idempotent no-op when already done)
    rather than relying on the inducer having run first in this process.

    Stage 2 (STAGE2_REQUIREMENTS Section 2.1): a ComposedProgram chains its
    stages — stage k+1 re-segments stage k's rendered output — through this
    same single execution path."""
    if isinstance(program, ComposedProgram):
        grid = input_grid
        for stage in program.stages:
            grid = render_program(stage, grid)
        return grid
    from .types import FramedProgram, OverlayProgram, ReductionProgram
    from .graduation import ErasePatchProgram
    if isinstance(program, ErasePatchProgram):
        return render_program(program.patch, input_grid)
    if isinstance(program, OverlayProgram):
        out = render_program(program.base, input_grid).to_numpy().copy()
        patch = render_program(program.patch, input_grid).to_numpy()
        if patch.shape == out.shape:
            mask = patch != 0
            out[mask] = patch[mask]
        return Grid(out)
    if isinstance(program, FramedProgram):
        # T = fliplr-then-rot90^k on the way in; inverse on the way out.
        k, flip = program.frame
        a = input_grid.to_numpy()
        if flip:
            a = np.fliplr(a)
        a = np.rot90(a, k)
        out = render_program(program.inner, Grid(np.ascontiguousarray(a)))
        b = np.rot90(out.to_numpy(), -k)
        if flip:
            b = np.fliplr(b)
        return Grid(np.ascontiguousarray(b))
    if isinstance(program, ReductionProgram):
        if program.split.get("kind") == "pixel_rule":
            from .pixel_rules import render_pixel_rule
            return render_pixel_rule(program.params, input_grid)
        if program.split.get("kind") == "symmetry":
            from .symmetry import render_symmetry_completion
            return render_symmetry_completion(program.params, input_grid)
        if program.split.get("kind") == "counting":
            from .counting import render_counting
            return render_counting(program.params, input_grid)
        from .reduction import ReductionError, render_reduction
        try:
            return render_reduction(program, input_grid)
        except ReductionError as exc:
            raise EvalError(str(exc)) from exc
    from .types import GenerativeProgram
    if isinstance(program, GenerativeProgram):
        from .generative import render_generative
        return render_generative(program, input_grid)
    register_builtin_features()
    variant = program.segmentation_variant
    bg_in = background_for(input_grid, variant)
    try:
        objects = segment(input_grid, variant, bg_in)
    except Exception as exc:  # degenerate grids: undefined, not a crash
        raise EvalError(f"segmentation failed: {exc}") from exc

    gctx = GridContext(grid=input_grid, objects=objects, background=bg_in,
                       pair_index=0, role="input", variant=variant)
    anchor = _grid_anchor(input_grid, objects)
    anchor_ectx = EvalContext(obj=anchor, grid_ctx=gctx)

    spec = program.output_spec
    if spec.mode == "constant_shape":
        if not spec.height or not spec.width:
            raise EvalError("constant_shape output_spec without height/width")
        height, width = int(spec.height), int(spec.width)
    elif spec.mode in ("same_as_input", "crop"):
        height, width = input_grid.height, input_grid.width
    else:
        raise EvalError(f"unknown output_spec mode {spec.mode!r}")

    background = bg_in
    if spec.background is not None:
        background = int(evaluate(spec.background, anchor, anchor_ectx))
    if spec.fill is not None:
        # ColorExpr-valued outputs (Section 3.6 shrink_const_out): the fill
        # color becomes the frame; surviving objects still paint on top.
        background = int(evaluate(spec.fill, anchor, anchor_ectx))

    canvas = ObjectCanvas(objects=[], height=height, width=width,
                          background=background, source_grid=input_grid)

    for obj in objects:
        ectx = EvalContext(obj=obj, grid_ctx=gctx)
        action = program.default_action
        for rule in program.rules:
            if evaluate(rule.selector.predicate, obj, ectx):
                action = rule.action
                break
        canvas.objects.extend(apply_action(canvas, obj, action, ectx))

    if spec.mode == "crop" and canvas.crop_region is None:
        if spec.region is None:
            raise EvalError("crop output_spec without region and no CROP_TO "
                            "action fired")
        region = evaluate(spec.region, anchor, anchor_ectx)
        canvas.crop_region = tuple(int(x) for x in region)

    return render(canvas)


def program_apply_fn(program: ObjectProgram) -> Callable:
    """Glue (implemented): wrap a program as the np.ndarray -> np.ndarray
    apply_fn the harness Solution contract expects."""
    import numpy as np

    def _fn(grid_array: "np.ndarray") -> "np.ndarray":
        return render_program(program, Grid(np.asarray(grid_array))).to_numpy()

    return _fn
