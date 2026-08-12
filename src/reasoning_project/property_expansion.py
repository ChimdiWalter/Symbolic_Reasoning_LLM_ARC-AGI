"""Property expansion engine for the v2 orchestrator.

Searches the full property language (core + relational) for discriminative
properties that separate kept from removed objects in training pairs.

When single-property search fails, delegates to SelectorInventor for
conjunctions, negations, rank selectors, and marker/frame relations.
Returns executable selector expressions that can pair with multiple
operator families.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.reasoning_engine import (
    BOOLEAN_PROPERTIES,
    DERIVED_PREDICATES,
    RELATIONAL_EXPANDED_PROPERTIES,
    _all_property_names,
    _classify_kept_removed,
    _extract_objects_with_properties,
    _add_relational_properties,
    _get_property_value,
)
from reasoning_project.selector_invention import SelectorInventor, SelectorCandidate


class PropertyExpansionEngine:
    """Find discriminative properties from the full property language."""

    def __init__(self):
        self.selector_inventor = SelectorInventor()

    def find_discriminative_property(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        object_trace: Dict[str, Any],
        failure_trace: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Search all properties for those that discriminate kept/removed objects.

        Returns properties sorted by discrimination score (fraction of training
        pairs where the property perfectly separates kept from removed).
        Falls back to SelectorInventor for conjunctions/negations when
        single-property search finds nothing with score 1.0.
        """
        all_props = _all_property_names()
        already_tried = set(failure_trace.get("properties_tried", []))

        results = []
        has_perfect = False
        for prop_name in all_props:
            if prop_name in already_tried:
                continue
            score = self._evaluate_discrimination(prop_name, train_pairs)
            if score > 0.0:
                results.append({
                    "name": prop_name,
                    "family": self._property_family(prop_name),
                    "score": score,
                    "complexity": self._complexity(prop_name),
                })
                if score >= 1.0:
                    has_perfect = True

        if not has_perfect:
            selector_candidates = self.selector_inventor.propose_selectors(
                train_pairs, object_trace, failure_trace,
            )
            for sc in selector_candidates:
                if sc.selector_expression not in already_tried:
                    results.append({
                        "name": sc.selector_expression,
                        "family": f"invented_{sc.selector_type}",
                        "score": sc.train_fit_score,
                        "complexity": sc.complexity,
                        "selector_type": sc.selector_type,
                        "selector_candidate": sc,
                    })

        results.sort(key=lambda x: (-x["score"], x["complexity"]))
        return results

    def find_executable_selectors(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        object_trace: Dict[str, Any],
        failure_trace: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Return selector results with executable callable attached.

        Each result has:
          selector_expression, selector_callable, selected_objects,
          property_names, score, complexity, ambiguity, evidence
        """
        candidates = self.selector_inventor.propose_selectors(
            train_pairs, object_trace, failure_trace,
        )
        results = []
        for sc in candidates:
            selector_fn = self.selector_inventor.build_selector_callable(
                sc.selector_expression
            )
            results.append({
                "selector_expression": sc.selector_expression,
                "selector_callable": selector_fn,
                "selected_objects": sc.selected_object_ids,
                "property_names": sc.property_names,
                "score": sc.train_fit_score,
                "complexity": sc.complexity,
                "ambiguity": sc.ambiguity_score,
                "evidence": sc.evidence,
                "selector_type": sc.selector_type,
            })
        return results

    def evaluate_single(
        self,
        prop_name: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        object_trace: Dict[str, Any],
    ) -> float:
        return self._evaluate_discrimination(prop_name, train_pairs)

    def get_property_catalog(self) -> List[Dict[str, Any]]:
        catalog = []
        for prop in _all_property_names():
            catalog.append({
                "name": prop,
                "family": self._property_family(prop),
                "complexity": self._complexity(prop),
            })
        return catalog

    def get_all_property_names(self) -> List[str]:
        return _all_property_names()

    def _evaluate_discrimination(
        self,
        prop_name: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> float:
        """Fraction of training pairs where prop_name perfectly separates
        kept from removed objects (all-true-kept/all-false-removed or vice versa)."""
        if not train_pairs:
            return 0.0

        n_good = 0
        n_classifiable = 0
        for inp, out in train_pairs:
            objs = _extract_objects_with_properties(inp)
            kr = _classify_kept_removed(objs, inp, out)
            if kr is None:
                continue
            n_classifiable += 1
            kept_idx, removed_idx = kr
            kv = [_get_property_value(objs[k], prop_name) for k in kept_idx]
            rv = [_get_property_value(objs[r], prop_name) for r in removed_idx]
            if (all(kv) and not any(rv)) or (not any(kv) and all(rv)):
                n_good += 1

        if n_classifiable == 0:
            return 0.0
        return n_good / n_classifiable

    def _property_family(self, prop_name: str) -> str:
        if prop_name in RELATIONAL_EXPANDED_PROPERTIES:
            if "marker" in prop_name:
                return "marker_relative"
            if "frame" in prop_name:
                return "frame_relative"
            if "unique_color" in prop_name:
                return "unique_color_relative"
            if "rotation" in prop_name:
                return "topology"
            if "scan_order" in prop_name:
                return "scan_order"
            return "relational"
        if prop_name in BOOLEAN_PROPERTIES:
            return "core"
        for name, _ in DERIVED_PREDICATES:
            if name == prop_name:
                if "color" in name:
                    return "color"
                if "area" in name or "size" in name or "largest" in name:
                    return "size"
                if "touch" in name or "adjacent" in name:
                    return "adjacency"
                if "sym" in name or "rot" in name:
                    return "symmetry"
                return "derived"
        return "unknown"

    def _complexity(self, prop_name: str) -> int:
        if prop_name in BOOLEAN_PROPERTIES:
            return 1
        if prop_name in RELATIONAL_EXPANDED_PROPERTIES:
            return 2
        return 2
