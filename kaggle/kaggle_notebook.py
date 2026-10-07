#!/usr/bin/env python3
"""ARC Prize 2026 submission notebook (single cell).

Dataset layout (attach arc_certified_solver_v23.tar.gz, built by
kaggle/build_dataset.sh, extracted anywhere under /kaggle/input/):
  geocat_arc/ harness/ src/reasoning_project/ scripts/ library.json learned_verbs.json

Pipeline: governed 3-layer harness with prediction emission ->
submission.json.  attempt_1 = LOO-certified render; attempt_2 = best
uncertified partial.  No internet, no GPU.

Native configuration (the sealed v23 chain, records/NATIVE_ASSETS_PROVENANCE.md):
the five chain flags below, set for the harness subprocess only, and the
frozen library.json + learned_verbs.json in the object layer's directory.
Local test overrides: K_SRC, K_COMP, K_WORK, K_WORKERS, K_BUDGET_S.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

#: the sealed v23 chain flags (RUN_HISTORY 2026-08-19)
CHAIN_FLAGS = {"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
               "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"}
#: object-layer assets of the sealed runs, with their sha256
ASSETS = {"library.json": "cdacd018da0bd9a3fa460c23beeff89fd5b0c5a85d70ecca276fe212df13ce03",
          "learned_verbs.json": "b1f07ba5f4337cf450b9c13cc142937c1c56b0dcc10e1796e6fcdb39fe2b585c"}
WORK = os.environ.get("K_WORK", "/kaggle/working")


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def find_comp():
    """The competition data dir: K_COMP, else the first dir under
    /kaggle/input with a challenges/test json that is not the solver."""
    if os.environ.get("K_COMP"):
        return os.environ["K_COMP"]
    for dirname, _dirs, files in os.walk("/kaggle/input"):
        if "geocat_arc" in dirname or any(f.endswith(".tar.gz") for f in files):
            continue
        names = [f.lower() for f in files]
        if any(f.endswith(".json") and ("challenge" in f or "test" in f) for f in names) \
                or "sample_submission.json" in names:
            return dirname
    raise SystemExit("no competition data dir found under /kaggle/input")


def resolve_src():
    """The solver: K_SRC when it holds geocat_arc/, else an extracted tree
    or a .tar.gz anywhere under /kaggle/input."""
    k_src = os.environ.get("K_SRC")
    if k_src and os.path.isdir(os.path.join(k_src, "geocat_arc")):
        return k_src
    tar_path = None
    for dirname, dirs, files in os.walk("/kaggle/input"):
        if "geocat_arc" in dirs:
            return dirname
        for f in files:
            if f.endswith(".tar.gz") and tar_path is None:
                tar_path = os.path.join(dirname, f)
    if tar_path is None:
        raise SystemExit("solver dataset not found under /kaggle/input")
    import tarfile
    dest = os.path.join(WORK, "src_extracted")
    if not os.path.isdir(os.path.join(dest, "geocat_arc")):
        tarfile.open(tar_path).extractall(dest)
    return dest


def install_assets(code, out_dir):
    """Copy the sealed object-layer assets into the run's object directory,
    refusing any missing or altered file."""
    obj = os.path.join(out_dir, "object")
    os.makedirs(obj, exist_ok=True)
    for name, digest in ASSETS.items():
        src = os.path.join(code, name)
        if not os.path.exists(src):
            raise SystemExit(f"{name} missing from the solver dataset (rebuild with kaggle/build_dataset.sh)")
        if _sha(src) != digest:
            raise SystemExit(f"{name} sha256 {_sha(src)} != sealed {digest}")
        shutil.copy(src, os.path.join(obj, name))
    return obj


def native_env(code, base=None):
    """The harness subprocess environment: the sealed flags, nothing else ARC_*."""
    env = {k: v for k, v in (base if base is not None else os.environ).items() if not k.startswith("ARC_")}
    env["PYTHONPATH"] = code + ":" + os.path.join(code, "src")
    env.update(CHAIN_FLAGS)
    return env


def main():
    src = resolve_src()
    comp = find_comp()
    code = os.path.join(WORK, "solver")
    shutil.rmtree(code, ignore_errors=True)          # always stage fresh
    shutil.copytree(src, code)
    os.chdir(code)
    os.makedirs("data/arc", exist_ok=True)
    for name in os.listdir(comp):
        if name.endswith(".json"):
            shutil.copy(os.path.join(comp, name), "data/arc/")
    # the competition test file plays the 'evaluation challenges' role;
    # solutions are absent by design (submission mode never needs them)
    cands = [n for n in os.listdir("data/arc")
             if n.endswith(".json") and "challenge" in n and "sample" not in n]
    test_files = [n for n in cands if "test" in n]
    test_file = sorted(test_files or cands)[0]
    print("using task file:", test_file)
    if test_file != "arc-agi_evaluation_challenges.json":
        shutil.copy(f"data/arc/{test_file}", "data/arc/arc-agi_evaluation_challenges.json")
        if os.path.exists("data/arc/arc-agi_evaluation_solutions.json"):
            os.remove("data/arc/arc-agi_evaluation_solutions.json")
    if not os.path.exists("data/arc/arc-agi_evaluation_solutions.json"):
        json.dump({}, open("data/arc/arc-agi_evaluation_solutions.json", "w"))
    out_dir = os.path.join(WORK, "run")
    obj = install_assets(code, out_dir)
    env = native_env(code)
    budget_s = int(os.environ.get("K_BUDGET_S", str(int(11.25 * 3600))))
    workers = os.environ.get("K_WORKERS", str(os.cpu_count()))
    print("native configuration:", json.dumps({"flags": CHAIN_FLAGS, "assets": {
        n: _sha(os.path.join(obj, n)) for n in ASSETS}, "budget_s": budget_s, "workers": workers}))
    subprocess.run([sys.executable, "scripts/run_unified_harness.py",
                    "--split", "evaluation", "--workers", workers,
                    "--out-dir", out_dir, "--run-id", "kaggle", "--emit-predictions",
                    "--global-budget-s", str(budget_s)], check=True, env=env)
    subprocess.run([sys.executable, "scripts/make_submission_v2.py", f"{out_dir}/progress.jsonl",
                    "data/arc/arc-agi_evaluation_challenges.json", os.path.join(WORK, "submission.json")],
                   check=True, env=env)
    print("submission.json written")


if __name__ == "__main__":
    main()
