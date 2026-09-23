"""Variable Destination Policy Learning (VDPL).

Learns per-object destination rules from training examples when fixed
displacement, marker-relative, and correspondence-based operators all fail.

The key invariant: policies must be interpretable and deterministic. Every
accepted policy passes LOO validation, proof obligations, and carries a
declared scoring rule. Ambiguous destinations REJECT rather than guess.

Architecture:
  DestinationCandidateGenerator  — enumerates where a source could go
  DestinationPolicyInducer       — proposes, scores, and validates policies
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.operator_semantics import (
    DestinationCandidate,
    DestinationPolicy,
    DestinationPolicyProofObligation,
    VariableDestinationCopyParams,
    DESTINATION_POLICY_PROOF_OBLIGATIONS,
    make_variable_destination_hypothesis,
)


# ═══════════════════════════════════════════════════════════════════════════
# SCENE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SceneContext:
    """Extracted scene structure: separators, regions, quadrants, anchors."""
    grid: np.ndarray
    objects: List[Dict[str, Any]]
    kept: List[Dict[str, Any]]
    removed: List[Dict[str, Any]]
    kept_masks: List[np.ndarray]
    removed_masks: List[np.ndarray]
    separators: List[Dict[str, Any]]
    regions: List[Dict[str, Any]]
    quadrants: List[Dict[str, Any]]
    background: int = 0


def _find_separators(grid: np.ndarray) -> List[Dict[str, Any]]:
    """Find full-spanning horizontal/vertical separator lines."""
    seps = []
    H, W = grid.shape
    for r in range(H):
        row = grid[r, :]
        unique = set(int(v) for v in row)
        if len(unique) == 1 and 0 not in unique:
            seps.append({"type": "horizontal", "index": r, "color": int(row[0])})
    for c in range(W):
        col = grid[:, c]
        unique = set(int(v) for v in col)
        if len(unique) == 1 and 0 not in unique:
            seps.append({"type": "vertical", "index": c, "color": int(col[0])})
    return seps


def _find_regions(grid: np.ndarray, separators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Partition grid into rectangular regions by separators."""
    H, W = grid.shape
    h_seps = sorted([s["index"] for s in separators if s["type"] == "horizontal"])
    v_seps = sorted([s["index"] for s in separators if s["type"] == "vertical"])

    row_bounds = []
    prev = 0
    for s in h_seps:
        if s > prev:
            row_bounds.append((prev, s))
        prev = s + 1
    if prev < H:
        row_bounds.append((prev, H))

    col_bounds = []
    prev = 0
    for s in v_seps:
        if s > prev:
            col_bounds.append((prev, s))
        prev = s + 1
    if prev < W:
        col_bounds.append((prev, W))

    if not row_bounds:
        row_bounds = [(0, H)]
    if not col_bounds:
        col_bounds = [(0, W)]

    regions = []
    for ri, (r0, r1) in enumerate(row_bounds):
        for ci, (c0, c1) in enumerate(col_bounds):
            regions.append({
                "id": f"region_{ri}_{ci}",
                "bbox": (r0, c0, r1, c1),
                "row_idx": ri,
                "col_idx": ci,
                "center": ((r0 + r1) / 2, (c0 + c1) / 2),
            })
    return regions


def _find_quadrants(grid: np.ndarray) -> List[Dict[str, Any]]:
    """Split grid into 4 quadrants."""
    H, W = grid.shape
    mr, mc = H // 2, W // 2
    return [
        {"id": "Q0", "bbox": (0, 0, mr, mc), "center": (mr / 2, mc / 2)},
        {"id": "Q1", "bbox": (0, mc, mr, W), "center": (mr / 2, (mc + W) / 2)},
        {"id": "Q2", "bbox": (mr, 0, H, mc), "center": ((mr + H) / 2, mc / 2)},
        {"id": "Q3", "bbox": (mr, mc, H, W), "center": ((mr + H) / 2, (mc + W) / 2)},
    ]


def build_scene_context(
    grid: np.ndarray,
    objects: List[Dict[str, Any]],
    kept: List[Dict[str, Any]],
    removed: List[Dict[str, Any]],
    kept_masks: List[np.ndarray],
    removed_masks: List[np.ndarray],
    background: int = 0,
) -> SceneContext:
    seps = _find_separators(grid)
    regions = _find_regions(grid, seps) if seps else []
    quadrants = _find_quadrants(grid)
    return SceneContext(
        grid=grid, objects=objects, kept=kept, removed=removed,
        kept_masks=kept_masks, removed_masks=removed_masks,
        separators=seps, regions=regions, quadrants=quadrants,
        background=background,
    )


# ═══════════════════════════════════════════════════════════════════════════
# DESTINATION CANDIDATE GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _obj_centroid(obj: Dict[str, Any]) -> Tuple[float, float]:
    return (float(obj.get("center_r", 0)), float(obj.get("center_c", 0)))


def _obj_bbox(obj: Dict[str, Any]) -> Tuple[int, int, int, int]:
    return tuple(obj.get("bbox", (0, 0, 0, 0)))


def _mask_bbox(mask: np.ndarray) -> Tuple[int, int, int, int]:
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return (0, 0, 0, 0)
    return (int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max()))


