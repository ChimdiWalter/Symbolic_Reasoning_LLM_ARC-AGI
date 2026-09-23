"""Generative concept grammar for structural reasoning.

Provides a compositional language of executable concept expressions that can be
enumerated bottom-up, evaluated on ARC-style scenes, and validated via
leave-one-out cross-validation.  Every expression is typed, has an MDL
complexity score, and can be rendered to a human-readable string.

Expression taxonomy
-------------------
- **PrimitiveConcept**    — wraps one of the 81 existing boolean properties
- **RelationConcept**     — binary relation (inside, touches, same_shape, ...)
- **NotConcept**          — logical negation
- **AndConcept / OrConcept** — conjunction / disjunction
- **ExistsConcept**       — existential quantifier over scene objects
- **ForAllConcept**       — universal quantifier
- **CountConcept**        — cardinality comparison
- **ArgMaxConcept / ArgMinConcept** — extremal selection
- **ReferenceConcept**    — resolves a distinguished object from the scene
- **BoundRelationConcept**— relation with a bound reference
- **SchemaConcept**       — high-level structural pattern
"""
from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.reasoning_engine import (
    BOOLEAN_PROPERTIES,
    DERIVED_PREDICATES,
    _all_property_names,
    _classify_kept_removed,
    _classify_two_groups,
    _classify_unchanged_changed,
    _extract_objects_with_properties,
    _get_property_value,
)


# ═══════════════════════════════════════════════════════════════════════════
# TYPE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

VALID_COMPOSITIONS = {
    "Not": [("Object->Bool",)],
    "And": [("Object->Bool", "Object->Bool")],
    "Or": [("Object->Bool", "Object->Bool")],
    "Exists": [("Object->Bool", "Object,Object->Bool")],
    "ForAll": [("Object->Bool", "Object,Object->Bool")],
    "BoundRelation": [("Object,Object->Bool", "Scene->Object")],
}


def _check_composition(kind: str, *children_types: str) -> bool:
    """Return True if the composition is type-valid."""
    valid = VALID_COMPOSITIONS.get(kind, [])
    return tuple(children_types) in valid


# ═══════════════════════════════════════════════════════════════════════════
# BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════

class ConceptExpression(ABC):
    """Executable concept expression — the unit of the generative property language."""

    name: str
    complexity: int
    dependencies: List[str]
    type_signature: str

    @abstractmethod
    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        """Evaluate this concept on an object in a scene context.

        Parameters
        ----------
        obj : dict
            Object dict produced by ``_extract_objects_with_properties``.
        scene : dict
            ``{"objects": List[Dict], "grid": np.ndarray,
               "grid_h": int, "grid_w": int}``
        """
        ...

    @abstractmethod
    def to_string(self) -> str:
        """Human-readable string representation."""
        ...

    def __repr__(self) -> str:
        return self.to_string()


# ═══════════════════════════════════════════════════════════════════════════
# EXPRESSION TYPES
# ═══════════════════════════════════════════════════════════════════════════

# 1. PrimitiveConcept -------------------------------------------------------

class PrimitiveConcept(ConceptExpression):
    """Wraps one of the existing boolean properties (complexity 1)."""

    def __init__(self, prop_name: str) -> None:
        self.prop_name = prop_name
        self.name = prop_name
        self.complexity = 1
        self.dependencies: List[str] = []
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        return _get_property_value(obj, self.prop_name)

    def to_string(self) -> str:
        return f"{self.prop_name}(x)"


# 2. RelationConcept --------------------------------------------------------

# --- Concrete relation functions -------------------------------------------

def _rel_inside(a: Dict, b: Dict) -> bool:
    """True if a's bbox is strictly within b's bbox."""
    ar1, ac1, ar2, ac2 = a["bbox"]
    br1, bc1, br2, bc2 = b["bbox"]
    return br1 <= ar1 and bc1 <= ac1 and br2 >= ar2 and bc2 >= ac2


def _rel_touches(a: Dict, b: Dict) -> bool:
    """True if a's mask overlaps the 4-connected dilation of b's mask."""
    dilated = ndimage.binary_dilation(b["mask"])
    return bool(np.any(dilated & a["mask"]))


def _rel_same_shape(a: Dict, b: Dict) -> bool:
    """True if local_masks match under any 90-degree rotation."""
    lm_a = a["local_mask"]
    lm_b = b["local_mask"]
    for k in range(4):
        rot = np.rot90(lm_b, k)
        if rot.shape == lm_a.shape and np.array_equal(rot, lm_a):
            return True
    return False


def _rel_same_color(a: Dict, b: Dict) -> bool:
    return a["primary_color"] == b["primary_color"]


def _rel_same_row(a: Dict, b: Dict) -> bool:
    return abs(a["center_r"] - b["center_r"]) < 1.5


