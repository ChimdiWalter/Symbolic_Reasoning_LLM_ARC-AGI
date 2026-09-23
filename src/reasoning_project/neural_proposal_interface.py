"""Neural proposal interface: advisory-only ranking from neural/VLM/ViT modules.

Neural output can only rank/propose operator families and selectors.
It cannot solve directly. All proposals must pass through ProposalVerifier.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

if TYPE_CHECKING:
    from reasoning_project.adaptive_orchestrator import TaskAnalysis


@dataclass
class NeuralProposal:
    operator_family_ranking: List[Tuple[str, float]]
    selector_candidates: List[Tuple[str, float]]
    relation_candidates: List[Tuple[str, float]]
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    selector_type_ranking: List[Tuple[str, float]] = field(default_factory=list)
    object_schema_hint: Optional[str] = None
    target_region_hint: Optional[str] = None
    neural_helped_routing: bool = False


class NeuralProposalInterface:
    """Advisory neural module for operator family ranking and selector proposals.

    Sources:
    - JEPA perception heads (if checkpoint available)
    - Rule-based fallback (always available)
    """

    def __init__(self, checkpoint_path: Optional[str] = None):
        self.checkpoint_path = checkpoint_path
        self._model_loaded = False
        self._perception_heads = None
        self._validation_history: List[Dict[str, Any]] = []

    def propose(
        self,
        analysis: "TaskAnalysis",
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> Optional[NeuralProposal]:
        if self._model_loaded and self._perception_heads is not None:
            return self._propose_neural(analysis, train_pairs)
        return self._propose_rule_based(analysis, train_pairs)

    def calibrate(self, validation_history: List[Dict[str, Any]]) -> None:
        self._validation_history = validation_history

    def _propose_neural(
        self, analysis: "TaskAnalysis", train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Optional[NeuralProposal]:
        return self._propose_rule_based(analysis, train_pairs)

    def _propose_rule_based(
        self, analysis: "TaskAnalysis", train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Optional[NeuralProposal]:
        pairs = analysis.object_trace.get("pairs", [])
        if not pairs:
            return None

        families = []
        has_size_change = any(p.get("size_change") for p in pairs)
        has_many_objects = any(p.get("n_input_objects", 0) > 5 for p in pairs)
        has_few_objects = all(p.get("n_input_objects", 0) <= 3 for p in pairs)
        has_many_to_few = any(
            p.get("n_input_objects", 0) > p.get("n_output_objects", 1)
            for p in pairs
        )
        has_same_objects = all(
            p.get("n_input_objects", 0) == p.get("n_output_objects", 0)
            for p in pairs
        )

        selector_type_ranking = []
        object_schema_hint = None
        target_region_hint = None

        if has_size_change:
            families.append(("separator_decompose", 0.7))
            families.append(("crop_extract", 0.6))
            families.append(("shape_completion", 0.4))
            selector_type_ranking.append(("rank", 0.6))
            selector_type_ranking.append(("single", 0.5))
            target_region_hint = "size_change_extract"
        elif has_many_to_few:
            families.append(("many_to_few_grouping", 0.5))
            families.append(("filter_select", 0.6))
            selector_type_ranking.append(("single", 0.7))
            selector_type_ranking.append(("conjunction", 0.4))
        elif has_many_objects:
            families.append(("filter_select", 0.6))
            families.append(("recolor", 0.5))
            families.append(("color_transfer", 0.4))
            selector_type_ranking.append(("single", 0.6))
            selector_type_ranking.append(("marker_relation", 0.5))
            selector_type_ranking.append(("conjunction", 0.4))
        elif has_few_objects:
            families.append(("copy_to_position", 0.5))
            families.append(("recolor", 0.4))
            selector_type_ranking.append(("rank", 0.5))
            selector_type_ranking.append(("marker_relation", 0.5))

        if has_same_objects and not has_size_change:
            families.append(("position_within_object_recolor", 0.4))
            families.append(("select_then_recolor", 0.4))
            if not selector_type_ranking:
                selector_type_ranking.append(("single", 0.5))
                selector_type_ranking.append(("rank", 0.4))

        if not families:
            families.append(("trace_invention", 0.3))

        selectors = []
        if analysis.property_trace.get("has_discriminative_property"):
            prop = analysis.property_trace.get("best_property", "")
            selectors.append((prop, 0.8))
        else:
            # Suggest selectors based on object structure
            selectors.append(("is_largest", 0.3))
            selectors.append(("is_most_common_color", 0.3))
            selectors.append(("is_unique_color", 0.25))
            selectors.append(("touches_boundary", 0.2))
            if has_few_objects:
                selectors.append(("is_marker", 0.3))
                selectors.append(("nearest_to_marker", 0.25))

        # Schema hint: if few objects extracted, suggest alternatives
        if pairs and all(p.get("n_input_objects", 0) < 3 for p in pairs):
            object_schema_hint = "per_color_components"
        elif pairs and any(p.get("n_input_objects", 0) > 10 for p in pairs):
            object_schema_hint = "monochrome_components"

        confidence = 0.4 if families else 0.1

        return NeuralProposal(
            operator_family_ranking=families,
            selector_candidates=selectors,
            relation_candidates=[],
            confidence=confidence,
            evidence={"source": "rule_based_fallback"},
            selector_type_ranking=selector_type_ranking,
            object_schema_hint=object_schema_hint,
            target_region_hint=target_region_hint,
            neural_helped_routing=True,
        )
