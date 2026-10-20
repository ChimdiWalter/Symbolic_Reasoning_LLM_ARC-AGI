"""ncv2-g1 budgeted search (Neural-CORA v2). It reads the demonstrations and the test input only.

1. **Candidate rules** are whole (selector, action) pairs, built from the demonstrations:
   - selectors: colour, size, size rank, boolean features, and relational `exists` guards;
   - actions: recolour (constant, colour of a referenced object, induced map); moves (constant vectors, slide, to
     border, step toward, gap closing, align, mirror, move until adjacent); copies (offsets, rays, at targets);
     lines; connect; reflect; rotate; scale; crop_to.
2. **Firing filter.** Per view, a rule whose selector selects no object in any demonstration is dropped. A cheap
   native probe detects this; the Occam restriction is in constraints.py.
3. **The symbolic order G1-CH**, pairing-aware: rule score = selector cost + action cost + correspondence-evidence
   bonuses (C+H-style, constraints.evidence) + a PAIRING bonus when the selector's colour is the observed source colour
   for that action's kind of change. Programs are best-first by view + number of rules + default + render + the sum
   of their rule scores. Two-rule programs come first when two kinds of change are observed.
4. **Execution.** Every candidate is compiled by bridge.py and run by the unchanged native interpreter on every
   demonstration, stopping at the first miss.
5. **Selection.** The same two-attempt rule as v1: the first distinct consistent prediction, then the next. Smaller
   budgets are exact truncations (`pred_at`).

`scores` may be passed in to replace the symbolic order (a learned joint guide plugs in here, later). The candidate
set, interpreter, checker and selection rule stay identical across arms.
"""
import heapq
import time
from collections import Counter

import numpy as np

from cora_neural_v2 import bridge as BR
from cora_neural_v2.constraints import evidence, sound_prunes
from cora_neural_v2.rast import GRAMMAR_VERSION, N

VIEWS = ("S1", "S2", "S3", "S5", "S4", "S6", "S7")
BOOL_FEATS = ("is_line", "is_rectangle", "has_hole", "touches_border", "is_unique_color", "is_unique_size",
              "is_multicolor", "is_container", "is_contained")
UNITS = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))
MAX_KEPT = 50


def T(f, v):
    return N("test", (f, "==", v))


def col(c):
    return N("color", (int(c),))


def near(c):
    return N("nearest", (T("color", int(c)),))


# ------------------------------------------------------------------ candidates (demonstrations only)
def selectors(ev):
    S = [(N("true", ()), 0.0, None)]
    S += [(T("color", c), 1.0, ("color", c)) for c in sorted(ev["in_cols"])]
    S += [(T("size", k), 1.5, None) for k in sorted(ev["sizes"]) if 1 <= k <= 12]
    S += [(T("size_rank", 0), 2.0, None), (T("size_rank_reversed", 0), 2.0, None)]
    S += [(T(f, True), 2.5, None) for f in BOOL_FEATS]
    for rel in ("adjacent", "inside", "contains"):
        S += [(N("exists", (rel, T("color", c))), 3.0, None) for c in sorted(ev["in_cols"])]
    return S


