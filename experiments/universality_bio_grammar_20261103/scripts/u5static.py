"""U5 static comparators (PROTOCOL.md section 12; Amendment 2 sections 4 and 5), fitted on calibration only.
    ALL_ON: every operator in canonical order, literature-default rules, values tuned by descent (Amendment 2, 4).
    MATCHED_SEARCH: beam search over 1..5-step programs (operator, theta, guard), no verification, anytime schedule
    up to CORA's measured calibration-side CPU.
Each fit returns a program that `apply_program` applies exactly to any image set (calibration or evaluation)."""
import time

import numpy as np

import u5core as C
import u5policy as P
import u5run as RN

INF = float("inf")
# ALL_ON's rules: (feature, comparison, grid from mildest), theta handling per operator
ALL_ON = {
    "add_lowthresh": ("area_rel", ">=", (1.0, 0.75, 0.5, 0.25)),
    "fill_holes": (None, None, (0.02, 0.1, 1.0)),
    "split_dt": ("solidity", "<", (0.70, 0.75, 0.80, 0.85, 0.90)),
    "split_int": ("solidity", "<", (0.70, 0.75, 0.80, 0.85, 0.90)),
    "merge_pairs": ("u_solidity", ">", (0.95, 0.90, 0.85, 0.80)),
    "close": (None, None, (1, 2, 3)),
    "open": (None, None, (1, 2, 3)),
    "dilate": (None, None, (1, 2, 3)),
    "erode": (None, None, (1, 2)),
    "delete": ("area_rel", "<", (0.1, 0.2, 0.3, 0.5)),
    "clear_border": ("area_rel", "<", (0.25, 0.5, 1.0, INF)),
}


def all_on_values(op):
    f, cmp_, grid = ALL_ON[op]
    if op in ("split_dt", "split_int"):
        return [(t, ti) for t in grid for ti in range(len(C.THETA[op]))]
    return list(grid)


def all_on_select(op, units, value):
    """(keys, theta index list, explicit theta value or None) selected by ALL_ON's rule at `value`."""
    f, cmp_, grid = ALL_ON[op]
    names = C.FEATS[op]
    if op in ("close", "open", "dilate", "erode"):
        t = list(C.THETA[op]).index(value)
        sel = units["valid"][t]
        return [k for k, s in zip(units["keys"], sel) if s], t, None
    if op == "fill_holes":
        return list(units["keys"]), 0, value                 # explicit hole-size limit; no-op units are skipped
    if op in ("split_dt", "split_int"):
        thr, t = value
        X = units["feats"][t][:, names.index("solidity")]
        sel = units["valid"][t] & (X < thr)
        return [k for k, s in zip(units["keys"], sel) if s], t, None
    X = units["feats"][0][:, names.index(f)] if len(units["keys"]) else np.zeros(0)
    sel = (X >= value) if cmp_ == ">=" else ((X < value) if cmp_ == "<" else (X > value))
    sel = sel & units["valid"][0]
    return [k for k, s in zip(units["keys"], sel) if s], 0, None


def _apply_step(S, op, chooser):
    """Apply one operator to every image of S; chooser(units of one image) -> (keys, t, th). Returns edit log."""
    log = []
    for u in S.uids:
        k = (S.ds, u, C.sha(S.L[u]), op, False)                 # selection needs no effects
        if k not in RN._UNITS:
            RN._UNITS[k] = C.units(S.image(u), op, with_effects=False)
        keys, t, th = chooser(RN._UNITS[k])
        if not keys:
            continue
        img = S.image(u)
        newL, applied = C.apply(img, op, [(kk, t) for kk in keys], th)
        log += [{"uid": u, "op": op, "key": kk if not isinstance(kk, tuple) else list(kk), "theta": t,
                 "theta_value": th, "before_sha": C.sha(S.L[u])} for kk, _ in applied]
        S.L[u] = newL
    return log


def fit_all_on(ds, cal_uids):
    """Amendment 2, section 4: canonical order; each value scored by the exact pooled calibration F1 after that operator."""
    t0 = time.process_time()
    S = RN.ImgSet(ds, cal_uids, "S", True)
    chosen, trail = {}, []
    for op in C.OPS:
        best = None
        for v in all_on_values(op):
            T = RN.ImgSet(ds, cal_uids, "S", True, labels=S.copy_labels(), share=S)
            _apply_step(T, op, lambda un, v=v: all_on_select(op, un, v))
            _, f1 = RN.score_set(T)
            trail.append({"op": op, "value": v, "cal_f1": f1})
            if best is None or f1 > best[1] + 1e-12:
                best = (v, f1)
        chosen[op] = best[0]
        _apply_step(S, op, lambda un, v=best[0]: all_on_select(op, un, v))
    _, f_final = RN.score_set(S)
    return {"values": chosen, "trail": trail, "cal_f1": f_final, "sweeps": 1, "cpu_s": round(time.process_time() - t0, 1)}


def apply_all_on(S, values):
    log = []
    for op in C.OPS:
        v = values[op]
        v = tuple(v) if isinstance(v, list) else v
        log += _apply_step(S, op, lambda un, v=v: all_on_select(op, un, v))
    return log


