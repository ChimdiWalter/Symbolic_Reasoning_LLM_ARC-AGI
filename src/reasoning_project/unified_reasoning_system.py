"""Unified Iterative Reasoning System.

Architecture: PERCEIVE → REASON → DIAGNOSE → REFINE → ACCUMULATE

Unlike the previous linear pipeline (try each layer once, stop at first solve),
this system:
  1. Runs all layers and collects ALL candidates (not just the first)
  2. When no candidate solves exactly, diagnoses what's wrong with the best
  3. Uses the diagnosis to generate targeted corrections
  4. Feeds insights from solved tasks into unsolved ones (accumulation)
  5. Tries multiple perceptual decompositions (not just one view of the grid)

Modules integrated:
  - adaptive_synthesizer: DSL-based delta-guided synthesis
  - adaptive_reasoner: context-based rule construction (23 perceptual lenses)
  - hypothesis_engine: multi-level hypothesis generation
  - composable_reasoner: data-driven rule discovery
  - object_spatial_reasoner: gestalt + spatial reasoning
  - meta_learner: transfer from previously solved tasks
  - grid_decomposition: implicit grid subdivision
  - inverse_reasoning: bidirectional program search
  - output_shape_predictor: different-shape task handling
  - failure_diagnosis: targeted error correction
  - rule_abstraction: generalize memorized rules
  - meta_reasoning: observe→represent→hypothesise→test→refine cycle
"""
from __future__ import annotations

import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.operator_genesis import SynthesizedOperator
from reasoning_project.delta_engine import (
    compute_task_delta,
    delta_to_embedding,
    TaskDelta,
)


# ===================================================================
# Reasoning Trace
# ===================================================================

@dataclass
class UnifiedTrace:
    task_id: str = ""
    layers_tried: List[str] = field(default_factory=list)
    layer_timings: Dict[str, float] = field(default_factory=dict)
    solving_layer: Optional[str] = None
    solving_family: Optional[str] = None
    delta_type: Optional[str] = None
    delta_subtypes: List[str] = field(default_factory=list)
    partial_results: List[Dict[str, Any]] = field(default_factory=list)
    total_candidates: int = 0
    total_verified: int = 0
    iteration: int = 0
    diagnosis: Optional[str] = None


# ===================================================================
# Insight Memory — accumulates REASONING insights, not just layer+family
# ===================================================================

@dataclass
class ReasoningInsight:
    """A transferable reasoning insight from a solved task."""
    layer: str
    family: str
    delta_type: str
    delta_subtypes: List[str]
    task_ids: List[str] = field(default_factory=list)
    success_count: int = 1
    # The actual insight — what property/pattern/rule was discovered
    insight_type: str = ""  # e.g. "objects_with_holes_recolor", "row_color_determines_fill"
    insight_params: Dict[str, Any] = field(default_factory=dict)


class InsightMemory:
    """Accumulates reasoning insights within a session.

    Beyond just recording which layer solved what (the old SessionMemory),
    this records WHY — what property discriminated objects, what context
    lens found the rule, what decomposition strategy worked. These insights
    transfer to similar unseen tasks.
    """

    def __init__(self):
        self.insights: List[ReasoningInsight] = []
        self.solved_task_ids: set = set()
        self._delta_cache: Dict[str, List[ReasoningInsight]] = {}

    def record_success(self, layer: str, family: str, delta_type: str,
                       delta_subtypes: List[str], task_id: str,
                       insight_type: str = "", insight_params: Dict = None):
        for s in self.insights:
            if s.layer == layer and s.family == family and s.insight_type == insight_type:
                s.success_count += 1
                s.task_ids.append(task_id)
                self.solved_task_ids.add(task_id)
                self._delta_cache.clear()
                return
        self.insights.append(ReasoningInsight(
            layer=layer, family=family,
            delta_type=delta_type,
            delta_subtypes=delta_subtypes,
            task_ids=[task_id],
            insight_type=insight_type,
            insight_params=insight_params or {},
        ))
        self.solved_task_ids.add(task_id)
        self._delta_cache.clear()

    def suggest_layer_order(self, delta_type: str, delta_subtypes: List[str]) -> List[str]:
        scores: Dict[str, float] = {}
        for s in self.insights:
            similarity = 0.0
            if s.delta_type == delta_type:
                similarity += 2.0
            overlap = len(set(s.delta_subtypes) & set(delta_subtypes))
            similarity += overlap * 0.5
            layer_score = scores.get(s.layer, 0.0)
            scores[s.layer] = layer_score + similarity * s.success_count
        return sorted(scores.keys(), key=lambda k: -scores[k])

    def get_relevant_insights(self, delta_type: str, delta_subtypes: List[str]) -> List[ReasoningInsight]:
        relevant = []
        for s in self.insights:
            similarity = 0.0
            if s.delta_type == delta_type:
                similarity += 2.0
            overlap = len(set(s.delta_subtypes) & set(delta_subtypes))
            similarity += overlap * 0.5
            if similarity > 0:
                relevant.append(s)
        return sorted(relevant, key=lambda x: -x.success_count)


_insight_memory = InsightMemory()


# ===================================================================
# Layer wrappers
# ===================================================================

def _safe_run(name: str, fn: Callable, trace: UnifiedTrace) -> List[SynthesizedOperator]:
    start = time.time()
    trace.layers_tried.append(name)
    try:
        ops = fn()
        trace.layer_timings[name] = time.time() - start
        trace.total_candidates += len(ops)
        return ops
    except Exception:
        trace.layer_timings[name] = time.time() - start
        return []


def _run_adaptive_synthesizer(train_pairs, delta, timeout, trace):
    def fn():
        from reasoning_project.adaptive_synthesizer import synthesize_adaptive
        return synthesize_adaptive(train_pairs, max_depth=2, timeout_seconds=timeout)
    return _safe_run("adaptive_synthesizer", fn, trace)


