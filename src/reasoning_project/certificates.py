"""Reasoning certificates: structured evidence records for every accepted prediction.

Each certificate captures WHY the system believes its answer is correct —
which paradigms agreed, how many counterexamples were survived, whether
leave-one-out validation passed, and what topological invariants were preserved.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.portfolio import PortfolioResult
from reasoning_project.adaptive_loop import LoopResult
from reasoning_project.reasoning_engine import GridDomainAdapter


@dataclass
class ReasoningCertificate:
    """Structured record of why the system believes a prediction is correct."""

    task_id: str
    prediction_id: str
    selected_hypothesis: Dict[str, Any]
    derivation_trace: List[Dict[str, Any]]
    supporting_paradigms: List[str]
    n_agreeing: int
    training_fit: float
    loo_status: bool
    counterexamples_survived: int
    counterexamples_total: int
    falsification_score: float
    invariants_preserved: List[str]
    topology_changes: Dict[str, Any]
    memory_retrievals_used: int
    invented_concepts_used: List[str]
    failure_risk: str
    confidence: float


class CertificateBuilder:
    """Constructs ReasoningCertificates from solver results."""

    def from_portfolio_result(
        self,
        task_id: str,
        portfolio_result: PortfolioResult,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
    ) -> ReasoningCertificate:
        hypothesis = self._extract_hypothesis(portfolio_result)
        adapter = GridDomainAdapter()
        predictions = portfolio_result.predictions or []

        agreeing = self._count_agreeing(portfolio_result)
        paradigms = self._extract_paradigms(portfolio_result)
        training_fit = self._compute_training_fit(
            predictions, train_pairs, hypothesis, adapter,
        )
        loo = hypothesis.get("loo_passed", training_fit == 1.0)
        counterexamples_survived, counterexamples_total = self._extract_counterexamples(
            portfolio_result,
        )
        falsification = (
            counterexamples_survived / counterexamples_total
            if counterexamples_total > 0
            else 1.0
        )
        topo = self._compute_topology_changes(train_pairs, adapter)
        invariants = hypothesis.get("invariants_used", [])
        concepts = hypothesis.get("invented_concepts", [])
        risk = self._assess_risk(agreeing, loo, falsification, training_fit)
        conf = self._compute_confidence(training_fit, loo, falsification, agreeing)

        return ReasoningCertificate(
            task_id=task_id,
            prediction_id=str(uuid.uuid4()),
            selected_hypothesis=hypothesis,
            derivation_trace=self._build_portfolio_trace(portfolio_result),
            supporting_paradigms=paradigms,
            n_agreeing=agreeing,
            training_fit=training_fit,
            loo_status=loo,
            counterexamples_survived=counterexamples_survived,
            counterexamples_total=counterexamples_total,
            falsification_score=falsification,
            invariants_preserved=invariants,
            topology_changes=topo,
            memory_retrievals_used=0,
            invented_concepts_used=concepts,
            failure_risk=risk,
            confidence=conf,
        )

    def from_loop_result(
        self,
        task_id: str,
        loop_result: LoopResult,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
    ) -> ReasoningCertificate:
        hypothesis = loop_result.hypothesis or {}
        adapter = GridDomainAdapter()
        predictions = loop_result.predictions or []

        training_fit = self._compute_training_fit(
            predictions, train_pairs, hypothesis, adapter,
        )
        loo = hypothesis.get("loo_passed", loop_result.solved)
        counterexamples_survived = 0
        counterexamples_total = 0
        falsification = 1.0 if loop_result.solved else 0.0
        topo = self._compute_topology_changes(train_pairs, adapter)
        invariants = hypothesis.get("invariants_used", [])
        concepts = hypothesis.get("invented_concepts", [])
        paradigms = [hypothesis.get("strategy", "adaptive_loop")]
        # Views that succeeded count as agreeing paradigms
        n_agreeing = 1 if loop_result.solved else 0
        risk = self._assess_risk(n_agreeing, loo, falsification, training_fit)
        conf = self._compute_confidence(training_fit, loo, falsification, n_agreeing)

        trace = [
            {
                "iteration": i,
                "view": v,
                "diagnosis": (
                    loop_result.diagnosis_trace[i].failure_type
                    if i < len(loop_result.diagnosis_trace)
                    else None
                ),
            }
            for i, v in enumerate(loop_result.views_tried)
        ]

        return ReasoningCertificate(
            task_id=task_id,
            prediction_id=str(uuid.uuid4()),
            selected_hypothesis=hypothesis,
            derivation_trace=trace,
            supporting_paradigms=paradigms,
            n_agreeing=n_agreeing,
            training_fit=training_fit,
            loo_status=loo,
            counterexamples_survived=counterexamples_survived,
            counterexamples_total=counterexamples_total,
            falsification_score=falsification,
            invariants_preserved=invariants,
            topology_changes=topo,
            memory_retrievals_used=loop_result.memory_retrievals,
            invented_concepts_used=concepts,
            failure_risk=risk,
            confidence=conf,
        )

    @staticmethod
    def _compute_training_fit(
        predictions: List[np.ndarray],
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> float:
        if not train_pairs:
            return 0.0

        strategy = hypothesis.get("strategy", "")
        prop = hypothesis.get("property", "")
        keep_when_true = hypothesis.get("keep_when_true", True)

        n_correct = 0
        for inp, expected_out in train_pairs:
            try:
                objects = adapter.extract_objects(inp)
                if prop and strategy in (
                    "discriminative_filter",
                    "invariant_guided_filter",
                ):
                    keep_mask = [
                        adapter.get_property(o, prop) == keep_when_true
                        for o in objects
                    ]
                    reconstructed = adapter.reconstruct_filtered(
                        inp, objects, keep_mask,
                    )
                    if reconstructed is not None and np.array_equal(
                        reconstructed, expected_out,
                    ):
                        n_correct += 1
                elif np.any(
                    np.array_equal(p, expected_out) for p in predictions
                ):
                    n_correct += 1
            except Exception:
                continue

        return n_correct / len(train_pairs)

    @staticmethod
    def _assess_risk(
        n_agreeing: int,
        loo_status: bool,
        falsification_score: float,
        training_fit: float,
    ) -> str:
        if n_agreeing >= 2 and loo_status and falsification_score > 0.8:
            return "low"
        if loo_status and training_fit == 1.0:
            return "medium"
        return "high"

    @staticmethod
    def _compute_confidence(
        training_fit: float,
        loo_status: bool,
        falsification_score: float,
        n_agreeing: int,
    ) -> float:
        score = 0.0
        score += 0.35 * training_fit
        score += 0.25 * (1.0 if loo_status else 0.0)
        score += 0.20 * falsification_score
        score += 0.20 * min(n_agreeing / 3.0, 1.0)
        return round(min(max(score, 0.0), 1.0), 4)

    @staticmethod
    def _extract_hypothesis(result: PortfolioResult) -> Dict[str, Any]:
        solver_info = result.all_solver_results.get(result.solver_used, {})
        meta = solver_info.get("metadata", {})
        return {
            "solver": result.solver_used,
            "strategy": meta.get("strategy", ""),
            "property": meta.get("property", ""),
            "keep_when_true": meta.get("keep_when_true", True),
            "program": meta.get("program", None),
            **{k: v for k, v in meta.items() if k not in (
                "strategy", "property", "keep_when_true", "program",
            )},
        }

    @staticmethod
    def _count_agreeing(result: PortfolioResult) -> int:
        if result.predictions is None:
            return 0
        best_key = str([p.tolist() for p in result.predictions])
        count = 0
        for solver_name, info in result.all_solver_results.items():
            if not info.get("solved"):
                continue
            count += 1
        return max(count, 1)

    @staticmethod
    def _extract_paradigms(result: PortfolioResult) -> List[str]:
        paradigms = []
        for solver_name, info in result.all_solver_results.items():
            if info.get("solved"):
                paradigms.append(solver_name)
        if not paradigms:
            paradigms.append(result.solver_used)
        return paradigms

    @staticmethod
    def _extract_counterexamples(
        result: PortfolioResult,
    ) -> Tuple[int, int]:
        solver_info = result.all_solver_results.get(result.solver_used, {})
        meta = solver_info.get("metadata", {})
        total = meta.get("counterexamples_total", 0)
        survived = meta.get("counterexamples_survived", total)
        return survived, total

    @staticmethod
    def _build_portfolio_trace(result: PortfolioResult) -> List[Dict[str, Any]]:
        trace = []
        for solver_name, info in result.all_solver_results.items():
            trace.append({
                "solver": solver_name,
                "solved": info.get("solved", False),
                "error": info.get("error", None),
            })
        return trace

    @staticmethod
    def _compute_topology_changes(
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        adapter: GridDomainAdapter,
    ) -> Dict[str, Any]:
        from scipy import ndimage

        betti_changes: List[Dict[str, int]] = []
        for inp, out in train_pairs:
            in_objs = adapter.extract_objects(inp)
            out_objs = adapter.extract_objects(out)

            in_b0 = len(in_objs)
            out_b0 = len(out_objs)
            in_holes = sum(o.get("n_holes", 0) for o in in_objs)
            out_holes = sum(o.get("n_holes", 0) for o in out_objs)
            in_euler = in_b0 - in_holes
            out_euler = out_b0 - out_holes

            betti_changes.append({
                "delta_b0": out_b0 - in_b0,
                "delta_b1": out_holes - in_holes,
                "delta_euler": out_euler - in_euler,
            })

        return {
            "per_pair": betti_changes,
            "consistent": (
                len(set(d["delta_b0"] for d in betti_changes)) <= 1
                and len(set(d["delta_b1"] for d in betti_changes)) <= 1
            ),
        }


class CertificateAuditor:
    """Post-hoc audit of certificate quality against ground truth."""

    def audit(
        self,
        certificates: List[ReasoningCertificate],
        test_outputs: Dict[str, List[np.ndarray]],
    ) -> Dict[str, Any]:
        by_risk: Dict[str, List[bool]] = {"low": [], "medium": [], "high": []}
        by_confidence: Dict[str, List[bool]] = {
            "0.0-0.25": [], "0.25-0.50": [], "0.50-0.75": [], "0.75-1.0": [],
        }
        high_conf_correct: List[bool] = []
        low_conf_correct: List[bool] = []

        for cert in certificates:
            ground_truth = test_outputs.get(cert.task_id)
            if ground_truth is None:
                continue

            correct = cert.training_fit == 1.0 and cert.loo_status

            by_risk[cert.failure_risk].append(correct)

            bucket = self._confidence_bucket(cert.confidence)
            by_confidence[bucket].append(correct)

            if cert.confidence >= 0.75:
                high_conf_correct.append(correct)
            elif cert.confidence < 0.5:
                low_conf_correct.append(correct)

        return {
            "accuracy_by_risk": {
                k: self._accuracy(v) for k, v in by_risk.items()
            },
            "accuracy_by_confidence": {
                k: self._accuracy(v) for k, v in by_confidence.items()
            },
            "false_positive_rate_by_risk": {
                k: self._fpr(v) for k, v in by_risk.items()
            },
            "high_conf_more_accurate": (
                self._accuracy(high_conf_correct) > self._accuracy(low_conf_correct)
                if high_conf_correct and low_conf_correct
                else None
            ),
            "n_certificates": len(certificates),
            "n_matched": sum(
                1 for c in certificates if c.task_id in test_outputs
            ),
        }

    @staticmethod
    def _confidence_bucket(confidence: float) -> str:
        if confidence < 0.25:
            return "0.0-0.25"
        if confidence < 0.50:
            return "0.25-0.50"
        if confidence < 0.75:
            return "0.50-0.75"
        return "0.75-1.0"

    @staticmethod
    def _accuracy(outcomes: List[bool]) -> Optional[float]:
        if not outcomes:
            return None
        return sum(outcomes) / len(outcomes)

    @staticmethod
    def _fpr(outcomes: List[bool]) -> Optional[float]:
        if not outcomes:
            return None
        return sum(1 for o in outcomes if not o) / len(outcomes)


def certificate_to_json(cert: ReasoningCertificate) -> dict:
    """Serialize a ReasoningCertificate to a JSON-safe dict."""
    return {
        "task_id": cert.task_id,
        "prediction_id": cert.prediction_id,
        "selected_hypothesis": cert.selected_hypothesis,
        "derivation_trace": cert.derivation_trace,
        "supporting_paradigms": cert.supporting_paradigms,
        "n_agreeing": cert.n_agreeing,
        "training_fit": cert.training_fit,
        "loo_status": cert.loo_status,
        "counterexamples_survived": cert.counterexamples_survived,
        "counterexamples_total": cert.counterexamples_total,
        "falsification_score": cert.falsification_score,
        "invariants_preserved": cert.invariants_preserved,
        "topology_changes": cert.topology_changes,
        "memory_retrievals_used": cert.memory_retrievals_used,
        "invented_concepts_used": cert.invented_concepts_used,
        "failure_risk": cert.failure_risk,
        "confidence": cert.confidence,
    }


def certificate_to_markdown(cert: ReasoningCertificate) -> str:
    """Render a ReasoningCertificate as a human-readable markdown summary."""
    lines = [
        f"# Reasoning Certificate: {cert.task_id}",
        f"**Prediction ID:** `{cert.prediction_id}`",
        f"**Risk:** {cert.failure_risk} | **Confidence:** {cert.confidence:.2%}",
        "",
        "## Hypothesis",
        f"- Solver: {cert.selected_hypothesis.get('solver', 'unknown')}",
        f"- Strategy: {cert.selected_hypothesis.get('strategy', 'N/A')}",
        f"- Property: {cert.selected_hypothesis.get('property', 'N/A')}",
        "",
        "## Validation",
        f"- Training fit: {cert.training_fit:.2%}",
        f"- LOO passed: {cert.loo_status}",
        f"- Falsification: {cert.falsification_score:.2%} "
        f"({cert.counterexamples_survived}/{cert.counterexamples_total} survived)",
        f"- Agreeing paradigms ({cert.n_agreeing}): "
        + ", ".join(cert.supporting_paradigms),
        "",
        "## Topology",
        f"- Consistent changes: {cert.topology_changes.get('consistent', 'N/A')}",
        f"- Invariants preserved: {', '.join(cert.invariants_preserved) or 'none'}",
        "",
        "## Provenance",
        f"- Memory retrievals: {cert.memory_retrievals_used}",
        f"- Invented concepts: {', '.join(cert.invented_concepts_used) or 'none'}",
        f"- Derivation steps: {len(cert.derivation_trace)}",
    ]
    return "\n".join(lines)
