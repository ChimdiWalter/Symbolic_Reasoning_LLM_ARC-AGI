from __future__ import annotations
from typing import Iterable, List, Tuple, Set
import numpy as np

RC = Tuple[int, int]

# -----------------------------
# Basic geometry from coordinates
# -----------------------------
def bbox_from_coords(coords: Iterable[RC]) -> Tuple[int,int,int,int]:
    coords = list(coords)
    if not coords:
        return (0,0,0,0)
    rs, cs = zip(*coords)
    return (min(rs), min(cs), max(rs)+1, max(cs)+1)

def centroid_from_coords(coords: Iterable[RC]) -> Tuple[float,float]:
    coords = list(coords)
    if not coords:
        return (0.0, 0.0)
    arr = np.asarray(coords, dtype=np.float64)
    return (float(arr[:,0].mean()), float(arr[:,1].mean()))

def perimeter4_from_coords(coords: Iterable[RC]) -> int:
    """4-neighborhood perimeter: number of foreground-to-background edge adjacencies."""
    S: Set[RC] = set(coords)
    if not S:
        return 0
    perim = 0
    for (r,c) in S:
        if (r-1, c) not in S: perim += 1
        if (r+1, c) not in S: perim += 1
        if (r, c-1) not in S: perim += 1
        if (r, c+1) not in S: perim += 1
    return perim

def perimeter8_from_coords(coords: Iterable[RC]) -> int:
    """Simple 8-neighborhood boundary length (counts missing 8-neighbors as well)."""
    S: Set[RC] = set(coords)
    if not S:
        return 0
    perim = 0
    N8 = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
    for (r,c) in S:
        for dr,dc in N8:
            if (r+dr, c+dc) not in S:
                perim += 1
    return perim

def is_border_touching(H: int, W: int, coords: Iterable[RC]) -> bool:
    for r,c in coords:
        if r == 0 or c == 0 or r == H-1 or c == W-1:
            return True
    return False

# -----------------------------
# PCA on pixel coordinates
# -----------------------------
def pca_from_coords(coords: Iterable[RC]) -> Tuple[np.ndarray, np.ndarray, Tuple[float,float]]:
    """Return (eigvals[2], eigvecs[2x2], centroid). eigvals sorted desc."""
    coords = list(coords)
    if not coords:
        return np.array([0.0, 0.0]), np.eye(2), (0.0, 0.0)
    X = np.asarray(coords, dtype=np.float64)
    mu = X.mean(axis=0)
    XC = X - mu
    # covariance (2x2)
    C = (XC.T @ XC) / max(len(XC)-1, 1)
    vals, vecs = np.linalg.eigh(C)  # returns ascending
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    return vals, vecs, (float(mu[0]), float(mu[1]))

# -----------------------------
# 8-neighbor Freeman chain code
# -----------------------------
def boundary_code_from_coords(coords: Iterable[RC]) -> List[int]:
    """Return 8-connected Freeman chain code around the outer boundary of the set.
       Uses Moore-Neighbor tracing. Directions: 0:E,1:SE,2:S,3:SW,4:W,5:NW,6:N,7:NE.
    """
    S: Set[RC] = set(coords)
    if not S:
        return []

    # Find a start pixel on the boundary (lowest row, then lowest col) that has at least one 8-neighbor missing
    def is_boundary(p: RC) -> bool:
        r,c = p
        for dr,dc in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
            if (r+dr, c+dc) not in S:
                return True
        return False
    start = min((p for p in S if is_boundary(p)), default=None)
    if start is None:
        return []

    # Moore-neighbor tracing
    # Order of neighbors clockwise beginning from East
    nbrs = [(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1)]
    p = start
    # previous direction index (we start as if we came from West so we look East first)
    prev_dir = 4
    code: List[int] = []

    def next_dir_idx(i: int) -> int:
        return (i+1) % 8

    visited_first = False
    while True:
        # Search neighbors starting from (prev_dir+1) mod 8
        dir_idx = next_dir_idx(prev_dir)
        found = None
        for k in range(8):
            idx = (dir_idx + k) % 8
            dr,dc = nbrs[idx]
            q = (p[0]+dr, p[1]+dc)
            if q in S:
                found = (idx, q)
                break
        if found is None:
            # Isolated pixel or numerical issue; stop
            break
        idx, q = found
        code.append(idx)
        prev_dir = (idx + 4) % 8  # next search starts from the neighbor behind the move
        p = q
        if p == start:
            if visited_first:
                break
            visited_first = True
    return code

