"""CORA × NVARC fusion layer: the no-op switch, the fixed policies, the explanation check and grid validation."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cora_funnel import run as FR                                      # noqa: F401,E402  (sealed flags)
from cora_neural_fusion.contract import Proposal, valid_grid          # noqa: E402
from cora_neural_fusion import policy as P                            # noqa: E402

A1, A2 = [[1, 2], [3, 4]], [[4, 3], [2, 1]]


def _analysis(cora_grids, verification="EXPLORATORY", cands=()):
    return {"candidates": list(cands),
            "cora": [Proposal(task="t", output_index=0, grid=g, source="CORA_BASE", executable=True,
                              verification=verification) for g in cora_grids]}


def test_n0_is_a_byte_identical_no_op():
    att = {"attempt_1": A1, "attempt_2": P.DEFAULT}
    out, prov = P.decide("N0", att, _analysis([A2]))
    assert out == att and prov["attempt_2"] == "NVARC_DEFAULT"


def test_fill_replaces_only_the_default_second_attempt():
    out, prov = P.decide("FILL_V1", {"attempt_1": A1, "attempt_2": P.DEFAULT}, _analysis([A2]))
    assert out == {"attempt_1": A1, "attempt_2": A2} and prov.get("replaced_default") is True
    out, prov = P.decide("FILL_V1", {"attempt_1": A1, "attempt_2": [[5]]}, _analysis([A2]))
    assert out["attempt_2"] == [[5]] and "replaced_default" not in prov          # a genuine attempt 2 is kept
    out, _ = P.decide("FILL_V1", {"attempt_1": A1, "attempt_2": P.DEFAULT}, _analysis([A1]))
    assert out["attempt_2"] == P.DEFAULT                                        # never a duplicate of attempt 1
    out, _ = P.decide("FILL_V1", {"attempt_1": A1, "attempt_2": P.DEFAULT}, None)
    assert out["attempt_2"] == P.DEFAULT                                        # CORA did not run: unchanged


def test_explain_policy_needs_an_explained_alternative():
    expl = Proposal(task="t", output_index=0, grid=[[7]], source="NVARC_BASE", rank=2, explained_by=[{"family": "grow"}],
                    executable=True, verification="DEMO_CONSISTENT")
    plain = Proposal(task="t", output_index=0, grid=A2, source="NVARC_BASE", rank=1)
    out, prov = P.decide("EXPLAIN_V1", {"attempt_1": A1, "attempt_2": A2}, _analysis([], cands=[plain, expl]))
    assert out["attempt_2"] == [[7]] and prov.get("replaced_genuine") is True
    out, _ = P.decide("FILL_V1", {"attempt_1": A1, "attempt_2": A2}, _analysis([], cands=[plain, expl]))
    assert out["attempt_2"] == A2                                               # FILL never touches a genuine attempt


def test_grid_validation():
    assert valid_grid([[0]]) and valid_grid(A1)
    for bad in ([], [[]], [[1, 2], [3]], [[10]], [[-1]], [["1"]], [[0] * 31]):
        assert not valid_grid(bad)
    with pytest.raises(AssertionError):
        Proposal(task="t", output_index=0, grid=[[12]], source="NVARC_BASE")


def test_explain_task_marks_the_demonstration_consistent_candidate():
    """Only colour-1 objects grow a ray east (the selection family's synthetic task). The right candidate is explained
    by a CORA hypothesis; a wrong candidate is not."""
    from cora_neural_fusion.explain import explain_task

    def mk(objs, H=8, W=10):
        A = np.zeros((H, W), int)
        for (r, c), v in objs:
            A[r, c] = v
        B = A.copy()
        for (r, c), v in objs:
            if v == 1:
                B[r, c + 1:] = np.where(B[r, c + 1:] == 0, v, B[r, c + 1:])
        return A.tolist(), B.tolist()
    train = [mk([((1, 2), 1), ((4, 5), 2), ((6, 1), 1)]), mk([((2, 4), 2), ((5, 3), 1)])]
    ti, to = mk([((0, 1), 1), ((3, 6), 2), ((7, 2), 1)])
    wrong = [row[:] for row in to]
    wrong[0][9] = 0
    res = explain_task("synthetic", train, [ti], [[wrong, to]])
    c_wrong, c_right = res["outputs"][0]["candidates"]
    assert c_right.explained_by and c_right.verification == "DEMO_CONSISTENT"
    assert not c_wrong.explained_by and c_wrong.verification == "UNVERIFIED"
