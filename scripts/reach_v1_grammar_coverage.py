"""Which generic growth relations explain the memorized instances?
(development, the 60 training-development tasks; no target is read)

  python scripts/reach_v1_grammar_coverage.py  -> outputs/reach_v1/grammar_coverage.json

An instance is one object the native engine memorized with the constant
`pattern` growth: input object cells O (with colours), output object cells,
the input grid G. Added cells A = output minus input. A candidate relation
R(O, G; params) returns a cell set; it explains a task only if ONE parameter
setting reproduces A exactly for EVERY instance of the task, with a colour
rule that is one of: a single colour for the whole task, the object's own
colour, or (for copies) the copied cells' colours. Families are generic
functions of the object and the scene; none reads a task id or an output.
"""
import itertools
import json
import os
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "reach_v1")
BG = 0


def bbox(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), max(rs), min(cs), max(cs)


def window_fill(O, G, k):
    """background cells covered by k x k all-background windows inside bbox(O)"""
    r0, r1, c0, c1 = bbox(O)
    out = set()
    for r in range(r0, r1 - k + 2):
        for c in range(c0, c1 - k + 2):
            win = G[r:r + k, c:c + k]
            if win.shape == (k, k) and (win == BG).all():
                out |= {(r + i, c + j) for i in range(k) for j in range(k)}
    return out


def empty_square(O, G, k):
    """background 4-connected regions inside bbox(O) that are exactly k x k squares"""
    r0, r1, c0, c1 = bbox(O)
    seen, out = set(), set()
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if G[r, c] != BG or (r, c) in seen:
                continue
            comp, stack = set(), [(r, c)]
            while stack:
                x = stack.pop()
                if x in comp or not (r0 <= x[0] <= r1 and c0 <= x[1] <= c1) or G[x] != BG:
                    continue
                comp.add(x)
                stack += [(x[0] + 1, x[1]), (x[0] - 1, x[1]), (x[0], x[1] + 1), (x[0], x[1] - 1)]
            seen |= comp
            if len(comp) == k * k:
                rs = [y for y, _ in comp]
                cs = [z for _, z in comp]
                if max(rs) - min(rs) == k - 1 and max(cs) - min(cs) == k - 1:
                    out |= comp
    return out


def bbox_fill(O, G):
    r0, r1, c0, c1 = bbox(O)
    return {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if G[r, c] == BG and (r, c) not in O}


def bbox_ring(O, G):
    r0, r1, c0, c1 = bbox(O)
    H, W = G.shape
    out = set()
    for r in range(r0 - 1, r1 + 2):
        for c in range(c0 - 1, c1 + 2):
            if (r in (r0 - 1, r1 + 1) or c in (c0 - 1, c1 + 1)) and 0 <= r < H and 0 <= c < W and G[r, c] == BG:
                out.add((r, c))
    return out


def band(O, G, axis):
    r0, r1, c0, c1 = bbox(O)
    H, W = G.shape
    rows = set(range(r0, r1 + 1)) if axis in ("rows", "cross") else set()
    cols = set(range(c0, c1 + 1)) if axis in ("cols", "cross") else set()
    return {(r, c) for r in range(H) for c in range(W)
            if (r in rows or c in cols) and G[r, c] == BG and (r, c) not in O}


def dilate(O, G, m):
    H, W = G.shape
    out = set()
    for r in range(H):
        for c in range(W):
            if G[r, c] != BG or (r, c) in O:
                continue
            n = sum((r + dr, c + dc) in O for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)
            if n >= m:
                out.add((r, c))
    return out


def connect(O, G):
    """background cells strictly between two object cells on one row or column, with only background between"""
    out = set()
    by_row, by_col = {}, {}
    for r, c in O:
        by_row.setdefault(r, []).append(c)
        by_col.setdefault(c, []).append(r)
    for r, cs in by_row.items():
        cs.sort()
        for a, b in zip(cs, cs[1:]):
            seg = [(r, c) for c in range(a + 1, b)]
            if seg and all(G[x] == BG for x in seg):
                out |= set(seg)
    for c, rs in by_col.items():
        rs.sort()
        for a, b in zip(rs, rs[1:]):
            seg = [(r, c) for r in range(a + 1, b)]
            if seg and all(G[x] == BG for x in seg):
                out |= set(seg)
    return out


