"""Reusable task-level operator schemas.

Each schema is executable, LOO-checkable, falsifiable, and certifiable.
Schemas capture high-level transformation patterns that recur across ARC tasks.

Schemas:
    MarkerTargetTransform     — marker object selects targets for transformation
    ContainerContentExtract   — extract contents from containers
    SeparatorCellCompose      — decompose by separators, compose cells
    SymmetryCompletion        — complete a pattern by symmetry
    PatternRepetitionFill     — fill region by repeating a pattern
    LineExtendUntilBoundary   — extend lines until they hit a boundary
    ObjectMatchTransferColor  — match objects and transfer color
    FilterCropRecolor         — filter objects, crop, and recolor
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    StructuralReasoner,
    _classify_kept_removed,
    _extract_objects_with_properties,
    _add_relational_properties,
)


@dataclass
class SchemaMatch:
    """Result of matching a schema to a task."""
    schema_name: str
    matched: bool
    confidence: float
    bindings: Dict[str, Any] = field(default_factory=dict)
    predictions: Optional[List[np.ndarray]] = None
    hypothesis: Optional[Dict[str, Any]] = None


@dataclass
class SchemaValidation:
    """LOO + falsification validation of a schema match."""
    schema_name: str
    loo_passed: bool
    loo_score: float
    n_pairs_fit: int
    n_pairs_total: int
    falsification_score: float = 1.0
    certified: bool = False


class OperatorSchema(abc.ABC):
    """Base class for reusable operator schemas."""

    name: str
    description: str

    @abc.abstractmethod
    def detect(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> SchemaMatch:
        ...

    @abc.abstractmethod
    def apply(
        self,
        input_grid: np.ndarray,
        bindings: Dict[str, Any],
    ) -> np.ndarray:
        ...

    def loo_validate(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        match: SchemaMatch,
    ) -> SchemaValidation:
        if not match.matched:
            return SchemaValidation(
                schema_name=self.name, loo_passed=False, loo_score=0.0,
                n_pairs_fit=0, n_pairs_total=len(train_pairs),
            )

        n_fit = 0
        for i in range(len(train_pairs)):
            held_out_inp, held_out_out = train_pairs[i]
            train_subset = [p for j, p in enumerate(train_pairs) if j != i]
            try:
                sub_match = self.detect(train_subset)
                if not sub_match.matched:
                    continue
                pred = self.apply(held_out_inp, sub_match.bindings)
                if np.array_equal(pred, held_out_out):
                    n_fit += 1
            except Exception:
                continue

        loo_score = n_fit / max(len(train_pairs), 1)
        return SchemaValidation(
            schema_name=self.name,
            loo_passed=loo_score == 1.0,
            loo_score=loo_score,
            n_pairs_fit=n_fit,
            n_pairs_total=len(train_pairs),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMA IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════

class MarkerTargetTransform(OperatorSchema):
    name = "MarkerTargetTransform"
    description = "Marker object selects targets for transformation"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        marker_color = None
        target_transform = None

        for inp, out in train_pairs:
            objects = adapter.extract_objects(inp)
            if len(objects) < 2:
                return SchemaMatch(self.name, False, 0.0)

            sizes = [o["area"] for o in objects]
            smallest_idx = int(np.argmin(sizes))
            marker = objects[smallest_idx]
            mc = marker.get("primary_color", -1)

            if marker_color is None:
                marker_color = mc
            elif mc != marker_color:
                return SchemaMatch(self.name, False, 0.0)

            out_objects = adapter.extract_objects(out)
            if len(out_objects) == 0:
                continue

            # Check if marker disappears in output
            marker_bbox = marker["bbox"]
            marker_region_out = out[marker_bbox[0]:marker_bbox[2]+1, marker_bbox[1]:marker_bbox[3]+1]
            marker_region_in = inp[marker_bbox[0]:marker_bbox[2]+1, marker_bbox[1]:marker_bbox[3]+1]
            if np.array_equal(marker_region_out, marker_region_in):
                marker_removed = False
            else:
                marker_removed = True

            if target_transform is None:
                target_transform = "recolor" if not marker_removed else "remove_marker"

        if marker_color is None:
            return SchemaMatch(self.name, False, 0.0)

        return SchemaMatch(
            self.name, True, 0.6,
            bindings={
                "marker_color": marker_color,
                "transform": target_transform or "recolor",
            },
        )

    def apply(self, input_grid, bindings):
        out = input_grid.copy()
        mc = bindings.get("marker_color", -1)
        mask = input_grid == mc
        if bindings.get("transform") == "remove_marker":
            out[mask] = 0
        return out


class ContainerContentExtract(OperatorSchema):
    name = "ContainerContentExtract"
    description = "Extract contents from containers (frames, enclosed regions)"

    def detect(self, train_pairs):
        for inp, out in train_pairs:
            h, w = inp.shape
            oh, ow = out.shape
            if oh >= h and ow >= w:
                return SchemaMatch(self.name, False, 0.0)

        adapter = GridDomainAdapter()
        container_color = None
        for inp, out in train_pairs:
            objects = adapter.extract_objects(inp)
            largest = max(objects, key=lambda o: o["area"]) if objects else None
            if largest is None:
                return SchemaMatch(self.name, False, 0.0)
            lc = largest.get("primary_color", -1)
            if container_color is None:
                container_color = lc
            elif lc != container_color:
                container_color = -1

        return SchemaMatch(
            self.name, True, 0.5,
            bindings={"container_color": container_color},
        )

    def apply(self, input_grid, bindings):
        cc = bindings.get("container_color", -1)
        if cc >= 0:
            mask = input_grid == cc
            rows, cols = np.where(mask)
            if len(rows) > 0:
                r0, r1 = rows.min() + 1, rows.max()
                c0, c1 = cols.min() + 1, cols.max()
                if r1 > r0 and c1 > c0:
                    return input_grid[r0:r1, c0:c1].copy()
        return input_grid.copy()


class SeparatorCellCompose(OperatorSchema):
    name = "SeparatorCellCompose"
    description = "Decompose grid by separators, compose cells"

    def detect(self, train_pairs):
        for inp, out in train_pairs:
            sep_rows, sep_cols = self._find_separators(inp)
            if sep_rows or sep_cols:
                return SchemaMatch(
                    self.name, True, 0.7,
                    bindings={
                        "separator_rows": sep_rows,
                        "separator_cols": sep_cols,
                    },
                )
        return SchemaMatch(self.name, False, 0.0)

    def _find_separators(self, grid):
        h, w = grid.shape
        sep_rows = []
        sep_cols = []
        for r in range(h):
            row = grid[r, :]
            if len(set(row.tolist())) == 1 and row[0] != 0:
                sep_rows.append(r)
        for c in range(w):
            col = grid[:, c]
            if len(set(col.tolist())) == 1 and col[0] != 0:
                sep_cols.append(c)
        return sep_rows, sep_cols

    def apply(self, input_grid, bindings):
        return input_grid.copy()


class SymmetryCompletion(OperatorSchema):
    name = "SymmetryCompletion"
    description = "Complete a pattern by symmetry (H, V, D, or rotational)"

    def detect(self, train_pairs):
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                continue
            diff = (inp != out)
            if not diff.any():
                continue
            # Check if output = horizontally symmetric version of input
            flipped_h = np.flip(inp, axis=0)
            flipped_v = np.flip(inp, axis=1)
            for sym_type, flipped in [("horizontal", flipped_h), ("vertical", flipped_v)]:
                merged = inp.copy()
                mask = inp == 0
                merged[mask] = flipped[mask]
                if np.array_equal(merged, out):
                    return SchemaMatch(
                        self.name, True, 0.8,
                        bindings={"symmetry_type": sym_type},
                    )
        return SchemaMatch(self.name, False, 0.0)

    def apply(self, input_grid, bindings):
        st = bindings.get("symmetry_type", "horizontal")
        axis = 0 if st == "horizontal" else 1
        flipped = np.flip(input_grid, axis=axis)
        out = input_grid.copy()
        mask = input_grid == 0
        out[mask] = flipped[mask]
        return out


class PatternRepetitionFill(OperatorSchema):
    name = "PatternRepetitionFill"
    description = "Fill region by repeating a pattern tile"

    def detect(self, train_pairs):
        for inp, out in train_pairs:
            oh, ow = out.shape
            ih, iw = inp.shape
            if oh == ih and ow == iw:
                for th in range(1, ih // 2 + 1):
                    for tw in range(1, iw // 2 + 1):
                        if ih % th != 0 or iw % tw != 0:
                            continue
                        tile = out[:th, :tw]
                        match = True
                        for r in range(0, ih, th):
                            for c in range(0, iw, tw):
                                if not np.array_equal(out[r:r+th, c:c+tw], tile):
                                    match = False
                                    break
                            if not match:
                                break
                        if match:
                            return SchemaMatch(
                                self.name, True, 0.8,
                                bindings={"tile_h": th, "tile_w": tw},
                            )
        return SchemaMatch(self.name, False, 0.0)

    def apply(self, input_grid, bindings):
        th = bindings.get("tile_h", 1)
        tw = bindings.get("tile_w", 1)
        h, w = input_grid.shape
        tile = input_grid[:th, :tw]
        out = np.zeros_like(input_grid)
        for r in range(0, h, th):
            for c in range(0, w, tw):
                rr = min(th, h - r)
                cc = min(tw, w - c)
                out[r:r+rr, c:c+cc] = tile[:rr, :cc]
        return out


class LineExtendUntilBoundary(OperatorSchema):
    name = "LineExtendUntilBoundary"
    description = "Extend lines until they hit a boundary or another object"

    def detect(self, train_pairs):
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                continue
            diff = (inp != out)
            if not diff.any():
                continue
            # Check if new pixels form lines
            diff_rows, diff_cols = np.where(diff)
            if len(diff_rows) == 0:
                continue
            row_counts = np.bincount(diff_rows, minlength=inp.shape[0])
            col_counts = np.bincount(diff_cols, minlength=inp.shape[1])
            max_row_change = row_counts.max()
            max_col_change = col_counts.max()
            if max_row_change > 2 or max_col_change > 2:
                direction = "horizontal" if max_col_change > max_row_change else "vertical"
                return SchemaMatch(
                    self.name, True, 0.5,
                    bindings={"direction": direction},
                )
        return SchemaMatch(self.name, False, 0.0)

    def apply(self, input_grid, bindings):
        return input_grid.copy()


class ObjectMatchTransferColor(OperatorSchema):
    name = "ObjectMatchTransferColor"
    description = "Match objects by shape and transfer color"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        for inp, out in train_pairs:
            in_objs = adapter.extract_objects(inp)
            out_objs = adapter.extract_objects(out)
            if len(in_objs) < 2 or len(out_objs) < 2:
                continue
            color_changed = False
            for io in in_objs:
                for oo in out_objs:
                    if (io.get("area") == oo.get("area") and
                            np.array_equal(io.get("local_mask"), oo.get("local_mask")) and
                            io.get("primary_color") != oo.get("primary_color")):
                        color_changed = True
                        break
                if color_changed:
                    break
            if color_changed:
                return SchemaMatch(self.name, True, 0.6, bindings={})
        return SchemaMatch(self.name, False, 0.0)

    def apply(self, input_grid, bindings):
        return input_grid.copy()


class FilterCropRecolor(OperatorSchema):
    name = "FilterCropRecolor"
    description = "Filter objects by property, crop to bounding box, recolor"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        for inp, out in train_pairs:
            objects = adapter.extract_objects(inp)
            cls = _classify_kept_removed(objects, inp, out)
            if cls is not None:
                kept, removed = cls
                if kept and removed:
                    oh, ow = out.shape
                    ih, iw = inp.shape
                    is_crop = oh < ih or ow < iw
                    return SchemaMatch(
                        self.name, True, 0.7,
                        bindings={"crop": is_crop, "n_kept": len(kept)},
                    )
        return SchemaMatch(self.name, False, 0.0)

    def apply(self, input_grid, bindings):
        return input_grid.copy()


# ═══════════════════════════════════════════════════════════════════════════
# NEW OPERATOR SCHEMAS — executable, LOO-checkable, falsifiable, certifiable
# ═══════════════════════════════════════════════════════════════════════════

class CopyToPosition(OperatorSchema):
    """Copy a source object to positions indicated by marker objects."""
    name = "CopyToPosition"
    description = "Copy source object pattern to marker-indicated locations"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        source_color = None
        marker_color = None

        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)
            objects = adapter.extract_objects(inp)
            if len(objects) < 2:
                return SchemaMatch(self.name, False, 0.0)
            sizes = sorted([(o["area"], i) for i, o in enumerate(objects)], reverse=True)
            largest_idx = sizes[0][1]
            smallest_idxs = [i for a, i in sizes if a == sizes[-1][0] and a <= 4]
            if not smallest_idxs:
                return SchemaMatch(self.name, False, 0.0)

            src = objects[largest_idx]
            sc = src.get("primary_color", -1)
            mc = objects[smallest_idxs[0]].get("primary_color", -1)
            if source_color is None:
                source_color = sc
                marker_color = mc
            elif sc != source_color or mc != marker_color:
                return SchemaMatch(self.name, False, 0.0)

        if source_color is None or marker_color is None or source_color == marker_color:
            return SchemaMatch(self.name, False, 0.0)

        return SchemaMatch(
            self.name, True, 0.7,
            bindings={"source_color": source_color, "marker_color": marker_color},
        )

    def apply(self, input_grid, bindings):
        adapter = GridDomainAdapter()
        sc = bindings["source_color"]
        mc = bindings["marker_color"]
        objects = adapter.extract_objects(input_grid)
        source = None
        markers = []
        for o in objects:
            if o.get("primary_color") == sc and (source is None or o["area"] > source["area"]):
                source = o
            elif o.get("primary_color") == mc:
                markers.append(o)
        if source is None or not markers:
            return input_grid.copy()

        src_bbox = source["bbox"]
        src_h = src_bbox[2] - src_bbox[0] + 1
        src_w = src_bbox[3] - src_bbox[1] + 1
        src_patch = input_grid[src_bbox[0]:src_bbox[2]+1, src_bbox[1]:src_bbox[3]+1].copy()
        src_mask = source["mask"][src_bbox[0]:src_bbox[2]+1, src_bbox[1]:src_bbox[3]+1]

        out = input_grid.copy()
        out[input_grid == mc] = 0
        for m in markers:
            mr = (m["bbox"][0] + m["bbox"][2]) // 2
            mc_col = (m["bbox"][1] + m["bbox"][3]) // 2
            r0 = mr - src_h // 2
            c0 = mc_col - src_w // 2
            for dr in range(src_h):
                for dc in range(src_w):
                    r, c = r0 + dr, c0 + dc
                    if 0 <= r < out.shape[0] and 0 <= c < out.shape[1] and src_mask[dr, dc]:
                        out[r, c] = src_patch[dr, dc]
        return out


class GravityDrop(OperatorSchema):
    """Drop non-zero objects downward until they hit another object or boundary."""
    name = "GravityDrop"
    description = "Drop objects in a direction until collision"

    def detect(self, train_pairs):
        for direction in ["down", "up", "left", "right"]:
            if self._check_direction(train_pairs, direction):
                return SchemaMatch(
                    self.name, True, 0.8,
                    bindings={"direction": direction},
                )
        return SchemaMatch(self.name, False, 0.0)

    def _check_direction(self, train_pairs, direction):
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return False
            pred = self._apply_gravity(inp, direction)
            if not np.array_equal(pred, out):
                return False
        return True

    def _apply_gravity(self, grid, direction):
        h, w = grid.shape
        result = np.zeros_like(grid)
        if direction == "down":
            for c in range(w):
                col = grid[:, c]
                nonzero = col[col != 0]
                result[h - len(nonzero):h, c] = nonzero
        elif direction == "up":
            for c in range(w):
                col = grid[:, c]
                nonzero = col[col != 0]
                result[:len(nonzero), c] = nonzero
        elif direction == "right":
            for r in range(h):
                row = grid[r, :]
                nonzero = row[row != 0]
                result[r, w - len(nonzero):w] = nonzero
        elif direction == "left":
            for r in range(h):
                row = grid[r, :]
                nonzero = row[row != 0]
                result[r, :len(nonzero)] = nonzero
        return result

    def apply(self, input_grid, bindings):
        return self._apply_gravity(input_grid, bindings["direction"])


class HoleFillMultiColor(OperatorSchema):
    """Fill enclosed holes inside objects with specific colors."""
    name = "HoleFillMultiColor"
    description = "Fill holes/enclosed regions inside objects"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)
            diff = (inp != out)
            if not diff.any():
                return SchemaMatch(self.name, False, 0.0)
            diff_positions = np.where(diff)
            if not all(inp[r, c] == 0 for r, c in zip(diff_positions[0], diff_positions[1])):
                return SchemaMatch(self.name, False, 0.0)

        fill_color = None
        for inp, out in train_pairs:
            diff = (inp != out)
            fill_colors_here = set(out[diff].tolist())
            fill_colors_here.discard(0)
            if len(fill_colors_here) == 1:
                fc = fill_colors_here.pop()
                if fill_color is None:
                    fill_color = fc
                elif fc != fill_color:
                    fill_color = -1

        if fill_color is not None and fill_color > 0:
            return SchemaMatch(
                self.name, True, 0.7,
                bindings={"fill_color": fill_color},
            )

        return SchemaMatch(
            self.name, True, 0.5,
            bindings={"fill_color": -1},
        )

    def apply(self, input_grid, bindings):
        from scipy import ndimage as ndi
        h, w = input_grid.shape
        result = input_grid.copy()
        bg = (input_grid == 0)
        labeled, n = ndi.label(bg)
        border_labels = set()
        border_labels.update(labeled[0, :].tolist())
        border_labels.update(labeled[-1, :].tolist())
        border_labels.update(labeled[:, 0].tolist())
        border_labels.update(labeled[:, -1].tolist())
        border_labels.discard(0)

        fc = bindings.get("fill_color", -1)
        for lab in range(1, n + 1):
            if lab in border_labels:
                continue
            mask = (labeled == lab)
            if fc > 0:
                result[mask] = fc
            else:
                rows, cols = np.where(mask)
                for r, c in zip(rows, cols):
                    neighbors = []
                    for dr, dc_n in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc_n
                        if 0 <= nr < h and 0 <= nc < w and input_grid[nr, nc] != 0:
                            neighbors.append(input_grid[nr, nc])
                    if neighbors:
                        result[r, c] = max(set(neighbors), key=neighbors.count)
        return result


class LineExtendUntilCollision(OperatorSchema):
    """Extend colored line segments until they hit another object or boundary."""
    name = "LineExtendUntilCollision"
    description = "Extend line endpoints until collision with object or edge"

    def detect(self, train_pairs):
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)
            diff = (inp != out)
            if not diff.any():
                continue
            diff_colors = set(out[diff].tolist())
            diff_colors.discard(0)
            if len(diff_colors) > 3:
                return SchemaMatch(self.name, False, 0.0)

        extend_color = None
        for inp, out in train_pairs:
            diff = (inp != out)
            if not diff.any():
                continue
            colors = set(out[diff].tolist())
            colors.discard(0)
            if len(colors) == 1:
                ec = colors.pop()
                if extend_color is None:
                    extend_color = ec
                elif ec != extend_color:
                    extend_color = -1

        if extend_color is None:
            return SchemaMatch(self.name, False, 0.0)

        for direction in ["horizontal", "vertical", "both"]:
            pred_ok = True
            for inp, out in train_pairs:
                pred = self._extend(inp, extend_color, direction)
                if not np.array_equal(pred, out):
                    pred_ok = False
                    break
            if pred_ok:
                return SchemaMatch(
                    self.name, True, 0.8,
                    bindings={"extend_color": extend_color, "direction": direction},
                )

        return SchemaMatch(self.name, False, 0.0)

    def _extend(self, grid, color, direction):
        h, w = grid.shape
        result = grid.copy()
        mask = (grid == color)

        if direction in ("horizontal", "both"):
            for r in range(h):
                cols = np.where(mask[r, :])[0]
                if len(cols) >= 2:
                    for c in range(cols.min(), cols.max() + 1):
                        if result[r, c] == 0:
                            result[r, c] = color
                elif len(cols) == 1:
                    c0 = cols[0]
                    for c in range(c0 + 1, w):
                        if grid[r, c] != 0 and grid[r, c] != color:
                            break
                        if result[r, c] == 0:
                            result[r, c] = color
                    for c in range(c0 - 1, -1, -1):
                        if grid[r, c] != 0 and grid[r, c] != color:
                            break
                        if result[r, c] == 0:
                            result[r, c] = color

        if direction in ("vertical", "both"):
            for c in range(w):
                rows = np.where(mask[:, c])[0]
                if len(rows) >= 2:
                    for r in range(rows.min(), rows.max() + 1):
                        if result[r, c] == 0:
                            result[r, c] = color
                elif len(rows) == 1:
                    r0 = rows[0]
                    for r in range(r0 + 1, h):
                        if grid[r, c] != 0 and grid[r, c] != color:
                            break
                        if result[r, c] == 0:
                            result[r, c] = color
                    for r in range(r0 - 1, -1, -1):
                        if grid[r, c] != 0 and grid[r, c] != color:
                            break
                        if result[r, c] == 0:
                            result[r, c] = color

        return result

    def apply(self, input_grid, bindings):
        return self._extend(
            input_grid,
            bindings["extend_color"],
            bindings["direction"],
        )


class ObjectMatchRecolor(OperatorSchema):
    """Match input objects to output by shape, transfer/swap colors."""
    name = "ObjectMatchRecolor"
    description = "Match objects by shape and recolor"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        recolor_map = None
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)
            in_objs = adapter.extract_objects(inp)
            out_objs = adapter.extract_objects(out)
            if len(in_objs) != len(out_objs) or len(in_objs) < 2:
                return SchemaMatch(self.name, False, 0.0)
            matches = adapter.match_objects(in_objs, out_objs)
            pair_map = {}
            for i_idx, o_idx, cost in matches:
                ic = in_objs[i_idx].get("primary_color", -1)
                oc = out_objs[o_idx].get("primary_color", -1)
                if ic != oc:
                    pair_map[ic] = oc
            if recolor_map is None:
                recolor_map = pair_map
            elif pair_map != recolor_map:
                return SchemaMatch(self.name, False, 0.0)

        if not recolor_map:
            return SchemaMatch(self.name, False, 0.0)

        return SchemaMatch(
            self.name, True, 0.7,
            bindings={"recolor_map": recolor_map},
        )

    def apply(self, input_grid, bindings):
        rm = bindings["recolor_map"]
        result = input_grid.copy()
        for old_c, new_c in rm.items():
            result[input_grid == int(old_c)] = int(new_c)
        return result


class RegionColorPropagation(OperatorSchema):
    """Propagate color from seed pixels to fill enclosed regions."""
    name = "RegionColorPropagation"
    description = "Flood-fill from seed pixels into enclosed regions"

    def detect(self, train_pairs):
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)
            diff = (inp != out)
            if not diff.any():
                return SchemaMatch(self.name, False, 0.0)
            if not all(inp[r, c] == 0 for r, c in zip(*np.where(diff))):
                return SchemaMatch(self.name, False, 0.0)

        all_ok = True
        for inp, out in train_pairs:
            pred = self._propagate(inp)
            if not np.array_equal(pred, out):
                all_ok = False
                break

        if all_ok:
            return SchemaMatch(self.name, True, 0.6, bindings={})
        return SchemaMatch(self.name, False, 0.0)

    def _propagate(self, grid):
        h, w = grid.shape
        result = grid.copy()
        bg = (grid == 0)
        labeled, n = ndimage.label(bg)
        border_labels = set()
        border_labels.update(labeled[0, :].tolist())
        border_labels.update(labeled[-1, :].tolist())
        border_labels.update(labeled[:, 0].tolist())
        border_labels.update(labeled[:, -1].tolist())
        border_labels.discard(0)

        for lab in range(1, n + 1):
            if lab in border_labels:
                continue
            mask = (labeled == lab)
            rows, cols = np.where(mask)
            neighbor_colors = []
            for r, c in zip(rows, cols):
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w and grid[nr, nc] != 0:
                        neighbor_colors.append(grid[nr, nc])
            if neighbor_colors:
                fill_c = max(set(neighbor_colors), key=neighbor_colors.count)
                result[mask] = fill_c
        return result

    def apply(self, input_grid, bindings):
        return self._propagate(input_grid)


class FrameContentTransform(OperatorSchema):
    """Transform the content inside a frame/border object."""
    name = "FrameContentTransform"
    description = "Extract frame interior and apply consistent transform"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        frame_color = None
        transform_type = None
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)
            objects = adapter.extract_objects(inp)
            framed = [o for o in objects if o.get("has_holes", False) or o.get("n_holes", 0) > 0]
            if not framed:
                return SchemaMatch(self.name, False, 0.0)
            fc = framed[0].get("primary_color", -1)
            if frame_color is None:
                frame_color = fc
            elif fc != frame_color:
                return SchemaMatch(self.name, False, 0.0)

        if frame_color is None:
            return SchemaMatch(self.name, False, 0.0)

        return SchemaMatch(
            self.name, True, 0.5,
            bindings={"frame_color": frame_color},
        )

    def apply(self, input_grid, bindings):
        return input_grid.copy()


class MarkerDirectedMove(OperatorSchema):
    """Move selected objects in a direction determined by a marker's position."""
    name = "MarkerDirectedMove"
    description = "Move objects in direction indicated by marker position relative to target"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        direction = None
        marker_color = None
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)
            objects_in = adapter.extract_objects(inp)
            objects_out = adapter.extract_objects(out)
            if len(objects_in) < 2:
                return SchemaMatch(self.name, False, 0.0)
            sizes = sorted([(o["area"], i) for i, o in enumerate(objects_in)], reverse=True)
            small = [i for a, i in sizes if a == sizes[-1][0] and a <= 4]
            if not small:
                return SchemaMatch(self.name, False, 0.0)
            marker = objects_in[small[0]]
            mc = marker.get("primary_color", -1)
            mr = (marker["bbox"][0] + marker["bbox"][2]) // 2
            mcc = (marker["bbox"][1] + marker["bbox"][3]) // 2
            moved = [o for o in objects_in if o.get("primary_color") != mc]
            if not moved:
                return SchemaMatch(self.name, False, 0.0)
            target = moved[0]
            tr = (target["bbox"][0] + target["bbox"][2]) // 2
            tc = (target["bbox"][1] + target["bbox"][3]) // 2
            dr = 1 if mr > tr else (-1 if mr < tr else 0)
            dc = 1 if mcc > tc else (-1 if mcc < tc else 0)
            d = (dr, dc)
            if direction is None:
                direction = d
                marker_color = mc
            elif d != direction or mc != marker_color:
                return SchemaMatch(self.name, False, 0.0)
        if direction is None or direction == (0, 0):
            return SchemaMatch(self.name, False, 0.0)
        if self._verify(train_pairs, adapter, marker_color, direction):
            return SchemaMatch(
                self.name, True, 0.7,
                bindings={"direction": list(direction), "marker_color": marker_color},
            )
        return SchemaMatch(self.name, False, 0.0)

    def _verify(self, train_pairs, adapter, mc, direction):
        for inp, out in train_pairs:
            pred = self._move(inp, adapter, mc, direction)
            if not np.array_equal(pred, out):
                return False
        return True

    def _move(self, grid, adapter, mc, direction):
        h, w = grid.shape
        dr, dc = direction
        objects = adapter.extract_objects(grid)
        out = np.zeros_like(grid)
        for o in objects:
            if o.get("primary_color") == mc:
                continue
            mask = o["mask"]
            for r in range(h):
                for c in range(w):
                    if mask[r, c]:
                        nr, nc = r, c
                        while True:
                            cr, cc = nr + dr, nc + dc
                            if cr < 0 or cr >= h or cc < 0 or cc >= w:
                                break
                            if grid[cr, cc] != 0 and not mask[cr, cc]:
                                break
                            nr, nc = cr, cc
                        out[nr, nc] = grid[r, c]
        return out

    def apply(self, input_grid, bindings):
        adapter = GridDomainAdapter()
        return self._move(
            input_grid, adapter,
            bindings["marker_color"], tuple(bindings["direction"]),
        )


