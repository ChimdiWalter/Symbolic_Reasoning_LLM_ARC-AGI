"""G-rep v0: the representation grammar of records/CORA_REP_GROWTH_PLAN_20261013.md, section 2.

A representation program maps a grid to a partition of its non-background
cells:
- bases:
  - comp4_same, comp8_same, comp4_any, comp8_any: connected components,
    the equivalents of S1-S4;
  - layer: one group per colour, the equivalent of S6;
  - prox2: Chebyshev distance at most 2, transitively, the equivalent of S7;
- then up to two operators:
  - split: split each group into its colour classes;
  - merge(r): merge groups related by r, with transitive closure;
- relations r: same_colour, same_shape, same_size, bbox_overlap,
  bbox_contains, same_row, same_col, near3, near4.

Programs:
- (b,), (b, split), (b, merge r), (b, split, merge r), and
  (b, merge r1, merge r2) with r1 before r2;
- 6 x 56 = 336 programs, enumerated in canonical order: fewest operators
  first, then base order, then relation order.
"""
import numpy as np
from scipy import ndimage

BASES = ("comp4_same", "comp8_same", "comp4_any", "comp8_any", "layer", "prox2")
RELATIONS = ("same_colour", "same_shape", "same_size", "bbox_overlap", "bbox_contains", "same_row", "same_col", "near3", "near4")
_S4 = ndimage.generate_binary_structure(2, 1)
_S8 = ndimage.generate_binary_structure(2, 2)


def programs():
    out = [(b,) for b in BASES]
    out += [(b, "split") for b in BASES]
    out += [(b, ("merge", r)) for b in BASES for r in RELATIONS]
    out += [(b, "split", ("merge", r)) for b in BASES for r in RELATIONS]
    out += [(b, ("merge", r1), ("merge", r2)) for b in BASES for i, r1 in enumerate(RELATIONS) for r2 in RELATIONS[i + 1:]]
    return out


def name(prog):
    return "/".join(p if isinstance(p, str) else f"merge:{p[1]}" for p in prog)


def _label_groups(mask, structure):
    lab, n = ndimage.label(mask, structure=structure)
    return [frozenset(zip(*map(lambda a: a.tolist(), np.nonzero(lab == i)))) for i in range(1, n + 1)]


def base_groups(base, g, bg=0):
    fg = g != bg
    if base in ("comp4_same", "comp8_same"):
        st = _S4 if base == "comp4_same" else _S8
        return [grp for c in sorted(set(g[fg].tolist())) for grp in _label_groups(g == c, st)]
    if base in ("comp4_any", "comp8_any"):
        return _label_groups(fg, _S4 if base == "comp4_any" else _S8)
    if base == "layer":
        return [frozenset(zip(*map(lambda a: a.tolist(), np.nonzero(g == c)))) for c in sorted(set(g[fg].tolist()))]
    if base == "prox2":
        dil = ndimage.binary_dilation(fg, structure=_S8)
        lab, n = ndimage.label(dil, structure=_S8)
        return [frozenset((int(r), int(c)) for r, c in zip(*np.nonzero((lab == i) & fg))) for i in range(1, n + 1)
                if ((lab == i) & fg).any()]
    raise ValueError(base)


def _bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), min(cs), max(rs), max(cs)


def _shape_key(cells):
    r0, c0, _, _ = _bbox(cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def related(rel, a, b, g):
    if rel == "same_colour":
        return {int(g[x]) for x in a} == {int(g[x]) for x in b}
    if rel == "same_shape":
        return _shape_key(a) == _shape_key(b)
    if rel == "same_size":
        return len(a) == len(b)
    ra, rb = _bbox(a), _bbox(b)
    if rel == "bbox_overlap":
        return not (ra[2] < rb[0] or rb[2] < ra[0] or ra[3] < rb[1] or rb[3] < ra[1])
    if rel == "bbox_contains":
        inside = lambda p, q: p[0] <= q[0] and p[1] <= q[1] and p[2] >= q[2] and p[3] >= q[3]
        return inside(ra, rb) or inside(rb, ra)
    if rel == "same_row":
        return bool({r for r, _ in a} & {r for r, _ in b})
    if rel == "same_col":
        return bool({c for _, c in a} & {c for _, c in b})
    if rel in ("near3", "near4"):
        k = 3 if rel == "near3" else 4
        return any(max(abs(r1 - r2), abs(c1 - c2)) <= k for r1, c1 in a for r2, c2 in b)
    raise ValueError(rel)


def merge(groups, rel, g):
    parent = list(range(len(groups)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            if find(i) != find(j) and related(rel, groups[i], groups[j], g):
                parent[find(j)] = find(i)
    out = {}
    for i, grp in enumerate(groups):
        out.setdefault(find(i), set()).update(grp)
    return [frozenset(v) for v in out.values()]


def split(groups, g):
    out = []
    for grp in groups:
        for c in sorted({int(g[x]) for x in grp}):
            out.append(frozenset(x for x in grp if int(g[x]) == c))
    return out


def apply(prog, g, bg=0):
    """The partition of grid g (numpy) as a list of cell sets, sorted by first cell."""
    groups = base_groups(prog[0], g, bg)
    for op in prog[1:]:
        groups = split(groups, g) if op == "split" else merge(groups, op[1], g)
    return sorted(groups, key=lambda s: min(s))


def partition_key(groups):
    return frozenset(groups)
