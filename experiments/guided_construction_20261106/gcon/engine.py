"""The test's constructor: the frozen object-level constructor (`objgrow/construct.py`) cut into blocks, so that the
order of its searches can change while each search, each verification and the final ranking stay the frozen ones.

Per hole, every view's pair analysis is computed first (`HoleState`; frozen `Pair`, `predicates`, `covering`,
`conjunctions`, `table_edits`; no operation is applied). The blocks of a view are
    S  single-rule block for one edit e of the view's common-edit list: the frozen loop over the covering predicates
       and conjunctions, stopping at the first admissible predicate whose operation verifies on every pair;
    T  the frozen two-rule search; it runs only when every S block of the view ran to its end and none verified;
    W  the frozen whole-output forms (crop, token, count).
The hand-set order is the frozen sequence: views in `scene.VIEWS` order; inside a view S in list order, T, W. The
frozen symmetry forms follow every block, without a cap. An operation is applied only while the hole's operation
counter is at most the budget (the frozen checks, at the frozen places). Found candidates are put back into their
hand-set place (view index, block place, place inside the block) before the frozen de-duplication, grouping by
agreement on the test inputs, stable sort by (group, simplicity) and cut at 8, so every order gives the frozen
candidate list whenever the cap never binds.

`run_hole(hs, sequence, budget, log=None)` executes a block sequence; with `log` it records, per block, its
operations and the place of each found candidate's last operation (the trace used for simulation, `sim.py`).
`trace_hole` runs every block to its end or to `BLOCK_CAP` operations.
"""
import hashlib
import itertools
import json

from gcon import env as E                                                       # noqa: F401  (import paths)
from objgrow import construct as CS, edits as ED, scene as SC

VIEWS = SC.VIEWS
#: content comparisons of an object's bounding-box crop with a target (the whole-output crop precondition): pixel
#: work that the frozen step does outside its operation counter; counted here for reporting only
CMP = {"n": 0}
BLOCK_CAP = 20_001
FULL_BUDGET = CS.MAX_OPS_PER_HOLE              # 20,000, the frozen cap
EDIT_TYPES = CS.EDIT_ORDER + ("recolor_table",)


def verify(op, pairs, budget):
    """The frozen `construct.verify` with the cap passed in."""
    for p in pairs:
        if ED.COUNTS["op"] > budget:
            return False
        if op(p.x) != p.y:
            return False
    return True


class ViewState:
    """One view of one hole: the frozen pair analysis and the inputs of its blocks (frozen `hole_candidates` and
    `paint_candidates` up to their search loops)."""

    def __init__(self, hole, view, vi):
        self.view, self.vi = view, vi
        self.pairs = [CS.Pair(x, y, view) for x, y in hole]
        self.skipped = any(p.s is None for p in self.pairs)
        self.blocks = []
        if self.skipped:
            self.rec = {"skipped": "over the object cap"}
            return
        pairs = self.pairs
        same = all(p.same for p in pairs)
        n_changed = sum(len(p.changed) for p in pairs)
        n_expl = sum(1 for p in pairs for i in p.changed if p.bound[i])
        n_app = sum(len(p.appeared) for p in pairs)
        n_unexpl = sum(len(p.unexplained) for p in pairs)
        full = same and all(p.explained_all for p in pairs) and (n_changed + n_app) > 0
        partial = same and (n_expl > 0 or n_app > n_unexpl)
        self.rec = {"same_shape": same, "changed_objects": n_changed, "explained_objects": n_expl,
                    "appeared_cells": n_app, "unexplained_cells": n_unexpl, "full": full, "partial": partial,
                    "objects": [len(p.s.objs) for p in pairs]}
        self.same, self.full, self.partial = same, full, partial
        self.preds = CS.predicates([p.s for p in pairs])
        self.paint = same and (n_changed > 0 or n_app > 0)
        self.common, self.cov, self.cov_all, self.proposing, self.req_objs = [], [], [], {}, []
        self.growth, self.why0 = False, None
        if self.paint:
            self._paint_setup()
            for j, e in enumerate(self.common):
                self.blocks.append(("S", vi, j))
            if self.req_objs:
                self.blocks.append(("T", vi, 0))
        self.blocks.append(("W", vi, 0))

    def _paint_setup(self):
        """Frozen `paint_candidates` before its single-rule loop."""
        pairs = self.pairs
        req_objs = [(p, i) for p in pairs for i in p.required]
        grow_objs = [(p, i) for p in pairs for i in p.bound if i not in p.required]
        if not req_objs and not grow_objs:
            self.why0 = "no_required_objects"
            return
        if req_objs:
            common = None
            for p, i in req_objs:
                es = set(p.bound[i])
                common = es if common is None else common & es
            common = sorted(common or (), key=CS.edit_sort_key)
            common += CS.table_edits(pairs)
        else:
            cnt = {}
            for p, i in grow_objs:
                for e in p.bound[i]:
                    cnt[e] = cnt.get(e, 0) + 1
            common = sorted(cnt, key=lambda e: (-cnt[e], CS.edit_sort_key(e)))
            req_objs = grow_objs
            self.growth = True
        self.why0 = "no_common_edit" if not common else "no_admissible_predicate"
        proposing = {}
        for e in common:
            proposing[e] = sum(1 for p in pairs if any(e in es or (e[0] == "recolor_table" and
                                                                    any(f[0] == "recolor" for f in es))
                                                        for es in p.bound.values()))
        self.common, self.proposing, self.req_objs = common, proposing, req_objs
        self.cov = CS.covering(self.preds, pairs)
        self.cov_all = self.cov + CS.conjunctions(self.cov)


