#!/usr/bin/env python3
"""TRM inference: task dict -> predicted grid for each test input.

Mirrors build_dataset.py's serialization exactly (identity augmentation):
3 demo pairs + query input as [7,30,30] channels, PAD=10, canvas 30.
Runs N_SUP refinement steps with the EMA weights; decodes by trimming
the PAD frontier (largest top-left rectangle of non-PAD argmax cells).

Usage:
  from trm.infer import TRMSolver
  solver = TRMSolver("trm/checkpoints/ema_only.pt")
  grids = solver.solve(task_dict)   # one [list-of-lists] grid per test
"""
import os
import numpy as np
import torch

from trm.model import TRM, CANVAS, SEQ, VOCAB
from trm.build_dataset import pad_grid, PAD, MAX_DEMOS

N_SUP = int(os.environ.get("TRM_INFER_NSUP", "16"))


def encode_task(train_pairs, test_input):
    chan = []
    for di, do in train_pairs[:MAX_DEMOS]:
        chan.append(pad_grid(di))
        chan.append(pad_grid(do))
    while len(chan) < 2 * MAX_DEMOS:
        chan.append(np.full((CANVAS, CANVAS), PAD, dtype=np.int8))
    chan.append(pad_grid(test_input))
    return np.stack(chan)  # [7,30,30]


def decode_grid(pred):
    """pred: [30,30] int array of argmax tokens -> trimmed list-of-lists."""
    nonpad = pred != PAD
    if not nonpad.any():
        return [[0]]
    rows = np.where(nonpad.any(axis=1))[0]
    cols = np.where(nonpad.any(axis=0))[0]
    h, w = rows.max() + 1, cols.max() + 1
    g = pred[:h, :w].copy()
    g[g == PAD] = 0  # interior PAD holes -> background
    return g.astype(int).tolist()


class TRMSolver:
    def __init__(self, ckpt_path, device=None):
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu")
        ck = torch.load(ckpt_path, map_location=self.device)
        cfg = ck.get("cfg", {"d": 256, "layers": 2})
        self.model = TRM(**cfg).to(self.device)
        state = ck.get("ema", ck.get("model", ck))
        self.model.load_state_dict(state)
        self.model.eval()
        self.epoch = ck.get("epoch", -1)

    @torch.no_grad()
    def solve(self, task):
        """task: ARC dict with 'train' and 'test'. Returns list of grids."""
        pairs = [(p["input"], p["output"]) for p in task["train"]]
        if any(len(g) > CANVAS or len(g[0]) > CANVAS
               for pr in pairs for g in pr):
            return [None for _ in task["test"]]
        out = []
        for tc in task["test"]:
            ti = tc["input"]
            if len(ti) > CANVAS or len(ti[0]) > CANVAS:
                out.append(None)
                continue
            x = torch.from_numpy(
                encode_task(pairs, ti).astype(np.int64)
            ).unsqueeze(0).to(self.device)
            y = z = None
            for _ in range(N_SUP):
                logits, y, z, halt = self.model(x, y, z)
            pred = logits.argmax(-1).view(CANVAS, CANVAS).cpu().numpy()
            out.append(decode_grid(pred))
        return out


if __name__ == "__main__":
    import json
    import sys
    ckpt = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "checkpoints", "ema_only.pt")
    solver = TRMSolver(ckpt, device="cpu")
    chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
    sols = json.load(open("data/arc/arc-agi_training_solutions.json"))
    tids = sorted(chal)[:20]
    correct = 0
    for tid in tids:
        preds = solver.solve(chal[tid])
        for i, p in enumerate(preds):
            if p is not None and i < len(sols[tid]) and p == sols[tid][i]:
                correct += 1
    print(f"epoch={solver.epoch} sample-20 exact: {correct}/{len(tids)}")
