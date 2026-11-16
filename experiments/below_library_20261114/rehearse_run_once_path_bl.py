"""End-to-end rehearsal of the run-once path of BL1, in fresh processes, on development names only.
Author: Chimdi Walter Ndubuisi

The all-roster run is launched once. Its exact command path is therefore executed here first, on a COPY of this folder
and with a small roster made of development names: the setup-only pass, the freeze, the launch with the freeze and the
setup record, the receipt, the per-target records and journals, the summary read against the committed setup record,
the check of every frozen hash after the run, the refusals that must follow (a second launch into the same folder, a
launch into another folder, a launch into a folder that is not empty), and then the after-run checker
(after_run_bl.py) and the earlier-result check (earlier_result_check.py) on that output, as they will be run.

Only two things are replaced, by a small wrapper in the copy that then calls the unchanged code: the roster (a few
development names, through episode_bl.roster_all) and the list of names labelled "development" (so that some of them
count as outside it and the code path of the primary reading runs on real records). No name outside the development
roster is searched. With no control in the roster the calibration cannot be valid, so the primary must read "not
interpretable" here; that is checked as the expected reading. Every output of this script is a rehearsal, never a
result.

    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B \
        experiments/below_library_20261114/rehearse_run_once_path_bl.py <log.json> name1,name2,... <name kept as development>
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl_frozen             # noqa: E402
import presets_bl as P       # noqa: E402

WRAPPER = '''import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import presets_bl, episode_bl
ROSTER = %r
episode_bl.roster_all = lambda: list(ROSTER)            # the rehearsal's small roster of development names
presets_bl.DEV_ROSTER = %r                              # the names still labelled development in the rehearsal
import %s as M
sys.exit(M.main(sys.argv[1:]))
'''


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(argv):
    log_path, roster, keep_dev = argv[0], argv[1].split(","), argv[2]
    if os.path.exists(log_path):
        sys.exit("refusing: %s exists" % log_path)
    bad = [t for t in roster if t not in P.DEV_ROSTER]
    if bad or keep_dev not in roster:
        sys.exit("refusing: the rehearsal uses development names only (%s)" % bad)
    if not os.path.exists(os.path.join(HERE, "PROTOCOL.md")):
        sys.exit("refusing: PROTOCOL.md does not exist yet (the rehearsal freezes the real text)")
    work = tempfile.mkdtemp(prefix="bl1_rehearsal_")
    exp = os.path.join(work, "expcopy")
    shutil.copytree(HERE, exp, ignore=shutil.ignore_patterns("dev_out*", "dev_load*", "full_out*", "__pycache__", "RECEIPT*", "FREEZE*",
                                                             "SETUP*", "dev_setup*", "REHEARSAL*", "AFTER_RUN*", "EARLIER_RESULT*",
                                                             "FULL_OUT_MANIFEST*", "pilot_five_nodes_out", "*.time.txt"))
    for name, module in (("rehearsal_main.py", "run_bl"), ("rehearsal_after.py", "after_run_bl")):
        with open(os.path.join(exp, name), "w") as f:
            f.write(WRAPPER % (roster, (keep_dev,), module))
    with open(os.path.join(exp, "rehearsal_earlier.py"), "w") as f:
        f.write(WRAPPER.replace("sys.exit(M.main(sys.argv[1:]))", "sys.exit(M.main(*sys.argv[1:3]))") % (roster, (keep_dev,), "earlier_result_check"))
    env = dict(os.environ, PYTHONHASHSEED="0")
    S, F, OUT = os.path.join(exp, "SETUP_RECORD_ALL.json"), os.path.join(exp, "FREEZE.json"), os.path.join(work, "full_out")
    STATUS = os.path.join(work, "run.status")
    steps, ok = [], True

    def step(name, script, args, expect, must_contain=None):
        nonlocal ok
        t = time.time()
        r = subprocess.run([sys.executable, "-s", "-B", os.path.join(exp, script)] + args, env=env, capture_output=True, text=True, cwd=work)
        txt = r.stdout + r.stderr
        good = (r.returncode in expect) and (must_contain is None or must_contain in txt)
        ok = ok and good
        steps.append(dict(step=name, args=[a.replace(work, "<work>") for a in args], returncode=r.returncode, expected=sorted(expect),
                          passed=good, seconds=round(time.time() - t, 1), last_lines=[x.replace(work, "<work>") for x in txt.strip().splitlines()[-4:]]))
        return r

    def check(name, cond, **detail):
        nonlocal ok
        ok = ok and bool(cond)
        steps.append(dict(check=name, passed=bool(cond), **detail))

    run = "rehearsal_main.py"
    step("launch with no freeze", run, [OUT, "--roster", "all"], {1}, "freeze")
    step("setup-only pass", run, ["--setup-only", S, "--roster", "all"], {0})
    step("setup-only pass refuses to overwrite", run, ["--setup-only", S, "--roster", "all"], {1}, "exists")
    step("freeze", run, ["--make-freeze", F, "--setup-record", S], {0})
    step("freeze refuses to overwrite", run, ["--make-freeze", F, "--setup-record", S], {1}, "written once")
    os.makedirs(OUT)
    open(os.path.join(OUT, "left_over"), "w").write("x")
    step("launch into a folder that is not empty", run, [OUT, "--roster", "all", "--freeze", F, "--setup-record", S], {1}, "new or empty")
    check("no receipt after the refusals", not os.path.exists(os.path.join(exp, "RECEIPT_ALL_ROSTER.json")))
    shutil.rmtree(OUT)
    with open(STATUS, "w") as f:
        f.write("START %s 0\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    r = step("THE LAUNCH", run, [OUT, "--roster", "all", "--freeze", F, "--setup-record", S], {0}, "summary:")
    with open(STATUS, "a") as f:
        f.write("EXIT %d %s\n" % (r.returncode, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    rc = os.path.join(exp, "RECEIPT_ALL_ROSTER.json")
    check("receipt written, read-only, names the freeze", os.path.exists(rc) and os.stat(rc).st_mode & 0o222 == 0
          and json.load(open(rc))["freeze_sha256"] == sha(F))
    fz = json.load(open(F))
    changed = [k for table in ("files", "stage_a_files") for k, v in fz[table].items() if sha(os.path.join(bl_frozen.ROOT, k)) != v]
    check("every frozen file unchanged after the run", not changed, changed=changed)
    check("the setup record unchanged after the run", sha(S) == fz["setup_record"]["sha256"])
    recs = {t: json.load(open(os.path.join(OUT, "targets", t + ".json"))) for t in roster if os.path.exists(os.path.join(OUT, "targets", t + ".json"))}
    check("a record for every name of the roster", sorted(recs) == sorted(roster), statuses={t: r.get("status") for t, r in recs.items()})
    check("no incomplete record", all(r.get("status") in ("done", "excluded") for r in recs.values()))
    s = json.load(open(os.path.join(OUT, "SUMMARY.json")))
    prim, cal = s["PRIMARY"], s["calibration"]
    check("the primary reads 'not interpretable' with the calibration not valid (no control in this roster), never provisional",
          prim.get("status") == "not_interpretable" and not cal.get("valid"), status=prim.get("status"), calibration_state=cal.get("state"),
          calibration_reasons=cal.get("reasons"), complete=prim.get("cohort_complete"))
    rcn = s["reconciliation_with_the_committed_setup_record"]
    check("setup decisions and counts equal the committed record", rcn.get("available") and rcn["n_decisions_differ"] == 0 and rcn["n_counts_differ"] == 0,
          n_compared=rcn.get("n_compared"))
    dc = recs.get(P.DEV_CONTROL)
    if dc is not None and dc.get("status") == "done":
        w = dc.get("witness") or {}
        check("the development witness was evaluated after the final panel was opened", w.get("state") not in (None, "no manifest", "no manifest entry"),
              witness={k: w.get(k) for k in ("state", "valid", "agree_fit", "agree_final", "guard_timeout") if k in w})
    before = {f: sha(os.path.join(OUT, "targets", f)) for f in sorted(os.listdir(os.path.join(OUT, "targets")))}
    step("a second launch into the same folder", run, [OUT, "--roster", "all", "--freeze", F, "--setup-record", S], {1}, "never resumed")
    step("a launch into another folder", run, [OUT + "_2", "--roster", "all", "--freeze", F, "--setup-record", S], {1}, "never resumed")
    check("the refused launches changed nothing", before == {f: sha(os.path.join(OUT, "targets", f)) for f in sorted(os.listdir(os.path.join(OUT, "targets")))}
          and not os.path.exists(OUT + "_2"))
    AR = os.path.join(work, "AFTER_RUN_CHECK.json")
    step("the after-run checker", "rehearsal_after.py", ["--folder", exp, "--out", OUT, "--freeze", F, "--setup-record", S, "--status", STATUS,
                                                         "--write-manifest", "--report", AR], {0}, "primary status:")
    check("the after-run checker wrote its report and the output manifest", os.path.exists(AR) and os.path.exists(os.path.join(exp, "FULL_OUT_MANIFEST.sha256")))
    step("the after-run checker refuses to overwrite its report", "rehearsal_after.py", ["--folder", exp, "--out", OUT, "--freeze", F,
         "--setup-record", S, "--status", STATUS, "--report", AR], {1}, "FileExistsError")
    ER = os.path.join(work, "EARLIER_RESULT_CHECK.json")
    step("the earlier-result check", "rehearsal_earlier.py", [OUT, ER], {0})
    check("the earlier-result check covers every record", os.path.exists(ER) and len(json.load(open(ER))["rows"]) == len(recs))
    searches = {t: {k: (v.get("expr"), v.get("stop_class")) for k, v in (r.get("searches") or {}).items()} for t, r in recs.items()}
    body = dict(author="Chimdi Walter Ndubuisi", what="rehearsal of the run-once path of BL1 on development names; never a result",
                label="development only: a rehearsal", roster=roster, labelled_development_in_the_rehearsal=[keep_dev],
                all_passed=ok, steps=steps, outcomes_development_only=searches,
                after_run_report=json.load(open(AR)) if os.path.exists(AR) else None,
                code_hashes={n: sha(os.path.join(HERE, n)) for n in ("bl_frozen.py", "presets_bl.py", "episode_bl.py", "summarize_bl.py", "run_bl.py",
                                                                     "after_run_bl.py", "earlier_result_check.py")},
                protocol_sha256=sha(os.path.join(HERE, "PROTOCOL.md")), time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(log_path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True, default=str)
        f.write("\n")
    for root, _, files in os.walk(work):
        for fn in files:
            try:
                os.chmod(os.path.join(root, fn), 0o644)
            except OSError:
                pass
    shutil.rmtree(work, ignore_errors=True)
    print("rehearsal %s: %d steps and checks, log %s" % ("PASSED" if ok else "FAILED", len(steps), log_path))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