# For compatibility if someone imports "boundary_code" name
boundary_code = boundary_code_from_coords

# --- compatibility alias expected by pipeline.py ---
def freeman_chain_code(coords):
    """Compatibility shim: pipeline expects this name."""
    return boundary_code_from_coords(coords)

# -----------------------------
# Thickness (distance-transform based)
# -----------------------------
def _dt_manhattan(mask: np.ndarray) -> np.ndarray:
    """4-connected (Manhattan) distance transform to the nearest background pixel.
    mask: bool array where True = foreground.
    Returns an int array of same shape with distances (0 on background).
    """
    H, W = mask.shape
    INF = 10**9
    d = np.where(mask, INF, 0).astype(np.int32)

    # forward pass
    for r in range(H):
        for c in range(W):
            if d[r, c] == 0:
                continue
            if r > 0:   d[r, c] = min(d[r, c], d[r-1, c] + 1)
            if c > 0:   d[r, c] = min(d[r, c], d[r, c-1] + 1)

    # backward pass
    for r in range(H-1, -1, -1):
        for c in range(W-1, -1, -1):
            if r+1 < H: d[r, c] = min(d[r, c], d[r+1, c] + 1)
            if c+1 < W: d[r, c] = min(d[r, c], d[r, c+1] + 1)
    return d

def thickness_from_mask(mask: np.ndarray, agg: str = "median") -> float:
    """Estimate object thickness (stroke width) from a binary mask.
    Uses 4-connected distance transform; thickness ≈ 2 * aggregate(distance_on_fg).
    agg ∈ {"median","mean","max"}.
    """
    if mask.size == 0:
        return 0.0
    mask = mask.astype(bool)
    if not mask.any():
        return 0.0
    d = _dt_manhattan(mask)
    vals = d[mask].astype(np.float64)
    if agg == "max":
        core = float(vals.max())
    elif agg == "mean":
        core = float(vals.mean())
    else:
        core = float(np.median(vals))
    return 2.0 * core

# -----------------------------
# Small compatibility shims
# -----------------------------
def border_touching_from_coords(H: int, W: int, coords):
    """Alias expected by some pipelines."""
    return is_border_touching(H, W, coords)

# Already defined earlier:
#  - bbox_from_coords
#  - centroid_from_coords
#  - perimeter4_from_coords
#  - perimeter8_from_coords
#  - boundary_code_from_coords / boundary_code
# Add one more alias:
def freeman_chain_code(coords):
    return boundary_code_from_coords(coords)

# -----------------------------
# Skeleton & stats (deps: numpy only)
# -----------------------------
from dataclasses import dataclass

@dataclass
class SkeletonStats:
    length: int          # number of skeleton pixels
    endpoints: int       # 8-neighborhood degree == 1
    junctions: int       # 8-neighborhood degree >= 3

def _skeleton_ridge(mask: np.ndarray) -> np.ndarray:
    """
    Very lightweight skeleton approximation:
    - compute 4-connected (Manhattan) distance transform (see _dt_manhattan above),
    - keep pixels whose distance is a local maximum w.r.t. their 4-neighbors (ridges).
    Works well for ARC shapes and is fast.
    """
    if mask.size == 0:
        return np.zeros_like(mask, dtype=bool)
    m = mask.astype(bool)
    if not m.any():
        return np.zeros_like(mask, dtype=bool)
    d = _dt_manhattan(m)
    H, W = d.shape
    sk = np.zeros((H, W), dtype=bool)
    # consider only foreground; a pixel is skeleton if its distance is >= all 4-neighbors
    # (ties keep plateaus)
    for r in range(H):
        for c in range(W):
            if not m[r, c]:
                continue
            center = d[r, c]
            # neighbors (with clamps)
            up    = d[r-1, c] if r-1 >= 0 else -1
            down  = d[r+1, c] if r+1 < H else -1
            left  = d[r, c-1] if c-1 >= 0 else -1
            right = d[r, c+1] if c+1 < W else -1
            if center >= up and center >= down and center >= left and center >= right:
                sk[r, c] = True
    return sk