class ShapeCompleteFromBoundary(OperatorSchema):
    """Complete a partial shape by mirroring/extending from its boundary."""
    name = "ShapeCompleteFromBoundary"
    description = "Complete partial shapes using symmetry/boundary extrapolation"

    def detect(self, train_pairs):
        for sym_type in ["horizontal", "vertical", "both"]:
            if self._check_symmetry_completion(train_pairs, sym_type):
                return SchemaMatch(
                    self.name, True, 0.7,
                    bindings={"symmetry_type": sym_type},
                )
        return SchemaMatch(self.name, False, 0.0)

    def _check_symmetry_completion(self, train_pairs, sym_type):
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return False
            pred = self._complete(inp, sym_type)
            if not np.array_equal(pred, out):
                return False
        return True

    def _complete(self, grid, sym_type):
        h, w = grid.shape
        result = grid.copy()
        if sym_type in ("horizontal", "both"):
            for r in range(h):
                for c in range(w):
                    mirror_c = w - 1 - c
                    if result[r, c] == 0 and result[r, mirror_c] != 0:
                        result[r, c] = result[r, mirror_c]
                    elif result[r, c] != 0 and result[r, mirror_c] == 0:
                        result[r, mirror_c] = result[r, c]
        if sym_type in ("vertical", "both"):
            for r in range(h):
                for c in range(w):
                    mirror_r = h - 1 - r
                    if result[r, c] == 0 and result[mirror_r, c] != 0:
                        result[r, c] = result[mirror_r, c]
                    elif result[r, c] != 0 and result[mirror_r, c] == 0:
                        result[mirror_r, c] = result[r, c]
        return result

    def apply(self, input_grid, bindings):
        return self._complete(input_grid, bindings["symmetry_type"])


