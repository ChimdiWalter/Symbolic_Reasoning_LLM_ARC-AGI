"""Operational path corruption and repair experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from .compression import training_error
from .operators import candidate_programs
from .schemas import Program, ProgramStep, TaskExample, program_signature


@dataclass
class RepairReport:
    original_signature: str
    corrupted_signature: str
    repaired_signature: str
    recovered_original: bool
    corrupted_error: float
    repaired_error: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_signature": self.original_signature,
            "corrupted_signature": self.corrupted_signature,
            "repaired_signature": self.repaired_signature,
            "recovered_original": self.recovered_original,
            "corrupted_error": float(self.corrupted_error),
            "repaired_error": float(self.repaired_error),
            "details": self.details,
        }


def corrupt_program(program: Program, seed: int = 0) -> Program:
    rng = np.random.default_rng(seed)
    if not program:
        return [ProgramStep("identity")]
    corrupted = [ProgramStep(step.name, dict(step.params)) for step in program]
    action = str(rng.choice(["drop", "replace_param", "replace_step"]))
    if action == "drop" and len(corrupted) > 1:
        del corrupted[int(rng.integers(0, len(corrupted)))]
    elif action == "replace_param" and corrupted[0].params:
        key = sorted(corrupted[0].params)[0]
        value = corrupted[0].params[key]
        if isinstance(value, int):
            corrupted[0].params[key] = int(value) + 1
        else:
            corrupted[0].params[key] = "largest"
    else:
        replacements = ["identity", "reflect_horizontal", "reflect_vertical", "rotate_90"]
        corrupted[0] = ProgramStep(str(rng.choice(replacements)))
    return corrupted


def _signature_distance(a: Program, b: Program) -> int:
    a_tokens = [step.short() for step in a]
    b_tokens = [step.short() for step in b]
    distance = abs(len(a_tokens) - len(b_tokens))
    for left, right in zip(a_tokens, b_tokens):
        distance += 0 if left == right else 1
    return distance


def repair_program(
    corrupted: Program,
    examples: Iterable[TaskExample],
    colors: List[int],
    max_depth: int = 2,
    dsl_profile: str = "core",
) -> Program:
    examples = list(examples)
    candidates = candidate_programs(max_depth=max_depth, colors=colors, profile=dsl_profile)
    scored = []
    for candidate in candidates:
        fit = training_error(candidate, examples)
        distance = _signature_distance(corrupted, candidate)
        scored.append((fit, distance, len(candidate), candidate))
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    return scored[0][3]


def evaluate_repair(
    original: Program,
    examples: Iterable[TaskExample],
    colors: Optional[List[int]] = None,
    seed: int = 0,
    max_depth: int = 2,
    dsl_profile: str = "core",
) -> RepairReport:
    examples = list(examples)
    colors = colors or [1, 2, 3, 4, 5, 6, 7, 8]
    corrupted = corrupt_program(original, seed=seed)
    repaired = repair_program(
        corrupted,
        examples,
        colors=colors,
        max_depth=max_depth,
        dsl_profile=dsl_profile,
    )
    original_sig = program_signature(original)
    return RepairReport(
        original_signature=original_sig,
        corrupted_signature=program_signature(corrupted),
        repaired_signature=program_signature(repaired),
        recovered_original=program_signature(repaired) == original_sig,
        corrupted_error=training_error(corrupted, examples),
        repaired_error=training_error(repaired, examples),
        details={"max_depth": max_depth, "dsl_profile": str(dsl_profile)},
    )
