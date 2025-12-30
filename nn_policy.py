# nn_policy.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import numpy as np

# ------------- Feature extractor -------------

def _palette_hist(a: np.ndarray, k: int = 10) -> np.ndarray:
    h = np.bincount(a.ravel(), minlength=k)[:k].astype(np.float32)
    s = float(h.sum()) or 1.0
    return h / s

def _bbox(a: np.ndarray) -> Tuple[int,int,int,int]:
    ys, xs = np.where(a != 0)
    if ys.size == 0: 
        return 0, 0, 0, 0
    r0, r1 = int(ys.min()), int(ys.max())
    c0, c1 = int(xs.min()), int(xs.max())
    return r0, r1, c0, c1

def _centroid(a: np.ndarray) -> Tuple[float,float]:
    ys, xs = np.where(a != 0)
    if ys.size == 0:
        return 0.0, 0.0
    return float(ys.mean()), float(xs.mean())

def fe_task_pair(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Features describing a single (x,y) mapping."""
    Hx, Wx = x.shape
    Hy, Wy = y.shape
    pX = _palette_hist(x); pY = _palette_hist(y)
    r0x,r1x,c0x,c1x = _bbox(x); r0y,r1y,c0y,c1y = _bbox(y)
    cx, cy = _centroid(x), _centroid(y)

    fx = np.array([
        Hx/30.0, Wx/30.0, Hy/30.0, Wy/30.0,
        (r1x-r0x+1)/max(1,Hx), (c1x-c0x+1)/max(1,Wx),
        (r1y-r0y+1)/max(1,Hy), (c1y-c0y+1)/max(1,Wy),
        (cy[0]-cx[0])/30.0, (cy[1]-cx[1])/30.0,
        int(Hx==Hy), int(Wx==Wy),
        int(Hy*Wy > Hx*Wx),
        int(Hy*Wy < Hx*Wx),
    ], dtype=np.float32)

    return np.concatenate([fx, pX, pY], axis=0)  # ~ (15 + 10 + 10) = 35-dim

def fe_task_summary(train_pairs: List[Tuple[np.ndarray,np.ndarray]]) -> np.ndarray:
    """Aggregate features over all (x,y) pairs in the task."""
    if not train_pairs:
        return np.zeros(35, np.float32)
    Fs = [fe_task_pair(x,y) for (x,y) in train_pairs]
    F = np.stack(Fs, 0)
    # mean, std, min, max pooled:
    feats = np.concatenate([F.mean(0), F.std(0), F.min(0), F.max(0)], axis=0)
    return feats.astype(np.float32)  # 35*4 = 140 dims

# ------------- Tiny linear model -------------

def score_families(feats: np.ndarray, families: List[str], W: Optional[np.ndarray]) -> Dict[str, float]:
    """
    feats: (140,)
    W:    (D, C) or None; C=len(families)
    Returns name->score (higher is better).
    """
    # deterministic baseline if no weights
    base = {name: 0.0 for name in families}
    if W is None:
        return base

    D = feats.shape[0]
    C = len(families)
    W = np.array(W)
    if W.ndim == 1:
        # allow a single weight vector, same score for all families
        s = float(np.dot(feats, W[:D]))
        return {name: s for name in families}
    # matrix case
    W = W[:D, :C]
    s = feats @ W  # (C,)
    out = {}
    for i, name in enumerate(families):
        out[name] = float(s[i])
    return out

def load_nn_policy(path: Optional[str]) -> Optional[np.ndarray]:
    if not path:
        return None
    import os
    if not os.path.exists(path):
        return None
    dat = np.load(path, allow_pickle=True)
    if "W" in dat:
        return dat["W"]
    # fallback to any array
    for k in dat.files:
        try:
            return np.array(dat[k])
        except Exception:
            continue
    return None
