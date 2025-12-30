# safe_submission_builder.py
from __future__ import annotations
import json, os, sys, time, signal
from typing import Dict, List, Tuple
import numpy as np

from components import Grid
from solver_plus import SolverPlus, SolverPlusConfig
from heuristics import heuristics_two_attempts

# ------------------------
# Timeouts (POSIX only)
# ------------------------
class Timeout(Exception): pass

def _handle_timeout(signum, frame):
    raise Timeout()

def with_timeout(seconds, fn, *args, **kwargs):
    """Run fn(*args, **kwargs) with a soft POSIX alarm; return (ok, value_or_err)."""
    old = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(seconds)
    try:
        val = fn(*args, **kwargs)
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        return True, val
    except Timeout as e:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        return False, e
    except Exception as e:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
        return False, e

# ------------------------
# I/O helpers
# ------------------------
def _to_grid(a) -> Grid:
    return Grid(np.array(a, dtype=np.int8))

def _from_grid(g: Grid) -> List[List[int]]:
    return g.data.astype(int).tolist()

def _ensure_two_attempts(preds: List[Grid], fallback_shape: Tuple[int,int]) -> List[Grid]:
    out = list(preds)
    # pad with zeros
    while len(out) < 2:
        out.append(Grid(np.zeros(fallback_shape, dtype=np.int8)))
    # truncate if >2
    return out[:2]

def _coerce_shape(g: Grid, shape: Tuple[int,int]) -> Grid:
    """Force shape by center crop/pad (lossless for equal shapes)."""
    H, W = shape
    a = g.data
    h, w = a.shape
    if (h, w) == (H, W):
        return g
    out = np.zeros((H, W), dtype=a.dtype)
    ih = min(H, h); iw = min(W, w)
    src_r0 = (h - ih)//2; src_c0 = (w - iw)//2
    dst_r0 = (H - ih)//2; dst_c0 = (W - iw)//2
    out[dst_r0:dst_r0+ih, dst_c0:dst_c0+iw] = a[src_r0:src_r0+ih, src_c0:src_c0+iw]
    return Grid(out)

def _infer_test_shapes(task: dict) -> List[Tuple[int,int]]:
    shapes = []
    for t in task["test"]:
        arr = np.array(t["input"], dtype=np.int8)
        shapes.append(arr.shape)
    return shapes

# ------------------------
# Core per-task solve
# ------------------------
def solve_one_task(task: dict,
                   sym_cfg: SolverPlusConfig,
                   sym_timeout_s: int = 12,
                   heuristics_first: bool = False) -> List[Dict[str, List[List[int]]]]:
    """
    Returns a list with len == len(task['test']) and each element:
      {"attempt_1": grid, "attempt_2": grid}
    """
    train_pairs = [(_to_grid(p["input"]), _to_grid(p["output"])) for p in task["train"]]
    test_inputs = [_to_grid(t["input"]) for t in task["test"]]
    test_shapes = _infer_test_shapes(task)

    solver = SolverPlus(sym_cfg)

    def _symbolic():
        return solver.solve_task(train_pairs, test_inputs)

    # Strategy: heuristic-first if requested (super fast), otherwise symbolic then heuristic fallback
    preds_sym: List[List[Grid]] = []
    if heuristics_first:
        preds = heuristics_two_attempts(train_pairs, test_inputs)
        preds_sym = preds  # treat as already-two-attempts
    else:
        ok, val = with_timeout(sym_timeout_s, _symbolic)
        if ok and isinstance(val, list) and all(isinstance(v, list) for v in val) and len(val) == len(test_inputs):
            preds_sym = val
        else:
            preds_sym = []  # will fallback to heuristics

        # If symbolic emitted empty predictions for any test, we’ll fill those with heuristics
        need_heur = (not preds_sym) or any(len(x) == 0 for x in preds_sym)
        if need_heur:
            preds_heur = heuristics_two_attempts(train_pairs, test_inputs)
            if not preds_sym:
                preds_sym = preds_heur
            else:
                # merge per test: if symbolic empty, use heuristics for that test
                merged: List[List[Grid]] = []
                for i, preds in enumerate(preds_sym):
                    merged.append(preds if preds else preds_heur[i])
                preds_sym = merged

    # Final guards: shape + exactly 2 attempts
    out_json: List[Dict[str, List[List[int]]]] = []
    for i, preds in enumerate(preds_sym):
        shape = test_shapes[i]
        preds = [_coerce_shape(p, shape) for p in preds]
        preds = _ensure_two_attempts(preds, shape)
        out_json.append({
            "attempt_1": _from_grid(preds[0]),
            "attempt_2": _from_grid(preds[1]),
        })
    return out_json

# ------------------------
# Public entry
# ------------------------
def build_from_challenges(inp_path: str,
                          out_path: str,
                          beam: int = 256,
                          depth: int = 2,
                          sym_timeout_s: int = 12,
                          heuristics_first: bool = False) -> None:
    d = json.load(open(inp_path))
    out: Dict[str, List[Dict[str, List[List[int]]]]] = {}

    sym_cfg = SolverPlusConfig(
        beam=beam,
        max_depth=depth,
        use_prune=True,
        use_repair=True,
        use_heuristic_fallback=True,   # also inside solver_plus
        use_llm_fallback=False         # keep Kaggle-safe; can flip via env if needed
    )

    start = time.time()
    for k, task in d.items():
        out[k] = solve_one_task(task, sym_cfg, sym_timeout_s=sym_timeout_s,
                                heuristics_first=heuristics_first)
    json.dump(out, open(out_path, "w"))
    print(f"Wrote {out_path} with {len(out)} tasks in {time.time()-start:.1f}s")

# CLI
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--beam", type=int, default=256)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=12, help="symbolic timeout per task (sec)")
    ap.add_argument("--heuristics_first", action="store_true",
                    help="skip symbolic and use heuristics directly (fast baseline)")
    args = ap.parse_args()
    build_from_challenges(args.input, args.output, args.beam, args.depth,
                          sym_timeout_s=args.timeout,
                          heuristics_first=args.heuristics_first)
