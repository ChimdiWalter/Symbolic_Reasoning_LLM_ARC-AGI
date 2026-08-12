"""Tests for morphism_verification module."""
from __future__ import annotations

import json
import pytest
from reasoning_project.morphism_verification import (
    MorphismProofObligations,
    MorphismCertificate,
    ProofObligation,
    build_certificate,
    write_certificate_json,
    write_certificate_md,
)
from reasoning_project.domain_morphism import (
    DomainMorphism,
    DomainSignatureTyped,
    DomainObjectType,
    DomainRelationType,
    DomainFeatureType,
    TypeMapping,
)
from reasoning_project.abstract_operator_schemas import FILTER_BY_RELATION_SCHEMA


def _make_sig(name, obj_name, rel_name, rel_arity, rel_locality, feat_name, feat_dtype):
    return DomainSignatureTyped(
        domain_name=name,
        object_types=[DomainObjectType(obj_name, ["is_largest"], True, True, True)],
        relation_types=[DomainRelationType(rel_name, rel_arity, True, rel_locality)],
        feature_types=[DomainFeatureType(feat_name, feat_dtype, True)],
        operator_hooks=[],
    )


@pytest.fixture
def checker():
    return MorphismProofObligations()


@pytest.fixture
def grid_sig():
    return _make_sig("grid", "grid_obj", "adjacency", 2, "local", "color", "int")


@pytest.fixture
def graph_sig():
    return _make_sig("graph", "graph_obj", "adjacency", 2, "local", "color", "int")


@pytest.fixture
def valid_morphism():
    return DomainMorphism(
        source_domain="grid", target_domain="graph",
        object_mappings=[TypeMapping("grid_obj", "graph_obj", "object", 0.9, "overlap")],
        relation_mappings=[TypeMapping("adjacency", "adjacency", "relation", 1.0, "same")],
        feature_mappings=[TypeMapping("color", "color", "feature", 1.0, "same dtype")],
    )


class TestTotality:

    def test_totality_pass(self, checker, grid_sig, graph_sig, valid_morphism):
        ob = checker.check_type_mapping_totality(valid_morphism, grid_sig, graph_sig)
        assert ob.passed

    def test_totality_fail(self, checker, graph_sig):
        src = _make_sig("grid", "grid_obj", "adj", 2, "local", "c", "int")
        m = DomainMorphism(source_domain="grid", target_domain="graph")
        ob = checker.check_type_mapping_totality(m, src, graph_sig)
        assert not ob.passed
        assert "unmapped" in ob.counterexample


class TestArityPreservation:

    def test_arity_preserved(self, checker, grid_sig, graph_sig, valid_morphism):
        ob = checker.check_relation_arity_preservation(valid_morphism, grid_sig, graph_sig)
        assert ob.passed

    def test_arity_violation(self, checker):
        src = _make_sig("a", "obj_a", "rel_a", 2, "local", "f", "int")
        tgt = _make_sig("b", "obj_b", "rel_b", 3, "local", "f", "int")
        m = DomainMorphism(
            source_domain="a", target_domain="b",
            relation_mappings=[TypeMapping("rel_a", "rel_b", "relation", 0.8, "test")],
        )
        ob = checker.check_relation_arity_preservation(m, src, tgt)
        assert not ob.passed


class TestFeatureCompatibility:

    def test_compatible_pass(self, checker, grid_sig, graph_sig, valid_morphism):
        ob = checker.check_feature_compatibility(valid_morphism, grid_sig, graph_sig)
        assert ob.passed

    def test_incompatible_categorical_to_int(self, checker):
        src = _make_sig("a", "o", "r", 2, "local", "feat_a", "categorical")
        tgt = _make_sig("b", "o", "r", 2, "local", "feat_b", "int")
        m = DomainMorphism(
            source_domain="a", target_domain="b",
            feature_mappings=[TypeMapping("feat_a", "feat_b", "feature", 0.5, "test")],
        )
        ob = checker.check_feature_compatibility(m, src, tgt)
        assert not ob.passed


class TestAmbiguity:

    def test_no_ambiguity(self, checker, grid_sig, graph_sig, valid_morphism):
        ob = checker.check_ambiguity_rejection(valid_morphism, grid_sig, graph_sig)
        assert ob.passed

    def test_ambiguity_detected(self, checker, grid_sig, graph_sig):
        m = DomainMorphism(
            source_domain="grid", target_domain="graph",
            object_mappings=[
                TypeMapping("obj_a", "graph_obj", "object", 0.8, "t"),
                TypeMapping("obj_b", "graph_obj", "object", 0.7, "t"),
            ],
        )
        ob = checker.check_ambiguity_rejection(m, grid_sig, graph_sig)
        assert not ob.passed
        assert "ambiguous" in ob.counterexample


class TestCertificate:

    def test_certificate_emitted(self, grid_sig, graph_sig, valid_morphism):
        cert = build_certificate(valid_morphism, grid_sig, graph_sig)
        assert cert.obligations_total > 0
        assert cert.all_passed
        assert len(cert.certificate_id) > 0

    def test_certificate_with_schema(self, grid_sig, graph_sig, valid_morphism):
        cert = build_certificate(valid_morphism, grid_sig, graph_sig,
                                 schema=FILTER_BY_RELATION_SCHEMA)
        assert cert.obligations_total > 5
        assert cert.operator_schema == "FilterByRelation"

    def test_certificate_json_written(self, tmp_path, grid_sig, graph_sig, valid_morphism):
        cert = build_certificate(valid_morphism, grid_sig, graph_sig)
        out = str(tmp_path / "cert.json")
        write_certificate_json(cert, out)
        with open(out) as f:
            data = json.load(f)
        assert data["certificate_id"] == cert.certificate_id
        assert data["all_passed"] == cert.all_passed

    def test_certificate_md_written(self, tmp_path, grid_sig, graph_sig, valid_morphism):
        cert = build_certificate(valid_morphism, grid_sig, graph_sig)
        out = str(tmp_path / "cert.md")
        write_certificate_md(cert, out)
        with open(out) as f:
            text = f.read()
        assert cert.certificate_id in text
        assert "PASS" in text
