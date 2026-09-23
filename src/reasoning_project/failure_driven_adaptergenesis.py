"""Failure-driven AdapterGenesis: proposes ViewPrograms based on failure traces.

Instead of blindly trying all views, this module analyzes WHY the default
pipeline failed and proposes ViewPrograms that specifically address those
failure modes. Each proposed view is then paired with the existing operator
search and submitted through the full verification chain.

Architecture:
    failure_trace → failure_signature_classifier → candidate ViewPrograms
    → lift train pairs → run operator search on lifted view → project back
    → submit to ProposalVerifier → log every proposal
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.view_programs import (
    ViewProgram,
    ComposedViewProgram,
    IdentityView,
    CropNonBackgroundView,
    CropBoundingBoxView,
    CropMarkerNeighborhoodView,
    RemoveFrameView,
    ExtractInteriorView,
    SplitColorLayerView,
    ForegroundBackgroundView,
    ObjectGraphView,
    NormalizeObjectBBoxView,
    SymmetryQuotientView,
    RepeatedMotifView,
    LineAnchorView,
    ContainmentGraphView,
    enumerate_view_programs,
)
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    StructuralReasoner,
    ReasoningMemory,
    _extract_objects_with_properties,
    _add_relational_properties,
    _classify_kept_removed,
    _find_discriminative_property_extended,
    _apply_filter,
    _apply_filter_recolor,
    _apply_filter_extract,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop


def classify_failure_signature(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, Any]:
    """Analyze train pairs to classify the structural failure signature.

    Returns a dict of boolean flags indicating which failure patterns are present.
    These flags drive ViewProgram selection.
    """
    sig: Dict[str, Any] = {
        "size_changes": False,
        "output_is_crop": False,
        "output_is_subregion": False,
        "has_frame": False,
        "has_partial_frame": False,
        "largest_object_touches_all_borders": False,
        "wrong_pixels_concentrated_in_one_color": False,
        "objects_repeat_in_tile": False,
        "train_residual_is_mirrored": False,
        "object_role_depends_on_containment": False,
        "objects_need_canonicalization": False,
        "has_line_separators": False,
        "has_markers": False,
        "multi_color_with_layer_structure": False,
        "n_colors": 0,
        "dominant_failure": "unknown",
        "candidate_views": [],
    }

    if not train_pairs:
        return sig

    inp0, out0 = train_pairs[0]

    # Size changes
    size_changes = [inp.shape != out.shape for inp, out in train_pairs]
    sig["size_changes"] = any(size_changes)

    # Output is crop/subregion
    if sig["size_changes"]:
        all_smaller = all(
            out.shape[0] <= inp.shape[0] and out.shape[1] <= inp.shape[1]
            for inp, out in train_pairs
        )
        if all_smaller:
            sig["output_is_crop"] = True
            for inp, out in train_pairs:
                oh, ow = out.shape
                for r in range(inp.shape[0] - oh + 1):
                    for c in range(inp.shape[1] - ow + 1):
                        if np.array_equal(inp[r:r+oh, c:c+ow], out):
                            sig["output_is_subregion"] = True
                            break
                    if sig["output_is_subregion"]:
                        break
                if sig["output_is_subregion"]:
                    break

    # Color analysis
    all_colors = set()
    for inp, _ in train_pairs:
        all_colors.update(inp.flatten().tolist())
    sig["n_colors"] = len(all_colors)
    non_bg_colors = all_colors - {0}
    sig["multi_color_with_layer_structure"] = len(non_bg_colors) >= 3

    # Frame detection
    for inp, out in train_pairs:
        h, w = inp.shape
        if h >= 3 and w >= 3:
            border = np.concatenate([inp[0, :], inp[-1, :], inp[1:-1, 0], inp[1:-1, -1]])
            border_vals = set(border.tolist())
            if len(border_vals) == 1 and border_vals.pop() != 0:
                sig["has_frame"] = True
                break
            from collections import Counter
            bc = Counter(border.tolist())
            if bc:
                most_common_color, most_common_count = bc.most_common(1)[0]
                if most_common_count / len(border) >= 0.7 and most_common_color != 0:
                    sig["has_partial_frame"] = True

    # Largest object touches all borders
    try:
        labeled, n = ndimage.label(inp0 != 0)
        if n >= 1:
            sizes = ndimage.sum(np.ones_like(inp0), labeled, range(1, n + 1))
            largest_label = np.argmax(sizes) + 1
            largest_mask = labeled == largest_label
            rows, cols = np.where(largest_mask)
            if (rows.min() == 0 and rows.max() == inp0.shape[0] - 1
                    and cols.min() == 0 and cols.max() == inp0.shape[1] - 1):
                sig["largest_object_touches_all_borders"] = True
    except Exception:
        pass

    # Wrong pixels concentrated in one color (compare input vs output)
    if not sig["size_changes"]:
        color_diff_counts: Dict[int, int] = {}
        for inp, out in train_pairs:
            diff_mask = inp != out
            if np.any(diff_mask):
                for c in non_bg_colors:
                    color_mask = (inp == c) & diff_mask
                    color_diff_counts[c] = color_diff_counts.get(c, 0) + int(color_mask.sum())
        if color_diff_counts:
            total_diff = sum(color_diff_counts.values())
            for c, cnt in color_diff_counts.items():
                if cnt / max(total_diff, 1) >= 0.8:
                    sig["wrong_pixels_concentrated_in_one_color"] = True
                    sig["concentrated_color"] = c
                    break

    # Tile/motif detection
    for inp, _ in train_pairs:
        h, w = inp.shape
        for th in range(2, min(h // 2 + 1, 10)):
            if h % th != 0:
                continue
            for tw in range(2, min(w // 2 + 1, 10)):
                if w % tw != 0:
                    continue
                tile = inp[:th, :tw]
                is_tiled = True
                for r in range(0, h, th):
                    for c in range(0, w, tw):
                        if not np.array_equal(inp[r:r+th, c:c+tw], tile):
                            is_tiled = False
                            break
                    if not is_tiled:
                        break
                if is_tiled and (h // th > 1 or w // tw > 1):
                    sig["objects_repeat_in_tile"] = True
                    break
            if sig["objects_repeat_in_tile"]:
                break
        if sig["objects_repeat_in_tile"]:
            break

    # Symmetry in residual
    if not sig["size_changes"]:
        for inp, out in train_pairs:
            diff = (inp != out).astype(int)
            if np.any(diff):
                if np.array_equal(diff, diff[::-1, :]) or np.array_equal(diff, diff[:, ::-1]):
                    sig["train_residual_is_mirrored"] = True
                    break

    # Containment detection
    try:
        labeled, n = ndimage.label(inp0 != 0)
        if n >= 2:
            bboxes = ndimage.find_objects(labeled)
            for i in range(n):
                if bboxes[i] is None:
                    continue
                ri, ci = bboxes[i]
                for j in range(n):
                    if i == j or bboxes[j] is None:
                        continue
                    rj, cj = bboxes[j]
                    if (rj.start >= ri.start and rj.stop <= ri.stop
                            and cj.start >= ci.start and cj.stop <= ci.stop):
                        sig["object_role_depends_on_containment"] = True
                        break
                if sig["object_role_depends_on_containment"]:
                    break
    except Exception:
        pass

    # Line separator detection
    for inp, _ in train_pairs:
        h, w = inp.shape
        for r in range(h):
            row_vals = set(inp[r, :].tolist())
            if len(row_vals) == 1 and row_vals.pop() != 0:
                sig["has_line_separators"] = True
                break
        if not sig["has_line_separators"]:
            for c in range(w):
                col_vals = set(inp[:, c].tolist())
                if len(col_vals) == 1 and col_vals.pop() != 0:
                    sig["has_line_separators"] = True
                    break

    # Marker detection (unique single-pixel colors)
    try:
        from collections import Counter
        color_counts = Counter(inp0.flatten().tolist())
        for c, cnt in color_counts.items():
            if c != 0 and cnt == 1:
                sig["has_markers"] = True
                break
    except Exception:
        pass

    # Object canonicalization needed (objects of same shape, different positions)
    try:
        objs = _extract_objects_with_properties(inp0)
        if len(objs) >= 2:
            shapes = []
            for obj in objs:
                r_min, c_min, r_max, c_max = obj["bbox"]
                patch = inp0[r_min:r_max+1, c_min:c_max+1].copy()
                patch[~obj["mask"][r_min:r_max+1, c_min:c_max+1]] = 0
                shapes.append(patch.tobytes() + bytes(patch.shape))
            if len(set(shapes)) < len(shapes):
                sig["objects_need_canonicalization"] = True
    except Exception:
        pass

    # Determine dominant failure and candidate views
    candidates = []

    if sig["has_frame"] or sig["largest_object_touches_all_borders"]:
        candidates.extend(["RemoveFrameView", "ExtractInteriorView"])
        sig["dominant_failure"] = "frame_masking"

    if sig["wrong_pixels_concentrated_in_one_color"]:
        c = sig.get("concentrated_color")
        candidates.append(f"SplitColorLayerView({c})")
        sig["dominant_failure"] = "color_layer_interference"

    if sig["output_is_crop"] or sig["output_is_subregion"]:
        candidates.extend(["CropNonBackgroundView", "CropBoundingBoxView"])
        sig["dominant_failure"] = "output_is_subregion"

    if sig["objects_repeat_in_tile"]:
        candidates.append("RepeatedMotifView")
        sig["dominant_failure"] = sig.get("dominant_failure", "tiled_structure")

    if sig["train_residual_is_mirrored"]:
        candidates.append("SymmetryQuotientView")

    if sig["object_role_depends_on_containment"]:
        candidates.append("ContainmentGraphView")

    if sig["has_line_separators"]:
        candidates.append("LineAnchorView")

    if sig["has_markers"]:
        candidates.append("CropMarkerNeighborhoodView")

    if sig["multi_color_with_layer_structure"]:
        candidates.append("SplitColorLayerView")
        candidates.append("ForegroundBackgroundView")

    if sig["objects_need_canonicalization"]:
        candidates.append("NormalizeObjectBBoxView")

    if not candidates:
        candidates.extend(["CropNonBackgroundView", "ForegroundBackgroundView", "SplitColorLayerView"])
        sig["dominant_failure"] = "no_specific_pattern"

    sig["candidate_views"] = candidates
    return sig


def instantiate_candidate_views(
    sig: Dict[str, Any],
    grid: np.ndarray,
) -> List[ViewProgram]:
    """Instantiate ViewProgram objects from failure signature candidates."""
    views: List[ViewProgram] = []
    seen_sigs = set()

    non_bg_colors = sorted(set(grid.flatten().tolist()) - {0})

    for name in sig.get("candidate_views", []):
        try:
            if name == "RemoveFrameView":
                v = RemoveFrameView()
            elif name == "ExtractInteriorView":
                v = ExtractInteriorView()
            elif name == "CropNonBackgroundView":
                v = CropNonBackgroundView()
            elif name == "CropBoundingBoxView":
                v = CropBoundingBoxView()
            elif name.startswith("SplitColorLayerView(") and name.endswith(")"):
                c_str = name[len("SplitColorLayerView("):-1]
                if c_str == "None" or c_str == "":
                    for c in non_bg_colors:
                        v = SplitColorLayerView(target_color=c)
                        s = str(v.signature())
                        if s not in seen_sigs and v.can_apply(grid):
                            seen_sigs.add(s)
                            views.append(v)
                    continue
                else:
                    v = SplitColorLayerView(target_color=int(c_str))
            elif name == "SplitColorLayerView":
                for c in non_bg_colors:
                    v = SplitColorLayerView(target_color=c)
                    s = str(v.signature())
                    if s not in seen_sigs and v.can_apply(grid):
                        seen_sigs.add(s)
                        views.append(v)
                continue
            elif name == "ForegroundBackgroundView":
                v = ForegroundBackgroundView()
            elif name == "ObjectGraphView":
                v = ObjectGraphView()
            elif name == "NormalizeObjectBBoxView":
                v = NormalizeObjectBBoxView()
            elif name == "SymmetryQuotientView":
                v = SymmetryQuotientView()
            elif name == "RepeatedMotifView":
                v = RepeatedMotifView()
            elif name == "LineAnchorView":
                v = LineAnchorView()
            elif name == "ContainmentGraphView":
                v = ContainmentGraphView()
            elif name == "CropMarkerNeighborhoodView":
                v = CropMarkerNeighborhoodView()
            else:
                continue

            s = str(v.signature())
            if s not in seen_sigs and v.can_apply(grid):
                seen_sigs.add(s)
                views.append(v)
        except Exception:
            continue

    return views


def try_operator_on_view(
    view: ViewProgram,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    timeout: float = 60.0,
) -> List[Dict[str, Any]]:
    """Try existing operators on a lifted view and return executable proposals.

    Returns a list of proposal dicts, each containing:
    - execute: callable(grid) -> output_grid
    - view_program: the ViewProgram used
    - operator_family: strategy name
    - selector_property: discriminative property
    - train_consistent: bool
    - train_pixel_error: int
    """
    proposals = []
    deadline = time.time() + timeout

    # Lift train pairs
    try:
        lifted = view.lift_train_pairs(train_pairs)
    except Exception:
        return []

    if not lifted or len(lifted) != len(train_pairs):
        return []

    for li, lo in lifted:
        if li is None or lo is None:
            return []
        if not isinstance(li, np.ndarray) or not isinstance(lo, np.ndarray):
            return []

    # Strategy 1: StructuralReasoner on lifted view
    try:
        reasoner = StructuralReasoner(GridDomainAdapter(), memory=ReasoningMemory())
        lifted_test = []
        for ti in test_inputs:
            try:
                lp = view.lift_train_pairs([(ti, ti)])
                lifted_test.append(lp[0][0])
            except Exception:
                lifted_test.append(ti)

        result = reasoner.solve(lifted, lifted_test, deadline=deadline)
        if result is not None:
            preds, meta = result
            strategy = meta.get("strategy", "unknown")

            def _make_reasoner_exe(v, rsn_meta):
                strategy_name = rsn_meta.get("strategy", "unknown")
                prop = rsn_meta.get("property") or rsn_meta.get("filter_prop")
                keep = rsn_meta.get("keep_when_true", True)

                def execute(grid):
                    try:
                        lp = v.lift_train_pairs([(grid, grid)])
                        lifted_grid = lp[0][0]
                    except Exception:
                        return None
                    r = StructuralReasoner(GridDomainAdapter(), memory=ReasoningMemory())
                    # Re-solve is expensive; use the discovered strategy directly
                    if prop and strategy_name in ("discriminative_filter",):
                        applied = _apply_filter(lifted_grid, prop, keep)
                        if applied is not None:
                            return v.project(applied, grid)
                    # Fallback: full re-solve
                    res = r.solve(
                        v.lift_train_pairs([(grid, grid)]),
                        [lifted_grid],
                        deadline=time.time() + 30,
                    )
                    if res is None:
                        return None
                    p, _ = res
                    if not p:
                        return None
                    return v.project(p[0], grid)
                return execute

            exe = _make_reasoner_exe(view, meta)
            proposals.append({
                "execute": exe,
                "view_program": view,
                "operator_family": strategy,
                "selector_property": meta.get("property") or meta.get("filter_prop"),
                "strategy": f"view_{view.view_type}_{strategy}",
            })
    except Exception:
        pass

    if time.time() > deadline:
        return proposals

    # Strategy 2: Direct property-based filter on lifted objects
    try:
        for linp, lout in lifted[:1]:
            objs = _extract_objects_with_properties(linp)
            if len(objs) >= 2:
                objs = _add_relational_properties(objs, linp)
                kept, removed = _classify_kept_removed(linp, lout, objs)
                if kept or removed:
                    prop_result = _find_discriminative_property_extended(
                        objs, kept, removed
                    )
                    if prop_result is not None:
                        prop_name, keep_when_true = prop_result

                        # _apply_filter(grid, prop_name, keep_when_true)
                        if time.time() < deadline:
                            all_match = True
                            for li, lo in lifted:
                                try:
                                    applied = _apply_filter(li, prop_name, keep_when_true)
                                except Exception:
                                    all_match = False
                                    break
                                if applied is None or applied.shape != lo.shape:
                                    all_match = False
                                    break
                                if not np.array_equal(applied, lo):
                                    all_match = False

                            if all_match:
                                def _make_filter_exe(v, pn, kwt):
                                    def execute(grid):
                                        try:
                                            lp = v.lift_train_pairs([(grid, grid)])
                                            lifted_g = lp[0][0]
                                        except Exception:
                                            return None
                                        applied = _apply_filter(lifted_g, pn, kwt)
                                        if applied is None:
                                            return None
                                        return v.project(applied, grid)
                                    return execute

                                exe = _make_filter_exe(view, prop_name, keep_when_true)
                                proposals.append({
                                    "execute": exe,
                                    "view_program": view,
                                    "operator_family": "discriminative_filter",
                                    "selector_property": prop_name,
                                    "strategy": f"view_{view.view_type}_discriminative_filter",
                                })

                        # _apply_filter_extract(grid, objects, prop, keep_when_true)
                        if time.time() < deadline:
                            all_match = True
                            for li, lo in lifted:
                                try:
                                    lo_objs = _extract_objects_with_properties(li)
                                    lo_objs = _add_relational_properties(lo_objs, li)
                                    applied = _apply_filter_extract(li, lo_objs, prop_name, keep_when_true)
                                except Exception:
                                    all_match = False
                                    break
                                if applied is None or applied.shape != lo.shape:
                                    all_match = False
                                    break
                                if not np.array_equal(applied, lo):
                                    all_match = False

                            if all_match:
                                def _make_extract_exe(v, pn, kwt):
                                    def execute(grid):
                                        try:
                                            lp = v.lift_train_pairs([(grid, grid)])
                                            lifted_g = lp[0][0]
                                        except Exception:
                                            return None
                                        o = _extract_objects_with_properties(lifted_g)
                                        if len(o) < 2:
                                            return None
                                        o = _add_relational_properties(o, lifted_g)
                                        applied = _apply_filter_extract(lifted_g, o, pn, kwt)
                                        if applied is None:
                                            return None
                                        return v.project(applied, grid)
                                    return execute

                                exe = _make_extract_exe(view, prop_name, keep_when_true)
                                proposals.append({
                                    "execute": exe,
                                    "view_program": view,
                                    "operator_family": "discriminative_extract",
                                    "selector_property": prop_name,
                                    "strategy": f"view_{view.view_type}_discriminative_extract",
                                })
    except Exception:
        pass

    if time.time() > deadline:
        return proposals

    # Strategy 3: AdaptiveReasoningLoop on lifted view (broader strategy set)
    if not proposals:
        try:
            from reasoning_project.manifold_memory import MemoryManifold
            from reasoning_project.near_solved_memory import NearSolvedMemory
            from reasoning_project.events import ReasoningEventLog

            loop = AdaptiveReasoningLoop(
                max_iterations=4,
                timeout_seconds=min(30.0, deadline - time.time()),
                memory=ReasoningMemory(),
                manifold=MemoryManifold(),
                near_solved_memory=NearSolvedMemory(manifold=MemoryManifold()),
                event_log=ReasoningEventLog(),
            )
            lifted_test = []
            for ti in test_inputs:
                try:
                    lp = view.lift_train_pairs([(ti, ti)])
                    lifted_test.append(lp[0][0])
                except Exception:
                    lifted_test.append(ti)

            loop_result = loop.solve(lifted, lifted_test, task_id="view_search")
            if loop_result.solved and loop_result.predictions:
                meta = loop_result.hypothesis or {}
                strategy = meta.get("strategy", "adaptive_loop")

                def _make_loop_exe(v, loop_meta, train_p):
                    def execute(grid):
                        try:
                            lp = v.lift_train_pairs([(grid, grid)])
                            lifted_g = lp[0][0]
                        except Exception:
                            return None
                        inner_loop = AdaptiveReasoningLoop(
                            max_iterations=4,
                            timeout_seconds=30.0,
                            memory=ReasoningMemory(),
                            manifold=MemoryManifold(),
                            near_solved_memory=NearSolvedMemory(manifold=MemoryManifold()),
                            event_log=ReasoningEventLog(),
                        )
                        lt = v.lift_train_pairs(train_p)
                        res = inner_loop.solve(lt, [lifted_g], task_id="view_exe")
                        if not res.solved or not res.predictions:
                            return None
                        return v.project(res.predictions[0], grid)
                    return execute

                exe = _make_loop_exe(view, meta, train_pairs)
                proposals.append({
                    "execute": exe,
                    "view_program": view,
                    "operator_family": strategy,
                    "selector_property": meta.get("property") or meta.get("filter_prop"),
                    "strategy": f"view_{view.view_type}_adaptive_loop_{strategy}",
                })
        except Exception:
            pass

    if time.time() > deadline:
        return proposals

    # Strategy 5: Direct pixel comparison (if output == input with some pixels zeroed)
    if not proposals:
        try:
            for linp, lout in lifted:
                if linp.shape != lout.shape:
                    break
            else:
                all_zero_only = True
                for linp, lout in lifted:
                    diff = linp != lout
                    if np.any(diff):
                        changed_vals = lout[diff]
                        if not np.all(changed_vals == 0):
                            all_zero_only = False
                            break

                if all_zero_only:
                    removed_colors = set()
                    for linp, lout in lifted:
                        diff = linp != lout
                        if np.any(diff):
                            removed_colors.update(linp[diff].tolist())

                    if len(removed_colors) == 1:
                        remove_color = removed_colors.pop()

                        def _make_color_remove_exe(v, rc):
                            def execute(grid):
                                try:
                                    lp = v.lift_train_pairs([(grid, grid)])
                                    lifted_g = lp[0][0]
                                except Exception:
                                    return None
                                result = lifted_g.copy()
                                result[result == rc] = 0
                                return v.project(result, grid)
                            return execute

                        exe = _make_color_remove_exe(view, remove_color)
                        proposals.append({
                            "execute": exe,
                            "view_program": view,
                            "operator_family": "color_removal",
                            "selector_property": f"remove_color_{remove_color}",
                            "strategy": f"view_{view.view_type}_color_removal",
                        })
        except Exception:
            pass

    return proposals


def verify_proposal_on_train(
    exe,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Tuple[bool, int]:
    """Check train consistency and return total pixel error."""
    total_err = 0
    try:
        for inp, expected in train_pairs:
            pred = exe(inp)
            if pred is None:
                return False, -1
            if not isinstance(pred, np.ndarray):
                pred = np.array(pred)
            if pred.shape != expected.shape:
                return False, -1
            err = int(np.sum(pred != expected))
            total_err += err
            if err > 0:
                return False, total_err
        return True, 0
    except Exception:
        return False, -1


def run_failure_driven_adaptergenesis(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    timeout: float = 120.0,
    max_views: int = 30,
) -> List[Dict[str, Any]]:
    """Main entry point: generate ViewProgram proposals for a failed task.

    Returns list of proposal dicts with executable hypotheses that pass
    train consistency on the full pipeline (view → operate → project).
    """
    deadline = time.time() + timeout
    results: List[Dict[str, Any]] = []

    # Classify failure
    sig = classify_failure_signature(train_pairs)

    # Instantiate candidate views from failure signature
    inp0 = train_pairs[0][0]
    candidate_views = instantiate_candidate_views(sig, inp0)

    # Also try depth-2 compositions on the top candidates
    if len(candidate_views) <= 5 and time.time() < deadline:
        base_views = list(candidate_views)
        for v1 in base_views[:3]:
            for v2 in base_views[:3]:
                if v1 is v2:
                    continue
                try:
                    comp = ComposedViewProgram(v1, v2)
                    if comp.can_apply(inp0):
                        candidate_views.append(comp)
                except Exception:
                    continue

    # Limit total views
    candidate_views = candidate_views[:max_views]

    # Try each view
    for view in candidate_views:
        if time.time() > deadline:
            break

        per_view_timeout = min(30.0, deadline - time.time())
        if per_view_timeout <= 0:
            break

        proposals = try_operator_on_view(
            view, train_pairs, test_inputs, timeout=per_view_timeout,
        )

        for prop in proposals:
            exe = prop["execute"]
            train_ok, pixel_err = verify_proposal_on_train(exe, train_pairs)

            result = {
                "task_id": task_id,
                "view_program": view.view_type,
                "view_signature": view.signature(),
                "operator_family": prop["operator_family"],
                "selector_property": prop.get("selector_property"),
                "strategy": prop.get("strategy"),
                "train_consistent": train_ok,
                "train_pixel_error": pixel_err,
                "execute": exe if train_ok else None,
                "failure_signature": sig.get("dominant_failure"),
                "candidate_views_tried": len(candidate_views),
            }
            results.append(result)

    return results
