"""Hypothesis-Driven Reasoning Engine.

Instead of enumerating programs and checking if they work, this engine
reasons like a human: perceive what changed, form hypotheses about WHY
it changed, verify each hypothesis against all examples, then compile
the verified hypothesis into a precise executable program.

This is fundamentally different from:
  - DSL search (enumerates programs, hopes one works)
  - Template matching (checks if known patterns apply)
  - LLM generation (generates code, can't verify precisely)

Architecture:
  1. PERCEIVE: extract objects, compute properties, match I/O correspondences
  2. HYPOTHESIZE: generate candidate explanations at multiple abstraction levels
  3. VERIFY: check every hypothesis against every training pair
  4. COMPILE: turn verified hypothesis into executable function

The hypothesis types cover the major unsolved ARC categories:
  - ObjectConditionalHypothesis: "objects with property P get transform T"
    (covers object_recolor=111, object_movement=67, filter=40 tasks)
  - DecompositionHypothesis: "grid decomposes into regions, rule per region"
    (covers fill=251, complex=225 tasks)
  - SymmetryCompletionHypothesis: "output completes a symmetry pattern"
    (covers fill tasks involving pattern continuation)
  - RelationalHypothesis: "transform depends on relationship between objects"
    (covers complex multi-object tasks)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


# ---------------------------------------------------------------------------
# Object extraction + property computation (reuses reasoning_engine infra)
# ---------------------------------------------------------------------------

def _extract_objects(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Extract objects as connected components with rich properties."""
    try:
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _add_relational_properties,
        )
        objs = _extract_objects_with_properties(grid, bg=bg)
        _add_relational_properties(objs, grid)
        return objs
    except Exception:
        return _extract_objects_simple(grid, bg)


def _extract_objects_simple(grid: np.ndarray, bg: int = 0) -> List[Dict[str, Any]]:
    """Fallback: simple object extraction without relational properties."""
    objs = []
    for color in range(1, 10):
        mask = grid == color
        if not mask.any():
            continue
        labeled, n = ndlabel(mask)
        for comp_id in range(1, n + 1):
            comp = labeled == comp_id
            rows, cols = np.where(comp)
            objs.append({
                "mask": comp,
                "color": color,
                "primary_color": color,
                "area": int(comp.sum()),
                "bbox": (rows.min(), cols.min(), rows.max(), cols.max()),
                "center_r": float(rows.mean()),
                "center_c": float(cols.mean()),
                "bbox_h": int(rows.max() - rows.min() + 1),
                "bbox_w": int(cols.max() - cols.min() + 1),
                "touches_boundary": bool(
                    rows.min() == 0 or rows.max() == grid.shape[0] - 1
                    or cols.min() == 0 or cols.max() == grid.shape[1] - 1
                ),
            })
    objs.sort(key=lambda o: -o["area"])
    for i, o in enumerate(objs):
        o["is_largest"] = (i == 0)
        o["is_smallest"] = (i == len(objs) - 1)
        o["size_rank"] = i
    return objs


def _get_prop(obj: Dict, name: str) -> Any:
    """Get property value, with derived predicate fallback."""
    try:
        from reasoning_project.reasoning_engine import _get_property_value
        return _get_property_value(obj, name)
    except Exception:
        return obj.get(name, False)


def _all_props() -> List[str]:
    """Get all available property names."""
    try:
        from reasoning_project.reasoning_engine import _all_property_names
        return _all_property_names()
    except Exception:
        return [
            "is_largest", "is_smallest", "touches_boundary",
            "in_top_half", "in_left_half", "is_unique_color",
        ]


# ---------------------------------------------------------------------------
# Object correspondence between input and output
# ---------------------------------------------------------------------------

@dataclass
class ObjectMatch:
    """A matched input→output object pair with its transform."""
    inp_idx: int
    out_idx: int
    transform: str       # identical, recolored, moved, resized, disappeared, appeared
    color_change: Optional[Tuple[int, int]] = None  # (old_color, new_color)
    translation: Optional[Tuple[int, int]] = None    # (dr, dc)
    size_ratio: Optional[float] = None


def _match_objects_io(
    inp_objs: List[Dict], out_objs: List[Dict],
    inp_grid: np.ndarray, out_grid: np.ndarray,
) -> List[ObjectMatch]:
    """Match input objects to output objects by shape/position similarity."""
    if not inp_objs or not out_objs:
        return []

    matches = []
    used_out = set()

    for i, io in enumerate(inp_objs):
        best_j, best_score = -1, -1.0
        for j, oo in enumerate(out_objs):
            if j in used_out:
                continue
            score = _match_score(io, oo, inp_grid, out_grid)
            if score > best_score:
                best_score = score
                best_j = j
        if best_j >= 0 and best_score > 0.3:
            used_out.add(best_j)
            transform, color_change, translation = _classify_match(
                io, out_objs[best_j], inp_grid, out_grid
            )
            matches.append(ObjectMatch(
                inp_idx=i, out_idx=best_j, transform=transform,
                color_change=color_change, translation=translation,
            ))
        else:
            matches.append(ObjectMatch(inp_idx=i, out_idx=-1, transform="disappeared"))

    for j in range(len(out_objs)):
        if j not in used_out:
            matches.append(ObjectMatch(inp_idx=-1, out_idx=j, transform="appeared"))

    return matches


