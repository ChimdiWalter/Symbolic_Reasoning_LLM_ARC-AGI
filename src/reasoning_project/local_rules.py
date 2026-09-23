"""Extended local-rule / cellular-automata synthesis for ARC tasks.

Searches over configurable neighborhoods, color-conditioned rules,
boundary-sensitive rules, and multi-pass update rules.
"""
from __future__ import annotations

import numpy as np
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class LocalRule:
    """A learned local rule mapping neighborhood patterns to output colors."""
    strategy_name: str
    neighborhood_size: int
    mapping: Dict[tuple, int]
    n_conflicts: int = 0
    boundary_mode: str = "constant"


def _neighborhood_keys_3x3(grid: np.ndarray, r: int, c: int, boundary: str = "constant") -> tuple:
    h, w = grid.shape
    key = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                key.append(int(grid[rr, cc]))
            elif boundary == "constant":
                key.append(-1)
            elif boundary == "wrap":
                key.append(int(grid[rr % h, cc % w]))
            else:
                key.append(-1)
    return tuple(key)


def _neighborhood_keys_5x5(grid: np.ndarray, r: int, c: int, boundary: str = "constant") -> tuple:
    h, w = grid.shape
    key = []
    for dr in [-2, -1, 0, 1, 2]:
        for dc in [-2, -1, 0, 1, 2]:
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                key.append(int(grid[rr, cc]))
            elif boundary == "constant":
                key.append(-1)
            elif boundary == "wrap":
                key.append(int(grid[rr % h, cc % w]))
            else:
                key.append(-1)
    return tuple(key)


def _neighborhood_keys_cross(grid: np.ndarray, r: int, c: int, boundary: str = "constant") -> tuple:
    """Cross/plus-shaped neighborhood (center + 4 cardinal)."""
    h, w = grid.shape
    offsets = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
    key = []
    for dr, dc in offsets:
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            key.append(int(grid[rr, cc]))
        elif boundary == "wrap":
            key.append(int(grid[rr % h, cc % w]))
        else:
            key.append(-1)
    return tuple(key)


def _neighborhood_keys_diagonal(grid: np.ndarray, r: int, c: int, boundary: str = "constant") -> tuple:
    """Center + 4 diagonal neighbors."""
    h, w = grid.shape
    offsets = [(0, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    key = []
    for dr, dc in offsets:
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            key.append(int(grid[rr, cc]))
        elif boundary == "wrap":
            key.append(int(grid[rr % h, cc % w]))
        else:
            key.append(-1)
    return tuple(key)


def _color_count_key(grid: np.ndarray, r: int, c: int, radius: int = 1) -> tuple:
    """Key: (center_color, count_of_each_neighbor_color)."""
    h, w = grid.shape
    center = int(grid[r, c])
    counts = {}
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                v = int(grid[rr, cc])
                counts[v] = counts.get(v, 0) + 1
    return (center,) + tuple(sorted(counts.items()))


def _relative_position_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center_color, relative_row_bin, relative_col_bin)."""
    h, w = grid.shape
    center = int(grid[r, c])
    row_bin = r * 3 // h
    col_bin = c * 3 // w
    return (center, row_bin, col_bin)


def _color_and_position_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center_color, row%period, col%period) for periodicity detection."""
    center = int(grid[r, c])
    h, w = grid.shape
    return (center, r % 2, c % 2)


def _color_and_position_key_3(grid: np.ndarray, r: int, c: int) -> tuple:
    center = int(grid[r, c])
    return (center, r % 3, c % 3)


def _color_and_position_key_4(grid: np.ndarray, r: int, c: int) -> tuple:
    center = int(grid[r, c])
    return (center, r % 4, c % 4)


def _majority_neighbor_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center_color, majority_neighbor_color)."""
    h, w = grid.shape
    center = int(grid[r, c])
    counts = {}
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                v = int(grid[rr, cc])
                counts[v] = counts.get(v, 0) + 1
    if counts:
        majority = max(counts, key=counts.get)
    else:
        majority = center
    return (center, majority)


def _boundary_distance_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center_color, min_distance_to_boundary)."""
    h, w = grid.shape
    center = int(grid[r, c])
    dist = min(r, c, h - 1 - r, w - 1 - c)
    return (center, min(dist, 3))


