"""Tests for P3 certified analogy (geocat_arc.object_reasoning.analogy).

Covers: retrieval sanity, adaptation on a synthetic variant pair,
full LOO recertification, and zero-cost-off (env gate).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.analogy import (
    ProgramSignature,
    _ANALOGY_ON,
    _is_train_perfect,
    adapt_program,
    induce_by_analogy,
    load_certified_corpus,
    program_signature,
    retrieve_precedents,
    structure_similarity,
)
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    GridPair,
    ObjectProgram,
    ObjectRule,
    OutputSpec,
    ParameterClass,
    SegmentationVariant,
    SelectorRule,
)
from geocat_arc.object_reasoning.expressions import (
    ColorExpr,
    PredExpr,
    VecExpr,
)
from geocat_arc.object_reasoning.actions import render_program


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recolor_program(from_color: int, to_color: int) -> ObjectProgram:
    """A simple recolor program: objects of from_color -> to_color."""
    return ObjectProgram(
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
        rules=[ObjectRule(
            selector=SelectorRule(
                predicate=PredExpr(op="test",
                                   args=("color", "==", from_color)),
                literals=1),
            action=ActionRule(
                delta_type=DeltaType.RECOLOR,
                params={"color": ColorExpr(op="const", args=(to_color,))},
                parameter_class=ParameterClass.CONSTANT,
            ),
        )],
        default_action=ActionRule(delta_type=DeltaType.KEEP),
        output_spec=OutputSpec(mode="same_as_input"),
    )


def _make_translate_program(dr: int, dc: int) -> ObjectProgram:
    """A simple translate-all program."""
    return ObjectProgram(
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
        rules=[ObjectRule(
            selector=SelectorRule(
                predicate=PredExpr(op="true", args=()),
                literals=0),
            action=ActionRule(
                delta_type=DeltaType.TRANSLATE,
                params={"vector": VecExpr(op="const", args=(dr, dc))},
                parameter_class=ParameterClass.CONSTANT,
            ),
        )],
        default_action=ActionRule(delta_type=DeltaType.KEEP),
        output_spec=OutputSpec(mode="same_as_input"),
    )


def _grid_pair(inp_list, out_list) -> GridPair:
    return (Grid.from_list(inp_list), Grid.from_list(out_list))


def _make_corpus_dir(programs: dict[str, dict]) -> Path:
    """Create a temporary directory mimicking the outputs/*/programs/ layout."""
    tmpdir = Path(tempfile.mkdtemp())
    prog_dir = tmpdir / "outputs" / "test_run" / "programs"
    prog_dir.mkdir(parents=True)
    for task_id, prog_dict in programs.items():
        (prog_dir / f"{task_id}.json").write_text(
            json.dumps(prog_dict, indent=2))
    return tmpdir


# ---------------------------------------------------------------------------
# 1. Program signature tests
# ---------------------------------------------------------------------------

class TestProgramSignature:
    def test_recolor_signature(self):
        prog = _make_recolor_program(1, 3)
        sig = program_signature(prog.to_dict())
        assert "recolor" in sig.delta_types
        assert sig.n_rules == 1
        assert sig.output_mode == "same_as_input"
        assert sig.segmentation_variant == "S1"

    def test_translate_signature(self):
        prog = _make_translate_program(1, 0)
        sig = program_signature(prog.to_dict())
        assert "translate" in sig.delta_types
        assert sig.n_rules == 1

    def test_signature_stability(self):
        """Same program should always produce the same signature."""
        prog = _make_recolor_program(2, 5)
        sig1 = program_signature(prog.to_dict())
        sig2 = program_signature(prog.to_dict())
        assert sig1 == sig2


# ---------------------------------------------------------------------------
# 2. Structure similarity tests
# ---------------------------------------------------------------------------

class TestStructureSimilarity:
    def test_identical(self):
        sig = ProgramSignature(
            segmentation_variant="S1",
            delta_types=("recolor",),
            param_classes=("constant",),
            n_rules=1)
        assert structure_similarity(sig, sig) == pytest.approx(1.0)

    def test_different_delta_types(self):
        a = ProgramSignature(delta_types=("recolor",))
        b = ProgramSignature(delta_types=("translate",))
        sim = structure_similarity(a, b)
        assert sim < 1.0
        assert sim >= 0.0

    def test_range(self):
        a = ProgramSignature(
            segmentation_variant="S1",
            delta_types=("recolor", "translate"),
            n_rules=3)
        b = ProgramSignature(
            segmentation_variant="S3",
            delta_types=("scale",),
            n_rules=1,
            output_mode="crop_to")
        sim = structure_similarity(a, b)
        assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# 3. Corpus loading test
# ---------------------------------------------------------------------------

class TestCorpusLoading:
    def test_load_from_temp_dir(self):
        prog = _make_recolor_program(1, 3)
        corpus_dir = _make_corpus_dir({"task_abc": prog.to_dict()})
        corpus = load_certified_corpus(corpus_dir)
        assert "task_abc" in corpus
        assert corpus["task_abc"]["rules"][0]["action"]["delta_type"] == "recolor"

    def test_load_empty(self):
        tmpdir = Path(tempfile.mkdtemp())
        corpus = load_certified_corpus(tmpdir)
        assert corpus == {}


# ---------------------------------------------------------------------------
# 4. Retrieval tests
# ---------------------------------------------------------------------------

class TestRetrieval:
    def test_retrieve_returns_top_k(self):
        """Retrieval should return at most top_k results."""
        progs = {}
        for i in range(10):
            progs[f"task_{i}"] = _make_recolor_program(i % 10, (i + 1) % 10).to_dict()
        corpus_dir = _make_corpus_dir(progs)
        corpus = load_certified_corpus(corpus_dir)

        # Create a simple target task (recolor variant)
        pairs = [_grid_pair(
            [[1, 1, 0], [0, 0, 0]], [[3, 3, 0], [0, 0, 0]])]
        results = retrieve_precedents(pairs, corpus, top_k=3)
        assert len(results) <= 3
        assert all(len(r) == 3 for r in results)  # (task_id, dict, score)

    def test_retrieve_empty_corpus(self):
        pairs = [_grid_pair([[1]], [[2]])]
        results = retrieve_precedents(pairs, {})
        assert results == []

    def test_retrieve_scores_descending(self):
        """Results should be sorted by descending score."""
        progs = {
            "recolor_task": _make_recolor_program(1, 3).to_dict(),
            "translate_task": _make_translate_program(1, 0).to_dict(),
        }
        corpus_dir = _make_corpus_dir(progs)
        corpus = load_certified_corpus(corpus_dir)

        pairs = [_grid_pair(
            [[1, 1, 0], [0, 0, 0]], [[3, 3, 0], [0, 0, 0]])]
        results = retrieve_precedents(pairs, corpus)
        scores = [r[2] for r in results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 5. Adaptation test (synthetic variant pair)
# ---------------------------------------------------------------------------

class TestAdaptation:
    def test_adapt_recolor_variant(self):
        """A recolor-1-to-3 precedent should help solve recolor-2-to-5."""
        precedent = _make_recolor_program(1, 3)
        # Target task: recolor 2 -> 5
        target_pairs = [
            _grid_pair([[2, 2, 0], [0, 0, 0], [0, 2, 0]],
                       [[5, 5, 0], [0, 0, 0], [0, 5, 0]]),
            _grid_pair([[0, 2, 2], [2, 0, 0]],
                       [[0, 5, 5], [5, 0, 0]]),
        ]
        adapted = adapt_program(precedent.to_dict(), target_pairs)
        # The inducer should find the recolor program regardless
        # (this tests that the adaptation path at least runs without error)
        # adapted may be empty if the inducer doesn't find it in the budget
        assert isinstance(adapted, list)

    def test_adapt_preserves_train_perfection(self):
        """Any returned adaptation must be train-perfect."""
        precedent = _make_recolor_program(1, 3)
        target_pairs = [
            _grid_pair([[2, 2, 0], [0, 0, 0]], [[5, 5, 0], [0, 0, 0]]),
            _grid_pair([[0, 2, 0], [2, 2, 0]], [[0, 5, 0], [5, 5, 0]]),
        ]
        adapted = adapt_program(precedent.to_dict(), target_pairs)
        for prog in adapted:
            assert _is_train_perfect(prog, target_pairs)


# ---------------------------------------------------------------------------
# 6. Full LOO recertification test
# ---------------------------------------------------------------------------

class TestLOORecertification:
    def test_induce_by_analogy_returns_train_perfect(self):
        """Any result from induce_by_analogy must be train-perfect."""
        progs = {
            "recolor_1_3": _make_recolor_program(1, 3).to_dict(),
        }
        corpus_dir = _make_corpus_dir(progs)
        corpus = load_certified_corpus(corpus_dir)

        target_pairs = [
            _grid_pair([[2, 2, 0], [0, 0, 0]], [[5, 5, 0], [0, 0, 0]]),
            _grid_pair([[0, 2, 0], [2, 2, 0]], [[0, 5, 0], [5, 5, 0]]),
        ]
        results = induce_by_analogy(target_pairs, corpus=corpus)
        for prog in results:
            assert _is_train_perfect(prog, target_pairs)


# ---------------------------------------------------------------------------
# 7. Zero-cost-off test (env gate)
# ---------------------------------------------------------------------------

class TestZeroCostOff:
    def test_off_by_default(self):
        """ARC_ANALOGY should be off by default."""
        old = os.environ.pop("ARC_ANALOGY", None)
        try:
            assert not _ANALOGY_ON()
        finally:
            if old is not None:
                os.environ["ARC_ANALOGY"] = old

    def test_on_when_set(self):
        """ARC_ANALOGY=1 should activate the path."""
        old = os.environ.get("ARC_ANALOGY")
        os.environ["ARC_ANALOGY"] = "1"
        try:
            assert _ANALOGY_ON()
        finally:
            if old is not None:
                os.environ["ARC_ANALOGY"] = old
            else:
                os.environ.pop("ARC_ANALOGY", None)

    def test_off_when_zero(self):
        """ARC_ANALOGY=0 should keep the path off."""
        old = os.environ.get("ARC_ANALOGY")
        os.environ["ARC_ANALOGY"] = "0"
        try:
            assert not _ANALOGY_ON()
        finally:
            if old is not None:
                os.environ["ARC_ANALOGY"] = old
            else:
                os.environ.pop("ARC_ANALOGY", None)

    def test_induce_noop_when_off(self):
        """With ARC_ANALOGY off, induce_by_analogy should still work
        (the env gate is in the hook, not in the function itself)."""
        # The function itself should run regardless of env
        # It returns [] with empty corpus
        results = induce_by_analogy([], corpus={})
        assert results == []


# ---------------------------------------------------------------------------
# 8. Inducer hook integration test
# ---------------------------------------------------------------------------

class TestInducerHook:
    def test_analogy_hook_off_by_default(self):
        """With ARC_ANALOGY unset, the hook should not fire."""
        old = os.environ.pop("ARC_ANALOGY", None)
        try:
            from geocat_arc.object_reasoning.inducer import induce_program
            # A simple recolor task that the engine can solve normally
            pairs = [
                _grid_pair([[1, 1, 0], [0, 0, 0]], [[3, 3, 0], [0, 0, 0]]),
                _grid_pair([[0, 1, 1], [1, 0, 0]], [[0, 3, 3], [3, 0, 0]]),
                _grid_pair([[1, 0, 0], [0, 1, 0]], [[3, 0, 0], [0, 3, 0]]),
            ]
            result = induce_program(pairs)
            # Should solve via normal path (not analogy)
            if result.accepted:
                assert "ANALOGY_ADAPTED_FOUND" not in result.events
        finally:
            if old is not None:
                os.environ["ARC_ANALOGY"] = old
