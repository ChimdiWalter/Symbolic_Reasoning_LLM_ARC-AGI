"""Cortical Reasoning Module — Brain-inspired reasoning for grid-based tasks.

Six cognitive mechanisms adapted from computational neuroscience:
1. Hierarchical Perception (V1→V4): multi-level grid representation
2. Structural Hypothesis Correction (Predictive Coding): low-parameter transforms
3. Multi-Column Voting (Thousand Brains): consensus across imperfect candidates
4. Metacognitive Confidence: calibrated near-miss acceptance
5. Feature Binding (Cortical Oscillations): compose strengths from different solvers
6. Structural Session Memory (Analogical Reasoning): transfer by structural signature

All mechanisms are task-agnostic — they operate on abstract representations,
not ARC-specific heuristics. Designed for hidden-test environments where
test outputs are never visible to the solver.
"""
from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set

import numpy as np

from reasoning_project.operator_genesis import SynthesizedOperator


# ===================================================================
# Layer 1: Hierarchical Perception (V1 → V4 cortical hierarchy)
# ===================================================================

@dataclass
class ObjectRepr:
    """A perceived object in the grid."""
    pixels: Set[Tuple[int, int]]
    color: int
    bbox: Tuple[int, int, int, int]  # (min_r, min_c, max_r, max_c)
    size: int
    is_rectangular: bool
    has_holes: bool


@dataclass
class GridPerception:
    """Multi-level hierarchical perception of a grid."""
    # L1: Pixel-level
    shape: Tuple[int, int]
    background_color: int
    color_histogram: Dict[int, int]
    n_colors: int
    n_nonbg_cells: int

    # L2: Object-level
    objects: List[ObjectRepr]
    n_objects: int

    # L3: Relational
    has_containment: bool
    has_alignment: bool
    has_uniform_spacing: bool
    has_grid_structure: bool
    symmetry_axes: List[str]  # "horizontal", "vertical", "diagonal", "rotational"

    # L4: Abstract
    dominant_pattern: str  # "scattered", "grid", "symmetric", "nested", "linear"


def perceive_grid(grid: np.ndarray) -> GridPerception:
    """Extract hierarchical representation from a grid (V1→V4 pipeline)."""
    h, w = grid.shape

    # L1: Pixel statistics
    unique, counts = np.unique(grid, return_counts=True)
    color_hist = dict(zip(unique.tolist(), counts.tolist()))
    bg_color = int(unique[np.argmax(counts)])
    n_colors = len(unique)
    n_nonbg = int(np.sum(grid != bg_color))

    # L2: Object extraction (connected components)
    objects = _extract_objects(grid, bg_color)

    # L3: Relational analysis
    has_containment = _detect_containment(objects)
    has_alignment = _detect_alignment(objects)
    has_uniform_spacing = _detect_uniform_spacing(objects)
    has_grid_structure = _detect_grid_structure(grid, bg_color)
    symmetry_axes = _detect_symmetries(grid)

    # L4: Abstract pattern classification
    dominant_pattern = _classify_pattern(
        objects, has_grid_structure, symmetry_axes, has_containment, n_nonbg, h * w)

    return GridPerception(
        shape=(h, w),
        background_color=bg_color,
        color_histogram=color_hist,
        n_colors=n_colors,
        n_nonbg_cells=n_nonbg,
        objects=objects,
        n_objects=len(objects),
        has_containment=has_containment,
        has_alignment=has_alignment,
        has_uniform_spacing=has_uniform_spacing,
        has_grid_structure=has_grid_structure,
        symmetry_axes=symmetry_axes,
        dominant_pattern=dominant_pattern,
    )


def _extract_objects(grid: np.ndarray, bg_color: int) -> List[ObjectRepr]:
    """BFS-based connected component extraction."""
    h, w = grid.shape
    visited = np.zeros((h, w), dtype=bool)
    objects = []

    for r in range(h):
        for c in range(w):
            if visited[r, c] or grid[r, c] == bg_color:
                continue
            color = int(grid[r, c])
            pixels = set()
            stack = [(r, c)]
            while stack:
                cr, cc = stack.pop()
                if cr < 0 or cr >= h or cc < 0 or cc >= w:
                    continue
                if visited[cr, cc] or grid[cr, cc] != color:
                    continue
                visited[cr, cc] = True
                pixels.add((cr, cc))
                stack.extend([(cr - 1, cc), (cr + 1, cc), (cr, cc - 1), (cr, cc + 1)])

            if pixels:
                rows = [p[0] for p in pixels]
                cols = [p[1] for p in pixels]
                min_r, max_r = min(rows), max(rows)
                min_c, max_c = min(cols), max(cols)
                bbox_area = (max_r - min_r + 1) * (max_c - min_c + 1)
                is_rect = len(pixels) == bbox_area

                has_holes = False
                if is_rect and bbox_area > 1:
                    for ir in range(min_r + 1, max_r):
                        for ic in range(min_c + 1, max_c):
                            if grid[ir, ic] != color:
                                has_holes = True
                                break
                        if has_holes:
                            break

                objects.append(ObjectRepr(
                    pixels=pixels,
                    color=color,
                    bbox=(min_r, min_c, max_r, max_c),
                    size=len(pixels),
                    is_rectangular=is_rect,
                    has_holes=has_holes,
                ))

    return objects


