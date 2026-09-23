"""Inverse Reasoning — bidirectional program search.

Instead of only searching forward (input → transforms → check output),
also reasons backward: what input structure would produce this output?
Doubles effective search depth without exponential cost.
"""
from __future__ import annotations

import uuid
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.operator_genesis import SynthesizedOperator


# ===================================================================
# Transform inversion
# ===================================================================

def _invert_transform(grid: np.ndarray, name: str) -> Optional[np.ndarray]:
    """Given an output grid and a transform name, produce the pre-image."""
    try:
        if name == "reflect_h":
            return np.fliplr(grid)
        elif name == "reflect_v":
            return np.flipud(grid)
        elif name == "rotate_90":
            return np.rot90(grid, -1)
        elif name == "rotate_180":
            return np.rot90(grid, -2)
        elif name == "rotate_270":
            return np.rot90(grid, -3)
        elif name == "transpose":
            return grid.T.copy()
    except Exception:
        pass
    return None


# Forward transforms (cheap, used as step-1 or step-2)
def _forward_transforms():
    """Generate (name, fn) pairs for simple forward transforms."""
    transforms = [
        ("identity", lambda g: g.copy()),
        ("reflect_h", lambda g: np.fliplr(g)),
        ("reflect_v", lambda g: np.flipud(g)),
        ("rotate_90", lambda g: np.rot90(g, 1)),
        ("rotate_180", lambda g: np.rot90(g, 2)),
        ("rotate_270", lambda g: np.rot90(g, 3)),
        ("transpose", lambda g: g.T.copy()),
    ]

    # Color swaps for colors 1-9
    for a in range(1, 10):
        for b in range(a + 1, 10):
            def make_swap(x, y):
                def fn(grid, _x=x, _y=y):
                    out = grid.copy()
                    out[grid == _x] = _y
                    out[grid == _y] = _x
                    return out
                return fn
            transforms.append((f"swap_{a}_{b}", make_swap(a, b)))

    # Color remaps
    for src in range(1, 10):
        for tgt in range(10):
            if src == tgt:
                continue
            def make_remap(s, t):
                def fn(grid, _s=s, _t=t):
                    out = grid.copy()
                    out[grid == _s] = _t
                    return out
                return fn
            transforms.append((f"remap_{src}to{tgt}", make_remap(src, tgt)))

    # Gravity
    for direction in ["down", "up", "left", "right"]:
        def make_gravity(d):
            def fn(grid, _d=d):
                H, W = grid.shape
                out = np.zeros_like(grid)
                if _d == "down":
                    for c in range(W):
                        vals = [int(grid[r, c]) for r in range(H) if grid[r, c] != 0]
                        for i, v in enumerate(vals):
                            out[H - len(vals) + i, c] = v
                elif _d == "up":
                    for c in range(W):
                        vals = [int(grid[r, c]) for r in range(H) if grid[r, c] != 0]
                        for i, v in enumerate(vals):
                            out[i, c] = v
                elif _d == "left":
                    for r in range(H):
                        vals = [int(grid[r, c]) for c in range(W) if grid[r, c] != 0]
                        for i, v in enumerate(vals):
                            out[r, i] = v
                elif _d == "right":
                    for r in range(H):
                        vals = [int(grid[r, c]) for c in range(W) if grid[r, c] != 0]
                        for i, v in enumerate(vals):
                            out[r, W - len(vals) + i] = v
                return out
            return fn
        transforms.append((f"gravity_{direction}", make_gravity(direction)))

    return transforms


# ===================================================================
# Backward search
# ===================================================================

