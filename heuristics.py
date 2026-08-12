# heuristics.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import numpy as np
from collections import Counter
from itertools import product

from components import Grid

# ---------------------------
# Basic helpers
# ---------------------------

def palette(arr: np.ndarray) -> Tuple[int, ...]:
    return tuple(sorted(int(x) for x in np.unique(arr)))

def nonzero_count(arr: np.ndarray) -> int:
    return int((arr != 0).sum())

def bbox(arr: np.ndarray) -> Tuple[int,int,int,int]:
    """Return (r0, r1, c0, c1) inclusive-exclusive bbox of nonzeros; if empty, whole array sized 0."""
    R, C = arr.shape
    nz = np.argwhere(arr != 0)
    if nz.size == 0:
        return 0, 0, 0, 0
    r0 = int(nz[:,0].min()); r1 = int(nz[:,0].max()) + 1
    c0 = int(nz[:,1].min()); c1 = int(nz[:,1].max()) + 1
    return r0, r1, c0, c1

def center_crop_or_pad(arr: np.ndarray, out_shape: Tuple[int,int]) -> np.ndarray:
    """Center-crop if too large; zero-pad centered if too small."""
    H, W = out_shape
    h, w = arr.shape
    out = np.zeros((H, W), dtype=arr.dtype)
    ih = min(H, h); iw = min(W, w)
    src_r0 = (h - ih)//2; src_c0 = (w - iw)//2
    dst_r0 = (H - ih)//2; dst_c0 = (W - iw)//2
    out[dst_r0:dst_r0+ih, dst_c0:dst_c0+iw] = arr[src_r0:src_r0+ih, src_c0:src_c0+iw]
    return out

def majority_nonzero_color(grids: List[np.ndarray]) -> Optional[int]:
    freq = Counter()
    for g in grids:
        vals, counts = np.unique(g, return_counts=True)
        for v, c in zip(vals, counts):
            if v != 0: freq[int(v)] += int(c)
    return freq.most_common(1)[0][0] if freq else None

def infer_out_shape_from_train(train_pairs: List[Tuple[Grid, Grid]], default_in: Tuple[int,int]) -> Tuple[int,int]:
    """If all train outputs share one shape, use it; else use input shape."""
    shapes = [y.data.shape for _, y in train_pairs]
    if shapes and all(s == shapes[0] for s in shapes):
        return shapes[0]
    return default_in

# ---------------------------
# Color transforms
# ---------------------------

def color_hist(arr: np.ndarray) -> np.ndarray:
    h = np.zeros(10, dtype=np.int64)
    vals, counts = np.unique(arr, return_counts=True)
    for v, c in zip(vals, counts):
        if 0 <= v <= 9: h[int(v)] = int(c)
    return h

def best_color_permutation(x: np.ndarray, y: np.ndarray) -> Optional[Dict[int,int]]:
    """
    If x->y mostly just recolors, build a 1-1 mapping by Hungarian assignment
    on histogram L1 distances. Return None if hist mass differs wildly.
    """
    hx, hy = color_hist(x), color_hist(y)
    if hx.sum() != hy.sum():  # different area: likely not pure recolor
        return None
    # small 10x10 cost = |count_x[c] - count_y[d]|, prefer preserve zeros->zeros
    # implement simple Hungarian via scipy-free O(10!) beam (pruned)
    # To keep deterministic and cheap: greedy + refinement
    zero_lock = True
    costs = np.abs(hx[:,None] - hy[None,:]).astype(np.int64)
    # prefer 0->0 if possible
    if zero_lock:
        costs[0, :] += 5
        costs[:, 0] += 5
        costs[0, 0] -= 10
    # greedy match by row minima, breaking ties by column minima
    used_cols = set()
    mapping = {}
    for r in np.argsort(hx)[::-1]:  # largest colors first
        cands = np.argsort(costs[r])
        for c in cands:
            if c not in used_cols:
                mapping[int(r)] = int(c)
                used_cols.add(int(c))
                break
    # ensure 0..9 in domain map to something (identity fallback)
    for k in range(10):
        mapping.setdefault(k, k)
    return mapping

def apply_color_mapping(arr: np.ndarray, mapping: Dict[int,int]) -> np.ndarray:
    out = arr.copy()
    lut = np.arange(10, dtype=out.dtype)
    for k, v in mapping.items():
        if 0 <= k <= 9 and 0 <= v <= 9:
            lut[k] = v
    mask = (out >= 0) & (out <= 9)
    out[mask] = lut[out[mask]]
    return out

