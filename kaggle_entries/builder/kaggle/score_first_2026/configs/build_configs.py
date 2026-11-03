#!/usr/bin/env python3
"""Build the exact Kaggle notebook folders for configurations A and B and the A/B rehearsal (never pushes).

  python3 build_configs.py [--cast-manifest PATH] [--kernels DIR] [--only A,B,AB] [--test-overrides JSON]

The folders:
- A, `sf-ttt-cfgA-arc-agi-2`: the reviewed neural TTT entry, built by the unchanged `tools/build_kernel.py` with the
  reviewed arguments. Its notebook is byte-identical to the reviewed build (sha256 `0bed9cfe...`).
- B, `sf-ttt-cfgB-cast-arc-agi-2`: A's two cells unchanged, plus two fail-safe cells. The first, before A's driver,
  writes the CAST package and the B side code, then starts the CAST side process on CPU. The second, after A's
  driver, merges CAST answers into attempt 2 under the frozen tier.
- AB, `sf-ttt-rehearsal-AB-eval120`: B's notebook on the 120 public evaluation challenges (the submit path with
  `SF_REHEARSE_ON=evaluation` and the 5.75 h deadline of the reviewed rehearsal). One neural pass writes both
  `submission_A.json` (configuration A's file) and `submission_B.json`.
- O, `cora-cast-only-arc-agi-2`: the CORA-only CPU entry. CAST alone (no neural model, no GPU): attempt 1 is CAST's
  answer where it gives one, otherwise a copy of the test input; attempt 2 is that copy. ORH,
  `cora-cast-only-rehearsal-eval120`, is the same notebook on the 120 public evaluation challenges.

The CAST package is taken from its MANIFEST.json (package name, version, entry point, file hashes), so a new
package version needs only a new `--cast-manifest`. Every embedded package file is checked against that manifest.
Build manifests (file hashes, environment, sources) are written into each folder; `configs/MANIFEST.json` collects
them (see verify_builds.py).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))                 # kaggle/score_first_2026/configs
SF_HOME = os.path.dirname(HERE)                                   # kaggle/score_first_2026
REPO = os.path.dirname(os.path.dirname(SF_HOME))
KERNELS = os.path.join(REPO, "outputs", "score_first", "kernels")
DEFAULT_CAST_MANIFEST = os.path.join(REPO, "experiments", "cora_cast_20261026", "kaggle_pkg", "MANIFEST.json")
V2_MANIFEST = os.path.join(REPO, "experiments", "cora_cast_20261026", "kaggle_pkg", "cast_selective_v2", "MANIFEST.json")
C4_COPY = os.path.join(HERE, "h", "c4_frozen")
C4_NOTEBOOK_SHA = "b571233a9afae5a6374cd569d448285e3f6006bddd3e5e9d013f5f8dcb2409bc"
# Constructor packages, in priority order. mode "evidence": cast_selective_v2's evaluate() runs next to the neural pass
# and its own insert_attempt2(policy) decides at the end; mode "grids": a package returning one grid or None per test
# input (cast_v1, or a reviewed R29 package later), under the generic tier rule.
B_PACKAGES = [{"manifest": V2_MANIFEST, "entry": "evaluate", "mode": "evidence", "policy": "tier0"}]
H_PACKAGES = [{"manifest": V2_MANIFEST, "entry": "evaluate", "mode": "evidence", "policy": "tier1:B3"}]
SFB_FILES = ["sfb/__init__.py", "sfb/cast_side.py", "sfb/merge.py"]

# The reviewed configuration (SUBMISSION_READY draft, section 1; identical to the built sf-ttt-arc-agi-2).
NEURAL_ENV = [("SF_TTT_STEPS", "48"), ("SF_TTT_RANK", "64"), ("SF_TTT_ALPHA", "64"), ("SF_TTT_LR", "1e-4"),
              ("SF_TTT_MAX_TOKENS", "8192"), ("SF_TTT_FRAC", "0.7"), ("SF_N_GEN", "8"), ("SF_N_SCORE", "8"),
              ("SF_METHOD", "score"), ("SF_TASK_CAP_S", "900")]
SUBMIT_ENV = NEURAL_ENV + [("SF_DEADLINE_S", "41400"), ("SF_COMMIT_TASKS", "8")]
REHEARSAL_ENV = NEURAL_ENV + [("SF_REHEARSE_ON", "evaluation"), ("SF_DEADLINE_S", "20700")]

BUILDS = {
    "A": {"slug": "sf-ttt-cfga-arc-agi-2", "title": "SF TTT cfga ARC-AGI-2", "env": SUBMIT_ENV, "cast": False},
    "B": {"slug": "sf-ttt-cfgb-cast-arc-agi-2", "title": "SF TTT cfgb CAST ARC-AGI-2", "env": SUBMIT_ENV,
          "cast": True, "cast_total_s": "10800", "packages": B_PACKAGES},
    "AB": {"slug": "sf-ttt-rehearsal-ab-eval120", "title": "SF TTT rehearsal ab eval120", "env": REHEARSAL_ENV,
           "cast": True, "cast_total_s": "5400", "packages": B_PACKAGES},
}
# Entry H: the frozen C4 notebook, byte for byte, with the two CORA cells around its guard cell.
H_BUILDS = {
    "H": {"slug": "sf-h-c4-cast-arc-agi-2", "title": "SF H C4 CAST ARC-AGI-2", "rehearse": False,
          "cast_total_s": "10800", "packages": H_PACKAGES},
    "HRH": {"slug": "sf-h-rehearsal-eval120", "title": "SF H rehearsal eval120", "rehearse": True,
            "cast_total_s": "10800", "packages": H_PACKAGES},
}
B_LAUNCH = r'''
# CORA side processes (configurations B and H), part 1 of 2: start one CAST side process per constructor package on
# CPU, next to the neural run below. Fail-safe: any failure in this cell only means that the neural output is submitted.
import hashlib, json, os, signal, subprocess, sys, threading, time
B_ENV = __B_ENV__
B_PACKAGES = __B_PACKAGES__
for _k, _v in B_ENV.items():
    os.environ[_k] = _v
CAST_B = {"procs": [], "packages": [], "error": None, "deadline": None, "t0": time.time(), "ch_path": None}
try:
    _files = json.loads(__B_FILES__)
    _sha = __B_SHA__
    for _name, _text in _files.items():
        if hashlib.sha256(_text.encode("utf-8")).hexdigest() != _sha[_name]:
            raise RuntimeError("embedded file hash mismatch: " + _name)
        _p = os.path.join(CODE_DIR, _name)
        os.makedirs(os.path.dirname(_p), exist_ok=True)
        with open(_p, "w", encoding="utf-8") as _f:
            _f.write(_text)
    _kroot = os.environ.get("SF_KAGGLE_ROOT", "/kaggle")
    _comp = None
    for _d in (_kroot + "/input/competitions/arc-prize-2026-arc-agi-2", _kroot + "/input/arc-prize-2026-arc-agi-2"):
        if os.path.isdir(_d):
            _comp = _d
            break
    if _comp is None:
        import glob
        _comp = os.path.dirname(glob.glob(_kroot + "/input/**/arc-agi_test_challenges.json", recursive=True)[0])
    _ids = ""
    if os.environ.get("SF_REHEARSE_ON") == "evaluation":
        _ch_path = os.path.join(_comp, "arc-agi_evaluation_challenges.json")
    else:
        _ch_path = os.path.join(_comp, "arc-agi_test_challenges.json")
        with open(_ch_path) as _f:
            _test = json.load(_f)
        try:
            with open(os.path.join(_comp, "arc-agi_training_challenges.json")) as _f:
                _train_ids = set(json.load(_f))
        except (OSError, ValueError):
            _train_ids = set()
        if _test and set(_test) <= _train_ids:      # the public placeholder: the neural driver's commit subset
            _ids = ",".join(sorted(_test)[:int(os.environ.get("SF_COMMIT_TASKS", "8"))])
    CAST_B["ch_path"] = _ch_path
    _budget = min(float(os.environ["SF_CAST_TOTAL_S"]),
                  float(os.environ.get("SF_DEADLINE_S", str(11.5 * 3600))) - float(os.environ["SF_CAST_END_RESERVE_S"]))
    CAST_B["deadline"] = time.time() + max(0.0, _budget)
    _env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", PYTHONHASHSEED="0", PYTHONUNBUFFERED="1")

    def _cast_watchdog(p, end):
        while p.poll() is None and time.time() < end:
            time.sleep(5)
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
    for _i, _pk in enumerate(B_PACKAGES):
        _out = _kroot + "/working/cora_side/%d_%s" % (_i, _pk["name"])
        os.makedirs(_out, exist_ok=True)
        _cmd = [sys.executable, "-m", "sfb.cast_side", "--challenges", _ch_path, "--out", _out,
                "--package", _pk["name"], "--entry", _pk["entry"], "--mode", _pk["mode"],
                "--deadline", str(CAST_B["deadline"]), "--cpu-s", _pk["cpu_s"], "--wall-s", _pk["wall_s"],
                "--grace-s", os.environ["SF_CAST_GRACE_S"], "--nice", os.environ["SF_CAST_NICE"]]
        if _ids:
            _cmd += ["--task-ids", _ids]
        _log = open(_out + ".log", "w")
        _proc = subprocess.Popen(_cmd, cwd=CODE_DIR, env=_env, stdout=_log, stderr=_log, start_new_session=True)
        CAST_B["procs"].append(_proc)
        CAST_B["packages"].append({"name": _pk["name"], "mode": _pk["mode"], "policy": _pk["policy"], "dir": _out})
        threading.Thread(target=_cast_watchdog, args=(_proc, CAST_B["deadline"] + 60), daemon=True).start()
        print("CORA side process started:", _pk["name"], _pk["version"], _pk["mode"], _pk["policy"],
              "budget_s", round(_budget), "tasks", _ids or "all", flush=True)
except BaseException as _e:
    CAST_B["error"] = repr(_e)
    print("CORA not started; the neural output will be submitted:", repr(_e), flush=True)
'''

B_MERGE = r'''
# CORA side processes, part 2 of 2: CORA may change attempt 2 under each package's frozen policy (sfb/merge.py).
# Fail-safe: if anything in this cell fails, submission.json stays the neural file.
import json, os, shutil, signal, sys, time
try:
    _kroot = os.environ.get("SF_KAGGLE_ROOT", "/kaggle")
    _sub = _kroot + "/working/submission.json"
    _end = min((CAST_B["deadline"] or time.time()) + 30,
               CAST_B["t0"] + float(os.environ.get("SF_DEADLINE_S", str(11.5 * 3600))) + 300)
    for _p in CAST_B.get("procs") or []:              # still running: wait, but never past its own deadline
        while _p.poll() is None and time.time() < _end:
            time.sleep(2)
        if _p.poll() is None:
            try:
                os.killpg(_p.pid, signal.SIGKILL)
            except OSError:
                pass
            _p.wait(timeout=30)
    if CODE_DIR not in sys.path:
        sys.path.insert(0, CODE_DIR)
    from sfb import merge as _BM
    _ch_path = CAST_B.get("ch_path")
    if not _ch_path:
        with open(_kroot + "/working/run_info.json") as _f:
            _ch_path = json.load(_f)["challenges"]
    try:                                               # entry H: C4's own salvage with the real child path
        _recon = _BM.reconcile_guard_output(_sub, _ch_path, _kroot, CODE_DIR)
    except BaseException as _e:
        _recon = {"applied": False, "reason": repr(_e)}
    print("neural file reconciliation:", json.dumps(_recon)[:500], flush=True)
    shutil.copyfile(_sub, _kroot + "/working/submission_A.json")      # the neural file, frozen before CORA
    _rep = _BM.merge_files_packages(_sub, _ch_path, CAST_B["packages"], _kroot + "/working/submission_B.json",
                                    _kroot + "/working/cast_merge_report.json", CODE_DIR)
    if _rep["ok"]:
        with open(_kroot + "/working/submission_B.json") as _f:
            _BM.atomic_json(_sub, json.load(_f))
    print("CORA merge:", json.dumps({k: _rep.get(k) for k in (
        "ok", "tier", "identical_attempt_outputs", "replaced_tier0", "replaced_tier1", "per_package",
        "problems")}), flush=True)
except BaseException as _e:
    print("CORA merge skipped; submission.json is the neural file:", repr(_e), flush=True)
'''


# ----- configuration O: CORA-only CPU entry (CAST alone; no neural model, no GPU) -----------------------------------
O_BUILDS = {
    "O": {"slug": "cora-cast-only-arc-agi-2", "title": "CORA CAST only ARC-AGI-2", "env": {}},
    "ORH": {"slug": "cora-cast-only-rehearsal-eval120", "title": "CORA CAST only rehearsal eval120",
            "env": {"SF_REHEARSE_ON": "evaluation"}},
}
SFO_FILES = ["sfb/__init__.py", "sfb/cast_side.py", "sfo/__init__.py", "sfo/driver.py"]

O_FILES_CELL = r"""
# Configuration O (CORA only): CAST v1 core alone on CPU; no neural model, no GPU, no internet.
# Cell 1 of 2: write the embedded code (hash-checked).
import hashlib, json, os
O_ENV = __O_ENV__
for _k, _v in O_ENV.items():
    os.environ[_k] = _v
