"""Addendum 1 recomputation script (outside the frozen set). ADDENDUM_1.md states this file's sha256, and the third
line of GO_CAS binds ADDENDUM_1.md by its sha256.

    python addendum_1_recompute.py runs/analysis_addendum_1 runs/generated/W1 runs/generated/W2 runs/generated/W3
    python addendum_1_recompute.py --self-test SCRATCH_DIR OUT.json            (phase 1 test, scratch mirrors only)

Phase 2: run from this study folder right after the frozen analysis
(`python -m cas.analysis runs/analysis runs/generated/W1 runs/generated/W2 runs/generated/W3`), with the same world
folders in the same order. It writes OUT_DIR/ADDENDUM_1_RECOMPUTATION.json in every case, and OUT_DIR/ANALYSIS.json
only when the colour rule applies.
1. Binding. The gate's analyse stage must pass, the GO's third line must be exactly
   "addendum_1_sha256 <sha256 of ADDENDUM_1.md>", and ADDENDUM_1.md must state this file's sha256.
2. The frozen result. The frozen strict verification (cas/analysis.verify_complete, unchanged) runs here as frozen;
   its result must agree with the frozen analysis's latest output in runs/analysis (INCOMPLETE.json with the same
   status and problems, or ANALYSIS.json when there are none). Otherwise nothing is computed.
3. Colour rule (ADDENDUM_1.md, section 1). A committed prediction (one attempt: one grid per query input) holding a
   cell that is not an integer from 0 to 9 is scored incorrect. The verification runs a second time with its grid
   check reduced to the shape (a non-empty rectangular list of non-empty lists), everything else identical. If the
   frozen run has problems, the reduced run has none, and at least one committed prediction holds such a cell, every
   endpoint resting on such a prediction is re-scored in memory by the frozen rule (analysis._rescore) with that
   prediction counted incorrect, and the frozen analysis code (cas/analysis.main, unchanged) writes OUT_DIR/ANALYSIS.json
   from the verified worlds so corrected: that is the reported analysis. In every other case with problems the
   frozen INCOMPLETE or INVALID stands.
4. Failure status (section 2). Each matched search's failure status is the commit stage's record ("failed" in
   runs/cas_commit/COMMITTED_PREDICTIONS.json), checked against the matched-search stages' own records: the result
   files runs/cas_c7m/c7m_M.json and c7m_E.json (final record after the rerun stage: failed when timed out, child
   failed or memory capped) and the kernel log runs/kaggle_main.log (the last line a search's stage printed: a
   finished search always prints a stop reason, a failed one none; a rerun's line decides nothing). From that status:
   the descriptive primary without the tasks whose matched search failed, and the failure counts. A disagreement
   between the sources makes both unavailable (listed); every mismatch with the results' own flags is listed.
5. Memory note (section 4). Every matched search that stopped on its CPU cap with a peak virtual memory above 90% of
   its address-space limit.
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = "ADDENDUM_1_RECOMPUTATION.json"


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def shape_grid(g):
    """The frozen grid check without its cell rule: a non-empty rectangular list of non-empty lists."""
    return bool(isinstance(g, list) and g and all(isinstance(r, list) and r and len(r) == len(g[0]) for r in g))


def out_of_range(attempt):
    """An attempt holds a cell that is not an integer from 0 to 9 (another integer, a Boolean, a float, anything
    else). A malformed attempt is left to the frozen checks."""
    try:
        return any(not (type(v) is int and 0 <= v <= 9) for g in attempt for r in g for v in r)
    except TypeError:
        return False


def oor_attempts(preds):
    return [i for i, a in enumerate(preds) if out_of_range(a)] if isinstance(preds, list) else []


def records_out_of_range(com):
    out = []
    for sec in ("units", "c7m", "grown"):
        d = com.get(sec)
        for k, v in sorted(d.items() if isinstance(d, dict) else []):
            if isinstance(v, dict) and oor_attempts(v.get("preds")):
                out.append(f"{sec}:{k}")
    return out


def label(problems):
    return None if not problems else ("INVALID" if any(p.startswith("INVALID") for p in problems) else "INCOMPLETE")


def check_binding(study):
    from cas import gate
    if not gate.check("analyse"):
        raise SystemExit("the gate's analyse stage refused")
    with open(os.path.join(study, "GO_CAS"), encoding="utf-8") as f:
        lines = f.read().splitlines()
    if len(lines) < 3 or lines[2] != "addendum_1_sha256 " + sha(os.path.join(study, "ADDENDUM_1.md")):
        raise SystemExit("GO_CAS line 3 does not bind the live ADDENDUM_1.md")
    with open(os.path.join(study, "ADDENDUM_1.md"), encoding="utf-8") as f:
        if sha(os.path.abspath(__file__)) not in f.read():
            raise SystemExit("ADDENDUM_1.md does not state this script's sha256")


def verify(AN, world_dirs, relaxed):
    orig = AN._grid
    if relaxed:
        AN._grid = shape_grid
    try:
        return AN.verify_complete(world_dirs, strict=True)
    finally:
        AN._grid = orig


def frozen_output(frozen_out):
    """The frozen analysis's latest output: ("incomplete", its record) or ("analysis", None); None if neither."""
    found = [(os.path.getmtime(os.path.join(frozen_out, n)), k, n) for k, n in
             (("incomplete", "INCOMPLETE.json"), ("analysis", "ANALYSIS.json")) if os.path.exists(os.path.join(frozen_out, n))]
    if not found:
        return None
    _, kind, name = max(found)
    return kind, (load(os.path.join(frozen_out, name)) if kind == "incomplete" else None)