def _neighbor_diversity_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center_color, n_distinct_neighbor_colors)."""
    h, w = grid.shape
    center = int(grid[r, c])
    neighbors = set()
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                neighbors.add(int(grid[rr, cc]))
    return (center, len(neighbors))


def _cardinal_pattern_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, N==center, S==center, E==center, W==center)."""
    h, w = grid.shape
    center = int(grid[r, c])
    def get(dr, dc):
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            return int(grid[rr, cc]) == center
        return False
    return (center, get(-1, 0), get(1, 0), get(0, 1), get(0, -1))


def _row_projection_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: entire row content (for row-uniform transforms)."""
    return (int(grid[r, c]),) + tuple(int(v) for v in grid[r, :])


def _col_projection_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: entire column content (for column-uniform transforms)."""
    return (int(grid[r, c]),) + tuple(int(v) for v in grid[:, c])


def _row_color_signature_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, sorted unique colors in row)."""
    center = int(grid[r, c])
    row_colors = tuple(sorted(set(int(v) for v in grid[r, :])))
    return (center, row_colors)


def _col_color_signature_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, sorted unique colors in column)."""
    center = int(grid[r, c])
    col_colors = tuple(sorted(set(int(v) for v in grid[:, c])))
    return (center, col_colors)


def _conditional_neighbor_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, has_nonzero_neighbor, n_nonzero_neighbors)."""
    h, w = grid.shape
    center = int(grid[r, c])
    n_nonzero = 0
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and grid[rr, cc] != 0:
                n_nonzero += 1
    return (center, n_nonzero > 0, n_nonzero)


def _color_position_boundary_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, is_edge, n_same_color_neighbors)."""
    h, w = grid.shape
    center = int(grid[r, c])
    is_edge = r == 0 or c == 0 or r == h - 1 or c == w - 1
    n_same = 0
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and int(grid[rr, cc]) == center:
                n_same += 1
    return (center, is_edge, n_same)


def _symmetry_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, mirror_h_value, mirror_v_value) for symmetry tasks."""
    h, w = grid.shape
    center = int(grid[r, c])
    mirror_r = h - 1 - r
    mirror_c = w - 1 - c
    mirror_h = int(grid[mirror_r, c]) if 0 <= mirror_r < h else -1
    mirror_v = int(grid[r, mirror_c]) if 0 <= mirror_c < w else -1
    return (center, mirror_h, mirror_v)


def _simple_color_map_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: just the center color. Captures pure recoloring tasks."""
    return (int(grid[r, c]),)


def _absolute_position_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (row, col). Captures position-determined output for small grids."""
    return (r, c)


def _color_and_absolute_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, row, col). Full position + color context."""
    return (int(grid[r, c]), r, c)


def _checkerboard_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, parity). Captures alternating/checkerboard patterns."""
    return (int(grid[r, c]), (r + c) % 2)


def _row_index_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, row). Row-dependent transforms."""
    return (int(grid[r, c]), r)


def _col_index_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, col). Column-dependent transforms."""
    return (int(grid[r, c]), c)


def _binary_3x3_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, binary pattern of same/diff in 3x3). Color-invariant structure."""
    h, w = grid.shape
    center = int(grid[r, c])
    pattern = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                pattern.append(1 if int(grid[rr, cc]) == center else 0)
            else:
                pattern.append(-1)
    return (center,) + tuple(pattern)


def _edge_detection_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, has_different_N, S, E, W). Detects edges/borders between regions."""
    h, w = grid.shape
    center = int(grid[r, c])
    def diff(dr, dc):
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            return int(grid[rr, cc]) != center
        return True
    return (center, diff(-1, 0), diff(1, 0), diff(0, -1), diff(0, 1))


def _global_color_rank_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, frequency_rank). Rank of color by frequency in the grid."""
    center = int(grid[r, c])
    unique, counts = np.unique(grid, return_counts=True)
    freq_order = unique[np.argsort(-counts)]
    rank = int(np.where(freq_order == center)[0][0])
    return (center, rank)