CODE_DIR = os.environ.get("SF_KAGGLE_ROOT", "/kaggle") + "/working/o_code"
CODE_SHA = __CODE_SHA__
FILES = json.loads(__O_FILES__)
FILE_SHA = __O_SHA__
for _name, _text in FILES.items():
    if hashlib.sha256(_text.encode("utf-8")).hexdigest() != FILE_SHA[_name]:
        raise RuntimeError("embedded file hash mismatch: " + _name)
    _p = os.path.join(CODE_DIR, _name)
    os.makedirs(os.path.dirname(_p), exist_ok=True)
    with open(_p, "w", encoding="utf-8") as _f:
        _f.write(_text)
print("code written", CODE_SHA, len(FILES), flush=True)
"""

O_DRIVER_CELL = r"""
# Cell 2 of 2: a valid fallback file first, then CAST on CPU (sfo/driver.py), then a final schema guard.
import glob, json, os, subprocess, sys, time
KROOT = os.environ.get("SF_KAGGLE_ROOT", "/kaggle")
T0 = time.time()
SUB = KROOT + "/working/submission.json"
COMP_DIR = None
for _d in (KROOT + "/input/competitions/arc-prize-2026-arc-agi-2", KROOT + "/input/arc-prize-2026-arc-agi-2"):
    if os.path.isdir(_d):
        COMP_DIR = _d
        break