def _degree8(skel: np.ndarray, r: int, c: int) -> int:
    H, W = skel.shape
    deg = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0: 
                continue
            nr, nc = r+dr, c+dc
            if 0 <= nr < H and 0 <= nc < W and skel[nr, nc]:
                deg += 1
    return deg

def skeleton_stats(mask: np.ndarray) -> SkeletonStats:
    """
    Return simple skeleton statistics for a binary mask (True=foreground).
    Uses ridge-of-distance skeleton (fast, no external libs).
    """
    if mask.size == 0:
        return SkeletonStats(length=0, endpoints=0, junctions=0)
    sk = _skeleton_ridge(mask.astype(bool))
    length = int(sk.sum())
    endpoints = 0
    junctions = 0
    H, W = sk.shape
    for r in range(H):
        for c in range(W):
            if not sk[r, c]:
                continue
            deg = _degree8(sk, r, c)
            if deg == 1:
                endpoints += 1
            elif deg >= 3:
                junctions += 1
    return SkeletonStats(length=length, endpoints=endpoints, junctions=junctions)

# -----------------------------
# Robust boundary + Freeman chain code
# Accepts mask, Nx2 ndarray, or list of (r,c) tuples
# -----------------------------
from typing import Iterable, Tuple, List
import numpy as _np

def _coords_from_any(obj) -> List[Tuple[int,int]]:
    """Coerce input into a list[(r,c)]. If 2D mask, return boundary pixels only."""
    arr = _np.asarray(obj)
    if arr.ndim == 2 and arr.dtype != object:
        # treat as mask; pick boundary pixels (4-neighborhood)
        mask = arr.astype(bool)
        H, W = mask.shape
        if H == 0 or W == 0:
            return []
        # boundary: any foreground pixel with at least one 4-neighbor = False/outside
        rr, cc = _np.where(mask)
        out: List[Tuple[int,int]] = []
        for r, c in zip(rr.tolist(), cc.tolist()):
            if r == 0 or not mask[r-1, c]:
                out.append((int(r), int(c))); continue
            if r == H-1 or not mask[r+1, c]:
                out.append((int(r), int(c))); continue
            if c == 0 or not mask[r, c-1]:
                out.append((int(r), int(c))); continue
            if c == W-1 or not mask[r, c+1]:
                out.append((int(r), int(c))); continue
        return out
    if arr.ndim == 2 and arr.shape[1] == 2:
        return [(int(r), int(c)) for r, c in arr.tolist()]
    # assume iterable of rc-like
    try:
        return [(int(r), int(c)) for (r, c) in obj]
    except Exception:
        raise TypeError("Unsupported boundary input: expected mask, Nx2 coords, or list[(r,c)].")

def boundary_code_from_coords(coords_any) -> List[int]:
    """
    Compute a simple 8-direction Freeman chain code from a set/array/list of (r,c).
    If unordered, we sort by (r,c) and connect consecutive points; this is a
    lightweight descriptor (not a full boundary trace). Deterministic & robust.
    """
    pts = _coords_from_any(coords_any)
    if len(pts) < 2:
        return []
    pts.sort()  # deterministic ordering
    # 8-neighborhood direction map
    dir_map = {
        (-1,  0): 0,  # up
        (-1,  1): 1,  # up-right
        ( 0,  1): 2,  # right
        ( 1,  1): 3,  # down-right
        ( 1,  0): 4,  # down
        ( 1, -1): 5,  # down-left
        ( 0, -1): 6,  # left
        (-1, -1): 7,  # up-left
    }
    code: List[int] = []
    for (r0, c0), (r1, c1) in zip(pts, pts[1:]):
        dr = _np.clip(r1 - r0, -1, 1)
        dc = _np.clip(c1 - c0, -1, 1)
        if (int(dr), int(dc)) == (0, 0):
            continue
        d = dir_map.get((int(dr), int(dc)))
        if d is not None:
            code.append(d)
    # close the loop loosely (optional)
    (r0, c0), (r1, c1) = pts[-1], pts[0]
    dr = _np.clip(r1 - r0, -1, 1); dc = _np.clip(c1 - c0, -1, 1)
    d = {(-1,0):0, (-1,1):1, (0,1):2, (1,1):3, (1,0):4, (1,-1):5, (0,-1):6, (-1,-1):7}.get((int(dr), int(dc)))
    if d is not None:
        code.append(d)
    return code