def _neighbor_color_set_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, frozenset of neighbor colors). Order-invariant neighborhood."""
    h, w = grid.shape
    center = int(grid[r, c])
    neighbors = set()
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                neighbors.add(int(grid[rr, cc]))
    return (center, tuple(sorted(neighbors)))


def _diagonal_position_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, on_main_diag, on_anti_diag, dist_to_main)."""
    h, w = grid.shape
    center = int(grid[r, c])
    on_main = abs(r - c) <= 0
    on_anti = abs(r - (w - 1 - c)) <= 0
    return (center, on_main, on_anti, min(abs(r - c), 3))


def _flood_region_size_key(grid: np.ndarray, r: int, c: int) -> tuple:
    """Key: (center, binned_region_size). Size of connected same-color region."""
    h, w = grid.shape
    center = int(grid[r, c])
    visited = set()
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if (cr, cc) in visited:
            continue
        if 0 <= cr < h and 0 <= cc < w and int(grid[cr, cc]) == center:
            visited.add((cr, cc))
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                stack.append((cr + dr, cc + dc))
    size = len(visited)
    if size <= 1:
        bin_size = 1
    elif size <= 4:
        bin_size = 2
    elif size <= 9:
        bin_size = 3
    elif size <= 16:
        bin_size = 4
    else:
        bin_size = 5
    return (center, bin_size)


def _cross_5(grid: np.ndarray, r: int, c: int, boundary: str = "constant") -> tuple:
    """Extended cross: center + 4 cardinal at distance 1 and 2."""
    h, w = grid.shape
    offsets = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1),
               (-2, 0), (2, 0), (0, -2), (0, 2)]
    key = []
    for dr, dc in offsets:
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            key.append(int(grid[rr, cc]))
        elif boundary == "wrap":
            key.append(int(grid[rr % h, cc % w]))
        else:
            key.append(-1)
    return tuple(key)


STRATEGY_REGISTRY: Dict[str, callable] = {
    "full_3x3": lambda g, r, c: _neighborhood_keys_3x3(g, r, c, "constant"),
    "full_3x3_wrap": lambda g, r, c: _neighborhood_keys_3x3(g, r, c, "wrap"),
    "full_5x5": lambda g, r, c: _neighborhood_keys_5x5(g, r, c, "constant"),
    "full_5x5_wrap": lambda g, r, c: _neighborhood_keys_5x5(g, r, c, "wrap"),
    "cross": lambda g, r, c: _neighborhood_keys_cross(g, r, c, "constant"),
    "cross_5": lambda g, r, c: _cross_5(g, r, c, "constant"),
    "diagonal": lambda g, r, c: _neighborhood_keys_diagonal(g, r, c, "constant"),
    "color_count_r1": lambda g, r, c: _color_count_key(g, r, c, 1),
    "color_count_r2": lambda g, r, c: _color_count_key(g, r, c, 2),
    "relative_position": _relative_position_key,
    "periodic_2": _color_and_position_key,
    "periodic_3": _color_and_position_key_3,
    "periodic_4": _color_and_position_key_4,
    "majority_neighbor": _majority_neighbor_key,
    "boundary_distance": _boundary_distance_key,
    "neighbor_diversity": _neighbor_diversity_key,
    "cardinal_pattern": _cardinal_pattern_key,
    "row_projection": _row_projection_key,
    "col_projection": _col_projection_key,
    "row_color_sig": _row_color_signature_key,
    "col_color_sig": _col_color_signature_key,
    "conditional_neighbor": _conditional_neighbor_key,
    "color_position_boundary": _color_position_boundary_key,
    "symmetry": _symmetry_key,
    "simple_color_map": _simple_color_map_key,
    "absolute_position": _absolute_position_key,
    "color_and_absolute": _color_and_absolute_key,
    "checkerboard": _checkerboard_key,
    "row_index": _row_index_key,
    "col_index": _col_index_key,
    "binary_3x3": _binary_3x3_key,
    "edge_detection": _edge_detection_key,
    "global_color_rank": _global_color_rank_key,
    "neighbor_color_set": _neighbor_color_set_key,
    "diagonal_position": _diagonal_position_key,
    "flood_region_size": _flood_region_size_key,
}