class HoleState:
    """A hole (list of (input, target) grid pairs) with its test inputs and the pair analysis of all 12 views."""

    def __init__(self, hole, test_inputs=(), meta=None):
        ED.reset_counts()
        self.hole, self.test_inputs, self.meta = hole, tuple(test_inputs), dict(meta or {})
        self.views = [ViewState(hole, v, vi) for vi, v in enumerate(VIEWS)]
        self.setup_counts = dict(ED.COUNTS)
        self.blocks = [b for vs in self.views for b in vs.blocks]     # the hand-set sequence
        self.hand_pos = {b: k for k, b in enumerate(self.blocks)}

    def block_key(self, b):
        """(kind, view, edit type) for S blocks; (kind, view) otherwise."""
        kind, vi, j = b
        vs = self.views[vi]
        if kind == "S":
            return (kind, vs.view, vs.common[j][0])
        return (kind, vs.view)


# ------------------------------------------------------------------ the blocks
def run_S(vs, j, budget, why):
    """Frozen single-rule loop for one edit. Returns (candidate or None, aborted)."""
    e = vs.common[j]
    for pred in vs.cov_all:
        if ED.COUNTS["op"] > budget:
            return None, True
        if not CS.admissible(pred, e, vs.pairs):
            continue
        op = ED.ObjOp({"form": "paint", "view": vs.view, "rules": [[pred, e]]})
        if verify(op, vs.pairs, budget):
            return {"op": op, "loo": vs.proposing[e] >= 2, "proposing": vs.proposing[e],
                    "simplicity": (1, CS.pred_size(pred), CS.edit_sort_key(e))}, False
        why["verification_failed"] = why.get("verification_failed", 0) + 1
    return None, False


