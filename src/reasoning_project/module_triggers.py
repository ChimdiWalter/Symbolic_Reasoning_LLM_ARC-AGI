"""Module trigger logic for the Gated Adaptive Reasoning Orchestrator.

Each trigger function returns (triggered: bool, reason: str).
Triggers determine when each module should be called vs skipped.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from reasoning_project.adaptive_orchestrator import TaskAnalysis


def should_call_adapter_genesis(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    if analysis.domain != "arc":
        return True, "non_arc_domain_requires_genesis"

    if not analysis.adapter_status.get("adapter_ok", True):
        return True, "adapter_extraction_failed"

    if analysis.adapter_status.get("confidence", 1.0) < 0.5:
        return True, "adapter_low_confidence"

    pairs = analysis.object_trace.get("pairs", [])
    if pairs and all(p.get("n_input_objects", 0) < 2 for p in pairs):
        return True, "object_extraction_instability"

    if not analysis.property_trace.get("has_discriminative_property"):
        return True, "no_discriminative_property_try_alternate_perception"

    return False, "arc_adapter_sufficient"


def should_call_manifold_memory(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    if analysis.memory_retrievals:
        closest = min(
            (r.get("distance", float("inf")) for r in analysis.memory_retrievals),
            default=float("inf"),
        )
        if closest < 2.0:
            return True, f"similar_task_in_memory_d={closest:.2f}"

    if not analysis.property_trace.get("has_discriminative_property"):
        return True, "no_discriminative_property_check_memory"

    if analysis.failure_trace.get("failure_type") == "generation_failure":
        return True, "generation_failure_check_memory"

    return False, "no_relevant_memory_signal"


def should_call_near_solved_memory(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    if analysis.failure_trace.get("failure_type") == "no_discriminative_property":
        return True, "property_failure_may_have_near_solved_state"

    if analysis.failure_trace.get("failure_type") == "generation_failure":
        return True, "generation_failure_may_have_partial_solution"

    pairs = analysis.object_trace.get("pairs", [])
    if pairs and any(p.get("n_input_objects", 0) >= 2 for p in pairs):
        return True, "sufficient_objects_for_near_solved_resume"

    return False, "no_near_solved_signal"


def should_call_operator_memory(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    if analysis.candidate_operator_families:
        return True, f"candidate_families_detected:{','.join(analysis.candidate_operator_families[:3])}"

    if analysis.memory_retrievals:
        return True, "memory_retrievals_may_contain_operators"

    return False, "no_operator_candidates"


def should_call_neural_advisory(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    if len(analysis.candidate_operator_families) > 3:
        return True, "high_routing_uncertainty"

    if not analysis.property_trace.get("has_discriminative_property"):
        return True, "no_property_neural_may_help_route"

    if analysis.failure_trace.get("failure_type") == "generation_failure":
        return True, "generation_failure_neural_ranking"

    return False, "routing_clear_no_neural_needed"


def should_call_domain_morphism(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    if analysis.domain != "arc":
        return True, "non_arc_domain_needs_morphism"

    if analysis.morphism_candidates:
        return True, "morphism_candidates_available"

    if analysis.domain_signature:
        return True, "domain_signature_available_for_transfer"

    return False, "arc_domain_no_morphism_needed"


def should_call_property_expansion(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    if not analysis.property_trace.get("has_discriminative_property"):
        return True, "no_discriminative_property_expand"

    score = analysis.property_trace.get("score", 0.0)
    if score < 0.8:
        return True, f"weak_property_score={score:.2f}"

    return False, "strong_property_exists"


def should_call_frontier_operators(analysis: "TaskAnalysis") -> Tuple[bool, str]:
    pairs = analysis.object_trace.get("pairs", [])

    has_size_change = any(p.get("size_change") for p in pairs)
    has_many_to_few = any(
        p.get("n_input_objects", 0) > p.get("n_output_objects", 1)
        for p in pairs
    )

    frontier_families = {"shape_completion", "position_recolor", "many_to_few_grouping",
                         "color_transfer", "copy_to_position", "project_to_halo", "quadrant_fill"}
    overlap = frontier_families & set(analysis.candidate_operator_families)

    if overlap:
        return True, f"frontier_families_detected:{','.join(overlap)}"

    if has_size_change:
        return True, "size_change_may_need_frontier_op"

    if has_many_to_few:
        return True, "many_to_few_detected"

    if analysis.property_trace.get("has_discriminative_property"):
        prop = analysis.property_trace.get("best_property", "")
        if any(kw in str(prop) for kw in ["position", "interior", "boundary", "shape"]):
            return True, f"property_suggests_frontier:{prop}"

    return False, "no_frontier_signal"
