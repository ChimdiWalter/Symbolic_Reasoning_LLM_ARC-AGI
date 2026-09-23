"""Finite predicates over ARC objects."""
from __future__ import annotations
from geocat_arc.perception.objects import ARCObject


class Predicate:
    """Base class for predicates."""
    arity: int = 1

    def __call__(self, *args) -> bool:
        raise NotImplementedError


class HasColor(Predicate):
    arity = 1
    def __init__(self, color: int):
        self.color = color
    def __call__(self, obj: ARCObject) -> bool:
        return obj.color == self.color
    def __repr__(self):
        return f"HasColor({self.color})"


class SameColor(Predicate):
    arity = 2
    def __call__(self, a: ARCObject, b: ARCObject) -> bool:
        return a.color == b.color and a.id != b.id
    def __repr__(self):
        return "SameColor()"


class IsRectangle(Predicate):
    arity = 1
    def __call__(self, obj: ARCObject) -> bool:
        return obj.is_rectangle
    def __repr__(self):
        return "IsRectangle()"


class IsLine(Predicate):
    arity = 1
    def __call__(self, obj: ARCObject) -> bool:
        return obj.is_line
    def __repr__(self):
        return "IsLine()"


class HasHole(Predicate):
    arity = 1
    def __call__(self, obj: ARCObject) -> bool:
        return obj.has_hole
    def __repr__(self):
        return "HasHole()"


class SameShape(Predicate):
    arity = 2
    def __call__(self, a: ARCObject, b: ARCObject) -> bool:
        return a.shape_signature == b.shape_signature and a.id != b.id
    def __repr__(self):
        return "SameShape()"


class IsLargest(Predicate):
    arity = 1
    def __init__(self, all_objects: list[ARCObject]):
        self._max_size = max(o.size for o in all_objects) if all_objects else 0
    def __call__(self, obj: ARCObject) -> bool:
        return obj.size == self._max_size
    def __repr__(self):
        return "IsLargest()"


class IsSmallest(Predicate):
    arity = 1
    def __init__(self, all_objects: list[ARCObject]):
        self._min_size = min(o.size for o in all_objects) if all_objects else 0
    def __call__(self, obj: ARCObject) -> bool:
        return obj.size == self._min_size
    def __repr__(self):
        return "IsSmallest()"


class SameSize(Predicate):
    arity = 2
    def __call__(self, a: ARCObject, b: ARCObject) -> bool:
        return a.size == b.size and a.id != b.id
    def __repr__(self):
        return "SameSize()"


class Inside(Predicate):
    arity = 2
    def __call__(self, inner: ARCObject, outer: ARCObject) -> bool:
        if inner.id == outer.id:
            return False
        ar0, ac0, ar1, ac1 = outer.bounding_box
        br0, bc0, br1, bc1 = inner.bounding_box
        return ar0 <= br0 and ac0 <= bc0 and ar1 >= br1 and ac1 >= bc1
    def __repr__(self):
        return "Inside()"


class TouchesBorder(Predicate):
    arity = 1
    def __init__(self, grid_h: int, grid_w: int):
        self.grid_h = grid_h
        self.grid_w = grid_w
    def __call__(self, obj: ARCObject) -> bool:
        for r, c in obj.cells:
            if r == 0 or r == self.grid_h - 1 or c == 0 or c == self.grid_w - 1:
                return True
        return False
    def __repr__(self):
        return f"TouchesBorder({self.grid_h},{self.grid_w})"


class LeftOf(Predicate):
    arity = 2
    def __call__(self, a: ARCObject, b: ARCObject) -> bool:
        return a.centroid[1] < b.centroid[1] and a.bounding_box[3] <= b.bounding_box[1]
    def __repr__(self):
        return "LeftOf()"


class Above(Predicate):
    arity = 2
    def __call__(self, a: ARCObject, b: ARCObject) -> bool:
        return a.centroid[0] < b.centroid[0] and a.bounding_box[2] <= b.bounding_box[0]
    def __repr__(self):
        return "Above()"