def induce_local_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    strategy_name: str,
) -> Optional[LocalRule]:
    """Learn a local rule from input-output pairs.

    Returns None if the strategy produces conflicting mappings.
    """
    if strategy_name not in STRATEGY_REGISTRY:
        return None

    key_fn = STRATEGY_REGISTRY[strategy_name]
    mapping: Dict[tuple, int] = {}
    conflicts = 0

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                key = key_fn(inp, r, c)
                target = int(out[r, c])
                if key in mapping:
                    if mapping[key] != target:
                        conflicts += 1
                        return None
                else:
                    mapping[key] = target

    if not mapping:
        return None

    return LocalRule(
        strategy_name=strategy_name,
        neighborhood_size=len(next(iter(mapping))),
        mapping=mapping,
        n_conflicts=conflicts,
    )


def apply_local_rule(grid: np.ndarray, rule: LocalRule) -> Optional[np.ndarray]:
    """Apply a learned local rule to a grid. Returns None if any key is unmapped."""
    key_fn = STRATEGY_REGISTRY[rule.strategy_name]
    h, w = grid.shape
    out = np.zeros((h, w), dtype=int)
    for r in range(h):
        for c in range(w):
            key = key_fn(grid, r, c)
            if key in rule.mapping:
                out[r, c] = rule.mapping[key]
            else:
                return None
    return out


def apply_local_rule_with_fallback(grid: np.ndarray, rule: LocalRule) -> np.ndarray:
    """Apply rule with identity fallback for unmapped keys."""
    key_fn = STRATEGY_REGISTRY[rule.strategy_name]
    h, w = grid.shape
    out = np.zeros((h, w), dtype=int)
    for r in range(h):
        for c in range(w):
            key = key_fn(grid, r, c)
            if key in rule.mapping:
                out[r, c] = rule.mapping[key]
            else:
                out[r, c] = int(grid[r, c])
    return out


def _fuzzy_lookup(key: tuple, mapping: Dict[tuple, int], max_dist: int = 2) -> Optional[int]:
    """Find the nearest key in mapping by Hamming distance, with majority vote on ties."""
    best_dist = max_dist + 1
    vote: Dict[int, int] = {}

    for known_key, value in mapping.items():
        if len(known_key) != len(key):
            continue
        dist = 0
        for a, b in zip(key, known_key):
            if a != b:
                dist += 1
                if dist >= best_dist:
                    break
        if dist < best_dist:
            best_dist = dist
            vote = {value: 1}
        elif dist == best_dist:
            vote[value] = vote.get(value, 0) + 1

    if best_dist > max_dist or not vote:
        return None
    return max(vote, key=vote.get)