def _search_backward(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Invert output, check if input can reach the inverted intermediate."""
    results = []
    start = time.time()

    invertible = ["reflect_h", "reflect_v", "rotate_90", "rotate_180",
                  "rotate_270", "transpose"]
    forward = _forward_transforms()

    for inv_name in invertible:
        if time.time() - start > timeout:
            break

        # Check if inverting the output gives us something reachable from input
        valid_for_all = True
        intermediates = []
        for inp, out in train_pairs:
            candidate = _invert_transform(out, inv_name)
            if candidate is None or candidate.shape != inp.shape:
                valid_for_all = False
                break
            intermediates.append(candidate)

        if not valid_for_all:
            continue

        # Now find a forward transform from input → intermediate
        for fwd_name, fwd_fn in forward:
            if time.time() - start > timeout:
                break

            matches = True
            for inp, intermediate in zip([p[0] for p in train_pairs], intermediates):
                try:
                    fwd_result = fwd_fn(inp)
                    if fwd_result.shape != intermediate.shape or \
                       not np.array_equal(fwd_result, intermediate):
                        matches = False
                        break
                except Exception:
                    matches = False
                    break

            if matches:
                # Solution: fwd_fn → inv_name's forward (which reverses the inversion)
                def make_composed(fwd, inv):
                    def fn(grid, _fwd=fwd, _inv=inv):
                        mid = _fwd(grid)
                        if _inv == "reflect_h":
                            return np.fliplr(mid)
                        elif _inv == "reflect_v":
                            return np.flipud(mid)
                        elif _inv == "rotate_90":
                            return np.rot90(mid, 1)
                        elif _inv == "rotate_180":
                            return np.rot90(mid, 2)
                        elif _inv == "rotate_270":
                            return np.rot90(mid, 3)
                        elif _inv == "transpose":
                            return mid.T.copy()
                        return mid
                    return fn

                fn = make_composed(fwd_fn, inv_name)
                if _verify(fn, train_pairs):
                    results.append(SynthesizedOperator(
                        operator_id=f"inverse_{fwd_name}_{inv_name}_{uuid.uuid4().hex[:8]}",
                        operator_family=f"inverse_{fwd_name}_then_{inv_name}",
                        parameters={"forward": fwd_name, "inverse_of": inv_name},
                        preconditions=[],
                        execute=fn,
                        explanation=f"[Inverse] {fwd_name} → {inv_name}",
                        source_failure_signature={},
                    ))
                    return results

    return results


# ===================================================================
# Meet-in-the-middle search
# ===================================================================

def _search_meet_in_middle(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Apply forward from input and backward from output, find matching intermediate."""
    results = []
    start = time.time()

    if not train_pairs:
        return results

    forward = _forward_transforms()
    invertible = ["reflect_h", "reflect_v", "rotate_90", "rotate_180",
                  "rotate_270", "transpose"]

    inp0, out0 = train_pairs[0]

    # Build backward candidates from first output
    backward_cache = {}
    for inv_name in invertible:
        candidate = _invert_transform(out0, inv_name)
        if candidate is not None:
            key = candidate.tobytes()
            backward_cache[key] = inv_name

    # Try forward transforms, check if result matches any backward candidate
    for fwd_name, fwd_fn in forward:
        if time.time() - start > timeout:
            break
        try:
            fwd_result = fwd_fn(inp0)
            key = fwd_result.tobytes()
            if key in backward_cache:
                inv_name = backward_cache[key]
                # Verify on ALL training pairs
                def make_composed(fwd, inv):
                    def fn(grid, _fwd=fwd, _inv=inv):
                        mid = _fwd(grid)
                        if _inv == "reflect_h":
                            return np.fliplr(mid)
                        elif _inv == "reflect_v":
                            return np.flipud(mid)
                        elif _inv == "rotate_90":
                            return np.rot90(mid, 1)
                        elif _inv == "rotate_180":
                            return np.rot90(mid, 2)
                        elif _inv == "rotate_270":
                            return np.rot90(mid, 3)
                        elif _inv == "transpose":
                            return mid.T.copy()
                        return mid
                    return fn

                fn = make_composed(fwd_fn, inv_name)
                if _verify(fn, train_pairs):
                    results.append(SynthesizedOperator(
                        operator_id=f"mitm_{fwd_name}_{inv_name}_{uuid.uuid4().hex[:8]}",
                        operator_family=f"meet_middle_{fwd_name}_{inv_name}",
                        parameters={},
                        preconditions=[],
                        execute=fn,
                        explanation=f"[Meet-in-middle] {fwd_name} → {inv_name}",
                        source_failure_signature={},
                    ))
                    return results
        except Exception:
            continue

    return results


# ===================================================================
# Main entry point
# ===================================================================

def search_bidirectional(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 15.0,
) -> List[SynthesizedOperator]:
    """Bidirectional program search: forward, backward, and meet-in-middle."""
    start = time.time()
    results = []

    # Meet-in-middle first (fastest for 2-step compositions)
    remaining = timeout_seconds * 0.4
    mitm = _search_meet_in_middle(train_pairs, remaining)
    if mitm:
        return mitm

    # Backward search
    remaining = min(timeout_seconds * 0.6, timeout_seconds - (time.time() - start))
    if remaining > 0:
        backward = _search_backward(train_pairs, remaining)
        if backward:
            return backward

    return results


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