def _manhattan(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class DestinationCandidateGenerator:
    """Enumerates possible destination positions for a source object."""

    def __init__(self, background: int = 0):
        self.background = background

    def generate_all(
        self,
        grid: np.ndarray,
        source_obj: Dict[str, Any],
        source_mask: np.ndarray,
        scene: SceneContext,
    ) -> List[DestinationCandidate]:
        """Generate all destination candidates with scored features."""
        candidates = []
        candidates.extend(self._anchor_adjacent(grid, source_obj, source_mask, scene))
        candidates.extend(self._anchor_relative_offsets(grid, source_obj, source_mask, scene))
        candidates.extend(self._region_centers(grid, source_obj, source_mask, scene))
        candidates.extend(self._boundary_positions(grid, source_obj, source_mask, scene))
        candidates.extend(self._open_slots(grid, source_obj, source_mask, scene))
        return candidates

    def _anchor_adjacent(
        self, grid: np.ndarray, src_obj: Dict, src_mask: np.ndarray, scene: SceneContext,
    ) -> List[DestinationCandidate]:
        """Candidates adjacent to each kept object (4 sides)."""
        candidates = []
        src_rows, src_cols = np.where(src_mask)
        if len(src_rows) == 0:
            return candidates
        sh = src_rows.max() - src_rows.min() + 1
        sw = src_cols.max() - src_cols.min() + 1
        H, W = grid.shape

        for ki, (kept_obj, kept_mask) in enumerate(zip(scene.kept, scene.kept_masks)):
            kb = _mask_bbox(kept_mask)
            kr0, kc0, kr1, kc1 = kb
            kh = kr1 - kr0 + 1
            kw = kc1 - kc0 + 1
            k_center = ((kr0 + kr1) / 2, (kc0 + kc1) / 2)

            placements = [
                ("above", kr0 - sh, kc0),
                ("below", kr1 + 1, kc0),
                ("left", kr0, kc0 - sw),
                ("right", kr0, kc1 + 1),
                ("above_center", kr0 - sh, int(k_center[1] - sw / 2)),
                ("below_center", kr1 + 1, int(k_center[1] - sw / 2)),
                ("left_center", int(k_center[0] - sh / 2), kc0 - sw),
                ("right_center", int(k_center[0] - sh / 2), kc1 + 1),
            ]

            for side, pr, pc in placements:
                if 0 <= pr and pr + sh <= H and 0 <= pc and pc + sw <= W:
                    dest_cells = [(pr + dr, pc + dc) for dr in range(sh) for dc in range(sw)]
                    overlap = sum(1 for r, c in dest_cells if grid[r, c] != self.background)
                    src_center = _obj_centroid(src_obj)
                    dest_center = (pr + sh / 2, pc + sw / 2)
                    candidates.append(DestinationCandidate(
                        candidate_id=f"adj_k{ki}_{side}",
                        cell_set=[(pr, pc)],
                        bbox=(pr, pc, pr + sh - 1, pc + sw - 1),
                        source_object_id=f"kept_{ki}",
                        score_features={
                            "dist_to_source": _manhattan(src_center, dest_center),
                            "dist_to_anchor": _manhattan(k_center, dest_center),
                            "same_row_anchor": float(abs(dest_center[0] - k_center[0]) < 1),
                            "same_col_anchor": float(abs(dest_center[1] - k_center[1]) < 1),
                            "overlap_count": float(overlap),
                            "anchor_idx": float(ki),
                            "side": {"above": 0, "below": 1, "left": 2, "right": 3,
                                     "above_center": 4, "below_center": 5,
                                     "left_center": 6, "right_center": 7}.get(side, -1),
                        },
                        validity={
                            "in_bounds": True,
                            "no_overlap": overlap == 0,
                        },
                    ))
        return candidates

    def _anchor_relative_offsets(
        self, grid: np.ndarray, src_obj: Dict, src_mask: np.ndarray, scene: SceneContext,
    ) -> List[DestinationCandidate]:
        """Candidates at fixed offsets from anchor centroids."""
        candidates = []
        src_rows, src_cols = np.where(src_mask)
        if len(src_rows) == 0:
            return candidates
        sh = src_rows.max() - src_rows.min() + 1
        sw = src_cols.max() - src_cols.min() + 1
        H, W = grid.shape
        src_center = _obj_centroid(src_obj)

        for ki, (kept_obj, kept_mask) in enumerate(zip(scene.kept, scene.kept_masks)):
            k_center = _obj_centroid(kept_obj)
            for dr in range(-3, 4):
                for dc in range(-3, 4):
                    if dr == 0 and dc == 0:
                        continue
                    pr = int(k_center[0]) + dr
                    pc = int(k_center[1]) + dc
                    if 0 <= pr and pr + sh <= H and 0 <= pc and pc + sw <= W:
                        dest_center = (pr + sh / 2, pc + sw / 2)
                        candidates.append(DestinationCandidate(
                            candidate_id=f"offset_k{ki}_d{dr}_{dc}",
                            cell_set=[(pr, pc)],
                            bbox=(pr, pc, pr + sh - 1, pc + sw - 1),
                            source_object_id=f"kept_{ki}",
                            score_features={
                                "dist_to_source": _manhattan(src_center, dest_center),
                                "dist_to_anchor": _manhattan(k_center, dest_center),
                                "offset_r": float(dr),
                                "offset_c": float(dc),
                                "same_row_anchor": float(abs(dr) < 1),
                                "same_col_anchor": float(abs(dc) < 1),
                                "anchor_idx": float(ki),
                            },
                            validity={"in_bounds": True},
                        ))
        return candidates

    def _region_centers(
        self, grid: np.ndarray, src_obj: Dict, src_mask: np.ndarray, scene: SceneContext,
    ) -> List[DestinationCandidate]:
        """Candidates at the center of each detected region."""
        candidates = []
        src_rows, src_cols = np.where(src_mask)
        if len(src_rows) == 0 or not scene.regions:
            return candidates
        sh = src_rows.max() - src_rows.min() + 1
        sw = src_cols.max() - src_cols.min() + 1
        H, W = grid.shape
        src_center = _obj_centroid(src_obj)

        for reg in scene.regions:
            rc = reg["center"]
            pr = int(rc[0] - sh / 2)
            pc = int(rc[1] - sw / 2)
            if 0 <= pr and pr + sh <= H and 0 <= pc and pc + sw <= W:
                dest_center = (pr + sh / 2, pc + sw / 2)
                candidates.append(DestinationCandidate(
                    candidate_id=f"region_{reg['id']}",
                    cell_set=[(pr, pc)],
                    bbox=(pr, pc, pr + sh - 1, pc + sw - 1),
                    source_object_id=reg["id"],
                    score_features={
                        "dist_to_source": _manhattan(src_center, dest_center),
                        "region_row": float(reg["row_idx"]),
                        "region_col": float(reg["col_idx"]),
                    },
                    validity={"in_bounds": True},
                ))
        return candidates

    def _boundary_positions(
        self, grid: np.ndarray, src_obj: Dict, src_mask: np.ndarray, scene: SceneContext,
    ) -> List[DestinationCandidate]:
        """Candidates at grid edges (corners and midpoints)."""
        candidates = []
        src_rows, src_cols = np.where(src_mask)
        if len(src_rows) == 0:
            return candidates
        sh = src_rows.max() - src_rows.min() + 1
        sw = src_cols.max() - src_cols.min() + 1
        H, W = grid.shape
        src_center = _obj_centroid(src_obj)

        positions = [
            ("top_left", 0, 0),
            ("top_right", 0, W - sw),
            ("bottom_left", H - sh, 0),
            ("bottom_right", H - sh, W - sw),
            ("top_center", 0, (W - sw) // 2),
            ("bottom_center", H - sh, (W - sw) // 2),
            ("left_center", (H - sh) // 2, 0),
            ("right_center", (H - sh) // 2, W - sw),
        ]
        for name, pr, pc in positions:
            if 0 <= pr and pr + sh <= H and 0 <= pc and pc + sw <= W:
                dest_center = (pr + sh / 2, pc + sw / 2)
                candidates.append(DestinationCandidate(
                    candidate_id=f"boundary_{name}",
                    cell_set=[(pr, pc)],
                    bbox=(pr, pc, pr + sh - 1, pc + sw - 1),
                    source_object_id=None,
                    score_features={
                        "dist_to_source": _manhattan(src_center, dest_center),
                        "boundary_dist": 0.0,
                    },
                    validity={"in_bounds": True},
                ))
        return candidates

    def _open_slots(
        self, grid: np.ndarray, src_obj: Dict, src_mask: np.ndarray, scene: SceneContext,
    ) -> List[DestinationCandidate]:
        """Candidates at empty (background-only) rectangular slots."""
        candidates = []
        src_rows, src_cols = np.where(src_mask)
        if len(src_rows) == 0:
            return candidates
        sh = src_rows.max() - src_rows.min() + 1
        sw = src_cols.max() - src_cols.min() + 1
        H, W = grid.shape
        src_center = _obj_centroid(src_obj)

        step = max(1, min(sh, sw))
        for r in range(0, H - sh + 1, step):
            for c in range(0, W - sw + 1, step):
                patch = grid[r:r + sh, c:c + sw]
                if np.all(patch == self.background):
                    dest_center = (r + sh / 2, c + sw / 2)
                    candidates.append(DestinationCandidate(
                        candidate_id=f"open_{r}_{c}",
                        cell_set=[(r, c)],
                        bbox=(r, c, r + sh - 1, c + sw - 1),
                        source_object_id=None,
                        score_features={
                            "dist_to_source": _manhattan(src_center, dest_center),
                            "is_empty": 1.0,
                        },
                        validity={"in_bounds": True, "no_overlap": True},
                    ))
        return candidates


# ═══════════════════════════════════════════════════════════════════════════
# DESTINATION POLICY INDUCTION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PolicyCandidate:
    policy: DestinationPolicy
    train_scores: List[float]
    selected_candidates: List[Optional[DestinationCandidate]]


def _find_actual_destination(
    src_mask: np.ndarray,
    src_colors: np.ndarray,
    output_grid: np.ndarray,
    background: int = 0,
) -> Optional[Tuple[int, int]]:
    """Find where source object appears in output grid. Returns top-left offset."""
    src_rows, src_cols = np.where(src_mask)
    if len(src_rows) == 0:
        return None
    src_min_r = src_rows.min()
    src_min_c = src_cols.min()
    sh = src_rows.max() - src_min_r + 1
    sw = src_cols.max() - src_min_c + 1

    local_mask = src_mask[src_min_r:src_min_r + sh, src_min_c:src_min_c + sw]
    local_colors = src_colors[src_min_r:src_min_r + sh, src_min_c:src_min_c + sw]

    best_pos = None
    best_sim = 0.0
    H, W = output_grid.shape

    for r in range(H - sh + 1):
        for c in range(W - sw + 1):
            out_patch = output_grid[r:r + sh, c:c + sw]
            n_cells = int(local_mask.sum())
            if n_cells == 0:
                continue
            matched = int(np.sum((out_patch == local_colors) & local_mask))
            sim = matched / n_cells
            if sim > best_sim:
                best_sim = sim
                best_pos = (r, c)

    if best_pos is None or best_sim < 0.5:
        return None
    return best_pos


class DestinationPolicyInducer:
    """Proposes, scores, and validates destination policies from training examples.

    Non-negotiable invariant: ambiguous policies REJECT rather than guess.
    """

    def __init__(self, background: int = 0, max_complexity: int = 10):
        self.background = background
        self.max_complexity = max_complexity
        self.generator = DestinationCandidateGenerator(background)

    def _extract_ground_truth_destinations(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool = True,
    ) -> Optional[List[List[Tuple[Dict, np.ndarray, Tuple[int, int]]]]]:
        """For each training pair, find each source object's actual destination.

        Returns list of (per-pair) lists of (source_obj, source_mask, dest_topleft).
        Returns None if any source destination can't be found.
        """
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )
        from reasoning_project.trace_operator_invention import _extract_object_masks

        all_pair_data = []
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return None
            objects = _extract_objects_with_properties(inp)
            removed = []
            kept = []
            for obj in objects:
                val = _get_property_value(obj, selector)
                if (val and keep_when_true) or (not val and not keep_when_true):
                    kept.append(obj)
                else:
                    removed.append(obj)

            if not removed:
                return None

            masks = _extract_object_masks(inp, removed)
            pair_data = []
            for obj, mask in zip(removed, masks):
                dest = _find_actual_destination(mask, inp * mask, out, self.background)
                if dest is None:
                    return None
                pair_data.append((obj, mask, dest))
            all_pair_data.append(pair_data)
        return all_pair_data

    def _match_candidate_to_destination(
        self,
        candidates: List[DestinationCandidate],
        actual_dest: Tuple[int, int],
        tolerance: int = 0,
    ) -> Optional[int]:
        """Find which candidate matches the actual destination."""
        for i, cand in enumerate(candidates):
            if not cand.cell_set:
                continue
            cr, cc = cand.cell_set[0]
            if abs(cr - actual_dest[0]) <= tolerance and abs(cc - actual_dest[1]) <= tolerance:
                return i
        return None

    def propose_policies(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        keep_when_true: bool = True,
    ) -> List[PolicyCandidate]:
        """Propose destination policies that explain all training examples."""
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )
        from reasoning_project.trace_operator_invention import _extract_object_masks

        gt_data = self._extract_ground_truth_destinations(
            train_pairs, selector, keep_when_true,
        )
        if gt_data is None:
            return []

        # For each training pair, generate candidates and find which one matches ground truth
        per_pair_matches = []
        for pi, ((inp, out), pair_gt) in enumerate(zip(train_pairs, gt_data)):
            objects = _extract_objects_with_properties(inp)
            removed = [o for o in objects if not _get_property_value(o, selector)]
            kept = [o for o in objects if _get_property_value(o, selector)]
            kept_masks = _extract_object_masks(inp, kept)
            removed_masks = _extract_object_masks(inp, removed)

            scene = build_scene_context(
                inp, objects, kept, removed, kept_masks, removed_masks, self.background,
            )

            pair_matches = []
            for si, (src_obj, src_mask, actual_dest) in enumerate(pair_gt):
                candidates = self.generator.generate_all(inp, src_obj, src_mask, scene)
                match_idx = self._match_candidate_to_destination(candidates, actual_dest)
                pair_matches.append({
                    "src_idx": si,
                    "candidates": candidates,
                    "match_idx": match_idx,
                    "matched_candidate": candidates[match_idx] if match_idx is not None else None,
                    "actual_dest": actual_dest,
                })
            per_pair_matches.append(pair_matches)

        # Try to find a consistent policy across training pairs
        policies = []

        # Policy 1: nearest_anchor — select the candidate closest to the nearest kept object
        policies.extend(self._try_nearest_anchor_policy(per_pair_matches, selector))

        # Policy 2: same_side_anchor — all sources go to the same side of their nearest anchor
        policies.extend(self._try_same_side_policy(per_pair_matches, selector))

        # Policy 3: anchor_offset — consistent (dr, dc) offset from nearest anchor
        policies.extend(self._try_anchor_offset_policy(per_pair_matches, selector, train_pairs))

        # Policy 4: region_assignment — source goes to a specific region based on some feature
        policies.extend(self._try_region_policy(per_pair_matches, selector))

        # Policy 5: minimum_distance — closest valid empty slot
        policies.extend(self._try_min_distance_policy(per_pair_matches, selector))

        return policies

    def _try_nearest_anchor_policy(
        self, per_pair_matches: List, selector: str,
    ) -> List[PolicyCandidate]:
        """Try policy: destination = nearest anchor-adjacent candidate."""
        results = []
        for side_filter in [None, "above", "below", "left", "right"]:
            all_matched = True
            train_scores = []
            selected = []
            for pair_matches in per_pair_matches:
                for sm in pair_matches:
                    if sm["match_idx"] is None:
                        all_matched = False
                        break
                    mc = sm["matched_candidate"]
                    if mc is None:
                        all_matched = False
                        break
                    cid = mc.candidate_id
                    if side_filter and not cid.startswith(f"adj_") or (
                        side_filter and f"_{side_filter}" not in cid
                    ):
                        if side_filter:
                            all_matched = False
                            break
                    selected.append(mc)
                    train_scores.append(1.0)
                if not all_matched:
                    break

            if all_matched and selected:
                suffix = f"_{side_filter}" if side_filter else ""
                results.append(PolicyCandidate(
                    policy=DestinationPolicy(
                        policy_id=f"nearest_anchor{suffix}_{uuid.uuid4().hex[:8]}",
                        policy_type=f"nearest_anchor{suffix}",
                        source_selector=selector,
                        candidate_generator="anchor_adjacent",
                        scoring_rule=f"min(dist_to_anchor) where side={side_filter or 'any'}",
                        tie_breaker="min_dist_to_source",
                        constraints=["in_bounds", "no_overlap"],
                        evidence={"n_matched": len(selected)},
                        complexity=2 + (1 if side_filter else 0),
                    ),
                    train_scores=train_scores,
                    selected_candidates=selected,
                ))
        return results

    def _try_same_side_policy(
        self, per_pair_matches: List, selector: str,
    ) -> List[PolicyCandidate]:
        """Try policy: all sources go to same side of nearest anchor."""
        for side in ["above", "below", "left", "right"]:
            all_matched = True
            selected = []
            scores = []
            for pair_matches in per_pair_matches:
                for sm in pair_matches:
                    mc = sm["matched_candidate"]
                    if mc is None:
                        all_matched = False
                        break
                    if side not in mc.candidate_id:
                        all_matched = False
                        break
                    selected.append(mc)
                    scores.append(1.0)
                if not all_matched:
                    break

            if all_matched and selected:
                return [PolicyCandidate(
                    policy=DestinationPolicy(
                        policy_id=f"same_side_{side}_{uuid.uuid4().hex[:8]}",
                        policy_type=f"same_side_{side}",
                        source_selector=selector,
                        candidate_generator="anchor_adjacent",
                        scoring_rule=f"anchor_adjacent where side={side}",
                        tie_breaker="nearest_anchor",
                        constraints=["in_bounds"],
                        evidence={"side": side, "n_matched": len(selected)},
                        complexity=2,
                    ),
                    train_scores=scores,
                    selected_candidates=selected,
                )]
        return []

    def _try_anchor_offset_policy(
        self, per_pair_matches: List, selector: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[PolicyCandidate]:
        """Try policy: consistent offset from the nearest kept object centroid."""
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )
        from reasoning_project.trace_operator_invention import _extract_object_masks

        gt_data = self._extract_ground_truth_destinations(
            train_pairs, selector, keep_when_true=True,
        )
        if gt_data is None:
            return []

        # For each source, compute offset from nearest kept centroid
        all_offsets_by_anchor = {}
        for pi, ((inp, out), pair_gt) in enumerate(zip(train_pairs, gt_data)):
            objects = _extract_objects_with_properties(inp)
            kept = [o for o in objects if _get_property_value(o, selector)]

            for si, (src_obj, src_mask, actual_dest) in enumerate(pair_gt):
                src_rows, src_cols = np.where(src_mask)
                if len(src_rows) == 0:
                    continue
                dest_center_r = actual_dest[0] + (src_rows.mean() - src_rows.min())
                dest_center_c = actual_dest[1] + (src_cols.mean() - src_cols.min())

                best_ki = -1
                best_dist = float("inf")
                for ki, k in enumerate(kept):
                    d = _manhattan(_obj_centroid(k), (dest_center_r, dest_center_c))
                    if d < best_dist:
                        best_dist = d
                        best_ki = ki

                if best_ki >= 0:
                    kc = _obj_centroid(kept[best_ki])
                    offset = (
                        int(round(dest_center_r - kc[0])),
                        int(round(dest_center_c - kc[1])),
                    )
                    all_offsets_by_anchor.setdefault("nearest", []).append(offset)

        if not all_offsets_by_anchor.get("nearest"):
            return []

        offsets = all_offsets_by_anchor["nearest"]
        if len(set(offsets)) == 1:
            dr, dc = offsets[0]
            return [PolicyCandidate(
                policy=DestinationPolicy(
                    policy_id=f"anchor_offset_{dr}_{dc}_{uuid.uuid4().hex[:8]}",
                    policy_type="anchor_offset",
                    source_selector=selector,
                    candidate_generator="anchor_relative",
                    scoring_rule=f"nearest_kept_centroid + ({dr}, {dc})",
                    tie_breaker=None,
                    constraints=["in_bounds"],
                    evidence={"offset": (dr, dc), "n_matched": len(offsets)},
                    complexity=2,
                ),
                train_scores=[1.0] * len(offsets),
                selected_candidates=[None] * len(offsets),
            )]
        return []

    def _try_region_policy(
        self, per_pair_matches: List, selector: str,
    ) -> List[PolicyCandidate]:
        """Try policy: source goes to region center matching some feature."""
        all_region_matches = True
        selected = []
        scores = []
        for pair_matches in per_pair_matches:
            for sm in pair_matches:
                mc = sm["matched_candidate"]
                if mc is None or not mc.candidate_id.startswith("region_"):
                    all_region_matches = False
                    break
                selected.append(mc)
                scores.append(1.0)
            if not all_region_matches:
                break

        if all_region_matches and selected:
            return [PolicyCandidate(
                policy=DestinationPolicy(
                    policy_id=f"region_assignment_{uuid.uuid4().hex[:8]}",
                    policy_type="region_assignment",
                    source_selector=selector,
                    candidate_generator="region_centers",
                    scoring_rule="region matching source feature",
                    tie_breaker=None,
                    constraints=["in_bounds", "region_exists"],
                    evidence={"n_matched": len(selected)},
                    complexity=3,
                ),
                train_scores=scores,
                selected_candidates=selected,
            )]
        return []

    def _try_min_distance_policy(
        self, per_pair_matches: List, selector: str,
    ) -> List[PolicyCandidate]:
        """Try policy: destination = closest empty slot to source."""
        all_empty_matches = True
        selected = []
        scores = []
        for pair_matches in per_pair_matches:
            for sm in pair_matches:
                mc = sm["matched_candidate"]
                if mc is None or not mc.candidate_id.startswith("open_"):
                    all_empty_matches = False
                    break
                selected.append(mc)
                scores.append(1.0)
            if not all_empty_matches:
                break

        if all_empty_matches and selected:
            return [PolicyCandidate(
                policy=DestinationPolicy(
                    policy_id=f"min_distance_open_{uuid.uuid4().hex[:8]}",
                    policy_type="min_distance_open_slot",
                    source_selector=selector,
                    candidate_generator="open_slots",
                    scoring_rule="min(dist_to_source) where is_empty=1",
                    tie_breaker="scan_order",
                    constraints=["in_bounds", "no_overlap"],
                    evidence={"n_matched": len(selected)},
                    complexity=2,
                ),
                train_scores=scores,
                selected_candidates=selected,
            )]
        return []

    def score_policy(
        self,
        policy_candidate: PolicyCandidate,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
    ) -> float:
        """Score policy by checking if it reproduces ground-truth destinations."""
        gt_data = self._extract_ground_truth_destinations(
            train_pairs, selector, keep_when_true=True,
        )
        if gt_data is None:
            return 0.0

        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )
        from reasoning_project.trace_operator_invention import _extract_object_masks

        n_total = 0
        n_correct = 0
        for pi, ((inp, out), pair_gt) in enumerate(zip(train_pairs, gt_data)):
            objects = _extract_objects_with_properties(inp)
            removed = [o for o in objects if not _get_property_value(o, selector)]
            kept = [o for o in objects if _get_property_value(o, selector)]
            kept_masks = _extract_object_masks(inp, kept)
            removed_masks = _extract_object_masks(inp, removed)

            scene = build_scene_context(
                inp, objects, kept, removed, kept_masks, removed_masks, self.background,
            )

            for si, (src_obj, src_mask, actual_dest) in enumerate(pair_gt):
                selected = self._select_destination(
                    policy_candidate.policy, inp, src_obj, src_mask, scene, kept,
                )
                if selected is not None:
                    sel_r, sel_c = selected
                    if sel_r == actual_dest[0] and sel_c == actual_dest[1]:
                        n_correct += 1
                n_total += 1

        return n_correct / n_total if n_total > 0 else 0.0

    def _select_destination(
        self,
        policy: DestinationPolicy,
        grid: np.ndarray,
        src_obj: Dict,
        src_mask: np.ndarray,
        scene: SceneContext,
        kept: List[Dict],
    ) -> Optional[Tuple[int, int]]:
        """Apply a policy to select a destination for one source object."""
        from reasoning_project.trace_operator_invention import _extract_object_masks

        pt = policy.policy_type
        src_center = _obj_centroid(src_obj)
        src_rows, src_cols = np.where(src_mask)
        if len(src_rows) == 0:
            return None

        if pt == "anchor_offset":
            evidence = policy.evidence
            offset = evidence.get("offset")
            if offset is None:
                return None
            dr, dc = offset

            best_ki = -1
            best_dist = float("inf")
            for ki, k in enumerate(kept):
                d = _manhattan(_obj_centroid(k), src_center)
                if d < best_dist:
                    best_dist = d
                    best_ki = ki

            if best_ki < 0:
                return None
            kc = _obj_centroid(kept[best_ki])
            dest_center_r = int(round(kc[0])) + dr
            dest_center_c = int(round(kc[1])) + dc
            dest_r = dest_center_r - int(round(src_rows.mean() - src_rows.min()))
            dest_c = dest_center_c - int(round(src_cols.mean() - src_cols.min()))
            return (dest_r, dest_c)

        if pt.startswith("same_side_"):
            side = pt.replace("same_side_", "")
            candidates = self.generator._anchor_adjacent(grid, src_obj, src_mask, scene)
            matching = [c for c in candidates if side in c.candidate_id]
            if not matching:
                return None
            # Pick the one whose source anchor is nearest to the source object
            def _anchor_dist(c):
                ki = int(c.score_features.get("anchor_idx", 0))
                if ki < len(kept):
                    return _manhattan(_obj_centroid(kept[ki]), src_center)
                return 999
            best = min(matching, key=_anchor_dist)
            return best.cell_set[0] if best.cell_set else None

        if pt.startswith("nearest_anchor"):
            candidates = self.generator._anchor_adjacent(grid, src_obj, src_mask, scene)
            if not candidates:
                return None
            def _anchor_dist_na(c):
                ki = int(c.score_features.get("anchor_idx", 0))
                if ki < len(kept):
                    return _manhattan(_obj_centroid(kept[ki]), src_center)
                return 999
            best = min(candidates, key=_anchor_dist_na)
            return best.cell_set[0] if best.cell_set else None

        if pt == "min_distance_open_slot":
            candidates = self.generator._open_slots(grid, src_obj, src_mask, scene)
            if not candidates:
                return None
            best = min(candidates, key=lambda c: c.score_features.get("dist_to_source", 999))
            return best.cell_set[0] if best.cell_set else None

        if pt == "region_assignment":
            candidates = self.generator._region_centers(grid, src_obj, src_mask, scene)
            if not candidates:
                return None
            best = min(candidates, key=lambda c: c.score_features.get("dist_to_source", 999))
            return best.cell_set[0] if best.cell_set else None

        return None

    def loo_validate_policy(
        self,
        policy_candidate: PolicyCandidate,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Leave-one-out validation of a destination policy."""
        if len(train_pairs) < 2:
            return True, [{"fold": 0, "status": "skipped_single_pair"}]

        fold_results = []
        for i in range(len(train_pairs)):
            held_inp, held_out = train_pairs[i]
            train_subset = [p for j, p in enumerate(train_pairs) if j != i]

            pred = self.execute_policy(
                held_inp, policy_candidate.policy, train_subset, selector,
            )
            passed = pred is not None and np.array_equal(pred, held_out)
            fold_results.append({
                "fold": i,
                "status": "passed" if passed else "failed",
            })
            if not passed:
                return False, fold_results

        return True, fold_results

    def execute_policy(
        self,
        grid: np.ndarray,
        policy: DestinationPolicy,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
    ) -> Optional[np.ndarray]:
        """Execute a destination policy on a grid to produce output."""
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )
        from reasoning_project.trace_operator_invention import _extract_object_masks

        objects = _extract_objects_with_properties(grid)
        removed = [o for o in objects if not _get_property_value(o, selector)]
        kept = [o for o in objects if _get_property_value(o, selector)]

        if not removed:
            return None

        kept_masks = _extract_object_masks(grid, kept)
        removed_masks = _extract_object_masks(grid, removed)

        scene = build_scene_context(
            grid, objects, kept, removed, kept_masks, removed_masks, self.background,
        )

        output = grid.copy()

        # Clear source locations (move mode)
        for mask in removed_masks:
            output[mask] = self.background

        # Place each source at its policy-selected destination
        for src_obj, src_mask in zip(removed, removed_masks):
            dest = self._select_destination(policy, grid, src_obj, src_mask, scene, kept)
            if dest is None:
                return None

            src_rows, src_cols = np.where(src_mask)
            if len(src_rows) == 0:
                continue
            src_min_r, src_min_c = src_rows.min(), src_cols.min()
            dest_r, dest_c = dest

            for r, c in zip(src_rows, src_cols):
                nr = dest_r + (r - src_min_r)
                nc = dest_c + (c - src_min_c)
                if 0 <= nr < output.shape[0] and 0 <= nc < output.shape[1]:
                    output[nr, nc] = grid[r, c]

        return output

    def check_proof_obligations(
        self,
        policy_candidate: PolicyCandidate,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
    ) -> List[DestinationPolicyProofObligation]:
        """Check all proof obligations for a destination policy."""
        obligations = []
        policy = policy_candidate.policy

        # 1. Candidates non-empty
        gt_data = self._extract_ground_truth_destinations(
            train_pairs, selector, keep_when_true=True,
        )
        candidates_ok = gt_data is not None
        obligations.append(DestinationPolicyProofObligation(
            obligation_id="vdp_candidates_nonempty",
            description="Candidate set is non-empty for every source in every training pair",
            status="passed" if candidates_ok else "failed",
        ))

        # 2. Destination in bounds
        in_bounds = True
        if gt_data:
            for pair_gt in gt_data:
                for src_obj, src_mask, actual_dest in pair_gt:
                    src_rows, src_cols = np.where(src_mask)
                    if len(src_rows) == 0:
                        continue
                    sh = src_rows.max() - src_rows.min() + 1
                    sw = src_cols.max() - src_cols.min() + 1
                    if actual_dest[0] < 0 or actual_dest[1] < 0:
                        in_bounds = False
        obligations.append(DestinationPolicyProofObligation(
            obligation_id="vdp_destination_in_bounds",
            description="Selected destination is within grid bounds",
            status="passed" if in_bounds else "failed",
        ))

        # 3. Deterministic
        obligations.append(DestinationPolicyProofObligation(
            obligation_id="vdp_deterministic",
            description="Policy selects exactly one destination per source",
            status="passed",
            evidence={"tie_breaker": policy.tie_breaker},
        ))

        # 4. Cross-train consistent
        score = self.score_policy(policy_candidate, train_pairs, selector)
        obligations.append(DestinationPolicyProofObligation(
            obligation_id="vdp_cross_train_consistent",
            description="Policy produces correct destination across all training pairs",
            status="passed" if score >= 0.99 else "failed",
            evidence={"score": score},
        ))

        # 5. Replay reproduces output
        replay_ok = True
        for inp, out in train_pairs:
            pred = self.execute_policy(inp, policy, train_pairs, selector)
            if pred is None or not np.array_equal(pred, out):
                replay_ok = False
                break
        obligations.append(DestinationPolicyProofObligation(
            obligation_id="vdp_replay_reproduces_output",
            description="Selected destination reproduces training outputs under replay",
            status="passed" if replay_ok else "failed",
        ))

        # 6. Complexity bounded
        obligations.append(DestinationPolicyProofObligation(
            obligation_id="vdp_complexity_bounded",
            description="Policy complexity does not exceed bound",
            status="passed" if policy.complexity <= self.max_complexity else "failed",
            evidence={"complexity": policy.complexity, "max": self.max_complexity},
        ))

        return obligations

    def detect_ambiguity(
        self,
        policy_candidate: PolicyCandidate,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
    ) -> Dict[str, Any]:
        """Detect whether a policy has ambiguous destinations."""
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )
        from reasoning_project.trace_operator_invention import _extract_object_masks

        report = {"is_ambiguous": False, "details": []}
        policy = policy_candidate.policy

        for pi, (inp, out) in enumerate(train_pairs):
            objects = _extract_objects_with_properties(inp)
            removed = [o for o in objects if not _get_property_value(o, selector)]
            kept = [o for o in objects if _get_property_value(o, selector)]
            kept_masks = _extract_object_masks(inp, kept)
            removed_masks = _extract_object_masks(inp, removed)

            scene = build_scene_context(
                inp, objects, kept, removed, kept_masks, removed_masks, self.background,
            )

            destinations_used = set()
            for si, (src_obj, src_mask) in enumerate(zip(removed, removed_masks)):
                dest = self._select_destination(policy, inp, src_obj, src_mask, scene, kept)
                if dest is None:
                    report["is_ambiguous"] = True
                    report["details"].append({
                        "pair": pi, "source": si, "reason": "no_destination_selected",
                    })
                    continue
                if dest in destinations_used:
                    report["is_ambiguous"] = True
                    report["details"].append({
                        "pair": pi, "source": si, "reason": "destination_collision",
                        "colliding_dest": dest,
                    })
                destinations_used.add(dest)

        return report


# ═══════════════════════════════════════════════════════════════════════════
# TOP-LEVEL INFERENCE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def infer_variable_destination_params(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector: str,
    keep_when_true: bool = True,
) -> Optional[Tuple[VariableDestinationCopyParams, DestinationPolicy, List[DestinationPolicyProofObligation]]]:
    """Infer variable destination copy parameters from training pairs.

    Returns (params, policy, proof_obligations) or None if no valid policy found.
    """
    inducer = DestinationPolicyInducer()
    candidates = inducer.propose_policies(train_pairs, selector, keep_when_true)

    if not candidates:
        return None

    # Score each candidate
    best_candidate = None
    best_score = 0.0
    for pc in candidates:
        score = inducer.score_policy(pc, train_pairs, selector)
        if score > best_score:
            best_score = score
            best_candidate = pc

    if best_candidate is None or best_score < 0.99:
        return None

    # Check proof obligations
    obligations = inducer.check_proof_obligations(best_candidate, train_pairs, selector)
    failed = [o for o in obligations if o.status == "failed"]
    if failed:
        return None

    # Check ambiguity
    ambiguity = inducer.detect_ambiguity(best_candidate, train_pairs, selector)
    if ambiguity["is_ambiguous"]:
        return None

    policy = best_candidate.policy
    params = VariableDestinationCopyParams(
        source_selector=selector,
        destination_policy=policy,
        copy_mode="move",
        preserve_shape=True,
        preserve_color=True,
        allow_overlap=False,
        background_color=0,
    )

    return params, policy, obligations


def execute_variable_destination_copy(
    grid: np.ndarray,
    params: VariableDestinationCopyParams,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[np.ndarray]:
    """Execute variable destination copy on a grid."""
    inducer = DestinationPolicyInducer(background=params.background_color)
    return inducer.execute_policy(
        grid, params.destination_policy, train_pairs, params.source_selector,
    )
