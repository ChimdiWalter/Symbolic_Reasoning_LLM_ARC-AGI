"""M2 verb 2 (COPY_PART): geometry, detection, end-to-end LOO."""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.growth import find_part_window, render_part
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant, DeltaType
from geocat_arc.object_reasoning.inducer import induce_program, InductionConfig
from geocat_arc.object_reasoning.actions import render_program


def test_find_part_window_and_render():
    src = {(2, 2): 3, (2, 3): 5, (3, 2): 3, (3, 3): 3}
    orphan = {(6, 7): 3, (6, 8): 5}          # top row of src, moved
    p = find_part_window(src, orphan)
    assert p == {"window": (0, 0, 1, 2), "placement": (4, 5)}
    assert render_part(src, p["window"], p["placement"]) == orphan
    assert find_part_window(src, {(0, 0): 9}) is None   # color mismatch


def _g(rows):
    return Grid.from_list(rows)


def test_copy_part_detection():
    gi = _g([[3, 5, 0, 0, 0],
             [3, 3, 0, 0, 0],
             [0, 0, 0, 0, 0]])
    go = _g([[3, 5, 0, 3, 5],   # top row copied to the right
             [3, 3, 0, 0, 0],
             [0, 0, 0, 0, 0]])
    seg = evaluate_variant(SegmentationVariant("S3"), [(gi, go)])
    corr = match_pair(seg.input_objects[0], seg.output_objects[0],
                      gi, go, pair_index=0)[0]
    deltas = extract_deltas(corr)
    kinds = {d.delta_type for d in deltas}
    orphans = [d for d in deltas if d.input_object_id is None]
    assert DeltaType.COPY_PART in kinds, kinds
    assert not orphans


def _pairs(specs):
    return [(Grid.from_list(i), Grid.from_list(o)) for i, o in specs]


def test_induce_copy_part_task():
    """The source's top row is stamped at a fixed offset — must induce via
    COPY_PART and pass LOO (window + placement stable across pairs)."""
    def make(r, c, cols, h=8, w=10):
        gi = [[0] * w for _ in range(h)]
        gi[r][c], gi[r][c + 1] = cols
        gi[r + 1][c] = gi[r + 1][c + 1] = cols[0]
        go = [row[:] for row in gi]
        go[r][c + 5], go[r][c + 6] = cols
        return gi, go

    pairs = _pairs([make(1, 1, (3, 5)), make(3, 2, (6, 8)),
                    make(5, 0, (2, 4))])
    res = induce_program(pairs, InductionConfig(budget_s=90))
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 3
    dts = {r.action.delta_type for r in res.program.rules}
    assert DeltaType.COPY_PART in dts, dts
    gi, go = _pairs([make(2, 3, (7, 9))])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()
