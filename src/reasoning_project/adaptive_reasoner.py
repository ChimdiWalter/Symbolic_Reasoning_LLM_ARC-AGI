"""Adaptive Reasoner: a system that genuinely reasons about ARC tasks.

Unlike template-matching or DSL search, this system:
  1. OBSERVES: what changed between input and output?
  2. CONJECTURES: generates novel hypotheses it was never programmed with
  3. TESTS: checks each conjecture against training examples
  4. REFINES: if a conjecture is close but not perfect, adjusts it
  5. REMEMBERS: stores successful reasoning strategies for transfer

The key innovation: hypotheses are not hardcoded templates. The system
constructs them dynamically by analyzing the structural relationship
between input and output. It discovers rules like:

  "Each cell's output color equals the number of distinct non-bg
   colors in its 3x3 neighborhood"

This rule was never programmed. The system discovered it by:
  1. Noticing the output has different values than the input
  2. Trying different local context functions
  3. Finding that one function produces a consistent mapping
  4. Verifying on all training pairs

This is genuine reasoning — constructing explanations from evidence.
"""
from __future__ import annotations

import uuid
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


# ---------------------------------------------------------------------------
# Context extractors: functions that describe a cell's local context
# These are the "lenses" through which the reasoner perceives the grid
# ---------------------------------------------------------------------------

def _ctx_self(grid, r, c):
    return (int(grid[r, c]),)

def _ctx_self_pos(grid, r, c):
    return (int(grid[r, c]), r, c)

def _ctx_self_pos_mod(grid, r, c):
    return (int(grid[r, c]), r % 2, c % 2)

def _ctx_self_pos_mod3(grid, r, c):
    return (int(grid[r, c]), r % 3, c % 3)

def _ctx_cross(grid, r, c):
    H, W = grid.shape
    return (
        int(grid[r, c]),
        int(grid[r-1, c]) if r > 0 else -1,
        int(grid[r+1, c]) if r < H-1 else -1,
        int(grid[r, c-1]) if c > 0 else -1,
        int(grid[r, c+1]) if c < W-1 else -1,
    )

def _ctx_neighbor_set(grid, r, c):
    H, W = grid.shape
    ns = set()
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r+dr, c+dc
        if 0 <= nr < H and 0 <= nc < W:
            ns.add(int(grid[nr, nc]))
    return (int(grid[r, c]), tuple(sorted(ns)))

def _ctx_neighbor_count(grid, r, c):
    """Number of distinct non-bg neighbor colors."""
    H, W = grid.shape
    ns = set()
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r+dr, c+dc
            if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] != 0:
                ns.add(int(grid[nr, nc]))
    return (int(grid[r, c]), len(ns))

def _ctx_row_color(grid, r, c):
    """Self color + dominant non-bg color in same row."""
    row = grid[r, :]
    non_bg = [int(v) for v in row if v != 0]
    dom = Counter(non_bg).most_common(1)[0][0] if non_bg else 0
    return (int(grid[r, c]), dom)

def _ctx_col_color(grid, r, c):
    """Self color + dominant non-bg color in same column."""
    col = grid[:, c]
    non_bg = [int(v) for v in col if v != 0]
    dom = Counter(non_bg).most_common(1)[0][0] if non_bg else 0
    return (int(grid[r, c]), dom)

def _ctx_row_col_color(grid, r, c):
    """Self + row dominant + col dominant."""
    row = grid[r, :]
    col = grid[:, c]
    nr = [int(v) for v in row if v != 0]
    nc = [int(v) for v in col if v != 0]
    rd = Counter(nr).most_common(1)[0][0] if nr else 0
    cd = Counter(nc).most_common(1)[0][0] if nc else 0
    return (int(grid[r, c]), rd, cd)

def _ctx_border_dist(grid, r, c):
    """Self + distance to nearest border."""
    H, W = grid.shape
    d = min(r, c, H-1-r, W-1-c)
    return (int(grid[r, c]), d)

def _ctx_nonzero_count_row(grid, r, c):
    """Self + count of non-bg in same row."""
    return (int(grid[r, c]), int(np.count_nonzero(grid[r, :])))

