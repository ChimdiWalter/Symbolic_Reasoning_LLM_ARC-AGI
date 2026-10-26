"""Rule-language version 5 (L1 engineering extension of version 4): parity of its executor with version 4 on version
4 rules; the new rules' semantics on hand-made grids; construction correctness, safety and determinism on DEV-style
generated tasks; the version 5 search's budget accounting. No evaluation data is used.
"""
import os
import sys
import zlib

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cora_neural_v2.rast import N                                        # noqa: E402
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g4 import program as PG                               # noqa: E402
from cora_neural_v2g5 import construct as C5                             # noqa: E402
from cora_neural_v2g5 import program as P5                               # noqa: E402
from cora_neural_v2g5 import search as S5                                # noqa: E402
from cora_neural_v2g5 import select as SEL5                              # noqa: E402
from g5_generators import CASES, T, TRUE, make_task                     # noqa: E402


def seeded(name, seed):
    return zlib.crc32(f"{name}{seed}".encode())


# ------------------------------------------------------------------ parity with version 4
@pytest.mark.parametrize("seed", range(5))
def test_version4_rules_execute_identically(seed):
    rng = np.random.default_rng(seed)
    g = None
    while g is None:
        g = F.scene_mixed(rng)
    for rules in ([PG.PartRule(T("is_line", "==", True), "border", 7)], [PG.PartRule(TRUE, "holes", "own")],
                  [PG.RayRule(T("size", "==", 1), ((0, 1), (1, 0)), "obstacle", 4)],
                  [PG.RayRule(TRUE, PG.DIRS8[:4], "through", "own"), PG.PartRule(TRUE, "corners", 9)]):
        a = PG.execute(PG.make("S1", None, rules), g.tolist())
        b = P5.execute(P5.make("S1", None, rules), g.tolist())
        assert (a is None and b is None) or np.array_equal(a, b)


# ------------------------------------------------------------------ the new rules on hand-made grids
def test_ray_turns_clockwise_at_an_obstacle():
    A = np.zeros((5, 5), dtype=int)
    A[4, 2] = 3                                                          # the dot
    A[1, 2] = 5                                                          # the obstacle above it
    out = P5.execute(P5.make("S1", None, [P5.Ray2Rule(T("color", "==", 3), ((-1, 0),), "turn_cw", "none", "own")]), A.tolist())
    assert out[3, 2] == 3 and out[2, 2] == 3 and out[2, 3] == 3 and out[2, 4] == 3 and out[1, 2] == 5


def test_ray_paints_the_obstacle_it_hits():
    A = np.zeros((3, 6), dtype=int)
    A[1, 0] = 2
    A[1, 4] = 5
    out = P5.execute(P5.make("S1", None, [P5.Ray2Rule(T("color", "==", 2), ((0, 1),), "stop", "cell", "own")]), A.tolist())
    assert list(out[1]) == [2, 2, 2, 2, 2, 0]


def test_stamp_by_marker_and_segment_and_fills():
    A = np.zeros((9, 9), dtype=int)
    A[0:3, 0:3] = 2
    A[1, 1] = 5                                                          # a ring of 2 with a colour-5 marker inside
    A[6, 6] = 5                                                          # an anchor of colour 5
    out = P5.execute(P5.make("S1", None, [P5.StampRule(T("color", "==", 2), T("color", "==", 5), "box", "marker", "keep")]),
                     A.tolist())
    assert (out[5:8, 5:8] == A[0:3, 0:3]).all()
    B = np.zeros((5, 7), dtype=int)
    B[2, 0] = B[2, 6] = 4
    seg = P5.execute(P5.make("S1", None, [P5.SegmentRule(TRUE, "h", "own")]), B.tolist())
    assert list(seg[2]) == [4] * 7
    C = np.zeros((6, 6), dtype=int)
    C[1, 2:4] = 1; C[4, 2:4] = 1; C[2:4, 1] = 1; C[2:4, 4] = 1           # four bars closing a 2x2 hole
    fill = P5.execute(P5.make("S1", None, [P5.FillRule(TRUE, "enclosed", 8)]), C.tolist())
    assert (fill[2:4, 2:4] == 8).all() and fill[0, 0] == 0


# ------------------------------------------------------------------ construction
@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("seed", [1, 2])
def test_construction_puts_a_correct_program_early(name, seed):
    prog, scene = CASES[name]
    task, ans = make_task(prog, scene, seeded(name, seed))
    assert task is not None
    progs = C5.programs(task)
    correct = [i for i, p in enumerate(progs) if P5.fits(p, task["train"])
               and np.array_equal(P5.execute(p, task["test_inputs"][0]), ans)]
    assert correct and correct[0] <= 2


@pytest.mark.parametrize("name", sorted(CASES))
def test_constructed_rules_write_only_cells_the_output_has(name):
    prog, scene = CASES[name]
    task, _ = make_task(prog, scene, seeded(name, 1))
    for cand in C5.candidates(task["train"], "S1"):
        for rule in cand.rules:
            for (a, b), cov in zip(task["train"], cand.cover):
                A, B = np.asarray(a), np.asarray(b)
                W = P5.rule_writes(rule, "S1", A)
                assert all(B[x] == v for x, v in W.items())
                assert {x for x, v in W.items() if A[x] != v} == set(cov)


def test_construction_is_deterministic_and_programs_render():
    prog, scene = CASES["segments_between_pairs"]
    task, _ = make_task(prog, scene, seeded("segments_between_pairs", 1))
    a, b = C5.programs(task), C5.programs(task)
    assert a == b and all(C5.sexpr(p).startswith("(g5program") for p in a)
    assert SEL5.n_rules(a[0]) == len(a[0].rules) and SEL5.family(a[0])[0] == "g5"


def test_g5_search_budget_and_answer():
    prog, scene = CASES["fill_enclosed_by_bars"]
    task, ans = make_task(prog, scene, seeded("fill_enclosed_by_bars", 1))
    r = S5.search(task, 600)
    assert r["n_candidates"] <= 600 and r["head"]["evaluated"] <= 180
    assert r["fit_origins"].get("g5_construct", 0) >= 1
    assert any(np.array_equal(np.asarray(x), ans) for x in r["attempts"])
