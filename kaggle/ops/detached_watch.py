"""A detached watcher for the October Kaggle work. It survives the end of a
Claude session and is started with setsid/nohup.

  setsid nohup python kaggle/ops/detached_watch.py >> outputs/kaggle_deploy/detached_watch.log 2>&1 &

Every 10 minutes, for up to 30 h, it updates
outputs/kaggle_deploy/detached_status.json:
1. native submission 57144804: when COMPLETE or ERROR, it writes
   outputs/kaggle_deploy/native_v1/official_score.json;
2. neural committed run `chimdiwalter/cora-neural-ttt-baseline-v1`,
   version 1:
   - on COMPLETE it downloads the outputs into
     outputs/kaggle_deploy/neural_v1_full_run1/ and runs
     kaggle/neural_v1/audit_run.py;
   - it submits ONCE, as NEURAL_TTT_BASELINE, only if every gate holds
     (the user's standing one-entry authorization of 2026-10-13):
     - the status is COMPLETE;
     - 0 schema problems;
     - log span under 11.9 h;
     - all stand-in tasks started;
     - default-only positions at most 10%;
     - fallback positions (default, missing or repair input-copy) at most 10%;
     - decoded output files for at least 90% of tasks (from the manifest);
     - the stored kernel metadata still has internet off;
     - submission-limits shows a remaining slot;
     - no earlier NEURAL_TTT_BASELINE submission exists.

     Otherwise it records NEURAL_BLOCKED with the reasons and submits
     nothing.
   - It then follows that submission's score;
3. C2 CORA_ONLY run: notes when outputs/hybrid_c2/native_run/run_meta.json
   appears.

A pid file refuses a second copy. No credential is ever printed.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
K = os.path.expanduser("~/.venvs/kaggle-cli/bin/kaggle")
COMP = "arc-prize-2026-arc-agi-2"
NATIVE_ID = "57144804"
KERNEL = "chimdiwalter/cora-neural-ttt-baseline-v1"
DEP = os.path.join(ROOT, "outputs", "kaggle_deploy")
STATUS = os.path.join(DEP, "detached_status.json")
PID = os.path.join(DEP, "detached_watch.pid")
RUN = os.path.join(DEP, "neural_v1_full_run1")
STANDIN = os.path.join(DEP, "native_v1", "kaggle_run_v1", "comp", "arc-agi_test_challenges.json")
MSG = ("NEURAL_TTT_BASELINE neural_v1: public NVARC Qwen3-4B TTT pipeline reproduced (sorokin/qwen3_4b_grids15_sft139, "
       "notebook chimdiwalter/cora-neural-ttt-baseline-v1 v1); not CORA, not FULL_CORA")


def kag(*args, timeout=300):
    try:
        r = subprocess.run([K, "-W", *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except Exception as e:                                          # noqa: BLE001
        return 1, repr(e)


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def submission_rows():
    rc, out = kag("competitions", "submissions", COMP)
    return out.splitlines() if rc == 0 else []


def gates(audit):
    reasons = []
    if audit.get("schema_problems") != 0:
        reasons.append(f"schema_problems={audit.get('schema_problems')}")
    if not audit.get("log_span_s") or audit["log_span_s"] >= 11.9 * 3600:
        reasons.append(f"log_span_s={audit.get('log_span_s')}")
    if audit.get("tasks_never_started", 1) != 0:
        reasons.append(f"tasks_never_started={audit.get('tasks_never_started')}")
    if audit.get("positions_default_only", 999) > 0.10 * audit.get("positions", 0):
        reasons.append(f"positions_default_only={audit.get('positions_default_only')}")
    # fallback = default [[0]], missing, or the repair cell's input copy; none of these is a neural prediction
    if audit.get("positions_fallback") is None or audit["positions_fallback"] > 0.10 * audit.get("positions", 0):
        reasons.append(f"positions_fallback={audit.get('positions_fallback')}")
    # independent of submission.json: decoded output files must exist for at least 90% of tasks
    if (audit.get("tasks_with_decoded_outputs") or 0) < 0.90 * audit.get("tasks", 10 ** 6):
        reasons.append(f"tasks_with_decoded_outputs={audit.get('tasks_with_decoded_outputs')}")
    return reasons


def main():
    if os.path.exists(PID):
        try:
            os.kill(int(open(PID).read()), 0)
            sys.exit("another watcher is alive: refusing")
        except (OSError, ValueError):
            pass
    open(PID, "w").write(str(os.getpid()))
    st = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    st.setdefault("native", {"done": False}); st.setdefault("neural", {"stage": "running"}); st.setdefault("c2", {"done": False})
    end = time.time() + 30 * 3600
    while time.time() < end:
        st["checked_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rows = submission_rows()
        # 1. native score
        if not st["native"]["done"]:
            line = next((l for l in rows if l.startswith(NATIVE_ID)), "")
            if "COMPLETE" in line or "ERROR" in line:
                st["native"] = {"done": True, "row": " ".join(line.split())}
                json.dump(st["native"], open(os.path.join(DEP, "native_v1", "official_score.json"), "w"), indent=1)
                log(f"native scored: {st['native']['row']}")
        # 2. neural run
        nst = st["neural"]
        if nst["stage"] == "running":
            rc, out = kag("kernels", "status", KERNEL)
            last = out.strip().splitlines()[-1] if out.strip() else ""
            nst["kernel_status"] = last
            if "ERROR" in last or "CANCEL" in last:
                os.makedirs(RUN, exist_ok=True)
                kag("kernels", "output", KERNEL, "-p", RUN, "--file-pattern", r"(\.log|execution_manifest\.json)$", timeout=1800)
                nst["stage"] = "NEURAL_BLOCKED"; nst["reasons"] = [f"kernel {last}"]
                log(f"neural run failed: {last}")
            elif "COMPLETE" in last:
                os.makedirs(RUN, exist_ok=True)
                kag("kernels", "output", KERNEL, "-p", RUN, "--file-pattern",
                    r"(submission\.json|execution_manifest\.json|asset_identity_light\.json|\.log)$", timeout=1800)
                a = subprocess.run([sys.executable, os.path.join(ROOT, "kaggle", "neural_v1", "audit_run.py"), RUN, STANDIN],
                                   capture_output=True, text=True)
                audit = json.load(open(os.path.join(RUN, "coverage_audit.json"))) if os.path.exists(os.path.join(RUN, "coverage_audit.json")) else {}
                nst["audit"] = {k: audit.get(k) for k in ("tasks_started", "tasks_finished", "tasks_timed_out", "tasks_never_started",
                                                          "positions_genuine_attempt_1", "positions_genuine_attempt_2",
                                                          "positions_default_only", "positions_fallback", "positions_genuine", "repaired_attempts",
                                                          "tasks_with_decoded_outputs", "schema_problems", "log_span_h")}
                reasons = gates(audit) if audit else ["audit failed: " + a.stderr[-300:]]
                meta_dir = os.path.join(RUN, "meta_check")
                os.makedirs(meta_dir, exist_ok=True)
                kag("kernels", "pull", KERNEL, "-p", meta_dir, "-m")
                try:
                    if json.load(open(os.path.join(meta_dir, "kernel-metadata.json"))).get("enable_internet") is not False:
                        reasons.append("stored metadata: internet not off")
                except Exception:                                   # noqa: BLE001
                    reasons.append("stored metadata unreadable")
                if any("NEURAL_TTT_BASELINE" in l for l in rows):
                    reasons.append("a NEURAL_TTT_BASELINE submission already exists")
                rc, lim = kag("competitions", "submission-limits", COMP)
                if "Remaining today: 0" in lim or rc != 0:
                    reasons.append("no submission slot today (will retry next check)")
                    nst["gates_waiting_for_slot"] = True
                if reasons and not (reasons == ["no submission slot today (will retry next check)"]):
                    nst["stage"] = "NEURAL_BLOCKED"; nst["reasons"] = reasons
                    log(f"neural gates failed: {reasons}")
                elif not reasons:
                    rc, out = kag("competitions", "submit", COMP, "-k", KERNEL, "-v", "1", "-f", "submission.json", "-m", MSG)
                    nst["submit_output"] = out.strip()[-300:]
                    nst["stage"] = "submitted" if rc == 0 else "NEURAL_BLOCKED"
                    nst["submitted_utc"] = st["checked_utc"]
                    log(f"neural submit rc={rc}: {out.strip()[-200:]}")
        elif nst["stage"] == "submitted":
            line = next((l for l in rows if "NEURAL_TTT_BASELINE" in l), "")
            nst["row"] = " ".join(line.split())
            if "COMPLETE" in line or "ERROR" in line:
                nst["stage"] = "scored"
                json.dump(nst, open(os.path.join(DEP, "neural_v1_official_score.json"), "w"), indent=1)
                log(f"neural scored: {nst['row']}")
        # 3. C2
        if not st["c2"]["done"]:
            m = os.path.join(ROOT, "outputs", "hybrid_c2", "native_run", "run_meta.json")
            if os.path.exists(m):
                st["c2"] = {"done": True, "run_meta": json.load(open(m))}
                log(f"C2 CORA_ONLY finished: {st['c2']['run_meta']}")
        json.dump(st, open(STATUS, "w"), indent=1)
        if st["native"]["done"] and st["c2"]["done"] and nst["stage"] in ("scored", "NEURAL_BLOCKED"):
            log("all watched items settled; exiting")
            break
        time.sleep(600)
    os.remove(PID)


if __name__ == "__main__":
    main()