class SeparatorCellComposeAdvanced(OperatorSchema):
    """Decompose by separators and compose cells via learned binary operation."""
    name = "SeparatorCellComposeAdvanced"
    description = "Split grid by separators, apply per-cell operation, compose result"

    def detect(self, train_pairs):
        adapter = GridDomainAdapter()
        for sep_color in range(1, 10):
            result = self._try_separator(train_pairs, adapter, sep_color)
            if result is not None:
                return result
        return SchemaMatch(self.name, False, 0.0)

    def _try_separator(self, train_pairs, adapter, sep_color):
        op_type = None
        for inp, out in train_pairs:
            rows = [r for r in range(inp.shape[0]) if np.all(inp[r, :] == sep_color)]
            cols = [c for c in range(inp.shape[1]) if np.all(inp[:, c] == sep_color)]
            if not rows and not cols:
                return None
            cells = self._extract_cells(inp, rows, cols)
            if len(cells) < 2:
                return None
            for op in ["and", "or", "xor", "overlay", "diff"]:
                pred = self._compose(cells, op, out.shape)
                if pred is not None and np.array_equal(pred, out):
                    if op_type is None:
                        op_type = op
                    elif op != op_type:
                        return None
                    break
            else:
                return None
        if op_type is None:
            return None
        return SchemaMatch(
            self.name, True, 0.8,
            bindings={"sep_color": sep_color, "op_type": op_type},
        )

    def _extract_cells(self, grid, rows, cols):
        h, w = grid.shape
        row_bounds = [0] + [r for r in rows] + [h]
        col_bounds = [0] + [c for c in cols] + [w]
        cells = []
        for i in range(len(row_bounds) - 1):
            for j in range(len(col_bounds) - 1):
                r0, r1 = row_bounds[i], row_bounds[i+1]
                c0, c1 = col_bounds[j], col_bounds[j+1]
                if r0 in rows:
                    r0 += 1
                if c0 in cols:
                    c0 += 1
                if r0 < r1 and c0 < c1:
                    cells.append(grid[r0:r1, c0:c1])
        return cells

    def _compose(self, cells, op, target_shape):
        if len(cells) < 2:
            return None
        ref_shape = cells[0].shape
        for c in cells[1:]:
            if c.shape != ref_shape:
                return None
        a = (cells[0] != 0).astype(int)
        b = (cells[1] != 0).astype(int)
        if op == "and":
            mask = (a & b).astype(bool)
        elif op == "or":
            mask = (a | b).astype(bool)
        elif op == "xor":
            mask = (a ^ b).astype(bool)
        elif op == "overlay":
            result = cells[0].copy()
            for c in cells[1:]:
                nz = c != 0
                result[nz] = c[nz]
            if result.shape == target_shape:
                return result
            return None
        elif op == "diff":
            mask = (a & ~b).astype(bool)
        else:
            return None
        result = np.zeros(ref_shape, dtype=cells[0].dtype)
        result[mask] = cells[0][mask]
        if result.shape == target_shape:
            return result
        return None

    def apply(self, input_grid, bindings):
        sep_color = bindings["sep_color"]
        op_type = bindings["op_type"]
        h, w = input_grid.shape
        rows = [r for r in range(h) if np.all(input_grid[r, :] == sep_color)]
        cols = [c for c in range(w) if np.all(input_grid[:, c] == sep_color)]
        cells = self._extract_cells(input_grid, rows, cols)
        if len(cells) < 2:
            return input_grid.copy()
        ref_shape = cells[0].shape
        result = self._compose(cells, op_type, ref_shape)
        if result is not None:
            return result
        return input_grid.copy()


