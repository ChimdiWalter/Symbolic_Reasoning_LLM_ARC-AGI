"""Grid Decomposition — multi-strategy grid subdivision for ARC tasks.

Detects implicit grid structure: equal subdivisions, repeated patterns,
color-based regions. Applies binary operations (AND/OR/XOR/overlay) across
subgrids to generate candidate solutions.
"""
from __future__ import annotations

import uuid
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.operator_genesis import SynthesizedOperator


@dataclass
class SubgridDecomposition:
    n_rows: int
    n_cols: int
    cell_height: int
    cell_width: int
    subgrids: List[np.ndarray]


def detect_equal_subdivision(grid: np.ndarray) -> List[SubgridDecomposition]:
    """Try dividing grid into equal NxM subgrids."""
    H, W = grid.shape
    results = []
    for nr in range(2, min(H + 1, 8)):
        for nc in range(2, min(W + 1, 8)):
            if H % nr != 0 or W % nc != 0:
                continue
            ch, cw = H // nr, W // nc
            if ch < 1 or cw < 1:
                continue
            subgrids = []
            for ri in range(nr):
                for ci in range(nc):
                    sg = grid[ri*ch:(ri+1)*ch, ci*cw:(ci+1)*cw].copy()
                    subgrids.append(sg)
            results.append(SubgridDecomposition(nr, nc, ch, cw, subgrids))
    return results


def detect_separator_subdivision(grid: np.ndarray, bg: int = 0) -> List[SubgridDecomposition]:
    """Detect grid divided by single-color separator lines."""
    H, W = grid.shape
    results = []

    for sep_color in range(10):
        # Find full horizontal lines of sep_color
        h_lines = []
        for r in range(H):
            if all(int(grid[r, c]) == sep_color for c in range(W)):
                h_lines.append(r)

        # Find full vertical lines of sep_color
        v_lines = []
        for c in range(W):
            if all(int(grid[r, c]) == sep_color for r in range(H)):
                v_lines.append(c)

        if not h_lines and not v_lines:
            continue

        # Build row boundaries
        row_bounds = [0]
        for r in h_lines:
            if r > row_bounds[-1]:
                row_bounds.append(r)
            row_bounds.append(r + 1)
        row_bounds.append(H)

        # Build col boundaries
        col_bounds = [0]
        for c in v_lines:
            if c > col_bounds[-1]:
                col_bounds.append(c)
            col_bounds.append(c + 1)
        col_bounds.append(W)

        # Extract subgrids
        row_ranges = [(row_bounds[i], row_bounds[i+1])
                      for i in range(0, len(row_bounds)-1, 2)
                      if row_bounds[i] < row_bounds[i+1]]
        col_ranges = [(col_bounds[i], col_bounds[i+1])
                      for i in range(0, len(col_bounds)-1, 2)
                      if col_bounds[i] < col_bounds[i+1]]

        if len(row_ranges) < 2 and len(col_ranges) < 2:
            continue

        subgrids = []
        shapes = set()
        for r0, r1 in row_ranges:
            for c0, c1 in col_ranges:
                sg = grid[r0:r1, c0:c1].copy()
                subgrids.append(sg)
                shapes.add(sg.shape)

        if len(shapes) == 1 and len(subgrids) >= 2:
            sh = subgrids[0].shape
            results.append(SubgridDecomposition(
                len(row_ranges), len(col_ranges),
                sh[0], sh[1], subgrids))

    return results


def apply_subgrid_operation(subgrids: List[np.ndarray], op_name: str,
                            bg: int = 0) -> Optional[np.ndarray]:
    """Apply a binary/n-ary operation across subgrids."""
    if not subgrids or len(subgrids) < 2:
        return None
    shape = subgrids[0].shape
    if not all(sg.shape == shape for sg in subgrids):
        return None

    if op_name == "and":
        result = subgrids[0].copy()
        for sg in subgrids[1:]:
            result[result != sg] = bg
        return result

    elif op_name == "or":
        result = np.full(shape, bg, dtype=subgrids[0].dtype)
        for sg in subgrids:
            mask = sg != bg
            result[mask] = sg[mask]
        return result

    elif op_name == "xor":
        counts = np.zeros(shape, dtype=int)
        vals = np.zeros(shape, dtype=subgrids[0].dtype)
        for sg in subgrids:
            mask = sg != bg
            counts[mask] += 1
            vals[mask] = sg[mask]
        result = np.full(shape, bg, dtype=subgrids[0].dtype)
        result[counts == 1] = vals[counts == 1]
        return result

    elif op_name == "overlay":
        result = subgrids[0].copy()
        for sg in subgrids[1:]:
            mask = sg != bg
            result[mask] = sg[mask]
        return result

    elif op_name == "majority":
        result = np.zeros(shape, dtype=subgrids[0].dtype)
        H, W = shape
        for r in range(H):
            for c in range(W):
                vals = [int(sg[r, c]) for sg in subgrids if sg[r, c] != bg]
                if vals:
                    result[r, c] = Counter(vals).most_common(1)[0][0]
        return result

    elif op_name == "diff":
        if len(subgrids) != 2:
            return None
        a, b = subgrids[0], subgrids[1]
        result = np.full(shape, bg, dtype=a.dtype)
        diff_mask = a != b
        result[diff_mask] = a[diff_mask]
        return result

    return None


