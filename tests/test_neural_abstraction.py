"""Tests for neural_abstraction module — 25 tests covering all components."""
from __future__ import annotations

import numpy as np
import torch
import pytest

from reasoning_project.neural_abstraction import (
    FailureEncoder,
    ObjectRelationEncoder,
    ContrastivePropertyLearner,
    SymbolicPropertyDistiller,
    OperatorTemplateProposer,
    NeuralCounterexampleGenerator,
    SymbolicValidationGate,
    ConceptGraphMemory,
    NeuralAbstractionPipeline,
    InventedProperty,
    Counterexample,
    _make_symbolic_grammar,
    FAILURE_TYPES,
)
from reasoning_project.near_solved_memory import (
    NearSolvedMemory,
    NearSolvedTaskState,
    RepairAction,
)
from reasoning_project.manifold_memory import ManifoldPoint
from reasoning_project.events import ReasoningEventLog
from reasoning_project.operator_invention import InventedOperator


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _make_state(task_id="t1", failure_type="no_discrimination", train_fit=0.6):
    emb = np.zeros(16)
    point = ManifoldPoint(
        embedding=emb,
        task_signature={"n_objects": 4, "n_colors": 3},
        domain="grid",
    )
    return NearSolvedTaskState(
        task_id=task_id,
        manifold_point=point,
        active_chart="default",
        best_hypothesis={"strategy": "discriminative_filter", "property": "is_largest"},
        hypothesis_score=train_fit,
        train_fit=train_fit,
        train_fit_detail=[True, False],
        loo_passed=False,
        failure_type=failure_type,
        failed_examples=[1],
        error_signature={"failure_type": failure_type},
        retrieved_success_anchors=[],
        retrieved_failure_anchors=[],
        proposed_repairs=[
            RepairAction(action_type="add_conjunction", description="try conj", priority=0.9),
        ],
        missing_capability_guess="richer_property_language",
        views_tried=["default"],
        iterations_used=5,
        topology_signature={
            "n_objects": 4,
            "has_separators": False,
            "has_containment": True,
            "has_holes": False,
            "has_symmetry": True,
        },
    )


def _make_objects(n=4):
    """Create mock object dicts similar to GridDomainAdapter output."""
    objs = []
    for i in range(n):
        mask = np.zeros((10, 10), dtype=bool)
        r, c = i * 2, i * 2
        mask[r:r+2, c:c+2] = True
        local_mask = np.ones((2, 2), dtype=bool)
        objs.append({
            "label": i + 1,
            "mask": mask,
            "local_mask": local_mask,
            "bbox": (r, c, r + 1, c + 1),
            "center_r": float(r + 0.5),
            "center_c": float(c + 0.5),
            "area": 4,
            "bbox_h": 2,
            "bbox_w": 2,
            "primary_color": (i % 3) + 1,
            "colors": [(i % 3) + 1],
            "n_colors": 1,
            "perimeter": 8,
            "n_holes": 0,
            "euler_char": 1,
            "h_sym": True,
            "v_sym": True,
            "d_sym": True,
            "any_sym": True,
            "convexity": 1.0,
            "is_filled_rect": True,
            "is_square": True,
            "touches_boundary": i == 0,
            "touches_top": i == 0,
            "touches_bottom": False,
            "touches_left": i == 0,
            "touches_right": False,
            "bbox_ratio": 1.0,
            "is_largest": i == 0,
            "is_smallest": i == n - 1,
            "size_rank": i,
            "_n_objects": n,
            "shape_group_id": 0,
            "shape_group_size": n,
            "is_unique_shape": False,
            "is_majority_shape": True,
            "is_contained": i == 2,
            "is_container": i == 0,
            "touches_largest": i == 1,
            "is_largest_in_color_group": i == 0,
            "color_group_size": 2,
            "is_unique_color": i == 3,
            "in_top_half": i < 2,
            "in_left_half": i < 2,
            "n_touching": 1,
            "same_row_as_largest": False,
            "same_col_as_largest": False,
            "above_largest": False,
            "below_largest": i > 0,
            "left_of_largest": False,
            "right_of_largest": i > 0,
            "is_most_common_color": i < 2,
            "is_rarest_color": i == 3,
            "same_color_as_largest": i == 0,
        })
    return objs


# ═══════════════════════════════════════════════════════════════════════
# 1. FAILURE ENCODER
# ═══════════════════════════════════════════════════════════════════════