if COMP_DIR is None:
    COMP_DIR = os.path.dirname(glob.glob(KROOT + "/input/**/arc-agi_test_challenges.json", recursive=True)[0])
if os.environ.get("SF_REHEARSE_ON") == "evaluation":
    CH = os.path.join(COMP_DIR, "arc-agi_evaluation_challenges.json")
else:
    CH = os.path.join(COMP_DIR, "arc-agi_test_challenges.json")
with open(CH) as _f:
    ch = json.load(_f)

def _fallback_all():
    return {t: [{"attempt_1": x["input"], "attempt_2": x["input"]} for x in v["test"]] for t, v in ch.items()}

def _write(obj):
    _tmp = SUB + ".tmp"
    with open(_tmp, "w") as _f:
        json.dump(obj, _f)
        _f.flush()
        os.fsync(_f.fileno())
    os.replace(_tmp, SUB)

def _grid_ok(g):
    if not isinstance(g, list) or not 1 <= len(g) <= 30:
        return False
    w = len(g[0]) if isinstance(g[0], list) else -1
    return 1 <= w <= 30 and all(isinstance(r, list) and len(r) == w and
                                all(type(v) is int and 0 <= v <= 9 for v in r) for r in g)

def _valid(sub):
    return isinstance(sub, dict) and set(sub) == set(ch) and all(
        isinstance(sub[t], list) and len(sub[t]) == len(v["test"]) and
        all(isinstance(a, dict) and set(a) == {"attempt_1", "attempt_2"} and _grid_ok(a["attempt_1"]) and
            _grid_ok(a["attempt_2"]) for a in sub[t]) for t, v in ch.items())

