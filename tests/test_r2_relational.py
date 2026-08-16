"""Tests for R2 (the relational rung): ray_relational generators and relift.

Part A tests the ray_relational generator kind in generative.py — rays whose
direction is computed relative to another object (toward/away/perpendicular).
Part B tests the relift pass (relift.py) that re-expresses constant parameters
as relational/feature expressions so overfitting programs generalize.

Written test-first: the implementation may not be complete, so Part A tests
may fail with KeyError/AttributeError on the missing generator kind, and
Part B tests are skipped when relift.py does not exist yet.
"""
import os

import numpy as np
import pytest

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject
from geocat_arc.object_reasoning.types import (
    GenerativeProgram,
    SegmentationVariant,
    ObjectProgram,
    ObjectRule,
    ActionRule,
    SelectorRule,
    DeltaType,
    ParameterClass,
    OutputSpec,
)
from geocat_arc.object_reasoning.expressions import (
    ColorExpr,
    VecExpr,
    PredExpr,
    parameter_class_of,
)
from geocat_arc.object_reasoning.generative import (
    render_generative,
    _apply_generator,
)

# Conditional imports for relift (Part B) — may not exist yet.
try:
    from geocat_arc.object_reasoning.relift import relift_program, ReliftResult
    HAS_RELIFT = True
except ImportError:
    HAS_RELIFT = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_object(cells, color, obj_id=1):
    """Build an ARCObject from a set/list of (r, c) tuples."""
    cells_fs = frozenset(cells)
    rows = [r for r, _ in cells_fs]
    cols = [c for _, c in cells_fs]
    bbox = (min(rows), min(cols), max(rows) + 1, max(cols) + 1)
    return ARCObject(id=obj_id, cells=cells_fs, color=color,
                     bounding_box=bbox)


def _grid_from_objects(objects, bg=0, h=10, w=10):
    """Build a Grid by painting objects onto a background."""
    arr = np.full((h, w), bg, dtype=np.int32)
    for obj in objects:
        for r, c in obj.cells:
            arr[r, c] = obj.color
    return Grid(arr)


# ---------------------------------------------------------------------------
# Part A — ray_relational generator
# ---------------------------------------------------------------------------

class TestRayRelationalTowardLargest:
    """Test 1: ray_relational with direction_mode='toward', target largest."""

    def _setup(self):
        # Small object (2 cells, color 3) at top-left
        small = _make_object([(0, 0), (0, 1)], color=3, obj_id=1)
        # Large object (6 cells, color 5) at bottom-right
        large = _make_object([(7, 7), (7, 8), (7, 9),
                              (8, 7), (8, 8), (8, 9)], color=5, obj_id=2)
        grid = _grid_from_objects([small, large], bg=0, h=10, w=10)
        return small, large, grid

    def test_ray_toward_largest_produces_cells(self):
        """A ray_relational toward the largest object must produce non-empty
        output heading from the small object toward the large object."""
        small, large, grid = self._setup()
        rule = {
            "kind": "ray_relational",
            "direction_mode": "toward",
            "target_pred": {"type": "largest"},
            "color": 3,
        }
        bounds = (10, 10)
        added = _apply_generator(rule, small, bounds,
                                 grid_array=grid.to_numpy(),
                                 all_objects=[small, large])
        assert len(added) > 0, "ray_relational toward largest must emit cells"

    def test_ray_toward_largest_direction_is_down_right(self):
        """The dominant direction from (0,0) to (7-8, 7-9) is down-right;
        the ray cells must be below and/or to the right of the source."""
        small, large, grid = self._setup()
        rule = {
            "kind": "ray_relational",
            "direction_mode": "toward",
            "target_pred": {"type": "largest"},
            "color": 3,
        }
        bounds = (10, 10)
        added = _apply_generator(rule, small, bounds,
                                 grid_array=grid.to_numpy(),
                                 all_objects=[small, large])
        # Every emitted cell should be at row >= 0 and col >= 0 (trivially),
        # and at least some should be at row > 0 or col > 1 (below/right of
        # the source object which spans rows 0, cols 0-1).
        src_rows = {r for r, _ in small.cells}
        src_cols = {c for _, c in small.cells}
        max_src_r = max(src_rows)
        max_src_c = max(src_cols)
        has_below_or_right = any(
            r > max_src_r or c > max_src_c for (r, c) in added
        )
        assert has_below_or_right, \
            "ray toward largest must go down and/or right from top-left source"

    def test_ray_toward_largest_correct_color(self):
        """All emitted cells should carry the specified color."""
        small, large, grid = self._setup()
        rule = {
            "kind": "ray_relational",
            "direction_mode": "toward",
            "target_pred": {"type": "largest"},
            "color": 3,
        }
        bounds = (10, 10)
        added = _apply_generator(rule, small, bounds,
                                 grid_array=grid.to_numpy(),
                                 all_objects=[small, large])
        assert len(added) > 0, "ray must emit cells (prerequisite for color check)"
        assert all(v == 3 for v in added.values()), \
            "all ray cells must have color 3"


