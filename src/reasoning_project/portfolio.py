"""Portfolio solver: routes ARC tasks to the best solver family based on task features.

Architecture: collect-all-then-select (multi-proposer reasoning).
All solvers propose candidates in parallel, then the best is selected via
training-pair validation, complexity preference, and optional world-model reranking.
"""
from __future__ import annotations

import time
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field


@dataclass
class PortfolioResult:
    """Result from portfolio routing."""
    task_id: str
    solver_used: str
    solved: bool
    predictions: Optional[List[np.ndarray]]
    confidence: float
    all_solver_results: Dict[str, Dict[str, Any]]
    routing_reason: str
    elapsed_seconds: float
    reranker_info: Optional[Dict[str, Any]] = None


def compute_task_features(train_pairs: List[Tuple[np.ndarray, np.ndarray]]) -> Dict[str, float]:
    """Compute routing features from training examples."""
    features = {}

    sizes_match = all(inp.shape == out.shape for inp, out in train_pairs)
    features["same_size"] = float(sizes_match)

    if train_pairs:
        inp0, out0 = train_pairs[0]
        features["input_h"] = float(inp0.shape[0])
        features["input_w"] = float(inp0.shape[1])
        features["output_h"] = float(out0.shape[0])
        features["output_w"] = float(out0.shape[1])
        features["size_ratio"] = (out0.shape[0] * out0.shape[1]) / max(inp0.shape[0] * inp0.shape[1], 1)
    else:
        features["input_h"] = 0
        features["input_w"] = 0
        features["output_h"] = 0
        features["output_w"] = 0
        features["size_ratio"] = 1.0

    all_in_colors = set()
    all_out_colors = set()
    for inp, out in train_pairs:
        all_in_colors.update(inp.flatten().tolist())
        all_out_colors.update(out.flatten().tolist())
    features["in_colors"] = float(len(all_in_colors))
    features["out_colors"] = float(len(all_out_colors))
    features["new_colors"] = float(len(all_out_colors - all_in_colors))

    if sizes_match:
        pixel_changes = []
        for inp, out in train_pairs:
            pixel_changes.append(float(np.mean(inp != out)))
        features["pixel_change_rate"] = float(np.mean(pixel_changes))
    else:
        features["pixel_change_rate"] = 1.0

    from scipy import ndimage
    in_obj_counts = []
    out_obj_counts = []
    for inp, out in train_pairs:
        _, n_in = ndimage.label(inp > 0)
        _, n_out = ndimage.label(out > 0)
        in_obj_counts.append(n_in)
        out_obj_counts.append(n_out)
    features["in_objects"] = float(np.mean(in_obj_counts))
    features["out_objects"] = float(np.mean(out_obj_counts))

    return features


def heuristic_route(features: Dict[str, float]) -> List[str]:
    """Decide solver order based on task features. Returns ordered solver list."""
    order = []

    if features["same_size"] > 0.5:
        if features["pixel_change_rate"] < 0.5:
            order.append("local_rule")
            order.append("color_solver")
            order.append("dsl")
            order.append("cegis")
        else:
            order.append("dsl")
            order.append("color_solver")
            order.append("local_rule")
            order.append("cegis")
    else:
        if features["size_ratio"] < 1.0:
            order.append("separator_decompose")
            order.append("crop_extract")
            order.append("dsl")
            order.append("cegis")
        else:
            order.append("dsl")
            order.append("separator_decompose")
            order.append("crop_extract")
            order.append("cegis")

    if features.get("in_objects", 0) >= 3 and features.get("out_objects", 0) >= 2:
        if "object_graph" not in order:
            order.insert(min(1, len(order)), "object_graph")

    for fallback in ["local_rule", "color_solver", "separator_decompose", "crop_extract",
                     "object_graph", "rule_induction", "abstract_program", "fill_solver",
                     "relation_solver", "reasoning_engine", "dsl", "cegis", "world_model"]:
        if fallback not in order:
            order.append(fallback)

    return order


def _complexity_score(meta: Dict[str, Any]) -> float:
    """Lower = simpler. Used for tiebreaking between competing solutions.

    DSL programs get a bonus (lower score) because they are verified exact
    on all training pairs by construction. The reasoning engine gets a similar
    bonus because it uses LOO cross-validation for soundness.
    """
    if "program" in meta:
        return float(len(meta["program"])) * 0.5
    strategy = meta.get("strategy", "")
    if strategy in ("discriminative_filter", "transform_induction", "compositional"):
        return 3.0
    if "n_rules" in meta:
        return float(meta["n_rules"])
    if strategy:
        return 10.0
    return 100.0