def apply_colour_rule(AN, w, com, ev):
    """In memory: every endpoint whose committed predictions hold an out-of-range attempt, re-scored by the frozen
    rule (at most two predictions, cgrow/evaluate.correct, the matched search's failure flag, the grown search's fit)
    with that attempt counted incorrect. Returns the endpoints it changed."""
    changed = []

    def new_value(rec, t, extra):
        p = rec.get("preds") or []
        bad = set(oor_attempts(p))
        keep = [a for i, a in enumerate(p) if i not in bad]
        return bool(keep) and len(p) <= 2 and AN.EV.correct(keep, ev[t]["test_outputs"]) and extra

    def fix(holder, key, rec, t, extra, name):
        if rec and oor_attempts(rec.get("preds")) and t in ev:
            v = new_value(rec, t, extra)
            if holder.get(key) != v:
                holder[key] = v
                changed.append(name)

    cu, cc, cg = com.get("units") or {}, com.get("c7m") or {}, com.get("grown") or {}
    for u in w["units"]:
        t = u["task"]
        for s, arms in u["seeds"].items():
            for arm, a in arms.items():
                fix(a, "recovered", cu.get(f"{arm}|{t}|{s}"), t, True, f"{arm}|{t}|{s}")
        rec = cc.get(f"M|{t}")
        fix(u["C7m"], "recovered", rec, t, not (rec or {}).get("failed"), f"C7m|M|{t}")
    for t, e in w["e_tasks"].items():
        rec = cc.get(f"E|{t}")
        fix(e["C7m"], "recovered", rec, t, not (rec or {}).get("failed"), f"C7m|E|{t}")
        for k in ("reuse", "transfer"):
            rec = cg.get(f"{k}|{t}")
            fix(e[k], "recovered", rec, t, bool((rec or {}).get("fit")), f"{k}|{t}")
    structs = w.get("structures") or {}
    struct_changed = False
    for sid, v in structs.items():
        res = (v or {}).get("e_results") or {}
        for t in list(res):
            rec = cg.get(f"struct|{sid}|{t}")
            n0 = len(changed)
            fix(res, t, rec, t, bool((rec or {}).get("fit")), f"struct|{sid}|{t}")
            struct_changed = struct_changed or len(changed) > n0
    if struct_changed:                          # the excluded tasks' oracle reach rests on the per-structure results
        gbf = com.get("grown_by_family") or {}
        for t, e in w["e_tasks"].items():
            own = gbf.get(e["family"], [])
            other = sorted({sid for f, ss in gbf.items() if f != e["family"] for sid in ss})
            e["reach_reuse"] = any(structs.get(sid, {}).get("e_results", {}).get(t) for sid in own)
            e["reach_transfer"] = any(structs.get(sid, {}).get("e_results", {}).get(t) for sid in other)
    return changed


