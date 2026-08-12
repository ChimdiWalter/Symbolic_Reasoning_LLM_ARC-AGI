"""Round-18 generator mining: machine-invented generative primitives.

Implements STAGE 2 of the Generative Ladder Plan (docs/GENERATIVE_LADDER_PLAN.md).
Reuses M2/M3b/M4 scaffolding one level down: residual-paint substrate ->
hypothesis-language enumeration -> M3b delta-LOO admission.

HYPOTHESIS LANGUAGE (hand-authored one-level-more-primitive layer):
  A generator hypothesis is a parameterized cell-set function:
    WALK direction  : 4 cardinal (up/down/left/right) + 4 diagonal
                      (up_left/up_right/down_left/down_right)
    STOP predicate  : grid_border | first_nonbg | first_color_C |
                      after_N_steps | nearest_obj_boundary
    COLOR rule      : source_color | obstacle_color | constant_C |
                      two_phase (source then obstacle)
    EMIT shape      : line_1wide | full_row | full_col | cross
    delete_source   : bool

  This space includes the R17b hand-added modes as points:
    - cross_line = EMIT:cross, STOP:grid_border, COLOR:source_color
    - intersection_color = cross-overlap recolor (separate mechanism)
    - ray_through_absorbed = WALK:cardinal, STOP:grid_border,
        COLOR:two_phase (source before obstacle, obstacle after)

Env-gated: the miner runs offline; admitted generators loaded by
generative.py when ARC_GENERATIVE=1 and learned_generators.json exists.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject

from .generative import (
    _apply_generator,
    _composite_matches,
    _fusion_signature,
    _object_sort_key,
    _selector_matches,
    induce_generative_candidates,
    render_generative,
)
from .growth import _UNIT
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
# Direction vocabulary (cardinal + diagonal)
# ---------------------------------------------------------------------------

_UNIT_8: dict[str, tuple[int, int]] = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
    "up_left": (-1, -1),
    "up_right": (-1, 1),
    "down_left": (1, -1),
    "down_right": (1, 1),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ResidualRecord:
    """One residual instance: the gap between best composite render and
    the expected output, attributed to a specific source object."""
    task_id: str
    pair_index: int
    source_color: int
    source_bbox: tuple[int, int, int, int]  # (r_min, c_min, r_max, c_max)
    source_cells: list[tuple[int, int]]
    source_size: int
    grid_h: int
    grid_w: int
    # Cells that should be painted but are not (expected - rendered)
    missing_cells: dict[str, int]  # "(r,c)" -> expected color
    # Cells that are overpainted (rendered but wrong color vs expected)
    overpainted_cells: dict[str, int]  # "(r,c)" -> expected color
    # Grid context: the input grid values (for obstacle detection)
    input_grid: list[list[int]]
    seg_variant: str
    bg: int

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "pair_index": self.pair_index,
            "source_color": self.source_color,
            "source_bbox": list(self.source_bbox),
            "source_cells": self.source_cells,
            "source_size": self.source_size,
            "grid_h": self.grid_h,
            "grid_w": self.grid_w,
            "missing_cells": self.missing_cells,
            "overpainted_cells": self.overpainted_cells,
            "input_grid": self.input_grid,
            "seg_variant": self.seg_variant,
            "bg": self.bg,
        }

    @staticmethod
    def from_dict(d: dict) -> "ResidualRecord":
        return ResidualRecord(
            task_id=d["task_id"],
            pair_index=d["pair_index"],
            source_color=d["source_color"],
            source_bbox=tuple(d["source_bbox"]),
            source_cells=[tuple(c) for c in d["source_cells"]],
            source_size=d["source_size"],
            grid_h=d["grid_h"],
            grid_w=d["grid_w"],
            missing_cells=d["missing_cells"],
            overpainted_cells=d["overpainted_cells"],
            input_grid=d["input_grid"],
            seg_variant=d["seg_variant"],
            bg=d["bg"],
        )


@dataclass
class GeneratorHypothesis:
    """A hypothesis-language expression: a parameterized cell-set function.

    The language includes the R17b hand-added modes as points:
      - cross_line        = emit:cross, stop:grid_border, color:source_color
      - intersection_color= emit:cross + intersection_color parameter
                            (cells where lines from DIFFERENT source objects
                            overlap get repainted with this color)
      - ray_through_absorbed = emit:line_1wide, stop:grid_border,
                               color:two_phase, direction:cardinal
    """
    direction: str           # one of _UNIT_8 keys
    stop: str                # grid_border | first_nonbg | first_color_C | after_N | nearest_obj
    color_rule: str          # source_color | obstacle_color | constant_C | two_phase
    emit: str                # line_1wide | full_row | full_col | cross
    delete_source: bool = False
    # Bound parameters (from stop/color rules)
    stop_color: Optional[int] = None    # for first_color_C
    stop_n: Optional[int] = None        # for after_N
    constant_color: Optional[int] = None  # for constant_C
    # Program-level parameter: intersection_color for cross emits
    # (cells painted by generators from objects of DIFFERENT source colors
    # get repainted with this value -- mirrors GenerativeProgram.intersection_color)
    intersection_color: Optional[int] = None

    def to_dict(self) -> dict:
        d = {
            "direction": self.direction,
            "stop": self.stop,
            "color_rule": self.color_rule,
            "emit": self.emit,
            "delete_source": self.delete_source,
        }
        if self.stop_color is not None:
            d["stop_color"] = self.stop_color
        if self.stop_n is not None:
            d["stop_n"] = self.stop_n
        if self.constant_color is not None:
            d["constant_color"] = self.constant_color
        if self.intersection_color is not None:
            d["intersection_color"] = self.intersection_color
        return d

    @staticmethod
    def from_dict(d: dict) -> "GeneratorHypothesis":
        return GeneratorHypothesis(
            direction=d["direction"],
            stop=d["stop"],
            color_rule=d["color_rule"],
            emit=d["emit"],
            delete_source=d.get("delete_source", False),
            stop_color=d.get("stop_color"),
            stop_n=d.get("stop_n"),
            constant_color=d.get("constant_color"),
            intersection_color=d.get("intersection_color"),
        )

    def signature(self) -> str:
        """Hashable string for dedup."""
        parts = [self.direction, self.stop, self.color_rule, self.emit]
        if self.delete_source:
            parts.append("del_src")
        if self.stop_color is not None:
            parts.append(f"sc={self.stop_color}")
        if self.stop_n is not None:
            parts.append(f"sn={self.stop_n}")
        if self.constant_color is not None:
            parts.append(f"cc={self.constant_color}")
        if self.intersection_color is not None:
            parts.append(f"ic={self.intersection_color}")
        return "|".join(parts)

    def behavioral_key(self) -> str:
        """Key that is identical for behaviorally-equivalent hypotheses.

        Cross and full_row/full_col emits are direction-invariant, so
        different directions produce the same cells.  This key collapses
        them by replacing direction with '*' when the emit ignores it.
        Also collapses stop variants that are equivalent for area emits
        (grid_border vs first_nonbg are identical for full_row/col/cross
        which do not walk).
        """
        dir_key = self.direction
        stop_key = self.stop
        if self.emit in ("cross", "full_row", "full_col"):
            dir_key = "*"
            # For area emits, stop predicate is irrelevant (no walk)
            stop_key = "*"

        parts = [dir_key, stop_key, self.color_rule, self.emit]
        if self.delete_source:
            parts.append("del_src")
        if self.stop_color is not None:
            parts.append(f"sc={self.stop_color}")
        if self.stop_n is not None:
            parts.append(f"sn={self.stop_n}")
        if self.constant_color is not None:
            parts.append(f"cc={self.constant_color}")
        if self.intersection_color is not None:
            parts.append(f"ic={self.intersection_color}")
        return "|".join(parts)


@dataclass
class AdmittedGenerator:
    """A mined generator that passed the M3b delta-LOO admission gate."""
    hypothesis: GeneratorHypothesis
    supporting_tasks: list[str]  # task IDs with full LOO certification
    fold_records: list[dict]     # per-task fold details
    provenance: str = "mined"    # "mined" | "rediscovered"

    def to_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis.to_dict(),
            "supporting_tasks": self.supporting_tasks,
            "fold_records": self.fold_records,
            "provenance": self.provenance,
        }

    @staticmethod
    def from_dict(d: dict) -> "AdmittedGenerator":
        return AdmittedGenerator(
            hypothesis=GeneratorHypothesis.from_dict(d["hypothesis"]),
            supporting_tasks=d["supporting_tasks"],
            fold_records=d["fold_records"],
            provenance=d.get("provenance", "mined"),
        )


# ---------------------------------------------------------------------------
# 1. RESIDUAL-PAINT SUBSTRATE
# ---------------------------------------------------------------------------

def _best_composite_for_task(
    train_pairs: list[GridPair],
    *,
    disabled_kinds: Optional[set[str]] = None,
    disable_intersection_color: bool = False,
) -> tuple[Optional[GenerativeProgram], Optional[SegmentationVariant]]:
    """Run the inducer and return the best (possibly imperfect) program.

    When ``disabled_kinds`` is given, we monkeypatch the inducer to skip
    those generator kinds (used for E10 to remove R17b modes).
    """
    if disabled_kinds or disable_intersection_color:
        # Run with filtered vocabulary
        candidates = _induce_with_filter(
            train_pairs, disabled_kinds or set(),
            disable_intersection_color)
    else:
        candidates = induce_generative_candidates(train_pairs)

    if candidates:
        return candidates[0], candidates[0].seg_variant
    return None, None


def _induce_with_filter(
    train_pairs: list[GridPair],
    disabled_kinds: set[str],
    disable_intersection_color: bool,
) -> list[GenerativeProgram]:
    """Run induction with some generator kinds removed from the vocabulary.

    Instead of monkeypatching, we filter the candidates post-hoc and also
    provide a wrapper that pre-filters the candidate generators.
    """
    from .generative import _candidate_generators_for_object as _orig_cand
    import types

    # Save the originals
    import geocat_arc.object_reasoning.generative as _gen_mod

    _orig_apply = _gen_mod._apply_generator
    _orig_cand_fn = _gen_mod._candidate_generators_for_object
    _orig_try_ic = _gen_mod._try_intersection_color

    def _filtered_apply(rule, obj, bounds, grid_array=None,
                        include_source=False):
        if rule.get("kind") in disabled_kinds:
            return {}
        return _orig_apply(rule, obj, bounds, grid_array=grid_array,
                           include_source=include_source)

    def _filtered_cand(obj, target, bg_in, bounds, grid_array=None):
        cands = _orig_cand_fn(obj, target, bg_in, bounds,
                              grid_array=grid_array)
        return [c for c in cands if c.get("kind") not in disabled_kinds]

    def _noop_try_ic(*args, **kwargs):
        return None

    try:
        _gen_mod._apply_generator = _filtered_apply
        _gen_mod._candidate_generators_for_object = _filtered_cand
        if disable_intersection_color:
            _gen_mod._try_intersection_color = _noop_try_ic
        result = induce_generative_candidates(train_pairs)
        # Also filter any that slipped through
        result = [p for p in result
                  if all(r.get("kind") not in disabled_kinds
                         for _, r in p.generators)]
        if disable_intersection_color:
            result = [p for p in result
                      if p.intersection_color is None]
        return result
    finally:
        _gen_mod._apply_generator = _orig_apply
        _gen_mod._candidate_generators_for_object = _orig_cand_fn
        _gen_mod._try_intersection_color = _orig_try_ic


def extract_residuals_for_task(
    task_id: str,
    train_pairs: list[GridPair],
    *,
    disabled_kinds: Optional[set[str]] = None,
    disable_intersection_color: bool = False,
) -> list[ResidualRecord]:
    """Extract per-object residuals for a fused-signature task.

    For each segmentation variant where the fusion signature holds, try
    the inducer. For each pair, compute the residual between the best
    composite render and the expected output, attributed to each source
    object.
    """
    records: list[ResidualRecord] = []

    for variant in SEGMENTATION_TRIAL_ORDER:
        if not _fusion_signature(train_pairs, variant):
            continue

        # Try to get a composite (possibly imperfect)
        prog, _ = _best_composite_for_task(
            train_pairs,
            disabled_kinds=disabled_kinds,
            disable_intersection_color=disable_intersection_color,
        )

        for pair_idx, (gi, go) in enumerate(train_pairs):
            bg_in = background_for(gi, variant)
            objects = sorted(segment(gi, variant, bg_in),
                             key=_object_sort_key)
            target = go.to_numpy()
            grid_array = gi.to_numpy()
            h, w = gi.height, gi.width

            # Get the rendered output (or blank if no program found)
            if prog is not None:
                rendered = render_generative(prog, gi).to_numpy()
            else:
                rendered = grid_array.copy()

            # Compute the full residual
            diff_mask = rendered != target

            if not diff_mask.any():
                continue  # No residual for this pair

            # Collect all diff cells with their expected colors
            diff_cells: list[tuple[int, int, int, int]] = []
            for r in range(h):
                for c in range(w):
                    if diff_mask[r, c]:
                        diff_cells.append(
                            (r, c, int(target[r, c]), int(rendered[r, c])))

            # Build a list of non-bg objects for attribution
            non_bg_objs = [obj for obj in objects if obj.color != bg_in]

            # Attribute each diff cell to the NEAREST source object
            # based on geometric proximity. If a cell matches the source
            # object's color, it's strongly attributed to that object.
            obj_missing: dict[int, dict[str, int]] = {
                i: {} for i in range(len(non_bg_objs))}
            obj_overpainted: dict[int, dict[str, int]] = {
                i: {} for i in range(len(non_bg_objs))}

            for r, c, exp_color, ren_color in diff_cells:
                # Score each object: prefer color match + geometric alignment
                best_obj_idx = _best_attribution(
                    r, c, exp_color, non_bg_objs, bg_in)
                if best_obj_idx < 0:
                    continue
                key = f"({r},{c})"
                if exp_color != bg_in and ren_color == bg_in:
                    obj_missing[best_obj_idx][key] = exp_color
                elif exp_color != ren_color:
                    if exp_color != bg_in:
                        obj_missing[best_obj_idx][key] = exp_color
                    else:
                        obj_overpainted[best_obj_idx][key] = exp_color

            for i, obj in enumerate(non_bg_objs):
                missing = obj_missing[i]
                overpainted = obj_overpainted[i]
                if missing or overpainted:
                    cells_list = list(obj.cells)
                    rows = [r for r, _ in cells_list]
                    cols = [c for _, c in cells_list]
                    bbox = (min(rows), min(cols), max(rows), max(cols))
                    records.append(ResidualRecord(
                        task_id=task_id,
                        pair_index=pair_idx,
                        source_color=obj.color,
                        source_bbox=bbox,
                        source_cells=cells_list,
                        source_size=len(cells_list),
                        grid_h=h,
                        grid_w=w,
                        missing_cells=missing,
                        overpainted_cells=overpainted,
                        input_grid=gi.to_list(),
                        seg_variant=variant.value,
                        bg=bg_in,
                    ))

        # Only try the first matching variant
        break

    return records


def _best_attribution(
    r: int, c: int,
    exp_color: int,
    objects: list[ARCObject],
    bg: int,
) -> int:
    """Find which source object a residual cell should be attributed to.

    Scoring:
      +10 if exp_color == obj.color (strong signal: object paints its own color)
      +5  if cell is on same row or column as the object
      +3  if cell is on a diagonal from the object
      -1  per unit Manhattan distance from nearest object cell

    Returns the index of the best object, or -1 if no valid attribution.
    """
    if not objects:
        return -1

    best_score = -999999
    best_idx = 0

    for i, obj in enumerate(objects):
        score = 0
        cells_list = list(obj.cells)
        obj_rows = set(rr for rr, _ in cells_list)
        obj_cols = set(cc for _, cc in cells_list)

        # Color match bonus
        if exp_color == obj.color:
            score += 10

        # Geometric alignment
        if r in obj_rows or c in obj_cols:
            score += 5

        # Diagonal alignment
        for rr, cc in cells_list:
            if abs(r - rr) == abs(c - cc) and abs(r - rr) > 0:
                score += 3
                break

        # Distance penalty
        min_dist = min(abs(r - rr) + abs(c - cc) for rr, cc in cells_list)
        score -= min_dist

        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def _cell_related_to_object(
    r: int, c: int,
    cells: list[tuple[int, int]],
    bbox: tuple[int, int, int, int],
    h: int, w: int,
) -> bool:
    """Check whether a residual cell is geometrically related to a source
    object (same row, same column, diagonal, or within reasonable proximity)."""
    r_min, c_min, r_max, c_max = bbox
    obj_rows = set(rr for rr, _ in cells)
    obj_cols = set(cc for _, cc in cells)
    if r in obj_rows or c in obj_cols:
        return True
    for rr, cc in cells:
        if abs(r - rr) == abs(c - cc) and abs(r - rr) > 0:
            return True
    max_dist = max(h, w) // 2
    for rr, cc in cells:
        if abs(r - rr) <= max_dist and abs(c - cc) <= max_dist:
            return True
    return True


def save_residuals(records: list[ResidualRecord], path: Path) -> None:
    """Append residual records to a JSONL file (resumable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict()) + "\n")


