"""Compression and intervention-aware scoring proxies."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np

from .generators import HiddenRuleWorld
from .operators import apply_program, program_description_length
from .schemas import Program, TaskExample


def grid_error(pred: np.ndarray, target: np.ndarray) -> float:
    if pred.shape != target.shape:
        return 1.0
    return float(np.mean(pred != target))


def exact_match(pred: np.ndarray, target: np.ndarray) -> bool:
    return pred.shape == target.shape and bool(np.array_equal(pred, target))


def training_error(program: Program, examples: Iterable[TaskExample]) -> float:
    errors = [grid_error(apply_program(example.input_grid, program), example.output_grid) for example in examples]
    if not errors:
        return 1.0
    return float(np.mean(errors))


def sparsity_penalty(program: Program, examples: Iterable[TaskExample]) -> float:
    penalties: List[float] = []
    for example in examples:
        pred = apply_program(example.input_grid, program)
        if pred.shape != example.input_grid.shape:
            penalties.append(1.0)
        else:
            penalties.append(float(np.mean(pred != example.input_grid)))
    return float(np.mean(penalties)) if penalties else 0.0


def perturb_grid(grid: np.ndarray, seed: int = 0) -> np.ndarray:
    """Add a small nuisance component in a free corner if possible."""

    rng = np.random.default_rng(seed)
    out = np.asarray(grid, dtype=int).copy()
    h, w = out.shape
    candidates = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]
    rng.shuffle(candidates)
    for r, c in candidates:
        if out[r, c] == 0:
            out[r, c] = int(rng.integers(1, 9))
            return out
    return out


def nuisance_robustness(program: Program, examples: Iterable[TaskExample], seed: int = 0) -> float:
    """Estimate stability of program behavior under a small nuisance edit.

    This is not causal proof. It is a practical proxy used by the selector.
    """

    scores: List[float] = []
    for idx, example in enumerate(examples):
        base = apply_program(example.input_grid, program)
        perturbed_input = perturb_grid(example.input_grid, seed + idx)
        perturbed_output = apply_program(perturbed_input, program)
        if base.shape != perturbed_output.shape:
            scores.append(0.0)
        else:
            scores.append(1.0 - float(np.mean(base != perturbed_output)))
    return float(np.mean(scores)) if scores else 0.0


def intervention_stability(
    program: Program,
    world: Optional[HiddenRuleWorld],
    n_probes: int = 0,
) -> float:
    if world is None or n_probes <= 0:
        return 0.0
    matches = []
    for _ in range(n_probes):
        probe = world.sample_probe(split="ood")
        pred = apply_program(probe.input_grid, program)
        truth = world.probe(probe.input_grid)
        matches.append(exact_match(pred, truth))
    return float(np.mean(matches)) if matches else 0.0


def compression_score(
    program: Program,
    train_examples: Iterable[TaskExample],
    world: Optional[HiddenRuleWorld] = None,
    n_intervention_probes: int = 0,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    examples = list(train_examples)
    weights = weights or {
        "fit": 10.0,
        "description": 0.3,
        "sparsity": 0.2,
        "nuisance": 0.5,
        "intervention": 1.0,
    }
    fit = training_error(program, examples)
    description = program_description_length(program)
    sparsity = sparsity_penalty(program, examples)
    nuisance = nuisance_robustness(program, examples)
    intervention = intervention_stability(program, world, n_intervention_probes)
    score = (
        weights["fit"] * fit
        + weights["description"] * description
        + weights["sparsity"] * sparsity
        - weights["nuisance"] * nuisance
        - weights["intervention"] * intervention
    )
    return {
        "score": float(score),
        "fit_error": float(fit),
        "description_length_proxy": float(description),
        "sparsity_penalty": float(sparsity),
        "nuisance_robustness": float(nuisance),
        "intervention_stability": float(intervention),
    }

