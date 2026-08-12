from pathlib import Path

from reasoning_project.generators import generate_suite
from reasoning_project.h4_analysis import write_h4_bounded_compression_analysis
from reasoning_project.schemas import program_to_dict, program_signature
from reasoning_project.utils import write_json


def test_h4_bounded_compression_analysis_writes_artifacts(tmp_path: Path):
    suite = generate_suite(
        {
            "name": "unit_h4",
            "run_name": "unit_h4",
            "seed": 3,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 6,
            "ood_grid_size": 8,
            "object_count": 2,
            "colors": [1, 2],
            "candidate_max_depth": 1,
        }
    )
    task = suite.tasks[0]
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_json(run_dir / "config.json", suite.config)
    write_json(run_dir / "dataset.json", suite.to_dict())
    write_json(
        run_dir / "predictions.json",
        [
            {
                "model_name": "compression_selector",
                "task_id": task.task_id,
                "family": task.family,
                "predictions": {},
                "candidate": {
                    "program": program_to_dict(task.program),
                    "program_signature": program_signature(task.program),
                    "train_error": 0.0,
                    "score": 0.0,
                    "diagnostics": {},
                },
                "diagnostics": {},
            }
        ],
    )
    write_json(
        run_dir / "results.json",
        [
            {
                "model_name": "compression_selector",
                "task_id": task.task_id,
                "description_length_proxy": 1.0,
                "nuisance_robustness": 0.5,
                "intervention_stability": 0.25,
                "causal_factor_recovery": 1.0,
            }
        ],
    )
    result = write_h4_bounded_compression_analysis(run_dir)
    out = Path(result["output_dir"])
    assert (out / "per_task_exact_mdl.csv").stat().st_size > 0
    assert (out / "h4_summary.json").stat().st_size > 0
    assert (out / "h4_bounded_compression_summary.md").stat().st_size > 0
    model_summary = result["summary"]["by_model"]["compression_selector"]
    assert model_summary["selected_train_fit_rate"] == 1.0
    assert model_summary["exact_min_available_rate"] == 1.0
