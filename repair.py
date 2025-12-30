from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from components import Grid
from dsl import Program
from pipeline import build_scene_bundle

@dataclass
class RepairConfig:
    # These field names/semantics are what SolverPlus expects
    trans_radius: int = 1
    trans_steps: int = 1
    try_axis_flip: bool = True
    try_rot_k: bool = True
    try_color_swaps: bool = True

def verify_on_pairs(p: Program, train_pairs: List[Tuple[Grid, Grid]]) -> bool:
    """Verify a program across all train pairs."""
    for x, y in train_pairs:
        B = build_scene_bundle(x)
        yhat = p.run(x, B)
        if not np.array_equal(yhat.data, y.data):
            return False
    return True

def repair_programs(programs: List[Program],
                    train_pairs: List[Tuple[Grid, Grid]],
                    cfg: RepairConfig) -> List[Program]:
    """
    Minimal repair stub:
    - Return programs that already verify on all pairs (no mutation yet).
    - Keeps pipeline wiring working. You can add real mutations later.
    """
    repaired: List[Program] = []
    for p in programs:
        try:
            if verify_on_pairs(p, train_pairs):
                repaired.append(p)
        except Exception:
            # If a program crashes, skip it
            pass
    return repaired
