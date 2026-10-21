"""ncv2-g4 first slice (engineering): sub-object parts, the part/ray layer's parity with native, the inversion engine
(selector induction over native's full test grammar, group inversion, composition, parameter leave-one-out),
construction of part, region and ray rules (don't-care selectors, covers, partial inversion programs), g4-readable
selection features, and the g4 search (budget accounting, correctness, determinism).

Only DEV-style tasks are used: hand-made grids, ncv2-g2 DEV families and test-local programs. Expected outputs are
compared here, after each search returns; no solver reads them.
"""
import os
import sys
import zlib

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_neural_v2.rast import N                                        # noqa: E402
from cora_neural_v2g2 import families as F                               # noqa: E402
from cora_neural_v2g2 import grammar as G                                # noqa: E402
from cora_neural_v2g3 import scene as SC                                 # noqa: E402
from cora_neural_v2g4 import construct as C                             # noqa: E402
from cora_neural_v2g4 import invert as INV                               # noqa: E402
from cora_neural_v2g4 import parts as PT                                 # noqa: E402
from cora_neural_v2g4 import program as PG                               # noqa: E402
from cora_neural_v2g4 import search as S4                                # noqa: E402
from cora_neural_v2g4 import select as SEL4                              # noqa: E402


def make(src, scene, seed, n=3, n_tests=1):
    prog = G.parse(src)
    rng = np.random.default_rng(zlib.crc32(f"{src}|{seed}".encode()))
    pairs = []
    for _ in range(400):
        g = scene(rng)
        if g is None:
            continue
        out = G.execute(prog, g)
        if out is None or np.array_equal(out, g):
            continue
        pairs.append((g.tolist(), out.tolist()))
        if len(pairs) == n + n_tests:
            break
    assert len(pairs) == n + n_tests
    return {"train": pairs[:n], "test_inputs": [p[0] for p in pairs[n:]]}, [np.asarray(p[1]) for p in pairs[n:]]


CASES = {
    "relational_recolour": (F.FAMILIES["relational_feature_recolour"][1], F.scene_lines_and_blobs),
    "two_rule": (F.P("(rule (test has_hole == #t) (delete)) (rule (test is_line == #t) (recolor (color 6)))"), F.scene_mixed),
    "ne_scaled_move": (F.P("(rule (test color != 8) (translate (scaled up (feature size))))"),
                       lambda r: F.scene_parts(r, [("dot", 8), ("domino", 3), ("dot", 2), ("ell", 4)], (12, 12))),
    "exists_above": (F.P("(rule (exists above (test color == 2)) (recolor (color 5)))"), lambda r: F.scene_dots(r, (2, 3))),
}


# ------------------------------------------------------------------ parts
def test_parts_of_a_filled_square_a_ring_and_a_line():
    G_ = np.zeros((7, 9), dtype=int)
    G_[1:4, 1:4] = 2                                                     # 3x3 square
    G_[1:4, 5:8] = 3
    G_[2, 6] = 0                                                         # ring with one hole
    G_[5, 1:5] = 4                                                       # line
    sq = {(r, c) for r in range(1, 4) for c in range(1, 4)}
    ring = {(r, c) for r in range(1, 4) for c in range(5, 8)} - {(2, 6)}
    line = {(5, c) for c in range(1, 5)}
    assert PT.part(sq, "interior", G_, 0) == {(2, 2)} and len(PT.part(sq, "border", G_, 0)) == 8
    assert PT.part(sq, "corners", G_, 0) == {(1, 1), (1, 3), (3, 1), (3, 3)}
    assert PT.part(ring, "holes", G_, 0) == {(2, 6)} and PT.part(sq, "holes", G_, 0) == frozenset()
    assert PT.part(line, "endpoints", G_, 0) == {(5, 1), (5, 4)}
    assert PT.part(ring, "bbox_background", G_, 0) == {(2, 6)}


@pytest.mark.parametrize("seed", range(5))
def test_whole_part_recolour_matches_native_recolour(seed):
    sel = N("test", ("is_line", "==", True))
    rng = np.random.default_rng(seed)
    g = None
    while g is None:
        g = F.scene_mixed(rng)
    native = G.execute(G.parse(F.P("(rule (test is_line == #t) (recolor (color 7)))")), g.tolist())
    mine = PG.execute(PG.make("S1", None, [PG.PartRule(sel, "whole", 7)]), g.tolist())
    assert np.array_equal(native, mine)


