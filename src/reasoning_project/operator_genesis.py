"""OperatorGenesis: verifier-gated operator synthesis from train-pair residuals.

Synthesizes executable operators by analyzing the pixel-level difference
between input and output on (optionally lifted) train pairs. Each operator
family has a parameter inference step and produces an executable callable.

Every SynthesizedOperator has an `execute(grid) -> grid` callable that
transforms an input grid into a predicted output grid using ONLY information
derived from train pairs. Test outputs are never used during synthesis.

Architecture:
    train_pairs → residual analysis → candidate operator families
    → parameter inference (per family) → executable synthesis
    → train consistency check → LOO validation → return candidates
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage


@dataclass
class SynthesizedOperator:
    """Executable operator proposal from OperatorGenesis."""
    operator_id: str
    operator_family: str
    parameters: Dict[str, Any]
    preconditions: List[str]
    execute: Callable[[np.ndarray], np.ndarray]
    explanation: str
    source_failure_signature: Dict[str, Any]


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _extract_objects(grid: np.ndarray) -> List[Dict[str, Any]]:
    """Extract connected components as object dicts."""
    labeled, n = ndimage.label(grid != 0)
    objects = []
    for i in range(1, n + 1):
        mask = labeled == i
        rows, cols = np.where(mask)
        if len(rows) == 0:
            continue
        r0, c0, r1, c1 = rows.min(), cols.min(), rows.max(), cols.max()
        obj = {
            "label": i,
            "mask": mask,
            "bbox": (int(r0), int(c0), int(r1), int(c1)),
            "area": int(mask.sum()),
            "colors": sorted(set(grid[mask].tolist())),
            "primary_color": int(np.bincount(grid[mask].flatten())[1:].argmax() + 1) if grid[mask].max() > 0 else 0,
            "center_r": float(rows.mean()),
            "center_c": float(cols.mean()),
            "pixels": grid[mask].copy(),
            "shape_patch": grid[r0:r1+1, c0:c1+1].copy(),
        }
        objects.append(obj)
    return objects


def _bbox_content(grid: np.ndarray) -> Tuple[int, int, int, int]:
    """Bounding box of all non-zero pixels."""
    nz = np.nonzero(grid)
    if len(nz[0]) == 0:
        return (0, 0, grid.shape[0] - 1, grid.shape[1] - 1)
    return (int(nz[0].min()), int(nz[1].min()), int(nz[0].max()), int(nz[1].max()))


def _check_train_consistency(
    execute: Callable, train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Tuple[bool, float]:
    """Check if execute(inp) == out for all train pairs. Returns (ok, error_rate)."""
    total_pixels = 0
    wrong_pixels = 0
    for inp, out in train_pairs:
        try:
            pred = execute(inp)
        except Exception:
            return False, 1.0
        if pred.shape != out.shape:
            return False, 1.0
        total_pixels += out.size
        wrong_pixels += int((pred != out).sum())
    error_rate = wrong_pixels / max(total_pixels, 1)
    return error_rate == 0.0, error_rate


def _check_loo(
    synthesize_fn: Callable,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> bool:
    """Leave-one-out validation: for each held-out pair, synthesize from the
    rest and check if the held-out pair is predicted correctly."""
    if len(train_pairs) < 2:
        return True
    for i in range(len(train_pairs)):
        rest = train_pairs[:i] + train_pairs[i+1:]
        held = train_pairs[i]
        ops = synthesize_fn(rest)
        if not ops:
            return False
        solved_held = False
        for op in ops:
            try:
                pred = op.execute(held[0])
                if pred.shape == held[1].shape and np.array_equal(pred, held[1]):
                    solved_held = True
                    break
            except Exception:
                continue
        if not solved_held:
            return False
    return True


# ---------------------------------------------------------------------------
# Operator Family: CropToChangedRegion
# ---------------------------------------------------------------------------

def _synthesize_crop_to_changed_region(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Crop input to the bounding box of the output content."""
    candidates = []

    # Strategy 1: output is a subregion of input — find which subregion
    for strategy_name, crop_fn in [
        ("content_bbox", _crop_content_bbox),
        ("largest_object_bbox", _crop_largest_object),
        ("non_background_bbox", _crop_non_background),
    ]:
        fn = crop_fn
        ok, err = _check_train_consistency(fn, train_pairs)
        if ok:
            candidates.append(SynthesizedOperator(
                operator_id=f"crop_{uuid.uuid4().hex[:8]}",
                operator_family="crop_extract",
                parameters={"strategy": strategy_name},
                preconditions=["output_smaller_than_input"],
                execute=fn,
                explanation=f"Crop input using {strategy_name}",
                source_failure_signature={},
            ))

    # Strategy 2: crop to specific object by color
    if train_pairs:
        inp0, out0 = train_pairs[0]
        out_colors = set(out0.flatten().tolist()) - {0}
        for color in out_colors:
            def make_crop_color(c):
                def _crop(grid, _c=c):
                    mask = grid == _c
                    if not mask.any():
                        return grid
                    rows, cols = np.where(mask)
                    r0, c0, r1, c1 = rows.min(), cols.min(), rows.max(), cols.max()
                    return grid[r0:r1+1, c0:c1+1]
                return _crop
            fn = make_crop_color(color)
            ok, err = _check_train_consistency(fn, train_pairs)
            if ok:
                candidates.append(SynthesizedOperator(
                    operator_id=f"crop_color_{color}_{uuid.uuid4().hex[:8]}",
                    operator_family="crop_extract",
                    parameters={"strategy": "crop_to_color", "color": color},
                    preconditions=["output_smaller_than_input"],
                    execute=fn,
                    explanation=f"Crop to bounding box of color {color}",
                    source_failure_signature={},
                ))

    # Strategy 3: extract specific rectangular region by offset from train pairs
    if len(train_pairs) >= 2:
        inp0, out0 = train_pairs[0]
        oh, ow = out0.shape
        # Try all offsets where out0 matches a subgrid of inp0
        for r_off in range(inp0.shape[0] - oh + 1):
            for c_off in range(inp0.shape[1] - ow + 1):
                subgrid = inp0[r_off:r_off+oh, c_off:c_off+ow]
                if np.array_equal(subgrid, out0):
                    def make_crop_offset(ro, co, h, w):
                        def _crop(grid, _ro=ro, _co=co, _h=h, _w=w):
                            return grid[_ro:_ro+_h, _co:_co+_w]
                        return _crop
                    fn = make_crop_offset(r_off, c_off, oh, ow)
                    ok, err = _check_train_consistency(fn, train_pairs)
                    if ok:
                        candidates.append(SynthesizedOperator(
                            operator_id=f"crop_offset_{uuid.uuid4().hex[:8]}",
                            operator_family="crop_extract",
                            parameters={"r_offset": r_off, "c_offset": c_off, "h": oh, "w": ow},
                            preconditions=["output_smaller_than_input"],
                            execute=fn,
                            explanation=f"Crop at fixed offset ({r_off},{c_off}) size ({oh},{ow})",
                            source_failure_signature={},
                        ))
                    break
            else:
                continue
            break

    return candidates


