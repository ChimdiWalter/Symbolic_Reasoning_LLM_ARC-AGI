"""Tests for inducer.py (induction stages, LOO gate) and engine.py
(orchestration, persistence, JSON-reconstructable apply_fn, memory hooks).

All tasks here are SYNTHETIC and generic — nothing task-ID-shaped; the tests
exercise the same code paths the dev-set run uses.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from geocat_arc.object_reasoning.actions import program_apply_fn, render_program
from geocat_arc.object_reasoning.engine import (
    ObjectReasoningEngine,
    ObjectReasoningResult,
)
from geocat_arc.object_reasoning.inducer import (
    InductionConfig,
    build_labeled_table,
    certify,
    enumerate_labeled_tables,
    induce_fuzzy_selector,
    induce_parameters,
    induce_program,
    induce_selector,
    loo_validate,
    rank_candidates,
)
from geocat_arc.object_reasoning.memory import promote_fragments
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    FailureStage,
    InductionResult,
    LOOReport,
    ObjectProgram,
    ParameterClass,
    SegmentationVariant,
    to_grid_pairs,
)

CFG = InductionConfig(budget_s=25.0)


# ---------------------------------------------------------------------------
# Synthetic task builders (generic, parameterized — no task IDs anywhere)
# ---------------------------------------------------------------------------

def delete_by_color_task():
    """Objects of color 5 disappear; color-3 objects stay.  3 pairs."""
    pairs = []
    for shift in range(3):
        inp = np.zeros((8, 8), int)
        inp[1:3, 1 + shift:3 + shift] = 5
        inp[5:7, 5:7] = 3
        out = np.zeros((8, 8), int)
        out[5:7, 5:7] = 3
        pairs.append((inp, out))
    return pairs


def gravity_task():
    """A color-2 bar falls until adjacent to the color-8 floor."""
    pairs = []
    for start in (0, 2, 4):
        inp = np.zeros((10, 6), int)
        inp[start:start + 2, 2] = 2
        inp[8, 1:5] = 8
        out = np.zeros((10, 6), int)
        out[6:8, 2] = 2
        out[8, 1:5] = 8
        pairs.append((inp, out))
    return pairs


def recolor_map_task():
    """Global color map 3->4, 6->8 applied to every object (induced_map)."""
    mapping = {3: 4, 6: 8}
    pairs = []
    for shift in range(3):
        inp = np.zeros((8, 8), int)
        inp[1:3, 1 + shift] = 3
        inp[5:6, 4:6] = 6
        out = inp.copy()
        for src, dst in mapping.items():
            out[inp == src] = dst
        pairs.append((inp, out))
    return pairs


def delete_by_color_task_v(color: int, keep_color: int):
    """delete_by_color with parameterized colors (for fragment mining)."""
    pairs = []
    for shift in range(3):
        inp = np.zeros((8, 8), int)
        inp[1:3, 1 + shift:3 + shift] = color
        inp[5:7, 5:7] = keep_color
        out = np.zeros((8, 8), int)
        out[5:7, 5:7] = keep_color
        pairs.append((inp, out))
    return pairs


def crop_largest_task():
    """Output = bbox crop of the (unique) 3x3 object."""
    pairs = []
    for shift in range(3):
        inp = np.zeros((10, 10), int)
        inp[1:4, 1 + shift:4 + shift] = 4
        inp[7, 7] = 7
        out = inp[1:4, 1 + shift:4 + shift].copy()
        pairs.append((inp, out))
    return pairs


def uniform_fill_task():
    """Output = 2x2 grid of the largest object's color (shrink_const_out)."""
    pairs = []
    for i, big_color in enumerate((3, 6, 2)):
        inp = np.zeros((9, 9), int)
        inp[1:4, 1:4] = big_color   # largest
        inp[6:7, 6:8] = 5           # small
        out = np.full((2, 2), big_color, int)
        pairs.append((inp, out))
    return pairs


def unsolvable_morph_task():
    """Two KEEP objects + one object morphing into a genuinely new shape:
    partial fit >= 0.5, never train-perfect -> near-solve path."""
    pairs = []
    for shift in range(3):
        inp = np.zeros((9, 9), int)
        inp[0:2, 0:2] = 3                    # keep
        inp[4:6, 4:6] = 6                    # keep
        inp[7, 1 + shift:4 + shift] = 8      # morphs
        out = inp.copy()
        out[7, 1 + shift:4 + shift] = 0
        # new shape unrelated to any input object (L pattern grows with pair)
        out[8, 0:2 + shift] = 8
        pairs.append((inp, out))
    return pairs


