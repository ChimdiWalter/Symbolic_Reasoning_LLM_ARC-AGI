"""Selector invention: search for discriminative object selectors.

Goes beyond single-property search by supporting conjunctions, negations,
rank selectors, and marker/frame/anchor relations.  Every selector is
executable: it maps (objects) -> list[bool] telling the caller which objects
are selected.

Integration points:
  - PropertyExpansionEngine calls SelectorInventor when single-property fails
  - adaptive_orchestrator uses selectors to build executable proposals
  - frontier operators receive selectors to pair with transforms
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _add_relational_properties as _add_rel_props_raw,
    _get_property_value,
    _all_property_names,
    _classify_kept_removed,
    _classify_object_changes,
)


def _add_relational_properties(objects, grid=None):
    """Wrapper that handles the full signature of the underlying function."""
    if grid is not None:
        h, w = grid.shape[:2]
        _add_rel_props_raw(objects, grid, h, w)
    return objects


@dataclass
class SelectorCandidate:
    selector_expression: str
    selector_type: str  # single, conjunction, negation, rank, marker_relation
    property_names: list
    selected_object_ids: list
    target_object_ids: list
    train_fit_score: float
    ambiguity_score: float
    complexity: int
    evidence: dict = field(default_factory=dict)


class SelectorInventor:
    """Search for executable selectors that identify target objects."""

    def __init__(self, max_conjuncts: int = 2, max_negation_depth: int = 1):
        self._all_props: Optional[List[str]] = None
        self.max_conjuncts = max_conjuncts
        self.max_negation_depth = max_negation_depth

    @property
    def all_props(self) -> List[str]:
        if self._all_props is None:
            self._all_props = _all_property_names()
        return self._all_props

    def infer_targets_from_change(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        object_trace: Optional[Dict] = None,
    ) -> List[Dict]:
        """For each training pair, identify target objects via change analysis.

        Returns one dict per pair with keys:
          objects, target_indices, non_target_indices, change_type
        """
        per_pair = []
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            objects = _add_relational_properties(objects, inp)

            if len(objects) < 2:
                per_pair.append({
                    "objects": objects,
                    "target_indices": [],
                    "non_target_indices": [],
                    "change_type": "too_few_objects",
                })
                continue

            if inp.shape != out.shape:
                per_pair.append({
                    "objects": objects,
                    "target_indices": list(range(len(objects))),
                    "non_target_indices": [],
                    "change_type": "size_change",
                })
                continue

            kr = _classify_kept_removed(objects, inp, out)
            if kr is not None:
                kept, removed = kr
                per_pair.append({
                    "objects": objects,
                    "target_indices": removed,
                    "non_target_indices": kept,
                    "change_type": "kept_removed",
                })
                continue

            changes = _classify_object_changes(objects, inp, out)
            if changes is not None:
                unchanged = list(changes.kept)
                changed = sorted(set(range(len(objects))) - set(unchanged))
                if changed and unchanged:
                    per_pair.append({
                        "objects": objects,
                        "target_indices": changed,
                        "non_target_indices": unchanged,
                        "change_type": "object_changes",
                    })
                    continue

            diff = inp != out
            changed_idx = [i for i, obj in enumerate(objects) if diff[obj["mask"]].any()]
            unchanged_idx = [i for i in range(len(objects)) if i not in changed_idx]
            per_pair.append({
                "objects": objects,
                "target_indices": changed_idx,
                "non_target_indices": unchanged_idx,
                "change_type": "pixel_diff",
            })

        return per_pair

    def search_single_properties(
        self,
        per_pair_targets: List[Dict],
    ) -> List[SelectorCandidate]:
        candidates = []
        for prop in self.all_props:
            fits_all = True
            total_selected = []
            total_targets = []
            for pp in per_pair_targets:
                objs = pp["objects"]
                target_idx = pp["target_indices"]
                non_target_idx = pp["non_target_indices"]
                if not target_idx or not non_target_idx:
                    fits_all = False
                    break
                t_vals = [_get_property_value(objs[i], prop) for i in target_idx]
                nt_vals = [_get_property_value(objs[i], prop) for i in non_target_idx]
                if all(t_vals) and not any(nt_vals):
                    total_selected.extend(target_idx)
                    total_targets.extend(target_idx)
                elif not any(t_vals) and all(nt_vals):
                    total_selected.extend(non_target_idx)
                    total_targets.extend(target_idx)
                else:
                    fits_all = False
                    break
            if fits_all and total_targets:
                candidates.append(SelectorCandidate(
                    selector_expression=prop,
                    selector_type="single",
                    property_names=[prop],
                    selected_object_ids=total_selected,
                    target_object_ids=total_targets,
                    train_fit_score=1.0,
                    ambiguity_score=0.0,
                    complexity=1,
                    evidence={"type": "single_property"},
                ))
        return candidates

    def search_conjunctions(
        self,
        per_pair_targets: List[Dict],
    ) -> List[SelectorCandidate]:
        candidates = []
        top_props = self.all_props[:50]
        for p1, p2 in combinations(top_props, 2):
            conj = f"{p1}&{p2}"
            fits_all = True
            for pp in per_pair_targets:
                objs = pp["objects"]
                target_idx = pp["target_indices"]
                non_target_idx = pp["non_target_indices"]
                if not target_idx or not non_target_idx:
                    fits_all = False
                    break
                t_vals = [_get_property_value(objs[i], conj) for i in target_idx]
                nt_vals = [_get_property_value(objs[i], conj) for i in non_target_idx]
                if not ((all(t_vals) and not any(nt_vals)) or
                        (not any(t_vals) and all(nt_vals))):
                    fits_all = False
                    break
            if fits_all:
                candidates.append(SelectorCandidate(
                    selector_expression=conj,
                    selector_type="conjunction",
                    property_names=[p1, p2],
                    selected_object_ids=[],
                    target_object_ids=[],
                    train_fit_score=1.0,
                    ambiguity_score=0.0,
                    complexity=2,
                    evidence={"type": "conjunction"},
                ))
        return candidates

    def search_negations(
        self,
        per_pair_targets: List[Dict],
    ) -> List[SelectorCandidate]:
        candidates = []
        top_props = self.all_props[:30]
        for p1 in top_props:
            for p2 in top_props:
                if p1 == p2:
                    continue
                neg = f"{p1}&!{p2}"
                fits_all = True
                for pp in per_pair_targets:
                    objs = pp["objects"]
                    target_idx = pp["target_indices"]
                    non_target_idx = pp["non_target_indices"]
                    if not target_idx or not non_target_idx:
                        fits_all = False
                        break
                    t_vals = [_get_property_value(objs[i], neg) for i in target_idx]
                    nt_vals = [_get_property_value(objs[i], neg) for i in non_target_idx]
                    if not ((all(t_vals) and not any(nt_vals)) or
                            (not any(t_vals) and all(nt_vals))):
                        fits_all = False
                        break
                if fits_all:
                    candidates.append(SelectorCandidate(
                        selector_expression=neg,
                        selector_type="negation",
                        property_names=[p1, p2],
                        selected_object_ids=[],
                        target_object_ids=[],
                        train_fit_score=1.0,
                        ambiguity_score=0.0,
                        complexity=2,
                        evidence={"type": "negation"},
                    ))
        return candidates

    def search_rank_selectors(
        self,
        per_pair_targets: List[Dict],
    ) -> List[SelectorCandidate]:
        """Rank-based selectors: largest, smallest, nth by area/position."""
        candidates = []
        rank_props = [
            "is_largest", "is_smallest", "is_2nd_largest", "is_3rd_largest",
            "first_in_scan_order", "last_in_scan_order",
            "is_largest_in_color_group", "is_smallest_in_color_group",
        ]
        for prop in rank_props:
            if prop in self.all_props:
                fits_all = True
                for pp in per_pair_targets:
                    objs = pp["objects"]
                    target_idx = pp["target_indices"]
                    non_target_idx = pp["non_target_indices"]
                    if not target_idx or not non_target_idx:
                        fits_all = False
                        break
                    t_vals = [_get_property_value(objs[i], prop) for i in target_idx]
                    nt_vals = [_get_property_value(objs[i], prop) for i in non_target_idx]
                    if not ((all(t_vals) and not any(nt_vals)) or
                            (not any(t_vals) and all(nt_vals))):
                        fits_all = False
                        break
                if fits_all:
                    candidates.append(SelectorCandidate(
                        selector_expression=prop,
                        selector_type="rank",
                        property_names=[prop],
                        selected_object_ids=[],
                        target_object_ids=[],
                        train_fit_score=1.0,
                        ambiguity_score=0.0,
                        complexity=1,
                        evidence={"type": "rank"},
                    ))
        return candidates

    def search_marker_frame_anchor_relations(
        self,
        per_pair_targets: List[Dict],
    ) -> List[SelectorCandidate]:
        """Relational selectors: marker, frame, anchor based."""
        candidates = []
        relational_props = [
            "is_marker", "touches_marker",
            "aligned_with_marker_row", "aligned_with_marker_col",
            "same_color_as_marker", "nearest_to_marker",
            "inside_frame", "outside_all_frames",
            "between_markers",
            "nearest_to_unique_color", "same_shape_as_unique_color",
            "is_contained", "is_container",
            "touches_largest", "same_color_as_largest",
            "same_row_as_largest", "same_col_as_largest",
            "above_largest", "below_largest",
            "left_of_largest", "right_of_largest",
        ]
        for prop in relational_props:
            if prop not in self.all_props:
                continue
            fits_all = True
            for pp in per_pair_targets:
                objs = pp["objects"]
                target_idx = pp["target_indices"]
                non_target_idx = pp["non_target_indices"]
                if not target_idx or not non_target_idx:
                    fits_all = False
                    break
                t_vals = [_get_property_value(objs[i], prop) for i in target_idx]
                nt_vals = [_get_property_value(objs[i], prop) for i in non_target_idx]
                if not ((all(t_vals) and not any(nt_vals)) or
                        (not any(t_vals) and all(nt_vals))):
                    fits_all = False
                    break
            if fits_all:
                candidates.append(SelectorCandidate(
                    selector_expression=prop,
                    selector_type="marker_relation",
                    property_names=[prop],
                    selected_object_ids=[],
                    target_object_ids=[],
                    train_fit_score=1.0,
                    ambiguity_score=0.0,
                    complexity=1,
                    evidence={"type": "relational"},
                ))
        return candidates

    def propose_selectors(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        object_trace: Optional[Dict] = None,
        failure_trace: Optional[Dict] = None,
    ) -> List[SelectorCandidate]:
        """Main entry point: search all selector types, return ranked candidates."""
        per_pair = self.infer_targets_from_change(train_pairs, object_trace)

        valid = [pp for pp in per_pair if pp["target_indices"] and pp["non_target_indices"]]
        if not valid:
            return []

        candidates = []

        # Fast: single properties
        candidates.extend(self.search_single_properties(valid))
        if candidates:
            return self._rank_and_deduplicate(candidates)

        # Medium: rank selectors (subset of single but searched separately for clarity)
        candidates.extend(self.search_rank_selectors(valid))
        if candidates:
            return self._rank_and_deduplicate(candidates)

        # Medium: relational selectors
        candidates.extend(self.search_marker_frame_anchor_relations(valid))
        if candidates:
            return self._rank_and_deduplicate(candidates)

        # Slower: conjunctions
        candidates.extend(self.search_conjunctions(valid))
        if candidates:
            return self._rank_and_deduplicate(candidates)

        # Slowest: negations
        candidates.extend(self.search_negations(valid))
        return self._rank_and_deduplicate(candidates)

    def build_selector_callable(
        self, selector_expr: str
    ) -> Callable[[List[Dict]], List[bool]]:
        """Build an executable selector function from a selector expression."""
        def _select(objects: List[Dict], _expr=selector_expr) -> List[bool]:
            return [_get_property_value(obj, _expr) for obj in objects]
        return _select

    def _rank_and_deduplicate(
        self, candidates: List[SelectorCandidate]
    ) -> List[SelectorCandidate]:
        seen = set()
        unique = []
        for c in candidates:
            if c.selector_expression not in seen:
                seen.add(c.selector_expression)
                unique.append(c)
        return sorted(unique, key=lambda c: (c.complexity, -c.train_fit_score))
