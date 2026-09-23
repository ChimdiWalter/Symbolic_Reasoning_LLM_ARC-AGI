"""Neural or heuristic ranking of DSL candidates from grid/task embeddings."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from ..compression import training_error
from ..operators import (
    ARC_EXPANDED_DSL_PROFILE,
    CORE_DSL_PROFILE,
    apply_program,
    base_candidate_steps,
    program_description_length,
)
from ..schemas import Program, ReasoningTask, TaskExample, program_signature
from .grid_encoder import HandcraftedGridEncoder, build_grid_encoder, torch_available

if torch_available():
    import torch
    from torch import Tensor, nn
else:  # pragma: no cover - exercised on no-torch systems
    torch = None
    Tensor = Any
    nn = object


def _operator_order() -> List[str]:
    names = set()
    for profile in [CORE_DSL_PROFILE, ARC_EXPANDED_DSL_PROFILE]:
        names.update(step.name for step in base_candidate_steps(list(range(1, 10)), profile=profile))
    return sorted(names)


OPERATOR_ORDER = _operator_order()
GEOMETRY_NAMES = {
    "reflect_horizontal",
    "reflect_vertical",
    "rotate_90",
    "rotate_180",
    "rotate_270",
    "translate",
    "translate_largest_component",
    "snap_largest_component",
}
CANVAS_NAMES = {"crop_nonzero_bbox", "crop_largest_component_bbox", "expand_canvas"}


def program_feature_vector(program: Program) -> np.ndarray:
    counts = np.zeros(len(OPERATOR_ORDER), dtype=float)
    translation = np.zeros(2, dtype=float)
    color_params: List[float] = []
    pad_params: List[float] = []
    predicate_to_index = {"touching_border": 0, "largest": 1, "contained": 2, "adjacent": 3, "has_hole": 4}
    predicate_flags = np.zeros(len(predicate_to_index), dtype=float)
    anchor_to_index = {"top_left": 0, "top_right": 1, "bottom_left": 2, "bottom_right": 3, "center": 4}
    anchor_flags = np.zeros(len(anchor_to_index), dtype=float)
    for step in program:
        counts[OPERATOR_ORDER.index(step.name)] += 1.0
        if step.name in {"translate", "translate_largest_component"}:
            translation[0] += float(step.params.get("dr", 0))
            translation[1] += float(step.params.get("dc", 0))
        for key in ["new_color", "target_color", "mark_color", "color"]:
            if key in step.params:
                color_params.append(float(step.params[key]) / 9.0)
        if "pad" in step.params:
            pad_params.append(float(step.params["pad"]))
        predicate = step.params.get("predicate")
        if predicate in predicate_to_index:
            predicate_flags[predicate_to_index[predicate]] = 1.0
        anchor = step.params.get("anchor")
        if anchor in anchor_to_index:
            anchor_flags[anchor_to_index[anchor]] = 1.0
    summary = np.asarray(
        [
            float(len(program)),
            float(sum(step.name in GEOMETRY_NAMES for step in program)),
            float(sum(step.name in CANVAS_NAMES for step in program)),
            float(program_description_length(program)) / 100.0,
            float(np.mean(color_params) if color_params else 0.0),
            float(np.max(color_params) if color_params else 0.0),
            translation[0] / 4.0,
            translation[1] / 4.0,
            float(np.mean(pad_params) if pad_params else 0.0) / 4.0,
        ],
        dtype=float,
    )
    return np.concatenate([counts, predicate_flags, anchor_flags, summary], axis=0)


def task_context_pairs(task: ReasoningTask) -> List[Tuple[np.ndarray, np.ndarray]]:
    return [
        (np.asarray(example.input_grid, dtype=int), np.asarray(example.output_grid, dtype=int))
        for example in task.examples.get("train", [])
    ]


def synthetic_candidate_target(task: ReasoningTask, program: Program) -> float:
    true_signature = program_signature(task.program)
    candidate_signature = program_signature(program)
    if candidate_signature == true_signature:
        return 1.0
    heldout_ok = True
    for split in ["val", "test", "ood"]:
        for example in task.examples.get(split, []):
            predicted = task.metadata.get("_apply_program_fn", lambda g, p: None)(example.input_grid, program)
            if predicted is None or not np.array_equal(predicted, example.output_grid):
                heldout_ok = False
                break
        if not heldout_ok:
            break
    if heldout_ok:
        return 0.75
    train_fit = float(training_error(program, task.examples.get("train", []))) == 0.0
    return 0.25 if train_fit else 0.0


def _pixel_accuracy(predicted: np.ndarray, target: np.ndarray) -> float:
    if predicted.shape != target.shape:
        return 0.0
    return float(np.mean(predicted == target))


def _support_iou(predicted: np.ndarray, target: np.ndarray) -> float:
    if predicted.shape != target.shape:
        return 0.0
    pred_support = np.asarray(predicted != 0, dtype=bool)
    target_support = np.asarray(target != 0, dtype=bool)
    union = float(np.sum(pred_support | target_support))
    if union == 0.0:
        return 1.0
    return float(np.sum(pred_support & target_support) / union)


def execution_feature_vector(task: ReasoningTask, program: Program) -> np.ndarray:
    cache = task.metadata.setdefault("_program_ranker_execution_cache", {})
    signature = program_signature(program)
    if signature in cache:
        return np.asarray(cache[signature], dtype=float)

    train_examples = list(task.examples.get("train", []))
    if not train_examples:
        features = np.zeros(9, dtype=float)
        cache[signature] = features.tolist()
        return features

    exact_scores: List[float] = []
    pixel_scores: List[float] = []
    shape_scores: List[float] = []
    color_jaccards: List[float] = []
    support_ious: List[float] = []
    non_background_ratio_errors: List[float] = []
    for example in train_examples:
        predicted = apply_program(example.input_grid, program)
        target = np.asarray(example.output_grid, dtype=int)
        predicted = np.asarray(predicted, dtype=int)
        exact_scores.append(float(np.array_equal(predicted, target)))
        pixel_scores.append(_pixel_accuracy(predicted, target))
        shape_scores.append(float(predicted.shape == target.shape))
        pred_colors = set(int(value) for value in np.unique(predicted) if int(value) != 0)
        target_colors = set(int(value) for value in np.unique(target) if int(value) != 0)
        union = pred_colors | target_colors
        color_jaccards.append(1.0 if not union else float(len(pred_colors & target_colors) / len(union)))
        support_ious.append(_support_iou(predicted, target))
        pred_non_background = float(np.mean(predicted != 0)) if predicted.size else 0.0
        target_non_background = float(np.mean(target != 0)) if target.size else 0.0
        non_background_ratio_errors.append(abs(pred_non_background - target_non_background))

    train_error_value = float(training_error(program, train_examples))
    features = np.asarray(
        [
            float(np.mean(exact_scores)),
            float(np.mean(pixel_scores)),
            float(np.min(pixel_scores)),
            float(np.mean(shape_scores)),
            float(np.mean(color_jaccards)),
            float(np.mean(support_ious)),
            float(1.0 - np.mean(non_background_ratio_errors)),
            float(train_error_value == 0.0),
            train_error_value / max(1.0, float(len(train_examples))),
        ],
        dtype=float,
    )
    cache[signature] = features.tolist()
    return features


def heuristic_rank_score(task: ReasoningTask, program: Program) -> float:
    execution = execution_feature_vector(task, program)
    return float(
        5.0 * execution[7]
        + 2.0 * execution[1]
        + 1.0 * execution[5]
        + 0.5 * execution[4]
        + 0.5 * execution[6]
        - 0.15 * program_description_length(program)
    )


@dataclass
class RankedProgram:
    program: Program
    score: float
    rank_source: str
    metadata: Dict[str, Any]


class HeuristicProgramRanker:
    name = "heuristic_program_ranker"

    def rank_task(self, task: ReasoningTask, programs: Sequence[Program]) -> List[RankedProgram]:
        ranked = []
        for program in programs:
            program_features = program_feature_vector(program)
            execution_features = execution_feature_vector(task, program)
            score = heuristic_rank_score(task, program)
            ranked.append(
                RankedProgram(
                    program=program,
                    score=score,
                    rank_source=self.name,
                    metadata={
                        "program_features": program_features.tolist(),
                        "execution_features": execution_features.tolist(),
                        "hybrid_components": {
                            "heuristic_score": float(score),
                            "train_exact": float(execution_features[7]),
                            "train_pixel": float(execution_features[1]),
                        },
                    },
                )
            )
        ranked.sort(key=lambda item: (-item.score, program_signature(item.program)))
        return ranked


class _RankerNetwork(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.layers(features).squeeze(-1)


class ProgramRanker:
    """Task-conditioned neural ranker with heuristic fallback."""

    name = "program_ranker"

    def __init__(
        self,
        encoder: Optional[Any] = None,
        hidden_dim: int = 128,
        learning_rate: float = 1e-3,
        device: Optional[str] = None,
        use_torch: bool = True,
    ) -> None:
        self.encoder = encoder or build_grid_encoder(use_torch=use_torch)
        self.hidden_dim = int(hidden_dim)
        self.learning_rate = float(learning_rate)
        self.device = device or ("cuda" if torch_available() and torch.cuda.is_available() else "cpu")
        if torch_available() and hasattr(self.encoder, "to"):
            self.encoder = self.encoder.to(self.device)
        self.heuristic = HeuristicProgramRanker()
        self.model: Optional[_RankerNetwork] = None
        self.input_dim: Optional[int] = None
        self.training_history: List[Dict[str, float]] = []

    def _task_embedding(self, task: ReasoningTask) -> np.ndarray:
        return np.asarray(self.encoder.encode_task_context(task_context_pairs(task)), dtype=float)

    def task_embedding(self, task: ReasoningTask) -> np.ndarray:
        return self._task_embedding(task)

    def candidate_embedding(
        self,
        task: ReasoningTask,
        program: Program,
        task_embedding: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        task_features = np.asarray(task_embedding if task_embedding is not None else self._task_embedding(task), dtype=float)
        return np.concatenate(
            [task_features, program_feature_vector(program), execution_feature_vector(task, program)],
            axis=0,
        )

    def _ensure_model(self, input_dim: int) -> None:
        if not torch_available():
            return
        if self.model is None or self.input_dim != input_dim:
            self.input_dim = int(input_dim)
            self.model = _RankerNetwork(input_dim=self.input_dim, hidden_dim=self.hidden_dim).to(self.device)

    def _align_feature_matrix(self, feature_matrix: np.ndarray) -> np.ndarray:
        features = np.asarray(feature_matrix, dtype=np.float32)
        if features.ndim == 1:
            features = features[None, :]
        target_dim = int(self.input_dim or features.shape[1])
        if features.shape[1] == target_dim:
            return features
        if features.shape[1] > target_dim:
            return features[:, :target_dim]
        padding = np.zeros((features.shape[0], target_dim - features.shape[1]), dtype=np.float32)
        return np.concatenate([features, padding], axis=1)

    def fit(
        self,
        feature_matrix: np.ndarray,
        targets: np.ndarray,
        epochs: int = 5,
        batch_size: int = 64,
    ) -> Dict[str, Any]:
        if not torch_available():
            return {"status": "skipped_no_torch", "epochs": 0, "final_loss": None}
        features = np.asarray(feature_matrix, dtype=np.float32)
        labels = np.asarray(targets, dtype=np.float32)
        self._ensure_model(features.shape[1])
        assert self.model is not None
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        loss_fn = nn.BCEWithLogitsLoss(reduction="none")
        dataset_size = features.shape[0]
        weights = np.ones(dataset_size, dtype=np.float32)
        weights[labels >= 0.75] = 4.0
        weights[(labels > 0.0) & (labels < 0.75)] = 2.0
        for epoch in range(int(epochs)):
            order = np.arange(dataset_size)
            np.random.shuffle(order)
            epoch_losses: List[float] = []
            for start in range(0, dataset_size, int(batch_size)):
                batch_indices = order[start : start + int(batch_size)]
                batch_x = torch.as_tensor(features[batch_indices], device=self.device)
                batch_y = torch.as_tensor(labels[batch_indices], device=self.device)
                batch_w = torch.as_tensor(weights[batch_indices], device=self.device)
                logits = self.model(batch_x)
                loss = (loss_fn(logits, batch_y) * batch_w).mean()
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_losses.append(float(loss.detach().cpu()))
            self.training_history.append({"epoch": epoch + 1, "loss": float(np.mean(epoch_losses))})
        return {
            "status": "trained",
            "epochs": int(epochs),
            "final_loss": self.training_history[-1]["loss"] if self.training_history else None,
        }

    def score_feature_matrix(self, feature_matrix: np.ndarray) -> np.ndarray:
        features = np.asarray(feature_matrix, dtype=np.float32)
        if not torch_available() or self.model is None:
            return -features[:, -1]
        features = self._align_feature_matrix(features)
        self.model.eval()
        with torch.no_grad():
            logits = self.model(torch.as_tensor(features, device=self.device))
            return torch.sigmoid(logits).detach().cpu().numpy()

    def rank_task(self, task: ReasoningTask, programs: Sequence[Program]) -> List[RankedProgram]:
        if not torch_available() or self.model is None:
            return self.heuristic.rank_task(task, programs)
        task_embedding = self._task_embedding(task)
        execution_features = [execution_feature_vector(task, program) for program in programs]
        features = np.asarray(
            [self.candidate_embedding(task, program, task_embedding=task_embedding) for program in programs],
            dtype=np.float32,
        )
        features = self._align_feature_matrix(features)
        neural_scores = self.score_feature_matrix(features)
        ranked = [
            RankedProgram(
                program=program,
                score=float(
                    score
                    + 2.5 * exec_features[7]
                    + 0.75 * exec_features[1]
                    + 0.25 * exec_features[5]
                    + 0.15 * exec_features[4]
                ),
                rank_source=self.name,
                metadata={
                    "program_features": program_feature_vector(program).tolist(),
                    "execution_features": exec_features.tolist(),
                    "hybrid_components": {
                        "neural_score": float(score),
                        "train_exact": float(exec_features[7]),
                        "train_pixel": float(exec_features[1]),
                        "support_iou": float(exec_features[5]),
                    },
                },
            )
            for program, score, exec_features in zip(programs, neural_scores, execution_features)
        ]
        ranked.sort(key=lambda item: (-item.score, program_signature(item.program)))
        return ranked

    def adapt_on_task(
        self,
        task: ReasoningTask,
        programs: Sequence[Program],
        labels: Sequence[float],
        steps: int = 3,
        learning_rate: float = 5e-4,
    ) -> Dict[str, Any]:
        if not torch_available() or self.model is None:
            return {"status": "skipped", "steps": 0, "final_loss": None}
        task_embedding = self._task_embedding(task)
        features = np.asarray(
            [self.candidate_embedding(task, program, task_embedding=task_embedding) for program in programs],
            dtype=np.float32,
        )
        features = self._align_feature_matrix(features)
        targets = np.asarray(labels, dtype=np.float32)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=float(learning_rate))
        loss_fn = nn.BCEWithLogitsLoss(reduction="none")
        weights = np.ones_like(targets, dtype=np.float32)
        weights[targets >= 0.5] = 3.0
        losses: List[float] = []
        self.model.train()
        batch_x = torch.as_tensor(features, device=self.device)
        batch_y = torch.as_tensor(targets, device=self.device)
        batch_w = torch.as_tensor(weights, device=self.device)
        for _ in range(int(steps)):
            logits = self.model(batch_x)
            loss = (loss_fn(logits, batch_y) * batch_w).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        return {"status": "adapted", "steps": int(steps), "final_loss": float(losses[-1]) if losses else None}

    def save(self, path: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if not torch_available() or self.model is None:
            raise RuntimeError("Cannot save a neural ranker before training or without torch")
        package = {
            "model_state": self.model.state_dict(),
            "input_dim": self.input_dim,
            "hidden_dim": self.hidden_dim,
            "learning_rate": self.learning_rate,
            "training_history": list(self.training_history),
            "extra": extra or {},
        }
        torch.save(package, path)

    def clone(self) -> "ProgramRanker":
        encoder = copy.deepcopy(self.encoder)
        cloned = ProgramRanker(
            encoder=encoder,
            hidden_dim=self.hidden_dim,
            learning_rate=self.learning_rate,
            device=self.device,
        )
        cloned.training_history = list(self.training_history)
        if torch_available() and self.model is not None and self.input_dim is not None:
            cloned._ensure_model(self.input_dim)
            assert cloned.model is not None
            cloned.model.load_state_dict(copy.deepcopy(self.model.state_dict()))
            cloned.training_history = list(self.training_history)
        return cloned

    @classmethod
    def load(cls, path: str, encoder: Optional[Any] = None, device: Optional[str] = None) -> "ProgramRanker":
        if not torch_available():
            raise RuntimeError("ProgramRanker loading requires torch")
        package = torch.load(path, map_location=device or "cpu")
        ranker = cls(
            encoder=encoder,
            hidden_dim=int(package.get("hidden_dim", 128)),
            learning_rate=float(package.get("learning_rate", 1e-3)),
            device=device,
        )
        input_dim = int(package["input_dim"])
        ranker._ensure_model(input_dim)
        assert ranker.model is not None
        ranker.model.load_state_dict(package["model_state"])
        ranker.training_history = list(package.get("training_history", []))
        return ranker
