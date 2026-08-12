# component_mapper.py
from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import numpy as np
from collections import defaultdict

# ---------- basic CC ----------

def _cc_label(arr: np.ndarray) -> Tuple[np.ndarray, int]:
    H, W = arr.shape
    lab = -np.ones((H, W), dtype=np.int32)
    cid = 0
    for r in range(H):
        for c in range(W):
            if arr[r, c] != 0 and lab[r, c] < 0:
                # flood fill 4-neigh
                q = [(r, c)]
                lab[r, c] = cid
                while q:
                    rr, cc = q.pop()
                    for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
                        nr, nc = rr+dr, cc+dc
                        if 0 <= nr < H and 0 <= nc < W and arr[nr, nc] != 0 and lab[nr, nc] < 0:
                            lab[nr, nc] = cid
                            q.append((nr, nc))
                cid += 1
    return lab, cid

def extract_components(arr: np.ndarray) -> List[Dict]:
    lab, K = _cc_label(arr)
    comps = []
    for k in range(K):
        ys, xs = np.where(lab == k)
        if ys.size == 0: 
            continue
        color_counts = defaultdict(int)
        for y, x in zip(ys, xs):
            color_counts[int(arr[y, x])] += 1
        # dominant color for signature
        dom = max(color_counts.items(), key=lambda t: t[1])[0]
        comps.append({
            "id": k,
            "pixels": np.stack([ys, xs], axis=1),  # N x 2
            "centroid": (float(ys.mean()), float(xs.mean())),
            "size": int(ys.size),
            "dominant": dom,
        })
    return comps

# ---------- Hungarian (rectangular, handles n<=m and n>m by padding) ----------

def hungarian(cost: np.ndarray) -> Tuple[List[Tuple[int,int]], float]:
    """
    Simple Hungarian for rectangular costs. Returns list of (i,j) assignments and total cost.
    Pads to square with large penalties.
    """
    C = np.array(cost, float)
    n, m = C.shape
    N = max(n, m)
    big = C.max() + 1e6
    P = np.full((N, N), big, float)
    P[:n, :m] = C

    # Hungarian (Kuhn-Munkres) — minimalistic
    u = np.zeros(N)
    v = np.zeros(N)
    p = np.full(N, -1, int)
    way = np.full(N, -1, int)

    for i in range(N):
        p[0] = i
        j0 = 0
        minv = np.full(N, 1e18, float)
        used = np.zeros(N, bool)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = 1e18
            j1 = 0
            for j in range(1, N):
                if not used[j]:
                    cur = P[i0, j] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(N):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == -1:
                break
        # augmenting
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    # p[j]=i (matching column->row)
    match = [(-1, -1)]
    total = 0.0
    result = []
    for j in range(1, N):
        i = p[j]
        if i >= 0 and i < n and j < m:
            result.append((i, j))
            total += C[i, j]
    return result, float(total)

# ---------- per-component rule learning ----------

def learn_component_rule(x: np.ndarray, y: np.ndarray) -> Optional[Dict]:
    """
    Learn per-component mapping: for each CC in x, assign to a CC in y,
    with a translation (Δr,Δc) and color-recolor "dominant->dominant".
    Returns dict with assignments & recolor map.
    """
    cx = extract_components(x)
    cy = extract_components(y)
    if len(cx) == 0 or len(cy) == 0:
        return None

    # build cost: squared centroid distance + dominant color mismatch penalty
    nx, ny = len(cx), len(cy)
    C = np.zeros((nx, ny), float)
    for i, a in enumerate(cx):
        for j, b in enumerate(cy):
            dr = a["centroid"][0] - b["centroid"][0]
            dc = a["centroid"][1] - b["centroid"][1]
            d = dr*dr + dc*dc
            pen = 0.0 if a["dominant"] == b["dominant"] else 1.5
            C[i, j] = d + pen

    assign, tot = hungarian(C)  # handles rectangular

    # build mapping and per-component Δr,Δc
    assignments = []
    recolor = {}
    for i, j in assign:
        ai = cx[i]; bj = cy[j]
        dr = int(round(bj["centroid"][0] - ai["centroid"][0]))
        dc = int(round(bj["centroid"][1] - ai["centroid"][1]))
        assignments.append({"from": i, "to": j, "dr": dr, "dc": dc})
        recolor[int(ai["dominant"])] = int(bj["dominant"])

    return {
        "assign": assignments,
        "recolor": recolor,
    }

def apply_component_rule(x: np.ndarray, rule: Dict, out_shape: Tuple[int,int]) -> np.ndarray:
    """
    Re-renders X's components into a fresh canvas of out_shape using learned per-comp translations and recolors.
    """
    H, W = out_shape
    out = np.zeros((H, W), dtype=np.int8)
    lab, K = _cc_label(x)
    # Build quick map: comp id -> pixels and dominant color
    comps = extract_components(x)
    dom_color = {c["id"]: c["dominant"] for c in comps}
    pix_map = {c["id"]: c["pixels"] for c in comps}

    for asg in rule.get("assign", []):
        k = asg["from"]
        dr, dc = asg["dr"], asg["dc"]
        color = dom_color.get(k, 0)
        color = rule.get("recolor", {}).get(color, color)
        if k not in pix_map:
            continue
        for y, x0 in pix_map[k]:
            yy = y + dr
            xx = x0 + dc
            if 0 <= yy < H and 0 <= xx < W:
                out[yy, xx] = color
    return out
