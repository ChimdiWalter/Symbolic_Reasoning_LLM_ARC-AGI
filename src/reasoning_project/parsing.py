"""Deterministic object and relation parsing for colored grids."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

import numpy as np


Coord = Tuple[int, int]


@dataclass(frozen=True)
class ObjectComponent:
    object_id: int
    color: int
    pixels: Tuple[Coord, ...]
    bbox: Tuple[int, int, int, int]
    size: int
    centroid: Tuple[float, float]
    touches_border: bool
    holes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "color": self.color,
            "pixels": [list(pixel) for pixel in self.pixels],
            "bbox": list(self.bbox),
            "size": self.size,
            "centroid": list(self.centroid),
            "touches_border": self.touches_border,
            "holes": self.holes,
        }


def _neighbors(r: int, c: int, h: int, w: int) -> Iterable[Coord]:
    if r > 0:
        yield r - 1, c
    if r + 1 < h:
        yield r + 1, c
    if c > 0:
        yield r, c - 1
    if c + 1 < w:
        yield r, c + 1


def _count_holes(mask: np.ndarray) -> int:
    """Count enclosed background regions inside an object's bounding mask."""

    if mask.size == 0:
        return 0
    padded = np.pad(mask.astype(bool), 1, constant_values=False)
    background = ~padded
    h, w = background.shape
    seen = np.zeros_like(background, dtype=bool)
    q: deque[Coord] = deque()
    for r in range(h):
        for c in (0, w - 1):
            if background[r, c] and not seen[r, c]:
                seen[r, c] = True
                q.append((r, c))
    for c in range(w):
        for r in (0, h - 1):
            if background[r, c] and not seen[r, c]:
                seen[r, c] = True
                q.append((r, c))
    while q:
        r, c = q.popleft()
        for nr, nc in _neighbors(r, c, h, w):
            if background[nr, nc] and not seen[nr, nc]:
                seen[nr, nc] = True
                q.append((nr, nc))
    holes = 0
    for r in range(h):
        for c in range(w):
            if background[r, c] and not seen[r, c]:
                holes += 1
                seen[r, c] = True
                q.append((r, c))
                while q:
                    rr, cc = q.popleft()
                    for nr, nc in _neighbors(rr, cc, h, w):
                        if background[nr, nc] and not seen[nr, nc]:
                            seen[nr, nc] = True
                            q.append((nr, nc))
    return holes


def parse_objects(grid: np.ndarray, background: int = 0) -> List[ObjectComponent]:
    """Parse same-color 4-connected non-background components."""

    arr = np.asarray(grid, dtype=int)
    h, w = arr.shape
    seen = np.zeros((h, w), dtype=bool)
    objects: List[ObjectComponent] = []
    object_id = 0
    for start_r in range(h):
        for start_c in range(w):
            color = int(arr[start_r, start_c])
            if color == background or seen[start_r, start_c]:
                continue
            q: deque[Coord] = deque([(start_r, start_c)])
            seen[start_r, start_c] = True
            pixels: List[Coord] = []
            while q:
                r, c = q.popleft()
                pixels.append((r, c))
                for nr, nc in _neighbors(r, c, h, w):
                    if seen[nr, nc] or int(arr[nr, nc]) != color:
                        continue
                    seen[nr, nc] = True
                    q.append((nr, nc))
            rows = [p[0] for p in pixels]
            cols = [p[1] for p in pixels]
            min_r, max_r = min(rows), max(rows)
            min_c, max_c = min(cols), max(cols)
            bbox = (min_r, min_c, max_r, max_c)
            local_mask = np.zeros((max_r - min_r + 1, max_c - min_c + 1), dtype=bool)
            for r, c in pixels:
                local_mask[r - min_r, c - min_c] = True
            touches_border = min_r == 0 or min_c == 0 or max_r == h - 1 or max_c == w - 1
            centroid = (float(np.mean(rows)), float(np.mean(cols)))
            objects.append(
                ObjectComponent(
                    object_id=object_id,
                    color=color,
                    pixels=tuple(sorted(pixels)),
                    bbox=bbox,
                    size=len(pixels),
                    centroid=centroid,
                    touches_border=touches_border,
                    holes=_count_holes(local_mask),
                )
            )
            object_id += 1
    return objects


def object_mask(grid: np.ndarray, obj: ObjectComponent) -> np.ndarray:
    mask = np.zeros_like(grid, dtype=bool)
    for r, c in obj.pixels:
        mask[r, c] = True
    return mask


def adjacency_edges(objects: Sequence[ObjectComponent]) -> List[Tuple[int, int]]:
    pixel_to_id: Dict[Coord, int] = {}
    max_r = 0
    max_c = 0
    for obj in objects:
        for pixel in obj.pixels:
            pixel_to_id[pixel] = obj.object_id
            max_r = max(max_r, pixel[0])
            max_c = max(max_c, pixel[1])
    edges: Set[Tuple[int, int]] = set()
    for (r, c), object_id in pixel_to_id.items():
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            other_id = pixel_to_id.get((nr, nc))
            if other_id is None or other_id == object_id:
                continue
            edges.add(tuple(sorted((object_id, other_id))))
    return sorted(edges)


def containment_edges(objects: Sequence[ObjectComponent]) -> List[Tuple[int, int]]:
    """Approximate containment by strict bounding-box inclusion."""

    edges: List[Tuple[int, int]] = []
    for outer in objects:
        omin_r, omin_c, omax_r, omax_c = outer.bbox
        for inner in objects:
            if outer.object_id == inner.object_id:
                continue
            imin_r, imin_c, imax_r, imax_c = inner.bbox
            if omin_r < imin_r and omin_c < imin_c and imax_r < omax_r and imax_c < omax_c:
                edges.append((outer.object_id, inner.object_id))
    return sorted(edges)


def symmetry_indicators(grid: np.ndarray) -> Dict[str, bool]:
    arr = np.asarray(grid, dtype=int)
    return {
        "horizontal": bool(np.array_equal(arr, np.flipud(arr))),
        "vertical": bool(np.array_equal(arr, np.fliplr(arr))),
        "rotational_180": bool(np.array_equal(arr, np.rot90(arr, 2))),
    }


def scene_graph(grid: np.ndarray, background: int = 0) -> Dict[str, Any]:
    objects = parse_objects(grid, background=background)
    return {
        "shape": list(np.asarray(grid).shape),
        "objects": [obj.to_dict() for obj in objects],
        "relations": {
            "adjacency": [list(edge) for edge in adjacency_edges(objects)],
            "containment": [list(edge) for edge in containment_edges(objects)],
            "symmetry": symmetry_indicators(grid),
        },
        "summary": {
            "object_count": len(objects),
            "colors": sorted({obj.color for obj in objects}),
            "component_sizes": sorted([obj.size for obj in objects], reverse=True),
            "hole_count": int(sum(obj.holes for obj in objects)),
        },
    }

