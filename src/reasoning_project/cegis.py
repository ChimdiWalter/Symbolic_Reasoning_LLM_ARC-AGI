"""Counterexample-Guided Inductive Synthesis (CEGIS) for ARC tasks.

CEGIS loop:
1. Propose candidate program from DSL or local rules
2. Test on training examples
3. Identify failed example and minimal failed region
4. Extract counterexample explanation
5. Specialize or repair candidate
6. Repeat until consistent or budget exhausted
"""
from __future__ import annotations

import time
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field


@dataclass
class Counterexample:
    """A training example where the candidate fails."""
    example_index: int
    input_grid: np.ndarray
    expected_output: np.ndarray
    predicted_output: Optional[np.ndarray]
    failed_pixels: List[Tuple[int, int]]
    failure_fraction: float


@dataclass
class CEGISCandidate:
    """A candidate hypothesis in the CEGIS loop."""
    hypothesis_type: str
    hypothesis_data: Any
    train_errors: List[float]
    counterexamples: List[Counterexample]
    refinement_step: int


@dataclass
class CEGISResult:
    """Result of a CEGIS synthesis attempt."""
    solved: bool
    predictions: Optional[List[np.ndarray]]
    best_candidate: Optional[CEGISCandidate]
    total_candidates_tried: int
    total_counterexamples: int
    refinement_steps: int
    elapsed_seconds: float
    trace: List[Dict[str, Any]]


def _find_failed_pixels(predicted: np.ndarray, expected: np.ndarray) -> List[Tuple[int, int]]:
    if predicted.shape != expected.shape:
        return [(r, c) for r in range(expected.shape[0]) for c in range(expected.shape[1])]
    failed = []
    for r in range(expected.shape[0]):
        for c in range(expected.shape[1]):
            if predicted[r, c] != expected[r, c]:
                failed.append((r, c))
    return failed


def _extract_counterexample(
    inp: np.ndarray, expected: np.ndarray, predicted: Optional[np.ndarray], example_idx: int
) -> Counterexample:
    if predicted is None:
        return Counterexample(
            example_index=example_idx,
            input_grid=inp,
            expected_output=expected,
            predicted_output=None,
            failed_pixels=[(r, c) for r in range(expected.shape[0]) for c in range(expected.shape[1])],
            failure_fraction=1.0,
        )
    failed = _find_failed_pixels(predicted, expected)
    total = expected.shape[0] * expected.shape[1]
    return Counterexample(
        example_index=example_idx,
        input_grid=inp,
        expected_output=expected,
        predicted_output=predicted,
        failed_pixels=failed,
        failure_fraction=len(failed) / max(total, 1),
    )


