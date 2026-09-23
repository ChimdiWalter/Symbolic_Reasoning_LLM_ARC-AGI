"""Round-10 panel/reduction family forcing tests.

The eval framing census: 26/84 uncovered eval tasks (and ~196 unsolved
training tasks) synthesize a small output from panel structure.  These
tests pin the three contract points: (1) cellwise truth-table programs
(XOR-of-panels) certify through the full LOO gate; (2) select-panel
programs (pick the unique panel) certify at RELATIONAL class; (3) the
family never fires outside the strict-shrink regime.
"""
import random

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.inducer import (InductionConfig,
                                                 induce_program)
from geocat_arc.object_reasoning.reduction import (
    induce_reduction_candidates)
from geocat_arc.object_reasoning.types import (ParameterClass,
                                               ReductionProgram)


def _xor_pair(rng, h=4, w=4, sep=5, a_col=3, b_col=2):
    """Two h x w panels separated by a full `sep` column; output cell = 4
    where exactly one panel is on.  Every truth-table key appears in every
    pair (so each LOO fold re-derives the identical table)."""
    while True:
        A = [[a_col if rng.random() < 0.5 else 0 for _ in range(w)]
             for _ in range(h)]
        B = [[b_col if rng.random() < 0.5 else 0 for _ in range(w)]
             for _ in range(h)]
        keys = {(A[r][c] != 0, B[r][c] != 0)
                for r in range(h) for c in range(w)}
        if len(keys) == 4:
            break
    gi = [A[r] + [sep] + B[r] for r in range(h)]
    go = [[4 if (A[r][c] != 0) != (B[r][c] != 0) else 0
           for c in range(w)] for r in range(h)]
    return Grid.from_list(gi), Grid.from_list(go)


def test_xor_panels_certifies_through_loo():
    rng = random.Random(7)
    pairs = [_xor_pair(rng) for _ in range(4)]
    res = induce_program(pairs, InductionConfig(budget_s=60))
    assert res.accepted, (res.failure_stage,
                          res.loo and res.loo.failed_pair_indices)
    assert isinstance(res.program, ReductionProgram)
    assert res.program.mode == "cellwise"
    assert res.loo.all_passed
    # unseen transfer
    ti, to = _xor_pair(rng)
    assert render_program(res.program, ti).to_list() == to.to_list()


def test_select_unique_panel_certifies_relational():
    """Three stacked panels (equal split, no separator): two identical, one
    unique; output = the unique panel.  Closed-vocabulary criterion ->
    RELATIONAL parameter class."""
    rng = random.Random(11)

    def make():
        base = [[rng.choice((0, 6)) for _ in range(5)] for _ in range(3)]
        base[0][0], base[1][2] = 6, 0        # pin two cells
        # unique panel = SAME palette and cell counts, different arrangement
        # -> most_colors / most_nonbg tie out; only unique_pattern fits
        other = [row[:] for row in base]
        other[0][0], other[1][2] = 0, 6
        order = rng.randrange(3)
        panels = [base, base, other]
        panels[2], panels[order] = panels[order], panels[2]
        gi = [row for p in panels for row in p]
        return Grid.from_list(gi), Grid.from_list(other)

    pairs = [make() for _ in range(4)]
    res = induce_program(pairs, InductionConfig(budget_s=60))
    assert res.accepted, (res.failure_stage,)
    assert isinstance(res.program, ReductionProgram)
    assert res.program.mode == "select_panel"
    assert res.program.params["criterion"] == "unique_pattern"
    assert res.program.worst_parameter_class is ParameterClass.RELATIONAL
    ti, to = make()
    assert render_program(res.program, ti).to_list() == to.to_list()


def test_reduction_never_fires_outside_strict_shrink():
    same = [(Grid.from_list([[1, 0], [0, 0]]),
             Grid.from_list([[0, 1], [0, 0]]))] * 3
    assert induce_reduction_candidates(same) == []
    grow = [(Grid.from_list([[1]]), Grid.from_list([[1, 1], [1, 1]]))] * 3
    assert induce_reduction_candidates(grow) == []


