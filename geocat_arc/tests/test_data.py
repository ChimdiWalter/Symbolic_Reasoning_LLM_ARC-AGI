"""Tests for ARC data loading and validation."""
import pytest
from geocat_arc.data.arc_loader import load_tasks, load_task, list_task_ids
from geocat_arc.data.arc_task import ARCTask, GridPair
from geocat_arc.data.validate_arc import validate_task, validate_grid, ValidationError


class TestARCLoader:
    def test_list_task_ids(self):
        ids = list_task_ids(split="training")
        assert len(ids) >= 400

    def test_load_all_training(self):
        tasks = load_tasks(split="training")
        assert len(tasks) >= 400
        for t in tasks[:5]:
            assert isinstance(t, ARCTask)
            assert t.task_id
            assert len(t.train) >= 1

    def test_load_single_task(self):
        ids = list_task_ids(split="training")
        task = load_task(ids[0])
        assert task.task_id == ids[0]
        assert len(task.train) >= 1
        pair = task.train[0]
        assert len(pair.input) > 0
        assert len(pair.output) > 0

    def test_load_evaluation(self):
        tasks = load_tasks(split="evaluation")
        assert len(tasks) >= 100

    def test_grids_are_integer_lists(self):
        task = load_tasks(split="training")[0]
        pair = task.train[0]
        for row in pair.input:
            for val in row:
                assert isinstance(val, int)
                assert 0 <= val <= 9


class TestValidation:
    def test_valid_grid(self):
        validate_grid([[0, 1, 2], [3, 4, 5]])

    def test_invalid_color(self):
        with pytest.raises(ValidationError):
            validate_grid([[0, 10]])

    def test_jagged_grid(self):
        with pytest.raises(ValidationError):
            validate_grid([[0, 1], [2]])

    def test_empty_grid(self):
        with pytest.raises(ValidationError):
            validate_grid([])

    def test_validate_real_task(self):
        task = load_tasks(split="training")[0]
        validate_task(task)

    def test_validate_all_training(self):
        tasks = load_tasks(split="training")
        for task in tasks:
            validate_task(task)