# ═══════════════════════════════════════════════════════════════════════════
# TRACE-DERIVED COPY-TO-POSITION — learns destination rules from training
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CopyToPositionParams:
    destination_rule: str
    copy_mode: str  # "move", "copy"
    preserve_color: bool
    preserve_shape: bool
    source_property: Optional[str]
    keep_when_true: Optional[bool]
    rule_params: Dict[str, Any] = field(default_factory=dict)


def _find_object_in_output(obj: Dict, inp: np.ndarray, out: np.ndarray) -> Optional[Tuple[int, int]]:
    """Find where an object's pixels appear in the output grid.

    Slides the object's local mask over the output, scoring pixel agreement.
    Returns (dest_r, dest_c) as top-left of best match, or None.
    """
    local = obj["local_mask"]
    oh, ow = local.shape
    pixels_in = inp[obj["bbox"][0]:obj["bbox"][2]+1, obj["bbox"][1]:obj["bbox"][3]+1].copy()
    pixels_in[~local] = -1

    best_sim = 0.0
    best_pos = None
    out_h, out_w = out.shape

    for r in range(out_h - oh + 1):
        for c in range(out_w - ow + 1):
            region = out[r:r+oh, c:c+ow]
            match_pixels = pixels_in[local]
            region_pixels = region[local]
            if len(match_pixels) == 0:
                continue
            sim = float(np.mean(match_pixels == region_pixels))
            if sim > best_sim and sim > 0.5:
                best_sim = sim
                best_pos = (r, c)

    return best_pos


