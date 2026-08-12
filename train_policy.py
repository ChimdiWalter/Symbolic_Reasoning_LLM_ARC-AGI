# train_policy.py
from __future__ import annotations
import json, argparse, math
from typing import Dict, List, Tuple
import numpy as np

# --- Helpers ---------------------------------------------------------------

def _arr(x):
    return np.array(x, dtype=np.int16)

def _palette(a: np.ndarray) -> tuple:
    return tuple(int(v) for v in np.unique(a))

def _centroid(a: np.ndarray) -> Tuple[float,float]:
    # centroid of nonzero pixels; if none, fall back to overall center
    ys, xs = np.where(a != 0)
    if len(ys) == 0:
        h, w = a.shape
        return ((h-1)/2.0, (w-1)/2.0)
    return (float(ys.mean()), float(xs.mean()))

def _maybe_mirror(a: np.ndarray, axis: int) -> np.ndarray:
    h, w = a.shape
    out = a.copy()
    if axis == 0:  # horizontal complete
        top = a[:h//2, :]
        out[h - top.shape[0]:, :] = top[::-1, :]
    else:         # vertical complete
        left = a[:, :w//2]
        out[:, w - left.shape[1]:] = left[:, ::-1]
    return out

def _detect_complete_mirror(x: np.ndarray, y: np.ndarray) -> int | None:
    for axis in (0,1):
        if np.array_equal(_maybe_mirror(x, axis), y):
            return axis
    return None

def _rot90_k(a: np.ndarray, k: int) -> np.ndarray:
    return np.rot90(a, k=k)

def _any_rot_match(x: np.ndarray, y: np.ndarray) -> bool:
    if x.shape != y.shape: return False
    for k in (1,2,3):
        if np.array_equal(_rot90_k(x,k), y): return True
    return False

def _flip_match(x: np.ndarray, y: np.ndarray) -> bool:
    if x.shape != y.shape: return False
    return np.array_equal(np.flipud(x), y) or np.array_equal(np.fliplr(x), y)

def _size_changed(x: np.ndarray, y: np.ndarray) -> bool:
    return x.shape != y.shape

def _palette_permutation(x: np.ndarray, y: np.ndarray) -> bool:
    # True if y's palette is a permutation subset/superset of x's palette
    px, py = set(_palette(x)), set(_palette(y))
    return (py == px) or (py.issubset(px)) or (px.issubset(py))

def _border_touch(a: np.ndarray) -> bool:
    return ((a[0,:]!=0).any() or (a[-1,:]!=0).any() or
            (a[:,0]!=0).any() or (a[:,-1]!=0).any())

def _outline_like(x: np.ndarray, y: np.ndarray) -> bool:
    # crude: y equals x OR x with a 1px dilation/outline around nonzero
    if x.shape != y.shape: return False
    if np.array_equal(x,y): return True
    h,w = x.shape
    out = x.copy()
    for r in range(h):
        for c in range(w):
            if x[r,c]!=0:
                for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                    rr,cc=r+dr,c+dc
                    if 0<=rr<h and 0<=cc<w and out[rr,cc]==0:
                        out[rr,cc]=x[r,c]
    return np.array_equal(out, y)

# --- Feature extraction from one (x,y) pair --------------------------------

FEATURES = [
    "mirror_axis0",            # complete horizontal mirror
    "mirror_axis1",            # complete vertical mirror
    "flip_match",              # simple flip (ud or lr)
    "rot_match",               # 90/180/270 rotation match
    "size_changed",            # output shape differs
    "palette_perm",            # palette permutation/containment
    "centroid_shift",          # nonzero centroid moved
    "border_touch_out",        # output touches border
    "outline_like",            # crude outline/dilation
]

def features_from_pair(x: np.ndarray, y: np.ndarray) -> Dict[str, int]:
    fx: Dict[str,int] = {k:0 for k in FEATURES}
    axis = _detect_complete_mirror(x, y)
    if axis == 0: fx["mirror_axis0"]=1
    if axis == 1: fx["mirror_axis1"]=1
    if _flip_match(x, y): fx["flip_match"]=1
    if _any_rot_match(x, y): fx["rot_match"]=1
    if _size_changed(x, y): fx["size_changed"]=1
    if _palette_permutation(x, y): fx["palette_perm"]=1
    c1, c2 = _centroid(x), _centroid(y)
    if abs(c1[0]-c2[0])>=0.5 or abs(c1[1]-c2[1])>=0.5: fx["centroid_shift"]=1
    if _border_touch(y): fx["border_touch_out"]=1
    if _outline_like(x, y): fx["outline_like"]=1
    return fx

# --- Aggregate per task ----------------------------------------------------

def aggregate_task_features(pairs: List[Tuple[np.ndarray,np.ndarray]]) -> Dict[str,float]:
    agg = {k:0 for k in FEATURES}
    n = max(1,len(pairs))
    for x,y in pairs:
        f = features_from_pair(x,y)
        for k,v in f.items():
            agg[k] += v
    # normalize to [0,1] by count of train pairs
    for k in agg:
        agg[k] = agg[k] / float(n)
    return agg

# --- Training: compute weights as log-odds ---------------------------------

def logit(p: float, eps=1e-3) -> float:
    p = min(max(p, eps), 1.0-eps)
    return math.log(p/(1.0-p))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True, help="arc-agi_training_challenges.json")
    ap.add_argument("--solutions", required=True, help="arc-agi_training_solutions.json")
    ap.add_argument("--out", default="policy_weights.npz")
    args = ap.parse_args()

    # Load train+solutions
    train = json.load(open(args.train, "r"))
    sols  = json.load(open(args.solutions, "r"))

    # For each task, aggregate features from *train* pairs
    # (We avoid peeking at ground-truth test outputs to stay honest)
    rows = []
    for tid, spec in train.items():
        pairs = []
        for pr in spec.get("train", []):
            x = _arr(pr["input"]); y = _arr(pr["output"])
            pairs.append((x,y))
        if not pairs: continue
        rows.append(aggregate_task_features(pairs))

    # Compute global probabilities per feature
    feat_means = {k:0.0 for k in FEATURES}
    for r in rows:
        for k,v in r.items():
            feat_means[k] += v
    n = max(1,len(rows))
    for k in feat_means:
        feat_means[k] /= float(n)

    # Convert to log-odds weights (centered)
    weights = np.zeros(len(FEATURES), dtype=np.float32)
    for i,k in enumerate(FEATURES):
        p = float(feat_means[k])
        weights[i] = logit(p)  # positive if more common than not

    np.savez_compressed(args.out,
        feature_names=np.array(FEATURES, dtype=object),
        weights=weights,
        bias=np.float32(0.0)
    )
    print("Saved", args.out)
    for k,w in zip(FEATURES, weights):
        print(f"{k:18s}: {w:+.3f}")

if __name__ == "__main__":
    main()
