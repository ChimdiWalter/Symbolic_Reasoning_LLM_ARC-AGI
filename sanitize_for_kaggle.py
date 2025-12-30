# sanitize_for_kaggle.py
from __future__ import annotations
import json, sys
from typing import Dict, Any, List, Tuple
import numpy as np
import os

CH_PATH = "data/challenges_eval.json"     # ground-truth structure for eval split
IN_PATH = "submission_eval.json"          # your current predictions
OUT_PATH = "submission.json"              # Kaggle-mandated name

def _to_np_grid(x: Any) -> np.ndarray:
    """Coerce nested list to 2D int array, clip to [0..9]."""
    a = np.array(x, dtype=int)
    if a.ndim != 2:
        # if flat or weird → make at least 1xN
        a = a.reshape(-1, a.size)
    a = np.clip(a, 0, 9)
    return a

def _zeros(h: int, w: int) -> np.ndarray:
    return np.zeros((h, w), dtype=int)

def _resize_crop_pad(a: np.ndarray, shape: Tuple[int,int]) -> np.ndarray:
    """Center-crop or center-pad with zeros to match shape."""
    H, W = shape
    h, w = a.shape
    out = np.zeros((H, W), dtype=int)
    ih = min(H, h); iw = min(W, w)
    src_r0 = (h - ih)//2; src_c0 = (w - iw)//2
    dst_r0 = (H - ih)//2; dst_c0 = (W - iw)//2
    out[dst_r0:dst_r0+ih, dst_c0:dst_c0+iw] = a[src_r0:src_r0+ih, src_c0:src_c0+iw]
    return out

def _ensure_two(a_list: List[np.ndarray], H: int, W: int) -> Tuple[np.ndarray, np.ndarray]:
    """Return exactly two arrays, padding/dup as needed."""
    if not a_list:
        z = _zeros(H, W)
        return z, z
    if len(a_list) == 1:
        a = _resize_crop_pad(a_list[0], (H, W))
        return a, a
    a1 = _resize_crop_pad(a_list[0], (H, W))
    a2 = _resize_crop_pad(a_list[1], (H, W))
    return a1, a2

def main():
    # load ground-structure (public eval)
    chall = json.load(open(CH_PATH))
    # your raw predictions
    raw_pred: Dict[str, Any] = json.load(open(IN_PATH))

    fixed: Dict[str, Any] = {}
    missing_tasks = 0
    fixed_counts = {"len_mismatch":0, "reshape":0, "clipped":0}

    for tid, spec in chall.items():
        tests = spec.get("test", [])
        n_tests = len(tests)

        # pull guesses for this task
        g_list = raw_pred.get(tid, [])
        if not isinstance(g_list, list):
            g_list = []
        # adjust length: if fewer guesses, append blanks; if more, truncate
        if len(g_list) != n_tests:
            fixed_counts["len_mismatch"] += 1
        if len(g_list) < n_tests:
            g_list = g_list + [{} for _ in range(n_tests - len(g_list))]
        if len(g_list) > n_tests:
            g_list = g_list[:n_tests]

        per_task_out: List[Dict[str, List[List[int]]]] = []
        for i, t in enumerate(tests):
            H, W = np.array(t["input"], dtype=int).shape

            cand: List[np.ndarray] = []
            gi = g_list[i] if i < len(g_list) and isinstance(g_list[i], dict) else {}

            for key in ("attempt_1", "attempt_2"):
                if key in gi:
                    try:
                        arr = _to_np_grid(gi[key])
                    except Exception:
                        continue
                    # track clips (roughly) by checking range
                    if arr.min() < 0 or arr.max() > 9:
                        fixed_counts["clipped"] += 1
                    cand.append(arr)

            a1, a2 = _ensure_two(cand, H, W)
            # count reshape if shapes differ from provided
            if (cand and (cand[0].shape != (H,W))) or (len(cand) > 1 and cand[1].shape != (H,W)):
                fixed_counts["reshape"] += 1

            per_task_out.append({
                "attempt_1": a1.astype(int).tolist(),
                "attempt_2": a2.astype(int).tolist(),
            })
        fixed[tid] = per_task_out

    # Write Kaggle-ready file
    with open(OUT_PATH, "w") as f:
        json.dump(fixed, f)
    print(f"[OK] Wrote {OUT_PATH} with {len(fixed)} tasks")
    print("Fix summary:", fixed_counts)

if __name__ == "__main__":
    main()
