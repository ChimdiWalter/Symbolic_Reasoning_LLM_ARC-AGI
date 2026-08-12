from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np

from components import Grid
from pipeline import build_scene_bundle
from dsl import Program
from search import GenConfig, enumerate_and_rank, verify_on_pairs, predict_on_tests
from repair import repair_programs, RepairConfig

@dataclass
class SolverConfig:
    beam: int = 128
    max_depth: int = 2
    policy: Optional[object] = None
    # Repair controls
    use_repair: bool = True
    repair_trans_radius: int = 1
    repair_trans_steps: int = 1
    repair_axis_flip: bool = True
    repair_rot_k: bool = True
    repair_color_swaps: bool = True


class Solver:
    def __init__(self, cfg: SolverConfig):
        self.cfg = cfg

    def solve_task(self, train_pairs: List[Tuple[Grid, Grid]], tests: List[Grid]) -> List[List[Grid]]:
        """Return a list of predictions per test input (pass@2) from top programs."""
        x0, y0 = train_pairs[0]
        B0 = build_scene_bundle(x0)
        gen = GenConfig(max_depth=self.cfg.max_depth, beamsize=self.cfg.beam)
        beam = enumerate_and_rank(B0, gen, policy=self.cfg.policy)

        # 1) initial-pair gate
        survivors: List[Program] = []
        for p in beam:
            yhat0 = p.run(x0, B0)
            if np.array_equal(yhat0.data, y0.data):
                survivors.append(p)

        # 2) full verify on all training pairs
        verified: List[Program] = []
        near_miss: List[Program] = []
        for p in survivors:
            if verify_on_pairs(p, train_pairs):
                verified.append(p)
            else:
                near_miss.append(p)

        # 2b) optional near-miss repair sweep
        if self.cfg.use_repair and near_miss and len(verified) < 2:
            rcfg = RepairConfig(
                trans_radius=self.cfg.repair_trans_radius,
                trans_steps=self.cfg.repair_trans_steps,
                try_axis_flip=self.cfg.repair_axis_flip,
                try_rot_k=self.cfg.repair_rot_k,
                try_color_swaps=self.cfg.repair_color_swaps,
            )
            for p in near_miss:
                repaired_ok = repair_programs([p], train_pairs, rcfg)
                # Extend but keep some cap to avoid overgrowth
                for q in repaired_ok:
                    if q not in verified:
                        verified.append(q)
                    if len(verified) >= 4:  # small bound
                        break
                if len(verified) >= 4:
                    break

        if not verified:
            # fallback: return empty preds (no solutions)
            return [[] for _ in tests]

        # 3) pass@2 per test: take top-2 verified programs
        topk = verified[:2]
        preds_all = []
        for x in tests:
            B = build_scene_bundle(x)
            preds = []
            for p in topk:
                preds.append(p.run(x, B))
            preds_all.append(preds)
        return preds_all


if __name__ == "__main__":
    # Dummy small example just to wire the API
    arr = np.array([[0,1,1],[0,1,0],[2,0,0]], dtype=np.int8)
    g = Grid(arr)
    # Fake training: identity mapping
    train_pairs = [(g, g)]
    tests = [g]
    sv = Solver(SolverConfig())
    outs = sv.solve_task(train_pairs, tests)
    print("#test preds:", len(outs[0]) if outs and outs[0] is not None else 0)
