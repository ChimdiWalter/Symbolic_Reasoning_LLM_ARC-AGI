"""ARC type system for the categorical DSL."""
from enum import Enum, auto


class ArcType(Enum):
    GRID = auto()
    OBJECT = auto()
    OBJECT_SET = auto()
    REGION = auto()
    MASK = auto()
    COLOR = auto()
    VECTOR = auto()
    AXIS = auto()
    ANGLE = auto()
    RELATION_GRAPH = auto()
    GRID_PATCH = auto()
    PREDICATE = auto()
