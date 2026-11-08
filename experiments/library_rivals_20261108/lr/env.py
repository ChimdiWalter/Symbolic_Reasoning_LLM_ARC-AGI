"""Paths and the write guard of the library-rivals test (experiments/library_rivals_20261108/).

Reused read-only: study A's natural-task code (experiments/natural_growth_20261105/ngrow: the benchmarks, the split,
G0, the structure productions, the statistics), the growth code it puts on the path (cgrow, a2), the object-level
builder's frozen code (experiments/object_growth_20261105/objgrow) and study B's frozen records (registries, the
source-half discovery records). Nothing in those folders is changed. Every write goes through check_write, which
refuses anything outside this study's folder.
"""
import hashlib
import json
import os
import sys

REPO = "/path/to/repository"
STUDY = os.path.join(REPO, "experiments", "library_rivals_20261108")
STUDY_A = os.path.join(REPO, "experiments", "natural_growth_20261105")
STUDY_B = os.path.join(REPO, "experiments", "natural_growth_b_20261105")
OBJ = os.path.join(REPO, "experiments", "object_growth_20261105")
DATA_ROOT = "/path/to/benchmark_data/prepared"
# fixed, not defaults: a shell variable must not redirect the split, the data or the builder's code
os.environ["NG_REPO"] = REPO
os.environ["NG_STUDY"] = STUDY_A
os.environ["NG_DATA"] = DATA_ROOT
os.environ["OG_REPO"] = REPO
os.environ["OG_STUDY"] = OBJ
os.environ.pop("NG_PACKAGE", None)
for p in (STUDY_A, OBJ):
    if p not in sys.path:
        sys.path.insert(0, p)
from ngrow import env as EA                                    # noqa: E402  (sets up cgrow and a2 on sys.path)

DATA = EA.DATA
if os.path.realpath(DATA) != os.path.realpath(DATA_ROOT):
    raise RuntimeError("the benchmark data root is not the frozen one")


class WriteRefused(PermissionError):
    pass


def check_write(path):
    rp = os.path.realpath(path)
    if not (rp == os.path.realpath(STUDY) or rp.startswith(os.path.realpath(STUDY) + os.sep)):
        raise WriteRefused(f"write outside the study folder refused: {path}")
    return rp


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(path):
    with open(path, "rb") as f:
        return sha_bytes(f.read())


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    check_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True, default=list)
    os.replace(tmp, path)


def open_write(path, mode="w"):
    check_write(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, mode, encoding="utf-8")
