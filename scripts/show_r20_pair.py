#!/usr/bin/env python3
"""Print an ARC train pair side by side (R20 tracing aid)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = json.load(open(os.path.join(ROOT,
                                 "data/arc/arc-agi_training_challenges.json")))


def show(tid, idx=None):
    tr = CH[tid]["train"]
    idxs = range(len(tr)) if idx is None else [idx]
    for i in idxs:
        gi, go = tr[i]["input"], tr[i]["output"]
        print(f"--- {tid} pair{i}  in {len(gi)}x{len(gi[0])}  "
              f"out {len(go)}x{len(go[0])} ---")
        n = max(len(gi), len(go))
        for r in range(n):
            a = "".join(str(v) for v in gi[r]) if r < len(gi) else ""
            b = "".join(str(v) for v in go[r]) if r < len(go) else ""
            print(f"  {a:<{len(gi[0])}}   |  {b}")


if __name__ == "__main__":
    show(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