_write(_fallback_all())                                       # valid before anything else runs
info = {"config": "O", "code_sha256": CODE_SHA, "challenges": CH, "n_tasks": len(ch),
        "rehearsal": os.environ.get("SF_REHEARSE_ON") == "evaluation",
        "rerun_env": os.environ.get("KAGGLE_IS_COMPETITION_RERUN"), "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(), "affinity": len(os.sched_getaffinity(0)),
        "package": os.environ["SF_O_PACKAGE"], "version": os.environ["SF_O_VERSION"]}
for _m in ("numpy", "scipy"):
    try:
        info[_m] = __import__(_m).__version__
    except Exception:
        info[_m] = None
with open(KROOT + "/working/run_info.json", "w") as _f:
    json.dump(info, _f, indent=1)
print(json.dumps(info), flush=True)
_cmd = [sys.executable, "-m", "sfo.driver", "--challenges", CH, "--out", KROOT + "/working/run", "--submission", SUB,
        "--package", os.environ["SF_O_PACKAGE"], "--entry", os.environ["SF_O_ENTRY"],
        "--deadline-s", os.environ["SF_O_DEADLINE_S"], "--shards", os.environ.get("SF_O_SHARDS", "0"),
        "--cpu-s", os.environ["SF_O_CPU_S"], "--wall-s", os.environ["SF_O_WALL_S"],
        "--grace-s", os.environ["SF_O_GRACE_S"], "--code-dir", CODE_DIR]
try:
    _r = subprocess.run(_cmd, cwd=CODE_DIR, timeout=float(os.environ["SF_O_DEADLINE_S"]) + 900)
    _rc = _r.returncode
except Exception as _e:                                       # the last valid file stays
    _rc = repr(_e)
try:
    with open(SUB) as _f:
        _ok = _valid(json.load(_f))
except Exception:
    _ok = False
if not _ok:
    _write(_fallback_all())
