from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Tuple
import numpy as np

@dataclass
class Topology:
    beta0: int      # number of connected foreground components
    beta1: int      # number of holes (cycles)
    euler: int      # Euler characteristic = beta0 - beta1

def _label_components(mask: np.ndarray, connectivity: int = 4) -> int:
    """Return number of connected components in a binary mask (True = foreground)."""
    H, W = mask.shape
    seen = np.zeros((H, W), dtype=bool)
    comps = 0
    nbrs4 = ((1,0),(-1,0),(0,1),(0,-1))
    nbrs8 = nbrs4 + ((1,1),(1,-1),(-1,1),(-1,-1))
    N = nbrs4 if connectivity == 4 else nbrs8
    for r in range(H):
        for c in range(W):
            if not mask[r, c] or seen[r, c]:
                continue
            comps += 1
            stack = [(r, c)]
            seen[r, c] = True
            while stack:
                rr, cc = stack.pop()
                for dr, dc in N:
                    nr, nc = rr + dr, cc + dc
                    if 0 <= nr < H and 0 <= nc < W and mask[nr, nc] and not seen[nr, nc]:
                        seen[nr, nc] = True
                        stack.append((nr, nc))
    return comps

def _count_background_components(mask: np.ndarray, connectivity: int = 4) -> int:
    """Count connected components of the BACKGROUND inside a padded frame.
    The number of holes is (#background components - 1 for the exterior), lower-bounded at 0.
    """
    H, W = mask.shape
    # Pad one ring of zeros so the exterior is a single connected background component
    pmask = np.pad(mask.astype(bool), 1, mode='constant', constant_values=False)
    seen = np.zeros_like(pmask, dtype=bool)
    comps = 0
    nbrs4 = ((1,0),(-1,0),(0,1),(0,-1))
    nbrs8 = nbrs4 + ((1,1),(1,-1),(-1,1),(-1,-1))
    N = nbrs4 if connectivity == 4 else nbrs8
    for r in range(pmask.shape[0]):
        for c in range(pmask.shape[1]):
            if pmask[r, c] or seen[r, c]:
                continue
            comps += 1
            stack = [(r, c)]
            seen[r, c] = True
            while stack:
                rr, cc = stack.pop()
                for dr, dc in N:
                    nr, nc = rr + dr, cc + dc
                    if 0 <= nr < pmask.shape[0] and 0 <= nc < pmask.shape[1]:
                        if (not pmask[nr, nc]) and (not seen[nr, nc]):
                            seen[nr, nc] = True
                            stack.append((nr, nc))
    return comps

def euler_betti_from_coords(coords: Iterable[Tuple[int,int]], connectivity: int = 4) -> Topology:
    """Compute (beta0, beta1, euler) from a set of (r,c) pixel coordinates.
    Uses 4- or 8-connectivity for both foreground and background consistently.
    """
    coords = list(coords)
    if not coords:
        return Topology(beta0=0, beta1=0, euler=0)
    rs, cs = zip(*coords)
    r0, c0 = min(rs), min(cs)
    r1, c1 = max(rs)+1, max(cs)+1
    mask = np.zeros((r1 - r0, c1 - c0), dtype=bool)
    mask[(np.array(rs)-r0, np.array(cs)-c0)] = True
    return euler_betti_from_mask(mask, connectivity=connectivity)

def euler_betti_from_mask(mask: np.ndarray, connectivity: int = 4) -> Topology:
    """Helper if you already have a binary mask (True=foreground)."""
    beta0 = _label_components(mask, connectivity=connectivity)
    bg_comps = _count_background_components(mask, connectivity=connectivity)
    beta1 = max(0, bg_comps - 1)  # subtract the exterior background component
    return Topology(beta0=beta0, beta1=beta1, euler=beta0 - beta1)
