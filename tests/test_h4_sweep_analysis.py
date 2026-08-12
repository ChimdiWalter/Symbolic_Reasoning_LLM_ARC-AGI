from pathlib import Path

from reasoning_project.experiment import run_experiment
from reasoning_project.h4_sweep_analysis import write_h4_sweep_analysis
from reasoning_project.utils import write_json


def test_h4_sweep_analysis_writes_artifacts(tmp_path: Path):
    base_config = {
        "name": "unit_h4_sweep",
        "run_name": "unit_h4_sweep",
        "families": ["reflection"],
        "tasks_per_family": 1,
        "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
        "grid_size": 6,
        "ood_grid_size": 8,
        "object_count": 2,
        "ood_object_count": 3,
        "colors": [1, 2],
        "candidate_max_depth": 1,
        "interactive_falsification": False,
        "models": ["transformation_library", "compression_selector"],
    }
    sweep_dir = tmp_path / "sweep"
    sweep_dir.mkdir()
    child_runs = []
    for seed in [11, 12]:
        config = dict(base_config)
        config["seed"] = seed
        result = run_experiment(config, output_dir=tmp_path, resume=False)
        child_runs.append({"seed": seed, "run_dir": result["run_dir"]})
    write_json(sweep_dir / "child_runs.json", child_runs)
    result = write_h4_sweep_analysis(sweep_dir)
    out = Path(result["output_dir"])
    assert (out / "per_task_exact_mdl.csv").stat().st_size > 0
    assert (out / "h4_sweep_summary.json").stat().st_size > 0
    assert (out / "h4_sweep_summary.md").stat().st_size > 0
    assert (out / "h4_seed_model_summary.csv").stat().st_size > 0
    assert result["summary"]["seed_count"] == 2
    assert "compression_selector" in result["summary"]["by_model"]