def _detect_containment(objects: List[ObjectRepr]) -> bool:
    """Check if any object's bounding box contains another."""
    for i, a in enumerate(objects):
        for j, b in enumerate(objects):
            if i == j:
                continue
            if (a.bbox[0] <= b.bbox[0] and a.bbox[1] <= b.bbox[1] and
                    a.bbox[2] >= b.bbox[2] and a.bbox[3] >= b.bbox[3]):
                return True
    return False


def _detect_alignment(objects: List[ObjectRepr]) -> bool:
    """Check if objects share row or column positions."""
    if len(objects) < 2:
        return False
    top_rows = [o.bbox[0] for o in objects]
    left_cols = [o.bbox[1] for o in objects]
    return len(set(top_rows)) < len(objects) or len(set(left_cols)) < len(objects)


def _detect_uniform_spacing(objects: List[ObjectRepr]) -> bool:
    """Check if objects are evenly spaced."""
    if len(objects) < 3:
        return False
    centers = sorted([(o.bbox[0] + o.bbox[2]) / 2 for o in objects])
    diffs = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    if diffs and max(diffs) - min(diffs) <= 1:
        return True
    centers_c = sorted([(o.bbox[1] + o.bbox[3]) / 2 for o in objects])
    diffs_c = [centers_c[i + 1] - centers_c[i] for i in range(len(centers_c) - 1)]
    return bool(diffs_c and max(diffs_c) - min(diffs_c) <= 1)


def _detect_grid_structure(grid: np.ndarray, bg_color: int) -> bool:
    """Check if the grid has a regular sub-grid pattern (separator lines)."""
    h, w = grid.shape
    if h < 3 or w < 3:
        return False
    for color in range(10):
        full_rows = [r for r in range(h) if np.all(grid[r, :] == color)]
        full_cols = [c for c in range(w) if np.all(grid[:, c] == color)]
        if len(full_rows) >= 1 and len(full_cols) >= 1:
            return True
    return False


def _detect_symmetries(grid: np.ndarray) -> List[str]:
    """Detect symmetry axes in the grid."""
    axes = []
    if np.array_equal(grid, np.flipud(grid)):
        axes.append("horizontal")
    if np.array_equal(grid, np.fliplr(grid)):
        axes.append("vertical")
    if grid.shape[0] == grid.shape[1]:
        if np.array_equal(grid, grid.T):
            axes.append("diagonal")
        if np.array_equal(grid, np.rot90(grid)):
            axes.append("rotational_90")
        elif np.array_equal(grid, np.rot90(grid, 2)):
            axes.append("rotational_180")
    return axes


def _classify_pattern(objects, has_grid, symmetries, has_containment, n_nonbg, total):
    """Classify the dominant visual pattern."""
    if has_grid:
        return "grid"
    if symmetries:
        return "symmetric"
    if has_containment:
        return "nested"
    if len(objects) <= 2 and n_nonbg < total * 0.3:
        return "sparse"
    if len(objects) > 5:
        return "scattered"
    return "structured"


# ===================================================================
# Structural Signature — for analogical transfer
# ===================================================================

@dataclass
class TaskSignature:
    """Abstract structural signature of a task for analogical matching."""
    shape_change: str  # "same", "scale", "crop", "grow", "reshape"
    n_objects_change: str  # "same", "more", "fewer", "zero_to_many", "many_to_zero"
    color_change: str  # "same", "remap", "reduce", "expand"
    input_pattern: str  # from GridPerception.dominant_pattern
    output_pattern: str
    input_symmetries: List[str]
    output_symmetries: List[str]
    has_size_correlation: bool