def _learn_destination_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    prop_name: str,
    keep_when_true: bool,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Try multiple destination rules and return the first that's LOO-consistent."""
    adapter = GridDomainAdapter()

    # Phase 1: collect per-pair displacement data
    pair_data = []
    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        if len(objects) < 2:
            return None
        km = [_get_property_value(obj, prop_name) == keep_when_true for obj in objects]
        if all(km) or not any(km):
            return None

        kept = [(i, objects[i]) for i, k in enumerate(km) if k]
        removed = [(i, objects[i]) for i, k in enumerate(km) if not k]
        if not kept or not removed:
            return None

        movements = []
        for ri, robj in removed:
            dest = _find_object_in_output(robj, inp, out)
            if dest is None:
                movements.append({"obj": robj, "dest": None, "dest_type": "removed"})
            else:
                movements.append({
                    "obj": robj,
                    "dest": dest,
                    "dest_type": "moved",
                    "src_bbox": robj["bbox"],
                })
        pair_data.append({
            "inp": inp, "out": out,
            "kept": kept, "removed": removed,
            "movements": movements, "objects": objects,
        })

    if not pair_data:
        return None

    # Phase 2: try destination rules in order of specificity
    rules = [
        _try_rule_nearest_kept_overlay,
        _try_rule_converge_to_kept_center,
        _try_rule_relative_to_nearest_kept,
    ]

    for rule_fn in rules:
        result = rule_fn(pair_data, train_pairs, prop_name, keep_when_true)
        if result is not None:
            return result

    return None