def run_T(vs, budget, why):
    """Frozen two-rule search (first-match lists). Returns (candidates (at most one), aborted)."""
    pairs, preds, req_objs, view = vs.pairs, vs.preds, vs.req_objs, vs.view
    found = []
    cnt = {}
    for p, i in req_objs:
        for e in p.bound[i]:
            cnt[e] = cnt.get(e, 0) + 1
    edits = sorted(cnt, key=lambda e: (-cnt[e], CS.edit_sort_key(e)))[:CS.MAX_TWO_RULE_EDITS]
    for e1, e2 in itertools.permutations(edits, 2):
        c1 = [(p, i) for p, i in req_objs if e1 in p.bound[i]]
        c2 = [(p, i) for p, i in req_objs if e2 in p.bound[i]]
        if len(c1) + len(c2) < len(req_objs) or not c1 or not c2:
            continue
        only1 = [(p, i) for p, i in c1 if e2 not in p.bound[i]]
        only2 = [(p, i) for p, i in c2 if e1 not in p.bound[i]]
        if not only1:
            continue
        for p1 in preds:
            if p1 == ("true",):
                continue
            if not all(SC.holds(p.s.objs[i], p1) for p, i in only1):
                continue
            if any(SC.holds(p.s.objs[i], p1) for p, i in only2):
                continue
            ok = True
            for p in pairs:
                for o in p.s.objs:
                    if SC.holds(o, p1):
                        if o.idx in p.bound:
                            ok = e1 in p.bound[o.idx]
                        else:
                            ok = CS.edit_ok(e1, o, p.s, p.x, p.y)
                        if not ok:
                            break
                if not ok:
                    break
            if not ok:
                continue
            rest = [(p, i) for p, i in req_objs if not SC.holds(p.s.objs[i], p1)]
            for p2 in preds:
                if not all(SC.holds(p.s.objs[i], p2) for p, i in rest):
                    continue
                ok = True
                for p in pairs:
                    for o in p.s.objs:
                        if not SC.holds(o, p1) and SC.holds(o, p2):
                            if o.idx in p.bound:
                                ok = e2 in p.bound[o.idx]
                            else:
                                ok = CS.edit_ok(e2, o, p.s, p.x, p.y)
                            if not ok:
                                break
                    if not ok:
                        break
                if not ok:
                    continue
                if ED.COUNTS["op"] > budget:
                    return found, True
                op = ED.ObjOp({"form": "paint", "view": view, "rules": [[p1, e1], [p2, e2]]})
                if verify(op, pairs, budget):
                    pr = min(CS.proposing_count(e1, pairs), CS.proposing_count(e2, pairs))
                    found.append({"op": op, "loo": pr >= 2, "proposing": pr,
                                  "simplicity": (2, CS.pred_size(p1) + CS.pred_size(p2), CS.edit_sort_key(e1))})
                    break
                why["verification_failed"] = why.get("verification_failed", 0) + 1
            if found:
                break
        if found:
            break
    return found, False


def run_W(vs, budget, marks=None):
    """Frozen `whole_candidates` (crop, token and count forms) with the cap passed in. `marks` receives the operation
    counter after each found candidate."""
    found = []
    pairs, preds = vs.pairs, vs.preds
    view = pairs[0].view
    xs_ys = [(p.x, p.y, p.s) for p in pairs]

    def add(c):
        found.append(c)
        if marks is not None:
            marks.append(ED.COUNTS["op"])
    # crop
    targets = []
    for x, y, s in xs_ys:
        t = []
        for o in s.objs:
            i0, j0, i1, j1 = o.box
            if (o.h, o.w) == (len(y), len(y[0])):
                CMP["n"] += 1
                if tuple(tuple(x[i][j0:j1 + 1]) for i in range(i0, i1 + 1)) == y:
                    t.append(o.idx)
        targets.append(t)
    if all(targets):
        for pred in preds + CS.conjunctions([p for p in preds if all(any(SC.holds(s.objs[i], p) for i in t)
                                                                      for (x, y, s), t in zip(xs_ys, targets))]):
            ok = True
            for (x, y, s), t in zip(xs_ys, targets):
                sel = [o.idx for o in s.objs if SC.holds(o, pred)]
                if len(sel) != 1 or sel[0] not in t:
                    ok = False
                    break
            if ok:
                op = ED.ObjOp({"form": "crop", "view": view, "rules": [[pred, ("keep",)]]})
                if verify(op, pairs, budget):
                    add({"op": op, "loo": True, "proposing": len(pairs),
                         "simplicity": (1, CS.pred_size(pred), (0, 0, "crop"))})
                    break
    # token and count: uniform targets
    uni = []
    for x, y, s in xs_ys:
        cols = {v for r in y for v in r}
        uni.append(next(iter(cols)) if len(cols) == 1 else None)
    if all(c is not None for c in uni):
        shapes = {(len(y), len(y[0])) for _, y, _ in xs_ys}
        if len(shapes) == 1:
            shape = next(iter(shapes))
            for pred in preds:
                ok = True
                for (x, y, s), c in zip(xs_ys, uni):
                    sel = [o for o in s.objs if SC.holds(o, pred)]
                    if not sel or {o.colour for o in sel} != {c}:
                        ok = False
                        break
                if ok:
                    op = ED.ObjOp({"form": "token", "view": view, "rules": [[pred, ("keep",)]],
                                   "params": {"shape": list(shape)}})
                    if verify(op, pairs, budget):
                        add({"op": op, "loo": True, "proposing": len(pairs),
                             "simplicity": (1, CS.pred_size(pred), (0, 0, "token"))})
                        break
        for orient in ("row", "col"):
            ns = []
            for _, y, _ in xs_ys:
                if orient == "row" and len(y) == 1:
                    ns.append(len(y[0]))
                elif orient == "col" and len(y[0]) == 1:
                    ns.append(len(y))
                else:
                    ns = None
                    break
            if ns is None:
                continue
            for pred in preds:
                sels = []
                ok = True
                for (x, y, s), n in zip(xs_ys, ns):
                    sel = [o for o in s.objs if SC.holds(o, pred)]
                    if len(sel) != n:
                        ok = False
                        break
                    sels.append(sel)
                if not ok:
                    continue
                colour = None
                if len(set(uni)) == 1:
                    colour = uni[0]
                elif all({o.colour for o in sel} == {c} for sel, c in zip(sels, uni)):
                    colour = "self"
                if colour is None:
                    continue
                op = ED.ObjOp({"form": "count", "view": view, "rules": [[pred, ("keep",)]],
                               "params": {"colour": colour, "orient": orient}})
                if verify(op, pairs, budget):
                    add({"op": op, "loo": True, "proposing": len(pairs),
                         "simplicity": (1, CS.pred_size(pred), (0, 0, "count"))})
                    break
    return found


