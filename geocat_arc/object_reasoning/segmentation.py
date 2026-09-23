"""Segmentation variants S1-S6 and per-task variant choice (Section 2.1).

All variants are built on geocat_arc.perception.segmentation.
extract_connected_components / objects.extract_objects — do NOT reimplement
flood fill.  S3/S4 return types.MultiColorObject (ARCObject + cell_colors).

The variant is chosen PER TASK by coherence over train pairs (Requirement
2.1.1) — never by task ID.  The chosen variant is bound into the program as
the Segment step's argument.

Implementation notes (segmentation team):
- perception's ``extract_connected_components(..., ignore_background=True)``
  hardcodes background = most-frequent color, so every variant here calls it
  with ``ignore_background=False`` and filters components by the variant's
  OWN background color.  This reuses the flood fill while keeping background
  semantics exact (S1-S4/S6 default to 0, S5 adapts).
- S3/S4 reuse the same flood fill on a binarized view of the grid (cell !=
  background -> 1) so "connected regardless of color" needs no new geometry
  code; per-cell colors are read back from the original grid.
- Object ids are reassigned densely (0..n-1) per grid in deterministic
  (row-major component / ascending color) order — feature tables key rows by
  (pair_index, object_id).
"""
from __future__ import annotations

from collections import Counter
from typing import Callable, Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject
from geocat_arc.perception.matching import match_objects
from geocat_arc.perception.segmentation import extract_connected_components

from .types import (
    GridPair,
    MultiColorObject,
    SegmentationResult,
    SegmentationVariant,
    SEGMENTATION_TRIAL_ORDER,
    cell_colors_of,
)

#: Coherence eligibility threshold: fraction of non-background pixels that
#: must be covered by matched or action-explained objects (Req 2.1.1).
COHERENCE_PIXEL_THRESHOLD: float = 0.80


# ---------------------------------------------------------------------------
# Shared helpers (private)
# ---------------------------------------------------------------------------

def _same_color_components(grid: Grid, connectivity: int,
                           bg: int) -> list[ARCObject]:
    """Same-color components under an EXPLICIT background color.

    Reuses perception's flood fill with ignore_background=False (which
    segments every color, including bg regions) and drops the bg-colored
    components — identical to flood-filling while ignoring ``bg``.
    """
    masks = extract_connected_components(grid, connectivity=connectivity,
                                         ignore_background=False)
    objects: list[ARCObject] = []
    for m in masks:
        if m.color == bg:
            continue
        objects.append(ARCObject(id=len(objects), cells=m.cells,
                                 color=m.color, bounding_box=m.bounding_box))
    return objects


def _multicolor_components(grid: Grid, connectivity: int,
                           bg: int) -> list[ARCObject]:
    """Multicolor components: any non-bg cells connected regardless of color.

    Reuses the same flood fill on a binarized view (non-bg -> 1), then reads
    per-cell colors back from the original grid.  Returns MultiColorObject
    with .color = majority color (ties -> smaller color, deterministic).
    """
    data = grid.to_numpy()
    binary = Grid((data != bg).astype(np.int32))
    masks = extract_connected_components(binary, connectivity=connectivity,
                                         ignore_background=False)
    objects: list[ARCObject] = []
    for m in masks:
        if m.color != 1:          # the bg-valued (0) components
            continue
        cell_colors = {(r, c): int(data[r, c]) for (r, c) in m.cells}
        counts = Counter(cell_colors.values())
        majority = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        objects.append(MultiColorObject(id=len(objects), cells=m.cells,
                                        color=majority,
                                        bounding_box=m.bounding_box,
                                        cell_colors=cell_colors))
    return objects


