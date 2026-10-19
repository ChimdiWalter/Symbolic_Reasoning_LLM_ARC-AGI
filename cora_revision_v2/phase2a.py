"""Phase 2a: the one authorized bounded development experiment (records/CORA_REASONING_V2_PHASE2_PROTOCOL_20261019.md).

  python -m cora_revision_v2.phase2a build       # cohort bundle under opaque keys; no answer is read
  python -m cora_revision_v2.phase2a preflight   # every frozen precondition; writes freeze.json
  python -m cora_revision_v2.phase2a run         # arms A, B, V: at most 2 workers, nice 10, CPU caps, 6 h wall cap
  python -m cora_revision_v2.phase2a evaluate    # only after every arm's rows are frozen: the first read of answers

**Cohort:** the first 40 eligible IDs from the isolated Step B check
(`outputs/cora_revision_v2/eligibility/eligible_ids_20261019.json`, PASS, 44 eligible).

**Arms**, exactly as frozen:
- A: frozen native v23 object branch, frozen library and verbs, 90 s CPU budget (`cora_fhr.measure.object_run`,
  unchanged).
- B: the same with budget × f_B. f_B = 1.053, from the engineering runs: native A mean CPU 297.9 s over 118 tasks;
  v2 mean CPU 15.8 s over 118 tasks.
- V: CORA-v2 reason + diagnose + decide (`cora_revision_v2.run_v2.one`, families "grow", the frozen design),
  600 s CPU.

**Blindness:**
- Every arm reads only the bundle, which holds training pairs and test inputs under opaque keys.
- The key map lives in a separate evaluator directory that no arm is given.
- The training solutions are opened only by `evaluate`, after the coverage of A, B and V is complete or the wall cap
  has passed.

**GO** (all of):
- complete coverage in A, B and V;
- valid hashes;
- zero certified-wrong V predictions;
- at least 2 tasks where V has a correct attempt (CERTIFIED or EXPLORATORY tier) and neither A nor B has a correct
  committed answer.

Certified and exploratory gains are reported separately.
"""
import hashlib
import hmac
import json
import os
import secrets
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_revision_v2", "phase2a")
EVAL_DIR = os.path.join(HERE, "outputs", "cora_revision_v2", "phase2a_evaluator")
ELIG = os.path.join(HERE, "outputs", "cora_revision_v2", "eligibility", "eligible_ids_20261019.json")
ELIG_SHA = "8637ac655fc71c01"                                          # prefix of the recorded file sha256
PROTOCOL = os.path.join(HERE, "records", "CORA_REASONING_V2_PHASE2_PROTOCOL_20261019.md")
N_COHORT, MIN_COHORT = 40, 25
F_B = 1.053
CPU_V, WORKERS, WALL_CAP_S, NICE = 600, 2, 6 * 3600, 10
ARMS = ("V", "A", "B")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _rows(arm):
    p = os.path.join(OUT, f"rows_{arm}.jsonl")
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


# ---------------------------------------------------------------- build (no answers)
def build():
    from cora_pilot import bundle as B
    el = json.load(open(ELIG))
    assert _sha(ELIG).startswith(ELIG_SHA) and el["attestation"]["status"] == "PASS"
    ids = el["eligible_ids"][:N_COHORT]
    assert len(ids) >= MIN_COHORT
    ch = B.load_challenges()                                            # sha-pinned; holds no test outputs
    key_secret = secrets.token_hex(16)
    keys = {"p2a_" + hmac.new(key_secret.encode(), t.encode(), hashlib.sha256).hexdigest()[:12]: t for t in ids}
    assert len(keys) == len(ids)
    tasks = {}
    for k in sorted(keys):
        t = ch[keys[k]]
        tasks[k] = {"train": [{"input": p["input"], "output": p["output"]} for p in t["train"]],
                    "test": [{"input": p["input"]} for p in t["test"]]}
        assert all(set(p) == {"input"} for p in tasks[k]["test"])
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(EVAL_DIR, exist_ok=True)
    bpath = os.path.join(OUT, "bundle.json")
    json.dump({"format": "cora-v2-phase2a-bundle/1", "tasks": tasks}, open(bpath, "w"))
    vb = {k: {"train": [(p["input"], p["output"]) for p in t["train"]], "test_inputs": [p["input"] for p in t["test"]]}
          for k, t in tasks.items()}
    json.dump(vb, open(os.path.join(OUT, "bundle_v.json"), "w"))
    json.dump({"bundle_sha256": _sha(bpath), "key_secret": key_secret, "keys": keys, "cohort_ids_in_order": ids,
               "eligibility_sha256": _sha(ELIG)}, open(os.path.join(EVAL_DIR, "keymap.json"), "w"), indent=1)
    print(json.dumps({"tasks": len(tasks), "bundle_sha256": _sha(bpath), "bundle_v_sha256": _sha(os.path.join(OUT, "bundle_v.json"))}))


