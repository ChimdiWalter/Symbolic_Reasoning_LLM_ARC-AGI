# rule_searcher.py (safe v2.1)
from __future__ import annotations
from typing import List, Tuple, Dict, Optional, Callable
import numpy as np

# ----------------------------
# Small utilities
# ----------------------------

def rot(a: np.ndarray, k:int) -> np.ndarray:
    return a if k%4==0 else np.rot90(a, k%4)

def flip_lr(a: np.ndarray) -> np.ndarray:
    return np.fliplr(a)

def flip_ud(a: np.ndarray) -> np.ndarray:
    return np.flipud(a)

def crop_pad_center(a: np.ndarray, shape: Tuple[int,int]) -> np.ndarray:
    H,W = shape; h,w = a.shape
    out = np.zeros((H,W), dtype=a.dtype)
    ih, iw = min(H,h), min(W,w)
    sr, sc = (h-ih)//2, (w-iw)//2
    dr, dc = (H-ih)//2, (W-iw)//2
    out[dr:dr+ih, dc:dc+iw] = a[sr:sr+ih, sc:sc+iw]
    return out

def translate(a: np.ndarray, dx:int, dy:int) -> np.ndarray:
    h,w = a.shape
    out = np.zeros_like(a)
    r0 = max(0, dx); c0 = max(0, dy)
    r1 = min(h, h+dx); c1 = min(w, w+dy)
    sr0 = max(0, -dx); sc0 = max(0, -dy)
    out[r0:r1, c0:c1] = a[sr0:sr0+(r1-r0), sc0:sc0+(c1-c0)]
    return out

def centroid(a: np.ndarray):
    pts = np.argwhere(a!=0)
    if len(pts)==0: return (0.0,0.0)
    return (float(pts[:,0].mean()), float(pts[:,1].mean()))

def apply_lut(a: np.ndarray, lut: np.ndarray) -> np.ndarray:
    out = a.copy()
    m = (out>=0)&(out<=9)
    out[m] = lut[out[m]]
    return out

def palette_overlap(a: np.ndarray, b: np.ndarray) -> int:
    return len(set(np.unique(a)) & set(np.unique(b)))

def nontrivial(a: np.ndarray) -> bool:
    return (a!=0).any()

# ----------------------------
# Tiny “Hungarian” for 10×10
# ----------------------------

def hungarian_max_weight(M: np.ndarray) -> np.ndarray:
    rows = list(range(10))
    rows.sort(key=lambda r: -M[r].max())
    used = [False]*10
    best = -1
    best_assign = [0]*10

    def dfs(i, score, assign):
        nonlocal best, best_assign
        if i==10:
            if score>best:
                best = score
                best_assign = assign[:]
            return
        r = rows[i]
        # optimistic bound
        rem = sum(M[rows[j]].max() for j in range(i,10))
        if score + rem <= best:
            return
        for c in np.argsort(-M[r]):
            if not used[c]:
                used[c]=True; assign[r]=int(c)
                dfs(i+1, score+int(M[r,c]), assign)
                used[c]=False

    dfs(0,0,[0]*10)
    lut = np.arange(10, dtype=np.int8)
    for r,c in enumerate(best_assign):
        lut[r]=c
    return lut

def fit_palette_perm_for_rule(train_pairs: List[Tuple[np.ndarray,np.ndarray]],
                              apply_rule: Callable[[np.ndarray], np.ndarray],
                              out_shape: Tuple[int,int]) -> Optional[np.ndarray]:
    H,W = out_shape
    M = np.zeros((10,10), dtype=np.int32)
    tot = 0
    for (x,y) in train_pairs:
        a = apply_rule(x)
        yy = crop_pad_center(y,(H,W))
        xv, yv = a.reshape(-1), yy.reshape(-1)
        for aa,bb in zip(xv,yv):
            if 0<=aa<=9 and 0<=bb<=9:
                M[aa,bb]+=1; tot+=1
    if tot==0: return None
    if np.trace(M) >= 0.9*M.sum():  # identity good enough
        return None
    return hungarian_max_weight(M)