def freeman_chain_code(obj_any) -> List[int]:
    """
    Back-compat entry: accept mask, Nx2 coords, or list[(r,c)] and return the
    deterministic Freeman chain descriptor above.
    """
    return boundary_code_from_coords(obj_any)

# -----------------------------
# Back-compat Freeman chain code object
# -----------------------------
from dataclasses import dataclass
from typing import List, Tuple
import numpy as _np

@dataclass(frozen=True)
class ChainCode:
    code: List[int]

    @property
    def length(self) -> int:
        return len(self.code)

    # Optional niceties
    def __iter__(self):
        return iter(self.code)
    def __len__(self):
        return len(self.code)
    def __repr__(self):
        return f"ChainCode(len={len(self.code)})"

def _coords_from_any(obj) -> List[Tuple[int,int]]:
    arr = _np.asarray(obj)
    if arr.ndim == 2 and arr.dtype != object:
        mask = arr.astype(bool)
        H, W = mask.shape
        if H == 0 or W == 0:
            return []
        rr, cc = _np.where(mask)
        out: List[Tuple[int,int]] = []
        for r, c in zip(rr.tolist(), cc.tolist()):
            if r == 0 or not mask[r-1, c]:
                out.append((int(r), int(c))); continue
            if r == H-1 or not mask[r+1, c]:
                out.append((int(r), int(c))); continue
            if c == 0 or not mask[r, c-1]:
                out.append((int(r), int(c))); continue
            if c == W-1 or not mask[r, c+1]:
                out.append((int(r), int(c))); continue
        return out
    if arr.ndim == 2 and arr.shape[1] == 2:
        return [(int(r), int(c)) for r, c in arr.tolist()]
    try:
        return [(int(r), int(c)) for (r, c) in obj]
    except Exception:
        raise TypeError("Unsupported boundary input: expected mask, Nx2 coords, or list[(r,c)].")

def boundary_code_from_coords(coords_any) -> ChainCode:
    pts = _coords_from_any(coords_any)
    if len(pts) < 2:
        return ChainCode([])
    pts.sort()
    dir_map = {
        (-1,  0): 0, (-1,  1): 1, ( 0,  1): 2, ( 1,  1): 3,
        ( 1,  0): 4, ( 1, -1): 5, ( 0, -1): 6, (-1, -1): 7,
    }
    code: List[int] = []
    for (r0, c0), (r1, c1) in zip(pts, pts[1:]):
        dr = int(_np.clip(r1 - r0, -1, 1))
        dc = int(_np.clip(c1 - c0, -1, 1))
        if (dr, dc) == (0, 0):
            continue
        d = dir_map.get((dr, dc))
        if d is not None:
            code.append(d)
    # lightly "close" loop
    r0, c0 = pts[-1]
    r1, c1 = pts[0]
    dr = int(_np.clip(r1 - r0, -1, 1))
    dc = int(_np.clip(c1 - c0, -1, 1))
    d = dir_map.get((dr, dc))
    if d is not None:
        code.append(d)
    return ChainCode(code)

def freeman_chain_code(obj_any) -> ChainCode:
    return boundary_code_from_coords(obj_any)

# -----------------------------
# Back-compat PCA result for coords/masks
# -----------------------------
from dataclasses import dataclass
from typing import Tuple, List
import numpy as _np
import math as _math

@dataclass(frozen=True)
class PCAResult:
    cx: float
    cy: float
    v1: Tuple[float, float]   # principal direction (unit)
    v2: Tuple[float, float]   # secondary direction (unit)
    ev1: float                # principal eigenvalue (variance along v1)
    ev2: float                # secondary eigenvalue
    angle: float              # orientation of v1 in radians (rows,cols convention)

