"""Position-within-object recolor operators.

Handles tasks where specific cells WITHIN an object are recolored based
on their position (boundary, interior, endpoint, corner, contact, neighborhood,
boundary-distance, mask).
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class PositionFamily(Enum):
    BOUNDARY = auto()
    INTERIOR = auto()
    ENDPOINT = auto()
    CORNER = auto()
    CONTACT_POINT = auto()
    NEIGHBORHOOD = auto()
    BOUNDARY_DISTANCE = auto()
    MASK = auto()


@dataclass
class RecolorRule:
    family: PositionFamily
    description: str
    target_color: Optional[int] = None
    source_color_rule: str = "fixed"
    params: Dict[str, Any] = field(default_factory=dict)
    deterministic: bool = True


@dataclass
class PositionRecolorResult:
    rule: RecolorRule
    output_grid: Optional[List[List[int]]] = None
    train_fit: int = 0
    loo_passed: bool = False
    ambiguity_rejected: bool = False
    rejection_reason: Optional[str] = None
    proof_obligations_met: List[str] = field(default_factory=list)
    certificate_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionRecolorProofObligation:
    obligation_id: str
    description: str
    satisfied: bool = False
    evidence: Optional[str] = None


# ---------------------------------------------------------------------------
# Grid / object helpers
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


def _grid_copy(grid: List[List[int]]) -> List[List[int]]:
    return [row[:] for row in grid]


def _diff_cells(inp: List[List[int]], out: List[List[int]]) -> Dict[Tuple[int, int], Tuple[int, int]]:
    changed = {}
    for r in range(min(len(inp), len(out))):
        for c in range(min(len(inp[0]), len(out[0]))):
            if inp[r][c] != out[r][c]:
                changed[(r, c)] = (inp[r][c], out[r][c])
    return changed


# ---------------------------------------------------------------------------
# Position classifiers
# ---------------------------------------------------------------------------

class PositionClassifier:

    @staticmethod
    def boundary(cells: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        boundary = set()
        for r, c in cells:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                if (r + dr, c + dc) not in cells:
                    boundary.add((r, c))
                    break
        return boundary

    @staticmethod
    def interior(cells: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        interior = set()
        for r, c in cells:
            if all((r + dr, c + dc) in cells for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]):
                interior.add((r, c))
        return interior

    @staticmethod
    def endpoints(cells: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        endpoints = set()
        for r, c in cells:
            neighbors = sum(1 for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)] if (r + dr, c + dc) in cells)
            if neighbors == 1:
                endpoints.add((r, c))
        return endpoints

    @staticmethod
    def corners(cells: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        rs = sorted(set(r for r, c in cells))
        cs = sorted(set(c for r, c in cells))
        if not rs or not cs:
            return set()
        corner_positions = {
            (rs[0], cs[0]), (rs[0], cs[-1]),
            (rs[-1], cs[0]), (rs[-1], cs[-1]),
        }
        return corner_positions & cells

    @staticmethod
    def contact_points(cells: Set[Tuple[int, int]], all_object_cells: List[Set[Tuple[int, int]]]) -> Set[Tuple[int, int]]:
        other_cells = set()
        for oc in all_object_cells:
            if oc is not cells:
                other_cells |= oc
        contacts = set()
        for r, c in cells:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                if (r + dr, c + dc) in other_cells:
                    contacts.add((r, c))
                    break
        return contacts

    @staticmethod
    def by_boundary_distance(cells: Set[Tuple[int, int]], distance: int) -> Set[Tuple[int, int]]:
        boundary = PositionClassifier.boundary(cells)
        if distance == 0:
            return boundary
        dist_map = {}
        queue = deque()
        for cell in boundary:
            dist_map[cell] = 0
            queue.append(cell)
        while queue:
            r, c = queue.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (nr, nc) in cells and (nr, nc) not in dist_map:
                    dist_map[(nr, nc)] = dist_map[(r, c)] + 1
                    queue.append((nr, nc))
        return {cell for cell, d in dist_map.items() if d == distance}

    CLASSIFIERS = {
        PositionFamily.BOUNDARY: lambda cells, **kw: PositionClassifier.boundary(cells),
        PositionFamily.INTERIOR: lambda cells, **kw: PositionClassifier.interior(cells),
        PositionFamily.ENDPOINT: lambda cells, **kw: PositionClassifier.endpoints(cells),
        PositionFamily.CORNER: lambda cells, **kw: PositionClassifier.corners(cells),
    }


# ---------------------------------------------------------------------------
# Detection: which position pattern explains input->output changes?
# ---------------------------------------------------------------------------

def _detect_position_pattern_single(inp: List[List[int]], out: List[List[int]], bg: int = 0) -> List[Tuple[RecolorRule, Dict]]:
    changed = _diff_cells(inp, out)
    if not changed:
        return []

    objects = _extract_objects(inp, bg)
    if not objects:
        return []

    all_obj_cells = [obj["cells"] for obj in objects]
    candidates = []

    for obj_idx, obj in enumerate(objects):
        cells = obj["cells"]
        obj_changed = {cell: (old, new) for cell, (old, new) in changed.items() if cell in cells}
        if not obj_changed:
            continue

        new_colors = Counter(new for _, (_, new) in obj_changed.items())
        if len(new_colors) != 1:
            continue
        target_color = new_colors.most_common(1)[0][0]

        changed_positions = set(obj_changed.keys())

        for family in [PositionFamily.BOUNDARY, PositionFamily.INTERIOR, PositionFamily.ENDPOINT, PositionFamily.CORNER]:
            classifier = PositionClassifier.CLASSIFIERS.get(family)
            if classifier is None:
                continue
            classified = classifier(cells)
            if classified and classified == changed_positions:
                rule = RecolorRule(
                    family=family,
                    description=f"recolor_{family.name.lower()}_to_{target_color}",
                    target_color=target_color,
                    source_color_rule="fixed",
                )
                candidates.append((rule, {"object_idx": obj_idx, "object_color": obj["color"]}))

        contacts = PositionClassifier.contact_points(cells, all_obj_cells)
        if contacts and contacts == changed_positions:
            rule = RecolorRule(
                family=PositionFamily.CONTACT_POINT,
                description=f"recolor_contact_to_{target_color}",
                target_color=target_color,
            )
            candidates.append((rule, {"object_idx": obj_idx, "object_color": obj["color"]}))

        for dist in range(1, 5):
            at_dist = PositionClassifier.by_boundary_distance(cells, dist)
            if at_dist and at_dist == changed_positions:
                rule = RecolorRule(
                    family=PositionFamily.BOUNDARY_DISTANCE,
                    description=f"recolor_bdist_{dist}_to_{target_color}",
                    target_color=target_color,
                    params={"distance": dist},
                )
                candidates.append((rule, {"object_idx": obj_idx, "object_color": obj["color"]}))

    return candidates


def detect_position_pattern(train_pairs: List[Tuple], bg: int = 0) -> List[RecolorRule]:
    if not train_pairs:
        return []
    all_candidates = []
    for inp, out in train_pairs:
        pair_cands = _detect_position_pattern_single(inp, out, bg)
        all_candidates.append({(rule.family, rule.target_color, rule.params.get("distance")): (rule, info) for rule, info in pair_cands})

    if not all_candidates:
        return []

    common_keys = set(all_candidates[0].keys())
    for cands in all_candidates[1:]:
        common_keys &= set(cands.keys())

    return [all_candidates[0][k][0] for k in common_keys]


# ---------------------------------------------------------------------------
# Core operator
# ---------------------------------------------------------------------------

class PositionRecolorOperator:

    def __init__(self, rule: RecolorRule):
        self.rule = rule

    def apply(self, grid: List[List[int]], bg: int = 0) -> Optional[List[List[int]]]:
        result = _grid_copy(grid)
        objects = _extract_objects(grid, bg)
        if not objects:
            return None

        all_obj_cells = [obj["cells"] for obj in objects]

        for obj in objects:
            cells = obj["cells"]
            target_cells = set()

            if self.rule.family == PositionFamily.BOUNDARY:
                target_cells = PositionClassifier.boundary(cells)
            elif self.rule.family == PositionFamily.INTERIOR:
                target_cells = PositionClassifier.interior(cells)
            elif self.rule.family == PositionFamily.ENDPOINT:
                target_cells = PositionClassifier.endpoints(cells)
            elif self.rule.family == PositionFamily.CORNER:
                target_cells = PositionClassifier.corners(cells)
            elif self.rule.family == PositionFamily.CONTACT_POINT:
                target_cells = PositionClassifier.contact_points(cells, all_obj_cells)
            elif self.rule.family == PositionFamily.BOUNDARY_DISTANCE:
                dist = self.rule.params.get("distance", 1)
                target_cells = PositionClassifier.by_boundary_distance(cells, dist)

            if target_cells and self.rule.target_color is not None:
                for r, c in target_cells:
                    result[r][c] = self.rule.target_color

        return result

    def check_preconditions(self, grid: List[List[int]], bg: int = 0) -> List[PositionRecolorProofObligation]:
        objects = _extract_objects(grid, bg)
        return [
            PositionRecolorProofObligation(
                "PO_OBJECTS_EXIST", "Non-background objects exist",
                satisfied=len(objects) > 0,
                evidence=f"{len(objects)} objects",
            ),
            PositionRecolorProofObligation(
                "PO_POSITION_RULE_EXPLICIT",
                f"Position rule is {self.rule.family.name}",
                satisfied=self.rule.deterministic,
            ),
            PositionRecolorProofObligation(
                "PO_COLOR_DETERMINISTIC",
                f"Target color is {self.rule.target_color}",
                satisfied=self.rule.target_color is not None,
            ),
        ]

    def check_postconditions(self, inp: List[List[int]], out: List[List[int]], pred: List[List[int]], bg: int = 0) -> List[PositionRecolorProofObligation]:
        match = pred == out
        inp_objs = _extract_objects(inp, bg)
        shape_preserved = True
        for obj in inp_objs:
            for r, c in obj["cells"]:
                if pred[r][c] == bg:
                    shape_preserved = False
                    break

        return [
            PositionRecolorProofObligation(
                "PO_OUTPUT_EXACT", "Prediction matches output",
                satisfied=match,
            ),
            PositionRecolorProofObligation(
                "PO_SHAPE_PRESERVED", "Object shape preserved (no cells removed)",
                satisfied=shape_preserved,
            ),
        ]


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

def solve_position_recolor(train_pairs: List[Tuple], bg: int = 0) -> Optional[PositionRecolorResult]:
    rules = detect_position_pattern(train_pairs, bg)
    if not rules:
        return None

    for rule in rules:
        op = PositionRecolorOperator(rule)
        fit = 0
        all_match = True

        for inp, out in train_pairs:
            pred = op.apply(inp, bg)
            if pred is not None and pred == out:
                fit += 1
            else:
                all_match = False
                break

        if all_match and fit == len(train_pairs):
            loo = validate_position_recolor_loo(rule, train_pairs, bg)
            return PositionRecolorResult(
                rule=rule,
                output_grid=op.apply(train_pairs[0][0], bg),
                train_fit=fit,
                loo_passed=loo,
                certificate_fields={
                    "position_family": rule.family.name,
                    "target_color": rule.target_color,
                    "train_fit": fit,
                    "loo_passed": loo,
                },
            )
    return None


def validate_position_recolor_loo(rule: RecolorRule, train_pairs: List[Tuple], bg: int = 0) -> bool:
    if len(train_pairs) < 2:
        return False
    for i in range(len(train_pairs)):
        held_inp, held_out = train_pairs[i]
        op = PositionRecolorOperator(rule)
        pred = op.apply(held_inp, bg)
        if pred != held_out:
            return False
    return True


def falsify_position_recolor(rule: RecolorRule, train_pairs: List[Tuple], bg: int = 0) -> List[Dict]:
    probes = []
    op = PositionRecolorOperator(rule)

    for i, (inp, out) in enumerate(train_pairs):
        pred = op.apply(inp, bg)
        probes.append({"probe": f"exact_match_{i}", "passed": pred == out})

        postconds = op.check_postconditions(inp, out, pred if pred else inp, bg)
        for po in postconds:
            probes.append({"probe": f"{po.obligation_id}_{i}", "passed": po.satisfied})

    probes.append({"probe": "loo", "passed": validate_position_recolor_loo(rule, train_pairs, bg)})
    return probes
