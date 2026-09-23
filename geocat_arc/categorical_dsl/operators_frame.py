"""Frame operators — cropping, enclosed region filling."""
from __future__ import annotations
from collections import deque
import numpy as np
from .morphism import Morphism
from .types import ArcType
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject


class CropToObject(Morphism):
    name = "crop_to_object"
    input_types = (ArcType.GRID, ArcType.OBJECT)
    output_type = ArcType.GRID
    cost = 0.5

    def apply(self, grid: Grid, obj: ARCObject) -> Grid:
        r0, c0, r1, c1 = obj.bounding_box
        return grid.subgrid((r0, c0, r1, c1))

    def applicable(self, *args) -> bool:
        if len(args) < 2:
            return False
        return isinstance(args[0], Grid) and isinstance(args[1], ARCObject)


class CropToFrame(Morphism):
    name = "crop_to_frame"
    input_types = (ArcType.GRID, ArcType.OBJECT)
    output_type = ArcType.GRID
    cost = 0.5

    def apply(self, grid: Grid, frame_obj: ARCObject) -> Grid:
        r0, c0, r1, c1 = frame_obj.bounding_box
        return grid.subgrid((r0, c0, r1, c1))

    def applicable(self, *args) -> bool:
        if len(args) < 2:
            return False
        return isinstance(args[0], Grid) and isinstance(args[1], ARCObject)


class ExtractInnerFrame(Morphism):
    name = "extract_inner_frame"
    input_types = (ArcType.GRID, ArcType.OBJECT)
    output_type = ArcType.GRID
    cost = 1.0

    def apply(self, grid: Grid, frame_obj: ARCObject) -> Grid:
        r0, c0, r1, c1 = frame_obj.bounding_box
        inner_r0 = r0 + 1
        inner_c0 = c0 + 1
        inner_r1 = r1 - 1
        inner_c1 = c1 - 1
        if inner_r1 <= inner_r0 or inner_c1 <= inner_c0:
            raise ValueError(f"Frame object too small to have interior: bbox={frame_obj.bounding_box}")
        return grid.subgrid((inner_r0, inner_c0, inner_r1, inner_c1))

    def applicable(self, *args) -> bool:
        if len(args) < 2 or not isinstance(args[1], ARCObject):
            return False
        r0, c0, r1, c1 = args[1].bounding_box
        return (r1 - r0) >= 3 and (c1 - c0) >= 3


class FillEnclosedRegion(Morphism):
    name = "fill_enclosed_region"
    input_types = (ArcType.GRID, ArcType.COLOR)
    output_type = ArcType.GRID
    cost = 1.5

    def apply(self, grid: Grid, fill_color: int) -> Grid:
        data = grid.to_numpy().copy()
        h, w = data.shape
        bg = grid.background_color

        reachable = np.zeros((h, w), dtype=bool)
        queue = deque()

        for r in range(h):
            for c in [0, w - 1]:
                if data[r, c] == bg and not reachable[r, c]:
                    reachable[r, c] = True
                    queue.append((r, c))
        for c in range(w):
            for r in [0, h - 1]:
                if data[r, c] == bg and not reachable[r, c]:
                    reachable[r, c] = True
                    queue.append((r, c))

        while queue:
            cr, cc = queue.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < h and 0 <= nc < w and not reachable[nr, nc] and data[nr, nc] == bg:
                    reachable[nr, nc] = True
                    queue.append((nr, nc))

        for r in range(h):
            for c in range(w):
                if data[r, c] == bg and not reachable[r, c]:
                    data[r, c] = fill_color

        return Grid(data)

    def applicable(self, *args) -> bool:
        return len(args) >= 2 and isinstance(args[0], Grid)
