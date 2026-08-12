"""Basic ARC operators as typed morphisms."""
from __future__ import annotations
import numpy as np
from .morphism import Morphism
from .types import ArcType
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject, extract_objects, render_objects


class Segment(Morphism):
    name = "segment"
    input_types = (ArcType.GRID,)
    output_type = ArcType.OBJECT_SET
    cost = 1.0

    def __init__(self, connectivity: int = 4):
        self.connectivity = connectivity

    def apply(self, grid: Grid) -> list[ARCObject]:
        return extract_objects(grid, connectivity=self.connectivity)


class Select(Morphism):
    name = "select"
    input_types = (ArcType.OBJECT_SET, ArcType.PREDICATE)
    output_type = ArcType.OBJECT
    cost = 0.5

    def apply(self, objects: list[ARCObject], predicate) -> ARCObject:
        for obj in objects:
            if predicate(obj):
                return obj
        raise ValueError("No object satisfies predicate")


class Filter(Morphism):
    name = "filter"
    input_types = (ArcType.OBJECT_SET, ArcType.PREDICATE)
    output_type = ArcType.OBJECT_SET
    cost = 0.5

    def apply(self, objects: list[ARCObject], predicate) -> list[ARCObject]:
        return [obj for obj in objects if predicate(obj)]


class Copy(Morphism):
    name = "copy"
    input_types = (ArcType.OBJECT,)
    output_type = ArcType.OBJECT
    cost = 0.2

    def apply(self, obj: ARCObject) -> ARCObject:
        return ARCObject(
            id=obj.id + 1000,
            cells=frozenset(obj.cells),
            color=obj.color,
            bounding_box=obj.bounding_box,
        )


class Render(Morphism):
    name = "render"
    input_types = (ArcType.OBJECT_SET,)
    output_type = ArcType.GRID
    cost = 1.0

    def __init__(self, height: int = 0, width: int = 0, background: int = 0):
        self.height = height
        self.width = width
        self.background = background

    def apply(self, objects: list[ARCObject], _ctx: dict | None = None) -> Grid:
        h = self.height
        w = self.width
        bg = self.background
        if _ctx:
            h = _ctx.get("height", h)
            w = _ctx.get("width", w)
            bg = _ctx.get("background", bg)
        if h == 0 or w == 0:
            if objects:
                h = max(max(r for r, c in o.cells) + 1 for o in objects) if objects else 1
                w = max(max(c for r, c in o.cells) + 1 for o in objects) if objects else 1
            else:
                h, w = 1, 1
        return render_objects(objects, h, w, bg)


class RecolorAll(Morphism):
    name = "recolor_all"
    input_types = (ArcType.OBJECT_SET, ArcType.COLOR)
    output_type = ArcType.OBJECT_SET
    cost = 1.0

    def apply(self, objects: list[ARCObject], new_color: int) -> list[ARCObject]:
        return [o.recolored(new_color) for o in objects]


class TranslateAll(Morphism):
    name = "translate_all"
    input_types = (ArcType.OBJECT_SET, ArcType.VECTOR)
    output_type = ArcType.OBJECT_SET
    cost = 1.0

    def apply(self, objects: list[ARCObject], vector: tuple[int, int]) -> list[ARCObject]:
        dr, dc = vector
        return [o.translated(dr, dc) for o in objects]


class ReflectAll(Morphism):
    name = "reflect_all"
    input_types = (ArcType.OBJECT_SET, ArcType.AXIS)
    output_type = ArcType.OBJECT_SET
    cost = 1.5

    def apply(self, objects: list[ARCObject], axis: str) -> list[ARCObject]:
        from .operators_spatial import Reflect
        ref = Reflect()
        return [ref.apply(o, axis) for o in objects]


class RotateAll(Morphism):
    name = "rotate_all"
    input_types = (ArcType.OBJECT_SET, ArcType.ANGLE)
    output_type = ArcType.OBJECT_SET
    cost = 1.5

    def apply(self, objects: list[ARCObject], angle: int) -> list[ARCObject]:
        from .operators_spatial import Rotate90
        rot = Rotate90()
        return [rot.apply(o, angle) for o in objects]
