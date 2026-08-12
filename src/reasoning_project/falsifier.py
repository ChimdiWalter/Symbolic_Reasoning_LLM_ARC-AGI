"""Candidate falsification checks for passive and interactive settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from .compression import exact_match, grid_error, perturb_grid
from .generators import HiddenRuleWorld
from .operators import apply_program
from .schemas import Program, TaskExample, program_signature


@dataclass
class FalsifierReport:
    program_signature: str
    accepted: bool
    contradictions: int
    passive_checks: int
    oracle_counterexamples: int
    oracle_checks: int
    perturbation_survival_rate: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_signature": self.program_signature,
            "accepted": self.accepted,
            "contradictions": self.contradictions,
            "passive_checks": self.passive_checks,
            "oracle_counterexamples": self.oracle_counterexamples,
            "oracle_checks": self.oracle_checks,
            "counterexample_survival_rate": self.counterexample_survival_rate,
            "perturbation_survival_rate": self.perturbation_survival_rate,
            "details": self.details,
        }

    @property
    def counterexample_survival_rate(self) -> float:
        if self.oracle_checks == 0:
            return 1.0
        return 1.0 - self.oracle_counterexamples / self.oracle_checks


class Falsifier:
    """Attack candidate programs with examples, perturbations, and optional oracle probes."""

    def __init__(self, tolerance: float = 0.0, perturbations: int = 2, oracle_probes: int = 0):
        self.tolerance = float(tolerance)
        self.perturbations = int(perturbations)
        self.oracle_probes = int(oracle_probes)

    def attack(
        self,
        program: Program,
        examples: Iterable[TaskExample],
        world: Optional[HiddenRuleWorld] = None,
        seed: int = 0,
    ) -> FalsifierReport:
        examples = list(examples)
        contradictions = 0
        passive_errors: List[float] = []
        for example in examples:
            pred = apply_program(example.input_grid, program)
            err = grid_error(pred, example.output_grid)
            passive_errors.append(err)
            if err > self.tolerance:
                contradictions += 1

        perturbation_survival: List[bool] = []
        for idx, example in enumerate(examples[: self.perturbations]):
            perturbed = perturb_grid(example.input_grid, seed + idx)
            base = apply_program(example.input_grid, program)
            attacked = apply_program(perturbed, program)
            survives = base.shape == attacked.shape and np.count_nonzero(attacked) > 0
            perturbation_survival.append(bool(survives))

        oracle_counterexamples = 0
        oracle_checks = 0
        if world is not None and self.oracle_probes > 0:
            for idx, example in enumerate(examples[: self.oracle_probes]):
                perturbed = perturb_grid(example.input_grid, seed + 1000 + idx)
                pred = apply_program(perturbed, program)
                truth = world.probe(perturbed)
                oracle_checks += 1
                if not exact_match(pred, truth):
                    oracle_counterexamples += 1
            while oracle_checks < self.oracle_probes:
                probe = world.sample_probe(split="ood")
                pred = apply_program(probe.input_grid, program)
                truth = world.probe(probe.input_grid)
                oracle_checks += 1
                if not exact_match(pred, truth):
                    oracle_counterexamples += 1

        accepted = contradictions == 0 and oracle_counterexamples == 0
        return FalsifierReport(
            program_signature=program_signature(program),
            accepted=accepted,
            contradictions=contradictions,
            passive_checks=len(examples),
            oracle_counterexamples=oracle_counterexamples,
            oracle_checks=oracle_checks,
            perturbation_survival_rate=float(np.mean(perturbation_survival)) if perturbation_survival else 1.0,
            details={
                "passive_error_mean": float(np.mean(passive_errors)) if passive_errors else 1.0,
                "tolerance": self.tolerance,
            },
        )