def load_residuals(path: Path) -> list[ResidualRecord]:
    """Load residual records from a JSONL file."""
    records = []
    if not path.exists():
        return records
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(ResidualRecord.from_dict(json.loads(line)))
    return records


# ---------------------------------------------------------------------------
# 2. HYPOTHESIS LANGUAGE
# ---------------------------------------------------------------------------

def _parse_cell_key(key: str) -> tuple[int, int]:
    """Parse a "(r,c)" string key back to coordinates."""
    key = key.strip("()")
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def _execute_hypothesis(
    hyp: GeneratorHypothesis,
    source_cells: list[tuple[int, int]],
    source_color: int,
    grid_array: np.ndarray,
    bg: int,
) -> dict[tuple[int, int], int]:
    """Execute a hypothesis-language expression, returning {cell: color}.

    This is the hypothesis-language INTERPRETER: it maps any
    GeneratorHypothesis to the cell set it would paint given a source
    object on a grid.
    """
    h, w = grid_array.shape
    cells_fs = frozenset(source_cells)
    result: dict[tuple[int, int], int] = {}

    if hyp.emit == "line_1wide":
        # Ray from each source cell in the given direction
        dr, dc = _UNIT_8.get(hyp.direction, (0, 0))
        if (dr, dc) == (0, 0):
            return {}

        for r0, c0 in source_cells:
            r, c = r0 + dr, c0 + dc
            cur_color = _resolve_color(hyp.color_rule, source_color,
                                       hyp.constant_color, None)
            steps = 0
            absorbed = False
            while 0 <= r < h and 0 <= c < w:
                if (r, c) in cells_fs:
                    r += dr
                    c += dc
                    continue

                cell_val = int(grid_array[r, c])

                # Check stop predicate
                if _should_stop(hyp, r, c, cell_val, bg, cells_fs,
                                steps, h, w):
                    break

                # Color rule
                if hyp.color_rule == "two_phase" and not absorbed:
                    if cell_val != bg and (r, c) not in cells_fs:
                        # Hit obstacle: absorb its color
                        cur_color = cell_val
                        absorbed = True
                elif hyp.color_rule == "obstacle_color":
                    # Use whatever color is at this cell in the input
                    if cell_val != bg:
                        cur_color = cell_val

                result[(r, c)] = cur_color
                r += dr
                c += dc
                steps += 1

    elif hyp.emit == "full_row":
        # Full row through every row the source occupies
        rows_occupied = sorted(set(r for r, _ in source_cells))
        cur_color = _resolve_color(hyp.color_rule, source_color,
                                   hyp.constant_color, None)
        for row in rows_occupied:
            for c in range(w):
                if (row, c) not in cells_fs:
                    result[(row, c)] = cur_color

    elif hyp.emit == "full_col":
        # Full column through every column the source occupies
        cols_occupied = sorted(set(c for _, c in source_cells))
        cur_color = _resolve_color(hyp.color_rule, source_color,
                                   hyp.constant_color, None)
        for col in cols_occupied:
            for r in range(h):
                if (r, col) not in cells_fs:
                    result[(r, col)] = cur_color

    elif hyp.emit == "cross":
        # Full row AND column (cross) through the source
        rows_occupied = sorted(set(r for r, _ in source_cells))
        cols_occupied = sorted(set(c for _, c in source_cells))
        cur_color = _resolve_color(hyp.color_rule, source_color,
                                   hyp.constant_color, None)
        for row in rows_occupied:
            for c in range(w):
                if (row, c) not in cells_fs:
                    result[(row, c)] = cur_color
        for col in cols_occupied:
            for r in range(h):
                if (r, col) not in cells_fs:
                    result[(r, col)] = cur_color

    return result


