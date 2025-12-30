# make_task_descriptions.py
import json, argparse, numpy as np
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List, Tuple

def np_arr(x):
    return np.array(x, dtype=np.int8)

def palette(a: np.ndarray):
    return [int(v) for v in np.unique(a)]

def comp_count(a: np.ndarray) -> int:
    # very cheap proxy: number of (non-zero) 4-connected components across all colors
    # to keep things simple (fast), we count components per color and sum.
    H, W = a.shape
    visited = np.zeros_like(a, dtype=bool)
    def dfs(sr, sc, color):
        stack = [(sr,sc)]
        visited[sr,sc] = True
        while stack:
            r,c = stack.pop()
            for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                rr,cc = r+dr, c+dc
                if 0<=rr<H and 0<=cc<W and not visited[rr,cc] and a[rr,cc]==color:
                    visited[rr,cc] = True
                    stack.append((rr,cc))

    count = 0
    for color in np.unique(a):
        if color == 0:  # ignore background for signal
            continue
        coords = np.argwhere((a==color) & (~visited))
        for r,c in coords:
            if not visited[r,c]:
                dfs(r,c,color)
                count += 1
    return int(count)

def bbox(mask: np.ndarray):
    rs, cs = np.where(mask)
    if rs.size == 0: return None
    return (int(rs.min()), int(rs.max()), int(cs.min()), int(cs.max()))

def centroid(a: np.ndarray):
    rs, cs = np.nonzero(a != 0)
    if rs.size == 0: return (None, None)
    return (float(rs.mean()), float(cs.mean()))

def pair_features(x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    fx = {
        "in_size": f"{x.shape[0]}x{x.shape[1]}",
        "in_palette": palette(x),
        "in_components": comp_count(x),
        "in_centroid": centroid(x),
    }
    fy = {
        "out_size": f"{y.shape[0]}x{y.shape[1]}",
        "out_palette": palette(y),
        "out_components": comp_count(y),
        "out_centroid": centroid(y),
    }
    # coarse diffs
    size_changed = fx["in_size"] != fy["out_size"]
    pal_x, pal_y = set(fx["in_palette"]), set(fy["out_palette"])
    palette_mode = {
        "subset": pal_y.issubset(pal_x),
        "superset": pal_x.issubset(pal_y) and pal_y!=pal_x,
        "equal": pal_x==pal_y
    }
    crx, ccx = fx["in_centroid"]
    cry, ccy = fy["out_centroid"]
    centroid_shift = None
    if crx is not None and cry is not None:
        centroid_shift = (round(cry-crx,2), round(ccy-ccx,2))
    return {
        **fx, **fy,
        "size_changed": bool(size_changed),
        "palette_relation": palette_mode,
        "centroid_shift": centroid_shift
    }

def build_prompt(task_id: str, pairs: List[Dict[str,Any]]) -> str:
    # compact, deterministic prompt the LLM can handle quickly
    lines = [f"Task {task_id}: decide the best high-level family."]
    lines.append("Choose ONE label strictly from: global_geom_palette, component_mapping.")
    lines.append("Heuristic guide:")
    lines.append("- global_geom_palette: single global rotation/flip/translate + palette permutation; often uniform size among outputs; shapes move as a whole.")
    lines.append("- component_mapping: per-component copy/shift/recolor; components may move relative to each other; color remaps differ per component.")
    lines.append("Training pairs summary:")
    for i,p in enumerate(pairs,1):
        lines.append(
            f" Pair {i}: in={p['in_size']}, out={p['out_size']}, "
            f"pal_in={p['in_palette']}, pal_out={p['out_palette']}, "
            f"comp_in={p['in_components']}, comp_out={p['out_components']}, "
            f"centroid_shift={p['centroid_shift']}, "
            f"size_changed={p['size_changed']}, "
            f"palette_relation={p['palette_relation']}"
        )
    lines.append('Answer with a strict JSON object: {"family": "<one of the two>"} and nothing else.')
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenges", required=True, help="path to arc-agi_*_challenges.json")
    ap.add_argument("--out", default="task_descriptions.jsonl")
    args = ap.parse_args()

    data = json.load(open(args.challenges))
    if "challenges" in data: data = data["challenges"]

    with open(args.out, "w") as fout:
        for tid, spec in data.items():
            pairs = []
            for tr in spec.get("train", []):
                x = np_arr(tr["input"]); y = np_arr(tr["output"])
                pairs.append(pair_features(x,y))
            prompt = build_prompt(tid, pairs)
            rec = {"task_id": tid, "prompt": prompt}
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
