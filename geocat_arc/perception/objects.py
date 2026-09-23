"""ARC object extraction and representation."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .grid import Grid
from .segmentation import ObjectMask, extract_connected_components


@dataclass
class ARCObject:
    id: int
    cells: frozenset[tuple[int, int]]
    color: int
    bounding_box: tuple[int, int, int, int]

    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def centroid(self) -> tuple[float, float]:
        rows = [c[0] for c in self.cells]
        cols = [c[1] for c in self.cells]
        return (sum(rows) / len(rows), sum(cols) / len(cols))

    @property
    def bbox_height(self) -> int:
        return self.bounding_box[2] - self.bounding_box[0]

    @property
    def bbox_width(self) -> int:
        return self.bounding_box[3] - self.bounding_box[1]

    @property
    def mask(self) -> np.ndarray:
        r0, c0, r1, c1 = self.bounding_box
        m = np.zeros((r1 - r0, c1 - c0), dtype=bool)
        for r, c in self.cells:
            m[r - r0, c - c0] = True
        return m

    @property
    def shape_signature(self) -> tuple:
        m = self.mask
        return tuple(map(tuple, m.astype(int).tolist()))

    @property
    def holes(self) -> list[tuple[int, int]]:
        r0, c0, r1, c1 = self.bounding_box
        m = self.mask
        hole_cells = []
        for r in range(m.shape[0]):
            for c in range(m.shape[1]):
                if not m[r, c]:
                    ar, ac = r + r0, c + c0
                    if self._is_interior(r, c, m):
                        hole_cells.append((ar, ac))
        return hole_cells

    def _is_interior(self, r: int, c: int, mask: np.ndarray) -> bool:
        h, w = mask.shape
        if r == 0 or r == h - 1 or c == 0 or c == w - 1:
            return False
        return (mask[r - 1, c] and mask[r + 1, c] and
                mask[r, c - 1] and mask[r, c + 1])

    @property
    def has_hole(self) -> bool:
        return len(self.holes) > 0

    @property
    def is_rectangle(self) -> bool:
        return self.size == self.bbox_height * self.bbox_width

    @property
    def is_line(self) -> bool:
        return self.bbox_height == 1 or self.bbox_width == 1

    def translated(self, dr: int, dc: int) -> ARCObject:
        new_cells = frozenset((r + dr, c + dc) for r, c in self.cells)
        r0, c0, r1, c1 = self.bounding_box
        return ARCObject(
            id=self.id,
            cells=new_cells,
            color=self.color,
            bounding_box=(r0 + dr, c0 + dc, r1 + dr, c1 + dc),
        )

    def recolored(self, new_color: int) -> ARCObject:
        return ARCObject(
            id=self.id,
            cells=self.cells,
            color=new_color,
            bounding_box=self.bounding_box,
        )


def extract_objects(grid: Grid, connectivity: int = 4) -> list[ARCObject]:
    masks = extract_connected_components(grid, connectivity=connectivity)
    objects = []
    for i, m in enumerate(masks):
        objects.append(ARCObject(
            id=i,
            cells=m.cells,
            color=m.color,
            bounding_box=m.bounding_box,
        ))
    return objects


def render_objects(objects: list[ARCObject], height: int, width: int, background: int = 0) -> Grid:
    data = np.full((height, width), background, dtype=np.int32)
    for obj in objects:
        for r, c in obj.cells:
            if 0 <= r < height and 0 <= c < width:
                data[r, c] = obj.color
    return Grid(data)