def solve_by_decomposition(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 15.0,
) -> List[SynthesizedOperator]:
    """Main entry: decompose inputs, try operations, verify."""
    results = []
    start = time.time()

    same_shape_io = all(inp.shape == out.shape for inp, out in train_pairs)

    # Try equal subdivision
    for inp0, out0 in train_pairs[:1]:
        decomps = detect_equal_subdivision(inp0)
        decomps.extend(detect_separator_subdivision(inp0))

        for decomp in decomps:
            if time.time() - start > timeout_seconds:
                break

            # Operation on subgrids → output
            for op_name in ["and", "or", "xor", "overlay", "majority", "diff"]:
                if time.time() - start > timeout_seconds:
                    break

                result = apply_subgrid_operation(decomp.subgrids, op_name)
                if result is None:
                    continue

                if np.array_equal(result, out0):
                    def make_decomp_op(nr, nc, op):
                        def fn(grid, _nr=nr, _nc=nc, _op=op):
                            H, W = grid.shape
                            if H % _nr != 0 or W % _nc != 0:
                                return grid
                            ch, cw = H // _nr, W // _nc
                            sgs = []
                            for ri in range(_nr):
                                for ci in range(_nc):
                                    sgs.append(grid[ri*ch:(ri+1)*ch, ci*cw:(ci+1)*cw].copy())
                            return apply_subgrid_operation(sgs, _op) or grid
                        return fn
                    fn = make_decomp_op(decomp.n_rows, decomp.n_cols, op_name)
                    if _verify(fn, train_pairs):
                        results.append(_make_op(
                            f"decomp_{decomp.n_rows}x{decomp.n_cols}_{op_name}",
                            f"grid_decomp_{op_name}",
                            fn,
                            f"Decompose {decomp.n_rows}x{decomp.n_cols}, apply {op_name}",
                        ))
                        return results

            # Selection: output is one specific subgrid
            if not same_shape_io:
                for idx, sg in enumerate(decomp.subgrids):
                    if sg.shape == out0.shape and np.array_equal(sg, out0):
                        ri, ci = idx // decomp.n_cols, idx % decomp.n_cols

                        def make_select(nr, nc, r_idx, c_idx):
                            def fn(grid, _nr=nr, _nc=nc, _ri=r_idx, _ci=c_idx):
                                H, W = grid.shape
                                if H % _nr != 0 or W % _nc != 0:
                                    return grid
                                ch, cw = H // _nr, W // _nc
                                return grid[_ri*ch:(_ri+1)*ch, _ci*cw:(_ci+1)*cw].copy()
                            return fn
                        fn = make_select(decomp.n_rows, decomp.n_cols, ri, ci)
                        if _verify(fn, train_pairs):
                            results.append(_make_op(
                                f"select_{ri}_{ci}",
                                "grid_subgrid_select",
                                fn,
                                f"Select subgrid ({ri},{ci}) from {decomp.n_rows}x{decomp.n_cols}",
                            ))
                            return results

    # Tiling detection: output = input tiled NxM
    if not same_shape_io:
        for inp, out in train_pairs[:1]:
            ih, iw = inp.shape
            oh, ow = out.shape
            if oh % ih == 0 and ow % iw == 0:
                nr, nc = oh // ih, ow // iw
                tiled = np.tile(inp, (nr, nc))
                if np.array_equal(tiled, out):
                    def make_tile(r_rep, c_rep):
                        def fn(grid, _rr=r_rep, _cr=c_rep):
                            return np.tile(grid, (_rr, _cr))
                        return fn
                    fn = make_tile(nr, nc)
                    if _verify(fn, train_pairs):
                        results.append(_make_op(
                            f"tile_{nr}x{nc}", "tile_grid", fn,
                            f"Tile input {nr}x{nc}",
                        ))
                        return results

    return results


def _make_op(name, family, fn, explanation):
    return SynthesizedOperator(
        operator_id=f"decomp_{name}_{uuid.uuid4().hex[:8]}",
        operator_family=family,
        parameters={},
        preconditions=[],
        execute=fn,
        explanation=f"[Decomp] {explanation}",
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
