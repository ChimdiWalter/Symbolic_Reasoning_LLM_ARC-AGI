"""Crop/extract solver for ARC tasks that require selecting a subgrid from the input."""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from typing import Optional, List, Tuple, Dict, Any


def _find_unique_subgrid(
    inp: np.ndarray,
    target_shape: Tuple[int, int],
) -> Optional[np.ndarray]:
    """Find a subgrid of target_shape within inp. Returns first match or None."""
    th, tw = target_shape
    if th > inp.shape[0] or tw > inp.shape[1]:
        return None
    for r in range(inp.shape[0] - th + 1):
        for c in range(inp.shape[1] - tw + 1):
            yield inp[r:r+th, c:c+tw]


def _try_unique_subgrid(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract the subgrid from input that matches the output.

    Learns a selection criterion from training pairs: picks the subgrid with
    the most unique colors (most "interesting" / least background-dominated).
    Falls back to the subgrid with the most non-zero pixels.
    """
    out_shapes = [out.shape for _, out in train_pairs]
    if len(set(out_shapes)) != 1:
        return None
    oh, ow = out_shapes[0]

    for inp, out in train_pairs:
        found = False
        for sub in _find_unique_subgrid(inp, (oh, ow)):
            if np.array_equal(sub, out):
                found = True
                break
        if not found:
            return None

    def _score_subgrid(sub: np.ndarray) -> Tuple[int, int, float]:
        n_unique = len(set(sub.flatten().tolist()))
        n_nonzero = int(np.count_nonzero(sub))
        diversity = float(n_unique) / max(sub.size, 1)
        return (n_unique, n_nonzero, diversity)

    # Verify the scoring criterion selects the correct subgrid on training pairs
    for inp, out in train_pairs:
        best_sub = None
        best_score = (-1, -1, -1.0)
        for sub in _find_unique_subgrid(inp, (oh, ow)):
            score = _score_subgrid(sub)
            if score > best_score:
                best_score = score
                best_sub = sub.copy()
        if best_sub is None or not np.array_equal(best_sub, out):
            return None

    predictions = []
    for ti in test_inputs:
        best_sub = None
        best_score = (-1, -1, -1.0)
        for sub in _find_unique_subgrid(ti, (oh, ow)):
            score = _score_subgrid(sub)
            if score > best_score:
                best_score = score
                best_sub = sub.copy()
        if best_sub is None:
            return None
        predictions.append(best_sub)
    return predictions, {"strategy": "unique_subgrid"}


def _try_nonzero_bbox(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract bounding box of all non-zero pixels."""
    for inp, out in train_pairs:
        nz = np.argwhere(inp > 0)
        if len(nz) == 0:
            return None
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        crop = inp[r0:r1, c0:c1]
        if crop.shape != out.shape or not np.array_equal(crop, out):
            return None

    predictions = []
    for ti in test_inputs:
        nz = np.argwhere(ti > 0)
        if len(nz) == 0:
            return None
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        predictions.append(ti[r0:r1, c0:c1].copy())
    return predictions, {"strategy": "nonzero_bbox"}


def _try_color_bbox(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract bounding box of a specific color."""
    all_colors = set()
    for inp, _ in train_pairs:
        all_colors.update(inp.flatten().tolist())

    for color in sorted(all_colors):
        ok = True
        for inp, out in train_pairs:
            mask = inp == color
            if not mask.any():
                ok = False
                break
            nz = np.argwhere(mask)
            r0, c0 = nz.min(axis=0)
            r1, c1 = nz.max(axis=0) + 1
            crop = inp[r0:r1, c0:c1]
            if crop.shape != out.shape or not np.array_equal(crop, out):
                ok = False
                break
        if not ok:
            continue

        predictions = []
        test_ok = True
        for ti in test_inputs:
            mask = ti == color
            if not mask.any():
                test_ok = False
                break
            nz = np.argwhere(mask)
            r0, c0 = nz.min(axis=0)
            r1, c1 = nz.max(axis=0) + 1
            predictions.append(ti[r0:r1, c0:c1].copy())
        if test_ok:
            return predictions, {"strategy": "color_bbox", "color": int(color)}
    return None


def _try_largest_cc(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract bounding box of the largest connected component."""
    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp > 0)
        if n == 0:
            return None
        sizes = ndimage.sum(inp > 0, labeled, range(1, n + 1))
        largest = int(np.argmax(sizes)) + 1
        mask = labeled == largest
        nz = np.argwhere(mask)
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        crop = inp[r0:r1, c0:c1]
        if crop.shape != out.shape or not np.array_equal(crop, out):
            return None

    predictions = []
    for ti in test_inputs:
        labeled, n = ndimage.label(ti > 0)
        if n == 0:
            return None
        sizes = ndimage.sum(ti > 0, labeled, range(1, n + 1))
        largest = int(np.argmax(sizes)) + 1
        mask = labeled == largest
        nz = np.argwhere(mask)
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        predictions.append(ti[r0:r1, c0:c1].copy())
    return predictions, {"strategy": "largest_cc"}


def _try_smallest_cc(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract bounding box of the smallest connected component."""
    for inp, out in train_pairs:
        labeled, n = ndimage.label(inp > 0)
        if n == 0:
            return None
        sizes = ndimage.sum(inp > 0, labeled, range(1, n + 1))
        smallest = int(np.argmin(sizes)) + 1
        mask = labeled == smallest
        nz = np.argwhere(mask)
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        crop = inp[r0:r1, c0:c1]
        if crop.shape != out.shape or not np.array_equal(crop, out):
            return None

    predictions = []
    for ti in test_inputs:
        labeled, n = ndimage.label(ti > 0)
        if n == 0:
            return None
        sizes = ndimage.sum(ti > 0, labeled, range(1, n + 1))
        smallest = int(np.argmin(sizes)) + 1
        mask = labeled == smallest
        nz = np.argwhere(mask)
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        predictions.append(ti[r0:r1, c0:c1].copy())
    return predictions, {"strategy": "smallest_cc"}


def _try_minority_region(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract bounding box of the least frequent non-zero color region."""
    for inp, out in train_pairs:
        unique, counts = np.unique(inp, return_counts=True)
        nz_mask = unique > 0
        if not nz_mask.any():
            return None
        nz_colors = unique[nz_mask]
        nz_counts = counts[nz_mask]
        minority = nz_colors[np.argmin(nz_counts)]
        mask = inp == minority
        nz = np.argwhere(mask)
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        crop = inp[r0:r1, c0:c1]
        if crop.shape != out.shape or not np.array_equal(crop, out):
            return None

    predictions = []
    for ti in test_inputs:
        unique, counts = np.unique(ti, return_counts=True)
        nz_mask = unique > 0
        if not nz_mask.any():
            return None
        nz_colors = unique[nz_mask]
        nz_counts = counts[nz_mask]
        minority = nz_colors[np.argmin(nz_counts)]
        mask = ti == minority
        nz = np.argwhere(mask)
        r0, c0 = nz.min(axis=0)
        r1, c1 = nz.max(axis=0) + 1
        predictions.append(ti[r0:r1, c0:c1].copy())
    return predictions, {"strategy": "minority_region"}


def _try_halves_and_quadrants(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Extract a half or quadrant of the grid."""
    slicers = {
        "top_half": lambda g: g[:g.shape[0]//2, :],
        "bottom_half": lambda g: g[g.shape[0]//2:, :],
        "left_half": lambda g: g[:, :g.shape[1]//2],
        "right_half": lambda g: g[:, g.shape[1]//2:],
        "top_left": lambda g: g[:g.shape[0]//2, :g.shape[1]//2],
        "top_right": lambda g: g[:g.shape[0]//2, g.shape[1]//2:],
        "bottom_left": lambda g: g[g.shape[0]//2:, :g.shape[1]//2],
        "bottom_right": lambda g: g[g.shape[0]//2:, g.shape[1]//2:],
    }
    for name, slicer in slicers.items():
        ok = True
        for inp, out in train_pairs:
            crop = slicer(inp)
            if crop.shape != out.shape or not np.array_equal(crop, out):
                ok = False
                break
        if not ok:
            continue
        predictions = []
        test_ok = True
        for ti in test_inputs:
            crop = slicer(ti)
            predictions.append(crop.copy())
        return predictions, {"strategy": name}
    return None


def _try_separator_split(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Detect a row/column separator line and extract a subgrid on one side.

    A separator is a full row or column of a single color. The output is
    the subgrid on one side of the separator.
    """
    # Try row separators
    for side in ["above", "below"]:
        ok = True
        sep_color_learned = None
        for inp, out in train_pairs:
            h, w = inp.shape
            found = False
            for r in range(h):
                row = inp[r, :]
                if len(set(row.tolist())) == 1:
                    sep_color = int(row[0])
                    if sep_color_learned is not None and sep_color != sep_color_learned:
                        continue
                    if side == "above":
                        candidate = inp[:r, :]
                    else:
                        candidate = inp[r+1:, :]
                    if candidate.size == 0:
                        continue
                    if candidate.shape == out.shape and np.array_equal(candidate, out):
                        sep_color_learned = sep_color
                        found = True
                        break
            if not found:
                ok = False
                break
        if ok and sep_color_learned is not None:
            predictions = []
            test_ok = True
            for ti in test_inputs:
                h, w = ti.shape
                found = False
                for r in range(h):
                    row = ti[r, :]
                    if len(set(row.tolist())) == 1 and int(row[0]) == sep_color_learned:
                        if side == "above":
                            predictions.append(ti[:r, :].copy())
                        else:
                            predictions.append(ti[r+1:, :].copy())
                        found = True
                        break
                if not found:
                    test_ok = False
                    break
            if test_ok:
                return predictions, {"strategy": "separator_split", "direction": "row", "side": side, "sep_color": sep_color_learned}

    # Try column separators
    for side in ["left", "right"]:
        ok = True
        sep_color_learned = None
        for inp, out in train_pairs:
            h, w = inp.shape
            found = False
            for c in range(w):
                col = inp[:, c]
                if len(set(col.tolist())) == 1:
                    sep_color = int(col[0])
                    if sep_color_learned is not None and sep_color != sep_color_learned:
                        continue
                    if side == "left":
                        candidate = inp[:, :c]
                    else:
                        candidate = inp[:, c+1:]
                    if candidate.size == 0:
                        continue
                    if candidate.shape == out.shape and np.array_equal(candidate, out):
                        sep_color_learned = sep_color
                        found = True
                        break
            if not found:
                ok = False
                break
        if ok and sep_color_learned is not None:
            predictions = []
            test_ok = True
            for ti in test_inputs:
                h, w = ti.shape
                found = False
                for c in range(w):
                    col = ti[:, c]
                    if len(set(col.tolist())) == 1 and int(col[0]) == sep_color_learned:
                        if side == "left":
                            predictions.append(ti[:, :c].copy())
                        else:
                            predictions.append(ti[:, c+1:].copy())
                        found = True
                        break
                if not found:
                    test_ok = False
                    break
            if test_ok:
                return predictions, {"strategy": "separator_split", "direction": "col", "side": side, "sep_color": sep_color_learned}

    return None


def _try_mask_extract(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Use one colored region as a mask to extract/overlay content from another region.

    Detects grids split into two halves (top/bottom or left/right), where one
    half has a mask pattern that selects pixels from the other half.
    """
    if len(train_pairs) == 0:
        return None

    # Try top/bottom split with mask in one half
    for mask_half in ["top", "bottom"]:
        ok = True
        mask_color_learned = None
        for inp, out in train_pairs:
            h, w = inp.shape
            if h % 2 != 0:
                ok = False
                break
            half_h = h // 2
            if mask_half == "top":
                mask_region = inp[:half_h, :]
                content_region = inp[half_h:, :]
            else:
                mask_region = inp[half_h:, :]
                content_region = inp[:half_h, :]

            if out.shape != (half_h, w):
                ok = False
                break

            # Find mask color: non-background, non-zero color in mask region
            mask_colors = set(mask_region.flatten().tolist()) - {0}
            if not mask_colors:
                ok = False
                break

            found_mc = False
            for mc in sorted(mask_colors):
                mask = mask_region == mc
                # Output should have content_region pixels where mask is True, else background
                pred = np.zeros((half_h, w), dtype=int)
                pred[mask] = content_region[mask]
                if np.array_equal(pred, out):
                    if mask_color_learned is not None and mask_color_learned != mc:
                        continue
                    mask_color_learned = mc
                    found_mc = True
                    break
            if not found_mc:
                ok = False
                break

        if ok and mask_color_learned is not None:
            predictions = []
            test_ok = True
            for ti in test_inputs:
                h, w = ti.shape
                if h % 2 != 0:
                    test_ok = False
                    break
                half_h = h // 2
                if mask_half == "top":
                    mask_region = ti[:half_h, :]
                    content_region = ti[half_h:, :]
                else:
                    mask_region = ti[half_h:, :]
                    content_region = ti[:half_h, :]
                mask = mask_region == mask_color_learned
                pred = np.zeros((half_h, w), dtype=int)
                pred[mask] = content_region[mask]
                predictions.append(pred)
            if test_ok:
                return predictions, {"strategy": "mask_extract", "split": "horizontal", "mask_half": mask_half, "mask_color": mask_color_learned}

    # Try left/right split
    for mask_half in ["left", "right"]:
        ok = True
        mask_color_learned = None
        for inp, out in train_pairs:
            h, w = inp.shape
            if w % 2 != 0:
                ok = False
                break
            half_w = w // 2
            if mask_half == "left":
                mask_region = inp[:, :half_w]
                content_region = inp[:, half_w:]
            else:
                mask_region = inp[:, half_w:]
                content_region = inp[:, :half_w]

            if out.shape != (h, half_w):
                ok = False
                break

            mask_colors = set(mask_region.flatten().tolist()) - {0}
            if not mask_colors:
                ok = False
                break

            found_mc = False
            for mc in sorted(mask_colors):
                mask = mask_region == mc
                pred = np.zeros((h, half_w), dtype=int)
                pred[mask] = content_region[mask]
                if np.array_equal(pred, out):
                    if mask_color_learned is not None and mask_color_learned != mc:
                        continue
                    mask_color_learned = mc
                    found_mc = True
                    break
            if not found_mc:
                ok = False
                break

        if ok and mask_color_learned is not None:
            predictions = []
            test_ok = True
            for ti in test_inputs:
                h, w = ti.shape
                if w % 2 != 0:
                    test_ok = False
                    break
                half_w = w // 2
                if mask_half == "left":
                    mask_region = ti[:, :half_w]
                    content_region = ti[:, half_w:]
                else:
                    mask_region = ti[:, half_w:]
                    content_region = ti[:, :half_w]
                mask = mask_region == mask_color_learned
                pred = np.zeros((h, half_w), dtype=int)
                pred[mask] = content_region[mask]
                predictions.append(pred)
            if test_ok:
                return predictions, {"strategy": "mask_extract", "split": "vertical", "mask_half": mask_half, "mask_color": mask_color_learned}

    return None


def _try_repeated_tile_extract(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Detect if the grid is made of repeated tiles and extract one tile.

    Tries all divisor-based tile sizes. If the grid is an exact repetition
    of a smaller tile, extract that tile.
    """
    if len(train_pairs) == 0:
        return None

    # Get consistent output shape from training
    out_shapes = [out.shape for _, out in train_pairs]
    if len(set(out_shapes)) != 1:
        return None
    oh, ow = out_shapes[0]

    for inp, out in train_pairs:
        h, w = inp.shape
        if h % oh != 0 or w % ow != 0:
            return None
        reps_r = h // oh
        reps_c = w // ow

        # Check that the tile at (0,0) matches the output
        tile = inp[:oh, :ow]
        if not np.array_equal(tile, out):
            return None

        # Check that the tile is repeated everywhere
        tile_ok = True
        for ri in range(reps_r):
            for ci in range(reps_c):
                sub = inp[ri*oh:(ri+1)*oh, ci*ow:(ci+1)*ow]
                if not np.array_equal(sub, tile):
                    tile_ok = False
                    break
            if not tile_ok:
                break

        if not tile_ok:
            return None

    predictions = []
    for ti in test_inputs:
        h, w = ti.shape
        if h < oh or w < ow:
            return None
        # Extract top-left tile
        predictions.append(ti[:oh, :ow].copy())

    return predictions, {"strategy": "repeated_tile_extract", "tile_shape": [oh, ow]}


CROP_STRATEGIES = [
    _try_unique_subgrid,
    _try_nonzero_bbox,
    _try_color_bbox,
    _try_largest_cc,
    _try_smallest_cc,
    _try_minority_region,
    _try_halves_and_quadrants,
    _try_separator_split,
    _try_mask_extract,
    _try_repeated_tile_extract,
]


def solve_task_crop_extract(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Try all crop/extract strategies on a task."""
    if all(inp.shape == out.shape for inp, out in train_pairs):
        return None

    for strategy_fn in CROP_STRATEGIES:
        try:
            result = strategy_fn(train_pairs, test_inputs)
            if result is not None:
                return result
        except Exception:
            continue
    return None
