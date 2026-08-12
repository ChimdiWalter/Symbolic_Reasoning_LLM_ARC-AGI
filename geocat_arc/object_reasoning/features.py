"""Typed feature/relation registries and feature-table construction (Sec 2.2).

Requirement 2.2.1: every feature and relation is a NAMED, TYPED, PURE
function registered here.  Induction and expressions may only reference
registered names — this keeps the hypothesis space enumerable and programs
serializable (registry name + args is the JSON form).

Two registries:
- FEATURE_REGISTRY:  name -> FeatureSpec, fn(obj, ctx) -> FeatureValue.
  Holds intrinsic features AND per-object relational summaries (e.g.
  vector_to_nearest) — anything that collapses to one value per object.
- RELATION_REGISTRY: name -> RelationSpec, fn(a, b, ctx) -> bool.
  Binary relations between two objects (wraps perception/relations.py).

Feature functions must be pure and total: on undefined cases (e.g.
vector_to_nearest with a single object) they return the kind's sentinel
(UNDEFINED_* below) rather than raising.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject
from geocat_arc.perception import relations as _rel

from .types import FeatureKind, FeatureTable, FeatureValue, GridContext, ObjectFeatures

# Sentinels for undefined feature values (pure-total contract).
UNDEFINED_SCALAR: int = -1
UNDEFINED_COLOR: int = -1
UNDEFINED_VECTOR: tuple[int, int] = (0, 0)


FeatureFn = Callable[[ARCObject, GridContext], FeatureValue]
RelationFn = Callable[[ARCObject, ARCObject, GridContext], bool]


@dataclass(frozen=True)
class FeatureSpec:
    """Registry entry: a named typed per-object feature."""
    name: str
    kind: FeatureKind
    fn: FeatureFn
    relational: bool = False      # True if it consults other objects in ctx
    doc: str = ""


@dataclass(frozen=True)
class RelationSpec:
    """Registry entry: a named binary boolean relation between two objects."""
    name: str
    fn: RelationFn
    doc: str = ""


FEATURE_REGISTRY: dict[str, FeatureSpec] = {}
RELATION_REGISTRY: dict[str, RelationSpec] = {}


# ---------------------------------------------------------------------------
# Registration API (implemented — mechanics are fixed)
# ---------------------------------------------------------------------------

def register_feature(name: str, kind: FeatureKind, fn: FeatureFn,
                     relational: bool = False, doc: str = "") -> FeatureSpec:
    """Register a pure per-object feature function under a unique name.
    Raises ValueError on duplicate names (registry is append-only per run)."""
    if name in FEATURE_REGISTRY:
        raise ValueError(f"feature already registered: {name}")
    spec = FeatureSpec(name=name, kind=kind, fn=fn, relational=relational, doc=doc)
    FEATURE_REGISTRY[name] = spec
    return spec


def register_relation(name: str, fn: RelationFn, doc: str = "") -> RelationSpec:
    """Register a pure binary relation function under a unique name."""
    if name in RELATION_REGISTRY:
        raise ValueError(f"relation already registered: {name}")
    spec = RelationSpec(name=name, fn=fn, doc=doc)
    RELATION_REGISTRY[name] = spec
    return spec


def get_feature(name: str) -> FeatureSpec:
    """Lookup with a helpful error naming the registry."""
    try:
        return FEATURE_REGISTRY[name]
    except KeyError:
        raise KeyError(f"unregistered feature: {name!r} "
                       f"(known: {sorted(FEATURE_REGISTRY)})") from None


def get_relation(name: str) -> RelationSpec:
    try:
        return RELATION_REGISTRY[name]
    except KeyError:
        raise KeyError(f"unregistered relation: {name!r} "
                       f"(known: {sorted(RELATION_REGISTRY)})") from None


def features_of_kind(kind: FeatureKind) -> list[FeatureSpec]:
    """All registered features returning ``kind`` (used by
    expressions.enumerate_expressions to propose typed leaves)."""
    return [s for s in FEATURE_REGISTRY.values() if s.kind is kind]


# ---------------------------------------------------------------------------
# Planned built-in features (the FIXED Stage-1 vocabulary).
# The features team implements register_builtin_features() so that after the
# call FEATURE_REGISTRY contains exactly these names with these kinds, and
# RELATION_REGISTRY the relations below.  Names are frozen: expressions and
# serialized programs reference them.
# ---------------------------------------------------------------------------

#: (name, kind, relational, semantics)
PLANNED_FEATURES: list[tuple[str, FeatureKind, bool, str]] = [
    # -- intrinsic --
    ("color", FeatureKind.COLOR, False, "obj.color (majority color for S3/S4)"),
    ("size", FeatureKind.SCALAR, False, "cell count"),
    ("bbox", FeatureKind.CATEGORICAL, False, "(r0,c0,r1,c1) tuple"),
    ("bbox_height", FeatureKind.SCALAR, False, "bounding-box height"),
    ("bbox_width", FeatureKind.SCALAR, False, "bounding-box width"),
    ("centroid", FeatureKind.VECTOR, False, "rounded (r,c) centroid"),
    ("shape_sig", FeatureKind.CATEGORICAL, False,
     "stable hash (hex str) of obj.shape_signature"),
    ("shape_sig_normalized", FeatureKind.CATEGORICAL, False,
     "hash of rotation/reflection-canonical shape signature"),
    ("hole_count", FeatureKind.SCALAR, False, "len(obj.holes)"),
    ("has_hole", FeatureKind.BOOL, False, "hole_count > 0"),
    ("enclosed_region_count", FeatureKind.SCALAR, False,
     "number of 4-connected non-object regions fully enclosed by the object "
     "mask (color/background-agnostic topology; counts multi-cell holes that "
     "obj.holes misses)"),
    ("has_enclosed_region", FeatureKind.BOOL, False,
     "enclosed_region_count > 0 (closed loop / ring detector)"),
    ("is_multicolor", FeatureKind.BOOL, False,
     "object carries >= 2 distinct cell colors (S3/S4 multicolor objects; "
     "always False for single-color objects)"),
    ("is_rectangle", FeatureKind.BOOL, False, "size == bbox area"),
    ("is_line", FeatureKind.BOOL, False, "height==1 or width==1"),
    ("touches_border", FeatureKind.BOOL, False, "bbox touches grid edge"),
    ("aspect_ratio", FeatureKind.SCALAR, False, "bbox_height/bbox_width (float)"),
    ("density", FeatureKind.SCALAR, False, "size / bbox area (float)"),
    # -- rank features over the grid's object set (relational=True) --
    ("size_rank", FeatureKind.SCALAR, True, "0 = largest object in grid"),
    ("size_rank_reversed", FeatureKind.SCALAR, True, "0 = smallest"),
    ("is_unique_size", FeatureKind.BOOL, True, "no other object has same size"),
    ("is_unique_color", FeatureKind.BOOL, True, "no other object has same color"),
    ("is_unique_shape", FeatureKind.BOOL, True,
     "no other object has same shape_sig_normalized"),
    ("is_majority_shape", FeatureKind.BOOL, True, "shape is the modal shape"),
    ("color_frequency_rank", FeatureKind.SCALAR, True,
     "rank of obj.color by object count (0 = most common)"),
    ("count_of_same_shape", FeatureKind.SCALAR, True,
     "how many objects (incl. self) share shape_sig_normalized (a.k.a. same_shape_as_count)"),
    ("count_of_same_color", FeatureKind.SCALAR, True,
     "how many objects (incl. self) share color"),
    # -- derived quantitative relations, per-object summaries --
    ("vector_to_nearest", FeatureKind.VECTOR, True,
     "rounded centroid vector to nearest other object (UNDEFINED_VECTOR if none)"),
    ("gap_to_nearest_row", FeatureKind.SCALAR, True,
     "empty-cell gap to nearest object along rows (UNDEFINED_SCALAR if none)"),
    ("gap_to_nearest_col", FeatureKind.SCALAR, True,
     "empty-cell gap to nearest object along cols"),
    ("nearest_object_color", FeatureKind.COLOR, True,
     "color of nearest other object (UNDEFINED_COLOR if none)"),
    ("is_container", FeatureKind.BOOL, True,
     "contains at least one other object (relations.contains)"),
    ("is_contained", FeatureKind.BOOL, True,
     "inside some other object (inverse of contains)"),
    ("containment_depth", FeatureKind.SCALAR, True,
     "nesting depth under 'contains' (0 = top level)"),
    ("aligned_row_count", FeatureKind.SCALAR, True,
     "number of other objects sharing this object's row band"),
    ("aligned_col_count", FeatureKind.SCALAR, True,
     "number of other objects sharing this object's column band"),
]

#: Binary relations wrapping perception/relations.py (all 10 existing checks
#: + inside as the inverse of contains).
PLANNED_RELATIONS: list[tuple[str, str]] = [
    ("left_of", "a strictly left of b (bbox centers)"),
    ("right_of", "a strictly right of b"),
    ("above", "a strictly above b"),
    ("below", "a strictly below b"),
    ("contains", "a's cells strictly enclose b's bbox"),
    ("inside", "inverse of contains: b contains a"),
    ("adjacent", "some cell of a is 4-adjacent to a cell of b"),
    ("same_color", "a.color == b.color"),
    ("same_shape", "identical shape_signature"),
    ("same_shape_normalized",
     "identical rotation/reflection-canonical shape signature"),
    ("same_size", "identical size"),
    ("overlaps", "cell sets intersect"),
]


# ---------------------------------------------------------------------------
# Built-in feature implementations (pure, total; sentinels on undefined).
# Geometry comes from perception (ARCObject properties, relations.py) — the
# only new geometry here is bbox-interval arithmetic and the canonical
# shape-signature reduction (min over the 8 rotations/reflections).
# ---------------------------------------------------------------------------

def _stable_hash(value: object) -> str:
    """Deterministic short hex digest (python hash() is salted per process)."""
    return hashlib.sha1(repr(value).encode("utf-8")).hexdigest()[:16]


@lru_cache(maxsize=8192)
def _canonical_signature_cached(sig: tuple) -> tuple:
    """Rotation/reflection-canonical form of a shape signature: the
    lexicographic minimum over the 8 orientations.  Cached on the signature
    tuple (hashable) because rank features consult it for every object pair."""
    if not sig or not sig[0]:
        return sig
    m = np.array(sig, dtype=int)
    best: Optional[tuple] = None
    for k in range(4):
        rot = np.rot90(m, k)
        for cand in (rot, np.fliplr(rot)):
            t = tuple(map(tuple, cand.tolist()))
            if best is None or t < best:
                best = t
    return best


def _normalized_signature(obj: ARCObject) -> tuple:
    return _canonical_signature_cached(obj.shape_signature)


def _others(obj: ARCObject, ctx: GridContext) -> list[ARCObject]:
    """All context objects except ``obj`` (by id)."""
    return [o for o in ctx.objects if o.id != obj.id]


def _nearest_other(obj: ARCObject, ctx: GridContext) -> Optional[ARCObject]:
    """Nearest other object by centroid Euclidean distance; deterministic
    tie-break by smaller object id.  None when the object is alone."""
    others = _others(obj, ctx)
    if not others or obj.size == 0:
        return None
    ar, ac = obj.centroid
    return min(others,
               key=lambda b: ((b.centroid[0] - ar) ** 2
                              + (b.centroid[1] - ac) ** 2, b.id))


def _row_spans_overlap(a: ARCObject, b: ARCObject) -> bool:
    """bbox row intervals [r0, r1) intersect (objects share a row band)."""
    return a.bounding_box[0] < b.bounding_box[2] and \
        b.bounding_box[0] < a.bounding_box[2]


def _col_spans_overlap(a: ARCObject, b: ARCObject) -> bool:
    """bbox column intervals [c0, c1) intersect (share a column band)."""
    return a.bounding_box[1] < b.bounding_box[3] and \
        b.bounding_box[1] < a.bounding_box[3]


def _row_gap(a: ARCObject, b: ARCObject) -> int:
    """Empty rows between the two bboxes along the row axis (0 if the row
    intervals overlap).  bboxes are half-open (r0, c0, r1, c1)."""
    if a.bounding_box[2] <= b.bounding_box[0]:
        return b.bounding_box[0] - a.bounding_box[2]
    if b.bounding_box[2] <= a.bounding_box[0]:
        return a.bounding_box[0] - b.bounding_box[2]
    return 0


def _col_gap(a: ARCObject, b: ARCObject) -> int:
    """Empty columns between the two bboxes along the column axis."""
    if a.bounding_box[3] <= b.bounding_box[1]:
        return b.bounding_box[1] - a.bounding_box[3]
    if b.bounding_box[3] <= a.bounding_box[1]:
        return a.bounding_box[1] - b.bounding_box[3]
    return 0


# -- intrinsic ---------------------------------------------------------------

def _f_color(obj, ctx):
    return int(obj.color)


def _f_size(obj, ctx):
    return int(obj.size)


def _f_bbox(obj, ctx):
    return tuple(int(x) for x in obj.bounding_box)


def _f_bbox_height(obj, ctx):
    return int(obj.bbox_height)


def _f_bbox_width(obj, ctx):
    return int(obj.bbox_width)


def _f_centroid(obj, ctx):
    if obj.size == 0:
        return UNDEFINED_VECTOR
    r, c = obj.centroid
    return (int(round(r)), int(round(c)))


def _f_shape_sig(obj, ctx):
    return _stable_hash(obj.shape_signature)


def _f_shape_sig_normalized(obj, ctx):
    return _stable_hash(_normalized_signature(obj))


def _f_hole_count(obj, ctx):
    return int(len(obj.holes))


def _f_has_hole(obj, ctx):
    return bool(obj.has_hole)


@lru_cache(maxsize=8192)
def _enclosed_regions_cached(cells: frozenset, bbox: tuple) -> int:
    """Number of 4-connected components of non-object cells within the bbox
    that cannot reach the bbox boundary ring — proper mask topology,
    independent of cell colors and of the background color (the fix for
    multi-cell holes and non-zero-background rings)."""
    r0, c0, r1, c1 = bbox
    h, w = r1 - r0, c1 - c0
    if h <= 0 or w <= 0:
        return 0
    mask = np.zeros((h + 2, w + 2), dtype=bool)   # 1-cell pad = outside ring
    for (r, c) in cells:
        mask[r - r0 + 1, c - c0 + 1] = True
    # flood fill the complement from the pad ring (BFS, 4-connected)
    visited = np.zeros_like(mask)
    stack = [(0, 0)]
    visited[0, 0] = True
    H, W = mask.shape
    while stack:
        r, c = stack.pop()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < H and 0 <= nc < W and not visited[nr, nc] \
                    and not mask[nr, nc]:
                visited[nr, nc] = True
                stack.append((nr, nc))
    # enclosed = complement cells never reached; count their 4-components
    count = 0
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            if mask[r, c] or visited[r, c]:
                continue
            count += 1
            stack = [(r, c)]
            visited[r, c] = True
            while stack:
                rr, cc = stack.pop()
                for nr, nc in ((rr - 1, cc), (rr + 1, cc),
                               (rr, cc - 1), (rr, cc + 1)):
                    if 0 <= nr < H and 0 <= nc < W and not visited[nr, nc] \
                            and not mask[nr, nc]:
                        visited[nr, nc] = True
                        stack.append((nr, nc))
    return count


def _f_enclosed_region_count(obj, ctx):
    return int(_enclosed_regions_cached(obj.cells,
                                        tuple(int(x) for x in obj.bounding_box)))


def _f_has_enclosed_region(obj, ctx):
    return _f_enclosed_region_count(obj, ctx) > 0


def _f_is_multicolor(obj, ctx):
    from .types import cell_colors_of
    return len(set(cell_colors_of(obj).values())) > 1


def _f_is_rectangle(obj, ctx):
    return bool(obj.is_rectangle)


def _f_is_line(obj, ctx):
    return bool(obj.is_line)


def _f_touches_border(obj, ctx):
    r0, c0, r1, c1 = obj.bounding_box
    return bool(r0 == 0 or c0 == 0
                or r1 >= ctx.grid.height or c1 >= ctx.grid.width)


def _f_aspect_ratio(obj, ctx):
    w = obj.bbox_width
    if w == 0:
        return float(UNDEFINED_SCALAR)
    return round(obj.bbox_height / w, 4)


def _f_density(obj, ctx):
    area = obj.bbox_height * obj.bbox_width
    if area == 0:
        return float(UNDEFINED_SCALAR)
    return round(obj.size / area, 4)


# -- rank features over the grid's object set --------------------------------

def _f_size_rank(obj, ctx):
    sizes = sorted({o.size for o in ctx.objects}, reverse=True)
    return sizes.index(obj.size) if obj.size in sizes else UNDEFINED_SCALAR


def _f_size_rank_reversed(obj, ctx):
    sizes = sorted({o.size for o in ctx.objects})
    return sizes.index(obj.size) if obj.size in sizes else UNDEFINED_SCALAR


def _f_is_unique_size(obj, ctx):
    return sum(1 for o in ctx.objects if o.size == obj.size) == 1


def _f_is_unique_color(obj, ctx):
    return sum(1 for o in ctx.objects if o.color == obj.color) == 1


def _f_is_unique_shape(obj, ctx):
    sig = _normalized_signature(obj)
    return sum(1 for o in ctx.objects if _normalized_signature(o) == sig) == 1


def _f_is_majority_shape(obj, ctx):
    if not ctx.objects:
        return False
    counts = Counter(_normalized_signature(o) for o in ctx.objects)
    return counts[_normalized_signature(obj)] == max(counts.values())


def _f_color_frequency_rank(obj, ctx):
    counts = Counter(o.color for o in ctx.objects)
    if obj.color not in counts:
        return UNDEFINED_SCALAR
    distinct = sorted(set(counts.values()), reverse=True)
    return distinct.index(counts[obj.color])


def _f_count_of_same_shape(obj, ctx):
    sig = _normalized_signature(obj)
    return sum(1 for o in ctx.objects if _normalized_signature(o) == sig)


def _f_count_of_same_color(obj, ctx):
    return sum(1 for o in ctx.objects if o.color == obj.color)


# -- derived quantitative relations (per-object summaries) --------------------

def _f_vector_to_nearest(obj, ctx):
    b = _nearest_other(obj, ctx)
    if b is None:
        return UNDEFINED_VECTOR
    ar, ac = obj.centroid
    br, bc = b.centroid
    return (int(round(br - ar)), int(round(bc - ac)))


def _f_gap_to_nearest_row(obj, ctx):
    """Min empty-row gap to another object whose column band overlaps ours
    (i.e. an object we would hit moving along the row axis)."""
    gaps = [_row_gap(obj, b) for b in _others(obj, ctx)
            if _col_spans_overlap(obj, b)]
    return min(gaps) if gaps else UNDEFINED_SCALAR


def _f_gap_to_nearest_col(obj, ctx):
    """Min empty-column gap to another object whose row band overlaps ours."""
    gaps = [_col_gap(obj, b) for b in _others(obj, ctx)
            if _row_spans_overlap(obj, b)]
    return min(gaps) if gaps else UNDEFINED_SCALAR


def _f_nearest_object_color(obj, ctx):
    b = _nearest_other(obj, ctx)
    return UNDEFINED_COLOR if b is None else int(b.color)


def _f_is_container(obj, ctx):
    return any(_rel.contains(obj, b) for b in _others(obj, ctx))


def _f_is_contained(obj, ctx):
    return any(_rel.contains(b, obj) for b in _others(obj, ctx))


def _f_containment_depth(obj, ctx):
    return sum(1 for b in _others(obj, ctx) if _rel.contains(b, obj))


def _f_aligned_row_count(obj, ctx):
    return sum(1 for b in _others(obj, ctx) if _row_spans_overlap(obj, b))


def _f_aligned_col_count(obj, ctx):
    return sum(1 for b in _others(obj, ctx) if _col_spans_overlap(obj, b))


#: name -> implementation; keys must cover PLANNED_FEATURES exactly.
_FEATURE_IMPLS: dict[str, FeatureFn] = {
    "color": _f_color,
    "size": _f_size,
    "bbox": _f_bbox,
    "bbox_height": _f_bbox_height,
    "bbox_width": _f_bbox_width,
    "centroid": _f_centroid,
    "shape_sig": _f_shape_sig,
    "shape_sig_normalized": _f_shape_sig_normalized,
    "hole_count": _f_hole_count,
    "has_hole": _f_has_hole,
    "enclosed_region_count": _f_enclosed_region_count,
    "has_enclosed_region": _f_has_enclosed_region,
    "is_multicolor": _f_is_multicolor,
    "is_rectangle": _f_is_rectangle,
    "is_line": _f_is_line,
    "touches_border": _f_touches_border,
    "aspect_ratio": _f_aspect_ratio,
    "density": _f_density,
    "size_rank": _f_size_rank,
    "size_rank_reversed": _f_size_rank_reversed,
    "is_unique_size": _f_is_unique_size,
    "is_unique_color": _f_is_unique_color,
    "is_unique_shape": _f_is_unique_shape,
    "is_majority_shape": _f_is_majority_shape,
    "color_frequency_rank": _f_color_frequency_rank,
    "count_of_same_shape": _f_count_of_same_shape,
    "count_of_same_color": _f_count_of_same_color,
    "vector_to_nearest": _f_vector_to_nearest,
    "gap_to_nearest_row": _f_gap_to_nearest_row,
    "gap_to_nearest_col": _f_gap_to_nearest_col,
    "nearest_object_color": _f_nearest_object_color,
    "is_container": _f_is_container,
    "is_contained": _f_is_contained,
    "containment_depth": _f_containment_depth,
    "aligned_row_count": _f_aligned_row_count,
    "aligned_col_count": _f_aligned_col_count,
}


# -- binary relations (wrap perception/relations.py verbatim) -----------------

def _r_left_of(a, b, ctx):
    return bool(_rel.left_of(a, b))


def _r_right_of(a, b, ctx):
    return bool(_rel.right_of(a, b))


def _r_above(a, b, ctx):
    return bool(_rel.above(a, b))


def _r_below(a, b, ctx):
    return bool(_rel.below(a, b))


def _r_contains(a, b, ctx):
    return bool(_rel.contains(a, b))


def _r_inside(a, b, ctx):
    return bool(_rel.contains(b, a))


def _r_adjacent(a, b, ctx):
    return bool(_rel.adjacent(a, b))


def _r_same_color(a, b, ctx):
    return bool(_rel.same_color(a, b))


def _r_same_shape(a, b, ctx):
    return bool(_rel.same_shape(a, b))


def _r_same_shape_normalized(a, b, ctx):
    return _normalized_signature(a) == _normalized_signature(b)


def _r_same_size(a, b, ctx):
    return bool(_rel.same_size(a, b))


def _r_overlaps(a, b, ctx):
    return bool(_rel.overlaps(a, b))


#: name -> implementation; keys must cover PLANNED_RELATIONS exactly.
_RELATION_IMPLS: dict[str, RelationFn] = {
    "left_of": _r_left_of,
    "right_of": _r_right_of,
    "above": _r_above,
    "below": _r_below,
    "contains": _r_contains,
    "inside": _r_inside,
    "adjacent": _r_adjacent,
    "same_color": _r_same_color,
    "same_shape": _r_same_shape,
    "same_shape_normalized": _r_same_shape_normalized,
    "same_size": _r_same_size,
    "overlaps": _r_overlaps,
}


def register_builtin_features() -> None:
    """Populate FEATURE_REGISTRY/RELATION_REGISTRY with exactly the
    PLANNED_FEATURES / PLANNED_RELATIONS vocabularies (idempotent: a second
    call is a no-op).  Implementations are pure, total (UNDEFINED_* sentinels
    on undefined cases), and reuse geocat_arc.perception.{objects,relations}
    — no duplicated geometry code."""
    missing_f = [n for n, _, _, _ in PLANNED_FEATURES if n not in _FEATURE_IMPLS]
    missing_r = [n for n, _ in PLANNED_RELATIONS if n not in _RELATION_IMPLS]
    if missing_f or missing_r:
        raise RuntimeError(
            f"builtin implementations out of sync with planned vocabulary: "
            f"features={missing_f} relations={missing_r}")
    for name, kind, relational, doc in PLANNED_FEATURES:
        if name in FEATURE_REGISTRY:       # idempotent per name
            continue
        register_feature(name, kind, _FEATURE_IMPLS[name],
                         relational=relational, doc=doc)
    for name, doc in PLANNED_RELATIONS:
        if name in RELATION_REGISTRY:
            continue
        register_relation(name, _RELATION_IMPLS[name], doc=doc)


# ---------------------------------------------------------------------------
# Feature-table construction (Section 3.3 step 1) — glue, implemented.
# ---------------------------------------------------------------------------

def compute_features(obj: ARCObject, ctx: GridContext) -> ObjectFeatures:
    """Evaluate every registered feature on one object (row constructor)."""
    intrinsic: dict[str, FeatureValue] = {}
    relational: dict[str, FeatureValue] = {}
    for spec in FEATURE_REGISTRY.values():
        value = spec.fn(obj, ctx)
        (relational if spec.relational else intrinsic)[spec.name] = value
    return ObjectFeatures(object_id=obj.id, pair_index=ctx.pair_index,
                          role=ctx.role, intrinsic=intrinsic,
                          relational=relational)


def compute_feature_table(objects: list[ARCObject], grid: Grid,
                          background: int, pair_index: int = 0,
                          role: str = "input") -> FeatureTable:
    """Rows for all objects of ONE grid.  The inducer concatenates the
    per-pair tables and attaches delta labels (FeatureTable.labels) itself.
    Requires register_builtin_features() to have been called."""
    if not FEATURE_REGISTRY:
        raise RuntimeError("FEATURE_REGISTRY empty — call register_builtin_features() first")
    ctx = GridContext(grid=grid, objects=objects, background=background,
                      pair_index=pair_index, role=role)
    rows = [compute_features(o, ctx) for o in objects]
    return FeatureTable(rows=rows, feature_names=sorted(FEATURE_REGISTRY))