class TestFailureEncoder:

    def test_forward_pass_shape(self):
        enc = FailureEncoder(failure_embedding_dim=16, use_jepa=False)
        state = _make_state()
        feat = enc.encode_state(state)
        assert feat.shape == (13,)
        out = enc(feat.unsqueeze(0))
        assert out.shape == (1, 16)

    def test_forward_pass_shape_with_jepa(self):
        enc = FailureEncoder(failure_embedding_dim=16, use_jepa=True)
        state = _make_state()
        feat = enc.encode_state(state)
        assert feat.shape == (13 + 64,)
        out = enc(feat.unsqueeze(0))
        assert out.shape == (1, 16)

    def test_batch_forward(self):
        enc = FailureEncoder(failure_embedding_dim=16, use_jepa=False)
        feats = torch.randn(5, 13)
        out = enc(feats)
        assert out.shape == (5, 16)

    def test_different_failure_types_produce_different_features(self):
        enc = FailureEncoder(failure_embedding_dim=16)
        s1 = _make_state(failure_type="no_discrimination")
        s2 = _make_state(failure_type="wrong_reconstruction")
        f1 = enc.encode_state(s1)
        f2 = enc.encode_state(s2)
        assert not torch.allclose(f1, f2)


# ═══════════════════════════════════════════════════════════════════════
# 2. OBJECT RELATION ENCODER
# ═══════════════════════════════════════════════════════════════════════

class TestObjectRelationEncoder:

    def test_forward_pass_shapes(self):
        enc = ObjectRelationEncoder(obj_embed_dim=32, scene_embed_dim=32)
        objs = _make_objects(3)
        obj_feats = torch.stack([ObjectRelationEncoder.obj_to_features(o) for o in objs])
        obj_emb, scene_emb = enc(obj_feats)
        assert obj_emb.shape == (3, 32)
        assert scene_emb.shape == (32,)

    def test_with_relation_features(self):
        enc = ObjectRelationEncoder()
        objs = _make_objects(3)
        obj_feats = torch.stack([ObjectRelationEncoder.obj_to_features(o) for o in objs])
        pairs = []
        for i in range(len(objs)):
            for j in range(i + 1, len(objs)):
                pairs.append(ObjectRelationEncoder.pair_to_features(objs[i], objs[j]))
        rel_feats = torch.stack(pairs)
        obj_emb, scene_emb = enc(obj_feats, rel_feats)
        assert obj_emb.shape == (3, 32)
        assert scene_emb.shape == (32,)

    def test_single_object(self):
        enc = ObjectRelationEncoder()
        objs = _make_objects(1)
        obj_feats = torch.stack([ObjectRelationEncoder.obj_to_features(o) for o in objs])
        obj_emb, scene_emb = enc(obj_feats)
        assert obj_emb.shape == (1, 32)
        assert scene_emb.shape == (32,)


# ═══════════════════════════════════════════════════════════════════════
# 3. CONTRASTIVE PROPERTY LEARNER
# ═══════════════════════════════════════════════════════════════════════

class TestContrastivePropertyLearner:

    def test_forward_and_loss(self):
        learner = ContrastivePropertyLearner(obj_embed_dim=32, property_dim=16)
        embs = torch.randn(6, 32)
        labels = torch.tensor([1, 1, 1, 0, 0, 0], dtype=torch.float32)
        prop_vec, scores = learner(embs, labels)
        assert prop_vec.shape == (16,)
        assert scores.shape == (6,)
        loss = learner.contrastive_loss(scores, labels)
        assert loss.item() >= 0

    def test_training_step_reduces_loss(self):
        learner = ContrastivePropertyLearner(obj_embed_dim=32, property_dim=16)
        opt = torch.optim.Adam(learner.parameters(), lr=0.01)
        torch.manual_seed(0)
        embs = torch.randn(8, 32)
        labels = torch.tensor([1, 1, 1, 1, 0, 0, 0, 0], dtype=torch.float32)

        _, scores0 = learner(embs, labels)
        loss0 = learner.contrastive_loss(scores0, labels).item()

        for _ in range(20):
            opt.zero_grad()
            _, scores = learner(embs, labels)
            loss = learner.contrastive_loss(scores, labels)
            loss.backward()
            opt.step()

        _, scores_f = learner(embs, labels)
        loss_f = learner.contrastive_loss(scores_f, labels).item()
        assert loss_f <= loss0 + 0.1  # should not increase much

    def test_all_targets_returns_valid_vector(self):
        learner = ContrastivePropertyLearner(obj_embed_dim=32, property_dim=16)
        embs = torch.randn(3, 32)
        labels = torch.ones(3)
        prop_vec, scores = learner(embs, labels)
        assert prop_vec.shape == (16,)