# ---------------------------------------------------------------- one native arm (child process)
def native_one(arm, key, out_path):
    import numpy as np
    from cora_funnel import run as FR
    FR.cpu_clock()
    from cora_fhr import measure as M
    from cora_pilot import native as N
    t = json.load(open(os.path.join(OUT, "bundle.json")))["tasks"][key]
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in t["train"]]
    tests = [np.asarray(p["input"], dtype=int) for p in t["test"]]
    d = N.prepare_object_dir(os.path.join(OUT, "engines", key, arm))
    rec, _prog = M.object_run(key, train, tests, d, budget_s=M.BUDGET_S * (F_B if arm == "B" else 1.0))
    json.dump({"key": key, "arm": arm, "committed": rec["predictions"] if rec["accepted"] else None,
               "certified": rec["accepted"], "run": rec, "f_B": F_B if arm == "B" else 1.0,
               "bundle_sha256": _sha(os.path.join(OUT, "bundle.json"))}, open(out_path, "w"))


# ---------------------------------------------------------------- preflight
def preflight(skip_slow=False):
    import glob
    checks = {}
    el = json.load(open(ELIG))
    km = json.load(open(os.path.join(EVAL_DIR, "keymap.json")))
    checks["eligibility_pass"] = el["attestation"]["status"] == "PASS" and _sha(ELIG).startswith(ELIG_SHA)
    checks["cohort_is_first_40_eligible"] = km["cohort_ids_in_order"] == el["eligible_ids"][:N_COHORT]
    checks["bundle_hash_matches_keymap"] = _sha(os.path.join(OUT, "bundle.json")) == km["bundle_sha256"]
    b = json.load(open(os.path.join(OUT, "bundle.json")))["tasks"]
    checks["bundle_has_no_test_outputs"] = all(set(p) == {"input"} for t in b.values() for p in t["test"])
    checks["bundle_keys_are_opaque"] = all(k.startswith("p2a_") and km["keys"][k] not in json.dumps(b) for k in b)
    checks["no_rows_yet"] = not glob.glob(os.path.join(OUT, "rows_*.jsonl"))
    ps = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "args"], capture_output=True, text=True).stdout
    checks["no_engineering_jobs_running"] = not any(("run_v2" in l or "eng_sel_run" in l or "eng_run.sh" in l)
                                                     for l in ps.splitlines() if "preflight" not in l)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "cora_revision_v2", "cora_fhr", "cora_funnel", "cora_pilot",
                            "harness", "geocat_arc", "tests"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    checks["code_committed_and_clean"] = bool(head) and dirty == ""
    checks["protocol_present"] = os.path.exists(PROTOCOL)
    if not skip_slow:
        t = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_fhr.py"], cwd=HERE, capture_output=True, text=True)
        checks["tests_pass"] = t.returncode == 0
        checks["tests_summary"] = t.stdout.strip().splitlines()[-1] if t.stdout.strip() else t.stderr[-200:]
        checks["v_regression_identical"] = _v_regression()
    ok = all(v for k, v in checks.items() if k != "tests_summary")
    freeze = {"protocol_sha256": _sha(PROTOCOL), "commit": head, "f_B": F_B, "cpu_V": CPU_V, "workers": WORKERS,
              "wall_cap_s": WALL_CAP_S, "nice": NICE, "bundle_sha256": km["bundle_sha256"],
              "bundle_v_sha256": _sha(os.path.join(OUT, "bundle_v.json")), "eligibility_sha256": _sha(ELIG),
              "code_sha256": {p: _sha(os.path.join(HERE, p)) for p in (
                  "cora_revision_v2/phase2a.py", "cora_revision_v2/run_v2.py", "cora_revision_v2/scene_reasoner.py",
                  "cora_revision_v2/diagnosis.py", "cora_revision_v2/selection.py", "cora_fhr/measure.py", "cora_fhr/ggrow.py",
                  "cora_fhr/oracle_expressibility.py")},
              "checks": checks, "PREFLIGHT": "PASS" if ok else "FAIL",
              "frozen_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(freeze, open(os.path.join(OUT, "freeze.json"), "w"), indent=1)
    print(json.dumps({"PREFLIGHT": freeze["PREFLIGHT"], "checks": checks}, indent=1))
    return ok


def _v_regression():
    """V on two engineering tasks with the frozen code must reproduce the recorded engineering rows exactly."""
    import tempfile
    from cora_revision_v2 import run_v2 as R
    eng = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(HERE, "outputs", "cora_revision_v2", "rows_standin58_eng.jsonl"))}
    bundle = R.blind_bundle("standin58")
    ok = True
    with tempfile.TemporaryDirectory() as td:
        bp = os.path.join(td, "b.json")
        keys = ("00dbd492", "045e512c")
        json.dump({k: bundle[k] for k in keys}, open(bp, "w"))
        for k in keys:
            op = os.path.join(td, k + ".json")
            subprocess.run([sys.executable, "-m", "cora_revision_v2.run_v2", "--one", bp, k, op, "grow"], cwd=HERE, check=True)
            r = json.load(open(op))
            ok = ok and all(r[f] == eng[k][f] for f in ("diagnosis", "tier", "attempts", "folds", "fold_detail"))
    return ok


