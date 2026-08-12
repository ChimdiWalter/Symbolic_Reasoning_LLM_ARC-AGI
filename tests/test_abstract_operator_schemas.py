"""Tests for abstract_operator_schemas module."""
from __future__ import annotations

import pytest
from reasoning_project.abstract_operator_schemas import (
    AbstractOperatorSchema,
    OperatorMorphismInstantiator,
    OperatorInstantiationResult,
    ALL_SCHEMAS,
    PROJECT_TO_NEIGHBORHOOD_SCHEMA,
    FILTER_BY_RELATION_SCHEMA,
    TRANSFER_FEATURE_BY_CORRESPONDENCE_SCHEMA,
    MOVE_OR_TRANSFER_TO_ANCHOR_SCHEMA,
    SCHEMA_BY_FAMILY,
)
from reasoning_project.domain_morphism import (
    DomainMorphism,
    DomainSignatureTyped,
    DomainObjectType,
    DomainRelationType,
    DomainFeatureType,
    DomainOperatorHook,
    TypeMapping,
)
from reasoning_project.cross_domain_operator_semantics import OperatorFamilyName


def _grid_sig():
    return DomainSignatureTyped(
        domain_name="grid",
        object_types=[DomainObjectType("grid_object", ["is_largest", "is_smallest"], True, True, True)],
        relation_types=[
            DomainRelationType("adjacency", 2, True, "local"),
            DomainRelationType("spatial_neighbor", 2, True, "spatial"),
        ],
        feature_types=[
            DomainFeatureType("color", "int", True),
            DomainFeatureType("size", "int", True),
        ],
        operator_hooks=[
            DomainOperatorHook("filter_by_property", ["scene_objects"], ["filtered_objects"],
                               "membership_predicate", "discriminative_property"),
            DomainOperatorHook("project_to_neighbor", ["source_object", "scene_objects"],
                               ["scene_objects"], "adjacency", "projectable_property"),
        ],
    )


def _graph_sig():
    return DomainSignatureTyped(
        domain_name="graph",
        object_types=[DomainObjectType("graph_object", ["is_largest", "is_hub"], False, True, True)],
        relation_types=[
            DomainRelationType("adjacency", 2, True, "local"),
        ],
        feature_types=[
            DomainFeatureType("color", "int", True),
            DomainFeatureType("degree", "int", True),
        ],
        operator_hooks=[
            DomainOperatorHook("filter_by_property", ["scene_objects"], ["filtered_objects"],
                               "membership_predicate", "discriminative_property"),
            DomainOperatorHook("project_to_neighbor", ["source_object", "scene_objects"],
                               ["scene_objects"], "adjacency", "projectable_property"),
        ],
    )


def _grid_to_graph_morphism():
    return DomainMorphism(
        source_domain="grid",
        target_domain="graph",
        object_mappings=[TypeMapping("grid_object", "graph_object", "object", 0.8, "property overlap")],
        relation_mappings=[TypeMapping("adjacency", "adjacency", "relation", 1.0, "same name")],
        feature_mappings=[TypeMapping("color", "color", "feature", 1.0, "same dtype")],
    )


class TestSchemaDefinitions:

    def test_all_schemas_defined(self):
        assert len(ALL_SCHEMAS) == 4

    def test_schemas_have_preconditions(self):
        for schema in ALL_SCHEMAS:
            assert len(schema.preconditions) > 0
            assert len(schema.postconditions) > 0
            assert len(schema.invariants) > 0

    def test_schema_by_family_complete(self):
        for family in OperatorFamilyName:
            assert family in SCHEMA_BY_FAMILY


class TestInstantiation:

    def test_instantiate_grid_domain(self):
        inst = OperatorMorphismInstantiator()
        sig = _grid_sig()
        morphism = DomainMorphism(
            source_domain="grid", target_domain="grid",
            object_mappings=[TypeMapping("grid_object", "grid_object", "object", 1.0, "identity")],
            relation_mappings=[TypeMapping("adjacency", "adjacency", "relation", 1.0, "identity")],
            feature_mappings=[TypeMapping("color", "color", "feature", 1.0, "identity")],
        )
        result = inst.instantiate(PROJECT_TO_NEIGHBORHOOD_SCHEMA, morphism, sig)
        assert result.success

    def test_instantiate_graph_domain(self):
        inst = OperatorMorphismInstantiator()
        morphism = _grid_to_graph_morphism()
        result = inst.instantiate(PROJECT_TO_NEIGHBORHOOD_SCHEMA, morphism, _graph_sig())
        assert result.success

    def test_reject_missing_relation_mapping(self):
        inst = OperatorMorphismInstantiator()
        sig = DomainSignatureTyped(
            domain_name="empty", object_types=[], relation_types=[], feature_types=[], operator_hooks=[],
        )
        morphism = DomainMorphism(source_domain="grid", target_domain="empty")
        result = inst.instantiate(PROJECT_TO_NEIGHBORHOOD_SCHEMA, morphism, sig)
        assert not result.success
        assert len(result.missing) > 0

    def test_obligation_checklist_emitted(self):
        inst = OperatorMorphismInstantiator()
        morphism = _grid_to_graph_morphism()
        result = inst.instantiate(FILTER_BY_RELATION_SCHEMA, morphism, _graph_sig())
        assert len(result.obligation_checklist) > 0

    def test_filter_by_relation_all_domains(self):
        inst = OperatorMorphismInstantiator()
        morphism = _grid_to_graph_morphism()
        result = inst.instantiate(FILTER_BY_RELATION_SCHEMA, morphism, _graph_sig())
        assert result.success
