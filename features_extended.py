from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
import numpy as np
from collections import Counter

from components import Grid, Scene, Component

Color = int
RC = Tuple[int, int]
BBox = Tuple[int, int, int, int]

# ----------------------------------
# Scene-level features
# ----------------------------------

@dataclass
class SceneFeatures:
    H: int
    W: int
    area: int
    palette: Set[Color]
    color_hist: Dict[Color, int]
    density: float  # non-zero / (H*W)
    per_color_density: Dict[Color, float]
    fg_bbox: BBox
    touches_border_any: bool
    symmetry_h: bool
    symmetry_v: bool
    symmetry_rot180: bool
    symmetry_d1: bool
    symmetry_d2: bool
    solid_rows: int
    solid_cols: int
    longest_row_run: int
    longest_col_run: int
    cc_count_by_color: Dict[Color, int]


def compute_scene_features(grid: Grid, scene: Scene) -> SceneFeatures:
    g = grid.data
    H, W = g.shape
    area = H * W
    palette = set(int(c) for c in np.unique(g))
    color_hist = {int(c): int(np.sum(g == c)) for c in palette}
    nz = area - color_hist.get(0, 0)
    density = nz / float(area) if area else 0.0
    per_color_density = {c: color_hist[c] / float(area) if area else 0.0 for c in color_hist}

    # foreground bbox
    rr, cc = np.where(g != 0)
    if rr.size > 0:
        fg_bbox = (int(rr.min()), int(cc.min()), int(rr.max()) + 1, int(cc.max()) + 1)
    else:
        fg_bbox = (0, 0, 0, 0)

    touches_border_any = any(c.touches_border for c in scene.comps)

    sym_h = np.array_equal(g, g[::-1, :])
    sym_v = np.array_equal(g, g[:, ::-1])
    sym_r = np.array_equal(g, np.rot90(g, 2))

    # diagonal symmetries (pad to square)
    if H != W:
        S = max(H, W)
        pad_r = (S - H) // 2
        pad_c = (S - W) // 2
        pad = ((pad_r, S - H - pad_r), (pad_c, S - W - pad_c))
        gs = np.pad(g, pad, mode="constant")
    else:
        gs = g
    sym_d1 = np.array_equal(gs, gs.T)
    sym_d2 = np.array_equal(gs, np.flipud(gs.T))

    # line/axis cues
    solid_rows = int(np.sum([len(np.unique(g[r, :])) == 1 for r in range(H)]))
    solid_cols = int(np.sum([len(np.unique(g[:, c])) == 1 for c in range(W)]))

    longest_row_run = _longest_run_rows(g)
    longest_col_run = _longest_run_cols(g)

    return SceneFeatures(
        H=H,
        W=W,
        area=area,
        palette=palette,
        color_hist=color_hist,
        density=density,
        per_color_density=per_color_density,
        fg_bbox=fg_bbox,
        touches_border_any=bool(touches_border_any),
        symmetry_h=bool(sym_h),
        symmetry_v=bool(sym_v),
        symmetry_rot180=bool(sym_r),
        symmetry_d1=bool(sym_d1),
        symmetry_d2=bool(sym_d2),
        solid_rows=solid_rows,
        solid_cols=solid_cols,
        longest_row_run=longest_row_run,
        longest_col_run=longest_col_run,
        cc_count_by_color=scene.cc_count_by_color,
    )


def _longest_run_rows(g: np.ndarray) -> int:
    H, W = g.shape
    best = 0
    for r in range(H):
        v = g[r, :]
        cur = 1
        for c in range(1, W):
            if v[c] == v[c - 1]:
                cur += 1
                if cur > best:
                    best = cur
            else:
                cur = 1
        if best < 1 and W > 0:
            best = 1
    return best


