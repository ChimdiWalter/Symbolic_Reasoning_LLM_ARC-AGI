"""M2 verb 1 (CONNECT): geometry, detection, render, end-to-end LOO."""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.growth import connect_segment
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant, DeltaType
from geocat_arc.object_reasoning.inducer import induce_program, InductionConfig
from geocat_arc.object_reasoning.actions import render_program


def test_connect_segment_geometry():
    a = {(2, 1), (3, 1)}
    b = {(2, 6), (3, 6)}
    seg = connect_segment(a, b, (6, 8))
    assert set(seg) == {(2, c) for c in range(2, 6)}
    # vertical
    seg2 = connect_segment({(0, 3)}, {(5, 3)}, (7, 7))
    assert set(seg2) == {(r, 3) for r in range(1, 5)}
    # non-facing -> None
    assert connect_segment({(0, 0)}, {(5, 5)}, (8, 8)) is None


def _g(rows):
    return Grid.from_list(rows)


def test_connect_detection():
    gi = _g([[0, 0, 0, 0, 0, 0],
             [3, 0, 0, 0, 0, 5],
             [0, 0, 0, 0, 0, 0]])
    go = _g([[0, 0, 0, 0, 0, 0],
             [3, 4, 4, 4, 4, 5],
             [0, 0, 0, 0, 0, 0]])
    seg = evaluate_variant(SegmentationVariant("S1"), [(gi, go)])
    corr = match_pair(seg.input_objects[0], seg.output_objects[0],
                      gi, go, pair_index=0)[0]
    deltas = extract_deltas(corr)
    kinds = {d.delta_type for d in deltas}
    assert DeltaType.CONNECT in kinds, kinds
    orphans = [d for d in deltas if d.input_object_id is None]
    assert not orphans


def _pairs(specs):
    return [(Grid.from_list(i), Grid.from_list(o)) for i, o in specs]


def test_induce_connect_task():
    """Pairs of aligned endpoints get joined by a fixed-color bridge —
    must induce via CONNECT and pass LOO."""
    def make(r, c1, c2, col1, col2, h=7, w=9):
        gi = [[0] * w for _ in range(h)]
        gi[r][c1] = col1
        gi[r][c2] = col2
        go = [row[:] for row in gi]
        for c in range(c1 + 1, c2):
            go[r][c] = 4
        return gi, go

    pairs = _pairs([make(1, 0, 5, 3, 5), make(3, 2, 8, 6, 8),
                    make(5, 1, 6, 2, 3)])
    res = induce_program(pairs, InductionConfig(budget_s=90))
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    dts = {r.action.delta_type for r in res.program.rules}
    assert DeltaType.CONNECT in dts, dts
    gi, go = _pairs([make(2, 1, 7, 8, 6)])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()
