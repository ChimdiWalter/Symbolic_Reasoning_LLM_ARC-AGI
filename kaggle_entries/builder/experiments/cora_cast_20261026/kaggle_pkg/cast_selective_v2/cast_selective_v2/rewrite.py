"""M2: typed guarded rewriting over a grounded scene, and guarded output frames.

Scene (per grid, per view): background = majority colour; entities = objects under a declared view
(mono-4, mono-8, multi-8), each with its source mask, box, colours and features; relation tables computed from the
masks (8-adjacency, enclosure of another object's cells inside the object's holes). Rendering is exact: an entity is
its cells.

A rule is a typed guarded rewrite (NOT a double-pushout construction: no categorical interface is checked; this is an
ordinary guarded graph rewrite with explicit semantics):
    pattern     one entity of the view
    guard       an atom over the entity's own features or its relations (or TRUE)
    preserved   every entity the rule does not match, and every cell outside the action's write set
    changed     the matched entity's write set (below)
    action      KEEP | DELETE | RECOLOR(c) | RECOLOR_REF(adjacent | enclosed) | FILL_HOLES(c) | OUTLINE(c) |
                MOVE(direction, until_blocked | to_border)
    schedule    SYNC for every action except MOVE: all matches and write values are computed on the INPUT scene,
                writes are applied together; two writes of different values to one cell make the program UNDEFINED.
                SEQ for MOVE: entities move one at a time, nearest to the target wall first, each reading the grid
                left by the previous moves (an entity stops at the border or before the first non-background cell).
A rule list is first-match: an entity takes the action of the first rule whose guard holds; no rule = KEEP.
Write sets (the contract): DELETE/RECOLOR: the entity's cells; FILL_HOLES: its enclosed background cells; OUTLINE:
background cells 8-adjacent to it; MOVE: cells in its corridor along the direction. Canvas unchanged.
Programs are found by construction from evidence (every demonstration object's observed fate proposes actions; guards
that separate the objects of different fates are enumerated) and are ALWAYS verified by exact execution of the whole
rule list on every demonstration. Frame rules (CropEntity) crop to the box of the unique entity satisfying a guard.
"""
import itertools

import numpy as np
from . import _nd as ndimage

from . import absdom as D
from . import grids as G
from .ops import Op

VIEWS = (("mono", 4), ("mono", 8), ("multi", 8))
MAX_ACTS = 8           # actions considered per view: the 8 that explain the most changed objects (declared bound)
MAX_OBJS = 120         # scenes with more objects over all demonstrations are skipped (declared bound)
TABLE_FEATURES = ("colour", "size", "holes", "shape", "height", "width", "n_colours")
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


# ------------------------------------------------------------------ scene
class Scene:
    def __init__(self, g, view):
        self.g = G.A(g)
        self.bg = G.bg_of(self.g)
        kind, conn = view
        self.view = view
        self.objs = G.objects(self.g, self.bg, conn=conn, mono=(kind == "mono"))
        H, W = self.g.shape
        lab = np.full(self.g.shape, -1)
        for o in self.objs:
            lab[o.mask] = o.idx
        self.lab = lab
        sizes = [o.size for o in self.objs]
        shapes = [o.shape_key() for o in self.objs]
        cols = [o.colour for o in self.objs]
        for o in self.objs:
            f = o.tags
            f["colour"] = o.colour
            f["size"] = o.size
            f["holes"] = G.hole_count(o, 4)
            f["has_hole"] = f["holes"] > 0
            f["border"] = bool(o.box[0] == 0 or o.box[1] == 0 or o.box[2] == H - 1 or o.box[3] == W - 1)
            f["largest"] = o.size == max(sizes)
            f["smallest"] = o.size == min(sizes)
            f["size_unique"] = sizes.count(o.size) == 1
            f["shape_unique"] = shapes.count(o.shape_key()) == 1
            f["colour_unique"] = cols.count(o.colour) == 1
            f["single_cell"] = o.size == 1
            f["n_colours"] = len(o.colours)
            dil = ndimage.binary_dilation(o.mask, structure=G.S8) & ~o.mask
            nb = set(np.unique(lab[dil]).tolist()) - {-1}
            f["adj_ids"] = sorted(nb)
            f["adj_colours"] = sorted({self.objs[i].colour for i in nb})
            holes = self.hole_mask(o)
            inner = set(np.unique(lab[holes]).tolist()) - {-1} if holes.any() else set()
            f["enc_ids"] = sorted(inner)
            f["enc_colours"] = sorted({self.objs[i].colour for i in inner})

    def hole_mask(self, o):
        r0, c0, r1, c1 = o.box
        sub = o.mask[r0:r1 + 1, c0:c1 + 1]
        filled = ndimage.binary_fill_holes(sub)
        m = np.zeros(self.g.shape, dtype=bool)
        m[r0:r1 + 1, c0:c1 + 1] = filled & ~sub
        return m


