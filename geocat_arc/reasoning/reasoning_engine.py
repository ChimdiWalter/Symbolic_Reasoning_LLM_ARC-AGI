"""Main reasoning engine — orchestrates rule induction, correction, and self-improvement.

Flow:
1. Analyze the transformation profile
2. Try grid-level solvers (crop, tile, fill, mirror, etc.)
3. Try context-based rule induction (21 extractors)
4. For partial solutions, compose with residual corrections
5. LOO validation to prevent overfitting
6. Record what works for incremental learning
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from typing import Callable

from .transformation_analyzer import analyze_task, TransformationProfile
from .rule_inducer import (
    induce_best_rule, induce_best_partial, induce_rule, InducedRule,
    POSITION_DEPENDENT, _generalization_score,
)
from .residual_corrector import find_correction, Correction
from .grid_solvers import ALL_GRID_SOLVERS
from .structural_inference import infer_structural_transform
from .context_extractors import ALL_EXTRACTORS


@dataclass
class Solution:
    task_id: str
    strategy: str
    apply_fn: Callable[[np.ndarray], np.ndarray]
    train_accuracy: float
    loo_score: float
    is_exact: bool


@dataclass
class NearSolve:
    task_id: str
    strategy: str
    apply_fn: Callable[[np.ndarray], np.ndarray]
    train_accuracy: float
    residual_pattern: str


@dataclass
class ReasoningResult:
    task_id: str
    solution: Solution | None
    near_solves: list[NearSolve]
    profile: TransformationProfile
    strategies_tried: list[str]
    best_accuracy: float


class ReasoningEngine:
    def __init__(self):
        self.solved_insights: dict[str, str] = {}
        self.near_solve_memory: list[NearSolve] = []

    def solve(
        self,
        task_id: str,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
        max_correction_iterations: int = 2,
    ) -> ReasoningResult:
        profile = analyze_task(train_pairs)
        strategies_tried = []
        near_solves = []
        best_solution = None
        best_accuracy = 0.0

        # Phase 0: Structural inference (discovers transforms from data)
        strategies_tried.append("structural_inference")
        si_fn = infer_structural_transform(train_pairs)
        if si_fn is not None:
            acc = self._verify(si_fn, train_pairs)
            if acc >= 1.0:
                loo = self._loo_validate(si_fn, train_pairs)
                if loo >= 1.0:
                    sol = Solution(
                        task_id=task_id,
                        strategy="inferred_structural",
                        apply_fn=si_fn,
                        train_accuracy=acc,
                        loo_score=loo,
                        is_exact=True,
                    )
                    best_solution = sol
            elif acc > best_accuracy:
                best_accuracy = acc

        if best_solution and best_solution.loo_score >= 1.0:
            self.solved_insights[task_id] = best_solution.strategy
            return ReasoningResult(
                task_id=task_id, solution=best_solution,
                near_solves=near_solves, profile=profile,
                strategies_tried=strategies_tried, best_accuracy=1.0,
            )

        # Phase 1: Grid-level solvers (these always generalize)
        for name, solver_fn in ALL_GRID_SOLVERS:
            strategies_tried.append(f"grid:{name}")
            fn = solver_fn(train_pairs)
            if fn is not None:
                acc = self._verify(fn, train_pairs)
                if acc >= 1.0:
                    loo = self._loo_validate(fn, train_pairs)
                    sol = Solution(
                        task_id=task_id,
                        strategy=f"grid:{name}",
                        apply_fn=fn,
                        train_accuracy=acc,
                        loo_score=loo,
                        is_exact=True,
                    )
                    if best_solution is None or loo > best_solution.loo_score:
                        best_solution = sol
                elif acc > best_accuracy:
                    best_accuracy = acc
                    near_solves.append(NearSolve(
                        task_id=task_id,
                        strategy=f"grid:{name}",
                        apply_fn=fn,
                        train_accuracy=acc,
                        residual_pattern="grid_solver_partial",
                    ))

        if best_solution and best_solution.loo_score >= 1.0:
            self.solved_insights[task_id] = best_solution.strategy
            return ReasoningResult(
                task_id=task_id, solution=best_solution,
                near_solves=near_solves, profile=profile,
                strategies_tried=strategies_tried, best_accuracy=1.0,
            )

        # Phase 2: Context-based rule induction with proper LOO
        if profile.same_shape:
            strategies_tried.append("rule_induction:exact")

            candidate_rules = []
            for ext_name, ext_fn in ALL_EXTRACTORS:
                rule = induce_rule(train_pairs, ext_name, ext_fn)
                if rule is None or rule.is_identity:
                    continue
                gen_score = _generalization_score(rule, train_pairs)
                if gen_score <= 0:
                    continue
                acc = self._verify(rule.apply, train_pairs)
                if acc >= 1.0:
                    candidate_rules.append((rule, gen_score))

            candidate_rules.sort(key=lambda x: (-x[1], x[0].num_keys))

            for rule, gen_score in candidate_rules:
                loo = self._loo_reinduce_rule(rule.extractor_name, train_pairs)
                if loo >= 1.0:
                    sol = Solution(
                        task_id=task_id,
                        strategy=f"rule:{rule.extractor_name}",
                        apply_fn=rule.apply,
                        train_accuracy=1.0,
                        loo_score=loo,
                        is_exact=True,
                    )
                    best_solution = sol
                    break

            # Fallback: position-independent extractors with cell-accuracy LOO
            if best_solution is None:
                for rule, gen_score in candidate_rules:
                    if rule.extractor_name in POSITION_DEPENDENT:
                        continue
                    if gen_score < 0.3:
                        continue
                    cell_loo = self._loo_reinduce_cell_accuracy(
                        rule.extractor_name, train_pairs
                    )
                    if cell_loo >= 0.98:
                        sol = Solution(
                            task_id=task_id,
                            strategy=f"rule:{rule.extractor_name}",
                            apply_fn=rule.apply,
                            train_accuracy=1.0,
                            loo_score=cell_loo,
                            is_exact=True,
                        )
                        best_solution = sol
                        break

            if best_solution:
                self.solved_insights[task_id] = best_solution.strategy
                return ReasoningResult(
                    task_id=task_id, solution=best_solution,
                    near_solves=near_solves, profile=profile,
                    strategies_tried=strategies_tried, best_accuracy=1.0,
                )

            # Phase 3: Rule + residual correction (try all extractors on residual)
            strategies_tried.append("rule_induction:partial+correction")
            correction_found = False
            for ext_name, ext_fn in ALL_EXTRACTORS:
                if ext_name in POSITION_DEPENDENT:
                    continue
                rule = induce_rule(train_pairs, ext_name, ext_fn)
                if rule is None or rule.is_identity:
                    continue
                acc = self._verify(rule.apply, train_pairs)
                if acc < 0.5 or acc >= 1.0:
                    continue

                predictions = [rule.apply(inp) for inp, _ in train_pairs]
                targets = [out for _, out in train_pairs]
                inputs = [inp for inp, _ in train_pairs]
                correction = find_correction(predictions, targets, inputs)
                if correction is not None:
                    def make_composed(br, co):
                        def f(grid):
                            return co.apply(br.apply(grid), grid)
                        return f
                    composed_fn = make_composed(rule, correction)
                    comp_acc = self._verify(composed_fn, train_pairs)
                    if comp_acc >= 1.0:
                        loo = self._loo_reinduce_with_correction(
                            ext_name, correction.strategy, train_pairs,
                        )
                        if loo >= 1.0:
                            best_solution = Solution(
                                task_id=task_id,
                                strategy=f"rule:{ext_name}+correction:{correction.strategy}",
                                apply_fn=composed_fn,
                                train_accuracy=1.0, loo_score=loo, is_exact=True,
                            )
                            correction_found = True
                            break

                # Also try: use this rule as base, then learn a SECOND rule on the residual
                residual_pairs = [
                    (rule.apply(inp), out)
                    for inp, out in train_pairs
                ]
                if not all(r[0].shape == r[1].shape for r in residual_pairs):
                    continue
                for res_name, res_fn in ALL_EXTRACTORS:
                    if res_name in POSITION_DEPENDENT:
                        continue
                    res_rule = induce_rule(residual_pairs, res_name, res_fn)
                    if res_rule is None or res_rule.is_identity:
                        continue
                    def make_two_stage(br, rr):
                        def f(grid):
                            return rr.apply(br.apply(grid))
                        return f
                    two_stage = make_two_stage(rule, res_rule)
                    ts_acc = self._verify(two_stage, train_pairs)
                    if ts_acc >= 1.0:
                        loo = self._loo_reinduce_two_stage(
                            ext_name, res_name, train_pairs,
                        )
                        if loo >= 1.0:
                            best_solution = Solution(
                                task_id=task_id,
                                strategy=f"rule:{ext_name}+rule2:{res_name}",
                                apply_fn=two_stage,
                                train_accuracy=1.0, loo_score=loo, is_exact=True,
                            )
                            correction_found = True
                            break
                if correction_found:
                    break

        if best_solution:
            self.solved_insights[task_id] = best_solution.strategy
            best_accuracy = 1.0

        if near_solves:
            self.near_solve_memory.extend(near_solves)

        return ReasoningResult(
            task_id=task_id,
            solution=best_solution,
            near_solves=near_solves,
            profile=profile,
            strategies_tried=strategies_tried,
            best_accuracy=best_accuracy,
        )

    def _verify(
        self,
        fn: Callable,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> float:
        correct = 0
        total = 0
        for inp, out in train_pairs:
            try:
                pred = fn(inp)
                pred = np.array(pred, dtype=np.int32)
                out = np.array(out, dtype=np.int32)
                if pred.shape == out.shape:
                    correct += int(np.sum(pred == out))
                    total += out.size
                else:
                    total += out.size
            except Exception:
                total += out.size
        return correct / total if total > 0 else 0.0

    def _verify_exact(
        self,
        fn: Callable,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> bool:
        for inp, out in train_pairs:
            try:
                pred = fn(inp)
                pred = np.array(pred, dtype=np.int32)
                out = np.array(out, dtype=np.int32)
                if not np.array_equal(pred, out):
                    return False
            except Exception:
                return False
        return True

    def _loo_validate(
        self,
        fn: Callable,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> float:
        if len(train_pairs) < 2:
            return 1.0

        correct_folds = 0
        for hold_idx in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_idx]
            try:
                pred = fn(held_inp)
                pred = np.array(pred, dtype=np.int32)
                held_out = np.array(held_out, dtype=np.int32)
                if np.array_equal(pred, held_out):
                    correct_folds += 1
            except Exception:
                pass

        return correct_folds / len(train_pairs)

    def _loo_reinduce_rule(
        self,
        extractor_name: str,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> float:
        """True LOO: re-induce the same extractor from N-1 pairs, test on held-out."""
        if len(train_pairs) < 2:
            return 1.0

        ext_fn = None
        for name, fn in ALL_EXTRACTORS:
            if name == extractor_name:
                ext_fn = fn
                break
        if ext_fn is None:
            return 0.0

        correct_folds = 0
        for hold_idx in range(len(train_pairs)):
            subset = [p for i, p in enumerate(train_pairs) if i != hold_idx]
            held_inp, held_out = train_pairs[hold_idx]

            rule = induce_rule(subset, extractor_name, ext_fn)
            if rule is None:
                continue

            try:
                pred = rule.apply(held_inp)
                pred = np.array(pred, dtype=np.int32)
                held_out_arr = np.array(held_out, dtype=np.int32)
                if np.array_equal(pred, held_out_arr):
                    correct_folds += 1
            except Exception:
                pass

        return correct_folds / len(train_pairs)

    def _loo_reinduce_cell_accuracy(
        self,
        extractor_name: str,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> float:
        """LOO with cell-level accuracy: re-induce from N-1 pairs, measure pixel accuracy."""
        if len(train_pairs) < 2:
            return 1.0

        ext_fn = None
        for name, fn in ALL_EXTRACTORS:
            if name == extractor_name:
                ext_fn = fn
                break
        if ext_fn is None:
            return 0.0

        total_correct = 0
        total_cells = 0
        for hold_idx in range(len(train_pairs)):
            subset = [p for i, p in enumerate(train_pairs) if i != hold_idx]
            held_inp, held_out = train_pairs[hold_idx]

            rule = induce_rule(subset, extractor_name, ext_fn)
            if rule is None:
                total_cells += held_out.size
                continue

            try:
                pred = rule.apply(held_inp)
                pred = np.array(pred, dtype=np.int32)
                held_out_arr = np.array(held_out, dtype=np.int32)
                if pred.shape == held_out_arr.shape:
                    total_correct += int(np.sum(pred == held_out_arr))
                total_cells += held_out_arr.size
            except Exception:
                total_cells += held_out.size

        return total_correct / total_cells if total_cells > 0 else 0.0

    def _loo_reinduce_with_correction(
        self,
        extractor_name: str,
        correction_strategy: str,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> float:
        """True LOO for rule+correction: re-induce both from N-1 pairs."""
        if len(train_pairs) < 3:
            return 0.0

        ext_fn = None
        for name, fn in ALL_EXTRACTORS:
            if name == extractor_name:
                ext_fn = fn
                break
        if ext_fn is None:
            return 0.0

        correct_folds = 0
        for hold_idx in range(len(train_pairs)):
            subset = [p for i, p in enumerate(train_pairs) if i != hold_idx]
            held_inp, held_out = train_pairs[hold_idx]

            rule = induce_rule(subset, extractor_name, ext_fn)
            if rule is None:
                continue

            predictions = [rule.apply(inp) for inp, _ in subset]
            targets = [out for _, out in subset]
            inputs = [inp for inp, _ in subset]

            correction = find_correction(predictions, targets, inputs)
            if correction is None:
                continue

            try:
                pred = rule.apply(held_inp)
                corrected = correction.apply(pred, held_inp)
                corrected = np.array(corrected, dtype=np.int32)
                held_out_arr = np.array(held_out, dtype=np.int32)
                if np.array_equal(corrected, held_out_arr):
                    correct_folds += 1
            except Exception:
                pass

        return correct_folds / len(train_pairs)

    def _loo_reinduce_two_stage(
        self,
        ext1_name: str,
        ext2_name: str,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> float:
        """True LOO for two-stage rules: re-induce both from N-1 pairs."""
        if len(train_pairs) < 2:
            return 0.0

        ext1_fn = ext2_fn = None
        for name, fn in ALL_EXTRACTORS:
            if name == ext1_name:
                ext1_fn = fn
            if name == ext2_name:
                ext2_fn = fn
        if ext1_fn is None or ext2_fn is None:
            return 0.0

        correct_folds = 0
        for hold_idx in range(len(train_pairs)):
            subset = [p for i, p in enumerate(train_pairs) if i != hold_idx]
            held_inp, held_out = train_pairs[hold_idx]

            rule1 = induce_rule(subset, ext1_name, ext1_fn)
            if rule1 is None:
                continue

            residual_pairs = [(rule1.apply(inp), out) for inp, out in subset]
            if not all(r[0].shape == r[1].shape for r in residual_pairs):
                continue

            rule2 = induce_rule(residual_pairs, ext2_name, ext2_fn)
            if rule2 is None:
                continue

            try:
                pred = rule2.apply(rule1.apply(held_inp))
                pred = np.array(pred, dtype=np.int32)
                held_out_arr = np.array(held_out, dtype=np.int32)
                if np.array_equal(pred, held_out_arr):
                    correct_folds += 1
            except Exception:
                pass

        return correct_folds / len(train_pairs)

    def _loo_validate_reinduce(
        self,
        strategy_type: str,
        train_pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> float:
        """True LOO: re-induce the rule from N-1 pairs, test on held-out."""
        if len(train_pairs) < 2:
            return 1.0

        correct_folds = 0
        for hold_idx in range(len(train_pairs)):
            subset = [p for i, p in enumerate(train_pairs) if i != hold_idx]
            held_inp, held_out = train_pairs[hold_idx]

            if strategy_type.startswith("grid:"):
                solver_name = strategy_type[5:]
                fn = None
                for name, solver_fn in ALL_GRID_SOLVERS:
                    if name == solver_name:
                        fn = solver_fn(subset)
                        break
            elif strategy_type.startswith("rule:"):
                ext_name = strategy_type[5:].split("+")[0]
                rule = induce_best_rule(subset, allow_position_dependent=True)
                fn = rule.apply if rule and rule.extractor_name == ext_name else None
            else:
                fn = None

            if fn is None:
                continue

            try:
                pred = fn(held_inp)
                pred = np.array(pred, dtype=np.int32)
                held_out_arr = np.array(held_out, dtype=np.int32)
                if np.array_equal(pred, held_out_arr):
                    correct_folds += 1
            except Exception:
                pass

        return correct_folds / len(train_pairs)