def _rel_same_col(a: Dict, b: Dict) -> bool:
    return abs(a["center_c"] - b["center_c"]) < 1.5


def _rel_left_of(a: Dict, b: Dict) -> bool:
    return a["center_c"] < b["center_c"]


def _rel_above(a: Dict, b: Dict) -> bool:
    return a["center_r"] < b["center_r"]


def _rel_closer_than(a: Dict, b: Dict, anchor: Dict) -> bool:
    """True if a is closer to *anchor* than b is (Manhattan distance)."""
    da = abs(a["center_r"] - anchor["center_r"]) + abs(a["center_c"] - anchor["center_c"])
    db = abs(b["center_r"] - anchor["center_r"]) + abs(b["center_c"] - anchor["center_c"])
    return da < db


RELATION_REGISTRY: Dict[str, Callable] = {
    "inside": _rel_inside,
    "touches": _rel_touches,
    "same_shape": _rel_same_shape,
    "same_color": _rel_same_color,
    "same_row": _rel_same_row,
    "same_col": _rel_same_col,
    "left_of": _rel_left_of,
    "above": _rel_above,
}


class RelationConcept(ConceptExpression):
    """Binary relation between two objects (complexity 2).

    For standalone use the second object must be supplied externally (e.g. via
    ``BoundRelationConcept`` or ``ExistsConcept``).
    """

    def __init__(self, relation_name: str) -> None:
        if relation_name not in RELATION_REGISTRY:
            raise ValueError(f"Unknown relation: {relation_name}")
        self.relation_name = relation_name
        self.relation_fn = RELATION_REGISTRY[relation_name]
        self.name = relation_name
        self.complexity = 2
        self.dependencies: List[str] = []
        self.type_signature = "Object,Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict, ref_obj: Optional[Dict] = None) -> bool:  # type: ignore[override]
        """Evaluate the relation.  *ref_obj* must be supplied."""
        if ref_obj is None:
            return False
        return self.relation_fn(obj, ref_obj)

    def evaluate_pair(self, a: Dict, b: Dict) -> bool:
        """Evaluate relation between two concrete objects (no scene needed)."""
        return self.relation_fn(a, b)

    def to_string(self) -> str:
        return f"{self.relation_name}(x, y)"


# 3. NotConcept -------------------------------------------------------------

class NotConcept(ConceptExpression):
    """Logical negation: NOT P(x)."""

    def __init__(self, child: ConceptExpression) -> None:
        if not _check_composition("Not", child.type_signature):
            raise TypeError(
                f"Not requires Object->Bool child, got {child.type_signature}"
            )
        self.child = child
        self.name = f"not_{child.name}"
        self.complexity = child.complexity + 1
        self.dependencies = [child.name]
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        return not self.child.evaluate(obj, scene)

    def to_string(self) -> str:
        return f"NOT({self.child.to_string()})"


# 4. AndConcept -------------------------------------------------------------

class AndConcept(ConceptExpression):
    """Conjunction: P(x) AND Q(x)."""

    def __init__(self, left: ConceptExpression, right: ConceptExpression) -> None:
        if not _check_composition("And", left.type_signature, right.type_signature):
            raise TypeError(
                f"And requires two Object->Bool children, got "
                f"{left.type_signature}, {right.type_signature}"
            )
        self.left = left
        self.right = right
        self.name = f"{left.name}_AND_{right.name}"
        self.complexity = left.complexity + right.complexity + 1
        self.dependencies = [left.name, right.name]
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        return self.left.evaluate(obj, scene) and self.right.evaluate(obj, scene)

    def to_string(self) -> str:
        return f"({self.left.to_string()} AND {self.right.to_string()})"


# 5. OrConcept --------------------------------------------------------------

class OrConcept(ConceptExpression):
    """Disjunction: P(x) OR Q(x)."""

    def __init__(self, left: ConceptExpression, right: ConceptExpression) -> None:
        if not _check_composition("Or", left.type_signature, right.type_signature):
            raise TypeError(
                f"Or requires two Object->Bool children, got "
                f"{left.type_signature}, {right.type_signature}"
            )
        self.left = left
        self.right = right
        self.name = f"{left.name}_OR_{right.name}"
        self.complexity = left.complexity + right.complexity + 1
        self.dependencies = [left.name, right.name]
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        return self.left.evaluate(obj, scene) or self.right.evaluate(obj, scene)

    def to_string(self) -> str:
        return f"({self.left.to_string()} OR {self.right.to_string()})"


# 6. ExistsConcept ----------------------------------------------------------