# ------------------------------------------------------------------ guards
_TRUE_ONLY = False


def guard_space(scenes):
    """Finite guard atoms from the demonstration scenes (values seen in the demonstrations only)."""
    out = [("true",)]
    if _TRUE_ONLY:
        return out
    cols = sorted({o.tags["colour"] for s in scenes for o in s.objs})
    out += [("colour", c) for c in cols]
    out += [("not_colour", c) for c in cols]
    for b in ("has_hole", "border", "largest", "smallest", "size_unique", "shape_unique", "colour_unique",
              "single_cell"):
        out += [(b, True), (b, False)]
    sizes = sorted({o.tags["size"] for s in scenes for o in s.objs})
    out += [("size", k) for k in sizes[:12]]
    hs = sorted({o.tags["holes"] for s in scenes for o in s.objs})
    out += [("holes", k) for k in hs if k <= 4]
    adj = sorted({c for s in scenes for o in s.objs for c in o.tags["adj_colours"]})
    out += [("adj_colour", c) for c in adj] + [("adj_any", True), ("adj_any", False)]
    enc = sorted({c for s in scenes for o in s.objs for c in o.tags["enc_colours"]})
    out += [("enc_colour", c) for c in enc]
    return out


def holds(o, gd):
    k = gd[0]
    f = o.tags
    if k == "true":
        return True
    if k == "colour":
        return f["colour"] == gd[1]
    if k == "not_colour":
        return f["colour"] != gd[1]
    if k in ("has_hole", "border", "largest", "smallest", "size_unique", "shape_unique", "colour_unique",
             "single_cell"):
        return f[k] == gd[1]
    if k == "size":
        return f["size"] == gd[1]
    if k == "holes":
        return f["holes"] == gd[1]
    if k == "adj_colour":
        return gd[1] in f["adj_colours"]
    if k == "adj_any":
        return bool(f["adj_ids"]) == gd[1]
    if k == "enc_colour":
        return gd[1] in f["enc_colours"]
    raise KeyError(k)


# ------------------------------------------------------------------ actions (SYNC write sets and values)
def writes(scene, o, act):
    """(mask, value array or scalar) written by a SYNC action on entity o; None = action undefined on o."""
    k = act[0]
    if k == "keep":
        return np.zeros(scene.g.shape, dtype=bool), 0
    if k == "delete":
        return o.mask, scene.bg
    if k == "recolor":
        return o.mask, act[1]
    if k == "recolor_ref":
        cs = o.tags["adj_colours"] if act[1] == "adjacent" else o.tags["enc_colours"]
        cs = [c for c in cs if c != o.tags["colour"]]
        if len(cs) != 1:
            return None
        return o.mask, cs[0]
    if k == "fill_holes":
        h = scene.hole_mask(o) & (scene.g == scene.bg)
        if not h.any():
            return None
        return h, act[1]
    if k == "outline":
        m = ndimage.binary_dilation(o.mask, structure=G.S8) & (scene.g == scene.bg)
        return m, act[1]
    raise KeyError(k)


def run_sync(scene, rules):
    out = scene.g.copy()
    wrote = np.zeros(scene.g.shape, dtype=bool)
    for o in scene.objs:
        act = next((a for gd, a in rules if holds(o, gd)), ("keep",))
        if act[0] == "keep":
            continue
        w = writes(scene, o, act)
        if w is None:
            return None
        m, v = w
        clash = wrote & m & (out != v)
        if clash.any():
            return None
        out[m] = v
        wrote |= m
    return out


