"""Round-12 FILL_LINE: draw axis-aligned lines through objects.

The 381-task line-fill pattern family: single-cell or small markers in the
input, output = lines drawn through them.  The simplest forcing case:
objects on a grid, output = vertical lines through each object's column,
colored by the object's color.
"""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.expressions import (ColorExpr, DirectionExpr,
                                                     PredExpr, RefExpr)
from geocat_arc.object_reasoning.types import (ActionRule, DeltaType,
                                               ObjectProgram, ObjectRule,
                                               OutputSpec,
                                               SegmentationVariant,
                                               SelectorRule)


def _fill_line_program(axis="vertical"):
    rule = ObjectRule(
        selector=SelectorRule(predicate=PredExpr(op="true", args=()),
                              literals=0),
        action=ActionRule(
            delta_type=DeltaType.FILL_LINE,
            params={
                "axis": DirectionExpr(op="const", args=(axis,)),
                "color": ColorExpr(op="color_of",
                                   args=(RefExpr(op="self"),)),
            }))
    return ObjectProgram(
        segmentation_variant=SegmentationVariant("S1"),
        rules=[rule],
        default_action=ActionRule(delta_type=DeltaType.KEEP),
        output_spec=OutputSpec(mode="same_as_input"))


def test_fill_line_vertical_renders():
    """A single colored pixel at (2, 3) on a 6x6 grid; FILL_LINE vertical
    should draw a vertical line of the same color through column 3."""
    grid = Grid.from_list([
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 5, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
    ])
    expected = [
        [0, 0, 0, 5, 0, 0],
        [0, 0, 0, 5, 0, 0],
        [0, 0, 0, 5, 0, 0],
        [0, 0, 0, 5, 0, 0],
        [0, 0, 0, 5, 0, 0],
        [0, 0, 0, 5, 0, 0],
    ]
    prog = _fill_line_program("vertical")
    out = render_program(prog, grid)
    assert out.to_list() == expected


def test_fill_line_both_renders_cross():
    """Two pixels -> two crosses (each axis through the object centroid)."""
    grid = Grid.from_list([
        [0, 0, 0, 0, 0],
        [0, 3, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 7, 0],
        [0, 0, 0, 0, 0],
    ])
    prog = _fill_line_program("both")
    out = render_program(prog, grid)
    data = out.to_list()
    assert data[1][0] == 3 and data[1][4] == 3  # horizontal through (1,1)
    assert data[0][1] == 3 and data[4][1] == 3  # vertical through (1,1)
    assert data[3][0] == 7 and data[3][4] == 7  # horizontal through (3,3)
    assert data[0][3] == 7 and data[4][3] == 7  # vertical through (3,3)
    assert data[1][1] == 3  # object itself preserved
    assert data[3][3] == 7
