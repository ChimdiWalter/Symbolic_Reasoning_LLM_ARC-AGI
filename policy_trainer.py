# policy_trainer.py
from __future__ import annotations
import json, math, os
from typing import Dict, List, Tuple
import numpy as np

OPS = [
    "rot0","rot90","rot180","rot270",
    "flip_lr","flip_ud",
    "mirror_h","mirror_v",         # completion-like hints
    "translate",                   # any delta
    "size_change",                 # HxW differs
    "palette_perm"                 # color permutation evident
]

def _hist10(a: np.ndarray) -> np.ndarray:
    h = np.bincount(a.reshape(-1), minlength=10).astype(np.float32)
    s = h.sum() or 1.0
    return h/s

def _bbox(a: np.ndarray):
    nz = np.argwhere(a!=0)
    if len(nz)==0: return 0,0,-1,-1
    r0,c0 = nz.min(0); r1,c1 = nz.max(0)
    return int(r0),int(c0),int(r1),int(c1)

def _rot(a: np.ndarray, k: int) -> np.ndarray:
    if k%4==0: return a
    return np.rot90(a, k%4)

def _flip_lr(a: np.ndarray) -> np.ndarray:
    return np.fliplr(a)

def _flip_ud(a: np.ndarray) -> np.ndarray:
    return np.flipud(a)

def _maybe_mirror(a: np.ndarray, axis: int) -> np.ndarray:
    # axis 0: horizontal mirror completion; axis 1: vertical
    h,w = a.shape
    out = a.copy()
    if axis==0:
        top = a[:h//2,:]
        out[h-top.shape[0]:,:] = top[::-1,:]
    else:
        left = a[:,:w//2]
        out[:,w-left.shape[1]:] = left[:,::-1]
    return out

def _centroid(a: np.ndarray):
    pts = np.argwhere(a!=0)
    if len(pts)==0: return (0.0,0.0)
    return (float(pts[:,0].mean()), float(pts[:,1].mean()))

def _labels_for_pair(x: np.ndarray, y: np.ndarray) -> Dict[str,int]:
    lab = {k:0 for k in OPS}
    # rotations
    if np.array_equal(_rot(x,0),y):   lab["rot0"]=1
    if np.array_equal(_rot(x,1),y):   lab["rot90"]=1
    if np.array_equal(_rot(x,2),y):   lab["rot180"]=1
    if np.array_equal(_rot(x,3),y):   lab["rot270"]=1
    # flips
    if np.array_equal(_flip_lr(x),y): lab["flip_lr"]=1
    if np.array_equal(_flip_ud(x),y): lab["flip_ud"]=1
    # mirror completion
    if np.array_equal(_maybe_mirror(x,0),y): lab["mirror_h"]=1
    if np.array_equal(_maybe_mirror(x,1),y): lab["mirror_v"]=1
    # translation (centroid moves)
    cx,cy = _centroid(x); ux,uy = _centroid(y)
    if abs((ux-cx)) + abs((uy-cy)) >= 1.0: lab["translate"]=1
    # size change
    if x.shape != y.shape: lab["size_change"]=1
    # palette change
    if not np.array_equal(np.unique(x), np.unique(y)): lab["palette_perm"]=1
    return lab

def train_policy_npz(train_json: str, out_npz: str):
    data = json.load(open(train_json))
    # Count over all train pairs
    cnt = {k:0 for k in OPS}; tot = 0
    for _, spec in data.items():
        for pr in spec["train"]:
            x = np.array(pr["input"], dtype=int)
            y = np.array(pr["output"], dtype=int)
            labs = _labels_for_pair(x,y)
            for k,v in labs.items(): cnt[k] += int(v)
            tot += 1
    # Convert to log-odds with Laplace smoothing
    # p = (c+1)/(tot+2); weight = log(p/(1-p))
    weights = {}
    for k in OPS:
        p = (cnt[k] + 1.0) / (tot + 2.0)
        odds = p / max(1e-6, 1.0 - p)
        weights[k] = float(math.log(odds))
    np.savez(out_npz, **weights)
    print("Saved", out_npz)
    for k in OPS:
        v = weights[k]
        s = "+" if v>=0 else ""
        print(f"{k:12s}: {s}{v:.3f}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True, help="arc-agi_training_challenges.json")
    ap.add_argument("--out",   required=True, help="policy.npz")
    args = ap.parse_args()
    train_policy_npz(args.train, args.out)
