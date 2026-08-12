from reasoning_project.evaluation import evaluate_prediction
from reasoning_project.generators import generate_suite
from reasoning_project.models import ModelConfig, build_model


def test_false_rule_selected_counts_without_falsifier_report():
    suite = generate_suite(
        {
            "name": "unit",
            "seed": 11,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    task = suite.tasks[0]
    model = build_model("proposer_only", ModelConfig(candidate_max_depth=1))
    prediction = model.predict_task(task)
    if prediction.candidate is not None and prediction.candidate.train_error == 0.0:
        prediction.candidate.program = []
    for split, examples in task.examples.items():
        if split in prediction.predictions:
            prediction.predictions[split] = [example.input_grid for example in examples]
    row = evaluate_prediction(task, prediction)
    assert row["false_rule_selected"] == 1.0
    assert row["false_rule_accepted"] == 1.0


def test_evaluation_emits_h2_stratification_fields():
    suite = generate_suite(
        {
            "name": "unit_h2_eval_fields",
            "seed": 14,
            "families": ["h2_noncommuting_composition_probe"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "object_count": 3,
            "distractors": 1,
            "ood_distractors": 2,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    task = suite.tasks[0]
    model = build_model("proposer_only", ModelConfig(candidate_max_depth=2))
    row = evaluate_prediction(task, model.predict_task(task))
    assert row["task_family"] == "h2_noncommuting_composition_probe"
    assert row["designed_ambiguity_level"] == "high"
    assert row["distractor_condition"] == "distractor_heavy"
    assert row["compositional_condition"] == "compositional"
    assert row["empirical_ambiguity_level"] in {"low", "medium", "high"}
    assert row["train_fit_candidate_count"] >= 1
    assert row["verification_budget_level"] == "none"