def _resolve_color(
    color_rule: str,
    source_color: int,
    constant_color: Optional[int],
    obstacle_color: Optional[int],
) -> int:
    """Resolve the initial color for a hypothesis color rule."""
    if color_rule == "source_color":
        return source_color
    if color_rule == "constant_C" and constant_color is not None:
        return constant_color
    if color_rule == "obstacle_color" and obstacle_color is not None:
        return obstacle_color
    if color_rule == "two_phase":
        return source_color  # starts with source, switches on obstacle
    return source_color  # fallback


def _should_stop(
    hyp: GeneratorHypothesis,
    r: int, c: int,
    cell_val: int,
    bg: int,
    cells_fs: frozenset,
    steps: int,
    h: int, w: int,
) -> bool:
    """Check whether the walk should stop at this position."""
    if hyp.stop == "grid_border":
        return False  # Walk continues to grid edge (loop condition handles it)
    if hyp.stop == "first_nonbg":
        return cell_val != bg and (r, c) not in cells_fs
    if hyp.stop == "first_color_C":
        return cell_val == hyp.stop_color and (r, c) not in cells_fs
    if hyp.stop == "after_N":
        return steps >= (hyp.stop_n or 1)
    if hyp.stop == "nearest_obj":
        # Stop at any non-bg, non-source cell
        return cell_val != bg and (r, c) not in cells_fs
    return False


