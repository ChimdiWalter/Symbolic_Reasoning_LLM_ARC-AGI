"""Randomized larger-grid property tests of every contract through the contract-checker API (quick level: tiny
exhaustive part plus structured random grids up to 20 x 20 on random backgrounds), and a negative control: the
checker must catch a deliberately unsound contract."""
import numpy as np
import pytest

from cast import absdom as D
from cast import contract_check as CC
from cast import ops as O
from cast import symmetry as S

OPS = list(O.L0) + [S.SymComplete()]


@pytest.mark.parametrize("op", OPS, ids=lambda o: o.name)
def test_quick_contract_check(op):
    rep = CC.check_operator(op, level="quick", seed=1)
    assert rep["verdict"] == "PASS", rep["checks"]
    # partial operators are defined on few random grids even with their samplers (declared thin coverage)
    assert rep["checks"]["random_fwd"]["cases"] >= {"down": 8, "symcomplete": 10}.get(op.name, 20)


class _UnsoundRecolor(O.Recolor):
    """Claims the palette is unchanged (false: colour b may appear)."""
    name = "unsound_recolor"

    def fwd(self, x, th):
        return x.copy()


def test_checker_catches_an_unsound_contract():
    rep = CC.check_operator(_UnsoundRecolor(), level="quick", seed=2)
    assert rep["verdict"] == "FAIL"
    assert rep["checks"]["fwd_concrete"]["violations"] > 0


def test_true_rule_that_changes_hole_count_is_not_rejected():
    # directive s.16: no blanket topology invariant; fill_enclosed removes a hole and its contract admits it
    x = np.zeros((6, 6), dtype=np.int64)                    # background 0 is the majority colour
    x[1:4, 1:4] = 1
    x[2, 2] = 0                                              # one enclosed background cell: a hole
    y = O.FillEnclosed().apply(x, (2,))
    assert y[2, 2] == 2
    assert D.contains(O.FillEnclosed().fwd(D.alpha(x), (2,)), y)
