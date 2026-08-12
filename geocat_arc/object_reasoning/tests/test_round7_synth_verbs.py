"""AUTONOMOUS M2 runtime: learned-verb registry, detection, render, LOO."""
import json

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.synth_verbs import (LearnedVerbRegistry,
                                                     apply_verb_chain)
from geocat_arc.object_reasoning import correspondence as C
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.types import SegmentationVariant, DeltaType
from geocat_arc.object_reasoning.inducer import induce_program, InductionConfig
from geocat_arc.object_reasoning.actions import render_program

MIRROR_V = [{"name": "verb_mirror_v", "chain": [["mirror_v", None]],
             "provenance": {"mined": "test"}}]


def setup_function(_fn):
    C.set_learned_verbs(LearnedVerbRegistry(MIRROR_V))


def teardown_function(_fn):
    C.set_learned_verbs(LearnedVerbRegistry([]))


def test_chain_interpreter():
    cells = {(0, 0), (1, 0), (2, 0), (2, 1)}       # an L
    img = apply_verb_chain([("mirror_v", None)], cells)
    assert img == frozenset({(0, 1), (1, 1), (2, 1), (2, 0)})


def _g(rows):
    return Grid.from_list(rows)


def test_synth_detection():
    gi = _g([[3, 0, 0, 0, 0, 0],
             [3, 0, 0, 0, 0, 0],
             [3, 3, 0, 0, 0, 0]])
    go = _g([[3, 0, 0, 0, 0, 3],
             [3, 0, 0, 0, 0, 3],
             [3, 3, 0, 0, 3, 3]])   # mirrored copy at the right
    seg = evaluate_variant(SegmentationVariant("S1"), [(gi, go)])
    corr = C.match_pair(seg.input_objects[0], seg.output_objects[0],
                        gi, go, pair_index=0)[0]
    deltas = C.extract_deltas(corr)
    kinds = {d.delta_type for d in deltas}
    assert DeltaType.SYNTH_COPY in kinds, kinds
    assert not [d for d in deltas if d.input_object_id is None]


def _pairs(specs):
    return [(Grid.from_list(i), Grid.from_list(o)) for i, o in specs]


def test_induce_with_learned_verb():
    """Mirrored-copy task: only solvable through the registered verb —
    the full autonomous-loop acceptance path (LOO folds included)."""
    def make(r, c, col, h=7, w=10):
        gi = [[0] * w for _ in range(h)]
        gi[r][c] = gi[r + 1][c] = gi[r + 2][c] = gi[r + 2][c + 1] = col
        go = [row[:] for row in gi]
        mc = c + 6
        go[r][mc + 1] = go[r + 1][mc + 1] = go[r + 2][mc + 1] = col
        go[r + 2][mc] = col
        return gi, go

    pairs = _pairs([make(0, 1, 3), make(2, 2, 5), make(1, 0, 8)])
    res = induce_program(pairs, InductionConfig(budget_s=90))
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    dts = {r.action.delta_type for r in res.program.rules}
    assert DeltaType.SYNTH_COPY in dts, dts
    gi, go = _pairs([make(3, 2, 6)])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()
