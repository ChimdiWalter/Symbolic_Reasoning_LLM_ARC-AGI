"""Environment of the specification-reading guide test: paths, read-only imports of the frozen object-level step
(objgrow) and of the guided-construction test's engine, features, models, policies and simulation (gcon), and this
study's write guard. Roots come from SG_REPO and SG_STUDY or default to Athe's paths."""
import hashlib
import json
import os
import re
import sys

REPO = os.environ.get("SG_REPO", "/path/to/repository")
STUDY = os.environ.get("SG_STUDY", os.path.join(REPO, "experiments", "spec_guide_20261108"))
GC_STUDY = os.path.join(REPO, "experiments", "guided_construction_20261106")
os.environ.setdefault("GC_REPO", REPO)
os.environ.setdefault("GC_STUDY", GC_STUDY)
for _p in (GC_STUDY, STUDY):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from gcon import env as GE                                     # noqa: E402  (objgrow, ngrow, cgrow, a2 imports)

ARC_TRAIN = os.path.join(REPO, "outputs", "score_first", "data", "arc-agi_training_challenges.json")
ARC_TRAIN_SHA256 = "779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5"

DENY = re.compile(r"arc_original|[/\\]re[-_]arc([/\\]|$)|^/tmp/reserved|stepb|step_b|vdcg|evaluation_solutions|"
                  r"evaluation_challenges|training_solutions|solutions_scorer_only|S_CONFIRM_SEALED|/reserved(/|$)|"
                  r"natural_growth_b_20261105[/\\](runs|checks|rehearsal|records|reviews|logs)", re.I)


class WriteRefused(PermissionError):
    pass


def check_write(path):
    rp = os.path.realpath(path)
    if not rp.startswith(os.path.realpath(STUDY) + os.sep) or DENY.search(rp):
        raise WriteRefused(f"write outside the study folder: {path}")
    return rp


def check_read(path):
    if DENY.search(os.path.realpath(path)):
        raise PermissionError(f"refused: {path}")
    return path


def open_write(path, mode="w"):
    check_write(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return open(path, mode, encoding="utf-8")


def dump(path, obj, indent=None):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open_write(tmp) as f:
        json.dump(obj, f, indent=indent, sort_keys=True, default=list)
    os.replace(check_write(tmp), check_write(path))


def load(path):
    with open(check_read(path), encoding="utf-8") as f:
        return json.load(f)


def sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha_text(s):
    return hashlib.sha256(s.encode()).hexdigest()
