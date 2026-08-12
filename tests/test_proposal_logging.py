"""Tests for ProposalLogger."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from reasoning_project.proposal_logger import ProposalLogger


class TestProposalLogger:
    def test_log_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "proposals.jsonl")
            logger = ProposalLogger(path)
            logger.log_proposal(
                task_id="task_01",
                proposal_idx=0,
                module_source="static_portfolio",
                operator_family="discriminative_filter",
                selector="is_largest",
                confidence=0.95,
                train_consistent=True,
                loo_passed=True,
                proof_obligations_passed=True,
                falsification_passed=True,
                test_output_matches=True,
                accepted=True,
                false_positive=False,
                rejection_reason=None,
                runtime_seconds=1.5,
            )
            assert os.path.exists(path)

    def test_log_writes_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "proposals.jsonl")
            logger = ProposalLogger(path)

            logger.log_proposal(
                task_id="task_01",
                proposal_idx=0,
                module_source="adapter_genesis",
                operator_family="filter",
                selector="is_largest",
                confidence=0.9,
                train_consistent=True,
                loo_passed=True,
                proof_obligations_passed=True,
                falsification_passed=False,
                test_output_matches=False,
                accepted=False,
                false_positive=False,
                rejection_reason="falsification_failed",
                runtime_seconds=2.3,
            )

            logger.log_proposal(
                task_id="task_02",
                proposal_idx=0,
                module_source="memory_retrieval",
                operator_family="containment_extract",
                selector="is_inner",
                confidence=1.0,
                train_consistent=True,
                loo_passed=True,
                proof_obligations_passed=True,
                falsification_passed=True,
                test_output_matches=True,
                accepted=True,
                false_positive=False,
                rejection_reason=None,
                runtime_seconds=0.5,
            )

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 2

            for line in lines:
                record = json.loads(line.strip())
                assert "task_id" in record
                assert "accepted" in record
                assert "timestamp" in record

    def test_read_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "proposals.jsonl")
            logger = ProposalLogger(path)

            logger.log_proposal(
                task_id="task_01", proposal_idx=0,
                module_source="test", operator_family="f",
                selector="s", confidence=0.5,
                train_consistent=True, loo_passed=False,
                proof_obligations_passed=False,
                falsification_passed=False,
                test_output_matches=False,
                accepted=False, false_positive=False,
                rejection_reason="loo_failed",
                runtime_seconds=1.0,
            )

            records = logger.read_all()
            assert len(records) == 1
            assert records[0]["task_id"] == "task_01"
            assert records[0]["rejection_reason"] == "loo_failed"

    def test_read_all_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nonexistent.jsonl")
            logger = ProposalLogger(path)
            records = logger.read_all()
            assert records == []

    def test_append_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "proposals.jsonl")
            logger = ProposalLogger(path)

            for i in range(5):
                logger.log_proposal(
                    task_id=f"task_{i:02d}", proposal_idx=i,
                    module_source="test", operator_family="f",
                    selector="s", confidence=float(i) / 10,
                    train_consistent=True, loo_passed=True,
                    proof_obligations_passed=True,
                    falsification_passed=True,
                    test_output_matches=True,
                    accepted=True, false_positive=False,
                    rejection_reason=None,
                    runtime_seconds=0.1 * i,
                )

            records = logger.read_all()
            assert len(records) == 5
            # Verify ordering
            for i, r in enumerate(records):
                assert r["task_id"] == f"task_{i:02d}"
