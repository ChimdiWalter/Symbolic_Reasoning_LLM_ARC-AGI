"""ncv2-g2 search. It reads the demonstrations and the test input only. Answers are never read here.

**Candidate generation.** The ncv2-g1 generator (`cora_neural_v2.search`, unchanged and imported) is completed over
constructs that ncv2-g1 already compiles. Native program classes are added.

1. Object rules: every ncv2-g1 selector and action, plus the following.
   - Negated boolean selectors, `(test f == #f)`.
   - Feature-keyed references. `nearest`, `unique` and `largest` of `(test color == c)` and of both polarities of
     every boolean feature. They are used by `color_of`, `step_toward`, `vector_to`, `align_to`, `gap_closing`,
     `move_until_adjacent_to`, `paint` and `connect`, and as `copy_targets`.
   - Recolouring by `most_common_color` / `least_common_color`, and an induced `feature_map`. The map is built only
     from (feature value, new colour) pairs of recoloured demonstration objects, and only when it is a function.
   - `move_to` the common destination of moved objects; `reflect_shift` / `rotate_shift` by observed displacements.
   - `extract_part` (the rotations and flips of the object's own box) at observed copy offsets.
   - Binding composites: `(rule_with ((?t R)) P (composite (translate (step_toward ?t)) (recolor (color_of ?t))))`.
   - **Dependent selector–action pairs.** A selector `(test f == v)` paired with a reference keyed by
     `(test f == (not v))` gets a pairing bonus. This is the "non-lines take the colour of the nearest line" shape.
2. Renders: ncv2-g1's, plus separator-cell crops and `constant_shape` with each observed output background colour.
3. Program classes, which are few and cheap, so they enter the agenda first:
   - symmetry completion (6 symmetries) and counting (5 modes), enumerated;
   - pixel rules, panel reductions and generative programs, proposed by native's own inducers on the demonstrations.
     They run under the sealed v23 flags (`V23_FLAGS`; the learned-generator asset stays off) and are decompiled
     into typed ASTs.

**Order.** Object programs keep the G1-CH best-first scheme (views, 0–2 rules, defaults, renders). Each new
candidate has a cost, and the evidence and dependent-pairing bonuses are added. Budgets truncate exactly
(`pred_at`). The record keeps the program behind each kept prediction, which the frozen G2 runner did not.
"""
import contextlib
import heapq
import os
import time
from collections import Counter

import numpy as np

from cora_neural_v2 import search as G1S
from cora_neural_v2.constraints import evidence, sound_prunes
from cora_neural_v2.rast import ASTError, N
from cora_neural_v2g2 import classes as C
from cora_neural_v2g2 import grammar as G

V23_FLAGS = {"ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1", "ARC_RAY_EXT": "1"}
VIEWS = G1S.VIEWS
BOOL_FEATS = G1S.BOOL_FEATS
SIZE_FEATS = ("size", "size_rank", "bbox_height", "bbox_width", "hole_count", "count_of_same_color",
              "count_of_same_shape", "aligned_row_count", "aligned_col_count")
MAX_KEPT = 50
T, col = G1S.T, G1S.col


@contextlib.contextmanager
def v23_flags():
    old = {k: os.environ.get(k) for k in V23_FLAGS}
    os.environ.update(V23_FLAGS)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ------------------------------------------------------------------ object-rule candidates
def feature_preds(ev):
    """(PRED, key): colour tests and both polarities of every boolean feature."""
    P = [(T("color", c), ("color", c)) for c in sorted(ev["in_cols"])]
    P += [(T(f, v), ("bool", f, v)) for f in BOOL_FEATS for v in (True, False)]
    return P


def selectors(ev):
    S = G1S.selectors(ev)
    S += [(T(f, False), 2.5, ("bool", f, False)) for f in BOOL_FEATS]
    return [(s, c, k if k is not None else (("bool", s.args[0], s.args[2]) if s.op == "test" and s.args[0] in BOOL_FEATS else None))
            for s, c, k in S]


def references(ev):
    """(REF node, cost, key) - g1 used only nearest-by-colour."""
    R = []
    for p, k in feature_preds(ev):
        R.append((N("nearest", (p,)), 0.0 if k[0] == "color" else 0.5, ("nearest",) + k))
        R.append((N("unique", (p,)), 0.75, ("unique",) + k))
    R.append((N("largest", (N("true", ()),)), 0.5, ("largest",)))
    R += [(N("container", ()), 0.5, ("container",)), (N("contained", ()), 0.5, ("contained",)),
          (N("shape_twin", ()), 0.75, ("twin",))]
    return R


