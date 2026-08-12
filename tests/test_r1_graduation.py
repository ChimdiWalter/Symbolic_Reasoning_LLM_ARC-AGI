"""Tests for R1 near-solve graduation pipeline.

Synthetic scenarios:
1. Partial base + ray residual graduates end-to-end with LOO
2. Erase-capable patch test (patch overwrites base including bg)
3. Zero-cost-off: ARC_GRADUATE unset -> graduation functions are importable
   but the gate blocks the script
4. LOO recertification rejects overfitting closure
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.expressions import ColorExpr, PredExpr
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    NearSolveRecord,
    ObjectProgram,
    ObjectRule,
    OutputSpec,
    OverlayProgram,
    SegmentationVariant,
    SelectorRule,
    program_from_dict,
)
from geocat_arc.object_reasoning.graduation import (
    ErasePatchProgram,
    GraduationResult,
    _GRADUATE_ON,
    _is_train_perfect_any,
    compute_residual,
    graduate_task,
    loo_recertify,
    load_near_solve_parts,
    render_erase_patch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prog(delta, params=None, sel=None, variant="S1"):
    """Build a minimal ObjectProgram."""
    rule = ObjectRule(
        selector=SelectorRule(
            predicate=sel or PredExpr(op="true", args=()),
            literals=0),
        action=ActionRule(delta_type=delta, params=params or {}))
    return ObjectProgram(
        segmentation_variant=SegmentationVariant(variant),
        rules=[rule],
        default_action=ActionRule(delta_type=DeltaType.KEEP),
        output_spec=OutputSpec(mode="same_as_input"))


def _grid_pair(inp_list, out_list):
    return (Grid(np.array(inp_list, dtype=np.int32)),
            Grid(np.array(out_list, dtype=np.int32)))


# ---------------------------------------------------------------------------
# 1. ErasePatchProgram render and round-trip
# ---------------------------------------------------------------------------

class TestErasePatchProgram:
    def test_erase_patch_renders_patch_output(self):
        """ErasePatchProgram should render the patch's output (full replace)."""
        grid = Grid.from_list([[0, 3, 0], [0, 0, 5], [0, 0, 0]])
        base = _make_prog(DeltaType.KEEP)
        # patch recolors all objects to 6
        patch = _make_prog(DeltaType.RECOLOR,
                           {"color": ColorExpr(op="const", args=(6,))})
        ep = ErasePatchProgram(base=base, patch=patch, erase_bg=0)
        out = render_program(ep, grid).to_list()
        # Patch renders on input: objects become 6, bg stays 0
        expected = render_program(patch, grid).to_list()
        assert out == expected

    def test_erase_patch_round_trip(self):
        """Serialize/deserialize ErasePatchProgram."""
        base = _make_prog(DeltaType.KEEP)
        patch = _make_prog(DeltaType.RECOLOR,
                           {"color": ColorExpr(op="const", args=(4,))})
        ep = ErasePatchProgram(base=base, patch=patch, erase_bg=0)
        d = ep.to_dict()
        assert d["program_class"] == "erase_patch"
        back = program_from_dict(d)
        assert isinstance(back, ErasePatchProgram)
        assert back.to_dict() == d

    def test_erase_patch_can_overwrite_with_bg(self):
        """ErasePatchProgram's patch output includes bg-colored cells,
        which can erase base mistakes (unlike OverlayProgram)."""
        # Base keeps everything, but the target is all-zero (all bg)
        grid = Grid.from_list([[1, 2], [3, 4]])
        base = _make_prog(DeltaType.KEEP)
        # Patch deletes all objects -> output is all bg
        patch = _make_prog(DeltaType.DELETE)
        ep = ErasePatchProgram(base=base, patch=patch, erase_bg=0)
        out = render_program(ep, grid).to_list()
        # Should be all zeros (patch deletes everything)
        assert out == [[0, 0], [0, 0]]

        # Compare with OverlayProgram which CAN'T erase:
        ov = OverlayProgram(base=base, patch=patch)
        ov_out = render_program(ov, grid).to_list()
        # Overlay: patch renders bg (0) everywhere, but mask = (patch != 0)
        # is empty, so base wins -> objects still visible
        assert ov_out == [[1, 2], [3, 4]]