def test_rays_stop_at_obstacles_or_run_through():
    A = np.zeros((3, 8), dtype=int)
    A[1, 1] = 2
    A[1, 5] = 3
    assert PG.ray_cells({(1, 1)}, ((0, 1),), "obstacle", A, 0) == {(1, 2), (1, 3), (1, 4)}
    assert PG.ray_cells({(1, 1)}, ((0, 1),), "through", A, 0) == {(1, 2), (1, 3), (1, 4), (1, 6), (1, 7)}


# ------------------------------------------------------------------ inversion
@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("seed", [0, 1])
def test_inversion_constructs_the_correct_program_early(name, seed):
    src, scene = CASES[name]
    task, (ans,) = make(src, scene, seed)
    cands = [p for p, _ in INV.invert(task)]
    correct = [i for i, p in enumerate(cands) if G.fit(p, task["train"])[0]
               and np.array_equal(G.execute(p, task["test_inputs"][0]), ans)]
    assert correct and correct[0] <= 3


def test_induced_selectors_are_exact_under_native_execution():
    task, _ = make(*CASES["ne_scaled_move"], 2)
    sc = SC.analyse(task["train"], "S1")
    tables = INV.feature_tables(task["train"], "S1")
    tests = INV.single_tests(tables)
    for key, members in sc.groups.items():
        sels = INV.induce_selectors("S1", task["train"], tables, tests, members)
        picks = SC.selections("S1", sels, task["train"])
        assert all(SC.separation(picks[s], members)[0] for s in sels)


def test_rederivation_of_a_stable_rule():
    task, _ = make(*CASES["exists_above"], 0, n=4)
    prog = G.parse(CASES["exists_above"][0])
    assert INV.rederived(task, [prog])[prog] == pytest.approx(1.0)


# ------------------------------------------------------------------ the g4 search
def test_g4_search_budget_correctness_and_head():
    task, (ans,) = make(*CASES["two_rule"], 3)
    r = S4.search(task, 1000)
    assert r["n_candidates"] <= 1000 and r["head"]["evaluated"] <= 300
    assert r["first_fit_at"] is not None and r["first_fit_at"] <= r["head"]["evaluated"]
    assert any(np.array_equal(np.asarray(a), ans) for a in r["attempts"])


def test_g4_search_is_deterministic():
    task, _ = make(*CASES["relational_recolour"], 4)
    a, b = S4.search(task, 600), S4.search(task, 600)
    a.pop("cpu_s")
    b.pop("cpu_s")
    a["g3"].pop("state", None)
    b["g3"].pop("state", None)
    assert a == b


# ------------------------------------------------------------------ construction: part, region and ray rules
def T(f, cmp, v):
    return N("test", (f, cmp, v))


def scene_blocks(rng):
    g = np.zeros((12, 12), dtype=int)
    for _ in range(int(rng.integers(2, 4))):
        h, w = int(rng.integers(3, 5)), int(rng.integers(3, 6))
        r, c = int(rng.integers(0, 12 - h)), int(rng.integers(0, 12 - w))
        if not g[max(0, r - 1):r + h + 1, max(0, c - 1):c + w + 1].any():
            g[r:r + h, c:c + w] = int(rng.integers(1, 9))
    for _ in range(2):
        r, c = int(rng.integers(0, 12)), int(rng.integers(0, 12))
        if not g[max(0, r - 1):r + 2, max(0, c - 1):c + 2].any():
            g[r, c] = int(rng.integers(1, 9))
    return g