def actions(ev, train):
    A = list(G1S.actions(ev))
    refs = references(ev)
    rec = bool(ev["recol_targets"])
    line_cols = sorted(ev["added_cols"])
    for r, rc, rk in refs:
        extra = [(N("recolor", (N("color_of", (r,)),)), 2.0 + rc, ("recolour_rel", rk)),
                 (N("translate", (N("step_toward", (r,)),)), 2.5 + rc, ("move_rel2", rk)),
                 (N("translate", (N("vector_to", (r,)),)), 2.75 + rc, ("move_rel2", rk)),
                 (N("paint", (r,)), 3.0 + rc, ("paint", rk))]
        extra += [(N("connect", (r, col(c))), 3.0 + rc, ("connect2", rk, c)) for c in line_cols[:2]]
        extra += [(N("translate", (N(op, (r, ax)),)), 3.0 + rc, ("move_rel2", rk))
                  for op in ("align_to", "gap_closing") for ax in ("horizontal", "vertical")]
        extra += [(N("move_until_adjacent_to", (N("dir", (d,)), r)), 3.0 + rc, ("move_rel2", rk))
                  for d in ("up", "down", "left", "right")]
        A += extra
    for p, k in feature_preds(ev):
        if k[0] == "bool":
            for al in ("bbox_center", "bbox_origin"):
                A.append((N("copy_targets", (p, N("align_mode", (al,)))), 3.0, ("copy2", k)))
    if rec:
        A += [(N("recolor", (N("most_common_color", ()),)), 2.5, ("recolour_freq",)),
              (N("recolor", (N("least_common_color", ()),)), 2.5, ("recolour_freq",))]
        A += feature_map_actions(train)
    dests = move_destinations(train)
    A += [(N("move_to", (N("vec", d),)), 2.0, ("move_to",)) for d in dests]
    for v in list(ev["vectors"])[:4]:
        A += [(N("reflect_shift", (N("axis", (ax,)), N("vec", v))), 3.0, ("geometry_shift",)) for ax in ("horizontal", "vertical")]
        A += [(N("rotate_shift", (N("angle", (k,)), N("vec", v))), 3.0, ("geometry_shift",)) for k in (90, 180, 270)]
    for o in list(ev["copy_offsets"])[:4]:
        A += [(N("extract_part", (N("bbox_self", ()), k, f, N("vec", o))), 3.0, ("extract",)) for k in range(4) for f in (0, 1)]
    for r, rc, rk in refs:
        if rk[0] in ("nearest", "unique"):
            parts = (N("translate", (N("step_toward", (N("var", ("?t",)),)),)),
                     N("recolor", (N("color_of", (N("var", ("?t",)),)),)))
            body = N("composite", (parts,))
            A.append((("bind", r, body), 3.5 + rc, ("bind", rk)))
    seen, uniq = set(), []                                          # first (cheapest, ncv2-g1's own) copy of each action
    for a in A:
        key = repr(a[0])
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq


def feature_map_actions(train):
    """Induced feature_map recolours. For each scalar feature, build the (value -> new colour) map over recoloured S1
    objects, keeping it only if it is a function covering at least two values. Values come from native's own
    `_feature_value`, the function `feature_map` evaluates with."""
    from geocat_arc.object_reasoning.expressions import _feature_value
    from geocat_arc.object_reasoning.features import register_builtin_features
    from geocat_arc.object_reasoning.segmentation import background_for, segment
    from geocat_arc.object_reasoning.types import GridContext, SegmentationVariant as SV
    from geocat_arc.perception.grid import Grid
    register_builtin_features()
    maps = {f: {} for f in SIZE_FEATS}
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return []
        g = Grid(A.astype(np.int32))
        bg = background_for(g, SV("S1"))
        objs = segment(g, SV("S1"), bg)
        ctx = GridContext(grid=g, objects=objs, background=bg, pair_index=0, role="input", variant=SV("S1"))
        for o in objs:
            vals = {int(B[r, c]) for r, c in o.cells}
            if len(vals) != 1 or vals == {int(o.color)} or vals == {bg}:
                continue
            new = next(iter(vals))
            for f in list(maps):
                try:
                    v = _feature_value(f, o, ctx)
                except Exception:                                   # noqa: BLE001 (undefined for this object)
                    maps.pop(f)
                    continue
                if isinstance(v, bool) or not isinstance(v, (int, float, np.integer)) or int(v) != v:
                    maps.pop(f)
                    continue
                if maps[f].get(int(v), new) != new:
                    maps.pop(f)
                    continue
                maps[f][int(v)] = new
    return [(N("recolor", (N("feature_map", (f, tuple(sorted(m.items())))),)), 2.0, ("recolour_featmap",))
            for f, m in maps.items() if len(m) >= 2]


