# size_infer.py
from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
from collections import Counter

Shape = Tuple[int, int]

def _mode(shapes: List[Shape]) -> Shape:
    return Counter(shapes).most_common(1)[0][0]

def _median_shape(shapes: List[Shape]) -> Shape:
    H = int(np.median([h for h, _ in shapes]))
    W = int(np.median([w for _, w in shapes]))
    return (max(1, min(30, H)), max(1, min(30, W)))

def _mean_shape(shapes: List[Shape]) -> Shape:
    H = int(round(float(np.mean([h for h, _ in shapes]))))
    W = int(round(float(np.mean([w for _, w in shapes]))))
    return (max(1, min(30, H)), max(1, min(30, W)))

def _clamp_shape(hw: Shape) -> Shape:
    h, w = hw
    return (max(1, min(30, int(h))), max(1, min(30, int(w))))

def _union_bbox_shape(arr: np.ndarray) -> Shape:
    """Tight box around all nonzero pixels. If none, return arr.shape."""
    nz = np.argwhere(arr != 0)
    if nz.size == 0:
        return arr.shape
    (r0, c0) = nz.min(0)
    (r1, c1) = nz.max(0)
    return (int(r1 - r0 + 1), int(c1 - c0 + 1))

def propose_size_candidates(train_pairs_np: List[Tuple[np.ndarray, np.ndarray]],
                            max_k: int = 3) -> List[Shape]:
    """
    Return up to `max_k` plausible output sizes:
      1) mode of train Y shapes
      2) median of train Y shapes (if different)
      3) union-bbox over Y (or over X if Y is empty), or mean shape
    Always clamped to [1..30].
    """
    if not train_pairs_np:
        return []

    y_shapes = [y.shape for (_, y) in train_pairs_np]
    cand: List[Shape] = []

    # 1) mode
    cand.append(_clamp_shape(_mode(y_shapes)))

    # 2) median (if different)
    med = _clamp_shape(_median_shape(y_shapes))
    if med not in cand:
        cand.append(med)

    # 3) union / mean backup
    # Build a union bbox of Y; if every Y is empty, fallback to union over X
    any_nz = any((y != 0).any() for (_, y) in train_pairs_np)
    if any_nz:
        # approximate: merge bboxes by max(h), max(w) of each y’s bbox
        boxes = [_union_bbox_shape(y) for (_, y) in train_pairs_np]
    else:
        boxes = [_union_bbox_shape(x) for (x, _) in train_pairs_np]
    uni = _clamp_shape((max(h for h, _ in boxes), max(w for _, w in boxes)))
    if uni not in cand:
        cand.append(uni)

    # If still short, try mean
    if len(cand) < max_k:
        mean = _clamp_shape(_mean_shape(y_shapes))
        if mean not in cand:
            cand.append(mean)

    # Trim
    return cand[:max_k]
