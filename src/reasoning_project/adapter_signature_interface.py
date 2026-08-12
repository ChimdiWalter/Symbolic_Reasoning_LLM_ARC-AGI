"""Adapter signature interface: typed domain adapter descriptions for morphism learning.

An AdapterSignature captures the schema of a domain adapter so that domain morphisms
can be computed between domains with compatible structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from reasoning_project.reasoning_engine import GridDomainAdapter


@dataclass
class AdapterSignature:
    domain_name: str
    adapter_name: str
    object_schema: Dict[str, Any]
    property_library: List[str]
    relation_algebra: List[str]
    operator_hooks: List[str]
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)


def adapter_to_signature(adapter, domain_name: str) -> AdapterSignature:
    if isinstance(adapter, GridDomainAdapter):
        return AdapterSignature(
            domain_name=domain_name,
            adapter_name="GridDomainAdapter",
            object_schema={
                "type": "colored_connected_component",
                "fields": ["mask", "color", "bbox", "size", "centroid"],
            },
            property_library=[
                "is_largest", "is_smallest", "is_most_common_color",
                "is_least_common_color", "has_holes", "is_symmetric",
                "in_top_half", "in_bottom_half", "in_left_half", "in_right_half",
                "is_on_boundary", "is_interior", "is_rectangular",
            ],
            relation_algebra=[
                "above", "below", "left_of", "right_of",
                "adjacent", "contains", "same_color", "same_shape",
                "same_size", "nearest_to",
            ],
            operator_hooks=[
                "filter_select", "recolor", "copy_to_position",
                "project_to_halo", "shape_completion", "separator_decompose",
            ],
            confidence=1.0,
            evidence={"source": "builtin_grid_adapter"},
        )

    return AdapterSignature(
        domain_name=domain_name,
        adapter_name=type(adapter).__name__,
        object_schema={"type": "unknown"},
        property_library=[],
        relation_algebra=[],
        operator_hooks=[],
        confidence=0.3,
        evidence={"source": "generic_adapter_introspection"},
    )


def adapter_genesis_to_signature(synthesized_adapter, domain_name: str) -> AdapterSignature:
    schema = getattr(synthesized_adapter, "object_schema", {"type": "synthesized"})
    props = getattr(synthesized_adapter, "property_names", [])
    rels = getattr(synthesized_adapter, "relation_names", [])
    hooks = getattr(synthesized_adapter, "operator_hooks", [])

    return AdapterSignature(
        domain_name=domain_name,
        adapter_name="SynthesizedAdapter",
        object_schema=schema,
        property_library=props,
        relation_algebra=rels,
        operator_hooks=hooks,
        confidence=0.5,
        evidence={"source": "adapter_genesis"},
    )


def validate_signature(signature: AdapterSignature) -> Dict[str, Any]:
    issues = []

    if not signature.domain_name:
        issues.append("missing_domain_name")
    if not signature.object_schema:
        issues.append("missing_object_schema")
    if not signature.property_library:
        issues.append("empty_property_library")
    if not signature.relation_algebra:
        issues.append("empty_relation_algebra")
    if signature.confidence < 0.0 or signature.confidence > 1.0:
        issues.append("invalid_confidence_range")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "property_count": len(signature.property_library),
        "relation_count": len(signature.relation_algebra),
        "operator_count": len(signature.operator_hooks),
    }
