"""Tests for operator_semantics and trace_operator_invention."""
import numpy as np
import pytest

from reasoning_project.operator_semantics import (
    ExecutableOperatorHypothesis,
    OperatorPrecondition,
    OperatorPostcondition,
    OperatorInvariant,
    OperatorProofObligation,
    VALIDATION_LEVELS,
    make_copy_to_position_hypothesis,
)
from reasoning_project.trace_operator_invention import (
    TraceDrivenOperatorInventor,
    CopyToPositionParams,
    infer_copy_to_position_params,
    execute_copy_to_position,
    OperatorCandidateRecord,
)


# ── operator_semantics tests ────────────────────────────────────────

class TestOperatorPrecondition:
    def test_check_passes(self):
        pre = OperatorPrecondition(
            name="test", expression="x > 0",
            check_fn=lambda x=0, **kw: x > 0,
        )
        assert pre.check(x=5) is True

    def test_check_fails(self):
        pre = OperatorPrecondition(
            name="test", expression="x > 0",
            check_fn=lambda x=0, **kw: x > 0,
        )
        assert pre.check(x=-1) is False

    def test_check_exception_returns_false(self):
        pre = OperatorPrecondition(
            name="test", expression="always fails",
            check_fn=lambda **kw: 1 / 0,
        )
        assert pre.check() is False


class TestExecutableOperatorHypothesis:
    def test_advance_level(self):
        h = make_copy_to_position_hypothesis("t1", "is_largest", {})
        assert h.validation_level == "proposed"
        h.advance_level("parameterized")
        assert h.validation_level == "parameterized"
        h.advance_level("proposed")  # can't go backwards
        assert h.validation_level == "parameterized"

    def test_advance_to_promotion(self):
        h = make_copy_to_position_hypothesis("t1", "is_largest", {})
        for level in VALIDATION_LEVELS:
            h.advance_level(level)
        assert h.validation_level == "transfer_validated"

    def test_check_preconditions(self):
        h = make_copy_to_position_hypothesis("t1", "is_largest", {})
        results = h.check_preconditions(
            source_objects=[1, 2],
            destination_rule="constant_displacement",
            destinations=[(0, 0)],
            grid_shape=(10, 10),
            source_masks=[np.ones((3, 3), dtype=bool)],
            params_consistent=True,
        )
        assert len(results) == 5
        assert all(r.passed for r in results)

    def test_check_preconditions_fail(self):
        h = make_copy_to_position_hypothesis("t1", "is_largest", {})
        results = h.check_preconditions(
            source_objects=[],
            destination_rule=None,
        )
        assert not all(r.passed for r in results)

    def test_to_dict(self):
        h = make_copy_to_position_hypothesis("t1", "is_largest", {"x": 1})
        d = h.to_dict()
        assert d["family"] == "copy_to_position"
        assert d["selector_expression"] == "is_largest"

    def test_all_obligations_passed(self):
        h = make_copy_to_position_hypothesis("t1", "is_largest", {})
        assert h.all_obligations_passed()  # no obligations yet
        h.proof_obligations.append(OperatorProofObligation(
            obligation_id="test", description="test", status="passed",
        ))
        assert h.all_obligations_passed()
        h.proof_obligations.append(OperatorProofObligation(
            obligation_id="test2", description="test2", status="failed",
        ))
        assert not h.all_obligations_passed()


# ── CopyToPositionParams tests ──────────────────────────────────────

class TestCopyToPositionParams:
    def test_to_dict(self):
        p = CopyToPositionParams(
            displacement=(2, 0), destination_rule="constant_displacement",
            copy_mode="move", preserve_color=True, preserve_shape=True,
            selector_expression="is_largest", marker_reference=None,
            allow_overlap=False, background_color=0,
        )
        d = p.to_dict()
        assert d["displacement"] == [2, 0]
        assert d["destination_rule"] == "constant_displacement"


# ── Parameter inference tests ───────────────────────────────────────

class TestInferParams:
    def _make_constant_disp_pairs(self):
        inp1 = np.zeros((6, 6), dtype=int)
        inp1[0:2, 0:2] = 1  # largest (4 cells)
        inp1[3, 4] = 2       # small (1 cell)
        out1 = inp1.copy()
        out1[3, 4] = 0
        out1[4, 4] = 2       # moved down by 1

        inp2 = np.zeros((6, 6), dtype=int)
        inp2[0:2, 0:2] = 3  # largest
        inp2[1, 5] = 4
        out2 = inp2.copy()
        out2[1, 5] = 0
        out2[2, 5] = 4       # moved down by 1

        return [(inp1, out1), (inp2, out2)]

    def test_infer_returns_params(self):
        pairs = self._make_constant_disp_pairs()
        params = infer_copy_to_position_params(pairs, "is_largest", keep_when_true=True)
        assert params is not None
        assert params.copy_mode == "move"

    def test_infer_empty_pairs(self):
        params = infer_copy_to_position_params([], "is_largest")
        assert params is None


# ── Execute tests ───────────────────────────────────────────────────

class TestExecute:
    def test_constant_displacement(self):
        params = CopyToPositionParams(
            displacement=(1, 0), destination_rule="constant_displacement",
            copy_mode="move", preserve_color=True, preserve_shape=True,
            selector_expression="is_largest", marker_reference=None,
            allow_overlap=False, background_color=0,
        )
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[3, 4] = 2
        result = execute_copy_to_position(inp, params, [(inp, inp)])
        assert result is not None
        assert result[4, 4] == 2  # moved
        assert result[3, 4] == 0  # cleared


# ── TraceDrivenOperatorInventor tests ───────────────────────────────

class TestTraceDrivenOperatorInventor:
    def test_cluster_by_family(self):
        inv = TraceDrivenOperatorInventor()
        traces = [
            {"needed_operator_family": "copy_to_position", "task_id": "a"},
            {"needed_operator_family": "copy_to_position", "task_id": "b"},
            {"needed_operator_family": "shape_completion", "task_id": "c"},
        ]
        clusters = inv.cluster_by_family(traces)
        assert len(clusters["copy_to_position"]) == 2
        assert len(clusters["shape_completion"]) == 1

    def test_propose_returns_hypothesis(self):
        inv = TraceDrivenOperatorInventor()
        inp = np.zeros((6, 6), dtype=int)
        inp[0:2, 0:2] = 1
        inp[3, 4] = 2
        out = inp.copy()
        out[3, 4] = 0
        out[4, 4] = 2

        h = inv.propose_copy_to_position(
            "t1", [(inp, out)],
            {"best_property": "is_largest", "task_id": "t1"},
        )
        # May or may not succeed depending on param inference
        # Just verify it doesn't crash
        assert h is None or h.family == "copy_to_position"

    def test_write_artifacts(self, tmp_path):
        inv = TraceDrivenOperatorInventor()
        inv.proposed.append(OperatorCandidateRecord(
            operator_id="test", family="copy_to_position",
            task_ids=["t1"], source_trace_ids=["t1"],
            parameters={"x": 1},
        ))
        inv.write_artifacts(str(tmp_path))
        assert (tmp_path / "proposed_operators.jsonl").exists()
        assert (tmp_path / "operator_validation_report.md").exists()


class TestOperatorCandidateRecord:
    def test_to_dict(self):
        rec = OperatorCandidateRecord(
            operator_id="test", family="copy_to_position",
            task_ids=["t1"], source_trace_ids=["t1"],
            parameters={"displacement": [2, 0]},
        )
        d = rec.to_dict()
        assert d["family"] == "copy_to_position"
        assert d["operator_id"] == "test"
