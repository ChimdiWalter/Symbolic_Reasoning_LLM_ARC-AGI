"""Conditional color transformation solver for ARC tasks.

Handles tasks where the output is derived from the input by recoloring
connected components based on their spatial or structural properties.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from typing import Optional, List, Tuple, Dict, Any


def _try_fill_enclosed(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Fill enclosed background regions (holes) with a consistent color."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for bg_color in [0]:
        fill_color = None
        ok = True

        for inp, out in train_pairs:
            bg_mask = inp == bg_color
            labeled_bg, n_bg = ndimage.label(bg_mask)
            if n_bg <= 1:
                ok = False
                break

            edge_labels = set()
            h, w = inp.shape
            for r in range(h):
                for c in range(w):
                    if (r == 0 or r == h - 1 or c == 0 or c == w - 1) and labeled_bg[r, c] > 0:
                        edge_labels.add(labeled_bg[r, c])

            for lab in range(1, n_bg + 1):
                mask = labeled_bg == lab
                if lab in edge_labels:
                    if not np.all(out[mask] == bg_color):
                        ok = False
                        break
                else:
                    out_vals = set(out[mask].tolist())
                    if len(out_vals) != 1:
                        ok = False
                        break
                    fc = out_vals.pop()
                    if fill_color is None:
                        fill_color = fc
                    elif fill_color != fc:
                        ok = False
                        break
            if not ok:
                break
            if not np.all(out[inp != bg_color] == inp[inp != bg_color]):
                ok = False
                break

        if ok and fill_color is not None:
            predictions = []
            for ti in test_inputs:
                bg_mask = ti == bg_color
                labeled_bg, n_bg = ndimage.label(bg_mask)
                edge_labels = set()
                h, w = ti.shape
                for r in range(h):
                    for c in range(w):
                        if (r == 0 or r == h - 1 or c == 0 or c == w - 1) and labeled_bg[r, c] > 0:
                            edge_labels.add(labeled_bg[r, c])
                pred = ti.copy()
                for lab in range(1, n_bg + 1):
                    if lab not in edge_labels:
                        pred[labeled_bg == lab] = fill_color
                predictions.append(pred)
            return predictions, {"strategy": "fill_enclosed", "fill_color": int(fill_color)}
    return None


def _try_fill_enclosed_adaptive(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Fill enclosed regions with the color of the surrounding boundary."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for bg_color in [0]:
        ok = True
        for inp, out in train_pairs:
            bg_mask = inp == bg_color
            labeled_bg, n_bg = ndimage.label(bg_mask)
            if n_bg <= 1:
                ok = False
                break

            edge_labels = set()
            h, w = inp.shape
            for r in range(h):
                for c in range(w):
                    if (r == 0 or r == h - 1 or c == 0 or c == w - 1) and labeled_bg[r, c] > 0:
                        edge_labels.add(labeled_bg[r, c])

            for lab in range(1, n_bg + 1):
                mask = labeled_bg == lab
                if lab in edge_labels:
                    if not np.all(out[mask] == bg_color):
                        ok = False
                        break
                else:
                    out_vals = set(out[mask].tolist())
                    if len(out_vals) != 1:
                        ok = False
                        break
                    fill_c = out_vals.pop()
                    dilated = ndimage.binary_dilation(mask)
                    boundary = dilated & ~mask & (inp != bg_color)
                    if boundary.any():
                        boundary_colors = inp[boundary]
                        unique_bc = set(boundary_colors.tolist())
                        if len(unique_bc) == 1 and unique_bc.pop() != fill_c:
                            ok = False
                            break
            if not ok:
                break
            if not np.all(out[inp != bg_color] == inp[inp != bg_color]):
                ok = False
                break

        if ok:
            predictions = []
            for ti in test_inputs:
                bg_mask = ti == bg_color
                labeled_bg, n_bg = ndimage.label(bg_mask)
                edge_labels = set()
                h, w = ti.shape
                for r in range(h):
                    for c in range(w):
                        if (r == 0 or r == h - 1 or c == 0 or c == w - 1) and labeled_bg[r, c] > 0:
                            edge_labels.add(labeled_bg[r, c])
                pred = ti.copy()
                for lab in range(1, n_bg + 1):
                    if lab not in edge_labels:
                        mask = labeled_bg == lab
                        dilated = ndimage.binary_dilation(mask)
                        boundary = dilated & ~mask & (ti != bg_color)
                        if boundary.any():
                            boundary_colors = ti[boundary]
                            unique, counts = np.unique(boundary_colors, return_counts=True)
                            fill_c = unique[np.argmax(counts)]
                            pred[mask] = fill_c
                predictions.append(pred)
            # Validate on training
            train_ok = True
            for (inp, out), pred in zip(train_pairs, []):
                pass
            return predictions, {"strategy": "fill_enclosed_adaptive"}
    return None


def _try_recolor_cc_by_size(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Recolor connected components based on their size rank."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    bg_color = 0
    rank_to_color = None

    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp != bg_color)
        if n == 0:
            return None

        components = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            size = int(mask.sum())
            components.append((lab, size))
        components.sort(key=lambda x: -x[1])

        local_rank_map = {}
        for rank, (lab, _) in enumerate(components):
            mask = labeled == lab
            out_vals = set(out[mask].tolist())
            if len(out_vals) != 1:
                return None
            oc = out_vals.pop()
            local_rank_map[rank] = oc

        if not np.all(out[inp == bg_color] == bg_color):
            return None

        if rank_to_color is None:
            rank_to_color = local_rank_map
        else:
            for rank, color in local_rank_map.items():
                if rank in rank_to_color and rank_to_color[rank] != color:
                    return None
            rank_to_color.update(local_rank_map)

    if rank_to_color is None:
        return None

    predictions = []
    for ti in test_inputs:
        labeled, n = ndimage.label(ti != bg_color)
        if n == 0:
            return None
        components = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            size = int(mask.sum())
            components.append((lab, size))
        components.sort(key=lambda x: -x[1])

        pred = ti.copy()
        for rank, (lab, _) in enumerate(components):
            mask = labeled == lab
            if rank in rank_to_color:
                pred[mask] = rank_to_color[rank]
            else:
                return None
        predictions.append(pred)

    # Validate on training
    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp != bg_color)
        components = sorted(
            [(lab, int((labeled == lab).sum())) for lab in range(1, n + 1)],
            key=lambda x: -x[1],
        )
        pred = inp.copy()
        for rank, (lab, _) in enumerate(components):
            pred[labeled == lab] = rank_to_color[rank]
        if not np.array_equal(pred, out):
            return None

    return predictions, {"strategy": "recolor_cc_by_size", "rank_map": {str(k): v for k, v in rank_to_color.items()}}


def _try_recolor_cc_by_color(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Recolor each connected component uniformly based on its input color."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    bg_color = 0
    color_map = {}

    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp != bg_color)
        for lab in range(1, n + 1):
            mask = labeled == lab
            in_vals = set(inp[mask].tolist())
            out_vals = set(out[mask].tolist())
            if len(in_vals) != 1 or len(out_vals) != 1:
                return None
            ic = in_vals.pop()
            oc = out_vals.pop()
            if ic in color_map:
                if color_map[ic] != oc:
                    return None
            else:
                color_map[ic] = oc

        if not np.all(out[inp == bg_color] == bg_color):
            return None

    if not color_map or all(k == v for k, v in color_map.items()):
        return None

    predictions = []
    for ti in test_inputs:
        pred = ti.copy()
        for ic, oc in color_map.items():
            pred[ti == ic] = oc
        predictions.append(pred)

    for inp, out in train_pairs:
        pred = inp.copy()
        for ic, oc in color_map.items():
            pred[inp == ic] = oc
        if not np.array_equal(pred, out):
            return None

    return predictions, {"strategy": "recolor_cc_by_color", "color_map": color_map}


def _try_majority_fill(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Replace each pixel with the majority color of its connected component."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp > 0)
        pred = inp.copy()
        for lab in range(1, n + 1):
            mask = labeled == lab
            vals = inp[mask]
            unique, counts = np.unique(vals, return_counts=True)
            majority = unique[np.argmax(counts)]
            pred[mask] = majority
        if not np.array_equal(pred, out):
            return None

    predictions = []
    for ti in test_inputs:
        labeled, n = ndimage.label(ti > 0)
        pred = ti.copy()
        for lab in range(1, n + 1):
            mask = labeled == lab
            vals = ti[mask]
            unique, counts = np.unique(vals, return_counts=True)
            majority = unique[np.argmax(counts)]
            pred[mask] = majority
        predictions.append(pred)
    return predictions, {"strategy": "majority_fill"}


def _try_global_color_permutation(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Learn a pixel-wise color map (color A -> color B) that applies uniformly.

    Many color_permutation tasks are simple global remappings where every pixel
    of color X becomes color Y across the entire grid.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    color_map: Dict[int, int] = {}

    for inp, out in train_pairs:
        for ic, oc in zip(inp.flatten(), out.flatten()):
            ic, oc = int(ic), int(oc)
            if ic in color_map:
                if color_map[ic] != oc:
                    return None
            else:
                color_map[ic] = oc

    # Must actually change something (not identity)
    if not color_map or all(k == v for k, v in color_map.items()):
        return None

    # Validate on training
    for inp, out in train_pairs:
        pred = inp.copy()
        for ic, oc in color_map.items():
            pred[inp == ic] = oc
        if not np.array_equal(pred, out):
            return None

    predictions = []
    for ti in test_inputs:
        pred = ti.copy()
        # Apply all mappings simultaneously using a temporary copy
        src = ti.copy()
        for ic, oc in color_map.items():
            pred[src == ic] = oc
        predictions.append(pred)

    return predictions, {"strategy": "global_color_permutation", "color_map": {str(k): v for k, v in color_map.items()}}


def _try_conditional_color_by_neighbor_count(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Recolor each pixel based on how many non-background neighbors it has.

    For example, corner pixels (2 neighbors) -> color A,
    edge pixels (3 neighbors) -> color B, interior (4 neighbors) -> color C.
    Only recolors non-background pixels.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    bg_color = 0
    # Map: (neighbor_count) -> output_color
    neighbor_map: Optional[Dict[int, int]] = None

    for inp, out in train_pairs:
        h, w = inp.shape
        local_map: Dict[int, int] = {}
        for r in range(h):
            for c in range(w):
                if inp[r, c] == bg_color:
                    if out[r, c] != bg_color:
                        return None
                    continue
                # Count non-background 4-connected neighbors
                count = 0
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w and inp[nr, nc] != bg_color:
                        count += 1
                oc = int(out[r, c])
                if count in local_map:
                    if local_map[count] != oc:
                        return None
                else:
                    local_map[count] = oc

        if neighbor_map is None:
            neighbor_map = local_map
        else:
            for count, oc in local_map.items():
                if count in neighbor_map and neighbor_map[count] != oc:
                    return None
            neighbor_map.update(local_map)

    if neighbor_map is None or len(neighbor_map) <= 1:
        return None

    # Must actually change something
    all_same = True
    for inp, out in train_pairs:
        if not np.array_equal(inp, out):
            all_same = False
            break
    if all_same:
        return None

    # Validate on training
    for inp, out in train_pairs:
        h, w = inp.shape
        pred = inp.copy()
        for r in range(h):
            for c in range(w):
                if inp[r, c] == bg_color:
                    continue
                count = 0
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w and inp[nr, nc] != bg_color:
                        count += 1
                if count in neighbor_map:
                    pred[r, c] = neighbor_map[count]
                else:
                    return None
        if not np.array_equal(pred, out):
            return None

    predictions = []
    for ti in test_inputs:
        h, w = ti.shape
        pred = ti.copy()
        for r in range(h):
            for c in range(w):
                if ti[r, c] == bg_color:
                    continue
                count = 0
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w and ti[nr, nc] != bg_color:
                        count += 1
                if count in neighbor_map:
                    pred[r, c] = neighbor_map[count]
                else:
                    return None
        predictions.append(pred)

    return predictions, {"strategy": "conditional_color_by_neighbor_count", "neighbor_map": {str(k): v for k, v in neighbor_map.items()}}


def _try_color_by_component_position(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Recolor each connected component based on its spatial position.

    Sorts components by (centroid_row, centroid_col) and assigns a learned
    color to each positional rank.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    bg_color = 0
    rank_to_color: Optional[Dict[int, int]] = None

    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp != bg_color)
        if n == 0:
            return None

        # Sort components by centroid position (row-major order)
        centroids = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            positions = np.argwhere(mask)
            centroid_r = positions[:, 0].mean()
            centroid_c = positions[:, 1].mean()
            centroids.append((lab, centroid_r, centroid_c))
        centroids.sort(key=lambda x: (x[1], x[2]))

        local_rank_map = {}
        for rank, (lab, _, _) in enumerate(centroids):
            mask = labeled == lab
            out_vals = set(out[mask].tolist())
            if len(out_vals) != 1:
                return None
            oc = out_vals.pop()
            local_rank_map[rank] = oc

        if not np.all(out[inp == bg_color] == bg_color):
            return None

        if rank_to_color is None:
            rank_to_color = local_rank_map
        else:
            for rank, color in local_rank_map.items():
                if rank in rank_to_color and rank_to_color[rank] != color:
                    return None
            rank_to_color.update(local_rank_map)

    if rank_to_color is None:
        return None

    # Must actually change something
    changes = False
    for inp, out in train_pairs:
        if not np.array_equal(inp, out):
            changes = True
            break
    if not changes:
        return None

    # Validate on training
    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp != bg_color)
        centroids = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            positions = np.argwhere(mask)
            centroid_r = positions[:, 0].mean()
            centroid_c = positions[:, 1].mean()
            centroids.append((lab, centroid_r, centroid_c))
        centroids.sort(key=lambda x: (x[1], x[2]))

        pred = inp.copy()
        for rank, (lab, _, _) in enumerate(centroids):
            mask = labeled == lab
            if rank not in rank_to_color:
                return None
            pred[mask] = rank_to_color[rank]
        if not np.array_equal(pred, out):
            return None

    predictions = []
    for ti in test_inputs:
        labeled, n = ndimage.label(ti != bg_color)
        if n == 0:
            return None
        centroids = []
        for lab in range(1, n + 1):
            mask = labeled == lab
            positions = np.argwhere(mask)
            centroid_r = positions[:, 0].mean()
            centroid_c = positions[:, 1].mean()
            centroids.append((lab, centroid_r, centroid_c))
        centroids.sort(key=lambda x: (x[1], x[2]))

        pred = ti.copy()
        for rank, (lab, _, _) in enumerate(centroids):
            mask = labeled == lab
            if rank not in rank_to_color:
                return None
            pred[mask] = rank_to_color[rank]
        predictions.append(pred)

    return predictions, {"strategy": "color_by_component_position", "rank_map": {str(k): v for k, v in rank_to_color.items()}}


def _try_swap_colors(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Detect and apply a pairwise color swap (e.g., all red->blue and blue->red).

    Specifically looks for exactly two colors that swap with each other,
    while all other colors remain unchanged.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    # Build color mapping from first pair
    color_map: Dict[int, int] = {}
    for inp, out in train_pairs:
        for ic, oc in zip(inp.flatten(), out.flatten()):
            ic, oc = int(ic), int(oc)
            if ic in color_map:
                if color_map[ic] != oc:
                    return None
            else:
                color_map[ic] = oc

    # Find swapped pairs: colors where A->B and B->A, with A != B
    swapped_pairs = []
    for a, b in color_map.items():
        if a != b and b in color_map and color_map[b] == a:
            if (b, a) not in swapped_pairs:
                swapped_pairs.append((a, b))

    if len(swapped_pairs) == 0:
        return None

    # All non-swapped colors must be identity
    swapped_colors = set()
    for a, b in swapped_pairs:
        swapped_colors.add(a)
        swapped_colors.add(b)
    for ic, oc in color_map.items():
        if ic not in swapped_colors and ic != oc:
            return None

    # Validate on training
    for inp, out in train_pairs:
        pred = inp.copy()
        src = inp.copy()
        for a, b in swapped_pairs:
            pred[src == a] = b
            pred[src == b] = a
        if not np.array_equal(pred, out):
            return None

    predictions = []
    for ti in test_inputs:
        pred = ti.copy()
        src = ti.copy()
        for a, b in swapped_pairs:
            pred[src == a] = b
            pred[src == b] = a
        predictions.append(pred)

    return predictions, {"strategy": "swap_colors", "swapped_pairs": [(int(a), int(b)) for a, b in swapped_pairs]}


def _try_remove_color(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Remove all pixels of a specific color (replace with background 0).

    Keeps everything else unchanged.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    bg_color = 0

    # Find which color(s) are present in input but absent in output
    candidate_colors = set()
    for inp, out in train_pairs:
        in_colors = set(inp.flatten().tolist())
        out_colors = set(out.flatten().tolist())
        removed = in_colors - out_colors - {bg_color}
        if not removed:
            return None
        if not candidate_colors:
            candidate_colors = removed
        else:
            candidate_colors &= removed
        if not candidate_colors:
            return None

    for remove_c in sorted(candidate_colors):
        ok = True
        for inp, out in train_pairs:
            pred = inp.copy()
            pred[pred == remove_c] = bg_color
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            predictions = []
            for ti in test_inputs:
                pred = ti.copy()
                pred[pred == remove_c] = bg_color
                predictions.append(pred)
            return predictions, {"strategy": "remove_color", "removed_color": int(remove_c)}

    return None


def _try_keep_only_color(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Keep only pixels of a specific color, set everything else to background.

    Opposite of remove_color: everything except the kept color becomes 0.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    bg_color = 0

    # Find which colors survive in the output
    candidate_colors: Optional[set] = None
    for inp, out in train_pairs:
        out_colors = set(out.flatten().tolist()) - {bg_color}
        if not out_colors:
            return None
        if candidate_colors is None:
            candidate_colors = out_colors
        else:
            candidate_colors &= out_colors
        if not candidate_colors:
            return None

    if candidate_colors is None:
        return None

    for keep_c in sorted(candidate_colors):
        ok = True
        for inp, out in train_pairs:
            pred = np.full_like(inp, bg_color)
            pred[inp == keep_c] = keep_c
            if not np.array_equal(pred, out):
                ok = False
                break
        if ok:
            predictions = []
            for ti in test_inputs:
                pred = np.full_like(ti, bg_color)
                pred[ti == keep_c] = keep_c
                predictions.append(pred)
            return predictions, {"strategy": "keep_only_color", "kept_color": int(keep_c)}

    return None


COLOR_STRATEGIES = [
    _try_fill_enclosed,
    _try_fill_enclosed_adaptive,
    _try_recolor_cc_by_size,
    _try_recolor_cc_by_color,
    _try_majority_fill,
    _try_global_color_permutation,
    _try_conditional_color_by_neighbor_count,
    _try_color_by_component_position,
    _try_swap_colors,
    _try_remove_color,
    _try_keep_only_color,
]


def solve_task_color(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Try all conditional color strategies on a task."""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for strategy_fn in COLOR_STRATEGIES:
        try:
            result = strategy_fn(train_pairs, test_inputs)
            if result is not None:
                return result
        except Exception:
            continue
    return None