class TestRayRelationalPerpendicularToColor:
    """Test 2: ray perpendicular to a vertical wall should go vertically."""

    def _setup(self):
        # Small object (color 4) at row 3, col 2
        small = _make_object([(3, 2)], color=4, obj_id=1)
        # Tall vertical wall (color 8) at col 7, spanning rows 0-9
        wall_cells = [(r, 7) for r in range(10)]
        wall = _make_object(wall_cells, color=8, obj_id=2)
        grid = _grid_from_objects([small, wall], bg=0, h=10, w=10)
        return small, wall, grid

    def test_perpendicular_ray_goes_vertically(self):
        """The dominant direction from (3,2) to the wall at col 7 is 'right'.
        Perpendicular to 'right' is vertical (up or down). The ray should
        produce cells at column 2 (same column as source) but different rows."""
        small, wall, grid = self._setup()
        rule = {
            "kind": "ray_relational",
            "direction_mode": "perpendicular",
            "target_pred": {"type": "color", "color": 8},
            "color": 4,
        }
        bounds = (10, 10)
        added = _apply_generator(rule, small, bounds,
                                 grid_array=grid.to_numpy(),
                                 all_objects=[small, wall])
        assert len(added) > 0, "perpendicular ray must emit cells"
        # All emitted cells should share the source column (vertical ray)
        # or share the source row (also perpendicular to 'right' but less
        # likely given 'perpendicular' semantics). At minimum, all cells
        # should NOT be to the right along the toward-direction axis.
        cols = {c for _, c in added}
        rows = {r for r, _ in added}
        # Perpendicular to horizontal (toward wall) means vertical motion:
        # cells should be vertically aligned (same column as source).
        assert 2 in cols, "perpendicular ray should have cells in source column"
        # The ray should span multiple rows
        assert len(rows) > 1 or len(added) > 1, \
            "perpendicular ray should span vertically"


class TestGenerativeProgramWithRelationalDirection:
    """Test 3: end-to-end render_generative with a ray_relational generator."""

    def test_render_generative_ray_relational(self):
        """Build a GenerativeProgram with a ray_relational generator and
        verify render_generative produces correct output on a simple case."""
        # Input: two objects -- a small dot (color 3) at (1,1) and a large
        # block (color 5) at bottom-right.
        grid_list = [[0] * 6 for _ in range(6)]
        grid_list[1][1] = 3
        for r in range(4, 6):
            for c in range(4, 6):
                grid_list[r][c] = 5
        input_grid = Grid.from_list(grid_list)

        # Generator: every object emits a ray_relational toward the largest
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({}, {"kind": "ray_relational",
                      "direction_mode": "toward",
                      "target_pred": {"type": "largest"},
                      "color": 3}),
            ],
            canvas_policy="over_input",
            background=0,
        )
        result = render_generative(prog, input_grid)
        result_arr = result.to_numpy()

        # The small object at (1,1) emits a ray toward the large block.
        # The dominant axis: dr=3.5 vs dc=3.5 (equal, so rows win -> down).
        # The ray paints downward through column 1 from row 2 to row 5.
        assert result_arr[1, 1] == 3, "source object preserved"
        assert result_arr[4, 4] == 5, "target object preserved"

        # The ray from the small object goes down column 1
        ray_cells = sum(1 for r in range(2, 6) if result_arr[r, 1] == 3)
        assert ray_cells > 0, \
            "ray_relational should paint cells downward from the source"


