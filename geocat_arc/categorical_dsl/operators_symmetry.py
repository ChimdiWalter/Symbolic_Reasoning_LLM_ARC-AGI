"""Symmetry ARC operators as typed morphisms."""
from __future__ import annotations
import numpy as np
from .morphism import Morphism
from .types import ArcType
from geocat_arc.perception.objects import ARCObject


class CompleteSymmetry(Morphism):
    name = "complete_symmetry"
    input_types = (ArcType.OBJECT_SET, ArcType.AXIS)
    output_type = ArcType.OBJECT_SET
    cost = 2.0

    def apply(self, objects: list[ARCObject], axis: str) -> list[ARCObject]:
        result = list(objects)
        existing_sigs = {(obj.shape_signature, obj.color) for obj in objects}

        for obj in objects:
            mask = obj.mask
            if axis == "horizontal":
                reflected = np.flipud(mask)
            elif axis == "vertical":
                reflected = np.fliplr(mask)
            else:
                continue

            r0, c0, r1, c1 = obj.bounding_box

            if axis == "horizontal":
                new_r0 = 2 * r0 - r1 + (r1 - r0)
                new_cells = set()
                for r in range(reflected.shape[0]):
                    for c in range(reflected.shape[1]):
                        if reflected[r, c]:
                            new_cells.add((new_r0 + r, c0 + c))
            else:
                new_c0 = 2 * c0 - c1 + (c1 - c0)
                new_cells = set()
                for r in range(reflected.shape[0]):
                    for c in range(reflected.shape[1]):
                        if reflected[r, c]:
                            new_cells.add((r0 + r, new_c0 + c))

            if new_cells:
                new_obj = ARCObject(
                    id=obj.id + 2000,
                    cells=frozenset(new_cells),
                    color=obj.color,
                    bounding_box=obj.bounding_box,
                )
                sig = (new_obj.shape_signature, new_obj.color)
                if sig not in existing_sigs:
                    result.append(new_obj)
                    existing_sigs.add(sig)

        return result
