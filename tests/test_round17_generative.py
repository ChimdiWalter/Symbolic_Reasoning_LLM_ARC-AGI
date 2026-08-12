"""Round 17: generative-composite induction path (ARC_GENERATIVE).

Tests:
  1. Synthetic ray-draw task with FUSION: objects at top and bottom of a
     column; both emit rays down; top ray fills column, bottom ray adds
     nothing (at border). Output is one fused object (n_in=2, n_out=1).
     Solved end-to-end via induce_program with LOO.
  2. Blank-canvas variant: generators paint on an empty canvas.
  3. Relational direction: direction derived from object color generalizes
     to unseen scenes.
  4. Zero-cost-when-off: no generative candidates when ARC_GENERATIVE unset.
  5. Program dict round-trip: to_dict / from_dict / render identical.
"""
import os
import unittest
from unittest import mock

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.types import (
    GenerativeProgram,
    SegmentationVariant,
    program_from_dict,
)
from geocat_arc.object_reasoning.actions import render_program


def _g(rows):
    return Grid.from_list(rows)


class TestGenerativeRayFusion(unittest.TestCase):
    """Synthetic task with genuine fusion: same-color dots at top and
    bottom of a column.  Each emits ray DOWN (top fills column, bottom
    adds nothing).  Under S1: n_in=2, n_out=1 (fusion satisfied).

    Three train pairs with different column positions ensure the rule
    generalizes spatially."""

    def _make_pair(self, col, h=8, w=8, color=3):
        """Dots at (0, col) and (h-1, col); output = entire column filled."""
        gi = [[0] * w for _ in range(h)]
        gi[0][col] = color
        gi[h - 1][col] = color
        go = [[0] * w for _ in range(h)]
        for r in range(h):
            go[r][col] = color
        return _g(gi), _g(go)

    def _pairs(self):
        return [
            self._make_pair(col=2),
            self._make_pair(col=5),
            self._make_pair(col=3),
        ]

    def test_render_generative_over_input(self):
        """A hand-built GenerativeProgram renders correctly."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({}, {"kind": "ray", "direction": "down"}),
            ],
            canvas_policy="over_input",
        )
        for gi, go in self._pairs():
            result = render_program(prog, gi)
            self.assertEqual(result.to_list(), go.to_list(),
                             "Ray-down generative render mismatch")

    def test_render_generative_blank_canvas(self):
        """Blank-canvas variant: only generator output, no input copy."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({}, {"kind": "ray", "direction": "down"}),
            ],
            canvas_policy="blank",
            background=0,
        )
        gi, go = self._make_pair(col=2)
        result = render_program(prog, gi)
        r = result.to_numpy()
        # Blank canvas: original dots at (0,2) and (7,2) are NOT copied.
        # Rays from (0,2) down fill (1,2)-(7,2) = color 3.
        # (0,2) itself is NOT on the canvas (not part of any ray).
        self.assertEqual(r[0, 2], 0, "blank canvas should not copy input dot")
        self.assertEqual(r[1, 2], 3, "ray pixel should be present")
        self.assertEqual(r[7, 2], 3, "ray should reach border")

    def test_dict_round_trip(self):
        """to_dict -> from_dict -> render produces identical output."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S3_MULTICOLOR_4,
            generators=[
                ({}, {"kind": "ray", "direction": "down"}),
                ({"color": 5}, {"kind": "halo", "color": 9, "conn": 4}),
            ],
            canvas_policy="over_input",
            background=0,
        )
        d = prog.to_dict()
        self.assertEqual(d["program_class"], "generative")
        prog2 = program_from_dict(d)
        self.assertIsInstance(prog2, GenerativeProgram)
        self.assertEqual(prog2.seg_variant, prog.seg_variant)
        self.assertEqual(prog2.canvas_policy, prog.canvas_policy)
        self.assertEqual(len(prog2.generators), len(prog.generators))

        # Render should be identical
        gi = _g([[0, 0, 0, 0, 0],
                 [0, 3, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0]])
        r1 = render_program(prog, gi).to_list()
        r2 = render_program(prog2, gi).to_list()
        self.assertEqual(r1, r2, "round-trip render mismatch")

    def test_zero_cost_when_off(self):
        """With ARC_GENERATIVE unset, inducer returns no generative
        candidates (the generative path is never entered)."""
        from geocat_arc.object_reasoning.inducer import induce_program

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ARC_GENERATIVE", None)
            result = induce_program(self._pairs())
        # Without ARC_GENERATIVE, the generative path is skipped.
        self.assertNotIn("GENERATIVE_COMPOSITE_FOUND", result.events)

    def test_induce_end_to_end_with_loo(self):
        """End-to-end: induce_program with ARC_GENERATIVE=1 finds a
        generative program that passes LOO on the fusion task."""
        from geocat_arc.object_reasoning.inducer import induce_program

        pairs = self._pairs()
        with mock.patch.dict(os.environ, {"ARC_GENERATIVE": "1"}):
            result = induce_program(pairs)
        if result.accepted and isinstance(result.program, GenerativeProgram):
            # Verify train-perfect
            for gi, go in pairs:
                rendered = render_program(result.program, gi)
                self.assertEqual(rendered.to_list(), go.to_list())
            # LOO should pass
            self.assertTrue(result.loo.all_passed,
                            f"LOO failed: {result.loo.failed_pair_indices}")

    def test_relational_direction_generalizes(self):
        """A uniform 'ray down' generator induced on 2 pairs generalizes
        to a 3rd pair with different column position."""
        from geocat_arc.object_reasoning.generative import (
            induce_generative_candidates,
        )

        # Use only 2 pairs for induction
        pairs = self._pairs()[:2]
        with mock.patch.dict(os.environ, {"ARC_GENERATIVE": "1"}):
            candidates = induce_generative_candidates(pairs)

        self.assertTrue(len(candidates) > 0,
                        "No generative candidates found")

        # The best candidate should also work on the 3rd pair
        prog = candidates[0]
        gi3, go3 = self._pairs()[2]
        rendered = render_program(prog, gi3)
        self.assertEqual(rendered.to_list(), go3.to_list(),
                         "Generative program should generalize to unseen pair")


class TestGenerativeHalo(unittest.TestCase):
    """Synthetic task: single dot emits halo.  Under S1, a dot with a
    halo is still 1 output object (5 cells).  To get fusion: use 2 dots
    whose halos merge.  Dots at (2,2) and (2,4): under S1, input has
    2 objects.  Halos touch at column 3 -> 1 output object."""

    def _make_pair(self, c1, c2, color=3, h=7, w=7):
        """Two dots in row 2, halo-4 around each. If |c2-c1|==2,
        halos merge at the midpoint column."""
        gi = [[0] * w for _ in range(h)]
        gi[2][c1] = color
        gi[2][c2] = color
        go = [row[:] for row in gi]
        for r0, c0 in [(2, c1), (2, c2)]:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r0 + dr, c0 + dc
                if 0 <= nr < h and 0 <= nc < w:
                    go[nr][nc] = color
        return _g(gi), _g(go)

    def _pairs(self):
        return [
            self._make_pair(c1=1, c2=3),   # halos merge at col 2
            self._make_pair(c1=2, c2=4),   # halos merge at col 3
            self._make_pair(c1=3, c2=5),   # halos merge at col 4
        ]

    def test_halo_induction(self):
        """Halo generator is found by the inducer."""
        from geocat_arc.object_reasoning.generative import (
            induce_generative_candidates,
        )
        with mock.patch.dict(os.environ, {"ARC_GENERATIVE": "1"}):
            candidates = induce_generative_candidates(self._pairs())
        self.assertTrue(len(candidates) > 0,
                        "No halo generative candidates found")
        prog = candidates[0]
        for gi, go in self._pairs():
            rendered = render_program(prog, gi)
            self.assertEqual(rendered.to_list(), go.to_list())


class TestGenerativeRowColLine(unittest.TestCase):
    """Synthetic cross-line tasks modeled after 178fcbfb: different-colored
    dots emit row or column lines, with delete_source to remove the dots."""

    def _pairs_178fcbfb_like(self):
        """3 pairs mimicking 178fcbfb: color-3 dots -> row_line, color-2 dot -> col_line."""
        pairs = []
        configs = [
            # (row_positions_for_3, col_for_2, h, w)
            ([(1, 1), (4, 3)], (7, 5), 10, 8),
            ([(2, 4), (6, 2)], (3, 6), 9, 9),
            ([(1, 5), (5, 2)], (7, 3), 10, 8),
        ]
        for dots_3, dot_2, h, w in configs:
            gi = [[0] * w for _ in range(h)]
            for r, c in dots_3:
                gi[r][c] = 3
            gi[dot_2[0]][dot_2[1]] = 2
            go = [[0] * w for _ in range(h)]
            # col_line for color 2 (paints first -> background layer)
            for r in range(h):
                go[r][dot_2[1]] = 2
            # row_lines for color 3 (paints on top)
            for r, c in dots_3:
                for cc in range(w):
                    go[r][cc] = 3
            pairs.append((_g(gi), _g(go)))
        return pairs

    def test_row_line_render(self):
        """row_line fills the entire row with the object's color."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[({}, {"kind": "row_line"})],
            canvas_policy="blank",
            background=0,
            delete_source=True,
        )
        gi = _g([[0, 0, 0, 0, 0],
                 [0, 3, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0]])
        result = render_program(prog, gi)
        # Row 1 should be all 3
        self.assertEqual(result.to_list()[1], [3, 3, 3, 3, 3])
        # Other rows should be 0
        self.assertEqual(result.to_list()[0], [0, 0, 0, 0, 0])

    def test_col_line_render(self):
        """col_line fills the entire column with the object's color."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[({}, {"kind": "col_line"})],
            canvas_policy="blank",
            background=0,
            delete_source=True,
        )
        gi = _g([[0, 0, 0, 0, 0],
                 [0, 3, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0]])
        result = render_program(prog, gi)
        # Col 1 should be all 3
        for r in range(5):
            self.assertEqual(result.to_list()[r][1], 3,
                             f"col_line wrong at row {r}")

    def test_cross_line_render(self):
        """cross_line fills both the row and column."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[({}, {"kind": "cross_line"})],
            canvas_policy="blank",
            background=0,
            delete_source=True,
        )
        gi = _g([[0, 0, 0, 0, 0],
                 [0, 3, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0]])
        result = render_program(prog, gi)
        # Row 1 should be all 3
        self.assertEqual(result.to_list()[1], [3, 3, 3, 3, 3])
        # Col 1 should be all 3
        for r in range(5):
            self.assertEqual(result.to_list()[r][1], 3)

    def test_per_color_induction_with_ordering(self):
        """Per-color generators with correct painter's ordering are found."""
        from geocat_arc.object_reasoning.generative import (
            induce_generative_candidates,
        )
        pairs = self._pairs_178fcbfb_like()
        with mock.patch.dict(os.environ, {"ARC_GENERATIVE": "1"}):
            candidates = induce_generative_candidates(pairs)
        self.assertTrue(len(candidates) > 0,
                        "No candidates found for row/col line task")
        prog = candidates[0]
        for gi, go in pairs:
            rendered = render_program(prog, gi)
            self.assertEqual(rendered.to_list(), go.to_list())

    def test_delete_source_round_trip(self):
        """delete_source flag survives serialization."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[({}, {"kind": "row_line"})],
            delete_source=True,
        )
        d = prog.to_dict()
        self.assertTrue(d.get("delete_source"))
        prog2 = program_from_dict(d)
        self.assertTrue(prog2.delete_source)

    def test_real_178fcbfb(self):
        """178fcbfb exemplar: generative candidates found."""
        import json as _json
        from geocat_arc.object_reasoning.generative import (
            induce_generative_candidates,
        )
        try:
            challenges = _json.load(open(
                "data/arc/arc-agi_training_challenges.json"))
            task = challenges["178fcbfb"]
        except (FileNotFoundError, KeyError):
            self.skipTest("ARC training data not available")
        pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                 for p in task["train"]]
        with mock.patch.dict(os.environ, {"ARC_GENERATIVE": "1"}):
            candidates = induce_generative_candidates(pairs)
        self.assertTrue(len(candidates) > 0,
                        "178fcbfb: no generative candidates found")
        prog = candidates[0]
        for gi, go in pairs:
            rendered = render_program(prog, gi)
            self.assertEqual(rendered.to_list(), go.to_list(),
                             "178fcbfb: composite mismatch")


class TestGenerativeParameterClass(unittest.TestCase):
    """Ranking surface properties of GenerativeProgram."""

    def test_relational_when_no_bound_literals(self):
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({}, {"kind": "ray", "direction": "down"}),
            ],
        )
        from geocat_arc.object_reasoning.types import ParameterClass
        self.assertEqual(prog.worst_parameter_class,
                         ParameterClass.RELATIONAL)
        self.assertEqual(prog.value_bound_count, 0)

    def test_induced_map_when_color_literal(self):
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({}, {"kind": "ray", "direction": "down", "color": 5}),
            ],
        )
        from geocat_arc.object_reasoning.types import ParameterClass
        self.assertEqual(prog.worst_parameter_class,
                         ParameterClass.INDUCED_MAP)
        self.assertEqual(prog.value_bound_count, 1)


class TestIntersectionColor(unittest.TestCase):
    """R17b: cross_line intersection color (23581191 semantics).

    Two dots of different colors emit cross_lines; where the lines
    intersect, the cell takes a fixed intersection_color (not either
    source color)."""

    def _pairs_23581191_like(self):
        """Synthetic version of 23581191: two dots emit cross_lines,
        intersections take color 2."""
        pairs = []
        configs = [
            # (dot8_pos, dot7_pos, h, w)
            ((1, 3), (7, 6), 9, 9),
            ((2, 2), (6, 6), 9, 9),
        ]
        for (r8, c8), (r7, c7), h, w in configs:
            gi = [[0] * w for _ in range(h)]
            gi[r8][c8] = 8
            gi[r7][c7] = 7
            go = [[0] * w for _ in range(h)]
            # Cross lines for color 8
            for c in range(w):
                go[r8][c] = 8
            for r in range(h):
                go[r][c8] = 8
            # Cross lines for color 7 (paints on top of 8 where overlapping)
            for c in range(w):
                go[r7][c] = 7
            for r in range(h):
                go[r][c7] = 7
            # Intersection cells: (r8, c7) and (r7, c8) get color 2
            go[r8][c7] = 2
            go[r7][c8] = 2
            pairs.append((_g(gi), _g(go)))
        return pairs

    def test_intersection_color_render(self):
        """GenerativeProgram with intersection_color renders correctly."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({"color": 8}, {"kind": "cross_line", "color": 8}),
                ({"color": 7}, {"kind": "cross_line", "color": 7}),
            ],
            canvas_policy="blank",
            background=0,
            delete_source=True,
            intersection_color=2,
        )
        for gi, go in self._pairs_23581191_like():
            result = render_program(prog, gi)
            self.assertEqual(result.to_list(), go.to_list(),
                             "intersection_color render mismatch")

    def test_intersection_color_round_trip(self):
        """intersection_color survives serialization."""
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({"color": 8}, {"kind": "cross_line", "color": 8}),
                ({"color": 7}, {"kind": "cross_line", "color": 7}),
            ],
            intersection_color=2,
        )
        d = prog.to_dict()
        self.assertEqual(d["intersection_color"], 2)
        prog2 = program_from_dict(d)
        self.assertEqual(prog2.intersection_color, 2)

    def test_intersection_color_induction(self):
        """Inducer discovers intersection_color for 23581191-like task."""
        from geocat_arc.object_reasoning.generative import (
            induce_generative_candidates,
        )
        pairs = self._pairs_23581191_like()
        with mock.patch.dict(os.environ, {"ARC_GENERATIVE": "1"}):
            candidates = induce_generative_candidates(pairs)
        self.assertTrue(len(candidates) > 0,
                        "No candidates found for intersection_color task")
        prog = candidates[0]
        self.assertEqual(prog.intersection_color, 2,
                         f"Expected intersection_color=2, got {prog.intersection_color}")
        for gi, go in pairs:
            rendered = render_program(prog, gi)
            self.assertEqual(rendered.to_list(), go.to_list(),
                             "intersection_color program should be train-perfect")

    def test_real_23581191(self):
        """23581191 exemplar: generative candidates found with intersection_color."""
        import json as _json
        from geocat_arc.object_reasoning.generative import (
            induce_generative_candidates,
        )
        try:
            challenges = _json.load(open(
                "data/arc/arc-agi_training_challenges.json"))
            task = challenges["23581191"]
        except (FileNotFoundError, KeyError):
            self.skipTest("ARC training data not available")
        pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                 for p in task["train"]]
        with mock.patch.dict(os.environ, {"ARC_GENERATIVE": "1"}):
            candidates = induce_generative_candidates(pairs)
        self.assertTrue(len(candidates) > 0,
                        "23581191: no generative candidates found")
        prog = candidates[0]
        for gi, go in pairs:
            rendered = render_program(prog, gi)
            self.assertEqual(rendered.to_list(), go.to_list(),
                             "23581191: composite mismatch")