# ---------------------------------------------------------------------------
# Part B — relift pass
# ---------------------------------------------------------------------------

def _recolor_program(color_val):
    """Build a minimal ObjectProgram that recolors all objects to a constant."""
    rule = ObjectRule(
        selector=SelectorRule(
            predicate=PredExpr(op="true", args=()),
            literals=0,
        ),
        action=ActionRule(
            delta_type=DeltaType.RECOLOR,
            params={"color": ColorExpr(op="const", args=(color_val,))},
            parameter_class=ParameterClass.CONSTANT,
        ),
    )
    return ObjectProgram(
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
        rules=[rule],
        default_action=ActionRule(delta_type=DeltaType.KEEP),
        output_spec=OutputSpec(mode="same_as_input"),
    )


def _make_recolor_pairs(src_color, target_color, large_color, n=3):
    """Build n train pairs where:
    - Input has a small object (src_color) and a large object (large_color).
    - Output has the small object recolored to target_color, large unchanged.
    The twist: target_color == large_color in every pair (the relational
    pattern relift should discover).
    """
    pairs = []
    for i in range(n):
        r_small = 1 + i
        c_small = 1
        gi = [[0] * 8 for _ in range(8)]
        gi[r_small][c_small] = src_color
        # Large object: 4 cells at bottom-right (constant across pairs)
        for r in range(5, 7):
            for c in range(5, 7):
                gi[r][c] = large_color
        go = [row[:] for row in gi]
        go[r_small][c_small] = target_color  # recolored
        pairs.append((Grid.from_list(gi), Grid.from_list(go)))
    return pairs


@pytest.mark.skipif(not HAS_RELIFT, reason="relift not yet built")
class TestReliftConstantColorToFeature:
    """Test 4: relift discovers that a constant color equals color_of(largest)."""

    def test_relift_finds_relational_expression(self):
        """A RECOLOR(const(5)) program where color 5 always equals
        color_of(largest(true)) should be relifted to use the relational
        expression."""
        prog = _recolor_program(5)
        pairs = _make_recolor_pairs(src_color=3, target_color=5,
                                    large_color=5, n=3)
        result = relift_program(prog, pairs)
        assert result is not None, "relift should return a result"
        assert result.program is not None, "relifted program should exist"

        # The relifted program's recolor param should no longer be const(5)
        recolor_rule = result.program.rules[0]
        color_expr = recolor_rule.action.params["color"]
        assert color_expr.op != "const" or color_expr.args != (5,), \
            "relift should replace the constant with a relational expression"

    def test_relifted_parameter_class_improves(self):
        """The parameter class should improve from CONSTANT to RELATIONAL
        or FEATURE after relifting."""
        prog = _recolor_program(5)
        pairs = _make_recolor_pairs(src_color=3, target_color=5,
                                    large_color=5, n=3)
        result = relift_program(prog, pairs)
        assert result is not None
        recolor_rule = result.program.rules[0]
        color_expr = recolor_rule.action.params["color"]
        pc = parameter_class_of(color_expr)
        assert pc.rank < ParameterClass.CONSTANT.rank, \
            f"parameter class should improve from CONSTANT, got {pc}"


@pytest.mark.skipif(not HAS_RELIFT, reason="relift not yet built")
class TestReliftPreservesTrainPerfect:
    """Test 5: relift must not break train-perfect programs."""

    def test_relifted_program_is_train_perfect(self):
        """After relifting, the program must still produce correct output
        on every train pair."""
        from geocat_arc.object_reasoning.actions import render_program

        prog = _recolor_program(5)
        pairs = _make_recolor_pairs(src_color=3, target_color=5,
                                    large_color=5, n=3)

        # Verify original is train-perfect
        for gi, go in pairs:
            rendered = render_program(prog, gi)
            assert np.array_equal(rendered.to_numpy(), go.to_numpy()), \
                "original program must be train-perfect"

        result = relift_program(prog, pairs)
        if result is None or result.program is None:
            pytest.skip("relift did not find a replacement (acceptable)")

        # Verify relifted is also train-perfect
        for gi, go in pairs:
            rendered = render_program(result.program, gi)
            assert np.array_equal(rendered.to_numpy(), go.to_numpy()), \
                "relifted program must remain train-perfect"