def cooccurrence_palette_mapping(train_pairs: List[Tuple[Grid, Grid]]) -> Dict[int,int]:
    """Fallback many-to-one palette mapping learned from train pairs (weak but cheap)."""
    tally: Dict[int, Counter] = {}
    for xg, yg in train_pairs:
        cx = Counter(np.ravel(xg.data).tolist())
        cy = Counter(np.ravel(yg.data).tolist())
        for c in cx.keys():
            row = tally.setdefault(int(c), Counter())
            for d, cnt in cy.items():
                row[int(d)] += int(cnt)
    mapping: Dict[int,int] = {}
    for c, row in tally.items():
        if row: mapping[c] = row.most_common(1)[0][0]
    return mapping

# ---------------------------
# Geometric transforms
# ---------------------------

def mirror_complete(arr: np.ndarray, axis: int) -> np.ndarray:
    h, w = arr.shape
    out = arr.copy()
    if axis == 0:  # horizontal
        top = arr[:h//2, :]
        out[h - top.shape[0]:, :] = top[::-1, :]
    else:         # vertical
        left = arr[:, :w//2]
        out[:, w - left.shape[1]:] = left[:, ::-1]
    return out

def detect_complete_mirror(x: np.ndarray, y: np.ndarray) -> Optional[int]:
    for axis in (0, 1):
        if np.array_equal(mirror_complete(x, axis), y):
            return axis
    return None

def rotations(arr: np.ndarray) -> List[np.ndarray]:
    return [arr, np.rot90(arr, 1), np.rot90(arr, 2), np.rot90(arr, 3)]

def detect_rotation(x: np.ndarray, y: np.ndarray) -> Optional[int]:
    for k, r in enumerate(rotations(x)):
        if r.shape == y.shape and np.array_equal(r, y):
            return k  # 0,1,2,3 quarter turns
    return None

def translate(arr: np.ndarray, dr: int, dc: int) -> np.ndarray:
    h, w = arr.shape
    out = np.zeros_like(arr)
    r0 = max(0, dr); r1 = min(h, h+dr)
    c0 = max(0, dc); c1 = min(w, w+dc)
    src_r0 = max(0, -dr); src_c0 = max(0, -dc)
    src_r1 = src_r0 + (r1 - r0); src_c1 = src_c0 + (c1 - c0)
    if r1 > r0 and c1 > c0:
        out[r0:r1, c0:c1] = arr[src_r0:src_r1, src_c0:src_c1]
    return out

def centroid_of_color(arr: np.ndarray, col: int) -> Optional[Tuple[float,float]]:
    pts = np.argwhere(arr == col)
    if pts.size == 0: return None
    r = float(pts[:,0].mean()); c = float(pts[:,1].mean())
    return (r, c)

def detect_global_translation(x: np.ndarray, y: np.ndarray) -> Optional[Tuple[int,int]]:
    """Try to infer a single (dr,dc) that makes x look like y for dominant colors."""
    cols = [c for c in range(1,10) if (x==c).any() and (y==c).any()]
    if not cols: return None
    drs = []; dcs = []
    for c in cols:
        cx = centroid_of_color(x, c); cy = centroid_of_color(y, c)
        if cx is None or cy is None: continue
        drs.append(int(round(cy[0] - cx[0]))); dcs.append(int(round(cy[1] - cx[1])))
    if not drs: return None
    # if consistent (most common), use it
    dr = Counter(drs).most_common(1)[0][0]
    dc = Counter(dcs).most_common(1)[0][0]
    # light sanity: after translate, palettes match?
    t = translate(x, dr, dc)
    if palette(t) == palette(y):
        return (dr, dc)
    return None

def detect_crop_pad(x: np.ndarray, y: np.ndarray) -> Optional[str]:
    """Return 'crop' or 'pad' if y is plausibly a centered crop/pad of x."""
    if x.shape == y.shape: return None
    hx, wx = x.shape; hy, wy = y.shape
    if hy <= hx and wy <= wx: return "crop"
    if hy >= hx and wy >= wx: return "pad"
    return None

# ---------------------------
# Candidate generation
# ---------------------------

def build_candidates_for_test(train_pairs: List[Tuple[Grid, Grid]], test: Grid) -> List[np.ndarray]:
    xsh = test.data.shape
    out_shape = infer_out_shape_from_train(train_pairs, xsh)
    candidates: List[np.ndarray] = []

    # (0) If any train input matches test shape, copy its paired output
    for xin, yout in train_pairs:
        if xin.data.shape == xsh:
            candidates.append(center_crop_or_pad(yout.data, out_shape))
            break

    # (1) Palette recolor from a same-shape train pair (Hungarian-ish)
    for xin, yout in train_pairs:
        if xin.data.shape == yout.data.shape:
            mp = best_color_permutation(xin.data, yout.data)
            if mp:
                candidates.append(center_crop_or_pad(apply_color_mapping(test.data, mp), out_shape))
            break

    # (2) Co-occurrence palette mapping (weak but general)
    co_map = cooccurrence_palette_mapping(train_pairs)
    if co_map:
        candidates.append(center_crop_or_pad(apply_color_mapping(test.data, co_map), out_shape))

    # (3) Mirror completion if seen in any train pair
    mirror_axis = None
    for xin, yout in train_pairs:
        axis = detect_complete_mirror(xin.data, yout.data)
        if axis is not None:
            mirror_axis = axis; break
    if mirror_axis is not None:
        candidates.append(center_crop_or_pad(mirror_complete(test.data, mirror_axis), out_shape))

    # (4) Rotation if seen in any train pair
    rot_k = None
    for xin, yout in train_pairs:
        k = detect_rotation(xin.data, yout.data)
        if k is not None:
            rot_k = k; break
    if rot_k is not None:
        candidates.append(center_crop_or_pad(np.rot90(test.data, rot_k), out_shape))

    # (5) Global translation if consistent across a pair
    for xin, yout in train_pairs:
        tr = detect_global_translation(xin.data, yout.data)
        if tr is not None:
            candidates.append(center_crop_or_pad(translate(test.data, *tr), out_shape))
            break

    # (6) Crop/pad transform if observed
    for xin, yout in train_pairs:
        cp = detect_crop_pad(xin.data, yout.data)
        if cp == "crop":
            candidates.append(center_crop_or_pad(test.data, out_shape))
            break
        elif cp == "pad":
            candidates.append(center_crop_or_pad(test.data, out_shape))
            break

    # (7) Majority fill (last-resort safe guess)
    fill = majority_nonzero_color([y.data for _, y in train_pairs])
    if fill is not None:
        candidates.append(np.full(out_shape, fill, dtype=test.data.dtype))

    # Always include identity reshaped to out_shape to avoid empties
    candidates.append(center_crop_or_pad(test.data, out_shape))

    # De-duplicate by content
    uniq: List[np.ndarray] = []
    seen = set()
    for a in candidates:
        key = (a.shape, tuple(np.ravel(a[:8,:8])) )  # cheap hash
        if key not in seen:
            uniq.append(a)
            seen.add(key)
    return uniq

# ---------------------------
# Candidate scoring & selection
# ---------------------------

def plausibility_score(candidate: np.ndarray,
                       train_pairs: List[Tuple[Grid, Grid]]) -> float:
    """
    Score with lightweight priors:
      + palette similarity to train outputs
      + border contact (often true)
      - over-sparsity penalty
      - size deviation penalty (already handled via center_crop_or_pad)
    """
    # target palettes from train outputs
    outs = [y.data for _, y in train_pairs]
    pal_target = Counter([palette(y) for y in outs]).most_common(1)[0][0]
    score = 0.0

    # palette overlap
    pal_c = set(palette(candidate))
    pal_t = set().union(*[set(p) for p in [pal_target]])
    inter = len(pal_c.intersection(pal_t))
    score += 1.0 * inter

    # border contact bonus
    h, w = candidate.shape
    border = np.r_[candidate[0,:], candidate[-1,:], candidate[:,0], candidate[:,-1]]
    if (border != 0).any():
        score += 0.5

    # sparsity penalty (reward some activity)
    nnz = nonzero_count(candidate)
    area = h * w
    if nnz == 0:
        score -= 2.0
    else:
        dens = nnz / max(1, area)
        if dens < 0.02: score -= 0.5

    return float(score)

def pick_top2(cands: List[np.ndarray], train_pairs: List[Tuple[Grid, Grid]]) -> List[np.ndarray]:
    if not cands:
        return [np.zeros((1,1), dtype=np.int8)]*2
    scored = [(plausibility_score(c, train_pairs), i, c) for i,c in enumerate(cands)]
    scored.sort(key=lambda x: x[0], reverse=True)
    top1 = scored[0][2]
    # choose second that is both high-score and different from first
    for _,_,c in scored[1:]:
        if not np.array_equal(c, top1):
            return [top1, c]
    return [top1, top1]

# ---------------------------
# Public API
# ---------------------------

def heuristics_two_attempts(train_pairs: List[Tuple[Grid, Grid]],
                            tests: List[Grid]) -> List[List[Grid]]:
    outs: List[List[Grid]] = []
    for t in tests:
        cands = build_candidates_for_test(train_pairs, t)
        best2 = pick_top2(cands, train_pairs)
        outs.append([Grid(best2[0]), Grid(best2[1])])
    return outs