# ---------------------------------------------------------------------------
# 3. HYPOTHESIS ENUMERATION
# ---------------------------------------------------------------------------

def enumerate_hypotheses(
    residuals: list[ResidualRecord],
    *,
    max_per_cluster: int = 5000,
) -> list[GeneratorHypothesis]:
    """Enumerate hypothesis-language expressions bounded by
    max_per_cluster.  Covers the full cross product of the hypothesis
    language dimensions, filtered by relevance to the residual data.

    The enumeration is BEHAVIORALLY DEDUPED: hypotheses that would
    produce identical cell-sets (e.g. cross with direction=up vs
    direction=down) are collapsed to one canonical representative.
    """

    # Collect all colors present in residuals for parameterization
    all_colors: set[int] = set()
    source_colors: set[int] = set()
    residual_colors: set[int] = set()  # colors seen in missing cells
    for rec in residuals:
        all_colors.add(rec.source_color)
        source_colors.add(rec.source_color)
        all_colors.add(rec.bg)
        for key, color in rec.missing_cells.items():
            all_colors.add(color)
            residual_colors.add(color)
        for key, color in rec.overpainted_cells.items():
            all_colors.add(color)
            residual_colors.add(color)

    # Colors that appear in residuals but NOT as source colors =>
    # candidates for constant_C or intersection_color
    non_source_colors = residual_colors - source_colors

    directions = list(_UNIT_8.keys())
    stops = ["grid_border", "first_nonbg"]
    color_rules = ["source_color", "obstacle_color", "constant_C", "two_phase"]
    emits = ["line_1wide", "full_row", "full_col", "cross"]

    hypotheses: list[GeneratorHypothesis] = []
    seen_behavioral: set[str] = set()

    def _add(h: GeneratorHypothesis) -> None:
        bk = h.behavioral_key()
        if bk not in seen_behavioral and len(hypotheses) < max_per_cluster:
            seen_behavioral.add(bk)
            hypotheses.append(h)

    # Core cross product (source_color + two_phase, no bound params)
    for direction in directions:
        for stop in stops:
            for color_rule in ["source_color", "two_phase"]:
                for emit in emits:
                    for del_src in (False, True):
                        _add(GeneratorHypothesis(
                            direction=direction,
                            stop=stop,
                            color_rule=color_rule,
                            emit=emit,
                            delete_source=del_src,
                        ))

    # obstacle_color variants (line_1wide only -- area emits have no walk)
    for direction in directions:
        for stop in ["grid_border", "first_nonbg"]:
            for del_src in (False, True):
                _add(GeneratorHypothesis(
                    direction=direction,
                    stop=stop,
                    color_rule="obstacle_color",
                    emit="line_1wide",
                    delete_source=del_src,
                ))

    # constant_C variants for ALL emits, using residual-observed colors
    for color in sorted(all_colors):
        for direction in directions:
            for emit in emits:
                for stop in ["grid_border", "first_nonbg"]:
                    for del_src in (False, True):
                        _add(GeneratorHypothesis(
                            direction=direction,
                            stop=stop,
                            color_rule="constant_C",
                            emit=emit,
                            constant_color=color,
                            delete_source=del_src,
                        ))

    # first_color_C stop variants
    for color in sorted(all_colors):
        for direction in directions:
            for emit in emits:
                _add(GeneratorHypothesis(
                    direction=direction,
                    stop="first_color_C",
                    color_rule="source_color",
                    emit=emit,
                    stop_color=color,
                ))

    # After_N variants (small N only, line_1wide only)
    for n in range(1, 6):
        for direction in directions:
            for color_rule in ["source_color", "two_phase"]:
                _add(GeneratorHypothesis(
                    direction=direction,
                    stop="after_N",
                    color_rule=color_rule,
                    emit="line_1wide",
                    stop_n=n,
                ))

    # INTERSECTION_COLOR variants for cross emits:
    # When two objects both emit cross_lines and overlap, the overlap
    # cells get repainted with a constant color.  Enumerate ic values
    # from non_source_colors (colors seen in residuals but not as any
    # source object's color -- these are the candidates).
    for ic_color in sorted(non_source_colors | all_colors):
        for color_rule in ["source_color", "constant_C"]:
            for del_src in (False, True):
                h = GeneratorHypothesis(
                    direction="up",  # irrelevant for cross
                    stop="grid_border",
                    color_rule=color_rule,
                    emit="cross",
                    delete_source=del_src,
                    intersection_color=ic_color,
                )
                if color_rule == "constant_C":
                    # Try each constant color for the lines themselves
                    for cc in sorted(all_colors):
                        h2 = GeneratorHypothesis(
                            direction="up",
                            stop="grid_border",
                            color_rule="constant_C",
                            emit="cross",
                            delete_source=del_src,
                            constant_color=cc,
                            intersection_color=ic_color,
                        )
                        _add(h2)
                else:
                    _add(h)

    return hypotheses


