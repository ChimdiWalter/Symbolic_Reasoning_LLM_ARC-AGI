# rule_miner_stronger.py
from __future__ import annotations
import itertools, math
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

# -------------------- small utils --------------------
def to_np(x): return np.array(x, dtype=np.int8)

def clamp01_09(A):
    A = A.astype(np.int16)
    A[A < 0] = 0
    A[A > 9] = 9
    return A.astype(np.int8)

def palette(A): 
    return sorted(set(int(c) for c in np.unique(A)))

def bbox(A):
    nz = np.argwhere(A!=0)
    if nz.size == 0: return (0,0,A.shape[0],A.shape[1])
    r0,c0 = nz.min(0); r1,c1 = nz.max(0)
    return (int(r0),int(c0),int(r1)+1,int(c1)+1)

def crop(A, r0,c0,r1,c1):
    r0=max(0,r0); c0=max(0,c0); r1=min(A.shape[0],r1); c1=min(A.shape[1],c1)
    if r1<=r0 or c1<=c0: 
        return np.zeros((max(1,r1-r0), max(1,c1-c0)), dtype=A.dtype)
    return A[r0:r1, c0:c1].copy()

def center_crop_pad(A, H, W):
    h,w = A.shape
    H=max(1,int(H)); W=max(1,int(W))
    if h==H and w==W: return A.copy()
    # pad if smaller
    ph=max(0,H-h); pw=max(0,W-w)
    if ph>0 or pw>0:
        top=ph//2; left=pw//2
        B=np.zeros((h+ph, w+pw), dtype=A.dtype)
        B[top:top+h, left:left+w]=A
        A=B; h,w=A.shape
    # crop center
    r0=max(0,(h-H)//2); c0=max(0,(w-W)//2)
    return A[r0:r0+H, c0:c0+W].copy()

def bbox_crop_to(A, H, W):
    r0,c0,r1,c1=bbox(A)
    return center_crop_pad(A[r0:r1, c0:c1], H,W)

def rotate_k(A, k):
    k%=4
    if k==0: return A.copy()
    return np.rot90(A, k=k)

def flip_lr(A): return np.fliplr(A)
def flip_ud(A): return np.flipud(A)

# -------------------- safe IoU for masks of diff sizes --------------------
def iou_mask(a: np.ndarray, b: np.ndarray) -> float:
    # Crop both to the overlap of their bboxes in their own frames by
    # resampling to the smaller bbox size (nearest neighbor via linspace indices)
    if a.ndim!=2 or b.ndim!=2: return 0.0
    ra0,ca0,ra1,ca1 = bbox(a)
    rb0,cb0,rb1,cb1 = bbox(b)
    Aa = a[ra0:ra1, ca0:ca1] != 0
    Bb = b[rb0:rb1, cb0:cb1] != 0
    ha,wa = Aa.shape
    hb,wb = Bb.shape
    H = max(1, min(ha,hb))
    W = max(1, min(wa,wb))
    # downsample both to HxW by nearest indices
    def sample(M, H,W):
        h,w = M.shape
        rs = np.clip(np.round(np.linspace(0, h-1, H)).astype(int),0,h-1)
        cs = np.clip(np.round(np.linspace(0, w-1, W)).astype(int),0,w-1)
        return M[np.ix_(rs,cs)]
    A2 = sample(Aa, H,W)
    B2 = sample(Bb, H,W)
    inter = np.logical_and(A2,B2).sum()
    uni   = np.logical_or (A2,B2).sum()
    return float(inter)/float(uni) if uni>0 else (1.0 if inter==0 else 0.0)

# -------------------- components --------------------
def connected_components(A: np.ndarray) -> List[Tuple[int,int,np.ndarray]]:
    h,w = A.shape
    seen = np.zeros((h,w), dtype=np.uint8)
    comps=[]
    for r in range(h):
        for c in range(w):
            col=A[r,c]
            if col!=0 and not seen[r,c]:
                stack=[(r,c)]
                seen[r,c]=1
                pix=[]
                while stack:
                    rr,cc=stack.pop()
                    pix.append((rr,cc))
                    for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                        r2,c2 = rr+dr,cc+dc
                        if 0<=r2<h and 0<=c2<w and not seen[r2,c2] and A[r2,c2]==col:
                            seen[r2,c2]=1; stack.append((r2,c2))
                rs=[p[0] for p in pix]; cs=[p[1] for p in pix]
                r0,r1=min(rs),max(rs); c0,c1=min(cs),max(cs)
                tile = np.zeros((r1-r0+1, c1-c0+1), dtype=np.int8)
                for (rr,cc) in pix: tile[rr-r0, cc-c0]=col
                comps.append((len(pix), col, tile))
    comps.sort(key=lambda t: (-t[0], t[1]))
    return comps  # (area,color,tile)

# -------------------- rectangular Hungarian (pad) --------------------
def hungarian_rect(cost: np.ndarray) -> Tuple[List[int], float]:
    # Pads to square with zeros on the larger dim (standard trick)
    n,m = cost.shape
    size = max(n,m)
    C = np.zeros((size,size), dtype=float)
    C[:n,:m] = cost
    # Simple Hungarian (O(n^3)) – tiny n in ARC components, OK.
    # Implementation per Kuh's algorithm (compact, minimal).
    u = np.zeros(size); v = np.zeros(size)
    p = np.full(size, -1, int); way = np.full(size, -1, int)
    for i in range(size):
        p[0] = i
        j0 = 0
        minv = np.full(size, float('inf'))
        used = np.zeros(size, dtype=bool)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float('inf'); j1 = 0
            for j in range(1,size):
                if not used[j]:
                    cur = C[i0,j] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur; way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]; j1 = j
            for j in range(size):
                if used[j]:
                    u[p[j]] += delta; v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == -1: break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0: break
    # Recover assignment
    assign = [-1]*n
    # p[j] = i matched to column j
    for j in range(1,size):
        if p[j] < n and j < m:
            assign[p[j]] = j
    # Compute total
    tot = 0.0
    for i in range(n):
        j = assign[i]
        if j>=0: tot += C[i, j]
    return assign, tot

