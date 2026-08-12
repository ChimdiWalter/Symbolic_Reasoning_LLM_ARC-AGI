"""Dataset helpers for grid encoders, JEPA pretraining, and neural ranking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from ..arc_adapter import ARCTask
from ..generators import generate_suite
from ..schemas import ReasoningTask, TaskExample


@dataclass
class GridPairRecord:
    task_id: str
    family: str
    source: str
    split: str
    input_grid: np.ndarray
    output_grid: Optional[np.ndarray]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "family": self.family,
            "source": self.source,
            "split": self.split,
            "input_shape": list(np.asarray(self.input_grid).shape),
            "output_shape": None if self.output_grid is None else list(np.asarray(self.output_grid).shape),
            "metadata": dict(self.metadata),
        }


def pad_grids(grids: Sequence[np.ndarray], pad_value: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """Pad variable-sized integer grids to a dense batch plus a validity mask."""

    if not grids:
        raise ValueError("pad_grids requires at least one grid")
    arrays = [np.asarray(grid, dtype=int) for grid in grids]
    max_h = max(int(arr.shape[0]) for arr in arrays)
    max_w = max(int(arr.shape[1]) for arr in arrays)
    padded = np.full((len(arrays), max_h, max_w), int(pad_value), dtype=int)
    mask = np.zeros((len(arrays), max_h, max_w), dtype=bool)
    for index, arr in enumerate(arrays):
        h, w = arr.shape
        padded[index, :h, :w] = arr
        mask[index, :h, :w] = True
    return padded, mask


def reasoning_tasks_to_records(
    tasks: Sequence[ReasoningTask],
    splits: Sequence[str] = ("train", "val", "test", "ood"),
) -> List[GridPairRecord]:
    records: List[GridPairRecord] = []
    for task in tasks:
        for split in splits:
            for example in task.examples.get(split, []):
                records.append(
                    GridPairRecord(
                        task_id=task.task_id,
                        family=task.family,
                        source="synthetic",
                        split=split,
                        input_grid=np.asarray(example.input_grid, dtype=int),
                        output_grid=np.asarray(example.output_grid, dtype=int),
                        metadata={**dict(task.metadata), **dict(example.metadata)},
                    )
                )
    return records


def arc_tasks_to_records(
    tasks: Sequence[ARCTask],
    include_unlabeled_test: bool = False,
) -> List[GridPairRecord]:
    records: List[GridPairRecord] = []
    for task in tasks:
        for example in task.train:
            records.append(
                GridPairRecord(
                    task_id=task.task_id,
                    family=f"arc_{task.split}",
                    source="arc",
                    split="train",
                    input_grid=np.asarray(example.input_grid, dtype=int),
                    output_grid=np.asarray(example.output_grid, dtype=int) if example.output_grid is not None else None,
                    metadata=dict(example.metadata),
                )
            )
        for example in task.test:
            if example.output_grid is None and not include_unlabeled_test:
                continue
            records.append(
                GridPairRecord(
                    task_id=task.task_id,
                    family=f"arc_{task.split}",
                    source="arc",
                    split="test",
                    input_grid=np.asarray(example.input_grid, dtype=int),
                    output_grid=np.asarray(example.output_grid, dtype=int) if example.output_grid is not None else None,
                    metadata=dict(example.metadata),
                )
            )
    return records


def build_synthetic_records(config: Dict[str, Any]) -> List[GridPairRecord]:
    suite = generate_suite(config)
    return reasoning_tasks_to_records(suite.tasks)


def group_records_by_task(records: Iterable[GridPairRecord]) -> Dict[str, List[GridPairRecord]]:
    grouped: Dict[str, List[GridPairRecord]] = {}
    for record in records:
        grouped.setdefault(record.task_id, []).append(record)
    return grouped


def records_to_task_context(records: Sequence[GridPairRecord]) -> List[Tuple[np.ndarray, np.ndarray]]:
    context: List[Tuple[np.ndarray, np.ndarray]] = []
    for record in records:
        if record.output_grid is None:
            continue
        context.append((np.asarray(record.input_grid, dtype=int), np.asarray(record.output_grid, dtype=int)))
    return context


def task_examples_to_pairs(examples: Sequence[TaskExample]) -> List[Tuple[np.ndarray, np.ndarray]]:
    return [
        (np.asarray(example.input_grid, dtype=int), np.asarray(example.output_grid, dtype=int))
        for example in examples
    ]
