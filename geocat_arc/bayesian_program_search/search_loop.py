"""Main Bayesian search loop over candidate programs.

``bayesian_search_v2`` is the Stage-2 rewrite (STAGE2_REQUIREMENTS Section
1): the same control flow — featurize -> rank by acquisition -> evaluate ->
update posterior — with the candidate source, featurizer, and objective
INJECTED, so the object-reasoning inducer can drive it without any coupling
to the old categorical DSL.  The legacy ``bayesian_search`` below is kept
for the old pipeline (candidate_generator-based) unchanged.
"""
from __future__ import annotations
import numpy as np
from geocat_arc.perception.grid import Grid
from geocat_arc.categorical_dsl.rule_schema import RuleSchema
from .bayes_ranker import BayesianLinearRanker
from .program_features import extract_features, feature_dim
from .real_objective import evaluate_program, exact_match
from .candidate_generator import generate_candidates
from .search_trace import SearchTrace, SearchRecord
from .acquisition import ucb


def bayesian_search_v2(candidates: list, feature_fn, evaluate_fn,
                       kappa: float = 2.0, alpha: float = 1.0,
                       beta: float = 1.0) -> list[tuple]:
    """UCB-ordered evaluation of an explicit candidate list.

    Args:
        candidates: anything; order is the deterministic tie-break.
        feature_fn: candidate -> 1-D feature vector (fixed dim across calls).
        evaluate_fn: candidate -> (outcome, realized_score float).  Raising
            stops the loop (budget exhaustion propagates to the caller);
            evaluated results so far are NOT lost — they are returned via
            the ``sink`` list the caller may pass as evaluate_fn closure
            state, and this function also attaches them to the exception as
            ``exc.partial_results`` when possible.

    Returns list of (candidate, outcome, realized_score) in evaluation
    order.  Deterministic: the ranker posterior starts from the same prior
    every call, UCB ties break by candidate index (stable argmax), and no
    randomness is used anywhere.
    """
    feats = [np.asarray(feature_fn(c), dtype=np.float64) for c in candidates]
    if not feats:
        return []
    ranker = BayesianLinearRanker(feature_dim=len(feats[0]),
                                  alpha=alpha, beta=beta)
    remaining = list(range(len(candidates)))
    results: list[tuple] = []
    while remaining:
        best_i, best_acq = remaining[0], None
        for i in remaining:
            mean, var = ranker.predict(feats[i])
            acq = ucb(mean, var, kappa=kappa)
            if best_acq is None or acq > best_acq:
                best_i, best_acq = i, acq
        remaining.remove(best_i)
        try:
            outcome, score = evaluate_fn(candidates[best_i])
        except BaseException as exc:
            try:
                exc.partial_results = results  # type: ignore[attr-defined]
            except Exception:
                pass
            raise
        ranker.update(feats[best_i], float(score))
        results.append((candidates[best_i], outcome, float(score)))
    return results


def bayesian_search(
    task,
    max_iterations: int = 50,
    kappa: float = 2.0,
    max_depth: int = 2,
    consistency_weight: float = 0.2,
) -> tuple:
    first_input = task.train[0].input
    grid_h = len(first_input)
    grid_w = len(first_input[0]) if first_input else 0
    bg = Grid.from_list(first_input).background_color

    candidates = generate_candidates(
        grid_h, grid_w, background=bg,
        max_candidates=max_iterations * 3,
        max_depth=max_depth,
    )

    ranker = BayesianLinearRanker(feature_dim=feature_dim(), alpha=1.0, beta=1.0)
    trace = SearchTrace()

    best_program = None
    best_score = -1.0

    features_list = [extract_features(p) for p in candidates]
    evaluated = set()

    for iteration in range(min(max_iterations, len(candidates))):
        ranking = ranker.rank_candidates(features_list, kappa=kappa)

        selected_idx = None
        for idx in ranking:
            if idx not in evaluated:
                selected_idx = idx
                break
        if selected_idx is None:
            break

        evaluated.add(selected_idx)
        program = candidates[selected_idx]
        features = features_list[selected_idx]

        raw_score = evaluate_program(program, task)

        schema = RuleSchema(global_template=program)
        consistency_metrics = schema.score_cross_example(task)
        consistency = consistency_metrics["cross_example_rule_consistency"]
        adjusted = raw_score * (1.0 - consistency_weight) + raw_score * consistency * consistency_weight

        mean, var = ranker.predict(features)
        acq = ucb(mean, var, kappa=kappa)

        is_exact = adjusted >= 1.95

        trace.add(SearchRecord(
            task_id=task.task_id,
            iteration=iteration,
            candidate_program=repr(program),
            posterior_mean=float(mean),
            posterior_uncertainty=float(np.sqrt(var)),
            acquisition_score=float(acq),
            real_score=float(adjusted),
            exact_match=bool(is_exact),
        ))

        ranker.update(features, adjusted)

        if adjusted > best_score:
            best_score = adjusted
            best_program = program

        if is_exact:
            break

    return best_program, best_score, trace