def _match_score(io: Dict, oo: Dict, ig: np.ndarray, og: np.ndarray) -> float:
    """Score how well two objects match (0-1)."""
    shape_sim = 0.0
    if io["bbox_h"] == oo.get("bbox_h", -1) and io["bbox_w"] == oo.get("bbox_w", -1):
        i_local = ig[io["mask"]] if isinstance(io["mask"], np.ndarray) else np.array([])
        o_local = og[oo["mask"]] if isinstance(oo["mask"], np.ndarray) else np.array([])
        if len(i_local) == len(o_local) and len(i_local) > 0:
            shape_sim = float(np.sum(i_local != 0) == np.sum(o_local != 0)) * 0.3
            shape_sim += 0.7 if io["area"] == oo.get("area", -1) else 0

    pos_sim = 0.0
    ir, ic = io.get("center_r", 0), io.get("center_c", 0)
    or_, oc = oo.get("center_r", 0), oo.get("center_c", 0)
    dist = ((ir - or_) ** 2 + (ic - oc) ** 2) ** 0.5
    max_dist = max(ig.shape) * 1.5
    pos_sim = max(0, 1 - dist / max_dist)

    color_sim = 1.0 if io.get("primary_color") == oo.get("primary_color") else 0.3
    area_sim = min(io["area"], oo.get("area", 1)) / max(io["area"], oo.get("area", 1))

    return 0.3 * shape_sim + 0.3 * pos_sim + 0.2 * color_sim + 0.2 * area_sim