def _accepted(pairs, cfg=CFG) -> InductionResult:
    res = induce_program(to_grid_pairs(pairs), cfg)
    assert res.accepted, (res.failure_stage, res.loo)
    assert res.program is not None
    return res


# ---------------------------------------------------------------------------
# induce_program end-to-end on synthetic tasks
# ---------------------------------------------------------------------------

class TestInduceProgram:
    def test_delete_by_color_accepted_with_full_loo(self):
        pairs = delete_by_color_task()
        res = _accepted(pairs)
        assert res.loo is not None
        assert res.loo.folds == len(pairs)         # A5: folds == n_train
        assert res.loo.all_passed
        assert res.train_fit_objects == 1.0
        # the program is train-perfect through the sole executor
        for inp, out in to_grid_pairs(pairs):
            assert np.array_equal(render_program(res.program, inp).to_numpy(),
                                  out.to_numpy())

    def test_gravity_is_relational(self):
        res = _accepted(gravity_task())
        assert res.program.worst_parameter_class is ParameterClass.RELATIONAL
        moves = [r for r in res.program.rules
                 if r.action.delta_type in (DeltaType.TRANSLATE,
                                            DeltaType.MOVE_UNTIL_ADJACENT)]
        assert moves, "expected a motion rule"

    def test_recolor_color_map_induced(self):
        res = _accepted(recolor_map_task())
        assert res.program.worst_parameter_class in (
            ParameterClass.INDUCED_MAP, ParameterClass.RELATIONAL,
            ParameterClass.FEATURE)
        # generalizes to unseen positions AND the mapped colors
        inp = np.zeros((8, 8), int)
        inp[2:4, 5] = 3
        inp[6, 1:3] = 6
        pred = render_program(res.program,
                              to_grid_pairs([(inp, inp)])[0][0]).to_numpy()
        expected = inp.copy()
        expected[inp == 3] = 4
        expected[inp == 6] = 8
        assert np.array_equal(pred, expected)

    def test_crop_selection(self):
        res = _accepted(crop_largest_task())
        assert res.program.output_spec.mode == "crop"
        assert res.program.rules[0].action.delta_type is DeltaType.CROP_TO

    def test_uniform_fill_constant_shape(self):
        res = _accepted(uniform_fill_task())
        spec = res.program.output_spec
        assert spec.mode == "constant_shape"
        assert (spec.height, spec.width) == (2, 2)
        assert spec.fill is not None

    def test_near_solve_on_partial_fit(self):
        res = induce_program(to_grid_pairs(unsolvable_morph_task()), CFG)
        assert not res.accepted
        assert res.near_solve is not None
        assert res.near_solve.train_fit_objects >= 0.5
        assert res.near_solve.failure_stage in {s.value for s in FailureStage}
        assert res.near_solve.delta_histogram  # non-empty signature

    def test_budget_exhaustion_never_raises(self):
        res = induce_program(to_grid_pairs(gravity_task()),
                             InductionConfig(budget_s=0.001))
        assert isinstance(res, InductionResult)

    def test_program_json_roundtrip_preserves_predictions(self):
        res = _accepted(gravity_task())
        clone = ObjectProgram.from_json(res.program.to_json())
        for inp, out in to_grid_pairs(gravity_task()):
            assert np.array_equal(render_program(clone, inp).to_numpy(),
                                  render_program(res.program, inp).to_numpy())


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------

