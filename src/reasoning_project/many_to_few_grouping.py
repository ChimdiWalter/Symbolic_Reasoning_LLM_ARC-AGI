"""Many-to-few grouping operators.

Handles tasks where multiple input objects collapse/merge into fewer output objects.
Operator families: group-by-color, group-by-shape, group-by-proximity,
group-by-row/column, group-by-frame, group-by-separator, merge-fragments,
collapse-to-region, collapse-to-color-block, collapse-to-anchor.
"""
from __future__ import annotations

import itertools
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class GroupingFamily(Enum):
    BY_COLOR = auto()
    BY_SHAPE = auto()
    BY_PROXIMITY = auto()
    BY_ROW_COLUMN = auto()
    BY_ENCLOSING_FRAME = auto()
    BY_SEPARATOR = auto()
    MERGE_FRAGMENTS = auto()
    COLLAPSE_TO_REGION = auto()
    COLLAPSE_TO_COLOR_BLOCK = auto()
    COLLAPSE_TO_ANCHOR = auto()


@dataclass
class GroupingRule:
    family: GroupingFamily
    predicate_desc: str
    group_key_fn: Optional[Callable] = None
    params: Dict[str, Any] = field(default_factory=dict)
    deterministic: bool = True


@dataclass
class GroupAssignment:
    group_id: int
    object_indices: List[int]
    group_key: Any = None


@dataclass
class GroupingResult:
    rule: GroupingRule
    groups: List[GroupAssignment]
    output_grid: Optional[List[List[int]]] = None
    train_fit: int = 0
    loo_passed: bool = False
    ambiguity_rejected: bool = False
    rejection_reason: Optional[str] = None
    proof_obligations_met: List[str] = field(default_factory=list)
    certificate_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ManyToFewProofObligation:
    obligation_id: str
    description: str
    satisfied: bool = False
    evidence: Optional[str] = None


# ---------------------------------------------------------------------------
# Object / grid helpers
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
                    rs = [p[0] for p in cells]
                    cs = [p[1] for p in cells]
                    objects.append({
                        "cells": cells,
                        "color": color,
                        "size": len(cells),
                        "bbox": (min(rs), min(cs), max(rs), max(cs)),
                        "rows": set(rs),
                        "cols": set(cs),
                    })
    return objects


def _shape_signature(obj: Dict) -> Tuple:
    r0, c0, _, _ = obj["bbox"]
    normalized = tuple(sorted((r - r0, c - c0) for r, c in obj["cells"]))
    return normalized


def _centroid(obj: Dict) -> Tuple[float, float]:
    cells = obj["cells"]
    return sum(r for r, c in cells) / len(cells), sum(c for r, c in cells) / len(cells)


def _manhattan_dist(a: Dict, b: Dict) -> float:
    ca, cb = _centroid(a), _centroid(b)
    return abs(ca[0] - cb[0]) + abs(ca[1] - cb[1])


