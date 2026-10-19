"""Component domains, the shared data-driven pruning, the symbolic orders and the best-first enumerator.

Every arm searches the SAME pruned space with the SAME interpreter and checker; only the ORDER differs:
- C+ (`simplicity_scores`): a fixed simplest-first, Occam order.
- C+H (`heuristic_scores`): C+ plus a researcher-designed delta analysis of the demonstrations (colours added,
  recoloured or deleted; object displacements; full-line additions). It is the strong symbolic control.
- L0 / L1: component scores from the neural prior (`prior.py`), untrained or trained.

Pruning reads the demonstrations only:
- selector colours: those present in demonstration inputs;
- selector sizes: object sizes present in demonstration inputs;
- recolour and line colours: those present in demonstration outputs.
"""
import heapq

import numpy as np

from cora_neural_v1.ir import (ACTIONS, DEFAULTS, SELECTORS, VARIANTS, VECTORS, DIRECTIONS, LINE_AXES, REFLECT_AXES,
                               Hypothesis, Rule)

FIXED_SELECTORS = (("size_rank", 0), ("size_rank_reversed", 0), ("touches_border", True), ("touches_border", False),
                   ("is_line", True), ("is_rectangle", True), ("has_hole", True), ("is_unique_color", True),
                   ("is_unique_size", True))


def _sizes(G):
    from geocat_arc.object_reasoning.segmentation import segment
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from geocat_arc.perception.grid import Grid
    return {len(o.cells) for o in segment(Grid(np.asarray(G, dtype=np.int32)), V("S1"))}


def domains(train):
    ins = [np.asarray(a) for a, _ in train]
    outs = [np.asarray(b) for _, b in train]
    in_cols = sorted({int(c) for A in ins for c in np.unique(A) if c != 0})
    out_cols = sorted({int(c) for B in outs for c in np.unique(B) if c != 0})
    sizes = sorted({k for A in ins for k in _sizes(A) if 1 <= k <= 12})
    sels = [("true", None)] + [("color", c) for c in in_cols] + [("size", k) for k in sizes] + list(FIXED_SELECTORS)
    acts = ([("keep",), ("delete",)] + [("recolor", c) for c in out_cols]
            + [("translate", dr, dc) for dr, dc in VECTORS] + [("slide", d) for d in DIRECTIONS]
            + [("fill_line", a, c) for a in LINE_AXES for c in out_cols] + [("reflect", a) for a in REFLECT_AXES])
    return {"variants": list(VARIANTS), "selectors": sels, "actions": acts, "defaults": list(DEFAULTS), "n_rules": [1, 2]}


# ------------------------------------------------------------------ symbolic orders
def _sel_cost(s):
    k = s[0]
    return {"true": 0.0, "color": 1.0, "size": 1.5, "size_rank": 2.0, "size_rank_reversed": 2.0}.get(k, 2.5)


def _act_cost(a):
    t = a[0]
    if t == "translate":
        return 1.0 + 0.25 * (abs(a[1]) + abs(a[2]))
    if t == "fill_line":
        return 2.0 + (0.2 if a[1] == "both" else 0.0)
    return {"keep": 0.2, "delete": 0.5, "recolor": 1.0, "slide": 1.5, "reflect": 2.5}[t]


def simplicity_scores(doms):
    """C+: score = -description cost (fewer and simpler parts first; native trial order for views)."""
    return {"variant": {v: -0.5 * i for i, v in enumerate(VARIANTS)}, "n_rules": {1: 0.0, 2: -4.0},
            "default": {"keep": 0.0, "delete": -1.0},
            "selector": {s: -_sel_cost(s) for s in doms["selectors"]},
            "action": {a: -_act_cost(a) for a in doms["actions"]}}


