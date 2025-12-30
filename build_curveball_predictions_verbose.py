# build_curveball_predictions_verbose.py
# usage:
#   python3 build_curveball_predictions_verbose.py data/curveball submission_curveball.json \
#       llm_hints_completed.json
from __future__ import annotations
import os, sys, json, numpy as np
from glob import glob
from typing import Dict, Any, List, Tuple, Optional
import sb_hybrid as sb

def load_json(path: Optional[str]) -> Any:
    if not path or not os.path.isfile(path): return {}
    with open(path, "r") as f: return json.load(f)

def grid_to_str(A: np.ndarray) -> str:
    # compact terminal view (digits), 0 = dot
    chars = " .123456789"
    out = []
    for r in range(A.shape[0]):
        out.append("".join(chars[min(9,int(A[r,c]))] for c in range(A.shape[1])))
    return "\n".join(out)

def family_pool(Hm: int, Wm: int, pal_hint=None):
    fams = []
    fams += [(f"G:{nm}", fn)  for (nm,fn) in sb.make_global_family(Hm, Wm, pal_hint)]
    fams += [(f"C:{nm}", fn)  for (nm,fn) in sb.make_component_family(Hm, Wm)]
    fams += [(f"OF:{nm}",fn)  for (nm,fn) in sb.make_outline_fill_family(Hm, Wm)]
    fams += [(f"P:{nm}", fn)  for (nm,fn) in sb.make_projection_family(Hm, Wm)]
    return fams

def solve_task_verbose(task_id: str, train_pairs, test_in, hint: Dict[str,Any], show_examples=False):
    Ht, Wt = sb.choose_target_shape(test_in, train_pairs)
    Hm, Wm = Ht, Wt
    pal_hint = hint.get("palette_hint") if isinstance(hint, dict) else None

    fams = family_pool(Hm, Wm, pal_hint=pal_hint)

    print(f"\n=== {task_id} ===")
    print(f"target_shape: {(Ht,Wt)}  pal_hint: {pal_hint}")
    print("Train pairs:", [(x.shape, y.shape) for x,y in train_pairs][:3], ("..." if len(train_pairs)>3 else ""))

    scored = []
    for name,fn in fams:
        def wrapped(x, fn=fn):
            y = fn(x)
            if y.shape != (Ht,Wt): y = sb.pad_or_crop_to(y, Ht, Wt)
            return y
        sc = sb.matches_train(wrapped, train_pairs)
        scored.append((sc, name, wrapped))
    scored.sort(key=lambda t: t[0])

    # print top-5 L0 scores
    print("Top families by L0 on train:")
    for sc, name, _ in scored[:5]:
        print(f"  L0={sc:6d}  {name}")

    best_name = scored[0][1] if scored else "IDENT"
    best = scored[0][2] if scored else (lambda x: sb.pad_or_crop_to(x, Ht, Wt))
    print(f"Chosen family: {best_name}")

    y = best(test_in)
    if y.shape != (Ht,Wt): y = sb.pad_or_crop_to(y, Ht, Wt)

    if show_examples:
        print("\nInput (test):")
        print(grid_to_str(test_in))
        print("\nOutput (guess):")
        print(grid_to_str(y))

    return y, best_name

def main(curve_dir, out_json, llm_hints_path=None):
    llm_hints = load_json(llm_hints_path)
    tasks = {}
    names = sorted(os.path.basename(p) for p in glob(os.path.join(curve_dir, "*.json")))
    example01_done = False

    for fname in names:
        tid = os.path.splitext(fname)[0]  # e.g., example01
        spec = json.load(open(os.path.join(curve_dir, fname)))
        train_pairs = [(sb.to_np(z["input"]), sb.to_np(z["output"])) for z in spec.get("train",[])]
        test_list = spec.get("test", [])
        if not test_list:
            continue
        test_in = sb.to_np(test_list[0]["input"])
        hint = llm_hints.get(tid, {})

        # Show grids for example01 for your video
        show = (tid == "example01" and not example01_done)
        y, fam = solve_task_verbose(tid, train_pairs, test_in, hint, show_examples=show)
        example01_done = example01_done or show

        tasks[tid] = {
            "train": spec["train"],
            "test":  [{"input": test_list[0]["input"], "output": y.astype(int).tolist()}]
        }

    json.dump(tasks, open(out_json, "w"))
    print(f"\nWrote {out_json} with {len(tasks)} curve-ball tasks")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python build_curveball_predictions_verbose.py data/curveball submission_curveball.json [llm_hints.json]")
        sys.exit(1)
    curve_dir   = sys.argv[1]
    out_json    = sys.argv[2]
    llm_hints   = sys.argv[3] if len(sys.argv)>3 else None
    main(curve_dir, out_json, llm_hints)

