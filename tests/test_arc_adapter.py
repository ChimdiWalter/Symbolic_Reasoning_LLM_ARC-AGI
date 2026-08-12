import json
from pathlib import Path

import pytest

from reasoning_project.arc_adapter import (
    arc_task_to_reasoning_task,
    evaluate_arc_prediction,
    load_arc_tasks,
)
from reasoning_project.arc_diagnostic import run_arc_diagnostic
from reasoning_project.arc_smoke import run_arc_smoke
from reasoning_project.schemas import PredictionResult


def _write_json(path: Path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _arc_fixture(root: Path) -> None:
    root.mkdir(exist_ok=True)
    challenges = {
        "task_b": {
            "train": [
                {"input": [[1, 0], [0, 0]], "output": [[1, 0], [0, 0]]},
            ],
            "test": [
                {"input": [[0, 1], [0, 0]]},
            ],
        },
        "task_a": {
            "train": [
                {"input": [[2, 0], [0, 0]], "output": [[2, 0], [0, 0]]},
                {"input": [[0, 0], [0, 2]], "output": [[0, 0], [0, 2]]},
            ],
            "test": [
                {"input": [[0, 2], [0, 0]]},
            ],
        },
    }
    solutions = {
        "task_a": [[[0, 2], [0, 0]]],
        "task_b": [[[0, 1], [0, 0]]],
    }
    _write_json(root / "arc-agi_training_challenges.json", challenges)
    _write_json(root / "arc-agi_training_solutions.json", solutions)


def test_load_arc_tasks_attaches_solutions_in_deterministic_order(tmp_path: Path):
    _arc_fixture(tmp_path)
    tasks = load_arc_tasks(tmp_path, split="training", max_tasks=1)
    assert [task.task_id for task in tasks] == ["task_a"]
    assert tasks[0].has_test_solutions
    assert tasks[0].metadata["has_test_solutions"] is True

    reasoning_task = arc_task_to_reasoning_task(tasks[0])
    assert reasoning_task.task_id == "arc_training_task_a"
    assert reasoning_task.metadata["latent_program_available"] is False
    assert len(reasoning_task.examples["train"]) == 2
    assert len(reasoning_task.examples["test"]) == 1


def test_arc_evaluation_omits_latent_rule_recovery(tmp_path: Path):
    _arc_fixture(tmp_path)
    task = load_arc_tasks(tmp_path, split="training", max_tasks=1)[0]
    prediction = PredictionResult(
        model_name="unit_oracle",
        task_id="arc_training_task_a",
        family="arc_training",
        predictions={"test": [task.test[0].output_grid.copy()]},
        candidate=None,
        diagnostics={"runtime_seconds": 0.01},
    )
    row = evaluate_arc_prediction(task, prediction)
    assert row["test_pair_accuracy"] == 1.0
    assert row["test_pixel_accuracy"] == 1.0
    assert row["latent_rule_recovery_computed"] == 0.0
    assert row["predicted_program"] is None


def test_arc_loader_rejects_non_rectangular_grid(tmp_path: Path):
    tmp_path.mkdir(exist_ok=True)
    _write_json(
        tmp_path / "arc-agi_training_challenges.json",
        {
            "bad": {
                "train": [{"input": [[1], [1, 2]], "output": [[1], [1]]}],
                "test": [{"input": [[1]]}],
            }
        },
    )
    _write_json(tmp_path / "arc-agi_training_solutions.json", {"bad": [[[1]]]})
    with pytest.raises(ValueError, match="width"):
        load_arc_tasks(tmp_path, split="training")


def test_run_arc_smoke_writes_required_artifacts(tmp_path: Path):
    arc_root = tmp_path / "arc"
    out_root = tmp_path / "outputs"
    _arc_fixture(arc_root)
    result = run_arc_smoke(
        {
            "name": "unit_arc_smoke",
            "run_name": "unit_arc_smoke",
            "seed": 5,
            "arc_root": str(arc_root),
            "split": "training",
            "max_tasks": 1,
            "models": ["direct_io_proxy"],
            "candidate_max_depth": 1,
        },
        output_dir=out_root,
        command="unit",
        config_path=None,
    )
    run_dir = Path(result["run_dir"])
    assert len(result["rows"]) == 1
    for name in [
        "config.json",
        "seed_list.json",
        "command_log.md",
        "arc_tasks.json",
        "metrics.json",
        "metrics.csv",
        "predictions.json",
        "summary.json",
        "summary.md",
        "manifest.json",
    ]:
        assert (run_dir / name).stat().st_size > 0
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert "no ARC performance claim" in summary["boundary"]


def test_run_arc_diagnostic_writes_comparison_and_failure_artifacts(tmp_path: Path):
    arc_root = tmp_path / "arc"
    out_root = tmp_path / "outputs"
    _arc_fixture(arc_root)
    result = run_arc_diagnostic(
        {
            "name": "unit_arc_diag",
            "run_name": "unit_arc_diag",
            "arc_root": str(arc_root),
            "split": "training",
            "require_solutions": True,
            "seeds": [1, 2],
            "max_tasks": 2,
            "max_tasks_per_bucket": 2,
            "models": ["direct_io_proxy", "transformation_library"],
            "candidate_max_depth": 1,
            "runtime_cap_seconds": 10.0,
        },
        output_dir=out_root,
        command="unit",
        config_path=None,
    )
    run_dir = Path(result["run_dir"])
    assert len(result["rows"]) == 8
    for name in [
        "config.json",
        "seed_list.json",
        "resume_instructions.json",
        "command_log.md",
        "task_profiles.json",
        "metrics.json",
        "metrics.csv",
        "seed_model_metrics.csv",
        "paired_contrasts.json",
        "paired_contrasts.md",
        "paired_seed_deltas.csv",
        "qualitative_failures.json",
        "qualitative_failures.md",
        "arc_evaluation_summary.md",
        "external_validity_summary.md",
        "manifest.json",
    ]:
        assert (run_dir / name).stat().st_size > 0
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert "no ARC benchmark" in summary["boundary"]
    assert summary["skipped_rows"] == 0
    contrasts = json.loads((run_dir / "paired_contrasts.json").read_text(encoding="utf-8"))
    assert "transformation_library_minus_direct_io_proxy" in contrasts
