"""Neural-math modules for adaptive structural reasoning.

Provides six CPU-friendly components that improve hypothesis generation,
verification, and composition for ARC-style visual reasoning:

1. TypedDSL         -- Neural type system for program composition
2. SheafConsistency -- Relational constraint satisfaction
3. EquivariantFeatures -- Symmetry-invariant structural features
4. InvariantDiscovery  -- Learn what doesn't change across input-output pairs
5. CounterfactualVerifier -- Causal verification of hypotheses
6. TopologicalLoss  -- Persistent homology for structural similarity
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import product as itertools_product
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)

import numpy as np

try:
    from scipy import ndimage as _ndimage
except ImportError:  # pragma: no cover
    _ndimage = None  # type: ignore[assignment]


# ====================================================================
# 1. TypedDSL -- Neural type system for program composition
# ====================================================================

TYPES: Set[str] = {
    "Grid",
    "Objects",
    "Object",
    "Color",
    "Int",
    "Bool",
    "Position",
    "Predicate",
}

OP_SIGNATURES: Dict[str, Tuple[List[str], str]] = {
    "extract_objects": (["Grid"], "Objects"),
    "filter": (["Objects", "Predicate"], "Objects"),
    "keep_largest": (["Objects"], "Object"),
    "keep_smallest": (["Objects"], "Object"),
    "count": (["Objects"], "Int"),
    "recolor": (["Object", "Color"], "Object"),
    "move": (["Object", "Position"], "Object"),
    "compose_grid": (["Objects"], "Grid"),
    "is_hollow": (["Object"], "Bool"),
    "is_largest": (["Object"], "Bool"),
    "touches_boundary": (["Object"], "Bool"),
    "get_color": (["Object"], "Color"),
    "get_position": (["Object"], "Position"),
    "get_size": (["Object"], "Int"),
}


class TypeChecker:
    """Validates sequences of typed operations for composability."""

    def __init__(
        self,
        op_signatures: Optional[Dict[str, Tuple[List[str], str]]] = None,
    ) -> None:
        self.op_signatures = dict(op_signatures or OP_SIGNATURES)

    # ------------------------------------------------------------------
    def is_valid_program(self, ops: List[str]) -> bool:
        """Return True if *ops* (list of operation names) forms a type-valid
        sequential pipeline starting from a ``Grid`` input.

        We model a *stack* of typed values.  Each operation pops its input
        types from the stack (rightmost = top) and pushes its output.
        The initial stack contains a single ``Grid``.
        """
        if not ops:
            return True
        stack: List[str] = ["Grid"]
        for op_name in ops:
            sig = self.op_signatures.get(op_name)
            if sig is None:
                return False
            in_types, out_type = sig
            # Try to consume required inputs from the stack (top first).
            needed = list(in_types)  # copy
            for t in reversed(needed):
                if t not in stack:
                    return False
                # Remove the *last* occurrence so that the stack behaves
                # in a LIFO manner.
                idx = len(stack) - 1 - stack[::-1].index(t)
                stack.pop(idx)
            stack.append(out_type)
        return True

    # ------------------------------------------------------------------
    def output_type(self, ops: List[str]) -> Optional[str]:
        """Return the type on top of the stack after running *ops*,
        or ``None`` if the program is invalid."""
        if not self.is_valid_program(ops):
            return None
        stack: List[str] = ["Grid"]
        for op_name in ops:
            in_types, out_type = self.op_signatures[op_name]
            for t in reversed(in_types):
                idx = len(stack) - 1 - stack[::-1].index(t)
                stack.pop(idx)
            stack.append(out_type)
        return stack[-1] if stack else None


def typed_enumerate(
    max_depth: int = 2,
    op_signatures: Optional[Dict[str, Tuple[List[str], str]]] = None,
) -> Generator[List[str], None, None]:
    """Yield all type-valid programs up to *max_depth* operations."""
    checker = TypeChecker(op_signatures)
    op_names = sorted((op_signatures or OP_SIGNATURES).keys())

    for depth in range(1, max_depth + 1):
        for combo in itertools_product(op_names, repeat=depth):
            prog = list(combo)
            if checker.is_valid_program(prog):
                yield prog


def count_typed_programs(
    max_depth: int = 2,
    op_signatures: Optional[Dict[str, Tuple[List[str], str]]] = None,
) -> Dict[str, Any]:
    """Return counts of type-valid vs total programs up to *max_depth*."""
    sigs = op_signatures or OP_SIGNATURES
    n_ops = len(sigs)
    total = sum(n_ops ** d for d in range(1, max_depth + 1))
    valid = sum(1 for _ in typed_enumerate(max_depth, sigs))
    return {"valid": valid, "total": total, "ratio": valid / max(total, 1)}


# ====================================================================
# 2. SheafConsistency -- Relational constraint satisfaction
# ====================================================================

@dataclass
class _Edge:
    i: int
    j: int
    relation_type: str
    constraint_fn: Callable[[Any, Any], bool]


class SheafConsistency:
    """Model objects as nodes with local constraints on edges.

    A *section* assigns a value (color, property, transformation) to each
    node.  Consistency requires neighbouring assignments to agree according
    to the edge constraint function.
    """

    def __init__(self) -> None:
        self.nodes: List[int] = []
        self.edges: List[_Edge] = []
        self._node_set: Set[int] = set()

    # ------------------------------------------------------------------
    def add_node(self, node_id: int) -> None:
        if node_id not in self._node_set:
            self.nodes.append(node_id)
            self._node_set.add(node_id)

    def add_relation(
        self,
        obj_i: int,
        obj_j: int,
        relation_type: str,
        constraint_fn: Callable[[Any, Any], bool],
    ) -> None:
        """Add consistency constraint between two objects."""
        self.add_node(obj_i)
        self.add_node(obj_j)
        self.edges.append(_Edge(obj_i, obj_j, relation_type, constraint_fn))

    # ------------------------------------------------------------------
    def check_global_consistency(self, assignment: Dict[int, Any]) -> float:
        """Fraction of edges where the local assignments satisfy the constraint."""
        if not self.edges:
            return 1.0
        satisfied = 0
        for e in self.edges:
            val_i = assignment.get(e.i)
            val_j = assignment.get(e.j)
            if val_i is not None and val_j is not None:
                try:
                    if e.constraint_fn(val_i, val_j):
                        satisfied += 1
                except Exception:
                    pass
        return satisfied / len(self.edges)

    # ------------------------------------------------------------------
    def find_consistent_assignment(
        self, candidates: Dict[int, List[Any]]
    ) -> Dict[int, Any]:
        """Find assignment that maximises global consistency (greedy search)."""
        # Build adjacency list for fast neighbour look-up.
        adj: Dict[int, List[_Edge]] = {n: [] for n in self.nodes}
        for e in self.edges:
            adj[e.i].append(e)
            adj[e.j].append(e)

        best_assignment: Dict[int, Any] = {}
        best_score = -1.0

        # Start from each node to reduce order-dependence bias.
        for start in self.nodes:
            assignment: Dict[int, Any] = {}
            order = self._bfs_order(start)
            for node in order:
                cands = candidates.get(node, [None])
                best_val = cands[0]
                best_local = -1
                for val in cands:
                    assignment[node] = val
                    local_ok = 0
                    local_total = 0
                    for e in adj[node]:
                        other = e.j if e.i == node else e.i
                        if other in assignment:
                            local_total += 1
                            try:
                                vi = assignment[node] if e.i == node else assignment[other]
                                vj = assignment[other] if e.i == node else assignment[node]
                                if e.constraint_fn(vi, vj):
                                    local_ok += 1
                            except Exception:
                                pass
                    if local_ok > best_local:
                        best_local = local_ok
                        best_val = val
                assignment[node] = best_val

            score = self.check_global_consistency(assignment)
            if score > best_score:
                best_score = score
                best_assignment = dict(assignment)

        return best_assignment

    # ------------------------------------------------------------------
    def detect_inconsistency(self, assignment: Dict[int, Any]) -> List[Tuple[int, int, str]]:
        """Return list of ``(i, j, relation_type)`` where consistency is violated."""
        violations: List[Tuple[int, int, str]] = []
        for e in self.edges:
            val_i = assignment.get(e.i)
            val_j = assignment.get(e.j)
            if val_i is None or val_j is None:
                violations.append((e.i, e.j, e.relation_type))
                continue
            try:
                if not e.constraint_fn(val_i, val_j):
                    violations.append((e.i, e.j, e.relation_type))
            except Exception:
                violations.append((e.i, e.j, e.relation_type))
        return violations

    # ------------------------------------------------------------------
    def _bfs_order(self, start: int) -> List[int]:
        adj_simple: Dict[int, List[int]] = {n: [] for n in self.nodes}
        for e in self.edges:
            adj_simple[e.i].append(e.j)
            adj_simple[e.j].append(e.i)
        visited: Set[int] = set()
        order: List[int] = []
        queue: deque[int] = deque()
        queue.append(start)
        visited.add(start)
        while queue:
            node = queue.popleft()
            order.append(node)
            for nb in adj_simple[node]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        # Append unreachable nodes at the end.
        for n in self.nodes:
            if n not in visited:
                order.append(n)
        return order


# ====================================================================
# 3. EquivariantFeatures -- Symmetry-invariant structural features
# ====================================================================

class EquivariantFeatures:
    """Compute features invariant to rotation, reflection, translation,
    and color permutation."""

    # ------------------------------------------------------------------
    @staticmethod
    def compute(grid: np.ndarray) -> np.ndarray:
        """Compute a fixed-length feature vector invariant to rotation,
        reflection, and color permutation for the full grid."""
        ef = EquivariantFeatures()
        mask = (grid != 0).astype(np.float64)
        obj_inv = ef.object_invariants(mask)
        color_feat = ef.color_orbit(grid)
        # Aggregate into a single feature vector.
        return np.concatenate([obj_inv, color_feat])

    # ------------------------------------------------------------------
    @staticmethod
    def object_invariants(obj_mask: np.ndarray) -> np.ndarray:
        """Per-object invariants: area, perimeter, Euler char, central
        moments, Hu moments (rotation-invariant)."""
        mask = np.asarray(obj_mask, dtype=np.float64)
        if mask.ndim != 2 or mask.size == 0:
            return np.zeros(16, dtype=np.float64)
        area = float(mask.sum())
        h, w = mask.shape
        # Perimeter: count boundary pixels (4-connected).
        perimeter = 0.0
        for r in range(h):
            for c in range(w):
                if mask[r, c] > 0:
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = r + dr, c + dc
                        if nr < 0 or nr >= h or nc < 0 or nc >= w or mask[nr, nc] == 0:
                            perimeter += 1.0

        # Euler characteristic via pixel count.
        n_holes = _count_holes_binary(mask > 0)
        euler = 1 - n_holes

        # Central moments and Hu moments.
        hu = _hu_moments(mask)

        feats = np.zeros(16, dtype=np.float64)
        feats[0] = area
        feats[1] = perimeter
        feats[2] = float(euler)
        feats[3] = float(n_holes)
        feats[4] = area / max(h * w, 1)  # density
        feats[5] = float(h) / max(float(w), 1.0)  # aspect ratio
        feats[6:13] = hu[:7]
        feats[13] = float(h)
        feats[14] = float(w)
        feats[15] = perimeter / max(area, 1.0)  # compactness
        return feats

    # ------------------------------------------------------------------
    @staticmethod
    def relation_invariants(obj_a: np.ndarray, obj_b: np.ndarray) -> np.ndarray:
        """Pairwise relation invariants between two binary masks (same grid frame)."""
        a = np.asarray(obj_a, dtype=np.float64)
        b = np.asarray(obj_b, dtype=np.float64)
        if a.shape != b.shape:
            # Pad to common shape.
            h = max(a.shape[0], b.shape[0])
            w = max(a.shape[1], b.shape[1])
            pa = np.zeros((h, w), dtype=np.float64)
            pb = np.zeros((h, w), dtype=np.float64)
            pa[: a.shape[0], : a.shape[1]] = a
            pb[: b.shape[0], : b.shape[1]] = b
            a, b = pa, pb

        area_a = float(a.sum())
        area_b = float(b.sum())

        # Centroid distance.
        ca = _centroid(a)
        cb = _centroid(b)
        dist = np.sqrt((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2)

        # Relative size ratio.
        size_ratio = min(area_a, area_b) / max(area_a, area_b, 1.0)

        # Overlap (containment measure).
        overlap = float((a * b).sum())
        containment_a_in_b = overlap / max(area_a, 1.0)
        containment_b_in_a = overlap / max(area_b, 1.0)

        # Adjacency: dilate a, check overlap with b.
        adj = 0.0
        if area_a > 0 and area_b > 0:
            dilated = np.zeros_like(a)
            h, w = a.shape
            for r in range(h):
                for c in range(w):
                    if a[r, c] > 0:
                        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < h and 0 <= nc < w:
                                dilated[nr, nc] = 1.0
            adj = min(float((dilated * b).sum()), 1.0)

        return np.array(
            [dist, size_ratio, containment_a_in_b, containment_b_in_a, adj, area_a, area_b],
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def color_orbit(grid: np.ndarray) -> np.ndarray:
        """Canonical form under color permutation -- colour histogram
        sorted descending by frequency.  Returns a fixed-length
        10-element vector (ARC uses colours 0-9)."""
        arr = np.asarray(grid, dtype=int)
        hist = np.zeros(10, dtype=np.float64)
        for c in range(10):
            hist[c] = float((arr == c).sum())
        total = max(hist.sum(), 1.0)
        hist /= total
        hist[::-1].sort()
        return hist


# -- helpers --

def _centroid(mask: np.ndarray) -> Tuple[float, float]:
    total = float(mask.sum())
    if total == 0:
        return (0.0, 0.0)
    h, w = mask.shape
    rows = np.arange(h, dtype=np.float64)
    cols = np.arange(w, dtype=np.float64)
    cr = float(np.dot(rows, mask.sum(axis=1))) / total
    cc = float(np.dot(cols, mask.sum(axis=0))) / total
    return (cr, cc)


def _central_moments(mask: np.ndarray) -> Dict[str, float]:
    """Raw and normalised central moments up to order 3."""
    total = float(mask.sum())
    if total == 0:
        return {"mu20": 0, "mu02": 0, "mu11": 0, "mu30": 0, "mu03": 0, "mu21": 0, "mu12": 0}
    cr, cc = _centroid(mask)
    h, w = mask.shape
    rs, cs = np.meshgrid(np.arange(h, dtype=np.float64), np.arange(w, dtype=np.float64), indexing="ij")
    dr = rs - cr
    dc = cs - cc

    def _mu(p: int, q: int) -> float:
        return float(np.sum(mask * (dr ** p) * (dc ** q)))

    return {
        "mu20": _mu(2, 0),
        "mu02": _mu(0, 2),
        "mu11": _mu(1, 1),
        "mu30": _mu(3, 0),
        "mu03": _mu(0, 3),
        "mu21": _mu(2, 1),
        "mu12": _mu(1, 2),
    }


def _hu_moments(mask: np.ndarray) -> np.ndarray:
    """Compute 7 Hu moments (rotation-invariant image moments)."""
    m = _central_moments(mask)
    total = float(mask.sum())
    if total == 0:
        return np.zeros(7, dtype=np.float64)

    # Normalise central moments: eta_pq = mu_pq / mu00^((p+q)/2 + 1)
    def eta(p: int, q: int) -> float:
        gamma = (p + q) / 2.0 + 1.0
        return m[f"mu{p}{q}"] / (total ** gamma) if total > 0 else 0.0

    n20 = eta(2, 0)
    n02 = eta(0, 2)
    n11 = eta(1, 1)
    n30 = eta(3, 0)
    n03 = eta(0, 3)
    n21 = eta(2, 1)
    n12 = eta(1, 2)

    h1 = n20 + n02
    h2 = (n20 - n02) ** 2 + 4 * n11 ** 2
    h3 = (n30 - 3 * n12) ** 2 + (3 * n21 - n03) ** 2
    h4 = (n30 + n12) ** 2 + (n21 + n03) ** 2
    h5 = (
        (n30 - 3 * n12) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2)
        + (3 * n21 - n03) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2)
    )
    h6 = (n20 - n02) * ((n30 + n12) ** 2 - (n21 + n03) ** 2) + 4 * n11 * (n30 + n12) * (n21 + n03)
    h7 = (
        (3 * n21 - n03) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2)
        - (n30 - 3 * n12) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2)
    )

    return np.array([h1, h2, h3, h4, h5, h6, h7], dtype=np.float64)


def _count_holes_binary(mask: np.ndarray) -> int:
    """Count enclosed background regions inside a binary mask."""
    if mask.size == 0:
        return 0
    padded = np.pad(mask.astype(bool), 1, constant_values=False)
    background = ~padded
    h, w = background.shape
    seen = np.zeros_like(background, dtype=bool)
    # Flood-fill from border.
    queue: deque[Tuple[int, int]] = deque()
    for r in range(h):
        for c in (0, w - 1):
            if background[r, c] and not seen[r, c]:
                queue.append((r, c))
                seen[r, c] = True
    for c in range(w):
        for r in (0, h - 1):
            if background[r, c] and not seen[r, c]:
                queue.append((r, c))
                seen[r, c] = True
    while queue:
        r, c = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and background[nr, nc] and not seen[nr, nc]:
                seen[nr, nc] = True
                queue.append((nr, nc))

    # Remaining unseen background pixels are holes.
    holes = 0
    for r in range(h):
        for c in range(w):
            if background[r, c] and not seen[r, c]:
                # Flood-fill this hole to count it once.
                holes += 1
                hq: deque[Tuple[int, int]] = deque()
                hq.append((r, c))
                seen[r, c] = True
                while hq:
                    hr, hc = hq.popleft()
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = hr + dr, hc + dc
                        if 0 <= nr < h and 0 <= nc < w and background[nr, nc] and not seen[nr, nc]:
                            seen[nr, nc] = True
                            hq.append((nr, nc))
    return holes


def _connected_components(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    """Label 4-connected components in a binary mask.  Returns
    ``(labeled, n_components)``."""
    bmask = np.asarray(mask, dtype=bool)
    h, w = bmask.shape
    labels = np.zeros((h, w), dtype=int)
    current_label = 0
    for r in range(h):
        for c in range(w):
            if bmask[r, c] and labels[r, c] == 0:
                current_label += 1
                queue: deque[Tuple[int, int]] = deque()
                queue.append((r, c))
                labels[r, c] = current_label
                while queue:
                    cr_, cc_ = queue.popleft()
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = cr_ + dr, cc_ + dc
                        if 0 <= nr < h and 0 <= nc < w and bmask[nr, nc] and labels[nr, nc] == 0:
                            labels[nr, nc] = current_label
                            queue.append((nr, nc))
    return labels, current_label


# ====================================================================
# 4. InvariantDiscovery -- Learn what doesn't change
# ====================================================================

# -- Built-in property extractors --

def _prop_object_count(grid: np.ndarray) -> int:
    _, n = _connected_components(grid != 0)
    return n


def _prop_color_set(grid: np.ndarray) -> Tuple[int, ...]:
    return tuple(sorted(set(grid.flat)))


def _prop_grid_shape(grid: np.ndarray) -> Tuple[int, int]:
    return (int(grid.shape[0]), int(grid.shape[1]))


def _prop_has_separators(grid: np.ndarray) -> bool:
    """True if any full row or full column is uniform nonzero."""
    arr = np.asarray(grid, dtype=int)
    for r in range(arr.shape[0]):
        row = arr[r, :]
        if row.min() == row.max() and row.min() != 0:
            return True
    for c in range(arr.shape[1]):
        col = arr[:, c]
        if col.min() == col.max() and col.min() != 0:
            return True
    return False


def _prop_symmetry_type(grid: np.ndarray) -> str:
    arr = np.asarray(grid, dtype=int)
    h_sym = np.array_equal(arr, arr[::-1, :])
    v_sym = np.array_equal(arr, arr[:, ::-1])
    if h_sym and v_sym:
        return "both"
    if h_sym:
        return "horizontal"
    if v_sym:
        return "vertical"
    return "none"


def _prop_n_holes(grid: np.ndarray) -> int:
    return _count_holes_binary(grid != 0)


def _prop_total_nonzero_area(grid: np.ndarray) -> int:
    return int((grid != 0).sum())


def _prop_color_histogram_sorted(grid: np.ndarray) -> Tuple[int, ...]:
    hist = []
    for c in range(10):
        hist.append(int((grid == c).sum()))
    hist.sort(reverse=True)
    return tuple(hist)


def _prop_bounding_box_of_all_objects(grid: np.ndarray) -> Tuple[int, int]:
    """Height and width of the bounding box of all nonzero pixels."""
    coords = np.argwhere(grid != 0)
    if coords.size == 0:
        return (0, 0)
    return (
        int(coords[:, 0].max() - coords[:, 0].min() + 1),
        int(coords[:, 1].max() - coords[:, 1].min() + 1),
    )


def _prop_is_connected(grid: np.ndarray) -> bool:
    _, n = _connected_components(grid != 0)
    return n <= 1


DEFAULT_PROPERTY_EXTRACTORS: Dict[str, Callable[[np.ndarray], Any]] = {
    "object_count": _prop_object_count,
    "color_set": _prop_color_set,
    "grid_shape": _prop_grid_shape,
    "has_separators": _prop_has_separators,
    "symmetry_type": _prop_symmetry_type,
    "n_holes": _prop_n_holes,
    "total_nonzero_area": _prop_total_nonzero_area,
    "color_histogram_sorted": _prop_color_histogram_sorted,
    "bounding_box_of_all_objects": _prop_bounding_box_of_all_objects,
    "is_connected": _prop_is_connected,
}


class InvariantDiscovery:
    """Discover which structural properties are preserved, transformed,
    or irrelevant across a set of input-output training pairs."""

    def __init__(
        self,
        property_extractors: Optional[Dict[str, Callable[[np.ndarray], Any]]] = None,
    ) -> None:
        self.property_extractors = dict(property_extractors or DEFAULT_PROPERTY_EXTRACTORS)

    # ------------------------------------------------------------------
    def discover(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> Dict[str, List[Any]]:
        """Analyse train pairs and classify each property.

        Returns ``{"preserved": [...], "transformed": [...], "irrelevant": [...]}``.

        * *preserved*: property value is identical in input and output for
          every pair.
        * *transformed*: property value changes but the *type* of change is
          consistent across pairs (e.g. always doubles).
        * *irrelevant*: changes with no detectable pattern.
        """
        preserved: List[str] = []
        transformed: List[Tuple[str, str]] = []
        irrelevant: List[str] = []

        for name, fn in self.property_extractors.items():
            in_vals = []
            out_vals = []
            for inp, out in train_pairs:
                try:
                    in_vals.append(fn(inp))
                    out_vals.append(fn(out))
                except Exception:
                    in_vals.append(None)
                    out_vals.append(None)

            if all(iv == ov for iv, ov in zip(in_vals, out_vals)):
                preserved.append(name)
                continue

            # Check for systematic numeric transforms.
            transform_type = self._detect_numeric_transform(in_vals, out_vals)
            if transform_type is not None:
                transformed.append((name, transform_type))
                continue

            irrelevant.append(name)

        return {
            "preserved": preserved,
            "transformed": transformed,
            "irrelevant": irrelevant,
        }

    # ------------------------------------------------------------------
    def prune_search_space(
        self,
        candidates: List[Dict[str, Any]],
        invariants: Dict[str, List[Any]],
    ) -> List[Dict[str, Any]]:
        """Remove candidate hypotheses that violate discovered invariants.

        Each candidate is a dict with at least ``{"prediction": np.ndarray}``.
        Only candidates whose predicted output preserves the *preserved*
        properties (relative to the candidate's ``"input"`` if present) are kept.
        """
        preserved = invariants.get("preserved", [])
        if not preserved:
            return list(candidates)

        kept: List[Dict[str, Any]] = []
        for cand in candidates:
            pred = cand.get("prediction")
            inp = cand.get("input")
            if pred is None:
                kept.append(cand)
                continue
            ok = True
            for prop_name in preserved:
                fn = self.property_extractors.get(prop_name)
                if fn is None:
                    continue
                try:
                    pred_val = fn(pred)
                    if inp is not None:
                        inp_val = fn(inp)
                        if pred_val != inp_val:
                            ok = False
                            break
                except Exception:
                    pass
            if ok:
                kept.append(cand)
        return kept

    # ------------------------------------------------------------------
    @staticmethod
    def _detect_numeric_transform(
        in_vals: List[Any], out_vals: List[Any]
    ) -> Optional[str]:
        """Detect if out = f(in) for a simple numeric transform."""
        if not in_vals or any(v is None for v in in_vals) or any(v is None for v in out_vals):
            return None
        # Only check numeric scalars.
        try:
            ins = [float(v) for v in in_vals]
            outs = [float(v) for v in out_vals]
        except (TypeError, ValueError):
            return None

        # additive shift
        diffs = [o - i for i, o in zip(ins, outs)]
        if len(set(diffs)) == 1 and diffs[0] != 0:
            return f"add({diffs[0]:.4g})"

        # multiplicative scale
        if all(i != 0 for i in ins):
            ratios = [o / i for i, o in zip(ins, outs)]
            if len(set(ratios)) == 1 and ratios[0] != 1.0:
                return f"multiply({ratios[0]:.4g})"

        # constant output
        if len(set(outs)) == 1:
            return f"constant({outs[0]:.4g})"

        return None


# ====================================================================
# 5. CounterfactualVerifier -- Causal verification of hypotheses
# ====================================================================

class CounterfactualVerifier:
    """Test whether a hypothesis captures the *causal* rule or is merely
    a correlate, by testing invariance to irrelevant perturbations and
    sensitivity to relevant ones."""

    INTERVENTIONS = [
        "swap_irrelevant_color",
        "add_distractor_object",
        "move_irrelevant_object",
        "change_grid_size",
        "reflect_grid",
    ]

    def __init__(self, rng: Optional[np.random.RandomState] = None) -> None:
        self.rng = rng or np.random.RandomState(42)

    # ------------------------------------------------------------------
    def generate_counterfactual(
        self, grid: np.ndarray, intervention_type: str
    ) -> np.ndarray:
        """Create a counterfactual variant of *grid*."""
        arr = np.asarray(grid, dtype=int).copy()
        if intervention_type == "swap_irrelevant_color":
            return self._swap_irrelevant_color(arr)
        if intervention_type == "add_distractor_object":
            return self._add_distractor_object(arr)
        if intervention_type == "move_irrelevant_object":
            return self._move_irrelevant_object(arr)
        if intervention_type == "change_grid_size":
            return self._change_grid_size(arr)
        if intervention_type == "reflect_grid":
            return self._reflect_grid(arr)
        return arr

    # ------------------------------------------------------------------
    def verify(
        self,
        hypothesis: Any,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        apply_fn: Callable[[Any, np.ndarray], np.ndarray],
    ) -> Dict[str, Dict[str, Any]]:
        """For each intervention type, test the hypothesis on counterfactual
        inputs and report invariance.

        ``apply_fn(hypothesis, grid) -> predicted_output``
        """
        results: Dict[str, Dict[str, Any]] = {}
        for intervention in self.INTERVENTIONS:
            invariant_count = 0
            total = 0
            for inp, out in train_pairs:
                cf_input = self.generate_counterfactual(inp, intervention)
                try:
                    orig_pred = apply_fn(hypothesis, inp)
                    cf_pred = apply_fn(hypothesis, cf_input)
                    total += 1
                    # For irrelevant interventions the *structure* of the
                    # prediction should be consistent.
                    if self._structurally_equivalent(orig_pred, cf_pred, intervention):
                        invariant_count += 1
                except Exception:
                    total += 1
            sensitivity = 1.0 - (invariant_count / max(total, 1))
            results[intervention] = {
                "invariant": invariant_count == total,
                "sensitivity": sensitivity,
                "n_tested": total,
            }
        return results

    # ------------------------------------------------------------------
    def causal_score(
        self,
        hypothesis: Any,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        apply_fn: Callable[[Any, np.ndarray], np.ndarray],
    ) -> float:
        """0-1 score.  1 means fully invariant to irrelevant changes."""
        results = self.verify(hypothesis, train_pairs, apply_fn)
        if not results:
            return 0.0
        # Irrelevant interventions should be invariant.
        irrelevant_interventions = [
            "swap_irrelevant_color",
            "add_distractor_object",
            "move_irrelevant_object",
        ]
        scores = []
        for k in irrelevant_interventions:
            if k in results:
                scores.append(1.0 if results[k]["invariant"] else 0.0)
        return float(np.mean(scores)) if scores else 0.0

    # ------------------------------------------------------------------
    # Intervention implementations
    # ------------------------------------------------------------------
    def _swap_irrelevant_color(self, grid: np.ndarray) -> np.ndarray:
        """Swap the background colour (0) with a colour not present in the grid."""
        present = set(grid.flat)
        unused = [c for c in range(1, 10) if c not in present]
        if not unused:
            return grid
        # Replace some background with an unused colour -- effectively adds
        # border noise that should be irrelevant.
        result = grid.copy()
        bg_positions = list(zip(*np.where(grid == 0)))
        if not bg_positions:
            return result
        n_swap = max(1, len(bg_positions) // 10)
        idxs = self.rng.choice(len(bg_positions), size=min(n_swap, len(bg_positions)), replace=False)
        new_color = unused[0]
        for idx in idxs:
            r, c = bg_positions[idx]
            result[r, c] = new_color
        return result

    def _add_distractor_object(self, grid: np.ndarray) -> np.ndarray:
        """Add a small 1-pixel distractor in a background region."""
        result = grid.copy()
        bg_positions = list(zip(*np.where(grid == 0)))
        if not bg_positions:
            return result
        present = set(grid.flat) - {0}
        color = list(present)[0] if present else 1
        idx = self.rng.randint(len(bg_positions))
        r, c = bg_positions[idx]
        result[r, c] = color
        return result

    def _move_irrelevant_object(self, grid: np.ndarray) -> np.ndarray:
        """Shift the smallest connected component by 1 pixel if possible."""
        labels, n = _connected_components(grid != 0)
        if n < 2:
            return grid.copy()
        # Find smallest component.
        sizes = []
        for lab in range(1, n + 1):
            sizes.append((int((labels == lab).sum()), lab))
        sizes.sort()
        _, smallest_lab = sizes[0]
        mask = labels == smallest_lab
        result = grid.copy()
        # Try shifting down by 1.
        coords = list(zip(*np.where(mask)))
        shifted_coords = [(r + 1, c) for r, c in coords]
        h, w = grid.shape
        if all(0 <= r < h and 0 <= c < w for r, c in shifted_coords):
            for r, c in coords:
                result[r, c] = 0
            for (r, c), (sr, sc) in zip(coords, shifted_coords):
                result[sr, sc] = grid[r, c]
        return result

    def _change_grid_size(self, grid: np.ndarray) -> np.ndarray:
        """Pad the grid with 1 row and 1 column of background."""
        h, w = grid.shape
        result = np.zeros((h + 1, w + 1), dtype=int)
        result[:h, :w] = grid
        return result

    def _reflect_grid(self, grid: np.ndarray) -> np.ndarray:
        """Reflect the grid horizontally."""
        return np.fliplr(grid).copy()

    # ------------------------------------------------------------------
    @staticmethod
    def _structurally_equivalent(
        pred_a: np.ndarray, pred_b: np.ndarray, intervention: str
    ) -> bool:
        """Check structural equivalence depending on intervention type."""
        if intervention in ("swap_irrelevant_color", "add_distractor_object", "move_irrelevant_object"):
            # For these interventions, we expect the output to be identical
            # or at least have the same shape.
            if pred_a.shape != pred_b.shape:
                return False
            return bool(np.array_equal(pred_a, pred_b))
        if intervention == "change_grid_size":
            # Shape may differ but non-zero content should be equivalent.
            a_nz = set(map(tuple, np.argwhere(pred_a != 0).tolist()))
            b_nz = set(map(tuple, np.argwhere(pred_b != 0).tolist()))
            # Allow structural match if same number of nonzero pixels.
            return len(a_nz) == len(b_nz)
        if intervention == "reflect_grid":
            # Prediction should also be reflected.
            if pred_a.shape != pred_b.shape:
                return False
            return bool(np.array_equal(np.fliplr(pred_a), pred_b))
        return bool(np.array_equal(pred_a, pred_b))


# ====================================================================
# 6. TopologicalLoss -- Persistent homology for structural similarity
# ====================================================================

class TopologicalLoss:
    """Measure similarity between grids based on topological features
    (connected components, holes, Euler characteristic) rather than
    pixel-level MSE."""

    # ------------------------------------------------------------------
    @staticmethod
    def grid_topology(grid: np.ndarray) -> Dict[str, Any]:
        """Compute topological invariants of the grid.

        Returns:
            n_components (H0), n_holes (H1), euler_characteristic,
            component_sizes, hole_sizes (not always computable cheaply,
            approximated), betti_numbers.
        """
        binary = np.asarray(grid, dtype=int) != 0
        labels, n_components = _connected_components(binary)
        component_sizes = []
        for lab in range(1, n_components + 1):
            component_sizes.append(int((labels == lab).sum()))
        component_sizes.sort(reverse=True)

        n_holes = _count_holes_binary(binary)
        euler = n_components - n_holes

        return {
            "n_components": n_components,
            "n_holes": n_holes,
            "euler_characteristic": euler,
            "component_sizes": component_sizes,
            "betti_0": n_components,
            "betti_1": n_holes,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def topology_distance(grid_a: np.ndarray, grid_b: np.ndarray) -> float:
        """Distance based on topological features, not pixel MSE."""
        tl = TopologicalLoss()
        ta = tl.grid_topology(grid_a)
        tb = tl.grid_topology(grid_b)

        # Weighted distance over topological features.
        d_components = abs(ta["n_components"] - tb["n_components"])
        d_holes = abs(ta["n_holes"] - tb["n_holes"])
        d_euler = abs(ta["euler_characteristic"] - tb["euler_characteristic"])

        # Component size distribution distance (pad shorter list).
        sa = ta["component_sizes"]
        sb = tb["component_sizes"]
        max_len = max(len(sa), len(sb))
        sa_padded = sa + [0] * (max_len - len(sa))
        sb_padded = sb + [0] * (max_len - len(sb))
        d_sizes = sum(abs(a - b) for a, b in zip(sa_padded, sb_padded))
        norm_sizes = max(sum(sa_padded), sum(sb_padded), 1)

        return float(
            2.0 * d_components
            + 3.0 * d_holes
            + 1.0 * d_euler
            + 1.0 * d_sizes / norm_sizes
        )

    # ------------------------------------------------------------------
    @staticmethod
    def persistence_diagram(grid: np.ndarray) -> List[Tuple[float, float, int]]:
        """Simplified persistence diagram.

        Threshold the grid at each unique nonzero colour level and track
        the birth/death of connected components.

        Returns list of ``(birth, death, dimension)`` tuples.
        ``dimension=0`` for components, ``dimension=1`` for holes.
        """
        arr = np.asarray(grid, dtype=int)
        levels = sorted(set(arr.flat) - {0})
        if not levels:
            return []

        diagram: List[Tuple[float, float, int]] = []

        prev_n_comp = 0
        prev_n_holes = 0
        prev_labels: Optional[np.ndarray] = None

        for level in levels:
            binary = arr >= level
            labels, n_comp = _connected_components(binary)
            n_holes = _count_holes_binary(binary)

            # Component births.
            new_births = n_comp - prev_n_comp
            if new_births > 0:
                for _ in range(new_births):
                    diagram.append((float(level), float("inf"), 0))

            # Component deaths (merges).
            if new_births < 0:
                deaths = -new_births
                # Mark earliest open components as dying.
                open_zero = [i for i, (b, d, dim) in enumerate(diagram) if d == float("inf") and dim == 0]
                for k in range(min(deaths, len(open_zero))):
                    b, _, dim = diagram[open_zero[k]]
                    diagram[open_zero[k]] = (b, float(level), dim)

            # Hole births.
            new_holes = n_holes - prev_n_holes
            if new_holes > 0:
                for _ in range(new_holes):
                    diagram.append((float(level), float("inf"), 1))

            # Hole deaths.
            if new_holes < 0:
                dead_holes = -new_holes
                open_one = [i for i, (b, d, dim) in enumerate(diagram) if d == float("inf") and dim == 1]
                for k in range(min(dead_holes, len(open_one))):
                    b, _, dim = diagram[open_one[k]]
                    diagram[open_one[k]] = (b, float(level), dim)

            prev_n_comp = n_comp
            prev_n_holes = n_holes
            prev_labels = labels

        return diagram

    # ------------------------------------------------------------------
    @staticmethod
    def topology_preserving_score(
        input_grid: np.ndarray,
        output_grid: np.ndarray,
        predicted_grid: np.ndarray,
    ) -> float:
        """Is the topology of *predicted_grid* closer to *output_grid* than
        a random baseline?

        Returns a score in [0, 1] where 1 means the prediction perfectly
        matches the output topology and 0 means it is as far as a random grid.
        """
        tl = TopologicalLoss()
        d_pred = tl.topology_distance(output_grid, predicted_grid)
        # Random baseline: measure distance from output to a random grid
        # of the same shape.  Use a simple all-zeros grid as a pessimistic
        # baseline for efficiency.
        random_baseline = np.zeros_like(output_grid)
        d_rand = tl.topology_distance(output_grid, random_baseline)
        if d_rand == 0:
            return 1.0 if d_pred == 0 else 0.0
        score = max(0.0, 1.0 - d_pred / d_rand)
        return float(score)
