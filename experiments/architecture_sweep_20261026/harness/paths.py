"""Paths, the read allowlist and the deny-list of the campaign.

Policy-side code reads ARC challenge files (demonstrations and test inputs) through `open_allowed`; answer files are
reachable only from `harness/scorer.py`, which runs as a separate process. The re-arc archive `arc_original.zip`
(ARC-AGI-1 evaluation tasks WITH test outputs; six are ARC-AGI-2 public-evaluation tasks) and any path into a re-arc
folder are refused for every caller. Nothing here walks a directory tree.
"""
import os
import re
import sys

REPO = "/path/to/repository"
EXP = os.path.join(REPO, "experiments", "architecture_sweep_20261026")
HYBRID = os.path.join(REPO, "kaggle", "hybrid_2026")
DOWNLOADS = "<ARC data folder>"
TRAIN_CHALLENGES = os.path.join(DOWNLOADS, "arc-agi_training_challenges.json")
TRAIN_SOLUTIONS = os.path.join(DOWNLOADS, "arc-agi_training_solutions.json")      # source labels (S_train/S_select)
EVAL_CHALLENGES = os.path.join(DOWNLOADS, "arc-agi_evaluation_challenges.json")
EVAL_SOLUTIONS = os.path.join(DOWNLOADS, "arc-agi_evaluation_solutions.json")      # scorer process only
LOCKS = os.path.join(REPO, "outputs", "locks")
GPU0_LOCK = os.path.join(LOCKS, "gpu0.lock")
RUNS = os.path.join(EXP, "runs")
LEDGER = os.path.join(EXP, "RUN_LEDGER.jsonl")
PYTHON = "python3"          # torch 2.13 + CUDA 13.0; runs CORA's executor unchanged

#: refused for every caller (the leaked re-arc archive and re-arc folders; sealed or protected roots)
DENY = re.compile(r"arc_original|[/\\]re[-_]arc([/\\]|$)|^/tmp/reserved|stepb|step_b|vdcg|gopa.*seal", re.I)
#: answer files: the scorer process only
ANSWERS = {os.path.realpath(EVAL_SOLUTIONS), os.path.realpath(TRAIN_SOLUTIONS)}
#: what policy-side code may open (exact files or directory prefixes)
FRESH40_FILE = os.path.join(HYBRID, "mechanism_test", "FROZEN_SAMPLE.json")      # ids only
ALLOW_FILES = {os.path.realpath(TRAIN_CHALLENGES), os.path.realpath(EVAL_CHALLENGES), os.path.realpath(FRESH40_FILE)}
ALLOW_PREFIXES = (os.path.realpath(EXP) + os.sep,)


class AccessDenied(PermissionError):
    pass


def check(path, role="policy"):
    """Raise AccessDenied unless `role` may read `path`. Roles: policy (default), source_labels, scorer."""
    rp = os.path.realpath(path)
    if DENY.search(path) or DENY.search(rp):
        raise AccessDenied(f"denied path: {path}")
    if rp in ANSWERS:
        if role == "scorer":
            return rp
        if role == "source_labels" and rp == os.path.realpath(TRAIN_SOLUTIONS):
            return rp
        raise AccessDenied(f"answer file outside the scorer: {path}")
    if rp in ALLOW_FILES or rp.startswith(ALLOW_PREFIXES):
        return rp
    raise AccessDenied(f"not on the allowlist: {path}")


def open_allowed(path, role="policy", mode="r"):
    if "w" in mode or "a" in mode:
        rp = os.path.realpath(path)
        if not rp.startswith(ALLOW_PREFIXES) or DENY.search(rp):
            raise AccessDenied(f"write outside the campaign folder: {path}")
        return open(path, mode, encoding="utf-8")
    return open(check(path, role), mode, encoding="utf-8")


def ensure_import_paths():
    """CORA's packages and the hybrid's llm_writer (read-only imports; nothing there is edited)."""
    for p in (os.path.dirname(EXP), EXP, HYBRID, REPO):
        if p not in sys.path:
            sys.path.insert(0, p)
