"""Predictive error computation between predicted and target grids."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from collections import deque


@dataclass
class PredictionError:
    error_map: np.ndarray
    error_rate: float
    error_locations: list[tuple[int, int]]
    localized_regions: list[tuple[int, int, int, int]]  # bounding boxes of error clusters


def compute_prediction_error(
    predicted: list[list[int]],
    target: list[list[int]],
) -> PredictionError:
    pred = np.array(predicted, dtype=np.int32)
    tgt = np.array(target, dtype=np.int32)

    if pred.shape != tgt.shape:
        min_h = min(pred.shape[0], tgt.shape[0])
        min_w = min(pred.shape[1], tgt.shape[1])
        error_map = np.ones(tgt.shape, dtype=bool)
        error_map[:min_h, :min_w] = pred[:min_h, :min_w] != tgt[:min_h, :min_w]
    else:
        error_map = pred != tgt

    error_rate = float(np.sum(error_map)) / error_map.size if error_map.size > 0 else 0.0
    error_locations = list(zip(*np.where(error_map)))
    regions = localize_errors(error_map)

    return PredictionError(
        error_map=error_map,
        error_rate=error_rate,
        error_locations=[(int(r), int(c)) for r, c in error_locations],
        localized_regions=regions,
    )


def localize_errors(error_map: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = error_map.shape
    visited = np.zeros_like(error_map, dtype=bool)
    regions = []

    for r in range(h):
        for c in range(w):
            if error_map[r, c] and not visited[r, c]:
                min_r, max_r = r, r
                min_c, max_c = c, c
                queue = deque([(r, c)])
                visited[r, c] = True

                while queue:
                    cr, cc = queue.popleft()
                    min_r = min(min_r, cr)
                    max_r = max(max_r, cr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)

                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < h and 0 <= nc < w and error_map[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = True
                            queue.append((nr, nc))

                regions.append((min_r, min_c, max_r + 1, max_c + 1))

    return regions