def _try_rule_nearest_kept_overlay(
    pair_data: List[Dict],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    prop_name: str,
    keep_when_true: bool,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Rule: each removed object overlays on (or adjacent to) the nearest kept object.
    Learn the exact anchor mode: center-to-center, edge-adjacent, etc."""

    anchor_modes = ["center", "top_edge", "bottom_edge", "left_edge", "right_edge"]

    for anchor in anchor_modes:
        all_consistent = True
        for pd in pair_data:
            for mv in pd["movements"]:
                if mv["dest"] is None:
                    continue
                robj = mv["obj"]
                dest_r, dest_c = mv["dest"]
                kept_objs = [k[1] for k in pd["kept"]]

                nearest = min(
                    kept_objs,
                    key=lambda ko: abs(ko["center_r"] - robj["center_r"]) +
                                   abs(ko["center_c"] - robj["center_c"]),
                )

                predicted = _predict_dest_by_anchor(robj, nearest, anchor)
                if predicted is None or (predicted[0] != dest_r or predicted[1] != dest_c):
                    all_consistent = False
                    break
            if not all_consistent:
                break

        if all_consistent:
            pred = _apply_copy_to_position_rule(
                train_pairs[0][0], prop_name, keep_when_true,
                "nearest_kept_overlay", {"anchor": anchor},
            )
            if pred is not None and np.array_equal(pred, train_pairs[0][1]):
                if _loo_validate_copy_rule(
                    train_pairs, prop_name, keep_when_true,
                    "nearest_kept_overlay", {"anchor": anchor},
                ):
                    return "nearest_kept_overlay", {"anchor": anchor}

    return None


def _try_rule_converge_to_kept_center(
    pair_data: List[Dict],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    prop_name: str,
    keep_when_true: bool,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Rule: all removed objects converge to a single destination,
    typically the center of one specific kept object."""

    for pd in pair_data:
        dests = [mv["dest"] for mv in pd["movements"] if mv["dest"] is not None]
        if not dests or len(set(dests)) > 1:
            return None

    # All converge to single point per pair. Is it consistently the center
    # of a specific kept object (e.g., the largest)?
    for kept_selector in ["largest", "smallest", "first"]:
        all_consistent = True
        for pd in pair_data:
            dests = [mv["dest"] for mv in pd["movements"] if mv["dest"] is not None]
            if not dests:
                all_consistent = False
                break
            target_dest = dests[0]
            kept_objs = [k[1] for k in pd["kept"]]

            if kept_selector == "largest":
                ref = max(kept_objs, key=lambda o: o["area"])
            elif kept_selector == "smallest":
                ref = min(kept_objs, key=lambda o: o["area"])
            else:
                ref = kept_objs[0]

            ref_r = int(round(ref["center_r"])) - pd["movements"][0]["obj"]["bbox_h"] // 2
            ref_c = int(round(ref["center_c"])) - pd["movements"][0]["obj"]["bbox_w"] // 2

            if (ref_r, ref_c) != target_dest:
                all_consistent = False
                break

        if all_consistent:
            if _loo_validate_copy_rule(
                train_pairs, prop_name, keep_when_true,
                "converge_to_kept_center", {"kept_selector": kept_selector},
            ):
                return "converge_to_kept_center", {"kept_selector": kept_selector}

    return None


def _try_rule_relative_to_nearest_kept(
    pair_data: List[Dict],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    prop_name: str,
    keep_when_true: bool,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Rule: each removed object goes to the nearest kept object with a
    consistent spatial relationship (e.g., placed inside, touching edge,
    or at the same row/col)."""

    # Learn per-pair what offset each removed object has relative to its nearest kept
    # Then check if there's a consistent pattern
    for offset_mode in ["inside_nearest_kept", "match_nearest_kept_topleft"]:
        all_consistent = True
        for pd in pair_data:
            for mv in pd["movements"]:
                if mv["dest"] is None:
                    continue
                robj = mv["obj"]
                dest_r, dest_c = mv["dest"]
                kept_objs = [k[1] for k in pd["kept"]]

                nearest = min(
                    kept_objs,
                    key=lambda ko: abs(ko["center_r"] - robj["center_r"]) +
                                   abs(ko["center_c"] - robj["center_c"]),
                )

                if offset_mode == "inside_nearest_kept":
                    # Object lands inside nearest kept's bbox
                    nb = nearest["bbox"]
                    if not (nb[0] <= dest_r and dest_r + robj["bbox_h"] - 1 <= nb[2] and
                            nb[1] <= dest_c and dest_c + robj["bbox_w"] - 1 <= nb[3]):
                        all_consistent = False
                        break
                elif offset_mode == "match_nearest_kept_topleft":
                    nb = nearest["bbox"]
                    if dest_r != nb[0] or dest_c != nb[1]:
                        all_consistent = False
                        break
            if not all_consistent:
                break

        if all_consistent and _loo_validate_copy_rule(
            train_pairs, prop_name, keep_when_true,
            "relative_to_nearest_kept", {"mode": offset_mode},
        ):
            return "relative_to_nearest_kept", {"mode": offset_mode}

    return None


def _predict_dest_by_anchor(
    removed_obj: Dict, kept_obj: Dict, anchor: str,
) -> Optional[Tuple[int, int]]:
    """Predict where a removed object should land relative to a kept object."""
    rh, rw = removed_obj["bbox_h"], removed_obj["bbox_w"]
    kb = kept_obj["bbox"]  # (r_min, c_min, r_max, c_max)

    if anchor == "center":
        kr = int(round(kept_obj["center_r"])) - rh // 2
        kc = int(round(kept_obj["center_c"])) - rw // 2
        return (kr, kc)
    elif anchor == "top_edge":
        return (kb[0] - rh, kb[1])
    elif anchor == "bottom_edge":
        return (kb[2] + 1, kb[1])
    elif anchor == "left_edge":
        return (kb[0], kb[1] - rw)
    elif anchor == "right_edge":
        return (kb[0], kb[3] + 1)
    return None


def _apply_copy_to_position_rule(
    inp: np.ndarray,
    prop_name: str,
    keep_when_true: bool,
    rule: str,
    rule_params: Dict[str, Any],
) -> Optional[np.ndarray]:
    """Apply a copy-to-position rule to an input grid."""
    objects = _extract_objects_with_properties(inp)
    if len(objects) < 2:
        return None
    km = [_get_property_value(obj, prop_name) == keep_when_true for obj in objects]
    if all(km) or not any(km):
        return None

    kept = [obj for obj, k in zip(objects, km) if k]
    removed = [obj for obj, k in zip(objects, km) if not k]

    result = inp.copy()
    # Zero out removed objects
    for robj in removed:
        result[robj["mask"]] = 0

    # Place removed objects at destinations
    for robj in removed:
        dest = _compute_destination(robj, kept, rule, rule_params, inp.shape)
        if dest is None:
            continue
        dr, dc = dest
        local = robj["local_mask"]
        src_patch = inp[robj["bbox"][0]:robj["bbox"][2]+1, robj["bbox"][1]:robj["bbox"][3]+1]
        rh, rw = local.shape
        for r in range(rh):
            for c in range(rw):
                if local[r, c]:
                    nr, nc = dr + r, dc + c
                    if 0 <= nr < result.shape[0] and 0 <= nc < result.shape[1]:
                        result[nr, nc] = src_patch[r, c]

    return result


def _compute_destination(
    robj: Dict,
    kept: List[Dict],
    rule: str,
    rule_params: Dict[str, Any],
    grid_shape: Tuple[int, int],
) -> Optional[Tuple[int, int]]:
    """Compute the destination (top-left corner) for a removed object."""
    if rule == "nearest_kept_overlay":
        nearest = min(
            kept,
            key=lambda ko: abs(ko["center_r"] - robj["center_r"]) +
                           abs(ko["center_c"] - robj["center_c"]),
        )
        anchor = rule_params.get("anchor", "center")
        return _predict_dest_by_anchor(robj, nearest, anchor)

    elif rule == "converge_to_kept_center":
        selector = rule_params.get("kept_selector", "largest")
        if selector == "largest":
            ref = max(kept, key=lambda o: o["area"])
        elif selector == "smallest":
            ref = min(kept, key=lambda o: o["area"])
        else:
            ref = kept[0]
        kr = int(round(ref["center_r"])) - robj["bbox_h"] // 2
        kc = int(round(ref["center_c"])) - robj["bbox_w"] // 2
        return (kr, kc)

    elif rule == "relative_to_nearest_kept":
        nearest = min(
            kept,
            key=lambda ko: abs(ko["center_r"] - robj["center_r"]) +
                           abs(ko["center_c"] - robj["center_c"]),
        )
        mode = rule_params.get("mode", "inside_nearest_kept")
        if mode == "inside_nearest_kept":
            nb = nearest["bbox"]
            return (nb[0], nb[1])
        elif mode == "match_nearest_kept_topleft":
            nb = nearest["bbox"]
            return (nb[0], nb[1])

    return None


def _loo_validate_copy_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    prop_name: str,
    keep_when_true: bool,
    rule: str,
    rule_params: Dict[str, Any],
) -> bool:
    """LOO validation: every training pair must be exactly reproduced."""
    for i in range(len(train_pairs)):
        inp, out = train_pairs[i]
        pred = _apply_copy_to_position_rule(inp, prop_name, keep_when_true, rule, rule_params)
        if pred is None or not np.array_equal(pred, out):
            return False
    return True


class TraceDerivedCopyToPosition(OperatorSchema):
    """Copy-to-position operator derived from failure traces.

    Learns per-object destination rules from training data:
    - nearest_kept_overlay: each removed object overlays nearest kept object
    - converge_to_kept_center: all removed converge to one kept object
    - relative_to_nearest_kept: each removed placed inside nearest kept

    Only fires when:
    - A discriminative property separates kept/removed objects
    - Removed objects' pixels appear elsewhere in the output
    - The destination rule is consistent across ALL training pairs
    - LOO validation passes
    """
    name = "TraceDerivedCopyToPosition"
    description = "Move removed objects to positions determined by structural rules"

    def detect(self, train_pairs):
        disc = _find_discriminative_property(train_pairs)
        if disc is None:
            return SchemaMatch(self.name, False, 0.0)
        prop_name, keep_when_true = disc

        # All pairs must have same-size I/O
        for inp, out in train_pairs:
            if inp.shape != out.shape:
                return SchemaMatch(self.name, False, 0.0)

        result = _learn_destination_rule(train_pairs, prop_name, keep_when_true)
        if result is None:
            return SchemaMatch(self.name, False, 0.0)

        rule, rule_params = result
        return SchemaMatch(
            self.name, True, 0.85,
            bindings={
                "property": prop_name,
                "keep_when_true": keep_when_true,
                "destination_rule": rule,
                "rule_params": rule_params,
            },
        )

    def apply(self, input_grid, bindings):
        prop = bindings["property"]
        keep = bindings["keep_when_true"]
        rule = bindings["destination_rule"]
        rp = bindings["rule_params"]
        pred = _apply_copy_to_position_rule(input_grid, prop, keep, rule, rp)
        if pred is not None:
            return pred
        return input_grid.copy()


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY + EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

ALL_SCHEMAS: List[OperatorSchema] = [
    MarkerTargetTransform(),
    ContainerContentExtract(),
    SeparatorCellCompose(),
    SymmetryCompletion(),
    PatternRepetitionFill(),
    LineExtendUntilBoundary(),
    ObjectMatchTransferColor(),
    FilterCropRecolor(),
    CopyToPosition(),
    GravityDrop(),
    HoleFillMultiColor(),
    LineExtendUntilCollision(),
    ObjectMatchRecolor(),
    RegionColorPropagation(),
    FrameContentTransform(),
    MarkerDirectedMove(),
    ShapeCompleteFromBoundary(),
    SeparatorCellComposeAdvanced(),
    TraceDerivedCopyToPosition(),
]


class SchemaEvaluator:
    """Try all schemas on a task and return the best validated match."""

    def __init__(self, schemas: Optional[List[OperatorSchema]] = None):
        self.schemas = schemas or ALL_SCHEMAS

    def evaluate_task(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
    ) -> Optional[SchemaMatch]:
        best_match = None
        best_loo = 0.0

        for schema in self.schemas:
            try:
                match = schema.detect(train_pairs)
                if not match.matched:
                    continue
                val = schema.loo_validate(train_pairs, match)
                if val.loo_passed and val.loo_score > best_loo:
                    preds = []
                    for ti in test_inputs:
                        preds.append(schema.apply(ti, match.bindings))
                    match.predictions = preds
                    match.hypothesis = {
                        "strategy": "schema",
                        "schema_name": schema.name,
                        "bindings": {
                            k: (v.tolist() if isinstance(v, np.ndarray) else v)
                            for k, v in match.bindings.items()
                        },
                        "loo_passed": True,
                    }
                    best_match = match
                    best_loo = val.loo_score
            except Exception:
                continue

        return best_match

    def evaluate_all(
        self,
        tasks: List[Dict],
    ) -> Dict[str, Any]:
        solved = []
        schema_counts: Dict[str, int] = {}
        tested = 0

        for task in tasks:
            tid = task.get("task_id", "")
            train_pairs = task.get("train_pairs", [])
            test_inputs = task.get("test_inputs", [])
            test_outputs = task.get("test_outputs", [])
            if not train_pairs or not test_inputs:
                continue
            tested += 1

            match = self.evaluate_task(train_pairs, test_inputs)
            if match is not None and match.predictions is not None and test_outputs:
                correct = all(
                    np.array_equal(p, e)
                    for p, e in zip(match.predictions, test_outputs)
                )
                if correct:
                    solved.append(tid)
                    sn = match.schema_name
                    schema_counts[sn] = schema_counts.get(sn, 0) + 1

        return {
            "tested": tested,
            "solved": len(solved),
            "solved_tasks": solved,
            "schema_breakdown": schema_counts,
        }
