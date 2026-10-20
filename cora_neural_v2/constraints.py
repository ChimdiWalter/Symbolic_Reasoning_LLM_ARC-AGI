"""Demonstration-derived evidence (for ORDERING) and the few PROVABLY SOUND prunes for ncv2-g1 search. Demonstrations only.

`evidence(train)` reads the demonstrations and matches S1 objects between input and output, as v1's C+H does:
- unchanged objects;
- recoloured objects, with the target colour;
- moved objects (same shape and colour elsewhere), with the displacement;
- deleted objects;
- added objects that copy an input object's shape, with the offset;
- full-row or full-column added lines;
- shape changes, and the cell counts added, removed and recoloured.

The evidence only ORDERS the search (search.py). It never removes a candidate. Plausible-looking shortcuts are not
sound in this language:
- a move onto same-coloured cells shows only removals;
- two same-shape objects swapping places show only recolouring;
- a multicolour reflection can be pure recolouring;
- a recoloured object can be overdrawn after a move.

`sound_prunes(train)` returns only provable restrictions:
- P1. If any demonstration changes shape, the same_as_input render cannot fit. Its canvas has the input's shape.
- P2. A constant_shape render must produce every demonstration's output shape. So it is allowed only when all
  outputs share one shape, and that shape is its (H, W).

Separately, search.py drops any rule whose selector selects no object in any demonstration, in that view. Such a
program behaves on every demonstration exactly like the same program without the rule. This is an Occam
restriction, applied the same way to every arm, not a soundness claim: at test time the rule might have fired.
"""
import numpy as np


def _objects(G):
    from cora_neural_v1.space import _objects as obj
    return obj(np.asarray(G))


def evidence(train):
    ev = {"same_shape": True, "out_shapes": set(), "added": 0, "removed": 0, "recoloured": 0, "kinds": set(),
          "in_cols": set(), "out_cols": set(), "added_cols": set(), "recol_targets": set(), "recol_pairs": set(),
          "vectors": {}, "copy_offsets": {}, "src": {"recolour": set(), "move": set(), "delete": set(), "copy": set()},
          "sizes": set(), "line_added": False, "deleted_any": False}
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        ev["out_shapes"].add(B.shape)
        ev["in_cols"] |= {int(c) for c in np.unique(A) if c}
        ev["out_cols"] |= {int(c) for c in np.unique(B) if c}
        ins = _objects(A)
        ev["sizes"] |= {int(o["size"]) for o in ins}
        if A.shape != B.shape:
            ev["same_shape"] = False
            ev["kinds"].add("reshape")
            continue
        add, rem = (A == 0) & (B != 0), (A != 0) & (B == 0)
        rec = (A != 0) & (B != 0) & (A != B)
        ev["added"] += int(add.sum())
        ev["removed"] += int(rem.sum())
        ev["recoloured"] += int(rec.sum())
        ev["added_cols"] |= {int(c) for c in np.unique(B[add])}
        ev["recol_targets"] |= {int(c) for c in np.unique(B[rec])}
        if any(add[r].sum() >= B.shape[1] - 3 for r in range(B.shape[0])) or \
                any(add[:, c].sum() >= B.shape[0] - 3 for c in range(B.shape[1])):
            ev["line_added"] = True
            ev["kinds"].add("line")
        outs = _objects(B)
        unchanged = []
        for x in ins:
            vals = {int(B[p]) for p in x["cells"]}
            if vals == {x["colour"]}:
                unchanged.append(x)
                continue
            if len(vals) == 1 and 0 not in vals:
                ev["kinds"].add("recolour")
                ev["src"]["recolour"].add(int(x["colour"]))
                ev["recol_pairs"].add((int(x["colour"]), int(next(iter(vals)))))
                continue
            mv = [y for y in outs if y["shape"] == x["shape"] and y["colour"] == x["colour"] and y["origin"] != x["origin"]]
            if mv:
                ev["kinds"].add("move")
                ev["src"]["move"].add(int(x["colour"]))
                for y in mv:
                    d = (int(y["origin"][0] - x["origin"][0]), int(y["origin"][1] - x["origin"][1]))
                    ev["vectors"][d] = ev["vectors"].get(d, 0) + 1
                continue
            if vals == {0}:
                ev["kinds"].add("delete")
                ev["deleted_any"] = True
                ev["src"]["delete"].add(int(x["colour"]))
        for y in outs:                       # added objects shaped like an input object that STAYED (a copy, not a move)
            if all(add[p] for p in y["cells"]):
                for x in unchanged:
                    if x["shape"] == y["shape"] and x["colour"] == y["colour"]:
                        d = (int(y["origin"][0] - x["origin"][0]), int(y["origin"][1] - x["origin"][1]))
                        ev["copy_offsets"][d] = ev["copy_offsets"].get(d, 0) + 1
                        ev["src"]["copy"].add(int(x["colour"]))
                        ev["kinds"].add("copy")
        if add.any() and "copy" not in ev["kinds"] and "line" not in ev["kinds"] and "move" not in ev["kinds"]:
            ev["kinds"].add("add")
    return ev


def sound_prunes(train):
    """P1 and P2 (see the module docstring)."""
    shapes_change = any(np.asarray(a).shape != np.asarray(b).shape for a, b in train)
    out_shapes = {np.asarray(b).shape for _, b in train}
    return {"same_as_input_allowed": not shapes_change,
            "constant_shape": next(iter(out_shapes)) if len(out_shapes) == 1 and shapes_change else None}
