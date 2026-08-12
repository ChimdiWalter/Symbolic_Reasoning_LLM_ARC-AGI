"""Relation graph construction between ARC objects."""
from __future__ import annotations
from dataclasses import dataclass, field
from .objects import ARCObject


@dataclass
class Relation:
    source_id: int
    target_id: int
    relation_type: str

    def __repr__(self) -> str:
        return f"{self.relation_type}({self.source_id}, {self.target_id})"


def _bbox_center(obj: ARCObject) -> tuple[float, float]:
    return obj.centroid


def left_of(a: ARCObject, b: ARCObject) -> bool:
    return a.centroid[1] < b.centroid[1] and a.bounding_box[3] <= b.bounding_box[1]


def right_of(a: ARCObject, b: ARCObject) -> bool:
    return left_of(b, a)


def above(a: ARCObject, b: ARCObject) -> bool:
    return a.centroid[0] < b.centroid[0] and a.bounding_box[2] <= b.bounding_box[0]


def below(a: ARCObject, b: ARCObject) -> bool:
    return above(b, a)


def contains(a: ARCObject, b: ARCObject) -> bool:
    if a.id == b.id:
        return False
    ar0, ac0, ar1, ac1 = a.bounding_box
    br0, bc0, br1, bc1 = b.bounding_box
    return ar0 <= br0 and ac0 <= bc0 and ar1 >= br1 and ac1 >= bc1


def adjacent(a: ARCObject, b: ARCObject) -> bool:
    if a.id == b.id:
        return False
    for r, c in a.cells:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if (r + dr, c + dc) in b.cells:
                return True
    return False


def same_color(a: ARCObject, b: ARCObject) -> bool:
    return a.color == b.color and a.id != b.id


def same_shape(a: ARCObject, b: ARCObject) -> bool:
    if a.id == b.id:
        return False
    return a.shape_signature == b.shape_signature


def same_size(a: ARCObject, b: ARCObject) -> bool:
    return a.size == b.size and a.id != b.id


def overlaps(a: ARCObject, b: ARCObject) -> bool:
    if a.id == b.id:
        return False
    return bool(a.cells & b.cells)


ALL_RELATION_CHECKS = [
    ("left_of", left_of),
    ("right_of", right_of),
    ("above", above),
    ("below", below),
    ("contains", contains),
    ("adjacent", adjacent),
    ("same_color", same_color),
    ("same_shape", same_shape),
    ("same_size", same_size),
    ("overlaps", overlaps),
]


def build_relation_graph(objects: list[ARCObject]) -> list[Relation]:
    relations = []
    for i, a in enumerate(objects):
        for j, b in enumerate(objects):
            if i == j:
                continue
            for rel_name, rel_fn in ALL_RELATION_CHECKS:
                if rel_fn(a, b):
                    relations.append(Relation(
                        source_id=a.id,
                        target_id=b.id,
                        relation_type=rel_name,
                    ))
    return relations