def _perception_guided_route(
    base_order: List[str],
    pipeline,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[str]:
    """Enhance solver ordering using neural perception analysis."""
    try:
        analysis = pipeline.analyze_task(train_pairs)
        perception = analysis["perception"]
    except Exception:
        return base_order

    order = list(base_order)

    if perception.has_separators > 0.5:
        _promote(order, "separator_decompose")
    if perception.has_containment > 0.5:
        _promote(order, "crop_extract")
        _promote(order, "object_graph")
    if perception.layout_type == "single_object":
        _promote(order, "local_rule")
        _promote(order, "fill_solver")
    if perception.layout_type == "grid_of_cells":
        _promote(order, "separator_decompose")
    if perception.estimated_object_count >= 5:
        _promote(order, "abstract_program")

    return order


def _promote(order: List[str], solver: str) -> None:
    """Move solver to position 0 (or 1 if already near front)."""
    if solver in order:
        order.remove(solver)
        order.insert(0, solver)


class WorldModelReranker:
    """Reranks candidate predictions using the world model's task-conditioned scoring."""

    def __init__(self, world_model, device: str = "cpu"):
        self.world_model = world_model
        self.device = device

    def score(
        self,
        input_grid: np.ndarray,
        candidate_output: np.ndarray,
        train_pairs=None,
    ) -> float:
        return self.world_model.score_candidate(
            input_grid, candidate_output, self.device, train_pairs=train_pairs
        )

    def rerank_candidates(
        self,
        input_grid: np.ndarray,
        candidates: List[Tuple[str, List[np.ndarray], Dict[str, Any]]],
        train_pairs=None,
    ) -> List[Tuple[str, List[np.ndarray], Dict[str, Any], float]]:
        scored = []
        for solver_name, predictions, metadata in candidates:
            avg_score = float(np.mean([
                self.score(input_grid, pred, train_pairs=train_pairs) for pred in predictions
            ])) if predictions else 0.0
            scored.append((solver_name, predictions, metadata, avg_score))
        scored.sort(key=lambda x: -x[3])
        return scored


class PortfolioSolver:
    """Multi-proposer portfolio: runs all solvers, then selects the best candidate."""

    def __init__(
        self,
        solvers: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 600.0,
        routing: str = "heuristic",
        reranker: Optional[WorldModelReranker] = None,
        mode: str = "collect_all",
        perception_pipeline=None,
    ):
        self.solvers = solvers or {}
        self.timeout_seconds = timeout_seconds
        self.routing = routing
        self.reranker = reranker
        self.mode = mode
        self.perception_pipeline = perception_pipeline

    def solve(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        test_outputs: Optional[List[np.ndarray]] = None,
    ) -> PortfolioResult:
        t0 = time.perf_counter()
        features = compute_task_features(train_pairs)
        solver_order = heuristic_route(features)

        if self.perception_pipeline is not None:
            solver_order = _perception_guided_route(
                solver_order, self.perception_pipeline, train_pairs,
            )

        all_results = {}
        all_candidates = []

        for solver_name in solver_order:
            if time.perf_counter() - t0 > self.timeout_seconds:
                break

            if solver_name not in self.solvers:
                continue

            solver_fn = self.solvers[solver_name]
            try:
                result = solver_fn(train_pairs, test_inputs)
            except Exception as e:
                all_results[solver_name] = {"error": str(e)}
                continue

            if result is None:
                all_results[solver_name] = {"solved": False}
                continue

            predictions, metadata = result
            correct = False
            if test_outputs is not None and predictions is not None:
                correct = all(
                    np.array_equal(p, e) for p, e in zip(predictions, test_outputs)
                )

            meta_dict = metadata if isinstance(metadata, dict) else {"info": str(metadata)}
            all_results[solver_name] = {
                "solved": correct if test_outputs else (predictions is not None),
                "metadata": meta_dict,
            }

            if predictions is not None:
                all_candidates.append((solver_name, predictions, meta_dict, correct))

                if self.mode == "first_hit":
                    elapsed = time.perf_counter() - t0
                    return PortfolioResult(
                        task_id=task_id,
                        solver_used=solver_name,
                        solved=correct if test_outputs else True,
                        predictions=predictions,
                        confidence=1.0 if correct else 0.5,
                        all_solver_results=all_results,
                        routing_reason=f"first_hit: accepted {solver_name} (order: {solver_order[:solver_order.index(solver_name)+1]})",
                        elapsed_seconds=elapsed,
                    )

        return self._select_best(
            task_id, train_pairs, test_inputs, test_outputs,
            all_candidates, all_results, solver_order, t0,
        )

    def _select_best(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        test_outputs: Optional[List[np.ndarray]],
        all_candidates: List[Tuple[str, List[np.ndarray], Dict[str, Any], bool]],
        all_results: Dict[str, Dict[str, Any]],
        solver_order: List[str],
        t0: float,
    ) -> PortfolioResult:
        if not all_candidates:
            elapsed = time.perf_counter() - t0
            return PortfolioResult(
                task_id=task_id,
                solver_used="none",
                solved=False,
                predictions=None,
                confidence=0.0,
                all_solver_results=all_results,
                routing_reason=f"collect_all: {solver_order} (all failed)",
                elapsed_seconds=elapsed,
            )

        # Group candidates by whether they agree on predictions
        prediction_groups: Dict[str, List[Tuple[str, List[np.ndarray], Dict, bool]]] = {}
        for cand in all_candidates:
            solver_name, preds, meta, correct = cand
            key = str([p.tolist() for p in preds])
            if key not in prediction_groups:
                prediction_groups[key] = []
            prediction_groups[key].append(cand)

        # Score each candidate: (n_agreeing_solvers, -complexity, routing_priority)
        scored = []
        for cand in all_candidates:
            solver_name, preds, meta, correct = cand
            key = str([p.tolist() for p in preds])
            n_agree = len(prediction_groups[key])
            complexity = _complexity_score(meta)
            route_priority = solver_order.index(solver_name) if solver_name in solver_order else 99
            scored.append((
                n_agree,
                -complexity,
                -route_priority,
                solver_name, preds, meta, correct,
            ))

        scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

        best_name = scored[0][3]
        best_preds = scored[0][4]
        best_meta = scored[0][5]
        best_correct = scored[0][6]

        # Optional: world model reranking — only override on clear margin + tie
        if self.reranker is not None and len(all_candidates) > 1:
            best_key = str([p.tolist() for p in best_preds])
            best_n_agree = len(prediction_groups.get(best_key, []))

            rerank_input = [(s, p, m) for s, p, m, _ in all_candidates]
            try:
                ranked = self.reranker.rerank_candidates(
                    test_inputs[0], rerank_input, train_pairs=train_pairs
                )
                best_wm_name = ranked[0][0]
                best_wm_preds = ranked[0][1]
                best_wm_score = ranked[0][3]

                current_wm_score = next(
                    (r[3] for r in ranked if r[0] == best_name), 0.0
                )

                wm_key = str([p.tolist() for p in best_wm_preds])
                wm_n_agree = len(prediction_groups.get(wm_key, []))

                margin = 0.15
                if (best_wm_name != best_name and
                    best_wm_score - current_wm_score > margin and
                    wm_n_agree >= best_n_agree):
                    best_name = ranked[0][0]
                    best_preds = ranked[0][1]
                    best_meta = ranked[0][2]
                    best_correct = False
                    if test_outputs is not None:
                        best_correct = all(
                            np.array_equal(p, e)
                            for p, e in zip(best_preds, test_outputs)
                        )
            except Exception:
                pass

        # Optional: world model simulation scoring
        if (self.perception_pipeline is not None and
            self.perception_pipeline.world_simulator.world_model is not None and
            len(all_candidates) > 1):
            try:
                sim_scores = {}
                for solver_name, preds, meta, _ in all_candidates:
                    sim = self.perception_pipeline.score_hypothesis(
                        preds[0], test_inputs[0], train_pairs,
                        hypothesis_meta={"solver": solver_name},
                    )
                    sim_scores[solver_name] = sim.agreement_score
                best_sim_name = max(sim_scores, key=sim_scores.get)
                if (best_sim_name != best_name and
                    sim_scores.get(best_sim_name, 0) - sim_scores.get(best_name, 0) > 0.1):
                    for s, p, m, c in all_candidates:
                        if s == best_sim_name:
                            best_name = s
                            best_preds = p
                            best_meta = m
                            best_correct = c
                            break
            except Exception:
                pass

        n_proposers = len(all_candidates)
        n_distinct = len(prediction_groups)

        elapsed = time.perf_counter() - t0
        return PortfolioResult(
            task_id=task_id,
            solver_used=best_name,
            solved=best_correct if test_outputs else True,
            predictions=best_preds,
            confidence=1.0 if best_correct else 0.5,
            all_solver_results=all_results,
            routing_reason=f"collect_all: {n_proposers} proposals, {n_distinct} distinct, selected {best_name}",
            elapsed_seconds=elapsed,
            reranker_info=(
                {"n_proposers": n_proposers, "n_distinct": n_distinct}
                if n_proposers > 1 else None
            ),
        )