def move_destinations(train):
    """The common output origin of moved S1 objects, if every moved object in every demonstration ends there."""
    from cora_neural_v1.space import _objects
    dests = set()
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return []
        outs = _objects(B)
        for x in _objects(A):
            mv = [y for y in outs if y["shape"] == x["shape"] and y["colour"] == x["colour"] and y["origin"] != x["origin"]
                  and not any(z["origin"] == x["origin"] and z["shape"] == x["shape"] for z in outs)]
            if len(mv) == 1:
                dests.add(tuple(int(v) for v in mv[0]["origin"]))
    return sorted(dests) if len(dests) == 1 else []


def renders(ev, train):
    R = list(G1S.renders(ev, train))
    pr = sound_prunes(train)
    if not pr["same_as_input_allowed"]:
        R += [(N("crop", (N("separator_cell", (i, j)),)), 2.0) for i in range(3) for j in range(3)]
    if pr["constant_shape"] is not None:
        h, w = pr["constant_shape"]
        bgs = Counter(int(v) for _, b in train for v in np.asarray(b).ravel())
        R += [(N("constant_shape", (int(h), int(w), col(c))), 1.75) for c, _ in bgs.most_common(2) if c != 0]
    return R


# ------------------------------------------------------------------ evidence (ordering only, never pruning)
def evidence2(train):
    """ncv2-g1's correspondence evidence plus "moved and recoloured" objects.

    Such an object's shape reappears elsewhere in the output in the colour of another input object. ncv2-g1's evidence
    sees neither a move (the colour changed) nor a recolour (the cells moved). This is the approach-and-adopt
    pattern."""
    from cora_neural_v1.space import _objects
    ev = evidence(train)
    mr, adopted = 0, set()
    for a, b in train:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            continue
        ins, outs = _objects(A), _objects(B)
        in_cols = {int(x["colour"]) for x in ins}
        for x in ins:
            for y in outs:
                if y["shape"] == x["shape"] and y["colour"] != x["colour"] and y["origin"] != x["origin"] \
                        and int(y["colour"]) in in_cols:
                    mr += 1
                    adopted.add(int(y["colour"]))
                    break
    ev["moved_recoloured"], ev["adopted"] = mr, adopted
    return ev


# ------------------------------------------------------------------ scores
def bonus(sel_key, kind, ev):
    k = kind[0] if isinstance(kind, tuple) else kind
    if k in ("recolour", "recolour_ref", "recolour_map", "move_vec", "move_rel", "delete", "copy_off", "copy", "line", "connect"):
        return G1S.action_bonus(kind, ev) + G1S.pairing_bonus(sel_key if sel_key and sel_key[0] == "color" else None, kind, ev)
    b = 0.0
    several = len(ev["recol_targets"]) >= 2 or len({t for _, t in ev["recol_pairs"]}) >= 2
    if k == "recolour_rel" and ev["recol_targets"]:
        b += 1.0 + (1.0 if several else 0.0)
    if k == "recolour_freq" and ev["recol_targets"]:
        b += 0.5
    if k == "recolour_featmap":
        b += 2.5
    if k in ("move_rel2", "bind") and ev["vectors"]:
        b += 1.5 if len(ev["vectors"]) > 1 else 0.5
    if k == "bind" and ev["recol_targets"]:
        b += 1.0
    if ev.get("moved_recoloured"):
        b += {"bind": 3.0, "move_rel2": 1.0, "recolour_rel": 0.5}.get(k, 0.0)
    if k == "move_to":
        b += 2.0
    if k == "geometry_shift" and ev["vectors"]:
        b += 0.5
    if k == "extract" and "copy" in ev["kinds"]:
        b += 1.0
    if k == "copy2" and "copy" in ev["kinds"]:
        b += 1.0
    if k == "paint" and ev["recol_targets"]:
        b += 0.5
    # dependent pair: (test f == v) with a reference keyed by (test f == not v)
    ref_key = kind[1] if isinstance(kind, tuple) and len(kind) > 1 and isinstance(kind[1], tuple) else None
    if sel_key and sel_key[0] == "bool" and ref_key and len(ref_key) == 4 and ref_key[1] == "bool" \
            and ref_key[2] == sel_key[1] and ref_key[3] == (not sel_key[2]):
        b += 2.0
    return b


