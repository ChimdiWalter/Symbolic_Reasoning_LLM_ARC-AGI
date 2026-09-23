"""Local ARC/ARC-AGI loading and ARC-only evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np

from .compression import exact_match
from .schemas import PredictionResult, ReasoningTask, TaskExample, grid_from_list, grid_to_list, program_signature
from .utils import read_json


ARC_FILE_NAMES = {
    "training": {
        "challenges": ["arc-agi_training_challenges.json", "training_challenges.json"],
        "solutions": ["arc-agi_training_solutions.json", "training_solutions.json"],
    },
    "evaluation": {
        "challenges": ["arc-agi_evaluation_challenges.json", "evaluation_challenges.json"],
        "solutions": ["arc-agi_evaluation_solutions.json", "evaluation_solutions.json"],
    },
    "test": {
        "challenges": ["arc-agi_test_challenges.json", "test_challenges.json"],
        "solutions": ["arc-agi_test_solutions.json", "test_solutions.json"],
        "submission": ["sample_submission.json"],
    },
}


@dataclass
class ARCExample:
    input_grid: np.ndarray
    output_grid: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_output(self) -> bool:
        return self.output_grid is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_grid": grid_to_list(self.input_grid),
            "output_grid": None if self.output_grid is None else grid_to_list(self.output_grid),
            "metadata": dict(self.metadata),
        }


@dataclass
class ARCTask:
    task_id: str
    split: str
    train: List[ARCExample]
    test: List[ARCExample]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_test_solutions(self) -> bool:
        return bool(self.test) and all(example.has_output for example in self.test)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "split": self.split,
            "train": [example.to_dict() for example in self.train],
            "test": [example.to_dict() for example in self.test],
            "metadata": dict(self.metadata),
        }


def _resolve_existing(root: Path, candidates: Sequence[str], required: bool = True) -> Optional[Path]:
    for name in candidates:
        path = root / name
        if path.exists():
            return path
    if required:
        raise FileNotFoundError(f"None of these ARC files exist under {root}: {list(candidates)}")
    return None


def _validate_grid(data: Any, *, context: str) -> np.ndarray:
    if not isinstance(data, list) or not data:
        raise ValueError(f"{context}: grid must be a non-empty list of rows")
    if not all(isinstance(row, list) and row for row in data):
        raise ValueError(f"{context}: every grid row must be a non-empty list")
    width = len(data[0])
    for row_index, row in enumerate(data):
        if len(row) != width:
            raise ValueError(f"{context}: row {row_index} has width {len(row)}; expected {width}")
        for col_index, value in enumerate(row):
            if not isinstance(value, int):
                raise ValueError(f"{context}: grid value at ({row_index}, {col_index}) is not an int")
            if value < 0 or value > 9:
                raise ValueError(f"{context}: grid value at ({row_index}, {col_index})={value} is outside 0..9")
    return grid_from_list(data)


def _load_solutions(path: Optional[Path]) -> Dict[str, List[np.ndarray]]:
    if path is None:
        return {}
    raw = read_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: solution file must be a task-id mapping")
    solutions: Dict[str, List[np.ndarray]] = {}
    for task_id, outputs in raw.items():
        if not isinstance(outputs, list):
            raise ValueError(f"{path}:{task_id}: solutions must be a list of output grids")
        solutions[str(task_id)] = [
            _validate_grid(output, context=f"{path}:{task_id}:solution[{idx}]")
            for idx, output in enumerate(outputs)
        ]
    return solutions


def _load_submission_template(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {}
    raw = read_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: sample submission must be a task-id mapping")
    return raw


def load_arc_tasks(
    root: str | Path,
    split: str = "training",
    max_tasks: Optional[int] = None,
    include_solutions: bool = True,
) -> List[ARCTask]:
    """Load local ARC tasks in a deterministic order.

    ARC tasks do not contain known latent programs. This loader preserves ARC's
    train/test structure and attaches test outputs only when real solution files
    are available for the requested split.
    """

    split = str(split)
    if split not in ARC_FILE_NAMES:
        raise ValueError(f"Unknown ARC split: {split}")
    root_path = Path(root)
    challenge_path = _resolve_existing(root_path, ARC_FILE_NAMES[split]["challenges"], required=True)
    solution_path = _resolve_existing(root_path, ARC_FILE_NAMES[split].get("solutions", []), required=False)
    submission_path = _resolve_existing(root_path, ARC_FILE_NAMES[split].get("submission", []), required=False)

    challenges = read_json(challenge_path)
    if not isinstance(challenges, dict):
        raise ValueError(f"{challenge_path}: challenge file must be a task-id mapping")
    solutions = _load_solutions(solution_path) if include_solutions else {}
    submission_template = _load_submission_template(submission_path)

    task_ids = sorted(str(task_id) for task_id in challenges)
    if max_tasks is not None:
        task_ids = task_ids[: int(max_tasks)]

    tasks: List[ARCTask] = []
    for task_id in task_ids:
        raw_task = challenges[task_id]
        if not isinstance(raw_task, dict):
            raise ValueError(f"{challenge_path}:{task_id}: task must be an object")
        raw_train = raw_task.get("train")
        raw_test = raw_task.get("test")
        if not isinstance(raw_train, list) or not isinstance(raw_test, list):
            raise ValueError(f"{challenge_path}:{task_id}: task requires train and test lists")

        train_examples: List[ARCExample] = []
        for idx, item in enumerate(raw_train):
            if not isinstance(item, dict) or "input" not in item or "output" not in item:
                raise ValueError(f"{challenge_path}:{task_id}:train[{idx}] requires input and output")
            train_examples.append(
                ARCExample(
                    input_grid=_validate_grid(item["input"], context=f"{challenge_path}:{task_id}:train[{idx}].input"),
                    output_grid=_validate_grid(item["output"], context=f"{challenge_path}:{task_id}:train[{idx}].output"),
                    metadata={"arc_split": split, "example_split": "train", "index": idx},
                )
            )

        attached_solutions = solutions.get(task_id, [])
        if attached_solutions and len(attached_solutions) != len(raw_test):
            raise ValueError(
                f"{challenge_path}:{task_id}: solution count {len(attached_solutions)} does not match test count {len(raw_test)}"
            )
        test_examples: List[ARCExample] = []
        for idx, item in enumerate(raw_test):
            if not isinstance(item, dict) or "input" not in item:
                raise ValueError(f"{challenge_path}:{task_id}:test[{idx}] requires input")
            output = attached_solutions[idx] if attached_solutions else None
            test_examples.append(
                ARCExample(
                    input_grid=_validate_grid(item["input"], context=f"{challenge_path}:{task_id}:test[{idx}].input"),
                    output_grid=output,
                    metadata={"arc_split": split, "example_split": "test", "index": idx},
                )
            )

        tasks.append(
            ARCTask(
                task_id=task_id,
                split=split,
                train=train_examples,
                test=test_examples,
                metadata={
                    "source": "local_arc_agi",
                    "challenge_path": str(challenge_path),
                    "solution_path": None if solution_path is None else str(solution_path),
                    "sample_submission_path": None if submission_path is None else str(submission_path),
                    "has_sample_submission_entry": task_id in submission_template,
                    "has_test_solutions": bool(attached_solutions),
                },
            )
        )
    return tasks


def load_conceptarc_tasks(
    root: str | Path,
    max_tasks: Optional[int] = None,
) -> List[ARCTask]:
    """Load ConceptARC tasks from corpus directory.

    ConceptARC uses the same JSON format as ARC (train/test with input/output),
    organized into concept-group subdirectories. Each task has 3 test examples
    with known outputs.
    """
    root_path = Path(root) / "corpus"
    if not root_path.is_dir():
        raise FileNotFoundError(f"ConceptARC corpus not found at {root_path}")

    tasks: List[ARCTask] = []
    for group_dir in sorted(root_path.iterdir()):
        if not group_dir.is_dir():
            continue
        concept_group = group_dir.name
        for task_file in sorted(group_dir.glob("*.json")):
            raw = read_json(task_file)
            task_id = task_file.stem
            train_examples: List[ARCExample] = []
            for idx, item in enumerate(raw.get("train", [])):
                train_examples.append(
                    ARCExample(
                        input_grid=_validate_grid(item["input"], context=f"{task_file}:train[{idx}].input"),
                        output_grid=_validate_grid(item["output"], context=f"{task_file}:train[{idx}].output"),
                        metadata={"concept_group": concept_group, "example_split": "train", "index": idx},
                    )
                )
            test_examples: List[ARCExample] = []
            for idx, item in enumerate(raw.get("test", [])):
                out_grid = _validate_grid(item["output"], context=f"{task_file}:test[{idx}].output") if "output" in item else None
                test_examples.append(
                    ARCExample(
                        input_grid=_validate_grid(item["input"], context=f"{task_file}:test[{idx}].input"),
                        output_grid=out_grid,
                        metadata={"concept_group": concept_group, "example_split": "test", "index": idx},
                    )
                )
            tasks.append(
                ARCTask(
                    task_id=task_id,
                    split="conceptarc",
                    train=train_examples,
                    test=test_examples,
                    metadata={
                        "source": "conceptarc",
                        "concept_group": concept_group,
                        "has_test_solutions": all(ex.has_output for ex in test_examples),
                    },
                )
            )

    tasks.sort(key=lambda t: t.task_id)
    if max_tasks is not None:
        tasks = tasks[:max_tasks]
    return tasks


def arc_task_to_reasoning_task(task: ARCTask) -> ReasoningTask:
    if not task.has_test_solutions:
        raise ValueError(f"ARC task {task.task_id} has no test solutions; cannot run labeled evaluation")
    examples = {
        "train": [
            TaskExample(
                input_grid=example.input_grid,
                output_grid=example.output_grid,
                metadata=dict(example.metadata),
            )
            for example in task.train
            if example.output_grid is not None
        ],
        "test": [
            TaskExample(
                input_grid=example.input_grid,
                output_grid=example.output_grid,
                metadata=dict(example.metadata),
            )
            for example in task.test
            if example.output_grid is not None
        ],
    }
    return ReasoningTask(
        task_id=f"arc_{task.split}_{task.task_id}",
        family=f"arc_{task.split}",
        program=[],
        examples=examples,
        metadata={
            "source": "local_arc_agi",
            "arc_task_id": task.task_id,
            "arc_split": task.split,
            "latent_program_available": False,
            "evaluation_note": "ARC adapter evaluates output accuracy only; no latent-rule recovery is computed.",
        },
    )


def _pixel_accuracy(pred: np.ndarray, target: np.ndarray) -> float:
    if pred.shape != target.shape:
        return 0.0
    return float(np.mean(pred == target))


def evaluate_arc_prediction(task: ARCTask, prediction: PredictionResult) -> Dict[str, Any]:
    """Evaluate predictions on ARC test examples without latent-rule claims."""

    preds = list(prediction.predictions.get("test", []))
    exact_scores: List[float] = []
    pixel_scores: List[float] = []
    shape_matches: List[float] = []
    for pred, example in zip(preds, task.test):
        if example.output_grid is None:
            continue
        exact_scores.append(float(exact_match(pred, example.output_grid)))
        pixel_scores.append(_pixel_accuracy(pred, example.output_grid))
        shape_matches.append(float(pred.shape == example.output_grid.shape))

    candidate_diagnostics = prediction.candidate.diagnostics if prediction.candidate is not None else {}

    def diagnostic_number(key: str, default: float = 0.0) -> float:
        value = prediction.diagnostics.get(key, candidate_diagnostics.get(key, default))
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    return {
        "model_name": prediction.model_name,
        "arc_task_id": task.task_id,
        "arc_split": task.split,
        "labels_available": float(task.has_test_solutions),
        "n_train": len(task.train),
        "n_test": len(task.test),
        "n_test_evaluated": len(exact_scores),
        "test_pair_accuracy": float(np.mean(exact_scores)) if exact_scores else 0.0,
        "test_pixel_accuracy": float(np.mean(pixel_scores)) if pixel_scores else 0.0,
        "test_exact_task_accuracy": float(all(score == 1.0 for score in exact_scores)) if exact_scores else 0.0,
        "test_shape_accuracy": float(np.mean(shape_matches)) if shape_matches else 0.0,
        "runtime_seconds": diagnostic_number("runtime_seconds"),
        "candidate_program_count": diagnostic_number("candidate_program_count"),
        "candidates_scored": diagnostic_number("candidates_scored"),
        "candidates_falsified": diagnostic_number("candidates_falsified"),
        "oracle_probe_budget": diagnostic_number("oracle_probe_budget"),
        "oracle_probes_used": diagnostic_number("oracle_probes_used"),
        "passive_checks_used": diagnostic_number("passive_checks_used"),
        "predicted_program": None if prediction.candidate is None else program_signature(prediction.candidate.program),
        "latent_rule_recovery_computed": 0.0,
    }


def predictions_to_json_records(task: ARCTask, prediction: PredictionResult) -> Dict[str, Any]:
    return {
        "arc_task_id": task.task_id,
        "arc_split": task.split,
        "model_name": prediction.model_name,
        "predictions": {
            split: [grid_to_list(grid) for grid in grids]
            for split, grids in prediction.predictions.items()
        },
        "candidate": None if prediction.candidate is None else prediction.candidate.to_dict(),
        "diagnostics": dict(prediction.diagnostics),
    }


def summarize_arc_rows(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    by_model: Dict[str, List[Mapping[str, Any]]] = {}
    for row in rows:
        by_model.setdefault(str(row["model_name"]), []).append(row)

    metric_keys = [
        "test_pair_accuracy",
        "test_pixel_accuracy",
        "test_exact_task_accuracy",
        "test_shape_accuracy",
        "runtime_seconds",
        "candidate_program_count",
        "candidates_scored",
    ]
    summary: Dict[str, Any] = {
        "n_rows": len(rows),
        "n_tasks": len({row["arc_task_id"] for row in rows}),
        "by_model": {},
        "boundary": "ARC smoke metrics validate adapter execution only; no ARC performance claim is made.",
    }
    for model, group in sorted(by_model.items()):
        summary["by_model"][model] = {
            f"{key}_mean": float(np.mean([float(row.get(key, 0.0)) for row in group]))
            for key in metric_keys
        }
        summary["by_model"][model]["n"] = len(group)
    return summary