def _classify_match(
    io: Dict, oo: Dict, ig: np.ndarray, og: np.ndarray,
) -> Tuple[str, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    """Classify the transform between matched objects."""
    ic, oc = io.get("primary_color"), oo.get("primary_color")
    ir, ic_ = io.get("center_r", 0), io.get("center_c", 0)
    or_, oc_ = oo.get("center_r", 0), oo.get("center_c", 0)

    same_pos = abs(ir - or_) < 0.5 and abs(ic_ - oc_) < 0.5
    same_color = ic == oc

    color_change = None if same_color else (ic, oc)
    translation = None if same_pos else (int(round(or_ - ir)), int(round(oc_ - ic_)))

    if same_pos and same_color:
        return "identical", None, None
    elif same_pos and not same_color:
        return "recolored", color_change, None
    elif not same_pos and same_color:
        return "moved", None, translation
    else:
        return "moved_recolored", color_change, translation


# ---------------------------------------------------------------------------
# Hypothesis types
# ---------------------------------------------------------------------------

@dataclass
class Hypothesis:
    """An explanation for why the transformation happens."""
    hypothesis_type: str
    description: str
    discriminant_property: Optional[str] = None
    transform_rule: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    execute: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Level 1: Object-Conditional Hypotheses
# "Objects with property P get transform T, others get transform U"
# ---------------------------------------------------------------------------

def _generate_object_conditional_hypotheses(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Generate hypotheses: property P discriminates which objects get which transform."""
    hypotheses = []

    all_pair_analyses = []
    for inp, out in train_pairs:
        if inp.shape != out.shape:
            continue
        inp_objs = _extract_objects(inp)
        out_objs = _extract_objects(out)
        matches = _match_objects_io(inp_objs, out_objs, inp, out)
        all_pair_analyses.append((inp_objs, out_objs, matches, inp, out))

    if not all_pair_analyses:
        return []

    # --- Type A: Property predicts RECOLOR ---
    hypotheses.extend(_hypothesize_conditional_recolor(all_pair_analyses, train_pairs))

    # --- Type B: Property predicts KEEP vs REMOVE ---
    hypotheses.extend(_hypothesize_conditional_filter(all_pair_analyses, train_pairs))

    # --- Type C: Property predicts MOVEMENT ---
    hypotheses.extend(_hypothesize_conditional_movement(all_pair_analyses, train_pairs))

    # --- Type D: Property determines OUTPUT COLOR ---
    hypotheses.extend(_hypothesize_property_to_color(all_pair_analyses, train_pairs))

    return hypotheses


def _hypothesize_conditional_recolor(
    analyses: List, train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """If property P → recolor to C1, not P → keep original color."""
    results = []
    props = _all_props()

    for prop in props:
        consistent = True
        recolor_map_true = {}   # prop=True → what color?
        recolor_map_false = {}  # prop=False → what color?

        for inp_objs, out_objs, matches, inp, out in analyses:
            for m in matches:
                if m.inp_idx < 0 or m.out_idx < 0:
                    continue
                obj = inp_objs[m.inp_idx]
                pval = _get_prop(obj, prop)
                out_obj = out_objs[m.out_idx]
                out_color = out_obj.get("primary_color")
                inp_color = obj.get("primary_color")

                if pval:
                    if out_color not in recolor_map_true:
                        recolor_map_true[out_color] = 0
                    recolor_map_true[out_color] += 1
                else:
                    if out_color not in recolor_map_false:
                        recolor_map_false[out_color] = 0
                    recolor_map_false[out_color] += 1

        if not recolor_map_true or not recolor_map_false:
            continue

        true_color = max(recolor_map_true, key=recolor_map_true.get)
        false_color = max(recolor_map_false, key=recolor_map_false.get)

        if true_color == false_color:
            continue

        total_true = sum(recolor_map_true.values())
        total_false = sum(recolor_map_false.values())
        purity_true = recolor_map_true[true_color] / total_true
        purity_false = recolor_map_false[false_color] / total_false

        if purity_true < 0.9 or purity_false < 0.9:
            continue

        def make_fn(p, tc, fc, bg=0):
            def fn(grid, _p=p, _tc=tc, _fc=fc, _bg=bg):
                objs = _extract_objects(grid, bg=_bg)
                out = grid.copy()
                for obj in objs:
                    pval = _get_prop(obj, _p)
                    target_color = _tc if pval else _fc
                    out[obj["mask"]] = target_color
                return out
            return fn

        fn = make_fn(prop, true_color, false_color)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="conditional_recolor",
                description=f"If {prop} → color {true_color}, else → color {false_color}",
                discriminant_property=prop,
                transform_rule={"true_color": true_color, "false_color": false_color},
                confidence=min(purity_true, purity_false),
                execute=fn,
            ))

    return results


def _hypothesize_conditional_filter(
    analyses: List, train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """If property P → keep object, not P → remove (set to bg)."""
    results = []
    props = _all_props()

    for prop in props:
        consistent = True
        for inp_objs, out_objs, matches, inp, out in analyses:
            for m in matches:
                if m.inp_idx < 0:
                    continue
                obj = inp_objs[m.inp_idx]
                pval = _get_prop(obj, prop)

                if m.transform == "disappeared":
                    if pval:
                        consistent = False
                        break
                elif m.out_idx >= 0:
                    if not pval:
                        out_pixels = out[obj["mask"]]
                        if np.all(out_pixels == 0):
                            pass
                        else:
                            consistent = False
                            break
            if not consistent:
                break

        if not consistent:
            continue

        has_kept = any(
            any(m.out_idx >= 0 and _get_prop(io[m.inp_idx], prop)
                for m in matches if m.inp_idx >= 0)
            for io, _, matches, _, _ in analyses
        )
        has_removed = any(
            any((m.transform == "disappeared" or (m.inp_idx >= 0 and not _get_prop(io[m.inp_idx], prop)))
                for m in matches if m.inp_idx >= 0)
            for io, _, matches, _, _ in analyses
        )

        if not has_kept or not has_removed:
            continue

        for keep_true in [True, False]:
            def make_fn(p, kt, bg=0):
                def fn(grid, _p=p, _kt=kt, _bg=bg):
                    objs = _extract_objects(grid, bg=_bg)
                    out = np.full_like(grid, _bg)
                    for obj in objs:
                        pval = _get_prop(obj, _p)
                        if (pval and _kt) or (not pval and not _kt):
                            out[obj["mask"]] = grid[obj["mask"]]
                    return out
                return fn

            fn = make_fn(prop, keep_true)
            if _verify_on_train(fn, train_pairs):
                direction = "keep" if keep_true else "remove"
                results.append(Hypothesis(
                    hypothesis_type="conditional_filter",
                    description=f"{direction} objects where {prop}",
                    discriminant_property=prop,
                    transform_rule={"keep_when_true": keep_true},
                    confidence=1.0,
                    execute=fn,
                ))

    return results


def _hypothesize_conditional_movement(
    analyses: List, train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """If property P → move by (dr,dc), not P → stay."""
    results = []

    moved_translations = {}
    for inp_objs, out_objs, matches, inp, out in analyses:
        for m in matches:
            if m.translation and m.inp_idx >= 0:
                t = m.translation
                moved_translations[t] = moved_translations.get(t, 0) + 1

    if not moved_translations:
        return []

    common_translations = sorted(moved_translations.items(), key=lambda x: -x[1])[:5]

    props = _all_props()
    for (dr, dc), _ in common_translations:
        for prop in props:
            consistent = True
            for inp_objs, out_objs, matches, inp, out in analyses:
                for m in matches:
                    if m.inp_idx < 0:
                        continue
                    obj = inp_objs[m.inp_idx]
                    pval = _get_prop(obj, prop)
                    if pval:
                        if m.translation != (dr, dc) and m.translation is not None:
                            consistent = False
                            break
                    else:
                        if m.translation == (dr, dc):
                            consistent = False
                            break
                if not consistent:
                    break

            if not consistent:
                continue

            def make_fn(p, r, c, bg=0):
                def fn(grid, _p=p, _dr=r, _dc=c, _bg=bg):
                    objs = _extract_objects(grid, bg=_bg)
                    out = np.full_like(grid, _bg)
                    H, W = grid.shape
                    for obj in objs:
                        pval = _get_prop(obj, _p)
                        rows, cols = np.where(obj["mask"])
                        if pval:
                            nr = np.clip(rows + _dr, 0, H - 1)
                            nc = np.clip(cols + _dc, 0, W - 1)
                            out[nr, nc] = grid[rows, cols]
                        else:
                            out[rows, cols] = grid[rows, cols]
                    return out
                return fn

            fn = make_fn(prop, dr, dc)
            if _verify_on_train(fn, train_pairs):
                results.append(Hypothesis(
                    hypothesis_type="conditional_movement",
                    description=f"If {prop} → move by ({dr},{dc}), else stay",
                    discriminant_property=prop,
                    transform_rule={"dr": dr, "dc": dc},
                    confidence=1.0,
                    execute=fn,
                ))

    return results


def _hypothesize_property_to_color(
    analyses: List, train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Each object's output color is determined by a property value.

    E.g., the largest object → color 1, 2nd largest → color 2, etc.
    Or: objects touching border → color 3, interior → color 7.
    """
    results = []

    for rank_prop in ["size_rank", "color"]:
        color_assignments = {}
        consistent = True

        for inp_objs, out_objs, matches, inp, out in analyses:
            for m in matches:
                if m.inp_idx < 0 or m.out_idx < 0:
                    continue
                obj = inp_objs[m.inp_idx]
                out_obj = out_objs[m.out_idx]
                rank = obj.get(rank_prop, m.inp_idx)
                out_color = out_obj.get("primary_color")

                if rank in color_assignments:
                    if color_assignments[rank] != out_color:
                        consistent = False
                        break
                else:
                    color_assignments[rank] = out_color
            if not consistent:
                break

        if not consistent or len(color_assignments) < 2:
            continue

        def make_fn(rp, ca, bg=0):
            def fn(grid, _rp=rp, _ca=ca, _bg=bg):
                objs = _extract_objects(grid, bg=_bg)
                out = grid.copy()
                for obj in objs:
                    rank = obj.get(_rp, 0)
                    if rank in _ca:
                        out[obj["mask"]] = _ca[rank]
                return out
            return fn

        fn = make_fn(rank_prop, color_assignments)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="property_to_color",
                description=f"Color determined by {rank_prop}: {color_assignments}",
                discriminant_property=rank_prop,
                transform_rule={"mapping": color_assignments},
                confidence=1.0,
                execute=fn,
            ))

    return results


