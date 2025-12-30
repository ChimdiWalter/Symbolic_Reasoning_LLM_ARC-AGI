# rl_bandit.py
from __future__ import annotations
from typing import Dict, List
import numpy as np

class SoftmaxBandit:
    """
    Per-family bandit using softmax over preferences; updates with negative L0 loss.
    No external libs; safe for Kaggle.
    """
    def __init__(self, families: List[str], tau: float = 0.5, lr: float = 0.2):
        self.families = list(families)
        self.tau = float(tau)
        self.lr = float(lr)
        self.pref = {f: 0.0 for f in families}

    def probs(self) -> Dict[str,float]:
        vs = np.array([self.pref[f] for f in self.families], float)
        vs = vs / max(1e-6, self.tau)
        ex = np.exp(vs - vs.max())
        p  = ex / ex.sum()
        return {f: float(p[i]) for i,f in enumerate(self.families)}

    def update(self, family: str, reward: float):
        # gradient step on chosen family
        self.pref[family] = self.pref.get(family, 0.0) + self.lr * reward

    def choose(self) -> str:
        ps = self.probs()
        names = list(ps.keys())
        probs = np.array([ps[n] for n in names], float)
        idx = int(np.random.choice(len(names), p=probs))
        return names[idx]