def apply_local_rule_fuzzy(grid: np.ndarray, rule: LocalRule) -> Optional[np.ndarray]:
    """Apply rule with fuzzy nearest-key fallback for unmapped keys.

    When exact key lookup fails, finds the closest known key by Hamming
    distance (max 2) and uses majority vote among equidistant keys.
    Returns None only if a pixel has no close match at all.
    """
    key_fn = STRATEGY_REGISTRY[rule.strategy_name]
    h, w = grid.shape
    klen = len(next(iter(rule.mapping))) if rule.mapping else 0
    max_dist = min(2, max(1, klen // 4))
    out = np.zeros((h, w), dtype=int)
    for r in range(h):
        for c in range(w):
            key = key_fn(grid, r, c)
            if key in rule.mapping:
                out[r, c] = rule.mapping[key]
            else:
                val = _fuzzy_lookup(key, rule.mapping, max_dist)
                if val is None:
                    return None
                out[r, c] = val
    return out


def synthesize_local_rules(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    strategies: Optional[List[str]] = None,
    require_exact_train: bool = True,
) -> List[LocalRule]:
    """Try all strategies and return valid rules sorted by generality (fewest mappings)."""
    if strategies is None:
        strategies = list(STRATEGY_REGISTRY.keys())

    valid_rules = []
    for strategy_name in strategies:
        rule = induce_local_rule(train_pairs, strategy_name)
        if rule is None:
            continue
        if require_exact_train:
            train_ok = True
            for inp, out in train_pairs:
                pred = apply_local_rule(inp, rule)
                if pred is None or not np.array_equal(pred, out):
                    train_ok = False
                    break
            if not train_ok:
                continue
        valid_rules.append(rule)

    valid_rules.sort(key=lambda r: len(r.mapping))
    return valid_rules


def _loo_validate_fuzzy(train_pairs, strategy_name):
    """LOO validation: for each pair, learn rule from N-1, predict held-out with fuzzy."""
    n = len(train_pairs)
    if n < 2:
        return False
    for i in range(n):
        fit_pairs = train_pairs[:i] + train_pairs[i + 1:]
        held_inp, held_out = train_pairs[i]
        rule = induce_local_rule(fit_pairs, strategy_name)
        if rule is None:
            return False
        pred = apply_local_rule(held_inp, rule)
        if pred is not None and np.array_equal(pred, held_out):
            continue
        pred = apply_local_rule_fuzzy(held_inp, rule)
        if pred is None or not np.array_equal(pred, held_out):
            return False
    return True


def solve_task_local_rules(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    strategies: Optional[List[str]] = None,
    try_multi_pass: bool = True,
) -> Optional[Tuple[List[np.ndarray], LocalRule]]:
    """Attempt to solve a task using local rules.

    Returns (predictions, rule) if successful, None otherwise.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    rules = synthesize_local_rules(train_pairs, strategies)
    if rules:
        best_rule = rules[0]

        # Try strict application first
        strict_ok = True
        predictions = []
        for test_inp in test_inputs:
            pred = apply_local_rule(test_inp, best_rule)
            if pred is None:
                strict_ok = False
                break
            predictions.append(pred)
        if strict_ok:
            return predictions, best_rule

        # Strict failed on test — try fuzzy with LOO validation
        for rule in rules:
            if _loo_validate_fuzzy(train_pairs, rule.strategy_name):
                preds_fuzzy = []
                fuzzy_ok = True
                for test_inp in test_inputs:
                    pred = apply_local_rule(test_inp, rule)
                    if pred is None:
                        pred = apply_local_rule_fuzzy(test_inp, rule)
                    if pred is None:
                        fuzzy_ok = False
                        break
                    preds_fuzzy.append(pred)
                if fuzzy_ok:
                    return preds_fuzzy, rule

        # Fall back to identity fallback (original behavior)
        predictions = []
        for test_inp in test_inputs:
            pred = apply_local_rule(test_inp, best_rule)
            if pred is None:
                pred = apply_local_rule_with_fallback(test_inp, best_rule)
            predictions.append(pred)
        return predictions, best_rule

    if try_multi_pass:
        mp_result = multi_pass_local_rule(train_pairs, max_passes=3, strategies=strategies)
        if mp_result is not None:
            n_passes, rule = mp_result
            predictions = []
            for test_inp in test_inputs:
                current = test_inp.copy()
                for _ in range(n_passes):
                    result = apply_local_rule(current, rule)
                    if result is None:
                        result = apply_local_rule_fuzzy(current, rule)
                    if result is None:
                        result = apply_local_rule_with_fallback(current, rule)
                    if np.array_equal(result, current):
                        break
                    current = result
                predictions.append(current)
            return predictions, rule

    return None


def multi_pass_local_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    max_passes: int = 3,
    strategies: Optional[List[str]] = None,
) -> Optional[Tuple[List[callable], List[LocalRule]]]:
    """Try multi-pass local rules: apply rule repeatedly until convergence.

    Some ARC tasks require iterated local updates (like cellular automata).
    """
    if strategies is None:
        strategies = list(STRATEGY_REGISTRY.keys())

    for n_passes in range(2, max_passes + 1):
        for strategy_name in strategies:
            rule = induce_local_rule(train_pairs, strategy_name)
            if rule is None:
                continue

            all_ok = True
            for inp, out in train_pairs:
                current = inp.copy()
                for _ in range(n_passes):
                    result = apply_local_rule(current, rule)
                    if result is None:
                        result = apply_local_rule_with_fallback(current, rule)
                    if np.array_equal(result, current):
                        break
                    current = result
                if not np.array_equal(current, out):
                    all_ok = False
                    break

            if all_ok:
                return n_passes, rule

    return None