def actions(ev):
    """[(ACTION node, cost, kind)] - kind keys the evidence and pairing bonuses."""
    ins, outs = sorted(ev["in_cols"]), sorted(ev["out_cols"])
    A = [(N("keep", ()), 0.2, "keep"), (N("delete", ()), 0.5, "delete")]
    A += [(N("recolor", (col(c),)), 1.0, ("recolour", c)) for c in outs]
    A += [(N("recolor", (N("color_of", (near(c),)),)), 2.0, "recolour_ref") for c in ins]
    if ev["recol_pairs"]:
        A.append((N("recolor", (N("color_map", (tuple(sorted(ev["recol_pairs"])),)),)), 1.5, "recolour_map"))
    vecs = list(ev["vectors"]) + [u for u in UNITS if u not in ev["vectors"]]
    A += [(N("translate", (N("vec", v),)), 1.0 + 0.25 * (abs(v[0]) + abs(v[1])), ("move_vec", v)) for v in vecs]
    for d in ("up", "down", "left", "right"):
        A += [(N("translate", (N("slide", (d,)),)), 1.5, "move_rel"), (N("translate", (N("to_border", (d,)),)), 2.0, "move_rel")]
        A += [(N("move_until_adjacent_to", (N("dir", (d,)), N("nearest_of_color", (c,)))), 2.5, "move_rel") for c in ins]
    for c in ins:
        A.append((N("translate", (N("step_toward", (near(c),)),)), 2.5, "move_rel"))
        for ax in ("horizontal", "vertical"):
            A.append((N("translate", (N("gap_closing", (near(c), ax)),)), 2.5, "move_rel"))
            A.append((N("translate", (N("align_to", (near(c), ax)),)), 2.5, "move_rel"))
    A += [(N("translate", (N("mirror", (ax,)),)), 2.5, "move_rel") for ax in ("horizontal", "vertical")]
    offs = list(ev["copy_offsets"]) + [o for o in UNITS + ((0, 2), (0, -2), (2, 0), (-2, 0)) if o not in ev["copy_offsets"]]
    A += [(N("copy_offsets", ((N("vec", o),),)), 2.0, ("copy_off", o)) for o in offs]    # fallback offsets: order only
    A += [(N("copy_rays", ((N("vec", u),),)), 2.5, "copy") for u in UNITS]
    for c in ins:
        for al in ("bbox_center", "bbox_origin"):
            A.append((N("copy_targets", (T("color", c), N("align_mode", (al,)))), 2.5, "copy"))
    for c in outs:
        for ax in ("horizontal", "vertical", "both"):
            for ex in ("to_border", "to_object"):
                A.append((N("fill_line", (ax, col(c), ex)), 2.0 + (0.2 if ax == "both" else 0) + (0.2 if ex == "to_object" else 0),
                          ("line", c)))
        A += [(N("connect", (near(s), col(c))), 2.5, ("connect", c)) for s in ins]
    A += [(N("reflect", (N("axis", (ax,)),)), 2.5, "geometry") for ax in ("horizontal", "vertical", "diag_main", "diag_anti")]
    A += [(N("rotate", (N("angle", (k,)),)), 2.5, "geometry") for k in (90, 180, 270)]
    A += [(N("scale", (N("int", (k,)),)), 3.0, "geometry") for k in (2, 3)]
    A.append((N("crop_to", (N("bbox_self", ()),)), 3.0, "crop"))
    return A


def renders(ev, train):
    pr = sound_prunes(train)
    R = []
    if pr["same_as_input_allowed"]:
        R.append((N("same_as_input", ()), 0.0))
        crop_cost = 6.0                                     # allowed (not provably impossible) but implausible
    else:
        crop_cost = 1.0
    regions = [N("bbox", (N("largest", (N("true", ()),)),))] + \
              [N("bbox", (N("unique", (T("color", c),)),)) for c in sorted(ev["in_cols"])] + \
              [N("quadrant", (q,)) for q in range(4)]
    R += [(N("crop", (r,)), crop_cost) for r in regions]
    R.append((N("crop_by_action", ()), crop_cost + 0.5))
    if pr["constant_shape"] is not None:
        h, w = pr["constant_shape"]
        R.append((N("constant_shape", (int(h), int(w), col(0))), 1.5))
    return R


# ------------------------------------------------------------------ the symbolic, pairing-aware order G1-CH
def _kind_family(kind):
    k = kind[0] if isinstance(kind, tuple) else kind
    return {"recolour": "recolour", "recolour_ref": "recolour", "recolour_map": "recolour", "move_vec": "move",
            "move_rel": "move", "delete": "delete", "copy_off": "copy", "copy": "copy", "line": "line",
            "connect": "add"}.get(k)


