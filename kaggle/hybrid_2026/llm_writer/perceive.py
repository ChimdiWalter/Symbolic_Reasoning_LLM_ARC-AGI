"""What the writer is shown about a puzzle: the demonstration grids, the test inputs, and CORA's own perception of
them (objects of one segmentation view and what happens to each object in the output).

Everything here reads demonstrations and test inputs only. The perception is CORA's (native segmentation,
`cora_neural_v2g3.scene` fates); it is identical in every arm, so it cannot explain a difference between arms.

The view shown is chosen from the demonstrations alone: the view whose objects' fates (recoloured, moved, deleted,
unchanged) explain the largest share of the changed cells, ties to the lower view number.
"""
import numpy as np

from cora_neural_v2g3 import scene as SC

VIEW_TEXT = {"S1": "same colour, 4-connected", "S2": "same colour, 8-connected (diagonal cells join)",
             "S3": "any non-background colours, 4-connected", "S4": "any non-background colours, 8-connected",
             "S5": "same colour, 4-connected, background = most common colour", "S6": "one object per colour",
             "S7": "nearby cells of any colour grouped"}
VIEWS = tuple(VIEW_TEXT)
MAX_OBJECTS = 12


def grid_text(g, sep=""):
    """Rows of digits, one row per line (`sep` between cells: '' for tokenizers that split digits, ' ' otherwise)."""
    return "\n".join(sep.join(str(int(v)) for v in row) for row in np.asarray(g))


def _box(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), min(cs), max(rs), max(cs)


def explained_share(train, view):
    """Share of changed cells lying on objects whose fate is recoloured, moved or deleted (0 if shapes change)."""
    sc = SC.analyse(train, view)
    if sc is None:
        return 0.0
    changed = expl = 0
    for (a, b), objs in zip(train, sc.objects):
        A, B = np.asarray(a), np.asarray(b)
        diff = A != B
        changed += int(diff.sum())
        for o in objs:
            if o.fate in ("recoloured", "moved", "deleted"):
                expl += sum(bool(diff[x]) for x in o.cells)
    return expl / changed if changed else 0.0


def choose_view(train):
    best, score = "S1", -1.0
    for v in VIEWS:
        try:
            s = explained_share(train, v)
        except Exception:                                  # noqa: BLE001 (a view native cannot segment)
            continue
        if s > score + 1e-9:
            best, score = v, s
    return best, score


def _fate_text(o):
    if o.fate == "recoloured":
        return f"recoloured to {o.to_colour}"
    if o.fate == "moved":
        return f"moved by ({o.vector[0]},{o.vector[1]})"
    return o.fate


def objects_text(grid, view, fates=None, limit=MAX_OBJECTS):
    """One line per object (changed objects first): colour, size, box, fate."""
    objs, bg = SC.native_objects(grid, view)
    rows = []
    for j, o in enumerate(objs):
        cells = sorted(o.cells)
        r0, c0, r1, c1 = _box(cells)
        colour = int(o.color)
        f = fates.get(j) if fates else None
        desc = f"#{j} colour {colour} size {len(cells)} rows {r0}-{r1} cols {c0}-{c1}"
        if getattr(o, "cell_colors", None):
            cols = sorted({int(v) for v in o.cell_colors.values()})
            if len(cols) > 1:
                desc = f"#{j} colours {cols} size {len(cells)} rows {r0}-{r1} cols {c0}-{c1}"
        if f is not None:
            desc += f" -> {_fate_text(f)}"
        rows.append((0 if (f is not None and f.fate != "unchanged") else 1, j, desc))
    rows.sort()
    shown = [d for _, _, d in rows[:limit]]
    if len(rows) > limit:
        shown.append(f"... and {len(rows) - limit} more objects")
    return f"background {bg}; {len(objs)} objects: " + "; ".join(shown)


def describe(task, sep="", with_objects=True):
    """The puzzle as text for a prompt. `task` = {"train": [(in, out)], "test_inputs": [grid]}."""
    train = task["train"]
    same = all(np.asarray(a).shape == np.asarray(b).shape for a, b in train)
    view, share = choose_view(train) if same else ("S1", 0.0)
    sc = SC.analyse(train, view) if (same and with_objects) else None
    out = []
    for i, (a, b) in enumerate(train):
        A, B = np.asarray(a), np.asarray(b)
        out.append(f"Example {i + 1}: input {A.shape[0]}x{A.shape[1]}, output {B.shape[0]}x{B.shape[1]}")
        out.append("input:\n" + grid_text(A, sep))
        out.append("output:\n" + grid_text(B, sep))
        if with_objects:
            try:
                if sc is not None:
                    fates = {o.index: o for o in sc.objects[i]}
                    n = int((A != B).sum())
                    out.append(f"CORA sees in view {view} ({VIEW_TEXT[view]}): {n} cells change; "
                               + objects_text(A, view, fates))
                else:
                    out.append(f"CORA sees in the input, view S1 ({VIEW_TEXT['S1']}): " + objects_text(A, "S1"))
            except Exception:                              # noqa: BLE001 (perception is optional)
                pass
    for k, t in enumerate(task["test_inputs"]):
        T = np.asarray(t)
        out.append(f"Test input {k + 1}: {T.shape[0]}x{T.shape[1]}\n" + grid_text(T, sep))
        if with_objects:
            try:
                out.append(f"CORA sees in view {view if same else 'S1'}: " + objects_text(T, view if same else "S1"))
            except Exception:                              # noqa: BLE001
                pass
    return "\n".join(out), {"view": view, "explained_share": round(share, 3), "same_shape": same}
