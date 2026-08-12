"""Stage-2 tests (STAGE2_REQUIREMENTS.md): typed composition, residual-driven
stage induction, deterministic scoring, ranker plumbing, phase-B fallback
(DECISIONS D16), and the ablation switches.

All tasks here are synthetic and generic — no ARC task ids, no data files.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from geocat_arc.bayesian_program_search.program_features import (
    OBJECT_FEATURE_NAMES,
    extract_features,
    object_feature_dim,
)
from geocat_arc.bayesian_program_search.search_loop import bayesian_search_v2
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.inducer import (
    InductionConfig,
    _composed_partial_attempt,
    _Attempt,
    _residual_px,
    certify,
    induce_program,
    rank_by_score,
    score_program,
)
from geocat_arc.object_reasoning.types import (
    ActionRule,
    ComposedProgram,
    DeltaType,
    FailureStage,
    ObjectProgram,
    SegmentationVariant,
    program_from_dict,
    to_grid_pairs,
)
from geocat_arc.perception.grid import Grid

S1 = SegmentationVariant.S1_SAME_COLOR_4
S2 = SegmentationVariant.S2_SAME_COLOR_8


# ---------------------------------------------------------------------------
# The synthetic two-pass task (flat overfits and fails LOO; a depth-2
# composition is clean): a wall (color 8) translates left by 2; a ball
# (color 2) must land immediately left-adjacent to the wall's FINAL column —
# a parameter relationally expressible only on the intermediate grid.
# ---------------------------------------------------------------------------

def _two_pass_pair(wall_col: int, ball_row: int):
    gi = np.zeros((5, 10), dtype=np.int32)
    go = np.zeros((5, 10), dtype=np.int32)
    gi[1:4, wall_col] = 8
    go[1:4, wall_col - 2] = 8
    gi[ball_row, 0] = 2
    go[ball_row, wall_col - 3] = 2
    return gi, go


def two_pass_task():
    return [_two_pass_pair(6, 2), _two_pass_pair(8, 1), _two_pass_pair(5, 3)]


# ---------------------------------------------------------------------------
# 2.1 ComposedProgram type + serialization
# ---------------------------------------------------------------------------

class TestComposedProgramType:
    def _cp(self) -> ComposedProgram:
        p1 = ObjectProgram(segmentation_variant=S1)
        p2 = ObjectProgram(segmentation_variant=S2,
                           default_action=ActionRule(delta_type=DeltaType.DELETE))
        return ComposedProgram(
            stages=[p1, p2],
            stage_provenance=[{"residual_before_px": 5,
                               "residual_after_px": 2,
                               "library_operators_used": []}])

    def test_roundtrip_via_dispatcher(self):
        cp = self._cp()
        d = json.loads(json.dumps(cp.to_dict()))
        back = program_from_dict(d)
        assert isinstance(back, ComposedProgram)
        assert back.to_dict() == cp.to_dict()

    def test_dispatcher_keeps_flat_programs_flat(self):
        p = ObjectProgram(segmentation_variant=S1)
        back = program_from_dict(json.loads(json.dumps(p.to_dict())))
        assert isinstance(back, ObjectProgram)
        assert back.to_dict() == p.to_dict()

    def test_composition_depth_distinct_from_program_depth(self):
        cp = self._cp()
        assert cp.composition_depth == 2
        assert cp.program_depth == sum(s.program_depth for s in cp.stages)
        assert cp.program_depth != cp.composition_depth

    def test_metrics_sum_over_stages(self):
        cp = self._cp()
        assert cp.expression_size == sum(s.expression_size for s in cp.stages)
        assert cp.rules == [r for s in cp.stages for r in s.rules]
        assert cp.segmentation_variant is S1

    def test_render_chains_stages(self):
        # two KEEP-identity stages: output == input through the chain
        cp = ComposedProgram(stages=[ObjectProgram(segmentation_variant=S1),
                                     ObjectProgram(segmentation_variant=S1)])
        g = Grid(np.array([[0, 1], [2, 0]], dtype=np.int32))
        assert np.array_equal(render_program(cp, g).to_numpy(), g.to_numpy())

    def test_fresh_process_re_render(self):
        """2.1.1: a fresh interpreter must deserialize and re-render exactly."""
        cp = ComposedProgram(stages=[ObjectProgram(segmentation_variant=S1),
                                     ObjectProgram(segmentation_variant=S1)])
        payload = json.dumps(cp.to_dict())
        code = (
            "import json, sys; import numpy as np\n"
            "from geocat_arc.object_reasoning.types import program_from_dict\n"
            "from geocat_arc.object_reasoning.actions import render_program\n"
            "from geocat_arc.perception.grid import Grid\n"
            "p = program_from_dict(json.loads(sys.argv[1]))\n"
            "g = Grid(np.array([[0, 1], [2, 0]], dtype=np.int32))\n"
            "out = render_program(p, g).to_numpy()\n"
            "assert np.array_equal(out, g.to_numpy()), out\n"
            "print('OK')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, payload],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[3]))
        assert proc.returncode == 0 and "OK" in proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# 2.2 Residual-driven composition (end to end through induce_program)
# ---------------------------------------------------------------------------

class TestCompositionInduction:
    def test_two_pass_task_solved_composed(self):
        gp = to_grid_pairs(two_pass_task())
        res = induce_program(gp, InductionConfig(budget_s=60))
        assert res.accepted, res.failure_stage
        assert isinstance(res.program, ComposedProgram)
        assert res.program.composition_depth == 2
        assert res.loo is not None and res.loo.all_passed
        # held-out generalization (never seen by induction)
        ti, to = _two_pass_pair(7, 2)
        pred = render_program(res.program, Grid(ti)).to_numpy()
        assert np.array_equal(pred, to)

    def test_stage_provenance_recorded(self):
        gp = to_grid_pairs(two_pass_task())
        res = induce_program(gp, InductionConfig(budget_s=60))
        assert res.accepted
        prov = res.program.stage_provenance
        assert len(prov) == res.program.composition_depth
        assert prov[0]["residual_after_px"] < prov[0]["residual_before_px"]

    def test_depth1_ablation_fails_two_pass_task(self):
        gp = to_grid_pairs(two_pass_task())
        res = induce_program(gp, InductionConfig(budget_s=60,
                                                 max_composition_depth=1))
        assert not res.accepted
        assert res.failure_stage is FailureStage.LOO  # flat overfits, gate holds

    def test_no_ranker_ablation_still_solves(self):
        gp = to_grid_pairs(two_pass_task())
        res = induce_program(gp, InductionConfig(budget_s=60,
                                                 use_ranker=False))
        assert res.accepted
        assert isinstance(res.program, ComposedProgram)

    def test_flat_solve_stays_flat(self):
        """A depth-1-solvable task must yield a bare ObjectProgram (2.1:
        depth 1 == today's flat program; no identity-stage padding)."""
        ti = np.array([[0, 3, 0], [0, 3, 0], [0, 0, 0]], dtype=np.int32)
        to = np.array([[0, 4, 0], [0, 4, 0], [0, 0, 0]], dtype=np.int32)
        ti2 = np.array([[0, 0, 0], [3, 0, 0], [3, 0, 0]], dtype=np.int32)
        to2 = np.array([[0, 0, 0], [4, 0, 0], [4, 0, 0]], dtype=np.int32)
        res = induce_program(to_grid_pairs([(ti, to), (ti2, to2)]),
                             InductionConfig(budget_s=30))
        assert res.accepted
        assert isinstance(res.program, ObjectProgram)

    def test_certificate_records_composition_depth(self):
        gp = to_grid_pairs(two_pass_task())
        res = induce_program(gp, InductionConfig(budget_s=60))
        assert res.accepted
        cert = certify(res, task_id="synthetic_two_pass")
        assert cert.composition_depth == 2
        assert cert.program.get("program_class") == "composed"

    def test_budget_respected(self):
        """2.2.3: the composition tree shares one cooperative budget."""
        gp = to_grid_pairs(two_pass_task())
        t0 = time.monotonic()
        induce_program(gp, InductionConfig(budget_s=3.0))
        # generous slack for non-interruptible leaf enumerations
        assert time.monotonic() - t0 < 30.0


# ---------------------------------------------------------------------------
# Monotone progress / residual helpers
# ---------------------------------------------------------------------------

class TestResidualHelpers:
    def test_residual_px_same_shape(self):
        a = Grid(np.array([[1, 2], [3, 4]], dtype=np.int32))
        b = Grid(np.array([[1, 0], [3, 4]], dtype=np.int32))
        assert _residual_px(a, b) == 1
        assert _residual_px(a, a) == 0

    def test_residual_px_shape_mismatch_is_full_target(self):
        a = Grid(np.array([[1, 2, 3]], dtype=np.int32))
        b = Grid(np.array([[1, 2], [3, 4]], dtype=np.int32))
        assert _residual_px(a, b) == 4

    def test_composed_partial_attempt_records_stage1_fragment(self):
        """2.2.4: failed compositions persist with the stage-1 fragment."""
        stage1 = {"segmentation_variant": "S1", "rules": [],
                  "default_action": {"delta_type": "keep", "params": {},
                                     "parameter_class": "relational"},
                  "output_spec": {"mode": "same_as_input", "region": None,
                                  "height": None, "width": None,
                                  "background": None, "fill": None},
                  "library_operators_used": []}
        cand = _Attempt(fit_objects=0.6, fit_pixels=0.5,
                        program_partial=stage1)
        sub = _Attempt(fit_objects=0.8, fit_pixels=0.7,
                       program_partial=dict(stage1),
                       stage=FailureStage.PARAMETER)
        merged = _composed_partial_attempt(cand, sub)
        pp = merged.program_partial
        assert pp["program_class"] == "composed_partial"
        assert pp["stage1"] == stage1
        assert merged.fit_objects == 0.8
        assert merged.stage is FailureStage.PARAMETER


# ---------------------------------------------------------------------------
# 3.1 Deterministic scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_score_prefers_shorter_program(self):
        cfg = InductionConfig()
        small = ObjectProgram(segmentation_variant=S1)
        big = ComposedProgram(stages=[ObjectProgram(segmentation_variant=S1),
                                      ObjectProgram(segmentation_variant=S1)])
        assert score_program(small, 1.0, 1.0, cfg) \
            > score_program(big, 1.0, 1.0, cfg)

    def test_score_rewards_loo_margin(self):
        cfg = InductionConfig()
        p = ObjectProgram(segmentation_variant=S1)
        assert score_program(p, 1.0, 1.0, cfg) > score_program(p, 1.0, 0.5, cfg)

    def test_rank_by_score_deterministic_and_score_first(self):
        cfg = InductionConfig()
        flat = ObjectProgram(segmentation_variant=S1)
        comp = ComposedProgram(stages=[ObjectProgram(segmentation_variant=S1),
                                       ObjectProgram(segmentation_variant=S2)])
        r1 = rank_by_score([comp, flat], {}, cfg)
        r2 = rank_by_score([flat, comp], {}, cfg)
        assert [p.to_dict() for p in r1] == [p.to_dict() for p in r2]
        assert isinstance(r1[0], ObjectProgram)  # shorter wins on equal fit


# ---------------------------------------------------------------------------
# 3.2 / 3.3 Ranker plumbing
# ---------------------------------------------------------------------------

class TestRankerPlumbing:
    def test_object_feature_vector_fixed_dim(self):
        flat = ObjectProgram(segmentation_variant=S1)
        comp = ComposedProgram(stages=[ObjectProgram(segmentation_variant=S1),
                                       ObjectProgram(segmentation_variant=S2)])
        f1, f2 = extract_features(flat), extract_features(comp)
        assert f1.shape == f2.shape == (object_feature_dim(),)
        assert object_feature_dim() == len(OBJECT_FEATURE_NAMES)
        # composition depth is a live dimension
        i = OBJECT_FEATURE_NAMES.index("composition_depth")
        assert f1[i] == 1.0 and f2[i] == 2.0

    def test_bayesian_search_v2_deterministic_full_coverage(self):
        cands = ["a", "b", "c", "d"]
        fv = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0]),
              "c": np.array([1.0, 1.0]), "d": np.array([0.5, 0.5])}
        scores = {"a": 0.1, "b": 0.9, "c": 0.5, "d": 0.2}

        def run():
            return bayesian_search_v2(
                cands, lambda c: fv[c], lambda c: (c.upper(), scores[c]))

        r1, r2 = run(), run()
        assert r1 == r2
        assert {c for c, _, _ in r1} == set(cands)  # no candidate dropped

    def test_bayesian_search_v2_attaches_partials_on_raise(self):
        def evaluate(c):
            if c == "stop":
                raise RuntimeError("budget")
            return c, 1.0

        with pytest.raises(RuntimeError) as exc_info:
            bayesian_search_v2(["x", "stop"], lambda c: np.ones(2), evaluate)
        partials = getattr(exc_info.value, "partial_results", None)
        assert partials is not None and len(partials) >= 0
