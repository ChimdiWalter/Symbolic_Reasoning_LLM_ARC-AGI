"""Tests for slot attention, graph network, and world model modules."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.neural.grid_encoder import torch_available


@pytest.mark.skipif(not torch_available(), reason="torch not available")
class TestSlotAttention:
    def test_slot_attention_forward(self):
        import torch
        from reasoning_project.neural.slot_attention import SlotAttentionModule
        sa = SlotAttentionModule(num_slots=4, slot_dim=32, input_dim=32, hidden_dim=64)
        inputs = torch.randn(2, 16, 32)
        slots, attn = sa(inputs)
        assert slots.shape == (2, 4, 32)
        assert attn.shape == (2, 4, 16)

    def test_grid_slot_model_forward(self):
        import torch
        from reasoning_project.neural.slot_attention import GridSlotModel
        model = GridSlotModel(num_slots=4, slot_dim=32, hidden_dim=64, max_grid_size=10)
        grids = torch.randint(0, 10, (2, 5, 5))
        valid = torch.ones(2, 5, 5, dtype=torch.bool)
        result = model(grids, valid)
        assert "loss" in result
        assert "slots" in result
        assert result["slots"].shape == (2, 4, 32)
        assert result["slot_masks"].shape[0] == 2
        assert result["slot_masks"].shape[1] == 4

    def test_extract_slots(self):
        from reasoning_project.neural.slot_attention import GridSlotModel
        model = GridSlotModel(num_slots=4, slot_dim=32, hidden_dim=64, max_grid_size=10)
        grid = np.array([[1, 0, 2], [0, 3, 0], [0, 0, 0]])
        result = model.extract_slots(grid)
        assert result["slots"].shape == (4, 32)
        assert result["slot_masks"].shape == (4, 3, 3)
        assert result["recon"].shape == (3, 3)


@pytest.mark.skipif(not torch_available(), reason="torch not available")
class TestGraphNetwork:
    def test_gns_forward(self):
        import torch
        from reasoning_project.neural.graph_network import GraphNetworkSimulator
        gns = GraphNetworkSimulator(
            input_node_dim=16, input_edge_dim=8,
            node_dim=32, edge_dim=16, hidden_dim=64,
            num_layers=2, output_node_dim=16,
        )
        nodes = torch.randn(5, 16)
        edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 4]], dtype=torch.long)
        edge_attr = torch.randn(4, 8)
        out = gns(nodes, edge_index, edge_attr)
        assert out.shape == (5, 16)

    def test_objects_to_graph_tensors(self):
        from reasoning_project.neural.graph_network import objects_to_graph_tensors
        objects = [
            {"color": 1, "size": 4, "bbox": (0, 0, 1, 1), "centroid": (0.5, 0.5), "is_rectangular": True},
            {"color": 2, "size": 2, "bbox": (2, 2, 2, 3), "centroid": (2.0, 2.5), "is_rectangular": True},
        ]
        nodes, edges, edge_attr = objects_to_graph_tensors(objects, (5, 5))
        assert nodes.shape == (2, 16)
        assert edges.shape[0] == 2
        assert edges.shape[1] == 2  # fully connected minus self-loops

    def test_grid_objects_to_dicts(self):
        from reasoning_project.neural.graph_network import grid_objects_to_dicts
        grid = np.array([[1, 1, 0], [0, 0, 2], [0, 2, 2]])
        objs = grid_objects_to_dicts(grid)
        assert len(objs) >= 2

    def test_empty_graph(self):
        from reasoning_project.neural.graph_network import objects_to_graph_tensors
        nodes, edges, edge_attr = objects_to_graph_tensors([], (3, 3))
        assert nodes.shape[0] == 0
        assert edges.shape[1] == 0


@pytest.mark.skipif(not torch_available(), reason="torch not available")
class TestWorldModel:
    def test_world_model_forward(self):
        import torch
        from reasoning_project.neural.graph_network import WorldModel
        model = WorldModel(num_slots=4, slot_dim=32, hidden_dim=64, gns_layers=2, max_grid_size=10)
        ig = torch.randint(0, 10, (2, 5, 5))
        iv = torch.ones(2, 5, 5, dtype=torch.bool)
        og = torch.randint(0, 10, (2, 4, 4))
        ov = torch.ones(2, 4, 4, dtype=torch.bool)
        result = model(ig, iv, og, ov)
        assert "loss" in result
        assert "input_slots" in result
        assert "predicted_output_slots" in result

    def test_world_model_predict(self):
        from reasoning_project.neural.graph_network import WorldModel
        model = WorldModel(num_slots=4, slot_dim=32, hidden_dim=64, gns_layers=2, max_grid_size=10)
        inp = np.array([[1, 2], [3, 0]])
        pred = model.predict(inp, (2, 2))
        assert pred.shape == (2, 2)
        assert pred.dtype in (np.int64, np.int32)

    def test_world_model_score_candidate(self):
        from reasoning_project.neural.graph_network import WorldModel
        model = WorldModel(num_slots=4, slot_dim=32, hidden_dim=64, gns_layers=2, max_grid_size=10)
        inp = np.array([[1, 2], [3, 0]])
        candidate = np.array([[0, 1], [2, 3]])
        score = model.score_candidate(inp, candidate)
        assert 0.0 <= score <= 1.0


@pytest.mark.skipif(not torch_available(), reason="torch not available")
class TestPortfolioIntegration:
    def test_world_model_reranker(self):
        from reasoning_project.neural.graph_network import WorldModel
        from reasoning_project.portfolio import WorldModelReranker
        model = WorldModel(num_slots=4, slot_dim=32, hidden_dim=64, gns_layers=2, max_grid_size=10)
        reranker = WorldModelReranker(model, device="cpu")
        inp = np.array([[1, 2, 0], [0, 3, 0], [0, 0, 4]])
        cand_a = np.array([[1, 1, 1], [0, 0, 0], [0, 0, 0]])
        cand_b = np.array([[0, 0, 0], [1, 1, 1], [0, 0, 0]])
        candidates = [
            ("solver_a", [cand_a], {"info": "a"}),
            ("solver_b", [cand_b], {"info": "b"}),
        ]
        ranked = reranker.rerank_candidates(inp, candidates)
        assert len(ranked) == 2
        assert all(isinstance(r[3], float) for r in ranked)
        assert ranked[0][3] >= ranked[1][3]

    def test_portfolio_with_reranker(self):
        from reasoning_project.neural.graph_network import WorldModel
        from reasoning_project.portfolio import PortfolioSolver, WorldModelReranker
        model = WorldModel(num_slots=4, slot_dim=32, hidden_dim=64, gns_layers=2, max_grid_size=10)
        reranker = WorldModelReranker(model, device="cpu")

        def dummy_solver(train_pairs, test_inputs):
            return [train_pairs[0][1].copy() for _ in test_inputs], {"solver": "dummy"}

        solvers = {"dummy": dummy_solver}
        portfolio = PortfolioSolver(solvers=solvers, reranker=reranker)
        train_pairs = [(np.array([[1, 2], [3, 0]]), np.array([[0, 1], [2, 3]]))]
        test_inputs = [np.array([[1, 2], [3, 0]])]
        test_outputs = [np.array([[0, 1], [2, 3]])]
        result = portfolio.solve("test_task", train_pairs, test_inputs, test_outputs)
        assert result.task_id == "test_task"

    def test_reranker_single_candidate_skips_reranking(self):
        from reasoning_project.neural.graph_network import WorldModel
        from reasoning_project.portfolio import PortfolioSolver, WorldModelReranker
        model = WorldModel(num_slots=4, slot_dim=32, hidden_dim=64, gns_layers=2, max_grid_size=10)
        reranker = WorldModelReranker(model, device="cpu")

        correct_out = np.array([[0, 1], [2, 3]])
        def good_solver(train_pairs, test_inputs):
            return [correct_out.copy() for _ in test_inputs], {"solver": "local_rule"}

        solvers = {"local_rule": good_solver}
        portfolio = PortfolioSolver(solvers=solvers, reranker=reranker)
        train_pairs = [(np.array([[1, 2], [3, 0]]), correct_out)]
        test_inputs = [np.array([[1, 2], [3, 0]])]
        test_outputs = [correct_out]
        result = portfolio.solve("test_single", train_pairs, test_inputs, test_outputs)
        assert result.solved
        assert result.solver_used == "local_rule"

    def test_reranker_preserves_best_on_close_scores(self):
        from reasoning_project.neural.graph_network import WorldModel
        from reasoning_project.portfolio import PortfolioSolver, WorldModelReranker
        model = WorldModel(num_slots=4, slot_dim=32, hidden_dim=64, gns_layers=2, max_grid_size=10)
        reranker = WorldModelReranker(model, device="cpu")

        correct_out = np.array([[0, 1], [2, 3]])
        wrong_out = np.array([[9, 9], [9, 9]])

        def first_solver(train_pairs, test_inputs):
            return [correct_out.copy() for _ in test_inputs], {"solver": "local_rule"}

        def second_solver(train_pairs, test_inputs):
            return [correct_out.copy() for _ in test_inputs], {"solver": "dsl"}

        def third_solver(train_pairs, test_inputs):
            return [wrong_out.copy() for _ in test_inputs], {"solver": "crop_extract"}

        solvers = {"local_rule": first_solver, "dsl": second_solver, "crop_extract": third_solver}
        portfolio = PortfolioSolver(solvers=solvers, reranker=reranker)
        train_pairs = [(np.array([[1, 2], [3, 0]]), correct_out)]
        test_inputs = [np.array([[1, 2], [3, 0]])]
        test_outputs = [correct_out]
        result = portfolio.solve("test_margin", train_pairs, test_inputs, test_outputs)
        assert result.solved

    def test_heuristic_route_includes_world_model(self):
        from reasoning_project.portfolio import heuristic_route
        features = {
            "same_size": 1.0, "pixel_change_rate": 0.3,
            "input_h": 5, "input_w": 5, "output_h": 5, "output_w": 5,
            "size_ratio": 1.0, "in_colors": 3, "out_colors": 3,
            "new_colors": 0, "in_objects": 2, "out_objects": 2,
        }
        order = heuristic_route(features)
        assert "world_model" in order
