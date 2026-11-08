"""The combined search objective of a candidate on the demonstrations (lower is better; 0 = every demonstration
reproduced). Demonstrations only.

Per demonstration d, from the candidate's output O, the input A and the expected output B:
- no output: r = 1;
- wrong output shape: r = 0.8 + 0.2 * shape distance (relative height and width error, averaged);
- right shape: r = 0.6 * changed-cell error + 0.4 * object residual, at least 0.01 unless O == B;
  * changed-cell error = wrong cells / ACTIVE cells, where ACTIVE = cells that must change (A != B) or that the
    candidate changed (O != A); when the shape differs from the input's, ACTIVE = cells that are not background in
    B or in O. The unchanged background is therefore never in the denominator: the identity program scores 1, not
    "97% of cells right";
  * object residual = 1 - 2 |objects of O that equal an object of B| / (|objects of O| + |objects of B|), objects
    being 4-connected single-colour components of non-background cells (background = B's most common colour).
score = mean of r over demonstrations. `exact` (demonstrations reproduced) and the components are kept too.
"""
import numpy as np


def _mode(G):
    vals, counts = np.unique(G, return_counts=True)
    return int(vals[int(np.argmax(counts))])


def objects4(G, bg):
    """{(colour, frozenset(cells))}: 4-connected single-colour components of the cells that are not bg."""
    G = np.asarray(G)
    h, w = G.shape
    seen = np.zeros(G.shape, dtype=bool)
    out = set()
    for r in range(h):
        for c in range(w):
            if seen[r, c] or G[r, c] == bg:
                continue
            col = G[r, c]
            stack, cells = [(r, c)], []
            seen[r, c] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= yy < h and 0 <= xx < w and not seen[yy, xx] and G[yy, xx] == col:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
            out.add((int(col), frozenset(cells)))
    return out


def demo_residual(a, b, o):
    A, B = np.asarray(a), np.asarray(b)
    if o is None:
        return {"exact": False, "shape_ok": False, "r": 1.0, "cc": None, "obj": None, "shape": 1.0}
    O = np.asarray(o)
    if O.ndim != 2 or O.shape != B.shape:
        if O.ndim != 2 or O.size == 0:
            return {"exact": False, "shape_ok": False, "r": 1.0, "cc": None, "obj": None, "shape": 1.0}
        dh = abs(O.shape[0] - B.shape[0]) / max(O.shape[0], B.shape[0])
        dw = abs(O.shape[1] - B.shape[1]) / max(O.shape[1], B.shape[1])
        s = (dh + dw) / 2
        return {"exact": False, "shape_ok": False, "r": 0.8 + 0.2 * s, "cc": None, "obj": None, "shape": s}
    wrong = O != B
    if not wrong.any():
        return {"exact": True, "shape_ok": True, "r": 0.0, "cc": 0.0, "obj": 0.0, "shape": 0.0}
    if A.shape == B.shape:
        active = (A != B) | (O != A)
    else:
        bg = _mode(B)
        active = (B != bg) | (O != bg)
    cc = float((wrong & active).sum()) / max(1, int(active.sum()))
    bg = _mode(B)
    ob, oo = objects4(B, bg), objects4(O, bg)
    obj = 0.0 if not ob and not oo else 1.0 - 2.0 * len(ob & oo) / (len(ob) + len(oo))
    r = max(0.01, 0.6 * cc + 0.4 * obj)
    return {"exact": False, "shape_ok": True, "r": r, "cc": cc, "obj": obj, "shape": 0.0}


def score(task, ex):
    """{"score", "exact", "shape_ok", "n", "cc", "obj", "per_demo"} of an Execution record (an invalid program or one
    without outputs scores 1 on every demonstration; FITS scores 0)."""
    train = task["train"]
    n = len(train)
    outs = getattr(ex, "outs", None)
    if ex.status == "FITS":
        return {"score": 0.0, "exact": n, "shape_ok": n, "n": n, "cc": 0.0, "obj": 0.0, "per_demo": [0.0] * n}
    if outs is None or len(outs) != n:
        return {"score": 1.0, "exact": 0, "shape_ok": 0, "n": n, "cc": None, "obj": None, "per_demo": [1.0] * n}
    rows = [demo_residual(a, b, o) for (a, b), o in zip(train, outs)]
    ccs = [r["cc"] for r in rows if r["cc"] is not None]
    objs = [r["obj"] for r in rows if r["obj"] is not None]
    return {"score": round(sum(r["r"] for r in rows) / n, 6), "exact": sum(r["exact"] for r in rows),
            "shape_ok": sum(r["shape_ok"] for r in rows), "n": n,
            "cc": round(sum(ccs) / len(ccs), 6) if ccs else None,
            "obj": round(sum(objs) / len(objs), 6) if objs else None,
            "per_demo": [round(r["r"], 6) for r in rows]}


def rank_key(obj):
    """Sort key: lower score first, then more demonstrations reproduced exactly."""
    return (obj["score"], -obj["exact"])


__all__ = ["score", "rank_key", "demo_residual", "objects4"]
