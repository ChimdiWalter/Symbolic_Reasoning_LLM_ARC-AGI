"""Generate candidate programs from the typed DSL."""
from __future__ import annotations
from geocat_arc.categorical_dsl.program import Program
from geocat_arc.categorical_dsl.operators_basic import (
    Segment, Filter, Render, RecolorAll, TranslateAll, ReflectAll, RotateAll,
)
from geocat_arc.categorical_dsl.operators_color import Recolor
from geocat_arc.categorical_dsl.operators_frame import FillEnclosedRegion
from geocat_arc.categorical_dsl.operators_object_logic import ConditionalRecolor
from geocat_arc.categorical_dsl.operators_pattern import (
    ExtendLineOrPattern, RepeatTilePattern,
)
from geocat_arc.visual_logic_topos.predicates import (
    HasColor, IsRectangle, IsLine, HasHole, TouchesBorder,
)


class NotPredicate:
    arity = 1

    def __init__(self, pred):
        self.pred = pred

    def __call__(self, obj) -> bool:
        return not self.pred(obj)

    def __repr__(self):
        return f"Not({self.pred!r})"


def generate_candidates(
    grid_h: int,
    grid_w: int,
    background: int = 0,
    max_candidates: int = 100,
    max_depth: int = 2,
) -> list[Program]:
    candidates = []

    def _add(p: Program):
        if len(candidates) < max_candidates:
            candidates.append(p)

    seg4 = Segment(connectivity=4)
    seg8 = Segment(connectivity=8)
    render = Render()

    unary_preds = [IsRectangle(), IsLine(), HasHole(), TouchesBorder(grid_h, grid_w)]
    color_preds = [HasColor(c) for c in range(10)]

    for seg in [seg4, seg8]:
        # Depth-1: identity (segment -> render)
        p = Program()
        p.add_step(seg)
        p.add_step(render)
        _add(p)

        # Depth-2: filter by color -> render
        for color in range(10):
            p = Program()
            p.add_step(seg)
            p.add_step(Filter(), HasColor(color))
            p.add_step(render)
            _add(p)

        # Depth-2: filter by NOT color -> render
        for color in range(10):
            p = Program()
            p.add_step(seg)
            p.add_step(Filter(), NotPredicate(HasColor(color)))
            p.add_step(render)
            _add(p)

        # Depth-2: filter by unary predicate -> render
        for pred in unary_preds:
            p = Program()
            p.add_step(seg)
            p.add_step(Filter(), pred)
            p.add_step(render)
            _add(p)

        # Depth-2: filter by NOT unary predicate -> render
        for pred in unary_preds:
            p = Program()
            p.add_step(seg)
            p.add_step(Filter(), NotPredicate(pred))
            p.add_step(render)
            _add(p)

        # Depth-2: recolor all -> render
        for target_color in range(10):
            p = Program()
            p.add_step(seg)
            p.add_step(RecolorAll(), target_color)
            p.add_step(render)
            _add(p)

        # Depth-2: reflect all -> render
        for axis in ["horizontal", "vertical"]:
            p = Program()
            p.add_step(seg)
            p.add_step(ReflectAll(), axis)
            p.add_step(render)
            _add(p)

        # Depth-2: rotate all -> render
        for angle in [90, 180, 270]:
            p = Program()
            p.add_step(seg)
            p.add_step(RotateAll(), angle)
            p.add_step(render)
            _add(p)

        # Depth-2: translate all -> render
        for dr in [-1, 0, 1, -2, 2]:
            for dc in [-1, 0, 1, -2, 2]:
                if dr == 0 and dc == 0:
                    continue
                p = Program()
                p.add_step(seg)
                p.add_step(TranslateAll(), (dr, dc))
                p.add_step(render)
                _add(p)

        # Depth-2: extend lines -> render
        p = Program()
        p.add_step(seg)
        p.add_step(ExtendLineOrPattern(grid_h, grid_w))
        p.add_step(render)
        _add(p)

    # Grid-level operators (no segmentation needed)
    # Fill enclosed regions with each color
    for fill_color in range(10):
        p = Program()
        p.add_step(FillEnclosedRegion(), fill_color)
        _add(p)

    # Tile patterns
    for direction in ["horizontal", "vertical", "both"]:
        for repeats in [2, 3]:
            p = Program()
            p.add_step(RepeatTilePattern(direction=direction, repeats=repeats))
            _add(p)

    # Reflect the whole grid
    for axis in ["horizontal", "vertical"]:
        p = Program()
        p.add_step(seg4)
        p.add_step(ReflectAll(), axis)
        p.add_step(render)
        _add(p)

    if max_depth >= 3:
        for seg in [seg4, seg8]:
            # Depth-3: filter by color -> recolor -> render
            for filter_color in range(10):
                for target_color in range(10):
                    if filter_color == target_color:
                        continue
                    p = Program()
                    p.add_step(seg)
                    p.add_step(Filter(), HasColor(filter_color))
                    p.add_step(RecolorAll(), target_color)
                    p.add_step(render)
                    _add(p)

            # Depth-3: filter by color -> translate -> render
            for color in range(10):
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, -2), (0, 2)]:
                    p = Program()
                    p.add_step(seg)
                    p.add_step(Filter(), HasColor(color))
                    p.add_step(TranslateAll(), (dr, dc))
                    p.add_step(render)
                    _add(p)

            # Depth-3: filter by color -> reflect -> render
            for color in range(10):
                for axis in ["horizontal", "vertical"]:
                    p = Program()
                    p.add_step(seg)
                    p.add_step(Filter(), HasColor(color))
                    p.add_step(ReflectAll(), axis)
                    p.add_step(render)
                    _add(p)

            # Depth-3: conditional recolor (recolor objects matching predicate)
            for pred in color_preds:
                for target_color in range(10):
                    if isinstance(pred, HasColor) and pred.color == target_color:
                        continue
                    p = Program()
                    p.add_step(seg)
                    p.add_step(ConditionalRecolor(), pred, target_color)
                    p.add_step(render)
                    _add(p)

            # Depth-3: conditional recolor by unary pred
            for pred in unary_preds:
                for target_color in range(10):
                    p = Program()
                    p.add_step(seg)
                    p.add_step(ConditionalRecolor(), pred, target_color)
                    p.add_step(render)
                    _add(p)

            # Depth-3: filter by NOT color -> recolor -> render
            for filter_color in range(10):
                for target_color in range(10):
                    if filter_color == target_color:
                        continue
                    p = Program()
                    p.add_step(seg)
                    p.add_step(Filter(), NotPredicate(HasColor(filter_color)))
                    p.add_step(RecolorAll(), target_color)
                    p.add_step(render)
                    _add(p)

            # Depth-3: filter by unary pred -> recolor -> render
            for pred in unary_preds:
                for target_color in range(10):
                    p = Program()
                    p.add_step(seg)
                    p.add_step(Filter(), pred)
                    p.add_step(RecolorAll(), target_color)
                    p.add_step(render)
                    _add(p)

            # Depth-3: extend lines -> filter -> render
            for pred in unary_preds:
                p = Program()
                p.add_step(seg)
                p.add_step(ExtendLineOrPattern(grid_h, grid_w))
                p.add_step(Filter(), pred)
                p.add_step(render)
                _add(p)

        # Depth-3: fill enclosed region then segment -> render
        for fill_color in range(10):
            for filter_color in range(10):
                if fill_color == filter_color:
                    continue
                p = Program()
                p.add_step(FillEnclosedRegion(), fill_color)
                p.add_step(seg4)
                p.add_step(Filter(), HasColor(filter_color))
                p.add_step(render)
                _add(p)

    return candidates[:max_candidates]


def get_generation_stats(
    grid_h: int, grid_w: int, background: int = 0,
    max_candidates: int = 10000, max_depth: int = 3,
) -> dict:
    progs = generate_candidates(grid_h, grid_w, background, max_candidates, max_depth)
    return {"total_generated": len(progs)}