def _proximity_multicolor_components(grid: Grid, bg: int) -> list[ARCObject]:
    """Proximity multicolor grouping (S7): non-background cells belong to one
    object when they are within Chebyshev distance <= 2 of each other
    (transitively) — i.e. 8-connectivity with 1-cell gaps allowed.  The
    granularity between S1-fragmentation and S3/S4 total-merge that scattered
    multicolor scenes (legend + dotted groups) need.

    Reuses the perception flood fill on a 1-cell-dilated binarized view (the
    dilation makes gap-1 cells 8-adjacent); per-cell colors and membership
    are read back from the ORIGINAL grid so no dilated cell leaks into an
    object.
    """
    data = grid.to_numpy()
    fg = data != bg
    if not fg.any():
        return []
    # 8-neighborhood dilation by 1 (pure numpy shifts; no new geometry code).
    h, w = fg.shape
    dilated = np.zeros_like(fg)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            r0s, r1s = max(0, dr), min(h, h + dr)
            r0d, r1d = max(0, -dr), min(h, h - dr)
            c0s, c1s = max(0, dc), min(w, w + dc)
            c0d, c1d = max(0, -dc), min(w, w - dc)
            dilated[r0d:r1d, c0d:c1d] |= fg[r0s:r1s, c0s:c1s]
    binary = Grid(dilated.astype(np.int32))
    masks = extract_connected_components(binary, connectivity=8,
                                         ignore_background=False)
    objects: list[ARCObject] = []
    for m in masks:
        if m.color != 1:            # the 0-valued (non-dilated) components
            continue
        cells = frozenset((r, c) for (r, c) in m.cells if fg[r, c])
        if not cells:
            continue
        cell_colors = {(r, c): int(data[r, c]) for (r, c) in cells}
        counts = Counter(cell_colors.values())
        majority = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        rows = [r for r, _ in cells]
        cols = [c for _, c in cells]
        bbox = (min(rows), min(cols), max(rows) + 1, max(cols) + 1)
        objects.append(MultiColorObject(id=len(objects), cells=cells,
                                        color=majority, bounding_box=bbox,
                                        cell_colors=cell_colors))
    return objects


def _canonical_signature(obj: ARCObject) -> tuple:
    """Rotation/reflection-canonical shape signature (min over 8 orientations).

    Used only for the coverage cross-check ("plausibly action-explained"):
    an unmatched output object whose canonical shape exists among the input
    objects is a copy/reflect/rotate candidate, not a genuinely new shape.
    """
    m = obj.mask.astype(int)
    variants = []
    for k in range(4):
        rot = np.rot90(m, k)
        variants.append(tuple(map(tuple, rot.tolist())))
        variants.append(tuple(map(tuple, np.fliplr(rot).tolist())))
    return min(variants)


# ---------------------------------------------------------------------------
# Per-grid segmentation primitives (one function per variant)
# ---------------------------------------------------------------------------

def segment_s1(grid: Grid, background: Optional[int] = None) -> list[ARCObject]:
    """S1: same-color 4-connected components (existing default).

    background: color treated as empty; None => 0 (the historical default).
    """
    bg = 0 if background is None else background
    return _same_color_components(grid, connectivity=4, bg=bg)


def segment_s2(grid: Grid, background: Optional[int] = None) -> list[ARCObject]:
    """S2: same-color 8-connected components (connectivity=8)."""
    bg = 0 if background is None else background
    return _same_color_components(grid, connectivity=8, bg=bg)


def segment_s3(grid: Grid, background: Optional[int] = None) -> list[ARCObject]:
    """S3: multicolor 4-connected — any non-background cells connected
    regardless of color form one object; returns MultiColorObject with
    cell_colors populated and .color = majority color."""
    bg = 0 if background is None else background
    return _multicolor_components(grid, connectivity=4, bg=bg)


def segment_s4(grid: Grid, background: Optional[int] = None) -> list[ARCObject]:
    """S4: multicolor 8-connected (as S3 with connectivity=8)."""
    bg = 0 if background is None else background
    return _multicolor_components(grid, connectivity=8, bg=bg)


def segment_s5(grid: Grid, background: Optional[int] = None) -> list[ARCObject]:
    """S5: background-adaptive — background := grid.background_color (most
    frequent color, NOT assumed 0), then same-color 4-connected components.
    The ``background`` argument, if given, overrides the adaptive choice."""
    bg = grid.background_color if background is None else background
    return _same_color_components(grid, connectivity=4, bg=bg)


def segment_s6(grid: Grid, background: Optional[int] = None) -> list[ARCObject]:
    """S6: color-layer view — one object per color: all cells of that color
    (possibly disconnected), for scattered same-color patterns."""
    bg = 0 if background is None else background
    data = grid.to_numpy()
    objects: list[ARCObject] = []
    for color in sorted(grid.colors_used):
        if color == bg:
            continue
        rows, cols = np.nonzero(data == color)
        cells = frozenset((int(r), int(c)) for r, c in zip(rows, cols))
        bbox = (int(rows.min()), int(cols.min()),
                int(rows.max()) + 1, int(cols.max()) + 1)
        objects.append(ARCObject(id=len(objects), cells=cells,
                                 color=int(color), bounding_box=bbox))
    return objects


def segment_s7(grid: Grid, background: Optional[int] = None) -> list[ARCObject]:
    """S7: proximity multicolor grouping — non-background cells within
    Chebyshev distance <= 2 (transitively) form one object; returns
    MultiColorObject like S3/S4 (the granularity for scattered multicolor
    groups that S1 fragments and S3/S4 over-merge)."""
    bg = 0 if background is None else background
    return _proximity_multicolor_components(grid, bg)


