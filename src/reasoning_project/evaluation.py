"""Evaluation metrics for hidden-rule reasoning tasks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from .compression import exact_match
from .schemas import PredictionResult, ReasoningTask, program_signature


def ambiguity_level_from_fit_count(count: float) -> str:
    if count <= 1:
        return "low"
    if count <= 5:
        return "medium"
    return "high"


def verification_budget_level(oracle_probe_budget: float) -> str:
    if oracle_probe_budget <= 0:
        return "none"
    if oracle_probe_budget <= 20:
        return "low"
    if oracle_probe_budget <= 240:
        return "medium"
    return "high"


def _pixel_accuracy(pred: np.ndarray, target: np.ndarray) -> float:
    if pred.shape != target.shape:
        return 0.0
    return float(np.mean(pred == target))


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def evaluate_prediction(task: ReasoningTask, prediction: PredictionResult) -> Dict[str, Any]:
    candidate_diagnostics = prediction.candidate.diagnostics if prediction.candidate is not None else {}

    def diagnostic_number(key: str, default: float = 0.0) -> float:
        value = prediction.diagnostics.get(key, candidate_diagnostics.get(key, default))
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    oracle_probe_budget = diagnostic_number("oracle_probe_budget")
    split_tags = dict(task.metadata.get("split_tags", {}))
    is_compositional = bool(split_tags.get("compositional", False))
    metrics: Dict[str, Any] = {
        "model_name": prediction.model_name,
        "task_id": task.task_id,
        "family": task.family,
        "task_family": task.family,
        "designed_ambiguity_level": str(task.metadata.get("designed_ambiguity_level", "unknown")),
        "distractor_condition": str(task.metadata.get("distractor_condition", "unknown")),
        "compositional_condition": str(
            task.metadata.get(
                "compositional_condition",
                "compositional" if is_compositional else "non_compositional",
            )
        ),
        "is_compositional": float(is_compositional),
        "is_distractor_heavy": float(task.metadata.get("distractor_condition") == "distractor_heavy"),
        "verification_budget_level": verification_budget_level(oracle_probe_budget),
        "compute_match_condition": "compute_matched" if diagnostic_number("budget_match_falsifier") else "not_compute_matched",
        "true_program": program_signature(task.program),
        "predicted_program": None,
        "latent_rule_recovered": 0.0,
        "causal_factor_recovery": 0.0,
        "runtime_seconds": float(prediction.diagnostics.get("runtime_seconds", 0.0)),
        "candidate_program_count": diagnostic_number("candidate_program_count"),
        "candidates_scored": diagnostic_number("candidates_scored"),
        "candidates_falsified": diagnostic_number("candidates_falsified"),
        "oracle_probe_budget": oracle_probe_budget,
        "oracle_probes_used": diagnostic_number("oracle_probes_used"),
        "passive_checks_used": diagnostic_number("passive_checks_used"),
        "falsifier_candidate_limit": diagnostic_number("falsifier_candidate_limit"),
        "fixed_falsifier_budget": diagnostic_number("fixed_falsifier_budget"),
        "budget_match_falsifier": diagnostic_number("budget_match_falsifier"),
        "train_fit_candidate_count": diagnostic_number("train_fit_candidate_count"),
        "empirical_ambiguity_level": str(
            candidate_diagnostics.get(
                "empirical_ambiguity_level",
                ambiguity_level_from_fit_count(diagnostic_number("train_fit_candidate_count")),
            )
        ),
    }

    heldout_exact_scores: List[float] = []
    for split, preds in prediction.predictions.items():
        examples = task.examples.get(split, [])
        exact = []
        pixel = []
        for pred, example in zip(preds, examples):
            exact.append(exact_match(pred, example.output_grid))
            pixel.append(_pixel_accuracy(pred, example.output_grid))
        metrics[f"{split}_pair_accuracy"] = float(np.mean(exact)) if exact else 0.0
        metrics[f"{split}_pixel_accuracy"] = float(np.mean(pixel)) if pixel else 0.0
        metrics[f"{split}_exact_task_accuracy"] = float(all(exact)) if exact else 0.0
        if split in {"val", "test", "ood"} and exact:
            heldout_exact_scores.append(float(all(exact)))
    heldout_behavior_recovered = bool(heldout_exact_scores and all(score == 1.0 for score in heldout_exact_scores))
    metrics["heldout_behavior_recovered"] = float(heldout_behavior_recovered)

    if prediction.candidate is not None:
        pred_sig = program_signature(prediction.candidate.program)
        true_sig = program_signature(task.program)
        metrics["predicted_program"] = pred_sig
        metrics["train_error"] = float(prediction.candidate.train_error)
        metrics["candidate_score"] = float(prediction.candidate.score)
        metrics["latent_rule_recovered"] = float(pred_sig == true_sig)
        metrics["causal_factor_recovery"] = _jaccard(
            [step.name for step in prediction.candidate.program],
            task.metadata.get("causal_variables", []),
        )
        falsifier = prediction.candidate.diagnostics.get("falsifier", {})
        metrics["counterexample_survival_rate"] = float(falsifier.get("counterexample_survival_rate", 1.0))
        is_wrong_rule = pred_sig != true_sig
        fits_training_examples = float(prediction.candidate.train_error) == 0.0
        if falsifier:
            accepted_by_model = bool(falsifier.get("accepted", False))
        else:
            accepted_by_model = fits_training_examples
        is_behaviorally_false = not heldout_behavior_recovered
        metrics["equivalent_or_repairable_rule_selected"] = float(
            is_wrong_rule and fits_training_examples and heldout_behavior_recovered
        )
        metrics["false_rule_selected"] = float(is_wrong_rule and fits_training_examples and is_behaviorally_false)
        metrics["false_rule_accepted"] = float(is_wrong_rule and accepted_by_model and is_behaviorally_false)
        repair = prediction.candidate.diagnostics.get("repair", {})
        metrics["recovery_after_corruption"] = float(bool(repair.get("recovered_original", False)))
        metrics["description_length_proxy"] = float(
            prediction.candidate.diagnostics.get("description_length_proxy", 0.0)
        )
        metrics["nuisance_robustness"] = float(prediction.candidate.diagnostics.get("nuisance_robustness", 0.0))
        metrics["intervention_stability"] = float(
            prediction.candidate.diagnostics.get("intervention_stability", 0.0)
        )
    else:
        metrics.update(
            {
                "train_error": 1.0,
                "candidate_score": 0.0,
                "counterexample_survival_rate": 1.0,
                "equivalent_or_repairable_rule_selected": 0.0,
                "false_rule_selected": 0.0,
                "false_rule_accepted": 0.0,
                "recovery_after_corruption": 0.0,
                "description_length_proxy": 0.0,
                "nuisance_robustness": 0.0,
                "intervention_stability": 0.0,
            }
        )
    return metrics


def aggregate_metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {}
    numeric_keys = sorted(
        key for key, value in rows[0].items() if isinstance(value, (int, float)) and key not in {"seed"}
    )
    by_model: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    by_family: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_model[str(row["model_name"])].append(row)
        by_family[str(row["family"])].append(row)

    def summarize(group: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for key in numeric_keys:
            values = [float(row.get(key, 0.0)) for row in group]
            out[key] = float(np.mean(values)) if values else 0.0
        return out

    return {
        "overall": summarize(rows),
        "by_model": {model: summarize(group) for model, group in sorted(by_model.items())},
        "by_family": {family: summarize(group) for family, group in sorted(by_family.items())},
        "n_rows": len(rows),
    }


def hypothesis_verdicts(summary: Mapping[str, Any]) -> Dict[str, str]:
    by_model = dict(summary.get("by_model", {}))

    def metric(model: str, key: str) -> float:
        return float(by_model.get(model, {}).get(key, 0.0))

    verdicts: Dict[str, str] = {}
    structural = metric("transformation_library", "ood_pair_accuracy") > metric("direct_io_proxy", "ood_pair_accuracy")
    verdicts["H1_structural_transfer"] = "supported_in_this_run" if structural else "not_supported_in_this_run"

    falsifier = metric("proposer_falsifier", "false_rule_accepted") < metric("proposer_only", "false_rule_accepted")
    compute_matched = (
        metric("proposer_falsifier", "budget_match_falsifier") > 0.0
        and metric("proposer_only", "budget_match_falsifier") > 0.0
    )
    if falsifier and compute_matched:
        verdicts["H2_conditional_falsification"] = "candidate_for_stratified_support_in_this_run"
    elif falsifier:
        verdicts["H2_conditional_falsification"] = "promising_but_not_compute_matched"
    else:
        verdicts["H2_conditional_falsification"] = "not_supported_or_inconclusive_in_this_run"

    repair = metric("path_repair", "recovery_after_corruption") > metric("compression_selector", "recovery_after_corruption")
    verdicts["H3_path_repair"] = "supported_in_this_run" if repair else "not_supported_or_inconclusive_in_this_run"

    compression = metric("compression_selector", "latent_rule_recovered") >= metric(
        "transformation_library", "latent_rule_recovered"
    )
    verdicts["H4_causal_compression"] = "weakly_supported_or_tied_in_this_run" if compression else "not_supported_in_this_run"

    integrated = metric("integrated_scientist", "test_pair_accuracy") >= max(
        metric("direct_io_proxy", "test_pair_accuracy"),
        metric("object_centric", "test_pair_accuracy"),
        metric("transformation_library", "test_pair_accuracy"),
    )
    verdicts["H5_integrated_scientist"] = "weakly_supported_or_tied_in_this_run" if integrated else "not_supported_in_this_run"
    return verdicts