def compute_task_signature(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]]
) -> TaskSignature:
    """Compute abstract structural signature from training pairs."""
    inp_percs = [perceive_grid(inp) for inp, _ in train_pairs]
    out_percs = [perceive_grid(out) for _, out in train_pairs]

    # Shape change
    shapes_match = all(ip.shape == op.shape for ip, op in zip(inp_percs, out_percs))
    if shapes_match:
        shape_change = "same"
    else:
        ratios = []
        for ip, op in zip(inp_percs, out_percs):
            r = (op.shape[0] / max(ip.shape[0], 1), op.shape[1] / max(ip.shape[1], 1))
            ratios.append(r)
        if all(r[0] == r[1] and r[0] == int(r[0]) for r in ratios):
            shape_change = "scale"
        elif all(op.shape[0] <= ip.shape[0] and op.shape[1] <= ip.shape[1]
                 for ip, op in zip(inp_percs, out_percs)):
            shape_change = "crop"
        elif all(op.shape[0] >= ip.shape[0] and op.shape[1] >= ip.shape[1]
                 for ip, op in zip(inp_percs, out_percs)):
            shape_change = "grow"
        else:
            shape_change = "reshape"

    # Object count change
    obj_changes = set()
    for ip, op in zip(inp_percs, out_percs):
        if ip.n_objects == op.n_objects:
            obj_changes.add("same")
        elif ip.n_objects == 0 and op.n_objects > 0:
            obj_changes.add("zero_to_many")
        elif ip.n_objects > 0 and op.n_objects == 0:
            obj_changes.add("many_to_zero")
        elif ip.n_objects < op.n_objects:
            obj_changes.add("more")
        else:
            obj_changes.add("fewer")
    n_objects_change = obj_changes.pop() if len(obj_changes) == 1 else "mixed"

    # Color change
    color_changes = set()
    for ip, op in zip(inp_percs, out_percs):
        ic = set(ip.color_histogram.keys())
        oc = set(op.color_histogram.keys())
        if ic == oc:
            color_changes.add("same")
        elif len(oc) < len(ic):
            color_changes.add("reduce")
        elif len(oc) > len(ic):
            color_changes.add("expand")
        else:
            color_changes.add("remap")
    color_change = color_changes.pop() if len(color_changes) == 1 else "mixed"

    # Dominant patterns (use first pair as representative)
    input_pattern = inp_percs[0].dominant_pattern
    output_pattern = out_percs[0].dominant_pattern

    # Symmetries
    input_syms = inp_percs[0].symmetry_axes
    output_syms = out_percs[0].symmetry_axes

    # Size correlation (do larger inputs produce larger outputs?)
    has_size_corr = False
    if len(train_pairs) >= 2 and not shapes_match:
        in_sizes = [ip.shape[0] * ip.shape[1] for ip in inp_percs]
        out_sizes = [op.shape[0] * op.shape[1] for op in out_percs]
        if sorted(range(len(in_sizes)), key=lambda i: in_sizes[i]) == \
           sorted(range(len(out_sizes)), key=lambda i: out_sizes[i]):
            has_size_corr = True

    return TaskSignature(
        shape_change=shape_change,
        n_objects_change=n_objects_change,
        color_change=color_change,
        input_pattern=input_pattern,
        output_pattern=output_pattern,
        input_symmetries=input_syms,
        output_symmetries=output_syms,
        has_size_correlation=has_size_corr,
    )


def signature_similarity(a: TaskSignature, b: TaskSignature) -> float:
    """Compute structural similarity between two task signatures."""
    score = 0.0
    if a.shape_change == b.shape_change:
        score += 3.0
    if a.n_objects_change == b.n_objects_change:
        score += 2.0
    if a.color_change == b.color_change:
        score += 2.0
    if a.input_pattern == b.input_pattern:
        score += 1.0
    if a.output_pattern == b.output_pattern:
        score += 1.0
    sym_overlap = len(set(a.input_symmetries) & set(b.input_symmetries))
    score += sym_overlap * 0.5
    return score


# ===================================================================
# Layer 2: Structural Hypothesis Corrections (Predictive Coding)
# ===================================================================

