"""Neural-guided but exactly verified candidate refinement loops."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .compression import compression_score, exact_match, training_error
from .falsifier import Falsifier
from .models import ModelConfig, build_model
from .operators import apply_program, candidate_programs
from .repair import evaluate_repair
from .schemas import CandidateResult, PredictionResult, Program, ProgramStep, ReasoningTask, TaskExample, program_signature, program_to_dict

try:
    import torch

    _TORCH_AVAILABLE = True
except Exception:  # pragma: no cover
    torch = None
    _TORCH_AVAILABLE = False


@dataclass
class RefinementConfig:
    candidate_max_depth: int = 2
    colors: List[int] = field(default_factory=lambda: list(range(1, 10)))
    dsl_profile: str = "core"
    initial_top_k: int = 24
    repair_top_k: int = 6
    return_top_k: int = 2
    use_falsifier: bool = False
    neural_guidance: bool = True
    test_time_adaptation_steps: int = 0
    test_time_adaptation_lr: float = 5e-4
    falsifier_oracle_probes: int = 0
    seed: int = 0
    device: str = "cpu"


@dataclass
class RankedCandidate:
    program: Program
    initial_score: float
    train_error: float
    verified: bool
    repaired: bool
    source: str
    embedding: np.ndarray
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program": program_to_dict(self.program),
            "program_signature": program_signature(self.program),
            "initial_score": float(self.initial_score),
            "train_error": float(self.train_error),
            "verified": bool(self.verified),
            "repaired": bool(self.repaired),
            "source": self.source,
            "embedding": [float(value) for value in self.embedding.tolist()],
            "diagnostics": dict(self.diagnostics),
        }


@dataclass
class RefinementResult:
    method_name: str
    task_id: str
    family: str
    top_candidates: List[RankedCandidate]
    predictions: Dict[str, List[np.ndarray]]
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method_name": self.method_name,
            "task_id": self.task_id,
            "family": self.family,
            "top_candidates": [candidate.to_dict() for candidate in self.top_candidates],
            "predictions": {
                split: [np.asarray(grid, dtype=int).tolist() for grid in grids]
                for split, grids in self.predictions.items()
            },
            "diagnostics": dict(self.diagnostics),
        }


def _train_examples(task: ReasoningTask) -> List[TaskExample]:
    return list(task.examples.get("train", []))


def _eval_splits(task: ReasoningTask) -> List[str]:
    return [split for split in ["test", "ood", "val"] if split in task.examples]


def _gpu_stats(device: str) -> Dict[str, float]:
    if not (_TORCH_AVAILABLE and device == "cuda" and torch.cuda.is_available()):
        return {"gpu_time_seconds": 0.0, "gpu_memory_mb": 0.0}
    return {
        "gpu_time_seconds": 0.0,
        "gpu_memory_mb": float(torch.cuda.max_memory_allocated() / (1024.0 * 1024.0)),
    }


def _candidate_program_lookup(programs: Sequence[Program]) -> Dict[str, Program]:
    return {program_signature(program): program for program in programs}


def _train_fit_labels(task: ReasoningTask, programs: Sequence[Program]) -> List[float]:
    train = _train_examples(task)
    return [1.0 if float(training_error(program, train)) == 0.0 else 0.0 for program in programs]


def _program_prediction(task: ReasoningTask, program: Program, splits: Sequence[str]) -> Dict[str, List[np.ndarray]]:
    predictions: Dict[str, List[np.ndarray]] = {split: [] for split in splits}
    for split in splits:
        for example in task.examples.get(split, []):
            predictions[split].append(apply_program(example.input_grid, program))
    return predictions


def evaluate_refinement_result(task: ReasoningTask, result: RefinementResult) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "method_name": result.method_name,
        "task_id": task.task_id,
        "family": task.family,
        "candidate_budget": int(result.diagnostics.get("candidate_count", 0)),
        "candidate_program_count": int(result.diagnostics.get("candidate_program_count", result.diagnostics.get("candidate_count", 0))),
        "candidates_scored": int(result.diagnostics.get("candidates_scored", result.diagnostics.get("candidate_count", 0))),
        "refinement_steps": int(result.diagnostics.get("refinement_steps", 0)),
        "verification_failures": int(result.diagnostics.get("verification_failures", 0)),
        "repair_success": float(bool(result.diagnostics.get("repair_success", False))),
        "runtime_seconds": float(result.diagnostics.get("runtime_seconds", 0.0)),
        "gpu_time_seconds": float(result.diagnostics.get("gpu_time_seconds", 0.0)),
        "gpu_memory_mb": float(result.diagnostics.get("gpu_memory_mb", 0.0)),
        "adaptation_steps": int(result.diagnostics.get("adaptation_steps", 0)),
        "adaptation_loss": result.diagnostics.get("adaptation_loss"),
    }
    top1_exact_scores: List[float] = []
    top2_exact_scores: List[float] = []
    pixel_scores: List[float] = []
    if "test" in task.examples:
        for example_index, example in enumerate(task.examples["test"]):
            candidate_matches = []
            candidate_pixels = []
            for candidate_index, _candidate in enumerate(result.top_candidates[:2]):
                predicted = result.predictions.get(f"test_top{candidate_index+1}", [])[example_index]
                candidate_matches.append(float(exact_match(predicted, example.output_grid)))
                candidate_pixels.append(float(np.mean(predicted == example.output_grid)) if predicted.shape == example.output_grid.shape else 0.0)
            top1_exact_scores.append(candidate_matches[0] if candidate_matches else 0.0)
            top2_exact_scores.append(float(any(value == 1.0 for value in candidate_matches)))
            pixel_scores.append(candidate_pixels[0] if candidate_pixels else 0.0)
    metrics["pass_at_1"] = float(np.mean(top1_exact_scores)) if top1_exact_scores else 0.0
    metrics["pass_at_2"] = float(np.mean(top2_exact_scores)) if top2_exact_scores else 0.0
    metrics["exact_solve_rate"] = float(all(value == 1.0 for value in top1_exact_scores)) if top1_exact_scores else 0.0
    metrics["pixel_accuracy"] = float(np.mean(pixel_scores)) if pixel_scores else 0.0
    return metrics


class RefinementEngine:
    def __init__(self, config: Optional[RefinementConfig] = None, ranker: Optional[Any] = None):
        self.config = config or RefinementConfig()
        self.ranker = ranker

    def _rank_programs(self, task: ReasoningTask, programs: Sequence[Program]) -> List[Any]:
        if self.ranker is None or not self.config.neural_guidance:
            return []
        return self.ranker.rank_task(task, programs)

    def _repair_candidates(
        self,
        task: ReasoningTask,
        ranked_candidates: Sequence[RankedCandidate],
        program_lookup: Dict[str, Program],
    ) -> List[RankedCandidate]:
        repaired: List[RankedCandidate] = []
        for candidate in ranked_candidates[: int(self.config.repair_top_k)]:
            report = evaluate_repair(
                candidate.program,
                _train_examples(task),
                colors=list(self.config.colors),
                seed=self.config.seed,
                max_depth=self.config.candidate_max_depth,
                dsl_profile=self.config.dsl_profile,
            )
            repaired_program = program_lookup.get(report.repaired_signature)
            if repaired_program is None:
                continue
            repaired_error = float(training_error(repaired_program, _train_examples(task)))
            repaired.append(
                RankedCandidate(
                    program=repaired_program,
                    initial_score=float(candidate.initial_score),
                    train_error=repaired_error,
                    verified=repaired_error == 0.0,
                    repaired=True,
                    source="repair",
                    embedding=np.asarray(candidate.embedding, dtype=float),
                    diagnostics={"repair": report.to_dict()},
                )
            )
        return repaired

    def run_task(
        self,
        task: ReasoningTask,
        method_name: str = "refinement_loop",
        use_integrated_rescoring: bool = False,
    ) -> RefinementResult:
        start = time.perf_counter()
        programs = candidate_programs(
            self.config.candidate_max_depth,
            self.config.colors,
            profile=self.config.dsl_profile,
        )
        program_lookup = _candidate_program_lookup(programs)
        adaptation_info = {"status": "not_requested", "steps": 0, "final_loss": None}
        if self.ranker is not None and self.config.test_time_adaptation_steps > 0:
            adaptation_labels = _train_fit_labels(task, programs)
            adaptation_start = time.perf_counter()
            adaptation_info = self.ranker.adapt_on_task(
                task,
                programs,
                adaptation_labels,
                steps=self.config.test_time_adaptation_steps,
                learning_rate=self.config.test_time_adaptation_lr,
            )
            adaptation_info["runtime_seconds"] = time.perf_counter() - adaptation_start
        ranked_programs = self._rank_programs(task, programs)
        if not ranked_programs:
            ranked_programs = []
            for program in programs:
                ranked_programs.append(
                    type(
                        "HeuristicRank",
                        (),
                        {
                            "program": program,
                            "score": -float(len(program)),
                            "metadata": {"program_features": []},
                        },
                    )()
                )
            ranked_programs.sort(key=lambda item: (-float(item.score), program_signature(item.program)))
        selected = ranked_programs[: int(self.config.initial_top_k)]
        candidates: List[RankedCandidate] = []
        verification_failures = 0
        falsifier = Falsifier(tolerance=0.0, perturbations=2, oracle_probes=self.config.falsifier_oracle_probes)
        for ranked in selected:
            fit_error = float(training_error(ranked.program, _train_examples(task)))
            verified = fit_error == 0.0
            if not verified:
                verification_failures += 1
            diagnostics: Dict[str, Any] = dict(getattr(ranked, "metadata", {}))
            if self.config.use_falsifier:
                report = falsifier.attack(ranked.program, _train_examples(task), world=None, seed=self.config.seed).to_dict()
                diagnostics["falsifier"] = report
            if use_integrated_rescoring:
                diagnostics["compression"] = compression_score(
                    ranked.program,
                    _train_examples(task),
                    world=None,
                    n_intervention_probes=0,
                )
            candidates.append(
                RankedCandidate(
                    program=ranked.program,
                    initial_score=float(getattr(ranked, "score", 0.0)),
                    train_error=fit_error,
                    verified=verified,
                    repaired=False,
                    source="ranked",
                    embedding=np.asarray(
                        getattr(ranked, "metadata", {}).get("program_features", []),
                        dtype=float,
                    )
                    if getattr(ranked, "metadata", {}).get("program_features")
                    else np.asarray([float(getattr(ranked, "score", 0.0))], dtype=float),
                    diagnostics=diagnostics,
                )
            )
        repair_candidates = self._repair_candidates(task, candidates, program_lookup)
        candidates.extend(repair_candidates)
        if use_integrated_rescoring:
            candidates.sort(
                key=lambda item: (
                    item.train_error,
                    -float(item.diagnostics.get("compression", {}).get("score", 0.0)),
                    -item.initial_score,
                    program_signature(item.program),
                )
            )
        else:
            candidates.sort(
                key=lambda item: (item.train_error, -item.initial_score, program_signature(item.program))
            )
        top_candidates = candidates[: int(self.config.return_top_k)]
        predictions: Dict[str, List[np.ndarray]] = {}
        for candidate_index, candidate in enumerate(top_candidates):
            candidate_predictions = _program_prediction(task, candidate.program, _eval_splits(task))
            for split, grids in candidate_predictions.items():
                predictions[f"{split}_top{candidate_index+1}"] = grids
        diagnostics = {
            "candidate_count": len(programs),
            "candidate_program_count": len(programs),
            "candidates_scored": len(selected),
            "ranked_top_k": int(self.config.initial_top_k),
            "refinement_steps": int(len(candidates)),
            "verification_failures": int(verification_failures),
            "repair_success": bool(any(candidate.repaired and candidate.verified for candidate in top_candidates)),
            "runtime_seconds": time.perf_counter() - start,
            "adaptation_steps": int(adaptation_info.get("steps", 0)),
            "adaptation_loss": adaptation_info.get("final_loss"),
            "trajectory_embeddings": [candidate.embedding.tolist() for candidate in candidates[: int(self.config.initial_top_k + self.config.repair_top_k)]],
            "trajectory_programs": [program_signature(candidate.program) for candidate in candidates[: int(self.config.initial_top_k + self.config.repair_top_k)]],
            "trajectory_verified": [bool(candidate.verified) for candidate in candidates[: int(self.config.initial_top_k + self.config.repair_top_k)]],
            **_gpu_stats(self.config.device),
        }
        return RefinementResult(
            method_name=method_name,
            task_id=task.task_id,
            family=task.family,
            top_candidates=top_candidates,
            predictions=predictions,
            diagnostics=diagnostics,
        )


def baseline_prediction_for_arc(
    task: ReasoningTask,
    model_name: str,
    candidate_max_depth: int = 1,
    dsl_profile: str = "core",
) -> PredictionResult:
    model = build_model(
        model_name,
        config=ModelConfig(
            candidate_max_depth=candidate_max_depth,
            colors=list(range(1, 10)),
            dsl_profile=str(dsl_profile),
        ),
    )
    return model.predict_task(task, splits=("test",), world=None)