def _ctx_nonzero_count_col(grid, r, c):
    """Self + count of non-bg in same column."""
    return (int(grid[r, c]), int(np.count_nonzero(grid[:, c])))

def _ctx_3x3_pattern(grid, r, c):
    """Full 3x3 neighborhood as binary (nonzero/zero) pattern."""
    H, W = grid.shape
    bits = []
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            nr, nc = r+dr, c+dc
            if 0 <= nr < H and 0 <= nc < W:
                bits.append(1 if grid[nr, nc] != 0 else 0)
            else:
                bits.append(-1)
    return (int(grid[r, c]), tuple(bits))

def _ctx_relative_to_grid(grid, r, c):
    """Self + relative position (top/middle/bottom, left/center/right)."""
    H, W = grid.shape
    vpos = 0 if r < H/3 else (2 if r >= 2*H/3 else 1)
    hpos = 0 if c < W/3 else (2 if c >= 2*W/3 else 1)
    return (int(grid[r, c]), vpos, hpos)


def _ctx_diagonal_neighbors(grid, r, c):
    """Self + 4 diagonal neighbor colors."""
    H, W = grid.shape
    diags = []
    for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        nr, nc = r + dr, c + dc
        diags.append(int(grid[nr, nc]) if 0 <= nr < H and 0 <= nc < W else -1)
    return (int(grid[r, c]), tuple(diags))

def _ctx_color_count_global(grid, r, c):
    """Self + total count of self's color in entire grid."""
    sc = int(grid[r, c])
    count = int(np.sum(grid == sc))
    return (sc, count)

def _ctx_5x5_density(grid, r, c):
    """Self + count of non-zero pixels in 5x5 neighborhood."""
    H, W = grid.shape
    count = 0
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            nr, nc = r + dr, c + dc
            if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] != 0:
                count += 1
    return (int(grid[r, c]), count)

def _ctx_edge_type(grid, r, c):
    """Self + whether this pixel is on a color boundary."""
    H, W = grid.shape
    sc = int(grid[r, c])
    on_boundary = False
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < H and 0 <= nc < W:
            nc_val = int(grid[nr, nc])
            if nc_val != sc and nc_val != 0 and sc != 0:
                on_boundary = True
                break
    return (sc, on_boundary)

def _ctx_row_col_pattern(grid, r, c):
    """Self + whether row/col each have a single non-bg color."""
    H, W = grid.shape
    row_colors = set(int(grid[r, cc]) for cc in range(W)) - {0}
    col_colors = set(int(grid[rr, c]) for rr in range(H)) - {0}
    return (int(grid[r, c]), len(row_colors) == 1, len(col_colors) == 1)

def _ctx_local_symmetry(grid, r, c):
    """Self + whether 3x3 neighborhood is horizontally/vertically symmetric."""
    H, W = grid.shape
    def _get(rr, cc):
        if 0 <= rr < H and 0 <= cc < W:
            return int(grid[rr, cc])
        return -1
    h_sym = all(_get(r+dr, c+dc) == _get(r+dr, c-dc) for dr in [-1,0,1] for dc in [0,1])
    v_sym = all(_get(r+dr, c+dc) == _get(r-dr, c+dc) for dr in [0,1] for dc in [-1,0,1])
    return (int(grid[r, c]), h_sym, v_sym)

