"""Residual corrector — analyzes near-solve errors and learns patches.

When a rule gets most cells right but not all, this module:
1. Identifies the wrong pixels
2. Builds a correction function from the error pattern
3. Composes: corrected(grid) = correction(base_rule(grid))

Correction strategies (escalating complexity):
- Global color swap: all wrong pixels have color A but should be color B
- Input-conditional swap: swap based on what the INPUT pixel was
- Neighborhood-conditional: use local context to decide correction
- Positional-modular: learn (r%k, c%k, pred_color) -> correct_color
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
import numpy as np
from typing import Callable


@dataclass
class Correction:
    strategy: str
    mapping: dict
    accuracy_gain: float

    def apply(self, predicted: np.ndarray, input_grid: np.ndarray) -> np.ndarray:
        return self._apply_fn(predicted, input_grid)

    def _apply_fn(self, predicted: np.ndarray, input_grid: np.ndarray) -> np.ndarray:
        raise NotImplementedError


@dataclass
class GlobalSwapCorrection(Correction):
    def _apply_fn(self, predicted: np.ndarray, input_grid: np.ndarray) -> np.ndarray:
        result = predicted.copy()
        for old_color, new_color in self.mapping.items():
            result[predicted == old_color] = new_color
        return result


@dataclass
class InputConditionalCorrection(Correction):
    def _apply_fn(self, predicted: np.ndarray, input_grid: np.ndarray) -> np.ndarray:
        result = predicted.copy()
        h, w = result.shape
        for r in range(h):
            for c in range(w):
                key = (int(input_grid[r, c]), int(predicted[r, c]))
                if key in self.mapping:
                    result[r, c] = self.mapping[key]
        return result


@dataclass
class NeighborhoodCorrection(Correction):
    def _apply_fn(self, predicted: np.ndarray, input_grid: np.ndarray) -> np.ndarray:
        result = predicted.copy()
        h, w = result.shape
        for r in range(h):
            for c in range(w):
                key = self._context_key(predicted, input_grid, r, c)
                if key in self.mapping:
                    result[r, c] = self.mapping[key]
        return result

    def _context_key(self, pred: np.ndarray, inp: np.ndarray, r: int, c: int) -> tuple:
        h, w = pred.shape

        def _g(grid, rr, cc):
            if 0 <= rr < h and 0 <= cc < w:
                return int(grid[rr, cc])
            return -1

        return (
            int(inp[r, c]),
            int(pred[r, c]),
            _g(inp, r - 1, c), _g(inp, r + 1, c),
            _g(inp, r, c - 1), _g(inp, r, c + 1),
        )


@dataclass
class PositionalModularCorrection(Correction):
    mod_r: int = 2
    mod_c: int = 2

    def _apply_fn(self, predicted: np.ndarray, input_grid: np.ndarray) -> np.ndarray:
        result = predicted.copy()
        h, w = result.shape
        for r in range(h):
            for c in range(w):
                key = (r % self.mod_r, c % self.mod_c, int(input_grid[r, c]), int(predicted[r, c]))
                if key in self.mapping:
                    result[r, c] = self.mapping[key]
        return result


def analyze_residual(
    predictions: list[np.ndarray],
    targets: list[np.ndarray],
    inputs: list[np.ndarray],
) -> dict:
    wrong_cells = []
    correct_cells = []

    for pred, tgt, inp in zip(predictions, targets, inputs):
        if pred.shape != tgt.shape:
            continue
        h, w = pred.shape
        for r in range(h):
            for c in range(w):
                entry = {
                    "r": r, "c": c,
                    "pred": int(pred[r, c]),
                    "target": int(tgt[r, c]),
                    "input": int(inp[r, c]),
                }
                if pred[r, c] != tgt[r, c]:
                    wrong_cells.append(entry)
                else:
                    correct_cells.append(entry)

    total = len(wrong_cells) + len(correct_cells)
    return {
        "num_wrong": len(wrong_cells),
        "num_correct": len(correct_cells),
        "accuracy": len(correct_cells) / total if total > 0 else 0.0,
        "wrong_cells": wrong_cells,
        "correct_cells": correct_cells,
    }


def try_global_swap(
    predictions: list[np.ndarray],
    targets: list[np.ndarray],
    inputs: list[np.ndarray],
) -> GlobalSwapCorrection | None:
    swap_map: dict[int, Counter] = {}

    for pred, tgt in zip(predictions, targets):
        if pred.shape != tgt.shape:
            return None
        h, w = pred.shape
        for r in range(h):
            for c in range(w):
                pc, tc = int(pred[r, c]), int(tgt[r, c])
                if pc != tc:
                    if pc not in swap_map:
                        swap_map[pc] = Counter()
                    swap_map[pc][tc] += 1

    if not swap_map:
        return None

    mapping = {}
    for old_c, target_counts in swap_map.items():
        if len(target_counts) == 1:
            mapping[old_c] = target_counts.most_common(1)[0][0]
        else:
            return None

    corrected_preds = []
    for pred in predictions:
        cp = pred.copy()
        for old_c, new_c in mapping.items():
            cp[pred == old_c] = new_c
        corrected_preds.append(cp)

    for cp, tgt in zip(corrected_preds, targets):
        if not np.array_equal(cp, tgt):
            return None

    return GlobalSwapCorrection(
        strategy="global_swap",
        mapping=mapping,
        accuracy_gain=1.0,
    )


def try_input_conditional(
    predictions: list[np.ndarray],
    targets: list[np.ndarray],
    inputs: list[np.ndarray],
) -> InputConditionalCorrection | None:
    mapping: dict[tuple, set[int]] = {}

    for pred, tgt, inp in zip(predictions, targets, inputs):
        if pred.shape != tgt.shape or inp.shape != tgt.shape:
            return None
        h, w = pred.shape
        for r in range(h):
            for c in range(w):
                key = (int(inp[r, c]), int(pred[r, c]))
                val = int(tgt[r, c])
                if key not in mapping:
                    mapping[key] = set()
                mapping[key].add(val)

    resolved = {}
    for key, vals in mapping.items():
        if len(vals) == 1:
            resolved[key] = next(iter(vals))
        else:
            return None

    for pred, tgt, inp in zip(predictions, targets, inputs):
        h, w = pred.shape
        for r in range(h):
            for c in range(w):
                key = (int(inp[r, c]), int(pred[r, c]))
                if resolved.get(key) != int(tgt[r, c]):
                    return None

    nontrivial = any(k[1] != v for k, v in resolved.items())
    if not nontrivial:
        return None

    return InputConditionalCorrection(
        strategy="input_conditional",
        mapping=resolved,
        accuracy_gain=1.0,
    )


def try_neighborhood_correction(
    predictions: list[np.ndarray],
    targets: list[np.ndarray],
    inputs: list[np.ndarray],
) -> NeighborhoodCorrection | None:
    dummy = NeighborhoodCorrection(strategy="neighborhood", mapping={}, accuracy_gain=0)
    mapping: dict[tuple, set[int]] = {}

    for pred, tgt, inp in zip(predictions, targets, inputs):
        if pred.shape != tgt.shape or inp.shape != tgt.shape:
            return None
        h, w = pred.shape
        for r in range(h):
            for c in range(w):
                key = dummy._context_key(pred, inp, r, c)
                val = int(tgt[r, c])
                if key not in mapping:
                    mapping[key] = set()
                mapping[key].add(val)

    resolved = {}
    for key, vals in mapping.items():
        if len(vals) == 1:
            resolved[key] = next(iter(vals))
        else:
            return None

    for pred, tgt, inp in zip(predictions, targets, inputs):
        result = pred.copy()
        h, w = result.shape
        for r in range(h):
            for c in range(w):
                key = dummy._context_key(pred, inp, r, c)
                result[r, c] = resolved[key]
        if not np.array_equal(result, tgt):
            return None

    return NeighborhoodCorrection(
        strategy="neighborhood",
        mapping=resolved,
        accuracy_gain=1.0,
    )


def try_positional_modular(
    predictions: list[np.ndarray],
    targets: list[np.ndarray],
    inputs: list[np.ndarray],
    mod_r: int = 2,
    mod_c: int = 2,
) -> PositionalModularCorrection | None:
    mapping: dict[tuple, set[int]] = {}

    for pred, tgt, inp in zip(predictions, targets, inputs):
        if pred.shape != tgt.shape or inp.shape != tgt.shape:
            return None
        h, w = pred.shape
        for r in range(h):
            for c in range(w):
                key = (r % mod_r, c % mod_c, int(inp[r, c]), int(pred[r, c]))
                val = int(tgt[r, c])
                if key not in mapping:
                    mapping[key] = set()
                mapping[key].add(val)

    resolved = {}
    for key, vals in mapping.items():
        if len(vals) == 1:
            resolved[key] = next(iter(vals))
        else:
            return None

    for pred, tgt, inp in zip(predictions, targets, inputs):
        result = pred.copy()
        h, w = result.shape
        for r in range(h):
            for c in range(w):
                key = (r % mod_r, c % mod_c, int(inp[r, c]), int(pred[r, c]))
                result[r, c] = resolved[key]
        if not np.array_equal(result, tgt):
            return None

    return PositionalModularCorrection(
        strategy="positional_modular",
        mapping=resolved,
        accuracy_gain=1.0,
        mod_r=mod_r,
        mod_c=mod_c,
    )


def find_correction(
    predictions: list[np.ndarray],
    targets: list[np.ndarray],
    inputs: list[np.ndarray],
) -> Correction | None:
    strategies = [
        lambda: try_global_swap(predictions, targets, inputs),
        lambda: try_input_conditional(predictions, targets, inputs),
        lambda: try_neighborhood_correction(predictions, targets, inputs),
        lambda: try_positional_modular(predictions, targets, inputs, 2, 2),
        lambda: try_positional_modular(predictions, targets, inputs, 3, 3),
        lambda: try_positional_modular(predictions, targets, inputs, 2, 3),
        lambda: try_positional_modular(predictions, targets, inputs, 3, 2),
    ]

    for strategy_fn in strategies:
        correction = strategy_fn()
        if correction is not None:
            return correction

    return None
