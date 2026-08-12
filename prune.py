from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from components import Grid
from pipeline import build_scene_bundle, build_pair_bundle
from dsl import Program

@dataclass
class PruneStats:
    checked: int = 0
    kept: int = 0
    dropped: int = 0


def quick_palette(arr: np.ndarray) -> tuple:
    return tuple(sorted(int(x) for x in np.unique(arr)))


def early_prune_candidates(x0: Grid, y0: Grid, programs: List[Program]) -> Tuple[List[Program], PruneStats]:
    """Cheap prune: simulate once on x0 and compare invariants vs y0.
    - If palette is preserved in y0 but program changes it, drop.
    - If y0 palette ⊆ x0 palette and program introduces unseen colors, drop.
    - If program output shape != y0 shape, drop (shouldn't happen).
    This avoids expensive multi-pair verification for obvious mismatches.
    """
    stats = PruneStats()
    kept: List[Program] = []

    pal_x = quick_palette(x0.data)
    pal_y = quick_palette(y0.data)

    # decide palette policy
    palette_must_match = (pal_y == pal_x)
    palette_is_subset = set(pal_y).issubset(set(pal_x))

    B0 = build_scene_bundle(x0)
    for p in programs:
        stats.checked += 1
        try:
            yhat = p.run(x0, B0)
        except Exception:
            stats.dropped += 1
            continue
        if yhat.data.shape != y0.data.shape:
            stats.dropped += 1
            continue
        pal_hat = quick_palette(yhat.data)
        if palette_must_match and pal_hat != pal_y:
            stats.dropped += 1
            continue
        if palette_is_subset and not set(pal_hat).issubset(set(pal_x)):
            stats.dropped += 1
            continue
        kept.append(p)
        stats.kept += 1
    return kept, stats