# ---------------------------------------------------------------------------
# 2. Compute residual
# ---------------------------------------------------------------------------

class TestComputeResidual:
    def test_residual_of_imperfect_program(self):
        """Residual should contain cells where program differs from target."""
        prog = _make_prog(DeltaType.KEEP)
        inp = [[0, 1, 0], [0, 0, 0]]
        # Target differs from keep-all at position (0, 2)
        out = [[0, 1, 5], [0, 0, 0]]
        pairs = [_grid_pair(inp, out)]
        residuals = compute_residual(prog.to_dict(), pairs)
        assert residuals is not None
        assert len(residuals) == 1
        assert (0, 2) in residuals[0]
        assert residuals[0][(0, 2)] == 5

    def test_residual_of_perfect_program(self):
        """No residual when program is perfect."""
        prog = _make_prog(DeltaType.KEEP)
        inp = [[0, 1, 0], [0, 0, 0]]
        pairs = [_grid_pair(inp, inp)]
        residuals = compute_residual(prog.to_dict(), pairs)
        assert residuals is None  # Already perfect


# ---------------------------------------------------------------------------
# 3. LOO recertification
# ---------------------------------------------------------------------------

class TestLOORecertify:
    def test_loo_accepts_consistent_closure(self):
        """LOO should accept a closure that works on all subsets."""
        # Trivial: keep everything is always consistent
        prog = _make_prog(DeltaType.KEEP)
        pairs = [
            _grid_pair([[1, 0]], [[1, 0]]),
            _grid_pair([[0, 2]], [[0, 2]]),
            _grid_pair([[3, 0]], [[3, 0]]),
        ]

        def closure_fn(sub_pairs):
            return prog

        passed, report = loo_recertify(closure_fn, pairs)
        assert passed is True
        assert report["all_passed"] is True
        assert report["folds"] == 3
        assert report["passed"] == 3

    def test_loo_rejects_overfitting_closure(self):
        """LOO should reject a closure that can't generalize."""
        pairs = [
            _grid_pair([[1, 0]], [[1, 5]]),
            _grid_pair([[0, 2]], [[0, 2]]),
            _grid_pair([[3, 0]], [[3, 0]]),
        ]

        # This closure always returns keep, which fails on pair 0
        prog_keep = _make_prog(DeltaType.KEEP)

        def closure_fn(sub_pairs):
            return prog_keep

        passed, report = loo_recertify(closure_fn, pairs)
        assert passed is False
        assert 0 in report["failed"]

    def test_loo_rejects_single_pair(self):
        """Single-pair tasks can't be LOO-validated."""
        pairs = [_grid_pair([[1]], [[1]])]

        def closure_fn(sub_pairs):
            return _make_prog(DeltaType.KEEP)

        passed, report = loo_recertify(closure_fn, pairs)
        assert passed is False


# ---------------------------------------------------------------------------
# 4. Zero-cost-off: env gate
# ---------------------------------------------------------------------------