def rule_node(sel, act):
    if isinstance(act, tuple) and act and act[0] == "bind":
        _, ref, body = act
        return N("rule_with", ((("?t", ref),), sel, body))
    return N("rule", (sel, act))


# ------------------------------------------------------------------ program-class candidates
def class_candidates(task, gen_deadline_s=20.0):
    """Typed program-class hypotheses for this task: enumerated symmetry and counting forms, and native-induced pixel
    rules, panel reductions and generative programs (decompiled; undecompilable ones are counted, not used)."""
    from geocat_arc.object_reasoning.types import to_grid_pairs
    train = task["train"]
    same = all(np.asarray(a).shape == np.asarray(b).shape for a, b in train)
    out, refused = [], Counter()
    if same:
        out += [N("symmetry_completion", (s,)) for s in C.SYMMETRIES]
    if all(np.asarray(b).size <= 30 for _, b in train):
        out += [N("counting", (m,)) for m in C.COUNTING_MODES]
    gp = to_grid_pairs([(np.asarray(a), np.asarray(b)) for a, b in train])
    with v23_flags():
        natives = []
        try:
            from geocat_arc.object_reasoning.pixel_rules import induce_pixel_rule
            pix = induce_pixel_rule(gp) if same else None
            if pix is not None:
                natives.append({"program_class": "reduction", "split": {"kind": "pixel_rule"}, "mode": pix["mode"], "params": pix})
        except Exception:                                           # noqa: BLE001
            refused["pixel_rule_inducer_error"] += 1
        try:
            from geocat_arc.object_reasoning.reduction import induce_reduction_candidates
            natives += [p.to_dict() for p in induce_reduction_candidates(gp)]
        except Exception:                                           # noqa: BLE001
            refused["reduction_inducer_error"] += 1
        try:
            from geocat_arc.object_reasoning.generative import induce_generative_candidates
            natives += [p.to_dict() for p in induce_generative_candidates(gp, deadline=time.monotonic() + gen_deadline_s)]
        except Exception:                                           # noqa: BLE001
            refused["generative_inducer_error"] += 1
    for d in natives:
        try:
            out.append(G.decompile(d))
        except ASTError:
            refused[f"not_exposed:{d.get('program_class')}"] += 1
    out += enumerated_generators(train) if same else []
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq, dict(refused)


def enumerated_generators(train):
    """Single-generator GenerativeProgram candidates that native's inducer never proposes. Its precondition needs
    objects to fuse or new objects to appear (`generative._fusion_signature`), so, e.g., a same-colour ray that merges
    with its seed is executable but never induced.

    The enumeration is bounded and is offered only when the demonstrations add cells. It covers: uniform rays in 4
    directions (own colour, or each added colour); row, column and cross lines; halo; fill_interior; all on S1, over
    the input, for all objects or one input colour."""
    ev = evidence(train)
    if not ev["added"]:
        return []
    added = sorted(ev["added_cols"])[:2]
    rules = [N("grule", ("ray", (N("gp", ("direction", d)),))) for d in ("up", "down", "left", "right")]
    rules += [N("grule", ("ray", (N("gp", ("direction", d)), N("gp", ("color", c))))) for d in ("up", "down", "left", "right") for c in added]
    rules += [N("grule", (k, ())) for k in ("row_line", "col_line", "cross_line", "halo", "fill_interior")]
    rules += [N("grule", (k, (N("gp", ("color", c)),))) for k in ("row_line", "col_line", "cross_line", "halo", "fill_interior") for c in added]
    sels = [N("gsel", ((),))] + [N("gsel", ((N("sel_color", (c,)),),)) for c in sorted(ev["in_cols"])]
    return [N("generative", ("S1", (N("gen", (s, r)),), "over_input", 0, False, "none")) for s in sels for r in rules]