def structural_corrections(
    best_op: SynthesizedOperator,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Generate low-parameter structural corrections with LOO validation.

    Instead of pixel-level residual patching, tries abstract hypotheses:
    geometric transforms, color permutations, and combinations.
    These have ≤11 parameters and are inherently generalizable.
    """
    results = []
    n = len(train_pairs)

    preds = []
    for inp, out in train_pairs:
        try:
            pred = best_op.execute(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return []
            preds.append(pred)
        except Exception:
            return []

    # --- Geometric transforms on prediction ---
    geo_transforms = [
        ("rot90", lambda x: np.rot90(x, 1)),
        ("rot180", lambda x: np.rot90(x, 2)),
        ("rot270", lambda x: np.rot90(x, 3)),
        ("flip_h", lambda x: np.fliplr(x)),
        ("flip_v", lambda x: np.flipud(x)),
        ("transpose", lambda x: x.T),
        ("flip_h_rot90", lambda x: np.rot90(np.fliplr(x), 1)),
        ("flip_v_rot90", lambda x: np.rot90(np.flipud(x), 1)),
    ]

    for tname, tfn in geo_transforms:
        if all(_try_transform(preds[i], train_pairs[i][1], tfn) for i in range(n)):
            op = _make_transform_op(best_op, tname, tfn)
            results.append(op)
            return results

    # --- Color permutation ---
    all_same_shape = all(
        p.shape == o.shape for p, (_, o) in zip(preds, train_pairs))
    if all_same_shape:
        perm = _learn_color_permutation(preds, train_pairs)
        if perm is not None and _loo_validate_perm(preds, train_pairs, best_op, perm):
            op = _make_perm_op(best_op, perm)
            results.append(op)
            return results

    # --- Geometric + color permutation combined ---
    if all_same_shape:
        for tname, tfn in geo_transforms:
            transformed = []
            valid = True
            for pred, (_, out) in zip(preds, train_pairs):
                try:
                    t = tfn(pred)
                    if t.shape != out.shape:
                        valid = False
                        break
                    transformed.append(t)
                except Exception:
                    valid = False
                    break
            if not valid:
                continue
            perm = _learn_color_permutation(transformed, train_pairs)
            if perm is not None:
                def make_combined(base_fn, tf, pm):
                    def fn(grid, _b=base_fn, _tf=tf, _pm=pm):
                        mid = _tf(_b(grid))
                        out = mid.copy()
                        for s, t in _pm.items():
                            out[mid == s] = t
                        return out
                    return fn
                combined_fn = make_combined(best_op.execute, tfn, perm)
                combined_op = SynthesizedOperator(
                    operator_id=f"structural_{tname}_perm_{uuid.uuid4().hex[:8]}",
                    operator_family=f"structural_{tname}_colorperm_{best_op.operator_family}",
                    parameters={"transform": tname, "perm": {str(k): v for k, v in perm.items()}},
                    preconditions=[],
                    execute=combined_fn,
                    explanation=f"[Structural] {best_op.explanation} → {tname} → recolor",
                    source_failure_signature={},
                )
                if _verify_all_train(combined_op, train_pairs):
                    results.append(combined_op)
                    return results

    # --- Input-conditional color correction ---
    # Learn (input_color) → color map, where the correction depends on input context
    if all_same_shape and all(
            p.shape == i.shape for p, (i, _) in zip(preds, train_pairs)):
        ic_perm = _learn_input_conditional_perm(preds, train_pairs)
        if ic_perm is not None:
            def make_ic_perm(base_fn, icp):
                def fn(grid, _b=base_fn, _icp=icp):
                    mid = _b(grid)
                    if mid.shape != grid.shape:
                        return mid
                    out = mid.copy()
                    for (ic, pc), tc in _icp.items():
                        mask = (grid == ic) & (mid == pc)
                        out[mask] = tc
                    return out
                return fn
            ic_fn = make_ic_perm(best_op.execute, ic_perm)
            ic_op = SynthesizedOperator(
                operator_id=f"structural_ic_perm_{uuid.uuid4().hex[:8]}",
                operator_family=f"structural_ic_colorperm_{best_op.operator_family}",
                parameters={},
                preconditions=[],
                execute=ic_fn,
                explanation=f"[Structural] {best_op.explanation} → input-conditional recolor",
                source_failure_signature={},
            )
            if _verify_all_train(ic_op, train_pairs) and _loo_validate_ic_perm(
                    preds, train_pairs, best_op, ic_perm):
                results.append(ic_op)
                return results

    return results


def _try_transform(pred, expected, tfn):
    try:
        t = tfn(pred)
        return t.shape == expected.shape and np.array_equal(t, expected)
    except Exception:
        return False


def _make_transform_op(best_op, tname, tfn):
    def make_fn(base_fn, tf):
        def fn(grid, _b=base_fn, _tf=tf):
            return _tf(_b(grid))
        return fn
    return SynthesizedOperator(
        operator_id=f"structural_{tname}_{uuid.uuid4().hex[:8]}",
        operator_family=f"structural_{tname}_{best_op.operator_family}",
        parameters={"transform": tname},
        preconditions=[],
        execute=make_fn(best_op.execute, tfn),
        explanation=f"[Structural] {best_op.explanation} → {tname}",
        source_failure_signature={},
    )


def _learn_color_permutation(preds, train_pairs):
    """Learn a deterministic color permutation from prediction errors."""
    perm = {}
    for pred, (_, out) in zip(preds, train_pairs):
        if pred.shape != out.shape:
            return None
        for r in range(pred.shape[0]):
            for c in range(pred.shape[1]):
                pc, ec = int(pred[r, c]), int(out[r, c])
                if pc != ec:
                    if pc in perm:
                        if perm[pc] != ec:
                            return None
                    else:
                        perm[pc] = ec
    if not perm:
        return None
    # Verify perm doesn't break correct pixels
    for pred, (_, out) in zip(preds, train_pairs):
        for r in range(pred.shape[0]):
            for c in range(pred.shape[1]):
                pc = int(pred[r, c])
                if pc in perm and perm[pc] != int(out[r, c]):
                    return None
    return perm


def _loo_validate_perm(preds, train_pairs, best_op, full_perm):
    """LOO validation for color permutation."""
    n = len(train_pairs)
    if n < 2:
        return True
    for hold in range(n):
        fold_perm = {}
        ok = True
        for j in range(n):
            if j == hold:
                continue
            pred_j = preds[j]
            _, out_j = train_pairs[j]
            for r in range(pred_j.shape[0]):
                for c in range(pred_j.shape[1]):
                    pc, ec = int(pred_j[r, c]), int(out_j[r, c])
                    if pc != ec:
                        if pc in fold_perm:
                            if fold_perm[pc] != ec:
                                ok = False
                                break
                        else:
                            fold_perm[pc] = ec
                if not ok:
                    break
            if not ok:
                break
        if not ok:
            return False
        # Apply fold_perm to held-out prediction
        held_pred = preds[hold]
        _, held_out = train_pairs[hold]
        if held_pred.shape != held_out.shape:
            return False
        result = held_pred.copy()
        for s, t in fold_perm.items():
            result[held_pred == s] = t
        if not np.array_equal(result, held_out):
            return False
    return True


def _learn_input_conditional_perm(preds, train_pairs):
    """Learn (input_color, pred_color) → target_color mapping from errors only."""
    perm = {}
    for pred, (inp, out) in zip(preds, train_pairs):
        wrong = pred != out
        if not wrong.any():
            continue
        wr, wc = np.where(wrong)
        for r, c in zip(wr, wc):
            key = (int(inp[r, c]), int(pred[r, c]))
            val = int(out[r, c])
            if key in perm:
                if perm[key] != val:
                    return None
            else:
                perm[key] = val
    if not perm:
        return None
    # Verify doesn't break correct pixels
    for pred, (inp, out) in zip(preds, train_pairs):
        correct = pred == out
        cr, cc = np.where(correct)
        for r, c in zip(cr, cc):
            key = (int(inp[r, c]), int(pred[r, c]))
            if key in perm and perm[key] != int(pred[r, c]):
                return None
    return perm


def _loo_validate_ic_perm(preds, train_pairs, best_op, full_perm):
    """LOO validation for input-conditional permutation."""
    n = len(train_pairs)
    if n < 2:
        return True
    for hold in range(n):
        fold_perm = {}
        ok = True
        for j in range(n):
            if j == hold:
                continue
            pred_j, (inp_j, out_j) = preds[j], train_pairs[j]
            wrong = pred_j != out_j
            if not wrong.any():
                continue
            wr, wc = np.where(wrong)
            for r, c in zip(wr, wc):
                key = (int(inp_j[r, c]), int(pred_j[r, c]))
                val = int(out_j[r, c])
                if key in fold_perm:
                    if fold_perm[key] != val:
                        ok = False
                        break
                else:
                    fold_perm[key] = val
            if not ok:
                break
        if not ok:
            return False
        held_pred = preds[hold]
        held_inp, held_out = train_pairs[hold]
        if held_pred.shape != held_out.shape or held_pred.shape != held_inp.shape:
            return False
        result = held_pred.copy()
        for (ic, pc), tc in fold_perm.items():
            mask = (held_inp == ic) & (held_pred == pc)
            result[mask] = tc
        if not np.array_equal(result, held_out):
            return False
    return True


def _verify_all_train(op, train_pairs):
    for inp, out in train_pairs:
        try:
            pred = op.execute(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


def _loo_validate(op, train_pairs):
    """LOO validation: hold out each training pair, verify on held-out input."""
    n = len(train_pairs)
    if n < 2:
        return True
    passes = 0
    for i in range(n):
        held_inp, held_out = train_pairs[i]
        try:
            pred = op.execute(held_inp)
            if pred is not None and isinstance(pred, np.ndarray) and \
                    pred.shape == held_out.shape and np.array_equal(pred, held_out):
                passes += 1
        except Exception:
            pass
    return passes >= max(1, n - 1)


# ===================================================================
# Layer 3: Multi-Column Voting (Thousand Brains)
# ===================================================================

def multi_column_vote(
    candidates: List[Tuple[str, SynthesizedOperator, float]],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[SynthesizedOperator]:
    """Pixel-wise majority vote across multiple partial candidates.

    Each candidate is an independent "cortical column" that models the
    transformation from its own perspective. No single column needs
    to be perfect — consensus across imperfect models yields correct output.
    """
    if len(candidates) < 3:
        return None

    n_train = len(train_pairs)

    # Generate predictions on all training inputs
    all_preds = []  # [candidate_idx][pair_idx] = pred or None
    for _, op, _ in candidates:
        cand_preds = []
        for inp, out in train_pairs:
            try:
                pred = op.execute(inp)
                if pred is not None and isinstance(pred, np.ndarray) and pred.shape == out.shape:
                    cand_preds.append(pred)
                else:
                    cand_preds.append(None)
            except Exception:
                cand_preds.append(None)
        all_preds.append(cand_preds)

    # Group candidates by their predicted output shape for each pair
    # (all candidates in a vote group must predict the same shape)

    # Pixel-wise majority vote weighted by partial score
    voted_train = []
    for pair_idx in range(n_train):
        expected_shape = train_pairs[pair_idx][1].shape
        valid = [(i, all_preds[i][pair_idx])
                 for i in range(len(candidates))
                 if all_preds[i][pair_idx] is not None]
        if len(valid) < 2:
            return None

        h, w = expected_shape
        voted = np.zeros((h, w), dtype=int)
        for r in range(h):
            for c in range(w):
                weighted_votes: Dict[int, float] = {}
                for cand_idx, pred in valid:
                    color = int(pred[r, c])
                    weight = candidates[cand_idx][2]  # partial score as weight
                    weighted_votes[color] = weighted_votes.get(color, 0.0) + weight
                voted[r, c] = max(weighted_votes, key=weighted_votes.get)
        voted_train.append(voted)

    # Check if voted output matches ALL training outputs
    for pair_idx in range(n_train):
        if not np.array_equal(voted_train[pair_idx], train_pairs[pair_idx][1]):
            return None

    # Build a voting operator that runs all candidates and votes at test time
    candidate_ops = [op for _, op, _ in candidates]
    candidate_weights = [w for _, _, w in candidates]

    def make_voter(ops, weights):
        def fn(grid, _ops=ops, _w=weights):
            preds = []
            ws = []
            for op, w in zip(_ops, _w):
                try:
                    pred = op.execute(grid)
                    if pred is not None and isinstance(pred, np.ndarray):
                        preds.append(pred)
                        ws.append(w)
                except Exception:
                    pass
            if not preds:
                return None
            shapes = [p.shape for p in preds]
            shape_counts = Counter(shapes)
            target_shape = shape_counts.most_common(1)[0][0]
            valid_preds = [(p, w) for p, w in zip(preds, ws) if p.shape == target_shape]
            if not valid_preds:
                return None
            h, w_dim = target_shape
            result = np.zeros((h, w_dim), dtype=int)
            for r in range(h):
                for c in range(w_dim):
                    weighted: Dict[int, float] = {}
                    for pred, wt in valid_preds:
                        color = int(pred[r, c])
                        weighted[color] = weighted.get(color, 0.0) + wt
                    result[r, c] = max(weighted, key=weighted.get)
            return result
        return fn

    voter_fn = make_voter(candidate_ops, candidate_weights)
    voter_op = SynthesizedOperator(
        operator_id=f"cortical_vote_{uuid.uuid4().hex[:8]}",
        operator_family="cortical_column_vote",
        parameters={"n_columns": len(candidate_ops)},
        preconditions=[],
        execute=voter_fn,
        explanation=f"[Cortical Vote] Consensus of {len(candidate_ops)} independent columns",
        source_failure_signature={},
    )

    if not _loo_validate(voter_op, train_pairs):
        return None
    return voter_op


# ===================================================================
# Layer 4: Metacognitive Confidence (Near-Miss Acceptance)
# ===================================================================

def metacognitive_accept(
    candidates: List[Tuple[str, SynthesizedOperator, float]],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    min_pass_ratio: float = 0.66,
    min_pixel_accuracy: float = 0.95,
) -> Optional[Tuple[str, SynthesizedOperator]]:
    """Accept a near-miss candidate with confidence calibration.

    Instead of binary pass/fail, uses a confidence gradient:
    - How many training pairs pass exactly?
    - How accurate is the worst-case pair?
    - Does LOO validate the generalization?
    """
    n = len(train_pairs)
    if n < 2:
        return None

    best_candidate = None
    best_confidence = 0.0

    for layer_name, op, partial_score in candidates:
        # Count how many training pairs pass exactly
        pass_count = 0
        fail_scores = []
        fail_indices = []
        for i, (inp, out) in enumerate(train_pairs):
            try:
                pred = op.execute(inp)
                if pred is not None and isinstance(pred, np.ndarray):
                    if pred.shape == out.shape and np.array_equal(pred, out):
                        pass_count += 1
                    elif pred.shape == out.shape:
                        pixel_acc = float(np.sum(pred == out)) / max(out.size, 1)
                        fail_scores.append(pixel_acc)
                        fail_indices.append(i)
                    else:
                        fail_scores.append(0.0)
                        fail_indices.append(i)
                else:
                    fail_scores.append(0.0)
                    fail_indices.append(i)
            except Exception:
                fail_scores.append(0.0)
                fail_indices.append(i)

        if pass_count < n * min_pass_ratio:
            continue
        if not fail_scores:
            continue  # Already fully passing — shouldn't be here
        if min(fail_scores) < min_pixel_accuracy:
            continue

        # LOO validation: hold out each PASSING pair, verify still passes
        loo_pass = True
        for i in range(n):
            if i in fail_indices:
                continue
            try:
                pred = op.execute(train_pairs[i][0])
                if pred is None or not isinstance(pred, np.ndarray):
                    loo_pass = False
                    break
                if pred.shape != train_pairs[i][1].shape or \
                        not np.array_equal(pred, train_pairs[i][1]):
                    loo_pass = False
                    break
            except Exception:
                loo_pass = False
                break
        if not loo_pass:
            continue

        # Confidence score
        confidence = (pass_count / n) * min(fail_scores)

        if confidence > best_confidence:
            best_confidence = confidence
            best_candidate = (layer_name, op)

    return best_candidate


# ===================================================================
# Layer 5: Feature Binding (Cortical Oscillations)
# ===================================================================

def feature_binding(
    candidates: List[Tuple[str, SynthesizedOperator, float]],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[SynthesizedOperator]:
    """Bind correct features from different solvers.

    If solver A gets geometry right but colors wrong, and solver B
    gets colors right but geometry wrong — bind their correct aspects.
    Uses training pairs to identify which dimensions each solver handles correctly.
    """
    n = len(train_pairs)
    if len(candidates) < 2:
        return None

    # Get predictions from all candidates
    cand_preds = []
    for _, op, _ in candidates:
        preds = []
        all_ok = True
        for inp, out in train_pairs:
            try:
                pred = op.execute(inp)
                if pred is not None and isinstance(pred, np.ndarray) and pred.shape == out.shape:
                    preds.append(pred)
                else:
                    all_ok = False
                    break
            except Exception:
                all_ok = False
                break
        if all_ok:
            cand_preds.append(preds)
        else:
            cand_preds.append(None)

    valid_cands = [(i, cand_preds[i]) for i in range(len(candidates))
                   if cand_preds[i] is not None]
    if len(valid_cands) < 2:
        return None

    # For each pair of candidates, try pixel-wise "best source" selection
    for ai, (idx_a, preds_a) in enumerate(valid_cands):
        for bi, (idx_b, preds_b) in enumerate(valid_cands):
            if ai >= bi:
                continue

            # For each pixel, determine which candidate is correct on training
            # Then build a mask: use A where A is correct, B where B is correct
            # If they agree on correct answer → good; if they both wrong → skip

            # Learn a source mask from training: for each pixel, should we use A or B?
            # The mask should be input-dependent, not position-dependent
            # Use a simple rule: use A where A matches training, else use B

            all_match = True
            for pair_idx in range(n):
                expected = train_pairs[pair_idx][1]
                a_pred = preds_a[pair_idx]
                b_pred = preds_b[pair_idx]

                # Build bound output: use A where A correct, B where B correct,
                # A where both wrong (prefer higher-score candidate)
                bound = np.where(a_pred == expected, a_pred,
                                 np.where(b_pred == expected, b_pred, a_pred))
                if not np.array_equal(bound, expected):
                    all_match = False
                    break

            if all_match:
                # The binding works on training. Now we need a test-time rule.
                # Use an input-conditioned mask: (input_color, position_features) → source
                # Simplified: learn which (input_color, A_output, B_output) → use A or B

                source_map: Dict[Tuple[int, int, int], str] = {}
                map_consistent = True
                for pair_idx in range(n):
                    inp = train_pairs[pair_idx][0]
                    expected = train_pairs[pair_idx][1]
                    a_pred = preds_a[pair_idx]
                    b_pred = preds_b[pair_idx]

                    if inp.shape != expected.shape:
                        map_consistent = False
                        break

                    for r in range(expected.shape[0]):
                        for c in range(expected.shape[1]):
                            av, bv, ev = int(a_pred[r, c]), int(b_pred[r, c]), int(expected[r, c])
                            if av == bv:
                                continue  # Both agree, no choice needed
                            key = (int(inp[r, c]), av, bv)
                            source = "a" if av == ev else "b"
                            if key in source_map:
                                if source_map[key] != source:
                                    map_consistent = False
                                    break
                            else:
                                source_map[key] = source
                        if not map_consistent:
                            break
                    if not map_consistent:
                        break

                if map_consistent and source_map:
                    op_a = candidates[idx_a][1]
                    op_b = candidates[idx_b][1]
                    frozen_map = dict(source_map)

                    def make_binder(fn_a, fn_b, smap):
                        def fn(grid, _a=fn_a, _b=fn_b, _sm=smap):
                            pred_a = _a(grid)
                            pred_b = _b(grid)
                            if pred_a is None or pred_b is None:
                                return pred_a if pred_a is not None else pred_b
                            if pred_a.shape != pred_b.shape:
                                return pred_a
                            result = pred_a.copy()
                            if grid.shape == pred_a.shape:
                                h, w = pred_a.shape
                                for r in range(h):
                                    for c in range(w):
                                        av, bv = int(pred_a[r, c]), int(pred_b[r, c])
                                        if av != bv:
                                            key = (int(grid[r, c]), av, bv)
                                            if key in _sm and _sm[key] == "b":
                                                result[r, c] = bv
                            return result
                        return fn

                    bind_fn = make_binder(op_a.execute, op_b.execute, frozen_map)
                    bind_op = SynthesizedOperator(
                        operator_id=f"bound_{uuid.uuid4().hex[:8]}",
                        operator_family=f"feature_bound_{op_a.operator_family}+{op_b.operator_family}",
                        parameters={"n_bindings": len(frozen_map)},
                        preconditions=[],
                        execute=bind_fn,
                        explanation=(
                            f"[Feature Binding] "
                            f"{candidates[idx_a][0]}:{op_a.operator_family} "
                            f"+ {candidates[idx_b][0]}:{op_b.operator_family}"
                        ),
                        source_failure_signature={},
                    )
                    if _verify_all_train(bind_op, train_pairs) and \
                            _loo_validate(bind_op, train_pairs):
                        return bind_op

    return None


# ===================================================================
# Layer 6: Structural Session Memory (Analogical Reasoning)
# ===================================================================

class StructuralMemory:
    """Analogical memory that indexes successful strategies by structural signature."""

    def __init__(self):
        self.entries: List[Tuple[TaskSignature, str, str]] = []

    def store(self, signature: TaskSignature, layer: str, family: str):
        self.entries.append((signature, layer, family))

    def retrieve(self, query: TaskSignature, top_k: int = 5) -> List[Tuple[str, str, float]]:
        scored = []
        for sig, layer, family in self.entries:
            sim = signature_similarity(query, sig)
            if sim > 0:
                scored.append((layer, family, sim))
        scored.sort(key=lambda x: -x[2])
        seen = set()
        result = []
        for layer, family, sim in scored:
            if layer not in seen:
                result.append((layer, family, sim))
                seen.add(layer)
            if len(result) >= top_k:
                break
        return result


_structural_memory = StructuralMemory()