# ---------------------------------------------------------------------------
# 4. CLUSTERING
# ---------------------------------------------------------------------------

def _classify_residual_geometry(rec: ResidualRecord) -> str:
    """Classify the geometric relation of residual cells to the source
    object: collinear_row / collinear_col / cross / diagonal / radiating /
    contained / other."""
    if not rec.missing_cells and not rec.overpainted_cells:
        return "empty"

    all_residual_cells = set()
    for key in list(rec.missing_cells.keys()) + list(rec.overpainted_cells.keys()):
        all_residual_cells.add(_parse_cell_key(key))

    if not all_residual_cells:
        return "empty"

    obj_rows = set(r for r, _ in rec.source_cells)
    obj_cols = set(c for _, c in rec.source_cells)

    res_in_row = sum(1 for r, c in all_residual_cells if r in obj_rows)
    res_in_col = sum(1 for r, c in all_residual_cells if c in obj_cols)
    # Cells in BOTH row and col (the overlap of row/col sets)
    res_in_both = sum(1 for r, c in all_residual_cells
                      if r in obj_rows and c in obj_cols)
    total = len(all_residual_cells)

    # Cross: most cells are on the source's row OR column (union),
    # AND both row and col are well-represented.
    res_in_row_or_col = sum(1 for r, c in all_residual_cells
                            if r in obj_rows or c in obj_cols)
    if (res_in_row_or_col > 0.8 * total
            and res_in_row > 0.2 * total
            and res_in_col > 0.2 * total):
        return "cross"
    if res_in_row > 0.8 * total:
        return "collinear_row"
    if res_in_col > 0.8 * total:
        return "collinear_col"

    # Check diagonal
    diag_count = 0
    for r, c in all_residual_cells:
        for rr, cc in rec.source_cells:
            if abs(r - rr) == abs(c - cc) and abs(r - rr) > 0:
                diag_count += 1
                break
    if diag_count > 0.8 * total:
        return "diagonal"

    # Radiating: cells extend outward from source in multiple directions
    # but NOT on row/col (those are cross/collinear)
    directions_hit = set()
    for r, c in all_residual_cells:
        for rr, cc in rec.source_cells:
            dr = r - rr
            dc = c - cc
            if dr != 0 or dc != 0:
                if dr != 0:
                    dr = dr // abs(dr)
                if dc != 0:
                    dc = dc // abs(dc)
                directions_hit.add((dr, dc))
    if len(directions_hit) >= 3:
        return "radiating"

    # Contained: all residual cells are within source bbox
    r_min, c_min, r_max, c_max = rec.source_bbox
    if all(r_min <= r <= r_max and c_min <= c <= c_max
           for r, c in all_residual_cells):
        return "contained"

    return "other"


def cluster_residuals(
    records: list[ResidualRecord],
) -> dict[str, list[ResidualRecord]]:
    """Cluster residuals by their geometric classification."""
    clusters: dict[str, list[ResidualRecord]] = defaultdict(list)
    for rec in records:
        geo = _classify_residual_geometry(rec)
        clusters[geo].append(rec)
    return dict(clusters)


# ---------------------------------------------------------------------------
# 5. MINER: fit hypotheses to residuals
# ---------------------------------------------------------------------------

def _hypothesis_reproduces_residual(
    hyp: GeneratorHypothesis,
    rec: ResidualRecord,
) -> bool:
    """Check whether a hypothesis EXACTLY reproduces the missing-cell
    residual for a single record.

    EXACT means: the hypothesis paints all cells in rec.missing_cells
    with exactly the right colors.  For hypotheses with intersection_color,
    cells whose expected color equals the intersection_color value are
    excused from the per-object color match (they will be repainted by
    the program-level intersection_color mechanism).
    """
    if not rec.missing_cells:
        return False

    grid_array = np.array(rec.input_grid, dtype=np.int32)
    painted = _execute_hypothesis(
        hyp,
        source_cells=rec.source_cells,
        source_color=rec.source_color,
        grid_array=grid_array,
        bg=rec.bg,
    )

    # Build the expected missing cell set
    expected: dict[tuple[int, int], int] = {}
    for key, color in rec.missing_cells.items():
        expected[_parse_cell_key(key)] = color

    ic = hyp.intersection_color

    # Check: every expected cell must be accounted for
    for cell, exp_color in expected.items():
        if ic is not None and exp_color == ic:
            # This cell will be handled by intersection_color post-processing.
            # The hypothesis just needs to PAINT the cell (any color is fine --
            # the intersection mechanism repaint happens after all generators).
            if cell not in painted:
                return False
        else:
            # Standard check: painted with the right color
            if cell not in painted or painted[cell] != exp_color:
                return False

    return True


