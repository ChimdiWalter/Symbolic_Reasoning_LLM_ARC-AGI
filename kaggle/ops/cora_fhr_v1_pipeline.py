#!/usr/bin/env python3
"""Detached, gated CORA_FHR_V1 pipeline (records/KAGGLE_CORA_FHR_V1_LOG_20261015.md).

  setsid nohup python kaggle/ops/cora_fhr_v1_pipeline.py >> outputs/kaggle_deploy/cora_fhr_v1/pipeline.log 2>&1 &

The user's directive (2026-10-14) authorizes ONE CORA-specific submission, and only if the gates pass.
The stages are resumable from state.json:

1. emulation: the offline, network-guarded notebook emulation (G2a).
2. dataset: upload the tested FHR package, as a private dataset.
3. kernel: push the tested notebook (private, no internet), which starts the committed run on the 240
   stand-in tasks.
4. run: poll the run until it completes.
5. outputs: download the outputs and check G2b (runtime, coverage, schema, FHR ran, restores, native
   agreement).
6. g1: wait for the 60-task development run and check its safety gates (0 wrong extension certificates,
   0 lost answers, 0 restore failures).
7. submit: ONE submission, guarded by a marker file and today's quota.
8. score: poll until the official score arrives.

Any failed gate stops the pipeline as BLOCKED_<stage>, with no submission. It never prints credentials,
never touches the NVARC or native kernels, and never selects final submissions.
"""
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
K = os.path.expanduser("~/.venvs/kaggle-cli/bin/kaggle")
PY = os.path.join(ROOT, ".venv_arc2026", "bin", "python")
COMP = "arc-prize-2026-arc-agi-2"
DATASET = "chimdiwalter/arc-cora-fhr-v1"
KERNEL = "chimdiwalter/cora-fhr-v1-arc-agi-2-research-entry"
SRC = os.path.join(ROOT, "kaggle", "cora_fhr_v1")
DEP = os.path.join(ROOT, "outputs", "kaggle_deploy", "cora_fhr_v1")
STATE = os.path.join(DEP, "state.json")
MARKER = os.path.join(DEP, "SUBMITTED")
STANDIN = os.path.join(ROOT, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "comp", "arc-agi_test_challenges.json")
NATIVE_V1_SUB = os.path.join(ROOT, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "submission.json")
TAG = "CORA_FHR_V1"


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def kag(*args, timeout=600):
    try:
        r = subprocess.run([K, "-W", *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:                                              # noqa: BLE001
        return 1, repr(e)


def save(st):
    st["updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(st, open(STATE, "w"), indent=1)


def sha(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def block(st, stage, why):
    st["stage"] = f"BLOCKED_{stage}"
    st["blocked_reason"] = why
    save(st)
    log(f"BLOCKED at {stage}: {why}")
    sys.exit(0)


def stage_emulation(st):
    summ = os.path.join(SRC, "emulation", "summary.json")
    r = subprocess.run([PY, os.path.join(SRC, "emulate.py")], capture_output=True, text=True, timeout=6 * 3600, cwd=ROOT)
    open(os.path.join(DEP, "emulation_stdout.log"), "w").write(r.stdout[-20000:] + "\n--- stderr ---\n" + r.stderr[-20000:])
    if r.returncode != 0 or not os.path.exists(summ):
        block(st, "EMULATION", f"emulator returncode {r.returncode}")
    s = json.load(open(summ))
    c = s.get("fhr_counts") or {}
    checks = {"notebook_rc0": s.get("returncode") == 0, "schema": s.get("schema_ok"), "provenance": s.get("provenance_complete"),
              "guard_clean": s.get("guard_log_empty"), "no_fhr_error": s.get("fhr_error") is None,
              "fhr_rc0": s.get("fhr_returncode") == 0, "fhr_ran": c.get("ran", 0) >= 1,
              "merge_exercised": c.get("committed_tasks", 0) >= 1,
              "witness_correct": s.get("witness_attempt_1_correct (dev answer, emulator only)") is True,
              "no_restore_failures": c.get("restore_failures", 1) == 0, "no_task_errors": c.get("errors", 1) == 0}
    st["emulation"] = {"checks": checks, "fhr_counts": c, "elapsed_s": s.get("elapsed_s")}
    if not all(checks.values()):
        block(st, "EMULATION", json.dumps(checks))
    st["tested"] = {"tarball_sha256": sha(os.path.join(SRC, "arc_cora_fhr_v1.tar.gz")),
                    "notebook_py_sha256": sha(os.path.join(SRC, "notebook.py")),
                    "notebook_ipynb_sha256": sha(os.path.join(SRC, "notebook.ipynb"))}
    st["stage"] = "dataset"
    save(st)
    log(f"emulation PASSED: {json.dumps(c)}")


def stage_dataset(st):
    import shutil
    d = os.path.join(DEP, "dataset")
    os.makedirs(d, exist_ok=True)
    tar = os.path.join(SRC, "arc_cora_fhr_v1.tar.gz")
    if sha(tar) != st["tested"]["tarball_sha256"]:
        block(st, "DATASET", "tarball changed after the emulation")
    shutil.copy(tar, os.path.join(d, "arc_cora_fhr_v1.tar.gz"))
    shutil.copy(os.path.join(ROOT, "kaggle", "cora_fhr_v1_deploy", "dataset", "dataset-metadata.json"), d)
    rc, out = kag("datasets", "create", "-p", d, timeout=1800)
    log(f"datasets create rc={rc}: {out[-300:]}")
    if rc != 0 and "already exists" in out.lower():
        rc, out = kag("datasets", "version", "-p", d, "-m", "CORA_FHR_V1 package (tested by emulation)", timeout=1800)
        log(f"datasets version rc={rc}: {out[-300:]}")
    if rc != 0:
        block(st, "DATASET", out[-300:])
    for _ in range(60):
        rc, out = kag("datasets", "status", DATASET)
        if rc == 0 and "ready" in out.lower():
            break
        time.sleep(60)
    else:
        block(st, "DATASET", f"not ready: {out[-200:]}")
    st["dataset"] = {"status": out[-200:], "tarball_sha256": st["tested"]["tarball_sha256"]}
    st["stage"] = "kernel"
    save(st)
    log("dataset ready")


def stage_kernel(st):
    import shutil
    d = os.path.join(DEP, "kernel")
    os.makedirs(d, exist_ok=True)
    nb = os.path.join(SRC, "notebook.ipynb")
    if sha(nb) != st["tested"]["notebook_ipynb_sha256"] or sha(os.path.join(SRC, "notebook.py")) != st["tested"]["notebook_py_sha256"]:
        block(st, "KERNEL", "notebook changed after the emulation")
    shutil.copy(nb, os.path.join(d, "notebook.ipynb"))
    shutil.copy(os.path.join(ROOT, "kaggle", "cora_fhr_v1_deploy", "kernel", "kernel-metadata.json"), d)
    rc, out = kag("kernels", "push", "-p", d, timeout=1800)
    log(f"kernels push rc={rc}: {out[-300:]}")
    m = re.search(r"version (\d+)", out, re.I)
    if rc != 0 or not m:
        block(st, "KERNEL", out[-300:])
    st["kernel_version"] = int(m.group(1))
    pull = os.path.join(DEP, "kernel_pulled")
    os.makedirs(pull, exist_ok=True)
    rc, out = kag("kernels", "pull", KERNEL, "-p", pull, "-m")
    meta = os.path.join(pull, "kernel-metadata.json")
    if rc == 0 and os.path.exists(meta):
        km = json.load(open(meta))
        st["kernel_settings"] = {k: km.get(k) for k in ("enable_internet", "enable_gpu", "dataset_sources", "competition_sources")}
        if km.get("enable_internet") is not False:
            block(st, "KERNEL", f"internet not disabled: {km.get('enable_internet')}")
    st["stage"] = "run"
    st["run_started_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save(st)
    log(f"kernel version {st['kernel_version']} pushed; committed run started")


def stage_run(st):
    t0 = time.time()
    while time.time() - t0 < 14 * 3600:
        rc, out = kag("kernels", "status", KERNEL)
        if rc == 0:
            st["kernel_status"] = out[-200:]
            save(st)
            low = out.lower()
            if "complete" in low:
                st["stage"] = "outputs"
                save(st)
                log(f"committed run COMPLETE: {out[-120:]}")
                return
            if "error" in low or "cancel" in low:
                block(st, "RUN", out[-200:])
        time.sleep(600)
    block(st, "RUN", "no completion within 14 h")


def validate(sub, ch):
    def ok(g):
        return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) for r in g) and 1 <= len(g[0]) <= 30
                and all(len(r) == len(g[0]) for r in g) and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))
    problems = 0
    for tid, t in ch.items():
        e = sub.get(tid)
        if not isinstance(e, list) or len(e) != len(t["test"]):
            problems += 1
            continue
        problems += sum(not (isinstance(x, dict) and set(x) == {"attempt_1", "attempt_2"} and ok(x["attempt_1"]) and ok(x["attempt_2"]))
                        for x in e)
    return problems + len(set(sub) - set(ch))


def stage_outputs(st):
    out_dir = os.path.join(DEP, f"run_v{st['kernel_version']}")
    os.makedirs(out_dir, exist_ok=True)
    rc, out = kag("kernels", "output", KERNEL, "-p", out_dir, "--file-pattern",
                  r"(submission\.json|submission_native\.json|execution_manifest\.json|provenance\.json|fhr_rows\.jsonl|\.log)$",
                  timeout=3600)
    log(f"kernels output rc={rc}: {out[-200:]}")
    need = ["submission.json", "submission_native.json", "execution_manifest.json", "provenance.json"]
    if rc != 0 or not all(os.path.exists(os.path.join(out_dir, n)) for n in need):
        block(st, "OUTPUTS", f"missing outputs: {out[-200:]}")
    ch = json.load(open(STANDIN))
    sub = json.load(open(os.path.join(out_dir, "submission.json")))
    nat = json.load(open(os.path.join(out_dir, "submission_native.json")))
    man = json.load(open(os.path.join(out_dir, "execution_manifest.json")))
    prov = json.load(open(os.path.join(out_dir, "provenance.json")))
    v1 = json.load(open(NATIVE_V1_SUB))
    pos = [(t, i) for t in ch for i in range(len(ch[t]["test"]))]
    same = sum(1 for t, i in pos if t in nat and t in v1 and nat[t][i]["attempt_1"] == v1[t][i]["attempt_1"])
    diffs = [f"{t}:{i}" for t, i in pos if not (t in nat and t in v1 and nat[t][i]["attempt_1"] == v1[t][i]["attempt_1"])]
    c = man.get("fhr_counts") or {}
    checks = {"harness_completed": man.get("harness_status") == "completed",
              "runtime_under_11.5h": (man.get("elapsed_s") or 1e9) < 11.5 * 3600,
              "coverage": set(sub) == set(ch), "schema_problems_0": validate(sub, ch) == 0,
              "provenance_complete": all(len(prov.get(t, [])) == len(ch[t]["test"]) for t in ch),
              "fhr_ran": c.get("ran", 0) >= 1, "no_fhr_error": "fhr_error" not in man,
              "fhr_rc0": man.get("fhr_returncode") == 0, "no_restore_failures": c.get("restore_failures", 1) == 0,
              "native_agreement_95pct": same / max(1, len(pos)) >= 0.95}
    st["g2b"] = {"checks": checks, "native_agreement": [same, len(pos)], "native_differences": diffs[:60],
                 "fhr_counts": c, "elapsed_h": round((man.get("elapsed_s") or 0) / 3600, 2),
                 "harness_h": round((man.get("harness_s") or 0) / 3600, 2), "fhr_h": round((man.get("fhr_s") or 0) / 3600, 2)}
    save(st)
    if not all(checks.values()):
        block(st, "OUTPUTS", json.dumps(checks))
    st["stage"] = "g1"
    save(st)
    log(f"G2b PASSED: {json.dumps(st['g2b'], default=str)[:600]}")


def stage_g1(st):
    flog = os.path.join(ROOT, "outputs", "cora_fhr", "followup_dev60.log")
    t0 = time.time()
    while not (os.path.exists(flog) and "DEV60 DONE" in open(flog).read()):
        if time.time() - t0 > 30 * 3600:
            block(st, "G1", "dev60 run not finished within 30 h")
        time.sleep(600)
    sys.path.insert(0, ROOT)
    from cora_fhr.evaluate import answers                               # evaluator side only
    ans = answers("dev60")
    rows = [json.loads(x) for x in open(os.path.join(ROOT, "outputs", "cora_fhr", "rows_dev60.jsonl"))]
    res = {"tasks": len(rows), "A_certified_correct": 0, "E_ext_correct": 0, "E_ext_wrong": 0, "E_lost_A": 0, "E_restore_failures": 0,
           "C2_ext_correct": 0, "C2_ext_wrong": 0, "B_certified_correct": 0, "E_outcomes": {}, "E_operators": []}
    for r in rows:
        outs = ans[r["key"]][0]
        A = r["arms"].get("A", {})
        a_ok = bool(A.get("certified")) and A.get("committed") == outs
        res["A_certified_correct"] += a_ok
        B = r["arms"].get("B", {})
        res["B_certified_correct"] += bool(B.get("certified")) and B.get("committed") == outs
        for arm in ("E", "C2"):
            x = r["arms"].get(arm, {})
            ext = str(x.get("certified_by") or "").endswith("+extension")
            res[f"{arm}_ext_correct"] += ext and x.get("committed") == outs
            res[f"{arm}_ext_wrong"] += ext and x.get("committed") != outs
            if arm == "E":
                res["E_lost_A"] += a_ok and x.get("committed") != outs
                o = str(x.get("outcome"))
                res["E_outcomes"][o] = res["E_outcomes"].get(o, 0) + 1
                top = x.get("top") or {}
                res["E_restore_failures"] += (top.get("restored") is False) + sum(
                    f.get("restored") is False for f in (x.get("folds") or []) if isinstance(f, dict))
                if ext:
                    res["E_operators"].append({"task": r["key"], "operator": (x.get("selected") or {}).get("pretty"),
                                               "correct": x.get("committed") == outs})
    st["g1"] = res
    save(st)
    if res["E_ext_wrong"] or res["E_lost_A"] or res["E_restore_failures"]:
        block(st, "G1", json.dumps(res))
    st["stage"] = "submit"
    save(st)
    log(f"G1 PASSED (safety): {json.dumps(res)[:600]}")


def stage_submit(st):
    if os.path.exists(MARKER):
        st["stage"] = "score"
        save(st)
        return
    while True:
        rc, out = kag("competitions", "submissions", COMP)
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if rc == 0 and not any(re.search(r"\s" + today + r"\s", " " + line + " ") for line in out.splitlines()[2:]):
            break
        log(f"waiting for a free daily slot (rc={rc})")
        time.sleep(1800)
    out_dir = os.path.join(DEP, f"run_v{st['kernel_version']}")
    msg = (f"{TAG}: native CORA v23 + CORA-FHR failure-driven construction (G-grow, reversible install, adaptive LOO); "
           f"notebook {KERNEL} v{st['kernel_version']}; no neural model, not NVARC")
    rc, out = kag("competitions", "submit", COMP, "-k", KERNEL, "-v", str(st["kernel_version"]), "-f", "submission.json", "-m", msg,
                  timeout=1800)
    open(MARKER, "w").write(json.dumps({"rc": rc, "out": out[-300:], "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
    st["submit"] = {"rc": rc, "out": out[-300:], "message": msg, "outputs_dir": out_dir}
    save(st)
    log(f"SUBMIT rc={rc}: {out[-300:]}")
    if rc != 0:
        block(st, "SUBMIT", out[-300:])
    st["stage"] = "score"
    save(st)


def stage_score(st):
    t0 = time.time()
    while time.time() - t0 < 72 * 3600:
        rc, out = kag("competitions", "submissions", COMP)
        line = next((l for l in out.splitlines() if TAG in l), "") if rc == 0 else ""
        if line:
            st["submission_row"] = " ".join(line.split())
            save(st)
            if "COMPLETE" in line or "ERROR" in line:
                json.dump(st, open(os.path.join(DEP, "official_score.json"), "w"), indent=1)
                st["stage"] = "DONE"
                save(st)
                log(f"SCORED: {st['submission_row']}")
                return
        time.sleep(600)
    log("no score within 72 h; leaving state at score")


def main():
    os.makedirs(DEP, exist_ok=True)
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"stage": "emulation"}
    save(st)
    log(f"pipeline start at stage {st['stage']}")
    stages = {"emulation": stage_emulation, "dataset": stage_dataset, "kernel": stage_kernel, "run": stage_run,
              "outputs": stage_outputs, "g1": stage_g1, "submit": stage_submit, "score": stage_score}
    while st["stage"] in stages:
        stages[st["stage"]](st)
        st = json.load(open(STATE))
    log(f"pipeline end at stage {st['stage']}")


if __name__ == "__main__":
    main()
