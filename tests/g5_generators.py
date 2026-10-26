"""DEV-style task generators for rule-language version 5 tests (scenes and truth programs; no evaluation data)."""
import numpy as np
from cora_neural_v2.rast import N
from cora_neural_v2g5 import program as P5

T = lambda f, c, v: N("test", (f, c, v))
TRUE = N("true", ())


def free(g, r0, r1, c0, c1, pad=1):
    h, w = g.shape
    return r0 >= 0 and c0 >= 0 and r1 < h and c1 < w and not g[max(0, r0 - pad):r1 + 1 + pad, max(0, c0 - pad):c1 + 1 + pad].any()


def scene_plus_and_dots(rng):
    g = np.zeros((12, 12), dtype=int)
    r, c = int(rng.integers(1, 10)), int(rng.integers(1, 10))
    for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        g[r + dr, c + dc] = 3
    k = 0
    for _ in range(40):
        rr, cc = int(rng.integers(1, 11)), int(rng.integers(1, 11))
        if free(g, rr - 1, rr + 1, cc - 1, cc + 1, pad=1):
            g[rr, cc] = int(rng.choice([2, 4, 6]))
            k += 1
        if k == 3:
            break
    return g if k >= 2 else None


def scene_dots_wall(rng):
    g = np.zeros((10, 12), dtype=int)
    wc = int(rng.integers(6, 11))
    g[:, wc] = 5
    rows = rng.choice(range(10), size=3, replace=False)
    for r in rows:
        g[int(r), int(rng.integers(0, wc - 2))] = int(rng.choice([2, 4]))
    return g


def scene_dot_pairs(rng):
    g = np.zeros((11, 11), dtype=int)
    for col in (2, 4):
        for _ in range(20):
            if rng.random() < 0.5:
                r = int(rng.integers(0, 11)); c1, c2 = sorted(rng.choice(range(11), size=2, replace=False))
                if c2 - c1 >= 3 and not g[r].any():
                    g[r, c1] = g[r, c2] = col
                    break
            else:
                c = int(rng.integers(0, 11)); r1, r2 = sorted(rng.choice(range(11), size=2, replace=False))
                if r2 - r1 >= 3 and not g[:, c].any():
                    g[r1, c] = g[r2, c] = col
                    break
    return g if (g > 0).sum() >= 4 else None


def scene_bars_box(rng):
    g = np.zeros((12, 12), dtype=int)
    for _ in range(2):
        h, w = int(rng.integers(3, 6)), int(rng.integers(3, 6))
        r, c = int(rng.integers(0, 12 - h - 1)), int(rng.integers(0, 12 - w - 1))
        if not free(g, r, r + h + 1, c, c + w + 1, pad=1):
            continue
        col = int(rng.choice([1, 2, 6]))
        g[r, c + 1:c + w + 1] = col                      # four separate bars around a hole
        g[r + h + 1, c + 1:c + w + 1] = col
        g[r + 1:r + h + 1, c] = col
        g[r + 1:r + h + 1, c + w + 1] = col
    return g if g.any() else None


CASES = {
    "stamp_plus_at_dots": (P5.make("S1", None, [P5.StampRule(T("size", "==", 5), T("size", "==", 1), "object", "centre", "anchor")]), scene_plus_and_dots),
    "ray_hits_wall": (P5.make("S1", None, [P5.Ray2Rule(T("size", "==", 1), ((0, 1),), "stop", "cell", "own")]), scene_dots_wall),
    "segments_between_pairs": (P5.make("S1", None, [P5.SegmentRule(TRUE, "hv", "own")]), scene_dot_pairs),
    "fill_enclosed_by_bars": (P5.make("S1", None, [P5.FillRule(TRUE, "enclosed", 8)]), scene_bars_box),
}


def make_task(prog, scene, seed, n=3):
    rng = np.random.default_rng(seed)
    pairs = []
    for _ in range(600):
        g = scene(rng)
        if g is None:
            continue
        out = P5.execute(prog, g.tolist())
        if out is None or np.array_equal(out, g):
            continue
        pairs.append((g.tolist(), out.tolist()))
        if len(pairs) == n + 1:
            break
    if len(pairs) < n + 1:
        return None, None
    return {"train": pairs[:n], "test_inputs": [pairs[n][0]]}, np.asarray(pairs[n][1])
