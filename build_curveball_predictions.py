# build_curveball_predictions.py
# usage:
#   python3 build_curveball_predictions.py data/curveball submission_curveball.json \
#       llm_hints_completed.json llm_programs.json policy_weights.npz
from __future__ import annotations
import os, sys, json, numpy as np
from glob import glob
from typing import Dict, Any, List, Tuple, Optional
import sb_hybrid as sb

def load_json(path: Optional[str]) -> Any:
    if not path or not os.path.isfile(path): return {}
    with open(path, "r") as f: return json.load(f)

def family_pool(Hm: int, Wm: int, pal_hint=None):
    fams = []
    fams += [(f"G:{nm}", fn)  for (nm,fn) in sb.make_global_family(Hm, Wm, pal_hint)]
    fams += [(f"C:{nm}", fn)  for (nm,fn) in sb.make_component_family(Hm, Wm)]
    fams += [(f"OF:{nm}",fn)  for (nm,fn) in sb.make_outline_fill_family(Hm, Wm)]
    fams += [(f"P:{nm}", fn)  for (nm,fn) in sb.make_projection_family(Hm, Wm)]
    return fams

def solve_task(train_pairs, test_in, hint: Dict[str,Any]):
    # choose a safe target shape
    Ht, Wt = sb.choose_target_shape(test_in, train_pairs)
    # anchor shape for family generation (median predicted == target here)
    Hm, Wm = Ht, Wt
    pal_hint = hint.get("palette_hint") if isinstance(hint, dict) else None

    # build pool
    fams = family_pool(Hm, Wm, pal_hint=pal_hint)

    # rank by train L0
    scored = []
    for name,fn in fams:
        def wrapped(x, fn=fn):
            y = fn(x)
            if y.shape != (Ht,Wt): y = sb.pad_or_crop_to(y, Ht, Wt)
            return y
        sc = sb.matches_train(wrapped, train_pairs)
        scored.append((sc, name, wrapped))
    scored.sort(key=lambda t: t[0])
    best = scored[0][2] if scored else (lambda x: sb.pad_or_crop_to(x, Ht, Wt))

    # predict one output for curve-ball (single attempt)
    y = best(test_in)
    if y.shape != (Ht,Wt): y = sb.pad_or_crop_to(y, Ht, Wt)
    return y

def main(curve_dir, out_json, llm_hints_path=None, llm_prog_path=None, policy_npz_path=None):
    llm_hints = load_json(llm_hints_path)
    # (llm_prog, policy) not used here, but kept for interface completeness
    tasks = {}
    for p in sorted(glob(os.path.join(curve_dir, "*.json"))):
        tid = os.path.splitext(os.path.basename(p))[0]  # example01
        spec = json.load(open(p))
        train_pairs = [(sb.to_np(z["input"]), sb.to_np(z["output"])) for z in spec.get("train",[])]
        test_list = spec.get("test", [])
        if not test_list:
            continue
        test_in = sb.to_np(test_list[0]["input"])
        hint = llm_hints.get(tid, {})
        y = solve_task(train_pairs, test_in, hint)
        # store a *full* ARC record with test output filled
        tasks[tid] = {
            "train": spec["train"],
            "test":  [{"input": test_list[0]["input"], "output": y.astype(int).tolist()}]
        }
    json.dump(tasks, open(out_json, "w"))
    print(f"Wrote {out_json} with {len(tasks)} curve-ball tasks")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python build_curveball_predictions.py data/curveball submission_curveball.json [llm_hints.json] [llm_programs.json] [policy.npz]")
        sys.exit(1)
    curve_dir   = sys.argv[1]
    out_json    = sys.argv[2]
    llm_hints   = sys.argv[3] if len(sys.argv)>3 else None
    llm_prog    = sys.argv[4] if len(sys.argv)>4 else None
    policy      = sys.argv[5] if len(sys.argv)>5 else None
    main(curve_dir, out_json, llm_hints, llm_prog, policy)

