"""Real objective function — evaluates programs on actual ARC grids."""
from __future__ import annotations
import numpy as np
from geocat_arc.perception.grid import Grid


def normalized_cell_accuracy(predicted: list[list[int]], target: list[list[int]]) -> float:
    pred = np.array(predicted, dtype=np.int32)
    tgt = np.array(target, dtype=np.int32)
    if pred.shape != tgt.shape:
        ph, pw = pred.shape
        th, tw = tgt.shape
        min_h, min_w = min(ph, th), min(pw, tw)
        matching = np.sum(pred[:min_h, :min_w] == tgt[:min_h, :min_w])
        total = th * tw
        shape_penalty = 1.0 - (min_h * min_w) / total if total > 0 else 1.0
        return (matching / total) * (1.0 - 0.5 * shape_penalty) if total > 0 else 0.0
    total = tgt.size
    return float(np.sum(pred == tgt)) / total if total > 0 else 0.0


def exact_match(predicted: list[list[int]], target: list[list[int]]) -> bool:
    return predicted == target


def evaluate_program(program, task, complexity_weight: float = 0.01) -> float:
    scores = []
    for pair in task.train:
        try:
            input_grid = Grid.from_list(pair.input)
            result = program.apply(input_grid)
            if isinstance(result, Grid):
                predicted = result.to_list()
            elif isinstance(result, list):
                if result and isinstance(result[0], list):
                    predicted = result
                else:
                    predicted = [[0]]
            else:
                predicted = [[0]]

            cell_acc = normalized_cell_accuracy(predicted, pair.output)
            is_exact = exact_match(predicted, pair.output)
            score = cell_acc + (1.0 if is_exact else 0.0)
            scores.append(score)
        except Exception:
            scores.append(0.0)

    if not scores:
        return 0.0

    avg_score = sum(scores) / len(scores)
    complexity_penalty = complexity_weight * getattr(program, 'total_cost', len(getattr(program, 'steps', [])))
    return max(0.0, avg_score - complexity_penalty)
