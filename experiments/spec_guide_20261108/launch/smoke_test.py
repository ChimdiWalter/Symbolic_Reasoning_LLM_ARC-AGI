"""Smoke test and gate refusal check of the candidate package (rehearsal mode only: validation families on
development-pool grids and a rehearsal GO; nothing held is generated or opened).

    python3 -s -B launch/smoke_test.py SCRATCH_DIR

1. Smoke: unpack runs/kaggle/package_candidate.tar.gz (the frozen files with their dependencies), write
   runs/REHEARSAL_GO, run `held all` with SG_REHEARSAL=1 (4 tasks per edit type, 300 s of generation; it generates,
   runs every arm and seals), then `score` in rehearsal.
2. Refusals: in fresh unpacked copies: (a) no GO (held mode): `held gen` refused; (b) a GO naming another FREEZE.json;
   (c) a GO whose nonce is not 64 hex; (d) one frozen file changed; (e) `held gen` again after tasks exist;
   (f) `score` a second time (the marker). (a) to (d) run with an empty held pool path so even a failed gate could not
   reach a held grid: they stop at the gate before any pool is read.
Writes checks/SMOKE_TEST.json and checks/GATE_REFUSAL.json.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "experiments/spec_guide_20261108"
PY = sys.executable
TOP = None


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def unpack(dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    with tarfile.open(os.path.join(STUDY, "runs", "kaggle", "package_candidate.tar.gz"), "r:gz") as tf:
        tf.extractall(dst)
    return os.path.join(dst, REL)


def env_for(root, rehearsal):
    e = dict(os.environ, PYTHONHASHSEED="0", NG_PACKAGE="1", NG_REPO=root,
             NG_STUDY=os.path.join(root, "experiments", "natural_growth_20261105"),
             NG_DATA=os.path.join(root, "data", "prepared"), OG_REPO=root,
             OG_STUDY=os.path.join(root, "experiments", "object_growth_20261105"), GC_REPO=root,
             GC_STUDY=os.path.join(root, "experiments", "guided_construction_20261106"), SG_REPO=root,
             SG_STUDY=os.path.join(root, REL), SG_PACKAGE="1", CUDA_VISIBLE_DEVICES="")
    e.pop("SG_REHEARSAL", None)
    if rehearsal:
        e["SG_REHEARSAL"] = "1"
    return e


def go_text(study, freeze_sha=None, nonce="0123456789abcdef" * 4):
    return ("GO\nstudy: spec_guide_20261108\nfreeze_commit: " + "0" * 40 + "\nfreeze_json_sha256: " +
            (freeze_sha or sha(os.path.join(study, "FREEZE.json"))) + "\npre_run_review: rehearsal\nnonce: " +
            nonce + "\n")


def run(study, args, env):
    p = subprocess.run([PY, "-s", "-B", os.path.join(study, "run.py")] + args, env=env, cwd=study,
                       capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[-1500:]


def scrub(path):
    t = open(path).read()
    if TOP:
        t = re.sub("/?" + re.escape(TOP.lstrip("/")) + r'[^"\\ ]*', "<scratch path>", t)
    json.loads(t)
    open(path, "w").write(t)


def smoke(scratch):
    root = os.path.join(scratch, "smoke")
    study = unpack(root)
    os.makedirs(os.path.join(study, "runs"), exist_ok=True)
    open(os.path.join(study, "runs", "REHEARSAL_GO"), "w").write(go_text(study))
    env = env_for(root, True)
    env["SG_REHEARSAL_LIMITS"] = "4,300"
    t0 = time.time()
    p = subprocess.run([PY, "-s", "-B", os.path.join(study, "run.py"), "held", "all"], env=env, cwd=study,
                       capture_output=True, text=True)
    seal = (0, "sealed inside held all")
    score = run(study, ["score"], env)
    again = run(study, ["score"], env)
    out = os.path.join(study, "runs", "rehearsal_held")
    res = json.load(open(os.path.join(out, "RESULTS.json"))) if os.path.exists(os.path.join(out, "RESULTS.json")) \
        else None
    rec = {"package_sha256": sha(os.path.join(STUDY, "runs", "kaggle", "package_candidate.tar.gz")),
           "freeze_sha256": sha(os.path.join(STUDY, "FREEZE.json")),
           "held_all": {"return_code": p.returncode, "output": (p.stdout + p.stderr)[-1500:]},
           "run_status": open(os.path.join(out, "run.status")).read() if os.path.exists(
               os.path.join(out, "run.status")) else None,
           "gen_records": [json.load(open(os.path.join(out, f))) for f in sorted(os.listdir(out))
                           if f.startswith("GEN_RECORD")] if os.path.isdir(out) else [],
           "seal": {"return_code": seal[0], "output": seal[1][-600:]},
           "score": {"return_code": score[0], "output": score[1][-800:]},
           "second_score": {"return_code": again[0], "refused": again[0] != 0 and "GateRefused" in again[1],
                            "output": again[1][-400:]},
           "results": None if res is None else {k: res[k] for k in ("n_tasks", "table", "primary", "secondaries",
                                                                     "rehearsal")},
           "wall_s": round(time.time() - t0, 1)}
    rec["passed"] = (p.returncode == 0 and seal[0] == 0 and score[0] == 0 and res is not None and
                     res["n_tasks"] > 0 and rec["second_score"]["refused"])
    path = os.path.join(STUDY, "checks", "SMOKE_TEST.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(rec, open(path, "w"), indent=1, sort_keys=True, default=list)
    scrub(path)
    print(json.dumps({"smoke_passed": rec["passed"], "tasks": res and res["n_tasks"], "wall_s": rec["wall_s"]}))


def refusals(scratch):
    out = {}
    cases = [("a_no_go", None, None, False), ("b_other_freeze", "f" * 64, None, False),
             ("c_bad_nonce", None, "xyz", False), ("d_changed_file", None, None, True)]
    for name, fz, nonce, change in cases:
        root = os.path.join(scratch, "refuse_" + name)
        study = unpack(root)
        os.makedirs(os.path.join(study, "runs"), exist_ok=True)
        if name != "a_no_go":
            open(os.path.join(study, "runs", "GO"), "w").write(go_text(study, fz, nonce or "0123456789abcdef" * 4))
        if change:
            open(os.path.join(study, "sgd", "net.py"), "a").write("\n# changed\n")
        env = env_for(root, False)
        env["SG_STUDY"] = study
        out[name] = run(study, ["held", "gen", "4", "60", "0/1"], env)
    # (e) generation again in rehearsal after tasks exist, (f) the rehearsal scorer twice: from the smoke run
    smoke_study = os.path.join(scratch, "smoke", REL)
    env = env_for(os.path.join(scratch, "smoke"), True)
    out["e_generate_again"] = run(smoke_study, ["held", "gen", "4", "60", "0/1"], env)
    out["f_score_again"] = run(smoke_study, ["score"], env)
    res = {k: {"return_code": v[0], "refused": v[0] != 0 and "GateRefused" in v[1], "output": v[1][-500:]}
           for k, v in out.items()}
    res["passed"] = all(v["refused"] for v in res.values() if isinstance(v, dict))
    res["package_sha256"] = sha(os.path.join(STUDY, "runs", "kaggle", "package_candidate.tar.gz"))
    path = os.path.join(STUDY, "checks", "GATE_REFUSAL.json")
    json.dump(res, open(path, "w"), indent=1, sort_keys=True)
    scrub(path)
    print(json.dumps({k: (v["refused"] if isinstance(v, dict) else v) for k, v in res.items()}))


if __name__ == "__main__":
    scratch = os.path.abspath(sys.argv[1])
    parts = scratch.split(os.sep)
    TOP = os.sep.join(parts[:3]) if len(parts) > 3 else scratch
    smoke(scratch)
    refusals(scratch)