# ------------------------------------------------------------------ executing a sequence
def run_block(hs, b, budget, why):
    """Returns (candidates with their within-block place, aborted, marks)."""
    kind, vi, j = b
    vs = hs.views[vi]
    if kind == "S":
        c, ab = run_S(vs, j, budget, why)
        return ([c] if c else []), ab, [ED.COUNTS["op"]] if c else []
    if kind == "T":
        cs, ab = run_T(vs, budget, why)
        return cs, ab, [ED.COUNTS["op"]] if cs else []
    marks = []
    cs = run_W(vs, budget, marks)
    return cs, False, marks


def run_hole(hs, sequence, budget, log=None):
    """Execute `sequence` (blocks of hs) under `budget` operations; returns (top candidates, record).
    The operation counter starts at 0 (the frozen per-hole reset); the pair analysis is not repeated."""
    ED.COUNTS["op"] = 0
    seg0, edit0, cmp0 = ED.COUNTS["segment"], ED.COUNTS["edit"], CMP["n"]
    found = []
    s_found, s_aborted = set(), set()
    s_left = {}
    for b in sequence:
        if b[0] == "S":
            s_left[b[1]] = s_left.get(b[1], 0) + 1
    whys = {}
    capped = False
    for b in sequence:
        if ED.COUNTS["op"] > budget:
            capped = True
            break
        kind, vi = b[0], b[1]
        if kind == "S" and vi in s_aborted:
            continue
        if kind == "T" and (s_left.get(vi, 0) or vi in s_found or vi in s_aborted):
            continue
        start = ED.COUNTS["op"]
        why = whys.setdefault(vi, {})
        cs, ab, marks = run_block(hs, b, budget, why)
        if kind == "S":
            s_left[vi] -= 1
            if cs:
                s_found.add(vi)
            if ab:
                s_aborted.add(vi)
        for k, c in enumerate(cs):
            c["block"], c["inblock"], c["view"] = b, k, hs.views[vi].view
            found.append(c)
        if log is not None:
            log.append({"block": list(b), "n": ED.COUNTS["op"] - start, "aborted": ab, "end": ED.COUNTS["op"],
                        "marks": [m - 1 - start for m in marks], "cands": cs})
    if ED.COUNTS["op"] > budget:
        capped = True
    block_ops = ED.COUNTS["op"]
    top, rec = finish(hs, found)
    rec.update(capped=capped, block_ops=block_ops, budget=budget,
               counts={"op": ED.COUNTS["op"], "segment": ED.COUNTS["segment"] - seg0 + hs.setup_counts["segment"],
                       "edit": ED.COUNTS["edit"] - edit0 + hs.setup_counts["edit"], "compare": CMP["n"] - cmp0},
               why={VIEWS[vi]: w for vi, w in whys.items() if w})
    return top, rec


