#!/usr/bin/env python3
"""GuidePredictor — rank action kinds/families for a real ARC task.

Usage (module):
  from guide.predict import GuidePredictor
  gp = GuidePredictor()                    # guide/checkpoints/latest.pt
  ranked = gp.rank(task_dict)              # {"kinds": [(name,p)...],
                                           #  "families": [(name,p)...]}
CLI smoke: python guide/predict.py [n_tasks=5] — prints predictions for
the first n real ARC training tasks.
"""
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guide.model import GuideNet, CANVAS
from guide.train_guide import pad_grid, MAXP, PAD


class GuidePredictor:
    def __init__(self, ckpt=None, device=None):
        ckpt = ckpt or os.path.join(os.path.dirname(__file__),
                                    "checkpoints", "latest.pt")
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu")
        ck = torch.load(ckpt, map_location=self.device)
        self.kinds = ck["kinds"]
        self.families = ck["families"]
        self.model = GuideNet(len(self.kinds), len(self.families)).to(
            self.device)
        self.model.load_state_dict(ck["model"])
        self.model.eval()
        self.epoch = ck.get("epoch", -1)

    @torch.no_grad()
    def rank(self, task):
        pairs = task["train"][:MAXP]
        xi = np.full((1, MAXP, CANVAS, CANVAS), PAD, dtype=np.int64)
        xo = np.full_like(xi, PAD)
        for p, pr in enumerate(pairs):
            xi[0, p] = pad_grid(pr["input"])
            xo[0, p] = pad_grid(pr["output"])
        np_ = torch.tensor([len(pairs)], device=self.device)
        lk, lf = self.model(torch.from_numpy(xi).to(self.device),
                            torch.from_numpy(xo).to(self.device), np_)
        pk = torch.sigmoid(lk)[0].cpu()
        pf = torch.softmax(lf, -1)[0].cpu()
        return {
            "kinds": sorted(zip(self.kinds, pk.tolist()),
                            key=lambda t: -t[1]),
            "families": sorted(zip(self.families, pf.tolist()),
                               key=lambda t: -t[1]),
        }


if __name__ == "__main__":
    import json
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    gp = GuidePredictor()
    chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
    for tid in sorted(chal)[:n]:
        r = gp.rank(chal[tid])
        top_k = ", ".join(f"{k}:{p:.2f}" for k, p in r["kinds"][:4])
        top_f = ", ".join(f"{f}:{p:.2f}" for f, p in r["families"][:3])
        print(f"{tid}  kinds[{top_k}]  fams[{top_f}]")
