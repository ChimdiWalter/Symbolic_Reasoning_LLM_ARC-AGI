"""Regression test from the pre-run review: a program that does not settle must be scored, not stop the run.
Nodes a, r1 and r2 with r1 = a AND NOT r2 and r2 = r1. With a on, the synchronous dynamics cycle with period 4, so the
program never settles; with a off, it settles at all zeros.
Run: python3 -I tests/test_checker.py"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from t5.model import Design, Obs, Space, simulate, simulate_core  # noqa: E402
from t5.tasks import check_models  # noqa: E402


class _T:
    pass


def main():
    sp = Space(["a", "r1", "r2"], [("r1", (("a", 1), ("r2", -1))), ("r2", (("r1", 1),))], ["a"], [], ["r1", "r2"])
    assert sp.topo is None, "the space must be cyclic"
    d = Design(sp, [(1,), (0,)], [(), ()], ["a"], [])
    model = (1 << sp.H) - 1
    x1, na1 = simulate(sp, d, model)
    x2, na2 = simulate_core(sp, d, model)
    assert (x1, na1) == (x2, na2), "simulate and simulate_core disagree"
    t = _T()
    t.design, t.label = d, "regression|three-node"
    check_models(t, sp, [model])                                      # must not raise
    assert na1 is not None and any(na1), "the NA mask must not be empty"
    ix = sp.ix
    assert (na1[ix["r1"]] | na1[ix["r2"]]) & 1, "column 0 (a on) must carry an NA readout bit"
    assert not ((na1[ix["r1"]] | na1[ix["r2"]]) & 2), "column 1 (a off) settles"
    n_na = sum(((na1[ix[r]] >> 0) & 1) for r in ("r1", "r2"))
    for obs_row in ((0.0, 0.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0)):
        obs = Obs(sp, d, [obs_row, (0.0, 0.0)])
        e = obs.errors(x1, na1, 1)                                     # column 0 only
        assert e >= n_na, f"every NA bit must count as wrong (errors {e}, NA bits {n_na})"
    obs = Obs(sp, d, [(0.0, 0.0), (0.0, 0.0)])
    assert obs.errors(x1, na1, 2) == 0, "the settled column (all zeros) is right"
    print(f"ok: checker agrees on a non-settling program; NA bits in column 0: {n_na}; NA counted as wrong")


if __name__ == "__main__":
    main()