# -------------------- palette perms (bounded) --------------------
def try_palette_perms(x: np.ndarray, y: np.ndarray, limit=720):
    # If palette size <= 6, brute force; else identity only
    pin = [c for c in palette(x) if c!=0]
    pout= [c for c in palette(y) if c!=0]
    if len(pin)==0 or len(pout)==0:
        yield lambda A: A  # nothing to do
        return
    if len(pin) > 6 or len(pout)>6:
        # fallback: keep colors or simple mapping by frequency
        freq_in  = sorted(((int((x==c).sum()), c) for c in pin), reverse=True)
        freq_out = sorted(((int((y==c).sum()), c) for c in pout), reverse=True)
        mapping = {fin[1]: fout[1] for fin, fout in zip(freq_in, freq_out)}
        def f(A):
            B=A.copy()
            for ci,co in mapping.items():
                B[A==ci]=co
            return B
        yield f
        yield (lambda A: A)  # identity as diversity
        return
    outs = list(itertools.permutations(pout, r=min(len(pin),len(pout))))
    outs = outs[:limit]
    for tup in outs:
        mp = {ci: co for ci,co in zip(pin, tup)}
        def f(A, mp=mp):
            B = A.copy()
            for ci,co in mp.items():
                B[A==ci]=co
            return B
        yield f

# -------------------- families --------------------
def make_global_candidates(Ht, Wt, x_sample, limit_perms=True):
    # build palette functions w.r.t. first train pair
    pal_funcs = list(try_palette_perms(x_sample, np.zeros((Ht,Wt),dtype=np.int8), limit=120 if limit_perms else 720))
    cands=[]
    for rk in (0,1,2,3):
        for fl in (0,1,2): # none, lr, ud
            for crop_mode in ("center","bbox"):
                for pf in pal_funcs[:6]:  # cap variants to keep beam sane
                    def factory(rk=rk,fl=fl,crop_mode=crop_mode,pf=pf):
                        def apply(x):
                            A=x
                            if rk: A=rotate_k(A,rk)
                            if fl==1: A=flip_lr(A)
                            elif fl==2: A=flip_ud(A)
                            if crop_mode=="bbox": B=bbox_crop_to(A,Ht,Wt)
                            else: B=center_crop_pad(A,Ht,Wt)
                            B=pf(B)
                            return clamp01_09(B)
                        return apply
                    name=f"G:r{rk}f{fl}:{crop_mode}"
                    cands.append((name, factory()))
    return cands

def make_component_pack(Ht, Wt):
    def pack(A):
        comps = connected_components(A)
        out = np.zeros((Ht,Wt), dtype=np.int8)
        r=c=0; maxrow=0; pad=1
        for area,col,tile in comps:
            th,tw = tile.shape
            if th>Ht or tw>Wt:
                # downsample coarse to fit
                rs = np.clip(np.round(np.linspace(0, th-1, min(Ht, th))).astype(int),0,th-1)
                cs = np.clip(np.round(np.linspace(0, tw-1, min(Wt, tw))).astype(int),0,tw-1)
                tile = tile[np.ix_(rs,cs)]
                th,tw=tile.shape
            if c+tw>Wt:
                r += maxrow + pad; c = 0; maxrow=0
            if r+th>Ht: break
            out[r:r+th, c:c+tw] = tile
            c += tw + pad
            maxrow = max(maxrow, th)
        return clamp01_09(out)
    return [("C:pack", pack)]