@pytest.mark.skipif(not HAS_RELIFT, reason="relift not yet built")
class TestReliftZeroCostWhenOff:
    """Test 6: with ARC_RELIFT unset, importing relift.py has no side effects
    and the env gate function returns False."""

    def test_env_gate_returns_false_when_unset(self):
        """The relift module should expose a gate function that returns False
        when ARC_RELIFT is not set (or set to '0')."""
        # Save and clear the env var
        old = os.environ.pop("ARC_RELIFT", None)
        try:
            # Re-import to get fresh state
            import importlib
            import geocat_arc.object_reasoning.relift as relift_mod
            importlib.reload(relift_mod)

            # The module should have an env-gate function
            gate_fn = getattr(relift_mod, "relift_enabled", None)
            if gate_fn is None:
                # Alternative name
                gate_fn = getattr(relift_mod, "is_enabled", None)
            assert gate_fn is not None, \
                "relift module must expose a relift_enabled or is_enabled gate"
            assert gate_fn() is False, \
                "gate must return False when ARC_RELIFT is unset"
        finally:
            if old is not None:
                os.environ["ARC_RELIFT"] = old

    def test_env_gate_returns_false_when_zero(self):
        """ARC_RELIFT=0 should also gate off."""
        old = os.environ.get("ARC_RELIFT")
        os.environ["ARC_RELIFT"] = "0"
        try:
            import importlib
            import geocat_arc.object_reasoning.relift as relift_mod
            importlib.reload(relift_mod)

            gate_fn = getattr(relift_mod, "relift_enabled",
                              getattr(relift_mod, "is_enabled", None))
            assert gate_fn is not None
            assert gate_fn() is False, \
                "gate must return False when ARC_RELIFT=0"
        finally:
            if old is not None:
                os.environ["ARC_RELIFT"] = old
            else:
                os.environ.pop("ARC_RELIFT", None)


@pytest.mark.skipif(not HAS_RELIFT, reason="relift not yet built")
class TestReliftOnSyntheticOverfit:
    """Test 7: relift finds the relational expression on a deliberately
    overfitting scenario and the relifted program generalizes."""

    def test_relift_generalizes_past_constant(self):
        """3 train pairs where constant color 7 is the correct recolor value
        and 7 == color_of(largest(true)) in each pair. The constant program
        passes all 3 but would fail a novel pair where largest is color 2.
        After relift, the program should generalize."""
        from geocat_arc.object_reasoning.actions import render_program

        # Train pairs: small object (color 3) recolored to 7,
        # large object (color 7) unchanged.
        train_pairs = _make_recolor_pairs(src_color=3, target_color=7,
                                          large_color=7, n=3)

        prog = _recolor_program(7)

        # Verify original is train-perfect
        for gi, go in train_pairs:
            assert np.array_equal(
                render_program(prog, gi).to_numpy(), go.to_numpy())

        # Novel pair: large object is color 2, so the correct recolor is 2
        # (since the true rule is "recolor to color_of(largest)")
        novel_gi = [[0] * 8 for _ in range(8)]
        novel_gi[2][1] = 3  # small object
        for r in range(5, 7):
            for c in range(5, 7):
                novel_gi[r][c] = 2  # large object, color 2
        novel_go = [row[:] for row in novel_gi]
        novel_go[2][1] = 2  # recolored to 2 (= color_of(largest))
        novel_pair = (Grid.from_list(novel_gi), Grid.from_list(novel_go))

        # Original constant program FAILS on the novel pair
        rendered_orig = render_program(prog, novel_pair[0]).to_numpy()
        assert not np.array_equal(rendered_orig, novel_pair[1].to_numpy()), \
            "constant program must fail on novel pair (sanity check)"

        # Relift should discover the relational expression
        result = relift_program(prog, train_pairs)
        assert result is not None and result.program is not None, \
            "relift should find a relational replacement"

        # The relifted program should generalize to the novel pair
        rendered_relifted = render_program(result.program,
                                           novel_pair[0]).to_numpy()
        assert np.array_equal(rendered_relifted, novel_pair[1].to_numpy()), \
            "relifted program should generalize to novel pair"