def action_bonus(kind, ev):
    k = kind[0] if isinstance(kind, tuple) else kind
    b = 0.0
    if k == "recolour" and kind[1] in ev["recol_targets"]:
        b += 2.0
    if k == "recolour_map":
        b += 2.0
    consistent = len(ev["vectors"]) == 1                    # one displacement explains every observed move
    if k == "move_vec" and kind[1] in ev["vectors"]:
        b += (1.0 + 0.5 * min(ev["vectors"][kind[1]], 4)) if consistent else 0.5
    if k == "move_rel" and ev["vectors"]:
        b += 0.75 if consistent else 2.5                     # several different moves: relational vectors first
    if k == "delete" and ev["deleted_any"]:
        b += 1.5
    if k == "line" and ev["line_added"] and kind[1] in ev["added_cols"]:
        b += 2.5
    if k == "copy_off" and kind[1] in ev["copy_offsets"]:
        b += 2.5 + 0.5 * min(ev["copy_offsets"][kind[1]], 4)
    if k == "copy" and "copy" in ev["kinds"]:
        b += 1.0
    if k == "connect" and kind[1] in ev["added_cols"] and ev["kinds"] & {"add", "line"}:
        b += 1.0
    return b


def pairing_bonus(sel_key, kind, ev):
    """+1.5 when a colour selector names the observed source colour for this action's kind of change."""
    fam = _kind_family(kind)
    if sel_key is None or sel_key[0] != "color" or fam is None:
        return 0.0
    src = ev["src"].get({"line": "copy", "add": "copy"}.get(fam, fam), set())
    return 1.5 if sel_key[1] in src else 0.0


def symbolic_scores(ev, rules):
    """{rule index: score} for the G1-CH order. `rules` = [(sel node, sel cost, sel key, act node, act cost, kind)]."""
    return [-(sc + ac) + action_bonus(kind, ev) + pairing_bonus(sk, kind, ev)
            for (_, sc, sk, _, ac, kind) in rules]


# ------------------------------------------------------------------ exact view equivalence
def distinct_views(task):
    """Views whose native segmentation differs on some grid this task will run on (every demonstration input and the
    test input). A program under a view with an identical segmentation of all those grids behaves identically on
    every one of them, so collapsing such views is an exact, proven equivalence, not an observational one."""
    from geocat_arc.object_reasoning.segmentation import segment
    from geocat_arc.object_reasoning.types import SegmentationVariant as SV
    from geocat_arc.perception.grid import Grid
    grids = [a for a, _ in task["train"]] + list(task["test_inputs"])
    keep, sigs = [], set()
    for v in VIEWS:
        try:
            sig = tuple(tuple(sorted(tuple(sorted(o.cells)) + (int(o.color),) for o in segment(Grid(np.asarray(g, dtype=np.int32)), SV(v))))
                        for g in grids)
        except Exception:                                   # noqa: BLE001  (a view native cannot segment is skipped)
            continue
        if sig not in sigs:
            sigs.add(sig)
            keep.append(v)
    return keep


# ------------------------------------------------------------------ firing probe (Occam filter, same for every arm)
def fires(view, sel, train):
    probe = N("program", (view, (N("rule", (sel, N("delete", ()))),), "keep", N("same_as_input", ())))
    d = BR.compile_program(probe)
    for a, _ in train:
        out = BR.run_native_dict(d, a)
        if out is not None and not np.array_equal(out, np.asarray(a)):
            return True
    return False


