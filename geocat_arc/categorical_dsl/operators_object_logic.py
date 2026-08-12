"""Object logic operators — copy, set operations, conditional transforms."""
from __future__ import annotations
from collections import Counter
from .morphism import Morphism
from .types import ArcType
from geocat_arc.perception.objects import ARCObject


class CopyToPosition(Morphism):
    name = "copy_to_position"
    input_types = (ArcType.OBJECT, ArcType.REGION)
    output_type = ArcType.OBJECT
    cost = 1.0

    def apply(self, obj: ARCObject, region: tuple[int, int, int, int]) -> ARCObject:
        target_r, target_c = region[0], region[1]
        src_r, src_c = obj.bounding_box[0], obj.bounding_box[1]
        return obj.translated(target_r - src_r, target_c - src_c)

    def applicable(self, *args) -> bool:
        return len(args) >= 2 and isinstance(args[0], ARCObject)


class CopyRelativeToAnchor(Morphism):
    name = "copy_relative_to_anchor"
    input_types = (ArcType.OBJECT, ArcType.OBJECT, ArcType.VECTOR)
    output_type = ArcType.OBJECT
    cost = 1.5

    def apply(self, obj: ARCObject, anchor: ARCObject, vector: tuple[int, int]) -> ARCObject:
        anchor_r, anchor_c = anchor.centroid
        dr, dc = vector
        target_r = int(anchor_r) + dr
        target_c = int(anchor_c) + dc
        src_r, src_c = obj.bounding_box[0], obj.bounding_box[1]
        return obj.translated(target_r - src_r, target_c - src_c)

    def applicable(self, *args) -> bool:
        return (len(args) >= 3 and isinstance(args[0], ARCObject)
                and isinstance(args[1], ARCObject))


class ConditionalRecolor(Morphism):
    name = "conditional_recolor"
    input_types = (ArcType.OBJECT_SET, ArcType.PREDICATE, ArcType.COLOR)
    output_type = ArcType.OBJECT_SET
    cost = 1.0

    def apply(self, objects: list[ARCObject], predicate, new_color: int) -> list[ARCObject]:
        result = []
        for obj in objects:
            if predicate(obj):
                result.append(obj.recolored(new_color))
            else:
                result.append(obj)
        return result

    def applicable(self, *args) -> bool:
        return len(args) >= 3 and isinstance(args[0], list)


class ReplaceObjectByShapeMatch(Morphism):
    name = "replace_by_shape"
    input_types = (ArcType.OBJECT_SET, ArcType.OBJECT)
    output_type = ArcType.OBJECT_SET
    cost = 1.5

    def apply(self, objects: list[ARCObject], replacement: ARCObject) -> list[ARCObject]:
        target_sig = replacement.shape_signature
        result = []
        for obj in objects:
            if obj.shape_signature == target_sig and obj.id != replacement.id:
                replaced = ARCObject(
                    id=obj.id, cells=obj.cells,
                    color=replacement.color, bounding_box=obj.bounding_box,
                )
                result.append(replaced)
            else:
                result.append(obj)
        return result

    def applicable(self, *args) -> bool:
        return len(args) >= 2 and isinstance(args[0], list) and isinstance(args[1], ARCObject)


class ObjectUnion(Morphism):
    name = "object_union"
    input_types = (ArcType.OBJECT, ArcType.OBJECT)
    output_type = ArcType.OBJECT
    cost = 0.5

    def apply(self, a: ARCObject, b: ARCObject) -> ARCObject:
        merged = a.cells | b.cells
        if not merged:
            raise ValueError("Union of two objects produced empty result")
        rows = [r for r, c in merged]
        cols = [c for r, c in merged]
        bbox = (min(rows), min(cols), max(rows) + 1, max(cols) + 1)
        return ARCObject(id=a.id, cells=frozenset(merged), color=a.color, bounding_box=bbox)

    def applicable(self, *args) -> bool:
        return len(args) >= 2 and isinstance(args[0], ARCObject) and isinstance(args[1], ARCObject)


class ObjectIntersection(Morphism):
    name = "object_intersection"
    input_types = (ArcType.OBJECT, ArcType.OBJECT)
    output_type = ArcType.OBJECT
    cost = 0.5

    def apply(self, a: ARCObject, b: ARCObject) -> ARCObject:
        common = a.cells & b.cells
        if not common:
            raise ValueError("Intersection of two objects is empty")
        rows = [r for r, c in common]
        cols = [c for r, c in common]
        bbox = (min(rows), min(cols), max(rows) + 1, max(cols) + 1)
        return ARCObject(id=a.id, cells=frozenset(common), color=a.color, bounding_box=bbox)

    def applicable(self, *args) -> bool:
        if len(args) < 2:
            return False
        if not isinstance(args[0], ARCObject) or not isinstance(args[1], ARCObject):
            return False
        return bool(args[0].cells & args[1].cells)


class ObjectDifference(Morphism):
    name = "object_difference"
    input_types = (ArcType.OBJECT, ArcType.OBJECT)
    output_type = ArcType.OBJECT
    cost = 0.5

    def apply(self, a: ARCObject, b: ARCObject) -> ARCObject:
        diff = a.cells - b.cells
        if not diff:
            raise ValueError("Difference of two objects is empty")
        rows = [r for r, c in diff]
        cols = [c for r, c in diff]
        bbox = (min(rows), min(cols), max(rows) + 1, max(cols) + 1)
        return ARCObject(id=a.id, cells=frozenset(diff), color=a.color, bounding_box=bbox)

    def applicable(self, *args) -> bool:
        if len(args) < 2:
            return False
        if not isinstance(args[0], ARCObject) or not isinstance(args[1], ARCObject):
            return False
        return bool(args[0].cells - args[1].cells)


class CountBasedSelect(Morphism):
    name = "count_based_select"
    input_types = (ArcType.OBJECT_SET,)
    output_type = ArcType.OBJECT
    cost = 0.5

    def __init__(self, mode: str = "largest"):
        self.mode = mode

    def apply(self, objects: list[ARCObject]) -> ARCObject:
        if not objects:
            raise ValueError("Cannot select from empty object set")
        if self.mode == "largest":
            return max(objects, key=lambda o: o.size)
        elif self.mode == "smallest":
            return min(objects, key=lambda o: o.size)
        elif self.mode == "most_frequent_color":
            color_counts = Counter(o.color for o in objects)
            target_color = color_counts.most_common(1)[0][0]
            return next(o for o in objects if o.color == target_color)
        elif self.mode == "least_frequent_color":
            color_counts = Counter(o.color for o in objects)
            target_color = color_counts.most_common()[-1][0]
            return next(o for o in objects if o.color == target_color)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def applicable(self, *args) -> bool:
        return len(args) >= 1 and isinstance(args[0], list) and len(args[0]) > 0