def stage_status(wd):
    out = {}
    for which in ("M", "E"):
        d = load(os.path.join(wd, "runs", "cas_c7m", f"c7m_{which}.json"))
        for t, r in (d.items() if isinstance(d, dict) else []):
            if isinstance(r, dict):
                out[f"{which}|{t}"] = bool(r.get("timed_out") or r.get("child_failed") or r.get("memory_capped"))
    return out


def log_status(wd):
    """{search: True (failed), False, or None (its last line is a rerun's)} from runs/kaggle_main.log; None if absent."""
    path = os.path.join(wd, "runs", "kaggle_main.log")
    if not os.path.exists(path):
        return None
    last = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s.startswith("{"):
                continue
            try:
                d = json.loads(s)
            except ValueError:
                continue
            if not isinstance(d, dict) or not isinstance(d.get("task"), str):
                continue
            if d.get("c7m") in ("M", "E"):
                last[f"{d['c7m']}|{d['task']}"] = d.get("stop") is None
            elif d.get("c7m_rerun") in ("M", "E"):
                last[f"{d['c7m_rerun']}|{d['task']}"] = None
    return last


def memory_note(wd):
    rows = []
    for which in ("M", "E"):
        d = load(os.path.join(wd, "runs", "cas_c7m", f"c7m_{which}.json"))
        for t, r in sorted(d.items() if isinstance(d, dict) else []):
            lim, peak = r.get("mem_limit_gb"), r.get("vm_peak_kb")
            if r.get("stop") == "cpu_cap" and lim and peak and peak * 1024 > 0.9 * float(lim) * (1 << 30):
                rows.append({"search": f"{which}|{t}", "vm_peak_kb": peak, "vm_peak_gib": round(peak / (1 << 20), 2),
                             "limit_gib": float(lim)})
    return rows


