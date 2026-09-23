"""Adaptive Structural Reasoning Suite — Cross-Domain Benchmark Generator.

Generates synthetic tasks across multiple domains to test adaptive reasoning:
    1. Concept Recombination — unseen combinations of atomic concepts
    2. Counterfactual Reasoning — invariance/sensitivity to interventions
    3. OOD Scaling — larger grids, more objects, new colors
    4. Graph Transformations — node/edge structural rules
    5. Chess-Like Board Puzzles — piece-based relational rules
    6. Molecule-Like Graph Tasks — ring/chain/functional-group reasoning
    7. Circuit-Like Layouts — series/parallel/connected component rules
    8. Memory Curriculum — staged concept exposure for memory growth

Each generator produces (input, output) pairs in the appropriate domain format.
"""
from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class BenchmarkTask:
    """A synthetic benchmark task with metadata."""
    task_id: str
    domain: str
    concept: str
    train_pairs: List[Tuple[Any, Any]]
    test_pairs: List[Tuple[Any, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# GRID TASK GENERATORS (ARC-style)
# ═══════════════════════════════════════════════════════════════════════════

class GridTaskGenerator:
    """Generate ARC-style grid tasks for concept testing."""

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng(42)

    def _random_grid(
        self, h: int = 10, w: int = 10, n_objects: int = 3,
        colors: Optional[List[int]] = None,
        distinct_sizes: bool = False,
        distinct_colors: bool = True,
        filled: bool = True,
        size_specs: Optional[List[Tuple[int, int]]] = None,
    ) -> Tuple[np.ndarray, List[Dict]]:
        """Create a random grid with non-overlapping objects.

        Parameters
        ----------
        size_specs : optional list of (height, width) tuples
            If provided, each object is created with the given dimensions.
            This guarantees clearly distinct sizes when needed.
        """
        grid = np.zeros((h, w), dtype=int)
        color_pool = list(colors or [1, 2, 3, 4, 5, 6, 7, 8])
        self.rng.shuffle(color_pool)
        objects = []
        used_sizes: set = set()
        color_idx = 0

        for obj_idx in range(n_objects):
            placed = False
            for _retry in range(80):
                if size_specs is not None and obj_idx < len(size_specs):
                    oh, ow = size_specs[obj_idx]
                else:
                    oh = int(self.rng.integers(2, max(3, h // 3) + 1))
                    ow = int(self.rng.integers(2, max(3, w // 3) + 1))
                if filled:
                    shape = np.ones((oh, ow), dtype=bool)
                else:
                    shape = self.rng.random((oh, ow)) > 0.3
                    shape[0, :] = True
                    shape[-1, :] = True
                    shape[:, 0] = True
                    shape[:, -1] = True
                sz = int(shape.sum())
                if distinct_sizes and sz in used_sizes:
                    if size_specs is not None:
                        # size_specs should already guarantee distinct areas;
                        # skip the check so we don't loop forever
                        pass
                    else:
                        continue
                for attempt in range(30):
                    r = int(self.rng.integers(0, h - oh))
                    c = int(self.rng.integers(0, w - ow))
                    region = grid[r:r+oh, c:c+ow]
                    if region.sum() == 0:
                        if distinct_colors and color_idx < len(color_pool):
                            color = color_pool[color_idx]
                            color_idx += 1
                        else:
                            color = int(self.rng.choice(color_pool))
                        grid[r:r+oh, c:c+ow][shape] = color
                        mask = np.zeros((h, w), dtype=bool)
                        mask[r:r+oh, c:c+ow] = shape
                        objects.append({
                            'mask': mask, 'color': color,
                            'size': sz,
                            'bbox': (r, c, r + oh - 1, c + ow - 1),
                            'r': r, 'c': c, 'h': oh, 'w': ow,
                            'is_hollow': not shape.all(),
                        })
                        used_sizes.add(sz)
                        placed = True
                        break
                if placed:
                    break

        return grid, objects

    def _make_hollow(self, mask: np.ndarray) -> np.ndarray:
        """Make an object hollow by removing interior pixels."""
        result = mask.copy()
        ys, xs = np.where(mask)
        if len(ys) == 0:
            return result
        sub = mask[ys.min():ys.max()+1, xs.min():xs.max()+1].copy()
        if sub.shape[0] > 2 and sub.shape[1] > 2:
            sub[1:-1, 1:-1] = False
            result[ys.min():ys.max()+1, xs.min():xs.max()+1] = sub
        return result

    # --- Atomic concept generators ---

    def generate_keep_largest(self, n_examples: int = 4, _depth: int = 0) -> BenchmarkTask:
        # Pre-defined size specs: first object is always the largest (4x4),
        # remaining objects are clearly smaller (2x2, 1x1 or 2x1, 1x2).
        _SIZE_POOLS = [
            [(4, 4), (2, 2), (1, 1)],
            [(4, 3), (2, 2), (1, 2)],
            [(3, 4), (2, 1), (1, 3)],
            [(4, 4), (3, 2), (2, 1), (1, 1)],
        ]
        pairs = []
        for _ in range(n_examples * 10):
            specs = list(_SIZE_POOLS[int(self.rng.integers(0, len(_SIZE_POOLS)))])
            self.rng.shuffle(specs)
            grid, objs = self._random_grid(
                h=14, w=14, n_objects=len(specs),
                distinct_sizes=True, size_specs=specs,
            )
            if len(objs) < 2:
                continue
            largest = max(objs, key=lambda o: o['size'])
            out = np.zeros_like(grid)
            out[largest['mask']] = largest['color']
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            if _depth >= 5:
                raise RuntimeError("Cannot generate keep_largest tasks")
            return self.generate_keep_largest(n_examples, _depth + 1)

        return BenchmarkTask(
            task_id='synth_keep_largest',
            domain='grid',
            concept='largest',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_keep_smallest(self, n_examples: int = 4, _depth: int = 0) -> BenchmarkTask:
        # Pre-defined size specs: objects have clearly distinct sizes.
        # The smallest (1x1 or 1x2) must be unique.
        _SIZE_POOLS = [
            [(4, 4), (3, 2), (1, 1)],
            [(3, 3), (2, 3), (1, 2)],
            [(4, 3), (2, 2), (1, 1)],
            [(4, 4), (3, 2), (2, 1), (1, 1)],
        ]
        pairs = []
        for _ in range(n_examples * 10):
            specs = list(_SIZE_POOLS[int(self.rng.integers(0, len(_SIZE_POOLS)))])
            self.rng.shuffle(specs)
            grid, objs = self._random_grid(
                h=14, w=14, n_objects=len(specs),
                distinct_sizes=True, size_specs=specs,
            )
            if len(objs) < 2:
                continue
            smallest = min(objs, key=lambda o: o['size'])
            out = np.zeros_like(grid)
            out[smallest['mask']] = smallest['color']
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            if _depth >= 5:
                raise RuntimeError("Cannot generate keep_smallest tasks")
            return self.generate_keep_smallest(n_examples, _depth + 1)

        return BenchmarkTask(
            task_id='synth_keep_smallest',
            domain='grid',
            concept='smallest',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_keep_hollow(self, n_examples: int = 4) -> BenchmarkTask:
        pairs = []
        for _ in range(n_examples * 5):
            grid = np.zeros((12, 12), dtype=int)
            objs = []
            colors = [1, 2, 3, 4, 5, 6]
            self.rng.shuffle(colors)

            n_hollow = int(self.rng.integers(2, 4))
            n_solid = int(self.rng.integers(2, 4))

            for idx in range(n_hollow + n_solid):
                oh = int(self.rng.integers(3, 5))
                ow = int(self.rng.integers(3, 5))
                is_hollow = idx < n_hollow
                for attempt in range(30):
                    r = int(self.rng.integers(0, 12 - oh))
                    c = int(self.rng.integers(0, 12 - ow))
                    if grid[r:r+oh, c:c+ow].sum() == 0:
                        mask = np.zeros((12, 12), dtype=bool)
                        mask[r:r+oh, c:c+ow] = True
                        if is_hollow:
                            mask[r+1:r+oh-1, c+1:c+ow-1] = False
                        color = colors[idx % len(colors)]
                        grid[mask] = color
                        objs.append({
                            'mask': mask, 'color': color,
                            'size': int(mask.sum()),
                            'is_hollow': is_hollow,
                        })
                        break

            hollow_objs = [o for o in objs if o['is_hollow']]
            solid_objs = [o for o in objs if not o['is_hollow']]
            if len(hollow_objs) < 2 or len(solid_objs) < 2:
                continue
            out = np.zeros_like(grid)
            for o in hollow_objs:
                out[o['mask']] = o['color']
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            if hasattr(self, '_hollow_depth') and self._hollow_depth >= 5:
                raise RuntimeError("Cannot generate keep_hollow tasks")
            self._hollow_depth = getattr(self, '_hollow_depth', 0) + 1
            result = self.generate_keep_hollow(n_examples)
            self._hollow_depth = 0
            return result

        return BenchmarkTask(
            task_id='synth_keep_hollow',
            domain='grid',
            concept='hollow',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_recolor_by_size(self, n_examples: int = 4, _depth: int = 0) -> BenchmarkTask:
        # Pre-defined size specs with 3+ clearly distinct sizes for
        # deterministic size-rank recoloring.
        _SIZE_POOLS = [
            [(4, 4), (3, 2), (1, 1)],
            [(4, 3), (2, 2), (1, 2)],
            [(4, 4), (3, 2), (2, 1), (1, 1)],
            [(3, 4), (2, 3), (1, 1)],
        ]
        pairs = []
        for _ in range(n_examples * 10):
            specs = list(_SIZE_POOLS[int(self.rng.integers(0, len(_SIZE_POOLS)))])
            self.rng.shuffle(specs)
            grid, objs = self._random_grid(
                h=14, w=14, n_objects=len(specs),
                distinct_sizes=True, size_specs=specs,
            )
            if len(objs) < 2:
                continue
            out = grid.copy()
            sorted_objs = sorted(objs, key=lambda o: o['size'])
            color_map = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
            for rank, o in enumerate(sorted_objs):
                new_color = color_map.get(rank, rank + 1)
                out[o['mask']] = new_color
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            if _depth >= 5:
                raise RuntimeError("Cannot generate recolor_by_size tasks")
            return self.generate_recolor_by_size(n_examples, _depth + 1)

        return BenchmarkTask(
            task_id='synth_recolor_by_size',
            domain='grid',
            concept='size_rank_recolor',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    # --- Compound concept generators (recombination) ---

    def generate_keep_largest_hollow(self, n_examples: int = 4) -> BenchmarkTask:
        """Unseen combination: largest AND hollow."""
        pairs = []
        for _ in range(n_examples * 3):
            grid = np.zeros((12, 12), dtype=int)
            objs = []
            colors = list(range(1, 7))
            self.rng.shuffle(colors)

            sizes = sorted(self.rng.integers(3, 6, size=4), reverse=True)
            for idx, sz in enumerate(sizes):
                for attempt in range(30):
                    r = self.rng.integers(0, 12 - sz)
                    c = self.rng.integers(0, 12 - sz)
                    if grid[r:r+sz, c:c+sz].sum() == 0:
                        mask = np.zeros((12, 12), dtype=bool)
                        mask[r:r+sz, c:c+sz] = True
                        is_hollow = idx in (0, 2)
                        if is_hollow and sz > 2:
                            mask[r+1:r+sz-1, c+1:c+sz-1] = False
                        color = colors[idx % len(colors)]
                        grid[mask] = color
                        objs.append({
                            'mask': mask, 'color': color,
                            'size': int(mask.sum()),
                            'is_hollow': is_hollow,
                            'raw_size': sz,
                        })
                        break

            hollow_objs = [o for o in objs if o['is_hollow']]
            if not hollow_objs:
                continue
            target = max(hollow_objs, key=lambda o: o['raw_size'])
            out = np.zeros_like(grid)
            out[target['mask']] = target['color']
            pairs.append((grid, out))

            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_keep_largest_hollow(n_examples)

        return BenchmarkTask(
            task_id='synth_keep_largest_hollow',
            domain='grid',
            concept='largest_AND_hollow',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
            metadata={'recombination': True, 'atomic_concepts': ['largest', 'hollow']},
        )

    def generate_keep_touching_boundary(self, n_examples: int = 4) -> BenchmarkTask:
        """Keep objects touching the grid boundary, breaking size confound.

        Explicitly places some objects at the boundary and others in the
        interior so the ``touches_boundary`` property is always
        discriminative.
        """
        H, W = 10, 10
        pairs = []
        for _ in range(n_examples * 20):
            grid = np.zeros((H, W), dtype=int)
            objs: List[Dict] = []
            color_pool = list(range(1, 9))
            self.rng.shuffle(color_pool)
            ci = 0

            # Place 2 boundary-touching objects --------------------------------
            n_boundary = int(self.rng.integers(2, 4))
            for _ in range(n_boundary):
                oh = int(self.rng.integers(2, 4))
                ow = int(self.rng.integers(2, 4))
                edge = int(self.rng.integers(0, 4))  # 0=top 1=bottom 2=left 3=right
                placed = False
                for _att in range(30):
                    if edge == 0:
                        r, c = 0, int(self.rng.integers(0, W - ow))
                    elif edge == 1:
                        r, c = H - oh, int(self.rng.integers(0, W - ow))
                    elif edge == 2:
                        r, c = int(self.rng.integers(0, H - oh)), 0
                    else:
                        r, c = int(self.rng.integers(0, H - oh)), W - ow
                    if grid[r:r+oh, c:c+ow].sum() == 0:
                        color = color_pool[ci % len(color_pool)]; ci += 1
                        grid[r:r+oh, c:c+ow] = color
                        mask = np.zeros((H, W), dtype=bool)
                        mask[r:r+oh, c:c+ow] = True
                        objs.append({'mask': mask, 'color': color,
                                     'size': int(mask.sum()), 'touching': True})
                        placed = True
                        break
                    edge = int(self.rng.integers(0, 4))

            # Place 2 interior-only objects (never touching border) ------------
            n_interior = int(self.rng.integers(2, 4))
            for _ in range(n_interior):
                oh = int(self.rng.integers(2, 4))
                ow = int(self.rng.integers(2, 4))
                placed = False
                for _att in range(40):
                    r = int(self.rng.integers(1, H - oh))
                    c = int(self.rng.integers(1, W - ow))
                    if r + oh > H - 1:
                        continue
                    if c + ow > W - 1:
                        continue
                    if grid[r:r+oh, c:c+ow].sum() == 0:
                        color = color_pool[ci % len(color_pool)]; ci += 1
                        grid[r:r+oh, c:c+ow] = color
                        mask = np.zeros((H, W), dtype=bool)
                        mask[r:r+oh, c:c+ow] = True
                        objs.append({'mask': mask, 'color': color,
                                     'size': int(mask.sum()), 'touching': False})
                        placed = True
                        break

            touching = [o for o in objs if o['touching']]
            non_touching = [o for o in objs if not o['touching']]
            if len(touching) < 2 or len(non_touching) < 1:
                continue

            # Break size confound: require at least one non-touching obj
            # smaller than a touching obj (so "large" is not the rule).
            touching_sizes = [o['size'] for o in touching]
            non_touching_sizes = [o['size'] for o in non_touching]
            if min(non_touching_sizes) >= max(touching_sizes):
                continue

            out = np.zeros_like(grid)
            for o in touching:
                out[o['mask']] = o['color']
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_keep_touching_boundary(n_examples)

        return BenchmarkTask(
            task_id='synth_keep_touching_boundary',
            domain='grid',
            concept='touches_border',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    # --- Additional recombination generators ---

    def generate_keep_smallest_touching(self, n_examples: int = 4) -> BenchmarkTask:
        """Unseen combination: smallest AND touches boundary.

        Places objects with explicit boundary/interior control and
        clearly distinct sizes so the conjunction is unambiguous.
        """
        H, W = 10, 10
        pairs = []
        for _ in range(n_examples * 20):
            grid = np.zeros((H, W), dtype=int)
            objs: List[Dict] = []
            color_pool = list(range(1, 9))
            self.rng.shuffle(color_pool)
            ci = 0

            # Boundary-touching objects with distinct sizes -------------------
            boundary_specs = [(1, 2), (2, 2), (3, 2)]
            self.rng.shuffle(boundary_specs)
            for oh, ow in boundary_specs:
                edge = int(self.rng.integers(0, 4))
                placed = False
                for _att in range(30):
                    if edge == 0:
                        r, c = 0, int(self.rng.integers(0, W - ow))
                    elif edge == 1:
                        r, c = H - oh, int(self.rng.integers(0, W - ow))
                    elif edge == 2:
                        r, c = int(self.rng.integers(0, H - oh)), 0
                    else:
                        r, c = int(self.rng.integers(0, H - oh)), W - ow
                    if grid[r:r+oh, c:c+ow].sum() == 0:
                        color = color_pool[ci % len(color_pool)]; ci += 1
                        grid[r:r+oh, c:c+ow] = color
                        mask = np.zeros((H, W), dtype=bool)
                        mask[r:r+oh, c:c+ow] = True
                        objs.append({'mask': mask, 'color': color,
                                     'size': oh * ow, 'touching': True})
                        placed = True
                        break
                    edge = int(self.rng.integers(0, 4))

            # Interior objects ------------------------------------------------
            interior_specs = [(2, 3), (3, 3)]
            self.rng.shuffle(interior_specs)
            for oh, ow in interior_specs:
                placed = False
                for _att in range(40):
                    r = int(self.rng.integers(1, H - oh))
                    c = int(self.rng.integers(1, W - ow))
                    if r + oh > H - 1 or c + ow > W - 1:
                        continue
                    if grid[r:r+oh, c:c+ow].sum() == 0:
                        color = color_pool[ci % len(color_pool)]; ci += 1
                        grid[r:r+oh, c:c+ow] = color
                        mask = np.zeros((H, W), dtype=bool)
                        mask[r:r+oh, c:c+ow] = True
                        objs.append({'mask': mask, 'color': color,
                                     'size': oh * ow, 'touching': False})
                        placed = True
                        break

            touching = [o for o in objs if o['touching']]
            non_touching = [o for o in objs if not o['touching']]
            if len(touching) < 2 or not non_touching:
                continue
            target = min(touching, key=lambda o: o['size'])
            out = np.zeros_like(grid)
            out[target['mask']] = target['color']
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_keep_smallest_touching(n_examples)

        return BenchmarkTask(
            task_id='synth_keep_smallest_touching',
            domain='grid',
            concept='smallest_AND_touches_border',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
            metadata={'recombination': True, 'atomic_concepts': ['smallest', 'touches_border']},
        )

    def generate_keep_hollow_not_largest(self, n_examples: int = 4) -> BenchmarkTask:
        """Unseen combination: hollow AND NOT largest."""
        pairs = []
        for _ in range(n_examples * 10):
            grid = np.zeros((12, 12), dtype=int)
            objs = []
            colors = list(range(1, 8))
            self.rng.shuffle(colors)

            sizes = sorted(self.rng.integers(3, 6, size=5), reverse=True)
            for idx, sz in enumerate(sizes):
                is_hollow = idx in (1, 3)
                for attempt in range(30):
                    r = int(self.rng.integers(0, 12 - sz))
                    c = int(self.rng.integers(0, 12 - sz))
                    if grid[r:r+sz, c:c+sz].sum() == 0:
                        mask = np.zeros((12, 12), dtype=bool)
                        mask[r:r+sz, c:c+sz] = True
                        if is_hollow and sz > 2:
                            mask[r+1:r+sz-1, c+1:c+sz-1] = False
                        color = colors[idx % len(colors)]
                        grid[mask] = color
                        objs.append({
                            'mask': mask, 'color': color,
                            'size': int(mask.sum()),
                            'is_hollow': is_hollow,
                            'raw_size': sz,
                        })
                        break

            if len(objs) < 3:
                continue
            hollow = [o for o in objs if o['is_hollow']]
            if not hollow:
                continue
            largest = max(objs, key=lambda o: o['raw_size'])
            targets = [o for o in hollow if o is not largest]
            if not targets:
                continue
            out = np.zeros_like(grid)
            for o in targets:
                out[o['mask']] = o['color']
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_keep_hollow_not_largest(n_examples)

        return BenchmarkTask(
            task_id='synth_keep_hollow_not_largest',
            domain='grid',
            concept='hollow_AND_NOT_largest',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
            metadata={'recombination': True, 'atomic_concepts': ['hollow', 'largest']},
        )

    def generate_recolor_boundary_objects(self, n_examples: int = 4) -> BenchmarkTask:
        """Unseen combination: recolor (not filter) + touches boundary.

        Explicitly places boundary and interior objects to guarantee
        the ``touches_boundary`` property is discriminative.
        """
        H, W = 10, 10
        pairs = []
        for _ in range(n_examples * 20):
            grid = np.zeros((H, W), dtype=int)
            objs: List[Dict] = []
            color_pool = [1, 2, 3, 4]
            self.rng.shuffle(color_pool)
            ci = 0

            # Boundary objects -----------------------------------------------
            n_boundary = int(self.rng.integers(2, 4))
            for _ in range(n_boundary):
                oh = int(self.rng.integers(2, 4))
                ow = int(self.rng.integers(2, 4))
                edge = int(self.rng.integers(0, 4))
                placed = False
                for _att in range(30):
                    if edge == 0:
                        r, c = 0, int(self.rng.integers(0, W - ow))
                    elif edge == 1:
                        r, c = H - oh, int(self.rng.integers(0, W - ow))
                    elif edge == 2:
                        r, c = int(self.rng.integers(0, H - oh)), 0
                    else:
                        r, c = int(self.rng.integers(0, H - oh)), W - ow
                    if grid[r:r+oh, c:c+ow].sum() == 0:
                        color = color_pool[ci % len(color_pool)]; ci += 1
                        grid[r:r+oh, c:c+ow] = color
                        mask = np.zeros((H, W), dtype=bool)
                        mask[r:r+oh, c:c+ow] = True
                        objs.append({'mask': mask, 'color': color,
                                     'touching': True})
                        placed = True
                        break
                    edge = int(self.rng.integers(0, 4))

            # Interior objects -----------------------------------------------
            n_interior = int(self.rng.integers(2, 4))
            for _ in range(n_interior):
                oh = int(self.rng.integers(2, 4))
                ow = int(self.rng.integers(2, 4))
                placed = False
                for _att in range(40):
                    r = int(self.rng.integers(1, H - oh))
                    c = int(self.rng.integers(1, W - ow))
                    if r + oh > H - 1 or c + ow > W - 1:
                        continue
                    if grid[r:r+oh, c:c+ow].sum() == 0:
                        color = color_pool[ci % len(color_pool)]; ci += 1
                        grid[r:r+oh, c:c+ow] = color
                        mask = np.zeros((H, W), dtype=bool)
                        mask[r:r+oh, c:c+ow] = True
                        objs.append({'mask': mask, 'color': color,
                                     'touching': False})
                        placed = True
                        break

            touching = [o for o in objs if o['touching']]
            non_touching = [o for o in objs if not o['touching']]
            if not touching or not non_touching:
                continue
            out = grid.copy()
            for o in touching:
                out[o['mask']] = 7
            if np.array_equal(grid, out):
                continue
            pairs.append((grid, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_recolor_boundary_objects(n_examples)

        return BenchmarkTask(
            task_id='synth_recolor_boundary',
            domain='grid',
            concept='recolor_IF_touches_border',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
            metadata={'recombination': True, 'atomic_concepts': ['recolor', 'touches_border']},
        )

    # --- Counterfactual generators ---

    def generate_counterfactual_variants(
        self, base_task: BenchmarkTask,
    ) -> List[BenchmarkTask]:
        """Create counterfactual variants of a base task."""
        variants = []

        cf_pairs = []
        for inp, out in base_task.train_pairs:
            new_inp = self._swap_irrelevant_color(inp, out)
            if new_inp is not None:
                cf_pairs.append((new_inp, out))
        if cf_pairs:
            variants.append(BenchmarkTask(
                task_id=f"{base_task.task_id}_cf_color",
                domain=base_task.domain,
                concept=f"{base_task.concept}_cf_irrelevant_color",
                train_pairs=cf_pairs,
                test_pairs=base_task.test_pairs,
                metadata={'counterfactual': True, 'intervention': 'irrelevant_color'},
            ))

        scaled_pairs = []
        for inp, out in base_task.train_pairs:
            new_inp, new_out = self._scale_grid(inp, out, factor=2)
            if new_inp is not None:
                scaled_pairs.append((new_inp, new_out))
        if scaled_pairs:
            variants.append(BenchmarkTask(
                task_id=f"{base_task.task_id}_ood_scale",
                domain=base_task.domain,
                concept=f"{base_task.concept}_ood_scale2x",
                train_pairs=scaled_pairs,
                test_pairs=[(self._scale_grid(t[0], t[1], 2)) for t in base_task.test_pairs],
                metadata={'ood': True, 'intervention': 'scale_2x'},
            ))

        return variants

    def _swap_irrelevant_color(
        self, inp: np.ndarray, out: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Change a color that doesn't appear in the output."""
        inp_colors = set(inp.flatten().tolist()) - {0}
        out_colors = set(out.flatten().tolist()) - {0}
        irrelevant = inp_colors - out_colors
        if not irrelevant:
            return None
        old_c = min(irrelevant)
        used = inp_colors | out_colors | {0}
        new_c = None
        for c in range(1, 10):
            if c not in used:
                new_c = c
                break
        if new_c is None:
            return None
        result = inp.copy()
        result[result == old_c] = new_c
        return result

    def _scale_grid(
        self, inp: np.ndarray, out: np.ndarray, factor: int = 2,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Scale grid up by repeating pixels."""
        new_inp = np.repeat(np.repeat(inp, factor, axis=0), factor, axis=1)
        new_out = np.repeat(np.repeat(out, factor, axis=0), factor, axis=1)
        return new_inp, new_out


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH TASK GENERATORS
# ═══════════════════════════════════════════════════════════════════════════

class GraphTaskGenerator:
    """Generate graph transformation tasks."""

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng(42)

    def _random_graph(
        self, n_nodes: int = 6, edge_prob: float = 0.3,
        labels: Optional[List] = None,
    ) -> Dict:
        labels = labels or list(range(1, 5))
        nodes = [{'index': i, 'label': int(self.rng.choice(labels)),
                  'color': int(self.rng.choice(labels))}
                 for i in range(n_nodes)]

        edges = []
        for i in range(n_nodes):
            for j in range(i + 1, n_nodes):
                if self.rng.random() < edge_prob:
                    edges.append({'source': i, 'target': j, 'type': 'edge'})

        for node in nodes:
            degree = sum(1 for e in edges
                         if e['source'] == node['index'] or e['target'] == node['index'])
            node['degree'] = degree

        return {'nodes': nodes, 'edges': edges}

    def generate_keep_high_degree(self, n_examples: int = 4) -> BenchmarkTask:
        """Keep nodes with degree >= 3."""
        pairs = []
        for _ in range(n_examples * 3):
            g = self._random_graph(n_nodes=self.rng.integers(5, 9), edge_prob=0.4)
            kept = [n for n in g['nodes'] if n['degree'] >= 3]
            removed = [n for n in g['nodes'] if n['degree'] < 3]
            if not kept or not removed:
                continue
            kept_idx = {n['index'] for n in kept}
            out_edges = [e for e in g['edges']
                         if e['source'] in kept_idx and e['target'] in kept_idx]
            out = {'nodes': kept, 'edges': out_edges}
            pairs.append((g, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_keep_high_degree(n_examples)

        return BenchmarkTask(
            task_id='synth_graph_keep_high_degree',
            domain='graph',
            concept='high_degree',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_recolor_by_degree(self, n_examples: int = 4) -> BenchmarkTask:
        """Recolor nodes: leaves→1, others→2, hubs→3."""
        pairs = []
        for _ in range(n_examples * 3):
            g = self._random_graph(n_nodes=self.rng.integers(5, 9), edge_prob=0.4)
            out = {'nodes': [], 'edges': list(g['edges'])}
            has_variation = set()
            for n in g['nodes']:
                new_node = dict(n)
                if n['degree'] <= 1:
                    new_node['label'] = 1
                    has_variation.add('leaf')
                elif n['degree'] >= 3:
                    new_node['label'] = 3
                    has_variation.add('hub')
                else:
                    new_node['label'] = 2
                    has_variation.add('mid')
                new_node['color'] = new_node['label']
                out['nodes'].append(new_node)
            if len(has_variation) < 2:
                continue
            pairs.append((g, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_recolor_by_degree(n_examples)

        return BenchmarkTask(
            task_id='synth_graph_recolor_by_degree',
            domain='graph',
            concept='degree_recolor',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_remove_isolated(self, n_examples: int = 4) -> BenchmarkTask:
        """Remove isolated nodes (degree 0)."""
        pairs = []
        for _ in range(n_examples * 3):
            g = self._random_graph(n_nodes=self.rng.integers(5, 9), edge_prob=0.25)
            kept = [n for n in g['nodes'] if n['degree'] > 0]
            removed = [n for n in g['nodes'] if n['degree'] == 0]
            if not removed or not kept:
                continue
            kept_idx = {n['index'] for n in kept}
            out_edges = [e for e in g['edges']
                         if e['source'] in kept_idx and e['target'] in kept_idx]
            out = {'nodes': kept, 'edges': out_edges}
            pairs.append((g, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_remove_isolated(n_examples)

        return BenchmarkTask(
            task_id='synth_graph_remove_isolated',
            domain='graph',
            concept='remove_isolated',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )


# ═══════════════════════════════════════════════════════════════════════════
# CHESS-LIKE BOARD TASK GENERATORS
# ═══════════════════════════════════════════════════════════════════════════

class ChessBoardTaskGenerator:
    """Generate chess-like board puzzle tasks."""

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng(42)

    def _random_board(
        self, size: int = 8, n_pieces: int = 5,
        piece_types: Optional[List[int]] = None,
    ) -> np.ndarray:
        piece_types = piece_types or [1, 2, 3]
        board = np.zeros((size, size), dtype=int)
        for _ in range(n_pieces):
            for attempt in range(20):
                r = self.rng.integers(0, size)
                c = self.rng.integers(0, size)
                if board[r, c] == 0:
                    board[r, c] = int(self.rng.choice(piece_types))
                    break
        return board

    def generate_remove_edge_pieces(self, n_examples: int = 4) -> BenchmarkTask:
        """Remove pieces on the board edge."""
        pairs = []
        for _ in range(n_examples * 3):
            board = self._random_board(size=6, n_pieces=self.rng.integers(4, 8))
            h, w = board.shape
            out = board.copy()
            edge_mask = np.zeros_like(board, dtype=bool)
            edge_mask[0, :] = True
            edge_mask[-1, :] = True
            edge_mask[:, 0] = True
            edge_mask[:, -1] = True
            has_edge = (board[edge_mask] > 0).any()
            has_interior = (board[~edge_mask] > 0).any()
            if not has_edge or not has_interior:
                continue
            out[edge_mask] = 0
            pairs.append((board, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_remove_edge_pieces(n_examples)

        return BenchmarkTask(
            task_id='synth_chess_remove_edge',
            domain='board',
            concept='remove_edge_pieces',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_keep_attacked_pieces(self, n_examples: int = 4) -> BenchmarkTask:
        """Keep pieces that share a row or column with another piece."""
        pairs = []
        for _ in range(n_examples * 3):
            board = self._random_board(size=6, n_pieces=self.rng.integers(4, 8))
            out = np.zeros_like(board)
            positions = list(zip(*np.where(board > 0)))
            attacked = set()
            for r, c in positions:
                for r2, c2 in positions:
                    if (r, c) != (r2, c2) and (r == r2 or c == c2):
                        attacked.add((r, c))
            if not attacked or len(attacked) == len(positions):
                continue
            for r, c in attacked:
                out[r, c] = board[r, c]
            pairs.append((board, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_keep_attacked_pieces(n_examples)

        return BenchmarkTask(
            task_id='synth_chess_keep_attacked',
            domain='board',
            concept='attacked_pieces',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_promote_boundary(self, n_examples: int = 4) -> BenchmarkTask:
        """Pieces on top row get recolored (promoted)."""
        pairs = []
        for _ in range(n_examples * 3):
            board = self._random_board(size=6, n_pieces=self.rng.integers(4, 8),
                                        piece_types=[1, 2])
            if not (board[0, :] > 0).any():
                continue
            out = board.copy()
            mask = (out[0, :] > 0)
            out[0, mask] = 3
            if np.array_equal(board, out):
                continue
            pairs.append((board, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_promote_boundary(n_examples)

        return BenchmarkTask(
            task_id='synth_chess_promote_boundary',
            domain='board',
            concept='boundary_promotion',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )


# ═══════════════════════════════════════════════════════════════════════════
# MOLECULE-LIKE GRAPH TASK GENERATORS
# ═══════════════════════════════════════════════════════════════════════════

class MoleculeTaskGenerator:
    """Generate molecule-like graph transformation tasks."""

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng(42)

    def _random_molecule(
        self, n_atoms: int = 8, ring_prob: float = 0.3,
    ) -> Dict:
        atom_types = ['C', 'N', 'O', 'S']
        atoms = []
        for i in range(n_atoms):
            atoms.append({
                'index': i,
                'label': self.rng.choice(atom_types),
                'color': {'C': 1, 'N': 2, 'O': 3, 'S': 4}[self.rng.choice(atom_types)],
            })

        bonds = []
        for i in range(n_atoms - 1):
            bonds.append({
                'source': i, 'target': i + 1,
                'type': 'single',
            })

        if self.rng.random() < ring_prob and n_atoms >= 4:
            ring_size = min(self.rng.integers(3, 7), n_atoms)
            start = self.rng.integers(0, max(1, n_atoms - ring_size))
            bonds.append({
                'source': start, 'target': start + ring_size - 1,
                'type': 'single',
            })

        for atom in atoms:
            degree = sum(1 for b in bonds
                         if b['source'] == atom['index'] or b['target'] == atom['index'])
            atom['degree'] = degree

        adj = {i: set() for i in range(n_atoms)}
        for b in bonds:
            adj[b['source']].add(b['target'])
            adj[b['target']].add(b['source'])
        for atom in atoms:
            atom['_neighbors'] = adj[atom['index']]

        return {'nodes': atoms, 'edges': bonds}

    def _is_in_ring(self, mol: Dict, node_idx: int) -> bool:
        nodes = mol['nodes']
        edges = mol['edges']
        adj = {n['index']: set() for n in nodes}
        for e in edges:
            adj[e['source']].add(e['target'])
            adj[e['target']].add(e['source'])

        visited = set()
        def dfs(current, parent, target, depth):
            if depth > 8:
                return False
            if current == target and depth > 0:
                return True
            visited.add(current)
            for nb in adj[current]:
                if nb == parent and depth == 1:
                    continue
                if nb not in visited or (nb == target and depth > 1):
                    if dfs(nb, current, target, depth + 1):
                        return True
            visited.discard(current)
            return False

        return dfs(node_idx, -1, node_idx, 0)

    def generate_keep_ring_atoms(self, n_examples: int = 4) -> BenchmarkTask:
        """Keep only atoms that are part of a ring."""
        pairs = []
        for _ in range(n_examples * 5):
            mol = self._random_molecule(n_atoms=self.rng.integers(6, 10), ring_prob=0.8)
            ring_atoms = [n for n in mol['nodes'] if self._is_in_ring(mol, n['index'])]
            non_ring = [n for n in mol['nodes'] if not self._is_in_ring(mol, n['index'])]
            if not ring_atoms or not non_ring:
                continue
            ring_idx = {n['index'] for n in ring_atoms}
            out_edges = [e for e in mol['edges']
                         if e['source'] in ring_idx and e['target'] in ring_idx]
            out = {'nodes': ring_atoms, 'edges': out_edges}
            pairs.append((mol, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_keep_ring_atoms(n_examples)

        return BenchmarkTask(
            task_id='synth_mol_keep_ring',
            domain='molecule',
            concept='ring_membership',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )

    def generate_recolor_terminal(self, n_examples: int = 4) -> BenchmarkTask:
        """Recolor terminal atoms (degree 1) to label 5."""
        pairs = []
        for _ in range(n_examples * 3):
            mol = self._random_molecule(n_atoms=self.rng.integers(5, 9))
            has_terminal = any(n['degree'] == 1 for n in mol['nodes'])
            has_nonterminal = any(n['degree'] > 1 for n in mol['nodes'])
            if not has_terminal or not has_nonterminal:
                continue
            import copy as _copy
            out = _copy.deepcopy(mol)
            for n in out['nodes']:
                n.pop('_neighbors', None)
            for n in out['nodes']:
                if n['degree'] == 1:
                    n['label'] = 'X'
                    n['color'] = 5
            pairs.append((mol, out))
            if len(pairs) >= n_examples:
                break

        if len(pairs) < 4:
            return self.generate_recolor_terminal(n_examples)

        return BenchmarkTask(
            task_id='synth_mol_recolor_terminal',
            domain='molecule',
            concept='terminal_recolor',
            train_pairs=pairs[:-1],
            test_pairs=pairs[-1:],
        )


# ═══════════════════════════════════════════════════════════════════════════
# BENCHMARK SUITE BUILDER
# ═══════════════════════════════════════════════════════════════════════════

class AdaptiveReasoningSuite:
    """Build the full cross-domain benchmark suite."""

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.grid_gen = GridTaskGenerator(self.rng)
        self.graph_gen = GraphTaskGenerator(self.rng)
        self.chess_gen = ChessBoardTaskGenerator(self.rng)
        self.mol_gen = MoleculeTaskGenerator(self.rng)

    def build_all(self) -> Dict[str, List[BenchmarkTask]]:
        suite = {}

        suite['atomic_grid'] = [
            self.grid_gen.generate_keep_largest(),
            self.grid_gen.generate_keep_smallest(),
            self.grid_gen.generate_keep_hollow(),
            self.grid_gen.generate_recolor_by_size(),
            self.grid_gen.generate_keep_touching_boundary(),
        ]

        suite['recombination'] = [
            self.grid_gen.generate_keep_largest_hollow(),
            self.grid_gen.generate_keep_smallest_touching(),
            self.grid_gen.generate_keep_hollow_not_largest(),
            self.grid_gen.generate_recolor_boundary_objects(),
        ]

        base_tasks = suite['atomic_grid']
        cf_tasks = []
        for t in base_tasks:
            cf_tasks.extend(self.grid_gen.generate_counterfactual_variants(t))
        suite['counterfactual'] = cf_tasks

        suite['graph'] = [
            self.graph_gen.generate_keep_high_degree(),
            self.graph_gen.generate_recolor_by_degree(),
            self.graph_gen.generate_remove_isolated(),
        ]

        suite['chess'] = [
            self.chess_gen.generate_remove_edge_pieces(),
            self.chess_gen.generate_keep_attacked_pieces(),
            self.chess_gen.generate_promote_boundary(),
        ]

        suite['molecule'] = [
            self.mol_gen.generate_keep_ring_atoms(),
            self.mol_gen.generate_recolor_terminal(),
        ]

        return suite

    def summary(self, suite: Dict[str, List[BenchmarkTask]]) -> str:
        lines = ['Adaptive Structural Reasoning Suite']
        lines.append('=' * 40)
        total = 0
        for category, tasks in suite.items():
            lines.append(f"  {category}: {len(tasks)} tasks")
            for t in tasks:
                lines.append(f"    {t.task_id} [{t.concept}] "
                             f"train={len(t.train_pairs)} test={len(t.test_pairs)}")
            total += len(tasks)
        lines.append(f"  TOTAL: {total} tasks across {len(suite)} categories")
        return '\n'.join(lines)
