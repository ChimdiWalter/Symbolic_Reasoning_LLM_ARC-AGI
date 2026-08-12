"""Output Shape Predictor — handles tasks where input/output shapes differ.

~35-40% of unsolved ARC tasks have different I/O shapes. This module predicts
the output shape and constructs candidate output grids.
"""
from __future__ import annotations

import uuid
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


@dataclass
class ShapePrediction:
    height: int
    width: int
    strategy: str
    confidence: float


def predict_output_shape(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[ShapePrediction]:
    """Predict output shape from training pair patterns."""
    predictions = []

    out_shapes = [out.shape for _, out in train_pairs]
    inp_shapes = [inp.shape for inp, _ in train_pairs]

    # Constant: all outputs same size
    if len(set(out_shapes)) == 1:
        h, w = out_shapes[0]
        predictions.append(ShapePrediction(h, w, "constant", 1.0))

    # Scale up: output = input * factor
    for factor in [2, 3, 4, 5]:
        if all(out.shape[0] == inp.shape[0] * factor and
               out.shape[1] == inp.shape[1] * factor
               for inp, out in train_pairs):
            h = train_pairs[0][0].shape[0] * factor
            w = train_pairs[0][0].shape[1] * factor
            predictions.append(ShapePrediction(h, w, f"scale_up_{factor}", 0.95))

    # Scale down: output = input / factor
    for factor in [2, 3, 4, 5]:
        if all(inp.shape[0] == out.shape[0] * factor and
               inp.shape[1] == out.shape[1] * factor
               for inp, out in train_pairs):
            h = train_pairs[0][0].shape[0] // factor
            w = train_pairs[0][0].shape[1] // factor
            predictions.append(ShapePrediction(h, w, f"scale_down_{factor}", 0.95))

    # Subgrid: output dimensions divide input
    for inp, out in train_pairs[:1]:
        ih, iw = inp.shape
        oh, ow = out.shape
        if ih % oh == 0 and iw % ow == 0:
            predictions.append(ShapePrediction(oh, ow, "subgrid", 0.8))

    # Transpose dims
    if all(out.shape == (inp.shape[1], inp.shape[0]) for inp, out in train_pairs):
        h, w = train_pairs[0][0].shape[1], train_pairs[0][0].shape[0]
        predictions.append(ShapePrediction(h, w, "transpose_dims", 0.9))

    # Crop to content: output is bounding box of non-bg
    crop_shapes = []
    for inp, out in train_pairs:
        nz = np.argwhere(inp != 0)
        if len(nz) > 0:
            r0, c0 = nz.min(axis=0)
            r1, c1 = nz.max(axis=0)
            crop_shapes.append((r1 - r0 + 1, c1 - c0 + 1))
    if crop_shapes and all(cs == out.shape for cs, (_, out) in zip(crop_shapes, train_pairs)):
        h, w = crop_shapes[0]
        predictions.append(ShapePrediction(h, w, "crop_to_content", 0.9))

    # Max object shape
    obj_shapes = []
    for inp, out in train_pairs:
        labeled, n = ndlabel(inp != 0)
        if n > 0:
            max_area = 0
            max_shape = None
            for cid in range(1, n + 1):
                mask = labeled == cid
                rows, cols = np.where(mask)
                area = len(rows)
                if area > max_area:
                    max_area = area
                    h = rows.max() - rows.min() + 1
                    w = cols.max() - cols.min() + 1
                    max_shape = (h, w)
            if max_shape:
                obj_shapes.append(max_shape)
    if obj_shapes and all(os == out.shape for os, (_, out) in zip(obj_shapes, train_pairs)):
        h, w = obj_shapes[0]
        predictions.append(ShapePrediction(h, w, "max_object_shape", 0.85))

    # Count-based: output height = number of objects
    for inp, out in train_pairs[:1]:
        labeled, n_objects = ndlabel(inp != 0)
        n_colors = len(set(int(v) for v in inp.flat) - {0})
        oh, ow = out.shape
        if oh == n_objects or ow == n_objects:
            predictions.append(ShapePrediction(oh, ow, "count_objects", 0.6))
        if oh == n_colors or ow == n_colors:
            predictions.append(ShapePrediction(oh, ow, "count_colors", 0.6))

    return predictions


def solve_different_shape_task(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 10.0,
) -> List[SynthesizedOperator]:
    """Main entry: predict shape, construct candidates, verify."""
    results = []
    start = time.time()

    same_shape = all(inp.shape == out.shape for inp, out in train_pairs)
    if same_shape:
        return results

    predictions = predict_output_shape(train_pairs)
    if not predictions:
        return results

    # Strategy: crop to content
    def make_crop_to_content():
        def fn(grid):
            nz = np.argwhere(grid != 0)
            if len(nz) == 0:
                return grid
            r0, c0 = nz.min(axis=0)
            r1, c1 = nz.max(axis=0)
            return grid[r0:r1+1, c0:c1+1].copy()
        return fn

    fn = make_crop_to_content()
    if _verify(fn, train_pairs):
        results.append(_make_op("crop_content", "crop_to_content", fn,
                                "Crop to bounding box of non-bg content"))
        return results

    # Strategy: crop to specific color
    for color in range(1, 10):
        def make_crop_color(c):
            def fn(grid, _c=c):
                nz = np.argwhere(grid == _c)
                if len(nz) == 0:
                    return grid
                r0, c0 = nz.min(axis=0)
                r1, c1 = nz.max(axis=0)
                return grid[r0:r1+1, c0:c1+1].copy()
            return fn
        fn = make_crop_color(color)
        if _verify(fn, train_pairs):
            results.append(_make_op(f"crop_color_{color}", "crop_to_color", fn,
                                    f"Crop to bbox of color {color}"))
            return results

    # Strategy: extract largest object
    def make_extract_largest():
        def fn(grid):
            labeled, n = ndlabel(grid != 0)
            if n == 0:
                return grid
            max_area = 0
            max_id = 1
            for cid in range(1, n + 1):
                area = int((labeled == cid).sum())
                if area > max_area:
                    max_area = area
                    max_id = cid
            mask = labeled == max_id
            rows, cols = np.where(mask)
            r0, r1 = rows.min(), rows.max()
            c0, c1 = cols.min(), cols.max()
            return grid[r0:r1+1, c0:c1+1].copy()
        return fn

    fn = make_extract_largest()
    if _verify(fn, train_pairs):
        results.append(_make_op("extract_largest", "extract_largest_object", fn,
                                "Extract largest object's bbox"))
        return results

    # Strategy: extract smallest object
    def make_extract_smallest():
        def fn(grid):
            labeled, n = ndlabel(grid != 0)
            if n == 0:
                return grid
            min_area = float('inf')
            min_id = 1
            for cid in range(1, n + 1):
                area = int((labeled == cid).sum())
                if 0 < area < min_area:
                    min_area = area
                    min_id = cid
            mask = labeled == min_id
            rows, cols = np.where(mask)
            r0, r1 = rows.min(), rows.max()
            c0, c1 = cols.min(), cols.max()
            return grid[r0:r1+1, c0:c1+1].copy()
        return fn

    fn = make_extract_smallest()
    if _verify(fn, train_pairs):
        results.append(_make_op("extract_smallest", "extract_smallest_object", fn,
                                "Extract smallest object's bbox"))
        return results

    # Strategy: downscale by factor
    for factor in [2, 3, 4, 5]:
        if time.time() - start > timeout_seconds:
            break
        # Mode: take every Nth pixel
        def make_downsample(f):
            def fn(grid, _f=f):
                return grid[::_f, ::_f].copy()
            return fn
        fn = make_downsample(factor)
        if _verify(fn, train_pairs):
            results.append(_make_op(f"downsample_{factor}", f"downsample_{factor}", fn,
                                    f"Downsample by {factor}"))
            return results

        # Mode: majority vote in each block
        def make_blockmode(f):
            def fn(grid, _f=f):
                H, W = grid.shape
                oh, ow = H // _f, W // _f
                out = np.zeros((oh, ow), dtype=grid.dtype)
                for r in range(oh):
                    for c in range(ow):
                        block = grid[r*_f:(r+1)*_f, c*_f:(c+1)*_f]
                        vals = Counter(int(v) for v in block.flat)
                        out[r, c] = vals.most_common(1)[0][0]
                return out
            return fn
        fn = make_blockmode(factor)
        if _verify(fn, train_pairs):
            results.append(_make_op(f"blockmode_{factor}", f"block_mode_{factor}", fn,
                                    f"Block mode downsample by {factor}"))
            return results

    # Strategy: upscale by factor
    for factor in [2, 3, 4, 5]:
        if time.time() - start > timeout_seconds:
            break
        def make_upscale(f):
            def fn(grid, _f=f):
                return np.repeat(np.repeat(grid, _f, axis=0), _f, axis=1)
            return fn
        fn = make_upscale(factor)
        if _verify(fn, train_pairs):
            results.append(_make_op(f"upscale_{factor}", f"upscale_{factor}", fn,
                                    f"Upscale by {factor}"))
            return results

    # Strategy: select a subgrid
    for inp, out in train_pairs[:1]:
        oh, ow = out.shape
        ih, iw = inp.shape
        if ih % oh == 0 and iw % ow == 0:
            nr, nc = ih // oh, iw // ow
            for ri in range(nr):
                for ci in range(nc):
                    if time.time() - start > timeout_seconds:
                        break
                    def make_subgrid_select(r_idx, c_idx, sh, sw):
                        def fn(grid, _ri=r_idx, _ci=c_idx, _sh=sh, _sw=sw):
                            return grid[_ri*_sh:(_ri+1)*_sh, _ci*_sw:(_ci+1)*_sw].copy()
                        return fn
                    fn = make_subgrid_select(ri, ci, oh, ow)
                    if _verify(fn, train_pairs):
                        results.append(_make_op(f"subgrid_{ri}_{ci}",
                                                "subgrid_select", fn,
                                                f"Select subgrid ({ri},{ci})"))
                        return results

    # Strategy: transpose
    def make_transpose():
        def fn(grid):
            return grid.T.copy()
        return fn
    fn = make_transpose()
    if _verify(fn, train_pairs):
        results.append(_make_op("transpose", "transpose", fn, "Transpose grid"))
        return results

    return results


def _make_op(name, family, fn, explanation):
    return SynthesizedOperator(
        operator_id=f"shape_{name}_{uuid.uuid4().hex[:8]}",
        operator_family=family,
        parameters={},
        preconditions=[],
        execute=fn,
        explanation=f"[Shape] {explanation}",
        source_failure_signature={},
    )


def _verify(fn, train_pairs):
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True
