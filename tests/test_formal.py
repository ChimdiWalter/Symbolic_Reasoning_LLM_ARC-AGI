import numpy as np

from reasoning_project.formal import (
    FiniteMorphism,
    aid_profile,
    audit_operator_topology,
    bounded_exact_dsl_minimum,
    check_finite_category_laws,
    enumerate_binary_grids,
    finite_group_morphisms_for_reflections,
    finite_path_witness,
    program_code_length_units,
)
from reasoning_project.operators import apply_program
from reasoning_project.generators import generate_suite
from reasoning_project.schemas import TaskExample, ProgramStep


def _domain():
    grids = []
    base = np.zeros((4, 4), dtype=int)
    base[1, 1] = 1
    grids.append(base)
    second = np.zeros((4, 4), dtype=int)
    second[0:2, 2:4] = 2
    grids.append(second)
    return grids


def test_finite_category_laws_hold_for_sample_morphisms():
    morphisms = [
        FiniteMorphism("identity", [ProgramStep("identity")]),
        FiniteMorphism("reflect_vertical", [ProgramStep("reflect_vertical")]),
        FiniteMorphism("reflect_horizontal", [ProgramStep("reflect_horizontal")]),
    ]
    report = check_finite_category_laws(morphisms, _domain())
    assert report.identity_law_holds
    assert report.associativity_holds
    assert report.composition_well_defined_holds
    assert report.checked_associativity_cases == 27


def test_exact_small_category_closure_for_reflection_group():
    report = check_finite_category_laws(finite_group_morphisms_for_reflections(), _domain(), require_closure=True)
    assert report.identity_law_holds
    assert report.associativity_holds
    assert report.closure_holds
    assert report.checked_closure_cases == 16
    assert "exact bounded small-category" in report.to_dict()["claim_scope"]


def test_finite_path_witness_distinguishes_equivalence_scope():
    left = [ProgramStep("reflect_vertical"), ProgramStep("recolor_largest_component", {"new_color": 7})]
    right = [ProgramStep("recolor_largest_component", {"new_color": 7}), ProgramStep("reflect_vertical")]
    witness = finite_path_witness(left, right, _domain())
    assert witness.relation == "finite_extensional_equivalence"
    assert "not a full identity type" in witness.claim_scope


def test_aid_profile_is_finite_proxy():
    suite = generate_suite(
        {
            "name": "unit",
            "seed": 13,
            "families": ["reflection"],
            "tasks_per_family": 1,
            "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
            "grid_size": 6,
            "ood_grid_size": 8,
            "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    task = suite.tasks[0]
    profile = aid_profile(task.program, task.examples["train"])
    assert profile.examples == 2
    assert profile.description_length_proxy > 0
    assert "not exact" in profile.claim_scope


def test_bounded_exact_dsl_minimum_finds_identity_program():
    examples = []
    for grid in _domain():
        examples.append(TaskExample(input_grid=grid, output_grid=grid.copy(), metadata={}))
    report = bounded_exact_dsl_minimum(examples, max_depth=1, colors=[1, 2])
    assert report.satisfying_count >= 1
    assert report.minimum_code_length_units == program_code_length_units([ProgramStep("identity")])
    assert report.minimum_program_signatures == ["identity"]
    assert "not exact Kolmogorov" in report.claim_scope


def test_bounded_exact_dsl_minimum_finds_reflection_program():
    program = [ProgramStep("reflect_vertical")]
    examples = [
        TaskExample(input_grid=grid, output_grid=apply_program(grid, program), metadata={})
        for grid in _domain()
    ]
    report = bounded_exact_dsl_minimum(examples, max_depth=1, colors=[1, 2])
    assert "reflect_vertical" in report.minimum_program_signatures
    assert report.minimum_code_length_units == program_code_length_units(program)


def test_operator_topology_audit_preserves_and_finds_counterexamples():
    domain = enumerate_binary_grids((3, 3))
    preserving = audit_operator_topology(ProgramStep("preserve_topology_change_color", {"new_color": 2}), domain)
    assert preserving.support_mask_preserved
    assert preserving.component_count_preserved
    assert preserving.hole_count_preserved
    assert preserving.classification == "topology_preserving_under_support_mask_definition"

    destructive = audit_operator_topology(ProgramStep("count_objects_emit_bar", {"color": 1}), domain)
    assert not destructive.support_mask_preserved
    assert "support_mask" in destructive.counterexamples
    assert destructive.classification == "not_topology_preserving_on_bounded_domain"
