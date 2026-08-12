"""Formal operator semantics for failure-derived reasoning operators.

Defines typed representations for operator hypotheses with machine-checkable
preconditions, postconditions, invariants, and proof obligations. These are
the formal contracts that every operator must satisfy before acceptance.

This module does NOT solve ARC tasks. It defines what it means for an
operator hypothesis to be valid.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════
# FORMAL CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OperatorPrecondition:
    name: str
    expression: str
    check_fn: Callable[..., bool]

    def check(self, **kwargs: Any) -> bool:
        try:
            return bool(self.check_fn(**kwargs))
        except Exception:
            return False


@dataclass
class OperatorPostcondition:
    name: str
    expression: str
    check_fn: Callable[..., bool]

    def check(self, **kwargs: Any) -> bool:
        try:
            return bool(self.check_fn(**kwargs))
        except Exception:
            return False


@dataclass
class OperatorInvariant:
    name: str
    expression: str
    check_fn: Callable[..., bool]

    def check(self, **kwargs: Any) -> bool:
        try:
            return bool(self.check_fn(**kwargs))
        except Exception:
            return False


@dataclass
class OperatorProofObligation:
    obligation_id: str
    description: str
    status: str  # "passed", "failed", "unknown", "skipped"
    counterexample: Optional[Dict[str, Any]] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProofObligationResult:
    obligation: OperatorProofObligation
    checked: bool
    passed: bool
    details: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTABLE OPERATOR HYPOTHESIS
# ═══════════════════════════════════════════════════════════════════════════

VALIDATION_LEVELS = [
    "proposed",
    "parameterized",
    "train_consistent",
    "loo_validated",
    "falsification_validated",
    "promotion_validated",
    "transfer_validated",
]


@dataclass
class ExecutableOperatorHypothesis:
    operator_id: str
    family: str
    source_tasks: List[str]
    selector_expression: str
    parameters: Dict[str, Any]
    preconditions: List[OperatorPrecondition]
    postconditions: List[OperatorPostcondition]
    invariants: List[OperatorInvariant]
    replay_fn: Optional[Callable] = None
    complexity: int = 1
    provenance: Dict[str, Any] = field(default_factory=dict)
    validation_level: str = "proposed"
    proof_obligations: List[OperatorProofObligation] = field(default_factory=list)
    rejection_reason: Optional[str] = None

    def advance_level(self, new_level: str) -> None:
        if new_level in VALIDATION_LEVELS:
            cur = VALIDATION_LEVELS.index(self.validation_level)
            nxt = VALIDATION_LEVELS.index(new_level)
            if nxt > cur:
                self.validation_level = new_level

    def check_preconditions(self, **kwargs: Any) -> List[ProofObligationResult]:
        results = []
        for pre in self.preconditions:
            passed = pre.check(**kwargs)
            obl = OperatorProofObligation(
                obligation_id=f"pre_{pre.name}",
                description=f"Precondition: {pre.expression}",
                status="passed" if passed else "failed",
                evidence={"kwargs_keys": list(kwargs.keys())},
            )
            results.append(ProofObligationResult(
                obligation=obl, checked=True, passed=passed,
            ))
        return results

    def check_postconditions(self, **kwargs: Any) -> List[ProofObligationResult]:
        results = []
        for post in self.postconditions:
            passed = post.check(**kwargs)
            obl = OperatorProofObligation(
                obligation_id=f"post_{post.name}",
                description=f"Postcondition: {post.expression}",
                status="passed" if passed else "failed",
                evidence={"kwargs_keys": list(kwargs.keys())},
            )
            results.append(ProofObligationResult(
                obligation=obl, checked=True, passed=passed,
            ))
        return results

    def check_invariants(self, **kwargs: Any) -> List[ProofObligationResult]:
        results = []
        for inv in self.invariants:
            passed = inv.check(**kwargs)
            obl = OperatorProofObligation(
                obligation_id=f"inv_{inv.name}",
                description=f"Invariant: {inv.expression}",
                status="passed" if passed else "failed",
                evidence={"kwargs_keys": list(kwargs.keys())},
            )
            results.append(ProofObligationResult(
                obligation=obl, checked=True, passed=passed,
            ))
        return results

    def all_obligations_passed(self) -> bool:
        return all(o.status == "passed" for o in self.proof_obligations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "family": self.family,
            "source_tasks": self.source_tasks,
            "selector_expression": self.selector_expression,
            "parameters": self.parameters,
            "complexity": self.complexity,
            "validation_level": self.validation_level,
            "rejection_reason": self.rejection_reason,
            "provenance": self.provenance,
            "proof_obligations": [
                {
                    "id": o.obligation_id,
                    "description": o.description,
                    "status": o.status,
                    "counterexample": o.counterexample,
                }
                for o in self.proof_obligations
            ],
            "n_preconditions": len(self.preconditions),
            "n_postconditions": len(self.postconditions),
            "n_invariants": len(self.invariants),
        }


# ═══════════════════════════════════════════════════════════════════════════
# COPY-TO-POSITION FORMAL OBLIGATIONS
# ═══════════════════════════════════════════════════════════════════════════

def _make_ctp_preconditions() -> List[OperatorPrecondition]:
    return [
        OperatorPrecondition(
            name="source_objects_nonempty",
            expression="len(source_objects) > 0",
            check_fn=lambda source_objects=None, **kw: (
                source_objects is not None and len(source_objects) > 0
            ),
        ),
        OperatorPrecondition(
            name="destination_rule_defined",
            expression="destination_rule is not None",
            check_fn=lambda destination_rule=None, **kw: (
                destination_rule is not None
            ),
        ),
        OperatorPrecondition(
            name="destination_in_bounds",
            expression="all destinations within grid bounds",
            check_fn=lambda destinations=None, grid_shape=None, **kw: (
                destinations is not None and grid_shape is not None
                and all(
                    0 <= r < grid_shape[0] and 0 <= c < grid_shape[1]
                    for r, c in destinations
                )
            ),
        ),
        OperatorPrecondition(
            name="source_mask_well_defined",
            expression="every source object has a valid pixel mask",
            check_fn=lambda source_masks=None, **kw: (
                source_masks is not None
                and all(m is not None and m.any() for m in source_masks)
            ),
        ),
        OperatorPrecondition(
            name="parameters_consistent",
            expression="displacement vectors are consistent across training examples or reference rule explains variation",
            check_fn=lambda params_consistent=None, **kw: (
                params_consistent is True
            ),
        ),
    ]


def _make_ctp_postconditions() -> List[OperatorPostcondition]:
    return [
        OperatorPostcondition(
            name="object_at_destination",
            expression="output contains copied object at destination",
            check_fn=lambda output_grid=None, expected_output=None, **kw: (
                output_grid is not None and expected_output is not None
                and np.array_equal(output_grid, expected_output)
            ),
        ),
        OperatorPostcondition(
            name="shape_preserved",
            expression="shape of copied object matches source if preserve_shape=True",
            check_fn=lambda source_shape=None, dest_shape=None, preserve_shape=True, **kw: (
                not preserve_shape or source_shape == dest_shape
            ),
        ),
        OperatorPostcondition(
            name="color_preserved",
            expression="colors of copied object match source if preserve_color=True",
            check_fn=lambda source_colors=None, dest_colors=None, preserve_color=True, **kw: (
                not preserve_color or source_colors == dest_colors
            ),
        ),
        OperatorPostcondition(
            name="no_undeclared_modifications",
            expression="non-target cells unchanged except by declared copy/move mode",
            check_fn=lambda input_grid=None, output_grid=None, modified_mask=None, declared_mask=None, **kw: (
                modified_mask is None or declared_mask is None
                or np.all(modified_mask <= declared_mask)
            ),
        ),
    ]


def _make_ctp_invariants() -> List[OperatorInvariant]:
    return [
        OperatorInvariant(
            name="grid_size_unchanged",
            expression="output grid has same shape as input grid",
            check_fn=lambda input_grid=None, output_grid=None, **kw: (
                input_grid is not None and output_grid is not None
                and input_grid.shape == output_grid.shape
            ),
        ),
        OperatorInvariant(
            name="non_target_objects_unchanged",
            expression="objects not selected by selector remain unchanged",
            check_fn=lambda non_target_preserved=None, **kw: (
                non_target_preserved is True
            ),
        ),
        OperatorInvariant(
            name="topology_preserved",
            expression="selected object topology (connected components, holes) preserved at destination",
            check_fn=lambda source_topology=None, dest_topology=None, **kw: (
                source_topology is None or dest_topology is None
                or source_topology == dest_topology
            ),
        ),
        OperatorInvariant(
            name="color_set_preserved",
            expression="selected object color set preserved at destination",
            check_fn=lambda source_color_set=None, dest_color_set=None, **kw: (
                source_color_set is None or dest_color_set is None
                or source_color_set == dest_color_set
            ),
        ),
    ]


def make_copy_to_position_hypothesis(
    task_id: str,
    selector_expression: str,
    parameters: Dict[str, Any],
    source_tasks: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ExecutableOperatorHypothesis:
    return ExecutableOperatorHypothesis(
        operator_id=f"ctp_{task_id}_{uuid.uuid4().hex[:8]}",
        family="copy_to_position",
        source_tasks=source_tasks or [task_id],
        selector_expression=selector_expression,
        parameters=parameters,
        preconditions=_make_ctp_preconditions(),
        postconditions=_make_ctp_postconditions(),
        invariants=_make_ctp_invariants(),
        complexity=len(parameters.get("displacements", [])) + 2,
        provenance=provenance or {"derived_from": "operator_gap_trace"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# MARKER-RELATIVE COPY-TO-POSITION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AnchorReference:
    """Reference to an anchor object used for relative positioning."""
    anchor_type: str  # e.g. "nearest_kept", "same_color", "same_shape", "largest_kept"
    selector_expression: str
    object_id: Optional[str] = None
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RelativeDestinationRule:
    """Describes how a destination is computed relative to an anchor object."""
    rule_type: str  # e.g. "offset_from_anchor", "align_row", "align_col", "inside_anchor_bbox", "adjacent_to_anchor"
    anchor: AnchorReference = field(default_factory=lambda: AnchorReference(
        anchor_type="nearest_kept", selector_expression="",
    ))
    offset: Optional[Tuple[int, int]] = None
    alignment: Optional[str] = None  # e.g. "center", "top_left", "bottom_right"
    evidence: Dict[str, Any] = field(default_factory=dict)


def _make_marker_relative_preconditions() -> List[OperatorPrecondition]:
    """Preconditions for marker-relative copy-to-position.

    Includes all standard CTP preconditions plus anchor-specific ones.
    """
    base = _make_ctp_preconditions()
    anchor_preconditions = [
        OperatorPrecondition(
            name="anchor_selector_returns_object",
            expression="anchor selector returns at least one anchor object",
            check_fn=lambda anchor_objects=None, **kw: (
                anchor_objects is not None and len(anchor_objects) > 0
            ),
        ),
        OperatorPrecondition(
            name="anchor_unambiguous",
            expression="exactly one anchor per source, or disambiguation rule is defined",
            check_fn=lambda anchor_objects=None, disambiguation_rule=None, **kw: (
                anchor_objects is not None
                and (len(anchor_objects) == 1 or disambiguation_rule is not None)
            ),
        ),
        OperatorPrecondition(
            name="relative_destination_defined",
            expression="relative destination rule is defined",
            check_fn=lambda relative_destination_rule=None, **kw: (
                relative_destination_rule is not None
            ),
        ),
    ]
    return anchor_preconditions + base


def _make_marker_relative_postconditions() -> List[OperatorPostcondition]:
    """Postconditions for marker-relative copy-to-position.

    Includes all standard CTP postconditions plus anchor-consistency check.
    """
    base = _make_ctp_postconditions()
    anchor_postconditions = [
        OperatorPostcondition(
            name="anchor_consistency",
            expression="relative offset from anchor to destination is consistent across examples",
            check_fn=lambda offsets_consistent=None, **kw: (
                offsets_consistent is True
            ),
        ),
    ]
    return base + anchor_postconditions


def _make_marker_relative_invariants() -> List[OperatorInvariant]:
    """Invariants for marker-relative copy-to-position.

    Includes all standard CTP invariants plus anchor preservation.
    """
    base = _make_ctp_invariants()
    anchor_invariants = [
        OperatorInvariant(
            name="anchor_unchanged",
            expression="anchor object is preserved in output",
            check_fn=lambda input_grid=None, output_grid=None, anchor_mask=None, **kw: (
                input_grid is not None and output_grid is not None
                and anchor_mask is not None
                and np.array_equal(
                    input_grid[anchor_mask],
                    output_grid[anchor_mask],
                )
            ),
        ),
    ]
    return base + anchor_invariants


def make_marker_relative_hypothesis(
    task_id: str,
    selector_expression: str,
    parameters: Dict[str, Any],
    source_tasks: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ExecutableOperatorHypothesis:
    """Factory for marker-relative copy-to-position operator hypotheses.

    Similar to make_copy_to_position_hypothesis but with additional
    preconditions for anchor selection and relative destination computation.
    """
    return ExecutableOperatorHypothesis(
        operator_id=f"mrctp_{task_id}_{uuid.uuid4().hex[:8]}",
        family="marker_relative_copy_to_position",
        source_tasks=source_tasks or [task_id],
        selector_expression=selector_expression,
        parameters=parameters,
        preconditions=_make_marker_relative_preconditions(),
        postconditions=_make_marker_relative_postconditions(),
        invariants=_make_marker_relative_invariants(),
        complexity=len(parameters.get("displacements", [])) + 4,
        provenance=provenance or {"derived_from": "operator_gap_trace"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# CORRESPONDENCE-BASED COPY-TO-POSITION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CorrespondenceCopyParams:
    source_selector: str
    correspondence_rule_type: str
    correspondence_rule_id: str
    relative_displacement: Optional[Tuple[int, int]]
    copy_mode: str  # "copy", "move", "copy_and_keep"
    preserve_shape: bool
    preserve_color: bool
    allow_overlap: bool
    background_color: int
    tie_breaker: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_selector": self.source_selector,
            "correspondence_rule_type": self.correspondence_rule_type,
            "correspondence_rule_id": self.correspondence_rule_id,
            "relative_displacement": list(self.relative_displacement) if self.relative_displacement else None,
            "copy_mode": self.copy_mode,
            "preserve_shape": self.preserve_shape,
            "preserve_color": self.preserve_color,
            "allow_overlap": self.allow_overlap,
            "background_color": self.background_color,
            "tie_breaker": self.tie_breaker,
        }


def _make_correspondence_preconditions() -> List[OperatorPrecondition]:
    base = _make_ctp_preconditions()
    correspondence_preconditions = [
        OperatorPrecondition(
            name="correspondence_rule_defined",
            expression="a correspondence rule mapping source→target objects is defined",
            check_fn=lambda correspondence_rule=None, **kw: (
                correspondence_rule is not None
            ),
        ),
        OperatorPrecondition(
            name="correspondence_injective",
            expression="no two source objects map to the same target object",
            check_fn=lambda correspondence_injective=None, **kw: (
                correspondence_injective is True
            ),
        ),
        OperatorPrecondition(
            name="correspondence_unambiguous",
            expression="every source has exactly one matching target, no ties unresolved",
            check_fn=lambda correspondence_unambiguous=None, **kw: (
                correspondence_unambiguous is True
            ),
        ),
        OperatorPrecondition(
            name="correspondence_consistent",
            expression="correspondence rule produces same matching across all training pairs",
            check_fn=lambda correspondence_consistent=None, **kw: (
                correspondence_consistent is True
            ),
        ),
    ]
    return correspondence_preconditions + base


def _make_correspondence_postconditions() -> List[OperatorPostcondition]:
    base = _make_ctp_postconditions()
    correspondence_postconditions = [
        OperatorPostcondition(
            name="matched_displacement_consistent",
            expression="relative displacement from matched target to source destination is consistent",
            check_fn=lambda displacement_consistent=None, **kw: (
                displacement_consistent is True
            ),
        ),
    ]
    return base + correspondence_postconditions


def _make_correspondence_invariants() -> List[OperatorInvariant]:
    base = _make_ctp_invariants()
    correspondence_invariants = [
        OperatorInvariant(
            name="target_objects_unchanged",
            expression="target/anchor objects used for correspondence are preserved in output",
            check_fn=lambda target_preserved=None, **kw: (
                target_preserved is True
            ),
        ),
        OperatorInvariant(
            name="correspondence_structure_preserved",
            expression="matching property (color/shape/size/topology) is preserved between source and its matched target",
            check_fn=lambda correspondence_preserved=None, **kw: (
                correspondence_preserved is True
            ),
        ),
    ]
    return base + correspondence_invariants


def make_correspondence_hypothesis(
    task_id: str,
    selector_expression: str,
    parameters: Dict[str, Any],
    source_tasks: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ExecutableOperatorHypothesis:
    return ExecutableOperatorHypothesis(
        operator_id=f"cctp_{task_id}_{uuid.uuid4().hex[:8]}",
        family="correspondence_copy_to_position",
        source_tasks=source_tasks or [task_id],
        selector_expression=selector_expression,
        parameters=parameters,
        preconditions=_make_correspondence_preconditions(),
        postconditions=_make_correspondence_postconditions(),
        invariants=_make_correspondence_invariants(),
        complexity=len(parameters.get("matches", [])) + 5,
        provenance=provenance or {"derived_from": "operator_gap_trace"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# VARIABLE DESTINATION POLICY
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DestinationCandidate:
    candidate_id: str
    cell_set: List[Tuple[int, int]]
    bbox: Optional[Tuple[int, int, int, int]]
    source_object_id: Optional[str]
    score_features: Dict[str, float]
    validity: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "cell_set": self.cell_set,
            "bbox": list(self.bbox) if self.bbox else None,
            "source_object_id": self.source_object_id,
            "score_features": self.score_features,
            "validity": self.validity,
        }


@dataclass
class DestinationPolicy:
    policy_id: str
    policy_type: str
    source_selector: str
    candidate_generator: str
    scoring_rule: str
    tie_breaker: Optional[str]
    constraints: List[str]
    evidence: Dict[str, Any]
    complexity: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_type": self.policy_type,
            "source_selector": self.source_selector,
            "candidate_generator": self.candidate_generator,
            "scoring_rule": self.scoring_rule,
            "tie_breaker": self.tie_breaker,
            "constraints": self.constraints,
            "evidence": self.evidence,
            "complexity": self.complexity,
        }


@dataclass
class DestinationPolicyProofObligation:
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


@dataclass
class VariableDestinationCopyParams:
    source_selector: str
    destination_policy: DestinationPolicy
    copy_mode: str  # "copy", "move"
    preserve_shape: bool
    preserve_color: bool
    allow_overlap: bool
    background_color: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_selector": self.source_selector,
            "destination_policy": self.destination_policy.to_dict(),
            "copy_mode": self.copy_mode,
            "preserve_shape": self.preserve_shape,
            "preserve_color": self.preserve_color,
            "allow_overlap": self.allow_overlap,
            "background_color": self.background_color,
        }


DESTINATION_POLICY_PROOF_OBLIGATIONS = [
    ("vdp_candidates_nonempty", "Candidate set is non-empty for every source in every training pair"),
    ("vdp_destination_in_bounds", "Selected destination is within grid bounds"),
    ("vdp_constraints_satisfied", "Selected destination satisfies all declared constraints"),
    ("vdp_deterministic", "Policy selects exactly one destination per source (no ties without tie-breaker)"),
    ("vdp_cross_train_consistent", "Policy produces correct destination across all training pairs"),
    ("vdp_replay_reproduces_output", "Selected destination reproduces training outputs under replay"),
    ("vdp_non_target_unchanged", "Cells not belonging to source or destination are unchanged"),
    ("vdp_complexity_bounded", "Policy complexity does not exceed bound"),
    ("vdp_tie_breaking_explicit", "Tie-breaking rule is declared if ties are possible"),
]


def _make_vdp_preconditions() -> List[OperatorPrecondition]:
    return [
        OperatorPrecondition(
            name="source_objects_exist",
            expression="at least one source object is identified by the selector",
            check_fn=lambda source_objects=None, **kw: (
                source_objects is not None and len(source_objects) > 0
            ),
        ),
        OperatorPrecondition(
            name="destination_policy_defined",
            expression="a destination policy mapping source objects to placements is defined",
            check_fn=lambda destination_policy=None, **kw: (
                destination_policy is not None
            ),
        ),
        OperatorPrecondition(
            name="destination_candidates_exist",
            expression="at least one destination candidate exists for every source",
            check_fn=lambda candidates_nonempty=None, **kw: (
                candidates_nonempty is True
            ),
        ),
        OperatorPrecondition(
            name="grid_shape_valid",
            expression="grid shape allows at least one valid placement",
            check_fn=lambda grid_shape=None, **kw: (
                grid_shape is not None and grid_shape[0] > 0 and grid_shape[1] > 0
            ),
        ),
    ]


def _make_vdp_postconditions() -> List[OperatorPostcondition]:
    return [
        OperatorPostcondition(
            name="source_placed_at_destination",
            expression="each source object appears at its policy-selected destination",
            check_fn=lambda source_placed=None, **kw: (
                source_placed is True
            ),
        ),
        OperatorPostcondition(
            name="destination_unique_per_source",
            expression="each source maps to exactly one destination",
            check_fn=lambda unique_destinations=None, **kw: (
                unique_destinations is True
            ),
        ),
    ]


def _make_vdp_invariants() -> List[OperatorInvariant]:
    return [
        OperatorInvariant(
            name="grid_size_unchanged",
            expression="output grid has the same dimensions as input grid",
            check_fn=lambda grid_size_preserved=None, **kw: (
                grid_size_preserved is True
            ),
        ),
        OperatorInvariant(
            name="non_target_cells_unchanged",
            expression="cells not belonging to source or destination are unchanged",
            check_fn=lambda non_target_preserved=None, **kw: (
                non_target_preserved is True
            ),
        ),
        OperatorInvariant(
            name="kept_objects_preserved",
            expression="kept/anchor objects are preserved in output",
            check_fn=lambda kept_preserved=None, **kw: (
                kept_preserved is True
            ),
        ),
    ]


def make_variable_destination_hypothesis(
    task_id: str,
    selector_expression: str,
    parameters: Dict[str, Any],
    source_tasks: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ExecutableOperatorHypothesis:
    return ExecutableOperatorHypothesis(
        operator_id=f"vdp_{task_id}_{uuid.uuid4().hex[:8]}",
        family="variable_destination_copy",
        source_tasks=source_tasks or [task_id],
        selector_expression=selector_expression,
        parameters=parameters,
        preconditions=_make_vdp_preconditions(),
        postconditions=_make_vdp_postconditions(),
        invariants=_make_vdp_invariants(),
        complexity=parameters.get("complexity", 5),
        provenance=provenance or {"derived_from": "operator_gap_trace"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# MARKER-PROJECTION OPERATOR
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MarkerProjectionProofObligation:
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


MARKER_PROJECTION_PROOF_OBLIGATIONS = [
    ("mp_markers_exist", "At least one marker (removed) object exists in the input"),
    ("mp_targets_exist", "At least one target (kept) object or background region exists"),
    ("mp_projection_type_consistent", "Projection type produces correct output across all training pairs"),
    ("mp_color_rule_consistent", "Color rule produces correct colors at projected cells"),
    ("mp_direction_consistent", "Projection direction is consistent across training pairs"),
    ("mp_non_target_unchanged", "Cells not affected by projection are unchanged"),
    ("mp_replay_reproduces_output", "Executing projection reproduces training outputs"),
    ("mp_loo_generalizes", "Projection generalizes under leave-one-out validation"),
]


def _make_marker_projection_preconditions() -> List[OperatorPrecondition]:
    return [
        OperatorPrecondition(
            name="marker_objects_exist",
            expression="at least one marker (removed) object is identified by the selector",
            check_fn=lambda marker_objects=None, **kw: (
                marker_objects is not None and len(marker_objects) > 0
            ),
        ),
        OperatorPrecondition(
            name="target_exists",
            expression="at least one target (kept object or background) is available for projection",
            check_fn=lambda target_exists=None, **kw: (
                target_exists is True
            ),
        ),
        OperatorPrecondition(
            name="projection_type_defined",
            expression="a projection type and direction are defined",
            check_fn=lambda projection_type=None, **kw: (
                projection_type is not None
            ),
        ),
        OperatorPrecondition(
            name="grid_shape_valid",
            expression="input and output grids have the same shape",
            check_fn=lambda grid_shape_valid=None, **kw: (
                grid_shape_valid is True
            ),
        ),
    ]


def _make_marker_projection_postconditions() -> List[OperatorPostcondition]:
    return [
        OperatorPostcondition(
            name="projection_cells_correct",
            expression="projected cells have the correct color per the color rule",
            check_fn=lambda projection_correct=None, **kw: (
                projection_correct is True
            ),
        ),
        OperatorPostcondition(
            name="output_matches_expected",
            expression="output grid matches expected output exactly",
            check_fn=lambda output_grid=None, expected_output=None, **kw: (
                output_grid is not None and expected_output is not None
                and np.array_equal(output_grid, expected_output)
            ),
        ),
    ]


def _make_marker_projection_invariants() -> List[OperatorInvariant]:
    return [
        OperatorInvariant(
            name="grid_size_unchanged",
            expression="output grid has the same dimensions as input grid",
            check_fn=lambda grid_size_preserved=None, **kw: (
                grid_size_preserved is True
            ),
        ),
        OperatorInvariant(
            name="kept_objects_preserved",
            expression="kept objects are preserved in output (unless explicitly modified by projection)",
            check_fn=lambda kept_preserved=None, **kw: (
                kept_preserved is True
            ),
        ),
        OperatorInvariant(
            name="non_projected_cells_unchanged",
            expression="cells not targeted by projection are unchanged from base",
            check_fn=lambda non_projected_preserved=None, **kw: (
                non_projected_preserved is True
            ),
        ),
    ]


def make_marker_projection_hypothesis(
    task_id: str,
    selector_expression: str,
    parameters: Dict[str, Any],
    source_tasks: Optional[List[str]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> ExecutableOperatorHypothesis:
    """Factory for marker-projection operator hypotheses."""
    return ExecutableOperatorHypothesis(
        operator_id=f"mp_{task_id}_{uuid.uuid4().hex[:8]}",
        family="marker_projection",
        source_tasks=source_tasks or [task_id],
        selector_expression=selector_expression,
        parameters=parameters,
        preconditions=_make_marker_projection_preconditions(),
        postconditions=_make_marker_projection_postconditions(),
        invariants=_make_marker_projection_invariants(),
        complexity=parameters.get("complexity", 6),
        provenance=provenance or {"derived_from": "operator_gap_trace"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# OBJECT-CHANGE CLASSIFICATION PROOF OBLIGATIONS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ObjectChangeProofObligation:
    obligation_id: str
    description: str
    status: str  # passed, failed, unknown, skipped
    evidence: Dict[str, Any] = field(default_factory=dict)
    counterexample: Optional[Dict[str, Any]] = None


OBJECT_CHANGE_PROOF_OBLIGATIONS = [
    ObjectChangeProofObligation(
        obligation_id="oc_unique_target",
        description="Each source object has at most one accepted target unless copy mode is declared",
        status="unknown",
    ),
    ObjectChangeProofObligation(
        obligation_id="oc_recolor_preserves_shape",
        description="Recolor classification requires identical mask/shape between input and output",
        status="unknown",
    ),
    ObjectChangeProofObligation(
        obligation_id="oc_move_preserves_shape_color",
        description="Move classification requires same shape and color at the destination unless recolor is declared",
        status="unknown",
    ),
    ObjectChangeProofObligation(
        obligation_id="oc_copy_preserves_source",
        description="Copy classification requires original source is preserved and target exists",
        status="unknown",
    ),
    ObjectChangeProofObligation(
        obligation_id="oc_ambiguous_rejected",
        description="Ambiguous matches (multiple candidate targets for one source) are rejected",
        status="unknown",
    ),
    ObjectChangeProofObligation(
        obligation_id="oc_non_target_unchanged",
        description="Non-target (kept) objects remain unchanged in the output",
        status="unknown",
    ),
    ObjectChangeProofObligation(
        obligation_id="oc_consistent_across_pairs",
        description="Object-change classification is consistent across all training pairs",
        status="unknown",
    ),
]


def check_object_change_obligations(
    classification: "ObjectChangeClassification",
    objects: list,
    inp: "np.ndarray",
    out: "np.ndarray",
) -> List[ObjectChangeProofObligation]:
    """Check proof obligations against a concrete classification."""
    import numpy as np

    results = []

    # oc_recolor_preserves_shape
    recolor_ok = True
    recolor_evidence: Dict[str, Any] = {}
    for ch in classification.changes:
        if ch.change_type == "recolored":
            obj = objects[ch.object_idx]
            in_nonzero = inp[obj["mask"]] != 0
            out_nonzero = out[obj["mask"]] != 0
            if not np.array_equal(in_nonzero, out_nonzero):
                recolor_ok = False
                recolor_evidence["violating_object"] = ch.object_idx
                break
    results.append(ObjectChangeProofObligation(
        obligation_id="oc_recolor_preserves_shape",
        description="Recolor classification requires identical mask/shape",
        status="passed" if recolor_ok else "failed",
        evidence=recolor_evidence,
    ))

    # oc_non_target_unchanged
    kept_ok = True
    kept_evidence: Dict[str, Any] = {}
    for ki in classification.kept:
        obj = objects[ki]
        if not np.array_equal(inp[obj["mask"]], out[obj["mask"]]):
            kept_ok = False
            kept_evidence["violating_object"] = ki
            break
    results.append(ObjectChangeProofObligation(
        obligation_id="oc_non_target_unchanged",
        description="Kept objects remain unchanged",
        status="passed" if kept_ok else "failed",
        evidence=kept_evidence,
    ))

    # oc_ambiguous_rejected
    results.append(ObjectChangeProofObligation(
        obligation_id="oc_ambiguous_rejected",
        description="Ambiguous matches are rejected",
        status="passed" if len(classification.ambiguous) == 0 else "failed",
        evidence={"n_ambiguous": len(classification.ambiguous)},
    ))

    return results


# ═══════════════════════════════════════════════════════════════════════════
# COLOR-TRANSFER SEMANTICS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ColorSourceRule:
    rule_id: str
    rule_type: str
    source_selector: str
    target_selector: str
    color_source_selector: str
    tie_breaker: Optional[str] = None
    mapping: Optional[Dict[str, Any]] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    complexity: int = 5


@dataclass
class ColorTransferProofObligation:
    obligation_id: str
    description: str
    status: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    counterexample: Optional[Dict[str, Any]] = None


COLOR_TRANSFER_PROOF_OBLIGATIONS = [
    ColorTransferProofObligation(
        obligation_id="ct_target_nonempty",
        description="Target objects are non-empty in every training pair",
        status="unknown",
    ),
    ColorTransferProofObligation(
        obligation_id="ct_source_exists",
        description="Color source object exists for every target in every pair",
        status="unknown",
    ),
    ColorTransferProofObligation(
        obligation_id="ct_source_unique",
        description="Color source is unique per target or ambiguity is rejected",
        status="unknown",
    ),
    ColorTransferProofObligation(
        obligation_id="ct_consistent_across_pairs",
        description="Color-transfer rule is consistent across all training pairs",
        status="unknown",
    ),
    ColorTransferProofObligation(
        obligation_id="ct_reproduces_output",
        description="Applying the color-transfer rule reproduces the training output",
        status="unknown",
    ),
    ColorTransferProofObligation(
        obligation_id="ct_non_target_unchanged",
        description="Non-target objects remain unchanged after color transfer",
        status="unknown",
    ),
    ColorTransferProofObligation(
        obligation_id="ct_deterministic",
        description="Color mapping is deterministic (same input → same output)",
        status="unknown",
    ),
    ColorTransferProofObligation(
        obligation_id="ct_loo_replay",
        description="LOO replay succeeds on every held-out pair",
        status="unknown",
    ),
]


@dataclass
class ColorTransferParams:
    target_selector: str
    color_source_rule: ColorSourceRule
    recolor_mode: str
    preserve_shape: bool = True
    preserve_position: bool = True
    background_color: int = 0
    invert_selector: bool = False