class ExistsConcept(ConceptExpression):
    """Existential: exists y in scene.objects: P(y) AND R(x, y)."""

    def __init__(
        self,
        filter_concept: ConceptExpression,
        relation: RelationConcept,
    ) -> None:
        if not _check_composition(
            "Exists", filter_concept.type_signature, relation.type_signature
        ):
            raise TypeError(
                f"Exists requires (Object->Bool, Object,Object->Bool), got "
                f"({filter_concept.type_signature}, {relation.type_signature})"
            )
        self.filter_concept = filter_concept
        self.relation = relation
        self.name = f"exists_{filter_concept.name}_{relation.name}"
        self.complexity = filter_concept.complexity + relation.complexity + 2
        self.dependencies = [filter_concept.name, relation.name]
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        for y in scene.get("objects", []):
            if y is obj:
                continue
            if self.filter_concept.evaluate(y, scene) and self.relation.evaluate_pair(obj, y):
                return True
        return False

    def to_string(self) -> str:
        return (
            f"exists y: {self.filter_concept.to_string().replace('(x)', '(y)')} "
            f"AND {self.relation.relation_name}(x, y)"
        )


# 7. ForAllConcept ----------------------------------------------------------

class ForAllConcept(ConceptExpression):
    """Universal: forall y in {y: P(y)}: R(x, y)."""

    def __init__(
        self,
        filter_concept: ConceptExpression,
        relation: RelationConcept,
    ) -> None:
        if not _check_composition(
            "ForAll", filter_concept.type_signature, relation.type_signature
        ):
            raise TypeError(
                f"ForAll requires (Object->Bool, Object,Object->Bool), got "
                f"({filter_concept.type_signature}, {relation.type_signature})"
            )
        self.filter_concept = filter_concept
        self.relation = relation
        self.name = f"forall_{filter_concept.name}_{relation.name}"
        self.complexity = filter_concept.complexity + relation.complexity + 2
        self.dependencies = [filter_concept.name, relation.name]
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        qualifying = [
            y for y in scene.get("objects", [])
            if y is not obj and self.filter_concept.evaluate(y, scene)
        ]
        if not qualifying:
            return True  # vacuous truth
        return all(self.relation.evaluate_pair(obj, y) for y in qualifying)

    def to_string(self) -> str:
        return (
            f"forall y: {self.filter_concept.to_string().replace('(x)', '(y)')} "
            f"=> {self.relation.relation_name}(x, y)"
        )


# 8. CountConcept -----------------------------------------------------------

class CountConcept(ConceptExpression):
    """Cardinality: count{y: P(y)} == k  or  count{y: P(y)} >= k.

    This is a *scene-level* property: evaluate returns the same value for every
    object in the scene.
    """

    def __init__(
        self,
        filter_concept: ConceptExpression,
        k: int,
        comparator: str = "==",
    ) -> None:
        if filter_concept.type_signature != "Object->Bool":
            raise TypeError(
                f"CountConcept filter must be Object->Bool, got {filter_concept.type_signature}"
            )
        if comparator not in ("==", ">=", "<=", ">", "<"):
            raise ValueError(f"Unknown comparator: {comparator}")
        self.filter_concept = filter_concept
        self.k = k
        self.comparator = comparator
        self.name = f"count_{filter_concept.name}_{comparator}_{k}"
        self.complexity = filter_concept.complexity + 2
        self.dependencies = [filter_concept.name]
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        count = sum(
            1 for y in scene.get("objects", [])
            if self.filter_concept.evaluate(y, scene)
        )
        if self.comparator == "==":
            return count == self.k
        if self.comparator == ">=":
            return count >= self.k
        if self.comparator == "<=":
            return count <= self.k
        if self.comparator == ">":
            return count > self.k
        if self.comparator == "<":
            return count < self.k
        return False  # pragma: no cover

    def to_string(self) -> str:
        return f"count(y: {self.filter_concept.to_string().replace('(x)', '(y)')}) {self.comparator} {self.k}"


# 9. ArgMaxConcept ----------------------------------------------------------

SCORE_FIELDS = [
    "area", "perimeter", "n_holes", "center_r", "center_c",
    "bbox_h", "bbox_w", "convexity",
]


class ArgMaxConcept(ConceptExpression):
    """True if obj has the maximum score among all scene objects."""

    def __init__(self, score_field: str) -> None:
        if score_field not in SCORE_FIELDS:
            raise ValueError(f"Unknown score field: {score_field}")
        self.score_field = score_field
        self.name = f"argmax_{score_field}"
        self.complexity = 2
        self.dependencies: List[str] = []
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        objects = scene.get("objects", [])
        if not objects:
            return False
        max_val = max(o.get(self.score_field, 0) for o in objects)
        return obj.get(self.score_field, 0) == max_val

    def to_string(self) -> str:
        return f"argmax_{self.score_field}(x)"


# 10. ArgMinConcept ---------------------------------------------------------

