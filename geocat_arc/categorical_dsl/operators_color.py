"""Color ARC operators as typed morphisms."""
from __future__ import annotations
import numpy as np
from .morphism import Morphism
from .types import ArcType
from geocat_arc.perception.objects import ARCObject


class Recolor(Morphism):
    name = "recolor"
    input_types = (ArcType.OBJECT, ArcType.COLOR)
    output_type = ArcType.OBJECT
    cost = 0.5

    def apply(self, obj: ARCObject, new_color: int) -> ARCObject:
        return obj.recolored(new_color)


class FillRegion(Morphism):
    name = "fill_region"
    input_types = (ArcType.REGION, ArcType.COLOR)
    output_type = ArcType.GRID_PATCH
    cost = 0.5

    def apply(self, region: tuple[int, int, int, int], color: int) -> dict:
        r0, c0, r1, c1 = region
        cells = frozenset((r, c) for r in range(r0, r1) for c in range(c0, c1))
        return {"cells": cells, "color": color, "region": region}
