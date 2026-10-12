#!/usr/bin/env python3
"""ARC Prize 2026 (ARC-AGI-2) submission notebook, NATIVE_BASELINE native_v1 (single cell).

LABEL: NATIVE_BASELINE. This is the sealed native solver (v23 chain), not
the CORA invention loop. No P2, P3, DCC, research controller or extension is
included.

Dataset (attach arc_native_baseline_v1.tar.gz, built by kaggle/native_v1/build_dataset.sh):
  geocat_arc/ harness/ src/reasoning_project/ scripts/ library.json learned_verbs.json MANIFEST.json

Reasoning: identical to the historical notebook (kaggle/kaggle_notebook.py):
- the unified harness, run with the five sealed chain flags (subprocess
  only), the sealed library.json and learned_verbs.json, the harness
  defaults per task, and the global governor (which only lowers per-task
  budgets when the clock is short);
- attempt_1 is the solving layer's render, attempt_2 the best uncertified
  object partial; the test input unchanged is the fallback
  (scripts/make_submission_v2.py).

Deployment robustness added in native_v1; the reasoning is unchanged:
- a hard wall-clock limit on the harness, and its process group is killed
  at the limit;
- submission.json is always written, even if the harness fails;
- every task and test-output position is validated (two attempts,
  rectangular 1-30 x 1-30 grids of integers 0-9), and an invalid entry is
  replaced by the fallback;
- an execution manifest with code, asset and output hashes.

No internet, no GPU. Local and emulation overrides: K_INPUT, K_SRC, K_COMP,
K_WORK, K_WORKERS, K_BUDGET_S, K_GUARD_DIR (emulation network guard only).
"""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

LABEL, VERSION = "NATIVE_BASELINE", "native_v1"
#: the sealed v23 chain flags (RUN_HISTORY 2026-08-19)
CHAIN_FLAGS = {"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
               "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"}
#: object-layer assets of the sealed runs, with their sha256
ASSETS = {"library.json": "cdacd018da0bd9a3fa460c23beeff89fd5b0c5a85d70ecca276fe212df13ce03",
          "learned_verbs.json": "b1f07ba5f4337cf450b9c13cc142937c1c56b0dcc10e1796e6fcdb39fe2b585c"}
INPUT = os.environ.get("K_INPUT", "/kaggle/input")
WORK = os.environ.get("K_WORK", "/kaggle/working")
T0 = time.time()


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def tree_sha(root):
    """One digest over every file of the staged solver (path and content)."""
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(root)):
        dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", "data"))
        for f in sorted(files):
            if f.endswith(".pyc"):
                continue
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, root).encode() + b"\0" + _sha(p).encode() + b"\n")
    return h.hexdigest()


def find_comp():
    if os.environ.get("K_COMP"):
        return os.environ["K_COMP"]
    for dirname, _dirs, files in os.walk(INPUT):
        if "geocat_arc" in dirname or any(f.endswith(".tar.gz") for f in files):
            continue
        names = [f.lower() for f in files]
        if any(f.endswith(".json") and ("challenge" in f or "test" in f) for f in names) \
                or "sample_submission.json" in names:
            return dirname
    raise SystemExit(f"no competition data dir found under {INPUT}")


def resolve_src():
    k_src = os.environ.get("K_SRC")
    if k_src and os.path.isdir(os.path.join(k_src, "geocat_arc")):
        return k_src
    tar_path = None
    for dirname, dirs, files in os.walk(INPUT):
        if "geocat_arc" in dirs:
            return dirname
        for f in files:
            if f.endswith(".tar.gz") and tar_path is None:
                tar_path = os.path.join(dirname, f)
    if tar_path is None:
        raise SystemExit(f"solver dataset not found under {INPUT}")
    import tarfile
    dest = os.path.join(WORK, "src_extracted")
    if not os.path.isdir(os.path.join(dest, "geocat_arc")):
        tarfile.open(tar_path).extractall(dest)
    return dest


