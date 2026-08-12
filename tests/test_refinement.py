import json
import subprocess
import sys
from pathlib import Path

from reasoning_project.generators import generate_suite
from reasoning_project.refinement import RefinementConfig, RefinementEngine, evaluate_refinement_result


def test_refinement_engine_recovers_bounded_reflection_task():
    suite = generate_suite(
        {
            "name": "refine_unit",
            "seed": 9,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 3, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "object_count": 3,
            "ood_object_count": 4,
            "colors": [1, 2, 3, 4],
        }
    )
    task = suite.tasks[0]
    engine = RefinementEngine(
        config=RefinementConfig(
            candidate_max_depth=1,
            colors=[1, 2, 3, 4],
            initial_top_k=12,
            repair_top_k=4,
            return_top_k=2,
            neural_guidance=False,
        )
    )

    result = engine.run_task(task, method_name="unit_refinement")
    metrics = evaluate_refinement_result(task, result)

    assert result.top_candidates
    assert any(candidate.verified for candidate in result.top_candidates)
    assert metrics["candidate_program_count"] > 0
    assert metrics["pass_at_1"] == 1.0


def test_run_arc_refinement_script_writes_resume_artifacts(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    config_path = tmp_path / "arc_refinement_resume_test.json"
    output_root = tmp_path / "outputs"
    run_name = "arc_refinement_resume_test"
    config = {
        "run_name": run_name,
        "split": "evaluation",
        "max_tasks": 1,
        "candidate_max_depth": 1,
        "colors": [1, 2, 3, 4],
        "initial_top_k": 8,
        "repair_top_k": 2,
        "test_time_adaptation_steps": 1,
        "baseline_models": ["direct_io_proxy", "transformation_library"],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    base_cmd = [
        sys.executable,
        str(repo_root / "scripts" / "run_arc_refinement.py"),
        "--config",
        str(config_path),
        "--output-dir",
        str(output_root),
    ]
    subprocess.run(base_cmd, check=True, cwd=repo_root)
    subprocess.run([*base_cmd, "--resume"], check=True, cwd=repo_root)

    run_dir = output_root / run_name
    expected_paths = [
        run_dir / "resume_instructions.json",
        run_dir / "run_state.json",
        run_dir / "status.txt",
        run_dir / "progress.jsonl",
        run_dir / "completed_rows.json",
        run_dir / "rows.json",
        run_dir / "summary.json",
        run_dir / "manifest.json",
    ]
    for path in expected_paths:
        assert path.exists(), path

    run_state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["status"] == "completed"
    assert run_state["phase"] == "completed"

    completed_rows = json.loads((run_dir / "completed_rows.json").read_text(encoding="utf-8"))["completed_rows"]
    assert completed_rows

    progress_lines = [
        json.loads(line)
        for line in (run_dir / "progress.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(line["event"] == "row_complete" for line in progress_lines)
    assert any(line["event"] == "completed" for line in progress_lines)

    resume_instructions = json.loads((run_dir / "resume_instructions.json").read_text(encoding="utf-8"))
    assert "--resume" in resume_instructions["resume_command"]