def recompute(out_dir, world_dirs, test=False):
    from cas import env as E
    from cas import analysis as AN
    if not test:
        check_binding(E.STUDY)
    frozen_out = os.path.join(E.STUDY, "runs", "analysis")
    if os.path.realpath(out_dir) == os.path.realpath(frozen_out):
        raise SystemExit("OUT_DIR must not be the frozen analysis's folder")
    E.check_write(os.path.join(out_dir, RECORD))
    os.makedirs(out_dir, exist_ok=True)
    names = [os.path.basename(os.path.realpath(wd)) for wd in world_dirs]
    com = {n: load(os.path.join(wd, "runs", "cas_commit", "COMMITTED_PREDICTIONS.json")) or {}
           for n, wd in zip(names, world_dirs)}
    rec = {"addendum": "ADDENDUM_1.md", "script_sha256": sha(os.path.abspath(__file__)), "world_dirs": world_dirs,
           "binding_checked": not test}

    def done(outcome, code=0):
        rec["outcome"] = outcome
        E.dump(os.path.join(out_dir, RECORD), rec)
        print(json.dumps({"outcome": outcome}))
        if code:
            raise SystemExit(code)
        return rec

    w0, p0 = verify(AN, world_dirs, relaxed=False)
    w1, p1 = verify(AN, world_dirs, relaxed=True)
    rec["frozen_verification"] = {"status": label(p0), "problems": p0}
    rec["shape_only_verification"] = {"status": label(p1), "problems": p1}
    rec["committed_predictions_out_of_range"] = {n: records_out_of_range(c) for n, c in com.items()}
    fo = frozen_output(frozen_out)
    agrees = fo is not None and ((fo[0] == "incomplete" and (fo[1] or {}).get("status") == label(p0) and
                                  (fo[1] or {}).get("problems") == p0) if p0 else fo[0] == "analysis")
    rec["frozen_analysis_output"] = {"found": fo and fo[0], "agrees_with_this_verification": agrees}
    if not agrees:
        return done("refused: the frozen analysis's output in runs/analysis is missing or differs from the frozen "
                    "verification run here (run the frozen analysis first, with the same world folders)", 3)
    any_oor = any(rec["committed_predictions_out_of_range"].values())
    if p0 and (p1 or not any_oor):
        return done(f"the frozen analysis's {label(p0)} stands (ADDENDUM_1.md, sections 1 and 3)")
    worlds = copy.deepcopy(w1 if p0 else w0)
    changed = {}
    if p0:
        for w, wd, n in zip(worlds, world_dirs, names):
            ev = load(os.path.join(wd, "evaluator_only", "TASKS_EVAL.json")) or {}
            changed[n] = apply_colour_rule(AN, w, com[n], ev)
        orig = AN.verify_complete
        AN.verify_complete = lambda dirs, strict=True: (copy.deepcopy(worlds), [])
        try:
            AN.main(out_dir, world_dirs, strict=True)
        finally:
            AN.verify_complete = orig
        rec["outcome"] = ("colour rule applied (ADDENDUM_1.md, section 1): the frozen INVALID rests only on committed "
                          "predictions with cells outside 0 to 9; ANALYSIS.json beside this record is the reported "
                          "analysis")
        rec["analysis_written"] = os.path.join(out_dir, "ANALYSIS.json")
    else:
        rec["outcome"] = "the frozen verification passed: the frozen runs/analysis/ANALYSIS.json is the reported analysis"
    rec["endpoints_changed_by_the_colour_rule"] = changed
    # failure status: the commit stage's record, checked against the stage files and the kernel log
    status, disagree, mismatch, undecided, failed_m, counts = {}, [], [], [], set(), {}
    for w, wd, n in zip(worlds, world_dirs, names):
        st, lg = stage_status(wd), log_status(wd)
        rows = {}
        for k, v in sorted((com[n].get("c7m") or {}).items()):
            a = bool(v.get("failed")) if isinstance(v, dict) else None
            b = st.get(k)
            c = "no log" if lg is None else lg.get(k, "no line")
            rows[k] = {"commit": a, "stage_file": b, "kernel_log": c}
            if a is None or b is None or a != b or (isinstance(c, bool) and c != a):
                disagree.append(f"{n}:{k}")
            if not isinstance(c, bool):
                undecided.append(f"{n}:{k}")
            if a and k.startswith("M|"):
                failed_m.add((w["world"], k[2:]))
        status[n] = rows
        counts[w["world"]] = {"M": sum(bool(r["commit"]) for k, r in rows.items() if k.startswith("M|")),
                              "E": sum(bool(r["commit"]) for k, r in rows.items() if k.startswith("E|"))}
        for u in w["units"]:
            k = f"M|{u['task']}"
            if k in rows and bool(u["C7m"].get("failed")) != rows[k]["commit"]:
                mismatch.append(f"{n}:{k}")
        for t, e in sorted(w["e_tasks"].items()):
            k = f"E|{t}"
            if k in rows and bool(e["C7m"].get("failed")) != rows[k]["commit"]:
                mismatch.append(f"{n}:{k}")
    rec["failure_status"] = status
    rec["failure_status_disagreements"] = disagree
    rec["searches_the_kernel_log_does_not_decide"] = len(undecided)
    rec["results_failure_flag_mismatches"] = mismatch
    if disagree:
        rec["primary_without_failed_matched_searches"] = "unavailable: the failure-status sources disagree"
        rec["c7m_failures"] = "unavailable: the failure-status sources disagree"
    else:
        rows_p = []
        for w in worlds:
            for u in w["units"]:
                sh = AN.per_task(u, "S-hole")
                if sh is None or (w["world"], u["task"]) in failed_m:
                    continue
                r = {"task": u["task"], "family": u["family"], "world": w["world"], "source": u["source"],
                     "family_id": f"{w['world']}:{u['family']}", "source_cluster": "src:" + u["source"]}
                r["cluster"] = AN.cluster_id(r)
                r["S-hole"] = {"recovered": sh["majority"]}
                r["C7m"] = {"recovered": bool(u["C7m"]["recovered"])}
                rows_p.append(r)
        rec["primary_without_failed_matched_searches"] = dict(AN.contrast(rows_p, "S-hole", "C7m") or {},
                                                              tasks_excluded=len(failed_m))
        rec["c7m_failures"] = counts
    rec["matched_searches_on_cpu_cap_above_90pct_of_memory_limit"] = {n: memory_note(wd)
                                                                      for n, wd in zip(names, world_dirs)}
    E.dump(os.path.join(out_dir, RECORD), rec)
    print(json.dumps({"outcome": rec["outcome"], "changed": changed, "disagreements": disagree,
                      "results_mismatches": mismatch}))
    return rec


