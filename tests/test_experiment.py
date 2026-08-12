from pathlib import Path

from reasoning_project.experiment import run_experiment


def test_tiny_experiment_writes_artifacts(tmp_path: Path):
    config = {
        "name": "tiny",
        "run_name": "tiny",
        "seed": 7,
        "families": ["reflection", "component_count"],
        "tasks_per_family": 1,
        "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
        "grid_size": 6,
        "ood_grid_size": 8,
        "object_count": 2,
        "ood_object_count": 3,
        "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        "candidate_max_depth": 1,
        "interactive_falsification": False,
        "models": ["direct_io_proxy", "transformation_library"],
    }
    result = run_experiment(config, output_dir=tmp_path, resume=False)
    run_dir = Path(result["run_dir"])
    assert (run_dir / "dataset.json").stat().st_size > 0
    assert (run_dir / "metrics.csv").stat().st_size > 0
    assert (run_dir / "summary.json").stat().st_size > 0
    assert len(result["rows"]) == 4