# ------------------------------------------------------------------------------------------------ matched search ---
def _step_candidates(S, ops, t0=None, budget_s=None, work=None):
    """All one-step programs on the current state, scored by pooled calibration F1 gain. Amendment 5: programs whose
    selection contains a conflicting pair (`sp.conflicted`, the executor's abstention rule) are removed BEFORE ranking,
    so an invalid program can never occupy a beam slot; every program whose gain was computed is counted in `work`
    (programs_scored), separately from the eligible candidates returned. The CPU budget is checked before each
    operator's program space is built; an overrun is reported, not hidden."""
    out = []
    base = S.base()
    work = {} if work is None else work
    for op in ops:
        if t0 is not None and budget_s is not None and time.process_time() - t0 >= budget_s:
            work["stopped_inside_step"] = work.get("stopped_inside_step", 0) + 1
            break
        du = RN.set_units(S, op)
        if not len(du["keys"]):
            continue
        sp = P.Space(du, base, len(S.parents))
        g = sp.pooled_gain(np.ones(sp.P, bool))
        work["programs_scored"] = work.get("programs_scored", 0) + len(sp.progs)
        work["conflicted_excluded"] = work.get("conflicted_excluded", 0) + int(sp.conflicted.sum())
        ok = (g > 1e-12) & (sp.E > 0) & ~sp.conflicted
        for i in np.flatnonzero(ok):
            t, gd = sp.progs[i]
            out.append((float(g[i]), int(sp.E[i]), len(gd), op, t, [list(sp.preds[t][k]) for k in gd]))
        work["eligible_candidates"] = work.get("eligible_candidates", 0) + int(ok.sum())
    out.sort(key=lambda x: (-round(x[0], 12), x[1], x[2]))
    return out


def _guard_select(op, units, t, guard):
    F, V = units["feats"][t], units["valid"][t]
    s = V.copy()
    for j, cmp_, q in guard:
        s &= (F[:, j] < q) if cmp_ == "<" else (F[:, j] > q)
    return [k for k, x in zip(units["keys"], s) if x], t, None


def apply_program(S, program):
    log = []
    for st in program:
        op, t, guard = st["op"], st["theta_index"], st["guard"]
        log += _apply_step(S, op, lambda un, op=op, t=t, guard=guard: _guard_select(op, un, t, guard))
    return log


SCHEDULE = [(3, 3), (3, 10), (3, 30), (5, 30)]          # (depth, beam) stages of the anytime schedule


def fit_matched(ds, cal_uids, budget_s):
    """Beam search over operator sequences on CORA's measured calibration CPU. Amendment 7: a budget stop inside a
    step (`_step_candidates` breaks before an operator's program space) ends the search at once as "budget reached";
    the partial candidate list is counted in `work` but never applied, and an interrupted stage is never "schedule
    exhausted". The unrounded CPU is returned for the work-match decision."""
    t0, wall0, w0 = time.process_time(), time.time(), RN.work_snapshot()
    schedule = [tuple(s) for s in SCHEDULE]
    best_prog, best_f1, n_eval, stopped = [], None, 0, "schedule exhausted"
    work = {"programs_scored": 0, "conflicted_excluded": 0, "eligible_candidates": 0, "exact_beam_applications": 0,
            "stopped_inside_step": 0, "partial_step_candidates_discarded": 0, "stages_completed": []}
    S0 = RN.ImgSet(ds, cal_uids, "S", True)
    _, f_base = RN.score_set(S0)
    best_f1 = f_base
    done = False
    for depth, beam in schedule:
        frontier = [([], S0.copy_labels(), f_base)]
        for d in range(depth):
            nxt = []
            for prog, labels, f_prev in frontier:
                if time.process_time() - t0 >= budget_s:
                    done, stopped = True, "budget reached"
                    break
                S = RN.ImgSet(ds, cal_uids, "S", True, labels=labels, share=S0)
                n_in = work["stopped_inside_step"]
                cands = _step_candidates(S, C.OPS, t0, budget_s, work)
                if work["stopped_inside_step"] > n_in:              # Amendment 7: interrupted inside the step
                    work["partial_step_candidates_discarded"] += len(cands)
                    done, stopped = True, "budget reached"
                    break
                n_eval += len(cands)
                for gain, e, npred, op, t, guard in cands[:beam]:
                    T = RN.ImgSet(ds, cal_uids, "S", True, labels=S.copy_labels(), share=S)
                    step = {"op": op, "theta_index": int(t), "guard": guard}
                    apply_program(T, [step])
                    _, f1 = RN.score_set(T)
                    work["exact_beam_applications"] += 1
                    nxt.append((prog + [step], T.copy_labels(), f1))
            if done or not nxt:
                break
            nxt.sort(key=lambda x: (-round(x[2], 12), len(x[0])))
            frontier = nxt[:beam]
            if frontier[0][2] > best_f1 + 1e-12:
                best_prog, best_f1 = frontier[0][0], frontier[0][2]
        if done:
            break
        work["stages_completed"].append([depth, beam])
    cpu = time.process_time() - t0
    return {"program": best_prog, "cal_f1": best_f1, "baseline_cal_f1": f_base,
            "candidates_scored": work["programs_scored"], "eligible_candidates_returned": n_eval, "work": work,
            "charged": {k: v - w0.get(k, 0) for k, v in RN.work_snapshot().items()},
            "cpu_s": round(cpu, 1), "cpu_s_exact": cpu, "wall_s": round(time.time() - wall0, 1), "budget_s": budget_s,
            "stopped": stopped, "schedule": [list(s) for s in schedule],
            "cpu_over_budget_s": round(max(0.0, cpu - budget_s), 1)}
