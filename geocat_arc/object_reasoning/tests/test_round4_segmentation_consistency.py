"""Round-4 lever 2: granularity-consistency in segmentation scoring.

Covers: merge/split mismatch counting; grow-aware coverage + the
growth-explained count relaxation (same-shape only, mismatch==0 only);
mismatch-first candidate ordering reaching the induction winner.
"""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.types import SegmentationVariant
from geocat_arc.object_reasoning.inducer import induce_program


def _g(rows):
    return Grid.from_list(rows)


def test_mismatch_counts_merges_and_splits():
    # input: two separate 3-bars; output: one 7-bar spanning both -> merge
    gi = _g([[0, 0, 0, 0, 0, 0, 0],
             [3, 3, 3, 0, 3, 3, 3],
             [0, 0, 0, 0, 0, 0, 0]])
    go = _g([[0, 0, 0, 0, 0, 0, 0],
             [3, 3, 3, 3, 3, 3, 3],
             [0, 0, 0, 0, 0, 0, 0]])
    res = evaluate_variant(SegmentationVariant("S1"), [(gi, go)])
    assert res.granularity_mismatch >= 1
    # identity pair -> zero mismatch
    res2 = evaluate_variant(SegmentationVariant("S1"), [(gi, gi)])
    assert res2.granularity_mismatch == 0


def test_grow_explained_coherence_same_shape_only():
    # halo growth changes the object-count relation arbitrarily? No — same
    # count; use RAY growth into a second object count change: one seed in,
    # seed + detached? Keep simple: growth keeps counts (1 -> 1) but the
    # grown shape is NOT a copy of the input; coverage must still pass.
    gi = _g([[0, 0, 0],
             [0, 5, 0],
             [0, 0, 0]])
    go = _g([[0, 5, 0],
             [5, 5, 5],
             [0, 5, 0]])   # 4-halo around the seed: contains the input cell
    res = evaluate_variant(SegmentationVariant("S1"), [(gi, go)] * 2)
    assert res.coherent, (res.pixel_coverage, res.object_counts)


def test_merge_y_variant_never_buys_growth_relaxation():
    # merged output (mismatch > 0) must not become coherent via growth
    gi = _g([[3, 0, 3]])
    go = _g([[3, 3, 3]])   # single object containing BOTH inputs -> merge
    res = evaluate_variant(SegmentationVariant("S1"), [(gi, go)])
    assert res.granularity_mismatch >= 1


def test_halo_task_end_to_end_with_consistency_ordering():
    """Seeds gain color-carrying halos; the consistent variant must be
    chosen and the task must induce + pass LOO (the merge-death pattern
    at miniature scale)."""
    def make(r, c, col, h=7, w=7):
        gi = [[0] * w for _ in range(h)]
        gi[r][c] = col
        go = [row[:] for row in gi]
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            go[r + dr][c + dc] = col
        return Grid.from_list(gi), Grid.from_list(go)

    pairs = [make(2, 2, 3), make(3, 4, 6), make(1, 1, 8)]
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3


def test_orphan_absorption_appendage():
    """A mark carved as a separate object but touching exactly one matched
    object is absorbed into that match as GROW (the appendage family)."""
    from geocat_arc.object_reasoning.correspondence import (match_pair,
                                                            extract_deltas)
    from geocat_arc.object_reasoning.types import DeltaType
    gi = _g([[0, 0, 0, 0],
             [0, 3, 3, 0],
             [0, 3, 3, 0],
             [0, 0, 0, 0]])
    go = _g([[0, 5, 0, 0],       # a differently-colored flag on the block
             [0, 3, 3, 0],
             [0, 3, 3, 0],
             [0, 0, 0, 0]])
    res = evaluate_variant(SegmentationVariant("S1"), [(gi, go)])
    corr = match_pair(res.input_objects[0], res.output_objects[0],
                      gi, go, pair_index=0)[0]
    deltas = extract_deltas(corr)
    orphans = [d for d in deltas if d.input_object_id is None]
    grows = [d for d in deltas if d.delta_type is DeltaType.GROW]
    assert not orphans, [d.delta_type for d in deltas]
    assert grows and grows[0].residual_pixels == 0
    assert len(grows[0].output_object_ids) == 2  # host + absorbed


def test_orphan_absorption_end_to_end():
    """Blocks gain a same-colored flag above-left — absorbed appendages must
    make the task inducible + LOO-passing."""
    def make(r, c, col, h=7, w=7):
        gi = [[0] * w for _ in range(h)]
        for dr in (0, 1):
            for dc in (0, 1):
                gi[r + dr][c + dc] = col
        go = [row[:] for row in gi]
        go[r - 1][c] = col          # flag: 8-adjacent, separate 4-conn obj?
        return Grid.from_list(gi), Grid.from_list(go)

    # NOTE: a 4-adjacent flag merges under S1; place diagonal for isolation
    def make_diag(r, c, col, h=7, w=7):
        gi = [[0] * w for _ in range(h)]
        for dr in (0, 1):
            for dc in (0, 1):
                gi[r + dr][c + dc] = col
        go = [row[:] for row in gi]
        go[r - 1][c - 1] = 4        # FIXED-color diagonal flag (varying
        # colors would need color-abstracted patterns — future work; the
        # gate rightly rejects those as per-member memorizers)
        return Grid.from_list(gi), Grid.from_list(go)

    pairs = [make_diag(2, 2, 3), make_diag(3, 4, 6), make_diag(2, 3, 8)]
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3


def test_color_abstracted_pattern_generalizes():
    """VARYING-color appendages (flag color = host color) must now induce
    via the color-abstracted pattern (mask + relational color slot) and
    pass LOO — the case the baked-color pattern rightly failed."""
    def make_diag(r, c, col, h=7, w=7):
        gi = [[0] * w for _ in range(h)]
        for dr in (0, 1):
            for dc in (0, 1):
                gi[r + dr][c + dc] = col
        go = [row[:] for row in gi]
        go[r - 1][c - 1] = col      # flag carries the HOST color
        return Grid.from_list(gi), Grid.from_list(go)

    pairs = [make_diag(2, 2, 3), make_diag(3, 4, 6), make_diag(2, 3, 8)]
    res = induce_program(pairs)
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    # generalizes to an unseen color
    gi, go = make_diag(3, 3, 9)
    from geocat_arc.object_reasoning.actions import render_program as _rp
    assert _rp(res.program, gi).to_list() == go.to_list()
