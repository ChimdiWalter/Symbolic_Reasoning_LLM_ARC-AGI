"""Round-9 lever 1: the feature_affine relational color spelling.

Mined from the LOO fold-divergence corpus (outputs/param_expr_mining.json):
recolor.color is the top parameter-divergence target (15 tasks), and the
recurring shape is an ordinal recolor memorized as a feature_map whose
entries drift or go missing under N-1-pair reinduction (e.g. 08ed6ac7:
size_rank -> {0:1, 1:2, 2:3, ...} — literally color = rank + 1).
feature_affine spells color = feature + offset with ONE bound literal, so
it re-derives identically from any subset.
"""
import json

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.expressions import (ColorExpr, EvalError,
                                                     parameter_class_of)
from geocat_arc.object_reasoning.inducer import (InductionConfig,
                                                 _expr_value_bound_count,
                                                 induce_program)
from geocat_arc.object_reasoning.types import Expr, ParameterClass


def test_feature_affine_accounting_and_round_trip():
    e = ColorExpr(op="feature_affine", args=("size", -1))
    assert _expr_value_bound_count(e) == 1
    assert parameter_class_of(e) is ParameterClass.FEATURE
    back = Expr.from_dict(json.loads(json.dumps(e.to_dict())))
    assert back == e
    # a 4-entry map costs 4 bound values — affine must outrank it
    from geocat_arc.object_reasoning.expressions import make_feature_map
    m = make_feature_map("size", {2: 1, 3: 2, 4: 3, 5: 4})
    assert _expr_value_bound_count(m) == 4


def _pair(sizes, h=9, w=12):
    """Two horizontal bars of the given sizes; output recolors each bar to
    (size - 1)."""
    gi = [[0] * w for _ in range(h)]
    go = [[0] * w for _ in range(h)]
    for i, s in enumerate(sizes):
        r = 2 + 3 * i
        for k in range(s):
            gi[r][1 + k] = 8            # 8 never equals any target (size-1)
            go[r][1 + k] = s - 1
    return Grid.from_list(gi), Grid.from_list(go)


def test_induce_affine_recolor_certifies_where_map_starves():
    """color = size - 1 with every feature value UNIQUE to its pair: any
    feature_map induced from N-1 pairs lacks the held-out pair's keys
    (EvalError per fold), so before feature_affine this family died at LOO.
    The affine spelling re-derives (offset -1) from every subset and must
    certify."""
    pairs = [_pair((2, 3)), _pair((4, 6)), _pair((5, 7))]
    res = induce_program(pairs, InductionConfig(budget_s=60))
    assert res.accepted, (res.failure_stage, res.loo)
    assert res.loo is not None and res.loo.all_passed
    # the accepted program must actually use the relational spelling —
    # its worst parameter class can be no worse than FEATURE
    assert res.program.worst_parameter_class.rank <= \
        ParameterClass.FEATURE.rank
