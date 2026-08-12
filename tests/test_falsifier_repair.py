from reasoning_project.falsifier import Falsifier
from reasoning_project.generators import HiddenRuleWorld, generate_suite
from reasoning_project.repair import evaluate_repair
from reasoning_project.schemas import ProgramStep


def test_falsifier_finds_oracle_counterexample_for_wrong_rule():
    suite = generate_suite(
        {
            "name": "unit",
            "seed": 4,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    task = suite.tasks[0]
    world = HiddenRuleWorld(task, seed=99)
    report = Falsifier(oracle_probes=2).attack([ProgramStep("identity")], task.examples["train"], world=world)
    assert report.oracle_counterexamples >= 1 or report.contradictions >= 1
    assert not report.accepted


def test_repair_report_is_well_formed():
    suite = generate_suite(
        {
            "name": "unit",
            "seed": 5,
            "families": ["translation"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 3, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    task = suite.tasks[0]
    report = evaluate_repair(task.program, task.examples["train"], seed=5, max_depth=2)
    assert report.repaired_signature
    assert report.repaired_error <= report.corrupted_error

