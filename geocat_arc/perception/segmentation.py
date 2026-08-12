"""Connected component segmentation for ARC grids."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from .grid import Grid


@dataclass
class ObjectMask:
    cells: frozenset[tuple[int, int]]
    color: int
    bounding_box: tuple[int, int, int, int]  # (r0, c0, r1, c1) exclusive end

    @property
    def size(self) -> int:
        return len(self.cells)


def _neighbors(r: int, c: int, h: int, w: int, connectivity: int) -> list[tuple[int, int]]:
    result = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            result.append((nr, nc))
    if connectivity == 8:
        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                result.append((nr, nc))
    return result


def extract_connected_components(
    grid: Grid,
    connectivity: int = 4,
    ignore_background: bool = True,
) -> list[ObjectMask]:
    data = grid.to_numpy()
    h, w = data.shape
    bg = grid.background_color if ignore_background else -1
    visited = np.zeros((h, w), dtype=bool)
    components = []

    for r in range(h):
        for c in range(w):
            if visited[r, c]:
                continue
            color = int(data[r, c])
            if color == bg:
                visited[r, c] = True
                continue

            cells = set()
            queue = deque([(r, c)])
            visited[r, c] = True
            while queue:
                cr, cc = queue.popleft()
                cells.add((cr, cc))
                for nr, nc in _neighbors(cr, cc, h, w, connectivity):
                    if not visited[nr, nc] and int(data[nr, nc]) == color:
                        visited[nr, nc] = True
                        queue.append((nr, nc))

            rows = [p[0] for p in cells]
            cols = [p[1] for p in cells]
            bbox = (min(rows), min(cols), max(rows) + 1, max(cols) + 1)
            components.append(ObjectMask(
                cells=frozenset(cells),
                color=color,
                bounding_box=bbox,
            ))

    return components