# ------------------------------------------------------------------ phase 1 self-test (scratch mirrors only)
def self_test(scratch, out_json):
    sys.path.insert(0, os.path.join(HERE, "checks"))
    import strict_fixture as FX
    base = os.path.join(scratch, "base")
    FX.build_mirror(base)
    W = os.path.join(FX.STUDY_REL, "runs", "generated", "s1_world")

    def rp(w, *p):
        return os.path.join(w, "runs", *p)

    def cp(w):
        return rp(w, "cas_commit", "COMMITTED_PREDICTIONS.json")

    def wr(w):
        return rp(w, "cas_eval", "world_results.json")

    def outs(w, t):
        return load(os.path.join(w, "evaluator_only", "TASKS_EVAL.json"))[t]["test_outputs"]

    def eq(att, ys):
        return [tuple(tuple(r) for r in g) for g in att] == [tuple(tuple(r) for r in y) for y in ys]

    def recommit(w):
        with open(rp(w, "cas_commit", "COMMITTED_SHA256"), "w") as f:
            f.write(sha(cp(w)) + "\n")
        FX._rw(wr(w), lambda r: r.__setitem__("committed_sha256", sha(cp(w))))

    def tens(g):
        return [[10] * len(r) for r in g]

    def shift(g):
        return [[(v + 1) % 10 for v in r] for r in g]

    def pick(w, sec, pattern):
        """The first committed record of the section, on a motivating task, whose attempts are correct as given."""
        for k, v in sorted(load(cp(w))[sec].items()):
            t = k.split("|")[1]
            if (sec == "units" or k.startswith("M|")) and v.get("preds") and \
                    tuple(eq(a, outs(w, t)) for a in v["preds"]) == pattern:
                return k
        raise RuntimeError(f"no {sec} record with attempts {pattern}")

    def edit(w, sec, k, fn):
        FX._rw(cp(w), lambda c: c[sec][k].__setitem__("preds", fn(c[sec][k]["preds"])))
        recommit(w)

    def c7m_recovered(w, t, val):
        FX._rw(wr(w), lambda r: [u["C7m"].__setitem__("recovered", val) for u in r["units"] if u["task"] == t])

    def unit_recovered(w, k, val):
        arm, t, s = k.split("|")
        FX._rw(wr(w), lambda r: [u["seeds"][s][arm].__setitem__("recovered", val) for u in r["units"] if u["task"] == t])

    def beside(w):                    # a wrong first attempt made out of range beside a correct second one
        k = pick(w, "c7m", (False, True))
        edit(w, "c7m", k, lambda p: [[tens(g) for g in p[0]], p[1]])
        return k

    def only(w, fn):                  # a correct matched search's two attempts made wrong; endpoint as scored
        k = pick(w, "c7m", (True, True))
        edit(w, "c7m", k, lambda p: [[fn(g) for g in a] for a in p])
        c7m_recovered(w, k[2:], False)
        return k

    def boolean(w):                   # one cell of a unit's only correct attempt made True or False
        k = pick(w, "units", (True, False))

        def f(p):
            for r in p[0][0]:
                for j, v in enumerate(r):
                    if type(v) is int and v in (0, 1):
                        r[j] = bool(v)
                        return p
            raise RuntimeError("no cell 0 or 1")
        edit(w, "units", k, f)
        return k

    def boolean_control(w):           # the same attempt in range and wrong; endpoint as scored
        k = pick(w, "units", (True, False))
        edit(w, "units", k, lambda p: [[shift(g) for g in p[0]], p[1]])
        unit_recovered(w, k, False)
        return k

    def first_task(w):
        return load(wr(w))["units"][0]["task"]

    def flag(w):                      # the results' failure flag set where the search did not fail
        t = first_task(w)
        FX._rw(wr(w), lambda r: r["units"][0]["C7m"].__setitem__("failed", True))
        return f"M|{t}"

    def oor_and_defect(w):
        k = only(w, tens)
        FX._rw(wr(w), lambda r: r["e_tasks"][sorted(r["e_tasks"])[0]]["C7m"].pop("failed"))
        return k

    def stage(w):                     # the stage file says timed out where the commit says not failed
        t = first_task(w)
        FX._rw(rp(w, "cas_c7m", "c7m_M.json"), lambda d: d[t].__setitem__("timed_out", True))
        return f"M|{t}"

    def kernel_log(w, contradict=False):
        dm, de = load(rp(w, "cas_c7m", "c7m_M.json")), load(rp(w, "cas_c7m", "c7m_E.json"))
        m = sorted(dm)
        rerun, bad = m[0], (m[1] if contradict else None)
        lines = ["controller: start", json.dumps({"task": m[0], "status": "done", "decision": "INVENT_NEW_OPERATION"})]
        for which, d in (("E", de), ("M", dm)):
            for t, r in sorted(d.items()):
                stop = None if which == "M" and t in (rerun, bad) else r.get("stop")
                lines.append(json.dumps({"c7m": which, "task": t, "fit": r.get("fit") if stop else False, "stop": stop,
                                         "cpu_s": r.get("cpu_s"), "budget_cpu_s": r.get("budget_cpu_s")}))
        lines += ["Traceback (most recent call last): a line of noise", "{not json",
                  json.dumps({"c7m_rerun": "M", "task": rerun, "fit": dm[rerun].get("fit"), "vm_peak_kb": 6262652}),
                  json.dumps({"committed_units": 132, "committed_c7m": 35})]
        with open(rp(w, "kaggle_main.log"), "w") as f:
            f.write("\n".join(lines) + "\n")
        return f"M|{bad}" if bad else f"M|{rerun}"

    cases = [("S1 world, complete", None),
             ("out-of-range wrong attempt beside a correct one", beside),
             ("out-of-range wrong grids as both attempts", lambda w: only(w, tens)),
             ("control: in-range wrong grids as both attempts", lambda w: only(w, shift)),
             ("Boolean cell that Python equality scores correct", boolean),
             ("control: that attempt in range and wrong", boolean_control),
             ("flipped failure flag in the results", flag),
             ("out-of-range grid with another defect", oor_and_defect),
             ("stage record contradicts the commit", stage),
             ("kernel log consistent with the records", kernel_log),
             ("kernel log contradicts the commit", lambda w: kernel_log(w, True))]
    res, docs = {}, {}
    for i, (name, mut) in enumerate(cases):
        mirror = os.path.join(scratch, "case_%02d" % i)
        shutil.rmtree(mirror, ignore_errors=True)
        shutil.copytree(base, mirror)
        study = os.path.join(mirror, FX.STUDY_REL)
        wd = os.path.join(mirror, W)
        shutil.copy(os.path.abspath(__file__), os.path.join(study, "addendum_1_recompute.py"))
        target = mut(wd) if mut else None
        FX.manifest(wd)
        fz = FX.analyse(mirror, [wd])
        add_out = os.path.join(study, "runs", "analysis_addendum_1")
        p = subprocess.run([FX.PY, "addendum_1_recompute.py", "--test", add_out, wd], cwd=study,
                           env=FX.env_for(mirror), capture_output=True, text=True)
        r = load(os.path.join(add_out, RECORD)) or {}
        docs[name] = {"frozen": load(os.path.join(study, "runs", "analysis", "ANALYSIS.json")),
                      "addendum": load(os.path.join(add_out, "ANALYSIS.json")), "record": r}
        d = r.get("primary_without_failed_matched_searches")
        res[name] = {"target": target, "frozen_status": fz["status"] or ("analysis written" if fz["analysis_written"] else None),
                     "frozen_problems": fz["problems"][:3], "script_returncode": p.returncode,
                     "script_stderr_tail": p.stderr[-400:] if p.returncode else "",
                     "outcome": r.get("outcome"), "out_of_range_records": r.get("committed_predictions_out_of_range"),
                     "endpoints_changed": r.get("endpoints_changed_by_the_colour_rule"),
                     "failure_status_disagreements": r.get("failure_status_disagreements"),
                     "results_failure_flag_mismatches": r.get("results_failure_flag_mismatches"),
                     "searches_the_kernel_log_does_not_decide": r.get("searches_the_kernel_log_does_not_decide"),
                     "primary_without_failed": ({k: d.get(k) for k in ("units", "only_S-hole", "only_C7m",
                                                                         "mcnemar_p_conditional", "tasks_excluded")}
                                                if isinstance(d, dict) else d),
                     "frozen_primary_without_failed": ({k: docs[name]["frozen"]["primary"]["without_failed_matched_search"].get(k)
                                                       for k in ("units", "tasks_excluded")} if docs[name]["frozen"] else None),
                     "reported_decision": ((docs[name]["addendum"] or docs[name]["frozen"] or {}).get("primary") or {}).get("decision")
                     if (r.get("outcome") or "").startswith(("colour", "the frozen verification")) else None}
        print(json.dumps({"case": name, "frozen": res[name]["frozen_status"], "outcome": res[name]["outcome"]}), flush=True)

    C = docs["S1 world, complete"]["frozen"]
    wf = C["primary"]["without_failed_matched_search"] if C else None

    def ok_frozen(n):
        return res[n]["frozen_status"] == "analysis written"

    def invalid(n):
        return res[n]["frozen_status"] == "INVALID"

    def says(n, word):
        return (res[n]["outcome"] or "").startswith(word)

    def desc(n):
        return docs[n]["record"].get("primary_without_failed_matched_searches")

    def changed(n):
        return [x for v in (res[n]["endpoints_changed"] or {}).values() for x in v]

    def clean(n):
        return not res[n]["failure_status_disagreements"] and not res[n]["results_failure_flag_mismatches"]

    def target(n):
        return "s1_world:" + str(res[n]["target"])

    n1, n2, n3, n3c, n4, n4c, n5, n6, n7, n8, n9 = [c[0] for c in cases]
    expect = {
        n1: ok_frozen(n1) and says(n1, "the frozen verification passed") and clean(n1) and desc(n1) == wf
        and docs[n1]["addendum"] is None,
        n2: invalid(n2) and says(n2, "colour rule applied") and changed(n2) == [] and docs[n2]["addendum"] == C,
        n3: invalid(n3) and says(n3, "colour rule applied") and changed(n3) == []
        and docs[n3]["addendum"] == docs[n3c]["frozen"],
        n3c: ok_frozen(n3c) and says(n3c, "the frozen verification passed"),
        n4: invalid(n4) and says(n4, "colour rule applied") and changed(n4) == [res[n4]["target"]]
        and docs[n4]["addendum"] == docs[n4c]["frozen"],
        n4c: ok_frozen(n4c) and says(n4c, "the frozen verification passed"),
        n5: ok_frozen(n5) and res[n5]["results_failure_flag_mismatches"] == [target(n5)]
        and not res[n5]["failure_status_disagreements"] and desc(n5) == wf
        and docs[n5]["frozen"]["primary"]["without_failed_matched_search"]["tasks_excluded"] == wf["tasks_excluded"] + 1,
        n6: invalid(n6) and says(n6, "the frozen analysis's INVALID stands") and docs[n6]["addendum"] is None,
        n7: ok_frozen(n7) and res[n7]["failure_status_disagreements"] == [target(n7)] and isinstance(desc(n7), str),
        n8: ok_frozen(n8) and clean(n8) and res[n8]["searches_the_kernel_log_does_not_decide"] == 1 and desc(n8) == wf,
        n9: ok_frozen(n9) and res[n9]["failure_status_disagreements"] == [target(n9)] and isinstance(desc(n9), str),
    }
    doc = {"note": "self-test of addendum_1_recompute.py after the revision 4 freeze, in scratch mirrors of S1's own "
                   "world (checks/strict_fixture.py's builder, CAS_PACKAGE=1); no arm runs, no main or pilot task, "
                   "nothing written in the real study. Each case: the frozen analysis (cas/analysis.main, strict), "
                   "then this script in test mode (binding not checked, there being no GO).",
           "script_sha256": sha(os.path.abspath(__file__)), "freeze_sha256": sha(os.path.join(HERE, "FREEZE.json")),
           "analysis_sha256": sha(os.path.join(HERE, "cas", "analysis.py")),
           "all_as_expected": all(expect.values()), "as_expected": expect, "cases": res}
    with open(out_json, "w") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(json.dumps({"all_as_expected": doc["all_as_expected"], "as_expected": expect}))


if __name__ == "__main__":
    if sys.argv[1] == "--self-test":
        self_test(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "--test":
        recompute(sys.argv[2], sys.argv[3:], test=True)
    else:
        recompute(sys.argv[1], sys.argv[2:])
