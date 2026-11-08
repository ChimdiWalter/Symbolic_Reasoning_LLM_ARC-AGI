"""Environment of the natural-task growth test: read-only imports of the frozen growth code, the study's write guard.

The study reuses the growth code in `experiments/capability_growth_20261027/cgrow/` (controller, search, schema
language, shared construction core) and A2's arc-dsl search in `experiments/architecture_sweep_20261026/a2/`
without changing any of their files. It imports only modules that need neither the model-code sandbox nor the
growth study's own task files: cgrow.controller, cgrow.search, cgrow.schema, cgrow.lang0, cgrow.probes and
cgrow.selfext_core.

Roots come from the environment (NG_REPO, NG_STUDY, NG_DATA; a package copy on Kaggle) or default to Athe's paths.
Benchmark files are read only; every write goes through check_write, which refuses anything outside this study.
"""
import hashlib
import json
import os
import re
import sys

REPO = os.environ.get("NG_REPO", "/path/to/repository")
STUDY = os.environ.get("NG_STUDY", os.path.join(REPO, "experiments", "natural_growth_20261105"))
DATA = os.environ.get("NG_DATA", "/path/to/benchmark_data/prepared")
CGROW_DIR = os.path.join(REPO, "experiments", "capability_growth_20261027")
SWEEP = os.path.join(REPO, "experiments", "architecture_sweep_20261026")
ARC_DSL = os.path.join(REPO, "outputs", "search_components", "resources_20261026", "github", "arc-dsl")
PACKAGE = os.environ.get("NG_PACKAGE") == "1"

#: never opened or written by this study
DENY = re.compile(r"arc_original|[/\\]re[-_]arc([/\\]|$)|^/tmp/reserved|stepb|step_b|vdcg|gopa.*seal|"
                  r"evaluation_solutions|S_CONFIRM_SEALED|/reserved(/|$)|<companion study folder>|"
                  r"construction_at_scale_20261105", re.I)

for _p in (CGROW_DIR, SWEEP):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import a2                                                   # noqa: E402,F401  (this repository's copy, first)
from a2 import arcdsl as _arcdsl                            # noqa: E402

if PACKAGE:
    _arcdsl.DSL_DIR = ARC_DSL
from cgrow import paths as _cgrow_paths                     # noqa: E402

if PACKAGE:
    _cgrow_paths.REPO, _cgrow_paths.SWEEP = REPO, SWEEP
_cgrow_paths.ensure_import_paths()


class WriteRefused(PermissionError):
    pass


def check_write(path):
    rp = os.path.realpath(path)
    if not rp.startswith(os.path.realpath(STUDY) + os.sep) or DENY.search(rp):
        raise WriteRefused(f"write outside the study folder: {path}")
    return rp


def open_write(path, mode="w"):
    check_write(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return open(path, mode, encoding="utf-8")


def dump(path, obj, indent=1):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open_write(tmp) as f:
        json.dump(obj, f, indent=indent, sort_keys=True, default=list)
    os.replace(check_write(tmp), check_write(path))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha_text(s):
    return hashlib.sha256(s.encode()).hexdigest()


def loaded_sources():
    """Every loaded module of the reused packages with its file (for the run record)."""
    out = {}
    for name, mod in sorted(sys.modules.items()):
        if name.split(".")[0] in ("cgrow", "a2", "ngrow") and getattr(mod, "__file__", None):
            out[name] = os.path.relpath(os.path.realpath(mod.__file__), os.path.realpath(REPO))
    return out
