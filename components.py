from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable, Optional, Set
import numpy as np
from scipy.ndimage import label as cc_label

Color = int  # 0..9 in ARC
RC = Tuple[int, int]  # (row, col)
BBox = Tuple[int, int, int, int]  # r0, c0, r1, c1 (exclusive)

# ----------------------------
# Core dataclasses
# ----------------------------

@dataclass(frozen=True)
class Grid:
    data: np.ndarray  # (H, W) int8 values in 0..9

    @property
    def H(self) -> int:
        return int(self.data.shape[0])

    @property
    def W(self) -> int:
        return int(self.data.shape[1])

    def copy(self) -> "Grid":
        return Grid(self.data.copy())


@dataclass
class Component:
    id: int
    color: Color
    pixels: np.ndarray  # (N, 2) array of (r,c)
    bbox: BBox
    area: int
    centroid: Tuple[float, float]
    perimeter4: int
    perimeter8: int
    holes: int
    euler_char: int  # components (always 1 here) - holes
    touches_border: bool
    symmetry_h: bool
    symmetry_v: bool
    symmetry_d1: bool  # main diagonal
    symmetry_d2: bool  # anti-diagonal


@dataclass
class Scene:
    comps: List[Component]
    # adjacency over component ids (4-connected adjacency between any pixels)
    adj4: Dict[Tuple[int, int], bool]
    # relations: left_of, above, encloses, overlaps, same_color pairs, aligned_row, aligned_col
    relations: Dict[str, List[Tuple[int, int]]]
    # scene-level summaries
    H: int
    W: int
    palette: Set[Color]
    cc_count_by_color: Dict[Color, int]


# ----------------------------
# Public API
# ----------------------------

def extract_scene(grid: Grid, connectivity: int = 4) -> Scene:
    """Extract connected components and scene relations from an ARC grid.

    Args:
        grid: Grid with values 0..9
        connectivity: 4 or 8 connectivity for component extraction
    Returns:
        Scene with components, adjacency, relations and summaries
    """
    assert connectivity in (4, 8)

    comps: List[Component] = []
    palette: Set[Color] = set(int(c) for c in np.unique(grid.data))
    if 0 in palette and not (grid.data == 0).any():  # robustness (unlikely)
        palette.discard(0)

    cc_count_by_color: Dict[Color, int] = {}

    # structure element for ndimage.label
    structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]) if connectivity == 4 else np.ones((3, 3), dtype=int)

    for color in range(10):
        mask = (grid.data == color)
        if not mask.any():
            continue
        lab, n = cc_label(mask, structure=structure)
        if n == 0:
            continue
        cc_count_by_color[color] = n
        for k in range(1, n + 1):
            coords = np.argwhere(lab == k)
            r0, c0 = coords.min(axis=0)
            r1, c1 = coords.max(axis=0) + 1
            area = int(coords.shape[0])
            centroid = coords.mean(axis=0)
            per4 = _perimeter(coords, conn=4)
            per8 = _perimeter(coords, conn=8)
            holes = _estimate_holes(coords)
            touches = _touches_border((r0, c0, r1, c1), grid.H, grid.W)
            # build a tight mask for symmetry checks
            box = grid.data[r0:r1, c0:c1]
            obj_mask = np.zeros_like(box, dtype=bool)
            # translate coords into local bbox frame
            obj_mask[(coords[:, 0] - r0, coords[:, 1] - c0)] = True
            sym_h, sym_v, sym_d1, sym_d2 = _symmetries(obj_mask)

            comps.append(
                Component(
                    id=len(comps),
                    color=color,
                    pixels=coords,
                    bbox=(int(r0), int(c0), int(r1), int(c1)),
                    area=area,
                    centroid=(float(centroid[0]), float(centroid[1])),
                    perimeter4=per4,
                    perimeter8=per8,
                    holes=holes,
                    euler_char=1 - holes,
                    touches_border=touches,
                    symmetry_h=sym_h,
                    symmetry_v=sym_v,
                    symmetry_d1=sym_d1,
                    symmetry_d2=sym_d2,
                )
            )

    # adjacency + relations
    adj4 = _adjacency4(comps)
    relations = _relations(comps)

    return Scene(
        comps=comps,
        adj4=adj4,
        relations=relations,
        H=grid.H,
        W=grid.W,
        palette=set(int(c) for c in np.unique(grid.data)),
        cc_count_by_color=cc_count_by_color,
    )


# ----------------------------
# Helpers
# ----------------------------

def _perimeter(coords: np.ndarray, conn: int = 4) -> int:
    """Grid-aware perimeter via counting exposed edges (conn=4) or corners (conn=8)."""
    S: Set[Tuple[int, int]] = set(map(tuple, coords.tolist()))
    per = 0
    if conn == 4:
        nbrs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for r, c in S:
            for dr, dc in nbrs:
                if (r + dr, c + dc) not in S:
                    per += 1
    elif conn == 8:
        nbrs = [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (1, -1), (-1, 1), (-1, -1),
        ]
        for r, c in S:
            # count missing neighbors with a small weight for diagonals
            for dr, dc in nbrs:
                if (r + dr, c + dc) not in S:
                    per += 1
    else:
        raise ValueError("conn must be 4 or 8")
    return int(per)