def copies(O, G, dr, dc, until_border):
    H, W = G.shape
    out = set()
    k = 1
    while True:
        moved = {(r + k * dr, c + k * dc) for r, c in O}
        inside = {x for x in moved if 0 <= x[0] < H and 0 <= x[1] < W}
        if not inside:
            break
        out |= inside - O
        if not until_border:
            break
        k += 1
        if k > 30:
            break
    return out


def families(O, G):
    """(family, params, predicted added cells) for every bounded setting."""
    for k in (2, 3, 4, 5):
        yield "window_fill", (k,), window_fill(O, G, k)
        yield "empty_square", (k,), empty_square(O, G, k)
    yield "bbox_fill", (), bbox_fill(O, G)
    yield "bbox_ring", (), bbox_ring(O, G)
    for ax in ("rows", "cols", "cross"):
        yield "band", (ax,), band(O, G, ax)
    for m in (1, 2, 3, 4):
        yield "dilate", (m,), dilate(O, G, m)
    yield "connect", (), connect(O, G)
    r0, r1, c0, c1 = bbox(O)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    for ub in (False, True):
        for sr, sc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            for gap in (0, 1):
                yield "copies_bbox", (sr, sc, gap, ub), copies(O, G, sr * (h + gap), sc * (w + gap), ub)
        for dr, dc in itertools.product(range(-4, 5), repeat=2):
            if (dr, dc) != (0, 0):
                yield "copies_offset", (dr, dc, ub), copies(O, G, dr, dc, ub)


def colour_rule(inst_list, family):
    """the colour rules every instance satisfies (task-level)."""
    rules = None
    for O, colours, A, G in inst_list:
        ok = set()
        cols = set(A.values())
        if len(cols) == 1:
            ok.add(("const", next(iter(cols))))
            if cols == set(colours.values()) and len(set(colours.values())) == 1:
                ok.add(("object",))
        rules = ok if rules is None else rules & ok
    return rules or set()


def main():
    src = os.path.join(OUT, os.environ.get("REACH_INSTANCES_DIR", "instances2"))
    files = sorted(os.listdir(src))
    cover, per_task = Counter(), {}
    for f in files:
        inst = json.load(open(os.path.join(src, f)))["instances"]
        groups = {}
        for i in inst:
            if i.get("grid") is None:
                continue
            G = np.asarray(i["grid"])
            O = {tuple(c): col for c, col in i["in"]}
            out = {tuple(c): col for c, col in i["out"]}
            A = {c: col for c, col in out.items() if c not in O}
            groups.setdefault(str(i.get("variant")), []).append((set(O), O, A, G))
        if not groups:
            per_task[f[:-5]] = {"instances": 0}
            continue
        found = {}
        for variant, insts in sorted(groups.items()):
            preds = [{(fam, params): pred for fam, params, pred in families(O, G)} for O, _c, _A, G in insts]
            for (fam, params), pred in preds[0].items():
                if fam in found or not pred or pred != set(insts[0][2]):
                    continue
                if all(preds[i].get((fam, params)) == set(insts[i][2]) for i in range(1, len(insts))) \
                        and colour_rule(insts, fam):
                    found[fam] = [variant, len(insts)] + list(map(str, params))
        per_task[f[:-5]] = {"instances": sum(len(v) for v in groups.values()), "variants": sorted(groups),
                            "explained_by": found}
        for fam in found:
            cover[fam] += 1
    tasks_with = sum(1 for v in per_task.values() if v.get("instances"))
    any_cov = sum(1 for v in per_task.values() if v.get("explained_by"))
    out = {"tasks_with_instances": tasks_with, "tasks_explained_by_any": any_cov,
           "coverage_by_family": dict(cover.most_common()), "per_task": per_task}
    with open(os.path.join(OUT, "grammar_coverage.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("tasks_with_instances", "tasks_explained_by_any", "coverage_by_family")}))


if __name__ == "__main__":
    main()