def _coords_from_any_for_pca(obj) -> _np.ndarray:
    arr = _np.asarray(obj)
    # If it's a 2D mask, collect foreground coords
    if arr.ndim == 2 and arr.dtype != object:
        rr, cc = _np.where(arr.astype(bool))
        return _np.stack([rr.astype(_np.float64), cc.astype(_np.float64)], axis=1)
    # If it's Nx2 coords
    if arr.ndim == 2 and arr.shape[1] == 2:
        return arr.astype(_np.float64)
    # If it's a Python iterable of (r,c)
    try:
        pts = _np.array([(float(r), float(c)) for (r,c) in obj], dtype=_np.float64)
        if pts.ndim == 2 and pts.shape[1] == 2:
            return pts
    except Exception:
        pass
    raise TypeError("pca_from_coords: expected mask, Nx2 array, or iterable of (r,c)")

def pca_from_coords(obj) -> PCAResult:
    """
    PCA over coordinates (row, col). Returns PCAResult with attributes:
      .cx, .cy, .v1, .v2, .ev1, .ev2, .angle
    - Accepts 2D mask, Nx2 ndarray, or list of (r,c) pairs.
    """
    P = _coords_from_any_for_pca(obj)
    n = P.shape[0]
    if n == 0:
        return PCAResult(0.0, 0.0, (1.0, 0.0), (0.0, 1.0), 0.0, 0.0, 0.0)
    cx, cy = float(P[:,0].mean()), float(P[:,1].mean())
    Q = P - _np.array([cx, cy], dtype=_np.float64)
    # 2x2 covariance
    C = (Q.T @ Q) / max(n - 1, 1)
    # eigendecomposition (symmetric)
    vals, vecs = _np.linalg.eigh(C)  # ascending order
    # sort descending
    idx = _np.argsort(vals)[::-1]
    vals = vals[idx]
    vecs = vecs[:, idx]
    v1 = vecs[:, 0]
    v2 = vecs[:, 1]
    # normalize directions
    def _unit(v):
        n = _np.linalg.norm(v)
        return (float(v[0]/n), float(v[1]/n)) if n > 0 else (1.0, 0.0)
    v1u = _unit(v1)
    v2u = _unit(v2)
    # angle of v1 in (row, col) coords
    angle = _math.atan2(v1u[0], v1u[1])  # y=row, x=col
    return PCAResult(cx=cx, cy=cy, v1=v1u, v2=v2u, ev1=float(vals[0]), ev2=float(vals[1]), angle=float(angle))

# --- Back-compat aliases for PCAResult ---
try:
    PCAResult  # type: ignore[name-defined]
    import math as _math

    def _angle_rad(self):  # alias for existing .angle
        return self.angle
    def _angle_deg(self):
        return (self.angle * 180.0) / _math.pi

    # attach as properties (works even after class definition)
    PCAResult.angle_rad = property(_angle_rad)  # type: ignore[attr-defined]
    PCAResult.angle_deg = property(_angle_deg)  # type: ignore[attr-defined]
except Exception:
    pass

# --- Back-compat: elongation metrics on PCAResult ---
try:
    PCAResult  # already defined above

    def _elongation(self):
        # ratio of principal to secondary variance (>=1). epsilon avoids div/0.
        eps = 1e-9
        return float(self.ev1 / (self.ev2 + eps))

    def _flatness(self):
        # inverse ratio in [0,1]; useful for some heuristics.
        eps = 1e-9
        return float(self.ev2 / (self.ev1 + eps))

    PCAResult.elongation = property(_elongation)  # type: ignore[attr-defined]
    PCAResult.flatness   = property(_flatness)    # type: ignore[attr-defined]
except Exception:
    pass

# -----------------------------
# Back-compat thickness stats from mask/coords
# -----------------------------
from dataclasses import dataclass
from typing import Tuple, List
import numpy as _np

@dataclass(frozen=True)
class ThicknessStats:
    max_diameter: float
    avg_diameter: float
    min_diameter: float
    num_pixels: int

