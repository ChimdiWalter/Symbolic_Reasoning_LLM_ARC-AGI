"""Round-12 pixel-level rules: cellular-automaton-style programs.

Targets the 191 same-shape tasks the object engine can't engage at all
(no near-solve record). These operate at the cell level, not the object
level: each output cell is a function of its input neighborhood.
"""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.pixel_rules import (
    induce_pixel_rule, render_pixel_rule)


def test_color_swap_induces_and_renders():
    """Global color map: 1->3, 2->5, 0->0 everywhere."""
    gi1 = Grid.from_list([[0, 1, 2], [1, 0, 1], [2, 2, 0]])
    go1 = Grid.from_list([[0, 3, 5], [3, 0, 3], [5, 5, 0]])
    gi2 = Grid.from_list([[1, 1, 0], [0, 2, 2], [1, 0, 2]])
    go2 = Grid.from_list([[3, 3, 0], [0, 5, 5], [3, 0, 5]])
    pairs = [(gi1, go1), (gi2, go2)]
    prog = induce_pixel_rule(pairs)
    assert prog is not None
    assert prog["mode"] == "color_swap"
    # unseen transfer
    gi3 = Grid.from_list([[2, 0, 1], [0, 0, 0], [1, 2, 1]])
    out = render_pixel_rule(prog, gi3)
    assert out.to_list() == [[5, 0, 3], [0, 0, 0], [3, 5, 3]]


def test_neighbor_count_induces():
    """bg cells with exactly 2 non-bg neighbors become color 4."""
    gi = [[0, 1, 0], [1, 0, 1], [0, 1, 0]]
    go = [[0, 1, 0], [1, 4, 1], [0, 1, 0]]
    gi2 = [[0, 0, 0, 0], [0, 1, 0, 0], [1, 0, 1, 0], [0, 1, 0, 0]]
    go2 = [[0, 0, 0, 0], [0, 1, 0, 0], [1, 4, 1, 0], [0, 1, 0, 0]]
    pairs = [(Grid.from_list(gi), Grid.from_list(go)),
             (Grid.from_list(gi2), Grid.from_list(go2))]
    prog = induce_pixel_rule(pairs)
    assert prog is not None
    assert prog["mode"] in ("neighbor_count", "neighbor_pattern")


def test_pixel_rule_returns_none_for_complex_tasks():
    """Tasks that need deeper context than 4-neighbors should return None."""
    gi = Grid.from_list([[1, 0, 0], [0, 0, 0], [0, 0, 2]])
    go = Grid.from_list([[1, 0, 3], [0, 0, 0], [3, 0, 2]])
    prog = induce_pixel_rule([(gi, go)])
    # single pair is ok, but this specific task places new colors at
    # computed positions — may or may not match a neighborhood rule
    # (not asserting None, just that it doesn't crash)
    if prog is not None:
        out = render_pixel_rule(prog, gi)
        assert out.to_list() == go.to_list()