def _estimate_holes(coords: np.ndarray) -> int:
    """Estimate number of holes using Euler characteristic on a tight mask.
    For small shapes this grid-based approach is robust and fast."""
    r0, c0 = coords.min(axis=0)
    r1, c1 = coords.max(axis=0) + 1
    H, W = int(r1 - r0), int(c1 - c0)
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[(coords[:, 0] - r0, coords[:, 1] - c0)] = 1

    # Count vertices/edges/faces using 2x2 block configurations (digital topology)
    # Using the formula chi = C - H = V - E + F for binary images.
    # Here we approximate via 2x2 pattern counts (see e.g., Lee 1990).
    # For our purposes, a simpler approach suffices: flood-fill background and count components.
    from collections import deque

    # Pad to capture outer background as one region
    mpad = np.pad(mask, 1, constant_values=0)
    H2, W2 = mpad.shape

    # mark background components
    visited = np.zeros_like(mpad, dtype=bool)

    def bfs(sr: int, sc: int, val: int):
        q = deque([(sr, sc)])
        visited[sr, sc] = True
        while q:
            r, c = q.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < H2 and 0 <= cc < W2 and not visited[rr, cc] and mpad[rr, cc] == val:
                    visited[rr, cc] = True
                    q.append((rr, cc))

    # Count background components (0) and foreground components (1) in the padded box
    bg_comp = 0
    fg_comp = 0
    for r in range(H2):
        for c in range(W2):
            if not visited[r, c]:
                if mpad[r, c] == 0:
                    bg_comp += 1
                    bfs(r, c, 0)
                else:
                    fg_comp += 1
                    bfs(r, c, 1)

    # Remove the outer background region from bg_comp to get true holes
    holes = max(bg_comp - 1, 0)
    # Sanity: for our component extraction, fg_comp should be 1
    return int(holes)


def _touches_border(bbox: BBox, H: int, W: int) -> bool:
    r0, c0, r1, c1 = bbox
    return r0 == 0 or c0 == 0 or r1 == H or c1 == W


def _symmetries(mask: np.ndarray) -> Tuple[bool, bool, bool, bool]:
    """Check exact symmetry of a boolean mask in its bbox frame."""
    h = np.array_equal(mask, mask[::-1, :])
    v = np.array_equal(mask, mask[:, ::-1])
    # Diagonals need square; pad if needed
    H, W = mask.shape
    if H != W:
        S = max(H, W)
        pad_r = (S - H) // 2
        pad_c = (S - W) // 2
        pad = ((pad_r, S - H - pad_r), (pad_c, S - W - pad_c))
        m = np.pad(mask, pad, mode="constant")
    else:
        m = mask
    d1 = np.array_equal(m, m.T)
    d2 = np.array_equal(m, np.flipud(m.T))
    return bool(h), bool(v), bool(d1), bool(d2)


def _adjacency4(comps: List[Component]) -> Dict[Tuple[int, int], bool]:
    idx = {i: set(map(tuple, c.pixels.tolist())) for i, c in enumerate(comps)}
    edges: Dict[Tuple[int, int], bool] = {}
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            if _touching4(idx[i], idx[j]):
                edges[(i, j)] = True
                edges[(j, i)] = True
    return edges


def _touching4(a: Set[RC], b: Set[RC]) -> bool:
    for r, c in a:
        if (r + 1, c) in b or (r - 1, c) in b or (r, c + 1) in b or (r, c - 1) in b:
            return True
    return False


def _relations(comps: List[Component]) -> Dict[str, List[Tuple[int, int]]]:
    rel: Dict[str, List[Tuple[int, int]]] = {
        "left_of": [], "above": [], "encloses": [], "overlaps": [],
        "same_color": [], "aligned_row": [], "aligned_col": []
    }

    def encloses(a: Component, b: Component) -> bool:
        r0a, c0a, r1a, c1a = a.bbox
        r0b, c0b, r1b, c1b = b.bbox
        return r0a <= r0b and c0a <= c0b and r1a >= r1b and c1a >= c1b

    def overlaps(a: Component, b: Component) -> bool:
        r0a, c0a, r1a, c1a = a.bbox
        r0b, c0b, r1b, c1b = b.bbox
        return not (r1a <= r0b or r1b <= r0a or c1a <= c0b or c1b <= c0a)

    for i, a in enumerate(comps):
        for j, b in enumerate(comps):
            if i == j:
                continue
            if a.color == b.color:
                rel["same_color"].append((i, j))
            # positional relations by centroids
            if a.centroid[1] < b.centroid[1]:
                rel["left_of"].append((i, j))
            if a.centroid[0] < b.centroid[0]:
                rel["above"].append((i, j))
            # coarse alignment
            if int(round(a.centroid[0])) == int(round(b.centroid[0])):
                rel["aligned_row"].append((i, j))
            if int(round(a.centroid[1])) == int(round(b.centroid[1])):
                rel["aligned_col"].append((i, j))
            # bbox relations
            if encloses(a, b):
                rel["encloses"].append((i, j))
            if overlaps(a, b):
                rel["overlaps"].append((i, j))

    return rel


# ----------------------------
# Quick self-test (can be removed in prod)
# ----------------------------
if __name__ == "__main__":
    # Tiny sanity grid
    g = Grid(
        np.array([
            [0,0,1,1,0],
            [0,0,1,1,0],
            [2,0,0,0,0],
            [2,2,0,3,3],
            [0,0,0,3,3],
        ], dtype=np.int8)
    )
    scene = extract_scene(g, connectivity=4)
    print(f"H,W={scene.H},{scene.W} palette={scene.palette} comps={len(scene.comps)}")
    for c in scene.comps:
        print(c.id, c.color, c.area, c.bbox, c.perimeter4, c.holes, c.touches_border)
    print("relations keys:", {k: len(v) for k, v in scene.relations.items()})