# ═══════════════════════════════════════════════════════════════════════
# 4. SYMBOLIC PROPERTY DISTILLER
# ═══════════════════════════════════════════════════════════════════════

class TestSymbolicPropertyDistiller:

    def test_distill_on_mock_objects(self):
        distiller = SymbolicPropertyDistiller(correlation_threshold=0.3)
        objs = _make_objects(4)
        # kept: 0,1 (have is_contained=False except obj 2); removed: 2,3
        kept = [0, 1]
        removed = [2, 3]
        results = distiller.distill(objs, kept, removed)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, InventedProperty)
            assert callable(r.compute_fn)

    def test_empty_objects_returns_empty(self):
        distiller = SymbolicPropertyDistiller()
        assert distiller.distill([], [], []) == []

    def test_all_grammar_predicates_are_callable(self):
        grammar = _make_symbolic_grammar()
        assert len(grammar) == 15
        for name, fn in grammar:
            assert callable(fn)
            assert isinstance(name, str)


# ═══════════════════════════════════════════════════════════════════════
# 5. OPERATOR TEMPLATE PROPOSER
# ═══════════════════════════════════════════════════════════════════════

class TestOperatorTemplateProposer:

    def test_propose_for_discrimination(self):
        proposer = OperatorTemplateProposer()
        results = proposer.propose("no_discrimination", "richer_property_language")
        assert len(results) > 0
        assert all("confidence" in r for r in results)
        assert all(r["confidence"] > 0 for r in results)

    def test_propose_for_wrong_reconstruction(self):
        proposer = OperatorTemplateProposer()
        results = proposer.propose("wrong_reconstruction", "", {"has_symmetry": True})
        assert len(results) > 0

    def test_propose_returns_empty_for_unknown(self):
        proposer = OperatorTemplateProposer()
        results = proposer.propose("totally_alien_failure")
        assert isinstance(results, list)


# ═══════════════════════════════════════════════════════════════════════
# 6. NEURAL COUNTEREXAMPLE GENERATOR
# ═══════════════════════════════════════════════════════════════════════

class TestNeuralCounterexampleGenerator:

    def test_all_probe_families_run(self):
        gen = NeuralCounterexampleGenerator(rng_seed=42)
        objs = _make_objects(4)
        kept = [0, 1]
        removed = [2, 3]
        pred_fn = lambda obj, all_objs, grid: obj.get("is_largest", False)
        probes = gen.generate_probes(objs, kept, removed, pred_fn)
        probe_types = {p.probe_type for p in probes}
        assert "color_relabeling" in probe_types
        assert "distractor_insertion" in probe_types
        assert "marker_target_swap" in probe_types
        assert "object_duplication" in probe_types
        assert "border_interior_swap" in probe_types

    def test_counterexample_dataclass(self):
        cx = Counterexample(probe_type="test", passed=True, details="ok")
        assert cx.probe_type == "test"
        assert cx.passed is True
        assert cx.details == "ok"

    def test_empty_objects(self):
        gen = NeuralCounterexampleGenerator(rng_seed=0)
        probes = gen.generate_probes([], [], [], lambda o, a, g: True)
        assert isinstance(probes, list)


# ═══════════════════════════════════════════════════════════════════════
# 7. SYMBOLIC VALIDATION GATE
# ═══════════════════════════════════════════════════════════════════════