# ---------------------------------------------------------------- run
def run():
    fz = json.load(open(os.path.join(OUT, "freeze.json")))
    assert fz["PREFLIGHT"] == "PASS", "preflight has not passed"
    assert _sha(os.path.join(OUT, "bundle.json")) == fz["bundle_sha256"]
    keys = sorted(json.load(open(os.path.join(OUT, "bundle.json")))["tasks"])
    done = {(arm, r["key"]) for arm in ARMS for r in _rows(arm)}
    todo = [(arm, k) for k in keys for arm in ARMS if (arm, k) not in done]
    tmp = os.path.join(OUT, "tmp")
    os.makedirs(tmp, exist_ok=True)
    start_p = os.path.join(OUT, "start_time.txt")
    if not os.path.exists(start_p):
        open(start_p, "w").write(str(time.time()))
    t_start = float(open(start_p).read())

    def limit(cpu):
        def f():
            import resource
            os.setsid()
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 10))
            os.nice(NICE)
        return f
    running = {}
    while todo or running:
        over = time.time() - t_start > WALL_CAP_S
        while todo and len(running) < WORKERS and not over:
            arm, k = todo.pop(0)
            op = os.path.join(tmp, f"{arm}_{k}.json")
            ep = open(os.path.join(tmp, f"{arm}_{k}.err"), "w")
            if arm == "V":
                cmd, cpu = [sys.executable, "-m", "cora_revision_v2.run_v2", "--one", os.path.join(OUT, "bundle_v.json"), k, op, "grow"], CPU_V
            else:
                cmd, cpu = [sys.executable, "-m", "cora_revision_v2.phase2a", "native", arm, k, op], 900
            p = subprocess.Popen(cmd, cwd=HERE, preexec_fn=limit(cpu), stdout=subprocess.DEVNULL, stderr=ep)
            ep.close()
            running[(arm, k)] = (p, op, time.time())
        for (arm, k), (p, op, ts) in list(running.items()):
            if over and p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            if p.poll() is None:
                continue
            if p.returncode == 0 and os.path.exists(op):
                row = json.load(open(op))
            else:
                row = {"key": k, "arm": arm, "error": "WALL_CAP" if over else ("CPU_LIMIT" if p.returncode in (-24, -9) else "ERROR"),
                       "returncode": p.returncode, "certified": False, "committed": None, "tier": "NONE", "attempts": None}
            row["wall_s"] = round(time.time() - ts, 1)
            with open(os.path.join(OUT, f"rows_{arm}.jsonl"), "a") as fh:
                fh.write(json.dumps(row) + "\n")
            del running[(arm, k)]
            print(arm, k, row.get("tier", row.get("certified")), row["wall_s"], flush=True)
        if over and not running:
            break
        time.sleep(2)
    cov = {arm: len({r["key"] for r in _rows(arm) if r.get("error") not in ("ERROR", "WALL_CAP")}) for arm in ARMS}
    print(json.dumps({"coverage": cov, "of": len(keys), "wall_h": round((time.time() - t_start) / 3600, 2)}))