print("driver returncode", _rc, "final file valid", _ok, "wall_s", round(time.time() - T0, 1), flush=True)
"""


# ----- configuration O+: CORA-only CPU entry with the constructor hook (CAST v1 first, then reviewed R29) -----------
R29_COPY = os.path.join(HERE, "op", "r29_frozen", "r29_cpu_package_20261101")
R29_MANIFEST_SHA = "11eb2ee9cd10f1507a0ffdcc6ae069de2efed79eb569788888aebcc3fd685ef7"
OP_BUILDS = {
    "OP": {"slug": "cora-cast-r29-arc-agi-2", "title": "CORA CAST R29 ARC-AGI-2", "rehearse": False},
    "OPRH": {"slug": "cora-cast-r29-rehearsal-eval120", "title": "CORA CAST R29 rehearsal eval120",
             "rehearse": True},
    # O+ v2 (the author's 1 Nov decision, option (a)): CAST v1's per-puzzle caps raised to 45 CPU-s / 90 wall-s,
    # because Kaggle's CPU ran CAST v1 about 2.3 to 2.8 times slower than our development machine and its 15 s cap dropped answers.
    # Packages and acceptance policy unchanged.
    "OP2": {"slug": "cora-cast-r29-v2-arc-agi-2", "title": "CORA CAST R29 v2 ARC-AGI-2", "rehearse": False,
            "cast_v1_caps": (45, 90)},
    "OP2RH": {"slug": "cora-cast-r29-v2-rehearsal-eval120", "title": "CORA CAST R29 v2 rehearsal eval120",
              "rehearse": True, "cast_v1_caps": (45, 90)},
}
OP_SIDE = ["sfb/__init__.py", "sfb/cast_side.py", "sfo/__init__.py", "sfo/driver_plus.py"]
OP_PACKAGES = [{"name": "cast_v1", "entry": "cast_candidates", "cpu_s": 15, "wall_s": 30, "details": 1},
               {"name": "r29_cpu_package_20261101", "entry": "candidates", "cpu_s": 12, "wall_s": 24, "details": 0}]

OP_DRIVER_CELL = r'''
# Cell 2 of 2: the constructor packages in priority order on CPU (sfo/driver_plus.py), then a final schema guard.
# attempt_1 = the first package's answer; attempt_2 = the next distinct answer from another package; else a copy
# of the test input.
import glob, json, os, subprocess, sys, time
KROOT = os.environ.get("SF_KAGGLE_ROOT", "/kaggle")
T0 = time.time()
SUB = KROOT + "/working/submission.json"
COMP_DIR = None
for _d in (KROOT + "/input/competitions/arc-prize-2026-arc-agi-2", KROOT + "/input/arc-prize-2026-arc-agi-2"):
    if os.path.isdir(_d):
        COMP_DIR = _d
        break
if COMP_DIR is None:
    COMP_DIR = os.path.dirname(glob.glob(KROOT + "/input/**/arc-agi_test_challenges.json", recursive=True)[0])
if os.environ.get("SF_REHEARSE_ON") == "evaluation":
    CH = os.path.join(COMP_DIR, "arc-agi_evaluation_challenges.json")
else:
    CH = os.path.join(COMP_DIR, "arc-agi_test_challenges.json")
with open(CH) as _f:
    ch = json.load(_f)

def _fallback_all():
    return {t: [{"attempt_1": x["input"], "attempt_2": x["input"]} for x in v["test"]] for t, v in ch.items()}

def _write(obj):
    _tmp = SUB + ".tmp"
    with open(_tmp, "w") as _f:
        json.dump(obj, _f)
        _f.flush()
        os.fsync(_f.fileno())
    os.replace(_tmp, SUB)

def _grid_ok(g):
    if not isinstance(g, list) or not 1 <= len(g) <= 30:
        return False
    w = len(g[0]) if isinstance(g[0], list) else -1
    return 1 <= w <= 30 and all(isinstance(r, list) and len(r) == w and
                                all(type(v) is int and 0 <= v <= 9 for v in r) for r in g)

def _valid(sub):
    return isinstance(sub, dict) and set(sub) == set(ch) and all(
        isinstance(sub[t], list) and len(sub[t]) == len(v["test"]) and
        all(isinstance(a, dict) and set(a) == {"attempt_1", "attempt_2"} and _grid_ok(a["attempt_1"]) and
            _grid_ok(a["attempt_2"]) for a in sub[t]) for t, v in ch.items())

_write(_fallback_all())                                       # valid before anything else runs
info = {"config": "O+", "code_sha256": CODE_SHA, "challenges": CH, "n_tasks": len(ch),
        "rehearsal": os.environ.get("SF_REHEARSE_ON") == "evaluation",
        "rerun_env": os.environ.get("KAGGLE_IS_COMPETITION_RERUN"), "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(), "affinity": len(os.sched_getaffinity(0)),
        "packages": json.loads(os.environ["SF_OP_PACKAGES"])}
for _m in ("numpy", "scipy"):
    try:
        info[_m] = __import__(_m).__version__
    except Exception:
        info[_m] = None
with open(KROOT + "/working/run_info.json", "w") as _f:
    json.dump(info, _f, indent=1)
print(json.dumps(info), flush=True)
_cmd = [sys.executable, "-m", "sfo.driver_plus", "--challenges", CH, "--out", KROOT + "/working/run",
        "--submission", SUB, "--packages", os.environ["SF_OP_PACKAGES"],
        "--deadline-s", os.environ["SF_O_DEADLINE_S"], "--shards", os.environ.get("SF_O_SHARDS", "0"),
        "--grace-s", os.environ["SF_O_GRACE_S"], "--code-dir", CODE_DIR]
try:
    _r = subprocess.run(_cmd, cwd=CODE_DIR, timeout=float(os.environ["SF_O_DEADLINE_S"]) + 900)
    _rc = _r.returncode
except Exception as _e:                                       # the last valid file stays
    _rc = repr(_e)
try:
    with open(SUB) as _f:
        _ok = _valid(json.load(_f))
except Exception:
    _ok = False
if not _ok:
    _write(_fallback_all())
print("driver returncode", _rc, "final file valid", _ok, "wall_s", round(time.time() - T0, 1), flush=True)
'''


def build_op(name, kernels):
    """Configuration O+ or its CPU rehearsal: CAST v1 (manifest acd57e12) then the reviewed R29 copy (manifest
    11eb2ee9; every file it lists, byte for byte, since its worker re-checks them on every call)."""
    spec = OP_BUILDS[name]
    out = os.path.join(kernels, spec["slug"])
    os.makedirs(out, exist_ok=True)
    cp = cast_package(DEFAULT_CAST_MANIFEST)
    files = dict(cp["files"])
    rman_p = os.path.join(R29_COPY, "MANIFEST.json")
    if sha256_file(rman_p) != R29_MANIFEST_SHA:
        raise SystemExit("R29 manifest is not the reviewed 11eb2ee9")
    rman = json.load(open(rman_p))
    for rel, h in sorted(rman["files"].items()):
        text = open(os.path.join(R29_COPY, rel), encoding="utf-8").read()
        if sha256_text(text) != h:
            raise SystemExit(f"R29 file {rel} does not match its manifest")
        files["r29_cpu_package_20261101/" + rel] = text
    files["r29_cpu_package_20261101/MANIFEST.json"] = open(rman_p, encoding="utf-8").read()
    if sha256_text(files["r29_cpu_package_20261101/MANIFEST.json"]) != R29_MANIFEST_SHA:
        raise SystemExit("R29 manifest text is not byte-exact")
    files.update({f: open(os.path.join(HERE, f), encoding="utf-8").read() for f in OP_SIDE})
    blob = json.dumps(files, sort_keys=True)
    code_sha = sha256_text(blob)
    packages = [dict(pk) for pk in OP_PACKAGES]
    if spec.get("cast_v1_caps"):
        packages[0].update(cpu_s=spec["cast_v1_caps"][0], wall_s=spec["cast_v1_caps"][1])
    env = {"SF_O_GRACE_S": "10", "SF_O_DEADLINE_S": "39600", "SF_OP_PACKAGES": json.dumps(packages)}
    if spec["rehearse"]:
        env["SF_REHEARSE_ON"] = "evaluation"
    c0 = (O_FILES_CELL.replace("__O_ENV__", repr(dict(sorted(env.items()))))
          .replace("__CODE_SHA__", repr(code_sha)).replace("__O_FILES__", repr(blob))
          .replace("__O_SHA__", repr({k: sha256_text(v) for k, v in sorted(files.items())}))
          .replace("Configuration O (CORA only): CAST v1 core alone on CPU", "Configuration O+ (CORA only): CAST v1 core, "
                   "then the reviewed R29 package, on CPU"))
    mk = {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": []}
    nb = {"cells": [dict(mk, source=c0), dict(mk, source=OP_DRIVER_CELL)],
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    nb_path = os.path.join(out, "notebook.ipynb")
    with open(nb_path, "w") as f:
        json.dump(nb, f, indent=1)
    meta = {"id": f"chimdiwalter/{spec['slug']}", "title": spec["title"], "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": False,
            "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
            "competition_sources": ["arc-prize-2026-arc-agi-2"], "kernel_sources": [], "model_sources": []}
    with open(os.path.join(out, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=1)
    manifest = {"config": name, "code_sha256": code_sha, "files": {k: sha256_text(v) for k, v in sorted(files.items())},
                "env": dict(sorted(env.items())), "packages": packages,
                "cast_v1_manifest_sha256": cp["manifest_sha256"], "r29_manifest_sha256": R29_MANIFEST_SHA,
                "cells_sha256": [sha256_text(c["source"]) for c in nb["cells"]], "notebook_sha256": sha256_file(nb_path)}
    with open(os.path.join(out, "build_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return {"name": name, "dir": os.path.relpath(out, REPO), "notebook_sha256": manifest["notebook_sha256"],
            "kernel_metadata_sha256": sha256_file(os.path.join(out, "kernel-metadata.json")),
            "build_manifest_sha256": sha256_file(os.path.join(out, "build_manifest.json")), "code_sha256": code_sha}


def build_o(name, cast_manifest, kernels):
    spec = O_BUILDS[name]
    out = os.path.join(kernels, spec["slug"])
    os.makedirs(out, exist_ok=True)
    cp = cast_package(cast_manifest)
    files = dict(cp["files"])
    # O embeds the frozen side files it was tested with (configs/sfo/frozen/), not the live sfb/ used by B and H
    files.update({f: open(os.path.join(HERE, "sfo", "frozen", f), encoding="utf-8").read() for f in SFO_FILES})
    blob = json.dumps(files, sort_keys=True)
    code_sha = sha256_text(blob)
    env = {"SF_O_PACKAGE": cp["package"], "SF_O_ENTRY": cp["entry"], "SF_O_VERSION": str(cp["version"]),
           "SF_O_CPU_S": cp["cpu_s"], "SF_O_WALL_S": cp["wall_s"], "SF_O_GRACE_S": "10",
           "SF_O_DEADLINE_S": "39600"}
    env.update(spec["env"])
    c0 = (O_FILES_CELL.replace("__O_ENV__", repr(dict(sorted(env.items()))))
          .replace("__CODE_SHA__", repr(code_sha)).replace("__O_FILES__", repr(blob))
          .replace("__O_SHA__", repr({k: sha256_text(v) for k, v in sorted(files.items())})))
    mk = {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": []}
    nb = {"cells": [dict(mk, source=c0), dict(mk, source=O_DRIVER_CELL)],
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    with open(os.path.join(out, "notebook.ipynb"), "w") as f:
        json.dump(nb, f, indent=1)
    meta = {"id": f"chimdiwalter/{spec['slug']}", "title": spec["title"], "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": False,
            "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
            "competition_sources": ["arc-prize-2026-arc-agi-2"], "kernel_sources": [], "model_sources": []}
    with open(os.path.join(out, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=1)
    manifest = {"config": name, "code_sha256": code_sha, "files": {k: sha256_text(v) for k, v in sorted(files.items())},
                "env": dict(sorted(env.items())), "cast_manifest": cp["manifest_path"],
                "cast_manifest_sha256": cp["manifest_sha256"], "cast_package": cp["package"],
                "cast_version": cp["version"], "cells_sha256": [sha256_text(c["source"]) for c in nb["cells"]],
                "notebook_sha256": sha256_file(os.path.join(out, "notebook.ipynb"))}
    with open(os.path.join(out, "build_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return {"name": name, "dir": os.path.relpath(out, REPO), "notebook_sha256": manifest["notebook_sha256"],
            "kernel_metadata_sha256": sha256_file(os.path.join(out, "kernel-metadata.json")),
            "build_manifest_sha256": sha256_file(os.path.join(out, "build_manifest.json")), "code_sha256": code_sha,
            "cast_manifest_sha256": cp["manifest_sha256"]}


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_build_kernel():
    spec = importlib.util.spec_from_file_location("build_kernel", os.path.join(SF_HOME, "tools", "build_kernel.py"))
    bk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bk)
    return bk


def run_build_kernel(bk, out, slug, title, env):
    """The unchanged reviewed builder, called exactly as on the command line."""
    argv = ["build_kernel.py", out, slug, title, "--mode", "submit"]
    for k, v in env:
        argv += ["--env", f"{k}={v}"]
    old = sys.argv
    sys.argv = argv
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            bk.main()
    finally:
        sys.argv = old


def cast_package(manifest_path, entry_name=None):
    """(package name, version, entry function, {embedded path: text}, manifest sha256, caps, tier) from a manifest.
    cast_v1 names one "entry_point"; cast_selective_v2 lists "entry_points" (the build names the one it uses)."""
    man = json.load(open(manifest_path))
    base = os.path.dirname(os.path.abspath(manifest_path))
    pkg = man["package"]
    if "entry_point" in man:
        entry = man["entry_point"].split("(")[0].strip()
        mod, _, fn = entry.rpartition(".")
        if mod != pkg:
            raise SystemExit(f"entry point {entry} is not in package {pkg}")
    else:
        names = [e.split("(")[0].strip() for e in man.get("entry_points", [])]
        fn = entry_name
        if fn not in names:
            raise SystemExit(f"{entry_name!r} is not among the manifest's entry points {names}")
    if entry_name and fn != entry_name:
        raise SystemExit(f"the manifest's entry point is {fn}, not {entry_name}")
    files = {}
    for rel, sha in sorted(man["files"].items()):
        if not (rel.startswith(pkg + "/") and rel.endswith(".py")):
            continue                                   # tests, README: not embedded
        p = os.path.join(base, rel)
        text = open(p, encoding="utf-8").read()
        if sha256_text(text) != sha or sha256_file(p) != sha:
            raise SystemExit(f"hash mismatch against the CAST manifest: {rel}")
        files[rel] = text
    if not any(r == f"{pkg}/__init__.py" for r in files):
        raise SystemExit("package __init__.py missing from the manifest")
    caps = man.get("caps") or {}
    tier = man.get("replacement_tier", man.get("tier", 0))
    return {"package": pkg, "version": man.get("version"), "entry": fn, "files": files, "manifest": man,
            "manifest_sha256": sha256_file(manifest_path), "manifest_path": os.path.relpath(manifest_path, REPO),
            "cpu_s": str(caps.get("cpu_s", 15.0)), "wall_s": str(caps.get("wall_s", 30.0)),
            "tier": int(tier) if str(tier).isdigit() else 0, "manifest_tier_field": tier}


def cora_cells(spec, overrides=None):
    """The two CORA cells for a package list, and their manifest fields."""
    pkgs, files, info = [], {}, []
    for pk in spec["packages"]:
        cp = cast_package(pk["manifest"], pk["entry"])
        files.update(cp["files"])
        pkgs.append({"name": cp["package"], "entry": cp["entry"], "mode": pk["mode"], "policy": pk["policy"],
                     "version": str(cp["version"]), "cpu_s": cp["cpu_s"], "wall_s": cp["wall_s"]})
        info.append({"package": cp["package"], "version": cp["version"], "entry": cp["entry"], "mode": pk["mode"],
                     "policy": pk["policy"], "manifest": cp["manifest_path"],
                     "manifest_sha256": cp["manifest_sha256"],
                     "files": {k: sha256_text(v) for k, v in sorted(cp["files"].items())}})
    sfb = {f: open(os.path.join(HERE, f), encoding="utf-8").read() for f in SFB_FILES}
    files.update(sfb)
    b_env = {"SF_CAST_GRACE_S": "10", "SF_CAST_TOTAL_S": spec["cast_total_s"], "SF_CAST_END_RESERVE_S": "1800",
             "SF_CAST_NICE": "10"}
    if overrides and overrides.get("b_env"):
        b_env.update(overrides["b_env"])
    blob = json.dumps(files, sort_keys=True)
    launch = (B_LAUNCH.replace("__B_ENV__", repr(dict(sorted(b_env.items()))))
              .replace("__B_PACKAGES__", repr(pkgs))
              .replace("__B_FILES__", repr(blob))
              .replace("__B_SHA__", repr({k: sha256_text(v) for k, v in sorted(files.items())})))
    man = {"cora_packages": info, "cora_package_list": pkgs,
           "sfb_files": {k: sha256_text(v) for k, v in sorted(sfb.items())}, "b_env": dict(sorted(b_env.items())),
           "b_embedded_sha256": sha256_text(blob), "b_launch_cell_sha256": sha256_text(launch),
           "b_merge_cell_sha256": sha256_text(B_MERGE)}
    return launch, B_MERGE, man


def build_h(name, kernels, overrides=None):
    """Entry H (and its rehearsal): the verified C4 copy's two cells byte for byte, with CORA's launch cell between them
    and CORA's merge cell after them. The rehearsal adds one first cell that sets SF_REHEARSE_ON=evaluation, the
    same change as the C4 rehearsal that ran on Kaggle. Test overrides may rewrite C4's environment lines (CPU dress
    rehearsals only; the real builds never do)."""
    spec = H_BUILDS[name]
    src_nb = os.path.join(C4_COPY, "notebook", "notebook.ipynb")
    if sha256_file(src_nb) != C4_NOTEBOOK_SHA:
        raise SystemExit("the C4 copy is not the verified b571233a notebook")
    c4 = json.load(open(src_nb))
    c4_cells = [c["source"] if isinstance(c["source"], str) else "".join(c["source"]) for c in c4["cells"]]
    if len(c4_cells) != 2:
        raise SystemExit("unexpected C4 layout")
    if overrides and overrides.get("neural_env"):
        for k, v in overrides["neural_env"].items():
            pat = f"os.environ['{k}'] = '"
            i = c4_cells[0].index(pat) + len(pat)
            j = c4_cells[0].index("'", i)
            c4_cells[0] = c4_cells[0][:i] + v + c4_cells[0][j:]
    launch, merge_src, cman = cora_cells(spec, overrides)
    mk = {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": []}
    cells = [dict(mk, source=c4_cells[0]), dict(mk, source=launch), dict(mk, source=c4_cells[1]),
             dict(mk, source=merge_src)]
    if spec["rehearse"]:
        cells.insert(0, dict(mk, source="import os\nos.environ['SF_REHEARSE_ON'] = 'evaluation'   # rehearsal on the "
                                        "120 public evaluation challenges\n"))
    nb = {"cells": cells, "metadata": c4.get("metadata", {}), "nbformat": c4.get("nbformat", 4),
          "nbformat_minor": c4.get("nbformat_minor", 5)}
    out = os.path.join(kernels, spec["slug"])
    os.makedirs(out, exist_ok=True)
    nb_path = os.path.join(out, "notebook.ipynb")
    with open(nb_path, "w") as f:
        json.dump(nb, f, indent=1)
    meta = json.load(open(os.path.join(C4_COPY, "notebook", "kernel-metadata.json")))
    meta.update(id=f"chimdiwalter/{spec['slug']}", title=spec["title"])
    with open(os.path.join(out, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=1)
    manifest = {"config": name, "c4_notebook_sha256": C4_NOTEBOOK_SHA,
                "c4_cells_sha256": [sha256_text(c) for c in c4_cells], "c4_cells_verbatim": not (
                    overrides and overrides.get("neural_env")),
                "c4_copy_check": "configs/results/h_c4_copy.json", **cman,
                "cells_sha256": [sha256_text(c["source"]) for c in cells], "notebook_sha256": sha256_file(nb_path)}
    man_path = os.path.join(out, "build_manifest.json")
    with open(man_path, "w") as f:
        json.dump(manifest, f, indent=1)
    return {"name": name, "dir": os.path.relpath(out, REPO), "notebook_sha256": manifest["notebook_sha256"],
            "kernel_metadata_sha256": sha256_file(os.path.join(out, "kernel-metadata.json")),
            "build_manifest_sha256": sha256_file(man_path), "c4_notebook_sha256": C4_NOTEBOOK_SHA,
            "cora_packages": [(x["package"], x["version"], x["policy"]) for x in cman["cora_packages"]]}


def build(name, cast_manifest, kernels, overrides=None):
    spec = BUILDS[name]
    out = os.path.join(kernels, spec["slug"])
    bk = load_build_kernel()
    env = list(spec["env"])
    if overrides and overrides.get("neural_env"):
        env = [(k, overrides["neural_env"].get(k, v)) for k, v in env]
    run_build_kernel(bk, out, spec["slug"], spec["title"], env)
    nb_path = os.path.join(out, "notebook.ipynb")
    man_path = os.path.join(out, "build_manifest.json")
    manifest = json.load(open(man_path))
    manifest["config"] = name
    manifest["base_notebook_sha256"] = sha256_file(nb_path)
    if spec["cast"]:
        launch, merge_src, cman = cora_cells(spec, overrides)
        nb = json.load(open(nb_path))
        if len(nb["cells"]) != 2:
            raise SystemExit("unexpected base notebook layout")
        mk = {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": []}
        nb["cells"] = [nb["cells"][0], dict(mk, source=launch), nb["cells"][1], dict(mk, source=merge_src)]
        with open(nb_path, "w") as f:
            json.dump(nb, f, indent=1)
        manifest.update(cman)
    nb = json.load(open(nb_path))
    manifest["cells_sha256"] = [sha256_text(c["source"]) for c in nb["cells"]]
    manifest["notebook_sha256"] = sha256_file(nb_path)
    with open(man_path, "w") as f:
        json.dump(manifest, f, indent=1)
    return {"name": name, "dir": os.path.relpath(out, REPO), "notebook_sha256": manifest["notebook_sha256"],
            "kernel_metadata_sha256": sha256_file(os.path.join(out, "kernel-metadata.json")),
            "build_manifest_sha256": sha256_file(man_path), "code_sha256": manifest["code_sha256"],
            "cast_manifest_sha256": manifest.get("cast_manifest_sha256")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cast-manifest", default=DEFAULT_CAST_MANIFEST)
    ap.add_argument("--kernels", default=KERNELS)
    ap.add_argument("--only", default="A,B,AB,H,HRH")
    ap.add_argument("--test-overrides", default="")
    a = ap.parse_args()
    ov = json.loads(a.test_overrides) if a.test_overrides else None
    res = []
    for n in a.only.split(","):
        if n in OP_BUILDS:
            res.append(build_op(n, a.kernels))
        elif n in O_BUILDS:
            res.append(build_o(n, a.cast_manifest, a.kernels))      # O stays on cast_v1 (the default manifest)
        elif n in H_BUILDS:
            res.append(build_h(n, a.kernels, ov))
        else:
            res.append(build(n, a.cast_manifest, a.kernels, ov))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
