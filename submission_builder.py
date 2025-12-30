# submission_builder.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os, sys, json, glob, re
import numpy as np

# your project imports
from components import Grid
from solver_plus import SolverPlus, SolverPlusConfig
from heuristics import heuristics_two_attempts

# If you wired a stronger miner, keep this import.
# Otherwise, fall back to your existing miner module.
try:
    from rule_miner_stronger import infer_two_attempts  # expects np arrays I/O
    _HAS_STRONGER_MINER = True
except Exception:
    try:
        from rule_miner import infer_two_attempts  # fallback
        _HAS_STRONGER_MINER = False
    except Exception:
        infer_two_attempts = None
        _HAS_STRONGER_MINER = False


# ------------------ small utils ------------------

def _to_np(grid_list: List[List[int]]) -> np.ndarray:
    return np.asarray(grid_list, dtype=np.int8)

def _sanitize10(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.int16, copy=False)
    a[a < 0] = 0
    a[a > 9] = 9
    return a.astype(np.int8, copy=False)

def _is_all_zero(a: np.ndarray) -> bool:
    return a.size == 0 or (a == 0).all()

def _mode(items: List[Tuple[int,int]]) -> Tuple[int,int]:
    # most common (H,W)
    if not items:
        return (1,1)
    vals, counts = np.unique(np.array(items, dtype=int), axis=0, return_counts=True)
    return tuple(vals[counts.argmax()].tolist())  # (H,W)

def _infer_shape_from_train(
    train_pairs: List[Tuple[Grid, Grid]],
    test_input_shape: Tuple[int,int]
) -> Tuple[int,int]:
    """
    Heuristic shape inference:
      1) If all train outputs share one (H,W), use that.
      2) Else, check consistent ΔH=Hout-Hin and ΔW=Wout-Win; if consistent, apply to test.
      3) Else, check consistent integer ratios Hout/Hin and Wout/Win; if consistent, apply (round).
      4) Else, fallback to mode of train output shapes.
      5) Clamp to [1..30].
    """
    if not train_pairs:
        return test_input_shape

    in_shapes  = [(p[0].data.shape[0], p[0].data.shape[1]) for p in train_pairs]
    out_shapes = [(p[1].data.shape[0], p[1].data.shape[1]) for p in train_pairs]
    Hin, Win   = zip(*in_shapes)
    Hout, Wout = zip(*out_shapes)
    Ht, Wt     = test_input_shape

    # 1) constant shape?
    if len(set(out_shapes)) == 1:
        return out_shapes[0]

    # 2) consistent deltas?
    dH = set([Ho - Hi for Hi,Ho in zip(Hin,Hout)])
    dW = set([Wo - Wi for Wi,Wo in zip(Win,Wout)])
    if len(dH) == 1 and len(dW) == 1:
        H = Ht + list(dH)[0]
        W = Wt + list(dW)[0]
        H = int(max(1, min(30, H)))
        W = int(max(1, min(30, W)))
        return (H,W)

    # 3) consistent ratios (integer-ish)?
    def _ratios_ok(numer, denom):
        R = []
        for n,d in zip(numer, denom):
            if d == 0:
                return None
            r = n / d
            # allow small floating noise; try rounding if near integer
            r_rounded = round(r)
            if abs(r - r_rounded) < 1e-6 and r_rounded >= 1 and r_rounded <= 5:
                R.append(r_rounded)
            else:
                return None
        if len(set(R)) == 1:
            return R[0]
        return None

    rH = _ratios_ok(Hout, Hin)
    rW = _ratios_ok(Wout, Win)
    if (rH is not None) and (rW is not None):
        H = int(max(1, min(30, round(Ht * rH))))
        W = int(max(1, min(30, round(Wt * rW))))
        return (H,W)

    # 4) fallback: mode of output shapes
    Hm, Wm = _mode(out_shapes)
    Hm = int(max(1, min(30, Hm)))
    Wm = int(max(1, min(30, Wm)))
    return (Hm, Wm)