# -------------------- component mapping by IoU + rectangular Hungarian --------------------
def component_mapping_infer(x: np.ndarray, Ht: int, Wt: int) -> np.ndarray:
    # Predict target by packing / simple remap for diversity
    pack = make_component_pack(Ht,Wt)[0][1]
    return pack(x)

def try_component_mapping(train_pairs, test_inputs, Ht, Wt):
    # Learn mapping by aligning components across train ins→outs via IoU
    # then apply that packing flavor to test
    # Build a meta "template" from training: which source comp → which position in packed target.
    # Use rectangular Hungarian for each pair and average positions; here we just rely on pack at inference.
    outs=[]
    for tA in test_inputs:
        outs.append(component_mapping_infer(tA, Ht,Wt))
    return outs

# -------------------- top-level miner --------------------
def infer_two_attempts(tr_np: List[Tuple[np.ndarray,np.ndarray]],
                       te_np: List[np.ndarray],
                       policy=None,
                       shape_predict_fn=None,
                       family_hint: Optional[str]=None,
                       palette_hint: Optional[List[int]]=None,
                       beam:int=128, depth:int=2) -> List[List[np.ndarray]]:
    """
    Returns [[attempt1, attempt2], ...] for each test input.
    We build a small pool of global transforms (G) + component pack (C),
    score them on train (L0), then apply best to tests with shape-snapping.
    """

    # Decide a reference input for palette guesses
    x_sample = tr_np[0][0] if tr_np else te_np[0]
    # Predict shapes per test with provided shape model
    def predict_shape(A):
        if shape_predict_fn is None:
            # naive: snap to most common train output shape
            ys=[y.shape for _,y in tr_np]
            if ys:
                uniq,cnts=np.unique(np.array(ys), axis=0, return_counts=True)
                Ht,Wt = uniq[np.argmax(cnts)]
                return int(Ht),int(Wt)
            return (A.shape[0], A.shape[1])
        return shape_predict_fn(A)

    # Build families per *median* predicted shape for ranking
    if tr_np:
        shp = [predict_shape(x) for x,_ in tr_np]
        Hm = int(np.median([h for h,_ in shp])); Wm = int(np.median([w for _,w in shp]))
    else:
        Hm,Wm = te_np[0].shape

    G = make_global_candidates(Hm, Wm, x_sample)
    C = make_component_pack(Hm, Wm)

    families = []
    if family_hint == "component_mapping":
        families = C + G
    elif family_hint == "global_geom_palette":
        families = G + C
    else:
        families = G + C

    # Score on train with per-input predicted shape + shape snapping
    def wrap(fn):
        def f(x):
            Ht,Wt = predict_shape(x)
            y = fn(x)
            if y.shape != (Ht,Wt):
                y = bbox_crop_to(y, Ht, Wt) if (y!=0).any() else center_crop_pad(y, Ht, Wt)
            return clamp01_09(y)
        return f

    scored=[]
    for name,fn in families[:max(64, beam)]:  # cap evaluated pool
        wfn = wrap(fn)
        tot=0
        for x,y in tr_np:
            yp = wfn(x)
            if yp.shape != y.shape:
                tot += 10**7
            else:
                tot += int((yp!=y).sum())
            if tot >= 10**7: break
        scored.append((tot,name,wfn))
    scored.sort(key=lambda t: t[0])
    best = [w for _,_,w in scored[:max(8, beam//4)]]

    # Apply to tests, build two diversified attempts
    results=[]
    for tA in te_np:
        Ht,Wt = predict_shape(tA)
        cands=[]
        for fn in best[:8]:
            y = fn(tA)
            if y.shape != (Ht,Wt):
                y = bbox_crop_to(y, Ht, Wt) if (y!=0).any() else center_crop_pad(y, Ht, Wt)
            cands.append(clamp01_09(y))
        uniq=[]
        for y in cands:
            if not uniq or np.any(uniq[-1]!=y):
                uniq.append(y)
            if len(uniq)>=2: break
        if len(uniq)<2:
            z=np.zeros((Ht,Wt), dtype=np.int8)
            uniq = uniq + [z]
        results.append(uniq[:2])
    return results
