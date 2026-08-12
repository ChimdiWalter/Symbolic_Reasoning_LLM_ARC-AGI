import numpy as np

from reasoning_project.operators import apply_program, candidate_programs
from reasoning_project.schemas import ProgramStep, program_signature


def test_reflection_and_count_bar():
    grid = np.zeros((4, 4), dtype=int)
    grid[0, 1] = 2
    reflected = apply_program(grid, [ProgramStep("reflect_vertical")])
    assert reflected[0, 2] == 2

    grid[2, 0] = 3
    counted = apply_program(grid, [ProgramStep("count_objects_emit_bar", {"color": 5})])
    assert counted[0].tolist().count(5) == 2


def test_candidate_programs_include_composition():
    programs = candidate_programs(max_depth=2, colors=[1, 2, 3, 4, 5, 6, 7, 8])
    signatures = {program_signature(program) for program in programs}
    assert "reflect_vertical -> recolor_largest_component(new_color=7)" in signatures


def test_arc_expanded_operators_cover_crop_expand_and_local_motion():
    grid = np.zeros((6, 6), dtype=int)
    grid[1, 1] = 7
    grid[2:4, 2:4] = 3

    cropped = apply_program(grid, [ProgramStep("crop_nonzero_bbox")])
    assert cropped.shape == (3, 3)
    assert cropped[0, 0] == 7

    largest_crop = apply_program(grid, [ProgramStep("crop_largest_component_bbox")])
    assert largest_crop.shape == (2, 2)
    assert np.all(largest_crop == 3)

    moved = apply_program(grid, [ProgramStep("translate_largest_component", {"dr": -1, "dc": 1})])
    assert moved[1:3, 3:5].tolist() == [[3, 3], [3, 3]]
    assert moved[1, 1] == 7

    expanded = apply_program(grid, [ProgramStep("expand_canvas", {"pad": 1, "anchor": "center"})])
    assert expanded.shape == (8, 8)
    assert np.array_equal(expanded[1:7, 1:7], grid)


def test_arc_expanded_candidate_programs_include_new_spatial_compositions():
    programs = candidate_programs(max_depth=2, colors=[1, 2, 3, 4], profile="arc_expanded")
    signatures = {program_signature(program) for program in programs}
    assert "translate_largest_component(dc=1,dr=0) -> crop_largest_component_bbox" in signatures
