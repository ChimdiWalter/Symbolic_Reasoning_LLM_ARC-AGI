"""Checks after THE all-roster run of BL1, before any number is read out. Author: Chimdi Walter Ndubuisi.

It runs after the run and takes no part in it. It reads the experiment folder and the run's output folder and
changes nothing in either, except that --write-manifest writes FULL_OUT_MANIFEST.sha256 into the experiment folder
(once; it refuses to overwrite) and --report writes this check's report (once).

Checks, in order:
 1. the freeze still verifies (every frozen file and the setup record), by the runner's own check;
 2. exactly one receipt, read-only, naming the freeze, the setup record and the output folder;
 3. the detached job started once and ended once, with exit 0;
 4. the run's MANIFEST names the freeze and the setup record, is not a development run, covers the whole roster in
    the runner's order, and states the policy of the freeze (the budget N, the safety limit, s, the caps);
 5. one record for every listed target and no other; every record is done, excluded or incomplete, and the
    incomplete ones are listed (an incomplete record is never read as "none");
 6. the journal of every target: one start; for a done target the five seals in their order (setup_record,
    first_fits_9, first_fits_36, selections, final_set), once each and equal to the record's seals, then
    final_opened, then done; for an excluded target, start, the usability step if it was reached, then excluded;
 7. SUMMARY.json equal to a summary made now from the records, and the calibration set (K and its names) equal to
    the one committed with the freeze;
 8. the run's setup decisions and counts equal to the committed setup record (the summary's reconciliation);
 9. the status of the primary. "provisional" means STOP: nothing is read further until the independent review has
    read the reason.
Two readings are informational and are not checks, both declared before any outcome: every search whose processor
time came within 20% of the safety limit (on another machine it could have stopped there), and every evaluation
guard that ran out, by step, with every guarded step that has no mark at all listed as a missing validation.
A third reading bounds whether any guard can have fired at all, independently of the marks: a guard fires only
after its whole length of processor time was spent inside one guarded batch (the shortest are the streams of the
true operation, 20 s), and a search's processor seconds are recorded before its first fit is checked again, so no
guarded batch is inside them. For each target its total minus its searches is compared with that length, with
0.010 s added for rounding (the total is kept to 0.01 s, six searches to 0.001 s each). A missing or non-finite
time makes the target unknown, never an all-clear; a target at or above the length is listed as not excluded by
the bound, nothing more.

The protocol requires the found expressions to be read before any count is reported.

    env PYTHONHASHSEED=0 python3 -s -B experiments/below_library_20261114/after_run_bl.py \
        --out <output folder> --freeze <freeze> --setup-record <setup record> --status outputs/detached/<job>/run.status \
        [--folder <experiment folder>] [--write-manifest] [--report <report.json>]

Exit 0 when every check passed, 1 when one failed, 2 when the primary reading is provisional.
"""
import argparse
import glob
import hashlib
import json
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SEALS = ("setup_record", "first_fits_9", "first_fits_36", "selections", "final_set")
NEAR = 0.8


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def journal_problem(events, rec):
    kinds = [e.get("event") for e in events]
    if kinds.count("start") != 1 or kinds[:1] != ["start"]:
        return "not exactly one start, first"
    st = rec.get("status")
    if st == "excluded":
        ok = kinds in (["start", "excluded"], ["start", "setup_usability", "excluded"])     # excluded by the generator, or at usability
        return None if ok else "an excluded target's journal is not start, [setup_usability,] excluded"
    if st != "done":
        return None                                  # incomplete: listed under check 5, its journal is not judged here
    seals = [e.get("name") for e in events if e.get("event") == "seal"]
    if tuple(seals) != SEALS:
        return "seals %s, not %s" % (seals, list(SEALS))
    shas = {e["name"]: e.get("sha256") for e in events if e.get("event") == "seal"}
    if shas != (rec.get("seals") or {}):
        return "the journal's seals differ from the record's"
    tail = [k for k in kinds if k in ("final_opened", "done")]
    if tail != ["final_opened", "done"] or kinds[-1] != "done":
        return "final_opened then done not found at the end"
    if kinds.index("final_opened") < max(i for i, k in enumerate(kinds) if k == "seal"):
        return "the final panel was opened before the last seal"
    return None


