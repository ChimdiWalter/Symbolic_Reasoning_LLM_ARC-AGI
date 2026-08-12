"""Round-12 symmetry completion tests."""
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.symmetry import (
    induce_symmetry_completion, render_symmetry_completion)


def test_4fold_symmetry_completion():
    """11852cab pattern: diamond with one corner missing -> fill it."""
    gi = Grid.from_list([
        [0, 0, 0, 0, 0],
        [0, 2, 0, 3, 0],
        [0, 0, 4, 0, 0],
        [0, 3, 0, 0, 0],  # missing (3,3) = 2
        [0, 0, 0, 0, 0],
    ])
    go = Grid.from_list([
        [0, 0, 0, 0, 0],
        [0, 2, 0, 3, 0],
        [0, 0, 4, 0, 0],
        [0, 3, 0, 2, 0],  # filled
        [0, 0, 0, 0, 0],
    ])
    prog = induce_symmetry_completion([(gi, go)])
    assert prog is not None
    out = render_symmetry_completion(prog, gi)
    assert out.to_list() == go.to_list()


def test_horizontal_reflection_completion():
    """Left side present, right side partially missing."""
    gi = Grid.from_list([
        [0, 0, 0, 0, 0],
        [0, 3, 0, 0, 0],
        [0, 5, 0, 5, 0],
        [0, 3, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ])
    go = Grid.from_list([
        [0, 0, 0, 0, 0],
        [0, 3, 0, 3, 0],
        [0, 5, 0, 5, 0],
        [0, 3, 0, 3, 0],
        [0, 0, 0, 0, 0],
    ])
    prog = induce_symmetry_completion([(gi, go)])
    assert prog is not None
    assert prog["symmetry"] in ("horizontal", "4fold")
    out = render_symmetry_completion(prog, gi)
    assert out.to_list() == go.to_list()


def test_no_symmetry_returns_none():
    """Random changes should not match any symmetry."""
    gi = Grid.from_list([[1, 0], [0, 2]])
    go = Grid.from_list([[1, 3], [4, 2]])
    prog = induce_symmetry_completion([(gi, go)])
    assert prog is None
