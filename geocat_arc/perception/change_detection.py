"""Detect changes between input and output grids."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .grid import Grid
from .objects import ARCObject, extract_objects
from .matching import match_objects


@dataclass
class ChangeReport:
    cells_changed: list[tuple[int, int, int, int]]  # (r, c, old_color, new_color)
    num_cells_changed: int
    objects_added: list[ARCObject]
    objects_removed: list[ARCObject]
    objects_moved: list[tuple[ARCObject, ARCObject, tuple[int, int]]]  # (in, out, displacement)
    objects_recolored: list[tuple[ARCObject, ARCObject]]  # (in, out)
    cell_accuracy: float


def detect_changes(input_grid: Grid, output_grid: Grid) -> ChangeReport:
    in_data = input_grid.to_numpy()
    out_data = output_grid.to_numpy()

    ih, iw = in_data.shape
    oh, ow = out_data.shape

    cells_changed = []
    min_h, min_w = min(ih, oh), min(iw, ow)
    total_cells = oh * ow
    matching_cells = 0

    for r in range(oh):
        for c in range(ow):
            if r < ih and c < iw:
                if in_data[r, c] != out_data[r, c]:
                    cells_changed.append((r, c, int(in_data[r, c]), int(out_data[r, c])))
                else:
                    matching_cells += 1
            else:
                cells_changed.append((r, c, -1, int(out_data[r, c])))

    cell_accuracy = matching_cells / total_cells if total_cells > 0 else 0.0

    in_objects = extract_objects(input_grid)
    out_objects = extract_objects(output_grid)

    matches = match_objects(in_objects, out_objects)
    matched_in_ids = {m[0].id for m in matches}
    matched_out_ids = {m[1].id for m in matches}

    objects_removed = [o for o in in_objects if o.id not in matched_in_ids]
    objects_added = [o for o in out_objects if o.id not in matched_out_ids]

    objects_moved = []
    objects_recolored = []
    for in_obj, out_obj, sim in matches:
        in_c = in_obj.centroid
        out_c = out_obj.centroid
        dr = out_c[0] - in_c[0]
        dc = out_c[1] - in_c[1]
        if abs(dr) > 0.5 or abs(dc) > 0.5:
            objects_moved.append((in_obj, out_obj, (int(round(dr)), int(round(dc)))))
        if in_obj.color != out_obj.color:
            objects_recolored.append((in_obj, out_obj))

    return ChangeReport(
        cells_changed=cells_changed,
        num_cells_changed=len(cells_changed),
        objects_added=objects_added,
        objects_removed=objects_removed,
        objects_moved=objects_moved,
        objects_recolored=objects_recolored,
        cell_accuracy=cell_accuracy,
    )
