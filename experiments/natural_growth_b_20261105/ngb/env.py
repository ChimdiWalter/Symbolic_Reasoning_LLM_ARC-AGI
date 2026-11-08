"""Environment of the library-transfer test (study B): paths, read-only reuse of study A's code and the growth code,
and this study's write guard.

Reused read-only: `experiments/natural_growth_20261105/ngrow/` (benchmark loading, the split, the plug-in for the
full G0, analysis) and `experiments/capability_growth_20261027/cgrow/` (search, gates). Nothing in those folders is
changed. Every write goes through check_write, which refuses anything outside this study's folder.
Roots come from the environment (NGB_REPO, NGB_STUDY; a package copy on Kaggle) or default to Athe's paths; the
benchmark root and package mode are study A's (NG_DATA, NG_PACKAGE).
"""
import hashlib
import json
import os
import sys

REPO = os.environ.get("NGB_REPO", os.environ.get("NG_REPO",
                                                  "/path/to/repository"))
STUDY = os.environ.get("NGB_STUDY", os.path.join(REPO, "experiments", "natural_growth_b_20261105"))
STUDY_A = os.environ.get("NG_STUDY", os.path.join(REPO, "experiments", "natural_growth_20261105"))
os.environ.setdefault("NG_REPO", REPO)
os.environ.setdefault("NG_STUDY", STUDY_A)
if STUDY_A not in sys.path:
    sys.path.insert(0, STUDY_A)
from ngrow import env as EA                                   # noqa: E402  (sets up cgrow and a2 on sys.path)

DATA = EA.DATA
PACKAGE = EA.PACKAGE
CGROW_DIR = EA.CGROW_DIR

#: Rehearsal mode (amendment 3): the real kernel path on source tasks standing in for the held halves. Set only by the
#: rehearsal kernels (NGB_REHEARSAL=1). The held half is replaced by the source half for every caller of
#: ngrow.data.half; the data root holds source tasks only (checked by the gate); the GO file is runs/REHEARSAL_GO.
REHEARSAL = os.environ.get("NGB_REHEARSAL") == "1"
from ngrow import data as _DT                                 # noqa: E402

REAL_HALF = _DT.half
if REHEARSAL:
    def _rehearsal_half(name, benches=_DT.BENCHMARKS):
        return REAL_HALF("source" if name == "held" else name, benches)
    _DT.half = _rehearsal_half


class WriteRefused(PermissionError):
    pass


def check_write(path):
    rp = os.path.realpath(path)
    if not rp.startswith(os.path.realpath(STUDY) + os.sep) or EA.DENY.search(rp):
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
