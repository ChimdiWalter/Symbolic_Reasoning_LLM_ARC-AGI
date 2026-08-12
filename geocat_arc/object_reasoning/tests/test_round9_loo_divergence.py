"""Round-9 lever 4: fold-divergence instrumentation on the LOO gate.

The v11 failure census: loo 264 / matching 147 / parameter 26 / selector 9.
The dominant blocker is programs that are train-perfect but fold-divergent,
and until now the near-solve record kept only the failed fold INDICES.
These tests pin the new trace: each failed fold records the reinduced fold
program and the cell-level mismatch on the held-out pair — the raw material
for cross-task parameter-expression mining (lever 1).
"""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.expressions import PredExpr
from geocat_arc.object_reasoning.inducer import (InductionConfig,
                                                 induce_program,
                                                 loo_validate)
from geocat_arc.object_reasoning.types import (ActionRule, DeltaType,
                                               FailureStage, InductionResult,
                                               ObjectProgram, ObjectRule,
                                               OutputSpec, SegmentationVariant,
                                               SelectorRule)


def _identity_program() -> ObjectProgram:
    rule = ObjectRule(
        selector=SelectorRule(predicate=PredExpr(op="true", args=()),
                              literals=0),
        action=ActionRule(delta_type=DeltaType.KEEP))
    return ObjectProgram(segmentation_variant=SegmentationVariant("S1"),
                         rules=[rule],
                         default_action=ActionRule(delta_type=DeltaType.KEEP),
                         output_spec=OutputSpec(mode="same_as_input"))


def test_loo_divergence_trace_direct():
    """A constant identity inducer against pairs where identity is wrong on
    one pair (cell diff) and impossible on another (shape diff): the report
    must carry one trace per failed fold with the fold program serialized."""
    prog = _identity_program()

    def fn(sub_pairs):
        return InductionResult(task_id="", accepted=True, program=prog)

    ident = Grid.from_list([[1, 0], [0, 0]])
    pairs = [
        (ident, ident),                                    # identity holds
        (ident, Grid.from_list([[1, 0], [0, 5]])),         # 1 cell wrong
        (ident, Grid.from_list([[1, 0, 0], [0, 0, 0]])),   # shape mismatch
    ]
    rep = loo_validate(fn, pairs)
    assert rep.folds == 3 and rep.passed == 1
    assert rep.failed_pair_indices == [1, 2]
    assert len(rep.divergence) == 2
    by_fold = {t["fold"]: t for t in rep.divergence}
    t1 = by_fold[1]
    assert t1["fold_program"] is not None            # serialized program
    assert t1["cells_wrong"] == 1
    assert t1["shape_mismatch"] is False
    assert t1["expected_shape"] == [2, 2]
    t2 = by_fold[2]
    assert t2["shape_mismatch"] is True
    assert t2["cells_wrong"] is None
    assert t2["pred_shape"] == [2, 2] and t2["expected_shape"] == [2, 3]


def _recolor_pair(in_color, out_color, size, h=6, w=6):
    gi = [[0] * w for _ in range(h)]
    go = [[0] * w for _ in range(h)]
    for k in range(size):
        gi[2][1 + k] = in_color
        go[2][1 + k] = out_color
    return Grid.from_list(gi), Grid.from_list(go)


def test_loo_failure_emits_divergence_in_near_solve():
    """The E4 forcing shape: color_map {2:7, 3:7, 5:9} is train-perfect on
    the full data, but every fold subset either collapses to a single-valued
    map (blocked by the guard -> a wrong constant wins) or drops a map key
    (EvalError on the held-out pair).  LOO must reject, and the near-solve
    record must now carry the fold-divergence trace next to the full-data
    program so the expression miner can diff them."""
    pairs = [
        _recolor_pair(2, 7, size=2),
        _recolor_pair(3, 7, size=3),
        _recolor_pair(5, 9, size=4),
    ]
    res = induce_program(pairs, InductionConfig(budget_s=60))
    assert not res.accepted
    assert res.failure_stage == FailureStage.LOO
    assert res.near_solve is not None
    div = res.near_solve.residual.get("loo_divergence")
    assert div, "LOO near-solve must carry the divergence trace"
    assert res.near_solve.program_partial is not None
    # every trace entry names its fold and is JSON-plain
    import json
    json.dumps(div)
    assert {t["fold"] for t in div} <= {0, 1, 2}
    # at least one fold reinduced a program (the wrong-constant or keyless
    # map) — the miner's raw material
    assert any(t["fold_program"] is not None for t in div)
