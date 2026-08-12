import numpy as np

from reasoning_project.generators import generate_suite
from reasoning_project.operators import apply_program
from reasoning_project.schemas import ProgramStep


def test_generate_suite_has_ground_truth_programs():
    suite = generate_suite(
        {
            "name": "unit",
            "seed": 1,
            "families": ["reflection", "compositional"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
            "candidate_max_depth": 2,
        }
    )
    assert len(suite.tasks) == 2
    for task in suite.tasks:
        assert task.metadata["true_latent_rule"]
        assert task.metadata["designed_ambiguity_level"] in {"low", "medium", "high"}
        assert task.metadata["distractor_condition"] in {"simple", "distractor_heavy"}
        assert task.metadata["compositional_condition"] in {"compositional", "non_compositional"}
        for example in task.all_examples():
            expected = apply_program(example.input_grid, task.program)
            assert np.array_equal(expected, example.output_grid)
            assert example.metadata["family"] == task.family


def test_h2_noncommuting_probe_has_train_ambiguity_and_heldout_counterexample():
    suite = generate_suite(
        {
            "name": "unit_h2_probe",
            "seed": 12,
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
    assert task.metadata["designed_ambiguity_level"] == "high"
    assert task.metadata["distractor_condition"] == "distractor_heavy"
    assert task.metadata["compositional_condition"] == "compositional"
    count_only = [ProgramStep("count_objects_emit_bar", {"color": 1})]
    for example in task.examples["train"]:
        assert np.array_equal(apply_program(example.input_grid, count_only), example.output_grid)
    heldout = task.examples["test"][0]
    assert not np.array_equal(apply_program(heldout.input_grid, count_only), heldout.output_grid)
    assert np.array_equal(apply_program(heldout.input_grid, task.program), heldout.output_grid)


def test_expanded_h2_ambiguous_families_have_train_fit_false_simple_rules():
    families_and_wrong_rules = {
        "h2_symmetric_reflect_recolor_probe": [ProgramStep("recolor_largest_component", {"new_color": 7})],
        "h2_symmetric_rotate_recolor_probe": [ProgramStep("recolor_largest_component", {"new_color": 7})],
        "h2_reflect_select_border_probe": [
            ProgramStep("select_by_relational_predicate", {"predicate": "touching_border"})
        ],
        "h2_reflect_mark_contained_probe": [ProgramStep("mark_contained_objects", {"mark_color": 8})],
        "h2_copy_corner_probe": [ProgramStep("select_by_relational_predicate", {"predicate": "largest"})],
        "h2_largest_vs_border_probe": [
            ProgramStep("select_by_relational_predicate", {"predicate": "touching_border"})
        ],
    }
    suite = generate_suite(
        {
            "name": "unit_h2_expanded",
            "seed": 13,
            "families": list(families_and_wrong_rules),
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
    assert len(suite.tasks) == len(families_and_wrong_rules)
    for task in suite.tasks:
        wrong_rule = families_and_wrong_rules[task.family]
        assert task.metadata["designed_ambiguity_level"] == "high"
        assert task.metadata["compositional_condition"] == "compositional"
        for example in task.examples["train"]:
            assert np.array_equal(apply_program(example.input_grid, wrong_rule), example.output_grid)
        heldout = task.examples["test"][0]
        assert not np.array_equal(apply_program(heldout.input_grid, wrong_rule), heldout.output_grid)
        assert np.array_equal(apply_program(heldout.input_grid, task.program), heldout.output_grid)


def test_paper_breadth_families_generate_metadata_and_outputs():
    families = [
        "paper_composition_reflect_count",
        "paper_composition_adjacent_reflect",
        "paper_copy_corner_distractor",
        "paper_topology_distractor",
        "paper_nuisance_marker_recolor",
        "paper_causal_spurious_largest",
        "paper_containment_reflect_mark",
        "paper_symmetry_repair_challenge",
    ]
    suite = generate_suite(
        {
            "name": "unit_paper_breadth",
            "seed": 17,
            "families": families,
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "object_count": 3,
            "distractors": 2,
            "ood_distractors": 3,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
            "candidate_max_depth": 2,
        }
    )
    assert len(suite.tasks) == len(families)
    for task in suite.tasks:
        assert task.metadata["designed_ambiguity_level"] in {"medium", "high"}
        assert task.metadata["distractor_condition"] == "distractor_heavy"
        assert task.metadata["compositional_condition"] in {"compositional", "non_compositional"}
        for example in task.all_examples():
            assert np.array_equal(apply_program(example.input_grid, task.program), example.output_grid)


def test_arc_expanded_training_families_generate_valid_outputs():
    families = [
        "arc_crop_nonzero_bbox",
        "arc_crop_largest_component_bbox",
        "arc_translate_largest_component",
        "arc_snap_largest_component",
        "arc_expand_canvas",
    ]
    suite = generate_suite(
        {
            "name": "unit_arc_expanded",
            "seed": 31,
            "families": families,
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 8,
            "ood_grid_size": 10,
            "object_count": 3,
            "ood_object_count": 4,
            "distractors": 1,
            "ood_distractors": 2,
            "colors": [1, 2, 3, 4, 5, 6],
        }
    )
    assert len(suite.tasks) == len(families)
    for task in suite.tasks:
        assert task.metadata["designed_ambiguity_level"] == "medium"
        for example in task.all_examples():
            expected = apply_program(example.input_grid, task.program)
            assert np.array_equal(expected, example.output_grid)
    crop_task = next(task for task in suite.tasks if task.family == "arc_crop_nonzero_bbox")
    expand_task = next(task for task in suite.tasks if task.family == "arc_expand_canvas")
    assert crop_task.examples["train"][0].output_grid.shape[0] <= crop_task.examples["train"][0].input_grid.shape[0]
    assert expand_task.examples["train"][0].output_grid.shape[0] >= expand_task.examples["train"][0].input_grid.shape[0]
