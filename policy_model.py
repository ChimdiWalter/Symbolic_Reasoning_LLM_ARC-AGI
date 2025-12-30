# policy_model.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List
import numpy as np

# Light, offline policy:
# - Extract simple scene features (color hist, object count proxy, symmetry cues)
# - Emit priors over primitives + arguments (colors, axis, small translations)
# - If policy_weights.npz exists, multiply learned weights; else use heuristics.

Color = int

@dataclass
class SceneStats:
    H: int
    W: int
    color_hist: np.ndarray  # shape (10,)
    nonzero_ratio: float
    v_sym: float
    h_sym: float
    palette: np.ndarray  # sorted unique colors in grid

def _symmetry_score(arr: np.ndarray, axis: int) -> float:
    # axis=1 vertical mirror, axis=0 horizontal
    if axis == 1:
        L = arr[:, :arr.shape[1]//2]
        R = arr[:, -L.shape[1]:][:, ::-1]
        if L.size == 0 or R.size == 0: return 0.0
        return float((L == R).mean())
    else:
        T = arr[:arr.shape[0]//2, :]
        B = arr[-T.shape[0]:, :][::-1, :]
        if T.size == 0 or B.size == 0: return 0.0
        return float((T == B).mean())

def _scene_stats(grid: np.ndarray) -> SceneStats:
    H, W = grid.shape
    hist = np.bincount(grid.reshape(-1), minlength=10)[:10].astype(np.float32)
    hist = hist / max(1, hist.sum())
    nz_ratio = float((grid != 0).mean())
    v = _symmetry_score(grid, axis=1)
    h = _symmetry_score(grid, axis=0)
    pal = np.unique(grid)
    return SceneStats(H=H, W=W, color_hist=hist, nonzero_ratio=nz_ratio, v_sym=v, h_sym=h, palette=pal)

@dataclass
class PolicyPriors:
    # primitive priors (higher = more likely)
    prim: Dict[str, float]
    # argument priors:
    colors_src: Dict[Color, float]
    colors_dst: Dict[Color, float]
    translate: Dict[Tuple[int,int], float]  # (dr,dc) -> score
    reflect_axis: Dict[int, float]          # 0 or 1
    mirror_axis: Dict[int, float]           # 0 or 1
    border_side: Dict[int, float]           # 0=top,1=bottom,2=left,3=right

class SimplePolicy:
    def __init__(self, weights_path: Optional[str] = "policy_weights.npz"):
        self.has_weights = False
        self.W_prim = None
        self.W_args = None
        try:
            w = np.load(weights_path)
            self.W_prim = w.get("W_prim", None)
            self.W_args = w.get("W_args", None)
            self.has_weights = (self.W_prim is not None) or (self.W_args is not None)
        except Exception:
            self.has_weights = False

    def _base_prim_prior(self, st: SceneStats) -> Dict[str, float]:
        # Heuristic base priors
        prims = {
            "identity": 0.1,
            "paint_largest": 0.4 if st.nonzero_ratio>0 else 0.05,
            "translate_color": 0.35 if st.nonzero_ratio>0 else 0.05,
            "reflect_color": 0.2 if max(st.v_sym, st.h_sym)>0.6 else 0.05,
            "complete_mirror": 0.5 if max(st.v_sym, st.h_sym)>0.8 else 0.05,
            "snap_to_border": 0.15 if st.nonzero_ratio>0 else 0.05,
            "rect_outline": 0.15 if st.nonzero_ratio>0 else 0.05,
        }
        return prims

    def _base_args_prior(self, st: SceneStats) -> Tuple[Dict[int,float], Dict[int,float], Dict[Tuple[int,int], float], Dict[int,float], Dict[int,float], Dict[int,float]]:
        colors_src = {int(c): 0.1 for c in st.palette if c!=0}
        colors_dst = {c: 0.05 for c in range(10)}
        # favor dst colors close to frequent nonzero in histogram
        nz_idx = [int(i) for i,v in enumerate(st.color_hist) if v>0 and i!=0]
        for c in nz_idx:
            colors_dst[c] += 0.2
        colors_dst[0] += 0.05  # sometimes zero painting

        # small translations (bias toward near-zero)
        translate = {}
        for dr in [-2,-1,0,1,2]:
            for dc in [-2,-1,0,1,2]:
                if dr==0 and dc==0: continue
                translate[(dr,dc)] = 0.05 + 0.15*(1.0/(1+abs(dr)+abs(dc)))

        reflect_axis = {0: st.h_sym, 1: st.v_sym}
        mirror_axis  = {0: st.h_sym, 1: st.v_sym}
        border_side  = {0:0.1,1:0.1,2:0.1,3:0.1}
        return colors_src, colors_dst, translate, reflect_axis, mirror_axis, border_side

    def _apply_weights(self, vec: np.ndarray, W: Optional[np.ndarray]) -> np.ndarray:
        if W is None: return vec
        # simple linear reweight
        try:
            out = vec * np.clip(W[:len(vec)], 0.05, 5.0)
            s = out.sum()
            if s>0: out = out/s
            return out
        except Exception:
            return vec

    def priors_for_pair(self, x: np.ndarray, y: np.ndarray) -> PolicyPriors:
        # Combine info from input & output (train pair)
        st_x = _scene_stats(x)
        st_y = _scene_stats(y)
        # merge heuristics (favor operations consistent with y)
        prim = self._base_prim_prior(st_x)
        if st_y.v_sym>st_x.v_sym+0.2 or st_y.h_sym>st_x.h_sym+0.2:
            prim["complete_mirror"] += 0.2

        (csrc, cdst, trans, rax, maxis, bside) = self._base_args_prior(st_x)
        # light hint: if y adds a new color, push paint_largest + that dst
        new_cols = [int(c) for c in st_y.palette if c not in st_x.palette]
        for c in new_cols:
            cdst[c] = cdst.get(c,0.05)+0.3
            prim["paint_largest"] += 0.1

        # normalize dictionaries
        def _norm(d: Dict) -> Dict:
            s = float(sum(d.values())) or 1.0
            return {k:v/s for k,v in d.items()}
        prim = _norm(prim)
        csrc = _norm(csrc) if csrc else {}
        cdst = _norm(cdst)
        trans = _norm(trans)
        rax = _norm(rax)
        maxis = _norm(maxis)
        bside = _norm(bside)

        return PolicyPriors(prim=prim, colors_src=csrc, colors_dst=cdst,
                            translate=trans, reflect_axis=rax, mirror_axis=maxis, border_side=bside)
