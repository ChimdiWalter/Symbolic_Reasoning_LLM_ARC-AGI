"""Round-13 dihedral-frame wrapper tests."""
import json
import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.expressions import ColorExpr, PredExpr
from geocat_arc.object_reasoning.types import (ActionRule, DeltaType,
                                               FramedProgram, ObjectProgram,
                                               ObjectRule, OutputSpec,
                                               SegmentationVariant,
                                               SelectorRule, program_from_dict)


def _recolor_program(color):
    rule = ObjectRule(
        selector=SelectorRule(predicate=PredExpr(op="true", args=()),
                              literals=0),
        action=ActionRule(delta_type=DeltaType.RECOLOR,
                          params={"color": ColorExpr(op="const",
                                                     args=(color,))}))
    return ObjectProgram(segmentation_variant=SegmentationVariant("S1"),
                         rules=[rule],
                         default_action=ActionRule(delta_type=DeltaType.KEEP),
                         output_spec=OutputSpec(mode="same_as_input"))


def test_framed_round_trip():
    fp = FramedProgram(frame=(1, True), inner=_recolor_program(4))
    back = program_from_dict(json.loads(json.dumps(fp.to_dict())))
    assert isinstance(back, FramedProgram)
    assert back.frame == (1, True)
    assert back.to_dict() == fp.to_dict()
    assert back.worst_parameter_class == fp.inner.worst_parameter_class


def test_framed_render_equals_conjugated_inner():
    """T_inv(inner(T(x))) must equal applying the frame conjugation: for a
    frame-equivariant inner program (recolor-all), the framed render must
    equal the plain inner render."""
    grid = Grid.from_list([[0, 3, 0], [0, 0, 5], [7, 0, 0]])
    inner = _recolor_program(4)
    plain = render_program(inner, grid).to_list()
    for k in range(4):
        for flip in (False, True):
            framed = FramedProgram(frame=(k, flip), inner=inner)
            assert render_program(framed, grid).to_list() == plain, (k, flip)


def test_framed_render_non_square():
    """Frame transforms must handle non-square grids (rot90 changes shape)."""
    grid = Grid.from_list([[1, 0, 2, 0], [0, 3, 0, 0]])   # 2x4
    inner = _recolor_program(9)
    framed = FramedProgram(frame=(1, False), inner=inner)
    out = render_program(framed, grid)
    assert (out.height, out.width) == (2, 4)               # shape restored
    assert out.to_list() == render_program(inner, grid).to_list()
