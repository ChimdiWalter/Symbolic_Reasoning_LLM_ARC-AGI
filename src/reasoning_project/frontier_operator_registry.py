"""Frontier operator registry: registered operators with trigger/propose/execute/verify interface.

Each operator wrapper exposes:
- trigger(analysis) -> bool
- propose(analysis, train_pairs, test_inputs) -> list[dict]
- execute(hypothesis, input_grid) -> ndarray
- proof_obligations(hypothesis) -> list
- falsification_probes(hypothesis) -> list
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

if TYPE_CHECKING:
    from reasoning_project.adaptive_orchestrator import TaskAnalysis


def _to_list(grid):
    """Convert numpy array or grid to list-of-lists."""
    if hasattr(grid, "tolist"):
        return grid.tolist()
    return [row[:] for row in grid]


class FrontierOperator:
    """Base class for frontier operator wrappers."""

    name: str = "base"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        return False

    def propose(
        self,
        analysis: "TaskAnalysis",
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
    ) -> List[Dict[str, Any]]:
        return []

    def execute(self, hypothesis: Dict[str, Any], input_grid: np.ndarray) -> Optional[np.ndarray]:
        return None

    def proof_obligations(self, hypothesis: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def falsification_probes(self, hypothesis: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []


# ---------------------------------------------------------------------------
# Shape completion
# ---------------------------------------------------------------------------

def _build_shape_completion_execute(family, params0):
    """Build a test-time execute function for shape completion.

    The detection functions need (inp, out) but at test time we only have inp.
    We learn the family-level rule (color, direction, axis, fill_color, period)
    from training and apply it to new inputs using input-only detection.
    """
    from reasoning_project.shape_completion import (
        CompletionFamily,
        _extract_objects,
        _detect_lines,
        _detect_symmetry_axis,
        _find_holes,
        _grid_copy,
    )

    if family == CompletionFamily.LINE_EXTENSION:
        color = params0["color"]
        direction = params0["direction"]

        def execute(grid):
            gl = _to_list(grid)
            objects = _extract_objects(gl)
            result = _grid_copy(gl)
            rows, cols = len(gl), len(gl[0])
            for obj in objects:
                if obj["color"] == color:
                    lines = _detect_lines(obj["cells"])
                    for line in lines:
                        if line["direction"] == direction:
                            if direction == "horizontal":
                                for c in range(cols):
                                    result[line["row"]][c] = color
                            else:
                                for r in range(rows):
                                    result[r][line["col"]] = color
            return np.array(result)
        return execute

    elif family == CompletionFamily.SYMMETRY_COMPLETION:
        learned_color = params0["color"]
        learned_axis = params0["axis"]

        def execute(grid):
            gl = _to_list(grid)
            objects = _extract_objects(gl)
            result = _grid_copy(gl)
            rows, cols = len(gl), len(gl[0])
            for obj in objects:
                if obj["color"] == learned_color:
                    sym = _detect_symmetry_axis(obj["cells"])
                    if sym and sym["axis"] == learned_axis:
                        mid = sym["mid"]
                        for r, c in obj["cells"]:
                            if learned_axis == "horizontal":
                                mr = int(2 * mid - r)
                                if 0 <= mr < rows:
                                    result[mr][c] = learned_color
                            else:
                                mc = int(2 * mid - c)
                                if 0 <= mc < cols:
                                    result[r][mc] = learned_color
            return np.array(result)
        return execute

    elif family == CompletionFamily.HOLE_COMPLETION:
        fill_color = params0["fill_color"]

        def execute(grid):
            gl = _to_list(grid)
            objects = _extract_objects(gl)
            result = _grid_copy(gl)
            for obj in objects:
                holes = _find_holes(gl, obj["cells"])
                for r, c in holes:
                    result[r][c] = fill_color
            return np.array(result)
        return execute

    elif family == CompletionFamily.BOUNDARY_COMPLETION:
        fill_color = params0["color"]

        def execute(grid):
            gl = _to_list(grid)
            objects = _extract_objects(gl)
            result = _grid_copy(gl)
            for obj in objects:
                cells = obj["cells"]
                r0 = min(r for r, c in cells)
                c0 = min(c for r, c in cells)
                r1 = max(r for r, c in cells)
                c1 = max(c for r, c in cells)
                for r in range(r0, r1 + 1):
                    result[r][c0] = fill_color
                    result[r][c1] = fill_color
                for c in range(c0, c1 + 1):
                    result[r0][c] = fill_color
                    result[r1][c] = fill_color
            return np.array(result)
        return execute

    elif family == CompletionFamily.MOTIF_CONTINUATION:
        period_r = params0["period_r"]
        period_c = params0["period_c"]

        def execute(grid):
            gl = _to_list(grid)
            result = _grid_copy(gl)
            rows, cols = len(gl), len(gl[0])
            exemplars = {}
            for r in range(rows):
                for c in range(cols):
                    if gl[r][c] != 0:
                        key = (r % period_r, c % period_c)
                        exemplars[key] = gl[r][c]
            for r in range(rows):
                for c in range(cols):
                    key = (r % period_r, c % period_c)
                    if key in exemplars:
                        result[r][c] = exemplars[key]
            return np.array(result)
        return execute

    return None


class ShapeCompletionOperator(FrontierOperator):
    name = "shape_completion"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        if "shape_completion" in analysis.candidate_operator_families:
            return True
        pairs = analysis.object_trace.get("pairs", [])
        if pairs and any(p.get("size_change") for p in pairs):
            return True
        return False

    def propose(self, analysis, train_pairs, test_inputs):
        proposals = []
        try:
            from reasoning_project.shape_completion import (
                solve_shape_completion,
                ShapeCompletionOperator as SCOp,
            )

            list_pairs = [(_to_list(inp), _to_list(out)) for inp, out in train_pairs]
            result = solve_shape_completion(list_pairs)
            if result is None or not result.loo_passed:
                return proposals

            family = result.rule.family
            det_fn = SCOp.DETECTORS.get(family)
            if det_fn is None:
                return proposals
            params0 = det_fn(list_pairs[0][0], list_pairs[0][1])
            if params0 is None:
                return proposals

            execute_fn = _build_shape_completion_execute(family, params0)
            if execute_fn is not None:
                proposals.append({
                    "operator": "shape_completion",
                    "family": family.name,
                    "confidence": 0.6,
                    "selector": None,
                    "execute": execute_fn,
                    "proof_obligations": [],
                })
        except Exception:
            pass
        return proposals


# ---------------------------------------------------------------------------
# Position-within-object recolor
# ---------------------------------------------------------------------------

class PositionRecolorOperator(FrontierOperator):
    name = "position_within_object_recolor"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        if "position_recolor" in analysis.candidate_operator_families:
            return True
        prop = analysis.property_trace.get("best_property", "")
        return any(kw in str(prop) for kw in ["position", "interior", "boundary"])

    def propose(self, analysis, train_pairs, test_inputs):
        proposals = []
        try:
            from reasoning_project.position_within_object_recolor import (
                solve_position_recolor,
                PositionRecolorOperator as PROp,
            )

            list_pairs = [(_to_list(inp), _to_list(out)) for inp, out in train_pairs]
            result = solve_position_recolor(list_pairs)
            if result is None or not result.loo_passed:
                return proposals

            op = PROp(result.rule)

            def execute_fn(grid, _op=op):
                gl = _to_list(grid)
                pred = _op.apply(gl)
                return np.array(pred) if pred is not None else None

            proposals.append({
                "operator": "position_within_object_recolor",
                "family": result.rule.family.name,
                "confidence": 0.55,
                "selector": None,
                "execute": execute_fn,
                "proof_obligations": [],
            })
        except Exception:
            pass
        return proposals


# ---------------------------------------------------------------------------
# Many-to-few grouping
# ---------------------------------------------------------------------------

class ManyToFewGroupingOperator(FrontierOperator):
    name = "many_to_few_grouping"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        pairs = analysis.object_trace.get("pairs", [])
        return any(
            p.get("n_input_objects", 0) > p.get("n_output_objects", 1)
            for p in pairs
        )

    def propose(self, analysis, train_pairs, test_inputs):
        proposals = []
        try:
            from reasoning_project.many_to_few_grouping import (
                solve_many_to_few,
                ManyToFewOperator as M2FOp,
            )

            list_pairs = [(_to_list(inp), _to_list(out)) for inp, out in train_pairs]
            result = solve_many_to_few(list_pairs)
            if result is None or not result.loo_passed:
                return proposals

            collapse = result.certificate_fields.get("collapse_mode", "union")
            op = M2FOp(result.rule, collapse_mode=collapse)

            def execute_fn(grid, _op=op):
                gl = _to_list(grid)
                pred = _op.apply(gl)
                return np.array(pred) if pred is not None else None

            proposals.append({
                "operator": "many_to_few_grouping",
                "family": result.rule.family.name,
                "confidence": 0.5,
                "selector": f"group_by_{result.rule.family.name.lower()}",
                "execute": execute_fn,
                "proof_obligations": [],
            })
        except Exception:
            pass
        return proposals


# ---------------------------------------------------------------------------
# Color transfer
# ---------------------------------------------------------------------------

class ColorTransferOperator(FrontierOperator):
    name = "color_transfer"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        return "color_transfer" in analysis.candidate_operator_families

    def propose(self, analysis, train_pairs, test_inputs):
        proposals = []
        try:
            from reasoning_project.color_transfer import (
                ColorSourceInferer,
                infer_color_transfer_params,
            )
            params = infer_color_transfer_params(train_pairs)
            if params:
                proposals.append({
                    "operator": "color_transfer",
                    "params": params,
                    "confidence": 0.5,
                    "selector": getattr(params, "selector", None),
                    "hypothesis": {"type": "color_transfer", "params": params},
                    "execute": lambda grid, _p=params: _execute_color_transfer(grid, _p),
                    "proof_obligations": [],
                })
        except Exception:
            pass
        return proposals


# ---------------------------------------------------------------------------
# Copy-to-position (wraps trace_operator_invention)
# ---------------------------------------------------------------------------

class CopyToPositionOperator(FrontierOperator):
    name = "copy_to_position"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        return "copy_to_position" in analysis.candidate_operator_families

    def propose(self, analysis, train_pairs, test_inputs):
        proposals = []
        try:
            from reasoning_project.trace_operator_invention import (
                infer_copy_to_position_params,
                execute_copy_to_position,
                CopyToPositionParams,
            )
            from reasoning_project.reasoning_engine import (
                _extract_objects_with_properties,
                _add_relational_properties,
                _classify_kept_removed,
            )

            inp0, out0 = train_pairs[0]
            objects = _extract_objects_with_properties(inp0)
            objects = _add_relational_properties(objects)
            classification = _classify_kept_removed(inp0, out0, objects)
            if not classification or not classification.get("property"):
                return proposals

            selector = classification["property"]
            keep = classification.get("keep_when_true", True)

            params = infer_copy_to_position_params(train_pairs, selector, keep)
            if params is None:
                from reasoning_project.trace_operator_invention import (
                    infer_copy_to_position_params_extended,
                )
                params = infer_copy_to_position_params_extended(train_pairs, selector, keep)

            if params is None:
                return proposals

            def execute_fn(grid, _params=params, _tp=train_pairs):
                return execute_copy_to_position(grid, _params, _tp)

            proposals.append({
                "operator": "copy_to_position",
                "family": "copy_to_position",
                "confidence": 0.5,
                "selector": selector,
                "execute": execute_fn,
                "proof_obligations": [],
            })
        except Exception:
            pass
        return proposals


# ---------------------------------------------------------------------------
# Stubs for operators without backing solvers
# ---------------------------------------------------------------------------

class ProjectToHaloOperator(FrontierOperator):
    name = "project_to_halo"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        return "project_to_halo" in analysis.candidate_operator_families

    def propose(self, analysis, train_pairs, test_inputs):
        return []


class QuadrantFillOperator(FrontierOperator):
    name = "quadrant_fill"

    def trigger(self, analysis: "TaskAnalysis") -> bool:
        return "quadrant_fill" in analysis.candidate_operator_families

    def propose(self, analysis, train_pairs, test_inputs):
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _execute_color_transfer(grid, params):
    try:
        from reasoning_project.color_transfer import execute_color_transfer
        return execute_color_transfer(grid, params)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class FrontierOperatorRegistry:
    """Registry of all frontier operators."""

    def __init__(self):
        self.operators: Dict[str, FrontierOperator] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(ShapeCompletionOperator())
        self.register(PositionRecolorOperator())
        self.register(ManyToFewGroupingOperator())
        self.register(ColorTransferOperator())
        self.register(CopyToPositionOperator())
        self.register(ProjectToHaloOperator())
        self.register(QuadrantFillOperator())
        try:
            from reasoning_project.composed_frontier_operators import (
                SelectThenRecolorOperator,
                SelectThenCropExtractOperator,
            )
            self.register(SelectThenRecolorOperator())
            self.register(SelectThenCropExtractOperator())
        except Exception:
            pass

    def register(self, operator: FrontierOperator):
        self.operators[operator.name] = operator

    def get_triggered(self, analysis: "TaskAnalysis") -> List[Tuple[str, FrontierOperator]]:
        triggered = []
        for name, op in self.operators.items():
            try:
                if op.trigger(analysis):
                    triggered.append((name, op))
            except Exception:
                pass
        return triggered

    def get_all(self) -> List[str]:
        return list(self.operators.keys())
