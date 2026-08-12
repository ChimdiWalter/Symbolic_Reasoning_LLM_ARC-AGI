"""Abstract operator schemas with typed signatures for cross-domain instantiation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from reasoning_project.cross_domain_operator_semantics import (
    OperatorFamilyName,
    OPERATOR_FAMILIES,
)
from reasoning_project.domain_morphism import (
    DomainMorphism,
    DomainSignatureTyped,
    TypeMapping,
)


@dataclass
class AbstractOperatorSchema:
    name: str
    family: OperatorFamilyName
    input_object_types: List[str]
    output_object_types: List[str]
    required_relation: str
    required_features: List[str]
    preconditions: List[str]
    postconditions: List[str]
    invariants: List[str]
    domain_realizations: Dict[str, str] = field(default_factory=dict)


PROJECT_TO_NEIGHBORHOOD_SCHEMA = AbstractOperatorSchema(
    name="ProjectToNeighborhood",
    family=OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD,
    input_object_types=["source_object", "scene_objects"],
    output_object_types=["scene_objects"],
    required_relation="neighborhood",
    required_features=["projectable_property"],
    preconditions=[
        "source_object exists in scene",
        "neighborhood relation is defined",
        "projectable_property is identified on source",
    ],
    postconditions=[
        "all neighbors receive projected property",
        "source_object preserved",
        "non-neighbors unchanged",
    ],
    invariants=[
        "scene size unchanged",
        "source identity preserved",
        "projection is deterministic",
    ],
    domain_realizations={
        "grid": "fill_4adjacent_with_source_color",
        "graph": "project_label_to_adjacent_nodes",
    },
)

TRANSFER_FEATURE_BY_CORRESPONDENCE_SCHEMA = AbstractOperatorSchema(
    name="TransferFeatureByCorrespondence",
    family=OperatorFamilyName.COPY_FEATURE_TO_CORRESPONDENT,
    input_object_types=["source_object", "target_object"],
    output_object_types=["target_object"],
    required_relation="correspondence",
    required_features=["transferable_feature"],
    preconditions=[
        "source and target objects exist",
        "correspondence relation defined",
        "transferable_feature identified on source",
    ],
    postconditions=[
        "target receives source feature",
        "non-target objects unchanged",
        "correspondence is deterministic",
    ],
    invariants=[
        "scene structure preserved",
        "only specified feature changes",
    ],
    domain_realizations={
        "grid": "copy_color_by_shape_match",
        "graph": "copy_label_by_degree_match",
    },
)

FILTER_BY_RELATION_SCHEMA = AbstractOperatorSchema(
    name="FilterByRelation",
    family=OperatorFamilyName.FILTER_BY_RELATION,
    input_object_types=["scene_objects"],
    output_object_types=["filtered_objects"],
    required_relation="membership_predicate",
    required_features=["discriminative_property"],
    preconditions=[
        "multiple objects exist",
        "discriminative_property separates kept from removed",
        "at least one object satisfies predicate",
    ],
    postconditions=[
        "all kept objects satisfy predicate",
        "no removed object satisfies predicate",
        "kept objects are unmodified",
    ],
    invariants=[
        "scene dimensions unchanged",
        "predicate is boolean and deterministic",
    ],
    domain_realizations={
        "grid": "keep_objects_by_boolean_property",
        "graph": "keep_nodes_by_boolean_property",
        "chess": "keep_pieces_by_boolean_property",
        "molecule": "keep_atoms_by_boolean_property",
    },
)

MOVE_OR_TRANSFER_TO_ANCHOR_SCHEMA = AbstractOperatorSchema(
    name="MoveOrTransferToAnchor",
    family=OperatorFamilyName.MOVE_OR_TRANSFER_TO_ANCHOR,
    input_object_types=["source_object", "anchor_object"],
    output_object_types=["scene_objects"],
    required_relation="anchor_reference",
    required_features=["transfer_rule"],
    preconditions=[
        "source and anchor objects exist",
        "anchor position identified",
        "transfer rule defined",
    ],
    postconditions=[
        "source appears at anchor-relative position",
        "anchor unchanged unless overlay",
    ],
    invariants=[
        "transfer is deterministic given anchor",
        "spatial relationship preserved",
    ],
    domain_realizations={
        "grid": "move_object_relative_to_anchor",
    },
)

ALL_SCHEMAS = [
    PROJECT_TO_NEIGHBORHOOD_SCHEMA,
    TRANSFER_FEATURE_BY_CORRESPONDENCE_SCHEMA,
    FILTER_BY_RELATION_SCHEMA,
    MOVE_OR_TRANSFER_TO_ANCHOR_SCHEMA,
]

SCHEMA_BY_FAMILY = {s.family: s for s in ALL_SCHEMAS}


@dataclass
class OperatorInstantiationResult:
    schema: AbstractOperatorSchema
    target_domain: str
    success: bool
    resolved_types: Dict[str, str] = field(default_factory=dict)
    resolved_relation: Optional[str] = None
    resolved_features: List[str] = field(default_factory=list)
    obligation_checklist: List[Tuple[str, bool]] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    notes: str = ""


class OperatorMorphismInstantiator:

    def instantiate(
        self,
        schema: AbstractOperatorSchema,
        morphism: DomainMorphism,
        target_sig: DomainSignatureTyped,
    ) -> OperatorInstantiationResult:
        resolved_types: Dict[str, str] = {}
        resolved_features: List[str] = []
        resolved_relation: Optional[str] = None
        missing: List[str] = []

        obj_map = {m.source_type: m.target_type for m in morphism.object_mappings}
        rel_map = {m.source_type: m.target_type for m in morphism.relation_mappings}
        feat_map = {m.source_type: m.target_type for m in morphism.feature_mappings}

        for abs_type in schema.input_object_types + schema.output_object_types:
            if abs_type in obj_map:
                resolved_types[abs_type] = obj_map[abs_type]
            else:
                target_obj_names = [ot.name for ot in target_sig.object_types]
                if target_obj_names:
                    resolved_types[abs_type] = target_obj_names[0]
                else:
                    missing.append(f"object_type:{abs_type}")

        if schema.required_relation in rel_map:
            resolved_relation = rel_map[schema.required_relation]
        else:
            target_rel_names = [rt.name for rt in target_sig.relation_types]
            matched = False
            for rn in target_rel_names:
                if schema.required_relation in rn or rn in schema.required_relation:
                    resolved_relation = rn
                    matched = True
                    break
            if not matched:
                if target_rel_names:
                    resolved_relation = target_rel_names[0]
                else:
                    missing.append(f"relation:{schema.required_relation}")

        for abs_feat in schema.required_features:
            if abs_feat in feat_map:
                resolved_features.append(feat_map[abs_feat])
            else:
                target_feat_names = [ft.name for ft in target_sig.feature_types]
                if target_feat_names:
                    resolved_features.append(target_feat_names[0])
                else:
                    missing.append(f"feature:{abs_feat}")

        obligations = self.check_obligations_internal(
            schema, resolved_types, resolved_relation, resolved_features, missing,
        )

        success = len(missing) == 0
        return OperatorInstantiationResult(
            schema=schema,
            target_domain=morphism.target_domain,
            success=success,
            resolved_types=resolved_types,
            resolved_relation=resolved_relation,
            resolved_features=resolved_features,
            obligation_checklist=obligations,
            missing=missing,
        )

    def check_obligations_internal(
        self,
        schema: AbstractOperatorSchema,
        resolved_types: Dict[str, str],
        resolved_relation: Optional[str],
        resolved_features: List[str],
        missing: List[str],
    ) -> List[Tuple[str, bool]]:
        obligations = []
        all_types = schema.input_object_types + schema.output_object_types
        types_mapped = all(t in resolved_types for t in all_types)
        obligations.append(("all_object_types_mapped", types_mapped))
        obligations.append(("required_relation_mapped", resolved_relation is not None))
        obligations.append((
            "all_features_mapped",
            len(resolved_features) >= len(schema.required_features),
        ))
        obligations.append(("preconditions_expressible", len(missing) == 0))
        obligations.append(("postconditions_expressible", len(missing) == 0))
        obligations.append(("no_missing_types", len(missing) == 0))
        return obligations

    def check_obligations(
        self, result: OperatorInstantiationResult,
    ) -> List[Tuple[str, bool]]:
        return result.obligation_checklist
