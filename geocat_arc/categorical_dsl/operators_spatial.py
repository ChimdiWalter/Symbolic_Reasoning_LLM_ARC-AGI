"""Spatial ARC operators as typed morphisms."""
from __future__ import annotations
import numpy as np
from .morphism import Morphism
from .types import ArcType
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject


class Translate(Morphism):
    name = "translate"
    input_types = (ArcType.OBJECT, ArcType.VECTOR)
    output_type = ArcType.OBJECT
    cost = 1.0

    def apply(self, obj: ARCObject, vector: tuple[int, int]) -> ARCObject:
        dr, dc = vector
        return obj.translated(dr, dc)


class Rotate90(Morphism):
    name = "rotate90"
    input_types = (ArcType.OBJECT, ArcType.ANGLE)
    output_type = ArcType.OBJECT
    cost = 1.5

    def apply(self, obj: ARCObject, angle: int) -> ARCObject:
        rotations = (angle % 360) // 90
        mask = obj.mask
        for _ in range(rotations):
            mask = np.rot90(mask, k=-1)
        r0, c0 = obj.bounding_box[0], obj.bounding_box[1]
        new_cells = set()
        for r in range(mask.shape[0]):
            for c in range(mask.shape[1]):
                if mask[r, c]:
                    new_cells.add((r0 + r, c0 + c))
        new_h, new_w = mask.shape
        return ARCObject(
            id=obj.id,
            cells=frozenset(new_cells),
            color=obj.color,
            bounding_box=(r0, c0, r0 + new_h, c0 + new_w),
        )


class Reflect(Morphism):
    name = "reflect"
    input_types = (ArcType.OBJECT, ArcType.AXIS)
    output_type = ArcType.OBJECT
    cost = 1.5

    def apply(self, obj: ARCObject, axis: str) -> ARCObject:
        mask = obj.mask
        if axis == "horizontal":
            mask = np.flipud(mask)
        elif axis == "vertical":
            mask = np.fliplr(mask)
        else:
            raise ValueError(f"Unknown axis: {axis}")
        r0, c0 = obj.bounding_box[0], obj.bounding_box[1]
        new_cells = set()
        for r in range(mask.shape[0]):
            for c in range(mask.shape[1]):
                if mask[r, c]:
                    new_cells.add((r0 + r, c0 + c))
        return ARCObject(
            id=obj.id,
            cells=frozenset(new_cells),
            color=obj.color,
            bounding_box=obj.bounding_box,
        )


class Crop(Morphism):
    name = "crop"
    input_types = (ArcType.GRID, ArcType.REGION)
    output_type = ArcType.GRID
    cost = 0.5

    def apply(self, grid: Grid, region: tuple[int, int, int, int]) -> Grid:
        return grid.subgrid(region)


class Place(Morphism):
    name = "place"
    input_types = (ArcType.OBJECT, ArcType.REGION)
    output_type = ArcType.GRID_PATCH
    cost = 1.0

    def apply(self, obj: ARCObject, region: tuple[int, int, int, int]) -> dict:
        r0, c0, r1, c1 = region
        dr = r0 - obj.bounding_box[0]
        dc = c0 - obj.bounding_box[1]
        new_obj = obj.translated(dr, dc)
        return {"object": new_obj, "region": region}
