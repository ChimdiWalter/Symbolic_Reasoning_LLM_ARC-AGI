"""Baseline and scientist-model variants."""

from __future__ import annotations

import time
import warnings
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from .compression import compression_score, exact_match, grid_error, training_error
from .falsifier import Falsifier
from .generators import HiddenRuleWorld
from .operators import apply_program, candidate_programs, program_description_length
from .repair import evaluate_repair
from .schemas import CandidateResult, PredictionResult, Program, ProgramStep, ReasoningTask, TaskExample, program_signature


def _train_examples(task: ReasoningTask) -> List[TaskExample]:
    return list(task.examples.get("train", []))


def _predict_splits(task: ReasoningTask, splits: Sequence[str]) -> Dict[str, List[np.ndarray]]:
    return {split: [] for split in splits if split in task.examples}


def _fit_program_candidate(program: Program, examples: Iterable[TaskExample]) -> CandidateResult:
    fit = training_error(program, examples)
    score = fit * 10.0 + program_description_length(program) * 0.3
    return CandidateResult(
        program=program,
        train_error=fit,
        score=score,
        diagnostics={"selector": "fit_then_description"},
    )


def _ambiguity_level_from_fit_count(count: int) -> str:
    if count <= 1:
        return "low"
    if count <= 5:
        return "medium"
    return "high"


@dataclass
class ModelConfig:
    candidate_max_depth: int = 1
    colors: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7, 8])
    dsl_profile: str = "core"
    oracle_probes: int = 0
    seed: int = 0
    falsifier_candidate_limit: int = 40
    fixed_falsifier_budget: bool = False
    budget_match_falsifier: bool = False
    learned_hidden_dim: int = 64
    learned_max_iter: int = 300
    learned_alpha: float = 1e-4


def _base_budget(config: ModelConfig) -> Dict[str, Any]:
    return {
        "candidate_program_count": 0,
        "candidates_scored": 0,
        "candidates_falsified": 0,
        "oracle_probe_budget": int(config.oracle_probes),
        "oracle_probes_used": 0,
        "passive_checks_used": 0,
        "falsifier_candidate_limit": int(config.falsifier_candidate_limit),
        "fixed_falsifier_budget": float(bool(config.fixed_falsifier_budget)),
        "budget_match_falsifier": float(bool(config.budget_match_falsifier)),
    }


def _prediction_diagnostics(start: float, config: ModelConfig, candidate: Optional[CandidateResult] = None) -> Dict[str, Any]:
    diagnostics = _base_budget(config)
    if candidate is not None:
        for key in diagnostics:
            if key in candidate.diagnostics:
                diagnostics[key] = candidate.diagnostics[key]
    diagnostics["runtime_seconds"] = time.perf_counter() - start
    return diagnostics


class ReasoningModel:
    name = "abstract_model"

    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()

    def predict_task(
        self,
        task: ReasoningTask,
        splits: Sequence[str] = ("val", "test", "ood"),
        world: Optional[HiddenRuleWorld] = None,
    ) -> PredictionResult:
        raise NotImplementedError


class DirectIOProxyBaseline(ReasoningModel):
    """Nearest-example input-output proxy, not a trained transformer."""

    name = "direct_io_proxy"

    def predict_task(
        self,
        task: ReasoningTask,
        splits: Sequence[str] = ("val", "test", "ood"),
        world: Optional[HiddenRuleWorld] = None,
    ) -> PredictionResult:
        start = time.perf_counter()
        train = _train_examples(task)
        predictions = _predict_splits(task, splits)
        for split in predictions:
            for example in task.examples[split]:
                same_shape = [tr for tr in train if tr.input_grid.shape == example.input_grid.shape]
                if not same_shape:
                    predictions[split].append(example.input_grid.copy())
                    continue
                nearest = min(
                    same_shape,
                    key=lambda tr: float(np.mean(tr.input_grid != example.input_grid)),
                )
                predictions[split].append(nearest.output_grid.copy())
        return PredictionResult(
            model_name=self.name,
            task_id=task.task_id,
            family=task.family,
            predictions=predictions,
            candidate=None,
            diagnostics={
                **_prediction_diagnostics(start, self.config),
                "implemented_as": "nearest-example pixel proxy; no learned transformer dependency",
            },
        )


def _most_common_output_shape(train: Sequence[TaskExample]) -> tuple[int, int]:
    shapes = [tuple(int(v) for v in example.output_grid.shape) for example in train]
    if not shapes:
        return (1, 1)
    ranked = Counter(shapes).most_common()
    top_count = ranked[0][1]
    tied = sorted(shape for shape, count in ranked if count == top_count)
    return tied[0]