class ArgMinConcept(ConceptExpression):
    """True if obj has the minimum score among all scene objects."""

    def __init__(self, score_field: str) -> None:
        if score_field not in SCORE_FIELDS:
            raise ValueError(f"Unknown score field: {score_field}")
        self.score_field = score_field
        self.name = f"argmin_{score_field}"
        self.complexity = 2
        self.dependencies: List[str] = []
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        objects = scene.get("objects", [])
        if not objects:
            return False
        min_val = min(o.get(self.score_field, 0) for o in objects)
        return obj.get(self.score_field, 0) == min_val

    def to_string(self) -> str:
        return f"argmin_{self.score_field}(x)"


# 11. ReferenceConcept ------------------------------------------------------

class ReferenceConcept(ConceptExpression):
    """Resolves a distinguished reference object from the scene.

    Not a boolean concept itself (type_signature = "Scene->Object").
    Used inside BoundRelationConcept.
    """

    REFERENCE_TYPES = ("largest", "smallest", "unique_color", "unique_shape",
                       "marker", "frame")

    def __init__(self, ref_type: str) -> None:
        if ref_type not in self.REFERENCE_TYPES:
            raise ValueError(f"Unknown reference type: {ref_type}")
        self.ref_type = ref_type
        self.name = f"ref_{ref_type}"
        self.complexity = 1
        self.dependencies: List[str] = []
        self.type_signature = "Scene->Object"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        # ReferenceConcept is not a Bool concept; calling evaluate is a no-op.
        return False

    def resolve(self, scene: Dict) -> Optional[Dict]:
        """Return the reference object, or None if not found."""
        objects = scene.get("objects", [])
        if not objects:
            return None

        if self.ref_type == "largest":
            return max(objects, key=lambda o: o.get("area", 0))

        if self.ref_type == "smallest":
            return min(objects, key=lambda o: o.get("area", 0))

        if self.ref_type == "unique_color":
            color_counts: Dict[int, int] = Counter(
                o["primary_color"] for o in objects
            )
            unique_colors = [c for c, cnt in color_counts.items() if cnt == 1]
            if not unique_colors:
                return None
            for o in objects:
                if o["primary_color"] == unique_colors[0]:
                    return o
            return None  # pragma: no cover

        if self.ref_type == "unique_shape":
            shape_keys = [o["local_mask"].tobytes() for o in objects]
            counts = Counter(shape_keys)
            unique_keys = [k for k, cnt in counts.items() if cnt == 1]
            if not unique_keys:
                return None
            idx = shape_keys.index(unique_keys[0])
            return objects[idx]

        if self.ref_type == "marker":
            markers = [o for o in objects if o.get("area", 0) == 1]
            return markers[0] if markers else None

        if self.ref_type == "frame":
            frames = [
                o for o in objects
                if o.get("n_holes", 0) > 0 and o.get("convexity", 1.0) < 0.7
            ]
            if not frames:
                return None
            return max(frames, key=lambda o: o.get("area", 0))

        return None  # pragma: no cover

    def to_string(self) -> str:
        return f"ref({self.ref_type})"


# 12. BoundRelationConcept --------------------------------------------------

class BoundRelationConcept(ConceptExpression):
    """A relation with a bound reference: R(x, ref) where ref is resolved
    by a ReferenceConcept."""

    def __init__(
        self,
        relation: RelationConcept,
        reference: ReferenceConcept,
    ) -> None:
        if not _check_composition(
            "BoundRelation", relation.type_signature, reference.type_signature
        ):
            raise TypeError(
                f"BoundRelation requires (Object,Object->Bool, Scene->Object), got "
                f"({relation.type_signature}, {reference.type_signature})"
            )
        self.relation = relation
        self.reference = reference
        self.name = f"{relation.relation_name}_wrt_{reference.ref_type}"
        self.complexity = relation.complexity + reference.complexity
        self.dependencies = [relation.name, reference.name]
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        ref_obj = self.reference.resolve(scene)
        if ref_obj is None:
            return False
        if ref_obj is obj:
            return False
        return self.relation.evaluate_pair(obj, ref_obj)

    def to_string(self) -> str:
        return f"{self.relation.relation_name}(x, {self.reference.ref_type})"


# 13. SchemaConcept ---------------------------------------------------------

