# submission_builder.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os, sys, json, re, gc, time
import numpy as np

# --- local imports ---
from components import Grid
from solver_plus import SolverPlus, SolverPlusConfig
from heuristics import heuristics_two_attempts

# Prefer stronger miner if you have it, else fall back to rule_miner
try:
    from rule_miner_stronger import infer_two_attempts as miner_infer_two_attempts
except Exception:
    from rule_miner import infer_two_attempts as miner_infer_two_attempts  # type: ignore

# optional extras
try:
    import dsl_extra  # noqa: F401
except Exception:
    pass

# -------- utils --------
def _to_np(grid_list: List[List[int]]) -> np.ndarray:
    return np.asarray(grid_list, dtype=np.int8)

def _ensure_two(preds: List[np.ndarray], H: int, W: int) -> Tuple[List[List[int]], List[List[int]]]:
    if not preds:
        z = [[0]*W for _ in range(H)]
        return z, z
    if len(preds) == 1:
        a = preds[0].astype(int).tolist()
        return a, a
    return preds[0].astype(int).tolist(), preds[1].astype(int).tolist()

def _load_challenges_json(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, dict) and "challenges" in data and isinstance(data["challenges"], dict):
        return data["challenges"]
    return data

def _sanitize10(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.int16, copy=False)
    if a.size:
        a[a < 0] = 0
        a[a > 9] = 9
    return a.astype(np.int8, copy=False)

# -------- core per-task solve --------
def solve_task(
    train_pairs: List[Tuple[Grid, Grid]],
    tests: List[Grid],
    beam: int = 64,
    depth: int = 2,
    policy_npz: Optional[str] = None,
    max_sizes: int = 10,
    perm_beam: int = 24,
) -> List[List[Grid]]:
    # SYMBOLIC (keep light)
    sym_outs: Optional[List[List[Grid]]] = None
    try:
        sv = SolverPlus(SolverPlusConfig(
            beam=beam, max_depth=depth, use_prune=True, use_repair=True, policy=None
        ))
        sym_outs = sv.solve_task(train_pairs, tests)
    except Exception:
        sym_outs = None

    # Miner (works on np arrays; respects policy if miner uses it internally)
    tr_np = [(x.data, y.data) for (x,y) in train_pairs]
    te_np = [t.data for t in tests]

    priors = None
    if policy_npz and os.path.exists(policy_npz):
        try:
            dat = np.load(policy_npz, allow_pickle=True)
            priors = dict(dat.items())
        except Exception:
            priors = None

    try:
        miner_outs_np: List[List[np.ndarray]] = miner_infer_two_attempts(
            tr_np, te_np, policy=priors, geom_radius=2, perm_beam=perm_beam, keep_top=2
        )
    except Exception:
        miner_outs_np = [[] for _ in te_np]

    finals: List[List[Grid]] = []
    for i, x in enumerate(tests):
        chosen: List[np.ndarray] = []

        # symbolic first
        if sym_outs is not None and i < len(sym_outs) and sym_outs[i]:
            for g in sym_outs[i][:2]:
                chosen.append(np.array(g.data, copy=True))

        # miner next
        if len(chosen) < 2 and i < len(miner_outs_np):
            for yhat in miner_outs_np[i]:
                if len(chosen) < 2:
                    chosen.append(np.array(yhat, copy=True))

        # heuristics fallback
        if len(chosen) < 2:
            try:
                hs = heuristics_two_attempts(train_pairs, [x])[0]
                for g in hs:
                    if len(chosen) < 2:
                        chosen.append(np.array(g.data, copy=True))
            except Exception:
                pass

        # pad/trim and sanitize
        H, W = x.data.shape
        if not chosen:
            z = np.zeros((H, W), np.int8); chosen=[z,z]
        elif len(chosen)==1:
            chosen=[chosen[0], chosen[0].copy()]
        else:
            chosen = chosen[:2]

        chosen = [_sanitize10(c) for c in chosen]
        finals.append([Grid(chosen[0]), Grid(chosen[1])])

    # free miner buffers
    del tr_np, te_np
    gc.collect()
    return finals

# -------- streaming builders --------
def _iter_tasks(ch_path: str):
    raw = _load_challenges_json(ch_path)
    # deterministic order for stable commas in streaming JSON
    for tid in sorted(raw.keys()):
        yield tid, raw[tid]

def build_streaming(
    ch_path: str,
    out_path: str,
    beam: int = 64,
    depth: int = 2,
    policy_npz: Optional[str] = None,
    perm_beam: int = 24,
):
    # Precount tasks for clean comma placement
    raw = _load_challenges_json(ch_path)
    tids = sorted(raw.keys())
    n = len(tids)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write("{\n")
        for idx, tid in enumerate(tids):
            spec = raw[tid]
            train_pairs = [(Grid(_to_np(z["input"])), Grid(_to_np(z["output"]))) for z in spec.get("train", [])]
            tests = [Grid(_to_np(z["input"])) for z in spec.get("test", [])]

            # Solve this task
            preds = solve_task(train_pairs, tests, beam=beam, depth=depth, policy_npz=policy_npz, perm_beam=perm_beam)

            # Convert results for streaming write
            per_task = []
            for i, x in enumerate(tests):
                H, W = x.data.shape
                cand = [g.data for g in preds[i]] if i < len(preds) else []
                a1, a2 = _ensure_two(cand, H, W)
                per_task.append({"attempt_1": a1, "attempt_2": a2})

            # Write one entry
            f.write(f"  \"{tid}\": ")
            json.dump(per_task, f)
            if idx < n-1:
                f.write(",\n")
            else:
                f.write("\n")

            # free per-task memory
            del train_pairs, tests, preds, per_task, cand
            gc.collect()
        f.write("}\n")

# -------- CLI --------
def _parse_argv(argv: List[str]):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  required=True, help="challenges_eval.json or folder of tasks")
    ap.add_argument("--output", required=True, help="submission.json")
    ap.add_argument("--beam",   type=int, default=64)
    ap.add_argument("--depth",  type=int, default=2)
    ap.add_argument("--policy", type=str, default=None, help="optional .npz prior for miner")
    ap.add_argument("--perm_beam", type=int, default=24, help="palette beam inside miner")
    return ap.parse_args(argv)

def main(argv: List[str]) -> int:
    args = _parse_argv(sys.argv[1:])
    t0 = time.time()
    build_streaming(
        ch_path=args.input,
        out_path=args.output,
        beam=args.beam,
        depth=args.depth,
        policy_npz=args.policy,
        perm_beam=args.perm_beam,
    )
    print(f"Wrote {args.output} in {time.time()-t0:.1f}s")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