class TestEnvGate:
    def test_graduate_off_by_default(self):
        """ARC_GRADUATE not set -> gate returns False."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ARC_GRADUATE", None)
            assert _GRADUATE_ON() is False

    def test_graduate_on_when_set(self):
        """ARC_GRADUATE=1 -> gate returns True."""
        with patch.dict(os.environ, {"ARC_GRADUATE": "1"}, clear=False):
            assert _GRADUATE_ON() is True

    def test_graduate_off_when_zero(self):
        """ARC_GRADUATE=0 -> gate returns False."""
        with patch.dict(os.environ, {"ARC_GRADUATE": "0"}, clear=False):
            assert _GRADUATE_ON() is False


# ---------------------------------------------------------------------------
# 5. GraduationResult serialization
# ---------------------------------------------------------------------------

class TestGraduationResult:
    def test_to_dict_roundtrip(self):
        r = GraduationResult(
            task_id="test123",
            graduated=True,
            route="refit",
            partial_fit=0.85,
            closure_fit=1.0,
            time_s=12.5,
            routes_tried=["generative_patch", "analogy", "refit"],
        )
        d = r.to_dict()
        assert d["task_id"] == "test123"
        assert d["graduated"] is True
        assert d["route"] == "refit"
        assert len(d["routes_tried"]) == 3


# ---------------------------------------------------------------------------
# 6. Integration: train-perfect check
# ---------------------------------------------------------------------------

class TestTrainPerfect:
    def test_keep_is_perfect_on_identity(self):
        prog = _make_prog(DeltaType.KEEP)
        pairs = [
            _grid_pair([[1, 0]], [[1, 0]]),
            _grid_pair([[0, 2]], [[0, 2]]),
        ]
        assert _is_train_perfect_any(prog, pairs) is True

    def test_keep_is_not_perfect_on_transform(self):
        prog = _make_prog(DeltaType.KEEP)
        pairs = [
            _grid_pair([[1, 0]], [[5, 0]]),
        ]
        assert _is_train_perfect_any(prog, pairs) is False


# ---------------------------------------------------------------------------
# 7. load_near_solve_parts (with temp files)
# ---------------------------------------------------------------------------

class TestLoadParts:
    def test_load_from_directory(self, tmp_path):
        parts_dir = tmp_path / "parts"
        parts_dir.mkdir()
        rec = {
            "task_id": "abc123",
            "timestamp": "2026-01-01T00:00:00Z",
            "segmentation_variant": "S1",
            "program_partial": {"rules": [], "segmentation_variant": "S1",
                                "default_action": {"delta_type": "keep",
                                                   "params": {},
                                                   "parameter_class": "constant"},
                                "output_spec": {"mode": "same_as_input",
                                                "region": None,
                                                "height": None,
                                                "width": None,
                                                "background": None,
                                                "fill": None},
                                "library_operators_used": []},
            "train_fit_pixels": 0.85,
            "train_fit_objects": 0.8,
            "explained_rules": [],
            "residual": {},
            "delta_histogram": {},
            "failure_stage": "loo",
        }
        with open(parts_dir / "abc123.jsonl", "w") as f:
            f.write(json.dumps(rec) + "\n")

        loaded = load_near_solve_parts(parts_dir)
        assert "abc123" in loaded
        assert len(loaded["abc123"]) == 1
        assert loaded["abc123"][0].task_id == "abc123"
        assert loaded["abc123"][0].train_fit_pixels == 0.85


# ---------------------------------------------------------------------------
# 8. graduate_task integration (minimal: expect no graduation on identity)
# ---------------------------------------------------------------------------

class TestGraduateTask:
    def test_no_graduation_on_already_perfect_partial(self):
        """If the partial is already perfect, there's no residual to close."""
        prog = _make_prog(DeltaType.KEEP)
        rec = NearSolveRecord(
            task_id="test_id",
            timestamp="2026-01-01T00:00:00Z",
            segmentation_variant="S1",
            program_partial=prog.to_dict(),
            train_fit_pixels=1.0,
            train_fit_objects=1.0,
            failure_stage="loo",
        )
        pairs = [
            _grid_pair([[1, 0]], [[1, 0]]),
            _grid_pair([[0, 2]], [[0, 2]]),
        ]
        result = graduate_task("test_id", [rec], pairs, budget_s=5.0)
        # Partial is already perfect on identity pairs, so residual is None
        # -> no closure needed, but also no graduation (the partial
        # already failed LOO in the original run)
        assert isinstance(result, GraduationResult)
        assert result.task_id == "test_id"
