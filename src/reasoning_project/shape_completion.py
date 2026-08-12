"""Shape completion operators.

Handles tasks where partial/incomplete shapes must be completed in the output.
Operator families: line extension, symmetry completion, boundary completion,
hole completion, motif continuation, missing segment fill, template completion.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple


class CompletionFamily(Enum):
    LINE_EXTENSION = auto()
    SYMMETRY_COMPLETION = auto()
    BOUNDARY_COMPLETION = auto()
    HOLE_COMPLETION = auto()
    MOTIF_CONTINUATION = auto()
    MISSING_SEGMENT_FILL = auto()
    TEMPLATE_COMPLETION = auto()


@dataclass
class CompletionRule:
    family: CompletionFamily
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    deterministic: bool = True


@dataclass
class CompletionResult:
    rule: CompletionRule
    output_grid: Optional[List[List[int]]] = None
    train_fit: int = 0
    loo_passed: bool = False
    ambiguity_rejected: bool = False
    rejection_reason: Optional[str] = None
    proof_obligations_met: List[str] = field(default_factory=list)
    certificate_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShapeCompletionProofObligation:
    obligation_id: str
    description: str
    satisfied: bool = False
    evidence: Optional[str] = None


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

def _extract_objects(grid: List[List[int]], bg: int = 0) -> List[Dict]:
    rows, cols = len(grid), len(grid[0])
    visited = [[False] * cols for _ in range(rows)]
    objects = []
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != bg and not visited[r][c]:
                color = grid[r][c]
                cells = set()
                stack = [(r, c)]
                while stack:
                    cr, cc = stack.pop()
                    if 0 <= cr < rows and 0 <= cc < cols and not visited[cr][cc] and grid[cr][cc] == color:
                        visited[cr][cc] = True
                        cells.add((cr, cc))
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            stack.append((cr + dr, cc + dc))
                if cells:
                    objects.append({"cells": cells, "color": color, "size": len(cells)})
    return objects


def _diff_grids(inp: List[List[int]], out: List[List[int]]) -> Set[Tuple[int, int]]:
    changed = set()
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if r < len(out) and c < len(out[0]) and inp[r][c] != out[r][c]:
                changed.add((r, c))
    return changed


def _grid_copy(grid: List[List[int]]) -> List[List[int]]:
    return [row[:] for row in grid]


# ---------------------------------------------------------------------------
# Line extension
# ---------------------------------------------------------------------------

def _detect_lines(cells: Set[Tuple[int, int]]) -> List[Dict]:
    lines = []
    by_row = defaultdict(set)
    by_col = defaultdict(set)
    for r, c in cells:
        by_row[r].add(c)
        by_col[c].add(r)
    for r, cols_set in by_row.items():
        if len(cols_set) >= 2:
            sorted_c = sorted(cols_set)
            contiguous = all(sorted_c[i + 1] - sorted_c[i] == 1 for i in range(len(sorted_c) - 1))
            if contiguous:
                lines.append({"direction": "horizontal", "row": r, "c_min": sorted_c[0], "c_max": sorted_c[-1], "length": len(sorted_c)})
    for c, rows_set in by_col.items():
        if len(rows_set) >= 2:
            sorted_r = sorted(rows_set)
            contiguous = all(sorted_r[i + 1] - sorted_r[i] == 1 for i in range(len(sorted_r) - 1))
            if contiguous:
                lines.append({"direction": "vertical", "col": c, "r_min": sorted_r[0], "r_max": sorted_r[-1], "length": len(sorted_r)})
    return lines


def _try_line_extension(inp: List[List[int]], out: List[List[int]], bg: int = 0) -> Optional[Dict]:
    rows, cols = len(inp), len(inp[0])
    added = _diff_grids(inp, out)
    if not added:
        return None

    inp_cells = set()
    for r in range(rows):
        for c in range(cols):
            if inp[r][c] != bg:
                inp_cells.add((r, c))

    colors_added = Counter()
    for r, c in added:
        colors_added[out[r][c]] += 1

    for color, count in colors_added.most_common():
        color_cells = {(r, c) for r, c in inp_cells if inp[r][c] == color}
        lines = _detect_lines(color_cells)
        for line in lines:
            extended = set()
            if line["direction"] == "horizontal":
                r = line["row"]
                for c in range(cols):
                    if (r, c) not in color_cells:
                        extended.add((r, c))
            else:
                c = line["col"]
                for r in range(rows):
                    if (r, c) not in color_cells:
                        extended.add((r, c))
            if extended == added:
                return {"direction": line["direction"], "color": color, "line": line}
    return None


def _apply_line_extension(grid: List[List[int]], params: Dict, bg: int = 0) -> List[List[int]]:
    result = _grid_copy(grid)
    rows, cols = len(result), len(result[0])
    line = params["line"]
    color = params["color"]
    if line["direction"] == "horizontal":
        r = line["row"]
        for c in range(cols):
            result[r][c] = color
    else:
        c = line["col"]
        for r in range(rows):
            result[r][c] = color
    return result


# ---------------------------------------------------------------------------
# Symmetry completion
# ---------------------------------------------------------------------------

def _detect_symmetry_axis(cells: Set[Tuple[int, int]]) -> Optional[Dict]:
    if not cells:
        return None
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    mid_r = (min(rs) + max(rs)) / 2
    mid_c = (min(cs) + max(cs)) / 2

    h_mirror = {(int(2 * mid_r - r), c) for r, c in cells}
    h_overlap = len(h_mirror & cells)
    v_mirror = {(r, int(2 * mid_c - c)) for r, c in cells}
    v_overlap = len(v_mirror & cells)

    if h_overlap > len(cells) * 0.3:
        return {"axis": "horizontal", "mid": mid_r, "missing": h_mirror - cells}
    if v_overlap > len(cells) * 0.3:
        return {"axis": "vertical", "mid": mid_c, "missing": v_mirror - cells}
    return None


def _try_symmetry_completion(inp: List[List[int]], out: List[List[int]], bg: int = 0) -> Optional[Dict]:
    rows, cols = len(inp), len(inp[0])
    added = _diff_grids(inp, out)
    if not added:
        return None

    objects = _extract_objects(inp, bg)
    for obj in objects:
        sym = _detect_symmetry_axis(obj["cells"])
        if sym and sym["missing"]:
            valid_missing = {(r, c) for r, c in sym["missing"] if 0 <= r < rows and 0 <= c < cols}
            if valid_missing and valid_missing <= added:
                return {"axis": sym["axis"], "mid": sym["mid"], "color": obj["color"], "object_cells": obj["cells"]}
    return None


def _apply_symmetry_completion(grid: List[List[int]], params: Dict, bg: int = 0) -> List[List[int]]:
    result = _grid_copy(grid)
    rows, cols = len(result), len(result[0])
    cells = params["object_cells"]
    color = params["color"]
    mid = params["mid"]

    if params["axis"] == "horizontal":
        for r, c in cells:
            mr = int(2 * mid - r)
            if 0 <= mr < rows:
                result[mr][c] = color
    else:
        for r, c in cells:
            mc = int(2 * mid - c)
            if 0 <= mc < cols:
                result[r][mc] = color
    return result


# ---------------------------------------------------------------------------
# Boundary completion
# ---------------------------------------------------------------------------

def _boundary_cells(cells: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
    boundary = set()
    for r, c in cells:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if (r + dr, c + dc) not in cells:
                boundary.add((r, c))
                break
    return boundary


def _try_boundary_completion(inp: List[List[int]], out: List[List[int]], bg: int = 0) -> Optional[Dict]:
    rows, cols = len(inp), len(inp[0])
    added = _diff_grids(inp, out)
    if not added:
        return None

    objects = _extract_objects(inp, bg)
    for obj in objects:
        bnd = _boundary_cells(obj["cells"])
        r0 = min(r for r, c in obj["cells"])
        c0 = min(c for r, c in obj["cells"])
        r1 = max(r for r, c in obj["cells"])
        c1 = max(c for r, c in obj["cells"])

        expected_border = set()
        for r in range(r0, r1 + 1):
            expected_border.add((r, c0))
            expected_border.add((r, c1))
        for c in range(c0, c1 + 1):
            expected_border.add((r0, c))
            expected_border.add((r1, c))

        missing_border = expected_border - obj["cells"]
        if missing_border and missing_border <= added:
            added_colors = {out[r][c] for r, c in missing_border}
            if len(added_colors) == 1:
                return {"bbox": (r0, c0, r1, c1), "color": added_colors.pop(), "missing": missing_border, "object_cells": obj["cells"]}
    return None


def _apply_boundary_completion(grid: List[List[int]], params: Dict, bg: int = 0) -> List[List[int]]:
    result = _grid_copy(grid)
    for r, c in params["missing"]:
        if 0 <= r < len(result) and 0 <= c < len(result[0]):
            result[r][c] = params["color"]
    return result


# ---------------------------------------------------------------------------
# Hole completion
# ---------------------------------------------------------------------------

def _find_holes(grid: List[List[int]], obj_cells: Set[Tuple[int, int]], bg: int = 0) -> Set[Tuple[int, int]]:
    rows, cols = len(grid), len(grid[0])
    r0 = min(r for r, c in obj_cells)
    c0 = min(c for r, c in obj_cells)
    r1 = max(r for r, c in obj_cells)
    c1 = max(c for r, c in obj_cells)

    interior_bg = set()
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if (r, c) not in obj_cells and grid[r][c] == bg:
                interior_bg.add((r, c))

    holes = set()
    for cell in interior_bg:
        stack = [cell]
        visited = set()
        touches_edge = False
        while stack:
            cr, cc = stack.pop()
            if (cr, cc) in visited:
                continue
            visited.add((cr, cc))
            if cr <= r0 or cr >= r1 or cc <= c0 or cc >= c1:
                if (cr, cc) not in obj_cells:
                    touches_edge = True
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = cr + dr, cc + dc
                if r0 <= nr <= r1 and c0 <= nc <= c1 and (nr, nc) not in obj_cells and grid[nr][nc] == bg and (nr, nc) not in visited:
                    stack.append((nr, nc))
        if not touches_edge:
            holes |= visited

    return holes


def _try_hole_completion(inp: List[List[int]], out: List[List[int]], bg: int = 0) -> Optional[Dict]:
    added = _diff_grids(inp, out)
    if not added:
        return None
    objects = _extract_objects(inp, bg)
    for obj in objects:
        holes = _find_holes(inp, obj["cells"], bg)
        if holes and holes <= added:
            added_colors = {out[r][c] for r, c in holes}
            if len(added_colors) == 1:
                return {"holes": holes, "fill_color": added_colors.pop(), "object_cells": obj["cells"]}
    return None


def _apply_hole_completion(grid: List[List[int]], params: Dict, bg: int = 0) -> List[List[int]]:
    result = _grid_copy(grid)
    for r, c in params["holes"]:
        result[r][c] = params["fill_color"]
    return result


# ---------------------------------------------------------------------------
# Motif continuation
# ---------------------------------------------------------------------------

def _try_motif_continuation(inp: List[List[int]], out: List[List[int]], bg: int = 0) -> Optional[Dict]:
    rows, cols = len(inp), len(inp[0])
    if len(out) != rows or any(len(row) != cols for row in out):
        return None
    added = _diff_grids(inp, out)
    if not added:
        return None

    for period_r in range(1, rows // 2 + 1):
        for period_c in range(1, cols // 2 + 1):
            matches = 0
            total = 0
            for r in range(rows):
                for c in range(cols):
                    if inp[r][c] != bg:
                        sr, sc = r % period_r, c % period_c
                        for r2 in range(rows):
                            for c2 in range(cols):
                                if r2 % period_r == sr and c2 % period_c == sc and (r2, c2) != (r, c):
                                    total += 1
                                    if out[r2][c2] == inp[r][c]:
                                        matches += 1

            if total > 0 and matches / total > 0.8:
                expected_fill = {}
                for r in range(rows):
                    for c in range(cols):
                        if inp[r][c] != bg:
                            for r2 in range(rows):
                                for c2 in range(cols):
                                    if r2 % period_r == r % period_r and c2 % period_c == c % period_c:
                                        expected_fill[(r2, c2)] = inp[r][c]

                pred = _grid_copy(inp)
                for (r, c), color in expected_fill.items():
                    pred[r][c] = color
                if pred == out:
                    return {"period_r": period_r, "period_c": period_c, "fill": expected_fill}
    return None


def _apply_motif_continuation(grid: List[List[int]], params: Dict, bg: int = 0) -> List[List[int]]:
    result = _grid_copy(grid)
    for (r, c), color in params["fill"].items():
        if 0 <= r < len(result) and 0 <= c < len(result[0]):
            result[r][c] = color
    return result


# ---------------------------------------------------------------------------
# Core operator
# ---------------------------------------------------------------------------

class ShapeCompletionOperator:

    DETECTORS = {
        CompletionFamily.LINE_EXTENSION: _try_line_extension,
        CompletionFamily.SYMMETRY_COMPLETION: _try_symmetry_completion,
        CompletionFamily.BOUNDARY_COMPLETION: _try_boundary_completion,
        CompletionFamily.HOLE_COMPLETION: _try_hole_completion,
        CompletionFamily.MOTIF_CONTINUATION: _try_motif_continuation,
    }

    APPLIERS = {
        CompletionFamily.LINE_EXTENSION: _apply_line_extension,
        CompletionFamily.SYMMETRY_COMPLETION: _apply_symmetry_completion,
        CompletionFamily.BOUNDARY_COMPLETION: _apply_boundary_completion,
        CompletionFamily.HOLE_COMPLETION: _apply_hole_completion,
        CompletionFamily.MOTIF_CONTINUATION: _apply_motif_continuation,
    }

    def __init__(self, rule: CompletionRule, params: Dict = None):
        self.rule = rule
        self.params = params or {}

    def apply(self, grid: List[List[int]], bg: int = 0) -> Optional[List[List[int]]]:
        applier = self.APPLIERS.get(self.rule.family)
        if applier is None or not self.params:
            return None
        try:
            return applier(grid, self.params, bg)
        except Exception:
            return None


class ShapeCompletionDetector:

    def detect(self, train_pairs: List[Tuple], bg: int = 0) -> List[Tuple[CompletionRule, Dict]]:
        candidates = []
        for family, detector in ShapeCompletionOperator.DETECTORS.items():
            all_params = []
            all_match = True
            for inp, out in train_pairs:
                params = detector(inp, out, bg)
                if params is None:
                    all_match = False
                    break
                all_params.append(params)
            if all_match and all_params:
                rule = CompletionRule(family=family, description=family.name)
                candidates.append((rule, all_params[0]))
        return candidates


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

def solve_shape_completion(train_pairs: List[Tuple], bg: int = 0) -> Optional[CompletionResult]:
    detector = ShapeCompletionDetector()
    candidates = detector.detect(train_pairs, bg)

    for rule, params in candidates:
        op = ShapeCompletionOperator(rule, params)
        fit = 0
        all_match = True
        for inp, out in train_pairs:
            det_fn = ShapeCompletionOperator.DETECTORS.get(rule.family)
            task_params = det_fn(inp, out, bg) if det_fn else None
            if task_params is None:
                all_match = False
                break
            task_op = ShapeCompletionOperator(rule, task_params)
            pred = task_op.apply(inp, bg)
            if pred == out:
                fit += 1
            else:
                all_match = False
                break

        if all_match and fit == len(train_pairs):
            loo = validate_completion_loo(rule, train_pairs, bg)
            return CompletionResult(
                rule=rule,
                output_grid=op.apply(train_pairs[0][0], bg),
                train_fit=fit,
                loo_passed=loo,
                certificate_fields={
                    "completion_family": rule.family.name,
                    "train_fit": fit,
                    "loo_passed": loo,
                    "params": {k: str(v)[:100] for k, v in params.items() if k != "object_cells"},
                },
            )
    return None


def detect_completion_type(train_pairs: List[Tuple], bg: int = 0) -> List[CompletionRule]:
    detector = ShapeCompletionDetector()
    return [rule for rule, _ in detector.detect(train_pairs, bg)]


def validate_completion_loo(rule: CompletionRule, train_pairs: List[Tuple], bg: int = 0) -> bool:
    if len(train_pairs) < 2:
        return False
    det_fn = ShapeCompletionOperator.DETECTORS.get(rule.family)
    if det_fn is None:
        return False
    for i in range(len(train_pairs)):
        held_inp, held_out = train_pairs[i]
        params = det_fn(held_inp, held_out, bg)
        if params is None:
            return False
        op = ShapeCompletionOperator(rule, params)
        pred = op.apply(held_inp, bg)
        if pred != held_out:
            return False
    return True


def falsify_completion(rule: CompletionRule, train_pairs: List[Tuple], bg: int = 0) -> List[Dict]:
    probes = []
    det_fn = ShapeCompletionOperator.DETECTORS.get(rule.family)
    if det_fn is None:
        probes.append({"probe": "detector_exists", "passed": False})
        return probes

    for i, (inp, out) in enumerate(train_pairs):
        params = det_fn(inp, out, bg)
        if params is None:
            probes.append({"probe": f"detection_pair_{i}", "passed": False})
            continue
        op = ShapeCompletionOperator(rule, params)
        pred = op.apply(inp, bg)
        probes.append({"probe": f"exact_match_pair_{i}", "passed": pred == out})

    probes.append({"probe": "loo", "passed": validate_completion_loo(rule, train_pairs, bg)})
    return probes