def run_moves(scene, rules):
    """SEQ schedule for MOVE rules (other entities keep their place)."""
    g = scene.g.copy()
    plan = []
    for o in scene.objs:
        act = next((a for gd, a in rules if holds(o, gd)), ("keep",))
        if act[0] == "move":
            plan.append((o, act))
        elif act[0] != "keep":
            return None
    if not plan:
        return None

    def key(item):
        o, act = item
        dr, dc = DIRS[act[1]]
        r0, c0, r1, c1 = o.box
        return -(r1 if dr > 0 else (-r0 if dr < 0 else (c1 if dc > 0 else -c0)))
    plan.sort(key=key)
    H, W = g.shape
    for o, act in plan:
        dr, dc = DIRS[act[1]]
        vals = g[o.mask]
        ys, xs = np.nonzero(o.mask)
        g[o.mask] = scene.bg
        step = 0
        while True:
            ny, nx = ys + (step + 1) * dr, xs + (step + 1) * dc
            if ny.min() < 0 or nx.min() < 0 or ny.max() >= H or nx.max() >= W:
                break
            if act[2] == "until_blocked" and (g[ny, nx] != scene.bg).any():
                break
            step += 1
        g[ys + step * dr, xs + step * dc] = vals
    return g


_SCENES = {}


def scene_of(g, view):
    g = G.A(g)
    key = (g.shape, g.tobytes(), view)
    s = _SCENES.get(key)
    if s is None:
        if len(_SCENES) > 512:
            _SCENES.clear()
        s = Scene(g, view)
        _SCENES[key] = s
    return s


def execute(g, view, rules):
    s = scene_of(g, view)
    if any(a[0] == "move" for _, a in rules):
        return run_moves(s, rules)
    return run_sync(s, rules)


# ------------------------------------------------------------------ construction from evidence
def fates(scene, y):
    """Actions that explain each object of a demonstration in isolation (SYNC actions), by object index."""
    out = {}
    if y.shape != scene.g.shape:
        return None
    for o in scene.objs:
        ex = set()
        if (y[o.mask] == scene.g[o.mask]).all():
            ex.add(("keep",))
        vals = np.unique(y[o.mask])
        if len(vals) == 1:
            v = int(vals[0])
            if v == scene.bg:
                ex.add(("delete",))
            elif not (len(o.colours) == 1 and v == o.colour):
                ex.add(("recolor", v))
                for rel in ("adjacent", "enclosed"):
                    w = writes(scene, o, ("recolor_ref", rel))
                    if w is not None and w[1] == v:
                        ex.add(("recolor_ref", rel))
        h = scene.hole_mask(o) & (scene.g == scene.bg)
        if h.any():
            hv = np.unique(y[h])
            if len(hv) == 1 and int(hv[0]) != scene.bg:
                ex.add(("fill_holes", int(hv[0])))
        m = ndimage.binary_dilation(o.mask, structure=G.S8) & (scene.g == scene.bg)
        if m.any():
            mv = np.unique(y[m])
            if len(mv) == 1 and int(mv[0]) != scene.bg:
                ex.add(("outline", int(mv[0])))
        out[o.idx] = ex
    return out


def construct(demos, view, max_lists=64):
    """Candidate rule lists (first-match, <= 2 rules + KEEP default, or 1 rule + another default) from evidence,
    each verified by exact execution on every demonstration. Returns verified rule lists."""
    if any(x.shape != y.shape for x, y in demos):
        return []
    scenes = [scene_of(x, view) for x, _ in demos]
    fs = [fates(s, y) for s, (_, y) in zip(scenes, demos)]
    cover = {}
    for f in fs:
        for e in f.values():
            if ("keep",) in e:
                continue
            for a in e:
                cover[a] = cover.get(a, 0) + 1
    acts = sorted(cover, key=lambda a: (-cover[a], repr(a)))[:MAX_ACTS]
    objs = [(i, o) for i, s in enumerate(scenes) for o in s.objs]
    if len(objs) > MAX_OBJS:
        return []
    guards = guard_space(scenes)
    # which guards are consistent with an action: every matching object is explained by it
    match = {gd: [holds(o, gd) for _, o in objs] for gd in guards}
    expl = {a: [a in fs[i][o.idx] for i, o in objs] for a in acts + [("keep",)]}
    cands = []
    for a in acts:
        for gd in guards:
            m = match[gd]
            if not any(m) or not all(e for e, mm in zip(expl[a], m) if mm):
                continue
            rest = [k for k, mm in enumerate(m) if not mm]
            if all(expl[("keep",)][k] for k in rest):
                cands.append([(gd, a)])
                continue
            for a2 in acts:
                if a2 == a:
                    continue
                if all(expl[a2][k] for k in rest):
                    cands.append([(gd, a), (("true",), a2)])
                    continue
                for g2 in guards:
                    m2 = match[g2]
                    if not all((not m2[k]) or expl[a2][k] for k in rest):
                        continue
                    if all(m2[k] or expl[("keep",)][k] for k in rest) and any(m2[k] for k in rest):
                        cands.append([(gd, a), (g2, a2)])
                        break
            if len(cands) > 4 * max_lists:
                break
    verified, seen = [], set()
    for rules in cands:
        key = repr(rules)
        if key in seen:
            continue
        seen.add(key)
        ok = True
        for x, y in demos:
            out = execute(x, view, rules)
            if out is None or not np.array_equal(out, y):
                ok = False
                break
        if ok:
            verified.append(rules)
            if len(verified) >= max_lists:
                break
    return verified