# ------------------------------------------------------------------ best-first enumeration over whole rules
def enumerate_programs(task, budget, rule_scores=None):
    """Yield (program AST, score) best-first. rule_scores(view, rules) may supply learned joint scores."""
    train = task["train"]
    ev = evidence(train)
    S, A, R = selectors(ev), actions(ev), renders(ev, train)
    two_first = len(ev["kinds"] - {"reshape"}) >= 2
    sn = {1: -4.0, 2: 0.0} if two_first else {1: 0.0, 2: -4.0}
    sn[0] = 0.0 if not sound_prunes(train)["same_as_input_allowed"] else -6.0   # no-rule programs: pure renders
    sd = {"keep": 0.0, "delete": -0.5 if ev["deleted_any"] else -1.0}
    sv = {v: -0.5 * i for i, v in enumerate(VIEWS)}
    per_view = {}
    views = distinct_views(task)
    for v in views:
        live = [(s, c, k) for s, c, k in S if fires(v, s, train)]
        rules = [(s, sc, sk, a, ac, kind) for s, sc, sk in live for a, ac, kind in A]
        scores = rule_scores(v, rules, ev) if rule_scores else symbolic_scores(ev, rules)
        order = np.argsort(-np.asarray(scores, dtype=float), kind="stable") if rules else []
        per_view[v] = ([rules[i] for i in order], [float(scores[i]) for i in order])
    R = sorted(R, key=lambda r: r[1])
    rend_sc = [-c for _, c in R]
    heap, seen = [], set()

    def push(st):
        if st in seen:
            return
        v, n, ird, idf = st[0], st[1], st[2], st[3]
        rules, rs = per_view[VIEWS[v]]
        idx = st[4:]
        if ird >= len(R) or idf >= 2 or any(i >= len(rules) for i in idx):
            return
        s = sv[VIEWS[v]] + sn.get(n, -8.0) + rend_sc[ird] + list(sd.values())[idf] + sum(rs[i] for i in idx)
        seen.add(st)
        heapq.heappush(heap, (-s, st))

    for v in [VIEWS.index(x) for x in views]:
        push((v, 0, 0, 0))
        push((v, 1, 0, 0, 0))
        push((v, 2, 0, 0, 0, 1))
        push((v, 2, 0, 0, 1, 0))
    out = 0
    defaults = list(sd)
    while heap and out < budget:
        negs, st = heapq.heappop(heap)
        v, n, ird, idf, idx = st[0], st[1], st[2], st[3], st[4:]
        push((v, n, ird + 1, idf) + idx)
        push((v, n, ird, idf + 1) + idx)
        for j in range(len(idx)):
            push((v, n, ird, idf) + tuple(i + 1 if k == j else i for k, i in enumerate(idx)))
        rules = per_view[VIEWS[v]][0]
        chosen = [rules[i] for i in idx]
        if n == 2 and (idx[0] == idx[1] or chosen[0][0] == chosen[1][0]):
            continue                                        # a repeated selector can never fire as the second rule
        render = R[ird][0]
        if (render.op == "crop_by_action") != any(r[3].op == "crop_to" for r in chosen):
            continue                                        # crop_by_action needs exactly a crop_to rule, and vice versa
        prog = N("program", (VIEWS[v], tuple(N("rule", (r[0], r[3])) for r in chosen), defaults[idf], render))
        out += 1
        yield prog, -negs


