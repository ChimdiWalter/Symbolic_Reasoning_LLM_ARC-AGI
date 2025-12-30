# solver_plus.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import os
import numpy as np

from components import Grid
from pipeline import build_scene_bundle
from dsl import Program
from search import GenConfig, enumerate_and_rank, verify_on_pairs
from vision_solver import solve_with_llm_fallback
from prune import early_prune_candidates
from repair import repair_programs, RepairConfig

# Optional LLM client entrypoint (only used if ARC_LLM_FALLBACK=1)
try:
    from llm_client import llm_rule as _default_llm_fn  # type: ignore
except Exception:
    _default_llm_fn = None  # still works without


@dataclass
class SolverPlusConfig:
    beam: int = 256
    max_depth: int = 2
    policy: Optional[object] = None
    # prune
    use_prune: bool = True
    # repair
    use_repair: bool = True
    repair_trans_radius: int = 1
    repair_trans_steps: int = 1
    repair_axis_flip: bool = True
    repair_rot_k: bool = True
    repair_color_swaps: bool = True
    # fallback toggles
    use_llm_fallback: bool = bool(int(os.getenv("ARC_LLM_FALLBACK", "0")))
    use_heuristic_fallback: bool = True


class SolverPlus:
    def __init__(self, cfg: SolverPlusConfig):
        self.cfg = cfg

    # --------------------------
    # Heuristic fallback helpers
    # --------------------------
    @staticmethod
    def _zeros_like(test: Grid) -> Grid:
        return Grid(np.zeros_like(test.data, dtype=test.data.dtype))

    @staticmethod
    def _copy_train_output_if_shape_match(
        train_pairs: List[Tuple[Grid, Grid]],
        test: Grid
    ) -> Optional[Grid]:
        """
        If any training input has exactly the same shape as this test,
        return its paired output as a naive guess (shape-correct).
        """
        for xin, yout in train_pairs:
            if xin.data.shape == test.data.shape:
                return Grid(np.array(yout.data, copy=True))
        return None

    @staticmethod
    def _pixelwise_color_map(x: np.ndarray, y: np.ndarray) -> Optional[np.ndarray]:
        """
        Build a color→color mapping from a SAME-SHAPE pair (x->y).
        If mapping is contradictory (same input color maps to multiple output colors),
        we fall back to the most frequent output for each input color.

        Returns: an array 'lut' of shape (10,) that maps each color 0..9 -> 0..9,
                 or None if we cannot infer anything.
        """
        if x.shape != y.shape:
            return None
        # tally (in_color, out_color) counts
        counts = np.zeros((10, 10), dtype=np.int64)
        xv = x.reshape(-1)
        yv = y.reshape(-1)
        for a, b in zip(xv, yv):
            if 0 <= a <= 9 and 0 <= b <= 9:
                counts[a, b] += 1
        # build lut by argmax over output colors per input color
        lut = np.arange(10, dtype=np.int8)
        any_use = False
        for c in range(10):
            row = counts[c]
            if row.sum() > 0:
                any_use = True
                lut[c] = np.int8(row.argmax())
        return lut if any_use else None

    @classmethod
    def _apply_color_lut(cls, arr: np.ndarray, lut: np.ndarray) -> np.ndarray:
        out = np.array(arr, copy=True)
        # vectorized map: for 0..9 only
        mask = (out >= 0) & (out <= 9)
        out[mask] = lut[out[mask]]
        return out

    @classmethod
    def _color_map_guess_if_shape_match(
        cls,
        train_pairs: List[Tuple[Grid, Grid]],
        test: Grid
    ) -> Optional[Grid]:
        """
        For the first training pair with the same shape as this test, infer a
        pixelwise color mapping (x->y) and apply to the test.
        """
        for xin, yout in train_pairs:
            if xin.data.shape == test.data.shape:
                lut = cls._pixelwise_color_map(xin.data, yout.data)
                if lut is not None:
                    guess = cls._apply_color_lut(test.data, lut)
                    return Grid(guess)
        return None

    def _heuristic_fallback(
        self,
        train_pairs: List[Tuple[Grid, Grid]],
        tests: List[Grid]
    ) -> List[List[Grid]]:
        """
        Produce up to 2 attempts per test using simple heuristics:
        1) If a train input shape matches the test shape, copy that train's output.
        2) If shapes match as well, try a per-pixel color map from that train pair.
        3) Otherwise fall back to zeros – so you always emit two attempts.
        """
        outs: List[List[Grid]] = []
        for t in tests:
            # A1: copy paired output if shape matches any train input
            a1 = self._copy_train_output_if_shape_match(train_pairs, t)
            # A2: color map guess if same-shape pair exists
            a2 = self._color_map_guess_if_shape_match(train_pairs, t)

            # Make sure you return exactly two attempts (Kaggle format)
            guesses: List[Grid] = []
            if a1 is not None:
                guesses.append(a1)
            if a2 is not None and (a1 is None or not np.array_equal(a2.data, a1.data)):
                guesses.append(a2)
            # pad with zeros if needed
            while len(guesses) < 2:
                guesses.append(self._zeros_like(t))
            outs.append(guesses[:2])
        return outs

    # --------------------------
    # Main solve
    # --------------------------
    def solve_task(
        self,
        train_pairs: List[Tuple[Grid, Grid]],
        tests: List[Grid]
    ) -> List[List[Grid]]:
        # ---------- Symbolic-first ----------
        x0, y0 = train_pairs[0]
        B0 = build_scene_bundle(x0)
        gen = GenConfig(max_depth=self.cfg.max_depth, beam=self.cfg.beam)

        beam = enumerate_and_rank(train_pairs, gen, policy=self.cfg.policy)
        # Optional: early prune
        if self.cfg.use_prune and beam:
            beam, _ = early_prune_candidates(x0, y0, beam)

        # Gate on first pair and verify
        survivors: List[Program] = []
        for p in beam:
            try:
                yhat0 = p.run(x0, B0)
            except Exception:
                continue
            if np.array_equal(yhat0.data, y0.data):
                survivors.append(p)

        verified: List[Program] = []
        misses: List[Program] = []
        for p in survivors:
            try:
                ok = verify_on_pairs(p, train_pairs)
            except Exception:
                ok = False
            if ok:
                verified.append(p)
            else:
                misses.append(p)

        # Optional light “repair”
        if self.cfg.use_repair and misses and len(verified) < 2:
            rcfg = RepairConfig(
                trans_radius=self.cfg.repair_trans_radius,
                trans_steps=self.cfg.repair_trans_steps,
                try_axis_flip=self.cfg.repair_axis_flip,
                try_rot_k=self.cfg.repair_rot_k,
                try_color_swaps=self.cfg.repair_color_swaps,
            )
            try:
                repaired = repair_programs(misses, train_pairs, rcfg)
                if repaired:
                    verified.extend(repaired)
            except Exception:
                pass

        # If we have symbolic programs, produce predictions
        if verified:
            topk = verified[:2]
            preds_all: List[List[Grid]] = []
            for x in tests:
                B = build_scene_bundle(x)
                preds = []
                for p in topk:
                    try:
                        preds.append(p.run(x, B))
                    except Exception:
                        preds.append(self._zeros_like(x))
                # always 2 attempts
                if len(preds) == 1:
                    preds.append(preds[0])
                preds_all.append(preds[:2])
            return preds_all

        # ---------- Heuristic fallback ----------
        if self.cfg.use_heuristic_fallback:
            return self._heuristic_fallback(train_pairs, tests)

        # ---------- LLM fallback (optional) ----------
        if self.cfg.use_llm_fallback and _default_llm_fn is not None:
            try:
                llm_dicts = solve_with_llm_fallback(
                    train_pairs=train_pairs,
                    test_inputs=tests,
                    llm_fn=_default_llm_fn,
                    max_trials=int(os.getenv("ARC_LLM_MAX_TRIALS", "2")),
                )
                outs: List[List[Grid]] = []
                for d in llm_dicts:
                    a1 = Grid(np.array(d["attempt_1"], dtype=int))
                    a2 = Grid(np.array(d["attempt_2"], dtype=int))
                    outs.append([a1, a2])
                return outs
            except Exception:
                pass

        # nothing worked: return empty lists for shape compliance
        return [[] for _ in tests]


if __name__ == "__main__":
    # Tiny smoke test
    arr = np.array([[0,2,2],[0,0,0],[0,0,0]], dtype=np.int8)
    g = Grid(arr)
    train = [(g, g)]
    tests = [g]
    sv = SolverPlus(SolverPlusConfig())
    outs = sv.solve_task(train, tests)
    print("ok", [len(x) for x in outs])
