"""Checks after THE all-roster run of EAF1, before any number is read out. Author: Chimdi Walter Ndubuisi

Not part of the freeze: it runs after the run and takes no part in it. It reads the experiment folder and the run's
output folder and changes nothing in either, except that --write-manifest writes FULL_OUT_MANIFEST.sha256 into the
experiment folder (once; it refuses to overwrite) and --report writes this check's report (once).

Checks, in order: the freeze still verifies (every frozen file and the setup record); exactly one receipt, read-only,
naming the freeze, the setup record and the output folder; the detached job started once and ended with exit 0; the
run's MANIFEST names the freeze, the setup record, the frozen code, the whole roster and the protocol's allowance; a
record for every listed target and no other, and no incomplete record; every done target's journal holds exactly the
seals its committed path requires (from the committed setup record: the admission set only in the admission cohort,
the reuse support set only in the reuse cohort, the library seal always), once each, in order, equal to the record's
seals, with one start at the protocol's allowance and a done event; the library files one per admitted arm,
read-only, equal to the hashes in the records, and bound through them to the journalled library seal of every done
target; SUMMARY.json equal to a summary made now from the records; the run's setup decisions and counts
equal to the committed record; the primary reading's status. A "provisional" status means STOP: nothing is read
further until the independent review has read the reason. Two readings are informational and not checks, both
declared before any outcome. (1) Per arm, the searches that used up the processor-time allowance or found their first
fit after 80% of it (where a run on another machine could end differently). (2) Whether a CPU guard can have fired at
all: a guard fires only after its whole length of processor time was spent inside one guarded batch, and the guards
of the evaluation code are 10 CPU seconds (candidate wrappers at setup), 20 (streams of pooled inputs) and 30 (checks
of a candidate); the searches are not under them. So for each done target the time outside its recorded searches (its
total minus the five arm searches and the two reuse controls) is compared with those lengths, and for each other
target the interval printed by the run. The comparison is conservative for rounding: 0.010 seconds is added to a
recorded remainder (the total is recorded to 0.01 s, up to seven search times to 0.001 s each) and 0.050 seconds to a
printed interval (one decimal). A missing or non-finite time, or a remainder more negative than the margin, makes the
target unknown; it is never taken as evidence that no guard fired. Only the final check of a first fit marks a timeout in the record; admission,
task exactness, reuse and the streams count a timed-out check as not exact or not usable without a mark, so this bound
is how their absence is shown. A target at or above a length is listed as not excluded by the bound, nothing more.

The protocol requires that the found expressions are read before any count is reported (read_expressions.py).

    env PYTHONHASHSEED=0 python3 -s -B experiments/evidence_across_failures_20261114/after_run_eaf.py \
        [--folder <experiment folder>] [--out <output folder>] [--freeze <freeze>] [--setup-record <setup record>] \
        --status outputs/detached/eaf1_full/run.status [--write-manifest] [--report <report.json>]

Defaults: this folder, its full_out/, FREEZE_3.json and SETUP_RECORD_ALL_3.json (the freeze in force); --status is required. Exit 0 when every check passed,
1 when one failed, 2 when the primary reading is provisional.
"""
import argparse
import glob
import hashlib
import json
import math
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NEAR = 0.8                                     # informational threshold: a first fit after 80% of the allowance
GUARDS = (("candidate wrappers at setup", 10.0), ("streams of pooled inputs", 20.0), ("checks of a candidate", 30.0))
ROUNDING_MARGIN = 0.010                        # CPU seconds added to a done target's recorded remainder before comparing
PRINTED_MARGIN = 0.050                         # CPU seconds added to an interval printed with one decimal
PRIMARY_FIELDS = ("status", "criterion_met", "n_targets_terminal", "wrong_first_fits", "right_first_fits", "n_favourable", "n_unfavourable",
                  "p_two_sided_sign_test", "conditions", "all_four_conditions_hold", "all_four_conditions_hold_in_both_readings",
                  "targets_with_a_wrong_only_because_the_final_check_timed_out", "incomplete_targets", "missing_eligible_targets",
                  "done_targets_outside_the_committed_cohort", "targets_whose_setup_differs_from_the_committed_record")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def expected_seals(decision):
    """The seals a done target must journal, once each and in this order, given its COMMITTED setup decision (episode_eaf:
    the admission set is sealed only in the admission cohort, the reuse support set only in the reuse cohort, the library
    seal always, even when no arm was admitted)."""
    out = ["setup_record", "acquisition_record", "first_fit_records"]
    if decision.get("cohort_admission"):
        out.append("admission_set")
    out.append("libraries")
    if decision.get("cohort_reuse"):
        out.append("reuse_support_set")
    return out + ["final_set"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=HERE)
    ap.add_argument("--out")
    ap.add_argument("--freeze")
    ap.add_argument("--setup-record")
    ap.add_argument("--status", required=True)
    ap.add_argument("--write-manifest", action="store_true")
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    folder = os.path.abspath(a.folder)
    out = os.path.abspath(a.out or os.path.join(folder, "full_out"))
    freeze = os.path.abspath(a.freeze or os.path.join(folder, "FREEZE_3.json"))
    setup = os.path.abspath(a.setup_record or os.path.join(folder, "SETUP_RECORD_ALL_3.json"))
    manifest_path = os.path.join(folder, "FULL_OUT_MANIFEST.sha256")
    if a.report and os.path.exists(a.report):
        sys.exit("refusing: %s exists" % a.report)
    if a.write_manifest and os.path.exists(manifest_path):
        sys.exit("refusing: %s exists" % manifest_path)
    if not os.path.isdir(out):
        sys.exit("refusing: no output folder %s" % out)
    sys.path.insert(0, folder)
    import run_eaf                     # noqa: E402  (imports eaf_frozen, which checks stage A's imported files)
    import summarize_eaf as SM         # noqa: E402
    import presets_eaf as P            # noqa: E402
    import library as LIB              # noqa: E402  (stage A's, read-only; on the path through eaf_frozen)
    checks, ok = [], [True]

    def check(name, cond, **detail):
        ok[0] = ok[0] and bool(cond)
        checks.append(dict(check=name, passed=bool(cond), **detail))
        print("%s  %s%s" % ("PASS" if cond else "FAIL", name, "" if cond or not detail else "\n      " + json.dumps(detail, default=str)[:800]),
              flush=True)

    # 1. the freeze
    try:
        fsha = run_eaf.check_freeze(freeze, setup)
        check("the freeze still verifies (every frozen file and the setup record)", fsha == sha(freeze), freeze_sha256=fsha)
    except SystemExit as e:
        check("the freeze still verifies (every frozen file and the setup record)", False, reason=str(e))
    fz = json.load(open(freeze))
    sr = json.load(open(setup))
    # 2. the receipt
    rc = sorted(glob.glob(os.path.join(folder, "RECEIPT_ALL_ROSTER*.json")))
    r = json.load(open(rc[0])) if len(rc) == 1 else {}
    check("exactly one receipt, read-only, naming this freeze, this setup record and this output folder",
          len(rc) == 1 and os.stat(rc[0]).st_mode & 0o222 == 0 and r.get("freeze_sha256") == sha(freeze)
          and r.get("setup_record_sha256") == sha(setup) and r.get("outdir") == os.path.realpath(out),
          receipts=[os.path.basename(p) for p in rc], receipt=r)
    # 3. the detached job
    lines = [x for x in open(a.status).read().split("\n") if x] if os.path.exists(a.status) else []
    check("the detached job started once and ended with exit 0",
          sum(x.startswith("START ") for x in lines) == 1 and sum(x.startswith("EXIT ") for x in lines) == 1
          and any(x.startswith("EXIT 0 ") for x in lines), lines=lines, status_file=a.status)
    # 4. the run's MANIFEST
    mp = os.path.join(out, "MANIFEST.json")
    m = json.load(open(mp)) if os.path.exists(mp) else {}
    hashes = m.get("hashes") or {}
    check("the run's MANIFEST names the freeze, the setup record, the frozen code, the whole roster and the allowance",
          m.get("roster") == "all" and m.get("development_only") is False and m.get("B") == P.B and m.get("freeze_sha256") == sha(freeze)
          and m.get("setup_record_sha256") == sha(setup) and m.get("pythonhashseed") == "0" and bool(hashes)
          and all(fz["files"].get(k) == v for k, v in hashes.items()),
          manifest={k: v for k, v in m.items() if k not in ("hashes", "targets")},
          code_not_in_the_freeze=sorted(k for k, v in hashes.items() if fz["files"].get(k) != v))
    # 5. the target records
    targets = list(m.get("targets") or [])
    on_disk = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(out, "targets", "*.json"))}
    recs = {t: json.load(open(os.path.join(out, "targets", t + ".json"))) for t in targets if t in on_disk}
    statuses = {}
    for t, x in recs.items():
        statuses[x.get("status")] = statuses.get(x.get("status"), 0) + 1
    missing, extra = sorted(set(targets) - on_disk), sorted(on_disk - set(targets))
    check("a record for every listed target and no other; the listed targets are those of the committed setup record",
          not missing and not extra and sorted(targets) == sorted(sr["targets"]), n_listed=len(targets), n_in_setup_record=len(sr["targets"]),
          missing=missing, extra=extra, statuses=statuses)
    incomplete = sorted(t for t, x in recs.items() if x.get("status") not in ("done", "excluded"))
    check("no incomplete record", not incomplete, statuses=statuses, incomplete={t: recs[t].get("reason") for t in incomplete})
    # 6. seals, 7. library files
    bad_seals, libs_journal, bad_journal, paths = {}, {}, [], {}
    for t, x in recs.items():
        if x.get("status") != "done":
            continue
        jp = os.path.join(out, "journal", t + ".jsonl")
        ev = [json.loads(y) for y in open(jp)] if os.path.exists(jp) else []
        seals = [(e.get("name"), e.get("sha256")) for e in ev if e.get("event") == "seal"]
        names = [n for n, _ in seals]
        need = expected_seals(sr["targets"][t]["decision"]) if t in sr["targets"] else None
        paths[" > ".join(need or ["<not in the setup record>"])] = paths.get(" > ".join(need or ["<not in the setup record>"]), 0) + 1
        if need is None or names != need or dict(seals) != (x.get("seals") or {}):
            bad_seals[t] = dict(journalled=names, required=need, equal_to_the_record=dict(seals) == (x.get("seals") or {}))
        libs_journal[t] = [h for n, h in seals if n == "libraries"]
        starts = [e for e in ev if e.get("event") == "start"]
        if len(starts) != 1 or starts[0].get("B") != P.B or sum(e.get("event") == "done" for e in ev) != 1:
            bad_journal.append(t)
    check("every done target journalled exactly the seals its committed path requires, once each, in order, equal to the record's seals",
          not bad_seals, differ=bad_seals, paths=paths)
    check("every done target's journal has one start at the protocol's allowance and one done event", not bad_journal, targets=bad_journal)
    libdir = os.path.join(out, "library")
    files = sorted(os.listdir(libdir)) if os.path.isdir(libdir) else []
    want, seal_bad = {}, []
    for t, x in recs.items():
        if x.get("status") != "done":
            continue
        arms = x.get("arms") or {}
        for arm, v in arms.items():
            if v.get("admitted"):
                want["%s__%s.json" % (t, arm)] = (v.get("library") or {}).get("sha256")
        shas = {arm: ((v.get("library") or {}).get("sha256") if v.get("admitted") else None) for arm, v in arms.items()}
        if libs_journal.get(t) != [LIB.sha256_json(shas)]:      # required: every done target journals one library seal
            seal_bad.append(t)
    not_matching = [f for f in files if want.get(f) != sha(os.path.join(libdir, f))]
    writable = [f for f in files if os.stat(os.path.join(libdir, f)).st_mode & 0o222]
    check("library files: one per admitted arm, read-only, equal to the hashes in the records, bound to each done target's journalled library seal",
          files == sorted(want) and not not_matching and not writable and not seal_bad, n_files=len(files), n_admitted_arms=len(want),
          files_without_an_admitted_arm=sorted(set(files) - set(want)), admitted_arms_without_a_file=sorted(set(want) - set(files)),
          not_matching=not_matching[:20], writable=writable[:20], seal_differs=seal_bad[:20])
    # 8. the summary
    sp = os.path.join(out, "SUMMARY.json")
    s_file = json.load(open(sp)) if os.path.exists(sp) else {}
    try:
        s_now, why = json.loads(json.dumps(SM.summarize(out, sr), sort_keys=True)), None
    except Exception as e:                                     # noqa: BLE001  a damaged record must fail the check, not stop the checker
        s_now, why = {}, "%s: %s" % (type(e).__name__, str(e)[:200])
    check("SUMMARY.json equals a summary made now from the records", s_file == s_now and why is None,
          keys_that_differ=sorted(k for k in set(s_file) | set(s_now) if s_file.get(k) != s_now.get(k)), summary_could_not_be_made=why)
    rcn = s_file.get("reconciliation_with_committed_setup_record") or {}
    check("the run's setup decisions and counts equal the committed setup record",
          rcn.get("available") is True and rcn.get("n_decisions_differ") == 0 and rcn.get("n_counts_differ") == 0
          and not rcn.get("targets_not_in_the_record"),
          reconciliation={k: rcn.get(k) for k in ("available", "n_compared", "n_decisions_differ", "n_counts_differ", "decisions_differ",
                                                  "targets_whose_counts_differ", "targets_not_in_the_record")})
    # 9. the primary reading
    prim = (s_file.get("block_outside_development_roster") or {}).get("PRIMARY_A3x3_against_A1x9") or {}
    status = prim.get("status")
    check("the primary reading is complete: met or not met (provisional means STOP)", status in ("met", "not_met"), status=status,
          incomplete=prim.get("incomplete_targets"), missing=prim.get("missing_eligible_targets"),
          outside=prim.get("done_targets_outside_the_committed_cohort"), setup_differs=prim.get("targets_whose_setup_differs_from_the_committed_record"))
    # Informational, not a check, declared before any outcome: the allowance is counted in processor seconds, so a search
    # that used it up, or found its first fit late in it, is where a run on another machine could end differently.
    near = {}
    for t, x in sorted(recs.items()):
        if x.get("status") != "done":
            continue
        for arm, v in sorted((x.get("arms") or {}).items()):
            c = v.get("cpu_to_first_fit")
            if v.get("stop_class") == "allowance_used_up" or (c is not None and c > NEAR * P.B):
                near.setdefault(arm, []).append(dict(target=t, stop_class=v.get("stop_class"), first_fit=v.get("first_fit"), cpu_to_first_fit=c))
    print("informational: per arm, searches that used up the allowance or found their first fit after %d%% of it: %s"
          % (round(100 * NEAR), {arm: len(v) for arm, v in sorted(near.items())}))
    # Informational, not a check, declared before any outcome: can a CPU guard have fired? (see the docstring)
    # Rounding (the independent review, note 0741): the total is recorded to 0.01 s and up to seven search times to 0.001 s
    # each, so the true time outside the searches is at most the recorded remainder plus 0.0085 s; ROUNDING_MARGIN is used.
    # A printed interval is rounded to 0.1 s: PRINTED_MARGIN is added. A missing or non-finite time, or a remainder more
    # negative than the margin, makes the target UNKNOWN: it is never evidence that no guard fired.
    def finite(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    outside, unknown = {}, {}
    for t, x in sorted(recs.items()):
        if x.get("status") != "done":
            continue
        times = [v.get("cpu_s") for v in (x.get("arms") or {}).values()]
        times += [c.get("cpu_s") for c in ((x.get("reuse") or {}).get("controls") or {}).values()]
        times = [v for v in times if v is not None]            # a search that did not run has no time: nothing is subtracted for it
        if not finite(x.get("cpu_s_total")) or not all(finite(v) and v >= 0 for v in times):
            unknown[t] = "a recorded time is missing or is not a finite number"
            continue
        rem = round(x["cpu_s_total"] - sum(times), 3)
        if rem < -ROUNDING_MARGIN:
            unknown[t] = "the recorded searches sum to more than the recorded total (remainder %.3f s)" % rem
            continue
        outside[t] = rem
    log_path = os.path.join(os.path.dirname(os.path.abspath(a.status)), "stdout.log")
    printed = {}
    if os.path.exists(log_path):
        for line in open(log_path):
            mm = re.match(r"\[\d+/\d+\] (\S+) (\S+) .*cpu=([0-9.]+)\s*$", line)
            if mm:
                printed[mm.group(1)] = float(mm.group(3))
    not_done = sorted(t for t, x in recs.items() if x.get("status") != "done")
    other = {t: printed[t] for t in not_done if t in printed and finite(printed[t])}
    for t in not_done:
        if t not in other:
            unknown[t] = "no printed interval in the job's log"
    upper_done = {t: round(v + ROUNDING_MARGIN, 3) for t, v in outside.items()}
    upper_other = {t: round(v + PRINTED_MARGIN, 3) for t, v in other.items()}
    by_guard = {}
    for name, length in GUARDS:
        by_guard[name] = dict(cpu_seconds=length, done_targets_not_excluded=sorted(t for t, v in upper_done.items() if v >= length),
                              other_targets_not_excluded=sorted(t for t, v in upper_other.items() if v >= length))
    none = not unknown and all(not g["done_targets_not_excluded"] and not g["other_targets_not_excluded"] for g in by_guard.values())
    top = sorted(((v, t) for t, v in outside.items()), reverse=True)[:5]
    guard_bound = dict(by_guard=by_guard, targets_without_a_recorded_time=sorted(unknown), why_unknown=unknown,
                       run_log=log_path if os.path.exists(log_path) else None,
                       rounding_margin_cpu_s=ROUNDING_MARGIN, printed_interval_margin_cpu_s=PRINTED_MARGIN,
                       compared="for a done target the recorded remainder plus the rounding margin; for any other target the printed interval plus its margin",
                       done_largest_time_outside_the_searches=top, other_largest_printed_interval=sorted(((v, t) for t, v in other.items()), reverse=True)[:5],
                       slightly_negative_remainders_within_the_margin=sorted(t for t, v in outside.items() if v < 0),
                       no_guard_can_have_fired=bool(none), per_done_target_cpu_s_outside_the_searches=outside,
                       assumptions="the recorded times are right; every guard needs its whole length inside one guarded batch; the searches are not under "
                                   "these guards; rounding as stated")
    print("informational: can a CPU guard have fired? %s; largest time outside the searches %s; not excluded by the bound: %s; no recorded time: %s"
          % ("no, for every target" if none else "NOT EXCLUDED for some targets", top[:1],
             {n: g["done_targets_not_excluded"] + g["other_targets_not_excluded"] for n, g in by_guard.items()
              if g["done_targets_not_excluded"] or g["other_targets_not_excluded"]}, sorted(unknown)))
    body = dict(author="Chimdi Walter Ndubuisi", what="checks after the all-roster run of EAF1 (after_run_eaf.py); no number is reported from here",
                near_the_allowance=dict(threshold_fraction=NEAR, by_arm=near), could_a_guard_have_fired=guard_bound,
                time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), folder=folder, out=out, freeze_sha256=sha(freeze),
                setup_record_sha256=sha(setup), all_passed=ok[0], checks=checks,
                primary={k: prim.get(k) for k in PRIMARY_FIELDS if k in prim}, summary_sha256=sha(sp) if os.path.exists(sp) else None,
                checker_sha256=sha(os.path.abspath(__file__)))
    if a.write_manifest:
        lines = []
        for dp, dn, fn in os.walk(out):
            dn.sort()
            for f in fn:
                p = os.path.join(dp, f)
                lines.append((os.path.relpath(p, out), sha(p)))
        lines.sort()
        with open(manifest_path, "x") as f:
            for rel, h in lines:
                f.write("%s  ./%s\n" % (h, rel))
        body["full_out_manifest"] = dict(path=manifest_path, n_files=len(lines), sha256=sha(manifest_path))
        print("manifest written: %s (%d files, sha256 %s)" % (manifest_path, len(lines), body["full_out_manifest"]["sha256"]))
    if a.report:
        with open(a.report, "x") as f:
            json.dump(body, f, indent=1, sort_keys=True, default=str)
            f.write("\n")
    print("\n%s; primary status: %s" % ("ALL CHECKS PASSED" if ok[0] else "A CHECK FAILED: stop and look before reading anything", status))
    if status == "provisional":
        print("STOP: the primary reading is provisional. Nothing is read further until the independent review has read the reason.")
        return 2
    print("Next, before any count is reported: read every found expression (read_expressions.py %s)." % out)
    return 0 if ok[0] else 1


if __name__ == "__main__":
    sys.exit(main())