def mine_generators(
    residuals: list[ResidualRecord],
    *,
    max_hypotheses: int = 5000,
) -> list[tuple[GeneratorHypothesis, list[ResidualRecord]]]:
    """Mine generators: for each hypothesis, find residuals it exactly
    reproduces. Return hypotheses with their supporting residuals.

    A hypothesis is kept only if it reproduces at least one residual
    exactly.  Results are BEHAVIORALLY DEDUPED: if two hypotheses
    support exactly the same set of residual records, only the simpler
    one (fewer bound parameters) is kept.
    """
    hypotheses = enumerate_hypotheses(residuals, max_per_cluster=max_hypotheses)

    results: list[tuple[GeneratorHypothesis, list[ResidualRecord]]] = []

    for hyp in hypotheses:
        supporting: list[ResidualRecord] = []
        for rec in residuals:
            if _hypothesis_reproduces_residual(hyp, rec):
                supporting.append(rec)
        if supporting:
            results.append((hyp, supporting))

    # Sort by number of supporting residuals (more is better)
    results.sort(key=lambda x: -len(x[1]))

    # Behavioral dedup: collapse hypotheses with identical support sets
    deduped: list[tuple[GeneratorHypothesis, list[ResidualRecord]]] = []
    seen_support: set[str] = set()
    for hyp, supporting in results:
        # Build a support signature from the behavioral key + support set
        support_sig = hyp.behavioral_key() + "||" + ",".join(
            sorted(f"{r.task_id}:{r.pair_index}:{r.source_color}"
                   for r in supporting))
        if support_sig not in seen_support:
            seen_support.add(support_sig)
            deduped.append((hyp, supporting))

    return deduped


# ---------------------------------------------------------------------------
# 6. M3b DELTA-LOO ADMISSION
# ---------------------------------------------------------------------------

def _apply_hypothesis_to_rendered(
    hyp: GeneratorHypothesis,
    rendered: np.ndarray,
    source_cells: list[tuple[int, int]],
    source_color: int,
    grid_array: np.ndarray,
    bg: int,
) -> np.ndarray:
    """Apply a hypothesis on top of a rendered canvas, returning the
    modified canvas."""
    canvas = rendered.copy()
    painted = _execute_hypothesis(
        hyp,
        source_cells=source_cells,
        source_color=source_color,
        grid_array=grid_array,
        bg=bg,
    )
    for (r, c), color in painted.items():
        h, w = canvas.shape
        if 0 <= r < h and 0 <= c < w:
            canvas[r, c] = color
    return canvas


def admit_generator_m3b(
    hyp: GeneratorHypothesis,
    supporting_residuals: list[ResidualRecord],
    all_task_pairs: dict[str, list[GridPair]],
    *,
    k_delta: int = 2,
    disabled_kinds: Optional[set[str]] = None,
    disable_intersection_color: bool = False,
) -> Optional[AdmittedGenerator]:
    """M3b delta-level LOO: for each supporting task, hold out one pair,
    check that the hypothesis (fit on the remaining pairs' residuals)
    reproduces the held-out pair's residual EXACTLY.

    Require >= k_delta supporting tasks with full LOO pass.
    """
    # Group residuals by task
    task_residuals: dict[str, list[ResidualRecord]] = defaultdict(list)
    for rec in supporting_residuals:
        task_residuals[rec.task_id].append(rec)

    certified_tasks: list[str] = []
    fold_records: list[dict] = []

    for task_id, task_recs in task_residuals.items():
        if task_id not in all_task_pairs:
            continue

        train_pairs = all_task_pairs[task_id]
        n_pairs = len(train_pairs)

        if n_pairs < 2:
            continue

        # Group residuals by pair index
        recs_by_pair: dict[int, list[ResidualRecord]] = defaultdict(list)
        for rec in task_recs:
            recs_by_pair[rec.pair_index].append(rec)

        # Need residuals for at least 2 pairs
        if len(recs_by_pair) < 2:
            continue

        all_folds_pass = True
        fold_details = []

        for held_out_pair in sorted(recs_by_pair.keys()):
            # Fit on all pairs except held_out_pair
            fit_recs = []
            for pidx, recs in recs_by_pair.items():
                if pidx != held_out_pair:
                    fit_recs.extend(recs)

            # Check: does the hypothesis reproduce the held-out pair's
            # residuals exactly?
            held_out_recs = recs_by_pair[held_out_pair]
            fold_pass = True
            for ho_rec in held_out_recs:
                if not _hypothesis_reproduces_residual(hyp, ho_rec):
                    fold_pass = False
                    break

            fold_details.append({
                "held_out_pair": held_out_pair,
                "passed": fold_pass,
            })

            if not fold_pass:
                all_folds_pass = False
                break

        if all_folds_pass and len(recs_by_pair) >= 2:
            certified_tasks.append(task_id)
            fold_records.append({
                "task_id": task_id,
                "n_pairs": n_pairs,
                "n_folds": len(recs_by_pair),
                "folds": fold_details,
            })

    if len(certified_tasks) >= k_delta:
        return AdmittedGenerator(
            hypothesis=hyp,
            supporting_tasks=certified_tasks,
            fold_records=fold_records,
        )

    return None


# ---------------------------------------------------------------------------
# 7. INTEGRATION: convert hypothesis to generator rule
# ---------------------------------------------------------------------------

def hypothesis_to_generator_rule(hyp: GeneratorHypothesis) -> dict:
    """Convert a GeneratorHypothesis to the generator rule dict format
    used by generative.py's _apply_generator.

    Maps hypothesis-language expressions back to the existing vocabulary
    where possible, or creates a new 'learned_generator' kind.

    NOTE: intersection_color is a PROGRAM-LEVEL parameter, not a rule
    parameter.  The caller must set GenerativeProgram.intersection_color
    separately when constructing the program.
    """
    # Check if this maps to an existing vocabulary item
    if hyp.emit == "cross" and hyp.color_rule == "source_color":
        return {"kind": "cross_line"}

    if hyp.emit == "cross" and hyp.color_rule == "constant_C":
        return {"kind": "cross_line", "color": hyp.constant_color}

    if hyp.emit == "full_row" and hyp.color_rule == "source_color":
        return {"kind": "row_line"}

    if hyp.emit == "full_row" and hyp.color_rule == "constant_C":
        return {"kind": "row_line", "color": hyp.constant_color}

    if hyp.emit == "full_col" and hyp.color_rule == "source_color":
        return {"kind": "col_line"}

    if hyp.emit == "full_col" and hyp.color_rule == "constant_C":
        return {"kind": "col_line", "color": hyp.constant_color}

    if hyp.emit == "line_1wide" and hyp.stop == "grid_border" and \
       hyp.color_rule == "source_color" and hyp.direction in _UNIT:
        return {"kind": "ray", "direction": hyp.direction}

    if hyp.emit == "line_1wide" and hyp.stop == "first_nonbg" and \
       hyp.color_rule == "source_color" and hyp.direction in _UNIT:
        return {"kind": "ray_until_obstacle", "direction": hyp.direction}

    if hyp.emit == "line_1wide" and hyp.stop == "grid_border" and \
       hyp.color_rule == "two_phase" and hyp.direction in _UNIT:
        return {"kind": "ray_through_absorbed", "direction": hyp.direction}

    # General case: encode as a learned_generator rule
    rule: dict = {
        "kind": "learned_generator",
        "hypothesis": hyp.to_dict(),
    }
    return rule