def _bounding_box_of_cells(cells: Set[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    return min(rs), min(cs), max(rs), max(cs)


def _reconstruct_grid(rows: int, cols: int, bg: int, cell_colors: Dict[Tuple[int, int], int]) -> List[List[int]]:
    grid = [[bg] * cols for _ in range(rows)]
    for (r, c), color in cell_colors.items():
        if 0 <= r < rows and 0 <= c < cols:
            grid[r][c] = color
    return grid


# ---------------------------------------------------------------------------
# Grouping algorithms
# ---------------------------------------------------------------------------

def _group_by_color(objects: List[Dict]) -> List[GroupAssignment]:
    by_color = defaultdict(list)
    for i, obj in enumerate(objects):
        by_color[obj["color"]].append(i)
    return [GroupAssignment(gid, idxs, key) for gid, (key, idxs) in enumerate(sorted(by_color.items()))]


def _group_by_shape(objects: List[Dict]) -> List[GroupAssignment]:
    by_shape = defaultdict(list)
    for i, obj in enumerate(objects):
        sig = _shape_signature(obj)
        by_shape[sig].append(i)
    return [GroupAssignment(gid, idxs, key) for gid, (key, idxs) in enumerate(sorted(by_shape.items(), key=lambda x: len(x[1]), reverse=True))]


def _group_by_proximity(objects: List[Dict], threshold: float = 3.0) -> List[GroupAssignment]:
    n = len(objects)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for i in range(n):
        for j in range(i + 1, n):
            if _manhattan_dist(objects[i], objects[j]) <= threshold:
                union(i, j)

    groups_map = defaultdict(list)
    for i in range(n):
        groups_map[find(i)].append(i)
    return [GroupAssignment(gid, idxs) for gid, idxs in enumerate(groups_map.values())]


def _group_by_row(objects: List[Dict]) -> List[GroupAssignment]:
    by_row = defaultdict(list)
    for i, obj in enumerate(objects):
        cr, _ = _centroid(obj)
        by_row[round(cr)].append(i)
    return [GroupAssignment(gid, idxs, key) for gid, (key, idxs) in enumerate(sorted(by_row.items()))]


def _group_by_column(objects: List[Dict]) -> List[GroupAssignment]:
    by_col = defaultdict(list)
    for i, obj in enumerate(objects):
        _, cc = _centroid(obj)
        by_col[round(cc)].append(i)
    return [GroupAssignment(gid, idxs, key) for gid, (key, idxs) in enumerate(sorted(by_col.items()))]


def _find_frames(objects: List[Dict], grid: List[List[int]]) -> Dict[int, List[int]]:
    """Find objects enclosed by larger rectangular frame objects."""
    frames = {}
    for i, obj in enumerate(objects):
        r0, c0, r1, c1 = obj["bbox"]
        area = (r1 - r0 + 1) * (c1 - c0 + 1)
        if obj["size"] > area * 0.5:
            continue
        border_cells = set()
        for r in range(r0, r1 + 1):
            border_cells.add((r, c0))
            border_cells.add((r, c1))
        for c in range(c0, c1 + 1):
            border_cells.add((r0, c))
            border_cells.add((r1, c))
        overlap = len(obj["cells"] & border_cells)
        if overlap >= len(border_cells) * 0.8:
            enclosed = []
            for j, other in enumerate(objects):
                if j == i:
                    continue
                or0, oc0, or1, oc1 = other["bbox"]
                if or0 > r0 and or1 < r1 and oc0 > c0 and oc1 < c1:
                    enclosed.append(j)
            if enclosed:
                frames[i] = enclosed
    return frames


def _group_by_frame(objects: List[Dict], grid: List[List[int]]) -> List[GroupAssignment]:
    frames = _find_frames(objects, grid)
    groups = []
    assigned = set()
    for gid, (frame_idx, enclosed_idxs) in enumerate(frames.items()):
        group_members = [frame_idx] + enclosed_idxs
        groups.append(GroupAssignment(gid, group_members, f"frame_{frame_idx}"))
        assigned.update(group_members)
    unassigned = [i for i in range(len(objects)) if i not in assigned]
    if unassigned:
        groups.append(GroupAssignment(len(groups), unassigned, "unframed"))
    return groups


def _find_separators(grid: List[List[int]], bg: int = 0) -> List[Tuple[str, int, int]]:
    """Find horizontal/vertical separator lines."""
    rows, cols = len(grid), len(grid[0])
    separators = []
    for r in range(rows):
        vals = set(grid[r])
        if len(vals) == 1 and bg not in vals:
            separators.append(("horizontal", r, grid[r][0]))
    for c in range(cols):
        vals = set(grid[r][c] for r in range(rows))
        if len(vals) == 1 and bg not in vals:
            separators.append(("vertical", c, grid[0][c]))
    return separators


def _group_by_separator(objects: List[Dict], grid: List[List[int]]) -> List[GroupAssignment]:
    separators = _find_separators(grid)
    if not separators:
        return [GroupAssignment(0, list(range(len(objects))))]

    h_seps = sorted([s[1] for s in separators if s[0] == "horizontal"])
    v_seps = sorted([s[1] for s in separators if s[0] == "vertical"])

    boundaries_r = [0] + h_seps + [len(grid)]
    boundaries_c = [0] + v_seps + [len(grid[0])]

    cell_groups = defaultdict(list)
    for i, obj in enumerate(objects):
        cr, cc = _centroid(obj)
        region_r = sum(1 for b in boundaries_r if cr >= b) - 1
        region_c = sum(1 for b in boundaries_c if cc >= b) - 1
        cell_groups[(region_r, region_c)].append(i)

    return [GroupAssignment(gid, idxs, key) for gid, (key, idxs) in enumerate(sorted(cell_groups.items()))]


def _merge_fragments(objects: List[Dict], grid: List[List[int]]) -> List[GroupAssignment]:
    """Merge spatially adjacent objects of any color into connected components."""
    rows, cols = len(grid), len(grid[0])
    n = len(objects)
    all_cells = {}
    for i, obj in enumerate(objects):
        for cell in obj["cells"]:
            all_cells[cell] = i

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for (r, c), obj_i in all_cells.items():
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (nr, nc) in all_cells:
                union(obj_i, all_cells[(nr, nc)])

    groups_map = defaultdict(list)
    for i in range(n):
        groups_map[find(i)].append(i)
    return [GroupAssignment(gid, idxs) for gid, idxs in enumerate(groups_map.values())]


# ---------------------------------------------------------------------------
# Reconstruction: how groups become output
# ---------------------------------------------------------------------------

def _collapse_group_to_bounding_box(objects: List[Dict], group: GroupAssignment, color: Optional[int] = None) -> Dict[Tuple[int, int], int]:
    all_cells = set()
    colors = Counter()
    for idx in group.object_indices:
        all_cells |= objects[idx]["cells"]
        colors[objects[idx]["color"]] += objects[idx]["size"]
    fill_color = color if color is not None else colors.most_common(1)[0][0]
    r0, c0, r1, c1 = _bounding_box_of_cells(all_cells)
    result = {}
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            result[(r, c)] = fill_color
    return result


def _collapse_group_to_union(objects: List[Dict], group: GroupAssignment, color: Optional[int] = None) -> Dict[Tuple[int, int], int]:
    all_cells = set()
    colors = Counter()
    for idx in group.object_indices:
        all_cells |= objects[idx]["cells"]
        colors[objects[idx]["color"]] += objects[idx]["size"]
    fill_color = color if color is not None else colors.most_common(1)[0][0]
    return {cell: fill_color for cell in all_cells}


def _collapse_group_keep_largest(objects: List[Dict], group: GroupAssignment) -> Dict[Tuple[int, int], int]:
    largest_idx = max(group.object_indices, key=lambda i: objects[i]["size"])
    obj = objects[largest_idx]
    return {cell: obj["color"] for cell in obj["cells"]}


# ---------------------------------------------------------------------------
# Core operator
# ---------------------------------------------------------------------------

class ManyToFewOperator:

    GROUPING_FNS = {
        GroupingFamily.BY_COLOR: lambda objs, grid: _group_by_color(objs),
        GroupingFamily.BY_SHAPE: lambda objs, grid: _group_by_shape(objs),
        GroupingFamily.BY_PROXIMITY: lambda objs, grid: _group_by_proximity(objs),
        GroupingFamily.BY_ROW_COLUMN: lambda objs, grid: _group_by_row(objs),
        GroupingFamily.BY_ENCLOSING_FRAME: _group_by_frame,
        GroupingFamily.BY_SEPARATOR: _group_by_separator,
        GroupingFamily.MERGE_FRAGMENTS: _merge_fragments,
    }

    COLLAPSE_FNS = {
        "bounding_box": _collapse_group_to_bounding_box,
        "union": _collapse_group_to_union,
        "keep_largest": _collapse_group_keep_largest,
    }

    def __init__(self, rule: GroupingRule, collapse_mode: str = "union"):
        self.rule = rule
        self.collapse_mode = collapse_mode

    def apply(self, grid: List[List[int]], bg: int = 0) -> Optional[List[List[int]]]:
        objects = _extract_objects(grid, bg)
        if not objects:
            return None

        grouping_fn = self.GROUPING_FNS.get(self.rule.family)
        if grouping_fn is None:
            return None

        try:
            if self.rule.family in (GroupingFamily.BY_ENCLOSING_FRAME, GroupingFamily.BY_SEPARATOR, GroupingFamily.MERGE_FRAGMENTS):
                groups = grouping_fn(objects, grid)
            else:
                groups = grouping_fn(objects, grid)
        except Exception:
            return None

        if len(groups) >= len(objects):
            return None

        rows, cols = len(grid), len(grid[0])
        cell_colors = {}
        collapse_fn = self.COLLAPSE_FNS.get(self.collapse_mode, _collapse_group_to_union)

        for group in groups:
            if len(group.object_indices) <= 1:
                for idx in group.object_indices:
                    for cell in objects[idx]["cells"]:
                        cell_colors[cell] = objects[idx]["color"]
            else:
                collapsed = collapse_fn(objects, group)
                cell_colors.update(collapsed)

        return _reconstruct_grid(rows, cols, bg, cell_colors)

    def check_preconditions(self, grid: List[List[int]], bg: int = 0) -> List[ManyToFewProofObligation]:
        objects = _extract_objects(grid, bg)
        obligations = []
        obligations.append(ManyToFewProofObligation(
            "PO_OBJECTS_EXIST",
            "At least 2 non-background objects exist",
            satisfied=len(objects) >= 2,
            evidence=f"{len(objects)} objects found",
        ))
        obligations.append(ManyToFewProofObligation(
            "PO_GROUPING_DETERMINISTIC",
            "Grouping rule produces deterministic assignment",
            satisfied=self.rule.deterministic,
        ))
        return obligations

    def check_postconditions(self, inp: List[List[int]], out: List[List[int]], pred: List[List[int]], bg: int = 0) -> List[ManyToFewProofObligation]:
        obligations = []
        match = pred == out
        obligations.append(ManyToFewProofObligation(
            "PO_OUTPUT_EXACT",
            "Prediction matches expected output exactly",
            satisfied=match,
        ))
        inp_objs = _extract_objects(inp, bg)
        out_objs = _extract_objects(out, bg)
        obligations.append(ManyToFewProofObligation(
            "PO_FEWER_OBJECTS",
            "Output has fewer objects than input",
            satisfied=len(out_objs) < len(inp_objs),
            evidence=f"input={len(inp_objs)}, output={len(out_objs)}",
        ))
        return obligations


# ---------------------------------------------------------------------------
# Solver: try all grouping families
# ---------------------------------------------------------------------------

def solve_many_to_few(train_pairs: List[Tuple], bg: int = 0) -> Optional[GroupingResult]:
    families = [
        (GroupingFamily.BY_COLOR, "union"),
        (GroupingFamily.BY_COLOR, "bounding_box"),
        (GroupingFamily.BY_SHAPE, "union"),
        (GroupingFamily.BY_SHAPE, "keep_largest"),
        (GroupingFamily.BY_PROXIMITY, "union"),
        (GroupingFamily.BY_ROW_COLUMN, "union"),
        (GroupingFamily.BY_ENCLOSING_FRAME, "union"),
        (GroupingFamily.BY_SEPARATOR, "union"),
        (GroupingFamily.MERGE_FRAGMENTS, "union"),
    ]

    for family, collapse in families:
        rule = GroupingRule(family=family, predicate_desc=f"{family.name}+{collapse}")
        op = ManyToFewOperator(rule, collapse_mode=collapse)

        fit = 0
        all_match = True
        for inp, out in train_pairs:
            pred = op.apply(inp, bg)
            if pred is not None and pred == out:
                fit += 1
            else:
                all_match = False

        if all_match and fit == len(train_pairs):
            loo = validate_grouping_loo(rule, collapse, train_pairs, bg)
            objects = _extract_objects(train_pairs[0][0], bg)
            grouping_fn = ManyToFewOperator.GROUPING_FNS.get(family)
            try:
                if family in (GroupingFamily.BY_ENCLOSING_FRAME, GroupingFamily.BY_SEPARATOR, GroupingFamily.MERGE_FRAGMENTS):
                    groups = grouping_fn(objects, train_pairs[0][0])
                else:
                    groups = grouping_fn(objects, train_pairs[0][0])
            except Exception:
                groups = []

            return GroupingResult(
                rule=rule,
                groups=groups,
                output_grid=op.apply(train_pairs[0][0], bg),
                train_fit=fit,
                loo_passed=loo,
                certificate_fields={
                    "grouping_family": family.name,
                    "collapse_mode": collapse,
                    "train_fit": fit,
                    "loo_passed": loo,
                    "n_groups": len(groups),
                },
            )

    return None


def validate_grouping_loo(rule: GroupingRule, collapse: str, train_pairs: List[Tuple], bg: int = 0) -> bool:
    if len(train_pairs) < 2:
        return False
    for i in range(len(train_pairs)):
        held_out = train_pairs[i]
        remaining = train_pairs[:i] + train_pairs[i + 1:]
        op = ManyToFewOperator(rule, collapse_mode=collapse)
        all_remaining_fit = all(op.apply(inp, bg) == out for inp, out in remaining)
        if not all_remaining_fit:
            return False
        pred = op.apply(held_out[0], bg)
        if pred != held_out[1]:
            return False
    return True


@dataclass
class FalsificationProbe:
    probe_type: str
    description: str
    passed: bool = False


def falsify_grouping(rule: GroupingRule, collapse: str, train_pairs: List[Tuple], bg: int = 0) -> List[FalsificationProbe]:
    probes = []
    op = ManyToFewOperator(rule, collapse_mode=collapse)

    for inp, out in train_pairs:
        in_objs = _extract_objects(inp, bg)
        out_objs = _extract_objects(out, bg)
        probes.append(FalsificationProbe(
            "fewer_objects",
            f"Output has fewer objects ({len(out_objs)}) than input ({len(in_objs)})",
            passed=len(out_objs) < len(in_objs),
        ))

    for inp, out in train_pairs:
        pred = op.apply(inp, bg)
        probes.append(FalsificationProbe(
            "exact_match",
            "Prediction matches output exactly",
            passed=pred == out,
        ))

    if len(train_pairs) >= 2:
        loo = validate_grouping_loo(rule, collapse, train_pairs, bg)
        probes.append(FalsificationProbe(
            "loo_validation",
            "Leave-one-out validation passes",
            passed=loo,
        ))

    return probes


# ---------------------------------------------------------------------------
# Inventor: mine from near-solved / failure traces
# ---------------------------------------------------------------------------

class ManyToFewInventor:

    def identify_candidates(self, tasks: List[Tuple[str, dict]], bg: int = 0) -> List[Dict]:
        candidates = []
        for tid, task in tasks:
            train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
            is_m2f = False
            for inp, out in train_pairs:
                in_objs = _extract_objects(inp, bg)
                out_objs = _extract_objects(out, bg)
                if len(out_objs) < len(in_objs) and len(in_objs) >= 2:
                    is_m2f = True
                    break
            if is_m2f:
                result = solve_many_to_few(train_pairs, bg)
                candidates.append({
                    "task_id": tid,
                    "solved": result is not None,
                    "grouping_family": result.rule.family.name if result else None,
                    "loo_passed": result.loo_passed if result else False,
                })
        return candidates