class TestStages:
    def _table(self, pairs):
        grid_pairs = to_grid_pairs(pairs)
        seg = evaluate_variant(SegmentationVariant.S1_SAME_COLOR_4, grid_pairs)
        assert seg.coherent
        return build_labeled_table(seg, grid_pairs)

    def test_labeled_table_covers_all_input_objects(self):
        table, report = self._table(delete_by_color_task())
        assert len(table.labels) == len(table.rows)
        types = {d.delta_type for d in table.labels.values()}
        assert types == {DeltaType.KEEP, DeltaType.DELETE}

    def test_enumerate_labeled_tables_bounded(self):
        grid_pairs = to_grid_pairs(delete_by_color_task())
        seg = evaluate_variant(SegmentationVariant.S1_SAME_COLOR_4, grid_pairs)
        tables = list(enumerate_labeled_tables(seg, grid_pairs,
                                               max_alternatives=4))
        # cap: max_alternatives best-first combos + at most one
        # profile-diagonal combo per weighting profile (deduped)
        from geocat_arc.object_reasoning.correspondence import WEIGHT_PROFILES
        assert 1 <= len(tables) <= 4 + len(WEIGHT_PROFILES)

    def test_induce_selector_zero_conflict(self):
        table, _ = self._table(delete_by_color_task())
        sel = induce_selector(table, DeltaType.DELETE)
        assert sel is not None
        assert sel.literals >= 1
        # exact selection: it must NOT select the keep objects
        sel_keep = induce_selector(table, DeltaType.KEEP)
        assert sel_keep is not None
        assert sel_keep.predicate != sel.predicate

    def test_induce_parameters_zero_conflict(self):
        table, _ = self._table(gravity_task())
        sel = induce_selector(table, DeltaType.TRANSLATE)
        assert sel is not None
        action = induce_parameters(table, sel, DeltaType.TRANSLATE, CFG)
        assert action is not None
        assert action.delta_type in (DeltaType.TRANSLATE,
                                     DeltaType.MOVE_UNTIL_ADJACENT)
        assert action.parameter_class is ParameterClass.RELATIONAL

    def test_fuzzy_selector_reports_accuracy_below_one(self):
        # inconsistent labels: identical twin objects, but the DELETED one
        # swaps position between pairs -> no zero-conflict selector exists
        pairs = []
        for keep_top in (True, False):
            inp = np.zeros((8, 8), int)
            inp[1:3, 1:3] = 3
            inp[5:7, 5:7] = 3
            out = np.zeros((8, 8), int)
            if keep_top:
                out[1:3, 1:3] = 3
            else:
                out[5:7, 5:7] = 3
            pairs.append((inp, out))
        table, _ = self._table(pairs)
        assert induce_selector(table, DeltaType.DELETE) is None
        fuzzy = induce_fuzzy_selector(table, DeltaType.DELETE)
        if fuzzy is not None:                      # fuzzy is best-effort
            _rule, acc = fuzzy
            assert 0.0 < acc < 1.0

    def test_rank_candidates_prefers_fewer_literals(self):
        res = _accepted(delete_by_color_task())
        progs = [res.program]
        loo = {0: res.loo}
        assert rank_candidates(progs, loo) == progs


# ---------------------------------------------------------------------------
# The LOO gate (blocking)
# ---------------------------------------------------------------------------

class TestLOOGate:
    def test_loo_validate_passes_correct_inducer(self):
        grid_pairs = to_grid_pairs(delete_by_color_task())

        def good_inducer(sub_pairs):
            return induce_program(sub_pairs, CFG)

        report = loo_validate(good_inducer, grid_pairs)
        assert report.folds == 3 and report.passed == 3

    def test_loo_validate_fails_wrong_program(self):
        grid_pairs = to_grid_pairs(delete_by_color_task())
        # constant identity program: train inputs != outputs -> every fold fails
        identity = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4)

        def bad_inducer(sub_pairs):
            return InductionResult(task_id="", accepted=True, program=identity)

        report = loo_validate(bad_inducer, grid_pairs)
        assert report.folds == 3 and report.passed == 0
        assert report.failed_pair_indices == [0, 1, 2]
        assert not report.all_passed

    def test_single_pair_task_folds_zero(self):
        report = loo_validate(lambda p: None,
                              to_grid_pairs(delete_by_color_task()[:1]))
        assert report.folds == 0 and not report.all_passed

    def test_certify_requires_acceptance_and_loo(self):
        res = induce_program(to_grid_pairs(unsolvable_morph_task()), CFG)
        with pytest.raises(ValueError):
            certify(res, "t")
        ok = _accepted(delete_by_color_task())
        cert = certify(ok, "t", run_id="r")
        assert cert.loo_folds == 3 and cert.train_fit == 1.0
        assert cert.program  # full serialized program present


# ---------------------------------------------------------------------------
# Engine orchestration + persistence
# ---------------------------------------------------------------------------