def _longest_run_cols(g: np.ndarray) -> int:
    H, W = g.shape
    best = 0
    for c in range(W):
        v = g[:, c]
        cur = 1
        for r in range(1, H):
            if v[r] == v[r - 1]:
                cur += 1
                if cur > best:
                    best = cur
            else:
                cur = 1
        if best < 1 and H > 0:
            best = 1
    return best

# ----------------------------------
# Input→Output pair features & correspondences
# ----------------------------------

@dataclass
class Match:
    i_in: int
    i_out: int
    score: float  # higher is better


def pairwise_iou(a: Component, b: Component) -> float:
    # IoU on pixel sets
    A = set(map(tuple, a.pixels.tolist()))
    B = set(map(tuple, b.pixels.tolist()))
    inter = len(A & B)
    union = len(A | B)
    return float(inter) / union if union else 0.0


def shape_signature(c: Component) -> Tuple[int, int, int, int, int]:
    # Simple signature: area, perimeter4, bbox_w, bbox_h, holes
    r0, c0, r1, c1 = c.bbox
    return (c.area, c.perimeter4, int(c1 - c0), int(r1 - r0), c.holes)


def centroid_dist(a: Component, b: Component) -> float:
    ar, ac = a.centroid
    br, bc = b.centroid
    return float(abs(ar - br) + abs(ac - bc))


def same_shape_under_symmetry(a: Component, b: Component) -> bool:
    # quick check via symmetry flags and bbox dims set (orderless)
    ra = (a.bbox[2] - a.bbox[0], a.bbox[3] - a.bbox[1])
    rb = (b.bbox[2] - b.bbox[0], b.bbox[3] - b.bbox[1])
    dims_match = {ra, (ra[1], ra[0])}
    return rb in dims_match and a.area == b.area and a.holes == b.holes


def match_components(input_scene: Scene, output_scene: Scene) -> List[Match]:
    """Greedy bipartite matching guided by color, shape, and IoU over a shared frame.
    Note: exact IoU in different frames is 0; we instead use signatures + centroid distance.
    """
    matches: List[Match] = []
    used_out: Set[int] = set()
    for i, a in enumerate(input_scene.comps):
        cands = []
        for j, b in enumerate(output_scene.comps):
            if j in used_out:
                continue
            color_bonus = 1.0 if a.color == b.color else 0.0
            sig_a = shape_signature(a)
            sig_b = shape_signature(b)
            sig_score = 1.0 if sig_a == sig_b else 0.0
            relaxed = 1.0 if (a.area == b.area and a.holes == b.holes) else 0.0
            dist = centroid_dist(a, b)
            dist_score = 1.0 / (1.0 + dist)
            score = 2.0 * color_bonus + 1.5 * sig_score + 0.5 * relaxed + 0.5 * dist_score
            cands.append((score, j))
        if not cands:
            continue
        cands.sort(reverse=True)
        best_score, best_j = cands[0]
        used_out.add(best_j)
        matches.append(Match(i_in=i, i_out=best_j, score=float(best_score)))
    return matches


@dataclass
class PairFeatures:
    color_map: Dict[Color, Color]
    created_colors: Set[Color]
    removed_colors: Set[Color]
    total_pixel_delta: int
    per_color_delta: Dict[Color, int]
    displacements: Dict[int, Tuple[int, int]]  # comp_id_in -> (dr, dc)
    transforms_detected: Dict[str, bool]  # translate, reflect_h/v, rotate_90/180, fill_holes, border_trim, etc.