def install_assets(code, out_dir):
    obj = os.path.join(out_dir, "object")
    os.makedirs(obj, exist_ok=True)
    for name, digest in ASSETS.items():
        src = os.path.join(code, name)
        if not os.path.exists(src):
            raise SystemExit(f"{name} missing from the solver dataset")
        if _sha(src) != digest:
            raise SystemExit(f"{name} sha256 {_sha(src)} != sealed {digest}")
        shutil.copy(src, os.path.join(obj, name))
    return obj


def native_env(code, base=None):
    """The harness subprocess environment: the sealed flags, nothing else ARC_*."""
    env = {k: v for k, v in (base if base is not None else os.environ).items() if not k.startswith("ARC_")}
    env["PYTHONPATH"] = code + ":" + os.path.join(code, "src")
    if env.get("K_GUARD_DIR"):                       # offline emulation only
        env["PYTHONPATH"] = env["K_GUARD_DIR"] + ":" + env["PYTHONPATH"]
    env.update(CHAIN_FLAGS)
    return env


def _grid_ok(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) for r in g)
            and 1 <= len(g[0]) <= 30 and all(len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r))


def fallback_submission(challenges, progress_path):
    """The same policy as scripts/make_submission_v2.py, for when it cannot run."""
    preds = {}
    if os.path.exists(progress_path):
        for line in open(progress_path):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("predictions"):
                preds[d["task_id"]] = d["predictions"]
    sub = {}
    for tid, task in challenges.items():
        p = preds.get(tid) or {}
        a1s, a2s = p.get("attempt_1"), p.get("attempt_2")
        entries = []
        for i, case in enumerate(task["test"]):
            a1 = a1s[i] if a1s and i < len(a1s) and a1s[i] else None
            a2 = a2s[i] if a2s and i < len(a2s) and a2s[i] else None
            a1 = a1 if a1 is not None else (a2 if a2 is not None else case["input"])
            entries.append({"attempt_1": a1, "attempt_2": a2 if a2 is not None else a1})
        sub[tid] = entries
    return sub


def validate_and_repair(sub, challenges):
    """Every task id, every test position, exactly attempt_1 and attempt_2, valid grids;
    an invalid or missing entry becomes the test input (the existing fallback)."""
    repairs = []
    out = {}
    for tid, task in challenges.items():
        entries = sub.get(tid) if isinstance(sub.get(tid), list) else []
        fixed = []
        for i, case in enumerate(task["test"]):
            e = entries[i] if i < len(entries) and isinstance(entries[i], dict) else {}
            a1, a2 = e.get("attempt_1"), e.get("attempt_2")
            ok1, ok2 = _grid_ok(a1), _grid_ok(a2)
            if not ok1:
                repairs.append((tid, i, "attempt_1"))
            if not ok2:
                repairs.append((tid, i, "attempt_2"))
            a1 = a1 if ok1 else (a2 if ok2 else case["input"])     # the writer's own fallback order
            fixed.append({"attempt_1": a1, "attempt_2": a2 if ok2 else a1})
        out[tid] = fixed
    extra = sorted(set(sub) - set(challenges))
    return out, repairs, extra