# ---------------------------------------------------------------------------
# Level 2: Grid Decomposition Hypotheses
# "Grid decomposes into regions, each gets independent treatment"
# ---------------------------------------------------------------------------

def _generate_decomposition_hypotheses(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Generate hypotheses about grid decomposition."""
    results = []
    results.extend(_hypothesize_separator_decomposition(train_pairs))
    results.extend(_hypothesize_quadrant_rule(train_pairs))
    return results


def _hypothesize_separator_decomposition(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """If a single-color row/column divides the grid, treat each half independently."""
    results = []

    for inp, out in train_pairs[:1]:
        if inp.shape != out.shape:
            continue
        H, W = inp.shape

        for r in range(1, H - 1):
            row = inp[r, :]
            if len(set(row)) == 1 and row[0] != 0:
                top_in = inp[:r, :]
                bot_in = inp[r + 1:, :]
                top_out = out[:r, :]
                bot_out = out[r + 1:, :]

                if np.array_equal(top_in, top_out) and not np.array_equal(bot_in, bot_out):
                    if np.array_equal(bot_out, top_in[:bot_out.shape[0], :bot_out.shape[1]]):
                        def make_fn(sep_row):
                            def fn(grid, _r=sep_row):
                                H2 = grid.shape[0]
                                top = grid[:_r, :]
                                result = grid.copy()
                                bot_h = H2 - _r - 1
                                result[_r + 1:_r + 1 + min(bot_h, top.shape[0]), :] = top[:min(bot_h, top.shape[0]), :]
                                return result
                            return fn
                        fn = make_fn(r)
                        if _verify_on_train(fn, train_pairs):
                            results.append(Hypothesis(
                                hypothesis_type="separator_copy",
                                description=f"Copy top half to bottom across separator at row {r}",
                                confidence=1.0,
                                execute=fn,
                            ))

    return results


def _hypothesize_quadrant_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Output is constructed by combining/comparing grid quadrants."""
    results = []

    for inp, out in train_pairs[:1]:
        H, W = inp.shape
        oH, oW = out.shape

        if H % 2 != 0 or W % 2 != 0:
            continue
        hH, hW = H // 2, W // 2

        if oH != hH or oW != hW:
            continue

        q_tl = inp[:hH, :hW]
        q_tr = inp[:hH, hW:]
        q_bl = inp[hH:, :hW]
        q_br = inp[hH:, hW:]

        for op_name, op_fn in [
            ("AND", lambda a, b: np.where((a != 0) & (b != 0), a, 0)),
            ("OR", lambda a, b: np.where(a != 0, a, b)),
            ("XOR", lambda a, b: np.where((a != 0) ^ (b != 0), np.where(a != 0, a, b), 0)),
            ("DIFF", lambda a, b: np.where((a != 0) & (b == 0), a, 0)),
        ]:
            for q1_name, q1, q2_name, q2 in [
                ("TL", q_tl, "BR", q_br), ("TL", q_tl, "TR", q_tr),
                ("TL", q_tl, "BL", q_bl), ("TR", q_tr, "BL", q_bl),
                ("TR", q_tr, "BR", q_br), ("BL", q_bl, "BR", q_br),
            ]:
                if q1.shape != q2.shape or q1.shape != out.shape:
                    continue
                try:
                    result = op_fn(q1, q2)
                    if np.array_equal(result, out):
                        def make_fn(qn1, qn2, op, hh, hw):
                            quad_map = {"TL": (0, 0), "TR": (0, hw), "BL": (hh, 0), "BR": (hh, hw)}
                            r1, c1 = quad_map[qn1]
                            r2, c2 = quad_map[qn2]

                            def fn(grid, _r1=r1, _c1=c1, _r2=r2, _c2=c2, _op=op, _hh=hh, _hw=hw):
                                a = grid[_r1:_r1 + _hh, _c1:_c1 + _hw]
                                b = grid[_r2:_r2 + _hh, _c2:_c2 + _hw]
                                return _op(a, b)
                            return fn

                        fn = make_fn(q1_name, q2_name, op_fn, hH, hW)
                        if _verify_on_train(fn, train_pairs):
                            results.append(Hypothesis(
                                hypothesis_type="quadrant_op",
                                description=f"Output = {q1_name} {op_name} {q2_name}",
                                confidence=1.0,
                                execute=fn,
                            ))
                except Exception:
                    continue

    return results


# ---------------------------------------------------------------------------
# Level 3: Symmetry Completion Hypotheses
# "Output completes a partial symmetry in the input"
# ---------------------------------------------------------------------------

def _generate_symmetry_hypotheses(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Generate hypotheses about symmetry completion/enforcement."""
    results = []

    for sym_type in ["horizontal", "vertical", "both"]:
        def make_fn(st):
            def fn(grid, _st=st):
                H, W = grid.shape
                out = grid.copy()
                if _st == "horizontal":
                    for r in range(H):
                        for c in range(W // 2):
                            mc = W - 1 - c
                            if out[r, c] == 0 and out[r, mc] != 0:
                                out[r, c] = out[r, mc]
                            elif out[r, mc] == 0 and out[r, c] != 0:
                                out[r, mc] = out[r, c]
                elif _st == "vertical":
                    for r in range(H // 2):
                        for c in range(W):
                            mr = H - 1 - r
                            if out[r, c] == 0 and out[mr, c] != 0:
                                out[r, c] = out[mr, c]
                            elif out[mr, c] == 0 and out[r, c] != 0:
                                out[mr, c] = out[r, c]
                elif _st == "both":
                    for r in range(H):
                        for c in range(W):
                            mr, mc = H - 1 - r, W - 1 - c
                            candidates = [out[r, c], out[r, mc], out[mr, c], out[mr, mc]]
                            nonzero = [v for v in candidates if v != 0]
                            if nonzero and out[r, c] == 0:
                                out[r, c] = nonzero[0]
                return out
            return fn

        fn = make_fn(sym_type)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="symmetry_completion",
                description=f"Complete {sym_type} symmetry (fill bg from mirror)",
                confidence=1.0,
                execute=fn,
            ))

    for sym_type in ["horizontal", "vertical"]:
        def make_force_fn(st):
            def fn(grid, _st=st):
                H, W = grid.shape
                out = grid.copy()
                if _st == "horizontal":
                    for r in range(H):
                        for c in range(W // 2):
                            out[r, W - 1 - c] = out[r, c]
                elif _st == "vertical":
                    for r in range(H // 2):
                        out[H - 1 - r, :] = out[r, :]
                return out
            return fn

        fn = make_force_fn(sym_type)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="symmetry_force",
                description=f"Force {sym_type} symmetry (overwrite from mirror)",
                confidence=1.0,
                execute=fn,
            ))

    return results


# ---------------------------------------------------------------------------
# Level 4: Pattern-based fill hypotheses
# "Fill bg cells using local context rules"
# ---------------------------------------------------------------------------

def _generate_fill_hypotheses(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Generate hypotheses about filling background cells."""
    results = []
    results.extend(_hypothesize_majority_neighbor_fill(train_pairs))
    results.extend(_hypothesize_row_col_fill(train_pairs))
    results.extend(_hypothesize_flood_fill_variants(train_pairs))
    return results


def _hypothesize_majority_neighbor_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Fill each bg cell with the most common non-bg neighbor color."""
    results = []

    for n_passes in [1, 2, 3]:
        def make_fn(np_):
            def fn(grid, _np=np_):
                out = grid.copy()
                H, W = out.shape
                for _ in range(_np):
                    changed = False
                    new = out.copy()
                    for r in range(H):
                        for c in range(W):
                            if out[r, c] != 0:
                                continue
                            neighbors = []
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < H and 0 <= nc < W and out[nr, nc] != 0:
                                    neighbors.append(out[nr, nc])
                            if neighbors:
                                from collections import Counter
                                new[r, c] = Counter(neighbors).most_common(1)[0][0]
                                changed = True
                    out = new
                    if not changed:
                        break
                return out
            return fn

        fn = make_fn(n_passes)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="neighbor_fill",
                description=f"Fill bg with majority neighbor color ({n_passes} passes)",
                confidence=1.0,
                execute=fn,
            ))

    return results


def _hypothesize_row_col_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Fill each bg cell with the unique non-bg color in its row or column."""
    results = []

    for mode in ["row", "col", "row_or_col"]:
        def make_fn(m):
            def fn(grid, _m=m):
                out = grid.copy()
                H, W = grid.shape
                for r in range(H):
                    for c in range(W):
                        if out[r, c] != 0:
                            continue
                        if _m == "row" or _m == "row_or_col":
                            row_colors = set(grid[r, :]) - {0}
                            if len(row_colors) == 1:
                                out[r, c] = row_colors.pop()
                                continue
                        if _m == "col" or _m == "row_or_col":
                            col_colors = set(grid[:, c]) - {0}
                            if len(col_colors) == 1:
                                out[r, c] = col_colors.pop()
                return out
            return fn

        fn = make_fn(mode)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="row_col_fill",
                description=f"Fill bg from unique {mode} color",
                confidence=1.0,
                execute=fn,
            ))

    return results