def tfeat(o, f):
    if f == "shape":
        return o.shape_key()
    if f == "height":
        return o.h
    if f == "width":
        return o.w
    return o.tags[f]


def run_table(scene, f, table):
    out = scene.g.copy()
    for o in scene.objs:
        k = tfeat(o, f)
        if k in table:
            out[o.mask] = table[k]
    return out


def construct_tables(demos, view):
    """N-guard table rewrite: one categorical feature f; every object whose f-value is in the table is recoloured
    to the table's colour (guards f == v_i, actions RECOLOR(c_i)); all other objects KEEP. The table is a
    task-level constant learned from the demonstrations (an OBSERVED_DEMONSTRATION_CONSTRAINT), unlike M1's tables
    which are re-read from every input. Verified by exact execution."""
    if any(x.shape != y.shape for x, y in demos):
        return []
    out = []
    for f in TABLE_FEATURES:
        table, ok = {}, True
        for x, y in demos:
            s = scene_of(x, view)
            for o in s.objs:
                vals = np.unique(y[o.mask])
                k = tfeat(o, f)
                if len(vals) == 1 and not (len(o.colours) == 1 and int(vals[0]) == o.colour):
                    v = int(vals[0])
                    if table.get(k, v) != v:
                        ok = False
                        break
                    table[k] = v
            if not ok:
                break
        if not ok or not table:
            continue
        good = True
        for x, y in demos:
            if not np.array_equal(run_table(scene_of(x, view), f, table), y):
                good = False
                break
        if good:
            out.append((f, table))
    return out


def construct_moves(demos, view, max_lists=16):
    """MOVE rule lists (SEQ): [(guard, move)] + KEEP, or [(guard, move d1), (true, move d2)]; verified by execution."""
    if any(x.shape != y.shape for x, y in demos):
        return []
    # declared precondition of the move constructor: every demonstration changes and keeps its colour counts
    if any(np.array_equal(x, y) or not np.array_equal(G.counts(x), G.counts(y)) for x, y in demos):
        return []
    scenes = [scene_of(x, view) for x, _ in demos]
    guards = guard_space(scenes)
    moves = [("move", d, m) for d in DIRS for m in ("until_blocked", "to_border")]
    out = []
    for mv in moves:
        for gd in guards:
            for default in [None] + [m2 for m2 in moves if m2 != mv]:
                rules = [(gd, mv)] + ([(("true",), default)] if default else [])
                if gd == ("true",) and default:
                    continue
                ok = True
                for x, y in demos:
                    o = execute(x, view, rules)
                    if o is None or not np.array_equal(o, y):
                        ok = False
                        break
                if ok:
                    out.append(rules)
                    if len(out) >= max_lists:
                        return out
    return out