# ------------------------------------------------------------------ the agenda
def enumerate_programs(task, budget, rule_scores=None, classes=True, gen_deadline_s=20.0, info=None):
    """Yield (program AST, score): program-class candidates first, then object programs best-first."""
    train = task["train"]
    ev = evidence2(train)
    out = 0
    if classes:
        cands, refused = class_candidates(task, gen_deadline_s)
        if info is not None:
            info["class_candidates"], info["class_refused"] = len(cands), refused
        for p in cands:
            if out >= budget:
                return
            out += 1
            yield p, 0.0
    S, A, R = selectors(ev), actions(ev, train), renders(ev, train)
    two_first = len(ev["kinds"] - {"reshape"}) >= 2
    sn = {1: -4.0, 2: 0.0} if two_first else {1: 0.0, 2: -4.0}
    sn[0] = 0.0 if not sound_prunes(train)["same_as_input_allowed"] else -6.0
    sd = {"keep": 0.0, "delete": -0.5 if ev["deleted_any"] else -1.0}
    sv = {v: -0.5 * i for i, v in enumerate(VIEWS)}
    per_view = {}
    views = G1S.distinct_views(task)
    for v in views:
        live = [(s, c, k) for s, c, k in S if G1S.fires(v, s, train)]
        rules = [(s, sc, sk, a, ac, kind) for s, sc, sk in live for a, ac, kind in A]
        scores = rule_scores(v, rules, ev) if rule_scores else [-(sc + ac) + bonus(sk, kind, ev) for (_, sc, sk, _, ac, kind) in rules]
        order = np.argsort(-np.asarray(scores, dtype=float), kind="stable") if rules else []
        per_view[v] = ([rules[i] for i in order], [float(scores[i]) for i in order])
    R = sorted(R, key=lambda r: r[1])
    rend_sc = [-c for _, c in R]
    heap, seen = [], set()
    defaults = list(sd)

    def push(st):
        if st in seen:
            return
        v, n, ird, idf = st[0], st[1], st[2], st[3]
        rules, rs = per_view[VIEWS[v]]
        idx = st[4:]
        if ird >= len(R) or idf >= 2 or any(i >= len(rules) for i in idx):
            return
        seen.add(st)
        heapq.heappush(heap, (-(sv[VIEWS[v]] + sn.get(n, -8.0) + rend_sc[ird] + list(sd.values())[idf] + sum(rs[i] for i in idx)), st))

    for v in [VIEWS.index(x) for x in views]:
        push((v, 0, 0, 0))
        push((v, 1, 0, 0, 0))
        push((v, 2, 0, 0, 0, 1))
        push((v, 2, 0, 0, 1, 0))
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
            continue
        render = R[ird][0]
        if (render.op == "crop_by_action") != any(not isinstance(r[3], tuple) and r[3].op == "crop_to" for r in chosen):
            continue
        prog = N("program", (VIEWS[v], tuple(rule_node(r[0], r[3]) for r in chosen), defaults[idf], render))
        out += 1
        yield prog, -negs


def search(task, budget, rule_scores=None, cpu_cap_s=None, classes=True, gen_deadline_s=20.0):
    """The same record as cora_neural_v1/v2 search, plus the program behind each kept prediction and the first fit."""
    from cora_neural_v2.rast import to_sexpr
    train, test_in = task["train"], task["test_inputs"][0]
    c0 = time.process_time()
    preds, pred_at, programs, first_at = [], [], [], {}
    n = n_consistent = n_rejected = 0
    first_fit = None
    fail_demo = Counter()
    info = {}
    truncated = False
    for prog, s in enumerate_programs(task, budget, rule_scores, classes, gen_deadline_s, info):
        if cpu_cap_s is not None and time.process_time() - c0 > cpu_cap_s:
            truncated = True
            break
        n += 1
        try:
            ok, wrong = G.fit(prog, train)
        except ASTError:
            fail_demo["ill_typed"] += 1
            continue
        if not ok:
            fail_demo[len(wrong) - 1] += 1
            continue
        n_consistent += 1
        first_fit = first_fit or n
        p = G.execute(prog, test_in)
        if p is None:
            n_rejected += 1
            continue
        key = p.tobytes() + bytes(p.shape)
        if key not in first_at:
            first_at[key] = n
            if len(preds) < MAX_KEPT:
                preds.append(p.tolist())
                pred_at.append(n)
                programs.append(to_sexpr(prog))
    distinct = len(first_at)
    return {"grammar": G.GRAMMAR_VERSION, "attempts": preds[:2], "predictions": preds, "pred_at": pred_at,
            "programs": programs, "first_fit_at": first_fit, "n_candidates": n, "n_consistent": n_consistent,
            "n_distinct_predictions": distinct, "class_candidates": info.get("class_candidates", 0),
            "class_refused": info.get("class_refused", {}),
            "state": {"budget": budget, "fail_demo": {str(k): v for k, v in sorted(fail_demo.items(), key=str)},
                      "n_test_rejected": n_rejected, "cpu_cap_s": cpu_cap_s, "cpu_truncated": truncated},
            "cpu_s": round(time.process_time() - c0, 3)}