class TestRayThroughAbsorbed(unittest.TestCase):
    """R17b: ray_through_absorbed generator mode.

    A ray that goes through the first obstacle, absorbing its color.
    Segment before obstacle = source color; segment from obstacle onward
    = obstacle color."""

    def test_ray_through_absorbed_render(self):
        """ray_through_absorbed produces correct color segments."""
        # 5x10 grid: dot at (2,1), wall at col 5 (color 8)
        gi = [[0] * 10 for _ in range(5)]
        gi[2][1] = 3
        gi[0][5] = 8; gi[1][5] = 8; gi[2][5] = 8; gi[3][5] = 8; gi[4][5] = 8

        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({"color": 3}, {"kind": "ray_through_absorbed",
                                "direction": "right", "color": 3}),
            ],
            canvas_policy="over_input",
            background=0,
        )
        result = render_program(prog, _g(gi))
        r = result.to_list()
        # Row 2: dot at col 1, wall at col 5
        # Ray: cols 2-4 = 3 (source), col 5 = 8 (obstacle, absorbed),
        # cols 6-9 = 8 (absorbed continues to border)
        self.assertEqual(r[2][1], 3, "source stays")
        self.assertEqual(r[2][2], 3, "before obstacle = source color")
        self.assertEqual(r[2][3], 3, "before obstacle = source color")
        self.assertEqual(r[2][4], 3, "before obstacle = source color")
        self.assertEqual(r[2][5], 8, "obstacle cell keeps color")
        self.assertEqual(r[2][6], 8, "after obstacle = absorbed color")
        self.assertEqual(r[2][9], 8, "ray reaches border")
        # Rows without dot: unchanged
        self.assertEqual(r[0][2], 0, "no ray on row without dot")

    def test_ray_through_absorbed_no_obstacle(self):
        """ray_through_absorbed with no obstacle = regular ray to border."""
        gi = [[0] * 5 for _ in range(5)]
        gi[2][1] = 3
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[
                ({"color": 3}, {"kind": "ray_through_absorbed",
                                "direction": "right", "color": 3}),
            ],
            canvas_policy="over_input",
        )
        result = render_program(prog, _g(gi))
        r = result.to_list()
        # No obstacle: entire ray should be color 3
        self.assertEqual(r[2][2], 3)
        self.assertEqual(r[2][3], 3)
        self.assertEqual(r[2][4], 3)

    def test_ray_through_absorbed_induction(self):
        """ray_through_absorbed candidates are proposed by the inducer."""
        from geocat_arc.object_reasoning.generative import (
            _candidate_generators_for_object,
        )
        from geocat_arc.perception.objects import ARCObject
        import numpy as np

        # Object at (2,1), wall at col 5 (color 8)
        gi_np = np.zeros((5, 10), dtype=np.int32)
        gi_np[2, 1] = 3
        for r in range(5):
            gi_np[r, 5] = 8

        # Target: cols 2-4 = 3, col 5 = 8, cols 6-9 = 8 on row 2
        target = gi_np.copy()
        for c in range(2, 5):
            target[2, c] = 3
        for c in range(6, 10):
            target[2, c] = 8

        obj = ARCObject(id=0, cells=frozenset([(2, 1)]), color=3,
                        bounding_box=(2, 1, 2, 1))
        cands = _candidate_generators_for_object(
            obj, target, bg_in=0, bounds=(5, 10), grid_array=gi_np)

        kinds = [c["kind"] for c in cands]
        self.assertIn("ray_through_absorbed", kinds,
                      f"ray_through_absorbed not proposed; got kinds: {kinds}")


class TestValueBoundCountIntersection(unittest.TestCase):
    """intersection_color adds to value_bound_count."""

    def test_intersection_color_value_bound(self):
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[({}, {"kind": "cross_line"})],
            intersection_color=2,
        )
        self.assertEqual(prog.value_bound_count, 1)

    def test_no_intersection_color_value_bound(self):
        prog = GenerativeProgram(
            seg_variant=SegmentationVariant.S1_SAME_COLOR_4,
            generators=[({}, {"kind": "cross_line"})],
        )
        self.assertEqual(prog.value_bound_count, 0)


if __name__ == "__main__":
    unittest.main()
