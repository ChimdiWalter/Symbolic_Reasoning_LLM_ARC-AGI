"""Per-pair object matching and typed delta extraction (Sections 3.1 / 3.2).

Builds on geocat_arc.perception.matching (greedy overall_similarity matcher
and its component similarity functions) — re-weighted per hypothesis, never
reimplemented — and cross-checks against
geocat_arc.perception.change_detection.detect_changes.

Matching strategy (Section 3.1):
  1. Greedy weighted matching per WEIGHT_PROFILES hypothesis (the
     perception.matching.match_objects algorithm with re-weighted overall
     similarity; deterministic tie-break by (input_id, output_id)).
  2. Translation-invariant shape-identity pass for leftovers
     (shape_signature equality ignoring position and color) so moved and
     recolored objects still match.
  3. Copy detection: remaining unmatched outputs whose shape signature
     equals some input object's are recorded in ``copies[input_id]``
     (one input -> k outputs); sources with an exact cell-color pattern
     match are preferred, then already-matched sources, then smallest id.
  4. Leftover inputs -> deleted_input_ids; leftover outputs with no shape
     match anywhere -> created_output_ids (genuinely new shapes, Stage-2).
  5. Every alternative is pixel-reconciled (reconcile_with_pixels): the
     extracted deltas are applied to the input objects and re-rendered;
     any mismatch with the output grid marks the correspondence lossy
     (is_object_preserving=False).  Lossy alternatives are still returned
     — the inducer skips them or uses them for near-solves only.

Geometric conventions (actions.py must apply the same ones):
  - REFLECT axis, on the object's bbox-relative pattern of shape (h, w):
      "horizontal": (r, c) -> (h-1-r, c)      (flip across horizontal midline)
      "vertical":   (r, c) -> (r, w-1-c)      (flip across vertical midline)
      "diag_main":  (r, c) -> (c, r)          (transpose)
      "diag_anti":  (r, c) -> (w-1-c, h-1-r)  (anti-transpose)
  - ROTATE angle: counterclockwise, np.rot90 semantics:
      90:  (r, c) -> (w-1-c, r);  180: (r, c) -> (h-1-r, w-1-c);
      270: (r, c) -> (c, h-1-r).
  - REFLECT/ROTATE/SCALE deltas carry (dr, dc) = output bbox origin minus
    input bbox origin: the transformed pattern is placed at
    (in_r0 + dr, in_c0 + dc).
  - COPY placements are bbox-origin offsets (dr, dc) per placed copy; an
    optional "colors" list gives a uniform recolor per copy (None = keep
    the source cell colors).
  - Gravity-style motion is observed as a raw TRANSLATE here; the inducer
    may re-express it as MOVE_UNTIL_ADJACENT / gap_closing_vector (both
    spellings are legal per design decision 4).
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Optional

import numpy as np

from geocat_arc.perception.change_detection import detect_changes
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.matching import (
    color_similarity,
    location_similarity,
    shape_similarity,
    size_similarity,
)
from geocat_arc.perception.objects import ARCObject

from .types import (
    ANGLES,
    AXES,
    DeltaType,
    MultiColorObject,
    ObjectDelta,
    PairCorrespondence,
    cell_colors_of,
)
from .synth_verbs import LearnedVerbRegistry

#: Per-run learned-verb registry (set by the engine when its out_dir has a
#: learned_verbs.json; empty otherwise).  Constant within a run — the
#: vocabulary never changes inside a task or a fold (legality rule 3).
LEARNED_VERBS = LearnedVerbRegistry([])


def set_learned_verbs(reg: LearnedVerbRegistry) -> None:
    global LEARNED_VERBS
    LEARNED_VERBS = reg


from .growth import (
    connect_segment,
    detect_grow,
    grow_cavity_leak,
    grow_cross_center,
    grow_ray_deflect,
    find_extract_region,
    find_part_window,
    render_extract_part,
    render_part,
    grow_fill_interior,
    grow_frame_minority,
    grow_halo,
    grow_mirror_edge,
    grow_periodic,
    grow_ray,
    grow_symmetry_complete,
    pattern_cells,
)

#: Similarity re-weightings per matching hypothesis (Section 3.1): motion
#: hypotheses down-weight location, recolor hypotheses down-weight color.
#: Keys: profile name -> (w_shape, w_color, w_size, w_location); weights sum
#: to 1.0.  "default" mirrors perception.matching.overall_similarity.
WEIGHT_PROFILES: dict[str, tuple[float, float, float, float]] = {
    "default": (0.3, 0.2, 0.2, 0.3),
    "motion": (0.45, 0.30, 0.25, 0.0),
    "recolor": (0.45, 0.0, 0.25, 0.30),
    "motion_recolor": (0.60, 0.0, 0.40, 0.0),
    # Reference-frame hypotheses: location similarity is computed after
    # mirroring the INPUT object's position about the grid center along one
    # axis — the correspondence lattice for order-reversal / mirror-position
    # tasks where many same-shape objects make identity-frame greedy matching
    # ambiguous.  Weights = "default"; only the location frame changes.
    "mirror_rows": (0.3, 0.2, 0.2, 0.3),
    "mirror_cols": (0.3, 0.2, 0.2, 0.3),
}

#: Round-16 orphan-tolerant profile: shape+size dominant, location zeroed,
#: color reduced.  Unmatched outputs that are shape-similar to inputs at
#: different positions match under this profile instead of becoming
#: created_output_ids (which poison the correspondence for the preserved
#: objects).  Env-gated: only included in match_pair when
#: ARC_CREATE_COHERENCE=1.  Additive: existing profiles are untouched.
_ORPHAN_TOLERANT_PROFILE: tuple[str, tuple[float, float, float, float]] = (
    "orphan_tolerant", (0.50, 0.10, 0.40, 0.0),
)

#: profile name -> location frame ("identity" unless listed).
_LOCATION_FRAMES: dict[str, str] = {
    "mirror_rows": "rows",
    "mirror_cols": "cols",
}

#: Minimum similarity for a match (perception.matching precedent).
MATCH_THRESHOLD: float = 0.1

#: Pixel-reconciliation tolerance (Section 3.2): unreconciled pixels beyond
#: this fraction of changed pixels mark the pair not object-preserving.
RECONCILE_TOLERANCE: float = 0.05


# ---------------------------------------------------------------------------
# Similarity (perception.matching components, re-weighted per hypothesis)
# ---------------------------------------------------------------------------

def _color_component(a: ARCObject, b: ARCObject) -> float:
    """Color similarity extended for multicolor objects: exact cell-color
    multiset equality for MultiColorObject, perception color_similarity
    otherwise."""
    if isinstance(a, MultiColorObject) or isinstance(b, MultiColorObject):
        return 1.0 if (Counter(cell_colors_of(a).values())
                       == Counter(cell_colors_of(b).values())) else 0.0
    return color_similarity(a, b)


def _location_proxy(a: ARCObject, frame: str,
                    grid_shape: tuple[int, int]) -> ARCObject:
    """The object whose position is used for the location component: ``a``
    itself in the identity frame, or ``a`` translated to its grid-center
    mirror position along one axis (pattern irrelevant for location)."""
    if frame == "rows":
        r0, _c0, r1, _c1 = a.bounding_box
        return a.translated(grid_shape[0] - r1 - r0, 0)
    if frame == "cols":
        _r0, c0, _r1, c1 = a.bounding_box
        return a.translated(0, grid_shape[1] - c1 - c0)
    return a


def _weighted_similarity(a: ARCObject, b: ARCObject,
                         weights: tuple[float, float, float, float],
                         frame: str = "identity",
                         grid_shape: tuple[int, int] = (0, 0)) -> float:
    w_shape, w_color, w_size, w_loc = weights
    loc_a = a if frame == "identity" else _location_proxy(a, frame, grid_shape)
    return (w_shape * shape_similarity(a, b)
            + w_color * _color_component(a, b)
            + w_size * size_similarity(a, b)
            + w_loc * location_similarity(loc_a, b))


# ---------------------------------------------------------------------------
# Pattern helpers (bbox-relative per-cell color maps)
# ---------------------------------------------------------------------------

def _rel_pattern(obj: ARCObject) -> tuple[dict[tuple[int, int], int],
                                          tuple[int, int]]:
    """(pattern, (h, w)): the object's cells relative to its bbox origin,
    mapped to their colors (uniform for plain objects)."""
    r0, c0, r1, c1 = obj.bounding_box
    cc = cell_colors_of(obj)
    return ({(r - r0, c - c0): col for (r, c), col in cc.items()},
            (r1 - r0, c1 - c0))


def _transformed(pattern: dict[tuple[int, int], int], shape: tuple[int, int],
                 kind: str) -> tuple[dict[tuple[int, int], int],
                                     tuple[int, int]]:
    """Apply a named reflection/rotation to a bbox-relative pattern.
    ``kind``: one of AXES or "rot90"/"rot180"/"rot270" (see module
    docstring conventions)."""
    h, w = shape
    if kind == "horizontal":
        fn, out_shape = (lambda r, c: (h - 1 - r, c)), (h, w)
    elif kind == "vertical":
        fn, out_shape = (lambda r, c: (r, w - 1 - c)), (h, w)
    elif kind == "diag_main":
        fn, out_shape = (lambda r, c: (c, r)), (w, h)
    elif kind == "diag_anti":
        fn, out_shape = (lambda r, c: (w - 1 - c, h - 1 - r)), (w, h)
    elif kind == "rot90":
        fn, out_shape = (lambda r, c: (w - 1 - c, r)), (w, h)
    elif kind == "rot180":
        fn, out_shape = (lambda r, c: (h - 1 - r, w - 1 - c)), (h, w)
    elif kind == "rot270":
        fn, out_shape = (lambda r, c: (c, h - 1 - r)), (w, h)
    else:  # pragma: no cover - defended by callers
        raise ValueError(f"unknown transform kind: {kind}")
    return {fn(r, c): col for (r, c), col in pattern.items()}, out_shape


def _upscaled(pattern: dict[tuple[int, int], int], shape: tuple[int, int],
              factor: int) -> tuple[dict[tuple[int, int], int],
                                    tuple[int, int]]:
    """Integer upscale: every cell becomes a factor x factor block."""
    h, w = shape
    out: dict[tuple[int, int], int] = {}
    for (r, c), col in pattern.items():
        for i in range(factor):
            for j in range(factor):
                out[(r * factor + i, c * factor + j)] = col
    return out, (h * factor, w * factor)


def _downscaled(pattern: dict[tuple[int, int], int], shape: tuple[int, int],
                factor: int) -> tuple[dict[tuple[int, int], int],
                                      tuple[int, int]]:
    """Integer downscale (inverse of _upscaled; block top-left representative)."""
    h, w = shape
    out = {(r // factor, c // factor): col
           for (r, c), col in pattern.items()
           if r % factor == 0 and c % factor == 0}
    return out, (h // factor, w // factor)


# ---------------------------------------------------------------------------
# Minimal typed delta for one matched (o_in, o_out) pair (Section 3.2)
# ---------------------------------------------------------------------------

def _minimal_delta(in_obj: ARCObject, out_obj: ARCObject,
                   pair_index: int,
                   grid_shape: tuple[int, int] = (0, 0),
                   grid: Any = None,
                   ) -> tuple[DeltaType, dict[str, Any], int]:
    """(delta_type, raw params, residual_pixels) — checked minimal-first:
    KEEP, TRANSLATE, RECOLOR, COMPOSITE(translate+recolor), REFLECT, ROTATE,
    SCALE, PAINT, GROW (round 2: output ⊇ input, added cells reproducible by
    a generic growth mode); otherwise the best of KEEP/TRANSLATE with a pixel
    residual."""
    in_cc = cell_colors_of(in_obj)
    out_cc = cell_colors_of(out_obj)
    if in_cc == out_cc:
        return DeltaType.KEEP, {}, 0

    pin, shape_in = _rel_pattern(in_obj)
    pout, shape_out = _rel_pattern(out_obj)
    dr = out_obj.bounding_box[0] - in_obj.bounding_box[0]
    dc = out_obj.bounding_box[1] - in_obj.bounding_box[1]
    moved = (dr, dc) != (0, 0)
    out_colors = set(pout.values())
    uniform_out = len(out_colors) == 1

    # TRANSLATE: identical relative pattern (mask AND colors), new position.
    if pin == pout and moved:
        return DeltaType.TRANSLATE, {"dr": dr, "dc": dc}, 0

    # RECOLOR in place: identical absolute cells, uniform new color.
    if in_obj.cells == out_obj.cells and uniform_out:
        return DeltaType.RECOLOR, {"color": int(next(iter(out_colors)))}, 0

    # COMPOSITE translate+recolor: same mask, moved, uniform new color.
    if set(pin) == set(pout) and moved and uniform_out:
        color = int(next(iter(out_colors)))
        parts = [
            ObjectDelta(pair_index, DeltaType.TRANSLATE, in_obj.id,
                        [out_obj.id], {"dr": dr, "dc": dc}).to_dict(),
            ObjectDelta(pair_index, DeltaType.RECOLOR, in_obj.id,
                        [out_obj.id], {"color": color}).to_dict(),
        ]
        return DeltaType.COMPOSITE, {"parts": parts}, 0

    # REFLECT(axis) (+ implicit translate via dr,dc).
    for axis in AXES:
        p2, s2 = _transformed(pin, shape_in, axis)
        if s2 == shape_out and p2 == pout:
            return DeltaType.REFLECT, {"axis": axis, "dr": dr, "dc": dc}, 0

    # ROTATE(angle) (+ implicit translate via dr,dc).
    for angle in ANGLES:
        p2, s2 = _transformed(pin, shape_in, f"rot{angle}")
        if s2 == shape_out and p2 == pout:
            return DeltaType.ROTATE, {"angle": int(angle), "dr": dr, "dc": dc}, 0

    # SCALE(factor): integer up (factor >= 2) or down (negative = shrink /|f|).
    (hi, wi), (ho, wo) = shape_in, shape_out
    if hi and wi and ho % hi == 0 and wo % wi == 0 and ho // hi == wo // wi \
            and ho // hi > 1:
        factor = ho // hi
        p2, _ = _upscaled(pin, shape_in, factor)
        if p2 == pout:
            return DeltaType.SCALE, {"factor": factor, "dr": dr, "dc": dc}, 0
    if ho and wo and hi % ho == 0 and wi % wo == 0 and hi // ho == wi // wo \
            and hi // ho > 1:
        factor = hi // ho
        p2, _ = _upscaled(pout, shape_out, factor)
        if p2 == pin:
            return DeltaType.SCALE, {"factor": -factor, "dr": dr, "dc": dc}, 0

    # PAINT (template stamping): identical absolute cell set, colors
    # rewritten NON-uniformly (uniform rewrites were caught by RECOLOR above;
    # in-place symmetric reflections/rotations were caught earlier).  The
    # induced parameter is a same-mask source REF whose pattern is copied —
    # the raw delta carries no parameters (the ground truth is the output
    # object's cells, checked by simulation).
    if in_obj.cells == out_obj.cells:
        pattern = sorted([[int(r), int(c)], int(col)]
                         for (r, c), col in pout.items())
        return DeltaType.PAINT, {"pattern": pattern}, 0

    # GROW (round 2): the output contains every input cell (same colors)
    # plus added cells reproducible by a generic growth mode
    # (fill_interior / halo / ray / exact pattern fallback).
    if grid_shape != (0, 0):
        grow_params = detect_grow(in_cc, out_cc, grid_shape, grid)
        if grow_params is not None:
            return DeltaType.GROW, grow_params, 0

    # Fallback: the delta vocabulary cannot explain this match; emit the
    # better of KEEP / TRANSLATE-to-out-bbox with an honest pixel residual.
    def residual_of(pred: dict[tuple[int, int], int]) -> int:
        wrong = sum(1 for cell, col in pred.items() if out_cc.get(cell) != col)
        missing = sum(1 for cell in out_cc if cell not in pred)
        return wrong + missing

    keep_residual = residual_of(in_cc)
    translated = {(r + dr, c + dc): col for (r, c), col in in_cc.items()}
    translate_residual = residual_of(translated)
    if moved and translate_residual < keep_residual:
        return DeltaType.TRANSLATE, {"dr": dr, "dc": dc}, translate_residual
    return DeltaType.KEEP, {}, keep_residual


# ---------------------------------------------------------------------------
# Per-profile greedy matching (Section 3.1)
# ---------------------------------------------------------------------------

def _match_one_profile(in_objects: list[ARCObject],
                       out_objects: list[ARCObject],
                       profile: str,
                       weights: tuple[float, float, float, float],
                       pair_index: int,
                       grid_shape: tuple[int, int] = (0, 0)) -> PairCorrespondence:
    """One correspondence hypothesis: greedy weighted matching + shape
    identity pass + copy detection (all deterministic)."""
    frame = _LOCATION_FRAMES.get(profile, "identity")
    # 1. Greedy weighted matching (match_objects algorithm, re-weighted).
    scored = [(_weighted_similarity(a, b, weights, frame, grid_shape),
               a.id, b.id)
              for a in in_objects for b in out_objects]
    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    used_in: set[int] = set()
    used_out: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for sim, iid, oid in scored:
        if sim <= MATCH_THRESHOLD:
            break
        if iid in used_in or oid in used_out:
            continue
        matches.append((iid, oid, float(sim)))
        used_in.add(iid)
        used_out.add(oid)

    # 2. Translation-invariant shape-identity pass for leftovers.
    leftovers = [(_weighted_similarity(a, b, weights, frame, grid_shape),
                  a.id, b.id)
                 for a in in_objects if a.id not in used_in
                 for b in out_objects if b.id not in used_out
                 if a.shape_signature == b.shape_signature]
    leftovers.sort(key=lambda t: (-t[0], t[1], t[2]))
    for sim, iid, oid in leftovers:
        if iid in used_in or oid in used_out:
            continue
        matches.append((iid, oid, float(sim)))
        used_in.add(iid)
        used_out.add(oid)

    # 3. Copy detection: unmatched outputs sharing a shape signature with
    #    some input (one-to-many; candidate COPY).
    primary_of = {iid: oid for iid, oid, _ in matches}
    copies: dict[int, list[int]] = {}
    claimed: set[int] = set()
    for out in sorted(out_objects, key=lambda o: o.id):
        if out.id in used_out:
            continue
        sources = [a for a in in_objects
                   if a.shape_signature == out.shape_signature]
        if not sources:
            continue
        p_out, _ = _rel_pattern(out)
        exact = [a for a in sources if _rel_pattern(a)[0] == p_out]
        pool = exact if exact else sources
        (or_, oc_) = out.centroid

        def _dist2(a: ARCObject) -> float:
            ar, ac = a.centroid
            return (ar - or_) ** 2 + (ac - oc_) ** 2

        # nearest same-shape source (primary-matched sources preferred):
        # distributes multi-seed copy growth to the seed that spawned it
        # instead of piling every copy onto the smallest id.
        pool = sorted(pool, key=lambda a: (0 if a.id in primary_of else 1,
                                           _dist2(a), a.id))
        copies.setdefault(pool[0].id, []).append(out.id)
        claimed.add(out.id)
    # copies[i] lists ALL of i's output ids (primary match first, if any).
    for iid in list(copies):
        if iid in primary_of:
            copies[iid] = [primary_of[iid]] + copies[iid]

    deleted = sorted(o.id for o in in_objects
                     if o.id not in used_in and o.id not in copies)
    created = sorted(o.id for o in out_objects
                     if o.id not in used_out and o.id not in claimed)
    return PairCorrespondence(
        pair_index=pair_index,
        input_objects=list(in_objects),
        output_objects=list(out_objects),
        matches=matches,
        copies=copies,
        deleted_input_ids=deleted,
        created_output_ids=created,
        weights_profile=profile,
    )


def _unexplained_count(corr: PairCorrespondence,
                       deltas: list[ObjectDelta]) -> int:
    """Unmatched-object count for best-first ordering: deleted inputs +
    genuinely-created outputs + matches whose delta left a residual."""
    lossy_matches = sum(1 for d in deltas
                        if d.input_object_id is not None
                        and d.delta_type is not DeltaType.DELETE
                        and d.residual_pixels > 0)
    return (len(corr.deleted_input_ids) + len(corr.created_output_ids)
            + lossy_matches)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _ray_ext_rows(input_grid: Grid):
    """The input grid as tuple-of-tuples, or None when the round-20 gate is
    off.  Gating HERE is what makes ARC_RAY_EXT genuinely zero-cost: with the
    flag unset nothing is materialized and every downstream grid-aware branch
    short-circuits on `grid is None`."""
    from .growth import _ray_ext_enabled, as_rows
    if not _ray_ext_enabled():
        return None
    return as_rows(input_grid)


def match_pair(in_objects: list[ARCObject], out_objects: list[ARCObject],
               input_grid: Grid, output_grid: Grid, pair_index: int = 0,
               profiles: list[str] | None = None) -> list[PairCorrespondence]:
    """Match one train pair's objects under each weighting profile.

    For each profile in ``profiles`` (default: all WEIGHT_PROFILES keys, in
    dict order), run greedy matching (the perception.matching.match_objects
    algorithm with re-weighted overall similarity), then:

      - attempt translation-invariant shape-identity matching (shape_signature
        equality ignoring position/color) for leftovers;
      - unmatched input objects  -> deleted_input_ids (candidate DELETE);
      - unmatched output objects -> created_output_ids; when a created output
        shares a shape signature with some input object, record it in
        ``copies[input_id]`` instead (one-to-many, candidate COPY);
      - fill unreconciled_pixels / is_object_preserving via
        reconcile_with_pixels().

    Returns one PairCorrespondence per profile, DEDUPLICATED by match set and
    ordered best-first (fewest unmatched objects, then fewest unreconciled
    pixels).  Ambiguity rule (Section 3.1): ties are all returned; downstream
    zero-conflict induction disambiguates (a wrong matching produces selector
    conflicts and dies).
    """
    names = list(profiles) if profiles is not None else list(WEIGHT_PROFILES)
    # Round 16: append orphan-tolerant profile when ARC_CREATE_COHERENCE=1
    # and no explicit profiles list was passed.  Additive only: existing
    # profiles untouched, alternatives machinery already returns multiple.
    import os as _os
    _all_weights = dict(WEIGHT_PROFILES)
    if profiles is None and _os.environ.get(
            "ARC_CREATE_COHERENCE", "") not in ("", "0"):
        ot_name, ot_weights = _ORPHAN_TOLERANT_PROFILE
        if ot_name not in names:
            names.append(ot_name)
            _all_weights[ot_name] = ot_weights
    alternatives: list[tuple[int, int, int, PairCorrespondence]] = []
    seen: set[tuple] = set()
    grid_shape = (input_grid.height, input_grid.width)
    for order, name in enumerate(names):
        weights = _all_weights[name]
        corr = _match_one_profile(in_objects, out_objects, name, weights,
                                  pair_index, grid_shape)
        corr.grid_shape = (output_grid.height, output_grid.width)
        # Round 20: carry the INPUT scene so the grid-aware GROW modes can
        # read obstacles / the background off it.  Re-derived here per pair,
        # i.e. inside the fold-re-derived path.
        corr.input_grid_rows = _ray_ext_rows(input_grid)
        key = (tuple(sorted((i, o) for i, o, _ in corr.matches)),
               tuple(sorted((i, tuple(v)) for i, v in corr.copies.items())),
               tuple(corr.deleted_input_ids),
               tuple(corr.created_output_ids))
        if key in seen:
            continue
        seen.add(key)
        reconcile_with_pixels(corr, input_grid, output_grid)
        deltas = extract_deltas(corr)
        alternatives.append((_unexplained_count(corr, deltas),
                             corr.unreconciled_pixels, order, corr))
    alternatives.sort(key=lambda t: (t[0], t[1], t[2]))
    return [corr for _, _, _, corr in alternatives]


def reconcile_with_pixels(corr: PairCorrespondence, input_grid: Grid,
                          output_grid: Grid) -> PairCorrespondence:
    """Section 3.2 cross-check: pixel diff totals from
    perception.change_detection.detect_changes must reconcile with the
    object-delta account.  Applies the extracted deltas to the input objects
    and re-renders; any mismatch with the output grid is unreconciled.
    Sets corr.unreconciled_pixels and corr.is_object_preserving (False if
    residue > RECONCILE_TOLERANCE of changed pixels); returns corr (mutated
    in place for convenience)."""
    deltas = extract_deltas(corr)
    out = output_grid.to_numpy()
    height, width = out.shape
    background = _infer_background(output_grid, corr.output_objects)
    canvas = np.full((height, width), background, dtype=out.dtype)
    in_by_id = {o.id: o for o in corr.input_objects}
    for delta in deltas:
        if delta.delta_type is DeltaType.DELETE or delta.input_object_id is None:
            continue  # deletions paint nothing; orphan creations are residue
        for (r, c), col in _predict_cells(delta,
                                          in_by_id[delta.input_object_id],
                                          (height, width),
                                          corr.input_grid_rows).items():
            if 0 <= r < height and 0 <= c < width:
                canvas[r, c] = col
    unreconciled = int(np.sum(canvas != out))
    changed = detect_changes(input_grid, output_grid).num_cells_changed
    corr.unreconciled_pixels = unreconciled
    corr.is_object_preserving = (unreconciled == 0
                                 or unreconciled <= RECONCILE_TOLERANCE * changed)
    return corr


def extract_deltas(correspondence: PairCorrespondence,
                   input_grid: "Optional[np.ndarray]" = None) -> list[ObjectDelta]:
    """Compute the minimal typed delta for every object in one pair
    (Section 3.2 vocabulary):

      - matched (o_in, o_out): KEEP if identical; else the single minimal
        delta among TRANSLATE(dr,dc) / RECOLOR(c') / REFLECT(axis)+translate /
        ROTATE(angle)+translate / SCALE(f); COMPOSITE(translate+recolor) when
        both position and color changed.  Raw observed values go in
        ObjectDelta.params (e.g. {"dr": 2, "dc": 0}); any pixels the delta
        cannot account for go in residual_pixels.
      - deleted_input_ids -> DELETE.
      - copies[i] = [o1..ok] -> one COPY delta with output_object_ids and
        params {"k": k, "placements": [(dr,dc)...]}.
      - created outputs with no shape match anywhere -> a DELETE-less residual:
        emit a delta with delta_type=COPY, input_object_id=None and
        residual_pixels = object size (genuinely new shapes are out of scope
        for Stage 1; they surface as unexplained residue in NearSolveRecords).

    Deterministic: iterates objects by id.  One delta per input object plus
    one per orphan output object.
    """
    corr = correspondence
    out_by_id = {o.id: o for o in corr.output_objects}
    match_of: dict[int, int] = {}
    for iid, oid, _sim in corr.matches:
        match_of.setdefault(iid, oid)
    claimed = {oid for oids in corr.copies.values() for oid in oids}

    deltas: list[ObjectDelta] = []
    for in_obj in sorted(corr.input_objects, key=lambda o: o.id):
        iid = in_obj.id
        if iid in corr.copies:
            oids = list(corr.copies[iid])
            placements: list[list[int]] = []
            colors: list[Optional[int]] = []
            residual = 0
            p_in, _ = _rel_pattern(in_obj)
            for oid in oids:
                out_obj = out_by_id[oid]
                placements.append([
                    out_obj.bounding_box[0] - in_obj.bounding_box[0],
                    out_obj.bounding_box[1] - in_obj.bounding_box[1],
                ])
                p_out, _ = _rel_pattern(out_obj)
                if p_out == p_in:
                    colors.append(None)
                else:
                    out_colors = set(p_out.values())
                    if set(p_out) == set(p_in) and len(out_colors) == 1:
                        colors.append(int(next(iter(out_colors))))
                    else:  # same mask guaranteed by sig equality; colors odd
                        colors.append(None)
                        residual += sum(1 for cell in p_out
                                        if p_in.get(cell) != p_out[cell])
            params: dict[str, Any] = {"k": len(oids), "placements": placements}
            if any(c is not None for c in colors):
                params["colors"] = colors
            deltas.append(ObjectDelta(corr.pair_index, DeltaType.COPY, iid,
                                      oids, params, residual))
        elif iid in match_of:
            oid = match_of[iid]
            dtype, params, residual = _minimal_delta(in_obj, out_by_id[oid],
                                                     corr.pair_index,
                                                     corr.grid_shape,
                                                     corr.input_grid_rows)
            deltas.append(ObjectDelta(corr.pair_index, dtype, iid, [oid],
                                      params, residual))
        else:
            deltas.append(ObjectDelta(corr.pair_index, DeltaType.DELETE, iid,
                                      [], {}, 0))

    matched_out = set(match_of.values()) | claimed

    # CONNECT detection (M2 verb 1, round 6): an orphan that is a straight
    # 1-wide segment whose deterministic connect_segment between two
    # DIFFERENT matched hosts reproduces it EXACTLY becomes a CONNECT delta
    # on the first host's input object (the host keeps its own delta only
    # if it was KEEP — scoped to the battery-validated family).
    connected: set[int] = set()
    matched_pairs0 = {oid: iid for iid, oid in match_of.items()}
    for out_obj in sorted(corr.output_objects, key=lambda o: o.id):
        if out_obj.id in (set(match_of.values()) | claimed):
            continue
        om_h = out_obj.bbox_height
        om_w = out_obj.bbox_width
        if om_h != 1 and om_w != 1:
            continue
        halo = {(r + dr, c + dc) for (r, c) in out_obj.cells
                for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
        touched = sorted({o.id for o in corr.output_objects
                          if o.id in matched_pairs0 and (halo & o.cells)})
        if len(touched) != 2:
            continue
        a = next(o for o in corr.output_objects if o.id == touched[0])
        b = next(o for o in corr.output_objects if o.id == touched[1])
        seg = connect_segment(a.cells, b.cells, corr.grid_shape)
        if seg is None or set(seg) != set(out_obj.cells):
            continue
        colors = set(cell_colors_of(out_obj).values())
        if len(colors) != 1:
            continue
        # SYMMETRIC attribution: both endpoints CONNECT toward each other
        # (the segment renders idempotently); a one-sided delta would force
        # selector induction to separate two symmetric endpoints.
        ixs = []
        for k in (0, 1):
            host_iid = matched_pairs0[touched[k]]
            ix = next((i for i, d in enumerate(deltas)
                       if d.input_object_id == host_iid), None)
            if ix is None or deltas[ix].delta_type is not DeltaType.KEEP:
                ixs = []
                break
            ixs.append((ix, host_iid, touched[k], touched[1 - k]))
        if not ixs:
            continue
        for ix, host_iid, own_out, other_out in ixs:
            deltas[ix] = ObjectDelta(
                corr.pair_index, DeltaType.CONNECT, host_iid,
                [own_out, out_obj.id],
                {"other_output_id": other_out,
                 "color": int(next(iter(colors)))}, 0)
        connected.add(out_obj.id)

    # LEARNED-VERB detection (AUTONOMOUS M2, round 7): registered chains
    # from learned_verbs.json claim orphans that are a chain-image of some
    # input object (mirrored/rotated/scaled copies the base COPY detection
    # cannot type).  Runs before COPY_PART (more specific spellings first).
    synthed: set[int] = set()
    if LEARNED_VERBS.verbs:
        for out_obj in sorted(corr.output_objects, key=lambda o: o.id):
            if out_obj.id in (set(match_of.values()) | claimed | connected):
                continue
            occ = cell_colors_of(out_obj)
            hit = None
            for in_obj in sorted(corr.input_objects, key=lambda o: o.id):
                params = LEARNED_VERBS.match_orphan(
                    cell_colors_of(in_obj), occ)
                if params is not None:
                    hit = (in_obj, params)
                    break
            if hit is None:
                continue
            in_obj, params = hit
            ix = next((i for i, d in enumerate(deltas)
                       if d.input_object_id == in_obj.id), None)
            if ix is None or deltas[ix].delta_type is not DeltaType.KEEP:
                continue
            own_out = match_of.get(in_obj.id)
            deltas[ix] = ObjectDelta(
                corr.pair_index, DeltaType.SYNTH_COPY, in_obj.id,
                ([own_out] if own_out is not None else []) + [out_obj.id],
                params, 0)
            synthed.add(out_obj.id)

    # COPY_PART detection (M2 verb 2, round 6): an orphan that is an EXACT
    # color-matching subwindow of some input object becomes a COPY_PART
    # delta on that source (deterministic: smallest source id with a match;
    # sources whose own delta is KEEP preferred so the group stays clean).
    parted: set[int] = set()
    for out_obj in sorted(corr.output_objects, key=lambda o: o.id):
        if out_obj.id in (set(match_of.values()) | claimed | connected
                          | synthed):
            continue
        occ = cell_colors_of(out_obj)
        hit = None
        for in_obj in sorted(corr.input_objects, key=lambda o: o.id):
            if len(in_obj.cells) <= len(occ.keys()):
                continue
            params = find_part_window(cell_colors_of(in_obj), occ)
            if params is not None:
                hit = (in_obj, params)
                break
        if hit is None:
            continue
        in_obj, params = hit
        ix = next((i for i, d in enumerate(deltas)
                   if d.input_object_id == in_obj.id), None)
        if ix is None or deltas[ix].delta_type is not DeltaType.KEEP:
            continue
        own_out = match_of.get(in_obj.id)
        deltas[ix] = ObjectDelta(
            corr.pair_index, DeltaType.COPY_PART, in_obj.id,
            ([own_out] if own_out is not None else []) + [out_obj.id],
            params, 0)
        parted.add(out_obj.id)

    # EXTRACT_PART detection (round 15, M2): an orphan that is an exact (or
    # dihedral-transformed) sub-region of the INPUT GRID becomes an
    # EXTRACT_PART delta.  Env-gated: ARC_EXTRACT_PART=1 enables (default
    # off, zero cost).  Runs AFTER COPY_PART (which is object-scoped and
    # more specific); orphans already claimed are skipped.
    # Attribution: find the input object whose bbox CONTAINS the source
    # region (relational path for the inducer); that object must currently
    # have a KEEP delta so the group stays clean.
    import os as _os
    extracted: set[int] = set()
    if input_grid is not None and _os.environ.get(
            "ARC_EXTRACT_PART", "") not in ("", "0"):
        grid_arr = input_grid
        for out_obj in sorted(corr.output_objects, key=lambda o: o.id):
            if out_obj.id in (set(match_of.values()) | claimed | connected
                              | synthed | parted):
                continue
            occ = cell_colors_of(out_obj)
            # Guard: mono-color orphans are trivially matchable to any same-
            # color grid rectangle.  Require >= 2 distinct colors OR a
            # multi-color source region to avoid stealing deltas from
            # existing solves (v16 lesson, round-15 regression on 9ddd00f0).
            if len(set(occ.values())) < 2:
                continue
            candidates = find_extract_region(grid_arr, occ)
            if not candidates:
                continue
            # Pick the best candidate: prefer identity transform, then the
            # one whose source bbox is contained by an input object with KEEP.
            hit = None
            for cand in candidates:
                sb = cand["source_bbox"]
                # Find the input object whose bbox fully contains source_bbox
                for in_obj in sorted(corr.input_objects, key=lambda o: o.id):
                    ir0, ic0, ir1, ic1 = in_obj.bounding_box
                    if ir0 <= sb[0] and ic0 <= sb[1] and ir1 >= sb[2] and ic1 >= sb[3]:
                        ix = next((j for j, d in enumerate(deltas)
                                   if d.input_object_id == in_obj.id), None)
                        if ix is not None and deltas[ix].delta_type is DeltaType.KEEP:
                            hit = (in_obj, cand, ix)
                            break
                if hit is not None:
                    break
            if hit is None:
                continue
            in_obj, cand, ix = hit
            own_out = match_of.get(in_obj.id)
            deltas[ix] = ObjectDelta(
                corr.pair_index, DeltaType.EXTRACT_PART, in_obj.id,
                ([own_out] if own_out is not None else []) + [out_obj.id],
                {"source_bbox": list(cand["source_bbox"]),
                 "transform_k": cand["transform_k"],
                 "transform_flip": cand["transform_flip"],
                 "placement": list(cand["placement"])}, 0)
            extracted.add(out_obj.id)

    # ORPHAN ABSORPTION (round 4, the appendage family): an orphan output
    # object 8-adjacent to EXACTLY ONE matched output object is absorbed
    # into that match — the (input, host∪orphan) pair is re-typed through
    # _minimal_delta, and only a CLEAN re-type (residual 0, GROW) replaces
    # the host's delta.  Deterministic: orphans processed in id order,
    # cumulative unions.  Segmentation carved the appendage separately;
    # semantically it is growth of its host.
    absorbed: set[int] = set()
    host_union: dict[int, dict] = {}   # host OUT id -> union cell colors
    host_extra: dict[int, list[int]] = {}
    delta_ix = {tuple(d.output_object_ids): i for i, d in enumerate(deltas)
                if d.input_object_id is not None and d.output_object_ids}
    matched_pairs = {oid: iid for iid, oid in match_of.items()}
    for out_obj in sorted(corr.output_objects, key=lambda o: o.id):
        if out_obj.id in matched_out or out_obj.id in connected \
                or out_obj.id in parted or out_obj.id in synthed \
                or out_obj.id in extracted:
            continue
        halo = {(r + dr, c + dc) for (r, c) in out_obj.cells
                for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
        touched = [o for o in corr.output_objects
                   if o.id in matched_pairs and (halo & o.cells)]
        if len(touched) != 1:
            continue
        host = touched[0]
        iid = matched_pairs[host.id]
        in_obj = next(o for o in corr.input_objects if o.id == iid)
        base = host_union.get(host.id) or cell_colors_of(host)
        union_cc = dict(base)
        union_cc.update(cell_colors_of(out_obj))
        union_obj = MultiColorObject(
            id=host.id, cells=frozenset(union_cc),
            color=host.color,
            bounding_box=(min(r for r, _ in union_cc),
                          min(c for _, c in union_cc),
                          max(r for r, _ in union_cc) + 1,
                          max(c for _, c in union_cc) + 1),
            cell_colors=union_cc)
        dtype, params, resid = _minimal_delta(in_obj, union_obj,
                                              corr.pair_index,
                                              corr.grid_shape,
                                              corr.input_grid_rows)
        if resid == 0 and dtype is DeltaType.GROW:
            host_union[host.id] = union_cc
            host_extra.setdefault(host.id, []).append(out_obj.id)
            ix = delta_ix.get((host.id,))
            if ix is None:
                ix = next(i for i, d in enumerate(deltas)
                          if d.input_object_id == iid
                          and host.id in d.output_object_ids)
                delta_ix[(host.id,)] = ix
            deltas[ix] = ObjectDelta(
                corr.pair_index, dtype, iid,
                [host.id] + host_extra[host.id], params, 0)
            absorbed.add(out_obj.id)

    for out_obj in sorted(corr.output_objects, key=lambda o: o.id):
        if out_obj.id in matched_out or out_obj.id in absorbed \
                or out_obj.id in connected or out_obj.id in parted \
                or out_obj.id in synthed or out_obj.id in extracted:
            continue
        deltas.append(ObjectDelta(corr.pair_index, DeltaType.COPY, None,
                                  [out_obj.id], {"k": 1},
                                  residual_pixels=out_obj.size))
    return deltas


def delta_histogram(deltas: list[ObjectDelta]) -> dict[str, int]:
    """Glue (implemented): {delta_type.value: count} — the NearSolveRecord /
    failure-clustering signature (Section 5.1/5.2)."""
    hist: dict[str, int] = {}
    for d in deltas:
        hist[d.delta_type.value] = hist.get(d.delta_type.value, 0) + 1
    return hist


# ---------------------------------------------------------------------------
# Delta simulation (reconciliation re-render)
# ---------------------------------------------------------------------------

def _predict_cells(delta: ObjectDelta,
                   in_obj: ARCObject,
                   bounds: tuple[int, int] = (0, 0),
                   grid: Any = None,
                   ) -> dict[tuple[int, int], int]:
    """Absolute (r, c) -> color cells this delta predicts for its input
    object.  DELETE / orphan COPY predict nothing (handled by callers).
    ``bounds`` (output grid h, w) is required by GROW halo/ray modes;
    ``grid`` (the INPUT scene, round 20) by the grid-aware GROW modes."""
    dtype = delta.delta_type
    params = delta.params
    cc = cell_colors_of(in_obj)
    if dtype is DeltaType.KEEP:
        return dict(cc)
    if dtype is DeltaType.SYNTH_COPY:
        chain = LEARNED_VERBS.chain_of(params["verb"])
        if chain is None:
            return dict(cc)
        from .synth_verbs import apply_verb_chain
        img = apply_verb_chain(chain, set(cc)) or set()
        sr0 = min(r for r, _ in cc); sc0 = min(c for _, c in cc)
        dr, dc = params["placement"]
        col = params.get("color")
        merged = dict(cc)
        src_color = next(iter(set(cc.values())))
        for (r, c) in img:
            merged[(sr0 + dr + r, sc0 + dc + c)] = \
                int(col) if col is not None else src_color
        return merged
    if dtype is DeltaType.COPY_PART:
        merged = dict(cc)
        merged.update(render_part(cc, params["window"], params["placement"]))
        return merged
    if dtype is DeltaType.EXTRACT_PART:
        # host cells + the extracted region (needs the input grid to render;
        # at reconcile time we return just cc so the segment is accounted
        # via the orphan id like CONNECT — the renderer draws it at apply).
        return dict(cc)
    if dtype is DeltaType.CONNECT:
        # host cells + the deterministic segment toward the other output
        return dict(cc)  # segment cells are accounted by the other host's
                         # own delta at reconcile time via the orphan id in
                         # output_object_ids; renderer draws it (actions)
    if dtype is DeltaType.GROW:
        if "dr" in params or "dc" in params:   # translate+grow (round 4)
            dr, dc = int(params.get("dr", 0)), int(params.get("dc", 0))
            cc = {(r + dr, c + dc): col for (r, c), col in cc.items()}
        cells = set(cc)
        mode = params["mode"]
        if mode == "fill_interior":
            added = grow_fill_interior(cells, params["color"])
        elif mode == "halo":
            added = grow_halo(cells, params["color"],
                              int(params.get("conn", 4)), bounds)
        elif mode == "ray":
            added = grow_ray(cells, params["direction"], params["color"],
                             params.get("length"), bounds)
        elif mode == "symmetry_complete":
            added = grow_symmetry_complete(cc, params["axis"]) or {}
        elif mode == "mirror_edge":
            added = grow_mirror_edge(cc, params["direction"], bounds) or {}
        elif mode in ("periodic_self", "periodic_bbox"):   # round 19
            added = grow_periodic(
                cc, params["direction"], bounds,
                "self" if mode == "periodic_self" else "bbox") or {}
        elif mode == "frame_minority":                     # round 19
            added = grow_frame_minority(cc, bounds) or {}
        elif mode == "cross_center":                       # round 20
            added = grow_cross_center(cells, grid, params["color"]) or {}
        elif mode == "cavity_leak":                        # round 20
            added = grow_cavity_leak(cells, grid, params["color"]) or {}
        elif mode == "ray_deflect":                        # round 20
            added = grow_ray_deflect(cells, grid, params["direction"],
                                     params["color"]) or {}
        else:  # pattern (colored, or color-abstracted mask + color)
            added = pattern_cells(cells, params["pattern"],
                                  params.get("color"))
        merged = dict(cc)
        merged.update(added)
        return merged
    if dtype is DeltaType.TRANSLATE:
        dr, dc = int(params["dr"]), int(params["dc"])
        return {(r + dr, c + dc): col for (r, c), col in cc.items()}
    if dtype is DeltaType.RECOLOR:
        color = int(params["color"])
        return {cell: color for cell in cc}
    if dtype is DeltaType.PAINT:
        r0, c0 = in_obj.bounding_box[:2]
        return {(r0 + int(r), c0 + int(c)): int(col)
                for (r, c), col in params["pattern"]}
    if dtype is DeltaType.MOVE_TO:
        r0, c0 = in_obj.bounding_box[:2]
        nr, nc = int(params["r0"]), int(params["c0"])
        return {(r - r0 + nr, c - c0 + nc): col for (r, c), col in cc.items()}
    if dtype is DeltaType.COPY:
        cells: dict[tuple[int, int], int] = {}
        colors = params.get("colors")
        for i, (dr, dc) in enumerate(params["placements"]):
            override = colors[i] if colors else None
            for (r, c), col in cc.items():
                cells[(int(r + dr), int(c + dc))] = \
                    int(override) if override is not None else col
        return cells
    if dtype is DeltaType.COMPOSITE:
        cells = dict(cc)
        for part in params["parts"]:
            pd = ObjectDelta.from_dict(part) if isinstance(part, dict) else part
            if pd.delta_type is DeltaType.TRANSLATE:
                dr, dc = int(pd.params["dr"]), int(pd.params["dc"])
                cells = {(r + dr, c + dc): col for (r, c), col in cells.items()}
            elif pd.delta_type is DeltaType.RECOLOR:
                color = int(pd.params["color"])
                cells = {cell: color for cell in cells}
        return cells
    if dtype in (DeltaType.REFLECT, DeltaType.ROTATE, DeltaType.SCALE):
        pattern, shape = _rel_pattern(in_obj)
        if dtype is DeltaType.REFLECT:
            pattern, shape = _transformed(pattern, shape, params["axis"])
        elif dtype is DeltaType.ROTATE:
            pattern, shape = _transformed(pattern, shape,
                                          f"rot{int(params['angle'])}")
        else:
            factor = int(params["factor"])
            if factor >= 2:
                pattern, shape = _upscaled(pattern, shape, factor)
            else:
                pattern, shape = _downscaled(pattern, shape, -factor)
        r0 = in_obj.bounding_box[0] + int(params.get("dr", 0))
        c0 = in_obj.bounding_box[1] + int(params.get("dc", 0))
        return {(r + r0, c + c0): col for (r, c), col in pattern.items()}
    return {}


def _infer_background(output_grid: Grid,
                      out_objects: list[ARCObject]) -> int:
    """Background color for the reconciliation canvas: the most frequent
    color among output cells NOT covered by any output object (deterministic
    tie-break by smaller color); falls back to output_grid.background_color
    when the objects tile the whole grid."""
    data = output_grid.to_numpy()
    covered: set[tuple[int, int]] = set()
    for obj in out_objects:
        covered |= obj.cells
    counts: Counter = Counter()
    height, width = data.shape
    for r in range(height):
        for c in range(width):
            if (r, c) not in covered:
                counts[int(data[r, c])] += 1
    if counts:
        return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]
    return int(output_grid.background_color)
