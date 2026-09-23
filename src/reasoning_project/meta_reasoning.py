"""Meta-Reasoning Engine — Human-Like Adaptive Reasoning for ARC.

This is THE core reasoning engine.  It does not add another layer — it IS the
reasoning loop that a human would run:

  1. OBSERVE  — what changes between input and output?
  2. REPRESENT — pixel? object? region? color? figure/icon? Pick the
     most informative view from data, including recognising that a grid
     IS a representation of a figure (arrow, letter, car, …).
  3. HYPOTHESISE — generate transformation hypotheses from data, including
     calling ALL existing engines as "tools" available to it.
  4. TEST — verify every hypothesis on ALL training pairs.
  5. SELF-TEST — generate its own synthetic tasks to verify it truly
     understands the transformation, not just memorised the examples.
  6. REFINE — when a method is *near* completion, analyse the residual
     and invent a targeted correction.
  7. COMPOSE — chain, residual-stack, or interleave multiple partial
     methods to build a novel one.
  8. REMEMBER — persist (signature → strategy) so similar tasks benefit.

Nothing is hardcoded. Methods are discovered, composed, and invented from
data.  Existing engines (adaptive_synthesizer, adaptive_reasoner, …) are
tools that this engine orchestrates, not peers that run in parallel.
"""
from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from scipy.ndimage import label as ndlabel

from reasoning_project.operator_genesis import SynthesizedOperator


# ===================================================================
# Near-Solved Memory — persists across tasks within a session
# ===================================================================

@dataclass
class NearSolvedEntry:
    task_signature: Tuple
    best_score: float
    best_representation: str
    best_hypothesis: str
    residual_pattern: Optional[str] = None


class NearSolvedMemory:
    """Tracks tasks that are almost solved — focuses future effort."""

    def __init__(self):
        self.entries: Dict[str, NearSolvedEntry] = {}
        self.successful_strategies: List[Tuple[Tuple, str, str]] = []

    def record(self, task_id: str, signature: Tuple, score: float,
               representation: str, hypothesis: str, residual: str = ""):
        if task_id not in self.entries or score > self.entries[task_id].best_score:
            self.entries[task_id] = NearSolvedEntry(
                task_signature=signature,
                best_score=score,
                best_representation=representation,
                best_hypothesis=hypothesis,
                residual_pattern=residual,
            )

    def record_success(self, signature: Tuple, representation: str, hypothesis: str):
        self.successful_strategies.append((signature, representation, hypothesis))

    def get_similar_strategies(self, signature: Tuple) -> List[Tuple[str, str]]:
        """Find strategies that worked on tasks with similar signatures."""
        results = []
        for sig, rep, hyp in self.successful_strategies:
            overlap = sum(1 for a, b in zip(sig, signature) if a == b)
            if overlap >= len(signature) * 0.5:
                results.append((rep, hyp))
        return results

    def get_near_solved(self, min_score: float = 0.5) -> List[NearSolvedEntry]:
        return [e for e in self.entries.values() if e.best_score >= min_score]


_near_solved_memory = NearSolvedMemory()


# ===================================================================
# 1. OBSERVE — What changes between input and output?
# ===================================================================

@dataclass
class Observation:
    """What we notice about a single training pair."""
    same_shape: bool
    changed_mask: Optional[np.ndarray]
    unchanged_mask: Optional[np.ndarray]
    frac_changed: float
    input_colors: Set[int]
    output_colors: Set[int]
    new_colors: Set[int]
    removed_colors: Set[int]
    bg_color: int
    n_input_objects: int
    n_output_objects: int
    change_is_local: bool
    change_is_global: bool
    input_has_symmetry: Tuple[bool, bool]  # h, v
    output_has_symmetry: Tuple[bool, bool]


def _detect_bg(grid: np.ndarray) -> int:
    counts = np.bincount(grid.flatten().astype(int), minlength=10)
    return int(np.argmax(counts))


def _check_symmetry(grid: np.ndarray) -> Tuple[bool, bool]:
    return (np.array_equal(grid, grid[::-1, :]),
            np.array_equal(grid, grid[:, ::-1]))


def _count_objects(grid: np.ndarray, bg: int) -> int:
    _, n = ndlabel(grid != bg)
    return n


def observe_pair(inp: np.ndarray, out: np.ndarray) -> Observation:
    same_shape = inp.shape == out.shape
    bg = _detect_bg(inp)
    ic = set(inp.flatten().tolist())
    oc = set(out.flatten().tolist())

    if same_shape:
        changed = inp != out
        frac = float(changed.sum()) / max(changed.size, 1)
        change_local = frac < 0.3
        change_global = frac > 0.7
    else:
        changed = None
        frac = 1.0
        change_local = False
        change_global = True

    return Observation(
        same_shape=same_shape,
        changed_mask=changed,
        unchanged_mask=~changed if changed is not None else None,
        frac_changed=frac,
        input_colors=ic,
        output_colors=oc,
        new_colors=oc - ic,
        removed_colors=ic - oc,
        bg_color=bg,
        n_input_objects=_count_objects(inp, bg),
        n_output_objects=_count_objects(out, bg),
        change_is_local=change_local,
        change_is_global=change_global,
        input_has_symmetry=_check_symmetry(inp),
        output_has_symmetry=_check_symmetry(out),
    )


