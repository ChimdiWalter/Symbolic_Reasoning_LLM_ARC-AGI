"""Verify invented operators before promotion."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from .invented_operator import InventedOperator


@dataclass
class VerificationResult:
    passed: bool
    exact_matches: int
    total: int
    regression_failures: list[str] = field(default_factory=list)
    details: str = ""


def verify_operator(
    operator: InventedOperator,
    test_cases: list[dict],
    regression_tasks: list[dict] | None = None,
) -> VerificationResult:
    if operator.apply_fn is None:
        return VerificationResult(
            passed=False, exact_matches=0, total=len(test_cases),
            details="No apply function defined",
        )

    exact = 0
    total = len(test_cases)

    for tc in test_cases:
        try:
            result = operator.apply(tc.get("input"))
            if result == tc.get("expected_output"):
                exact += 1
        except Exception as e:
            pass

    regression_fails = []
    if regression_tasks:
        for rt in regression_tasks:
            try:
                result = operator.apply(rt.get("input"))
                if result != rt.get("expected_output"):
                    regression_fails.append(rt.get("task_id", "unknown"))
            except Exception:
                regression_fails.append(rt.get("task_id", "unknown"))

    passed = exact == total and len(regression_fails) == 0

    return VerificationResult(
        passed=passed,
        exact_matches=exact,
        total=total,
        regression_failures=regression_fails,
    )


def generate_certificate(operator: InventedOperator, result: VerificationResult) -> dict:
    return {
        "operator_name": operator.name,
        "verified": result.passed,
        "exact_matches": result.exact_matches,
        "total_tests": result.total,
        "regression_failures": result.regression_failures,
        "timestamp": time.time(),
        "input_types": operator.input_types,
        "output_type": operator.output_type,
        "preconditions": operator.preconditions,
        "postconditions": operator.postconditions,
    }
