import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from reasoning_project.generators import generate_suite
from reasoning_project.neural.grid_encoder import HandcraftedGridEncoder, torch_available
from reasoning_project.neural.program_ranker import ProgramRanker, execution_feature_vector, program_feature_vector
from reasoning_project.operators import candidate_programs
from reasoning_project.schemas import program_signature


def _reflection_task():
    suite = generate_suite(
        {
            "name": "ranker_unit",
            "seed": 5,
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
    return suite.tasks[0]


def test_program_feature_vector_is_finite():
    program = candidate_programs(max_depth=1, colors=[1, 2, 3])[0]
    features = program_feature_vector(program)
    assert features.ndim == 1
    assert features.size > 0
    assert np.isfinite(features).all()


def test_program_ranker_heuristic_fallback_runs_without_model():
    task = _reflection_task()
    programs = candidate_programs(max_depth=1, colors=[1, 2, 3, 4])
    ranker = ProgramRanker(encoder=HandcraftedGridEncoder(), use_torch=False)

    ranked = ranker.rank_task(task, programs[:8])

    assert ranked
    assert all(item.rank_source == "heuristic_program_ranker" for item in ranked)


def test_execution_feature_vector_tracks_train_fit_signal():
    task = _reflection_task()
    programs = candidate_programs(max_depth=1, colors=[1, 2, 3, 4])
    correct = next(program for program in programs if program_signature(program) == program_signature(task.program))
    incorrect = next(program for program in programs if program_signature(program) != program_signature(task.program))

    correct_features = execution_feature_vector(task, correct)
    incorrect_features = execution_feature_vector(task, incorrect)

    assert correct_features.shape == incorrect_features.shape
    assert correct_features[7] == 1.0
    assert correct_features[1] >= incorrect_features[1]


@pytest.mark.skipif(not torch_available(), reason="neural ranker save/load requires torch")
def test_program_ranker_save_and_load_round_trip(tmp_path):
    task = _reflection_task()
    programs = candidate_programs(max_depth=1, colors=[1, 2, 3, 4])
    encoder = HandcraftedGridEncoder()
    ranker = ProgramRanker(encoder=encoder, hidden_dim=32, learning_rate=1e-2, device="cpu")
    feature_matrix = np.asarray([ranker.candidate_embedding(task, program) for program in programs], dtype=np.float32)
    targets = np.asarray(
        [1.0 if program_signature(program) == program_signature(task.program) else 0.0 for program in programs],
        dtype=np.float32,
    )

    training = ranker.fit(feature_matrix, targets, epochs=8, batch_size=16)
    before_scores = ranker.score_feature_matrix(feature_matrix)
    checkpoint = tmp_path / "ranker.pt"
    ranker.save(str(checkpoint))
    loaded = ProgramRanker.load(str(checkpoint), encoder=HandcraftedGridEncoder(), device="cpu")
    after_scores = loaded.score_feature_matrix(feature_matrix)

    assert training["status"] == "trained"
    np.testing.assert_allclose(before_scores, after_scores, atol=1e-5, rtol=1e-5)


@pytest.mark.skipif(not torch_available(), reason="feature-dimension compatibility requires torch")
def test_loaded_ranker_tolerates_feature_dimension_growth(tmp_path):
    task = _reflection_task()
    programs = candidate_programs(max_depth=1, colors=[1, 2, 3, 4])
    encoder = HandcraftedGridEncoder()
    ranker = ProgramRanker(encoder=encoder, hidden_dim=32, learning_rate=1e-2, device="cpu")
    feature_matrix = np.asarray([ranker.candidate_embedding(task, program) for program in programs], dtype=np.float32)
    targets = np.asarray(
        [1.0 if program_signature(program) == program_signature(task.program) else 0.0 for program in programs],
        dtype=np.float32,
    )
    ranker.fit(feature_matrix, targets, epochs=4, batch_size=16)
    checkpoint = tmp_path / "ranker.pt"
    ranker.save(str(checkpoint))

    loaded = ProgramRanker.load(str(checkpoint), encoder=HandcraftedGridEncoder(), device="cpu")
    expanded_features = np.concatenate(
        [feature_matrix, np.ones((feature_matrix.shape[0], 7), dtype=np.float32)],
        axis=1,
    )
    scores = loaded.score_feature_matrix(expanded_features)

    assert scores.shape == (feature_matrix.shape[0],)


@pytest.mark.skipif(not torch_available(), reason="scripted resumability check requires torch")
def test_train_program_ranker_script_writes_resume_artifacts(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    config_path = tmp_path / "program_ranker_resume_test.json"
    output_root = tmp_path / "outputs"
    run_name = "program_ranker_resume_test"
    config = {
        "run_name": run_name,
        "seed": 3,
        "encoder_mode": "grid_encoder",
        "hidden_dim": 32,
        "learning_rate": 1e-3,
        "epochs": 2,
        "batch_size": 64,
        "candidate_max_depth": 1,
        "colors": [1, 2, 3, 4],
        "synthetic_train": {
            "name": "ranker_resume_train",
            "seed": 11,
            "families": ["reflection"],
            "tasks_per_family": 2,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 6,
            "ood_grid_size": 7,
            "object_count": 2,
            "ood_object_count": 3,
            "colors": [1, 2, 3, 4],
        },
        "synthetic_eval": {
            "name": "ranker_resume_eval",
            "seed": 13,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 6,
            "ood_grid_size": 7,
            "object_count": 2,
            "ood_object_count": 3,
            "colors": [1, 2, 3, 4],
        },
        "arc_eval_splits": ["evaluation"],
        "arc_eval_tasks": 1,
        "arc_eval_tasks_per_split": {"evaluation": 1},
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    base_cmd = [
        sys.executable,
        str(repo_root / "scripts" / "train_program_ranker.py"),
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
        run_dir / "dataset_summary.json",
        run_dir / "dataset_cache.npz",
        run_dir / "ranker_training_checkpoint.pt",
        run_dir / "ranker.pt",
        run_dir / "metrics.json",
        run_dir / "manifest.json",
    ]
    for path in expected_paths:
        assert path.exists(), path

    run_state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["status"] == "completed"
    assert run_state["phase"] == "completed"

    progress_lines = [
        json.loads(line)
        for line in (run_dir / "progress.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(line["event"] == "dataset_chunk" for line in progress_lines)
    assert any(line["event"] == "dataset_cache_loaded" for line in progress_lines)
    assert any(line["event"] == "resume" for line in progress_lines)