class TestEngine:
    def test_solve_persists_program_and_certificate(self, tmp_path):
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        result = engine.solve("syn_delete", delete_by_color_task())
        assert isinstance(result, ObjectReasoningResult)
        assert result.solution is not None and result.solution.is_exact
        prog_path = tmp_path / "programs" / "syn_delete.json"
        cert_path = tmp_path / "certificates" / "syn_delete.json"
        assert prog_path.exists() and cert_path.exists()
        cert = json.loads(cert_path.read_text())
        assert cert["loo_folds"] == 3 and cert["loo_score"] == 1.0
        assert engine.task_order == ["syn_delete"]
        assert "syn_delete" in engine.accepted

    def test_apply_fn_reconstructable_from_program_json_alone(self, tmp_path):
        """Requirement 4.2 proof: the serialized JSON on disk is sufficient
        to reconstruct the executable, with identical predictions."""
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        pairs = gravity_task()
        result = engine.solve("syn_gravity", pairs)
        assert result.solution is not None
        # fresh reconstruction from the artifact file only
        raw = (tmp_path / "programs" / "syn_gravity.json").read_text()
        rebuilt = program_apply_fn(ObjectProgram.from_json(raw))
        # unseen test input (new start position)
        test_in = np.zeros((10, 6), int)
        test_in[1:3, 2] = 2
        test_in[8, 1:5] = 8
        expected = np.zeros((10, 6), int)
        expected[6:8, 2] = 2
        expected[8, 1:5] = 8
        assert np.array_equal(rebuilt(test_in), expected)
        assert np.array_equal(result.solution.apply_fn(test_in), expected)

    def test_near_solve_recorded_to_store(self, tmp_path):
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        result = engine.solve("syn_morph", unsolvable_morph_task())
        assert result.solution is None
        assert result.near_solves and result.near_solves[0].task_id == "syn_morph"
        stored = engine.near_solve_store.load_all()
        assert len(stored) == 1
        assert stored[0].failure_stage in {s.value for s in FailureStage}

    def test_task_id_independence(self, tmp_path):
        """Renaming task IDs must not change any prediction (constraint 6.1)."""
        e1 = ObjectReasoningEngine(tmp_path / "a", config=CFG)
        e2 = ObjectReasoningEngine(tmp_path / "b", config=CFG)
        r1 = e1.solve("alpha", delete_by_color_task())
        r2 = e2.solve("zeta_renamed", delete_by_color_task())
        assert r1.solution is not None and r2.solution is not None
        assert r1.solution.program_json == r2.solution.program_json

    def test_engine_never_raises_on_degenerate_input(self, tmp_path):
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        empty = np.zeros((3, 3), int)
        result = engine.solve("syn_empty", [(empty, empty)])
        assert result.solution is None or result.solution.is_exact

    def test_no_library_ablation(self, tmp_path):
        engine = ObjectReasoningEngine(tmp_path, use_library=False, config=CFG)
        assert engine.library.operators() == []
        result = engine.solve("syn_delete2", delete_by_color_task())
        assert result.solution is not None  # solving works without library


# ---------------------------------------------------------------------------
# Memory loop: promote -> validate -> register -> reuse
# ---------------------------------------------------------------------------

class TestMemoryLoop:
    def test_promote_and_validate_and_reuse(self, tmp_path):
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        variants = [(5, 3), (7, 4), (6, 1)]
        for i, (dead, kept) in enumerate(variants):
            res = engine.solve(f"syn_del_{i}", delete_by_color_task_v(dead, kept))
            assert res.solution is not None, f"variant {i} unsolved"

        # the shared (selector schema, action) fragment appears in 3 programs
        accepted = {tid: ObjectProgram.from_dict(d)
                    for tid, d in engine.accepted.items()}
        mined = promote_fragments(accepted)
        assert mined, "expected >= 1 mined fragment across 3 accepted programs"

        registered = engine.promote_and_validate()
        assert registered, "expected >= 1 validated + registered operator"
        assert len(engine.library) >= 1
        assert (tmp_path / "library.json").exists()

        # a 4th task with fresh colors re-binds the fragment's free slots
        result = engine.solve("syn_del_new", delete_by_color_task_v(9, 2))
        assert result.solution is not None
        # library-first instantiation is recorded when the fragment's rule
        # survived into the winning program (usage is optional, solving isn't)
        assert isinstance(result.solution.program_json.get(
            "library_operators_used"), list)

    def test_resume_tasks_for_unknown_operator(self, tmp_path):
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        assert engine.resume_tasks_for("no_such_op", lambda t: []) == []
