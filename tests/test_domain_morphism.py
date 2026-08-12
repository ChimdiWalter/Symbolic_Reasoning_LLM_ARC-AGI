"""Tests for domain_morphism module."""
from __future__ import annotations

import pytest
from reasoning_project.domain_morphism import (
    DomainSignatureExtractorTyped,
    DomainMorphismLearner,
    DomainObjectType,
    DomainRelationType,
    DomainFeatureType,
    DomainOperatorHook,
    DomainSignatureTyped,
    TypeMapping,
    DomainMorphism,
)
from reasoning_project.reasoning_engine import GridDomainAdapter
from reasoning_project.domain_adapters import (
    GraphDomainAdapter,
    ChessBoardDomainAdapter,
    MoleculeGraphDomainAdapter,
)


@pytest.fixture
def extractor():
    return DomainSignatureExtractorTyped()


@pytest.fixture
def learner():
    return DomainMorphismLearner()


class TestSignatureExtraction:

    def test_grid_signature_extraction(self, extractor):
        adapter = GridDomainAdapter()
        sig = extractor.extract(adapter)
        assert sig.domain_name == "grid"
        assert len(sig.object_types) >= 1
        assert len(sig.relation_types) >= 1
        assert any(rt.name == "adjacency" for rt in sig.relation_types)

    def test_graph_signature_extraction(self, extractor):
        adapter = GraphDomainAdapter()
        sig = extractor.extract(adapter)
        assert sig.domain_name == "graph"
        assert len(sig.object_types) >= 1
        assert any(rt.name == "adjacency" for rt in sig.relation_types)

    def test_chess_signature_extraction(self, extractor):
        adapter = ChessBoardDomainAdapter()
        sig = extractor.extract(adapter)
        assert sig.domain_name == "chess"
        assert any(rt.name == "attack" for rt in sig.relation_types)

    def test_molecule_signature_extraction(self, extractor):
        adapter = MoleculeGraphDomainAdapter()
        sig = extractor.extract(adapter)
        assert sig.domain_name == "molecule"
        assert any(rt.name == "bond" for rt in sig.relation_types)


class TestMorphismProposal:

    def test_feature_mapping_proposed(self, extractor, learner):
        grid_sig = extractor.extract(GridDomainAdapter())
        graph_sig = extractor.extract(GraphDomainAdapter())
        morphisms = learner.propose_morphisms(grid_sig, graph_sig)
        assert len(morphisms) >= 1
        assert len(morphisms[0].feature_mappings) >= 1

    def test_relation_mapping_proposed(self, extractor, learner):
        grid_sig = extractor.extract(GridDomainAdapter())
        graph_sig = extractor.extract(GraphDomainAdapter())
        morphisms = learner.propose_morphisms(grid_sig, graph_sig)
        assert len(morphisms) >= 1
        assert len(morphisms[0].relation_mappings) >= 1

    def test_object_mapping_proposed(self, extractor, learner):
        grid_sig = extractor.extract(GridDomainAdapter())
        graph_sig = extractor.extract(GraphDomainAdapter())
        morphisms = learner.propose_morphisms(grid_sig, graph_sig)
        assert len(morphisms[0].object_mappings) >= 1

    def test_morphism_score_positive(self, extractor, learner):
        grid_sig = extractor.extract(GridDomainAdapter())
        graph_sig = extractor.extract(GraphDomainAdapter())
        morphisms = learner.propose_morphisms(grid_sig, graph_sig)
        assert morphisms[0].score > 0.0


class TestAmbiguityRejection:

    def test_ambiguous_duplicate_rejected(self, learner):
        m = DomainMorphism(
            source_domain="grid",
            target_domain="graph",
            object_mappings=[
                TypeMapping("grid_obj_a", "graph_obj", "object", 0.8, "test"),
                TypeMapping("grid_obj_b", "graph_obj", "object", 0.7, "test"),
            ],
        )
        accepted = learner.reject_ambiguous([m])
        assert len(accepted) == 0
        assert m.rejected
        assert "ambiguous" in m.rejection_reason.lower() or "duplicate" in m.rejection_reason.lower()

    def test_no_object_mapping_rejected(self, learner):
        m = DomainMorphism(source_domain="grid", target_domain="graph")
        accepted = learner.reject_ambiguous([m])
        assert len(accepted) == 0
        assert m.rejected


class TestMorphismValidation:

    def test_valid_morphism(self, extractor, learner):
        grid_sig = extractor.extract(GridDomainAdapter())
        graph_sig = extractor.extract(GraphDomainAdapter())
        morphisms = learner.propose_morphisms(grid_sig, graph_sig)
        result = learner.validate_morphism(morphisms[0], grid_sig, graph_sig)
        assert result.obligations_checked > 0
        assert result.obligations_passed > 0

    def test_invalid_source_type_fails(self, extractor, learner):
        grid_sig = extractor.extract(GridDomainAdapter())
        graph_sig = extractor.extract(GraphDomainAdapter())
        m = DomainMorphism(
            source_domain="grid",
            target_domain="graph",
            object_mappings=[
                TypeMapping("nonexistent_type", "graph_object", "object", 0.9, "test"),
            ],
        )
        result = learner.validate_morphism(m, grid_sig, graph_sig)
        assert len(result.failures) > 0
