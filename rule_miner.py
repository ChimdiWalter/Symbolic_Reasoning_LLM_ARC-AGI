# rule_miner.py
from __future__ import annotations
from typing import List, Tuple, Optional, Dict
import numpy as np

from components import Grid
from size_infer import choose_size_rule

# ---------- low-level transforms ----------
def rot90(a):  return np.rot90(a, 1)
def rot180(a): return np.rot90(a, 2)
def rot270(a): return np.rot90(a, 3)
def flip_h(a): return np.flipud(a)
def flip_v(a): return np.fliplr(a)

def translate(a: np.ndarray, dr: int, dc: int, H: int, W: int) -> np.ndarray:
    """Place `a` into an HxW canvas shifted by (dr,dc), cropping at borders."""
    out = np.zeros((H, W), dtype=a.dtype)
    h, w = a.shape
    r0 = max(0, dr)
    c0 = max(0, dc)
    r1 = min(H, dr + h)
    c1 = min(W, dc + w)
    if r0 >= r1 or c0 >= c1:
        return out
    src_r0 = max(0, -dr)
    src_c0 = max(0, -dc)
    src_r1 = src_r0 + (r1 - r0)
    src_c1 = src_c0 + (c1 - c0)
    out[r0:r1, c0:c1] = a[src_r0:src_r1, src_c0:src_c1]
    return out

def enforce_shape(a: np.ndarray, shape: Tuple[int,int]) -> np.ndarray:
    """Center crop or zero-pad to exact shape (H,W)."""
    H, W = shape
    h, w = a.shape
    out = np.zeros((H, W), dtype=a.dtype)
    ih = min(H, h); iw = min(W, w)
    src_r0 = (h - ih)//2
    src_c0 = (w - iw)//2
    dst_r0 = (H - ih)//2
    dst_c0 = (W - iw)//2
    out[dst_r0:dst_r0+ih, dst_c0:dst_c0+iw] = a[src_r0:src_r0+ih, src_c0:src_c0+iw]
    return out

def pix_loss(a: np.ndarray, b: np.ndarray) -> int:
    """Hamming loss (pixel mismatch count); shapes must match."""
    if a.shape != b.shape:
        return 10**9
    return int((a != b).sum())

# ---------- palette mapping ----------
def palette_map_lut(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """
    Build a 10-entry LUT mapping input colors to output colors based on co-occurrence.
    If ambiguous/missing, default to identity for that entry.
    """
    lut = np.arange(10, dtype=np.int8)
    # co-occurrence vote: when c appears in src, all dst pixels vote for mapping to d
    votes = [np.zeros(10, dtype=np.int32) for _ in range(10)]
    src_cols = set(np.unique(src).tolist())
    for c in src_cols:
        if c < 0 or c > 9: continue
        # count dst distribution when src had color c (simple heuristic)
        # weight by dst frequencies
        vals, cnts = np.unique(dst, return_counts=True)
        for d, k in zip(vals, cnts):
            if 0 <= d <= 9:
                votes[c][d] += int(k)
    for c in range(10):
        if votes[c].sum() > 0:
            lut[c] = np.argmax(votes[c])
        else:
            lut[c] = c
    return lut

def apply_lut(a: np.ndarray, lut: np.ndarray) -> np.ndarray:
    out = a.copy()
    mask = (out >= 0) & (out <= 9)
    out[mask] = lut[out[mask]]
    return out

# ---------- policy re-rank ----------
def _feat_score(transform_name: str, dr: int, dc: int, use_palette: bool,
                target_shape, src_shape, priors: Optional[Dict[str, float]]) -> float:
    if not priors: return 0.0
    w = lambda k: float(priors.get(k, 0.0))
    score = 0.0

    # rotations / flips / mirror axes
    if transform_name in ("rot90","rot180","rot270"):
        score += w("rot_match")
    if transform_name in ("flip_h","flip_v","flip_h_rot90","flip_v_rot90"):
        score += w("flip_match")
    if transform_name == "flip_h":
        score += w("mirror_axis0")
    if transform_name == "flip_v":
        score += w("mirror_axis1")

    # palette usage
    if use_palette:
        score += w("palette_perm")

    # size_change
    if target_shape != src_shape:
        score += w("size_changed")

    # centroid-like shift
    if dr != 0 or dc != 0:
        score += w("centroid_shift")

    # border-touch heuristic: big shifts relative to size
    H, W = target_shape
    if abs(dr) >= max(1, H//3) or abs(dc) >= max(1, W//3):
        score += w("border_touch_out")

    return score

# ---------- main miner ----------
def infer_two_attempts(train_pairs: List[Tuple[Grid, Grid]],
                       tests: List[Grid],
                       policy: Optional[Dict[str, float]] = None) -> List[List[Grid]]:
    """
    Produce two attempts per test:
      Attempt 1: best geom(rotate/flip)+translate + palette LUT at inferred target size
      Attempt 2: palette-only at inferred target size
    Shapes are enforced, outputs non-trivial if possible.
    """
    # choose size transform (name, fn(H,W)->(H2,W2)), allowing small policy nudges
    size_name, size_fn = choose_size_rule(train_pairs, priors=policy)

    # learn palette LUT from a same-shape pair if available
    lut = None
    for x, y in train_pairs:
        if x.data.shape == y.data.shape:
            lut = palette_map_lut(x.data, y.data)
            break
    if lut is None:
        lut = np.arange(10, dtype=np.int8)

    # pick geom+translation using train pairs with policy-biased score
    best_geom = None  # (score, loss, (dr,dc), ref_shape, name)
    trans = range(-3, 4)
    geom_generators = [
        ("id",         lambda a: a),
        ("rot90",      rot90),
        ("rot180",     rot180),
        ("rot270",     rot270),
        ("flip_h",     flip_h),
        ("flip_v",     flip_v),
        ("flip_h_rot90", lambda a: flip_h(rot90(a))),
        ("flip_v_rot90", lambda a: flip_v(rot90(a))),
    ]

    for xin, yout in train_pairs:
        Ht, Wt = yout.data.shape
        for name, gen in geom_generators:
            g = gen(xin.data)
            for dr in trans:
                for dc in trans:
                    cand = translate(g, dr, dc, Ht, Wt)
                    loss = pix_loss(apply_lut(cand, lut), yout.data)
                    pol = _feat_score(name, dr, dc, True, (Ht, Wt), xin.data.shape, policy)
                    score = -float(loss) + pol
                    if (best_geom is None) or (score > best_geom[0]):
                        best_geom = (score, loss, (dr, dc), g.shape, name)

    outs: List[List[Grid]] = []
    for t in tests:
        H, W = size_fn(*t.data.shape)

        # Attempt 1: apply the best train-estimated D4+translate with palette at target size
        if best_geom is not None:
            _, _, (dr, dc), ref_shape, gname = best_geom
            # choose the D4 element on test that matches learned ref shape
            chosen = None
            for name, gen in geom_generators:
                g = gen(t.data)
                if g.shape == ref_shape:
                    chosen = g; chosen_name = name; break
            if chosen is None:
                chosen = t.data; chosen_name = "id"
            a1 = apply_lut(translate(chosen, dr, dc, H, W), lut)
        else:
            a1 = apply_lut(enforce_shape(t.data, (H, W)), lut)

        # Attempt 2: palette-only, size-enforced
        a2 = apply_lut(enforce_shape(t.data, (H, W)), lut)

        # avoid both-zero if we can
        if (a1 != 0).sum() == 0 and (a2 != 0).sum() > 0:
            a1, a2 = a2, a1

        outs.append([Grid(a1), Grid(a2)])
    return outs
