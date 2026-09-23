"""Grid representation for ARC tasks."""
from __future__ import annotations
import numpy as np
from collections import Counter


class Grid:
    def __init__(self, data: np.ndarray):
        self._data = np.asarray(data, dtype=np.int32)

    @classmethod
    def from_list(cls, lst: list[list[int]]) -> Grid:
        return cls(np.array(lst, dtype=np.int32))

    def to_numpy(self) -> np.ndarray:
        return self._data.copy()

    def to_list(self) -> list[list[int]]:
        return self._data.tolist()

    @property
    def height(self) -> int:
        return self._data.shape[0]

    @property
    def width(self) -> int:
        return self._data.shape[1]

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    @property
    def colors_used(self) -> set[int]:
        return set(int(v) for v in np.unique(self._data))

    @property
    def background_color(self) -> int:
        counts = Counter(self._data.flatten().tolist())
        return counts.most_common(1)[0][0]

    def cell(self, r: int, c: int) -> int:
        return int(self._data[r, c])

    def subgrid(self, bbox: tuple[int, int, int, int]) -> Grid:
        r0, c0, r1, c1 = bbox
        return Grid(self._data[r0:r1, c0:c1].copy())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Grid):
            return NotImplemented
        return np.array_equal(self._data, other._data)

    def __repr__(self) -> str:
        return f"Grid({self.height}x{self.width})"