def _objects(G):
    from geocat_arc.object_reasoning.segmentation import segment
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from geocat_arc.perception.grid import Grid
    out = []
    for o in segment(Grid(np.asarray(G, dtype=np.int32)), V("S1")):
        cells = sorted(o.cells)
        r0 = min(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        col = int(np.asarray(G)[cells[0]])
        out.append({"cells": cells, "colour": col, "size": len(cells), "origin": (r0, c0),
                    "shape": tuple((r - r0, c - c0) for r, c in cells)})
    return out


def change_kinds(train):
    """Hand-designed object-level delta analysis (no learning). Each input object is matched to the output:
    - unchanged: the same cells and colour remain;
    - recoloured: the same cells, now one other colour;
    - moved: the same shape and colour at another place, with the displacement recorded;
    - deleted: every cell becomes background.
    Added background cells forming a full row or column are a line. Returns the evidence dictionary."""
    ev = {"kinds": set(), "added_cols": set(), "recol_targets": set(), "changed_src_cols": set(),
          "changed_sizes": set(), "vectors": {}, "deleted_any": False, "line_added": False}
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        add = (A == 0) & (B != 0)
        ev["added_cols"] |= {int(c) for c in np.unique(B[add])}
        for r in range(B.shape[0]):
            if add[r].sum() >= B.shape[1] - 3:
                ev["line_added"] = True
        for c in range(B.shape[1]):
            if add[:, c].sum() >= B.shape[0] - 3:
                ev["line_added"] = True
        if ev["line_added"]:
            ev["kinds"].add("line")
        oo = _objects(B)
        for x in _objects(A):
            vals = {int(B[p]) for p in x["cells"]}
            if vals == {x["colour"]}:
                continue                                                      # unchanged
            ev["changed_sizes"].add(x["size"])
            ev["changed_src_cols"].add(x["colour"])
            if len(vals) == 1 and 0 not in vals:
                ev["kinds"].add("recolour")
                ev["recol_targets"] |= vals
                continue
            mv = [y for y in oo if y["shape"] == x["shape"] and y["colour"] == x["colour"] and y["origin"] != x["origin"]]
            if mv:
                ev["kinds"].add("move")
                for y in mv:
                    d = (y["origin"][0] - x["origin"][0], y["origin"][1] - x["origin"][1])
                    ev["vectors"][d] = ev["vectors"].get(d, 0) + 1
                continue
            if vals == {0}:
                ev["kinds"].add("delete")
                ev["deleted_any"] = True
    return ev


def heuristic_scores(doms, train):
    """C+H: the C+ order plus bonuses from the hand-designed delta analysis `change_kinds` (no learning). If the
    demonstrations show two kinds of change, two-rule programs come first."""
    sc = simplicity_scores(doms)
    bonus_a, bonus_s = {}, {}
    ev = change_kinds(train)
    added_cols, recol_targets, vectors = ev["added_cols"], ev["recol_targets"], ev["vectors"]
    changed_src_cols, changed_sizes = ev["changed_src_cols"], ev["changed_sizes"]
    deleted_any, line_added = ev["deleted_any"], ev["line_added"]
    if len(ev["kinds"]) >= 2:
        sc["n_rules"] = {1: -4.0, 2: 0.0}
    for act in doms["actions"]:
        t = act[0]
        b = 0.0
        if t == "recolor" and act[1] in recol_targets:
            b += 2.0
        if t == "fill_line" and act[2] in added_cols and line_added:
            b += 2.5
        if t == "delete" and deleted_any:
            b += 1.5
        if t == "translate" and (act[1], act[2]) in vectors:
            b += 1.0 + 0.5 * min(vectors[(act[1], act[2])], 4)
        if t == "slide" and vectors:
            b += 0.75
        bonus_a[act] = b
    for s in doms["selectors"]:
        b = 0.0
        if s[0] == "color" and s[1] in changed_src_cols:
            b += 1.0
        if s[0] == "size" and s[1] in changed_sizes:
            b += 0.75
        bonus_s[s] = b
    sc["action"] = {a: v + bonus_a.get(a, 0.0) for a, v in sc["action"].items()}
    sc["selector"] = {s: v + bonus_s.get(s, 0.0) for s, v in sc["selector"].items()}
    if deleted_any:
        sc["default"]["delete"] += 0.5
    return sc


# ------------------------------------------------------------------ best-first enumeration
def enumerate_programs(doms, scores, limit, max_pops=None):
    """Yield up to `limit` distinct hypotheses in decreasing total score:
    score(variant) + score(n_rules) + score(default) + sum over rules of (score(selector) + score(action)).

    Two-rule programs are ordered (first match). A pair sharing a selector is skipped: its second rule could never
    fire. Ties are broken by the component lists' fixed order, so enumeration is deterministic."""
    V = sorted(doms["variants"], key=lambda v: -scores["variant"][v])
    D = sorted(doms["defaults"], key=lambda d: -scores["default"][d])
    pairs = [(s, a) for s in doms["selectors"] for a in doms["actions"]]
    ps = np.array([scores["selector"][s] + scores["action"][a] for s, a in pairs])
    order = np.argsort(-ps, kind="stable")
    P = [pairs[i] for i in order]
    pv = ps[order]
    sv = [scores["variant"][v] for v in V]
    sd = [scores["default"][d] for d in D]
    sn = scores["n_rules"]
    heap, seen = [], set()

    def push(state):
        if state in seen:
            return
        n = state[0]
        if n == 1:
            _, iv, ip, idf = state
            if iv >= len(V) or ip >= len(P) or idf >= len(D):
                return
            s = sv[iv] + sn[1] + sd[idf] + pv[ip]
        else:
            _, iv, ip1, ip2, idf = state
            if iv >= len(V) or ip1 >= len(P) or ip2 >= len(P) or idf >= len(D):
                return
            s = sv[iv] + sn[2] + sd[idf] + pv[ip1] + pv[ip2]
        seen.add(state)
        heapq.heappush(heap, (-float(s), state))

    push((1, 0, 0, 0))
    push((2, 0, 0, 1, 0))
    push((2, 0, 1, 0, 0))
    out = 0
    pops = 0
    max_pops = max_pops or 50 * limit + 1000
    while heap and out < limit and pops < max_pops:
        pops += 1
        negs, st = heapq.heappop(heap)
        if st[0] == 1:
            _, iv, ip, idf = st
            push((1, iv + 1, ip, idf))
            push((1, iv, ip + 1, idf))
            push((1, iv, ip, idf + 1))
            rules = (Rule(*P[ip]),)
        else:
            _, iv, ip1, ip2, idf = st
            push((2, iv + 1, ip1, ip2, idf))
            push((2, iv, ip1 + 1, ip2, idf))
            push((2, iv, ip1, ip2 + 1, idf))
            push((2, iv, ip1, ip2, idf + 1))
            if ip1 == ip2 or P[ip1][0] == P[ip2][0]:
                continue
            rules = (Rule(*P[ip1]), Rule(*P[ip2]))
        out += 1
        yield Hypothesis(V[iv], rules, D[idf]), -negs