#: Dispatch table; the ONLY way callers map variant -> function.
SEGMENTERS: dict[SegmentationVariant, Callable[..., list[ARCObject]]] = {
    SegmentationVariant.S1_SAME_COLOR_4: segment_s1,
    SegmentationVariant.S2_SAME_COLOR_8: segment_s2,
    SegmentationVariant.S3_MULTICOLOR_4: segment_s3,
    SegmentationVariant.S4_MULTICOLOR_8: segment_s4,
    SegmentationVariant.S5_BG_ADAPTIVE: segment_s5,
    SegmentationVariant.S6_COLOR_LAYERS: segment_s6,
    SegmentationVariant.S7_PROXIMITY_MULTICOLOR: segment_s7,
}


def segment(grid: Grid, variant: SegmentationVariant,
            background: Optional[int] = None) -> list[ARCObject]:
    """Uniform entry point: apply one variant to one grid (dispatch glue)."""
    return SEGMENTERS[variant](grid, background)


def background_for(grid: Grid, variant: SegmentationVariant) -> int:
    """The background color a variant assumes for this grid: 0 for S1-S4/S6,
    grid.background_color (most frequent) for S5."""
    if variant is SegmentationVariant.S5_BG_ADAPTIVE:
        return grid.background_color
    return 0


# ---------------------------------------------------------------------------
# Per-task variant evaluation and choice
# ---------------------------------------------------------------------------