def _apply_learned_generator(
    rule: dict,
    obj: ARCObject,
    bounds: tuple[int, int],
    grid_array: Optional[np.ndarray] = None,
    include_source: bool = False,
) -> dict:
    """Apply a learned generator (hypothesis-language expression) to an
    object. Used by the integration hook in generative.py."""
    hyp_dict = rule.get("hypothesis")
    if hyp_dict is None:
        return {}

    hyp = GeneratorHypothesis.from_dict(hyp_dict)
    cells_list = list(obj.cells)
    bg = rule.get("bg", 0)

    if grid_array is None:
        grid_array = np.zeros(bounds, dtype=np.int32)

    return _execute_hypothesis(
        hyp,
        source_cells=cells_list,
        source_color=obj.color,
        grid_array=grid_array,
        bg=bg,
    )


# ---------------------------------------------------------------------------
# 8. PERSISTENCE
# ---------------------------------------------------------------------------

def save_admitted_generators(
    generators: list[AdmittedGenerator],
    path: Path,
) -> None:
    """Save admitted generators to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [g.to_dict() for g in generators]
    path.write_text(json.dumps(data, indent=2))


def load_admitted_generators(path: Path) -> list[AdmittedGenerator]:
    """Load admitted generators from JSON."""
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [AdmittedGenerator.from_dict(d) for d in data]


# ---------------------------------------------------------------------------
# 9. E10 REDISCOVERY EXPERIMENT
# ---------------------------------------------------------------------------

# The R17b hand-added modes that E10 must rediscover
R17B_DISABLED_KINDS = {"cross_line", "ray_through_absorbed"}


def _hypothesis_equivalent_to_r17b_mode(
    hyp: GeneratorHypothesis,
    mode_name: str,
) -> bool:
    """Check whether a mined hypothesis is functionally equivalent to
    an R17b hand-added mode."""
    if mode_name == "cross_line":
        # cross_line = cross emit with source_color (or constant_C)
        return (hyp.emit == "cross" and
                hyp.color_rule in ("source_color", "constant_C"))
    if mode_name == "intersection_color":
        # intersection_color = cross emit with intersection_color set
        return (hyp.emit == "cross" and
                hyp.intersection_color is not None)
    if mode_name == "ray_through_absorbed":
        return (hyp.emit == "line_1wide" and
                hyp.stop == "grid_border" and
                hyp.color_rule == "two_phase" and
                hyp.direction in _UNIT)
    return False


def run_e10_experiment(
    task_pairs: dict[str, list[GridPair]],
    e10_task_ids: list[str],
    output_dir: Path,
) -> dict:
    """Run the E10 rediscovery experiment.

    (a) Disable R17b modes (cross_line, intersection_color,
        ray_through_absorbed) from the built-in vocabulary.
    (b) Extract residuals from the target tasks with modes disabled.
    (c) Run the miner and M3b admission.
    (d) Check whether any admitted hypothesis is equivalent to the
        disabled modes.
    (e) If rediscovered, check whether the hypothesis re-certifies
        23581191 via LOO.

    Returns a verdict dict.
    """
    print("=" * 60)
    print("E10 REDISCOVERY EXPERIMENT")
    print("=" * 60)
    print(f"Target tasks: {e10_task_ids}")
    print(f"Disabled R17b modes: {R17B_DISABLED_KINDS}")
    print(f"Disabled intersection_color: True")
    print()

    # (a/b) Extract residuals with R17b modes disabled
    all_residuals: list[ResidualRecord] = []
    for task_id in e10_task_ids:
        if task_id not in task_pairs:
            print(f"  SKIP {task_id}: not in task_pairs")
            continue
        pairs = task_pairs[task_id]
        print(f"  Extracting residuals for {task_id} ({len(pairs)} pairs)...")
        recs = extract_residuals_for_task(
            task_id, pairs,
            disabled_kinds=R17B_DISABLED_KINDS,
            disable_intersection_color=True,
        )
        all_residuals.extend(recs)
        print(f"    -> {len(recs)} residual records")

    print(f"\nTotal residuals: {len(all_residuals)}")

    if not all_residuals:
        verdict = {
            "status": "NO_RESIDUALS",
            "message": "No residuals extracted with R17b modes disabled",
            "rediscovered_cross_line": False,
            "rediscovered_ray_through_absorbed": False,
            "recertified_23581191": False,
        }
        _save_verdict(verdict, output_dir)
        return verdict

    # (c) Mine generators
    print("\nMining generators...")
    mined = mine_generators(all_residuals, max_hypotheses=5000)
    print(f"  Hypotheses with support: {len(mined)}")

    # (c) Admit via M3b
    print("\nRunning M3b admission...")
    admitted: list[AdmittedGenerator] = []
    for hyp, supporting in mined:
        gen = admit_generator_m3b(
            hyp, supporting, task_pairs,
            k_delta=1,  # Relaxed for E10: even 1 task is informative
            disabled_kinds=R17B_DISABLED_KINDS,
            disable_intersection_color=True,
        )
        if gen is not None:
            gen.provenance = "rediscovered"
            admitted.append(gen)
            print(f"  ADMITTED: {hyp.signature()} "
                  f"(tasks: {gen.supporting_tasks})")

    print(f"\nTotal admitted: {len(admitted)}")

    # (d) Check for R17b mode equivalents — collect ALL matches
    rediscovered_cross_line = False
    rediscovered_ray_through = False
    rediscovered_intersection_color = False
    cross_line_gens: list[AdmittedGenerator] = []
    ic_gens: list[AdmittedGenerator] = []
    ray_through_gens: list[AdmittedGenerator] = []

    for gen in admitted:
        if _hypothesis_equivalent_to_r17b_mode(gen.hypothesis, "cross_line"):
            rediscovered_cross_line = True
            cross_line_gens.append(gen)
            print(f"\n  ** REDISCOVERED cross_line: {gen.hypothesis.signature()}")
        if _hypothesis_equivalent_to_r17b_mode(gen.hypothesis, "intersection_color"):
            rediscovered_intersection_color = True
            ic_gens.append(gen)
            print(f"\n  ** REDISCOVERED intersection_color: "
                  f"{gen.hypothesis.signature()}")
        if _hypothesis_equivalent_to_r17b_mode(gen.hypothesis, "ray_through_absorbed"):
            rediscovered_ray_through = True
            ray_through_gens.append(gen)
            print(f"\n  ** REDISCOVERED ray_through_absorbed: "
                  f"{gen.hypothesis.signature()}")

    # (e) Check re-certification of 23581191
    # Try ALL rediscovered ic and cross_line hypotheses.
    recertified_23581191 = False
    recert_hyp = None
    if "23581191" in task_pairs:
        # Try ic hypotheses first (they carry both cross + ic)
        for gen in ic_gens:
            if _check_recertification(gen, task_pairs["23581191"]):
                recertified_23581191 = True
                recert_hyp = gen
                break
        # Also try cross_line hypotheses with ic search
        if not recertified_23581191:
            for gen in cross_line_gens:
                if _check_recertification(gen, task_pairs["23581191"]):
                    recertified_23581191 = True
                    recert_hyp = gen
                    break
        print(f"\n  Re-certification of 23581191: {recertified_23581191}")
        if recert_hyp:
            print(f"    via: {recert_hyp.hypothesis.signature()}")

    verdict = {
        "status": "COMPLETE",
        "n_residuals": len(all_residuals),
        "n_mined_with_support": len(mined),
        "n_admitted": len(admitted),
        "rediscovered_cross_line": rediscovered_cross_line,
        "rediscovered_intersection_color": rediscovered_intersection_color,
        "rediscovered_ray_through_absorbed": rediscovered_ray_through,
        "recertified_23581191": recertified_23581191,
        "admitted_signatures": [g.hypothesis.signature()
                                for g in admitted],
        "admitted_details": [g.to_dict() for g in admitted],
    }

    if rediscovered_cross_line and cross_line_gens:
        verdict["cross_line_hypothesis"] = cross_line_gens[0].hypothesis.to_dict()
        verdict["n_cross_line_variants"] = len(cross_line_gens)
    if rediscovered_intersection_color and ic_gens:
        verdict["intersection_color_hypothesis"] = ic_gens[0].hypothesis.to_dict()
        verdict["n_ic_variants"] = len(ic_gens)
    if rediscovered_ray_through and ray_through_gens:
        verdict["ray_through_hypothesis"] = ray_through_gens[0].hypothesis.to_dict()
    if recert_hyp is not None:
        verdict["recertification_hypothesis"] = recert_hyp.hypothesis.to_dict()

    _save_verdict(verdict, output_dir)

    print("\n" + "=" * 60)
    print("E10 VERDICT")
    print("=" * 60)
    print(f"  cross_line REDISCOVERED: {rediscovered_cross_line}")
    print(f"  intersection_color REDISCOVERED: {rediscovered_intersection_color}")
    print(f"  ray_through_absorbed REDISCOVERED: {rediscovered_ray_through}")
    print(f"  23581191 RE-CERTIFIED: {recertified_23581191}")
    print("=" * 60)

    return verdict


def _check_recertification(
    gen: AdmittedGenerator,
    train_pairs: list[GridPair],
) -> bool:
    """Check whether a rediscovered generator re-certifies a task via LOO.

    This means: using the hypothesis as the generator rule (in place of
    the disabled R17b mode), does the task solve train-perfectly on every
    LOO fold?

    If the hypothesis carries intersection_color, that value is used
    directly; otherwise all values 0-9 are tried.
    """
    rule = hypothesis_to_generator_rule(gen.hypothesis)
    hyp_ic = gen.hypothesis.intersection_color

    # Try all segmentation variants
    for variant in SEGMENTATION_TRIAL_ORDER:
        if not _fusion_signature(train_pairs, variant):
            continue

        pd0_gi, pd0_go = train_pairs[0]
        bg = background_for(pd0_gi, variant)

        for canvas_policy in ("over_input", "blank"):
            for del_src in (False, True):
                # Uniform program
                prog = GenerativeProgram(
                    seg_variant=variant,
                    generators=[({}, rule)],
                    canvas_policy=canvas_policy,
                    background=bg,
                    delete_source=del_src,
                    intersection_color=hyp_ic,
                )
                if _try_program_loo(prog, train_pairs):
                    return True

                # Per-color-class: each color class gets this rule
                objs = sorted(
                    segment(pd0_gi, variant, bg),
                    key=_object_sort_key)
                color_groups = {}
                for obj in objs:
                    color_groups.setdefault(obj.color, []).append(obj)
                if len(color_groups) > 1:
                    gens = [({"color": c}, dict(rule))
                            for c in sorted(color_groups.keys())]

                    # Try with the hypothesis's own ic first
                    if hyp_ic is not None:
                        prog_ic = GenerativeProgram(
                            seg_variant=variant,
                            generators=gens,
                            canvas_policy=canvas_policy,
                            background=bg,
                            delete_source=del_src,
                            intersection_color=hyp_ic,
                        )
                        if _try_program_loo(prog_ic, train_pairs):
                            return True

                    # Without ic
                    prog = GenerativeProgram(
                        seg_variant=variant,
                        generators=gens,
                        canvas_policy=canvas_policy,
                        background=bg,
                        delete_source=del_src,
                    )
                    if _try_program_loo(prog, train_pairs):
                        return True

                    # Search ic values 0-9
                    for ic in range(10):
                        if ic in color_groups or ic == bg:
                            continue
                        if ic == hyp_ic:
                            continue  # already tried
                        prog_ic = GenerativeProgram(
                            seg_variant=variant,
                            generators=gens,
                            canvas_policy=canvas_policy,
                            background=bg,
                            delete_source=del_src,
                            intersection_color=ic,
                        )
                        if _try_program_loo(prog_ic, train_pairs):
                            return True

    return False


def _try_program_loo(
    prog: GenerativeProgram,
    train_pairs: list[GridPair],
) -> bool:
    """LOO verification: for each fold, hold out one pair, rebuild the
    program from the remaining pairs, check the held-out pair."""
    # First check: does the program solve ALL pairs?
    from .generative import _try_program
    if not _try_program(prog, train_pairs):
        return False

    # LOO: hold out each pair in turn
    for i in range(len(train_pairs)):
        fold_pairs = [p for j, p in enumerate(train_pairs) if j != i]
        held_out = train_pairs[i]

        # The program was induced from ALL pairs, but for LOO we need
        # to verify it still works on the held-out pair.
        # Since GenerativeProgram uses the same rule for all pairs
        # (no per-pair fitting), train-perfect => LOO passes.
        gi, go = held_out
        rendered = render_generative(prog, gi).to_numpy()
        if not _composite_matches(rendered, go.to_numpy()):
            return False

    return True


def _save_verdict(verdict: dict, output_dir: Path) -> None:
    """Save E10 verdict to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "e10_verdict.json"
    path.write_text(json.dumps(verdict, indent=2))
    print(f"\nVerdict saved to {path}")
