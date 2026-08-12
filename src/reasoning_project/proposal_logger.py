"""Append-only proposal-level logging for evaluation and diagnostics.

Every proposal submitted to the verifier is logged as one JSONL line.
This logger is purely observational -- it does not change any verification
decisions. It records what was proposed, whether it passed each stage,
and why it was accepted or rejected.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


class ProposalLogger:
    """Append-only JSONL logger for proposal-level events."""

    def __init__(self, log_path: str):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else ".", exist_ok=True)

    def log_proposal(
        self,
        task_id: str,
        proposal_idx: int,
        module_source: str,
        operator_family: Optional[str],
        selector: Optional[str],
        confidence: float,
        train_consistent: bool,
        loo_passed: bool,
        proof_obligations_passed: bool,
        falsification_passed: bool,
        test_output_matches: bool,
        accepted: bool,
        false_positive: bool,
        rejection_reason: Optional[str],
        runtime_seconds: float,
    ) -> None:
        """Append one JSONL line per proposal.

        This is purely observational -- does not modify verification decisions.
        """
        record = {
            "timestamp": time.time(),
            "task_id": task_id,
            "proposal_idx": proposal_idx,
            "module_source": module_source,
            "operator_family": operator_family,
            "selector": selector,
            "confidence": confidence,
            "train_consistent": train_consistent,
            "loo_passed": loo_passed,
            "proof_obligations_passed": proof_obligations_passed,
            "falsification_passed": falsification_passed,
            "test_output_matches": test_output_matches,
            "accepted": accepted,
            "false_positive": false_positive,
            "rejection_reason": rejection_reason,
            "runtime_seconds": runtime_seconds,
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def read_all(self) -> list:
        """Read all logged proposals."""
        if not os.path.exists(self.log_path):
            return []
        records = []
        with open(self.log_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
