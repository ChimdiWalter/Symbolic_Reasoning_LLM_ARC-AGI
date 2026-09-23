"""Failure-driven OperatorGenesis: synthesize operators on lifted views.

Combines ViewProgram lifting with OperatorGenesis synthesis, then projects
results back and submits through the full ProposalVerifier chain.

Flow:
    failure trace
    → candidate ViewPrograms
    → lifted train pairs
    → OperatorGenesis synthesis
    → project output back
    → ProposalVerifier
    → certificate

Every proposal is logged to proposals.jsonl.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.failure_driven_adaptergenesis import (
    classify_failure_signature,
    instantiate_candidate_views,
)
from reasoning_project.operator_genesis import (
    SynthesizedOperator,
    synthesize_operators_from_train,
    _check_train_consistency,
)
from reasoning_project.view_programs import (
    ViewProgram,
    enumerate_view_programs,
)
from reasoning_project.proposal_verifier import ProposalVerifier
from reasoning_project.adaptive_orchestrator import ModuleProposal


def _try_project_back(
    view: ViewProgram,
    op: SynthesizedOperator,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Callable[[np.ndarray], np.ndarray]]:
    """Build an execute callable that lifts, applies op, and projects back."""
    def _execute(grid, _view=view, _op=op):
        lifted = _view.apply(grid)
        transformed = _op.execute(lifted)
        projected = _view.project(transformed, grid)
        return projected

    # Verify on train pairs
    for inp, out in train_pairs:
        try:
            pred = _execute(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return None
            if pred.shape != out.shape:
                return None
            if not np.array_equal(pred, out):
                return None
        except Exception:
            return None

    return _execute


def run_failure_driven_operator_genesis(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    timeout: int = 180,
    max_views: int = 20,
    max_ops_per_view: int = 50,
    proposals_log_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run failure-driven operator genesis on a single task.

    Returns a list of proposal dicts, each with:
        task_id, view_program, operator_family, operator_id,
        explanation, execute, train_consistent, parameters
    """
    t_start = time.time()
    proposals = []

    # Step 1: classify failure signature
    failure_sig = classify_failure_signature(train_pairs)

    # Step 2: get candidate views
    inp0 = train_pairs[0][0]
    candidate_views = instantiate_candidate_views(failure_sig, inp0)

    # Also try identity (direct synthesis without view lifting)
    from reasoning_project.view_programs import IdentityView
    if not any(isinstance(v, IdentityView) for v in candidate_views):
        candidate_views.insert(0, IdentityView())

    # Step 3: for each view, lift and synthesize operators
    views_tried = 0
    for view in candidate_views:
        if time.time() - t_start > timeout:
            break
        if views_tried >= max_views:
            break

        view_name = type(view).__name__

        # Check if view can apply to all inputs
        try:
            if not all(view.can_apply(inp) for inp, _ in train_pairs):
                continue
        except Exception:
            continue

        views_tried += 1

        # Lift train pairs
        try:
            lifted_pairs = view.lift_train_pairs(train_pairs)
            if not lifted_pairs or len(lifted_pairs) != len(train_pairs):
                continue
        except Exception:
            continue

        # Synthesize operators on lifted pairs
        try:
            ops = synthesize_operators_from_train(
                lifted_pairs, view_program=view, max_candidates=max_ops_per_view,
            )
        except Exception:
            continue

        for op in ops:
            if time.time() - t_start > timeout:
                break

            # Try to project back
            execute_fn = _try_project_back(view, op, train_pairs)

            proposal = {
                "task_id": task_id,
                "view_program": view_name,
                "operator_family": op.operator_family,
                "operator_id": op.operator_id,
                "explanation": op.explanation,
                "parameters": op.parameters,
                "train_consistent": execute_fn is not None,
                "execute": execute_fn,
            }
            proposals.append(proposal)

            # Also try direct synthesis (op on unlifted pairs)
            if execute_fn is None and isinstance(view, IdentityView):
                ok, err = _check_train_consistency(op.execute, train_pairs)
                if ok:
                    proposal["train_consistent"] = True
                    proposal["execute"] = op.execute

    # Step 4: also try direct synthesis without any view
    if time.time() - t_start < timeout:
        try:
            direct_ops = synthesize_operators_from_train(
                train_pairs, max_candidates=max_ops_per_view,
            )
            for op in direct_ops:
                ok, err = _check_train_consistency(op.execute, train_pairs)
                if ok:
                    proposal = {
                        "task_id": task_id,
                        "view_program": "direct",
                        "operator_family": op.operator_family,
                        "operator_id": op.operator_id,
                        "explanation": op.explanation,
                        "parameters": op.parameters,
                        "train_consistent": True,
                        "execute": op.execute,
                    }
                    proposals.append(proposal)
        except Exception:
            pass

    # Log proposals
    if proposals_log_path:
        _log_proposals(proposals, proposals_log_path)

    return proposals


def _log_proposals(proposals: List[Dict[str, Any]], path: str) -> None:
    """Append proposals to JSONL log."""
    with open(path, "a") as f:
        for p in proposals:
            record = {
                "task_id": p["task_id"],
                "view_program": p["view_program"],
                "operator_family": p["operator_family"],
                "operator_id": p["operator_id"],
                "explanation": p["explanation"],
                "train_consistent": p["train_consistent"],
                "parameters": _safe_serialize(p["parameters"]),
            }
            f.write(json.dumps(record) + "\n")


def _safe_serialize(obj: Any) -> Any:
    """Make object JSON-serializable."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if callable(obj):
        return "<callable>"
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def submit_proposals_to_verifier(
    proposals: List[Dict[str, Any]],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
    test_outputs: Optional[List[np.ndarray]],
    verifier: ProposalVerifier,
) -> List[Dict[str, Any]]:
    """Submit train-consistent proposals through the full verification chain.

    Returns list of verification results with accepted/rejected status.
    """
    results = []

    for p in proposals:
        if not p.get("train_consistent") or p.get("execute") is None:
            results.append({**p, "submitted": False, "accepted": False, "reason": "not_train_consistent"})
            continue

        mod_prop = ModuleProposal(
            module_name="operator_genesis",
            proposal_type=f"og_{p.get('view_program', 'direct')}",
            operator_family=p.get("operator_family", "unknown"),
            selector=p.get("explanation", ""),
            hypothesis={"execute": p["execute"]},
            confidence=0.5,
            evidence={"parameters": _safe_serialize(p.get("parameters", {}))},
        )

        try:
            outcome = verifier.verify(mod_prop, train_pairs, test_inputs, test_outputs)
            results.append({
                **{k: v for k, v in p.items() if k != "execute"},
                "submitted": True,
                "accepted": outcome.accepted,
                "certificate_path": outcome.certificate_path if outcome.accepted else None,
                "reason": outcome.rejection_reason if not outcome.accepted else "accepted",
                "false_positive": getattr(outcome, "false_positive", False),
            })
        except Exception as e:
            results.append({
                **{k: v for k, v in p.items() if k != "execute"},
                "submitted": True,
                "accepted": False,
                "certificate_path": None,
                "reason": f"error: {e}",
                "false_positive": False,
            })

    return results
