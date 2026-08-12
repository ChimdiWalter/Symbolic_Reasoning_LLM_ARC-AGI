from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Dict, Any
import numpy as np

# Import your extended implementation
import features_extended as F  # must export compute_scene_features(grid, scene), compute_pair_features(x, sx, y, sy)

# Re-export dataclasses if present, else minimal fallbacks
try:
    SceneFeatures = F.SceneFeatures  # type: ignore[attr-defined]
except Exception:
    @dataclass
    class SceneFeatures:
        H: int; W: int
        area: int
        palette: Tuple[int, ...]
        color_hist: Dict[int, int]
try:
    PairFeatures = F.PairFeatures  # type: ignore[attr-defined]
except Exception:
    @dataclass
    class PairFeatures:
        color_map: Dict[int, int]
        created_colors: Tuple[int, ...]
        removed_colors: Tuple[int, ...]
        total_pixel_delta: int
        per_color_delta: Dict[int, int]

# Local imports kept inside functions to avoid cycles
def compute_scene_features(*args, **kwargs) -> SceneFeatures:
    """
    Adapter supporting:
      - compute_scene_features(grid)
      - compute_scene_features(grid, scene)
    Always forwards to features_extended.compute_scene_features(grid, scene).
    """
    if len(args) == 1:
        grid = args[0]
        from components import extract_scene
        scene = extract_scene(grid, connectivity=4)
        return F.compute_scene_features(grid, scene)  # type: ignore[misc]
    elif len(args) == 2:
        grid, scene = args
        return F.compute_scene_features(grid, scene)  # type: ignore[misc]
    else:
        raise TypeError("compute_scene_features expects (grid) or (grid, scene)")

def compute_pair_features(*args, **kwargs) -> PairFeatures:
    """
    Adapter supporting:
      - compute_pair_features(x_grid, y_grid)
      - compute_pair_features(x_grid, x_scene, y_grid, y_scene)
    Always forwards to features_extended.compute_pair_features(x, x_scene, y, y_scene).
    """
    if len(args) == 2:
        x, y = args
        from components import extract_scene
        sx = extract_scene(x, connectivity=4)
        sy = extract_scene(y, connectivity=4)
        return F.compute_pair_features(x, sx, y, sy)  # type: ignore[misc]
    elif len(args) == 4:
        x, sx, y, sy = args
        return F.compute_pair_features(x, sx, y, sy)  # type: ignore[misc]
    else:
        raise TypeError("compute_pair_features expects (x, y) or (x, sx, y, sy)")