class SchemaConcept(ConceptExpression):
    """High-level structural pattern (complexity 4)."""

    SCHEMA_TYPES = ("ContainerContent", "MarkerTarget", "SymmetryCompletion")

    def __init__(self, schema_type: str) -> None:
        if schema_type not in self.SCHEMA_TYPES:
            raise ValueError(f"Unknown schema type: {schema_type}")
        self.schema_type = schema_type
        self.name = f"schema_{schema_type}"
        self.complexity = 4
        self.dependencies: List[str] = []
        self.type_signature = "Object->Bool"

    def evaluate(self, obj: Dict, scene: Dict) -> bool:
        if self.schema_type == "ContainerContent":
            return self._eval_container_content(obj, scene)
        if self.schema_type == "MarkerTarget":
            return self._eval_marker_target(obj, scene)
        if self.schema_type == "SymmetryCompletion":
            return self._eval_symmetry_completion(obj, scene)
        return False  # pragma: no cover

    # -- ContainerContent: obj is inside a frame ----------------------------
    def _eval_container_content(self, obj: Dict, scene: Dict) -> bool:
        for other in scene.get("objects", []):
            if other is obj:
                continue
            if other.get("n_holes", 0) == 0 or other.get("convexity", 1.0) >= 0.7:
                continue
            if _rel_inside(obj, other):
                return True
        return False

    # -- MarkerTarget: obj shares colour with a single-cell marker ----------
    def _eval_marker_target(self, obj: Dict, scene: Dict) -> bool:
        if obj.get("area", 0) == 1:
            return False  # the marker itself is not a target
        markers = [
            o for o in scene.get("objects", [])
            if o.get("area", 0) == 1 and o is not obj
        ]
        if not markers:
            return False
        marker_colors = {m["primary_color"] for m in markers}
        return obj["primary_color"] in marker_colors

    # -- SymmetryCompletion: obj is part of a symmetric layout ---------------
    def _eval_symmetry_completion(self, obj: Dict, scene: Dict) -> bool:
        objects = scene.get("objects", [])
        if len(objects) < 2:
            return False
        grid_h = scene.get("grid_h", 1)
        grid_w = scene.get("grid_w", 1)
        cr = obj["center_r"]
        cc = obj["center_c"]
        # Check mirror partner across vertical center
        mirror_c = grid_w - 1 - cc
        for other in objects:
            if other is obj:
                continue
            if (abs(other["center_r"] - cr) < 1.5 and
                    abs(other["center_c"] - mirror_c) < 1.5):
                return True
        # Check mirror partner across horizontal center
        mirror_r = grid_h - 1 - cr
        for other in objects:
            if other is obj:
                continue
            if (abs(other["center_r"] - mirror_r) < 1.5 and
                    abs(other["center_c"] - cc) < 1.5):
                return True
        return False

    def to_string(self) -> str:
        return f"schema_{self.schema_type}(x)"


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS — build scene dicts from grids
# ═══════════════════════════════════════════════════════════════════════════

def _scene_from_grid(grid: np.ndarray) -> Dict:
    """Build the standard scene dict from a grid."""
    objects = _extract_objects_with_properties(grid)
    h, w = grid.shape
    return {"objects": objects, "grid": grid, "grid_h": h, "grid_w": w}


def _scene_from_objects(objects: List[Dict], grid: np.ndarray) -> Dict:
    """Build a scene dict from pre-extracted objects."""
    h, w = grid.shape
    return {"objects": objects, "grid": grid, "grid_h": h, "grid_w": w}


# ═══════════════════════════════════════════════════════════════════════════
# CONCEPT GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