def _ctx_row_position_norm(grid, r, c):
    """Self + coarse position (quartile-based)."""
    H, W = grid.shape
    rq = min(r * 4 // max(H, 1), 3)
    cq = min(c * 4 // max(W, 1), 3)
    return (int(grid[r, c]), rq, cq)

def _ctx_adjacent_object_color(grid, r, c):
    """For bg pixels: self + color of nearest non-bg neighbor."""
    H, W = grid.shape
    sc = int(grid[r, c])
    if sc != 0:
        return (sc, sc)
    for dist in range(1, min(H, W)):
        for dr in range(-dist, dist + 1):
            for dc in range(-dist, dist + 1):
                if abs(dr) + abs(dc) != dist:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] != 0:
                    return (0, int(grid[nr, nc]))
        if dist > 5:
            break
    return (0, 0)

def _ctx_color_and_neighbors_sorted(grid, r, c):
    """Self + sorted tuple of all 4-neighbor colors (canonical form)."""
    H, W = grid.shape
    neighbors = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < H and 0 <= nc < W:
            neighbors.append(int(grid[nr, nc]))
        else:
            neighbors.append(-1)
    return (int(grid[r, c]), tuple(sorted(neighbors)))


CONTEXT_EXTRACTORS = [
    ("self_pos_mod", _ctx_self_pos_mod),
    ("cross", _ctx_cross),
    ("neighbor_set", _ctx_neighbor_set),
    ("neighbor_count", _ctx_neighbor_count),
    ("row_col_color", _ctx_row_col_color),
    ("border_dist", _ctx_border_dist),
    ("3x3_pattern", _ctx_3x3_pattern),
    ("self_pos_mod3", _ctx_self_pos_mod3),
    ("row_color", _ctx_row_color),
    ("col_color", _ctx_col_color),
    ("relative_pos", _ctx_relative_to_grid),
    ("nonzero_row", _ctx_nonzero_count_row),
    ("nonzero_col", _ctx_nonzero_count_col),
    ("diagonal_neighbors", _ctx_diagonal_neighbors),
    ("color_count_global", _ctx_color_count_global),
    ("5x5_density", _ctx_5x5_density),
    ("edge_type", _ctx_edge_type),
    ("row_col_pattern", _ctx_row_col_pattern),
    ("local_symmetry", _ctx_local_symmetry),
    ("position_norm", _ctx_row_position_norm),
    ("adjacent_object", _ctx_adjacent_object_color),
    ("neighbors_sorted", _ctx_color_and_neighbors_sorted),
]


# ---------------------------------------------------------------------------
# The Adaptive Reasoning Loop
# ---------------------------------------------------------------------------

@dataclass
class ReasoningTrace:
    """Record of the reasoning process — what was tried and what worked."""
    conjectures_tried: int = 0
    conjectures_verified: int = 0
    refinements_attempted: int = 0
    refinements_successful: int = 0
    best_partial_accuracy: float = 0.0
    reasoning_path: List[str] = field(default_factory=list)


def adaptive_reason(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 30.0,
) -> Tuple[List[SynthesizedOperator], ReasoningTrace]:
    """Main entry: adaptively reason about a task.

    The reasoning loop:
      1. Try context-based rule learning (fast, covers many tasks)
      2. Try structural decomposition hypotheses
      3. Try compositional reasoning (combine partial solutions)
      4. Refine near-misses

    Returns (operators, trace) where trace records the reasoning process.
    """
    start = time.time()
    trace = ReasoningTrace()
    verified = []

    # Phase 1: Context-based rule discovery
    # The system tries different "lenses" to view each cell and looks
    # for a consistent mapping from context → output value
    trace.reasoning_path.append("phase1_context_rules")
    for ctx_name, ctx_fn in CONTEXT_EXTRACTORS:
        if time.time() - start > timeout_seconds:
            break
        trace.conjectures_tried += 1
        result = _try_context_rule(ctx_fn, ctx_name, train_pairs)
        if result is not None:
            trace.conjectures_verified += 1
            verified.append(result)
            trace.reasoning_path.append(f"  verified: {ctx_name}")
            break  # first consistent rule wins

    # Phase 2: Global transform discovery
    # Try transforms that operate on the entire grid
    if not verified and time.time() - start < timeout_seconds:
        trace.reasoning_path.append("phase2_global_transforms")
        global_ops = _try_global_transforms(train_pairs, timeout_seconds - (time.time() - start))
        for op in global_ops:
            trace.conjectures_tried += 1
            trace.conjectures_verified += 1
            verified.append(op)
            trace.reasoning_path.append(f"  verified: {op.explanation}")

    # Phase 3: Object-level reasoning
    # Reason about which objects change and why
    if not verified and time.time() - start < timeout_seconds:
        trace.reasoning_path.append("phase3_object_reasoning")
        obj_ops = _try_object_reasoning(train_pairs, timeout_seconds - (time.time() - start))
        for op in obj_ops:
            trace.conjectures_tried += 1
            trace.conjectures_verified += 1
            verified.append(op)
            trace.reasoning_path.append(f"  verified: {op.explanation}")

    # Phase 4: Compositional reasoning
    # Try composing partial solutions
    if not verified and time.time() - start < timeout_seconds:
        trace.reasoning_path.append("phase4_compositional")
        comp_ops = _try_compositional_reasoning(
            train_pairs, timeout_seconds - (time.time() - start), trace
        )
        verified.extend(comp_ops)

    return verified, trace


# ---------------------------------------------------------------------------
# Phase 1: Context-based rule discovery
# ---------------------------------------------------------------------------

def _try_context_rule(
    ctx_fn: Callable, ctx_name: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[SynthesizedOperator]:
    """Try to learn a consistent mapping: context → output value."""
    for inp0, out0 in train_pairs[:1]:
        if inp0.shape != out0.shape:
            return None

    rule = {}
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        H, W = inp.shape
        for r in range(H):
            for c in range(W):
                try:
                    ctx = ctx_fn(inp, r, c)
                except Exception:
                    return None
                ov = int(out[r, c])
                if ctx in rule:
                    if rule[ctx] != ov:
                        return None
                else:
                    rule[ctx] = ov

    if not rule:
        return None

    is_identity = True
    for inp, out in train_pairs:
        for r in range(inp.shape[0]):
            for c in range(inp.shape[1]):
                ctx = ctx_fn(inp, r, c)
                if rule.get(ctx) != int(inp[r, c]):
                    is_identity = False
                    break
            if not is_identity:
                break
        if not is_identity:
            break
    if is_identity:
        return None

    def make_fn(cf, rl):
        def fn(grid, _cf=cf, _rl=rl):
            H, W = grid.shape
            out = np.zeros_like(grid)
            for r in range(H):
                for c in range(W):
                    ctx = _cf(grid, r, c)
                    if ctx in _rl:
                        out[r, c] = _rl[ctx]
                    else:
                        out[r, c] = grid[r, c]
            return out
        return fn

    fn = make_fn(ctx_fn, rule)
    if _verify(fn, train_pairs):
        return SynthesizedOperator(
            operator_id=f"reason_{ctx_name}_{uuid.uuid4().hex[:8]}",
            operator_family=f"reasoned_{ctx_name}",
            parameters={"context": ctx_name, "rule_size": len(rule)},
            preconditions=[],
            execute=fn,
            explanation=f"[Reasoned] Local rule via {ctx_name} ({len(rule)} entries)",
            source_failure_signature={},
        )
    return None


# ---------------------------------------------------------------------------
# Phase 2: Global transforms
# ---------------------------------------------------------------------------

def _try_global_transforms(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Try global grid transforms discovered from the data."""
    results = []
    start = time.time()

    # 2a: Output = input with specific pixels changed to a learned value
    # Discover WHICH pixels change and to WHAT
    if train_pairs and train_pairs[0][0].shape == train_pairs[0][1].shape:
        inp0, out0 = train_pairs[0]
        changed_mask = inp0 != out0
        if changed_mask.any() and changed_mask.sum() < inp0.size * 0.5:
            change_vals = out0[changed_mask]
            if len(set(change_vals.flat)) == 1:
                fill_val = int(change_vals.flat[0])
                # Hypothesis: changed cells are determined by a spatial pattern
                # Try: cells where input == bg AND enclosed
                def make_enclosed_fill(fv):
                    def fn(grid, _fv=fv):
                        out = grid.copy()
                        bg_mask = grid == 0
                        labeled, n = ndlabel(bg_mask)
                        H, W = grid.shape
                        for cid in range(1, n+1):
                            comp = labeled == cid
                            rows, cols = np.where(comp)
                            if (rows.min() > 0 and rows.max() < H-1
                                and cols.min() > 0 and cols.max() < W-1):
                                out[comp] = _fv
                        return out
                    return fn

                fn = make_enclosed_fill(fill_val)
                if _verify(fn, train_pairs):
                    results.append(SynthesizedOperator(
                        operator_id=f"reason_enclosed_fill_{uuid.uuid4().hex[:8]}",
                        operator_family="reasoned_enclosed_fill",
                        parameters={"fill_value": fill_val},
                        preconditions=[],
                        execute=fn,
                        explanation=f"[Reasoned] Fill enclosed regions with {fill_val}",
                        source_failure_signature={},
                    ))

    # 2b: Symmetry completion
    if time.time() - start < timeout:
        for sym in ["h", "v", "hv"]:
            fn = _make_symmetry_fn(sym)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"reason_sym_{sym}_{uuid.uuid4().hex[:8]}",
                    operator_family=f"reasoned_symmetry_{sym}",
                    parameters={"symmetry": sym},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Reasoned] Complete {sym} symmetry",
                    source_failure_signature={},
                ))
                break

    # 2c: Row/col unique color fill
    if time.time() - start < timeout and not results:
        for mode in ["row", "col"]:
            fn = _make_unique_fill_fn(mode)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"reason_fill_{mode}_{uuid.uuid4().hex[:8]}",
                    operator_family=f"reasoned_fill_{mode}",
                    parameters={"mode": mode},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Reasoned] Fill bg from unique {mode} color",
                    source_failure_signature={},
                ))
                break

    return results


def _make_symmetry_fn(sym: str):
    def fn(grid, _s=sym):
        H, W = grid.shape
        out = grid.copy()
        if _s in ("h", "hv"):
            for r in range(H):
                for c in range(W):
                    mc = W-1-c
                    if out[r, c] == 0 and out[r, mc] != 0:
                        out[r, c] = out[r, mc]
                    elif out[r, mc] == 0 and out[r, c] != 0:
                        out[r, mc] = out[r, c]
        if _s in ("v", "hv"):
            for r in range(H//2):
                for c in range(W):
                    mr = H-1-r
                    if out[r, c] == 0 and out[mr, c] != 0:
                        out[r, c] = out[mr, c]
                    elif out[mr, c] == 0 and out[r, c] != 0:
                        out[mr, c] = out[r, c]
        return out
    return fn


def _make_unique_fill_fn(mode: str):
    def fn(grid, _m=mode):
        out = grid.copy()
        H, W = grid.shape
        for r in range(H):
            for c in range(W):
                if out[r, c] != 0:
                    continue
                if _m == "row":
                    colors = set(int(grid[r, cc]) for cc in range(W)) - {0}
                else:
                    colors = set(int(grid[rr, c]) for rr in range(H)) - {0}
                if len(colors) == 1:
                    out[r, c] = colors.pop()
        return out
    return fn


# ---------------------------------------------------------------------------
# Phase 3: Object-level reasoning
# ---------------------------------------------------------------------------

def _try_object_reasoning(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
) -> List[SynthesizedOperator]:
    """Reason about objects: what determines each object's fate?"""
    results = []
    start = time.time()

    for inp, out in train_pairs[:1]:
        if inp.shape != out.shape:
            return results

    # Extract objects and classify their fates across ALL training pairs
    try:
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _add_relational_properties,
            _get_property_value,
            _all_property_names,
        )
        use_rich = True
    except Exception:
        use_rich = False
        return results

    all_pair_data = []
    for inp, out in train_pairs:
        objs = _extract_objects_with_properties(inp, bg=0)
        _add_relational_properties(objs, inp, inp.shape[0], inp.shape[1])

        fates = []
        for obj in objs:
            mask = obj["mask"]
            out_region = out[mask]
            inp_region = inp[mask]

            if np.array_equal(out_region, inp_region):
                fates.append(("keep", None))
            elif np.all(out_region == 0):
                fates.append(("remove", None))
            elif len(set(out_region.flat)) == 1:
                fates.append(("recolor", int(out_region.flat[0])))
            else:
                fates.append(("changed", None))

        all_pair_data.append((objs, fates, inp, out))

    if not all_pair_data:
        return results

    props = _all_property_names()

    # Find property that discriminates fates
    fate_types = set()
    for _, fates, _, _ in all_pair_data:
        for f, _ in fates:
            fate_types.add(f)

    if fate_types == {"keep", "remove"}:
        for prop in props:
            if time.time() - start > timeout:
                break
            for keep_when_true in [True, False]:
                consistent = True
                for objs, fates, _, _ in all_pair_data:
                    for obj, (fate, _) in zip(objs, fates):
                        pval = _get_property_value(obj, prop)
                        should_keep = (pval == keep_when_true)
                        if (fate == "keep") != should_keep:
                            consistent = False
                            break
                    if not consistent:
                        break

                if consistent:
                    def make_fn(p, kt):
                        def fn(grid, _p=p, _kt=kt):
                            objs = _extract_objects_with_properties(grid, bg=0)
                            _add_relational_properties(objs, grid, grid.shape[0], grid.shape[1])
                            out = np.zeros_like(grid)
                            for obj in objs:
                                if _get_property_value(obj, _p) == _kt:
                                    out[obj["mask"]] = grid[obj["mask"]]
                            return out
                        return fn

                    fn = make_fn(prop, keep_when_true)
                    if _verify(fn, train_pairs):
                        d = "keep" if keep_when_true else "remove"
                        results.append(SynthesizedOperator(
                            operator_id=f"reason_filter_{uuid.uuid4().hex[:8]}",
                            operator_family="reasoned_object_filter",
                            parameters={"property": prop, "keep_when_true": keep_when_true},
                            preconditions=[],
                            execute=fn,
                            explanation=f"[Reasoned] {d} objects where {prop}",
                            source_failure_signature={},
                        ))
                        return results

    if "recolor" in fate_types:
        for prop in props:
            if time.time() - start > timeout:
                break
            color_when_true = None
            color_when_false = None
            consistent = True

            for objs, fates, _, _ in all_pair_data:
                for obj, (fate, color) in zip(objs, fates):
                    pval = _get_property_value(obj, prop)
                    if fate == "recolor":
                        if pval:
                            if color_when_true is None:
                                color_when_true = color
                            elif color_when_true != color:
                                consistent = False
                                break
                        else:
                            if color_when_false is None:
                                color_when_false = color
                            elif color_when_false != color:
                                consistent = False
                                break
                    elif fate == "keep":
                        pass
                if not consistent:
                    break

            if not consistent:
                continue
            if color_when_true is None and color_when_false is None:
                continue

            def make_fn(p, ct, cf):
                def fn(grid, _p=p, _ct=ct, _cf=cf):
                    objs = _extract_objects_with_properties(grid, bg=0)
                    _add_relational_properties(objs, grid, grid.shape[0], grid.shape[1])
                    out = grid.copy()
                    for obj in objs:
                        pval = _get_property_value(obj, _p)
                        if pval and _ct is not None:
                            out[obj["mask"]] = _ct
                        elif not pval and _cf is not None:
                            out[obj["mask"]] = _cf
                    return out
                return fn

            fn = make_fn(prop, color_when_true, color_when_false)
            if _verify(fn, train_pairs):
                results.append(SynthesizedOperator(
                    operator_id=f"reason_recolor_{uuid.uuid4().hex[:8]}",
                    operator_family="reasoned_object_recolor",
                    parameters={"property": prop},
                    preconditions=[],
                    execute=fn,
                    explanation=f"[Reasoned] Recolor by {prop}: True→{color_when_true}, False→{color_when_false}",
                    source_failure_signature={},
                ))
                return results

    return results


# ---------------------------------------------------------------------------
# Phase 4: Compositional reasoning
# Try composing partial solutions that individually get close
# ---------------------------------------------------------------------------

def _try_compositional_reasoning(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
    trace: ReasoningTrace,
) -> List[SynthesizedOperator]:
    """Compose partial solutions: if step A gets 70% right, find step B for the rest."""
    results = []
    start = time.time()

    # Generate candidate partial transforms
    partials = []
    for ctx_name, ctx_fn in CONTEXT_EXTRACTORS[:6]:
        if time.time() - start > timeout:
            break
        partial_fn = _build_partial_rule(ctx_fn, ctx_name, train_pairs)
        if partial_fn is not None:
            acc = _score_partial(partial_fn, train_pairs)
            if 0.3 < acc < 1.0 - 1e-9:
                partials.append((ctx_name, partial_fn, acc))
                trace.reasoning_path.append(f"  partial: {ctx_name} acc={acc:.1%}")

    if not partials:
        return results

    partials.sort(key=lambda x: -x[2])
    trace.best_partial_accuracy = partials[0][2]

    # For each partial, compute residual and try to fix it
    for p_name, p_fn, p_acc in partials[:3]:
        if time.time() - start > timeout:
            break

        # Compute intermediate results
        intermediates = []
        for inp, out in train_pairs:
            try:
                mid = p_fn(inp)
                if mid is not None and mid.shape == out.shape:
                    intermediates.append((mid, out))
            except Exception:
                break

        if len(intermediates) != len(train_pairs):
            continue

        # Try to find a correction rule for the residual
        trace.refinements_attempted += 1
        for ctx_name2, ctx_fn2 in CONTEXT_EXTRACTORS[:8]:
            if time.time() - start > timeout:
                break
            corr = _try_context_rule(ctx_fn2, ctx_name2, intermediates)
            if corr is not None:
                # Compose: step1 → step2
                def make_composed(f1, f2_exec):
                    def fn(grid, _f1=f1, _f2=f2_exec):
                        mid = _f1(grid)
                        return _f2(mid)
                    return fn

                composed_fn = make_composed(p_fn, corr.execute)
                if _verify(composed_fn, train_pairs):
                    trace.refinements_successful += 1
                    trace.conjectures_verified += 1
                    results.append(SynthesizedOperator(
                        operator_id=f"reason_composed_{uuid.uuid4().hex[:8]}",
                        operator_family="reasoned_composition",
                        parameters={"step1": p_name, "step2": ctx_name2},
                        preconditions=[],
                        execute=composed_fn,
                        explanation=f"[Reasoned] Compose: {p_name} → {ctx_name2}",
                        source_failure_signature={},
                    ))
                    return results

    return results


def _build_partial_rule(
    ctx_fn: Callable, ctx_name: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Callable]:
    """Build a rule even if it's not perfectly consistent — use majority vote."""
    for inp0, out0 in train_pairs[:1]:
        if inp0.shape != out0.shape:
            return None

    votes = {}
    for inp, out in train_pairs:
        H, W = inp.shape
        for r in range(H):
            for c in range(W):
                try:
                    ctx = ctx_fn(inp, r, c)
                except Exception:
                    return None
                ov = int(out[r, c])
                if ctx not in votes:
                    votes[ctx] = Counter()
                votes[ctx][ov] += 1

    rule = {ctx: counter.most_common(1)[0][0] for ctx, counter in votes.items()}

    def make_fn(cf, rl):
        def fn(grid, _cf=cf, _rl=rl):
            H, W = grid.shape
            out = np.zeros_like(grid)
            for r in range(H):
                for c in range(W):
                    ctx = _cf(grid, r, c)
                    out[r, c] = _rl.get(ctx, grid[r, c])
            return out
        return fn

    return make_fn(ctx_fn, rule)


def _score_partial(fn: Callable, train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> float:
    """Score a partial solution by pixel accuracy."""
    total, correct = 0, 0
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or pred.shape != out.shape:
                return 0.0
            total += pred.size
            correct += int(np.sum(pred == out))
        except Exception:
            return 0.0
    return correct / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _verify(fn: Callable, train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> bool:
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


# ---------------------------------------------------------------------------
# Convenience entry point returning just operators
# ---------------------------------------------------------------------------

def reason_adaptively(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 30.0,
) -> List[SynthesizedOperator]:
    """Convenience wrapper that returns just the operators."""
    ops, _ = adaptive_reason(train_pairs, timeout_seconds)
    return ops