def _hypothesize_flood_fill_variants(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Fill enclosed regions with the color of their enclosing object."""
    results = []

    def make_fn():
        def fn(grid):
            out = grid.copy()
            H, W = grid.shape
            bg_mask = grid == 0
            labeled, n = ndlabel(bg_mask)
            for comp_id in range(1, n + 1):
                comp = labeled == comp_id
                rows, cols = np.where(comp)
                if rows.min() == 0 or rows.max() == H - 1 or cols.min() == 0 or cols.max() == W - 1:
                    continue
                border_colors = set()
                for r, c in zip(rows, cols):
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < H and 0 <= nc < W and grid[nr, nc] != 0:
                            border_colors.add(grid[nr, nc])
                if len(border_colors) == 1:
                    out[comp] = border_colors.pop()
            return out
        return fn

    fn = make_fn()
    if _verify_on_train(fn, train_pairs):
        results.append(Hypothesis(
            hypothesis_type="flood_fill_enclosed_by_color",
            description="Fill enclosed bg regions with their enclosing color",
            confidence=1.0,
            execute=fn,
        ))

    return results


# ---------------------------------------------------------------------------
# Level 5: Relational Hypotheses
# "Transform depends on relationship between objects"
# ---------------------------------------------------------------------------

def _generate_relational_hypotheses(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Generate hypotheses about inter-object relationships."""
    results = []
    results.extend(_hypothesize_largest_as_template(train_pairs))
    results.extend(_hypothesize_overlay_objects(train_pairs))
    results.extend(_hypothesize_learned_pixel_rule(train_pairs))
    results.extend(_hypothesize_input_output_color_correspondence(train_pairs))
    results.extend(_hypothesize_object_count_output(train_pairs))
    results.extend(_hypothesize_cross_row_col_intersection(train_pairs))
    return results


def _hypothesize_largest_as_template(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """The largest object acts as a template/mask for smaller objects."""
    results = []

    def make_fn(bg=0):
        def fn(grid, _bg=bg):
            objs = _extract_objects(grid, bg=_bg)
            if len(objs) < 2:
                return grid.copy()
            largest = objs[0]
            out = grid.copy()
            for obj in objs[1:]:
                r0, c0 = obj.get("center_r", 0), obj.get("center_c", 0)
                lr0, lc0 = largest.get("center_r", 0), largest.get("center_c", 0)
                lmask = largest["mask"]
                l_rows, l_cols = np.where(lmask)
                for lr, lc in zip(l_rows, l_cols):
                    tr = int(lr - lr0 + r0)
                    tc = int(lc - lc0 + c0)
                    if 0 <= tr < grid.shape[0] and 0 <= tc < grid.shape[1]:
                        if grid[tr, tc] == _bg:
                            out[tr, tc] = obj.get("primary_color", 1)
            return out
        return fn

    fn = make_fn()
    if _verify_on_train(fn, train_pairs):
        results.append(Hypothesis(
            hypothesis_type="largest_as_template",
            description="Stamp largest object's shape at each smaller object's position",
            confidence=1.0,
            execute=fn,
        ))

    return results


def _hypothesize_overlay_objects(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Overlay all objects on top of each other (union/intersection)."""
    results = []

    for mode in ["union", "intersection"]:
        def make_fn(m, bg=0):
            def fn(grid, _m=m, _bg=bg):
                objs = _extract_objects(grid, bg=_bg)
                if len(objs) < 2:
                    return grid.copy()
                first = objs[0]
                r0, c0, r1, c1 = first["bbox"]
                h, w = r1 - r0 + 1, c1 - c0 + 1
                canvas = np.zeros((h, w), dtype=grid.dtype)
                for obj in objs:
                    or0, oc0 = obj["bbox"][0], obj["bbox"][1]
                    oh, ow = obj["bbox_h"], obj["bbox_w"]
                    local = grid[or0:or0 + oh, oc0:oc0 + ow]
                    paste_h = min(oh, h)
                    paste_w = min(ow, w)
                    if _m == "union":
                        for r in range(paste_h):
                            for c in range(paste_w):
                                if local[r, c] != _bg:
                                    canvas[r, c] = local[r, c]
                    elif _m == "intersection":
                        if obj is first:
                            canvas[:paste_h, :paste_w] = local[:paste_h, :paste_w]
                        else:
                            for r in range(paste_h):
                                for c in range(paste_w):
                                    if local[r, c] == _bg:
                                        canvas[r, c] = _bg
                return canvas
            return fn

        fn = make_fn(mode)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="overlay",
                description=f"Overlay objects ({mode})",
                confidence=1.0,
                execute=fn,
            ))

    return results


# ---------------------------------------------------------------------------
# Level 6: Learned Rule Hypotheses (genuine reasoning)
# These LEARN rules from training examples rather than testing fixed patterns
# ---------------------------------------------------------------------------

def _hypothesize_learned_pixel_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Learn a pixel-level rule from training by examining local context.

    For each pixel that changed, collect its local context (self + neighbors)
    and the output value. If the mapping from context → output is consistent
    across all training pairs, we've learned a local rule.

    This is genuine reasoning: the rule is DISCOVERED from examples, not
    hardcoded. It can express arbitrary local transformations.
    """
    results = []

    for inp0, out0 in train_pairs[:1]:
        if inp0.shape != out0.shape:
            return results

    H, W = train_pairs[0][0].shape

    for ctx_fn_name, ctx_fn in [
        ("cross_3x3", lambda g, r, c: _get_cross_context(g, r, c)),
        ("color_and_pos", lambda g, r, c: (g[r, c], r % 2, c % 2)),
        ("color_and_neighbors", lambda g, r, c: _get_neighbor_colors(g, r, c)),
    ]:
        rule = {}
        consistent = True

        for inp, out in train_pairs:
            if inp.shape != out.shape:
                consistent = False
                break
            for r in range(inp.shape[0]):
                for c in range(inp.shape[1]):
                    ctx = ctx_fn(inp, r, c)
                    out_val = int(out[r, c])
                    if ctx in rule:
                        if rule[ctx] != out_val:
                            consistent = False
                            break
                    else:
                        rule[ctx] = out_val
                if not consistent:
                    break
            if not consistent:
                break

        if not consistent or not rule:
            continue

        is_identity = all(
            rule.get(ctx_fn(inp, r, c)) == int(inp[r, c])
            for inp, out in train_pairs
            for r in range(inp.shape[0])
            for c in range(inp.shape[1])
        )
        if is_identity:
            continue

        def make_fn(cf, rl):
            def fn(grid, _cf=cf, _rl=rl):
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    for c in range(W):
                        ctx = _cf(grid, r, c)
                        if ctx in _rl:
                            out[r, c] = _rl[ctx]
                return out
            return fn

        fn = make_fn(ctx_fn, rule)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="learned_pixel_rule",
                description=f"Learned local rule ({ctx_fn_name}, {len(rule)} entries)",
                confidence=1.0,
                execute=fn,
            ))

    return results


def _get_cross_context(grid: np.ndarray, r: int, c: int) -> tuple:
    """Get the 5-cell cross context: (self, up, down, left, right)."""
    H, W = grid.shape
    return (
        int(grid[r, c]),
        int(grid[r - 1, c]) if r > 0 else -1,
        int(grid[r + 1, c]) if r < H - 1 else -1,
        int(grid[r, c - 1]) if c > 0 else -1,
        int(grid[r, c + 1]) if c < W - 1 else -1,
    )


def _get_neighbor_colors(grid: np.ndarray, r: int, c: int) -> tuple:
    """Get sorted set of neighbor colors + self color."""
    H, W = grid.shape
    neighbors = set()
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < H and 0 <= nc < W:
            neighbors.add(int(grid[nr, nc]))
    return (int(grid[r, c]), tuple(sorted(neighbors)))


def _hypothesize_input_output_color_correspondence(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Learn: for each input color, what's the corresponding output color?

    Goes beyond simple color_map by also handling position-dependent mappings:
    color C in the top half → color A, color C in the bottom half → color B.
    """
    results = []

    for mode in ["global", "top_bottom", "left_right"]:
        mapping = {}
        consistent = True

        for inp, out in train_pairs:
            if inp.shape != out.shape:
                consistent = False
                break
            H, W = inp.shape
            for r in range(H):
                for c in range(W):
                    ic = int(inp[r, c])
                    oc = int(out[r, c])
                    if mode == "global":
                        key = ic
                    elif mode == "top_bottom":
                        key = (ic, "top" if r < H // 2 else "bottom")
                    elif mode == "left_right":
                        key = (ic, "left" if c < W // 2 else "right")

                    if key in mapping:
                        if mapping[key] != oc:
                            consistent = False
                            break
                    else:
                        mapping[key] = oc
                if not consistent:
                    break
            if not consistent:
                break

        if not consistent or not mapping:
            continue

        is_identity = all(
            mapping.get(int(inp[r, c]) if mode == "global" else (int(inp[r, c]), "top" if r < inp.shape[0] // 2 else "bottom") if mode == "top_bottom" else (int(inp[r, c]), "left" if c < inp.shape[1] // 2 else "right")) == int(inp[r, c])
            for inp, _ in train_pairs
            for r in range(inp.shape[0])
            for c in range(inp.shape[1])
        )
        if is_identity:
            continue

        def make_fn(m, mp):
            def fn(grid, _m=m, _mp=mp):
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    for c in range(W):
                        ic = int(grid[r, c])
                        if _m == "global":
                            key = ic
                        elif _m == "top_bottom":
                            key = (ic, "top" if r < H // 2 else "bottom")
                        elif _m == "left_right":
                            key = (ic, "left" if c < W // 2 else "right")
                        if key in _mp:
                            out[r, c] = _mp[key]
                return out
            return fn

        fn = make_fn(mode, mapping)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="color_correspondence",
                description=f"Learned color mapping ({mode}, {len(mapping)} entries)",
                confidence=1.0,
                execute=fn,
            ))

    return results


def _hypothesize_object_count_output(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Output grid encodes object count/property as a small grid.

    E.g., count objects of each color → output is 1xN grid of counts,
    or output is NxN where N = number of objects.
    """
    results = []

    for inp, out in train_pairs[:1]:
        oH, oW = out.shape
        if oH > 10 or oW > 10:
            continue

        inp_objs = _extract_objects(inp)

        if oH == 1 and oW == len(inp_objs):
            color_list_consistent = True
            for inp2, out2 in train_pairs:
                objs2 = _extract_objects(inp2)
                if out2.shape != (1, len(objs2)):
                    color_list_consistent = False
                    break
                expected = [obj.get("primary_color", 0) for obj in objs2]
                if not np.array_equal(out2[0, :len(expected)], expected):
                    color_list_consistent = False
                    break

            if color_list_consistent:
                def make_fn():
                    def fn(grid):
                        objs = _extract_objects(grid)
                        colors = [obj.get("primary_color", 0) for obj in objs]
                        return np.array([colors], dtype=grid.dtype)
                    return fn
                fn = make_fn()
                if _verify_on_train(fn, train_pairs):
                    results.append(Hypothesis(
                        hypothesis_type="object_count_output",
                        description="Output = list of object colors",
                        confidence=1.0,
                        execute=fn,
                    ))

    return results


def _hypothesize_cross_row_col_intersection(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[Hypothesis]:
    """Output color at (r,c) = f(row_color[r], col_color[c]).

    For grids with colored rows and columns, the output is determined
    by the intersection of the row and column colors. This is a genuine
    reasoning pattern: the system discovers that position encodes two
    independent variables whose interaction determines the output.
    """
    results = []

    for inp, out in train_pairs[:1]:
        if inp.shape != out.shape:
            continue

    intersection_rule = {}
    consistent = True

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            consistent = False
            break
        H, W = inp.shape
        for r in range(H):
            row_colors = set(int(inp[r, c]) for c in range(W)) - {0}
            if len(row_colors) != 1:
                continue
            row_color = row_colors.pop()
            for c in range(W):
                col_colors = set(int(inp[rr, c]) for rr in range(H)) - {0}
                if len(col_colors) != 1:
                    continue
                col_color = col_colors.pop()
                key = (row_color, col_color)
                out_val = int(out[r, c])
                if key in intersection_rule:
                    if intersection_rule[key] != out_val:
                        consistent = False
                        break
                else:
                    intersection_rule[key] = out_val
            if not consistent:
                break
        if not consistent:
            break

    if consistent and len(intersection_rule) >= 2:
        def make_fn(rule):
            def fn(grid, _rule=rule):
                H, W = grid.shape
                out = grid.copy()
                for r in range(H):
                    row_colors = set(int(grid[r, c]) for c in range(W)) - {0}
                    if len(row_colors) != 1:
                        continue
                    rc = row_colors.pop()
                    for c in range(W):
                        col_colors = set(int(grid[rr, c]) for rr in range(H)) - {0}
                        if len(col_colors) != 1:
                            continue
                        cc = col_colors.pop()
                        key = (rc, cc)
                        if key in _rule:
                            out[r, c] = _rule[key]
                return out
            return fn

        fn = make_fn(intersection_rule)
        if _verify_on_train(fn, train_pairs):
            results.append(Hypothesis(
                hypothesis_type="cross_intersection",
                description=f"Output = f(row_color, col_color) with {len(intersection_rule)} rules",
                confidence=1.0,
                execute=fn,
            ))

    return results


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _verify_on_train(
    fn: Callable, train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> bool:
    """Check that fn produces the correct output for ALL training pairs."""
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape:
                return False
            if not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def reason_by_hypothesis(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 30.0,
) -> List[SynthesizedOperator]:
    """Main entry: generate, verify, and compile hypotheses into operators.

    This is the core reasoning function. It generates hypotheses at multiple
    levels of abstraction, verifies each one against all training pairs, and
    returns verified hypotheses as executable operators.
    """
    import time
    start = time.time()

    verified = []

    generators = [
        ("object_conditional", _generate_object_conditional_hypotheses),
        ("decomposition", _generate_decomposition_hypotheses),
        ("symmetry", _generate_symmetry_hypotheses),
        ("fill", _generate_fill_hypotheses),
        ("relational", _generate_relational_hypotheses),
    ]

    for gen_name, gen_fn in generators:
        if time.time() - start > timeout_seconds:
            break
        try:
            hypotheses = gen_fn(train_pairs)
            for h in hypotheses:
                if h.execute is not None:
                    verified.append(SynthesizedOperator(
                        operator_id=f"hyp_{h.hypothesis_type}_{uuid.uuid4().hex[:8]}",
                        operator_family=f"hypothesis_{h.hypothesis_type}",
                        parameters=h.transform_rule or {},
                        preconditions=[],
                        execute=h.execute,
                        explanation=f"[Hypothesis] {h.description}",
                        source_failure_signature={
                            "hypothesis_type": h.hypothesis_type,
                            "discriminant": h.discriminant_property,
                        },
                    ))
        except Exception:
            continue

    seen = set()
    unique = []
    for op in verified:
        key = op.explanation
        if key not in seen:
            seen.add(key)
            unique.append(op)

    return unique