def search(task, budget, rule_scores=None, cpu_cap_s=None):
    """Run the budget; the same record format as cora_neural_v1.search.search_typed. With `cpu_cap_s`, enumeration also
    stops after that many process-CPU seconds (setup included) and the record says so (`state.cpu_truncated`)."""
    train, test_in = task["train"], task["test_inputs"][0]
    c0, e0 = time.process_time(), BR.STATS["executions"]
    preds, pred_at, first_at, kept = [], [], {}, []
    n = n_consistent = n_rejected = 0
    fail_demo = Counter()
    truncated = False
    for prog, s in enumerate_programs(task, budget, rule_scores):
        if cpu_cap_s is not None and time.process_time() - c0 > cpu_cap_s:
            truncated = True
            break
        n += 1
        ok, wrong = BR.fit(prog, train)
        if not ok:
            fail_demo[len(wrong) - 1] += 1
            continue
        n_consistent += 1
        p = BR.execute(prog, test_in)
        if p is None:
            n_rejected += 1
            continue
        key = p.tobytes() + bytes(p.shape)
        if key not in first_at:
            first_at[key] = n
            if len(preds) < MAX_KEPT:
                preds.append(p.tolist())
                pred_at.append(n)
                kept.append({"at": n, "score": round(float(s), 4)})
    distinct = len(first_at)
    diag = (["NO_FIT_OBSERVED"] if n_consistent == 0 else []) + (["AMBIGUOUS_PREDICTIONS"] if distinct >= 2 else []) + \
           (["UNVERIFIED_QUERY"] if distinct == 1 else []) + (["PROGRAM_REJECTED"] if n_rejected else [])
    return {"grammar": GRAMMAR_VERSION, "attempts": preds[:2], "predictions": preds, "pred_at": pred_at,
            "n_candidates": n, "n_consistent": n_consistent, "n_distinct_predictions": distinct,
            "state": {"budget": budget, "fail_demo": {str(k): v for k, v in sorted(fail_demo.items())},
                      "diagnoses": diag, "n_test_rejected": n_rejected, "cpu_cap_s": cpu_cap_s, "cpu_truncated": truncated},
            "executions": BR.STATS["executions"] - e0, "cpu_s": round(time.process_time() - c0, 3)}


# ------------------------------------------------------------------ exhaustive bounded check (G2 diagnostics)
def exhaustive_single_rule(task, cpu_cap_s=300.0, keep=20):
    """Every program of the bounded single-rule ncv2-g1 space, with no ordering and no budget: each distinct view, each
    live selector, each candidate action, each default and each allowed render, plus the zero-rule programs. It
    reports whether any fits every demonstration (demonstrations only).

    It distinguishes "a single-rule g1 program exists, so the budgeted search missed it" from "no single-rule g1
    program exists". It says nothing about two-rule or richer programs. The size of the space is counted first. The
    loop is render-major, cheapest render first (same_as_input when it is allowed), so a run stopped at `cpu_cap_s`
    CPU seconds has covered whole renders; it then reports `complete=False` and the fraction checked."""
    train, test_in = task["train"], task["test_inputs"][0]
    ev = evidence(train)
    A, R = actions(ev), sorted(renders(ev, train), key=lambda r: r[1])
    c0 = time.process_time()
    live = {v: [s for s, _, _ in selectors(ev) if fires(v, s, train)] for v in distinct_views(task)}

    def space(r):
        for v, sels in live.items():
            for d in DEFAULTS_:
                yield N("program", (v, (), d, r))
            for s in sels:
                for a, _, _ in A:
                    if (r.op == "crop_by_action") == (a.op == "crop_to"):
                        for d in DEFAULTS_:
                            yield N("program", (v, (N("rule", (s, a)),), d, r))
    n_total = sum(1 for r, _ in R for _ in space(r))
    n, fits, preds = 0, [], set()
    complete = True
    for r, _ in R:
        for p in space(r):
            if time.process_time() - c0 > cpu_cap_s:
                complete = False
                break
            n += 1
            if BR.fit(p, train)[0]:
                out = BR.execute(p, test_in)
                if out is not None:
                    preds.add(out.tobytes() + bytes(out.shape))
                if len(fits) < keep:
                    fits.append({"program": p, "test_pred": None if out is None else out.tolist()})
        if not complete:
            break
    return {"n_total": n_total, "n_checked": n, "fraction_checked": round(n / n_total, 4) if n_total else 1.0,
            "n_fitting_kept": len(fits), "any_fit": bool(fits), "distinct_test_predictions": len(preds),
            "fits": fits, "complete": complete, "cpu_s": round(time.process_time() - c0, 1)}


DEFAULTS_ = ("keep", "delete")
