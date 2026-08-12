# rule_miner_components.py
from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import numpy as np

# ------------- basic geometry -------------
def _rot90(a, k=1): return np.rot90(a, k=k)
def _flip(a, axis): return np.flip(a, axis=axis)

def _apply_kind(a: np.ndarray, kind: str) -> np.ndarray:
    if kind == "id":    return a
    if kind == "rot1":  return _rot90(a,1)
    if kind == "rot2":  return _rot90(a,2)
    if kind == "rot3":  return _rot90(a,3)
    if kind == "flip0": return _flip(a,0)
    if kind == "flip1": return _flip(a,1)
    return a

# ------------- components -------------
def extract_components(a: np.ndarray) -> List[Dict]:
    h, w = a.shape
    seen = np.zeros((h, w), dtype=bool)
    comps: List[Dict] = []
    for r in range(h):
        for c in range(w):
            col = int(a[r, c])
            if col < 0 or col > 9: continue
            if seen[r, c]: continue
            # flood by color
            q = [(r, c)]
            seen[r, c] = True
            pix = [(r, c)]
            while q:
                rr, cc = q.pop()
                for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
                    nr, nc = rr+dr, cc+dc
                    if 0 <= nr < h and 0 <= nc < w and not seen[nr, nc] and a[nr, nc] == col:
                        seen[nr, nc] = True
                        q.append((nr, nc))
                        pix.append((nr, nc))
            rs = np.array([p[0] for p in pix]); cs = np.array([p[1] for p in pix])
            r0, r1 = rs.min(), rs.max()+1
            c0, c1 = cs.min(), cs.max()+1
            patch = a[r0:r1, c0:c1].copy()
            # binary mask of this component
            mask = (patch == col).astype(np.int8)
            centroid = (float(rs.mean()), float(cs.mean()))
            comps.append({
                "color": col,
                "pix": pix,
                "bbox": (int(r0), int(c0), int(r1), int(c1)),
                "mask": mask,
                "centroid": centroid
            })
    # stable order: larger first then color
    comps.sort(key=lambda d: (-len(d["pix"]), d["color"]))
    return comps

def _centroid(a: np.ndarray) -> Tuple[float,float]:
    rr, cc = np.nonzero(a)
    if rr.size == 0: return (a.shape[0]/2.0, a.shape[1]/2.0)
    return (float(rr.mean()), float(cc.mean()))

# ------------- Hungarian (simple) -------------
def _hungarian(cost: np.ndarray) -> Dict[int,int]:
    # Very small sizes; greedy+refine is enough for ARC component counts
    n, m = cost.shape
    # pad to square
    if n != m:
        k = max(n, m)
        pad = np.full((k, k), cost.max()+1, dtype=float)
        pad[:n, :m] = cost
        cost = pad; n = m = k
    # row/col reduce
    cost = cost.copy().astype(float)
    cost -= cost.min(axis=1, keepdims=True)
    cost -= cost.min(axis=0, keepdims=True)
    # greedy star
    starred = np.zeros_like(cost, dtype=bool)
    row_cov = np.zeros(n, dtype=bool); col_cov = np.zeros(n, dtype=bool)
    for r in range(n):
        for c in range(n):
            if abs(cost[r,c]) < 1e-12 and not row_cov[r] and not col_cov[c]:
                starred[r,c] = True; row_cov[r]=True; col_cov[c]=True
    # build mapping
    match = {}
    for r in range(n):
        cs = np.where(starred[r])[0]
        if cs.size: match[r] = int(cs[0])
        else: match[r] = int(np.argmin(cost[r]))
    return match

# ------------- per-component transform learner -------------
_KINDS = ("id","rot1","rot2","rot3","flip0","flip1")

def _apply_mask_transform(mask: np.ndarray, kind: str) -> np.ndarray:
    return _apply_kind(mask, kind)

