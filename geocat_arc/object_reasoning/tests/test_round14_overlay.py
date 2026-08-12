"""Round-14 overlay composition tests."""
import json

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.expressions import ColorExpr, PredExpr
from geocat_arc.object_reasoning.types import (ActionRule, DeltaType,
                                               ObjectProgram, ObjectRule,
                                               OutputSpec, OverlayProgram,
                                               SegmentationVariant,
                                               SelectorRule,
                                               program_from_dict)


def _prog(delta, params=None, sel=None):
    rule = ObjectRule(
        selector=SelectorRule(predicate=sel or PredExpr(op="true", args=()),
                              literals=0),
        action=ActionRule(delta_type=delta, params=params or {}))
    return ObjectProgram(segmentation_variant=SegmentationVariant("S1"),
                         rules=[rule],
                         default_action=ActionRule(delta_type=DeltaType.KEEP),
                         output_spec=OutputSpec(mode="same_as_input"))


def test_overlay_render_patch_overwrites_base():
    """base = keep everything; patch = recolor all to 6.  The overlay must
    show the patch wherever the patch renders non-background."""
    grid = Grid.from_list([[0, 3, 0], [0, 0, 5], [0, 0, 0]])
    base = _prog(DeltaType.KEEP)
    patch = _prog(DeltaType.RECOLOR,
                  {"color": ColorExpr(op="const", args=(6,))})
    ov = OverlayProgram(base=base, patch=patch)
    out = render_program(ov, grid).to_list()
    assert out == [[0, 6, 0], [0, 0, 6], [0, 0, 0]]


def test_overlay_round_trip_and_accounting():
    base = _prog(DeltaType.KEEP)
    patch = _prog(DeltaType.RECOLOR,
                  {"color": ColorExpr(op="const", args=(4,))})
    ov = OverlayProgram(base=base, patch=patch)
    back = program_from_dict(json.loads(json.dumps(ov.to_dict())))
    assert isinstance(back, OverlayProgram)
    assert back.to_dict() == ov.to_dict()
    assert back.value_bound_count == ov.value_bound_count
    assert len(ov.rules) == 2