def _count_relation_consistent(counts: list[tuple[int, int]]) -> bool:
    """Consistent object-count relation across pairs (Req 2.1.1).

    Accepted relations (each must hold with the SAME parameter on every
    pair): n_out == n_in + k (constant difference, covers keep/delete-k);
    n_out == k (constant output count, covers select/delete-all);
    n_out == f * n_in with integer f >= 1 (covers per-object copy).
    A pair with zero input objects is never consistent (nothing to reason
    about at object level).
    """
    if not counts:
        return False
    if any(n_in == 0 for n_in, _ in counts):
        return False
    if len(counts) == 1:
        return True
    diffs = {n_out - n_in for n_in, n_out in counts}
    if len(diffs) == 1:
        return True
    outs = {n_out for _, n_out in counts}
    if len(outs) == 1:
        return True
    ratios = set()
    for n_in, n_out in counts:
        if n_out % n_in != 0 or n_out < n_in:
            return False
        ratios.add(n_out // n_in)
    return len(ratios) == 1


def evaluate_variant(variant: SegmentationVariant,
                     train_pairs: list[GridPair]) -> SegmentationResult:
    """Segment every train input AND output with ``variant`` and score
    coherence per Requirement 2.1.1:

      - pixel_coverage: fraction of non-background pixels (over all pairs,
        inputs+outputs) covered by extracted objects that participate in a
        greedy perception.matching.match_objects correspondence or are
        plausibly action-explained (delete/copy candidates count as covered);
      - consistent object-count relation across pairs (e.g. n_out == n_in,
        n_out == n_in - k, n_out == k) — inconsistency zeroes coherence;
      - coherent = pixel_coverage >= COHERENCE_PIXEL_THRESHOLD and the
        count relation is consistent.

    Round 16 (ARC_CREATE_COHERENCE=1): when count-consistency fails but
    the failure is explained by ORPHAN OUTPUT OBJECTS (outputs with no
    input correspondence by shape/position/grow/connect), the variant is
    admitted with create_orphan_relaxed=True IF the "preserved core" (non-
    orphan outputs) satisfies count-consistency.  Guards:
      (a) preserved core must still cohere;
      (b) orphan-ness is per-pair (fold-invariant — subset-stable);
      (c) relaxed variants rank AFTER strict in the inducer trial order.

    Never raises on degenerate grids; returns coherent=False instead.
    """
    import os as _os
    _create_coherence = _os.environ.get(
        "ARC_CREATE_COHERENCE", "") not in ("", "0")

    try:
        input_objects: list[list[ARCObject]] = []
        output_objects: list[list[ARCObject]] = []
        backgrounds: list[int] = []
        object_counts: list[tuple[int, int]] = []
        covered_pixels = 0
        total_pixels = 0
        copy_like_growth = True  # every extra output is a copy of some input
        grow_explained = True    # every unmatched output CONTAINS an input
        mismatch = 0             # granularity: merges + splits (round 4)
        # Round 16: per-pair orphan output counts (fold-invariant: each
        # element depends only on one pair, never on fold membership).
        per_pair_orphan_counts: list[int] = []
        # Per-pair preserved-core counts: (n_in, n_explained_out) where
        # n_explained_out = matched + copy/grow/connect-explained outputs.
        core_counts: list[tuple[int, int]] = []

        for grid_in, grid_out in train_pairs:
            # One background per pair (the input grid's), so an object does
            # not change identity between input and output of the same pair.
            bg = background_for(grid_in, variant)
            in_objs = segment(grid_in, variant, bg)
            out_objs = segment(grid_out, variant, bg)
            input_objects.append(in_objs)
            output_objects.append(out_objs)
            backgrounds.append(bg)
            object_counts.append((len(in_objs), len(out_objs)))

            total_pixels += int(np.count_nonzero(grid_in.to_numpy() != bg))
            total_pixels += int(np.count_nonzero(grid_out.to_numpy() != bg))

            matches = match_objects(in_objs, out_objs)
            matched_in = {a.id for a, _, _ in matches}
            matched_out = {b.id for _, b, _ in matches}

            # Input side: matched objects are correspondence-covered;
            # unmatched input objects are delete candidates -> covered.
            covered_pixels += sum(o.size for o in in_objs)

            # Output side: matched -> covered; unmatched -> covered only if
            # a copy/reflect/rotate candidate (canonical shape exists among
            # the inputs).  Genuinely new shapes stay uncovered — the signal
            # that this segmentation does not explain the pair.
            covered_pixels += sum(o.size for o in out_objs
                                  if o.id in matched_out)
            unmatched_out = [o for o in out_objs if o.id not in matched_out]
            all_copy_like = True
            pair_orphan_count = 0
            n_explained = len(matched_out)
            if unmatched_out:
                input_shapes = {_canonical_signature(o) for o in in_objs}

                def _connect_candidate(o: ARCObject) -> bool:
                    # a straight 1-wide segment whose deterministic
                    # connect_segment between two MATCHED outputs
                    # reproduces it exactly (M2 verb 1) — the pre-CONNECT
                    # coverage rule penalized exactly the correct variant
                    # on bridge-drawing tasks (same bias GROW had).
                    from .growth import connect_segment
                    if o.bbox_height != 1 and o.bbox_width != 1:
                        return False
                    halo = {(r + dr, c + dc) for (r, c) in o.cells
                            for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
                    hosts = [m for m in out_objs
                             if m.id in matched_out and (halo & m.cells)]
                    if len(hosts) != 2:
                        return False
                    seg_cells = connect_segment(hosts[0].cells,
                                                hosts[1].cells,
                                                (grid_out.height,
                                                 grid_out.width))
                    return seg_cells is not None \
                        and set(seg_cells) == set(o.cells)

                def _grow_candidate(o: ARCObject) -> bool:
                    # An output object CONTAINING some input object's cells
                    # (same colors on the shared cells) is grow-explained
                    # (DeltaType.GROW, round 4) — the pre-GROW coverage rule
                    # penalized exactly the correct variant on growth tasks.
                    occ = cell_colors_of(o)
                    for a in in_objs:
                        acc = cell_colors_of(a)
                        if len(acc) < len(occ) and \
                                all(occ.get(cell) == col
                                    for cell, col in acc.items()):
                            return True
                    return False

                for o in unmatched_out:
                    if _canonical_signature(o) in input_shapes \
                            or _grow_candidate(o) or _connect_candidate(o):
                        covered_pixels += o.size
                        n_explained += 1
                    else:
                        all_copy_like = False
                        pair_orphan_count += 1
                all_copy_like_or_grow = all(
                    _canonical_signature(o) in input_shapes
                    or _grow_candidate(o) or _connect_candidate(o)
                    for o in unmatched_out)
                all_copy_like = all(_canonical_signature(o) in input_shapes
                                    for o in unmatched_out)
                if not all_copy_like_or_grow:
                    grow_explained = False
            if not (len(out_objs) >= len(in_objs) and all_copy_like):
                copy_like_growth = False
            per_pair_orphan_counts.append(pair_orphan_count)
            # Preserved core = MATCHED objects only.  Copy/grow "explained"
            # orphans must not inflate the core (a single-cell orphan whose
            # shape coincides with an input's signature would otherwise make
            # core counts inconsistent across pairs with different orphan
            # populations — the round-16 variable-orphan case).
            n_matched = len(out_objs) - len(unmatched_out)
            core_counts.append((len(in_objs), n_matched))
            # granularity mismatch by cell overlap (merges + splits)
            for o in out_objs:
                if sum(1 for a in in_objs if a.cells & o.cells) > 1:
                    mismatch += 1
            for a in in_objs:
                if sum(1 for o in out_objs if o.cells & a.cells) > 1:
                    mismatch += 1
            del matched_in  # coverage symmetry documented above

        pixel_coverage = (covered_pixels / total_pixels) if total_pixels else 0.0
        # Count-relation consistency (Req 2.1.1) OR generatively explained
        # growth: per-pair output counts may vary freely when every extra
        # output object is a copy of some input (COPY family) or CONTAINS an
        # input object (GROW family, round 4) — but the GROW relaxation only
        # applies at ZERO granularity mismatch, so a variant that merges or
        # splits objects can never buy eligibility through it.
        consistent = _count_relation_consistent(object_counts) \
            or (copy_like_growth and bool(object_counts)
                and all(n_in > 0 for n_in, _ in object_counts)) \
            or (grow_explained and mismatch == 0 and bool(object_counts)
                and all(n_in > 0 for n_in, _ in object_counts)
                and all((gi.height, gi.width) == (go.height, go.width)
                        for gi, go in train_pairs))

        # Round 16: create-aware coherence relaxation.
        # When ARC_CREATE_COHERENCE=1 and strict consistency fails,
        # check whether the "preserved core" (non-orphan outputs) alone
        # satisfies count-consistency.  If yes, the orphan outputs are
        # CREATE candidates — admit the variant with the relaxation flag.
        # Guard (a): preserved core must itself be count-consistent.
        # Guard (b): per_pair_orphan_counts is per-pair, fold-invariant.
        total_orphans = sum(per_pair_orphan_counts)
        create_relaxed = False
        needs_rescue = (not consistent
                        or pixel_coverage < COHERENCE_PIXEL_THRESHOLD)
        if needs_rescue and _create_coherence \
                and total_orphans > 0 and bool(object_counts) \
                and all(n_in > 0 for n_in, _ in object_counts):
            # The core counts: (n_in, n_matched) per pair.  Constant-diff
            # ONLY (uniform keep/delete): the broader relation set (e.g.
            # constant output count) would let an incoherent core slip
            # through when unrelated pairs happen to share a matched count.
            core_ok = len({m - n for n, m in core_counts}) == 1
            if core_ok:
                consistent = True
                create_relaxed = True
                # Under create relaxation, orphan output pixels are
                # CREATE candidates — count them as covered so they
                # don't suppress pixel_coverage below threshold.
                pixel_coverage = 1.0 if total_pixels else 0.0

        coherence = pixel_coverage if consistent else 0.0
        coherent = consistent and pixel_coverage >= COHERENCE_PIXEL_THRESHOLD
        return SegmentationResult(
            variant=variant, input_objects=input_objects,
            output_objects=output_objects, backgrounds=backgrounds,
            coherence=coherence, pixel_coverage=pixel_coverage,
            object_counts=object_counts, coherent=coherent,
            granularity_mismatch=mismatch,
            create_orphan_relaxed=create_relaxed,
            create_orphan_count=total_orphans)
    except Exception:
        return SegmentationResult(
            variant=variant, input_objects=[], output_objects=[],
            backgrounds=[], coherence=0.0, pixel_coverage=0.0,
            object_counts=[], coherent=False)


def _total_objects(result: SegmentationResult) -> int:
    return (sum(len(objs) for objs in result.input_objects)
            + sum(len(objs) for objs in result.output_objects))


def choose_segmentation(train_pairs: list[GridPair]) -> SegmentationResult:
    """Learned per-task segmentation choice (Requirement 2.1.1).

    Tries variants in SEGMENTATION_TRIAL_ORDER (S1,S2,S3,S5,S4,S6) via
    evaluate_variant and returns the FIRST coherent result (lazy: later
    variants are not evaluated once one passes — cheapest-first, Sec 3.5).
    If no variant is coherent, returns the best fallback ranked by
    (coherence, pixel_coverage), ties broken by fewer total objects
    (parsimony / MDL), then by trial order; the inducer will record
    failure_stage=SEGMENTATION.

    Deterministic in the train pairs only — no task IDs anywhere.
    """
    best: Optional[SegmentationResult] = None
    best_key: Optional[tuple] = None
    for variant in SEGMENTATION_TRIAL_ORDER:
        result = evaluate_variant(variant, train_pairs)
        if result.coherent:
            return result
        # Fallback ranking: higher coherence, then higher coverage, then
        # FEWER objects (note the negation), earlier trial order wins ties.
        key = (result.coherence, result.pixel_coverage,
               -_total_objects(result))
        if best_key is None or key > best_key:
            best, best_key = result, key
    assert best is not None  # SEGMENTATION_TRIAL_ORDER is non-empty
    return best