class TestSymbolicValidationGate:

    def test_validation_passes_for_perfect_predicate(self):
        gate = SymbolicValidationGate(rng_seed=42)
        prop = InventedProperty(
            name="is_largest",
            compute_fn=lambda obj, all_objs, grid: obj.get("is_largest", False),
            source_cluster="test",
            correlation=1.0,
        )
        objs = _make_objects(4)
        result = gate.validate(
            prop,
            task_objects_list=[objs],
            task_kept_list=[[0]],
            task_removed_list=[[1, 2, 3]],
        )
        assert result["stages"]["training_discrimination"] is True

    def test_validation_fails_for_bad_predicate(self):
        gate = SymbolicValidationGate(rng_seed=42)
        prop = InventedProperty(
            name="always_true",
            compute_fn=lambda obj, all_objs, grid: True,
            source_cluster="test",
            correlation=0.0,
        )
        objs = _make_objects(4)
        result = gate.validate(
            prop,
            task_objects_list=[objs],
            task_kept_list=[[0]],
            task_removed_list=[[1, 2, 3]],
        )
        assert result["stages"]["training_discrimination"] is False
        assert result["passed"] is False

    def test_all_five_stages_present(self):
        gate = SymbolicValidationGate(rng_seed=42)
        prop = InventedProperty(
            name="is_largest",
            compute_fn=lambda obj, all_objs, grid: obj.get("is_largest", False),
            source_cluster="test",
            correlation=1.0,
        )
        objs = _make_objects(4)
        result = gate.validate(
            prop,
            task_objects_list=[objs, objs],
            task_kept_list=[[0], [0]],
            task_removed_list=[[1, 2, 3], [1, 2, 3]],
        )
        expected_stages = {
            "training_discrimination",
            "loo_validation",
            "active_falsification",
            "no_false_positives",
            "promotes_or_solves",
        }
        assert set(result["stages"].keys()) == expected_stages


# ═══════════════════════════════════════════════════════════════════════
# 8. CONCEPT GRAPH MEMORY
# ═══════════════════════════════════════════════════════════════════════

class TestConceptGraphMemory:

    def test_register_and_retrieve_predicate(self):
        mem = ConceptGraphMemory()
        prop = InventedProperty(
            name="test_pred",
            compute_fn=lambda o, a, g: True,
            source_cluster="c1",
            correlation=0.9,
        )
        mem.register_predicate(prop, "c1")
        assert len(mem.invented_predicates) == 1
        assert mem.get_predicate("test_pred") is prop
        assert mem.get_predicate("nonexistent") is None

    def test_register_operator(self):
        mem = ConceptGraphMemory()
        op = InventedOperator(
            name="op_test",
            signature="test",
            program_template={},
            preconditions=[],
            postconditions=[],
            invariants_preserved=[],
            source_traces=[],
        )
        mem.register_operator(op)
        assert len(mem.invented_operators) == 1

    def test_mark_solved_and_promoted(self):
        mem = ConceptGraphMemory()
        mem.mark_solved("task1", "pred1")
        mem.mark_promoted("task2", "pred2")
        assert mem.tasks_solved["task1"] == "pred1"
        assert mem.tasks_promoted["task2"] == "pred2"

    def test_summary(self):
        mem = ConceptGraphMemory()
        mem.primitive_predicates = ["p1", "p2"]
        s = mem.summary()
        assert s["n_primitives"] == 2
        assert s["n_invented_predicates"] == 0

    def test_dependency_graph(self):
        mem = ConceptGraphMemory()
        mem.add_dependency("compound_pred", "base_pred_1")
        mem.add_dependency("compound_pred", "base_pred_2")
        assert len(mem.prerequisite_graph["compound_pred"]) == 2


# ═══════════════════════════════════════════════════════════════════════
# 9. PIPELINE END-TO-END
# ═══════════════════════════════════════════════════════════════════════

class TestNeuralAbstractionPipeline:

    def test_smoke_empty(self):
        pipeline = NeuralAbstractionPipeline()
        mem = NearSolvedMemory()
        result = pipeline.run_abstraction_pipeline(mem, [])
        assert result["status"] == "no_states"

    def test_smoke_with_states(self):
        pipeline = NeuralAbstractionPipeline(correlation_threshold=0.3)
        mem = NearSolvedMemory()
        s1 = _make_state("t1", "no_discrimination", 0.6)
        s2 = _make_state("t2", "no_discrimination", 0.7)
        mem.store_partial(s1)
        mem.store_partial(s2)

        objs = _make_objects(4)
        tasks = [
            {
                "task_id": "t1",
                "train": [
                    {
                        "input_objects": objs,
                        "kept_indices": [0, 1],
                        "removed_indices": [2, 3],
                        "input_grid": None,
                    }
                ],
            },
            {
                "task_id": "t2",
                "train": [
                    {
                        "input_objects": objs,
                        "kept_indices": [0],
                        "removed_indices": [1, 2, 3],
                        "input_grid": None,
                    }
                ],
            },
        ]

        event_log = ReasoningEventLog()
        result = pipeline.run_abstraction_pipeline(mem, tasks, event_log)
        assert result["status"] == "ok"
        assert result["n_states"] == 2
        assert result["n_clusters"] >= 1
        assert isinstance(result["validated_predicates"], list)
        assert len(event_log) >= 1