def test_reduction_program_round_trip_and_accounting():
    import json
    from geocat_arc.object_reasoning.types import program_from_dict
    p = ReductionProgram(split={"kind": "equal", "rows": 2, "cols": 1},
                         mode="cellwise",
                         params={"table": {"(True, False)": "@panel0",
                                           "(False, False)": 0}})
    back = program_from_dict(json.loads(json.dumps(p.to_dict())))
    assert isinstance(back, ReductionProgram)
    assert back.to_dict() == p.to_dict()
    assert p.value_bound_count == 1          # only the literal 0 is bound
    assert p.worst_parameter_class is ParameterClass.INDUCED_MAP


def test_cellwise_color_resolves_color_dependent_combination():
    """v2: two panels side-by-side; when BOTH cells are on with the SAME
    color -> keep that color; when on with DIFFERENT colors -> output 7.
    Binary keying maps (True, True) to a single value and cannot
    distinguish same-color-on from different-color-on — cellwise_color
    must pick up the full tuple.  Every color key appears in ALL 4 pairs
    so each LOO fold re-derives the identical table."""
    from geocat_arc.object_reasoning.reduction import (
        induce_reduction_candidates)

    # deterministic layout: each row has a fixed color pair, every pair
    # shows all combos — LOO-stable by construction
    ROWS = [(0, 0), (3, 0), (0, 5), (3, 5), (3, 3), (5, 5)]

    def make(h=6, w=1, sep=8):
        A = [[a] for a, _ in ROWS]
        B = [[b] for _, b in ROWS]
        gi = [A[r] + [sep] + B[r] for r in range(h)]
        go = [[0] for _ in range(h)]
        for r in range(h):
            a, b = ROWS[r]
            if a == 0 and b == 0:
                go[r][0] = 0
            elif a == 0 or b == 0:
                go[r][0] = a or b           # pass the non-bg through
            elif a == b:
                go[r][0] = a
            else:
                go[r][0] = 7                # different colors -> 7
        return Grid.from_list(gi), Grid.from_list(go)

    pairs = [make() for _ in range(4)]      # identical, but LOO-safe
    cands = induce_reduction_candidates(pairs)
    color_cands = [c for c in cands if c.mode == "cellwise_color"]
    assert color_cands, "cellwise_color candidate must be emitted"
    # binary cellwise should FAIL (True,True maps to both 3 and 7)
    binary_cands = [c for c in cands if c.mode == "cellwise"]
    assert not binary_cands, "binary cellwise must conflict on (True,True)"
    res = induce_program(pairs, InductionConfig(budget_s=60))
    assert res.accepted, (res.failure_stage,)
    assert isinstance(res.program, ReductionProgram)
    assert res.program.mode == "cellwise_color"


def test_overlay_first_certifies():
    """v2 overlay: first non-bg panel value wins."""
    def make(rng, h=4, w=4, sep=9):
        A = [[rng.choice((0, 2)) for _ in range(w)] for _ in range(h)]
        B = [[rng.choice((0, 6)) for _ in range(w)] for _ in range(h)]
        gi = [A[r] + [sep] + B[r] for r in range(h)]
        go = [[A[r][c] if A[r][c] != 0 else B[r][c]
               for c in range(w)] for r in range(h)]
        return Grid.from_list(gi), Grid.from_list(go)

    rng = random.Random(77)
    pairs = [make(rng) for _ in range(4)]
    res = induce_program(pairs, InductionConfig(budget_s=60))
    assert res.accepted, (res.failure_stage,)
    assert isinstance(res.program, ReductionProgram)
    assert res.program.mode == "overlay_first"
    ti, to = make(rng)
    assert render_program(res.program, ti).to_list() == to.to_list()