def _bbox_overlap_cost(a: Tuple[int,int,int,int], b: Tuple[int,int,int,int]) -> float:
    ar0, ac0, ar1, ac1 = a
    br0, bc0, br1, bc1 = b
    H = max(ar1, br1) - min(ar0, br0)
    W = max(ac1, bc1) - min(ac0, bc0)
    # cost = distance between bbox centers + area difference (heuristic)
    acen = ((ar0+ar1)/2.0, (ac0+ac1)/2.0)
    bcen = ((br0+br1)/2.0, (bc0+bc1)/2.0)
    d = abs(acen[0]-bcen[0]) + abs(acen[1]-bcen[1])
    aarea = (ar1-ar0)*(ac1-ac0); barea = (br1-br0)*(bc1-bc0)
    return d + 0.25*abs(aarea-barea)/(H*W+1e-6)

def learn_component_rule(x: np.ndarray, y: np.ndarray) -> Optional[Dict]:
    cx = extract_components(x)
    cy = extract_components(y)
    if not cx or not cy: 
        return None
    # Build cost between components (bbox/size/centroid)
    n, m = len(cx), len(cy)
    C = np.zeros((n, m), dtype=float)
    for i, a in enumerate(cx):
        for j, b in enumerate(cy):
            # cost prefers similar size and close centroids
            c_area = abs(len(a["pix"]) - len(b["pix"])) / max(1, len(b["pix"]))
            c_bbox = _bbox_overlap_cost(a["bbox"], b["bbox"])
            c_color = 0.0 if a["color"] == b["color"] else 0.5
            C[i, j] = c_area + c_bbox + c_color
    match = _hungarian(C)
    # For matched pairs, try all kinds and estimate median shift Δr,Δc in Y-space
    votes: List[Tuple[str, int, int]] = []
    for i in range(n):
        j = match.get(i, None)
        if j is None or j >= m: 
            continue
        a = cx[i]; b = cy[j]
        mask_a = a["mask"]; mask_b = b["mask"]
        best = None
        for kind in _KINDS:
            ta = _apply_mask_transform(mask_a, kind)
            # measure centroid shift needed to align to b
            ca = _centroid(ta); cb = _centroid(mask_b)
            dr = int(round(cb[0]-ca[0])); dc = int(round(cb[1]-ca[1]))
            # score overlap after shift (approx)
            H = max(mask_b.shape[0], ta.shape[0]+abs(dr))
            W = max(mask_b.shape[1], ta.shape[1]+abs(dc))
            ref = np.zeros((H, W), dtype=np.int8)
            tgt = np.zeros((H, W), dtype=np.int8)
            r0 = max(0, dr); c0 = max(0, dc)
            rs = max(0, -dr); cs = max(0, -dc)
            hh = min(ta.shape[0]-rs, H-r0); ww = min(ta.shape[1]-cs, W-c0)
            if hh>0 and ww>0:
                ref[r0:r0+hh, c0:c0+ww] = ta[rs:rs+hh, cs:cs+ww]
            rr = (H - mask_b.shape[0])//2; cc = (W - mask_b.shape[1])//2
            tgt[rr:rr+mask_b.shape[0], cc:cc+mask_b.shape[1]] = mask_b
            overlap = int((ref & tgt).sum())
            score = overlap - int(abs(dr) + abs(dc))  # prefer small shifts
            if best is None or score > best[0]:
                best = (score, kind, dr, dc)
        if best is not None:
            votes.append((best[1], best[2], best[3]))

    if not votes:
        return None
    # choose majority (kind, dr, dc)
    from collections import Counter
    key = Counter(votes).most_common(1)[0][0]
    return {"kind": key[0], "dr": key[1], "dc": key[2]}

def apply_component_rule(x: np.ndarray, rule: Dict, out_shape: Tuple[int,int], color: Optional[int]=None) -> np.ndarray:
    """Apply learned per-component transform kind+shift to the whole grid and paste into out_shape."""
    H, W = out_shape
    out = np.zeros((H, W), dtype=np.int8)
    kind = rule.get("kind", "id")
    dr   = int(rule.get("dr", 0))
    dc   = int(rule.get("dc", 0))
    xk = _apply_kind(x, kind)
    # shift and paste
    h, w = xk.shape
    r0 = max(0, dr); c0 = max(0, dc)
    rs = max(0, -dr); cs = max(0, -dc)
    hh = min(h - rs, H - r0); ww = min(w - cs, W - c0)
    if hh > 0 and ww > 0:
        out[r0:r0+hh, c0:c0+ww] = xk[rs:rs+hh, cs:cs+ww]
    return out