class ConceptGenerator:
    """Bottom-up enumeration of concept expressions."""

    # Score fields used for argmax / argmin at depth 1
    _DEPTH1_SCORE_FIELDS = ["area", "perimeter", "n_holes", "center_r", "center_c"]

    def __init__(self, primitives: Optional[List[str]] = None) -> None:
        self.primitives = primitives or _all_property_names()

    # -- depth 1 ------------------------------------------------------------

    def generate_depth_1(self) -> List[ConceptExpression]:
        """All primitive concepts plus argmax/argmin over numeric fields."""
        concepts: List[ConceptExpression] = []
        for p in self.primitives:
            concepts.append(PrimitiveConcept(p))
        for field in self._DEPTH1_SCORE_FIELDS:
            concepts.append(ArgMaxConcept(field))
            concepts.append(ArgMinConcept(field))
        return concepts

    # -- depth 2 ------------------------------------------------------------

    def generate_depth_2(self, beam_size: int = 200) -> List[ConceptExpression]:
        """Compose depth-1 concepts into depth-2 expressions."""
        d1 = self.generate_depth_1()
        bool_d1 = [c for c in d1 if c.type_signature == "Object->Bool"]
        concepts: List[ConceptExpression] = list(d1)

        # NOT(primitive)
        for c in bool_d1:
            concepts.append(NotConcept(c))

        # AND(primitive, primitive) — skip symmetric duplicates
        for i, p in enumerate(bool_d1):
            for q in bool_d1[i + 1:]:
                concepts.append(AndConcept(p, q))

        # BoundRelation(relation, reference)
        rel_names = list(RELATION_REGISTRY.keys())
        ref_types = list(ReferenceConcept.REFERENCE_TYPES)
        for rn in rel_names:
            rel = RelationConcept(rn)
            for rt in ref_types:
                ref = ReferenceConcept(rt)
                concepts.append(BoundRelationConcept(rel, ref))

        # ExistsConcept(filter, relation) — pick a small set of useful filters
        useful_filters = [
            PrimitiveConcept("single_cell"),
            PrimitiveConcept("is_largest"),
            PrimitiveConcept("is_frame"),
            PrimitiveConcept("is_unique_color"),
        ]
        for filt in useful_filters:
            for rn in rel_names:
                rel = RelationConcept(rn)
                concepts.append(ExistsConcept(filt, rel))

        # Prune to beam_size by complexity
        concepts.sort(key=lambda c: c.complexity)
        return concepts[:beam_size]

    # -- depth k ------------------------------------------------------------

    def generate_depth_k(self, k: int, beam_size: int = 100) -> List[ConceptExpression]:
        """Generate up to depth k, pruning by beam_size at each level."""
        if k <= 0:
            return []
        current = self.generate_depth_1()
        if k == 1:
            current.sort(key=lambda c: c.complexity)
            return current[:beam_size]

        for depth in range(2, k + 1):
            bool_pool = [c for c in current if c.type_signature == "Object->Bool"]
            new: List[ConceptExpression] = []

            # NOT of previous level
            for c in bool_pool:
                nc = NotConcept(c)
                if nc.complexity <= depth * 3:  # keep bounded
                    new.append(nc)

            # AND of two from pool (skip duplicates by sorted name)
            seen_pairs: set = set()
            for i, p in enumerate(bool_pool):
                for q in bool_pool[i + 1:]:
                    pair_key = (p.name, q.name) if p.name < q.name else (q.name, p.name)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    ac = AndConcept(p, q)
                    if ac.complexity <= depth * 3:
                        new.append(ac)

            # OR of two from pool
            seen_pairs2: set = set()
            for i, p in enumerate(bool_pool):
                for q in bool_pool[i + 1:]:
                    pair_key = (p.name, q.name) if p.name < q.name else (q.name, p.name)
                    if pair_key in seen_pairs2:
                        continue
                    seen_pairs2.add(pair_key)
                    oc = OrConcept(p, q)
                    if oc.complexity <= depth * 3:
                        new.append(oc)

            combined = current + new
            combined.sort(key=lambda c: c.complexity)
            # Deduplicate by name
            seen_names: set = set()
            deduped: List[ConceptExpression] = []
            for c in combined:
                if c.name not in seen_names:
                    seen_names.add(c.name)
                    deduped.append(c)
            current = deduped[:beam_size]

        return current

    # -- failure-guided generation ------------------------------------------

    def generate_from_failure_cluster(
        self,
        cluster_tasks: List[Dict],
        max_concepts: int = 50,
    ) -> List[ConceptExpression]:
        """Generate concepts guided by a specific failure cluster.

        Analyses each task to discover what structural features separate kept
        from removed objects, then produces targeted concepts.
        """
        concepts: List[ConceptExpression] = []
        seen: set = set()

        def _add(c: ConceptExpression) -> None:
            if c.name not in seen and len(concepts) < max_concepts:
                seen.add(c.name)
                concepts.append(c)

        for task in cluster_tasks:
            pairs = task.get("train", [])
            for pair in pairs:
                inp_raw = pair.get("input")
                out_raw = pair.get("output")
                if inp_raw is None or out_raw is None:
                    continue
                inp = np.array(inp_raw, dtype=int) if not isinstance(inp_raw, np.ndarray) else inp_raw
                out = np.array(out_raw, dtype=int) if not isinstance(out_raw, np.ndarray) else out_raw
                objs = _extract_objects_with_properties(inp)
                groups = _classify_two_groups(objs, inp, out)
                if groups is None:
                    continue
                kept_idx, removed_idx = groups
                scene = _scene_from_objects(objs, inp)

                # --- Reference-based patterns ---
                for ref_type in ReferenceConcept.REFERENCE_TYPES:
                    ref = ReferenceConcept(ref_type)
                    ref_obj = ref.resolve(scene)
                    if ref_obj is None:
                        continue
                    for rn in ("same_color", "same_shape", "same_row", "same_col",
                               "inside", "touches"):
                        rel = RelationConcept(rn)
                        br = BoundRelationConcept(rel, ref)
                        # Check if this separates kept/removed
                        kept_vals = [br.evaluate(objs[i], scene) for i in kept_idx
                                     if objs[i] is not ref_obj]
                        removed_vals = [br.evaluate(objs[i], scene) for i in removed_idx
                                        if objs[i] is not ref_obj]
                        if kept_vals and removed_vals:
                            if (all(kept_vals) and not any(removed_vals)) or \
                               (not any(kept_vals) and all(removed_vals)):
                                _add(br)

                # --- Spatial quantified patterns ---
                for filt_name in ("single_cell", "is_largest", "is_frame",
                                  "is_unique_color"):
                    filt = PrimitiveConcept(filt_name)
                    for rn in ("same_row", "same_col", "same_color", "inside",
                               "touches"):
                        rel = RelationConcept(rn)
                        ex = ExistsConcept(filt, rel)
                        kept_vals = [ex.evaluate(objs[i], scene) for i in kept_idx]
                        removed_vals = [ex.evaluate(objs[i], scene) for i in removed_idx]
                        if kept_vals and removed_vals:
                            if (all(kept_vals) and not any(removed_vals)) or \
                               (not any(kept_vals) and all(removed_vals)):
                                _add(ex)

                # --- Topology checks ---
                for pn in ("has_holes", "is_convex", "single_cell",
                           "is_unique_shape", "is_filled_rect"):
                    pc = PrimitiveConcept(pn)
                    kept_vals = [pc.evaluate(objs[i], scene) for i in kept_idx]
                    removed_vals = [pc.evaluate(objs[i], scene) for i in removed_idx]
                    if kept_vals and removed_vals:
                        if (all(kept_vals) and not any(removed_vals)) or \
                           (not any(kept_vals) and all(removed_vals)):
                            _add(pc)

                # --- Count-based patterns ---
                for pn in ("single_cell", "is_largest", "is_unique_color"):
                    filt = PrimitiveConcept(pn)
                    n_matching = sum(
                        1 for o in objs if filt.evaluate(o, scene)
                    )
                    if n_matching > 0:
                        cc = CountConcept(filt, n_matching, "==")
                        _add(cc)

        return concepts