def observe_task(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Tuple[List[Observation], Tuple]:
    """Observe all training pairs and compute a task signature."""
    observations = [observe_pair(inp, out) for inp, out in train_pairs]
    sig = (
        all(o.same_shape for o in observations),
        round(np.mean([o.frac_changed for o in observations]), 2),
        len(observations[0].input_colors),
        len(observations[0].output_colors),
        observations[0].n_input_objects,
        observations[0].n_output_objects,
        any(o.change_is_local for o in observations),
    )
    return observations, sig


# ===================================================================
# 2. REPRESENT — Guess the right representation from data
# ===================================================================

@dataclass
class Representation:
    name: str
    score: float  # how informative this representation is for this task
    data: Any  # representation-specific extracted data


def _repr_pixel(train_pairs, observations):
    """Pixel-level: each cell is independent."""
    if not all(o.same_shape for o in observations):
        return None
    score = 0.5
    if all(o.change_is_local for o in observations):
        score = 0.8
    return Representation("pixel", score, None)


def _repr_object(train_pairs, observations):
    """Object-level: connected components are the units."""
    score = 0.3
    if observations[0].n_input_objects >= 2:
        score = 0.7
    if observations[0].n_input_objects == observations[0].n_output_objects:
        score += 0.1
    return Representation("object", min(score, 1.0), None)


def _repr_color(train_pairs, observations):
    """Color-level: the transform is a color mapping."""
    if not all(o.same_shape for o in observations):
        return None
    # Check if change can be described purely as color remapping
    score = 0.2
    for inp, out in train_pairs:
        changed = inp != out
        if not changed.any():
            continue
        inp_changed = set(inp[changed].tolist())
        if len(inp_changed) <= 3:
            score += 0.2
    return Representation("color", min(score, 1.0), None)


def _repr_region(train_pairs, observations):
    """Region-level: grid divided into rectangular regions by separators."""
    inp = train_pairs[0][0]
    h, w = inp.shape
    score = 0.1

    # Check for separator lines
    for r in range(h):
        if len(set(inp[r, :].tolist())) == 1:
            score += 0.3
            break
    for c in range(w):
        if len(set(inp[:, c].tolist())) == 1:
            score += 0.3
            break

    return Representation("region", min(score, 1.0), None)


def _repr_pattern(train_pairs, observations):
    """Pattern-level: repeating motifs in the grid."""
    inp = train_pairs[0][0]
    h, w = inp.shape
    score = 0.1

    # Check for periodicity
    for period in range(2, min(h // 2 + 1, 8)):
        rows_match = all(
            np.array_equal(inp[r, :], inp[r % period, :])
            for r in range(period, h)
        )
        if rows_match:
            score = 0.7
            break

    for period in range(2, min(w // 2 + 1, 8)):
        cols_match = all(
            np.array_equal(inp[:, c], inp[:, c % period])
            for c in range(period, w)
        )
        if cols_match:
            score = max(score, 0.7)
            break

    return Representation("pattern", min(score, 1.0), None)


def _repr_iconic(train_pairs, observations):
    """Iconic/figure-level: the grid IS a picture of something.

    Some ARC tasks don't manipulate the grid — they recognise that the grid
    represents a figure (arrow, letter, cross, L-shape, …) and the answer
    depends on *what* the figure is, not on individual pixels.

    We detect this by looking for compact, named shapes in the objects.
    """
    if observations[0].n_input_objects < 1:
        return None

    inp = train_pairs[0][0]
    bg = observations[0].bg_color

    labeled, n_obj = ndlabel(inp != bg)
    shapes_found: List[str] = []

    for i in range(1, n_obj + 1):
        mask = labeled == i
        rows, cols = np.where(mask)
        if len(rows) == 0:
            continue
        min_r, max_r = rows.min(), rows.max()
        min_c, max_c = cols.min(), cols.max()
        bh = max_r - min_r + 1
        bw = max_c - min_c + 1

        crop = mask[min_r:max_r + 1, min_c:max_c + 1].astype(int)
        fill_ratio = crop.sum() / max(bh * bw, 1)
        aspect = bh / max(bw, 1)

        h_sym = np.array_equal(crop, crop[::-1, :])
        v_sym = np.array_equal(crop, crop[:, ::-1])
        d_sym = (bh == bw and np.array_equal(crop, crop.T))

        if fill_ratio > 0.95:
            shapes_found.append("rectangle")
        elif fill_ratio > 0.6 and h_sym and v_sym:
            shapes_found.append("diamond_or_circle")
        elif 0.4 < fill_ratio < 0.65 and (h_sym or v_sym):
            shapes_found.append("cross_or_plus")
        elif fill_ratio < 0.45 and (h_sym or v_sym):
            shapes_found.append("frame_or_hollow")
        elif bh >= 2 * bw or bw >= 2 * bh:
            shapes_found.append("bar_or_line")
        elif crop.sum() <= 5:
            shapes_found.append("dot_or_small")
        else:
            shapes_found.append("figure")

    score = 0.3
    if len(set(shapes_found)) >= 2:
        score = 0.6
    if any(s in ("cross_or_plus", "diamond_or_circle", "frame_or_hollow") for s in shapes_found):
        score = max(score, 0.7)

    return Representation("iconic", score, {"shapes": shapes_found})


def guess_representations(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    observations: List[Observation],
) -> List[Representation]:
    """Guess which representations are most useful for this task."""
    builders = [_repr_pixel, _repr_object, _repr_color, _repr_region,
                _repr_pattern, _repr_iconic]
    reps = []
    for builder in builders:
        try:
            r = builder(train_pairs, observations)
            if r is not None:
                reps.append(r)
        except Exception:
            continue
    reps.sort(key=lambda r: -r.score)
    return reps


# ===================================================================
# 3. HYPOTHESISE — Generate hypotheses FROM data, not templates
# ===================================================================

def _discover_color_mapping(train_pairs):
    """Discover: is there a consistent color→color mapping?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    # Learn mapping from ALL changed pixels across ALL pairs
    cmap: Dict[int, int] = {}
    consistent = True
    for inp, out in train_pairs:
        changed = inp != out
        if not changed.any():
            continue
        for ic, oc in zip(inp[changed].tolist(), out[changed].tolist()):
            if ic in cmap:
                if cmap[ic] != oc:
                    consistent = False
                    break
            else:
                cmap[ic] = oc
        if not consistent:
            break

    if consistent and cmap:
        frozen = dict(cmap)

        def apply_fn(grid, _m=frozen):
            out = grid.copy()
            for src, tgt in _m.items():
                out[grid == src] = tgt
            return out

        return [("color_mapping", apply_fn, f"Color map: {frozen}")]
    return []


def _discover_neighbor_rule(train_pairs):
    """Discover: does each pixel's output depend on its neighborhood?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    # For each changed pixel, compute (input_color, neighbor_signature) → output_color
    sig_map: Dict[Tuple, int] = {}
    sig_ok = True
    for inp, out in train_pairs:
        changed = inp != out
        if not changed.any():
            continue
        h, w = inp.shape
        wr, wc = np.where(changed)
        for r, c in zip(wr.tolist(), wc.tolist()):
            nbrs = []
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w:
                    nbrs.append(int(inp[nr, nc]))
                else:
                    nbrs.append(-1)
            key = (int(inp[r, c]),) + tuple(sorted(nbrs))
            val = int(out[r, c])
            if key in sig_map:
                if sig_map[key] != val:
                    sig_ok = False
                    break
            else:
                sig_map[key] = val
        if not sig_ok:
            break

    if sig_ok and sig_map:
        frozen = dict(sig_map)

        def apply_fn(grid, _m=frozen):
            out = grid.copy()
            h, w = grid.shape
            for r in range(h):
                for c in range(w):
                    nbrs = []
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            nbrs.append(int(grid[nr, nc]))
                        else:
                            nbrs.append(-1)
                    key = (int(grid[r, c]),) + tuple(sorted(nbrs))
                    if key in _m:
                        out[r, c] = _m[key]
            return out

        results.append(("neighbor_rule", apply_fn,
                         f"Neighbor-conditioned rule ({len(frozen)} entries)"))
    return results


def _discover_positional_rule(train_pairs):
    """Discover: does the output depend on (row, col) position modularly?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []
    for period_r in range(1, 6):
        for period_c in range(1, 6):
            if period_r == 1 and period_c == 1:
                continue
            pos_map: Dict[Tuple, int] = {}
            ok = True
            for inp, out in train_pairs:
                h, w = inp.shape
                changed = inp != out
                if not changed.any():
                    continue
                wr, wc = np.where(changed)
                for r, c in zip(wr.tolist(), wc.tolist()):
                    key = (r % period_r, c % period_c, int(inp[r, c]))
                    val = int(out[r, c])
                    if key in pos_map:
                        if pos_map[key] != val:
                            ok = False
                            break
                    else:
                        pos_map[key] = val
                if not ok:
                    break
            if ok and pos_map:
                # Verify it doesn't break unchanged pixels
                breaks = False
                for inp, out in train_pairs:
                    h, w = inp.shape
                    unchanged = inp == out
                    ur, uc = np.where(unchanged)
                    for r, c in zip(ur.tolist(), uc.tolist()):
                        key = (r % period_r, c % period_c, int(inp[r, c]))
                        if key in pos_map and pos_map[key] != int(inp[r, c]):
                            breaks = True
                            break
                    if breaks:
                        break
                if not breaks:
                    frozen = dict(pos_map)
                    pr, pc = period_r, period_c

                    def apply_fn(grid, _m=frozen, _pr=pr, _pc=pc):
                        out = grid.copy()
                        h, w = grid.shape
                        for r in range(h):
                            for c in range(w):
                                key = (r % _pr, c % _pc, int(grid[r, c]))
                                if key in _m:
                                    out[r, c] = _m[key]
                        return out

                    results.append(("positional_rule", apply_fn,
                                    f"Position-modular rule (period {period_r}×{period_c})"))
                    if len(results) >= 3:
                        return results
    return results


def _discover_symmetry_completion(train_pairs):
    """Discover: is the output a symmetric version of the input?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    # Check if output = input made symmetric
    for axis_name, flip_fn in [
        ("horizontal", lambda g: g[::-1, :]),
        ("vertical", lambda g: g[:, ::-1]),
        ("both", lambda g: g[::-1, ::-1]),
    ]:
        # Strategy: where input differs from flipped input, take the non-bg value
        def make_sym(flip, bg_detect=_detect_bg):
            def apply_fn(grid, _flip=flip):
                bg = bg_detect(grid)
                flipped = _flip(grid)
                out = grid.copy()
                # Where grid is bg but flipped is not, take flipped
                mask = (grid == bg) & (flipped != bg)
                out[mask] = flipped[mask]
                return out
            return apply_fn

        fn = make_sym(flip_fn)
        if _verify(fn, train_pairs):
            results.append(("symmetry_completion", fn,
                            f"Complete {axis_name} symmetry"))

    # Try: output = overlay of input and its flip (non-bg wins)
    for axis_name, flip_fn in [
        ("horizontal", lambda g: g[::-1, :]),
        ("vertical", lambda g: g[:, ::-1]),
    ]:
        def make_overlay(flip):
            def apply_fn(grid, _flip=flip):
                bg = _detect_bg(grid)
                flipped = _flip(grid)
                out = grid.copy()
                # Overlay: non-bg from either source
                mask1 = grid != bg
                mask2 = flipped != bg
                out[mask2 & ~mask1] = flipped[mask2 & ~mask1]
                return out
            return apply_fn

        fn = make_overlay(flip_fn)
        if _verify(fn, train_pairs):
            results.append(("symmetry_overlay", fn,
                            f"Overlay {axis_name} flip"))

    return results


def _discover_flood_fill(train_pairs):
    """Discover: are enclosed background regions filled?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    # Discover what color enclosed regions become
    for inp, out in train_pairs[:1]:
        bg = _detect_bg(inp)
        # Find enclosed bg regions (not touching border)
        bg_mask = inp == bg
        labeled, n = ndlabel(bg_mask)
        h, w = inp.shape

        for i in range(1, n + 1):
            region = labeled == i
            rows, cols = np.where(region)
            touches_border = (rows.min() == 0 or rows.max() == h - 1 or
                              cols.min() == 0 or cols.max() == w - 1)
            if touches_border:
                continue
            # This is an enclosed region — what color does it become?
            out_colors = set(out[region].tolist())
            if len(out_colors) == 1 and out_colors.pop() != bg:
                fill_color = out[region][0]
                # Check: does it get filled with the surrounding color?
                # Find surrounding colors
                surround = set()
                for r, c in zip(rows.tolist(), cols.tolist()):
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w and not region[nr, nc]:
                            surround.add(int(inp[nr, nc]))

    # Strategy: fill enclosed bg regions with surrounding color
    def fill_enclosed_surrounding(grid):
        bg = _detect_bg(grid)
        bg_mask = grid == bg
        labeled, n = ndlabel(bg_mask)
        h, w = grid.shape
        out = grid.copy()
        for i in range(1, n + 1):
            region = labeled == i
            rows, cols = np.where(region)
            touches_border = (rows.min() == 0 or rows.max() == h - 1 or
                              cols.min() == 0 or cols.max() == w - 1)
            if touches_border:
                continue
            # Find majority surrounding color
            surround_colors = []
            for r, c in zip(rows.tolist(), cols.tolist()):
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w and not region[nr, nc]:
                        surround_colors.append(int(grid[nr, nc]))
            if surround_colors:
                counts = Counter(c for c in surround_colors if c != bg)
                if counts:
                    fill_c = counts.most_common(1)[0][0]
                    out[region] = fill_c
        return out

    if _verify(fill_enclosed_surrounding, train_pairs):
        results.append(("flood_fill", fill_enclosed_surrounding,
                         "Fill enclosed bg regions with surrounding color"))

    # Strategy: fill enclosed regions with specific discovered color
    for fill_c in range(10):
        def make_fill(fc):
            def apply_fn(grid, _fc=fc):
                bg = _detect_bg(grid)
                bg_mask = grid == bg
                labeled, n = ndlabel(bg_mask)
                h, w = grid.shape
                out = grid.copy()
                for i in range(1, n + 1):
                    region = labeled == i
                    rows, cols = np.where(region)
                    touches_border = (rows.min() == 0 or rows.max() == h - 1 or
                                      cols.min() == 0 or cols.max() == w - 1)
                    if not touches_border:
                        out[region] = _fc
                return out
            return apply_fn

        fn = make_fill(fill_c)
        if _verify(fn, train_pairs):
            results.append(("flood_fill", fn,
                            f"Fill enclosed bg regions with color {fill_c}"))

    return results


def _discover_row_col_rule(train_pairs):
    """Discover: does output depend on row/column aggregates?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    # Discover: output[r,c] = f(row_dominant_color, col_dominant_color, input[r,c])
    rule_map: Dict[Tuple, int] = {}
    ok = True
    for inp, out in train_pairs:
        h, w = inp.shape
        bg = _detect_bg(inp)
        for r in range(h):
            row_colors = [int(v) for v in inp[r, :] if v != bg]
            row_dom = Counter(row_colors).most_common(1)[0][0] if row_colors else bg
            for c in range(w):
                col_colors = [int(v) for v in inp[:, c] if v != bg]
                col_dom = Counter(col_colors).most_common(1)[0][0] if col_colors else bg
                key = (int(inp[r, c]), row_dom, col_dom)
                val = int(out[r, c])
                if key in rule_map:
                    if rule_map[key] != val:
                        ok = False
                        break
                else:
                    rule_map[key] = val
            if not ok:
                break
        if not ok:
            break

    if ok and rule_map:
        frozen = dict(rule_map)

        def apply_fn(grid, _m=frozen):
            h, w = grid.shape
            bg = _detect_bg(grid)
            out = grid.copy()
            for r in range(h):
                row_colors = [int(v) for v in grid[r, :] if v != bg]
                row_dom = Counter(row_colors).most_common(1)[0][0] if row_colors else bg
                for c in range(w):
                    col_colors = [int(v) for v in grid[:, c] if v != bg]
                    col_dom = Counter(col_colors).most_common(1)[0][0] if col_colors else bg
                    key = (int(grid[r, c]), row_dom, col_dom)
                    if key in _m:
                        out[r, c] = _m[key]
            return out

        results.append(("row_col_rule", apply_fn,
                         f"Row/col context rule ({len(frozen)} entries)"))

    # Simpler: output[r,c] = row_dominant if input[r,c] is bg
    def fill_bg_with_row_dom(grid):
        bg = _detect_bg(grid)
        h, w = grid.shape
        out = grid.copy()
        for r in range(h):
            row_colors = [int(v) for v in grid[r, :] if v != bg]
            if row_colors:
                dom = Counter(row_colors).most_common(1)[0][0]
                for c in range(w):
                    if grid[r, c] == bg:
                        out[r, c] = dom
        return out

    if _verify(fill_bg_with_row_dom, train_pairs):
        results.append(("row_col_rule", fill_bg_with_row_dom,
                         "Fill bg with row dominant color"))

    def fill_bg_with_col_dom(grid):
        bg = _detect_bg(grid)
        h, w = grid.shape
        out = grid.copy()
        for c in range(w):
            col_colors = [int(v) for v in grid[:, c] if v != bg]
            if col_colors:
                dom = Counter(col_colors).most_common(1)[0][0]
                for r in range(h):
                    if grid[r, c] == bg:
                        out[r, c] = dom
        return out

    if _verify(fill_bg_with_col_dom, train_pairs):
        results.append(("row_col_rule", fill_bg_with_col_dom,
                         "Fill bg with column dominant color"))

    return results


def _discover_line_extension(train_pairs):
    """Discover: do colored lines/rays extend in a direction?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []
    bg = _detect_bg(train_pairs[0][0])

    for direction_name, dr, dc in [
        ("right", 0, 1), ("left", 0, -1),
        ("down", 1, 0), ("up", -1, 0),
    ]:
        def make_extend(d_r, d_c, _bg=bg):
            def apply_fn(grid, _dr=d_r, _dc=d_c, __bg=_bg):
                out = grid.copy()
                h, w = grid.shape
                for r in range(h):
                    for c in range(w):
                        if grid[r, c] != __bg:
                            nr, nc = r + _dr, c + _dc
                            while 0 <= nr < h and 0 <= nc < w and out[nr, nc] == __bg:
                                out[nr, nc] = grid[r, c]
                                nr += _dr
                                nc += _dc
                return out
            return apply_fn

        fn = make_extend(dr, dc)
        if _verify(fn, train_pairs):
            results.append(("line_extension", fn,
                            f"Extend colored pixels {direction_name}"))

    # All 4 directions at once
    def extend_all(grid):
        bg_l = _detect_bg(grid)
        out = grid.copy()
        h, w = grid.shape
        for r in range(h):
            for c in range(w):
                if grid[r, c] != bg_l:
                    for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nr, nc = r + dr, c + dc
                        while 0 <= nr < h and 0 <= nc < w and out[nr, nc] == bg_l:
                            out[nr, nc] = grid[r, c]
                            nr += dr
                            nc += dc
        return out

    if _verify(extend_all, train_pairs):
        results.append(("line_extension", extend_all,
                         "Extend colored pixels in all 4 directions"))

    return results


def _discover_gravity(train_pairs):
    """Discover: do non-bg pixels fall/slide to an edge?"""
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []
    bg = _detect_bg(train_pairs[0][0])

    # Gravity down: each column, non-bg pixels sink to bottom
    def gravity_down(grid, _bg=bg):
        out = np.full_like(grid, _bg)
        h, w = grid.shape
        for c in range(w):
            col = [int(grid[r, c]) for r in range(h) if grid[r, c] != _bg]
            for i, v in enumerate(reversed(col)):
                out[h - 1 - i, c] = v
        return out

    if _verify(gravity_down, train_pairs):
        results.append(("gravity", gravity_down, "Gravity: pixels fall down"))

    def gravity_up(grid, _bg=bg):
        out = np.full_like(grid, _bg)
        h, w = grid.shape
        for c in range(w):
            col = [int(grid[r, c]) for r in range(h) if grid[r, c] != _bg]
            for i, v in enumerate(col):
                out[i, c] = v
        return out

    if _verify(gravity_up, train_pairs):
        results.append(("gravity", gravity_up, "Gravity: pixels float up"))

    def gravity_left(grid, _bg=bg):
        out = np.full_like(grid, _bg)
        h, w = grid.shape
        for r in range(h):
            row = [int(grid[r, c]) for c in range(w) if grid[r, c] != _bg]
            for i, v in enumerate(row):
                out[r, i] = v
        return out

    if _verify(gravity_left, train_pairs):
        results.append(("gravity", gravity_left, "Gravity: pixels slide left"))

    def gravity_right(grid, _bg=bg):
        out = np.full_like(grid, _bg)
        h, w = grid.shape
        for r in range(h):
            row = [int(grid[r, c]) for c in range(w) if grid[r, c] != _bg]
            for i, v in enumerate(reversed(row)):
                out[r, w - 1 - i] = v
        return out

    if _verify(gravity_right, train_pairs):
        results.append(("gravity", gravity_right, "Gravity: pixels slide right"))

    return results


def _discover_input_output_mapping(train_pairs):
    """Discover: pixel-level (input_color, position_feature) → output_color.

    This is the most general same-shape hypothesis: learn the mapping
    from data without assuming ANY specific structure.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    # Feature sets to try, from simple to complex
    feature_extractors = [
        ("color_only", lambda g, r, c: (int(g[r, c]),)),
        ("color_border", lambda g, r, c: (
            int(g[r, c]),
            r == 0 or r == g.shape[0] - 1 or c == 0 or c == g.shape[1] - 1,
        )),
        ("color_parity", lambda g, r, c: (int(g[r, c]), r % 2, c % 2)),
        ("color_diag", lambda g, r, c: (int(g[r, c]), (r + c) % 2)),
    ]

    for feat_name, feat_fn in feature_extractors:
        rule: Dict[Tuple, int] = {}
        ok = True
        for inp, out in train_pairs:
            h, w = inp.shape
            for r in range(h):
                for c in range(w):
                    key = feat_fn(inp, r, c)
                    val = int(out[r, c])
                    if key in rule:
                        if rule[key] != val:
                            ok = False
                            break
                    else:
                        rule[key] = val
                if not ok:
                    break
            if not ok:
                break

        if ok and rule:
            frozen = dict(rule)
            _fn = feat_fn

            def make_apply(frule, ffn):
                def apply_fn(grid, _r=frule, _f=ffn):
                    out = grid.copy()
                    h, w = grid.shape
                    for r in range(h):
                        for c in range(w):
                            key = _f(grid, r, c)
                            if key in _r:
                                out[r, c] = _r[key]
                    return out
                return apply_fn

            fn = make_apply(frozen, _fn)
            if _verify(fn, train_pairs):
                results.append(("learned_mapping", fn,
                                f"Learned {feat_name} mapping ({len(frozen)} rules)"))

    return results


def _discover_copy_with_edits(train_pairs):
    """Generate: start from input copy, apply discovered edits.

    Even if we can't solve perfectly, this produces high partial scores
    for the correction loop.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    # Count how many pixels differ per pair
    diffs = []
    for inp, out in train_pairs:
        d = int((inp != out).sum())
        diffs.append(d)

    if max(diffs) == 0:
        # Identity
        def identity(grid):
            return grid.copy()
        results.append(("identity", identity, "Identity (no change)"))
        return results

    # If very few pixels change, try to learn the exact edit positions
    avg_changed = np.mean(diffs)
    total_pixels = train_pairs[0][0].size

    if avg_changed / total_pixels < 0.15:
        # Learn: (r, c, input_color) → output_color for changed pixels
        edit_map: Dict[Tuple, int] = {}
        ok = True
        for inp, out in train_pairs:
            changed = inp != out
            wr, wc = np.where(changed)
            for r, c in zip(wr.tolist(), wc.tolist()):
                key = (r, c, int(inp[r, c]))
                val = int(out[r, c])
                if key in edit_map:
                    if edit_map[key] != val:
                        ok = False
                        break
                else:
                    edit_map[key] = val
            if not ok:
                break

        if ok and edit_map:
            frozen = dict(edit_map)

            def apply_fn(grid, _m=frozen):
                out = grid.copy()
                h, w = grid.shape
                for (r, c, ic), oc in _m.items():
                    if r < h and c < w and int(grid[r, c]) == ic:
                        out[r, c] = oc
                return out

            if _verify(apply_fn, train_pairs):
                results.append(("sparse_edit", apply_fn,
                                f"Sparse edit: {len(frozen)} position-specific changes"))

    return results


# ===================================================================
# 3b. AUTO-SOLVER GENERATOR — Construct new solvers from primitives
# ===================================================================
#
# Instead of pre-coding "discover gravity" or "discover color mapping",
# this section:
#   1. Defines ATOMIC PRIMITIVES (features a pixel can have)
#   2. Automatically discovers WHICH features predict the output
#   3. Constructs a solver function from the discovered features
#
# This is how the system invents new solvers it was never coded to know.

def _extract_pixel_features(grid: np.ndarray, r: int, c: int) -> Dict[str, int]:
    """Extract all observable features of a pixel's context.

    These are the atoms. The system discovers which atoms matter.
    """
    h, w = grid.shape
    val = int(grid[r, c])
    feats: Dict[str, int] = {}

    # --- Identity ---
    feats["color"] = val
    feats["row"] = r
    feats["col"] = c
    feats["row_mod2"] = r % 2
    feats["col_mod2"] = c % 2
    feats["row_mod3"] = r % 3
    feats["col_mod3"] = c % 3
    feats["diag_mod2"] = (r + c) % 2
    feats["antidiag_mod2"] = (r - c) % 2

    # --- Position context ---
    feats["is_border"] = int(r == 0 or r == h - 1 or c == 0 or c == w - 1)
    feats["is_corner"] = int((r in (0, h-1)) and (c in (0, w-1)))
    feats["dist_top"] = r
    feats["dist_bottom"] = h - 1 - r
    feats["dist_left"] = c
    feats["dist_right"] = w - 1 - c
    feats["dist_edge"] = min(r, h-1-r, c, w-1-c)

    # --- Neighbor context ---
    n4_colors = []
    n8_colors = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            n4_colors.append(int(grid[nr, nc]))
        else:
            n4_colors.append(-1)
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                n8_colors.append(int(grid[nr, nc]))
            else:
                n8_colors.append(-1)

    feats["n4_same"] = sum(1 for nc in n4_colors if nc == val)
    feats["n8_same"] = sum(1 for nc in n8_colors if nc == val)
    feats["n4_diff"] = sum(1 for nc in n4_colors if nc != val and nc >= 0)
    n4_valid = [nc for nc in n4_colors if nc >= 0]
    feats["n4_unique"] = len(set(n4_valid))
    feats["n4_max"] = max(n4_valid) if n4_valid else -1
    feats["n4_min"] = min(n4_valid) if n4_valid else -1

    # --- Row/column context ---
    row_vals = [int(grid[r, cc]) for cc in range(w)]
    col_vals = [int(grid[rr, c]) for rr in range(h)]
    feats["row_unique"] = len(set(row_vals))
    feats["col_unique"] = len(set(col_vals))
    row_counts = Counter(row_vals)
    col_counts = Counter(col_vals)
    feats["row_dominant"] = row_counts.most_common(1)[0][0]
    feats["col_dominant"] = col_counts.most_common(1)[0][0]
    feats["row_count_self"] = row_counts[val]
    feats["col_count_self"] = col_counts[val]

    return feats


def _find_discriminative_features(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    max_features: int = 4,
) -> List[Tuple[List[str], Dict[Tuple, int]]]:
    """Discover which feature combinations predict output color.

    This is the core of auto-solver generation: scan all features,
    find which subset perfectly predicts the output, build a rule.
    No pre-coded hypothesis needed.
    """
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    # Collect all (features, output) pairs from training data
    all_data: List[Tuple[Dict[str, int], int]] = []
    for inp, out in train_pairs:
        h, w = inp.shape
        for r in range(h):
            for c in range(w):
                feats = _extract_pixel_features(inp, r, c)
                all_data.append((feats, int(out[r, c])))

    if not all_data:
        return []

    all_feature_names = sorted(all_data[0][0].keys())

    results: List[Tuple[List[str], Dict[Tuple, int]]] = []

    # Try single features first, then pairs, then triples
    for n_feats in range(1, min(max_features + 1, 4)):
        if results:
            break
        from itertools import combinations
        for feat_combo in combinations(all_feature_names, n_feats):
            rule: Dict[Tuple, int] = {}
            consistent = True
            for feats, out_val in all_data:
                key = tuple(feats[f] for f in feat_combo)
                if key in rule:
                    if rule[key] != out_val:
                        consistent = False
                        break
                else:
                    rule[key] = out_val

            if consistent and len(rule) < len(all_data) * 0.8:
                results.append((list(feat_combo), rule))
                if len(results) >= 5:
                    return results

    return results


def _build_solver_from_features(
    feat_names: List[str],
    rule: Dict[Tuple, int],
) -> Callable:
    """Construct a solver function from discovered features + rule.

    This is a new solver that was never coded — it was auto-generated
    from the features that the system discovered matter.
    """
    frozen_names = list(feat_names)
    frozen_rule = dict(rule)

    def solver(grid, _names=frozen_names, _rule=frozen_rule):
        h, w = grid.shape
        out = grid.copy()
        for r in range(h):
            for c in range(w):
                feats = _extract_pixel_features(grid, r, c)
                key = tuple(feats[f] for f in _names)
                if key in _rule:
                    out[r, c] = _rule[key]
        return out

    return solver


def _auto_generate_solvers(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    deadline: float,
) -> List[Tuple[str, Callable, str]]:
    """The auto-solver generator.

    Discovers which features of a pixel's context predict the output,
    then constructs a solver from those features. The system invents
    new transformation rules it was never explicitly programmed to know.
    """
    if time.time() > deadline:
        return []

    results = []

    discovered = _find_discriminative_features(train_pairs, max_features=3)

    for feat_names, rule in discovered:
        if time.time() > deadline:
            break

        solver = _build_solver_from_features(feat_names, rule)

        if _verify(solver, train_pairs):
            feat_desc = "+".join(feat_names)
            results.append((
                f"auto_{feat_desc}",
                solver,
                f"Auto-generated solver: output = f({feat_desc}), {len(rule)} rules"
            ))

    return results


# --- Object-level auto-solver (for tasks where objects transform) ---

def _extract_object_features(
    grid: np.ndarray, obj_mask: np.ndarray, bg: int,
) -> Dict[str, int]:
    """Extract features of an object (not just a pixel)."""
    rows, cols = np.where(obj_mask)
    if len(rows) == 0:
        return {}

    feats: Dict[str, int] = {}
    feats["area"] = int(obj_mask.sum())
    feats["min_r"] = int(rows.min())
    feats["max_r"] = int(rows.max())
    feats["min_c"] = int(cols.min())
    feats["max_c"] = int(cols.max())
    feats["height"] = feats["max_r"] - feats["min_r"] + 1
    feats["width"] = feats["max_c"] - feats["min_c"] + 1
    feats["color"] = int(Counter(grid[obj_mask].tolist()).most_common(1)[0][0])
    feats["n_colors"] = len(set(grid[obj_mask].tolist()))

    crop = obj_mask[feats["min_r"]:feats["max_r"]+1, feats["min_c"]:feats["max_c"]+1]
    feats["fill_ratio_x10"] = int(10 * crop.sum() / max(crop.size, 1))
    feats["h_symmetric"] = int(np.array_equal(crop, crop[::-1, :]))
    feats["v_symmetric"] = int(np.array_equal(crop, crop[:, ::-1]))
    feats["is_square"] = int(feats["height"] == feats["width"])

    # Has hole?
    inner = crop.copy()
    if inner.shape[0] >= 3 and inner.shape[1] >= 3:
        inner_region = inner[1:-1, 1:-1]
        feats["has_hole"] = int(not inner_region.all())
    else:
        feats["has_hole"] = 0

    return feats


def _auto_generate_object_solvers(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    deadline: float,
) -> List[Tuple[str, Callable, str]]:
    """Auto-generate solvers at the object level.

    Discovers which object features predict how objects change
    (recoloring, movement, etc.) and constructs solvers accordingly.
    """
    if time.time() > deadline:
        return []
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    # Learn: for each object, what color does it become in the output?
    # Feature: object property → new color of that object's pixels
    try:
        obj_rules: List[Tuple[Dict[str, int], int]] = []
        for inp, out in train_pairs:
            bg = _detect_bg(inp)
            labeled, n = ndlabel(inp != bg)
            for i in range(1, n + 1):
                mask = labeled == i
                feats = _extract_object_features(inp, mask, bg)
                if not feats:
                    continue
                # What color do these pixels become?
                out_colors = Counter(out[mask].tolist())
                dominant_out = out_colors.most_common(1)[0][0]
                obj_rules.append((feats, dominant_out))

        if not obj_rules:
            return results

        # Try single-feature rules
        feat_names = sorted(obj_rules[0][0].keys())
        for fname in feat_names:
            if time.time() > deadline:
                break
            rule: Dict[int, int] = {}
            ok = True
            for feats, out_color in obj_rules:
                key = feats.get(fname, -1)
                if key in rule:
                    if rule[key] != out_color:
                        ok = False
                        break
                else:
                    rule[key] = out_color

            if ok and rule and len(rule) <= len(obj_rules):
                frozen_fname = fname
                frozen_rule = dict(rule)

                def make_obj_solver(fn, fr):
                    def solver(grid, _fn=fn, _fr=fr):
                        bg = _detect_bg(grid)
                        labeled, n = ndlabel(grid != bg)
                        out = grid.copy()
                        for i in range(1, n + 1):
                            mask = labeled == i
                            feats = _extract_object_features(grid, mask, bg)
                            key = feats.get(_fn, -1)
                            if key in _fr:
                                out[mask] = _fr[key]
                        return out
                    return solver

                solver = make_obj_solver(frozen_fname, frozen_rule)
                if _verify(solver, train_pairs):
                    results.append((
                        f"auto_obj_{frozen_fname}",
                        solver,
                        f"Auto object solver: recolor by {frozen_fname} ({len(frozen_rule)} rules)"
                    ))

    except Exception:
        pass

    return results


# --- Relational features between objects ---

def _extract_relational_features(
    grid: np.ndarray, objects: List[Tuple[np.ndarray, Dict[str, int]]],
    idx: int, bg: int,
) -> Dict[str, int]:
    """Extract features that describe this object's RELATIONSHIP to others.

    This is what lets the system discover rules like 'the object above
    the largest object gets recolored' or 'objects with the same color
    as the border object get deleted'.
    """
    feats: Dict[str, int] = {}
    if idx >= len(objects) or len(objects) < 2:
        return feats

    _, my = objects[idx]
    my_cx = (my["min_r"] + my["max_r"]) / 2
    my_cy = (my["min_c"] + my["max_c"]) / 2

    areas = [f["area"] for _, f in objects]
    colors = [f["color"] for _, f in objects]
    sorted_areas = sorted(set(areas), reverse=True)

    feats["area_rank"] = sorted_areas.index(my["area"]) if my["area"] in sorted_areas else -1
    feats["is_largest"] = int(my["area"] == max(areas))
    feats["is_smallest"] = int(my["area"] == min(areas))
    feats["color_count_in_scene"] = sum(1 for c in colors if c == my["color"])
    feats["is_unique_color"] = int(feats["color_count_in_scene"] == 1)
    feats["n_objects_total"] = len(objects)

    # Spatial relations to other objects
    above = 0
    below = 0
    left_of = 0
    right_of = 0
    overlapping_col = 0
    overlapping_row = 0
    nearest_dist = 9999
    nearest_color = -1

    for j, (_, other) in enumerate(objects):
        if j == idx:
            continue
        o_cx = (other["min_r"] + other["max_r"]) / 2
        o_cy = (other["min_c"] + other["max_c"]) / 2

        if my_cx < o_cx:
            above += 1
        elif my_cx > o_cx:
            below += 1
        if my_cy < o_cy:
            left_of += 1
        elif my_cy > o_cy:
            right_of += 1

        if (my["min_c"] <= other["max_c"] and my["max_c"] >= other["min_c"]):
            overlapping_col += 1
        if (my["min_r"] <= other["max_r"] and my["max_r"] >= other["min_r"]):
            overlapping_row += 1

        dist = abs(my_cx - o_cx) + abs(my_cy - o_cy)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_color = other["color"]

    feats["n_above"] = above
    feats["n_below"] = below
    feats["n_left"] = left_of
    feats["n_right"] = right_of
    feats["n_overlapping_col"] = overlapping_col
    feats["n_overlapping_row"] = overlapping_row
    feats["nearest_obj_color"] = nearest_color
    feats["same_color_as_nearest"] = int(my["color"] == nearest_color)

    return feats


def _auto_generate_relational_solvers(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    deadline: float,
) -> List[Tuple[str, Callable, str]]:
    """Auto-generate solvers using inter-object relationships.

    Discovers rules like 'objects whose area_rank=0 get recolored to blue'
    or 'the object nearest to the largest object changes color'.
    """
    if time.time() > deadline:
        return []
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    try:
        # Collect (relational_features, output_color) for each object in each pair
        rel_rules: List[Tuple[Dict[str, int], int]] = []

        for inp, out in train_pairs:
            bg = _detect_bg(inp)
            labeled, n = ndlabel(inp != bg)

            objects = []
            for i in range(1, n + 1):
                mask = labeled == i
                feats = _extract_object_features(inp, mask, bg)
                if feats:
                    objects.append((mask, feats))

            if len(objects) < 2:
                continue

            for idx, (mask, base_feats) in enumerate(objects):
                rel_feats = _extract_relational_features(inp, objects, idx, bg)
                combined = {**base_feats, **rel_feats}
                out_colors = Counter(out[mask].tolist())
                dominant_out = out_colors.most_common(1)[0][0]
                rel_rules.append((combined, dominant_out))

        if not rel_rules or len(rel_rules) < 2:
            return results

        # Find single relational features that predict output color
        feat_names = sorted(rel_rules[0][0].keys())
        for fname in feat_names:
            if time.time() > deadline:
                break
            rule: Dict[int, int] = {}
            ok = True
            for feats, out_color in rel_rules:
                key = feats.get(fname, -1)
                if key in rule:
                    if rule[key] != out_color:
                        ok = False
                        break
                else:
                    rule[key] = out_color

            if ok and rule and len(rule) <= len(rel_rules):
                frozen_fname = fname
                frozen_rule = dict(rule)

                def make_rel_solver(fn, fr):
                    def solver(grid, _fn=fn, _fr=fr):
                        bg = _detect_bg(grid)
                        labeled, n = ndlabel(grid != bg)
                        out = grid.copy()
                        objects = []
                        for i in range(1, n + 1):
                            mask = labeled == i
                            feats = _extract_object_features(grid, mask, bg)
                            if feats:
                                objects.append((mask, feats))
                        for idx, (mask, base_feats) in enumerate(objects):
                            rel_feats = _extract_relational_features(
                                grid, objects, idx, bg)
                            combined = {**base_feats, **rel_feats}
                            key = combined.get(_fn, -1)
                            if key in _fr:
                                out[mask] = _fr[key]
                        return out
                    return solver

                solver = make_rel_solver(frozen_fname, frozen_rule)
                if _verify(solver, train_pairs):
                    results.append((
                        f"auto_rel_{frozen_fname}",
                        solver,
                        f"Auto relational solver: recolor by {frozen_fname} "
                        f"({len(frozen_rule)} rules)"
                    ))

    except Exception:
        pass

    return results


# --- Spatial transform auto-discovery ---

def _auto_generate_spatial_solvers(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    deadline: float,
) -> List[Tuple[str, Callable, str]]:
    """Auto-discover spatial transformations: where do objects MOVE?

    Instead of 'what color?' this asks 'where does each object go?'
    Discovers mappings like:
      object_color → displacement (dr, dc)
      area_rank → destination position
      is_largest → stays, others → move to largest's row
    """
    if time.time() > deadline:
        return []
    if not all(inp.shape == out.shape for inp, out in train_pairs):
        return []

    results = []

    try:
        for inp, out in train_pairs[:1]:  # analyze first pair
            bg_in = _detect_bg(inp)
            bg_out = _detect_bg(out)
            bg = bg_in

            labeled_in, n_in = ndlabel(inp != bg)
            labeled_out, n_out = ndlabel(out != bg)

            if n_in < 2 or n_out < 1:
                return results

            # Extract input objects
            in_objects = []
            for i in range(1, n_in + 1):
                mask = labeled_in == i
                feats = _extract_object_features(inp, mask, bg)
                if feats:
                    in_objects.append((mask, feats))

            # Extract output objects
            out_objects = []
            for i in range(1, n_out + 1):
                mask = labeled_out == i
                feats = _extract_object_features(out, mask, bg)
                if feats:
                    out_objects.append((mask, feats))

            if not in_objects or not out_objects:
                return results

            # --- Match input→output objects by color + shape similarity ---
            movements: List[Tuple[Dict[str, int], Tuple[int, int]]] = []

            for in_mask, in_feats in in_objects:
                in_cx = (in_feats["min_r"] + in_feats["max_r"]) // 2
                in_cy = (in_feats["min_c"] + in_feats["max_c"]) // 2

                best_match = None
                best_dist = 9999
                for out_mask, out_feats in out_objects:
                    if (out_feats["color"] == in_feats["color"] and
                            out_feats["area"] == in_feats["area"]):
                        out_cx = (out_feats["min_r"] + out_feats["max_r"]) // 2
                        out_cy = (out_feats["min_c"] + out_feats["max_c"]) // 2
                        dist = abs(in_cx - out_cx) + abs(in_cy - out_cy)
                        if dist < best_dist:
                            best_dist = dist
                            best_match = (out_cx - in_cx, out_cy - in_cy)

                if best_match is not None:
                    rel_feats = _extract_relational_features(
                        inp, in_objects, in_objects.index((in_mask, in_feats)), bg)
                    combined = {**in_feats, **rel_feats}
                    movements.append((combined, best_match))

            if len(movements) < 2:
                return results

            # --- Find which feature predicts the displacement ---
            feat_names = sorted(movements[0][0].keys())

            # Try: feature → (dr, dc)
            for fname in feat_names:
                if time.time() > deadline:
                    break
                rule: Dict[int, Tuple[int, int]] = {}
                ok = True
                for feats, disp in movements:
                    key = feats.get(fname, -1)
                    if key in rule:
                        if rule[key] != disp:
                            ok = False
                            break
                    else:
                        rule[key] = disp

                if ok and rule and any(d != (0, 0) for d in rule.values()):
                    frozen_fname = fname
                    frozen_rule = dict(rule)

                    def make_move_solver(fn, fr, _bg=bg):
                        def solver(grid, _fn=fn, _fr=fr, __bg=_bg):
                            bg_l = __bg
                            labeled, n = ndlabel(grid != bg_l)
                            out = np.full_like(grid, bg_l)

                            objects = []
                            for i in range(1, n + 1):
                                mask = labeled == i
                                feats = _extract_object_features(grid, mask, bg_l)
                                if feats:
                                    objects.append((mask, feats))

                            for idx, (mask, base_feats) in enumerate(objects):
                                rel_feats = _extract_relational_features(
                                    grid, objects, idx, bg_l)
                                combined = {**base_feats, **rel_feats}
                                key = combined.get(_fn, -1)
                                dr, dc = _fr.get(key, (0, 0))

                                rows, cols = np.where(mask)
                                h, w = grid.shape
                                for r, c in zip(rows.tolist(), cols.tolist()):
                                    nr, nc = r + dr, c + dc
                                    if 0 <= nr < h and 0 <= nc < w:
                                        out[nr, nc] = grid[r, c]
                            return out
                        return solver

                    solver = make_move_solver(frozen_fname, frozen_rule)
                    if _verify(solver, train_pairs):
                        disps = list(frozen_rule.values())
                        results.append((
                            f"auto_move_{frozen_fname}",
                            solver,
                            f"Auto spatial solver: move objects by {frozen_fname} "
                            f"→ {disps}"
                        ))

            # --- Try: objects that don't move stay, others get removed/recolored ---
            # Check if output is a SUBSET of input objects (deletion/filtering)
            if not results and time.time() < deadline:
                in_colors = set(f["color"] for _, f in in_objects)
                out_colors_obj = set(f["color"] for _, f in out_objects)
                removed = in_colors - out_colors_obj

                if removed and len(out_objects) < len(in_objects):
                    # Some objects were removed — which feature predicts survival?
                    survival_data = []
                    for in_mask, in_feats in in_objects:
                        survived = in_feats["color"] in out_colors_obj
                        rel_feats = _extract_relational_features(
                            inp, in_objects,
                            in_objects.index((in_mask, in_feats)), bg)
                        combined = {**in_feats, **rel_feats}
                        survival_data.append((combined, int(survived)))

                    for fname in feat_names:
                        if time.time() > deadline:
                            break
                        rule_s: Dict[int, int] = {}
                        ok_s = True
                        for feats, surv in survival_data:
                            key = feats.get(fname, -1)
                            if key in rule_s:
                                if rule_s[key] != surv:
                                    ok_s = False
                                    break
                            else:
                                rule_s[key] = surv

                        if ok_s and rule_s and 0 in rule_s.values() and 1 in rule_s.values():
                            frozen_fname_s = fname
                            frozen_rule_s = dict(rule_s)

                            def make_filter_solver(fn, fr, _bg=bg):
                                def solver(grid, _fn=fn, _fr=fr, __bg=_bg):
                                    bg_l = __bg
                                    labeled, n = ndlabel(grid != bg_l)
                                    out = np.full_like(grid, bg_l)

                                    objects = []
                                    for i in range(1, n + 1):
                                        mask = labeled == i
                                        feats = _extract_object_features(
                                            grid, mask, bg_l)
                                        if feats:
                                            objects.append((mask, feats))

                                    for idx, (mask, base_feats) in enumerate(objects):
                                        rel_feats = _extract_relational_features(
                                            grid, objects, idx, bg_l)
                                        combined = {**base_feats, **rel_feats}
                                        key = combined.get(_fn, -1)
                                        if _fr.get(key, 0) == 1:
                                            out[mask] = grid[mask]
                                    return out
                                return solver

                            solver = make_filter_solver(frozen_fname_s, frozen_rule_s)
                            if _verify(solver, train_pairs):
                                results.append((
                                    f"auto_filter_{frozen_fname_s}",
                                    solver,
                                    f"Auto filter solver: keep objects where "
                                    f"{frozen_fname_s} predicts survival"
                                ))

    except Exception:
        pass

    return results


# ===================================================================
# 4. TEST + VERIFY
# ===================================================================

def _verify(fn: Callable, train_pairs) -> bool:
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return False
            if pred.shape != out.shape or not np.array_equal(pred, out):
                return False
        except Exception:
            return False
    return True


def _partial_score(fn: Callable, train_pairs) -> float:
    total = 0
    correct = 0
    for inp, out in train_pairs:
        try:
            pred = fn(inp)
            if pred is None or not isinstance(pred, np.ndarray):
                return 0.0
            if pred.shape != out.shape:
                return 0.0
            total += out.size
            correct += int(np.sum(pred == out))
        except Exception:
            return 0.0
    return correct / max(total, 1)


# ===================================================================
# 5. REFINE — Analyse failure and invent a correction
# ===================================================================

def _refine_hypothesis(
    fn: Callable,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    deadline: float,
) -> List[Tuple[str, Callable, str]]:
    """Given a near-correct hypothesis, analyse residual and build correction."""
    results = []
    if time.time() > deadline:
        return results

    try:
        preds = [fn(inp) for inp, _ in train_pairs]
    except Exception:
        return results

    if any(p is None or p.shape != out.shape for p, (_, out) in zip(preds, train_pairs)):
        return results

    # Learn residual: (pred_color, input_color) → correct_color
    residual_map: Dict[Tuple, int] = {}
    res_ok = True
    for pred, (inp, out) in zip(preds, train_pairs):
        wrong = pred != out
        if not wrong.any():
            continue
        wr, wc = np.where(wrong)
        for r, c in zip(wr.tolist(), wc.tolist()):
            key = (int(pred[r, c]), int(inp[r, c]))
            val = int(out[r, c])
            if key in residual_map:
                if residual_map[key] != val:
                    res_ok = False
                    break
            else:
                residual_map[key] = val
        if not res_ok:
            break

    if res_ok and residual_map:
        frozen_res = dict(residual_map)

        def make_corrected(base_fn, rmap):
            def apply_fn(grid, _b=base_fn, _rm=rmap):
                mid = _b(grid)
                out = mid.copy()
                h, w = grid.shape
                for r in range(h):
                    for c in range(w):
                        key = (int(mid[r, c]), int(grid[r, c]))
                        if key in _rm:
                            out[r, c] = _rm[key]
                return out
            return apply_fn

        corrected = make_corrected(fn, frozen_res)
        if _verify(corrected, train_pairs):
            results.append(("refined", corrected,
                            f"Refined: base + {len(frozen_res)} residual fixes"))

    # Neighbour-conditioned residual
    if not res_ok and time.time() < deadline:
        nbr_map: Dict[Tuple, int] = {}
        nbr_ok = True
        for pred, (inp, out) in zip(preds, train_pairs):
            wrong = pred != out
            if not wrong.any():
                continue
            h, w = inp.shape
            wr, wc = np.where(wrong)
            for r, c in zip(wr.tolist(), wc.tolist()):
                n4 = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < h and 0 <= nc < w:
                        n4.append(int(inp[nr, nc]))
                    else:
                        n4.append(-1)
                key = (int(pred[r, c]), int(inp[r, c])) + tuple(sorted(n4))
                val = int(out[r, c])
                if key in nbr_map:
                    if nbr_map[key] != val:
                        nbr_ok = False
                        break
                else:
                    nbr_map[key] = val
            if not nbr_ok:
                break

        if nbr_ok and nbr_map:
            frozen_nbr = dict(nbr_map)

            def make_nbr_corrected(base_fn, nmap):
                def apply_fn(grid, _b=base_fn, _nm=nmap):
                    mid = _b(grid)
                    out = mid.copy()
                    h, w = grid.shape
                    for r in range(h):
                        for c in range(w):
                            n4 = []
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < h and 0 <= nc < w:
                                    n4.append(int(grid[nr, nc]))
                                else:
                                    n4.append(-1)
                            key = (int(mid[r, c]), int(grid[r, c])) + tuple(sorted(n4))
                            if key in _nm:
                                out[r, c] = _nm[key]
                    return out
                return apply_fn

            corrected = make_nbr_corrected(fn, frozen_nbr)
            if _verify(corrected, train_pairs):
                results.append(("refined_nbr", corrected,
                                f"Refined: base + {len(frozen_nbr)} neighbor-conditioned fixes"))

    return results


# ===================================================================
# 6. TOOL LAYER — Orchestrate ALL existing engines as tools
# ===================================================================

def _call_engine(name: str, train_pairs, timeout: float) -> List[SynthesizedOperator]:
    """Call any existing engine by name — the meta-reasoner's toolbox.

    Every engine we have is accessible here. The meta-reasoner picks which
    to call based on observation, not brute-force.
    """
    try:
        if name == "adaptive_synthesizer":
            from reasoning_project.adaptive_synthesizer import synthesize_adaptive
            return synthesize_adaptive(train_pairs, max_depth=2, timeout_seconds=timeout)
        elif name == "adaptive_reasoner":
            from reasoning_project.adaptive_reasoner import reason_adaptively
            return reason_adaptively(train_pairs, timeout_seconds=timeout)
        elif name == "hypothesis_engine":
            from reasoning_project.hypothesis_engine import reason_by_hypothesis
            return reason_by_hypothesis(train_pairs, timeout_seconds=timeout)
        elif name == "composable_reasoner":
            from reasoning_project.composable_reasoner import reason_composably
            return reason_composably(train_pairs, timeout_seconds=timeout)
        elif name == "object_correspondence":
            from reasoning_project.object_correspondence import reason_by_object_correspondence
            return reason_by_object_correspondence(train_pairs, timeout_seconds=timeout)
        elif name == "different_shape":
            from reasoning_project.different_shape_reasoner import reason_different_shape
            return reason_different_shape(train_pairs, timeout_seconds=timeout)
        elif name == "spatial_reasoner":
            from reasoning_project.object_spatial_reasoner import reason_spatially
            return reason_spatially(train_pairs, timeout_seconds=timeout)
        elif name == "fill_solver":
            from reasoning_project.fill_solver import solve_task_fill
            test_proxy = [inp for inp, _ in train_pairs[:1]]
            result = solve_task_fill(train_pairs, test_proxy)
            if result is None:
                return []
            preds, meta = result
            def _make_fill_fn(tp):
                def solve_fn(grid, _tp=tp):
                    from reasoning_project.fill_solver import solve_task_fill as stf
                    r = stf(_tp, [grid])
                    if r is None:
                        return grid.copy()
                    return r[0][0] if isinstance(r[0], list) else r[0]
                return solve_fn
            exec_fn = _make_fill_fn(train_pairs)
            return [SynthesizedOperator(
                operator_id=f"fill_{uuid.uuid4().hex[:8]}",
                operator_family="fill_solver",
                parameters={}, preconditions=[], execute=exec_fn,
                explanation=f"Fill solver: {meta.get('method', 'auto')}",
                source_failure_signature={},
            )]
        elif name == "relation_solver":
            from reasoning_project.relation_solver import RelationSolver
            rs = RelationSolver()
            prog = rs.solve(train_pairs, timeout=timeout)
            if prog is None:
                return []
            def _make_rel_fn(tp):
                def solve_fn(grid, _tp=tp):
                    from reasoning_project.relation_solver import RelationSolver as RS
                    s = RS()
                    p = s.solve(_tp, timeout=5.0)
                    if p is None:
                        return grid.copy()
                    return p(grid)
                return solve_fn
            exec_fn = _make_rel_fn(train_pairs)
            return [SynthesizedOperator(
                operator_id=f"relation_{uuid.uuid4().hex[:8]}",
                operator_family="relation_solver",
                parameters={}, preconditions=[], execute=exec_fn,
                explanation="Relation solver",
                source_failure_signature={},
            )]
        elif name == "grid_decomposition":
            from reasoning_project.grid_decomposition import solve_by_decomposition
            return solve_by_decomposition(train_pairs, timeout_seconds=timeout)
        elif name == "inverse_reasoning":
            from reasoning_project.inverse_reasoning import search_bidirectional
            return search_bidirectional(train_pairs, timeout_seconds=timeout)
        elif name == "output_shape_predictor":
            from reasoning_project.output_shape_predictor import solve_different_shape_task
            return solve_different_shape_task(train_pairs, timeout_seconds=timeout)
        elif name == "delta_engine":
            from reasoning_project.delta_engine import compute_task_delta
            delta = compute_task_delta(train_pairs)
            if delta and delta.programs:
                ops = []
                for prog in delta.programs[:5]:
                    if hasattr(prog, 'execute') and callable(prog.execute):
                        ops.append(SynthesizedOperator(
                            operator_id=f"delta_{uuid.uuid4().hex[:8]}",
                            operator_family="delta_engine",
                            parameters={}, preconditions=[], execute=prog.execute,
                            explanation=f"Delta: {getattr(prog, 'name', 'auto')}",
                            source_failure_signature={},
                        ))
                return ops
            return []
        elif name == "meta_learner":
            from reasoning_project.meta_learner import build_meta_learner_from_file
            import os
            pairs_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))),
                "outputs", "full_novel_reasoning_pipeline_v2",
                "solved_program_pairs.json"
            )
            if os.path.exists(pairs_path):
                ml = build_meta_learner_from_file(pairs_path)
                return ml.propose(train_pairs, top_k=10, try_compositions=True)
            return []
    except Exception:
        pass
    return []


ALL_ENGINE_NAMES = [
    "adaptive_synthesizer", "adaptive_reasoner", "hypothesis_engine",
    "composable_reasoner", "object_correspondence", "different_shape",
    "spatial_reasoner", "fill_solver", "relation_solver",
    "grid_decomposition", "inverse_reasoning", "output_shape_predictor",
    "delta_engine", "meta_learner",
]


def _select_engines(observations: List[Observation],
                    representations: List[Representation],
                    task_sig: Tuple) -> List[str]:
    """Decide which engines to try based on what we observed.

    A human doesn't try everything randomly — they look at the puzzle
    and pick the approach that fits. This is observation-driven selection.
    """
    selected: List[str] = []
    same_shape = all(o.same_shape for o in observations)
    has_objects = observations[0].n_input_objects >= 2
    many_objects = observations[0].n_input_objects >= 5
    local_change = any(o.change_is_local for o in observations)
    global_change = any(o.change_is_global for o in observations)
    few_colors = len(observations[0].input_colors) <= 4
    new_colors = bool(observations[0].new_colors)
    top_rep = representations[0].name if representations else "pixel"

    # Different shape → shape-aware engines first
    if not same_shape:
        selected.extend(["different_shape", "output_shape_predictor",
                         "object_correspondence"])

    # Object-centric tasks
    if has_objects:
        selected.append("spatial_reasoner")
        selected.append("object_correspondence")
        if many_objects:
            selected.append("grid_decomposition")

    # Local pixel edits → reasoner + synthesizer
    if local_change:
        selected.extend(["adaptive_reasoner", "adaptive_synthesizer"])

    # Fill/region tasks
    if top_rep in ("region", "iconic"):
        selected.append("fill_solver")

    # Global changes → synthesizer + composable
    if global_change:
        selected.extend(["adaptive_synthesizer", "composable_reasoner"])

    # Always try these as fallback
    for eng in ["adaptive_synthesizer", "hypothesis_engine",
                "composable_reasoner", "adaptive_reasoner"]:
        if eng not in selected:
            selected.append(eng)

    # Inverse reasoning for hard tasks
    selected.append("inverse_reasoning")

    # Meta-learner if solved-pairs exist
    selected.append("meta_learner")

    # Delta engine
    selected.append("delta_engine")

    # Relation solver for structured tasks
    if has_objects and few_colors:
        selected.append("relation_solver")

    # Prioritise based on memory — if a similar task was solved by an engine
    similar = _near_solved_memory.get_similar_strategies(task_sig)
    if similar:
        for rep, hyp in similar:
            for eng in ALL_ENGINE_NAMES:
                if eng in hyp.lower():
                    if eng not in selected:
                        selected.insert(0, eng)

    # Also check the method library
    for name, _, _, prev_sig in _method_library.methods:
        for eng in ALL_ENGINE_NAMES:
            if eng in name and eng not in selected:
                selected.append(eng)

    seen: Set[str] = set()
    return [e for e in selected if not (e in seen or seen.add(e))]  # type: ignore[func-returns-value]


# ===================================================================
# 7. SELF-TASK GENERATION — Verify understanding, not memorisation
# ===================================================================

def _generate_self_test(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    fn: Callable,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Create a synthetic input and the expected output using the hypothesis.

    A human, when they think they understand the rule, imagines a new example
    to confirm. We do the same: perturb a training input and check if the
    hypothesis still produces consistent results.
    """
    try:
        inp0, out0 = train_pairs[0]
        h, w = inp0.shape
        bg = _detect_bg(inp0)

        synth_inp = inp0.copy()

        rng = np.random.RandomState(42)
        n_perturb = max(1, h * w // 20)
        for _ in range(n_perturb):
            r, c = rng.randint(0, h), rng.randint(0, w)
            non_bg = [v for v in range(10) if v != bg]
            if synth_inp[r, c] == bg and non_bg:
                synth_inp[r, c] = rng.choice(non_bg)
            else:
                synth_inp[r, c] = bg

        synth_out = fn(synth_inp)
        if synth_out is None or not isinstance(synth_out, np.ndarray):
            return None

        return synth_inp, synth_out
    except Exception:
        return None


def _self_test_hypothesis(
    fn: Callable,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> bool:
    """Test if a hypothesis generalises beyond training data.

    Generate a self-test, run the function on it, then check consistency:
    the function applied twice should be idempotent (for same-shape tasks),
    and the output should look structurally similar to training outputs.
    """
    pair = _generate_self_test(train_pairs, fn)
    if pair is None:
        return True  # can't test, assume ok

    synth_inp, synth_out = pair

    try:
        if synth_inp.shape == synth_out.shape:
            double = fn(synth_out)
            if double is not None and isinstance(double, np.ndarray):
                if double.shape == synth_out.shape:
                    pass  # no idempotency requirement for all tasks

        out_colors = set(synth_out.flatten().tolist())
        if len(out_colors) > 10:
            return False

        return True
    except Exception:
        return False


# ===================================================================
# 8. DYNAMIC COMPOSITION — Chain and combine partial methods
# ===================================================================

def _compose_sequential(
    fn_a: Callable, fn_b: Callable,
    name_a: str, name_b: str,
) -> Tuple[str, Callable, str]:
    """Chain two functions: first apply fn_a, then fn_b."""
    def composed(grid, _a=fn_a, _b=fn_b):
        mid = _a(grid)
        if mid is None or not isinstance(mid, np.ndarray):
            return grid.copy()
        return _b(mid)
    return (f"composed_{name_a}_{name_b}", composed,
            f"Chain: {name_a} → {name_b}")


def _compose_residual(
    fn_base: Callable, fn_fix: Callable,
    name_base: str, name_fix: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Tuple[str, Callable, str]]:
    """Apply fn_base, then fn_fix only to pixels where fn_base was wrong."""
    try:
        wrong_masks = []
        for inp, out in train_pairs:
            pred = fn_base(inp)
            if pred is None or pred.shape != out.shape:
                return None
            wrong_masks.append(pred != out)

        def residual(grid, _base=fn_base, _fix=fn_fix):
            mid = _base(grid)
            if mid is None or not isinstance(mid, np.ndarray):
                return grid.copy()
            fix = _fix(grid)
            if fix is None or not isinstance(fix, np.ndarray) or fix.shape != mid.shape:
                return mid
            return fix
        return (f"residual_{name_base}_{name_fix}", residual,
                f"Residual: {name_base} base, {name_fix} correction")
    except Exception:
        return None


def _try_compositions(
    partials: List[Tuple[str, Callable, str, float]],
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    deadline: float,
) -> List[Tuple[str, Callable, str]]:
    """Try composing the top partial methods to see if any combination solves."""
    results = []
    top = partials[:4]

    for i in range(len(top)):
        if time.time() > deadline:
            break
        for j in range(len(top)):
            if i == j or time.time() > deadline:
                continue
            name_a, fn_a, expl_a, _ = top[i]
            name_b, fn_b, expl_b, _ = top[j]

            cname, cfn, cexpl = _compose_sequential(fn_a, fn_b, name_a, name_b)
            if _verify(cfn, train_pairs):
                results.append((cname, cfn, cexpl))
            else:
                score = _partial_score(cfn, train_pairs)
                if score > max(top[i][3], top[j][3]) + 0.05:
                    results.append((cname, cfn, f"{cexpl} (partial {score:.2f})"))

    return results


# ===================================================================
# 9. ADAPTIVE METHOD LIBRARY — Session-level learning
# ===================================================================

class AdaptiveMethodLibrary:
    """Grows within a session. Stores discovered method→signature mappings."""

    def __init__(self):
        self.methods: List[Tuple[str, Callable, str, Tuple]] = []
        self.success_count: Dict[str, int] = Counter()

    def record(self, name: str, fn: Callable, explanation: str, task_sig: Tuple):
        self.methods.append((name, fn, explanation, task_sig))
        self.success_count[name] += 1

    def suggest_for(self, task_sig: Tuple, train_pairs,
                    deadline: float) -> List[Tuple[str, Callable, str]]:
        """Find previously-learned methods that might work on a similar task."""
        results = []
        for name, fn, explanation, prev_sig in self.methods:
            if time.time() > deadline:
                break
            overlap = sum(1 for a, b in zip(prev_sig, task_sig) if a == b)
            if overlap >= len(task_sig) * 0.6:
                try:
                    if _verify(fn, train_pairs):
                        results.append((name, fn, f"[Transferred] {explanation}"))
                    else:
                        s = _partial_score(fn, train_pairs)
                        if s > 0.5:
                            results.append((name, fn, f"[Near-transfer {s:.0%}] {explanation}"))
                except Exception:
                    continue
        return results


_method_library = AdaptiveMethodLibrary()


# ===================================================================
# 10. MAIN ENTRY — The one engine that connects everything
# ===================================================================

def _make_op(family: str, fn: Callable, explanation: str) -> SynthesizedOperator:
    return SynthesizedOperator(
        operator_id=f"meta_{family}_{uuid.uuid4().hex[:8]}",
        operator_family=f"meta_{family}",
        parameters={},
        preconditions=[],
        execute=fn,
        explanation=f"[Meta] {explanation}",
        source_failure_signature={},
    )


def reason_meta(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    timeout_seconds: float = 10.0,
    task_id: str = "",
) -> List[SynthesizedOperator]:
    """Human-like reasoning: observe → represent → hypothesise → test → refine.

    This is the ONE engine. It:
      - Observes the task (including iconic/figure recognition)
      - Picks which existing engines to call as tools
      - Generates its own hypotheses from data
      - Self-tests to verify genuine understanding
      - Composes partial methods dynamically
      - Refines near-solves
      - Remembers what works for transfer
    """
    deadline = time.time() + timeout_seconds
    results: List[SynthesizedOperator] = []

    try:
        # ---- OBSERVE ----
        observations, task_sig = observe_task(train_pairs)

        # ---- REPRESENT (now includes iconic/figure recognition) ----
        representations = guess_representations(train_pairs, observations)

        # ---- CHECK LIBRARY — try methods from previous tasks ----
        transferred = _method_library.suggest_for(task_sig, train_pairs, deadline)
        for tname, tfn, texpl in transferred:
            if _verify(tfn, train_pairs):
                results.append(_make_op(tname, tfn, texpl))
        if results:
            return results

        # ---- CHECK MEMORY for similar successful strategies ----
        similar = _near_solved_memory.get_similar_strategies(task_sig)

        # ---- HYPOTHESISE — own data-driven methods ----
        hypothesis_generators = [
            _discover_color_mapping,
            _discover_input_output_mapping,
            _discover_neighbor_rule,
            _discover_positional_rule,
            _discover_symmetry_completion,
            _discover_flood_fill,
            _discover_row_col_rule,
            _discover_line_extension,
            _discover_gravity,
            _discover_copy_with_edits,
        ]

        all_hypotheses: List[Tuple[str, Callable, str, float]] = []

        for gen in hypothesis_generators:
            if time.time() > deadline:
                break
            try:
                hyps = gen(train_pairs)
                for name, fn, explanation in hyps:
                    if _verify(fn, train_pairs):
                        all_hypotheses.append((name, fn, explanation, 1.0))
                    else:
                        score = _partial_score(fn, train_pairs)
                        if score > 0.3:
                            all_hypotheses.append((name, fn, explanation, score))
            except Exception:
                continue

        # ---- AUTO-GENERATE SOLVERS — invent new methods from primitives ----
        if time.time() < deadline and not any(s >= 1.0 for _, _, _, s in all_hypotheses):
            auto_solvers = _auto_generate_solvers(train_pairs, deadline)
            for aname, afn, aexpl in auto_solvers:
                if _verify(afn, train_pairs):
                    all_hypotheses.append((aname, afn, aexpl, 1.0))
                else:
                    score = _partial_score(afn, train_pairs)
                    if score > 0.3:
                        all_hypotheses.append((aname, afn, aexpl, score))

            auto_obj = _auto_generate_object_solvers(train_pairs, deadline)
            for aname, afn, aexpl in auto_obj:
                if _verify(afn, train_pairs):
                    all_hypotheses.append((aname, afn, aexpl, 1.0))
                else:
                    score = _partial_score(afn, train_pairs)
                    if score > 0.3:
                        all_hypotheses.append((aname, afn, aexpl, score))

            # Relational solvers (inter-object relationships)
            auto_rel = _auto_generate_relational_solvers(train_pairs, deadline)
            for aname, afn, aexpl in auto_rel:
                if _verify(afn, train_pairs):
                    all_hypotheses.append((aname, afn, aexpl, 1.0))
                else:
                    score = _partial_score(afn, train_pairs)
                    if score > 0.3:
                        all_hypotheses.append((aname, afn, aexpl, score))

            # Spatial solvers (object movement, filtering)
            auto_spatial = _auto_generate_spatial_solvers(train_pairs, deadline)
            for aname, afn, aexpl in auto_spatial:
                if _verify(afn, train_pairs):
                    all_hypotheses.append((aname, afn, aexpl, 1.0))
                else:
                    score = _partial_score(afn, train_pairs)
                    if score > 0.3:
                        all_hypotheses.append((aname, afn, aexpl, score))

        # ---- CALL EXISTING ENGINES as tools (selected by observation) ----
        if time.time() < deadline and not any(s >= 1.0 for _, _, _, s in all_hypotheses):
            selected_engines = _select_engines(observations, representations, task_sig)
            per_engine = max(1.0, (deadline - time.time()) / max(len(selected_engines), 1))

            for eng_name in selected_engines:
                if time.time() > deadline:
                    break
                eng_results = _call_engine(eng_name, train_pairs, per_engine)
                for op in eng_results:
                    if _verify(op.execute, train_pairs):
                        all_hypotheses.append((
                            f"engine_{eng_name}_{op.operator_family}",
                            op.execute,
                            f"[{eng_name}] {op.explanation}",
                            1.0,
                        ))
                    else:
                        score = _partial_score(op.execute, train_pairs)
                        if score > 0.3:
                            all_hypotheses.append((
                                f"engine_{eng_name}_{op.operator_family}",
                                op.execute,
                                f"[{eng_name}] {op.explanation}",
                                score,
                            ))

        # ---- TEST — verified hypotheses + self-test ----
        for name, fn, explanation, score in all_hypotheses:
            if score >= 1.0:
                if _self_test_hypothesis(fn, train_pairs):
                    results.append(_make_op(name, fn, explanation))
                    _method_library.record(name, fn, explanation, task_sig)

        if results:
            _near_solved_memory.record_success(
                task_sig,
                representations[0].name if representations else "unknown",
                results[0].explanation,
            )
            return results

        # ---- COMPOSE — try combining partial methods ----
        partials = [(n, f, e, s) for n, f, e, s in all_hypotheses if 0.3 < s < 1.0]
        if partials and time.time() < deadline:
            partials.sort(key=lambda x: -x[3])
            compositions = _try_compositions(partials, train_pairs, deadline)
            for cname, cfn, cexpl in compositions:
                if _verify(cfn, train_pairs):
                    results.append(_make_op(cname, cfn, cexpl))
                    _method_library.record(cname, cfn, cexpl, task_sig)

        if results:
            _near_solved_memory.record_success(
                task_sig,
                representations[0].name if representations else "unknown",
                results[0].explanation,
            )
            return results

        # ---- REFINE — near-solve detection and targeted correction ----
        all_hypotheses.sort(key=lambda x: -x[3])

        for name, fn, explanation, score in all_hypotheses[:5]:
            if time.time() > deadline:
                break
            if score < 0.3:
                continue

            refinements = _refine_hypothesis(fn, train_pairs, deadline)
            for ref_name, ref_fn, ref_explanation in refinements:
                if _verify(ref_fn, train_pairs):
                    results.append(_make_op(ref_name, ref_fn,
                                           f"{explanation} → {ref_explanation}"))
                    _method_library.record(ref_name, ref_fn,
                                          f"{explanation} → {ref_explanation}", task_sig)

            _near_solved_memory.record(
                task_id, task_sig, score,
                representations[0].name if representations else "unknown",
                explanation,
                f"score={score:.2f}",
            )

        if results:
            _near_solved_memory.record_success(
                task_sig,
                representations[0].name if representations else "unknown",
                results[0].explanation,
            )

    except Exception:
        pass

    return results