# ----------------------------
# Geometric head (Head-A)
# ----------------------------

def candidate_orientations(a: np.ndarray) -> List[np.ndarray]:
    outs=[]
    for k in (0,1,2,3):
        r = rot(a,k)
        outs.append(r); outs.append(flip_lr(r))
    return outs  # 8

def candidate_translations(dx_hint:int, dy_hint:int, radius:int=3) -> List[Tuple[int,int]]:
    deltas=[]
    for dx in range(dx_hint-radius, dx_hint+radius+1):
        for dy in range(dy_hint-radius, dy_hint+radius+1):
            if abs(dx)+abs(dy) <= radius:
                deltas.append((dx,dy))
    deltas = sorted(set(deltas), key=lambda t:(abs(t[0])+abs(t[1]), abs(t[0]), abs(t[1])))
    return deltas

def _mode_size(sizes: List[Tuple[int,int]]) -> Tuple[int,int]:
    # sizes is non-empty
    uniq = {}
    for s in sizes:
        uniq[s] = uniq.get(s, 0) + 1
    return max(uniq, key=uniq.get)

def infer_rule_geometric(train_pairs: List[Tuple[np.ndarray,np.ndarray]],
                         policy: Optional[Dict[str,float]]=None,
                         trans_radius:int=3):
    # output size = mode of train outputs (fallback to first input size if weird)
    sizes = [y.shape for (_,y) in train_pairs]
    H,W = _mode_size(sizes) if sizes else train_pairs[0][0].shape

    # centroid median shift
    sh=[]
    for x,y in train_pairs:
        cx,cy = centroid(x); ux,uy = centroid(y)
        sh.append((int(round(ux-cx)), int(round(uy-cy))))
    sx = int(round(np.median([s[0] for s in sh]))) if sh else 0
    sy = int(round(np.median([s[1] for s in sh]))) if sh else 0

    def w(name:str, default:float=0.0)->float:
        return float(policy.get(name, default)) if policy else 0.0

    best_score = -1e18
    best = None

    # orient by first pair, but evaluate on all
    x0,_ = train_pairs[0]
    ori_list = candidate_orientations(x0)

    for ori_idx, ori_x0 in enumerate(ori_list):
        ori_bonus = max(w("rot0"), w("rot90"), w("rot180"), w("rot270")) + max(w("flip_lr"), w("flip_ud"), 0.0)
        for dx,dy in candidate_translations(sx, sy, radius=trans_radius):
            trans_bonus = w("translate") if (dx!=0 or dy!=0) else 0.0

            def apply_rule(a: np.ndarray, _ori_idx=ori_idx, _dx=dx, _dy=dy):
                cand8 = candidate_orientations(a)
                j = _ori_idx if _ori_idx < len(cand8) else int(np.argmax([palette_overlap(c, ori_x0) for c in cand8]))
                b = cand8[j]
                b = translate(b, _dx, _dy)
                b = crop_pad_center(b, (H,W))
                return b

            lut = fit_palette_perm_for_rule(train_pairs, apply_rule, (H,W))

            score = 0
            for (x,y) in train_pairs:
                a = apply_rule(x)
                if lut is not None:
                    a = apply_lut(a, lut)
                yy = crop_pad_center(y,(H,W))
                score += int((a==yy).sum())

            total_score = score + 100.0*(ori_bonus + trans_bonus) + (w("palette_perm") if lut is not None else 0.0)
            if total_score > best_score:
                best_score = total_score
                best = (apply_rule, lut, {"H":H,"W":W,"dx":dx,"dy":dy,"ori":ori_idx,"train_px":score})

    # *** SAFETY FALLBACK: if search found nothing, use identity -> crop/pad ***
    if best is None:
        def identity_rule(a: np.ndarray) -> np.ndarray:
            return crop_pad_center(a, (H, W))
        info = {"head":"geom","H":H,"W":W,"dx":0,"dy":0,"ori":0,"train_px":0}
        return info, (lambda a, use_lut=True: identity_rule(a))

    def apply_fn(a: np.ndarray, use_lut: bool=True) -> np.ndarray:
        ar = best[0](a)
        if use_lut and best[1] is not None:
            ar = apply_lut(ar, best[1])
        return ar

    info = {"head":"geom", **best[2], "palette": best[1] is not None}
    return info, apply_fn