def _center_crop(a: np.ndarray, H: int, W: int) -> np.ndarray:
    h, w = a.shape
    r0 = max(0, (h - H) // 2)
    c0 = max(0, (w - W) // 2)
    return a[r0:r0+H, c0:c0+W]

def _center_pad(a: np.ndarray, H: int, W: int, pad_val: int = 0) -> np.ndarray:
    h, w = a.shape
    out = np.full((H, W), pad_val, dtype=a.dtype)
    r0 = max(0, (H - h) // 2)
    c0 = max(0, (W - w) // 2)
    rr = min(H, r0 + h)
    cc = min(W, c0 + w)
    oh = rr - r0
    ow = cc - c0
    out[r0:rr, c0:cc] = a[:oh, :ow]
    return out

def _coerce_shape(a: np.ndarray, target: Tuple[int,int], pad_val: int = 0) -> np.ndarray:
    a = np.asarray(a, dtype=np.int8)
    H,W = target
    h,w = a.shape
    if h == H and w == W:
        return a
    if h >= H and w >= W:
        return _center_crop(a, H, W)
    # otherwise we need some pad (and maybe crop in one dim)
    a2 = a
    if h > H:
        a2 = _center_crop(a2, H, a2.shape[1])
    if a2.shape[1] > W:
        a2 = _center_crop(a2, a2.shape[0], W)
    return _center_pad(a2, H, W, pad_val=pad_val)

def _dominant_nonzero_color_from_trains(train_pairs: List[Tuple[Grid,Grid]]) -> int:
    hist = np.zeros(10, dtype=np.int64)
    for _, y in train_pairs:
        yy = y.data
        for c in range(1, 10):
            hist[c] += np.count_nonzero(yy == c)
    if hist[1:].sum() == 0:
        return 1
    # most frequent non-zero
    return int(1 + np.argmax(hist[1:]))

def _bbox_mask(a: np.ndarray) -> Optional[Tuple[int,int,int,int]]:
    """Return (r0,r1,c0,c1) over non-zero, or None."""
    nz = np.argwhere(a != 0)
    if nz.size == 0:
        return None
    r0 = int(nz[:,0].min()); r1 = int(nz[:,0].max()) + 1
    c0 = int(nz[:,1].min()); c1 = int(nz[:,1].max()) + 1
    return (r0,r1,c0,c1)

def _bbox_projection_guess(x: np.ndarray, target: Tuple[int,int]) -> np.ndarray:
    """
    Take bbox of non-zero in X; if empty, return zeros.
    Coerce to target via crop/pad.
    """
    bb = _bbox_mask(x)
    if bb is None:
        guess = np.zeros(target, dtype=np.int8)
        return guess
    r0,r1,c0,c1 = bb
    crop = x[r0:r1, c0:c1]
    guess = _coerce_shape(crop, target, pad_val=0)
    return guess


# ------------------ main solver ------------------

def solve_task(train_pairs: List[Tuple[Grid, Grid]],
               tests: List[Grid],
               beam: int = 256,
               depth: int = 2,
               policy_npz: Optional[str] = None,
               llm_hints: Optional[Dict[str,str]] = None,
               task_id: Optional[str] = None) -> List[List[Grid]]:
    """
    Returns list (len = #tests) of [Grid, Grid] (two attempts per test).
    """
    # 0) Preload priors from policy if you actually use them in miner
    priors = None
    if policy_npz and os.path.exists(policy_npz):
        try:
            dat = np.load(policy_npz, allow_pickle=True)
            priors = dict(dat.items())
        except Exception:
            priors = None

    # 1) symbolic solver first
    sv = SolverPlus(SolverPlusConfig(
        beam=beam, max_depth=depth,
        use_prune=True, use_repair=True,
        policy=None  # leave None unless your SolverPlus consumes priors
    ))
    sym_outs: Optional[List[List[Grid]]] = None
    try:
        sym_outs = sv.solve_task(train_pairs, tests)
    except Exception:
        sym_outs = None

    # 2) miner (np I/O)
    miner_outs_np: Optional[List[List[np.ndarray]]] = None
    if infer_two_attempts is not None:
        tr_np = [(p[0].data, p[1].data) for p in train_pairs]
        te_np = [t.data for t in tests]
        try:
            # If your stronger miner accepts hints, pass them; otherwise ignore.
            miner_outs_np = infer_two_attempts(
                tr_np, te_np,
                policy=priors,
                # if your miner supports these kwargs; else remove:
                family_hint=(llm_hints.get(task_id) if (llm_hints and task_id in llm_hints) else None),
            )
        except TypeError:
            # older signature without hints
            try:
                miner_outs_np = infer_two_attempts(tr_np, te_np, policy=priors)
            except Exception:
                miner_outs_np = None
        except Exception:
            miner_outs_np = None

    # 3) Merge per-test with shape guard & non-zero fallback
    finals: List[List[Grid]] = []
    for i, x in enumerate(tests):
        x_np = x.data
        # infer target shape from train pairs and test input shape
        target_shape = _infer_shape_from_train(train_pairs, x_np.shape)

        chosen: List[np.ndarray] = []

        # symbolic
        if sym_outs is not None and i < len(sym_outs) and sym_outs[i]:
            for g in sym_outs[i][:2]:
                chosen.append(np.array(g.data, copy=True))

        # miner (np arrays)
        if miner_outs_np is not None and i < len(miner_outs_np):
            for yhat in miner_outs_np[i]:
                if yhat is None:
                    continue
                chosen.append(np.array(yhat, copy=True))

        # heuristics (last resort to add diversity)
        if len(chosen) < 2:
            try:
                hs = heuristics_two_attempts(train_pairs, [x])[0]
                for g in hs:
                    chosen.append(np.array(g.data, copy=True))
            except Exception:
                pass

        # ensure at least something: add our non-zero fallbacks
        # 1) bbox projection
        if len(chosen) < 2:
            chosen.append(_bbox_projection_guess(x_np, target_shape))
        # 2) solid fill of dominant color from train outputs (or inputs if needed)
        if len(chosen) < 2:
            dom_color = _dominant_nonzero_color_from_trains(train_pairs)
            solid = np.full(target_shape, dom_color, dtype=np.int8)
            chosen.append(solid)

        # pad/trim to two
        if not chosen:
            z = np.zeros(target_shape, dtype=np.int8)
            chosen = [z, z]
        elif len(chosen) == 1:
            chosen = [chosen[0], chosen[0].copy()]
        else:
            chosen = chosen[:2]

        # coerce shapes and clamp to [0..9]
        coerced = []
        for k in range(2):
            a = chosen[k]
            # if miner/symbolic guessed silly sizes (e.g., 30x30 default), coerce to target
            a = _coerce_shape(a, target_shape, pad_val=0)
            a = _sanitize10(a)
            coerced.append(a)

        # breaker: avoid both-zero outputs
        if _is_all_zero(coerced[0]) and _is_all_zero(coerced[1]):
            # keep attempt_1 as is; force attempt_2 to dominant solid
            dom_color = _dominant_nonzero_color_from_trains(train_pairs)
            coerced[1] = np.full(target_shape, dom_color, dtype=np.int8)

        finals.append([Grid(coerced[0]), Grid(coerced[1])])

    return finals


# --------------- build helpers ---------------

def _load_challenges_json(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, dict) and "challenges" in data and isinstance(data["challenges"], dict):
        return data["challenges"]
    return data

def _ensure_two(preds: List[np.ndarray], H: int, W: int) -> Tuple[List[List[int]], List[List[int]]]:
    if not preds:
        z = [[0]*W for _ in range(H)]
        return z, z
    if len(preds) == 1:
        a = preds[0].astype(int).tolist()
        return a, a
    return preds[0].astype(int).tolist(), preds[1].astype(int).tolist()

def build_from_folder(folder: str, beam: int = 256, depth: int = 2,
                      policy_npz: Optional[str]=None,
                      llm_hints: Optional[Dict[str,str]] = None) -> Dict[str, Any]:
    submission: Dict[str, Any] = {}
    files = sorted(glob.glob(os.path.join(folder, "*.json")))
    hex_re = re.compile(r"([0-9a-fA-F]{8})\.json$")
    for p in files:
        m = hex_re.search(os.path.basename(p))
        if not m: 
            continue
        task_id = m.group(1)
        with open(p, "r") as f:
            spec = json.load(f)
        train_pairs = [(Grid(_to_np(z["input"])), Grid(_to_np(z["output"]))) for z in spec.get("train", [])]
        tests = [Grid(_to_np(z["input"])) for z in spec.get("test", [])]

        preds = solve_task(
            train_pairs, tests, beam=beam, depth=depth,
            policy_npz=policy_npz, llm_hints=llm_hints, task_id=task_id
        )

        per_task = []
        for i, x in enumerate(tests):
            H, W = x.data.shape
            cand = [g.data for g in preds[i]] if i < len(preds) else []
            a1, a2 = _ensure_two(cand, H, W)
            per_task.append({"attempt_1": a1, "attempt_2": a2})
        submission[task_id] = per_task
    return submission

def build_from_challenges(ch_path: str, beam: int = 256, depth: int = 2,
                          policy_npz: Optional[str]=None,
                          llm_hints_path: Optional[str]=None) -> Dict[str, Any]:
    raw = _load_challenges_json(ch_path)

    # load hints if provided
    hints: Optional[Dict[str,str]] = None
    if llm_hints_path and os.path.exists(llm_hints_path):
        try:
            with open(llm_hints_path, "r") as f:
                hints = json.load(f)
        except Exception:
            hints = None

    submission: Dict[str, Any] = {}
    for task_id, spec in raw.items():
        train_pairs = [(Grid(_to_np(z["input"])), Grid(_to_np(z["output"]))) for z in spec.get("train", [])]
        tests = [Grid(_to_np(z["input"])) for z in spec.get("test", [])]

        preds = solve_task(
            train_pairs, tests, beam=beam, depth=depth,
            policy_npz=policy_npz, llm_hints=hints, task_id=task_id
        )

        per_task = []
        for i, x in enumerate(tests):
            H, W = x.data.shape
            cand = [g.data for g in preds[i]] if i < len(preds) else []
            a1, a2 = _ensure_two(cand, H, W)
            per_task.append({"attempt_1": a1, "attempt_2": a2})
        submission[task_id] = per_task
    return submission


# ------------------ CLI ------------------

def _parse_argv(argv: List[str]):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--beam",   type=int, default=256)
    ap.add_argument("--depth",  type=int, default=2)
    ap.add_argument("--policy", type=str, default=None, help="optional path to .npz policy")
    ap.add_argument("--llm_hints", type=str, default=None, help="optional JSON map: task_id -> family hint")
    return ap.parse_args(argv)

def main(argv: List[str]) -> int:
    args = _parse_argv(sys.argv[1:])
    if os.path.isdir(args.input):
        sub = build_from_folder(args.input, beam=args.beam, depth=args.depth,
                                policy_npz=args.policy, llm_hints=None)  # folder mode: pass hints as needed
    else:
        sub = build_from_challenges(args.input, beam=args.beam, depth=args.depth,
                                    policy_npz=args.policy, llm_hints_path=args.llm_hints)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(sub, f)
    print(f"Wrote {args.output} with {len(sub)} tasks")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