G4_CASES = {
    "border_of_rectangles": (PG.make("S1", None, [PG.PartRule(T("is_rectangle", "==", True), "border", 5)]), F.scene_mixed),
    "fill_holes_own_colour": (PG.make("S1", None, [PG.PartRule(N("true", ()), "holes", "own")]), F.scene_mixed),
    "hollow_blocks": (PG.make("S1", None, [PG.PartRule(T("size", ">=", 4), "interior", 0)]), scene_blocks),
    "ray_right_from_dots": (PG.make("S1", None, [PG.RayRule(T("size", "==", 1), ((0, 1),), "obstacle", "own")]),
                            lambda r: F.scene_dots(r, (2, 3))),
    "orthogonal_rays_through": (PG.make("S1", None, [PG.RayRule(T("color", "==", 2), PG.DIRS8[:4], "through", 4)]),
                                lambda r: F.scene_dots(r, (2, 3))),
    "endpoints_and_holes": (PG.make("S1", None, [PG.PartRule(T("is_line", "==", True), "endpoints", 6),
                                                 PG.PartRule(T("has_hole", "==", True), "holes", 3)]), F.scene_mixed),
    "move_then_fill": (PG.make("S1", G.parse(F.P("(rule (test color == 8) (translate (vec 0 1)))")),
                               [PG.PartRule(T("has_hole", "==", True), "holes", 3)]),
                       lambda r: F.scene_parts(r, [("dot", 8), ("ring", 2), ("ell", 4), ("dot", 8)], (11, 11))),
}


def make_g4(prog, scene, seed, n=3):
    rng = np.random.default_rng(zlib.crc32(f"{prog}|{seed}".encode()))
    pairs = []
    for _ in range(400):
        g = scene(rng)
        if g is None:
            continue
        out = PG.execute(prog, g.tolist())
        if out is None or np.array_equal(out, g):
            continue
        pairs.append((g.tolist(), out.tolist()))
        if len(pairs) == n + 1:
            break
    assert len(pairs) == n + 1
    return {"train": pairs[:n], "test_inputs": [pairs[n][0]]}, np.asarray(pairs[n][1])


@pytest.mark.parametrize("name", sorted(G4_CASES))
@pytest.mark.parametrize("seed", [0, 1])
def test_construction_puts_a_correct_program_early(name, seed):
    task, ans = make_g4(*G4_CASES[name], seed)
    progs = C.programs(task)
    correct = [i for i, p in enumerate(progs) if PG.fits(p, task["train"])
               and np.array_equal(PG.execute(p, task["test_inputs"][0]), ans)]
    assert correct and correct[0] <= 2


@pytest.mark.parametrize("name", ["border_of_rectangles", "ray_right_from_dots", "endpoints_and_holes"])
def test_constructed_rules_change_exactly_their_cover_and_break_nothing(name):
    task, _ = make_g4(*G4_CASES[name], 0)
    for cand in C.candidates(task["train"], "S1"):
        for rule in cand.rules:
            for d, cov in zip(PG.deltas(PG.make("S1", None, [rule]), task["train"]), cand.cover):
                assert d.shape_ok and int(d.broken.sum()) == 0
                assert set(zip(*np.nonzero(d.fixed))) == set(cov)


def test_dont_care_objects_admit_the_simple_selector():
    """A colour-2 dot at the right edge has an empty ray: it may be picked or not, so (test color == 2) is exact."""
    truth = PG.make("S1", None, [PG.RayRule(T("color", "==", 2), ((0, 1),), "obstacle", 2)])
    inputs = []
    for dots in ([(1, 1, 2), (3, 6, 2), (5, 2, 3)], [(2, 0, 2), (4, 4, 3), (6, 3, 2)], [(0, 3, 2), (2, 5, 3), (5, 6, 2)]):
        g = np.zeros((7, 7), dtype=int)
        for r, c, k in dots:
            g[r, c] = k
        inputs.append(g.tolist())
    task = {"train": [(g, PG.execute(truth, g).tolist()) for g in inputs], "test_inputs": [inputs[0]]}
    first = C.programs(task)[0]
    assert first.rules[0].sel == T("color", "==", 2) and first.rules[0].dirs == ((0, 1),)


def test_g4_selection_reads_g4_programs():
    sel = T("is_line", "==", True)
    native = G.parse(F.P("(rule (test is_line == #t) (recolor (color 7)))"))
    mine = PG.make("S1", None, [PG.PartRule(sel, "whole", 7)])
    assert SEL4.description_length(mine) == SEL4.description_length(native)
    both = PG.make("S1", native, [PG.PartRule(sel, "border", 3)])
    assert SEL4.n_rules(both) == 2 and SEL4.family(both)[0] == "g4" and "border" in SEL4.family(both)


def test_g4_search_finds_a_part_level_answer():
    task, ans = make_g4(*G4_CASES["hollow_blocks"], 0)
    r = S4.search(task, 600)
    assert r["fit_origins"].get("g4_construct", 0) >= 1
    assert any(np.array_equal(np.asarray(a), ans) for a in r["attempts"])
