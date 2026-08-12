"""Rule inducer — learns transformation rules from training pairs.

For same-shape tasks:
  For each context extractor, try to learn a consistent mapping
  context_key -> output_color from all training cells.
  "Consistent" means no key maps to two different output colors.

For different-shape tasks:
  Try grid-level transforms (crop, tile, subgrid ops) first,
  then apply same-shape reasoning to the result.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import numpy as np
from collections import Counter

from .context_extractors import ALL_EXTRACTORS


@dataclass
class InducedRule:
    extractor_name: str
    mapping: dict[tuple, int]
    coverage: float
    is_identity: bool
    num_keys: int

    def apply(self, input_grid: np.ndarray) -> np.ndarray:
        h, w = input_grid.shape
        extractor = _get_extractor(self.extractor_name)
        output = np.zeros_like(input_grid)
        for r in range(h):
            for c in range(w):
                key = extractor(input_grid, r, c)
                if key in self.mapping:
                    output[r, c] = self.mapping[key]
                else:
                    best = self._fuzzy_lookup(key)
                    output[r, c] = best if best is not None else int(input_grid[r, c])
        return output

    def _fuzzy_lookup(self, key: tuple) -> int | None:
        if not self.mapping:
            return None
        best_key = None
        best_dist = float("inf")
        for known_key in self.mapping:
            if len(known_key) != len(key):
                continue
            dist = sum(1 for a, b in zip(key, known_key) if a != b)
            if dist < best_dist:
                best_dist = dist
                best_key = known_key
        max_dist = max(1, len(key) // 3)
        if best_key is not None and best_dist <= max_dist:
            return self.mapping[best_key]
        return None


@dataclass
class ComposedRule:
    base: InducedRule
    correction: InducedRule | None

    def apply(self, input_grid: np.ndarray) -> np.ndarray:
        intermediate = self.base.apply(input_grid)
        if self.correction:
            return self.correction.apply(intermediate)
        return intermediate


def _get_extractor(name: str) -> Callable:
    for n, fn in ALL_EXTRACTORS:
        if n == name:
            return fn
    raise ValueError(f"Unknown extractor: {name}")


def induce_rule(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
    extractor_name: str,
    extractor_fn: Callable,
) -> InducedRule | None:
    """Try to learn a consistent context -> output_color mapping."""
    mapping: dict[tuple, int] = {}
    conflicts = 0
    total = 0

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                key = extractor_fn(inp, r, c)
                val = int(out[r, c])
                total += 1
                if key in mapping:
                    if mapping[key] != val:
                        conflicts += 1
                        if conflicts > 0:
                            return None
                else:
                    mapping[key] = val

    if total == 0:
        return None

    is_identity = True
    for inp, out in train_pairs:
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                if int(inp[r, c]) != int(out[r, c]):
                    is_identity = False
                    break
            if not is_identity:
                break

    if is_identity:
        return None

    return InducedRule(
        extractor_name=extractor_name,
        mapping=mapping,
        coverage=1.0,
        is_identity=False,
        num_keys=len(mapping),
    )


POSITION_DEPENDENT = {
    "cell_color_and_position",
    "cell_color_and_relative_position",
    "neighborhood_3x3_with_pos",
    "row_pattern_hash",
    "col_pattern_hash",
    "cell_modular_4x4",
}


def _generalization_score(rule: InducedRule, train_pairs: list[tuple[np.ndarray, np.ndarray]]) -> float:
    """Score how likely a rule is to generalize, not just memorize."""
    total_cells = sum(inp.size for inp, _ in train_pairs)
    key_ratio = rule.num_keys / max(total_cells, 1)

    if rule.extractor_name in POSITION_DEPENDENT:
        return -1.0

    if key_ratio > 0.8:
        return 0.0
    if key_ratio > 0.5:
        return 0.3

    return 1.0 - key_ratio


def induce_best_rule(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
    extractors: list[tuple[str, Callable]] | None = None,
    allow_position_dependent: bool = False,
) -> InducedRule | None:
    """Try all extractors, return the best generalizing non-identity rule.
    Ranks by generalization score (fewest keys, not position-dependent)."""
    if extractors is None:
        extractors = ALL_EXTRACTORS

    valid_rules = []
    for name, fn in extractors:
        if not allow_position_dependent and name in POSITION_DEPENDENT:
            continue
        rule = induce_rule(train_pairs, name, fn)
        if rule is not None:
            gen_score = _generalization_score(rule, train_pairs)
            if gen_score > 0:
                valid_rules.append((rule, gen_score))

    if not valid_rules:
        if not allow_position_dependent:
            return induce_best_rule(train_pairs, extractors, allow_position_dependent=True)
        return None

    valid_rules.sort(key=lambda x: (-x[1], x[0].num_keys))
    return valid_rules[0][0]


def induce_partial_rule(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
    extractor_name: str,
    extractor_fn: Callable,
) -> tuple[InducedRule | None, float]:
    """Learn a rule that may have conflicts — return accuracy."""
    mapping: dict[tuple, list[int]] = {}
    total = 0

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None, 0.0
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                key = extractor_fn(inp, r, c)
                val = int(out[r, c])
                total += 1
                if key not in mapping:
                    mapping[key] = []
                mapping[key].append(val)

    if total == 0:
        return None, 0.0

    resolved: dict[tuple, int] = {}
    correct = 0
    for key, vals in mapping.items():
        majority = Counter(vals).most_common(1)[0]
        resolved[key] = majority[0]
        correct += majority[1]

    accuracy = correct / total

    is_identity = True
    for inp, out in train_pairs:
        if not np.array_equal(inp, out):
            is_identity = False
            break

    if is_identity:
        return None, 0.0

    rule = InducedRule(
        extractor_name=extractor_name,
        mapping=resolved,
        coverage=accuracy,
        is_identity=False,
        num_keys=len(resolved),
    )
    return rule, accuracy


def induce_best_partial(
    train_pairs: list[tuple[np.ndarray, np.ndarray]],
    min_accuracy: float = 0.5,
) -> tuple[InducedRule | None, float]:
    """Find the best partial rule across all extractors."""
    best_rule = None
    best_acc = min_accuracy

    for name, fn in ALL_EXTRACTORS:
        rule, acc = induce_partial_rule(train_pairs, name, fn)
        if rule and acc > best_acc:
            best_rule = rule
            best_acc = acc

    return best_rule, best_acc
