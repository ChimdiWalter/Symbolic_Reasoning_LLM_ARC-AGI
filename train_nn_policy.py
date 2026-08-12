# train_nn_policy.py
from __future__ import annotations
from typing import List, Tuple, Dict, Any
import json, argparse
import numpy as np
from nn_policy import fe_task_summary

def _to_np(M): return np.array(M, dtype=np.int8)
def _arr(x):
    if isinstance(x, dict) and "output" in x: x = x["output"]
    return _to_np(x)

def load_training(train_json: str, sol_json: str):
    with open(train_json, "r") as f:
        train = json.load(f)
    with open(sol_json, "r") as f:
        sols = json.load(f)
    X=[]; y=[]  # features, label index (0=global,1=component)
    for tid, spec in train.items():
        pairs = [(_to_np(p["input"]), _to_np(p["output"])) for p in spec.get("train",[])]
        tests = [_to_np(t["input"]) for t in spec.get("test",[])]
        # crude heuristic label: if output looks like translated per-shape with same size -> component; else global.
        # (You can refine later.)
        label = 0
        if pairs:
            xs, ys = zip(*pairs)
            same_size = all(x.shape == y.shape for x,y in pairs)
            # centroid consistency heuristic
            def centroid(a):
                ys, xs = np.where(a!=0)
                return (ys.mean(), xs.mean()) if ys.size else (0,0)
            cen_d = np.mean([abs(centroid(x)[0]-centroid(y)[0])+abs(centroid(x)[1]-centroid(y)[1]) for x,y in pairs])
            label = 1 if (same_size and cen_d<5.0) else 0
        feats = fe_task_summary(pairs)
        X.append(feats); y.append(label)
    X = np.stack(X,0)
    y = np.array(y, int)
    return X,y

def train_linear(X,y, lr=0.05, iters=200):
    # Two-class linear (one-vs-rest): W shape (D, C=2)
    D = X.shape[1]; C=2
    W = np.zeros((D,C), np.float32)
    for it in range(iters):
        # softmax regression
        z = X @ W  # (N,C)
        z -= z.max(axis=1, keepdims=True)
        e = np.exp(z)
        p = e / e.sum(axis=1, keepdims=True)
        # grad
        T = np.eye(C, dtype=np.float32)[y]
        g = X.T @ (p - T) / float(X.shape[0])
        W -= lr * g
    return W

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)   # arc-agi_training_challenges.json
    ap.add_argument("--solutions", required=True) # arc-agi_training_solutions.json (not strictly needed here)
    ap.add_argument("--out", required=True)     # nn_policy.npz
    args = ap.parse_args()

    X,y = load_training(args.train, args.solutions)
    W = train_linear(X,y, lr=0.05, iters=200)
    np.savez(args.out, W=W)
    print("Saved", args.out, "| W shape:", W.shape)

if __name__ == "__main__":
    main()
