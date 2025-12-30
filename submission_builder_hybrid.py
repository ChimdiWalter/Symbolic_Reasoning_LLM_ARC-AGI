# =============================
# submission_builder_hybrid.py
# (robust hybrid with LLM programs, fixed ShapeModel, no recursion bugs)
# =============================
from __future__ import annotations
import os, sys, json, time, math, random, signal
from typing import Dict, Any, List, Tuple, Optional, Callable
import numpy as np

# -----------------------------
# Grid utils
# -----------------------------
class Grid:
    def __init__(self, data: np.ndarray):
        self.data = np.asarray(data, dtype=np.int8)
    @property
    def h(self): return int(self.data.shape[0])
    @property
    def w(self): return int(self.data.shape[1])
    def copy(self): return Grid(self.data.copy())

def to_np(x):
    return np.array(x, dtype=np.int8)

def clamp01_09(A: np.ndarray) -> np.ndarray:
    A = A.astype(np.int16)
    A[A < 0] = 0
    A[A > 9] = 9
    return A.astype(np.int8)

# -----------------------------
# Shape / resample helpers (no mutual recursion)
# -----------------------------

def enforce_shape(A: np.ndarray, H: int, W: int, prefer_bbox: bool = False) -> np.ndarray:
    """Return A resized to exactly (H,W) via center pad/crop or bbox-crop then pad.
    No calls to integer_resample_nn to avoid recursion loops.
    """
    A = np.asarray(A, dtype=np.int8)
    H = int(max(1, min(30, int(H))))
    W = int(max(1, min(30, int(W))))
    h, w = A.shape

    if h == H and w == W:
        return A.copy()

    def bbox_of_nonzero(M: np.ndarray):
        nz = np.argwhere(M != 0)
        if nz.size == 0:
            return (0, 0, h, w)
        r0, c0 = nz.min(0)
        r1, c1 = nz.max(0)
        return int(r0), int(c0), int(r1) + 1, int(c1) + 1

    # optionally crop to bbox first
    if prefer_bbox and (A != 0).any():
        r0, c0, r1, c1 = bbox_of_nonzero(A)
        A = A[r0:r1, c0:c1]
        h, w = A.shape

    # pad if needed
    pad_h = max(0, H - h)
    pad_w = max(0, W - w)
    if pad_h > 0 or pad_w > 0:
        top = pad_h // 2
        left = pad_w // 2
        B = np.zeros((h + pad_h, w + pad_w), dtype=A.dtype)
        B[top:top + h, left:left + w] = A
        A = B
        h, w = A.shape

    # center crop down to (H,W)
    r0 = max(0, (h - H) // 2)
    c0 = max(0, (w - W) // 2)
    return A[r0:r0 + H, c0:c0 + W].copy()

def integer_resample_nn(A: np.ndarray, H: int, W: int) -> np.ndarray:
    """Nearest-neighbor resample to (H,W). No calls back to enforce_shape."""
    A = np.asarray(A, dtype=np.int8)
    H = int(max(1, min(30, int(H))))
    W = int(max(1, min(30, int(W))))
    h, w = A.shape
    if h == H and w == W:
        return A.copy()
    rs = np.clip(np.round(np.linspace(0, h - 1, H)).astype(int), 0, h - 1)
    cs = np.clip(np.round(np.linspace(0, w - 1, W)).astype(int), 0, w - 1)
    return A[np.ix_(rs, cs)].copy()

def rotate_k(A: np.ndarray, k: int) -> np.ndarray:
    k %= 4
    if k == 0: return A.copy()
    return np.rot90(A, k=k)

def flip_lr(A: np.ndarray) -> np.ndarray:
    return np.fliplr(A)

def flip_ud(A: np.ndarray) -> np.ndarray:
    return np.flipud(A)

# -----------------------------
# Families
# -----------------------------

def make_global_family(Ht: int, Wt: int, palette_hint=None, krots=(0,1,2,3), flips=(0,1,2), crop_modes=("center","bbox")):
    cands = []
    for rk in krots:
        for fl in flips:  # 0 none, 1 lr, 2 ud
            for crop_mode in crop_modes:
                for palette_mode in ("keep", "restrict"):
                    nm = f"G:r{rk}:f{fl}:crop{crop_mode}:pal{palette_mode}"
                    def make(rk=rk, fl=fl, crop_mode=crop_mode, palette_mode=palette_mode):
                        def fn(x):
                            A = x
                            if rk: A = rotate_k(A, rk)
                            if fl == 1: A = flip_lr(A)
                            elif fl == 2: A = flip_ud(A)
                            if crop_mode == "bbox" and (A != 0).any():
                                A = enforce_shape(A, Ht, Wt, prefer_bbox=True)
                            else:
                                A = integer_resample_nn(A, Ht, Wt)
                            if palette_mode == "restrict" and palette_hint is not None:
                                mask = np.isin(A, np.array(palette_hint, dtype=np.int8))
                                A = (A * mask).astype(np.int8)
                            return clamp01_09(A)
                        return fn
                    cands.append((nm, make()))
    return cands

def pack_components(A: np.ndarray, H: int, W: int, order="by_area") -> np.ndarray:
    A = np.asarray(A, dtype=np.int8)
    h, w = A.shape
    seen = np.zeros_like(A, dtype=np.uint8)
    comps: List[Tuple[int,int,np.ndarray]] = []  # (area, color, tile)

    def flood(sr, sc, col):
        stack = [(sr, sc)]; pix = []
        seen[sr, sc] = 1
        while stack:
            r, c = stack.pop()
            pix.append((r, c))
            for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and seen[rr, cc] == 0 and A[rr, cc] == col:
                    seen[rr, cc] = 1; stack.append((rr, cc))
        return pix

    for r in range(h):
        for c in range(w):
            col = int(A[r, c])
            if col != 0 and seen[r, c] == 0:
                pix = flood(r, c, col)
                rs = [p[0] for p in pix]; cs = [p[1] for p in pix]
                r0, r1 = min(rs), max(rs)
                c0, c1 = min(cs), max(cs)
                tile = np.zeros((r1 - r0 + 1, c1 - c0 + 1), dtype=np.int8)
                for (rr, cc) in pix: tile[rr - r0, cc - c0] = col
                comps.append((len(pix), col, tile))

    if order == "by_area":
        comps.sort(key=lambda t: (-t[0], t[1]))

    out = np.zeros((H, W), dtype=np.int8)
    r = c = 0; max_row_h = 0; pad = 1
    for _, _, tile in comps:
        th, tw = tile.shape
        if th > H or tw > W:
            tile = integer_resample_nn(tile, min(H, th), min(W, tw))
            th, tw = tile.shape
        if c + tw > W:
            r += max_row_h + pad
            c = 0
            max_row_h = 0
        if r + th > H: break
        out[r:r + th, c:c + tw] = tile
        c += tw + pad
        max_row_h = max(max_row_h, th)
    return out


def make_component_family(Ht: int, Wt: int):
    return [("C:pack_area", lambda x: clamp01_09(pack_components(x, Ht, Wt, order="by_area")))]


def project_rows(A: np.ndarray, H: int, W: int, mode="any") -> np.ndarray:
    rows = (A != 0).any(1).astype(np.int8)
    cols = (A != 0).any(0).astype(np.int8)
    Br = (rows.reshape(-1, 1) * np.ones_like(A)).astype(np.int8)
    Bc = (cols.reshape(1, -1) * np.ones_like(A)).astype(np.int8)
    if mode == "any":
        B = ((Br + Bc) > 0).astype(np.int8) * max(1, int(A.max()))
    else:
        B = Br.astype(np.int8) * max(1, int(A.max()))
    return enforce_shape(B, H, W, prefer_bbox=False)


def make_projection_family(Ht: int, Wt: int):
    return [
        ("P:any",  lambda x: clamp01_09(project_rows(x, Ht, Wt, mode="any"))),
        ("P:rows", lambda x: clamp01_09(project_rows(x, Ht, Wt, mode="rows"))),
    ]

# -----------------------------
# Scoring
# -----------------------------

def L0(a: np.ndarray, b: np.ndarray) -> int:
    if a.shape != b.shape:
        return 10 ** 9
    return int((a != b).sum())


def matches_train(rule_apply: Callable[[np.ndarray], np.ndarray], train_pairs: List[Tuple[np.ndarray, np.ndarray]], early_stop: bool = True) -> int:
    total = 0
    for x, y in train_pairs:
        yp = rule_apply(x)
        sc = L0(yp, y)
        total += sc
        if early_stop and total >= 10 ** 6:
            break
    return total

# -----------------------------
# Hints / policy / bandit
# -----------------------------

def load_json(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.isfile(path):
        return {}
    with open(path, "r") as f:
        txt = f.read().strip()
        if not txt:
            return {}
        return json.loads(txt)


def load_policy_npz(path: Optional[str]) -> Dict[str, np.ndarray]:
    if not path or not os.path.isfile(path):
        return {}
    try:
        dat = np.load(path, allow_pickle=True)
        return {k: dat[k] for k in dat.files}
    except Exception:
        return {}


def load_bandit(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.isfile(path):
        return {}
    try:
        return json.load(open(path))
    except Exception:
        return {}


def save_bandit(path: Optional[str], state: Dict[str, Any]):
    if path:
        try:
            json.dump(state, open(path, "w"))
        except Exception:
            pass


def bandit_key(train_pairs: List[Tuple[np.ndarray, np.ndarray]]):
    xs, ys = zip(*train_pairs)
    dH = int(np.sign(np.mean([y.shape[0] - x.shape[0] for x, y in train_pairs])))
    dW = int(np.sign(np.mean([y.shape[1] - x.shape[1] for x, y in train_pairs])))
    pin = len(set(np.concatenate([np.unique(x) for x, y in train_pairs]).tolist()))
    pout = len(set(np.concatenate([np.unique(y) for x, y in train_pairs]).tolist()))
    compish = int(np.mean([int((x != 0).sum() > 30) for x, y in train_pairs]))
    return f"dH{dH}_dW{dW}_pin{min(pin, 6)}_pout{min(pout, 6)}_C{compish}"


def bandit_update(state, key, arm_name, reward):
    tab = state.setdefault(key, {})
    rec = tab.setdefault(arm_name, {"n": 0, "r": 0.0})
    rec["n"] += 1
    rec["r"] += float(reward)


def bandit_order(state, key, candidates: List[Tuple[str, Callable]]):
    tab = state.get(key, {})
    total_n = sum(rec["n"] for rec in tab.values()) + 1e-6
    scored = []
    for name, fn in candidates:
        rec = tab.get(name, {"n": 0, "r": 0.0})
        n = rec["n"]; r = rec["r"]
        avg = (r / max(1, n)) if n > 0 else 0.0
        ucb = avg + 1.0 * math.sqrt(2.0 * math.log(total_n + 1) / max(1, n)) if n > 0 else 10.0
        scored.append((ucb, name, fn))
    scored.sort(key=lambda t: -t[0])
    return [(name, fn) for _, name, fn in scored]

# -----------------------------
# LLM Program parsing (o3-style hints)
# -----------------------------

def parse_llm_program(prog: Dict[str, Any], H_anchor: int, W_anchor: int) -> Callable[[np.ndarray], np.ndarray]:
    """Parse a program dict with steps: [{op: ..., args: {...}}, ...]."""
    steps = prog.get("steps", []) if isinstance(prog, dict) else []

    def apply(x: np.ndarray) -> np.ndarray:
        A = x.copy()
        Ht = int(prog.get("target_shape", [H_anchor, W_anchor])[0]) if isinstance(prog.get("target_shape"), list) else H_anchor
        Wt = int(prog.get("target_shape", [H_anchor, W_anchor])[1]) if isinstance(prog.get("target_shape"), list) else W_anchor
        for s in steps:
            op = s.get("op")
            args = s.get("args", {})
            if op == "rotate":
                A = rotate_k(A, int(args.get("k", 0)))
            elif op == "flip_lr":
                A = flip_lr(A)
            elif op == "flip_ud":
                A = flip_ud(A)
            elif op == "bbox_crop":
                A = enforce_shape(A, Ht, Wt, prefer_bbox=True)
            elif op == "center_crop":
                A = enforce_shape(A, Ht, Wt, prefer_bbox=False)
            elif op == "resample":
                Hx = int(args.get("H", Ht)); Wx = int(args.get("W", Wt))
                A = integer_resample_nn(A, Hx, Wx)
            elif op == "pack_components":
                A = pack_components(A, Ht, Wt, order=args.get("order", "by_area"))
            elif op == "project_rows":
                A = project_rows(A, Ht, Wt, mode=args.get("mode", "any"))
            # palette_map: {"0":0, "1":2, ...}
            elif op == "palette_map":
                mapping = {int(k): int(v) for k, v in args.get("map", {}).items()}
                B = A.copy()
                for k, v in mapping.items():
                    B[A == k] = v
                A = B
        # final snap to target
        return enforce_shape(clamp01_09(A), Ht, Wt, prefer_bbox=(A != 0).any())

    return apply

# -----------------------------
# ShapeModel
# -----------------------------
class ShapeModel:
    def __init__(self, train_pairs: List[Tuple[np.ndarray, np.ndarray]], hint: Optional[Dict[str, Any]] = None):
        self.train_pairs = train_pairs
        self.hint = hint or {}
        ts = self.hint.get("target_shape")
        if isinstance(ts, (list, tuple)) and len(ts) == 2:
            H, W = int(ts[0]), int(ts[1])
            self.predict_fn = lambda x: (max(1, min(30, H)), max(1, min(30, W)))
        else:
            rule = self.hint.get("shape_rule")
            if isinstance(rule, str):
                fn = self._parse_rule(rule)
                self.predict_fn = fn if fn is not None else self._fit(train_pairs)
            else:
                self.predict_fn = self._fit(train_pairs)

    # ---- static helpers ----
    @staticmethod
    def _bbox_of(A: np.ndarray) -> Tuple[int, int]:
        nz = np.argwhere(A != 0)
        if nz.size == 0: return (0, 0)
        r0, c0 = nz.min(0); r1, c1 = nz.max(0)
        return (int(r1 - r0 + 1), int(c1 - c0 + 1))

    @staticmethod
    def _count_components(A: np.ndarray) -> int:
        h, w = A.shape
        seen = np.zeros((h, w), dtype=np.uint8)
        cnt = 0
        for r in range(h):
            for c in range(w):
                if A[r, c] != 0 and not seen[r, c]:
                    cnt += 1
                    stack = [(r, c)]; seen[r, c] = 1
                    col = A[r, c]
                    while stack:
                        rr, cc = stack.pop()
                        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
                            r2, c2 = rr + dr, cc + dc
                            if 0 <= r2 < h and 0 <= c2 < w and not seen[r2, c2] and A[r2, c2] == col:
                                seen[r2, c2] = 1; stack.append((r2, c2))
        return cnt

    @staticmethod
    def _features(A) -> Tuple[int, int, int, int, int, int]:
        H, W = A.shape
        bh, bw = ShapeModel._bbox_of(A)
        comp = ShapeModel._count_components(A)
        pix = int((A != 0).sum())
        return H, W, bh, bw, comp, pix

    @staticmethod
    def _clamp_pair(H, W):
        H = int(max(1, min(30, round(float(H)))))
        W = int(max(1, min(30, round(float(W)))))
        return H, W

    @staticmethod
    def _loo_score(pairs, pred_fn):
        bad = 0; dist = 0
        for x, y in pairs:
            Ht, Wt = pred_fn(x)
            Hy, Wy = y.shape
            if (Ht, Wt) != (Hy, Wy):
                bad += 1
                dist += abs(Ht - Hy) + abs(Wt - Wy)
        return (bad, dist)

    # ---- rule parsing ----
    def _parse_rule(self, rule: str):
        toks = rule.strip().split()
        if not toks: return None
        kind = toks[0].lower()
        try:
            if kind == "id":
                return lambda x: x.shape
            if kind == "swap":
                return lambda x: (x.shape[1], x.shape[0])
            if kind == "const" and len(toks) == 3:
                H, W = int(toks[1]), int(toks[2])
                return lambda x, H=H, W=W: (max(1, min(30, H)), max(1, min(30, W)))
        except Exception:
            return None
        return None

    # ---- simple fitter ----
    def _fit(self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]):
        if not train_pairs:
            return lambda x: (3, 3)

        Ysh = [(y.shape[0], y.shape[1]) for _, y in train_pairs]
        uniq, cnts = np.unique(np.array(Ysh), axis=0, return_counts=True)
        modeH, modeW = map(int, uniq[np.argmax(cnts)])

        RH = []; RW = []; dH = []; dW = []
        for x, y in train_pairs:
            yh, yw = y.shape
            H, W = x.shape
            if H > 0: RH.append(yh / max(1, H))
            if W > 0: RW.append(yw / max(1, W))
            dH.append(yh - H); dW.append(yw - W)
        sh_med = float(np.median(RH)) if RH else 1.0
        sw_med = float(np.median(RW)) if RW else 1.0
        bh_med = int(round(np.median(dH))) if dH else 0
        bw_med = int(round(np.median(dW))) if dW else 0

        # tiny ridge on features H,W,bh,bw,comp,pix,1
        X = []; YH = []; YW = []
        for x, y in train_pairs:
            yh, yw = y.shape
            H, W, bh, bw, comp, pix = self._features(x)
            X.append([H, W, bh, bw, comp, pix, 1.0])
            YH.append(yh); YW.append(yw)
        X = np.array(X, float)
        YH = np.array(YH, float); YW = np.array(YW, float)

        def ls_predictor():
            try:
                lam = 1e-3
                XtX = X.T @ X + lam * np.eye(X.shape[1])
                wH = np.linalg.solve(XtX, X.T @ YH)
                wW = np.linalg.solve(XtX, X.T @ YW)
                def f(x):
                    H, W, bh, bw, comp, pix = self._features(x)
                    v = np.array([H, W, bh, bw, comp, pix, 1.0], float)
                    Ht = float(v @ wH); Wt = float(v @ wW)
                    return self._clamp_pair(Ht, Wt)
                return f
            except Exception:
                return None
        ls_fn = ls_predictor()

        cand: List[Tuple[str, Callable[[np.ndarray], Tuple[int,int]]]] = []
        cand.append(("const_mode", lambda x, H=modeH, W=modeW: (H, W)))
        cand.append(("id", lambda x: x.shape))
        cand.append(("swap", lambda x: (x.shape[1], x.shape[0])))
        for sh in (0.5, 2/3, 1.0, 1.5, 2.0, 3.0, sh_med):
            for sw in (0.5, 2/3, 1.0, 1.5, 2.0, 3.0, sw_med):
                cand.append((f"scale_{sh}_{sw}", lambda x, sh=sh, sw=sw: self._clamp_pair(x.shape[0]*sh, x.shape[1]*sw)))
        for (ah, aw) in ((bh_med, bw_med), (0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
            cand.append((f"add_{ah}_{aw}", lambda x, ah=ah, aw=aw: self._clamp_pair(x.shape[0]+ah, x.shape[1]+aw)))
        if ls_fn is not None:
            cand.append(("ls_hybrid", ls_fn))

        best = (10 ** 9, 10 ** 9); best_fn = cand[0][1]
        for name, fn in cand:
            sc = self._loo_score(train_pairs, fn)
            if sc < best:
                best = sc; best_fn = fn

        seen_shapes = {(h, w) for (h, w) in Ysh}
        def snapped(x):
            Ht, Wt = best_fn(x)
            def key(h, w): return abs(h - Ht) + abs(w - Wt)
            if seen_shapes:
                Hc, Wc = min(seen_shapes, key=lambda hw: key(hw[0], hw[1]))
                if key(Hc, Wc) <= 2:
                    return (Hc, Wc)
            best_local = (Ht, Wt); best_cost = key(Ht, Wt)
            for dh in (-2,-1,0,1,2):
                for dw in (-2,-1,0,1,2):
                    hh, ww = self._clamp_pair(Ht + dh, Wt + dw)
                    cost = key(hh, ww)
                    if cost < best_cost:
                        best_cost = cost; best_local = (hh, ww)
            return best_local
        return snapped

    def predict(self, xA: np.ndarray) -> Tuple[int, int]:
        return self.predict_fn(xA)

# -----------------------------
# Orchestration
# -----------------------------

def family_order_from_hint(hint_family: Optional[str]) -> List[str]:
    if hint_family == "global_geom_palette": return ["G", "OF", "P", "C"]
    if hint_family == "component_mapping":    return ["C", "G", "OF", "P"]
    return ["G", "C", "OF", "P"]


def solve_one_task(task_id: str,
                   train_pairs: List[Tuple[np.ndarray, np.ndarray]],
                   test_grids: List[np.ndarray],
                   beam: int, depth: int,
                   hint: Optional[Dict[str, Any]],
                   policy: Optional[Dict[str, np.ndarray]],
                   llm_programs_for_task: List[Dict[str, Any]],
                   bandit_state: Dict[str, Any],
                   timeout_sec: int) -> List[List[np.ndarray]]:
    def handler(signum, frame):
        raise TimeoutError()
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(max(1, int(timeout_sec)))
    try:
        hint_family = (hint or {}).get("family")
        palette_hint = (hint or {}).get("palette_hint")

        shape_model = ShapeModel(train_pairs, hint)

        fam_order = family_order_from_hint(hint_family)
        def wrap_with_shape(fn: Callable[[np.ndarray], np.ndarray]):
            def g(x):
                Ht, Wt = shape_model.predict(x)
                y = fn(x)
                if y.shape != (Ht, Wt):
                    y = enforce_shape(y, Ht, Wt, prefer_bbox=(y != 0).any())
                return clamp01_09(y)
            return g

        # Build base families anchored at median predicted train shape
        pred_train_shapes = [shape_model.predict(x) for x, _ in train_pairs]
        if pred_train_shapes:
            Hm = int(round(np.median([h for h, _ in pred_train_shapes])))
            Wm = int(round(np.median([w for _, w in pred_train_shapes])))
        else:
            Hm, Wm = 3, 3

        families: List[Tuple[str, Callable[[np.ndarray], np.ndarray]]] = []
        fam_map_builder = {
            "G": lambda H, W: make_global_family(H, W, palette_hint=palette_hint,
                                                   krots=(0,1,2,3), flips=(0,1,2),
                                                   crop_modes=("center","bbox")),
            "C": lambda H, W: make_component_family(H, W),
            "OF":lambda H, W: [("OF:fillholes", lambda x: clamp01_09(enforce_shape(x, H, W, prefer_bbox=False)))],
            "P": lambda H, W: make_projection_family(H, W),
        }
        for key in fam_order:
            fam = fam_map_builder[key](Hm, Wm)
            for nm, fn in fam:
                families.append((f"{key}:{nm}", wrap_with_shape(fn)))

        # Inject LLM program(s) as extra arms
        for prog in llm_programs_for_task:
            families.append(("LLM_PROG", wrap_with_shape(parse_llm_program(prog, Hm, Wm))))

        # POLICY reorder (two logits or probs expected per task id)
        pol = policy.get(task_id) if policy else None
        if pol is not None and len(pol) >= 2:
            p_global, p_comp = float(pol[0]), float(pol[1])
            bias = {"G": p_global + 0.5, "C": p_comp + 0.5, "OF": 0.6, "P": 0.5, "L": 0.7}
            families.sort(key=lambda t: -bias.get(t[0].split(":")[0], 0.5))

        # BANDIT reorder
        key = bandit_key(train_pairs)
        families = bandit_order(bandit_state, key, families)

        # Rank on trains
        scored: List[Tuple[int, str, Callable]] = []
        cap = max(32, beam)
        for name, fn in families[:cap]:
            sc = matches_train(fn, train_pairs, early_stop=True)
            scored.append((sc, name, fn))
        scored.sort(key=lambda t: t[0])
        top = scored[:max(8, beam // 4)]
        if top:
            reward = 1.0 if top[0][0] < 10 ** 9 else 0.0
            bandit_update(bandit_state, key, top[0][1], reward)

        # one-step test-time tweak (toggle crop/bbox if improves train score)
        def ttt_refine(fn: Callable[[np.ndarray], np.ndarray]):
            def alt(x):
                Ht, Wt = shape_model.predict(x)
                y = fn(x)
                # flip preference
                y2 = enforce_shape(y, Ht, Wt, prefer_bbox=not (y != 0).any())
                # choose y or y2 via self-consistency on x (proxy)
                return y if L0(y, enforce_shape(x, Ht, Wt, prefer_bbox=True)) <= L0(y2, enforce_shape(x, Ht, Wt, prefer_bbox=True)) else y2
            return alt

        # APPLY to tests
        results: List[List[np.ndarray]] = []
        for tA in test_grids:
            cands: List[np.ndarray] = []
            for _, _, fn in top[:8]:
                fnr = ttt_refine(fn)
                y = fnr(tA)
                Ht, Wt = shape_model.predict(tA)
                if y.shape != (Ht, Wt):
                    y = enforce_shape(y, Ht, Wt, prefer_bbox=(y != 0).any())
                y = clamp01_09(y)
                cands.append(y)
            # pick two diverse
            uniq: List[np.ndarray] = []
            for y in cands:
                if not uniq or np.any(uniq[-1] != y):
                    uniq.append(y)
                if len(uniq) >= 2: break
            if len(uniq) < 2:
                Ht, Wt = shape_model.predict(tA)
                z = np.zeros((Ht, Wt), dtype=np.int8)
                uniq = uniq + [z]
            results.append(uniq[:2])
        return results
    except TimeoutError:
        sm = ShapeModel(train_pairs)
        out = []
        for tA in test_grids:
            Ht, Wt = sm.predict(tA)
            z = np.zeros((Ht, Wt), dtype=np.int8)
            out.append([z.copy(), z.copy()])
        return out
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

# -----------------------------
# Build & CLI
# -----------------------------

def _load_challenges_json(path):
    data = json.load(open(path))
    if isinstance(data, dict) and "challenges" in data and isinstance(data["challenges"], dict):
        return data["challenges"]
    return data


def _ensure_two(preds: List[np.ndarray], H: int, W: int):
    if not preds:
        z = np.zeros((H, W), dtype=np.int8)
        return z.tolist(), z.tolist()
    if len(preds) == 1:
        a = preds[0].astype(int).tolist(); return a, a
    return preds[0].astype(int).tolist(), preds[1].astype(int).tolist()


def build_from_challenges(ch_path: str,
                          beam: int = 256,
                          depth: int = 2,
                          policy_npz: Optional[str] = None,
                          llm_hints_path: Optional[str] = None,
                          llm_programs_path: Optional[str] = None,
                          bandit_state_path: Optional[str] = None,
                          timeout_sec: int = 30) -> Dict[str, Any]:
    raw = _load_challenges_json(ch_path)
    llm_hints = load_json(llm_hints_path)
    policy = load_policy_npz(policy_npz)
    bandit_state = load_bandit(bandit_state_path)

    # normalize llm_programs: dict task_id -> (dict or list[dict])
    llm_programs_raw = load_json(llm_programs_path)
    def programs_for(task_id: str) -> List[Dict[str, Any]]:
        if not llm_programs_raw: return []
        v = llm_programs_raw.get(task_id)
        if v is None: return []
        if isinstance(v, list): return [vi for vi in v if isinstance(vi, dict)]
        if isinstance(v, dict): return [v]
        return []

    submission = {}
    for task_id, spec in raw.items():
        train_pairs = [(to_np(z["input"]), to_np(z["output"])) for z in spec.get("train", [])]
        tests = [to_np(z["input"]) for z in spec.get("test", [])]
        preds = solve_one_task(
            task_id, train_pairs, tests,
            beam=beam, depth=depth,
            hint=llm_hints.get(task_id),
            policy=policy,
            llm_programs_for_task=programs_for(task_id),
            bandit_state=bandit_state,
            timeout_sec=timeout_sec,
        )
        per_task = []
        sm = ShapeModel(train_pairs, llm_hints.get(task_id))
        for i, x in enumerate(tests):
            Ht, Wt = sm.predict(x)
            cand = preds[i] if i < len(preds) else []
            a1, a2 = _ensure_two(cand, Ht, Wt)
            per_task.append({"attempt_1": a1, "attempt_2": a2})
        submission[task_id] = per_task

    save_bandit(bandit_state_path, bandit_state)
    return submission


def _parse_argv(argv: List[str]):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--beam", type=int, default=256)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--timeout_sec", type=int, default=30)
    ap.add_argument("--policy", type=str, default=None, help="(opt) tiny policy npz")
    ap.add_argument("--llm_hints", type=str, default=None, help="(opt) task_id->hint json")
    ap.add_argument("--llm_programs", type=str, default=None, help="(opt) task_id->program(s) json")
    ap.add_argument("--bandit_state", type=str, default="bandit_state.json", help="(opt) RL memory json")
    return ap.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_argv(sys.argv[1:])
    sub = build_from_challenges(args.input,
                                beam=args.beam,
                                depth=args.depth,
                                policy_npz=args.policy,
                                llm_hints_path=args.llm_hints,
                                llm_programs_path=args.llm_programs,
                                bandit_state_path=args.bandit_state,
                                timeout_sec=args.timeout_sec)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    json.dump(sub, open(args.output, "w"))
    print(f"Wrote {args.output} with {len(sub)} tasks")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