def compute_pair_features(inp: Grid, in_scene: Scene, out: Grid, out_scene: Scene) -> PairFeatures:
    in_hist = Counter(int(c) for c in inp.data.flatten())
    out_hist = Counter(int(c) for c in out.data.flatten())
    colors_in = [c for c in in_hist if c != 0]
    colors_out = [c for c in out_hist if c != 0]

    color_map: Dict[Color, Color] = {}
    used: Set[Color] = set()
    for c in sorted(colors_in, key=lambda x: -in_hist[x]):
        if not colors_out:
            break
        best = None
        best_diff = 1e9
        for d in colors_out:
            if d in used:
                continue
            diff = abs(in_hist[c] - out_hist[d])
            if diff < best_diff:
                best_diff = diff
                best = d
        if best is not None:
            color_map[c] = best
            used.add(best)

    created_colors = set(colors_out) - set(color_map.values())
    removed_colors = set(colors_in) - set(color_map.keys())

    total_pixel_delta = int(sum((out_hist[c] - in_hist.get(c, 0)) for c in out_hist))
    per_color_delta = {c: int(out_hist[c] - in_hist.get(c, 0)) for c in set(in_hist) | set(out_hist)}

    matches = match_components(in_scene, out_scene)
    displacements: Dict[int, Tuple[int, int]] = {}
    for m in matches:
        a = in_scene.comps[m.i_in]
        b = out_scene.comps[m.i_out]
        dr = int(round(b.centroid[0] - a.centroid[0]))
        dc = int(round(b.centroid[1] - a.centroid[1]))
        displacements[m.i_in] = (dr, dc)

    transforms = {
        "translate": len(displacements) > 0 and len(set(displacements.values())) <= 2,
        "reflect_h": np.array_equal(out.data, inp.data[::-1, :]),
        "reflect_v": np.array_equal(out.data, inp.data[:, ::-1]),
        "rotate_90": np.array_equal(out.data, np.rot90(inp.data, 1)),
        "rotate_180": np.array_equal(out.data, np.rot90(inp.data, 2)),
        "rotate_270": np.array_equal(out.data, np.rot90(inp.data, 3)),
        "border_trim": _border_trim_detect(inp.data, out.data),
        "fill_holes": _fill_holes_detect(in_scene, out_scene),
    }

    return PairFeatures(
        color_map=color_map,
        created_colors=created_colors,
        removed_colors=removed_colors,
        total_pixel_delta=total_pixel_delta,
        per_color_delta=per_color_delta,
        displacements=displacements,
        transforms_detected=transforms,
    )

# ----------------------------------
# Heuristics for pairwise transform detection
# ----------------------------------

def _border_trim_detect(a: np.ndarray, b: np.ndarray) -> bool:
    Ha, Wa = a.shape
    Hb, Wb = b.shape
    if Hb > Ha or Wb > Wa:
        return False
    for top in range(0, 5):
        for left in range(0, 5):
            for bot in range(0, 5):
                for right in range(0, 5):
                    if top + bot >= Ha or left + right >= Wa:
                        continue
                    crop = a[top:Ha - bot, left:Wa - right]
                    if crop.shape == b.shape and np.array_equal(crop, b):
                        return True
    return False


def _fill_holes_detect(in_scene: Scene, out_scene: Scene) -> bool:
    matches = match_components(in_scene, out_scene)
    dec = False
    for m in matches:
        a = in_scene.comps[m.i_in]
        b = out_scene.comps[m.i_out]
        if b.holes < a.holes:
            dec = True
    return dec

# ----------------------------------
# Quick demo
# ----------------------------------
if __name__ == "__main__":
    g_in = Grid(np.array([
        [0,0,1,1,0],
        [0,0,1,1,0],
        [2,0,0,0,0],
        [2,2,0,3,3],
        [0,0,0,3,3],
    ], dtype=np.int8))
    from components import extract_scene
    s_in = extract_scene(g_in, connectivity=4)

    g_out = Grid(np.array([
        [0,0,1,1,0],
        [0,0,1,1,0],
        [0,0,0,0,2],
        [2,2,0,3,3],
        [0,0,0,3,3],
    ], dtype=np.int8))
    s_out = extract_scene(g_out, connectivity=4)

    sf = compute_scene_features(g_in, s_in)
    print("scene density:", sf.density, "palette:", sf.palette)

    pf = compute_pair_features(g_in, s_in, g_out, s_out)
    print("color_map:", pf.color_map)
    print("displacements:", pf.displacements)
    print("transforms:", pf.transforms_detected)