def guard_marks(rec):
    """(timeouts, missing): guarded steps whose guard ran out, and guarded steps without a mark."""
    out, missing = [], []
    for name, s in sorted((rec.get("searches") or {}).items()):
        for step in ("fit_recheck", "final"):
            if s.get("fit") and step in s:
                v = (s.get(step) or {}).get("guard_timeout")
                (out if v else missing if v is None else []).append("%s/%s" % (name, step))
    u = (rec.get("setup") or {}).get("usability")
    if u is not None:
        v = u.get("guard_timeout")
        (out if v else missing if v is None else []).append("setup/usability")
    fp = (rec.get("final_panel") or {}).get("pooled_slice")
    if fp is not None:
        v = fp.get("guard_timeout")
        (out if v else missing if v is None else []).append("final_panel/pooled_slice")
    w = rec.get("witness")
    if isinstance(w, dict) and w.get("state") == "evaluated":           # a static failure runs no guarded step
        v = w.get("guard_timeout")
        (out if v else missing if v is None else []).append("witness")
    return out, missing


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=HERE)
    ap.add_argument("--out", required=True)
    ap.add_argument("--freeze", required=True)
    ap.add_argument("--setup-record", required=True)
    ap.add_argument("--status", required=True)
    ap.add_argument("--write-manifest", action="store_true")
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    import run_bl as R
    import summarize_bl as SM
    import presets_bl as P
    import episode_bl as E
    checks, info = [], {}

    def check(name, ok, detail=None):
        checks.append(dict(check=name, passed=bool(ok), detail=detail))
        print("%-4s %s%s" % ("PASS" if ok else "FAIL", name, "" if detail is None else ": %s" % detail))

    try:                                                                        # 1
        fsha = R.check_freeze(a.freeze, a.setup_record)
        check("1 the freeze verifies", True, fsha)
    except SystemExit as e:
        fsha = None
        check("1 the freeze verifies", False, str(e))
    ssha = sha256_file(a.setup_record) if os.path.exists(a.setup_record) else None
    recs = sorted(glob.glob(os.path.join(a.folder, "RECEIPT_ALL_ROSTER*.json")))      # 2
    ok, detail = len(recs) == 1, recs
    if ok:
        mode = stat.S_IMODE(os.stat(recs[0]).st_mode)
        r = json.load(open(recs[0]))
        ok = (mode & 0o222) == 0 and r.get("outdir") == os.path.realpath(a.out) and r.get("freeze_sha256") == fsha \
            and r.get("setup_record_sha256") == ssha
        detail = dict(mode=oct(mode), outdir=r.get("outdir"), freeze=r.get("freeze_sha256"), setup=r.get("setup_record_sha256"))
    check("2 one read-only receipt naming the freeze, the setup record and the output folder", ok, detail)
    lines = [l.split() for l in open(a.status).read().splitlines() if l.strip()] if os.path.exists(a.status) else []   # 3
    starts, exits = [l for l in lines if l[0] == "START"], [l for l in lines if l[0] == "EXIT"]
    check("3 the job started once and ended once with exit 0", len(starts) == 1 and len(exits) == 1 and exits[0][1] == "0", lines)
    mpath = os.path.join(a.out, "MANIFEST.json")                                  # 4
    m = json.load(open(mpath)) if os.path.exists(mpath) else {}
    fz = json.load(open(a.freeze)) if os.path.exists(a.freeze) else {}
    roster = E.roster_all()
    listed = list(m.get("targets") or [])
    problems = [k for k, bad in (("freeze", m.get("freeze_sha256") != fsha), ("setup record", m.get("setup_record_sha256") != ssha),
                                 ("development run", m.get("development_only") is not False), ("roster", m.get("roster") != "all"),
                                 ("targets", listed != roster), ("policy", m.get("policy") != fz.get("policy")),
                                 ("size of C", m.get("size_c") != P.SIZE_C)) if bad]
    check("4 the run's manifest names the freeze, the setup record, the whole roster and the frozen policy", not problems, problems or None)
    tdir = os.path.join(a.out, "targets")                                          # 5
    have = sorted(n[:-5] for n in os.listdir(tdir) if n.endswith(".json")) if os.path.isdir(tdir) else []
    records = {n: json.load(open(os.path.join(tdir, n + ".json"))) for n in have}
    status = {}
    for n, r in records.items():
        status.setdefault(r.get("status"), []).append(n)
    odd = sorted(set(status) - {"done", "excluded", "incomplete"})
    check("5 one record for every listed target and no other", sorted(listed) == have and not odd,
          dict(missing=sorted(set(listed) - set(have)), extra=sorted(set(have) - set(listed)), other_status=odd))
    info["records_by_status"] = {k: len(v) for k, v in sorted(status.items(), key=lambda kv: str(kv[0]))}
    info["incomplete"] = sorted(status.get("incomplete", []))
    jbad = {}                                                                       # 6
    for n, r in records.items():
        jp = os.path.join(a.out, "journal", n + ".jsonl")
        ev = [json.loads(l) for l in open(jp)] if os.path.exists(jp) else []
        why = journal_problem(ev, r) if ev else "no journal"
        if why:
            jbad[n] = why
    check("6 every journal holds its path's events and seals, in order, equal to the record", not jbad, jbad or None)
    spath = os.path.join(a.out, "SUMMARY.json")                                   # 7
    have_s = json.load(open(spath)) if os.path.exists(spath) else None
    sr = json.load(open(a.setup_record)) if os.path.exists(a.setup_record) else None
    now_s = json.loads(json.dumps(SM.summarize(a.out, sr), default=str))
    check("7 SUMMARY.json equals a summary made now from the records", have_s == now_s)
    cal_f, cal_s = fz.get("calibration") or {}, (now_s or {}).get("calibration") or {}
    check("7b the calibration set (K and its names) equals the one committed with the freeze",
          "K" in cal_f and cal_f.get("K") == cal_s.get("K") and cal_f.get("names") == cal_s.get("names"),
          dict(freeze=cal_f.get("K"), summary=cal_s.get("K"), minimum=cal_s.get("minimum_K")))
    rc = (now_s or {}).get("reconciliation_with_the_committed_setup_record") or {}   # 8
    check("8 setup decisions and counts equal the committed record", rc.get("available") and rc.get("n_decisions_differ") == 0
          and rc.get("n_counts_differ") == 0, dict((k, rc.get(k)) for k in ("available", "n_compared", "n_decisions_differ", "n_counts_differ")))
    prim = (now_s or {}).get("PRIMARY") or {}
    info["primary_status"] = prim.get("status")                                    # 9
    near, timeouts, missing = [], {}, {}
    shortest = min(P.STREAM_GUARD_S, P.FINAL_GUARD_S)
    bound = dict(shortest_guard_s=shortest, margin_s=0.010, below=0, not_excluded=[], unknown=[])
    for n, r in records.items():
        tot, ss = r.get("cpu_s_total"), [s.get("cpu_s") for s in (r.get("searches") or {}).values()]
        if not isinstance(tot, (int, float)) or tot != tot or any(not isinstance(x, (int, float)) or x != x for x in ss):
            bound["unknown"].append(n)
            continue
        rest = tot - sum(ss) + 0.010
        if rest < -0.010:
            bound["unknown"].append(n)
        elif rest < shortest:
            bound["below"] += 1
        else:
            bound["not_excluded"].append("%s %.2f s" % (n, rest))
    info["guard_bound"] = bound
    for n, r in records.items():
        for k, s in (r.get("searches") or {}).items():
            if (s.get("cpu_s") or 0) >= NEAR * P.TIME_SAFETY_LIMIT_S:
                near.append("%s %s %.1f s" % (n, k, s["cpu_s"]))
        t, mi = guard_marks(r)
        if t:
            timeouts[n] = t
        if mi:
            missing[n] = mi
    info["searches_within_20_percent_of_the_safety_limit"] = near
    info["guard_timeouts"] = timeouts
    info["guarded_steps_without_a_mark"] = missing
    passed = all(c["passed"] for c in checks)
    print("primary status:", info["primary_status"], "| incomplete:", len(info["incomplete"]), "| near the safety limit:", len(near),
          "| guard timeouts:", sum(len(v) for v in timeouts.values()), "| unmarked guarded steps:", sum(len(v) for v in missing.values()),
          "| guard bound: below %d, not excluded %d, unknown %d" % (bound["below"], len(bound["not_excluded"]), len(bound["unknown"])))
    if a.write_manifest and passed:
        mp = os.path.join(a.folder, "FULL_OUT_MANIFEST.sha256")
        with open(mp, "x") as f:
            for root, _, files in sorted(os.walk(a.out)):
                for fn in sorted(files):
                    p = os.path.join(root, fn)
                    f.write("%s  %s\n" % (sha256_file(p), os.path.relpath(p, os.path.dirname(a.folder.rstrip("/")))))
        print("written:", mp)
    if a.report:
        with open(a.report, "x") as f:
            json.dump(dict(author="Chimdi Walter Ndubuisi", what="checks after the all-roster run of BL1", out=a.out, freeze=a.freeze,
                           freeze_sha256=fsha, setup_record=a.setup_record, setup_record_sha256=ssha, checks=checks,
                           informational=info, passed=passed), f, indent=1, default=str)
    if not passed:
        return 1
    return 2 if info["primary_status"] == "provisional" else 0


if __name__ == "__main__":
    sys.exit(main())
