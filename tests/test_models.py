from reasoning_project.generators import HiddenRuleWorld, generate_suite
from reasoning_project.models import ModelConfig, build_model


def test_transformation_library_recovers_reflection():
    suite = generate_suite(
        {
            "name": "unit",
            "seed": 2,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 3, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    model = build_model("transformation_library", ModelConfig(candidate_max_depth=1))
    pred = model.predict_task(suite.tasks[0])
    assert pred.candidate is not None
    assert pred.candidate.train_error == 0.0
    assert pred.candidate.diagnostics["train_fit_candidate_count"] >= 1
    assert pred.candidate.diagnostics["empirical_ambiguity_level"] in {"low", "medium", "high"}
    assert pred.diagnostics["runtime_seconds"] >= 0.0


def test_integrated_model_handles_compositional_task():
    suite = generate_suite(
        {
            "name": "unit",
            "seed": 3,
            "families": ["compositional"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 3, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    model = build_model("integrated_scientist", ModelConfig(candidate_max_depth=2, oracle_probes=0))
    pred = model.predict_task(suite.tasks[0])
    assert pred.candidate is not None
    assert pred.candidate.train_error == 0.0
    assert "repair" in pred.candidate.diagnostics


def test_budget_matched_h2_models_log_probe_counts():
    suite = generate_suite(
        {
            "name": "unit_h2_budget",
            "seed": 13,
            "families": ["h2_noncommuting_composition_probe"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "object_count": 3,
            "distractors": 1,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    task = suite.tasks[0]
    world = HiddenRuleWorld(task, seed=13)
    config = ModelConfig(
        candidate_max_depth=2,
        oracle_probes=2,
        seed=13,
        falsifier_candidate_limit=5,
        fixed_falsifier_budget=True,
        budget_match_falsifier=True,
    )
    proposer = build_model("proposer_only", config)
    falsifier = build_model("proposer_falsifier", config)
    proposer_pred = proposer.predict_task(task, world=world)
    falsifier_pred = falsifier.predict_task(task, world=HiddenRuleWorld(task, seed=13))
    assert proposer_pred.diagnostics["oracle_probes_used"] == falsifier_pred.diagnostics["oracle_probes_used"]
    assert proposer_pred.diagnostics["candidates_falsified"] == falsifier_pred.diagnostics["candidates_falsified"]
    assert proposer_pred.diagnostics["runtime_seconds"] >= 0.0
    assert falsifier_pred.diagnostics["runtime_seconds"] >= 0.0


def test_learned_task_mlp_emits_predictions_and_diagnostics():
    suite = generate_suite(
        {
            "name": "unit_learned",
            "seed": 17,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 3, "val": 1, "test": 1, "ood": 1},
            "grid_size": 6,
            "ood_grid_size": 8,
            "object_count": 2,
            "ood_object_count": 3,
            "colors": [1, 2, 3, 4],
        }
    )
    model = build_model("learned_task_mlp", ModelConfig(seed=17, learned_hidden_dim=24, learned_max_iter=120))
    pred = model.predict_task(suite.tasks[0])
    assert pred.candidate is None
    assert pred.diagnostics["runtime_seconds"] >= 0.0
    assert pred.diagnostics["train_pixel_samples"] > 0
    assert pred.diagnostics["implemented_as"].startswith("task-conditioned MLP")
    assert pred.predictions["test"][0].size > 0


def test_transformation_library_arc_expanded_profile_recovers_crop_family():
    suite = generate_suite(
        {
            "name": "unit_arc_expanded_model",
            "seed": 41,
            "families": ["arc_crop_largest_component_bbox"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 3, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "object_count": 3,
            "ood_object_count": 4,
            "distractors": 1,
            "colors": [1, 2, 3, 4, 5, 6],
        }
    )
    model = build_model(
        "transformation_library",
        ModelConfig(candidate_max_depth=1, dsl_profile="arc_expanded", colors=[1, 2, 3, 4, 5, 6]),
    )
    pred = model.predict_task(suite.tasks[0])
    assert pred.candidate is not None
    assert pred.candidate.train_error == 0.0
