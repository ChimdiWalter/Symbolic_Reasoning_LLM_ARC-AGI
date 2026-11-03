"""The four image operations CAST needs, in pure numpy, with scipy used as an accelerator when it imports.

    label(mask, structure)          connected components (labels 1..n), 4- or 8-connectivity from a 3x3 structure
    binary_dilation(mask, structure) dilation by a 3x3 structure, cells outside the grid count as False
    binary_fill_holes(mask)         mask plus every background cell not 4-connected to the border
    components_from_edges(n, a, b)  connected components of an undirected graph given as edge arrays
Callers never depend on label numbering (objects are sorted afterwards), so both backends give identical results;
tests/test_pkg.py checks the two backends against each other. Set CAST_FORCE_NUMPY=1 to disable scipy.
"""
import os

import numpy as np

_SCIPY = None
if os.environ.get("CAST_FORCE_NUMPY") != "1":
    try:                                                     # optional accelerator
        from scipy import ndimage as _sn
        from scipy.sparse import coo_matrix as _coo
        from scipy.sparse.csgraph import connected_components as _cc
        _SCIPY = True
    except Exception:                                        # noqa: BLE001
        _SCIPY = None


def _offsets(structure):
    s = np.asarray(structure, dtype=bool)
    return [(dr - 1, dc - 1) for dr in range(3) for dc in range(3) if s[dr, dc] and (dr, dc) != (1, 1)]


def label(mask, structure=None):
    mask = np.asarray(mask, dtype=bool)
    if structure is None:
        structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    if _SCIPY:
        return _sn.label(mask, structure=structure)
    H, W = mask.shape
    lab = np.zeros((H, W), dtype=np.int32)
    offs = _offsets(structure)
    n = 0
    for r0 in range(H):
        for c0 in range(W):
            if not mask[r0, c0] or lab[r0, c0]:
                continue
            n += 1
            lab[r0, c0] = n
            stack = [(r0, c0)]
            while stack:
                r, c = stack.pop()
                for dr, dc in offs:
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < H and 0 <= cc < W and mask[rr, cc] and not lab[rr, cc]:
                        lab[rr, cc] = n
                        stack.append((rr, cc))
    return lab, n


def binary_dilation(mask, structure=None):
    mask = np.asarray(mask, dtype=bool)
    if structure is None:
        structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    if _SCIPY:
        return _sn.binary_dilation(mask, structure=structure)
    out = mask.copy()
    H, W = mask.shape
    for dr, dc in _offsets(structure):
        sh = np.zeros_like(mask)
        r0, r1 = max(0, dr), min(H, H + dr)
        c0, c1 = max(0, dc), min(W, W + dc)
        sh[r0:r1, c0:c1] = mask[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
        out |= sh
    return out


def binary_fill_holes(mask):
    mask = np.asarray(mask, dtype=bool)
    if _SCIPY:
        return _sn.binary_fill_holes(mask)
    comp = ~mask
    lab, n = label(comp)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist()) - {0}
    holes = comp & ~np.isin(lab, list(border))
    return mask | holes


def components_from_edges(n, rows, cols):
    rows, cols = np.asarray(rows), np.asarray(cols)
    if _SCIPY:
        g = _coo((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n, n))
        return _cc(g, directed=False)
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in zip(rows.tolist(), cols.tolist()):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    roots = np.array([find(i) for i in range(n)])
    _, lab = np.unique(roots, return_inverse=True)
    return int(lab.max()) + 1 if n else 0, lab