def main():
    man = {"label": LABEL, "version": VERSION, "flags": CHAIN_FLAGS, "started_unix": round(T0, 1)}
    src = resolve_src()
    comp = find_comp()
    code = os.path.join(WORK, "solver")
    shutil.rmtree(code, ignore_errors=True)          # always stage fresh
    shutil.copytree(src, code)
    man["solver_tree_sha256"] = tree_sha(code)
    os.chdir(code)
    os.makedirs("data/arc", exist_ok=True)
    for name in os.listdir(comp):
        if name.endswith(".json"):
            shutil.copy(os.path.join(comp, name), "data/arc/")
    cands = [n for n in os.listdir("data/arc") if n.endswith(".json") and "challenge" in n and "sample" not in n]
    test_files = [n for n in cands if "test" in n]
    test_file = sorted(test_files or cands)[0]
    print("using task file:", test_file)
    man["task_file"], man["task_file_sha256"] = test_file, _sha(os.path.join("data/arc", test_file))
    if test_file != "arc-agi_evaluation_challenges.json":
        shutil.copy(f"data/arc/{test_file}", "data/arc/arc-agi_evaluation_challenges.json")
        if os.path.exists("data/arc/arc-agi_evaluation_solutions.json"):
            os.remove("data/arc/arc-agi_evaluation_solutions.json")
    if not os.path.exists("data/arc/arc-agi_evaluation_solutions.json"):
        json.dump({}, open("data/arc/arc-agi_evaluation_solutions.json", "w"))
    challenges = json.load(open("data/arc/arc-agi_evaluation_challenges.json"))
    out_dir = os.path.join(WORK, "run")
    obj = install_assets(code, out_dir)
    man["assets"] = {n: _sha(os.path.join(obj, n)) for n in ASSETS}
    env = native_env(code)
    budget_s = int(os.environ.get("K_BUDGET_S", str(int(11.25 * 3600))))
    workers = os.environ.get("K_WORKERS", str(os.cpu_count()))
    cmd = [sys.executable, "scripts/run_unified_harness.py", "--split", "evaluation", "--workers", workers,
           "--out-dir", out_dir, "--run-id", "kaggle", "--emit-predictions", "--global-budget-s", str(budget_s)]
    man.update(budget_s=budget_s, workers=workers, harness_cmd=cmd[1:], tasks=len(challenges),
               test_outputs=sum(len(t["test"]) for t in challenges.values()))
    print("native configuration:", json.dumps({k: man[k] for k in ("label", "flags", "assets", "budget_s", "workers")}))
    hard_limit = budget_s + 600
    t_h = time.time()
    proc = subprocess.Popen(cmd, env=env, start_new_session=True)
    try:
        man["harness_returncode"] = proc.wait(timeout=hard_limit)
        man["harness_status"] = "completed" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        man["harness_returncode"], man["harness_status"] = None, "killed_at_hard_limit"
    man["harness_s"] = round(time.time() - t_h, 1)
    progress = os.path.join(out_dir, "progress.jsonl")
    out_path = os.path.join(WORK, "submission.json")
    w = subprocess.run([sys.executable, "scripts/make_submission_v2.py", progress,
                        "data/arc/arc-agi_evaluation_challenges.json", out_path], env=env,
                       capture_output=True, text=True)
    man["writer"] = "make_submission_v2" if w.returncode == 0 and os.path.exists(out_path) else "notebook_fallback"
    print(w.stdout.strip() or w.stderr.strip()[-500:])
    try:
        sub = json.load(open(out_path)) if man["writer"] == "make_submission_v2" else None
    except ValueError:
        sub, man["writer"] = None, "notebook_fallback"
    if sub is None:
        sub = fallback_submission(challenges, progress)
    sub, repairs, extra = validate_and_repair(sub, challenges)
    json.dump(sub, open(out_path, "w"))
    rows = [json.loads(x) for x in open(progress)] if os.path.exists(progress) else []
    man.update(tasks_with_rows=len({r.get("task_id") for r in rows}),
               tasks_with_predictions=sum(1 for r in rows if r.get("predictions")),
               validation={"tasks": len(sub), "positions": sum(len(v) for v in sub.values()),
                           "repaired_entries": len(repairs), "extra_ids_dropped": extra},
               submission_sha256=_sha(out_path), elapsed_s=round(time.time() - T0, 1))
    json.dump(man, open(os.path.join(WORK, "execution_manifest.json"), "w"), indent=1)
    print("submission.json written:", json.dumps(man["validation"]), "| harness", man["harness_status"],
          "| elapsed", man["elapsed_s"], "s")


if __name__ == "__main__":
    main()