def _compress_large_grid(grid: np.ndarray, max_side: int = 10) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    h, w = arr.shape
    if h <= max_side and w <= max_side:
        return arr
    row_edges = np.linspace(0, h, num=max_side + 1, dtype=int)
    col_edges = np.linspace(0, w, num=max_side + 1, dtype=int)
    out = np.zeros((max_side, max_side), dtype=int)
    for row in range(max_side):
        for col in range(max_side):
            patch = arr[row_edges[row] : row_edges[row + 1], col_edges[col] : col_edges[col + 1]]
            if patch.size == 0:
                continue
            values, counts = np.unique(patch, return_counts=True)
            out[row, col] = int(values[np.argmax(counts)])
    return out


def _max_input_shape(task: ReasoningTask) -> tuple[int, int]:
    heights = []
    widths = []
    for examples in task.examples.values():
        for example in examples:
            feature_grid = _compress_large_grid(example.input_grid)
            heights.append(int(feature_grid.shape[0]))
            widths.append(int(feature_grid.shape[1]))
    return (max(heights) if heights else 1, max(widths) if widths else 1)


def _padded_flatten(grid: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    out = np.zeros(shape, dtype=float)
    feature_grid = _compress_large_grid(grid)
    h = min(shape[0], int(feature_grid.shape[0]))
    w = min(shape[1], int(feature_grid.shape[1]))
    out[:h, :w] = np.asarray(feature_grid, dtype=float)[:h, :w]
    return out.reshape(-1)


class LearnedTaskMLPBaseline(ReasoningModel):
    """Small task-conditioned MLP over padded input grids and output coordinates."""

    name = "learned_task_mlp"

    def _feature_vector(
        self,
        input_grid: np.ndarray,
        row: int,
        col: int,
        input_shape: tuple[int, int],
        output_shape: tuple[int, int],
        color_scale: float,
    ) -> np.ndarray:
        feature_grid = _compress_large_grid(input_grid)
        padded = _padded_flatten(input_grid, input_shape) / color_scale
        same_pixel = 0.0
        if 0 <= row < feature_grid.shape[0] and 0 <= col < feature_grid.shape[1]:
            same_pixel = float(feature_grid[row, col]) / color_scale
        features = np.concatenate(
            [
                padded,
                np.asarray(
                    [
                        float(row) / max(1.0, float(output_shape[0] - 1)),
                        float(col) / max(1.0, float(output_shape[1] - 1)),
                        float(feature_grid.shape[0]) / max(1.0, float(input_shape[0])),
                        float(feature_grid.shape[1]) / max(1.0, float(input_shape[1])),
                        same_pixel,
                    ],
                    dtype=float,
                ),
            ]
        )
        return features

    def _predict_shape(self, train: Sequence[TaskExample], fallback: tuple[int, int]) -> tuple[int, int]:
        if not train:
            return fallback
        shapes = [tuple(int(v) for v in example.output_grid.shape) for example in train]
        if len(set(shapes)) == 1:
            return shapes[0]
        input_shapes = [tuple(int(v) for v in example.input_grid.shape) for example in train]
        if len(set(shapes)) == len(set(input_shapes)):
            same_shape_pairs = sum(int(shape == in_shape) for shape, in_shape in zip(shapes, input_shapes))
            if same_shape_pairs == len(shapes):
                return fallback
        return _most_common_output_shape(train)

    def _fit_predictor(
        self,
        task: ReasoningTask,
    ) -> tuple[Any, np.ndarray, Dict[str, Any], tuple[int, int], tuple[int, int], float]:
        train = _train_examples(task)
        input_shape = _max_input_shape(task)
        predicted_shape = self._predict_shape(train, fallback=input_shape)
        max_output_h = max([predicted_shape[0], *[int(example.output_grid.shape[0]) for example in train]]) if train else predicted_shape[0]
        max_output_w = max([predicted_shape[1], *[int(example.output_grid.shape[1]) for example in train]]) if train else predicted_shape[1]
        feature_output_shape = (max_output_h, max_output_w)
        observed_max_color = max(
            [0, *self.config.colors, *[int(np.max(example.input_grid)) for example in train], *[int(np.max(example.output_grid)) for example in train]]
        )
        color_scale = float(max(1, observed_max_color))

        train_x: List[np.ndarray] = []
        train_y: List[int] = []
        for example in train:
            output_h, output_w = example.output_grid.shape
            for row in range(output_h):
                for col in range(output_w):
                    train_x.append(
                        self._feature_vector(
                            example.input_grid,
                            row,
                            col,
                            input_shape=input_shape,
                            output_shape=feature_output_shape,
                            color_scale=color_scale,
                        )
                    )
                    train_y.append(int(example.output_grid[row, col]))

        if not train_x:
            diagnostics = {
                "selector": "learned_task_mlp_empty_train_fallback",
                "implemented_as": "task-conditioned MLP over padded input grids and output coordinates",
                "train_pixel_accuracy": 0.0,
                "train_pixel_samples": 0,
                "predicted_output_shape": list(predicted_shape),
            }
            return None, np.asarray([], dtype=int), diagnostics, input_shape, predicted_shape, color_scale

        x = np.asarray(train_x, dtype=np.float32)
        y = np.asarray(train_y, dtype=np.int64)
        unique_labels = np.unique(y)
        diagnostics = {
            "selector": "learned_task_mlp",
            "implemented_as": "task-conditioned MLP over padded input grids and output coordinates",
            "train_pixel_samples": int(len(y)),
            "predicted_output_shape": list(predicted_shape),
            "learned_hidden_dim": int(self.config.learned_hidden_dim),
            "learned_max_iter": int(self.config.learned_max_iter),
            "learned_alpha": float(self.config.learned_alpha),
        }

        if len(unique_labels) == 1:
            diagnostics.update(
                {
                    "train_pixel_accuracy": 1.0,
                    "learned_class_count": 1,
                    "learned_solver": "constant_label",
                }
            )
            return None, np.asarray([int(unique_labels[0])], dtype=np.int64), diagnostics, input_shape, predicted_shape, color_scale

        from sklearn.exceptions import ConvergenceWarning
        from sklearn.neural_network import MLPClassifier

        use_fast_solver = x.shape[0] * x.shape[1] > 25000 or max(input_shape) > 10 or max(feature_output_shape) > 10
        solver = "adam" if use_fast_solver else "lbfgs"
        hidden_dim = min(int(self.config.learned_hidden_dim), 32) if use_fast_solver else int(self.config.learned_hidden_dim)
        max_iter = min(int(self.config.learned_max_iter), 60) if use_fast_solver else int(self.config.learned_max_iter)
        predictor = MLPClassifier(
            hidden_layer_sizes=(hidden_dim,),
            activation="relu",
            solver=solver,
            alpha=float(self.config.learned_alpha),
            max_iter=max_iter,
            learning_rate_init=0.01,
            random_state=int(self.config.seed),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=ConvergenceWarning)
            predictor.fit(x, y)
        train_pred = predictor.predict(x)
        diagnostics.update(
            {
                "train_pixel_accuracy": float(np.mean(train_pred == y)),
                "learned_class_count": int(len(unique_labels)),
                "learned_solver": f"sklearn_mlp_{solver}",
                "candidate_program_count": 0,
                "candidates_scored": 0,
            }
        )
        return predictor, np.asarray([], dtype=np.int64), diagnostics, input_shape, predicted_shape, color_scale

    def _predict_grid(
        self,
        predictor: Any,
        constant_label: np.ndarray,
        input_grid: np.ndarray,
        input_shape: tuple[int, int],
        output_shape: tuple[int, int],
        color_scale: float,
    ) -> np.ndarray:
        output_h, output_w = output_shape
        if predictor is None:
            fill_value = int(constant_label[0]) if constant_label.size else 0
            return np.full(output_shape, fill_value, dtype=int)
        predict_x = np.asarray(
            [
                self._feature_vector(
                    input_grid,
                    row,
                    col,
                    input_shape=input_shape,
                    output_shape=output_shape,
                    color_scale=color_scale,
                )
                for row in range(output_h)
                for col in range(output_w)
            ],
            dtype=np.float32,
        )
        pred = predictor.predict(predict_x).astype(int)
        return pred.reshape(output_shape)

    def predict_task(
        self,
        task: ReasoningTask,
        splits: Sequence[str] = ("val", "test", "ood"),
        world: Optional[HiddenRuleWorld] = None,
    ) -> PredictionResult:
        start = time.perf_counter()
        predictor, constant_label, diagnostics, input_shape, output_shape, color_scale = self._fit_predictor(task)
        predictions = _predict_splits(task, splits)
        for split in predictions:
            for example in task.examples[split]:
                shape = output_shape
                if shape == (1, 1):
                    shape = tuple(int(v) for v in example.input_grid.shape)
                predictions[split].append(
                    self._predict_grid(
                        predictor,
                        constant_label,
                        example.input_grid,
                        input_shape=input_shape,
                        output_shape=shape,
                        color_scale=color_scale,
                    )
                )
        return PredictionResult(
            model_name=self.name,
            task_id=task.task_id,
            family=task.family,
            predictions=predictions,
            candidate=None,
            diagnostics={**_prediction_diagnostics(start, self.config), **diagnostics},
        )


class ObjectCentricBaseline(ReasoningModel):
    """Object parser plus simple geometric transform detector."""

    name = "object_centric"

    def _detect_program(self, train: List[TaskExample]) -> CandidateResult:
        candidates = [
            [ProgramStep("identity")],
            [ProgramStep("reflect_horizontal")],
            [ProgramStep("reflect_vertical")],
            [ProgramStep("rotate_90")],
            [ProgramStep("rotate_180")],
            [ProgramStep("rotate_270")],
        ]
        scored = [_fit_program_candidate(program, train) for program in candidates]
        scored.sort(key=lambda item: (item.train_error, len(item.program), item.score))
        scored[0].diagnostics["selector"] = "object_centric_geometric_detector"
        scored[0].diagnostics.update(
            {
                "candidate_program_count": len(scored),
                "candidates_scored": len(scored),
            }
        )
        return scored[0]

    def predict_task(
        self,
        task: ReasoningTask,
        splits: Sequence[str] = ("val", "test", "ood"),
        world: Optional[HiddenRuleWorld] = None,
    ) -> PredictionResult:
        start = time.perf_counter()
        train = _train_examples(task)
        candidate = self._detect_program(train)
        predictions = _predict_splits(task, splits)
        for split in predictions:
            for example in task.examples[split]:
                predictions[split].append(apply_program(example.input_grid, candidate.program))
        return PredictionResult(
            model_name=self.name,
            task_id=task.task_id,
            family=task.family,
            predictions=predictions,
            candidate=candidate,
            diagnostics=_prediction_diagnostics(start, self.config, candidate),
        )


class TransformationLibraryModel(ReasoningModel):
    name = "transformation_library"

    def propose(self, train: List[TaskExample]) -> List[CandidateResult]:
        results: List[CandidateResult] = []
        for program in candidate_programs(
            self.config.candidate_max_depth,
            self.config.colors,
            profile=self.config.dsl_profile,
        ):
            results.append(_fit_program_candidate(program, train))
        results.sort(key=lambda item: (item.train_error, item.score, len(item.program), program_signature(item.program)))
        fit_count = sum(1 for result in results if float(result.train_error) == 0.0)
        for result in results:
            result.diagnostics.update(
                {
                    "candidate_program_count": len(results),
                    "candidates_scored": len(results),
                    "train_fit_candidate_count": fit_count,
                    "empirical_ambiguity_level": _ambiguity_level_from_fit_count(fit_count),
                }
            )
        return results

    def select_candidate(
        self,
        task: ReasoningTask,
        world: Optional[HiddenRuleWorld] = None,
    ) -> CandidateResult:
        return self.propose(_train_examples(task))[0]

    def predict_task(
        self,
        task: ReasoningTask,
        splits: Sequence[str] = ("val", "test", "ood"),
        world: Optional[HiddenRuleWorld] = None,
    ) -> PredictionResult:
        start = time.perf_counter()
        candidate = self.select_candidate(task, world=world)
        predictions = _predict_splits(task, splits)
        for split in predictions:
            for example in task.examples[split]:
                predictions[split].append(apply_program(example.input_grid, candidate.program))
        return PredictionResult(
            model_name=self.name,
            task_id=task.task_id,
            family=task.family,
            predictions=predictions,
            candidate=candidate,
            diagnostics=_prediction_diagnostics(start, self.config, candidate),
        )


class ProposerOnlyModel(TransformationLibraryModel):
    name = "proposer_only"

    def select_candidate(
        self,
        task: ReasoningTask,
        world: Optional[HiddenRuleWorld] = None,
    ) -> CandidateResult:
        train = _train_examples(task)
        proposed = self.propose(train)
        best = proposed[0]
        best.diagnostics["selector"] = "proposer_only_fit_then_description"
        if not (self.config.budget_match_falsifier and world is not None and self.config.oracle_probes > 0):
            return best

        limit = min(int(self.config.falsifier_candidate_limit), len(proposed))
        falsifier = Falsifier(tolerance=0.0, perturbations=2, oracle_probes=self.config.oracle_probes)
        oracle_checks = 0
        passive_checks = 0
        for candidate in proposed[:limit]:
            report = falsifier.attack(candidate.program, train, world=world, seed=self.config.seed)
            oracle_checks += report.oracle_checks
            passive_checks += report.passive_checks
        best.diagnostics.update(
            {
                "selector": "proposer_only_budget_matched_no_probe_outcome_use",
                "candidates_falsified": limit,
                "oracle_probe_budget": int(self.config.oracle_probes) * limit,
                "oracle_probes_used": oracle_checks,
                "passive_checks_used": passive_checks,
            }
        )
        return best


class ProposerFalsifierModel(TransformationLibraryModel):
    name = "proposer_falsifier"

    def select_candidate(
        self,
        task: ReasoningTask,
        world: Optional[HiddenRuleWorld] = None,
    ) -> CandidateResult:
        train = _train_examples(task)
        proposed = self.propose(train)
        falsifier = Falsifier(tolerance=0.0, perturbations=2, oracle_probes=self.config.oracle_probes)
        reports = []
        limit = min(int(self.config.falsifier_candidate_limit), len(proposed))
        accepted_candidate: Optional[CandidateResult] = None
        accepted_report: Optional[Dict[str, Any]] = None
        oracle_checks = 0
        passive_checks = 0
        for candidate in proposed[:limit]:
            report = falsifier.attack(candidate.program, train, world=world, seed=self.config.seed)
            report_dict = report.to_dict()
            reports.append(report_dict)
            oracle_checks += report.oracle_checks
            passive_checks += report.passive_checks
            if report.accepted and accepted_candidate is None:
                accepted_candidate = candidate
                accepted_report = report_dict
                if not self.config.fixed_falsifier_budget:
                    candidate.diagnostics.update(
                        {
                            "falsifier": report_dict,
                            "selector": "proposer_then_falsifier",
                            "candidates_falsified": len(reports),
                            "oracle_probe_budget": int(self.config.oracle_probes) * limit,
                            "oracle_probes_used": oracle_checks,
                            "passive_checks_used": passive_checks,
                        }
                    )
                    return candidate
        if accepted_candidate is not None and accepted_report is not None:
            accepted_candidate.diagnostics.update(
                {
                    "falsifier": accepted_report,
                    "falsifier_reports_considered": reports,
                    "selector": "proposer_then_falsifier",
                    "candidates_falsified": len(reports),
                    "oracle_probe_budget": int(self.config.oracle_probes) * limit,
                    "oracle_probes_used": oracle_checks,
                    "passive_checks_used": passive_checks,
                }
            )
            return accepted_candidate
        best = proposed[0]
        best.diagnostics["falsifier_reports_considered"] = reports
        best.diagnostics.update(
            {
                "selector": "fallback_best_fit_after_falsifier",
                "candidates_falsified": len(reports),
                "oracle_probe_budget": int(self.config.oracle_probes) * limit,
                "oracle_probes_used": oracle_checks,
                "passive_checks_used": passive_checks,
            }
        )
        return best


class CompressionSelectorModel(TransformationLibraryModel):
    name = "compression_selector"

    def select_candidate(
        self,
        task: ReasoningTask,
        world: Optional[HiddenRuleWorld] = None,
    ) -> CandidateResult:
        train = _train_examples(task)
        candidates = candidate_programs(
            self.config.candidate_max_depth,
            self.config.colors,
            profile=self.config.dsl_profile,
        )
        results: List[CandidateResult] = []
        for program in candidates:
            diagnostics = compression_score(
                program,
                train,
                world=world,
                n_intervention_probes=self.config.oracle_probes,
            )
            results.append(
                CandidateResult(
                    program=program,
                    train_error=diagnostics["fit_error"],
                    score=diagnostics["score"],
                    diagnostics={**diagnostics, "selector": "compression_intervention_proxy"},
                )
            )
        results.sort(key=lambda item: (item.train_error, item.score, len(item.program), program_signature(item.program)))
        probe_count = len(candidates) * int(self.config.oracle_probes) if world is not None else 0
        results[0].diagnostics.update(
            {
                "candidate_program_count": len(candidates),
                "candidates_scored": len(candidates),
                "oracle_probe_budget": probe_count,
                "oracle_probes_used": probe_count,
            }
        )
        return results[0]


class PathRepairModel(CompressionSelectorModel):
    name = "path_repair"

    def select_candidate(
        self,
        task: ReasoningTask,
        world: Optional[HiddenRuleWorld] = None,
    ) -> CandidateResult:
        train = _train_examples(task)
        base = super().select_candidate(task, world=world)
        repair_report = evaluate_repair(
            base.program,
            train,
            colors=self.config.colors,
            seed=self.config.seed,
            max_depth=self.config.candidate_max_depth,
            dsl_profile=self.config.dsl_profile,
        )
        repaired_program = [
            step
            for candidate in candidate_programs(
                self.config.candidate_max_depth,
                self.config.colors,
                profile=self.config.dsl_profile,
            )
            if program_signature(candidate) == repair_report.repaired_signature
            for step in candidate
        ]
        repaired_error = repair_report.repaired_error
        if repaired_program and repaired_error <= base.train_error:
            base = CandidateResult(
                program=repaired_program,
                train_error=repaired_error,
                score=base.score,
                diagnostics={**base.diagnostics, "repair": repair_report.to_dict(), "selector": "compression_plus_path_repair"},
            )
        else:
            base.diagnostics["repair"] = repair_report.to_dict()
        return base


class IntegratedScientistModel(CompressionSelectorModel):
    name = "integrated_scientist"

    def select_candidate(
        self,
        task: ReasoningTask,
        world: Optional[HiddenRuleWorld] = None,
    ) -> CandidateResult:
        train = _train_examples(task)
        raw_results = []
        falsifier = Falsifier(tolerance=0.0, perturbations=3, oracle_probes=self.config.oracle_probes)
        programs = candidate_programs(
            self.config.candidate_max_depth,
            self.config.colors,
            profile=self.config.dsl_profile,
        )
        oracle_checks = 0
        passive_checks = 0
        compression_probe_count = 0
        for program in programs:
            diagnostics = compression_score(
                program,
                train,
                world=world,
                n_intervention_probes=self.config.oracle_probes,
            )
            if world is not None:
                compression_probe_count += int(self.config.oracle_probes)
            report = falsifier.attack(program, train, world=world, seed=self.config.seed)
            oracle_checks += report.oracle_checks
            passive_checks += report.passive_checks
            if not report.accepted:
                diagnostics["score"] += 100.0 + report.contradictions
            raw_results.append(
                CandidateResult(
                    program=program,
                    train_error=diagnostics["fit_error"],
                    score=diagnostics["score"],
                    diagnostics={
                        **diagnostics,
                        "falsifier": report.to_dict(),
                        "selector": "integrated_compression_falsifier",
                    },
                )
        )
        raw_results.sort(key=lambda item: (item.train_error, item.score, len(item.program), program_signature(item.program)))
        best = raw_results[0]
        best.diagnostics.update(
            {
                "candidate_program_count": len(programs),
                "candidates_scored": len(programs),
                "candidates_falsified": len(programs),
                "oracle_probe_budget": compression_probe_count
                + (len(programs) * int(self.config.oracle_probes) if world is not None else 0),
                "oracle_probes_used": compression_probe_count + oracle_checks,
                "passive_checks_used": passive_checks,
            }
        )
        repair_report = evaluate_repair(
            best.program,
            train,
            colors=self.config.colors,
            seed=self.config.seed,
            max_depth=self.config.candidate_max_depth,
            dsl_profile=self.config.dsl_profile,
        )
        best.diagnostics["repair"] = repair_report.to_dict()
        best.diagnostics["component_contract"] = {
            "parser": "deterministic connected components and relation graph",
            "proposer": "finite explicit program enumeration",
            "executor": "operator library",
            "falsifier": "passive contradictions plus optional synthetic oracle probes",
            "compression": "MDL-like description, sparsity, nuisance robustness, intervention proxy",
            "abstraction_memory": "current run-level program candidates; no learned long-term memory",
        }
        return best


class RuleInductionModel(ReasoningModel):
    """Induce pixel-level rules from training examples and apply to test."""

    name = "rule_induction"

    _STRATEGIES = [
        "neighborhood_3x3",
        "cross_neighborhood",
        "color_neighbor_count",
        "color_nbr_diversity",
        "color_diag_orth",
        "periodic_2",
        "periodic_3",
        "color_object_size",
        "color_border",
    ]

    _GRID_STRATEGIES = [
        "majority_downscale_2",
        "majority_downscale_3",
        "majority_downscale_4",
        "extract_top_left",
        "extract_top_right",
        "extract_bottom_left",
        "extract_bottom_right",
        "extract_center",
    ]

    def _induce_rule(
        self, train: List[TaskExample], strategy: str,
    ) -> dict | None:
        rule: dict = {}
        for ex in train:
            inp = np.asarray(ex.input_grid, dtype=int)
            out = np.asarray(ex.output_grid, dtype=int)
            if inp.shape != out.shape:
                return None
            h, w = inp.shape
            size_map = self._object_size_map(inp) if strategy == "color_object_size" else None
            for r in range(h):
                for c in range(w):
                    key = self._pixel_key(inp, r, c, h, w, strategy, size_map=size_map)
                    if key is None:
                        return None
                    oc = int(out[r, c])
                    if key in rule:
                        if rule[key] != oc:
                            return None
                    else:
                        rule[key] = oc
        return rule if rule else None

    @staticmethod
    def _object_size_map(inp: np.ndarray) -> np.ndarray:
        from scipy import ndimage
        labeled, n = ndimage.label(inp > 0)
        size_grid = np.zeros_like(labeled)
        for lbl in range(1, n + 1):
            mask = labeled == lbl
            size_grid[mask] = int(mask.sum())
        return size_grid

    @staticmethod
    def _pixel_key(
        inp: np.ndarray, r: int, c: int, h: int, w: int, strategy: str,
        *, size_map: np.ndarray | None = None,
    ) -> tuple | None:
        ic = int(inp[r, c])
        if strategy == "neighborhood_3x3":
            nbr = []
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    nbr.append(int(inp[nr, nc]) if 0 <= nr < h and 0 <= nc < w else -1)
            return tuple(nbr)
        if strategy == "cross_neighborhood":
            nbr = [ic]
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                nbr.append(int(inp[nr, nc]) if 0 <= nr < h and 0 <= nc < w else -1)
            return tuple(nbr)
        if strategy == "color_neighbor_count":
            same = sum(
                1 for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                if 0 <= r + dr < h and 0 <= c + dc < w and int(inp[r + dr, c + dc]) == ic
            )
            return (ic, same)
        if strategy == "color_nbr_diversity":
            colors = set()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w:
                    colors.add(int(inp[nr, nc]))
            return (ic, len(colors))
        if strategy == "color_diag_orth":
            diag = any(
                0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr, c + dc] != 0
                for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            )
            orth = any(
                0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr, c + dc] != 0
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            )
            return (ic, diag, orth)
        if strategy.startswith("periodic_"):
            period = int(strategy.split("_")[1])
            return (ic, r % period, c % period)
        if strategy == "color_object_size":
            sz = int(size_map[r, c]) if size_map is not None else 0
            return (ic, sz)
        if strategy == "color_border":
            is_border = r == 0 or r == h - 1 or c == 0 or c == w - 1
            return (ic, is_border)
        return None

    def _apply_rule(
        self, inp: np.ndarray, rule: dict, strategy: str,
    ) -> np.ndarray | None:
        inp = np.asarray(inp, dtype=int)
        h, w = inp.shape
        pred = np.zeros_like(inp)
        size_map = self._object_size_map(inp) if strategy == "color_object_size" else None
        fallback: Dict[int, Counter] = {}
        for key, val in rule.items():
            if isinstance(key, tuple) and len(key) > 0:
                ic = key[0] if not isinstance(key[0], bool) else int(key[0])
                fallback.setdefault(ic, Counter())[val] += 1
        color_default = {
            ic: counts.most_common(1)[0][0] for ic, counts in fallback.items()
        }
        for r in range(h):
            for c in range(w):
                key = self._pixel_key(inp, r, c, h, w, strategy, size_map=size_map)
                if key is None:
                    return None
                if key in rule:
                    pred[r, c] = rule[key]
                elif int(inp[r, c]) in color_default:
                    pred[r, c] = color_default[int(inp[r, c])]
                else:
                    pred[r, c] = int(inp[r, c])
        return pred

    @staticmethod
    def _extract_offset(position: str, ih: int, iw: int, sh: int, sw: int):
        offsets = {
            "top_left": (0, 0),
            "top_right": (0, iw - sw),
            "bottom_left": (ih - sh, 0),
            "bottom_right": (ih - sh, iw - sw),
            "center": ((ih - sh) // 2, (iw - sw) // 2),
        }
        return offsets.get(position)

    def _try_grid_strategies(self, train, task, predictions):
        from scipy import ndimage as _ndi
        splits = [s for s in predictions]
        for gs in self._GRID_STRATEGIES:
            train_ok = True
            for ex in train:
                inp = np.asarray(ex.input_grid, dtype=int)
                out = np.asarray(ex.output_grid, dtype=int)
                pred = self._apply_grid_strategy(inp, gs)
                if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
                    train_ok = False
                    break
            if not train_ok:
                continue
            prog = [ProgramStep(f"grid_{gs}")]
            candidate = CandidateResult(
                program=prog,
                train_error=0.0,
                score=0.0,
                diagnostics={"strategy": gs},
            )
            for split in predictions:
                for ex in task.examples.get(split, []):
                    inp = np.asarray(ex.input_grid, dtype=int)
                    pred = self._apply_grid_strategy(inp, gs)
                    predictions[split].append(
                        pred if pred is not None else inp.copy()
                    )
            return candidate
        return None

    @staticmethod
    def _apply_grid_strategy(inp: np.ndarray, strategy: str):
        h, w = inp.shape
        if strategy.startswith("majority_downscale_"):
            factor = int(strategy.split("_")[-1])
            if h % factor != 0 or w % factor != 0:
                return None
            oh, ow = h // factor, w // factor
            out = np.zeros((oh, ow), dtype=int)
            for r in range(oh):
                for c in range(ow):
                    block = inp[r*factor:(r+1)*factor, c*factor:(c+1)*factor]
                    vals, counts = np.unique(block, return_counts=True)
                    out[r, c] = vals[np.argmax(counts)]
            return out
        if strategy.startswith("extract_"):
            pos = strategy[len("extract_"):]
            out_h, out_w = h // 2, w // 2
            if out_h < 1 or out_w < 1:
                return None
            off = RuleInductionModel._extract_offset(pos, h, w, out_h, out_w)
            if off is None:
                return None
            r0, c0 = off
            return inp[r0:r0+out_h, c0:c0+out_w].copy()
        return None

    def predict_task(
        self,
        task: ReasoningTask,
        splits: Sequence[str] = ("val", "test", "ood"),
        world: Optional[HiddenRuleWorld] = None,
    ) -> PredictionResult:
        start = time.perf_counter()
        train = _train_examples(task)
        predictions = _predict_splits(task, splits)
        best_candidate: Optional[CandidateResult] = None
        best_strategy: str = ""

        valid_rules: list = []
        for strategy in self._STRATEGIES:
            rule = self._induce_rule(train, strategy)
            if rule is None:
                continue
            train_ok = True
            for ex in train:
                pred = self._apply_rule(ex.input_grid, rule, strategy)
                if pred is None or not np.array_equal(pred, np.asarray(ex.output_grid, dtype=int)):
                    train_ok = False
                    break
            if train_ok:
                valid_rules.append((strategy, rule, len(rule)))

        valid_rules.sort(key=lambda x: x[2])

        for strategy, rule, n_rules in valid_rules:
            prog = [ProgramStep(f"induced_{strategy}")]
            candidate = CandidateResult(
                program=prog,
                train_error=0.0,
                score=0.0,
                diagnostics={"strategy": strategy, "rule_count": n_rules},
            )
            best_candidate = candidate
            best_strategy = strategy
            for split in predictions:
                for ex in task.examples.get(split, []):
                    pred = self._apply_rule(ex.input_grid, rule, strategy)
                    predictions[split].append(
                        pred if pred is not None else np.asarray(ex.input_grid, dtype=int).copy()
                    )
            break

        if best_candidate is None:
            best_candidate = self._try_grid_strategies(train, task, predictions)
            if best_candidate is not None:
                best_strategy = best_candidate.diagnostics.get("strategy", "")

        if best_candidate is None:
            best_candidate = CandidateResult(
                program=[ProgramStep("identity")],
                train_error=1.0,
                score=100.0,
                diagnostics={"strategy": "none"},
            )
            for split in predictions:
                for ex in task.examples.get(split, []):
                    predictions[split].append(np.asarray(ex.input_grid, dtype=int).copy())

        diagnostics = _prediction_diagnostics(start, self.config, best_candidate)
        diagnostics["induced_strategy"] = best_strategy
        return PredictionResult(
            model_name=self.name,
            task_id=task.task_id,
            family=task.family,
            predictions=predictions,
            candidate=best_candidate,
            diagnostics=diagnostics,
        )


MODEL_REGISTRY = {
    DirectIOProxyBaseline.name: DirectIOProxyBaseline,
    LearnedTaskMLPBaseline.name: LearnedTaskMLPBaseline,
    ObjectCentricBaseline.name: ObjectCentricBaseline,
    TransformationLibraryModel.name: TransformationLibraryModel,
    ProposerOnlyModel.name: ProposerOnlyModel,
    ProposerFalsifierModel.name: ProposerFalsifierModel,
    CompressionSelectorModel.name: CompressionSelectorModel,
    PathRepairModel.name: PathRepairModel,
    IntegratedScientistModel.name: IntegratedScientistModel,
    RuleInductionModel.name: RuleInductionModel,
}


def build_model(name: str, config: Optional[ModelConfig] = None) -> ReasoningModel:
    if name not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model: {name}")
    return MODEL_REGISTRY[name](config=config)
