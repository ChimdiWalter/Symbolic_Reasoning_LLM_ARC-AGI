"""Round-5 lever 1: the in_set disjunctive selector spelling.

From the selector census: ~90% of failed selector groups are separable by
an existing feature's VALUE SET but no grammar spelling existed.  in_set
is induced from the group members (color_map-style), priced at one bound
literal per element, and only proposed when no grammar predicate fits.
"""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.expressions import PredExpr, EvalContext
from geocat_arc.object_reasoning.inducer import (induce_program,
                                                 InductionConfig,
                                                 _expr_value_bound_count)
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.types import DeltaType


def test_in_set_literals_and_bound_count():
    p = PredExpr(op="in_set", args=("color", (2, 4, 7)))
    assert p.literals == 3
    assert _expr_value_bound_count(p) == 3
    single = PredExpr(op="test", args=("color", "==", 2))
    assert single.literals < p.literals   # single tests always outrank


def test_in_set_serialization_round_trip():
    import json
    from geocat_arc.object_reasoning.types import Expr
    p = PredExpr(op="in_set", args=("color", (2, 4)))
    back = Expr.from_dict(json.loads(json.dumps(p.to_dict())))
    assert back == p


def _pairs(specs):
    return [(Grid.from_list(i), Grid.from_list(o)) for i, o in specs]


def test_induce_value_set_selector_task():
    """Colors {2,4,6} move right 1; colors {3,5,8} stay.  A single test
    cannot select the movers, and the complement needs THREE negations —
    beyond the depth-2 conjunction grammar — so in_set({2,4,6}) is the
    ONLY expressible zero-conflict selector.  The set is stable across
    pairs, so LOO folds re-derive it identically."""
    def make(rows, h=8, w=6):
        # rows: dict color -> row index; movers {2,4,6}, keepers {3,5,8}
        gi = [[0] * w for _ in range(h)]
        go = [[0] * w for _ in range(h)]
        for col, r in rows.items():
            gi[r][1] = col
            if col in (2, 4, 6):
                go[r][2] = col
            else:
                go[r][1] = col
        return gi, go

    # 4 pairs, movers/keepers interleaved by row so positional/rank
    # features cannot spuriously separate them on any 3-pair fold subset
    pairs = _pairs([
        make({2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 8: 5}),
        make({3: 0, 2: 1, 5: 2, 4: 3, 8: 4, 6: 5}),
        make({2: 0, 5: 1, 6: 2, 3: 3, 4: 4, 8: 5}),
        make({8: 0, 4: 1, 3: 2, 6: 3, 5: 4, 2: 5}),
    ])
    res = induce_program(pairs, InductionConfig(budget_s=60))
    assert res.program is not None, res.failure_stage
    assert res.loo.passed == res.loo.folds == 4
    # the mover rule must use in_set (no single test can separate {2,4})
    ops = {r.selector.predicate.op for r in res.program.rules}
    assert "in_set" in ops, ops
    gi, go = _pairs([make({2: 3, 4: 5, 6: 1, 3: 0, 5: 2, 8: 7})])[0]
    assert render_program(res.program, gi).to_list() == go.to_list()