# ------------------------------------------------------------------ guarded output frames
class CropEntity(Op):
    """Crop the input to the box of the UNIQUE entity (under a view) whose guard holds; undefined otherwise."""
    name = "crop_entity"
    same_shape = False
    scope = "grids up to 30x30; views mono-4, mono-8, multi-8; guard atoms from the demonstrations"

    def domain(self, ctx):
        scenes = {v: [scene_of(x, v) for x, _ in ctx.train] for v in VIEWS}
        return [(v, gd) for v in VIEWS for gd in guard_space(scenes[v]) if gd != ("true",)]

    def apply(self, g, th):
        view, gd = th
        s = scene_of(g, view)
        hits = [o for o in s.objs if holds(o, gd)]
        if len(hits) != 1:
            return None
        return G.crop(s.g, hits[0].box)

    def fwd(self, a, th):
        if a.bottom:
            return D.BOTTOM()
        if a.shapes is None:
            return D.Abs(None, (1, 1), None, a.pal, 0, None, a.hi)
        shapes = {(h, w) for H, W in a.shapes for h in range(1, H + 1) for w in range(1, W + 1)}
        return D.Abs(shapes, (1, 1), None, a.pal, 0, None, a.hi)

    def bwd(self, y, th):
        y = np.asarray(y)
        return D.Abs(None, y.shape, None, D.ALL, D.mask_of(np.unique(y).tolist()), G.counts(y), None)


def program_text(view, rules):
    return f"(rewrite view={view[0]}{view[1]} " + " ".join(f"[{gd} -> {a}]" for gd, a in rules) + ")"


def search(task, max_lists=64, views=VIEWS, true_only=False, frames=True):
    """All verified rewrite programs (SYNC rule lists, SEQ moves, table rewrites, guarded crop frames) over the given
    views, with query predictions. true_only=True restricts every guard to TRUE (control: no guards)."""
    demos = [(np.asarray(x, dtype=np.int64), np.asarray(y, dtype=np.int64)) for x, y in task["train"]]
    qs = [np.asarray(q, dtype=np.int64) for q in task["test_inputs"]]
    fits, execs = [], 0
    global _TRUE_ONLY
    _TRUE_ONLY = true_only
    for view in views:
        for rules in construct(demos, view, max_lists) + construct_moves(demos, view):
            preds = [execute(q, view, rules) for q in qs]
            fits.append({"program": program_text(view, rules), "preds": preds,
                         "complete": [p is not None for p in preds], "cost": float(len(rules)),
                         "order": len(fits), "view": view, "rules": repr(rules)})
        for f, table in construct_tables(demos, view):
            preds = [run_table(scene_of(q, view), f, table) for q in qs]
            if true_only:
                continue
            fits.append({"program": f"(table-rewrite view={view[0]}{view[1]} feature={f} n={len(table)})",
                         "preds": preds, "complete": [True] * len(preds), "cost": float(len(table)),
                         "order": len(fits), "view": view, "rules": f"table:{f}"})
    if frames and not true_only and all(np.asarray(x).shape != np.asarray(y).shape for x, y in task["train"]):
        op = CropEntity()
        ctx = type("C", (), {"train": demos})
        for th in op.domain(ctx):
            if th[0] not in views:
                continue
            ok = True
            for x, y in demos:
                o = op.apply(x, th)
                if o is None or o.shape != y.shape or not np.array_equal(o, y):
                    ok = False
                    break
            if ok:
                preds = [op.apply(q, th) for q in qs]
                fits.append({"program": f"(crop-entity view={th[0][0]}{th[0][1]} guard={th[1]})", "preds": preds,
                             "complete": [p is not None for p in preds], "cost": 1.0, "order": len(fits),
                             "view": th[0], "rules": repr(th)})
    _TRUE_ONLY = False
    return fits


def footprint_ok(demos, view, rules):
    """M3 contract check for a SYNC rule list on concrete demonstrations: every changed cell must lie in the union of
    the matched entities' write sets (computed without evaluating values)."""
    for x, y in demos:
        s = scene_of(x, view)
        m = np.zeros(x.shape, dtype=bool)
        for o in s.objs:
            act = next((a for gd, a in rules if holds(o, gd)), ("keep",))
            if act[0] in ("keep",):
                continue
            if act[0] == "move":
                return True                                  # corridor footprint: no cheap rejection here
            w = writes(s, o, act)
            if w is not None:
                m |= w[0]
        if ((x != y) & ~m).any():
            return False
    return True


__all__ = ["Scene", "VIEWS", "construct", "construct_moves", "execute", "search", "CropEntity", "guard_space",
           "holds", "footprint_ok"]
_unused = itertools
