"""Paths and boundaries of the capability-growth experiment (Test I).

Writes go only under this experiment's folder, plus append-only rows (family CGROW) in the architecture campaign's
shared RUN_LEDGER.jsonl. Task data are read only through the campaign's split-guarded loader
(experiments/architecture_sweep_20261026/harness/data.py): S_train and S_select only; S_confirm is sealed and
ARC_eval_dev is never read by this experiment. Other components are imported read-only, never edited.
"""
import os
import re
import sys

REPO = "/path/to/repository"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # experiments/capability_growth_20261027
SWEEP = os.path.join(REPO, "experiments", "architecture_sweep_20261026")
HYBRID = os.path.join(REPO, "kaggle", "hybrid_2026")
LEDGER = os.path.join(SWEEP, "RUN_LEDGER.jsonl")
GPU0_LOCK = os.path.join(REPO, "outputs", "locks", "gpu0.lock")
CPU_SLOT = os.path.join(REPO, "scripts", "with_cpu_slot.sh")
RUNS = os.path.join(HERE, "runs")
PARTITIONS = os.path.join(HERE, "partitions")
REGISTRY_DIR = os.path.join(HERE, "registry")
REPORTS = os.path.join(HERE, "reports")
EVALUATOR_DIR = os.path.join(HERE, "evaluator_only")       # removed-capability identities and references live here
MODEL_DIR = os.path.join(REPO, "outputs", "hybrid_llm_writer", "downloads", "model_qwen3_4b_instruct_2507_cdbee75")
PY_GPU = "python3"    # transformers 5.14 + jinja2 3.1 (the project venv's
#                                                            jinja2 3.0.3 cannot render chat templates); inference only
PY_CPU = "python3"

#: never opened by this experiment (sealed, protected or out of scope)
DENY = re.compile(r"arc_original|[/\\]re[-_]arc([/\\]|$)|^/tmp/reserved|stepb|step_b|vdcg|gopa.*seal|"
                  r"evaluation_solutions|S_CONFIRM_SEALED|/reserved(/|$)", re.I)


class WriteRefused(PermissionError):
    pass


def check_write(path):
    rp = os.path.realpath(path)
    if rp == os.path.realpath(LEDGER):
        return rp
    if not rp.startswith(os.path.realpath(HERE) + os.sep) or DENY.search(rp):
        raise WriteRefused(f"write outside the experiment folder: {path}")
    return rp


def open_write(path, mode="w"):
    check_write(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return open(path, mode, encoding="utf-8")


def ensure_import_paths():
    """A2's tree IR and search, the campaign harness, and the hybrid's gridfn sandbox and writer (read-only)."""
    for p in (HYBRID, SWEEP, HERE):
        if p not in sys.path:
            sys.path.insert(0, p)