# ----------------------------
# Symmetry/completion head (Head-B)
# ----------------------------

def maybe_mirror(a: np.ndarray, axis:int) -> np.ndarray:
    h,w = a.shape
    out = a.copy()
    if axis==0:
        top = a[:h//2,:]
        out[h-top.shape[0]:,:] = top[::-1,:]
    else:
        left = a[:,:w//2]
        out[:,w-left.shape[1]:] = left[:,::-1]
    return out

def stripes_complete(a: np.ndarray, axis:int) -> np.ndarray:
    out = a.copy()
    if axis==0:
        for r in range(1, a.shape[0], 2):
            out[r,:] = out[r-1,:]
    else:
        for c in range(1, a.shape[1], 2):
            out[:,c] = out[:,c-1]
    return out

def infer_rule_symmetry(train_pairs: List[Tuple[np.ndarray,np.ndarray]]):
    # choose best of {mirror/stripe}×{axis}
    choices = [("mirror",0),("mirror",1),("stripe",0),("stripe",1)]
    best = None; best_score = -1
    sizes = [y.shape for _,y in train_pairs]
    H,W = _mode_size(sizes) if sizes else train_pairs[0][0].shape

    for kind,ax in choices:
        sc = 0
        for x,y in train_pairs:
            if kind=="mirror":
                a = maybe_mirror(x, ax)
            else:
                a = stripes_complete(x, ax)
            sc += int((crop_pad_center(a,(H,W)) == crop_pad_center(y,(H,W))).sum())
        if sc>best_score:
            best_score = sc
            best = (kind, ax)

    # fallback just in case
    if best is None:
        best = ("mirror", 1)

    def apply_fn(a: np.ndarray) -> np.ndarray:
        if best[0]=="mirror":
            z = maybe_mirror(a, best[1])
        else:
            z = stripes_complete(a, best[1])
        return z

    info = {"head":"sym", "kind":best[0], "axis":best[1], "train_px":int(best_score), "H":H,"W":W}
    return info, apply_fn

# ----------------------------
# Public API
# ----------------------------

def infer_two_attempts(train_pairs: List[Tuple[np.ndarray,np.ndarray]],
                       tests: List[np.ndarray],
                       policy: Optional[Dict[str,float]]=None) -> List[List[np.ndarray]]:
    """
    Returns per-test [[attempt1, attempt2]]:
      - attempt_1: geometric + LUT (or identity fallback)
      - attempt_2: geometric without LUT or symmetry (ensures non-trivial if possible)
    """
    # Head-A
    g_info, g_apply = infer_rule_geometric(train_pairs, policy=policy, trans_radius=3)
    # Head-B
    s_info, s_apply = infer_rule_symmetry(train_pairs)

    H = g_info.get("H", tests[0].shape[0]); W = g_info.get("W", tests[0].shape[1])
    outs: List[List[np.ndarray]] = []
    for x in tests:
        a1 = crop_pad_center(g_apply(x, use_lut=True), (H,W))
        if not nontrivial(a1):
            a1 = crop_pad_center(s_apply(x), (H,W))

        a2 = crop_pad_center((g_apply(x, use_lut=False) if g_info.get("palette", False) else s_apply(x)), (H,W))
        if not nontrivial(a2):
            alt = s_apply(x) if g_info.get("palette", False) else g_apply(x, use_lut=True)
            a2 = crop_pad_center(alt, (H,W))
        if not nontrivial(a2):
            a2 = a1.copy()

        outs.append([a1.astype(np.int16), a2.astype(np.int16)])
    return outs