def _as_mask(any_obj) -> _np.ndarray:
    """Coerce input to a boolean mask. Accepts mask, Nx2 coords, or list[(r,c)]."""
    arr = _np.asarray(any_obj)
    if arr.ndim == 2 and arr.dtype != object and arr.dtype != _np.dtype('O'):
        # already a 2D array (likely a grid/mask)
        if arr.dtype == bool:
            return arr
        # Treat nonzero as foreground
        return (arr != 0)
    # Nx2 numeric coords
    if arr.ndim == 2 and arr.shape[1] == 2:
        rr = arr[:, 0].astype(int)
        cc = arr[:, 1].astype(int)
        H = (rr.max() + 1) if rr.size else 0
        W = (cc.max() + 1) if cc.size else 0
        m = _np.zeros((H, W), dtype=bool)
        if rr.size:
            m[(rr, cc)] = True
        return m
    # Python list of (r,c) pairs
    try:
        pts = [(int(r), int(c)) for (r, c) in any_obj]
        if not pts:
            return _np.zeros((0, 0), dtype=bool)
        H = max(r for r, _ in pts) + 1
        W = max(c for _, c in pts) + 1
        m = _np.zeros((H, W), dtype=bool)
        rr, cc = zip(*pts)
        m[(list(rr), list(cc))] = True
        return m
    except Exception:
        raise TypeError("thickness_from_mask: expected mask, Nx2 coords, or list[(r,c)]")

def _dt_cityblock(mask: _np.ndarray) -> _np.ndarray:
    """Simple 2-pass cityblock (Manhattan) distance transform on foreground."""
    H, W = mask.shape
    inf = 10**9
    # initialize distances: 0 on background, big on foreground; we invert so we get distance to background
    # Actually for thickness we want distance to background for foreground pixels.
    dist = _np.full((H, W), inf, dtype=_np.int32)
    dist[~mask] = 0
    # forward pass
    for r in range(H):
        for c in range(W):
            if mask[r, c]:
                best = dist[r, c]
                if r > 0:     best = min(best, dist[r-1, c] + 1)
                if c > 0:     best = min(best, dist[r, c-1] + 1)
                dist[r, c] = best
    # backward pass
    for r in range(H - 1, -1, -1):
        for c in range(W - 1, -1, -1):
            if mask[r, c]:
                best = dist[r, c]
                if r + 1 < H: best = min(best, dist[r+1, c] + 1)
                if c + 1 < W: best = min(best, dist[r, c+1] + 1)
                dist[r, c] = best
    return dist

def thickness_from_mask(obj) -> ThicknessStats:
    """
    Return thickness stats as a dataclass with .max_diameter, etc.
    Uses a cityblock DT as a fast proxy (works well on ARC grids).
    """
    m = _as_mask(obj)
    if m.size == 0 or not m.any():
        return ThicknessStats(max_diameter=0.0, avg_diameter=0.0, min_diameter=0.0, num_pixels=0)
    dt = _dt_cityblock(m)
    # On foreground, dt gives distance to background (in Manhattan steps).
    # A simple diameter proxy is ~2 * max distance.
    fg = dt[m]
    max_d = 2.0 * float(fg.max())
    min_d = 2.0 * float(fg.min())  # thin parts
    avg_d = 2.0 * float(fg.mean())
    return ThicknessStats(max_diameter=max_d, avg_diameter=avg_d, min_diameter=min_d, num_pixels=int(fg.size))

# --- Back-compat aliases for ThicknessStats ---
try:
    ThicknessStats  # defined above

    @property
    def _mean_radius(self):  # avg_diameter / 2
        return float(self.avg_diameter) * 0.5

    @property
    def _max_radius(self):
        return float(self.max_diameter) * 0.5

    @property
    def _min_radius(self):
        return float(self.min_diameter) * 0.5

    @property
    def _mean_thickness(self):
        return float(self.avg_diameter)

    # attach properties
    ThicknessStats.mean_radius = _mean_radius          # type: ignore[attr-defined]
    ThicknessStats.max_radius  = _max_radius           # type: ignore[attr-defined]
    ThicknessStats.min_radius  = _min_radius           # type: ignore[attr-defined]
    ThicknessStats.mean_thickness = _mean_thickness    # type: ignore[attr-defined]
except Exception:
    pass