# ---------------------------------------------------------------- evaluate (first read of answers)
def evaluate():
    from cora_pilot import bundle as B
    from cora_pilot import evaluator as EV
    fz = json.load(open(os.path.join(OUT, "freeze.json")))
    km = json.load(open(os.path.join(EVAL_DIR, "keymap.json")))
    keys = sorted(km["keys"])
    rows = {arm: {r["key"]: r for r in _rows(arm)} for arm in ARMS}
    # a run that reached its declared CPU limit is complete (it abstains, as native's own hard cap does);
    # a crash or the wall cap is not
    coverage = {arm: sum(k in rows[arm] and rows[arm][k].get("error") not in ("ERROR", "WALL_CAP") for k in keys)
                for arm in ARMS}
    cpu_limited = {arm: sum(rows[arm].get(k, {}).get("error") == "CPU_LIMIT" for k in keys) for arm in ARMS}
    hashes_ok = (_sha(os.path.join(OUT, "bundle.json")) == fz["bundle_sha256"] == km["bundle_sha256"] and
                 _sha(os.path.join(OUT, "bundle_v.json")) == fz["bundle_v_sha256"] and
                 all(r.get("bundle_sha256") == fz["bundle_sha256"] for arm in ("A", "B") for r in rows[arm].values()
                     if not r.get("error")))
    sol = EV.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)
    per = {}
    for k in keys:
        truth = sol[km["keys"][k]]

        def right(preds):
            return isinstance(preds, list) and len(preds) == len(truth) and all(p == o for p, o in zip(preds, truth))
        a, b, v = rows["A"].get(k, {}), rows["B"].get(k, {}), rows["V"].get(k, {})
        att = v.get("attempts")
        v_either = bool(att) and len(att) == len(truth) and all(any(x == o for x in at) for at, o in zip(att, truth))
        per[k] = {"A_correct": right(a.get("committed")), "B_correct": right(b.get("committed")),
                  "A_certified": bool(a.get("certified")), "B_certified": bool(b.get("certified")),
                  "V_tier": v.get("tier"), "V_diagnosis": v.get("diagnosis"), "V_correct_either": v_either}
    new_cert = [k for k, p in per.items() if p["V_tier"] == "CERTIFIED" and p["V_correct_either"] and not (p["A_correct"] or p["B_correct"])]
    new_expl = [k for k, p in per.items() if p["V_tier"] == "EXPLORATORY" and p["V_correct_either"] and not (p["A_correct"] or p["B_correct"])]
    cert_wrong = [k for k, p in per.items() if p["V_tier"] == "CERTIFIED" and not p["V_correct_either"]]
    res = {"label": "PHASE 2a: development evaluation on reused public training tasks (Step B-eligible; not a blind "
                    "prospective test, not unseen-task evidence)",
           "n": len(keys), "coverage": coverage, "cpu_limited_rows": cpu_limited, "hashes_ok": hashes_ok,
           "A_certified_correct": sum(p["A_correct"] for p in per.values()),
           "A_certified_wrong": sum(p["A_certified"] and not p["A_correct"] for p in per.values()),
           "B_certified_correct": sum(p["B_correct"] for p in per.values()),
           "B_certified_wrong": sum(p["B_certified"] and not p["B_correct"] for p in per.values()),
           "V_tiers": {t: sum(p["V_tier"] == t for p in per.values()) for t in ("CERTIFIED", "EXPLORATORY", "DISCOURAGED", "NONE")},
           "V_certified_correct": sum(p["V_tier"] == "CERTIFIED" and p["V_correct_either"] for p in per.values()),
           "V_certified_wrong": len(cert_wrong),
           "V_exploratory_correct": sum(p["V_tier"] == "EXPLORATORY" and p["V_correct_either"] for p in per.values()),
           "V_exploratory_wrong": sum(p["V_tier"] == "EXPLORATORY" and not p["V_correct_either"] for p in per.values()),
           "V_discouraged_correct": sum(p["V_tier"] == "DISCOURAGED" and p["V_correct_either"] for p in per.values()),
           "new_correct_certified": new_cert, "new_correct_exploratory": new_expl,
           "solved_by_A_or_B_not_by_V": [k for k, p in per.items() if (p["A_correct"] or p["B_correct"]) and not p["V_correct_either"]],
           "per_task": per}
    go = (all(c == len(keys) for c in coverage.values()) and hashes_ok and not cert_wrong and len(new_cert) + len(new_expl) >= 2)
    res["GO"] = "GO" if go else "NO-GO"
    res["go_checks"] = {"complete_coverage": all(c == len(keys) for c in coverage.values()), "hashes_ok": hashes_ok,
                        "zero_certified_wrong_V": not cert_wrong, "at_least_2_new_correct_V": len(new_cert) + len(new_expl) >= 2}
    json.dump(res, open(os.path.join(EVAL_DIR, "phase2a_eval.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "per_task"}, indent=1))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        raise SystemExit(__doc__)
    cmd = argv[0]
    if cmd == "build":
        build()
    elif cmd == "preflight":
        raise SystemExit(0 if preflight() else 1)
    elif cmd == "run":
        run()
    elif cmd == "evaluate":
        evaluate()
    elif cmd == "native":
        native_one(argv[1], argv[2], argv[3])
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
