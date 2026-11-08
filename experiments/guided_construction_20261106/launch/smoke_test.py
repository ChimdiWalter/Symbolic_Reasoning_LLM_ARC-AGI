"""Step 4 checks on Athe (source tasks only; no held task, no solution, no GO):

1. Smoke test: the candidate package (runs/kaggle/package_candidate.tar.gz) is unpacked into a scratch folder, a
   rehearsal GO (runs/REHEARSAL_GO, naming the package's protocol and freeze) is written there, and the kernel driver
   runs every set in rehearsal mode (GC_REHEARSAL=1: source stand-ins, 2 per benchmark) with one worker; then the
   checks of verify.py run on the returned rows (rehearsal mode).
2. Gate refusal check: in fresh copies of the package, (a) no GO: the held run, the checks and the scorer are
   refused; (b) a GO that names another protocol: refused; (c) rehearsal mode with a valid rehearsal GO but one
   frozen file changed: refused; (d) the scorer in rehearsal mode: refused. (a) and (b) run with the data root set
   to an empty folder, so that even a failed gate could not reach a task.
3. Scorer guard regression tests (launch/score_guard_test.py, PROTOCOL_AMENDMENT_1.md section 1): on copies of the
   smoke rows inside the unpacked package (rehearsal mode; no solution file reachable), a stale, copied, forged,
   invented or missing invariant receipt stops the scorer before the marker and before any solution function; a
   valid receipt passes the guard and reaches the marker, which refuses in rehearsal mode.
Writes checks/SMOKE_TEST.json, checks/GATE_REFUSAL.json and checks/SCORE_GUARD_TESTS.json in the study.

    python3 -s -B launch/smoke_test.py SCRATCH_DIR
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "experiments/guided_construction_20261106"
PY = sys.executable


SCRATCH_TOP = None


def scrub_file(path):
    """Paths under the scratch folder's top-level temporary folder are replaced in the written records."""
    import re
    with open(path, encoding="utf-8") as f:
        t = f.read()
    if SCRATCH_TOP:
        t = re.sub("/?" + re.escape(SCRATCH_TOP.lstrip("/")) + r'[^"\\ ]*', "<scratch path>", t)
    json.loads(t)
    with open(path, "w", encoding="utf-8") as f:
        f.write(t)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def unpack(dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    with tarfile.open(os.path.join(STUDY, "runs", "kaggle", "package_candidate.tar.gz"), "r:gz") as tf:
        tf.extractall(dst)
    return os.path.join(dst, REL)


def env_for(root, rehearsal, data=None):
    e = dict(os.environ, PYTHONHASHSEED="0", NG_PACKAGE="1", NG_REPO=root,
             NG_STUDY=os.path.join(root, "experiments", "natural_growth_20261105"),
             NG_DATA=data or os.path.join(root, "data", "prepared"), OG_REPO=root,
             OG_STUDY=os.path.join(root, "experiments", "object_growth_20261105"), NGB_REPO=root,
             NGB_STUDY=os.path.join(root, "experiments", "natural_growth_b_20261105"), GC_REPO=root,
             GC_STUDY=os.path.join(root, REL))
    e.pop("GC_REHEARSAL", None)
    if rehearsal:
        e["GC_REHEARSAL"] = "1"
    return e


def go_text(study, protocol_sha=None):
    return (f"protocol_sha256 {protocol_sha or sha(os.path.join(study, 'PROTOCOL.md'))}\n"
            f"freeze_sha256 {sha(os.path.join(study, 'FREEZE.json'))}\nrehearsal smoke test\n")


def athe(cmd, env, cwd):
    """Run this study's Athe copy of run.py (it carries verify.py and score.py) against the package roots."""
    p = subprocess.run([PY, "-s", "-B", os.path.join(STUDY, "run.py")] + cmd, env=env, cwd=cwd,
                       capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[-1500:]


def pkg(cmd, env, study):
    p = subprocess.run([PY, "-s", "-B", os.path.join(study, "run.py")] + cmd, env=env, cwd=study,
                       capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[-1500:]


def smoke(scratch):
    root = os.path.join(scratch, "smoke_pkg")
    study = unpack(root)
    os.makedirs(os.path.join(study, "runs"), exist_ok=True)
    with open(os.path.join(study, "runs", "REHEARSAL_GO"), "w", encoding="utf-8") as f:
        f.write(go_text(study))
    run_dir = os.path.join(study, "runs", "held_run")
    env = env_for(root, True)
    t0 = time.time()
    c0 = os.times()
    p = subprocess.run([PY, "-s", "-B", os.path.join(study, "launch", "kernel_run.py"), root, run_dir, "1", "3600",
                        "concept_arc", "mini_arc", "1d_arc", "arc2"], env=env, cwd=study, capture_output=True,
                       text=True)
    c1 = os.times()
    code, out = athe(["verify", run_dir], env, study)
    inv = json.load(open(os.path.join(run_dir, "INVARIANTS.json"))) if os.path.exists(
        os.path.join(run_dir, "INVARIANTS.json")) else None
    rows = []
    for s in ("concept_arc", "mini_arc", "1d_arc", "arc2"):
        d = os.path.join(run_dir, s)
        for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if fn.startswith("rows."):
                rows += [json.loads(x) for x in open(os.path.join(d, fn)) if x.strip()]
    errors = [[r["task"], k] for r in rows for k, v in r.get("arms", {}).items() if "error" in v]
    summary = [{"task": r["task"], "bench": r["bench"], "shared": r.get("shared"), "ref_fit": r["ref"]["fit"],
                "ref_stage": r["ref"]["stage"], "cpu_s": r["cpu_s"],
                "arms_fit": {k: v.get("fit") for k, v in r.get("arms", {}).items()},
                "capped": {k: sum(1 for h in v.get("holes", []) if h["capped"]) for k, v in r.get("arms", {}).items()}}
               for r in rows if "ref" in r]
    rec = {"package_sha256": sha(os.path.join(STUDY, "runs", "kaggle", "package_candidate.tar.gz")),
           "freeze_sha256": sha(os.path.join(STUDY, "FREEZE.json")), "protocol_sha256": sha(os.path.join(STUDY,
                                                                                                    "PROTOCOL.md")),
           "kernel_driver_return_code": p.returncode, "kernel_driver_output": p.stdout[-1500:] + p.stderr[-1500:],
           "kernel_run": json.load(open(os.path.join(run_dir, "kernel_run.json"))),
           "verify_return_code": code, "verify_output": out, "invariants": inv, "rows": len(rows),
           "arm_errors": errors, "tasks": summary, "wall_s": round(time.time() - t0, 1),
           "children_cpu_s": round((c1.children_user + c1.children_system) - (c0.children_user + c0.children_system), 1),
           "passed": p.returncode == 0 and code == 0 and bool(inv) and inv["verdict"] == "PASS" and not errors}
    with open(os.path.join(STUDY, "checks", "SMOKE_TEST.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, sort_keys=True, default=list)
    scrub_file(os.path.join(STUDY, "checks", "SMOKE_TEST.json"))
    print(json.dumps({"smoke_passed": rec["passed"], "rows": len(rows), "errors": len(errors),
                      "verdict": inv and inv["verdict"], "wall_s": rec["wall_s"]}))
    # scorer guard regression tests on copies of these rows
    g = subprocess.run([PY, "-s", "-B", os.path.join(STUDY, "launch", "score_guard_test.py"), run_dir], env=env,
                       cwd=study, capture_output=True, text=True)
    try:
        gres = json.loads(g.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        gres = {"passed": False, "output": (g.stdout + g.stderr)[-2000:]}
    gres.update(return_code=g.returncode, package_sha256=rec["package_sha256"], freeze_sha256=rec["freeze_sha256"])
    with open(os.path.join(STUDY, "checks", "SCORE_GUARD_TESTS.json"), "w", encoding="utf-8") as f:
        json.dump(gres, f, indent=1, sort_keys=True)
    scrub_file(os.path.join(STUDY, "checks", "SCORE_GUARD_TESTS.json"))
    print(json.dumps({"guard_tests_passed": gres.get("passed"),
                      "scorer_boundary": gres.get("scorer_boundary_passed"),
                      "verify_sentinels": gres.get("verify_sentinels_passed"),
                      "kernel_receipt_cases": gres.get("kernel_receipt_cases_passed"),
                      "donor_total_case": gres.get("donor_total_case_passed"),
                      "failed": sorted([k for k, v in (gres.get("verify_cases") or {}).items() if not v.get("ok")] +
                                       [k for k, v in (gres.get("kernel_cases") or {}).items() if not v.get("ok")])}))
    return rec["passed"] and bool(gres.get("passed"))


def refusals(scratch):
    out = {}
    empty = os.path.join(scratch, "empty_data")
    os.makedirs(empty, exist_ok=True)
    # (a) no GO, real mode, empty data root
    root = os.path.join(scratch, "refuse_a")
    study = unpack(root)
    env = env_for(root, False, data=empty)
    rd = os.path.join(study, "runs", "held_run")
    out["a_no_go_held"] = pkg(["held", rd, "1d_arc", "0/1"], env, study)
    out["a_no_go_verify"] = athe(["verify", rd], env, study)
    out["a_no_go_score"] = athe(["score", rd], env, study)
    # (b) a GO naming another protocol
    root = os.path.join(scratch, "refuse_b")
    study = unpack(root)
    os.makedirs(os.path.join(study, "runs"), exist_ok=True)
    with open(os.path.join(study, "runs", "GO"), "w", encoding="utf-8") as f:
        f.write(go_text(study, protocol_sha="0" * 64))
    env = env_for(root, False, data=empty)
    rd = os.path.join(study, "runs", "held_run")
    out["b_wrong_go_held"] = pkg(["held", rd, "concept_arc", "0/1"], env, study)
    # (c) rehearsal, valid rehearsal GO, one frozen file changed
    root = os.path.join(scratch, "refuse_c")
    study = unpack(root)
    os.makedirs(os.path.join(study, "runs"), exist_ok=True)
    with open(os.path.join(study, "runs", "REHEARSAL_GO"), "w", encoding="utf-8") as f:
        f.write(go_text(study))
    with open(os.path.join(study, "gcon", "engine.py"), "a", encoding="utf-8") as f:
        f.write("\n# changed\n")
    env = env_for(root, True)
    rd = os.path.join(study, "runs", "held_run")
    out["c_changed_file_held"] = pkg(["held", rd, "mini_arc", "0/1"], env, study)
    # (d) the scorer in rehearsal mode (valid rehearsal GO, unchanged files)
    root = os.path.join(scratch, "refuse_d")
    study = unpack(root)
    os.makedirs(os.path.join(study, "runs"), exist_ok=True)
    with open(os.path.join(study, "runs", "REHEARSAL_GO"), "w", encoding="utf-8") as f:
        f.write(go_text(study))
    os.makedirs(os.path.join(study, "runs", "held_run"), exist_ok=True)
    with open(os.path.join(study, "runs", "held_run", "INVARIANTS.json"), "w", encoding="utf-8") as f:
        json.dump({"verdict": "PASS"}, f)
    env = env_for(root, True)
    out["d_rehearsal_score"] = athe(["score", os.path.join(study, "runs", "held_run")], env, study)
    res = {k: {"return_code": v[0], "refused": v[0] != 0 and "GateRefused" in v[1], "output": v[1][-600:]}
           for k, v in out.items()}
    res["passed"] = all(v["refused"] for k, v in res.items() if isinstance(v, dict))
    res["package_sha256"] = sha(os.path.join(STUDY, "runs", "kaggle", "package_candidate.tar.gz"))
    with open(os.path.join(STUDY, "checks", "GATE_REFUSAL.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    scrub_file(os.path.join(STUDY, "checks", "GATE_REFUSAL.json"))
    print(json.dumps({k: (v["refused"] if isinstance(v, dict) else v) for k, v in res.items()}))
    return res["passed"]


if __name__ == "__main__":
    scratch = os.path.abspath(sys.argv[1])
    parts = scratch.split(os.sep)
    SCRATCH_TOP = os.sep.join(parts[:3]) if len(parts) > 3 else scratch
    what = sys.argv[2] if len(sys.argv) > 2 else "both"
    if what in ("both", "refusals"):
        refusals(scratch)
    if what in ("both", "smoke"):
        smoke(scratch)
