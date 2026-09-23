"""Pattern operators — tiling, line extension."""
from __future__ import annotations
import numpy as np
from .morphism import Morphism
from .types import ArcType
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject


class RepeatTilePattern(Morphism):
    name = "repeat_tile_pattern"
    input_types = (ArcType.GRID,)
    output_type = ArcType.GRID
    cost = 1.5

    def __init__(self, direction: str = "both", repeats: int = 2):
        self.direction = direction
        self.repeats = repeats

    def apply(self, grid: Grid) -> Grid:
        data = grid.to_numpy()
        if self.direction == "horizontal":
            tiled = np.tile(data, (1, self.repeats))
        elif self.direction == "vertical":
            tiled = np.tile(data, (self.repeats, 1))
        elif self.direction == "both":
            tiled = np.tile(data, (self.repeats, self.repeats))
        else:
            raise ValueError(f"Unknown direction: {self.direction}")
        return Grid(tiled)

    def applicable(self, *args) -> bool:
        return len(args) >= 1 and isinstance(args[0], Grid)


class ExtendLineOrPattern(Morphism):
    name = "extend_line"
    input_types = (ArcType.OBJECT_SET,)
    output_type = ArcType.OBJECT_SET
    cost = 1.5

    def __init__(self, grid_h: int = 30, grid_w: int = 30):
        self.grid_h = grid_h
        self.grid_w = grid_w

    def apply(self, objects: list[ARCObject]) -> list[ARCObject]:
        extended = []
        for obj in objects:
            if obj.is_line:
                new_cells = set(obj.cells)
                rows = [r for r, c in obj.cells]
                cols = [c for r, c in obj.cells]
                if obj.bbox_height == 1:
                    r = rows[0]
                    for c in range(self.grid_w):
                        new_cells.add((r, c))
                elif obj.bbox_width == 1:
                    c = cols[0]
                    for r in range(self.grid_h):
                        new_cells.add((r, c))
                new_rows = [r for r, c in new_cells]
                new_cols = [c for r, c in new_cells]
                bbox = (min(new_rows), min(new_cols),
                        max(new_rows) + 1, max(new_cols) + 1)
                extended.append(ARCObject(
                    id=obj.id, cells=frozenset(new_cells),
                    color=obj.color, bounding_box=bbox,
                ))
            else:
                extended.append(obj)
        return extended

    def applicable(self, *args) -> bool:
        return len(args) >= 1 and isinstance(args[0], list)
