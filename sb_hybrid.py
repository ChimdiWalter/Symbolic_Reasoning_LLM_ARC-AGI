# sb_hybrid.py
from __future__ import annotations
import numpy as np
from typing import List, Tuple, Callable, Optional, Dict, Any

###############################################################################
# Basic utils
###############################################################################
def to_np(x): return np.array(x, dtype=np.int8)

def clamp01_09(A: np.ndarray) -> np.ndarray:
    A = A.astype(np.int16)
    A[A < 0] = 0
    A[A > 9] = 9
    return A.astype(np.int8)

def pad_or_crop_to(A: np.ndarray, H: int, W: int) -> np.ndarray:
    H = int(max(1, min(30, H))); W = int(max(1, min(30, W)))
    h, w = A.shape
    # pad to at least HxW
    Hpad, Wpad = max(H, h), max(W, w)
    B = np.zeros((Hpad, Wpad), dtype=A.dtype)
    top = (Hpad - h) // 2
    left = (Wpad - w) // 2
    B[top:top+h, left:left+w] = A
    # center crop to exactly HxW
    r0 = max(0, (Hpad - H) // 2)
    c0 = max(0, (Wpad - W) // 2)
    return B[r0:r0+H, c0:c0+W]

def rotate_k(A: np.ndarray, k: int) -> np.ndarray:
    k = k % 4
    if k == 0: return A.copy()
    return np.rot90(A, k=k)

def flip_lr(A: np.ndarray) -> np.ndarray: return np.fliplr(A)
def flip_ud(A: np.ndarray) -> np.ndarray: return np.flipud(A)

def bbox_of_nonzero(A: np.ndarray):
    nz = np.argwhere(A != 0)
    if nz.size == 0: return (0,0,A.shape[0],A.shape[1])
    r0, c0 = nz.min(0); r1, c1 = nz.max(0)
    return (int(r0), int(c0), int(r1)+1, int(c1)+1)

def crop_to_bbox(A: np.ndarray, H: int, W: int) -> np.ndarray:
    r0,c0,r1,c1 = bbox_of_nonzero(A)
    B = A[r0:r1, c0:c1]
    return pad_or_crop_to(B, H, W)

def integer_resample_nn(A: np.ndarray, H: int, W: int) -> np.ndarray:
    # strictly NN down/up without recursion
    h, w = A.shape
    if h == H and w == W: return A.copy()
    rs = np.clip(np.round(np.linspace(0, h-1, H)).astype(int), 0, h-1)
    cs = np.clip(np.round(np.linspace(0, w-1, W)).astype(int), 0, w-1)
    return A[np.ix_(rs, cs)].copy()

###############################################################################
# Families (API expected by build_curveball_predictions.py)
###############################################################################
def make_global_family(Ht: int, Wt: int, palette_hint: Optional[List[int]] = None,
                       krots=(0,1,2,3), flips=(0,1,2), crop_modes=("center","bbox")):
    cands = []
    for rk in krots:
        for fl in flips: # 0 none, 1 lr, 2 ud
            for crop_mode in crop_modes:
                name = f"G:r{rk}:f{fl}:crop{crop_mode}"
                def apply_factory(rk=rk, fl=fl, crop_mode=crop_mode):
                    def apply(x: np.ndarray) -> np.ndarray:
                        A = x.copy()
                        if rk: A = rotate_k(A, rk)
                        if fl==1: A = flip_lr(A)
                        elif fl==2: A = flip_ud(A)
                        if crop_mode == "bbox":
                            A = crop_to_bbox(A, Ht, Wt)
                        else:
                            A = integer_resample_nn(A, Ht, Wt)
                            A = pad_or_crop_to(A, Ht, Wt)
                        return clamp01_09(A)
                    return apply
                cands.append((name, apply_factory()))
    return cands

def _flood_components(A: np.ndarray):
    h,w = A.shape
    seen = np.zeros_like(A, dtype=np.uint8)
    comps = []
    for r in range(h):
        for c in range(w):
            col = A[r,c]
            if col != 0 and not seen[r,c]:
                stack=[(r,c)]; seen[r,c]=1; pix=[]
                while stack:
                    rr,cc = stack.pop()
                    pix.append((rr,cc))
                    for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                        r2,c2 = rr+dr, cc+dc
                        if 0<=r2<h and 0<=c2<w and not seen[r2,c2] and A[r2,c2]==col:
                            seen[r2,c2]=1; stack.append((r2,c2))
                rs=[p[0] for p in pix]; cs=[p[1] for p in pix]
                r0,r1=min(rs),max(rs); c0,c1=min(cs),max(cs)
                tile = np.zeros((r1-r0+1, c1-c0+1), dtype=np.int8)
                for (rr,cc) in pix: tile[rr-r0, cc-c0]=col
                comps.append((len(pix), col, tile))
    return comps

def pack_components(A: np.ndarray, H: int, W: int, order="by_area") -> np.ndarray:
    comps = _flood_components(A)
    if order == "by_area":
        comps.sort(key=lambda t:(-t[0], t[1]))
    out = np.zeros((H,W), dtype=np.int8)
    r=c=0; max_row=0; pad=1
    for _,_,tile in comps:
        th,tw = tile.shape
        if th>H or tw>W:
            tile = integer_resample_nn(tile, min(H,th), min(W,tw))
            th,tw = tile.shape
        if c+tw > W:
            r += max_row + pad
            c = 0
            max_row = 0
        if r+th > H: break
        out[r:r+th, c:c+tw] = tile
        c += tw + pad
        max_row = max(max_row, th)
    return out

def make_component_family(Ht: int, Wt: int):
    return [
        ("C:pack_area", lambda x: clamp01_09(pack_components(x, Ht, Wt, order="by_area")))
    ]

def outline(A: np.ndarray) -> np.ndarray:
    h,w = A.shape
    B = np.zeros_like(A)
    nz = (A!=0)
    for r in range(h):
        for c in range(w):
            if nz[r,c]:
                for dr in (-1,0,1):
                    for dc in (-1,0,1):
                        rr,cc = r+dr,c+dc
                        if 0<=rr<h and 0<=cc<w: B[rr,cc] = A[r,c]
    return B

def fill_holes(A: np.ndarray) -> np.ndarray:
    h,w = A.shape
    B = A.copy()
    for r in range(1,h-1):
        for c in range(1,w-1):
            if A[r,c]==0:
                vals = [A[r+dr,c+dc] for dr in (-1,0,1) for dc in (-1,0,1) if A[r+dr,c+dc]!=0]
                if len(vals)>=6:
                    u,cnt = np.unique(vals, return_counts=True)
                    B[r,c] = u[np.argmax(cnt)]
    return B

def make_outline_fill_family(Ht: int, Wt: int):
    return [
        ("OF:outline",    lambda x: clamp01_09(pad_or_crop_to(outline(x),    Ht, Wt))),
        ("OF:fillholes",  lambda x: clamp01_09(pad_or_crop_to(fill_holes(x), Ht, Wt))),
    ]

def project_rows(A: np.ndarray, H: int, W: int, mode="any") -> np.ndarray:
    rows = (A!=0).any(1).astype(np.int8)
    cols = (A!=0).any(0).astype(np.int8)
    Br = (rows.reshape(-1,1) * np.ones_like(A))
    Bc = (cols.reshape(1,-1) * np.ones_like(A))
    if mode=="any":
        B = ((Br+Bc)>0).astype(np.int8) * max(1, int(A.max()))
    else:
        B = Br.astype(np.int8) * max(1, int(A.max()))
    return pad_or_crop_to(B, H, W)

def make_projection_family(Ht: int, Wt: int):
    return [
        ("P:any",  lambda x: clamp01_09(project_rows(x, Ht, Wt, "any"))),
        ("P:rows", lambda x: clamp01_09(project_rows(x, Ht, Wt, "rows"))),
    ]

###############################################################################
# Tiny ranking by train L0; choose safe shapes
###############################################################################
def L0(a: np.ndarray, b: np.ndarray) -> int:
    if a.shape != b.shape: return 10**9
    return int((a != b).sum())

def matches_train(rule_apply: Callable[[np.ndarray], np.ndarray],
                  train_pairs: List[Tuple[np.ndarray,np.ndarray]],
                  cap_bad=10**6) -> int:
    total=0
    for x,y in train_pairs:
        yp = rule_apply(x)
        sc = L0(yp,y)
        total += sc
        if total >= cap_bad: break
    return total

def choose_target_shape(test_input: np.ndarray,
                        train_pairs: List[Tuple[np.ndarray,np.ndarray]]) -> Tuple[int,int]:
    # 1) identity-size default
    Ht, Wt = test_input.shape
    # 2) if all train outputs have the same shape, allow that override
    outs = {(y.shape[0], y.shape[1]) for (_,y) in train_pairs}
    if len(outs) == 1:
        return next(iter(outs))
    return (int(Ht), int(Wt))

