"""Validate ARC task data."""
from __future__ import annotations
from .arc_task import ARCTask, GridPair


class ValidationError(Exception):
    pass


def validate_grid(grid: list[list[int]], label: str = "grid") -> None:
    if not grid:
        raise ValidationError(f"{label}: empty grid")
    row_len = len(grid[0])
    for i, row in enumerate(grid):
        if len(row) != row_len:
            raise ValidationError(f"{label}: row {i} has length {len(row)}, expected {row_len}")
        for j, val in enumerate(row):
            if not isinstance(val, int) or val < 0 or val > 9:
                raise ValidationError(f"{label}[{i}][{j}] = {val}, expected int 0-9")


def validate_pair(pair: GridPair, label: str = "pair") -> None:
    validate_grid(pair.input, f"{label}.input")
    validate_grid(pair.output, f"{label}.output")


def validate_task(task: ARCTask) -> None:
    if not task.train:
        raise ValidationError(f"Task {task.task_id}: no training pairs")
    for i, pair in enumerate(task.train):
        validate_pair(pair, f"Task {task.task_id} train[{i}]")
    for i, pair in enumerate(task.test):
        validate_pair(pair, f"Task {task.task_id} test[{i}]")
