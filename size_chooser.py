# size_chooser.py
from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np

Arr = np.ndarray
PairNP = List[Tuple[Arr, Arr]]

def _l0(a: Arr, b: Arr) -> int:
    if a.shape != b.shape:
        return 10_000_000  # huge penalty for wrong size
    return int((a != b).sum())

def propose_from_train_outputs(train_pairs: PairNP) -> List[Tuple[int,int]]:
    shapes = {}
    for _, y in train_pairs:
        s = tuple(y.shape)
        shapes[s] = shapes.get(s, 0) + 1
    # sort by frequency desc, then area asc
    return sorted(shapes.keys(), key=lambda s: (-shapes[s], s[0]*s[1]))

def propose_from_input_shapes(train_pairs: PairNP) -> List[Tuple[int,int]]:
    shapes = {}
    for x, _ in train_pairs:
        s = tuple(x.shape)
        shapes[s] = shapes.get(s, 0) + 1
    return sorted(shapes.keys(), key=lambda s: (-shapes[s], s[0]*s[1]))

def propose_from_bboxes(train_pairs: PairNP) -> List[Tuple[int,int]]:
    def bbox_grid(a: Arr):
        rr, cc = np.where(a != 0)
        if len(rr) == 0: return (1,1)
        return (int(rr.max()-rr.min()+1), int(cc.max()-cc.min()+1))
    shapes = set()
    for x, y in train_pairs:
        bx = bbox_grid(x); by = bbox_grid(y)
        # include both; ARC often preserves or slightly grows bbox
        shapes.add(by); shapes.add(bx)
        # loose expansions up to +2 in each dir
        for dh in (0,1,2):
            for dw in (0,1,2):
                shapes.add((max(1, by[0]+dh), max(1, by[1]+dw)))
    # sort by area asc to try small canvases first
    return sorted(shapes, key=lambda s: (s[0]*s[1], s[0], s[1]))

def propose_size_candidates(train_pairs: PairNP) -> List[Tuple[int,int]]:
    # Union with dedupe, preferring |train y|, then bbox, then |train x|
    ys = propose_from_train_outputs(train_pairs)
    bb = propose_from_bboxes(train_pairs)
    xs = propose_from_input_shapes(train_pairs)
    seen = set()
    out: List[Tuple[int,int]] = []
    for src in (ys, bb, xs):
        for s in src:
            if s not in seen:
                seen.add(s); out.append(s)
    # final safeties
    if (30,30) not in seen: out.append((30,30))
    return out

def pick_best_size_by_train(rule_apply_fn,
                            train_pairs: PairNP,
                            candidates: List[Tuple[int,int]],
                            max_try: int = 12) -> Tuple[int,int]:
    """Evaluate each size by re-predicting train and minimizing L0."""
    best = None
    best_err = 10_000_000
    tried = 0
    for H,W in candidates:
        tried += 1
        if tried > max_try: break
        err = 0
        for x, y in train_pairs:
            yhat = rule_apply_fn(x, (H, W))
            err += _l0(yhat, y)
            if err >= best_err: break  # prune
        if err < best_err:
            best_err = err; best = (H, W)
            if best_err == 0: break
    return best if best is not None else candidates[0]