def _run_adaptive_reasoner(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.adaptive_reasoner import reason_adaptively
        return reason_adaptively(train_pairs, timeout_seconds=timeout)
    return _safe_run("adaptive_reasoner", fn, trace)


def _run_hypothesis_engine(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.hypothesis_engine import reason_by_hypothesis
        return reason_by_hypothesis(train_pairs, timeout_seconds=timeout)
    return _safe_run("hypothesis_engine", fn, trace)


def _run_composable_reasoner(train_pairs, timeout, trace, task_id=""):
    def fn():
        from reasoning_project.composable_reasoner import reason_composably
        return reason_composably(train_pairs, timeout_seconds=timeout, task_id=task_id)
    return _safe_run("composable_reasoner", fn, trace)


def _run_spatial_reasoner(train_pairs, timeout, trace, task_id=""):
    def fn():
        from reasoning_project.object_spatial_reasoner import reason_spatially
        return reason_spatially(train_pairs, timeout_seconds=timeout, task_id=task_id)
    return _safe_run("spatial_reasoner", fn, trace)


def _run_meta_learner(train_pairs, delta, timeout, trace):
    def fn():
        from reasoning_project.meta_learner import build_meta_learner_from_file
        import os
        pairs_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "outputs", "full_novel_reasoning_pipeline_v2",
            "solved_program_pairs.json"
        )
        if os.path.exists(pairs_path):
            ml = build_meta_learner_from_file(pairs_path)
            return ml.propose(train_pairs, top_k=10, try_compositions=True)
        return []
    return _safe_run("meta_learner", fn, trace)


def _run_grid_decomposition(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.grid_decomposition import solve_by_decomposition
        return solve_by_decomposition(train_pairs, timeout_seconds=timeout)
    return _safe_run("grid_decomposition", fn, trace)


def _run_inverse_reasoning(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.inverse_reasoning import search_bidirectional
        return search_bidirectional(train_pairs, timeout_seconds=timeout)
    return _safe_run("inverse_reasoning", fn, trace)


def _run_output_shape_predictor(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.output_shape_predictor import solve_different_shape_task
        return solve_different_shape_task(train_pairs, timeout_seconds=timeout)
    return _safe_run("output_shape_predictor", fn, trace)


def _run_object_correspondence(train_pairs, timeout, trace, task_id=""):
    def fn():
        from reasoning_project.object_correspondence import reason_by_object_correspondence
        return reason_by_object_correspondence(train_pairs, timeout_seconds=timeout, task_id=task_id)
    return _safe_run("object_correspondence", fn, trace)


def _run_different_shape(train_pairs, timeout, trace, task_id=""):
    def fn():
        from reasoning_project.different_shape_reasoner import reason_different_shape
        return reason_different_shape(train_pairs, timeout_seconds=timeout, task_id=task_id)
    return _safe_run("different_shape", fn, trace)


def _run_meta_reasoning(train_pairs, timeout, trace, task_id=""):
    def fn():
        from reasoning_project.meta_reasoning import reason_meta
        return reason_meta(train_pairs, timeout_seconds=timeout, task_id=task_id)
    return _safe_run("meta_reasoning", fn, trace)


def _run_fill_solver(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.fill_solver import solve_task_fill
        test_proxy = [inp for inp, _ in train_pairs[:1]]
        result = solve_task_fill(train_pairs, test_proxy)
        if result is None:
            return []
        preds, meta = result
        def make_solver_fn(tp):
            def solve_fn(grid, _tp=tp):
                from reasoning_project.fill_solver import solve_task_fill as stf
                r = stf(_tp, [grid])
                if r is None:
                    return grid.copy()
                return r[0][0] if isinstance(r[0], list) else r[0]
            return solve_fn
        exec_fn = make_solver_fn(train_pairs)
        if _check_train_consistency_fn(exec_fn, train_pairs):
            strategy = meta.get("strategy", "fill") if isinstance(meta, dict) else "fill"
            return [SynthesizedOperator(
                operator_id=f"fill_{strategy}_{uuid.uuid4().hex[:8]}",
                operator_family=f"fill_{strategy}",
                parameters={},
                preconditions=[],
                execute=exec_fn,
                explanation=f"Fill solver: {strategy}",
                source_failure_signature={},
            )]
        return []
    return _safe_run("fill_solver", fn, trace)


def _run_relation_solver(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.relation_solver import solve_task_relation
        test_proxy = [inp for inp, _ in train_pairs[:1]]
        result = solve_task_relation(train_pairs, test_proxy)
        if result is None:
            return []
        preds, meta = result
        def make_solver_fn(tp):
            def solve_fn(grid, _tp=tp):
                from reasoning_project.relation_solver import solve_task_relation as str_
                r = str_(_tp, [grid])
                if r is None:
                    return grid.copy()
                return r[0][0] if isinstance(r[0], list) else r[0]
            return solve_fn
        exec_fn = make_solver_fn(train_pairs)
        if _check_train_consistency_fn(exec_fn, train_pairs):
            strategy = meta.get("strategy", "relation") if isinstance(meta, dict) else "relation"
            return [SynthesizedOperator(
                operator_id=f"relation_{strategy}_{uuid.uuid4().hex[:8]}",
                operator_family=f"relation_{strategy}",
                parameters={},
                preconditions=[],
                execute=exec_fn,
                explanation=f"Relation solver: {strategy}",
                source_failure_signature={},
            )]
        return []
    return _safe_run("relation_solver", fn, trace)


def _run_reasoning_v2(train_pairs, timeout, trace):
    def fn():
        from reasoning_project.arc_reasoning_v2 import reason_v2
        return reason_v2(train_pairs, timeout_seconds=timeout)
    return _safe_run("reasoning_v2", fn, trace)


def _check_train_consistency_fn(fn, train_pairs):
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


# ===================================================================
# Verification
# ===================================================================

def _verify_on_test(op, test_inputs, test_outputs):
    for ti, to in zip(test_inputs, test_outputs):
        try:
            pred = op.execute(ti)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != to.shape or not np.array_equal(pred, to):
                return False
        except Exception:
            return False
    return True


def _verify_on_train(op, train_pairs):
    for inp, out in train_pairs:
        try:
            pred = op.execute(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


def _score_partial(op, train_pairs):
    """Score how close an operator gets — pixel accuracy across all pairs."""
    total = 0
    correct = 0
    for inp, out in train_pairs:
        try:
            pred = op.execute(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return 0.0
            if pred.shape != out.shape:
                return 0.0
            total += out.size
            correct += int(np.sum(pred == out))
        except Exception:
            return 0.0
    return correct / max(total, 1)


def _verify_loo_correction(best_op, train_pairs, timeout, trace):
    """Leave-one-out verification for corrections in submission mode.

    For each training pair, hold it out, derive a correction from the
    remaining N-1 pairs, and verify the correction on the held-out pair.
    Returns the full-data correction ONLY if every LOO fold succeeds.
    This prevents overfitted corrections from inflating submission scores.
    """
    n = len(train_pairs)
    if n < 2:
        corrections = _diagnose_and_correct(best_op, train_pairs, timeout, trace)
        return [c for c in corrections if _verify_on_train(c, train_pairs)]

    per_fold_timeout = timeout / (n + 2)

    full_corrections = _diagnose_and_correct(
        best_op, train_pairs, per_fold_timeout, trace)
    if not full_corrections:
        return []

    generalized = []
    for corr_op in full_corrections:
        if not _verify_on_train(corr_op, train_pairs):
            continue

        loo_pass = True
        for i in range(n):
            held_out = [train_pairs[i]]
            fit_pairs = train_pairs[:i] + train_pairs[i + 1:]

            fold_trace = UnifiedTrace()
            fold_corrections = _diagnose_and_correct(
                best_op, fit_pairs, per_fold_timeout, fold_trace)

            fold_ok = False
            for fc in fold_corrections:
                if _verify_on_train(fc, held_out):
                    fold_ok = True
                    break

            if not fold_ok:
                loo_pass = False
                break

        if loo_pass:
            generalized.append(corr_op)
            return generalized

    return generalized


def _loo_residual_correction(best_op, train_pairs, timeout, trace):
    """LOO-Residual Correction: generate corrections from cross-validation failures.

    When a program passes ALL training pairs (zero residuals), standard
    correction has nothing to fix. This method generates SYNTHETIC residuals
    via leave-one-out: hold out each pair, re-synthesize from N-1 pairs,
    and use the prediction errors on the held-out pair as correction targets.

    These LOO residuals approximate what happens on unseen test data,
    enabling corrections without test output leakage.
    """
    n = len(train_pairs)
    if n < 2:
        return []

    start = time.time()

    # Step 1: Generate LOO residuals
    # For each fold, re-derive the base operation from N-1 pairs,
    # apply to the held-out pair, and collect the residual.
    loo_residuals = []  # list of (held_input, loo_pred, expected_output)
    for i in range(n):
        if time.time() - start > timeout * 0.4:
            break
        held_inp, held_out = train_pairs[i]
        fit_pairs = train_pairs[:i] + train_pairs[i + 1:]

        # Re-run the same solver family on N-1 pairs to get a "reduced" program
        fold_trace = UnifiedTrace()
        fold_timeout = min(timeout * 0.1, 3.0)
        try:
            from reasoning_project.delta_engine import compute_task_delta
            delta = compute_task_delta(fit_pairs)
        except Exception:
            delta = None

        try:
            fold_ops = _run_adaptive_synthesizer(fit_pairs, delta, fold_timeout, fold_trace)
        except Exception:
            fold_ops = []

        # Find a fold program that passes N-1 pairs
        fold_op = None
        for fop in fold_ops:
            try:
                if all(fop.execute(inp) is not None and
                       isinstance(fop.execute(inp), np.ndarray) and
                       fop.execute(inp).shape == out.shape and
                       np.array_equal(fop.execute(inp), out)
                       for inp, out in fit_pairs):
                    fold_op = fop
                    break
            except Exception:
                continue

        if fold_op is None:
            continue

        # Apply fold program to held-out input
        try:
            loo_pred = fold_op.execute(held_inp)
            if loo_pred is not None and isinstance(loo_pred, np.ndarray) and \
                    loo_pred.shape == held_out.shape:
                if not np.array_equal(loo_pred, held_out):
                    loo_residuals.append((held_inp, loo_pred, held_out))
        except Exception:
            continue

    if not loo_residuals:
        return []

    # Step 2: Learn corrections from LOO residuals
    # Use the existing correction engine but with LOO residuals as diag_pairs
    results = []
    remaining = timeout - (time.time() - start)
    if remaining < 1.0:
        return []

    # Build correction pairs from LOO residuals
    loo_diag_pairs = [(inp, out) for inp, _, out in loo_residuals]
    loo_preds = [pred for _, pred, _ in loo_residuals]

    # Try the same correction strategies but on LOO residuals
    try:
        all_same_shape = all(p.shape == o.shape == i.shape
                             for p, (i, o) in zip(loo_preds, loo_diag_pairs))
        if not all_same_shape:
            return []

        # Strategy: Learn a consistent color correction from LOO failures
        # (input_color, loo_pred_color) → expected_color
        color_map = {}
        map_ok = True
        for loo_pred, (inp, out) in zip(loo_preds, loo_diag_pairs):
            wrong = loo_pred != out
            if not wrong.any():
                continue
            wr, wc = np.where(wrong)
            for r, c in zip(wr, wc):
                key = (int(inp[r, c]), int(loo_pred[r, c]))
                val = int(out[r, c])
                if key in color_map:
                    if color_map[key] != val:
                        map_ok = False
                        break
                else:
                    color_map[key] = val
            if not map_ok:
                break

        if map_ok and color_map:
            # Verify correction doesn't break correct LOO pixels
            breaks = False
            for loo_pred, (inp, out) in zip(loo_preds, loo_diag_pairs):
                correct = loo_pred == out
                cr, cc_arr = np.where(correct)
                for r, c in zip(cr, cc_arr):
                    key = (int(inp[r, c]), int(loo_pred[r, c]))
                    if key in color_map and color_map[key] != int(loo_pred[r, c]):
                        breaks = True
                        break
                if breaks:
                    break

            if not breaks:
                frozen_map = dict(color_map)
                def make_loo_corr(base_fn, cmap):
                    def fn(grid, _b=base_fn, _m=cmap):
                        mid = _b(grid)
                        if mid is None:
                            return None
                        out = mid.copy()
                        if grid.shape == mid.shape:
                            for (ic, pc), tc in _m.items():
                                mask = (grid == ic) & (mid == pc)
                                out[mask] = tc
                        return out
                    return fn
                corr_fn = make_loo_corr(best_op.execute, frozen_map)
                corr_op = SynthesizedOperator(
                    operator_id=f"loo_residual_{uuid.uuid4().hex[:8]}",
                    operator_family=f"loo_residual_corr_{best_op.operator_family}",
                    parameters={"n_loo_residuals": len(loo_residuals),
                                "n_corrections": len(frozen_map)},
                    preconditions=[],
                    execute=corr_fn,
                    explanation=(f"[LOO-Residual] {best_op.explanation} "
                                 f"→ input-conditional fix from {len(loo_residuals)} LOO failures"),
                    source_failure_signature={},
                )
                if _verify_on_train(corr_op, train_pairs):
                    results.append(corr_op)

        # Strategy: global color swap from LOO residuals
        if not results:
            for src_c in range(10):
                for tgt_c in range(10):
                    if src_c == tgt_c:
                        continue
                    consistent = True
                    for loo_pred, (_, out) in zip(loo_preds, loo_diag_pairs):
                        wrong = loo_pred != out
                        if not wrong.any():
                            continue
                        if not (np.all(loo_pred[wrong] == src_c) and
                                np.all(out[wrong] == tgt_c)):
                            consistent = False
                            break
                    if consistent:
                        def make_loo_swap(base_fn, s, t):
                            def fn(grid, _b=base_fn, _s=s, _t=t):
                                mid = _b(grid)
                                if mid is None:
                                    return None
                                out = mid.copy()
                                out[mid == _s] = _t
                                return out
                            return fn
                        swap_fn = make_loo_swap(best_op.execute, src_c, tgt_c)
                        swap_op = SynthesizedOperator(
                            operator_id=f"loo_swap_{uuid.uuid4().hex[:8]}",
                            operator_family=f"loo_swap_{best_op.operator_family}",
                            parameters={"src": src_c, "tgt": tgt_c},
                            preconditions=[],
                            execute=swap_fn,
                            explanation=f"[LOO-Swap] {best_op.explanation} → swap {src_c}→{tgt_c}",
                            source_failure_signature={},
                        )
                        if _verify_on_train(swap_op, train_pairs):
                            results.append(swap_op)
                            break
                if results:
                    break

        # Strategy: neighbor-conditioned correction from LOO residuals
        if not results and len(loo_residuals) >= 2:
            sig_map = {}
            sig_ok = True
            for loo_pred, (inp, out) in zip(loo_preds, loo_diag_pairs):
                wrong = loo_pred != out
                if not wrong.any():
                    continue
                wr, wc = np.where(wrong)
                for r, c in zip(wr, wc):
                    h_g, w_g = inp.shape
                    counts = [0] * 10
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < h_g and 0 <= nc < w_g:
                                counts[inp[nr, nc]] += 1
                    sig = (int(inp[r, c]), int(loo_pred[r, c])) + tuple(counts)
                    val = int(out[r, c])
                    if sig in sig_map:
                        if sig_map[sig] != val:
                            sig_ok = False
                            break
                    else:
                        sig_map[sig] = val
                if not sig_ok:
                    break

            if sig_ok and sig_map:
                breaks = False
                for loo_pred, (inp, out) in zip(loo_preds, loo_diag_pairs):
                    correct = loo_pred == out
                    cr, cc_arr = np.where(correct)
                    for r, c in zip(cr, cc_arr):
                        h_g, w_g = inp.shape
                        counts = [0] * 10
                        for dr in (-1, 0, 1):
                            for dc in (-1, 0, 1):
                                if dr == 0 and dc == 0:
                                    continue
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < h_g and 0 <= nc < w_g:
                                    counts[inp[nr, nc]] += 1
                        sig = (int(inp[r, c]), int(loo_pred[r, c])) + tuple(counts)
                        if sig in sig_map and sig_map[sig] != int(loo_pred[r, c]):
                            breaks = True
                            break
                    if breaks:
                        break

                if not breaks:
                    frozen_sig = dict(sig_map)
                    def make_loo_nbr(base_fn, smap):
                        def fn(grid, _b=base_fn, _m=smap):
                            mid = _b(grid)
                            if mid is None:
                                return None
                            out = mid.copy()
                            h_g, w_g = grid.shape
                            for r in range(h_g):
                                for c in range(w_g):
                                    counts = [0] * 10
                                    for dr in (-1, 0, 1):
                                        for dc in (-1, 0, 1):
                                            if dr == 0 and dc == 0:
                                                continue
                                            nr, nc = r + dr, c + dc
                                            if 0 <= nr < h_g and 0 <= nc < w_g:
                                                counts[grid[nr, nc]] += 1
                                    sig = (int(grid[r, c]), int(mid[r, c])) + tuple(counts)
                                    if sig in _m:
                                        out[r, c] = _m[sig]
                            return out
                        return fn
                    nbr_fn = make_loo_nbr(best_op.execute, frozen_sig)
                    nbr_op = SynthesizedOperator(
                        operator_id=f"loo_nbr_{uuid.uuid4().hex[:8]}",
                        operator_family=f"loo_nbr_corr_{best_op.operator_family}",
                        parameters={"n_sigs": len(frozen_sig)},
                        preconditions=[],
                        execute=nbr_fn,
                        explanation=(f"[LOO-Neighbor] {best_op.explanation} "
                                     f"→ neighbor fix from {len(loo_residuals)} LOO failures"),
                        source_failure_signature={},
                    )
                    if _verify_on_train(nbr_op, train_pairs):
                        results.append(nbr_op)

    except Exception:
        pass

    return results


def _score_partial_on_test(op, test_inputs, test_outputs):
    """Score partial correctness on test data."""
    total = 0
    correct = 0
    for inp, out in zip(test_inputs, test_outputs):
        try:
            pred = op.execute(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return 0.0
            if pred.shape != out.shape:
                return 0.0
            total += out.size
            correct += int(np.sum(pred == out))
        except Exception:
            return 0.0
    return correct / max(total, 1)


# ===================================================================
# Failure diagnosis + correction (iteration engine)
# ===================================================================

def _diagnose_and_correct(
    best_op: SynthesizedOperator,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout: float,
    trace: UnifiedTrace,
    test_inputs: Optional[List[np.ndarray]] = None,
    test_outputs: Optional[List[np.ndarray]] = None,
) -> List[SynthesizedOperator]:
    """Given a partial solution, diagnose what's wrong and generate corrections."""
    results = []
    start = time.time()

    diag_pairs: List[Tuple[np.ndarray, np.ndarray]]
    if test_inputs and test_outputs:
        diag_pairs = list(zip(test_inputs, test_outputs))
    else:
        diag_pairs = train_pairs

    try:
        from reasoning_project.failure_diagnosis import diagnose_failure, suggest_correction_ops
        preds = []
        for inp, out in diag_pairs:
            pred = best_op.execute(inp)
            if pred is None or pred.shape != out.shape:
                return []
            preds.append(pred)

        diagnoses = []
        for pred, (inp, out) in zip(preds, diag_pairs):
            d = diagnose_failure(pred, out, inp)
            diagnoses.append(d)

        if diagnoses:
            trace.diagnosis = diagnoses[0].error_pattern
            correction_pairs = [(pred, out) for pred, (_, out) in zip(preds, diag_pairs)]
            corr_ops = suggest_correction_ops(diagnoses[0], correction_pairs)
            for corr_op in corr_ops:
                if time.time() - start > timeout:
                    break
                def make_composed(base_fn, corr_fn):
                    def fn(grid, _b=base_fn, _c=corr_fn):
                        return _c(_b(grid))
                    return fn
                composed = make_composed(best_op.execute, corr_op.execute)
                composed_op = SynthesizedOperator(
                    operator_id=f"corrected_{uuid.uuid4().hex[:8]}",
                    operator_family=f"corrected_{best_op.operator_family}",
                    parameters={"base": best_op.operator_family,
                                "correction": corr_op.operator_family},
                    preconditions=[],
                    execute=composed,
                    explanation=f"[Corrected] {best_op.explanation} → {corr_op.explanation}",
                    source_failure_signature={},
                )
                if _verify_on_train(composed_op, train_pairs):
                    results.append(composed_op)
                    return results
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: try simple corrections without the diagnosis module
    try:
        preds = [best_op.execute(inp) for inp, _ in diag_pairs]
        if any(p is None for p in preds):
            return []

        correction_pairs = [(pred, out) for pred, (_, out) in zip(preds, diag_pairs)]
        all_same_shape = all(p.shape == o.shape for p, (_, o) in zip(preds, diag_pairs))
        if not all_same_shape:
            return []

        # Collect original inputs corresponding to diag_pairs
        diag_inputs = [inp for inp, _ in diag_pairs]

        # Try color swaps on the residual
        for src_c in range(10):
            for tgt_c in range(10):
                if src_c == tgt_c:
                    continue
                consistent = True
                for pred, (_, out) in zip(preds, diag_pairs):
                    wrong = pred != out
                    if not wrong.any():
                        continue
                    wrong_vals = pred[wrong]
                    expected_vals = out[wrong]
                    if not (np.all(wrong_vals == src_c) and np.all(expected_vals == tgt_c)):
                        consistent = False
                        break
                if consistent:
                    # Try global swap first
                    def make_swap(base_fn, s, t):
                        def fn(grid, _b=base_fn, _s=s, _t=t):
                            mid = _b(grid)
                            out = mid.copy()
                            out[mid == _s] = _t
                            return out
                        return fn
                    swap_fn = make_swap(best_op.execute, src_c, tgt_c)
                    swap_op = SynthesizedOperator(
                        operator_id=f"colorswap_{uuid.uuid4().hex[:8]}",
                        operator_family=f"corrected_colorswap_{best_op.operator_family}",
                        parameters={},
                        preconditions=[],
                        execute=swap_fn,
                        explanation=f"[Corrected] {best_op.explanation} then swap {src_c}→{tgt_c}",
                        source_failure_signature={},
                    )
                    if _verify_on_train(swap_op, train_pairs):
                        results.append(swap_op)
                        return results

                    # Global swap failed — try input-conditional swap:
                    # only swap at positions where the INPUT has a specific color
                    for cond_c in range(10):
                        cond_consistent = True
                        for pred, (inp, out) in zip(preds, diag_pairs):
                            wrong = pred != out
                            if not wrong.any():
                                continue
                            if inp.shape != pred.shape:
                                cond_consistent = False
                                break
                            wrong_input_colors = inp[wrong]
                            if not np.all(wrong_input_colors == cond_c):
                                cond_consistent = False
                                break
                            correct_src = (pred == src_c) & ~wrong
                            if correct_src.any() and not np.all(inp[correct_src] == cond_c):
                                pass  # OK — correct src pixels have different input color
                            else:
                                if correct_src.any():
                                    cond_consistent = False
                                    break
                        if cond_consistent:
                            def make_cond_swap(base_fn, s, t, cc):
                                def fn(grid, _b=base_fn, _s=s, _t=t, _cc=cc):
                                    mid = _b(grid)
                                    out = mid.copy()
                                    mask = (mid == _s) & (grid == _cc)
                                    out[mask] = _t
                                    return out
                                return fn
                            cswap_fn = make_cond_swap(best_op.execute, src_c, tgt_c, cond_c)
                            cswap_op = SynthesizedOperator(
                                operator_id=f"condswap_{uuid.uuid4().hex[:8]}",
                                operator_family=f"corrected_condswap_{best_op.operator_family}",
                                parameters={"src": src_c, "tgt": tgt_c, "cond": cond_c},
                                preconditions=[],
                                execute=cswap_fn,
                                explanation=f"[Corrected] {best_op.explanation} then swap {src_c}→{tgt_c} where input=={cond_c}",
                                source_failure_signature={},
                            )
                            if _verify_on_train(cswap_op, train_pairs):
                                results.append(cswap_op)
                                return results

        # Input-conditioned pixel overlay: learn a per-position color
        # correction rule based on (input_color, pred_color) → expected_color
        if preds and all(p.shape == o.shape == i.shape
                         for p, (i, o) in zip(preds, diag_pairs)):
            color_map: Dict[Tuple[int, int], int] = {}
            map_consistent = True
            for pred, (inp, out) in zip(preds, diag_pairs):
                wrong = pred != out
                if not wrong.any():
                    continue
                wr, wc = np.where(wrong)
                for r, c in zip(wr, wc):
                    key = (int(inp[r, c]), int(pred[r, c]))
                    val = int(out[r, c])
                    if key in color_map:
                        if color_map[key] != val:
                            map_consistent = False
                            break
                    else:
                        color_map[key] = val
                if not map_consistent:
                    break

            if map_consistent and color_map:
                # Verify the map doesn't break correct pixels
                breaks_correct = False
                for pred, (inp, out) in zip(preds, diag_pairs):
                    correct = pred == out
                    cr, cc_arr = np.where(correct)
                    for r, c in zip(cr, cc_arr):
                        key = (int(inp[r, c]), int(pred[r, c]))
                        if key in color_map and color_map[key] != int(pred[r, c]):
                            breaks_correct = True
                            break
                    if breaks_correct:
                        break

                if not breaks_correct:
                    frozen_map = dict(color_map)
                    def make_overlay(base_fn, cmap):
                        def fn(grid, _b=base_fn, _m=cmap):
                            mid = _b(grid)
                            out = mid.copy()
                            for (ic, pc), tc in _m.items():
                                mask = (grid == ic) & (mid == pc)
                                out[mask] = tc
                            return out
                        return fn
                    overlay_fn = make_overlay(best_op.execute, frozen_map)
                    overlay_op = SynthesizedOperator(
                        operator_id=f"overlay_{uuid.uuid4().hex[:8]}",
                        operator_family=f"corrected_overlay_{best_op.operator_family}",
                        parameters={"map": {f"{k[0]},{k[1]}": v for k, v in frozen_map.items()}},
                        preconditions=[],
                        execute=overlay_fn,
                        explanation=f"[Corrected] {best_op.explanation} then overlay {len(frozen_map)} input-conditioned fixes",
                        source_failure_signature={},
                    )
                    if _verify_on_train(overlay_op, train_pairs):
                        results.append(overlay_op)
                        return results

        # Neighbor-conditioned correction: use (input_color, pred_color,
        # neighbor_signature) to discriminate wrong from correct pixels
        if preds and all(p.shape == o.shape == i.shape
                         for p, (i, o) in zip(preds, diag_pairs)):
            def _neighbor_sig(grid, r, c):
                h, w = grid.shape
                counts = [0] * 10
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            counts[grid[nr, nc]] += 1
                return tuple(counts)

            sig_map: Dict[Tuple, int] = {}
            sig_consistent = True
            for pred, (inp, out) in zip(preds, diag_pairs):
                wrong = pred != out
                if not wrong.any():
                    continue
                wr, wc = np.where(wrong)
                for r, c in zip(wr, wc):
                    sig = (int(inp[r, c]), int(pred[r, c])) + _neighbor_sig(inp, r, c)
                    val = int(out[r, c])
                    if sig in sig_map:
                        if sig_map[sig] != val:
                            sig_consistent = False
                            break
                    else:
                        sig_map[sig] = val
                if not sig_consistent:
                    break

            if sig_consistent and sig_map:
                breaks = False
                for pred, (inp, out) in zip(preds, diag_pairs):
                    correct = pred == out
                    cr, cc_arr = np.where(correct)
                    for r, c in zip(cr, cc_arr):
                        sig = (int(inp[r, c]), int(pred[r, c])) + _neighbor_sig(inp, r, c)
                        if sig in sig_map and sig_map[sig] != int(pred[r, c]):
                            breaks = True
                            break
                    if breaks:
                        break

                if not breaks:
                    frozen_sig = dict(sig_map)
                    def make_nbr_overlay(base_fn, smap):
                        def fn(grid, _b=base_fn, _m=smap):
                            mid = _b(grid)
                            out = mid.copy()
                            h, w = grid.shape
                            for r in range(h):
                                for c in range(w):
                                    counts = [0] * 10
                                    for dr in (-1, 0, 1):
                                        for dc in (-1, 0, 1):
                                            if dr == 0 and dc == 0:
                                                continue
                                            nr, nc = r + dr, c + dc
                                            if 0 <= nr < h and 0 <= nc < w:
                                                counts[grid[nr, nc]] += 1
                                    sig = (int(grid[r, c]), int(mid[r, c])) + tuple(counts)
                                    if sig in _m:
                                        out[r, c] = _m[sig]
                            return out
                        return fn
                    nbr_fn = make_nbr_overlay(best_op.execute, frozen_sig)
                    nbr_op = SynthesizedOperator(
                        operator_id=f"nbrcorr_{uuid.uuid4().hex[:8]}",
                        operator_family=f"corrected_nbr_{best_op.operator_family}",
                        parameters={},
                        preconditions=[],
                        execute=nbr_fn,
                        explanation=f"[Corrected] {best_op.explanation} then neighbor-conditioned fix",
                        source_failure_signature={},
                    )
                    if _verify_on_train(nbr_op, train_pairs):
                        results.append(nbr_op)
                        return results

        # Position-based correction: learn (r%k, c%k, input_color) → output_color
        if preds and all(p.shape == o.shape == i.shape
                         for p, (i, o) in zip(preds, diag_pairs)):
            for mod in (2, 3, 4, 5):
                pos_map: Dict[Tuple, int] = {}
                pos_ok = True
                for pred, (inp, out) in zip(preds, diag_pairs):
                    wrong = pred != out
                    if not wrong.any():
                        continue
                    wr, wc = np.where(wrong)
                    for r, c in zip(wr, wc):
                        key = (r % mod, c % mod, int(inp[r, c]), int(pred[r, c]))
                        val = int(out[r, c])
                        if key in pos_map:
                            if pos_map[key] != val:
                                pos_ok = False
                                break
                        else:
                            pos_map[key] = val
                    if not pos_ok:
                        break
                if pos_ok and pos_map:
                    breaks_correct = False
                    for pred, (inp, out) in zip(preds, diag_pairs):
                        cr, cc_arr = np.where(pred == out)
                        for r, c in zip(cr, cc_arr):
                            key = (r % mod, c % mod, int(inp[r, c]), int(pred[r, c]))
                            if key in pos_map and pos_map[key] != int(pred[r, c]):
                                breaks_correct = True
                                break
                        if breaks_correct:
                            break
                    if not breaks_correct:
                        frozen_pos = dict(pos_map)
                        _mod = mod
                        def make_pos_corr(base_fn, pmap, m):
                            def fn(grid, _b=base_fn, _pm=pmap, _m=m):
                                mid = _b(grid)
                                out = mid.copy()
                                h, w = grid.shape
                                for r in range(h):
                                    for c in range(w):
                                        key = (r % _m, c % _m, int(grid[r, c]), int(mid[r, c]))
                                        if key in _pm:
                                            out[r, c] = _pm[key]
                                return out
                            return fn
                        pos_fn = make_pos_corr(best_op.execute, frozen_pos, _mod)
                        pos_op = SynthesizedOperator(
                            operator_id=f"poscorr_{uuid.uuid4().hex[:8]}",
                            operator_family=f"corrected_pos_{best_op.operator_family}",
                            parameters={"mod": mod},
                            preconditions=[],
                            execute=pos_fn,
                            explanation=f"[Corrected] {best_op.explanation} then position-mod-{mod} fix",
                            source_failure_signature={},
                        )
                        if _verify_on_train(pos_op, train_pairs):
                            results.append(pos_op)
                            return results

        # Row-column context correction: learn (row_color_signature, input_color) → output
        if preds and all(p.shape == o.shape == i.shape
                         for p, (i, o) in zip(preds, diag_pairs)):
            rc_map: Dict[Tuple, int] = {}
            rc_ok = True
            for pred, (inp, out) in zip(preds, diag_pairs):
                wrong = pred != out
                if not wrong.any():
                    continue
                wr, wc = np.where(wrong)
                for r, c in zip(wr, wc):
                    row_dom = int(np.argmax(np.bincount(inp[r, :].astype(int), minlength=10)))
                    col_dom = int(np.argmax(np.bincount(inp[:, c].astype(int), minlength=10)))
                    key = (int(inp[r, c]), int(pred[r, c]), row_dom, col_dom)
                    val = int(out[r, c])
                    if key in rc_map:
                        if rc_map[key] != val:
                            rc_ok = False
                            break
                    else:
                        rc_map[key] = val
                if not rc_ok:
                    break
            if rc_ok and rc_map:
                breaks = False
                for pred, (inp, out) in zip(preds, diag_pairs):
                    cr, cc_a = np.where(pred == out)
                    for r, c in zip(cr, cc_a):
                        row_dom = int(np.argmax(np.bincount(inp[r, :].astype(int), minlength=10)))
                        col_dom = int(np.argmax(np.bincount(inp[:, c].astype(int), minlength=10)))
                        key = (int(inp[r, c]), int(pred[r, c]), row_dom, col_dom)
                        if key in rc_map and rc_map[key] != int(pred[r, c]):
                            breaks = True
                            break
                    if breaks:
                        break
                if not breaks:
                    frozen_rc = dict(rc_map)
                    def make_rc_corr(base_fn, rcm):
                        def fn(grid, _b=base_fn, _rcm=rcm):
                            mid = _b(grid)
                            out = mid.copy()
                            h, w = grid.shape
                            for r in range(h):
                                row_dom = int(np.argmax(np.bincount(grid[r, :].astype(int), minlength=10)))
                                for c in range(w):
                                    col_dom = int(np.argmax(np.bincount(grid[:, c].astype(int), minlength=10)))
                                    key = (int(grid[r, c]), int(mid[r, c]), row_dom, col_dom)
                                    if key in _rcm:
                                        out[r, c] = _rcm[key]
                            return out
                        return fn
                    rc_fn = make_rc_corr(best_op.execute, frozen_rc)
                    rc_op = SynthesizedOperator(
                        operator_id=f"rccorr_{uuid.uuid4().hex[:8]}",
                        operator_family=f"corrected_rc_{best_op.operator_family}",
                        parameters={},
                        preconditions=[],
                        execute=rc_fn,
                        explanation=f"[Corrected] {best_op.explanation} then row-col context fix",
                        source_failure_signature={},
                    )
                    if _verify_on_train(rc_op, train_pairs):
                        results.append(rc_op)
                        return results

        # Try all reasoning layers on the residual (cross-layer correction)
        remaining = timeout - (time.time() - start)
        if remaining > 1.0:
            corr_sources = []
            try:
                from reasoning_project.adaptive_reasoner import reason_adaptively
                corr_sources.append(("reasoner",
                    reason_adaptively(correction_pairs, timeout_seconds=min(remaining * 0.3, 3.0))))
            except Exception:
                pass
            remaining = timeout - (time.time() - start)
            if remaining > 1.0:
                try:
                    from reasoning_project.adaptive_synthesizer import synthesize_adaptive
                    corr_sources.append(("synthesizer",
                        synthesize_adaptive(correction_pairs, max_depth=2,
                                            timeout_seconds=min(remaining * 0.3, 3.0))))
                except Exception:
                    pass
            remaining = timeout - (time.time() - start)
            if remaining > 1.0:
                try:
                    from reasoning_project.hypothesis_engine import reason_by_hypothesis
                    corr_sources.append(("hypothesis",
                        reason_by_hypothesis(correction_pairs,
                                             timeout_seconds=min(remaining * 0.3, 3.0))))
                except Exception:
                    pass
            remaining = timeout - (time.time() - start)
            if remaining > 1.0:
                try:
                    from reasoning_project.arc_reasoning_v2 import reason_v2
                    corr_sources.append(("reasoning_v2",
                        reason_v2(correction_pairs,
                                  timeout_seconds=min(remaining * 0.3, 3.0))))
                except Exception:
                    pass

            for source_name, corr_ops in corr_sources:
                for corr_op in (corr_ops or [])[:5]:
                    def make_composed2(base_fn, corr_fn):
                        def fn(grid, _b=base_fn, _c=corr_fn):
                            return _c(_b(grid))
                        return fn
                    composed = make_composed2(best_op.execute, corr_op.execute)
                    composed_op = SynthesizedOperator(
                        operator_id=f"residual_{source_name}_{uuid.uuid4().hex[:8]}",
                        operator_family=f"residual_{best_op.operator_family}_then_{corr_op.operator_family}",
                        parameters={},
                        preconditions=[],
                        execute=composed,
                        explanation=f"[Residual/{source_name}] {best_op.explanation} → {corr_op.explanation}",
                        source_failure_signature={},
                    )
                    if _verify_on_train(composed_op, train_pairs):
                        results.append(composed_op)
                        return results
    except Exception:
        pass

    return results


# ===================================================================
# MAIN ENTRY POINT — Iterative Reasoning
# ===================================================================

def reason_unified(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: Optional[List[np.ndarray]] = None,
    test_outputs: Optional[List[np.ndarray]] = None,
    task_id: str = "",
    timeout_seconds: float = 60.0,
    per_layer_timeout: float = 10.0,
) -> Tuple[List[SynthesizedOperator], UnifiedTrace]:
    """Iterative reasoning: try → diagnose → refine → retry."""
    start = time.time()
    trace = UnifiedTrace(task_id=task_id)
    verified = []

    # ---- PERCEIVE: compute structural delta ----
    try:
        delta = compute_task_delta(train_pairs)
        trace.delta_type = delta.delta_type
        trace.delta_subtypes = delta.delta_subtypes
    except Exception:
        delta = None
        trace.delta_type = "unknown"

    # Detect if this is a different-shape task
    same_shape = all(inp.shape == out.shape for inp, out in train_pairs)

    # ---- BUILD LAYER SET ----
    core_layers = [
        ("adaptive_synthesizer", lambda t: _run_adaptive_synthesizer(train_pairs, delta, t, trace)),
        ("adaptive_reasoner", lambda t: _run_adaptive_reasoner(train_pairs, t, trace)),
        ("hypothesis_engine", lambda t: _run_hypothesis_engine(train_pairs, t, trace)),
        ("composable_reasoner", lambda t: _run_composable_reasoner(train_pairs, t, trace, task_id)),
        ("object_correspondence", lambda t: _run_object_correspondence(train_pairs, t, trace, task_id)),
        ("spatial_reasoner", lambda t: _run_spatial_reasoner(train_pairs, t, trace, task_id)),
        ("meta_learner", lambda t: _run_meta_learner(train_pairs, delta, t, trace) if delta else []),
        ("fill_solver", lambda t: _run_fill_solver(train_pairs, t, trace)),
        ("relation_solver", lambda t: _run_relation_solver(train_pairs, t, trace)),
        ("reasoning_v2", lambda t: _run_reasoning_v2(train_pairs, t, trace)),
        ("meta_reasoning", lambda t: _run_meta_reasoning(train_pairs, t, trace, task_id)),
    ]

    extended_layers = [
        ("grid_decomposition", lambda t: _run_grid_decomposition(train_pairs, t, trace)),
        ("inverse_reasoning", lambda t: _run_inverse_reasoning(train_pairs, t, trace)),
    ]

    shape_layers = [
        ("different_shape", lambda t: _run_different_shape(train_pairs, t, trace, task_id)),
        ("output_shape_predictor", lambda t: _run_output_shape_predictor(train_pairs, t, trace)),
    ]

    # Reorder based on insight memory + structural memory (analogical transfer)
    suggested = _insight_memory.suggest_layer_order(
        trace.delta_type or "unknown",
        trace.delta_subtypes or [],
    )

    # Layer 6: Analogical Transfer — boost layers that worked on similar tasks
    try:
        from reasoning_project.cortical_reasoning import (
            compute_task_signature, _structural_memory,
        )
        task_sig = compute_task_signature(train_pairs)
        analogical_hits = _structural_memory.retrieve(task_sig, top_k=3)
        if analogical_hits:
            analog_layers = [layer for layer, _, _ in analogical_hits]
            if suggested:
                for al in reversed(analog_layers):
                    if al not in suggested:
                        suggested.insert(0, al)
            else:
                suggested = analog_layers
    except Exception:
        pass

    all_layers = core_layers + extended_layers
    if not same_shape:
        all_layers = shape_layers + all_layers

    if suggested:
        layer_map = dict(all_layers)
        ordered = []
        seen = set()
        for name in suggested:
            if name in layer_map and name not in seen:
                ordered.append((name, layer_map[name]))
                seen.add(name)
        for name, fn in all_layers:
            if name not in seen:
                ordered.append((name, fn))
                seen.add(name)
        layers = ordered
    else:
        layers = all_layers

    # ---- ITERATION 1: Run all layers, collect candidates ----
    all_candidates: List[Tuple[str, SynthesizedOperator, float]] = []

    for layer_name, layer_fn in layers:
        if time.time() - start > timeout_seconds * 0.7:
            break

        remaining = min(per_layer_timeout, timeout_seconds * 0.7 - (time.time() - start))
        if remaining <= 0:
            break

        ops = layer_fn(remaining)

        for op in ops:
            if test_inputs and test_outputs:
                if _verify_on_test(op, test_inputs, test_outputs):
                    trace.total_verified += 1
                    trace.solving_layer = layer_name
                    trace.solving_family = op.operator_family
                    trace.iteration = 1
                    verified.append(op)
                    _insight_memory.record_success(
                        layer_name, op.operator_family,
                        trace.delta_type or "unknown",
                        trace.delta_subtypes or [],
                        task_id,
                        insight_type=op.operator_family,
                    )
                    return verified, trace
            else:
                if _verify_on_train(op, train_pairs):
                    trace.total_verified += 1
                    trace.solving_layer = layer_name
                    trace.solving_family = op.operator_family
                    trace.iteration = 1
                    verified.append(op)
                    _insight_memory.record_success(
                        layer_name, op.operator_family,
                        trace.delta_type or "unknown",
                        trace.delta_subtypes or [],
                        task_id,
                        insight_type=op.operator_family,
                    )
                    return verified, trace

            # Score partial correctness for later iterations
            if test_inputs and test_outputs:
                score = _score_partial_on_test(op, test_inputs, test_outputs)
            else:
                score = _score_partial(op, train_pairs)
            if score > 0.05:
                all_candidates.append((layer_name, op, score))

    # ---- CORTICAL REASONING (submission mode) ----
    # In submission mode, use brain-inspired mechanisms BEFORE pixel-level
    # corrections. These are designed to generalize without test outputs.
    if not verified and all_candidates and not (test_inputs and test_outputs):
        try:
            from reasoning_project.cortical_reasoning import (
                structural_corrections as _cortical_structural,
                multi_column_vote as _cortical_vote,
                metacognitive_accept as _cortical_metacog,
                feature_binding as _cortical_bind,
                compute_task_signature, _structural_memory,
            )

            all_candidates.sort(key=lambda x: -x[2])

            # --- Layer 2: Structural Hypothesis Corrections (Predictive Coding) ---
            # Try low-parameter structural transforms on top partial candidates
            if time.time() - start < timeout_seconds * 0.85:
                for best_layer, best_op, best_score in all_candidates[:15]:
                    if time.time() - start > timeout_seconds * 0.85:
                        break
                    corr_ops = _cortical_structural(best_op, train_pairs)
                    for corr_op in corr_ops:
                        trace.total_verified += 1
                        trace.solving_layer = f"{best_layer}+structural"
                        trace.solving_family = corr_op.operator_family
                        trace.iteration = 2
                        verified.append(corr_op)
                        _insight_memory.record_success(
                            f"{best_layer}+structural",
                            corr_op.operator_family,
                            trace.delta_type or "unknown",
                            trace.delta_subtypes or [],
                            task_id,
                            insight_type=corr_op.operator_family,
                        )
                        return verified, trace

            # --- Layer 3: Multi-Column Voting (Thousand Brains) ---
            if not verified and time.time() - start < timeout_seconds * 0.88:
                vote_op = _cortical_vote(all_candidates, train_pairs)
                if vote_op is not None:
                    trace.total_verified += 1
                    trace.solving_layer = "cortical_vote"
                    trace.solving_family = vote_op.operator_family
                    trace.iteration = 2
                    verified.append(vote_op)
                    _insight_memory.record_success(
                        "cortical_vote", vote_op.operator_family,
                        trace.delta_type or "unknown",
                        trace.delta_subtypes or [],
                        task_id,
                        insight_type="cortical_column_vote",
                    )
                    return verified, trace

            # --- Layer 5: Feature Binding (Cortical Oscillations) ---
            if not verified and time.time() - start < timeout_seconds * 0.90:
                top_cands = all_candidates[:20]
                bind_op = _cortical_bind(top_cands, train_pairs)
                if bind_op is not None:
                    trace.total_verified += 1
                    trace.solving_layer = "feature_binding"
                    trace.solving_family = bind_op.operator_family
                    trace.iteration = 2
                    verified.append(bind_op)
                    _insight_memory.record_success(
                        "feature_binding", bind_op.operator_family,
                        trace.delta_type or "unknown",
                        trace.delta_subtypes or [],
                        task_id,
                        insight_type="feature_binding",
                    )
                    return verified, trace

            # --- Layer 4: Metacognitive Confidence (Near-Miss Acceptance) ---
            if not verified and time.time() - start < timeout_seconds * 0.92:
                near_miss = _cortical_metacog(all_candidates, train_pairs)
                if near_miss is not None:
                    nm_layer, nm_op = near_miss
                    trace.total_verified += 1
                    trace.solving_layer = f"{nm_layer}+metacognitive"
                    trace.solving_family = nm_op.operator_family
                    trace.iteration = 2
                    verified.append(nm_op)
                    _insight_memory.record_success(
                        f"{nm_layer}+metacognitive",
                        nm_op.operator_family,
                        trace.delta_type or "unknown",
                        trace.delta_subtypes or [],
                        task_id,
                        insight_type=f"metacognitive_{nm_op.operator_family}",
                    )
                    return verified, trace

            # --- Layer 6: Record structural signature for analogical transfer ---
            if verified:
                try:
                    sig = compute_task_signature(train_pairs)
                    _structural_memory.store(
                        sig, trace.solving_layer or "unknown",
                        trace.solving_family or "unknown")
                except Exception:
                    pass

        except Exception:
            pass

    # ---- ITERATIONS 2-4: Diagnose best partials → correct → re-correct ----
    # (Original pixel-level correction engine — fallback after cortical reasoning)
    max_iterations = 4
    use_loo = not (test_inputs and test_outputs)

    for iteration in range(2, max_iterations + 1):
        if verified or not all_candidates:
            break
        if time.time() - start > timeout_seconds * 0.95:
            break

        all_candidates.sort(key=lambda x: -x[2])
        n_try = min(10, len(all_candidates))

        for best_layer, best_op, best_score in all_candidates[:n_try]:
            if time.time() - start > timeout_seconds * 0.95:
                break

            remaining = timeout_seconds - (time.time() - start)
            corr_timeout = min(remaining * 0.3, 8.0)

            if use_loo:
                corrections = _loo_residual_correction(
                    best_op, train_pairs, corr_timeout, trace)
                if not corrections:
                    corrections = _verify_loo_correction(
                        best_op, train_pairs, corr_timeout, trace)
            else:
                corrections = _diagnose_and_correct(
                    best_op, train_pairs, corr_timeout, trace,
                    test_inputs=test_inputs, test_outputs=test_outputs)

            for corr_op in corrections:
                if test_inputs and test_outputs:
                    if _verify_on_test(corr_op, test_inputs, test_outputs):
                        trace.total_verified += 1
                        trace.solving_layer = f"{best_layer}+correction"
                        trace.solving_family = corr_op.operator_family
                        trace.iteration = iteration
                        verified.append(corr_op)
                        _insight_memory.record_success(
                            f"{best_layer}+correction",
                            corr_op.operator_family,
                            trace.delta_type or "unknown",
                            trace.delta_subtypes or [],
                            task_id,
                            insight_type=f"corrected_{best_op.operator_family}",
                        )
                        return verified, trace
                else:
                    # LOO already verified — accept
                    trace.total_verified += 1
                    trace.solving_layer = f"{best_layer}+correction"
                    trace.solving_family = corr_op.operator_family
                    trace.iteration = iteration
                    verified.append(corr_op)
                    _insight_memory.record_success(
                        f"{best_layer}+correction",
                        corr_op.operator_family,
                        trace.delta_type or "unknown",
                        trace.delta_subtypes or [],
                        task_id,
                        insight_type=f"corrected_{best_op.operator_family}",
                    )
                    return verified, trace

                # Partial correction — add to candidates for next iteration
                if test_inputs and test_outputs:
                    cscore = _score_partial_on_test(corr_op, test_inputs, test_outputs)
                else:
                    cscore = _score_partial(corr_op, train_pairs)
                if cscore > best_score + 0.01:
                    all_candidates.append((f"{best_layer}+corr_iter{iteration}", corr_op, cscore))

    return verified, trace


# ===================================================================
# Evaluation harness
# ===================================================================

def evaluate_arc_unified(
    challenges: Dict[str, Any],
    solutions: Dict[str, Any],
    skip_ids: Optional[set] = None,
    timeout_per_task: float = 30.0,
    per_layer_timeout: float = 5.0,
    max_tasks: Optional[int] = None,
    submission_mode: bool = False,
) -> Dict[str, Any]:
    """Evaluate on ARC tasks.

    submission_mode=True:  VALID for ARC-AGI2. Test outputs are NEVER
        passed to the solver. Programs are synthesized and verified on
        training pairs only. Test outputs are used ONLY after prediction
        for offline scoring. This is the honest number.
    submission_mode=False: Oracle/diagnostic mode. Test outputs are
        available during solving for verification and correction.
        Numbers from this mode are upper bounds, not submission-valid.
    """
    if skip_ids is None:
        skip_ids = set()

    solved = []
    total = 0
    layer_stats: Dict[str, int] = Counter()
    family_stats: Dict[str, int] = Counter()
    iteration_stats: Dict[int, int] = Counter()
    start = time.time()

    for task_id in sorted(challenges.keys()):
        if task_id in skip_ids:
            continue
        if max_tasks and total >= max_tasks:
            break

        task = challenges[task_id]
        sol = solutions.get(task_id)
        train_pairs = [(np.array(p["input"]), np.array(p["output"]))
                       for p in task["train"]]
        test_inputs = [np.array(p["input"]) for p in task["test"]]
        # Kaggle: sol may be None — emission proceeds unverified downstream
        test_outputs = None if sol is None else [np.array(s) for s in sol]
        total += 1

        if submission_mode:
            # SUBMISSION MODE: solver NEVER sees test outputs
            ops, trace = reason_unified(
                train_pairs,
                test_inputs=test_inputs,
                test_outputs=None,
                task_id=task_id,
                timeout_seconds=timeout_per_task,
                per_layer_timeout=per_layer_timeout,
            )
            # LOO-gated replacement: if solver returned a high-overfit-risk
            # family with LOO=0, try alternative layers for a better program.
            _is_local_rule = (ops and (
                ops[0].operator_family in ("solver_local_rule", "solver_color_solver")
                or ops[0].operator_family.startswith("meta_solver_local_rule")
                or ops[0].operator_family.startswith("meta_color")
            ))
            if _is_local_rule:
                _lr_op = ops[0]
                _do_replace = False
                if all(inp.shape == out.shape for inp, out in train_pairs):
                    from reasoning_project.local_rules import (
                        synthesize_local_rules as _lr_synth,
                        induce_local_rule as _lr_induce,
                        apply_local_rule as _lr_apply,
                        apply_local_rule_fuzzy as _lr_fuzzy,
                    )
                    _lr_rules = _lr_synth(train_pairs)
                    if _lr_rules:
                        _n = len(train_pairs)
                        _lp = 0
                        for _li in range(_n):
                            _fp = train_pairs[:_li] + train_pairs[_li + 1:]
                            _hi, _ho = train_pairs[_li]
                            _fr = _lr_induce(_fp, _lr_rules[0].strategy_name)
                            if _fr is not None:
                                _pred = _lr_apply(_hi, _fr)
                                if _pred is None:
                                    _pred = _lr_fuzzy(_hi, _fr)
                                if _pred is not None and np.array_equal(_pred, _ho):
                                    _lp += 1
                        if _lp == 0:
                            _do_replace = True

                if _do_replace:
                    _alt_trace = UnifiedTrace(task_id=task_id)
                    try:
                        _delta = compute_task_delta(train_pairs)
                    except Exception:
                        _delta = None
                    _alt_layers = [
                        lambda t: _run_adaptive_reasoner(train_pairs, t, _alt_trace),
                        lambda t: _run_hypothesis_engine(train_pairs, t, _alt_trace),
                        lambda t: _run_composable_reasoner(train_pairs, t, _alt_trace, task_id),
                        lambda t: _run_object_correspondence(train_pairs, t, _alt_trace, task_id),
                        lambda t: _run_fill_solver(train_pairs, t, _alt_trace),
                        lambda t: _run_reasoning_v2(train_pairs, t, _alt_trace),
                        lambda t: _run_meta_reasoning(train_pairs, t, _alt_trace, task_id),
                        lambda t: _run_spatial_reasoner(train_pairs, t, _alt_trace, task_id),
                    ]
                    _alt_candidates = []
                    for _alt_fn in _alt_layers:
                        try:
                            _alt_ops = _alt_fn(per_layer_timeout)
                        except Exception:
                            continue
                        for _aop in _alt_ops:
                            if _verify_on_train(_aop, train_pairs):
                                ops = [_aop]
                                trace.solving_layer = "loo_replace"
                                trace.solving_family = _aop.operator_family
                                break
                            _ascore = _score_partial(_aop, train_pairs)
                            if _ascore > 0.05:
                                _alt_candidates.append(("alt", _aop, _ascore))
                        if ops[0] is not _lr_op:
                            break

                    # Cortical reasoning on collected alternative candidates
                    if ops[0] is _lr_op and _alt_candidates:
                        try:
                            from reasoning_project.cortical_reasoning import (
                                structural_corrections as _cs,
                                multi_column_vote as _cv,
                                feature_binding as _cb,
                            )
                            _alt_candidates.sort(key=lambda x: -x[2])
                            for _, _cop, _ in _alt_candidates[:10]:
                                for _sop in _cs(_cop, train_pairs):
                                    ops = [_sop]
                                    trace.solving_layer = "loo_cortical_structural"
                                    trace.solving_family = _sop.operator_family
                                    break
                                if ops[0] is not _lr_op:
                                    break
                            if ops[0] is _lr_op:
                                _vop = _cv(_alt_candidates, train_pairs)
                                if _vop is not None:
                                    ops = [_vop]
                                    trace.solving_layer = "loo_cortical_vote"
                                    trace.solving_family = _vop.operator_family
                            if ops[0] is _lr_op:
                                _bop = _cb(_alt_candidates, train_pairs)
                                if _bop is not None:
                                    ops = [_bop]
                                    trace.solving_layer = "loo_cortical_bind"
                                    trace.solving_family = _bop.operator_family
                        except Exception:
                            pass

            # Score AFTER: apply best op to test inputs, compare offline
            if ops:
                op = ops[0]
                try:
                    all_correct = True
                    _preds = []
                    _no_gt = (test_outputs is None
                              or any(t is None for t in test_outputs)
                              or len(test_outputs) != len(test_inputs))
                    for i_t, ti in enumerate(test_inputs):
                        pred = op.execute(ti)
                        if pred is None or not isinstance(pred, np.ndarray):
                            all_correct = False
                            break
                        _preds.append(pred.tolist())
                        if _no_gt:
                            continue  # Kaggle: no ground truth — emit, don't verify
                        to = test_outputs[i_t]
                        if pred.shape != to.shape or not np.array_equal(pred, to):
                            all_correct = False
                            break
                    if all_correct and len(_preds) == len(test_inputs):
                        solved.append({
                            "predictions": _preds,
                            "unverified": _no_gt,
                            "task_id": task_id,
                            "layer": trace.solving_layer,
                            "family": trace.solving_family or op.operator_family,
                            "explanation": op.explanation,
                            "delta_type": trace.delta_type,
                            "iteration": trace.iteration,
                        })
                        layer_stats[trace.solving_layer or "unknown"] += 1
                        family_stats[op.operator_family] += 1
                        iteration_stats[trace.iteration] += 1
                except Exception:
                    pass
        else:
            # ORACLE MODE: solver sees test outputs (diagnostic only)
            ops, trace = reason_unified(
                train_pairs,
                test_inputs=test_inputs,
                test_outputs=test_outputs,
                task_id=task_id,
                timeout_seconds=timeout_per_task,
                per_layer_timeout=per_layer_timeout,
            )
            if ops:
                op = ops[0]
                solved.append({
                    "task_id": task_id,
                    "layer": trace.solving_layer,
                    "family": trace.solving_family or op.operator_family,
                    "explanation": op.explanation,
                    "delta_type": trace.delta_type,
                    "iteration": trace.iteration,
                })
                layer_stats[trace.solving_layer] += 1
                family_stats[op.operator_family] += 1
                iteration_stats[trace.iteration] += 1

    elapsed = time.time() - start

    return {
        "total_tested": total,
        "total_solved": len(solved),
        "elapsed_seconds": elapsed,
        "solved": solved,
        "by_layer": dict(layer_stats),
        "by_family": dict(family_stats),
        "by_iteration": dict(iteration_stats),
        "session_memory_strategies": len(_insight_memory.insights),
        "mode": "submission" if submission_mode else "oracle",
    }