# ═══════════════════════════════════════════════════════════════════════════
# CONCEPT VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class ConceptValidator:
    """Evaluate and validate concept expressions on ARC tasks."""

    def training_discrimination_score(
        self,
        concept: ConceptExpression,
        task: Dict,
    ) -> float:
        """Fraction of training pairs where concept discriminates kept from
        removed (perfectly, in either polarity)."""
        pairs = task.get("train", [])
        if not pairs:
            return 0.0
        n_good = 0
        for pair in pairs:
            inp = np.array(pair["input"], dtype=int) if not isinstance(pair["input"], np.ndarray) else pair["input"]
            out = np.array(pair["output"], dtype=int) if not isinstance(pair["output"], np.ndarray) else pair["output"]
            objs = _extract_objects_with_properties(inp)
            groups = _classify_two_groups(objs, inp, out)
            if groups is None:
                continue
            kept_idx, removed_idx = groups
            scene = _scene_from_objects(objs, inp)
            kept_vals = [concept.evaluate(objs[i], scene) for i in kept_idx]
            removed_vals = [concept.evaluate(objs[i], scene) for i in removed_idx]
            if (all(kept_vals) and not any(removed_vals)) or \
               (not any(kept_vals) and all(removed_vals)):
                n_good += 1
        return n_good / len(pairs)

    def loo_validate(
        self,
        concept: ConceptExpression,
        task: Dict,
    ) -> bool:
        """Leave-one-out cross-validation on training pairs."""
        pairs = task.get("train", [])
        if len(pairs) < 2:
            return True  # not enough data to falsify

        for hold_idx in range(len(pairs)):
            # Learn polarity from remaining pairs
            polarity_votes = {"true_keeps": 0, "false_keeps": 0}
            for i, pair in enumerate(pairs):
                if i == hold_idx:
                    continue
                inp = np.array(pair["input"], dtype=int) if not isinstance(pair["input"], np.ndarray) else pair["input"]
                out = np.array(pair["output"], dtype=int) if not isinstance(pair["output"], np.ndarray) else pair["output"]
                objs = _extract_objects_with_properties(inp)
                groups = _classify_two_groups(objs, inp, out)
                if groups is None:
                    continue
                kept_idx_list, removed_idx_list = groups
                scene = _scene_from_objects(objs, inp)
                kv = [concept.evaluate(objs[k], scene) for k in kept_idx_list]
                rv = [concept.evaluate(objs[k], scene) for k in removed_idx_list]
                if all(kv) and not any(rv):
                    polarity_votes["true_keeps"] += 1
                elif not any(kv) and all(rv):
                    polarity_votes["false_keeps"] += 1

            if polarity_votes["true_keeps"] == 0 and polarity_votes["false_keeps"] == 0:
                continue  # no signal — skip
            keep_when_true = polarity_votes["true_keeps"] >= polarity_votes["false_keeps"]

            # Test on held-out pair
            hp = pairs[hold_idx]
            inp_h = np.array(hp["input"], dtype=int) if not isinstance(hp["input"], np.ndarray) else hp["input"]
            out_h = np.array(hp["output"], dtype=int) if not isinstance(hp["output"], np.ndarray) else hp["output"]
            objs_h = _extract_objects_with_properties(inp_h)
            groups_h = _classify_two_groups(objs_h, inp_h, out_h)
            if groups_h is None:
                continue
            kept_h, removed_h = groups_h
            scene_h = _scene_from_objects(objs_h, inp_h)
            kv_h = [concept.evaluate(objs_h[k], scene_h) for k in kept_h]
            rv_h = [concept.evaluate(objs_h[k], scene_h) for k in removed_h]
            if keep_when_true:
                if not (all(kv_h) and not any(rv_h)):
                    return False
            else:
                if not (not any(kv_h) and all(rv_h)):
                    return False
        return True

    def batch_evaluate(
        self,
        concepts: List[ConceptExpression],
        tasks: List[Dict],
        min_discrimination: float = 1.0,
        require_loo: bool = True,
    ) -> List[Tuple[ConceptExpression, Dict]]:
        """Evaluate many concepts on many tasks, returning those that pass."""
        results: List[Tuple[ConceptExpression, Dict]] = []
        for concept in concepts:
            for task in tasks:
                task_id = task.get("task_id", "")
                disc = self.training_discrimination_score(concept, task)
                if disc < min_discrimination:
                    continue
                loo_passed = True
                if require_loo:
                    loo_passed = self.loo_validate(concept, task)
                if not loo_passed:
                    continue
                results.append((concept, {
                    "task_id": task_id,
                    "discrimination": disc,
                    "loo_passed": loo_passed,
                }))
        return results

    # ------------------------------------------------------------------
    # STAGED VALIDATION
    # ------------------------------------------------------------------

    def validate_staged(
        self,
        concept: ConceptExpression,
        tasks: List[Dict],
        cluster_tasks: Optional[List[Dict]] = None,
        holdout_tasks: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Run staged validation, returning the highest level reached.

        Levels:
          1 (candidate_validated): discriminates in ≥1 task
          2 (loo_validated): passes LOO on source tasks
          3 (cluster_validated): works across ≥2 cluster tasks
          5 (transfer_validated): works on held-out tasks

        Level 4 (promotion_validated) is set externally.
        """
        result: Dict[str, Any] = {
            "level": "proposed",
            "level_number": 0,
            "discrimination_scores": {},
            "loo_passed": False,
            "cluster_score": 0.0,
            "n_cluster_passed": 0,
            "transfer_score": 0.0,
            "n_transfer_passed": 0,
        }

        # Level 1: discrimination in any task
        best_disc = 0.0
        disc_scores: Dict[str, float] = {}
        for task in tasks:
            tid = task.get("task_id", "")
            disc = self.training_discrimination_score(concept, task)
            disc_scores[tid] = disc
            best_disc = max(best_disc, disc)

        result["discrimination_scores"] = disc_scores
        if best_disc < 1.0:
            return result
        result["level"] = "candidate_validated"
        result["level_number"] = 1

        # Level 2: LOO on tasks where it discriminates
        passing_tasks = [t for t in tasks
                         if disc_scores.get(t.get("task_id", ""), 0) >= 1.0]
        all_loo = all(self.loo_validate(concept, t) for t in passing_tasks)
        result["loo_passed"] = all_loo
        if not all_loo:
            return result
        result["level"] = "loo_validated"
        result["level_number"] = 2

        # Level 3: cluster validation
        eval_cluster = cluster_tasks if cluster_tasks else tasks
        n_cluster_passed = 0
        cluster_total = 0.0
        for task in eval_cluster:
            disc = self.training_discrimination_score(concept, task)
            cluster_total += disc
            if disc >= 1.0:
                n_cluster_passed += 1
        result["cluster_score"] = cluster_total / max(len(eval_cluster), 1)
        result["n_cluster_passed"] = n_cluster_passed

        if n_cluster_passed < 2 and len(eval_cluster) >= 2:
            return result
        result["level"] = "cluster_validated"
        result["level_number"] = 3

        # Level 5: transfer validation (skip 4, it's external)
        eval_holdout = holdout_tasks or []
        if not eval_holdout:
            return result
        n_transfer_passed = 0
        transfer_total = 0.0
        for task in eval_holdout:
            disc = self.training_discrimination_score(concept, task)
            transfer_total += disc
            if disc >= 1.0 and self.loo_validate(concept, task):
                n_transfer_passed += 1
        result["transfer_score"] = transfer_total / max(len(eval_holdout), 1)
        result["n_transfer_passed"] = n_transfer_passed

        if n_transfer_passed == 0:
            return result
        result["level"] = "transfer_validated"
        result["level_number"] = 5

        return result