def finish(hs, found):
    """Canonical re-sort, the frozen symmetry forms, de-duplication, grouping, sort and cut (frozen code)."""
    found.sort(key=lambda c: (hs.hand_pos[c["block"]], c["inblock"]))
    cands = list(found)
    cands += CS.symfill_candidates(hs.hole)
    test_inputs = hs.test_inputs
    seen, uniq = set(), []
    for c in cands:
        if c["op"].sid not in seen:
            seen.add(c["op"].sid)
            uniq.append(c)
    groups = {}
    for c in uniq:
        key = tuple(c["op"](t) for t in test_inputs) if test_inputs else ()
        c["pred_key"] = key
        groups[key] = groups.get(key, 0) + 1
    for c in uniq:
        c["group"] = groups[c["pred_key"]] if c["pred_key"] and all(v is not None for v in c["pred_key"]) else 0
    uniq.sort(key=lambda c: (-c["group"], c["simplicity"]))
    rec = {"n_verified": len(uniq), "n_loo": sum(1 for c in uniq if c["loo"]),
           "correspondence": next((vs.view for vs in hs.views if not vs.skipped and vs.full), None),
           "correspondence_partial": next((vs.view for vs in hs.views if not vs.skipped and vs.partial), None)}
    return uniq[:CS.MAX_CANDS], rec


def hand_sequence(hs):
    return list(hs.blocks)


# ------------------------------------------------------------------ the trace (development)
def pred_hash(key):
    return hashlib.sha256(repr(key).encode()).hexdigest()[:16]


def cand_record(c):
    return {"sid": c["op"].sid, "spec": c["op"].to_json()["spec"], "loo": c["loo"], "proposing": c["proposing"],
            "simplicity": list(c["simplicity"]), "view": c.get("view")}


def trace_hole(hs, hand_log=None, hand_budget=FULL_BUDGET, cap=BLOCK_CAP):
    """Every block of the hole run once to its end or to `cap` operations: per block its operations, whether it was
    cut, and its candidates with the place of their last operation. Blocks that ended inside the hand-set run with
    the counter still at most its budget (`hand_log`; such a block met no cap check) are taken from it; the others
    are run here (T only when every S block of its view ended with none verified). Then the candidates' agreement
    keys on the test inputs and the symmetry forms."""
    done = {}
    if hand_log:
        for r in hand_log:
            if r["end"] <= hand_budget and not r["aborted"]:
                done[tuple(r["block"])] = dict(r, cut=False)
    out = []
    s_state = {}
    for b in hs.blocks:
        kind, vi = b[0], b[1]
        if kind == "T":
            st = s_state.get(vi, {"found": False, "cut": False})
            if st["found"] or st["cut"]:
                continue
        if b in done:
            r = done[b]
        else:
            ED.COUNTS["op"] = 0
            why = {}
            cs, ab, marks = run_block(hs, b, cap - 1, why)
            n = ED.COUNTS["op"]
            r = {"block": list(b), "n": n, "cut": bool(ab) or n >= cap, "marks": [m - 1 for m in marks],
                 "cands": cs}
        if kind == "S":
            st = s_state.setdefault(vi, {"found": False, "cut": False})
            st["found"] = st["found"] or bool(r["cands"])
            st["cut"] = st["cut"] or r["cut"]
        out.append(r)
    # agreement keys, as the frozen grouping computes them
    ED.COUNTS["op"] = 0
    sym = CS.symfill_candidates(hs.hole)
    sym_ops = ED.COUNTS["op"]
    blocks = []
    for r in out:
        cl = []
        for k, c in enumerate(r["cands"]):
            key = tuple(c["op"](t) for t in hs.test_inputs) if hs.test_inputs else ()
            d = cand_record(c)
            d.update(inblock=k, at=r["marks"][k], pk=pred_hash(key),
                     valid=bool(key) and all(v is not None for v in key), view=hs.views[r["block"][1]].view)
            cl.append(d)
        blocks.append({"block": list(r["block"]), "n": r["n"], "cut": r["cut"], "cands": cl})
    syml = []
    for c in sym:
        key = tuple(c["op"](t) for t in hs.test_inputs) if hs.test_inputs else ()
        d = cand_record(c)
        d.update(pk=pred_hash(key), valid=bool(key) and all(v is not None for v in key), view=None)
        syml.append(d)
    return {"blocks": blocks, "sym": syml, "sym_ops": sym_ops, "n_test": len(hs.test_inputs)}


def comparable(top):
    """The fields of a hole's candidate list that the equivalence checks compare."""
    return [[c["op"].sid, bool(c["loo"]), c["proposing"], c["group"], list(c["simplicity"]), c.get("view")]
            for c in top]


def dumps(x):
    return json.dumps(x, sort_keys=True, default=list)
