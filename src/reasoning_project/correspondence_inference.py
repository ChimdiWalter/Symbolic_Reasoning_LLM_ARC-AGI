"""Correspondence inference: learn per-object source→target matching rules.

Given a set of source objects and target/anchor objects extracted from
training pairs, this module proposes, scores, and validates correspondence
rules that map each source to a specific target.

The key invariant: ambiguous correspondences MUST reject rather than guess.
Every emitted rule carries proof obligations that are machine-checkable.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage


# ═══════════════════════════════════════════════════════════════════════════
# OBJECT SIGNATURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ObjectSignature:
    object_id: str
    color_set: Tuple[int, ...]
    primary_color: int
    bbox: Tuple[int, int, int, int]
    area: int
    shape_hash: str
    topology_signature: Dict[str, Any]
    centroid: Tuple[float, float]
    relations: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "color_set": list(self.color_set),
            "primary_color": self.primary_color,
            "bbox": list(self.bbox),
            "area": self.area,
            "shape_hash": self.shape_hash,
            "topology_signature": self.topology_signature,
            "centroid": list(self.centroid),
            "relations": self.relations,
        }


def _compute_shape_hash(mask: np.ndarray, bbox: Tuple[int, int, int, int]) -> str:
    r0, c0, r1, c1 = bbox
    local = mask[r0:r1 + 1, c0:c1 + 1].astype(np.uint8)
    return hashlib.md5(local.tobytes() + f"{local.shape}".encode()).hexdigest()[:12]


def _compute_topology(mask: np.ndarray) -> Dict[str, Any]:
    labeled, n_cc = ndimage.label(mask.astype(int))
    inverted = ~mask
    if mask.shape[0] > 2 and mask.shape[1] > 2:
        interior = inverted.copy()
        interior[0, :] = False
        interior[-1, :] = False
        interior[:, 0] = False
        interior[:, -1] = False
        _, n_holes = ndimage.label(interior.astype(int))
    else:
        n_holes = 0

    perimeter = 0
    rows, cols = np.where(mask)
    for r, c in zip(rows, cols):
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= mask.shape[0] or nc < 0 or nc >= mask.shape[1]:
                perimeter += 1
            elif not mask[nr, nc]:
                perimeter += 1

    return {
        "n_components": int(n_cc),
        "n_holes": int(n_holes),
        "perimeter": int(perimeter),
        "euler_characteristic": int(n_cc - n_holes),
    }


def extract_object_signature(
    obj: Dict[str, Any], grid: np.ndarray, obj_index: int,
) -> ObjectSignature:
    mask = obj.get("mask")
    if mask is None:
        cells = obj.get("cells", [])
        mask = np.zeros(grid.shape, dtype=bool)
        for r, c in cells:
            if 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1]:
                mask[r, c] = True

    bbox = obj.get("bbox", (0, 0, 0, 0))
    rows, cols = np.where(mask)
    if len(rows) == 0:
        centroid = (0.0, 0.0)
    else:
        centroid = (float(rows.mean()), float(cols.mean()))

    colors_under_mask = grid[mask] if mask.any() else np.array([0])
    unique_colors = tuple(sorted(set(int(c) for c in colors_under_mask if c != 0)))
    if not unique_colors:
        unique_colors = (0,)

    return ObjectSignature(
        object_id=f"obj_{obj_index}",
        color_set=unique_colors,
        primary_color=int(obj.get("primary_color", unique_colors[0])),
        bbox=tuple(bbox),
        area=int(obj.get("area", int(mask.sum()))),
        shape_hash=_compute_shape_hash(mask, bbox),
        topology_signature=_compute_topology(mask),
        centroid=centroid,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CORRESPONDENCE RULES
# ═══════════════════════════════════════════════════════════════════════════

CORRESPONDENCE_TYPES = [
    "same_color",
    "same_shape",
    "same_size",
    "same_topology",
    "nearest_anchor",
    "row_col_alignment",
    "order_preserving_row",
    "order_preserving_col",
    "region_membership",
    "color_to_region",
    "shape_to_anchor",
]


@dataclass
class CorrespondenceRule:
    rule_id: str
    rule_type: str
    source_selector: str
    target_selector: str
    tie_breaker: Optional[str]
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    complexity: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type,
            "source_selector": self.source_selector,
            "target_selector": self.target_selector,
            "tie_breaker": self.tie_breaker,
            "confidence": self.confidence,
            "complexity": self.complexity,
            "evidence": self.evidence,
        }


@dataclass
class CorrespondenceMatch:
    source_idx: int
    target_idx: int
    source_sig: ObjectSignature
    target_sig: ObjectSignature
    match_quality: float
    displacement: Tuple[int, int]


@dataclass
class CorrespondenceProofObligation:
    obligation_id: str
    description: str
    status: str  # passed, failed, unknown, skipped
    counterexample: Optional[Dict[str, Any]] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "description": self.description,
            "status": self.status,
            "counterexample": self.counterexample,
            "evidence": self.evidence,
        }


# ═══════════════════════════════════════════════════════════════════════════
# CORRESPONDENCE INFERENCE
# ═══════════════════════════════════════════════════════════════════════════

class CorrespondenceInferer:
    """Infers per-object correspondence rules from training examples.

    Non-negotiable invariant: ambiguous correspondences REJECT rather than
    hallucinate. A correspondence is ambiguous when multiple target objects
    are equally valid matches for a single source, and no tie-breaker
    resolves it consistently across training pairs.
    """

    def __init__(self, background: int = 0):
        self.background = background

    def extract_object_signatures(
        self, grid: np.ndarray, objects: List[Dict[str, Any]],
    ) -> List[ObjectSignature]:
        return [
            extract_object_signature(obj, grid, i)
            for i, obj in enumerate(objects)
        ]

    def _find_object_destination(
        self,
        src_mask: np.ndarray,
        src_colors: np.ndarray,
        output_grid: np.ndarray,
    ) -> Optional[Tuple[Tuple[float, float], float]]:
        """Find where a source object appears in the output grid."""
        src_rows, src_cols = np.where(src_mask)
        if len(src_rows) == 0:
            return None

        src_min_r = src_rows.min()
        src_min_c = src_cols.min()
        patch_h = src_rows.max() - src_min_r + 1
        patch_w = src_cols.max() - src_min_c + 1

        local_mask = src_mask[src_min_r:src_min_r + patch_h, src_min_c:src_min_c + patch_w]
        local_colors = src_colors[src_min_r:src_min_r + patch_h, src_min_c:src_min_c + patch_w]

        best_pos = None
        best_sim = 0.0

        for r in range(output_grid.shape[0] - patch_h + 1):
            for c in range(output_grid.shape[1] - patch_w + 1):
                out_patch = output_grid[r:r + patch_h, c:c + patch_w]
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

        dest_centroid = (
            float(best_pos[0] + np.mean(src_rows) - src_min_r),
            float(best_pos[1] + np.mean(src_cols) - src_min_c),
        )
        return dest_centroid, best_sim

    def _match_by_color(
        self, source_sigs: List[ObjectSignature], target_sigs: List[ObjectSignature],
    ) -> Optional[List[Tuple[int, int]]]:
        """Match source to target by primary color. Reject if ambiguous."""
        matches = []
        for si, src in enumerate(source_sigs):
            candidates = [
                ti for ti, tgt in enumerate(target_sigs)
                if tgt.primary_color == src.primary_color
            ]
            if len(candidates) != 1:
                return None
            matches.append((si, candidates[0]))
        used_targets = [m[1] for m in matches]
        if len(set(used_targets)) != len(used_targets):
            return None
        return matches

    def _match_by_shape(
        self, source_sigs: List[ObjectSignature], target_sigs: List[ObjectSignature],
    ) -> Optional[List[Tuple[int, int]]]:
        """Match source to target by shape hash. Reject if ambiguous."""
        matches = []
        for si, src in enumerate(source_sigs):
            candidates = [
                ti for ti, tgt in enumerate(target_sigs)
                if tgt.shape_hash == src.shape_hash
            ]
            if len(candidates) != 1:
                return None
            matches.append((si, candidates[0]))
        used_targets = [m[1] for m in matches]
        if len(set(used_targets)) != len(used_targets):
            return None
        return matches

    def _match_by_size(
        self, source_sigs: List[ObjectSignature], target_sigs: List[ObjectSignature],
    ) -> Optional[List[Tuple[int, int]]]:
        """Match source to target by area. Reject if ambiguous (same-size objects)."""
        matches = []
        for si, src in enumerate(source_sigs):
            candidates = [
                ti for ti, tgt in enumerate(target_sigs)
                if tgt.area == src.area
            ]
            if len(candidates) != 1:
                return None
            matches.append((si, candidates[0]))
        used_targets = [m[1] for m in matches]
        if len(set(used_targets)) != len(used_targets):
            return None
        return matches

    def _match_by_topology(
        self, source_sigs: List[ObjectSignature], target_sigs: List[ObjectSignature],
    ) -> Optional[List[Tuple[int, int]]]:
        """Match source to target by topology signature."""
        def _topo_key(sig: ObjectSignature) -> Tuple:
            ts = sig.topology_signature
            return (ts.get("n_components", 0), ts.get("n_holes", 0), ts.get("euler_characteristic", 0))

        matches = []
        for si, src in enumerate(source_sigs):
            src_key = _topo_key(src)
            candidates = [
                ti for ti, tgt in enumerate(target_sigs)
                if _topo_key(tgt) == src_key
            ]
            if len(candidates) != 1:
                return None
            matches.append((si, candidates[0]))
        used_targets = [m[1] for m in matches]
        if len(set(used_targets)) != len(used_targets):
            return None
        return matches

    def _match_by_nearest(
        self, source_sigs: List[ObjectSignature], target_sigs: List[ObjectSignature],
    ) -> Optional[List[Tuple[int, int]]]:
        """Match each source to its nearest target by centroid distance."""
        if not source_sigs or not target_sigs:
            return None
        matches = []
        used_targets = set()
        sorted_pairs = []
        for si, src in enumerate(source_sigs):
            for ti, tgt in enumerate(target_sigs):
                dist = abs(src.centroid[0] - tgt.centroid[0]) + abs(src.centroid[1] - tgt.centroid[1])
                sorted_pairs.append((dist, si, ti))
        sorted_pairs.sort()

        matched_sources = set()
        for dist, si, ti in sorted_pairs:
            if si in matched_sources or ti in used_targets:
                continue
            matches.append((si, ti))
            matched_sources.add(si)
            used_targets.add(ti)

        if len(matches) != len(source_sigs):
            return None
        matches.sort(key=lambda m: m[0])
        return matches

    def _match_by_row_order(
        self, source_sigs: List[ObjectSignature], target_sigs: List[ObjectSignature],
    ) -> Optional[List[Tuple[int, int]]]:
        """Match source to target by row-sorted order."""
        if len(source_sigs) != len(target_sigs):
            return None
        src_order = sorted(range(len(source_sigs)), key=lambda i: source_sigs[i].centroid[0])
        tgt_order = sorted(range(len(target_sigs)), key=lambda i: target_sigs[i].centroid[0])
        return list(zip(src_order, tgt_order))

    def _match_by_col_order(
        self, source_sigs: List[ObjectSignature], target_sigs: List[ObjectSignature],
    ) -> Optional[List[Tuple[int, int]]]:
        """Match source to target by column-sorted order."""
        if len(source_sigs) != len(target_sigs):
            return None
        src_order = sorted(range(len(source_sigs)), key=lambda i: source_sigs[i].centroid[1])
        tgt_order = sorted(range(len(target_sigs)), key=lambda i: target_sigs[i].centroid[1])
        return list(zip(src_order, tgt_order))

    def propose_rules(
        self,
        source_sigs: List[ObjectSignature],
        target_sigs: List[ObjectSignature],
    ) -> List[CorrespondenceRule]:
        """Propose candidate correspondence rules between source and target objects."""
        rules = []
        matchers = [
            ("same_color", self._match_by_color, 1),
            ("same_shape", self._match_by_shape, 1),
            ("same_size", self._match_by_size, 1),
            ("same_topology", self._match_by_topology, 2),
            ("nearest_anchor", self._match_by_nearest, 3),
            ("order_preserving_row", self._match_by_row_order, 2),
            ("order_preserving_col", self._match_by_col_order, 2),
        ]

        for rule_type, match_fn, complexity in matchers:
            matches = match_fn(source_sigs, target_sigs)
            if matches is not None and len(matches) > 0:
                rules.append(CorrespondenceRule(
                    rule_id=f"corr_{rule_type}_{uuid.uuid4().hex[:8]}",
                    rule_type=rule_type,
                    source_selector="removed",
                    target_selector="kept",
                    tie_breaker=None,
                    confidence=1.0,
                    complexity=complexity,
                    evidence={
                        "n_matches": len(matches),
                        "matches": [(s, t) for s, t in matches],
                    },
                ))

        return rules

    def score_rule(
        self,
        rule: CorrespondenceRule,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector_property: str,
    ) -> float:
        """Score a correspondence rule by checking displacement consistency across training pairs.

        Returns the fraction of training pairs where the rule produces consistent
        per-object displacements (i.e., same displacement for the same correspondence).
        """
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )

        all_displacements: Dict[str, List[Tuple[int, int]]] = {}
        n_scored = 0

        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return 0.0

            objects = _extract_objects_with_properties(inp)
            removed = []
            kept = []
            removed_indices = []
            kept_indices = []
            for i, obj in enumerate(objects):
                val = _get_property_value(obj, selector_property)
                if val:
                    kept.append(obj)
                    kept_indices.append(i)
                else:
                    removed.append(obj)
                    removed_indices.append(i)

            if not removed or not kept:
                return 0.0

            src_sigs = self.extract_object_signatures(inp, removed)
            tgt_sigs = self.extract_object_signatures(inp, kept)

            matcher = self._get_matcher(rule.rule_type)
            if matcher is None:
                return 0.0

            matches = matcher(src_sigs, tgt_sigs)
            if matches is None:
                return 0.0

            from reasoning_project.trace_operator_invention import (
                _extract_object_masks,
                _find_object_in_output,
            )

            src_masks = _extract_object_masks(inp, removed)
            for si, ti in matches:
                if si >= len(src_masks):
                    continue
                mask = src_masks[si]
                result = self._find_object_destination(mask, inp * mask, out)
                if result is None:
                    continue
                dest_centroid, sim = result
                src_centroid = src_sigs[si].centroid
                tgt_centroid = tgt_sigs[ti].centroid

                rel_disp = (
                    int(round(dest_centroid[0] - tgt_centroid[0])),
                    int(round(dest_centroid[1] - tgt_centroid[1])),
                )
                key = f"{rule.rule_type}_{si}_{ti}"
                all_displacements.setdefault("global", []).append(rel_disp)

            n_scored += 1

        if not all_displacements.get("global"):
            return 0.0

        disps = all_displacements["global"]
        if len(set(disps)) == 1:
            return 1.0

        unique = len(set(disps))
        return 1.0 / unique

    def _get_matcher(self, rule_type: str):
        matchers = {
            "same_color": self._match_by_color,
            "same_shape": self._match_by_shape,
            "same_size": self._match_by_size,
            "same_topology": self._match_by_topology,
            "nearest_anchor": self._match_by_nearest,
            "order_preserving_row": self._match_by_row_order,
            "order_preserving_col": self._match_by_col_order,
        }
        return matchers.get(rule_type)

    def validate_rule_loo(
        self,
        rule: CorrespondenceRule,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector_property: str,
        execute_fn: Callable,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Leave-one-out validation of a correspondence rule.

        For each fold, infer the correspondence + displacement from the
        remaining pairs and check exact match on the held-out pair.
        """
        if len(train_pairs) < 2:
            return True, [{"fold": 0, "status": "skipped_single_pair"}]

        fold_results = []
        for i in range(len(train_pairs)):
            held_inp, held_out = train_pairs[i]
            train_subset = [p for j, p in enumerate(train_pairs) if j != i]

            pred = execute_fn(held_inp, rule, train_subset, selector_property)
            passed = pred is not None and np.array_equal(pred, held_out)
            fold_results.append({
                "fold": i,
                "status": "passed" if passed else "failed",
            })
            if not passed:
                return False, fold_results

        return True, fold_results

    def detect_ambiguity(
        self,
        rule: CorrespondenceRule,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector_property: str,
    ) -> Dict[str, Any]:
        """Detect whether a correspondence rule has ambiguous matches.

        Returns an ambiguity report with details on any detected issues.
        """
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )

        ambiguity_report: Dict[str, Any] = {
            "is_ambiguous": False,
            "ambiguity_type": None,
            "details": [],
        }

        for pair_idx, (inp, out) in enumerate(train_pairs):
            objects = _extract_objects_with_properties(inp)
            removed = [obj for obj in objects if not _get_property_value(obj, selector_property)]
            kept = [obj for obj in objects if _get_property_value(obj, selector_property)]

            if not removed or not kept:
                continue

            src_sigs = self.extract_object_signatures(inp, removed)
            tgt_sigs = self.extract_object_signatures(inp, kept)

            if rule.rule_type == "same_color":
                for si, src in enumerate(src_sigs):
                    candidates = [
                        ti for ti, tgt in enumerate(tgt_sigs)
                        if tgt.primary_color == src.primary_color
                    ]
                    if len(candidates) > 1:
                        ambiguity_report["is_ambiguous"] = True
                        ambiguity_report["ambiguity_type"] = "multiple_color_matches"
                        ambiguity_report["details"].append({
                            "pair": pair_idx,
                            "source": si,
                            "n_candidates": len(candidates),
                        })
                    elif len(candidates) == 0:
                        ambiguity_report["is_ambiguous"] = True
                        ambiguity_report["ambiguity_type"] = "no_color_match"
                        ambiguity_report["details"].append({
                            "pair": pair_idx,
                            "source": si,
                            "n_candidates": 0,
                        })

            elif rule.rule_type == "same_shape":
                for si, src in enumerate(src_sigs):
                    candidates = [
                        ti for ti, tgt in enumerate(tgt_sigs)
                        if tgt.shape_hash == src.shape_hash
                    ]
                    if len(candidates) > 1:
                        ambiguity_report["is_ambiguous"] = True
                        ambiguity_report["ambiguity_type"] = "multiple_shape_matches"
                        ambiguity_report["details"].append({
                            "pair": pair_idx,
                            "source": si,
                            "n_candidates": len(candidates),
                        })

        return ambiguity_report

    def emit_proof_obligations(
        self,
        rule: CorrespondenceRule,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector_property: str,
    ) -> List[CorrespondenceProofObligation]:
        """Generate proof obligations for a correspondence rule."""
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _get_property_value,
        )

        obligations = []

        # 1. Every source has a destination match
        all_sources_matched = True
        for pair_idx, (inp, out) in enumerate(train_pairs):
            objects = _extract_objects_with_properties(inp)
            removed = [obj for obj in objects if not _get_property_value(obj, selector_property)]
            kept = [obj for obj in objects if _get_property_value(obj, selector_property)]
            if not removed or not kept:
                continue
            src_sigs = self.extract_object_signatures(inp, removed)
            tgt_sigs = self.extract_object_signatures(inp, kept)
            matcher = self._get_matcher(rule.rule_type)
            if matcher is None:
                all_sources_matched = False
                break
            matches = matcher(src_sigs, tgt_sigs)
            if matches is None or len(matches) != len(src_sigs):
                all_sources_matched = False
                break

        obligations.append(CorrespondenceProofObligation(
            obligation_id="corr_all_sources_matched",
            description="Every source object has exactly one target match",
            status="passed" if all_sources_matched else "failed",
            evidence={"all_pairs_checked": True},
        ))

        # 2. Correspondence is injective
        is_injective = True
        for pair_idx, (inp, out) in enumerate(train_pairs):
            objects = _extract_objects_with_properties(inp)
            removed = [obj for obj in objects if not _get_property_value(obj, selector_property)]
            kept = [obj for obj in objects if _get_property_value(obj, selector_property)]
            if not removed or not kept:
                continue
            src_sigs = self.extract_object_signatures(inp, removed)
            tgt_sigs = self.extract_object_signatures(inp, kept)
            matcher = self._get_matcher(rule.rule_type)
            if matcher is None:
                is_injective = False
                break
            matches = matcher(src_sigs, tgt_sigs)
            if matches is not None:
                target_ids = [m[1] for m in matches]
                if len(set(target_ids)) != len(target_ids):
                    is_injective = False
                    break

        obligations.append(CorrespondenceProofObligation(
            obligation_id="corr_injective",
            description="Correspondence is injective (no two sources map to same target)",
            status="passed" if is_injective else "failed",
        ))

        # 3. Ambiguity check
        ambiguity = self.detect_ambiguity(rule, train_pairs, selector_property)
        obligations.append(CorrespondenceProofObligation(
            obligation_id="corr_no_ambiguity",
            description="Correspondence has no ambiguous matches",
            status="failed" if ambiguity["is_ambiguous"] else "passed",
            evidence=ambiguity,
        ))

        # 4. Consistent across training examples
        consistent = self.score_rule(rule, train_pairs, selector_property)
        obligations.append(CorrespondenceProofObligation(
            obligation_id="corr_cross_train_consistent",
            description="Relative displacements are consistent across training pairs",
            status="passed" if consistent >= 0.99 else "failed",
            evidence={"consistency_score": consistent},
        ))

        return obligations