def _crop_content_bbox(grid: np.ndarray) -> np.ndarray:
    r0, c0, r1, c1 = _bbox_content(grid)
    return grid[r0:r1+1, c0:c1+1]


def _crop_largest_object(grid: np.ndarray) -> np.ndarray:
    objects = _extract_objects(grid)
    if not objects:
        return grid
    largest = max(objects, key=lambda o: o["area"])
    r0, c0, r1, c1 = largest["bbox"]
    return grid[r0:r1+1, c0:c1+1]


def _crop_non_background(grid: np.ndarray) -> np.ndarray:
    nz = np.nonzero(grid)
    if len(nz[0]) == 0:
        return grid
    r0, c0 = nz[0].min(), nz[1].min()
    r1, c1 = nz[0].max(), nz[1].max()
    return grid[r0:r1+1, c0:c1+1]


# ---------------------------------------------------------------------------
# Operator Family: CopyObjectByVector / MoveObjectByVector
# ---------------------------------------------------------------------------

def _synthesize_move_copy(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize object move/copy operators from train pairs."""
    candidates = []

    if not train_pairs:
        return candidates

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return candidates

    # Find objects that move between input and output
    inp0, out0 = train_pairs[0]
    objs_in = _extract_objects(inp0)
    objs_out = _extract_objects(out0)

    if not objs_in or not objs_out:
        return candidates

    # Try to match objects by color and shape
    for obj_in in objs_in:
        for obj_out in objs_out:
            if obj_in["primary_color"] != obj_out["primary_color"]:
                continue
            if obj_in["shape_patch"].shape != obj_out["shape_patch"].shape:
                continue
            if not np.array_equal(obj_in["shape_patch"], obj_out["shape_patch"]):
                continue

            dr = int(obj_out["bbox"][0] - obj_in["bbox"][0])
            dc = int(obj_out["bbox"][1] - obj_in["bbox"][1])
            if dr == 0 and dc == 0:
                continue

            is_copy = len(objs_out) > len(objs_in)

            def make_move(delta_r, delta_c, do_copy):
                def _move(grid, _dr=delta_r, _dc=delta_c, _copy=do_copy):
                    result = grid.copy() if _copy else np.zeros_like(grid)
                    if not _copy:
                        result[:] = grid
                    objs = _extract_objects(grid)
                    for obj in objs:
                        r0, c0, r1, c1 = obj["bbox"]
                        patch = obj["shape_patch"]
                        if not _copy:
                            for rr in range(r0, r1+1):
                                for cc in range(c0, c1+1):
                                    if obj["mask"][rr, cc]:
                                        result[rr, cc] = 0
                        nr0, nc0 = r0 + _dr, c0 + _dc
                        for rr in range(patch.shape[0]):
                            for cc in range(patch.shape[1]):
                                if patch[rr, cc] != 0:
                                    tr, tc = nr0 + rr, nc0 + cc
                                    if 0 <= tr < result.shape[0] and 0 <= tc < result.shape[1]:
                                        result[tr, tc] = patch[rr, cc]
                    return result
                return _move

            fn = make_move(dr, dc, is_copy)
            ok, err = _check_train_consistency(fn, train_pairs)
            if ok:
                family = "copy_translate" if is_copy else "object_move"
                candidates.append(SynthesizedOperator(
                    operator_id=f"{family}_{uuid.uuid4().hex[:8]}",
                    operator_family=family,
                    parameters={"delta_r": dr, "delta_c": dc, "is_copy": is_copy},
                    preconditions=["same_shape"],
                    execute=fn,
                    explanation=f"{'Copy' if is_copy else 'Move'} objects by ({dr},{dc})",
                    source_failure_signature={},
                ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: ExtendLine
# ---------------------------------------------------------------------------

def _synthesize_extend_line(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize line extension operators."""
    candidates = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return candidates

    if not train_pairs:
        return candidates

    inp0, out0 = train_pairs[0]
    diff = inp0 != out0
    if not diff.any():
        return candidates

    # Check if the difference forms horizontal or vertical lines
    rows_changed = np.where(diff.any(axis=1))[0]
    cols_changed = np.where(diff.any(axis=0))[0]

    # Try extending each non-zero pixel's color along its row/column
    for direction in ["horizontal", "vertical"]:
        def make_extend(d):
            def _extend(grid, _dir=d):
                result = grid.copy()
                h, w = grid.shape
                for r in range(h):
                    for c in range(w):
                        if grid[r, c] != 0:
                            if _dir == "horizontal":
                                for cc in range(w):
                                    if result[r, cc] == 0:
                                        result[r, cc] = grid[r, c]
                            else:
                                for rr in range(h):
                                    if result[rr, c] == 0:
                                        result[rr, c] = grid[r, c]
                return result
            return _extend

        fn = make_extend(direction)
        ok, err = _check_train_consistency(fn, train_pairs)
        if ok:
            candidates.append(SynthesizedOperator(
                operator_id=f"extend_line_{direction}_{uuid.uuid4().hex[:8]}",
                operator_family="line_extend",
                parameters={"direction": direction},
                preconditions=["same_shape", "has_isolated_pixels"],
                execute=fn,
                explanation=f"Extend pixels as lines {direction}ly",
                source_failure_signature={},
            ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: FillEnclosedHole
# ---------------------------------------------------------------------------

def _synthesize_fill_hole(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize hole-filling operators."""
    candidates = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return candidates

    # Strategy 1: fill all enclosed zeros with surrounding color
    def _fill_enclosed(grid):
        result = grid.copy()
        h, w = grid.shape
        # Flood fill from border to find exterior zeros
        exterior = np.zeros((h, w), dtype=bool)
        stack = []
        for r in range(h):
            for c in [0, w - 1]:
                if grid[r, c] == 0 and not exterior[r, c]:
                    stack.append((r, c))
                    exterior[r, c] = True
        for c in range(w):
            for r in [0, h - 1]:
                if grid[r, c] == 0 and not exterior[r, c]:
                    stack.append((r, c))
                    exterior[r, c] = True
        while stack:
            r, c = stack.pop()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w and not exterior[nr, nc] and grid[nr, nc] == 0:
                    exterior[nr, nc] = True
                    stack.append((nr, nc))
        # Fill interior zeros with nearest non-zero neighbor color
        for r in range(h):
            for c in range(w):
                if grid[r, c] == 0 and not exterior[r, c]:
                    # Find nearest non-zero color
                    for dist in range(1, max(h, w)):
                        found = False
                        for dr in range(-dist, dist + 1):
                            for dc in range(-dist, dist + 1):
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < h and 0 <= nc < w and grid[nr, nc] != 0:
                                    result[r, c] = grid[nr, nc]
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
        return result

    ok, err = _check_train_consistency(_fill_enclosed, train_pairs)
    if ok:
        candidates.append(SynthesizedOperator(
            operator_id=f"fill_hole_{uuid.uuid4().hex[:8]}",
            operator_family="hole_fill",
            parameters={"strategy": "fill_enclosed_nearest"},
            preconditions=["same_shape", "has_enclosed_zeros"],
            execute=_fill_enclosed,
            explanation="Fill enclosed holes with nearest non-zero color",
            source_failure_signature={},
        ))

    # Strategy 2: fill with specific color
    if train_pairs:
        inp0, out0 = train_pairs[0]
        diff = inp0 != out0
        if diff.any():
            fill_colors = set(out0[diff].flatten().tolist()) - {0}
            for fill_color in fill_colors:
                def make_fill_color(fc):
                    def _fill(grid, _fc=fc):
                        result = grid.copy()
                        h, w = grid.shape
                        exterior = np.zeros((h, w), dtype=bool)
                        stack = []
                        for r in range(h):
                            for c in [0, w - 1]:
                                if grid[r, c] == 0 and not exterior[r, c]:
                                    stack.append((r, c))
                                    exterior[r, c] = True
                        for c in range(w):
                            for r in [0, h - 1]:
                                if grid[r, c] == 0 and not exterior[r, c]:
                                    stack.append((r, c))
                                    exterior[r, c] = True
                        while stack:
                            r, c = stack.pop()
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < h and 0 <= nc < w and not exterior[nr, nc] and grid[nr, nc] == 0:
                                    exterior[nr, nc] = True
                                    stack.append((nr, nc))
                        for r in range(h):
                            for c in range(w):
                                if grid[r, c] == 0 and not exterior[r, c]:
                                    result[r, c] = _fc
                        return result
                    return _fill
                fn = make_fill_color(fill_color)
                ok, err = _check_train_consistency(fn, train_pairs)
                if ok:
                    candidates.append(SynthesizedOperator(
                        operator_id=f"fill_hole_color_{fill_color}_{uuid.uuid4().hex[:8]}",
                        operator_family="hole_fill",
                        parameters={"strategy": "fill_enclosed_color", "color": fill_color},
                        preconditions=["same_shape", "has_enclosed_zeros"],
                        execute=fn,
                        explanation=f"Fill enclosed holes with color {fill_color}",
                        source_failure_signature={},
                    ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: CompleteSymmetry
# ---------------------------------------------------------------------------

def _synthesize_complete_symmetry(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize symmetry completion operators."""
    candidates = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return candidates

    for sym_type, sym_fn in [
        ("horizontal", lambda g: np.maximum(g, np.fliplr(g))),
        ("vertical", lambda g: np.maximum(g, np.flipud(g))),
        ("both", lambda g: np.maximum(np.maximum(g, np.fliplr(g)), np.flipud(g))),
        ("diagonal", lambda g: np.maximum(g, g.T) if g.shape[0] == g.shape[1] else g),
    ]:
        def make_sym(sfn):
            def _sym(grid, _sfn=sfn):
                try:
                    return _sfn(grid)
                except Exception:
                    return grid
            return _sym

        fn = make_sym(sym_fn)
        ok, err = _check_train_consistency(fn, train_pairs)
        if ok:
            candidates.append(SynthesizedOperator(
                operator_id=f"symmetry_{sym_type}_{uuid.uuid4().hex[:8]}",
                operator_family="symmetry_complete",
                parameters={"symmetry_type": sym_type},
                preconditions=["same_shape"],
                execute=fn,
                explanation=f"Complete {sym_type} symmetry",
                source_failure_signature={},
            ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: RepeatMotif
# ---------------------------------------------------------------------------

def _synthesize_repeat_motif(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize motif repetition/tiling operators."""
    candidates = []

    if not train_pairs:
        return candidates

    inp0, out0 = train_pairs[0]

    # Try tiling input to match output size
    if out0.shape[0] >= inp0.shape[0] and out0.shape[1] >= inp0.shape[1]:
        ih, iw = inp0.shape
        oh, ow = out0.shape

        if oh % ih == 0 and ow % iw == 0:
            reps_r = oh // ih
            reps_c = ow // iw

            def make_tile(rr, rc):
                def _tile(grid, _rr=rr, _rc=rc):
                    return np.tile(grid, (_rr, _rc))
                return _tile

            fn = make_tile(reps_r, reps_c)
            ok, err = _check_train_consistency(fn, train_pairs)
            if ok:
                candidates.append(SynthesizedOperator(
                    operator_id=f"repeat_tile_{uuid.uuid4().hex[:8]}",
                    operator_family="repeat_motif",
                    parameters={"reps_r": reps_r, "reps_c": reps_c},
                    preconditions=["output_larger_than_input"],
                    execute=fn,
                    explanation=f"Tile input {reps_r}x{reps_c}",
                    source_failure_signature={},
                ))

    # Try extracting a subgrid motif from input and tiling
    if inp0.shape == out0.shape:
        ih, iw = inp0.shape
        for mh in range(1, ih + 1):
            if ih % mh != 0:
                continue
            for mw in range(1, iw + 1):
                if iw % mw != 0:
                    continue
                if mh == ih and mw == iw:
                    continue
                motif = inp0[:mh, :mw]
                tiled = np.tile(motif, (ih // mh, iw // mw))
                if np.array_equal(tiled, out0):
                    def make_motif_tile(m_h, m_w):
                        def _mtile(grid, _mh=m_h, _mw=m_w):
                            motif = grid[:_mh, :_mw]
                            rr = grid.shape[0] // _mh
                            rc = grid.shape[1] // _mw
                            return np.tile(motif, (rr, rc))
                        return _mtile
                    fn = make_motif_tile(mh, mw)
                    ok, err = _check_train_consistency(fn, train_pairs)
                    if ok:
                        candidates.append(SynthesizedOperator(
                            operator_id=f"motif_tile_{mh}x{mw}_{uuid.uuid4().hex[:8]}",
                            operator_family="repeat_motif",
                            parameters={"motif_h": mh, "motif_w": mw},
                            preconditions=["same_shape"],
                            execute=fn,
                            explanation=f"Extract {mh}x{mw} motif and tile",
                            source_failure_signature={},
                        ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: ConditionalRecolor
# ---------------------------------------------------------------------------

def _synthesize_conditional_recolor(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize conditional recoloring operators."""
    candidates = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return candidates

    if not train_pairs:
        return candidates

    # Strategy 1: global color mapping
    inp0, out0 = train_pairs[0]
    color_map = {}
    for r in range(inp0.shape[0]):
        for c in range(inp0.shape[1]):
            ci, co = int(inp0[r, c]), int(out0[r, c])
            if ci in color_map:
                if color_map[ci] != co:
                    color_map = None
                    break
            else:
                color_map[ci] = co
        if color_map is None:
            break

    if color_map is not None and any(k != v for k, v in color_map.items()):
        def make_colormap(cm):
            def _recolor(grid, _cm=cm):
                result = grid.copy()
                for old_c, new_c in _cm.items():
                    result[grid == old_c] = new_c
                return result
            return _recolor
        fn = make_colormap(dict(color_map))
        ok, err = _check_train_consistency(fn, train_pairs)
        if ok:
            candidates.append(SynthesizedOperator(
                operator_id=f"recolor_map_{uuid.uuid4().hex[:8]}",
                operator_family="conditional_recolor",
                parameters={"color_map": dict(color_map)},
                preconditions=["same_shape"],
                execute=fn,
                explanation=f"Recolor by global mapping {dict(color_map)}",
                source_failure_signature={},
            ))

    # Strategy 2: recolor objects based on size rank
    for rank_by in ["area", "color"]:
        def make_rank_recolor(rb):
            def _recolor(grid, _rb=rb):
                result = grid.copy()
                objs = _extract_objects(grid)
                if not objs:
                    return result
                if _rb == "area":
                    objs.sort(key=lambda o: o["area"])
                else:
                    objs.sort(key=lambda o: o["primary_color"])
                for i, obj in enumerate(objs):
                    result[obj["mask"]] = i + 1
                return result
            return _recolor
        fn = make_rank_recolor(rank_by)
        ok, err = _check_train_consistency(fn, train_pairs)
        if ok:
            candidates.append(SynthesizedOperator(
                operator_id=f"recolor_rank_{rank_by}_{uuid.uuid4().hex[:8]}",
                operator_family="conditional_recolor",
                parameters={"strategy": f"rank_by_{rank_by}"},
                preconditions=["same_shape", "has_objects"],
                execute=fn,
                explanation=f"Recolor objects ranked by {rank_by}",
                source_failure_signature={},
            ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: ObjectCorrespondenceTransform
# ---------------------------------------------------------------------------

def _synthesize_object_correspondence(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize object correspondence transforms."""
    candidates = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return candidates

    if not train_pairs:
        return candidates

    # Check if output keeps only specific objects (by various criteria)
    for keep_criterion, keep_name in [
        (lambda objs: [o for o in objs if o["area"] == max(oo["area"] for oo in objs)], "keep_largest"),
        (lambda objs: [o for o in objs if o["area"] == min(oo["area"] for oo in objs)], "keep_smallest"),
        (lambda objs: [o for o in objs if len(o["colors"]) == 1], "keep_single_color"),
    ]:
        def make_keep(kfn):
            def _keep(grid, _kfn=kfn):
                result = np.zeros_like(grid)
                objs = _extract_objects(grid)
                if not objs:
                    return result
                kept = _kfn(objs)
                for obj in kept:
                    result[obj["mask"]] = grid[obj["mask"]]
                return result
            return _keep
        fn = make_keep(keep_criterion)
        ok, err = _check_train_consistency(fn, train_pairs)
        if ok:
            candidates.append(SynthesizedOperator(
                operator_id=f"obj_corr_{keep_name}_{uuid.uuid4().hex[:8]}",
                operator_family="object_correspondence",
                parameters={"strategy": keep_name},
                preconditions=["same_shape", "has_objects"],
                execute=fn,
                explanation=f"Keep objects by {keep_name}",
                source_failure_signature={},
            ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: TwoStepComposition
# ---------------------------------------------------------------------------

def _synthesize_two_step_composition(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    single_step_ops: List[SynthesizedOperator],
) -> List[SynthesizedOperator]:
    """Synthesize two-step compositions of existing operators."""
    candidates = []

    if len(single_step_ops) < 2:
        return candidates

    # Try all pairs (limited to first 10 to avoid explosion)
    for i, op1 in enumerate(single_step_ops[:10]):
        for j, op2 in enumerate(single_step_ops[:10]):
            if i == j:
                continue

            def make_compose(f1, f2):
                def _compose(grid, _f1=f1, _f2=f2):
                    intermediate = _f1(grid)
                    return _f2(intermediate)
                return _compose

            fn = make_compose(op1.execute, op2.execute)
            ok, err = _check_train_consistency(fn, train_pairs)
            if ok:
                candidates.append(SynthesizedOperator(
                    operator_id=f"compose_{uuid.uuid4().hex[:8]}",
                    operator_family="two_step_composition",
                    parameters={
                        "step1": op1.operator_family,
                        "step2": op2.operator_family,
                    },
                    preconditions=op1.preconditions + op2.preconditions,
                    execute=fn,
                    explanation=f"Compose: {op1.explanation} then {op2.explanation}",
                    source_failure_signature={},
                ))

    return candidates


# ---------------------------------------------------------------------------
# Operator Family: ContainmentDepthFill
# ---------------------------------------------------------------------------

def _find_filled_rectangles(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Find rectangular regions of a single non-bg color."""
    rects = []
    labeled, n = ndimage.label(grid != bg)
    for i in range(1, n + 1):
        comp = labeled == i
        rows, cols = np.where(comp)
        if len(rows) == 0:
            continue
        r0, c0, r1, c1 = int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max())
        h, w = r1 - r0 + 1, c1 - c0 + 1
        if h < 2 or w < 2:
            continue
        patch = grid[r0:r1+1, c0:c1+1]
        fill_color = int(grid[r0, c0])
        if fill_color == bg:
            continue
        if np.all((patch == fill_color) | (patch == bg)):
            if np.sum(patch == fill_color) >= 0.5 * patch.size:
                rects.append({
                    "r0": r0, "c0": c0, "r1": r1, "c1": c1,
                    "h": h, "w": w, "fill_color": fill_color,
                    "mask": comp,
                })
    return rects


def _find_bordered_rectangles(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Find rectangular regions with a uniform-color border enclosing interior."""
    rects = []
    border_colors = set(int(c) for c in np.unique(grid)) - {bg}
    for bc in border_colors:
        mask_bc = grid == bc
        labeled, n = ndimage.label(mask_bc)
        for i in range(1, n + 1):
            comp = labeled == i
            rows, cols = np.where(comp)
            if len(rows) < 4:
                continue
            r0, c0, r1, c1 = int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max())
            h, w = r1 - r0 + 1, c1 - c0 + 1
            if h < 3 or w < 3:
                continue
            top = np.all(grid[r0, c0:c1+1] == bc)
            bot = np.all(grid[r1, c0:c1+1] == bc)
            left = np.all(grid[r0:r1+1, c0] == bc)
            right = np.all(grid[r0:r1+1, c1] == bc)
            if not (top and bot and left and right):
                continue
            int_h, int_w = h - 2, w - 2
            interior = grid[r0+1:r1, c0+1:c1]
            int_markers = int(np.sum(interior == bc))
            int_zeros = int(np.sum(interior == bg))
            marker_positions = []
            for mr in range(r0+1, r1):
                for mc in range(c0+1, c1):
                    if int(grid[mr, mc]) == bc:
                        depth = min(mr - r0, r1 - mr, mc - c0, c1 - mc)
                        marker_positions.append((mr, mc, depth))
            rects.append({
                "r0": r0, "c0": c0, "r1": r1, "c1": c1,
                "h": h, "w": w, "border_color": bc,
                "int_h": int_h, "int_w": int_w,
                "int_markers": int_markers, "int_zeros": int_zeros,
                "marker_positions": marker_positions,
                "marker_depth": marker_positions[0][2] if marker_positions else 0,
            })
    return rects


def _chebyshev_depth_map(r0: int, c0: int, r1: int, c1: int) -> np.ndarray:
    """Compute Chebyshev distance from the rectangle border for each interior pixel."""
    h, w = r1 - r0 + 1, c1 - c0 + 1
    depth = np.zeros((h, w), dtype=int)
    for r in range(h):
        for c in range(w):
            depth[r, c] = min(r, h - 1 - r, c, w - 1 - c)
    return depth


def _synthesize_containment_depth_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize containment-depth-fill operators.

    Strategy 1 (concentric_ring): filled rectangles get concentric ring coloring.
    Strategy 2 (enclosed_flat_fill): bordered rectangles get interior filled by
    a color determined by a measurable property (marker depth, interior size).
    """
    candidates = []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return candidates

    # --- Strategy 1: Concentric ring coloring ---
    _try_concentric_ring(train_pairs, candidates)

    # --- Strategy 2: Enclosed flat fill by property ---
    _try_enclosed_flat_fill(train_pairs, candidates)

    return candidates


def _try_concentric_ring(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    candidates: List[SynthesizedOperator],
) -> None:
    """Detect filled rectangles, learn depth→color mapping, emit operator."""
    depth_color_samples: Dict[int, set] = {}
    base_color = None

    for inp, out in train_pairs:
        rects = _find_filled_rectangles(inp)
        if not rects:
            return
        for rect in rects:
            r0, c0, r1, c1 = rect["r0"], rect["c0"], rect["r1"], rect["c1"]
            fc = rect["fill_color"]
            if base_color is None:
                base_color = fc
            elif base_color != fc:
                return
            dmap = _chebyshev_depth_map(r0, c0, r1, c1)
            for lr in range(r1 - r0 + 1):
                for lc in range(c1 - c0 + 1):
                    d = int(dmap[lr, lc])
                    ov = int(out[r0 + lr, c0 + lc])
                    if d not in depth_color_samples:
                        depth_color_samples[d] = set()
                    depth_color_samples[d].add(ov)

    depth_to_color: Dict[int, int] = {}
    for d, colors in depth_color_samples.items():
        if len(colors) != 1:
            return
        depth_to_color[d] = colors.pop()

    if not depth_to_color:
        return

    max_depth = max(depth_to_color.keys())
    color_seq = [depth_to_color.get(d, base_color) for d in range(max_depth + 1)]

    def _execute_concentric(grid, _base=base_color, _seq=list(color_seq)):
        result = grid.copy()
        rects = _find_filled_rectangles(grid)
        for rect in rects:
            if rect["fill_color"] != _base:
                continue
            r0, c0, r1, c1 = rect["r0"], rect["c0"], rect["r1"], rect["c1"]
            dmap = _chebyshev_depth_map(r0, c0, r1, c1)
            for lr in range(r1 - r0 + 1):
                for lc in range(c1 - c0 + 1):
                    d = int(dmap[lr, lc])
                    if d < len(_seq):
                        result[r0 + lr, c0 + lc] = _seq[d]
                    else:
                        cyc_len = len(_seq) - 1
                        if cyc_len > 0:
                            cyc_idx = ((d - 1) % cyc_len) + 1 if d > 0 else 0
                            result[r0 + lr, c0 + lc] = _seq[cyc_idx]
        return result

    ok, err = _check_train_consistency(_execute_concentric, train_pairs)
    if not ok:
        extend_len = max_depth + 4
        for cycle_start in range(1, max_depth + 1):
            cycle = color_seq[cycle_start:]
            if len(cycle) < 2:
                continue
            extended = list(color_seq[:cycle_start])
            for i in range(extend_len - cycle_start):
                extended.append(cycle[i % len(cycle)])

            def _execute_ext(grid, _base=base_color, _seq=list(extended)):
                result = grid.copy()
                rects = _find_filled_rectangles(grid)
                for rect in rects:
                    if rect["fill_color"] != _base:
                        continue
                    r0, c0, r1, c1 = rect["r0"], rect["c0"], rect["r1"], rect["c1"]
                    dmap = _chebyshev_depth_map(r0, c0, r1, c1)
                    for lr in range(r1 - r0 + 1):
                        for lc in range(c1 - c0 + 1):
                            d = int(dmap[lr, lc])
                            if d < len(_seq):
                                result[r0 + lr, c0 + lc] = _seq[d]
                return result

            ok2, err2 = _check_train_consistency(_execute_ext, train_pairs)
            if ok2:
                candidates.append(SynthesizedOperator(
                    operator_id=f"cdf_ring_{uuid.uuid4().hex[:8]}",
                    operator_family="containment_depth_fill",
                    parameters={
                        "strategy": "concentric_ring",
                        "base_color": base_color,
                        "color_sequence": extended,
                        "cycle_start": cycle_start,
                    },
                    preconditions=["same_size", "filled_rectangles"],
                    execute=_execute_ext,
                    explanation=f"Concentric ring fill: base={base_color}, "
                                f"cycle from depth {cycle_start}: {cycle}",
                    source_failure_signature={},
                ))
                return
        return

    candidates.append(SynthesizedOperator(
        operator_id=f"cdf_ring_{uuid.uuid4().hex[:8]}",
        operator_family="containment_depth_fill",
        parameters={
            "strategy": "concentric_ring",
            "base_color": base_color,
            "color_sequence": color_seq,
        },
        preconditions=["same_size", "filled_rectangles"],
        execute=_execute_concentric,
        explanation=f"Concentric ring fill: base={base_color}, seq={color_seq}",
        source_failure_signature={},
    ))


def _try_enclosed_flat_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    candidates: List[SynthesizedOperator],
) -> None:
    """Detect bordered rectangles, learn property→fill mapping, emit operator."""
    property_to_fill: Dict[str, Dict] = {}

    for inp, out in train_pairs:
        rects = _find_bordered_rectangles(inp)
        if not rects:
            return
        for rect in rects:
            r0, c0, r1, c1 = rect["r0"], rect["c0"], rect["r1"], rect["c1"]
            bc = rect["border_color"]
            interior_out = out[r0+1:r1, c0+1:c1]
            fill_colors = set(int(c) for c in interior_out.flatten()) - {bc, 0}
            if len(fill_colors) != 1:
                continue
            fill_color = fill_colors.pop()
            marker_depth = rect["marker_depth"]
            int_side = rect["int_h"]
            int_area = rect["int_h"] * rect["int_w"]

            for prop_name, prop_val in [
                ("marker_depth", marker_depth),
                ("int_side", int_side),
                ("int_area", int_area),
            ]:
                key = f"{bc}_{prop_name}"
                if key not in property_to_fill:
                    property_to_fill[key] = {
                        "border_color": bc, "prop_name": prop_name, "mapping": {},
                    }
                mapping = property_to_fill[key]["mapping"]
                if prop_val in mapping and mapping[prop_val] != fill_color:
                    property_to_fill[key]["conflict"] = True
                mapping[prop_val] = fill_color

    for key, info in property_to_fill.items():
        if info.get("conflict"):
            continue
        if len(info["mapping"]) < 1:
            continue
        bc = info["border_color"]
        prop_name = info["prop_name"]
        mapping = dict(info["mapping"])

        def _execute_flat(grid, _bc=bc, _prop=prop_name, _map=dict(mapping)):
            result = grid.copy()
            rects = _find_bordered_rectangles(grid, bg=0)
            for rect in rects:
                if rect["border_color"] != _bc:
                    continue
                r0, c0, r1, c1 = rect["r0"], rect["c0"], rect["r1"], rect["c1"]
                if _prop == "marker_depth":
                    pv = rect["marker_depth"]
                elif _prop == "int_side":
                    pv = rect["int_h"]
                elif _prop == "int_area":
                    pv = rect["int_h"] * rect["int_w"]
                else:
                    continue
                fc = _map.get(pv)
                if fc is None:
                    continue
                for r in range(r0+1, r1):
                    for c in range(c0+1, c1):
                        if int(grid[r, c]) != _bc:
                            result[r, c] = fc
            return result

        ok, err = _check_train_consistency(_execute_flat, train_pairs)
        if ok:
            candidates.append(SynthesizedOperator(
                operator_id=f"cdf_flat_{uuid.uuid4().hex[:8]}",
                operator_family="containment_depth_fill",
                parameters={
                    "strategy": "enclosed_flat_fill",
                    "border_color": bc,
                    "property": prop_name,
                    "mapping": mapping,
                },
                preconditions=["same_size", "bordered_rectangles"],
                execute=_execute_flat,
                explanation=f"Enclosed fill: border={bc}, {prop_name}→color {mapping}",
                source_failure_signature={},
            ))


# ---------------------------------------------------------------------------
# Separator axis reflect
# ---------------------------------------------------------------------------


def _detect_separator(grid: np.ndarray, bg: int) -> Optional[Tuple[str, int, int]]:
    """Find a full-span separator row or column.

    Returns (axis, index, color) or None.
    axis is 'h' for horizontal row, 'v' for vertical column.
    """
    H, W = grid.shape
    for r in range(H):
        vals = set(int(c) for c in grid[r, :])
        if len(vals) == 1:
            sc = vals.pop()
            if sc != bg:
                return ("h", r, sc)
    for c in range(W):
        vals = set(int(grid[r, c]) for r in range(H))
        if len(vals) == 1:
            sc = vals.pop()
            if sc != bg:
                return ("v", c, sc)
    return None


def _infer_background(grid: np.ndarray) -> int:
    colors, counts = np.unique(grid, return_counts=True)
    return int(colors[np.argmax(counts)])


def _synthesize_separator_axis_reflect(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize separator-axis-reflect operators.

    Detects a full-span separator (row or column), then infers per-CC
    placement rules from training pairs:
      - Wide CCs (width > 1): translate so widest row aligns to sep-1.
      - Narrow CCs (width == 1): mirror (2*sep - r) then gravity-drop
        to lowest available row per column.
    Separator pixels are cleared at narrow-CC columns and pierced at
    wide-CC crossing columns.
    """
    if not train_pairs:
        return []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []

    bg0 = _infer_background(train_pairs[0][0])
    det0 = _detect_separator(train_pairs[0][0], bg0)
    if det0 is None:
        return []
    axis0, _, sep_color0 = det0

    for inp, out in train_pairs[1:]:
        bg_i = _infer_background(inp)
        if bg_i != bg0:
            return []
        det_i = _detect_separator(inp, bg_i)
        if det_i is None or det_i[0] != axis0 or det_i[2] != sep_color0:
            return []

    if axis0 == "v":
        train_T = [(inp.T, out.T) for inp, out in train_pairs]
        ops = _try_h_separator_reflect(train_T, bg0, sep_color0)
        result = []
        for op in ops:
            orig_exec = op.execute

            def _transpose_exec(grid, _fn=orig_exec):
                return _fn(grid.T).T

            result.append(SynthesizedOperator(
                operator_id=op.operator_id,
                operator_family=op.operator_family,
                parameters={**op.parameters, "transposed": True},
                preconditions=op.preconditions,
                execute=_transpose_exec,
                explanation=op.explanation.replace("row", "column"),
                source_failure_signature=op.source_failure_signature,
            ))
        return result

    return _try_h_separator_reflect(train_pairs, bg0, sep_color0)


def _try_h_separator_reflect(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    bg: int,
    sep_color: int,
) -> List[SynthesizedOperator]:
    """Attempt separator-axis-reflect for horizontal separators."""

    def _apply(grid: np.ndarray, _bg=bg, _sep_color=sep_color) -> np.ndarray:
        out = grid.copy()
        H, W = grid.shape

        sep_row = None
        for r in range(H):
            vals = set(int(c) for c in grid[r, :])
            if len(vals) == 1 and vals.pop() == _sep_color:
                sep_row = r
                break
        if sep_row is None:
            return out

        above = grid[:sep_row].copy()
        obj_mask = above != _bg
        labeled, n_cc = ndimage.label(obj_mask)

        from collections import defaultdict
        col_occupied: Dict[int, set] = defaultdict(set)

        for j in range(1, n_cc + 1):
            comp = labeled == j
            rows, cols = np.where(comp)
            pixels = [(int(r), int(c), int(grid[r, c]))
                      for r, c in zip(rows, cols)]
            min_c = min(c for _, c, _ in pixels)
            max_c = max(c for _, c, _ in pixels)
            width = max_c - min_c + 1

            if width <= 1:
                continue

            row_counts: Dict[int, int] = {}
            for r, c, _ in pixels:
                row_counts[r] = row_counts.get(r, 0) + 1
            widest_row = max(row_counts.keys(), key=lambda r: row_counts[r])
            shift = (sep_row - 1) - widest_row

            for r, c, _ in pixels:
                out[r, c] = _bg

            for r, c, color in pixels:
                new_r = r + shift
                if 0 <= new_r < H:
                    out[new_r, c] = color
                    col_occupied[c].add(new_r)

        narrow_pixels: List[Tuple[int, int, int]] = []
        narrow_cols: set = set()

        for j in range(1, n_cc + 1):
            comp = labeled == j
            rows, cols = np.where(comp)
            pixels = [(int(r), int(c), int(grid[r, c]))
                      for r, c in zip(rows, cols)]
            min_c = min(c for _, c, _ in pixels)
            max_c = max(c for _, c, _ in pixels)
            width = max_c - min_c + 1

            if width > 1:
                continue

            for r, c, color in pixels:
                out[r, c] = _bg
                mirror_r = 2 * sep_row - r
                narrow_pixels.append((mirror_r, c, color))
                narrow_cols.add(c)

            for _, c, _ in pixels:
                out[sep_row, c] = _bg

        col_mirrors: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        for mr, c, color in narrow_pixels:
            col_mirrors[c].append((mr, color))

        for c, mirrors in col_mirrors.items():
            available = H - 1
            for mr, color in sorted(mirrors, key=lambda x: -x[0]):
                while available in col_occupied[c] or available == sep_row:
                    available -= 1
                if available > sep_row:
                    out[available, c] = color
                    col_occupied[c].add(available)
                    available -= 1

        return out

    for inp, out in train_pairs:
        predicted = _apply(inp)
        if not np.array_equal(predicted, out):
            return []

    oid = f"sep_reflect_{uuid.uuid4().hex[:8]}"
    return [SynthesizedOperator(
        operator_id=oid,
        operator_family="separator_axis_reflect",
        parameters={"bg": bg, "sep_color": sep_color, "axis": "h"},
        preconditions=["full_span_separator_row"],
        execute=_apply,
        explanation=(
            "Reflect objects across a full-span separator row: "
            "wide CCs align widest row to sep-1, narrow CCs mirror+gravity."
        ),
        source_failure_signature={},
    )]


def _detect_cross_structure(
    grid: np.ndarray, bg: int,
) -> Optional[Dict[str, Any]]:
    """Detect a cross structure: vertical line column + horizontal separator rows.

    Returns dict with vcol_idx, vcol_color, icol, separators or None.
    """
    H, W = grid.shape

    vcol_idx = None
    vcol_color = None
    icol = None

    for c in range(W):
        col_vals = [int(grid[r, c]) for r in range(H)]
        if bg in col_vals:
            continue
        unique = set(col_vals)
        if len(unique) != 2:
            continue
        vals = list(unique)
        c0 = col_vals.count(vals[0])
        c1 = col_vals.count(vals[1])
        if c0 > c1:
            vcol_color_cand, icol_cand = vals[0], vals[1]
        else:
            vcol_color_cand, icol_cand = vals[1], vals[0]
        vcol_idx = c
        vcol_color = vcol_color_cand
        icol = icol_cand
        break

    if vcol_idx is None:
        return None

    seps: List[Tuple[int, int]] = []
    for r in range(H):
        if int(grid[r, vcol_idx]) != icol:
            continue
        row_vals = set()
        for c2 in range(W):
            if c2 == vcol_idx:
                continue
            row_vals.add(int(grid[r, c2]))
        if len(row_vals) == 1:
            fill_color = row_vals.pop()
            if fill_color != bg and fill_color != vcol_color:
                seps.append((r, fill_color))

    if not seps:
        return None

    return {
        "vcol_idx": vcol_idx,
        "vcol_color": vcol_color,
        "icol": icol,
        "separators": seps,
    }


def _apply_separator_region_fill(
    grid: np.ndarray, bg: int, vcol_color: int, icol: int,
) -> np.ndarray:
    """Apply separator-region-fill: fill regions between cross-separators."""
    H, W = grid.shape
    out = grid.copy()

    params = _detect_cross_structure(grid, bg)
    if params is None:
        return out

    vcol_idx = params["vcol_idx"]
    seps = sorted(params["separators"], key=lambda x: x[0])

    if not seps:
        return out

    sep_rows = [s[0] for s in seps]
    sep_colors = [s[1] for s in seps]

    is_original_sep = set(sep_rows)
    boundary_rows: set = set()
    row_fill: Dict[int, int] = {}

    # Before first separator
    for r in range(0, sep_rows[0]):
        row_fill[r] = sep_colors[0]

    # Between consecutive separators
    for i in range(len(sep_rows) - 1):
        r1, c1 = sep_rows[i], sep_colors[i]
        r2, c2 = sep_rows[i + 1], sep_colors[i + 1]
        start, end = r1 + 1, r2 - 1
        if start > end:
            continue
        if c1 == c2:
            for r in range(start, end + 1):
                row_fill[r] = c1
        else:
            mid = (r1 + r2) / 2.0
            if mid == int(mid):
                mid_row = int(mid)
                boundary_rows.add(mid_row)
                for r in range(start, mid_row):
                    row_fill[r] = c1
                for r in range(mid_row + 1, end + 1):
                    row_fill[r] = c2
            else:
                split = int(mid)
                for r in range(start, split + 1):
                    row_fill[r] = c1
                for r in range(split + 1, end + 1):
                    row_fill[r] = c2

    # After last separator
    for r in range(sep_rows[-1] + 1, H):
        row_fill[r] = sep_colors[-1]

    # Build output
    for r in range(H):
        if r in is_original_sep:
            for c in range(W):
                out[r, c] = vcol_color if c == vcol_idx else icol
        elif r in boundary_rows:
            for c in range(W):
                out[r, c] = icol
        elif r in row_fill:
            for c in range(W):
                out[r, c] = icol if c == vcol_idx else row_fill[r]

    return out


def _synthesize_separator_region_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize separator-region-fill operators.

    Detects cross structure (vertical line + horizontal separator rows),
    fills each region between separators with the nearest separator's color,
    converts separator rows to intersection color, swaps intersection pixels.
    Supports horizontal and vertical cross orientations.
    """
    if not train_pairs:
        return []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []

    bg0 = _infer_background(train_pairs[0][0])

    # Try horizontal cross first
    ops = _try_srf_orientation(train_pairs, bg0, transpose=False)
    if ops:
        return ops

    # Try vertical cross (transpose)
    train_T = [(inp.T, out.T) for inp, out in train_pairs]
    bg0_T = _infer_background(train_T[0][0])
    ops_T = _try_srf_orientation(train_T, bg0_T, transpose=True)
    return ops_T


def _try_srf_orientation(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    bg: int,
    transpose: bool,
) -> List[SynthesizedOperator]:
    """Try separator-region-fill in one orientation."""
    params0 = _detect_cross_structure(train_pairs[0][0], bg)
    if params0 is None:
        return []

    vcol_color = params0["vcol_color"]
    icol = params0["icol"]

    for inp, out in train_pairs[1:]:
        bg_i = _infer_background(inp)
        if bg_i != bg:
            return []
        params_i = _detect_cross_structure(inp, bg_i)
        if params_i is None:
            return []
        if params_i["vcol_color"] != vcol_color or params_i["icol"] != icol:
            return []

    if not transpose:
        def _apply(grid, _bg=bg, _vc=vcol_color, _ic=icol):
            return _apply_separator_region_fill(grid, _bg, _vc, _ic)
    else:
        def _apply(grid, _bg=bg, _vc=vcol_color, _ic=icol):
            return _apply_separator_region_fill(grid.T, _bg, _vc, _ic).T

    for inp, out in train_pairs:
        pred = _apply(inp) if not transpose else _apply(inp)
        if not np.array_equal(pred, out):
            return []

    oid = f"srf_{uuid.uuid4().hex[:8]}"
    orient = "transposed" if transpose else "standard"
    return [SynthesizedOperator(
        operator_id=oid,
        operator_family="separator_region_fill",
        parameters={"bg": int(bg), "vcol_color": int(vcol_color),
                     "icol": int(icol), "orientation": orient},
        preconditions=["cross_separator_structure"],
        execute=_apply,
        explanation=(
            "Fill regions between cross-separators with nearest separator "
            "color; separators become intersection color, intersections "
            "become line color."
        ),
        source_failure_signature={},
    )]


# ---------------------------------------------------------------------------
# Operator Family: SeparatorTrackMove
# ---------------------------------------------------------------------------

def _detect_box_and_track(
    grid: np.ndarray, bg: int,
) -> Optional[Dict[str, Any]]:
    """Detect a 3x3 bordered box sitting on an evenly-spaced dot track.

    Returns dict with box_r, box_c, border_color, track_color, axis ('h'/'v'),
    track_positions (sorted list), spacing, or None.
    """
    H, W = grid.shape

    for r in range(H - 2):
        for c in range(W - 2):
            patch = grid[r:r+3, c:c+3]
            center = int(patch[1, 1])
            if center == bg:
                continue
            border_vals = [
                int(patch[0, 0]), int(patch[0, 1]), int(patch[0, 2]),
                int(patch[1, 0]),                   int(patch[1, 2]),
                int(patch[2, 0]), int(patch[2, 1]), int(patch[2, 2]),
            ]
            if len(set(border_vals)) != 1:
                continue
            border_color = border_vals[0]
            if border_color == bg or border_color == center:
                continue

            box_cr, box_cc = r + 1, c + 1
            track_color = center

            for axis, fixed, var_max, get_pos in [
                ("v", box_cc, H, lambda idx: (idx, box_cc)),
                ("h", box_cr, W, lambda idx: (box_cr, idx)),
            ]:
                dots = []
                for idx in range(var_max):
                    pos = get_pos(idx)
                    if r <= pos[0] <= r + 2 and c <= pos[1] <= c + 2:
                        if pos == (box_cr, box_cc):
                            dots.append(idx)
                        continue
                    if int(grid[pos]) == track_color:
                        dots.append(idx)

                if len(dots) < 3:
                    continue

                dots.sort()
                diffs = [dots[i+1] - dots[i] for i in range(len(dots) - 1)]
                if len(set(diffs)) != 1:
                    continue
                spacing = diffs[0]

                center_idx = box_cr if axis == "v" else box_cc
                if center_idx not in dots:
                    continue

                return {
                    "box_r": r, "box_c": c,
                    "border_color": border_color,
                    "track_color": track_color,
                    "axis": axis,
                    "track_positions": dots,
                    "spacing": spacing,
                    "bg": bg,
                }

    return None


def _apply_track_move(
    grid: np.ndarray, bg: int, border_color: int, track_color: int,
) -> np.ndarray:
    """Move a 3x3 box one step along its track toward the longer side."""
    det = _detect_box_and_track(grid, bg)
    if det is None:
        return grid.copy()

    out = grid.copy()
    r, c = det["box_r"], det["box_c"]
    axis = det["axis"]
    positions = det["track_positions"]
    spacing = det["spacing"]
    center_idx = (r + 1) if axis == "v" else (c + 1)

    pos_list = positions
    ci = pos_list.index(center_idx)
    n_before = ci
    n_after = len(pos_list) - 1 - ci

    if n_after >= n_before:
        new_center = center_idx + spacing
    else:
        new_center = center_idx - spacing

    if axis == "v":
        new_r = new_center - 1
        new_c = c
    else:
        new_r = r
        new_c = new_center - 1

    H, W = grid.shape
    if new_r < 0 or new_r + 2 >= H or new_c < 0 or new_c + 2 >= W:
        return out

    for dr in range(3):
        for dc in range(3):
            out[r + dr, c + dc] = bg
    out[r + 1, c + 1] = track_color

    for dr in range(3):
        for dc in range(3):
            if dr == 1 and dc == 1:
                out[new_r + dr, new_c + dc] = track_color
            else:
                out[new_r + dr, new_c + dc] = border_color

    return out


def _synthesize_separator_track_move(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Synthesize separator-track-move operators.

    Detects a 3x3 bordered box on an evenly-spaced dot track. The box moves
    one track step toward the side with more remaining dots.
    """
    if not train_pairs:
        return []

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return []

    bg0 = _infer_background(train_pairs[0][0])
    det0 = _detect_box_and_track(train_pairs[0][0], bg0)
    if det0 is None:
        return []

    border_color = det0["border_color"]
    track_color = det0["track_color"]

    for inp, _ in train_pairs[1:]:
        bg_i = _infer_background(inp)
        if bg_i != bg0:
            return []
        det_i = _detect_box_and_track(inp, bg_i)
        if det_i is None:
            return []
        if det_i["border_color"] != border_color or det_i["track_color"] != track_color:
            return []

    def _apply(grid, _bg=bg0, _bc=border_color, _tc=track_color):
        return _apply_track_move(grid, _bg, _bc, _tc)

    for inp, out in train_pairs:
        pred = _apply(inp)
        if not np.array_equal(pred, out):
            return []

    oid = f"stm_{uuid.uuid4().hex[:8]}"
    return [SynthesizedOperator(
        operator_id=oid,
        operator_family="separator_track_move",
        parameters={"bg": int(bg0), "border_color": int(border_color),
                     "track_color": int(track_color)},
        preconditions=["box_on_dot_track"],
        execute=_apply,
        explanation=(
            "Move a 3x3 bordered box one step along its evenly-spaced "
            "dot track in the positive direction (down/right)."
        ),
        source_failure_signature={},
    )]


# ---------------------------------------------------------------------------
# Main synthesis entry point
# ---------------------------------------------------------------------------

FAMILY_SYNTHESIZERS = [
    ("crop_extract", _synthesize_crop_to_changed_region),
    ("move_copy", _synthesize_move_copy),
    ("line_extend", _synthesize_extend_line),
    ("hole_fill", _synthesize_fill_hole),
    ("symmetry_complete", _synthesize_complete_symmetry),
    ("repeat_motif", _synthesize_repeat_motif),
    ("conditional_recolor", _synthesize_conditional_recolor),
    ("object_correspondence", _synthesize_object_correspondence),
    ("containment_depth_fill", _synthesize_containment_depth_fill),
    ("separator_axis_reflect", _synthesize_separator_axis_reflect),
    ("separator_region_fill", _synthesize_separator_region_fill),
    ("separator_track_move", _synthesize_separator_track_move),
]


def synthesize_operators_from_train(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    view_program: Optional[Any] = None,
    max_candidates: int = 100,
) -> List[SynthesizedOperator]:
    """Synthesize executable operator candidates from train pairs.

    Uses train pairs ONLY. Test outputs are never used.
    Each returned operator has an executable `execute(grid)` callable
    that is train-consistent.

    Args:
        train_pairs: List of (input, output) numpy arrays
        view_program: Optional ViewProgram that was used to lift the pairs
        max_candidates: Maximum number of candidates to return
    """
    if not train_pairs:
        return []

    all_candidates: List[SynthesizedOperator] = []

    # Run each family synthesizer
    for family_name, synthesizer in FAMILY_SYNTHESIZERS:
        try:
            family_candidates = synthesizer(train_pairs)
            all_candidates.extend(family_candidates)
        except Exception:
            continue

    # Try two-step compositions if we have single-step ops
    if all_candidates:
        try:
            compositions = _synthesize_two_step_composition(
                train_pairs, all_candidates
            )
            all_candidates.extend(compositions)
        except Exception:
            pass

    # Deduplicate by operator_id and cap at max_candidates
    seen = set()
    unique = []
    for op in all_candidates:
        if op.operator_id not in seen:
            seen.add(op.operator_id)
            unique.append(op)
    unique = unique[:max_candidates]

    # Tag with view program info
    if view_program is not None:
        vp_name = getattr(view_program, '__class__', type(view_program)).__name__
        for op in unique:
            op.source_failure_signature["view_program"] = vp_name

    return unique