class CEGISSolver:
    """CEGIS solver that combines DSL programs, local rules, and refinement."""

    def __init__(
        self,
        max_refinement_steps: int = 100,
        timeout_seconds: float = 120.0,
        dsl_candidates: Optional[List] = None,
        local_rule_strategies: Optional[List[str]] = None,
    ):
        self.max_refinement_steps = max_refinement_steps
        self.timeout_seconds = timeout_seconds
        self.dsl_candidates = dsl_candidates or []
        self.local_rule_strategies = local_rule_strategies

    def solve(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
    ) -> CEGISResult:
        t0 = time.perf_counter()
        trace = []
        total_candidates = 0
        total_counterexamples = 0

        # Phase 1: Try DSL candidates with counterexample-guided pruning
        remaining_dsl = list(self.dsl_candidates)
        active_counterexamples: List[Counterexample] = []
        best_candidate = None
        best_score = float("inf")

        for step in range(self.max_refinement_steps):
            if time.perf_counter() - t0 > self.timeout_seconds:
                break

            if not remaining_dsl:
                break

            # Use counterexamples to prune: test against the counterexample first
            candidate = remaining_dsl.pop(0)
            total_candidates += 1

            if active_counterexamples:
                cx = active_counterexamples[-1]
                try:
                    pred = candidate(cx.input_grid)
                    if pred is None or pred.shape != cx.expected_output.shape:
                        continue
                    if not np.array_equal(pred, cx.expected_output):
                        continue
                except Exception:
                    continue

            errors = []
            all_correct = True
            counterexample = None

            for i, (inp, out) in enumerate(train_pairs):
                try:
                    pred = candidate(inp)
                except Exception:
                    pred = None
                if pred is None or pred.shape != out.shape:
                    errors.append(1.0)
                    all_correct = False
                    if counterexample is None:
                        counterexample = _extract_counterexample(inp, out, pred, i)
                    break
                pixel_err = np.mean(pred != out)
                errors.append(float(pixel_err))
                if pixel_err > 0:
                    all_correct = False
                    if counterexample is None:
                        counterexample = _extract_counterexample(inp, out, pred, i)

            score = sum(errors) / len(errors) if errors else float("inf")

            if counterexample is not None:
                active_counterexamples.append(counterexample)
                total_counterexamples += 1

            trace.append({
                "step": step,
                "type": "dsl",
                "score": score,
                "all_correct": all_correct,
                "n_counterexamples": len(active_counterexamples),
            })

            if score < best_score:
                best_score = score
                best_candidate = CEGISCandidate(
                    hypothesis_type="dsl",
                    hypothesis_data=candidate,
                    train_errors=errors,
                    counterexamples=active_counterexamples.copy(),
                    refinement_step=step,
                )

            if all_correct:
                predictions = []
                for test_inp in test_inputs:
                    try:
                        predictions.append(candidate(test_inp))
                    except Exception:
                        predictions.append(test_inp.copy())
                elapsed = time.perf_counter() - t0
                return CEGISResult(
                    solved=True,
                    predictions=predictions,
                    best_candidate=best_candidate,
                    total_candidates_tried=total_candidates,
                    total_counterexamples=total_counterexamples,
                    refinement_steps=step + 1,
                    elapsed_seconds=elapsed,
                    trace=trace,
                )

        # Phase 2: Try local rules if same-size
        same_size = all(inp.shape == out.shape for inp, out in train_pairs)
        if same_size:
            from reasoning_project.local_rules import synthesize_local_rules, apply_local_rule

            strategies = self.local_rule_strategies
            rules = synthesize_local_rules(train_pairs, strategies)
            for rule in rules:
                total_candidates += 1
                if time.perf_counter() - t0 > self.timeout_seconds:
                    break

                all_correct = True
                for inp, out in train_pairs:
                    pred = apply_local_rule(inp, rule)
                    if pred is None or not np.array_equal(pred, out):
                        all_correct = False
                        break

                if all_correct:
                    predictions = []
                    for test_inp in test_inputs:
                        pred = apply_local_rule(test_inp, rule)
                        if pred is None:
                            from reasoning_project.local_rules import apply_local_rule_fuzzy, apply_local_rule_with_fallback, _loo_validate_fuzzy
                            if _loo_validate_fuzzy(train_pairs, rule.strategy_name):
                                pred = apply_local_rule_fuzzy(test_inp, rule)
                            if pred is None:
                                pred = apply_local_rule_with_fallback(test_inp, rule)
                        predictions.append(pred)
                    elapsed = time.perf_counter() - t0
                    best_candidate = CEGISCandidate(
                        hypothesis_type="local_rule",
                        hypothesis_data=rule,
                        train_errors=[0.0] * len(train_pairs),
                        counterexamples=[],
                        refinement_step=0,
                    )
                    return CEGISResult(
                        solved=True,
                        predictions=predictions,
                        best_candidate=best_candidate,
                        total_candidates_tried=total_candidates,
                        total_counterexamples=total_counterexamples,
                        refinement_steps=0,
                        elapsed_seconds=elapsed,
                        trace=trace,
                    )

        elapsed = time.perf_counter() - t0
        return CEGISResult(
            solved=False,
            predictions=None,
            best_candidate=best_candidate,
            total_candidates_tried=total_candidates,
            total_counterexamples=total_counterexamples,
            refinement_steps=len(trace),
            elapsed_seconds=elapsed,
            trace=trace,
        )


def build_dsl_candidates(
    max_depth: int = 2,
    dsl_profile: str = "arc_expanded",
    colors: Optional[List[int]] = None,
) -> List:
    """Build DSL candidate functions from operators module."""
    from reasoning_project.operators import candidate_programs

    if colors is None:
        colors = list(range(1, 10))

    programs = candidate_programs(max_depth, colors, dsl_profile=dsl_profile)
    candidates = []

    for prog in programs:
        def make_fn(p):
            def fn(grid):
                from reasoning_project.operators import execute_program
                return execute_program(p, grid)
            return fn
        candidates.append(make_fn(prog))

    return candidates
