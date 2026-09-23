#!/usr/bin/env python3
"""ARC Prize 2026 submission notebook (single cell).

Dataset layout (attach arc_certified_solver.tar.gz extracted as
/kaggle/input/arc-certified-solver/):
  geocat_arc/ harness/ src/reasoning_project/ scripts/ library.json

Pipeline: governed 3-layer harness with prediction emission ->
submission.json.  attempt_1 = LOO-certified render (measured precision
0.95); attempt_2 = best uncertified partial (graduated-certificate
policy).  No internet, no GPU, deterministic.
"""
import json
import os
import shutil
import subprocess
import sys

SRC = os.environ.get("K_SRC", "/kaggle/input/arc-certified-solver")
def _find_comp():
    """Locate the competition data dir: walk /kaggle/input recursively for a
    json whose name suggests task data ('challenges'/'test'/'sample_
    submission' sibling), skipping our own solver dataset."""
    if os.environ.get("K_COMP"):
        return os.environ["K_COMP"]
    for dirname, _dirs, files in os.walk("/kaggle/input"):
        if "geocat_arc" in dirname or any(
                f.endswith(".tar.gz") for f in files):
            continue                      # our solver dataset, not the comp
        names = [f.lower() for f in files]
        if any(f.endswith(".json") and ("challenge" in f or "test" in f)
               for f in names) or "sample_submission.json" in names:
            return dirname
    raise SystemExit("no competition data dir found under /kaggle/input — "
                     "run the os.walk snippet and check the mounts")

COMP = None  # resolved after SRC staging (needs os.listdir)
WORK = os.environ.get("K_WORK", "/kaggle/working")

# --- stage the code (read-only input -> writable working dir) ---
def _resolve_src():
    """Find the solver ANYWHERE under /kaggle/input: an extracted
    geocat_arc/ tree, or a .tar.gz at any depth (Kaggle nests uploads)."""
    tar_path = None
    for dirname, dirs, files in os.walk("/kaggle/input"):
        if "geocat_arc" in dirs:
            return dirname
        for f in files:
            if f.endswith(".tar.gz") and tar_path is None:
                tar_path = os.path.join(dirname, f)
    if tar_path is None:
        raise SystemExit("solver dataset not found under /kaggle/input — "
                         "is the dataset attached as an Input?")
    import tarfile
    dest = os.path.join(WORK, "src_extracted")
    if not os.path.isdir(os.path.join(dest, "geocat_arc")):
        tarfile.open(tar_path).extractall(dest)
    return dest

SRC = _resolve_src()
COMP = _find_comp()
code = os.path.join(WORK, "solver")
shutil.rmtree(code, ignore_errors=True)   # always stage fresh
shutil.copytree(SRC, code)
os.chdir(code)
os.makedirs("data/arc", exist_ok=True)
for name in os.listdir(COMP):
    if name.endswith(".json"):
        shutil.copy(os.path.join(COMP, name), "data/arc/")
# competition test file plays the 'evaluation challenges' role; solutions
# are absent by design — the harness never needs them to SOLVE (submission
# mode); scoring fields just stay None.
cands = [n for n in os.listdir("data/arc")
         if n.endswith(".json") and "challenge" in n and "sample" not in n]
# the LEADERBOARD scores the TEST challenges — prefer it explicitly
test_files = [n for n in cands if "test" in n]
test_file = sorted(test_files or cands)[0]
print("using task file:", test_file)
if test_file != "arc-agi_evaluation_challenges.json":
    shutil.copy(f"data/arc/{test_file}",
                "data/arc/arc-agi_evaluation_challenges.json")
    if os.path.exists("data/arc/arc-agi_evaluation_solutions.json"):
        os.remove("data/arc/arc-agi_evaluation_solutions.json")
if not os.path.exists("data/arc/arc-agi_evaluation_solutions.json"):
    json.dump({}, open("data/arc/arc-agi_evaluation_solutions.json", "w"))

out_dir = os.path.join(WORK, "run")
os.makedirs(f"{out_dir}/object", exist_ok=True)
lib = "library.json" if os.path.exists("library.json") \
    else "outputs/object_reasoning_promotion_v3/library.json"
shutil.copy(lib, f"{out_dir}/object/library.json")

# --- governed run: leave 45 min of the 12 h for overhead + emission ---
BUDGET_S = int(11.25 * 3600)
env = dict(os.environ)
env["PYTHONPATH"] = code + ":" + os.path.join(code, "src")

subprocess.run([sys.executable, "scripts/run_unified_harness.py",
                "--split", "evaluation", "--workers", str(os.cpu_count()),
                "--out-dir", out_dir, "--run-id", "kaggle",
                "--emit-predictions",
                "--global-budget-s", str(BUDGET_S)],
               check=True, env=env)

subprocess.run([sys.executable, "scripts/make_submission_v2.py",
                f"{out_dir}/progress.jsonl",
                "data/arc/arc-agi_evaluation_challenges.json",
                os.path.join(WORK, "submission.json")],
               check=True, env=env)
print("submission.json written")
