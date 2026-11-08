"""Environment of the guided-construction test: paths, read-only imports of the frozen studies, the write guard and
the read guard.

Reused without change, by import only: the frozen object-level step (`objgrow`, freeze version 2), study A's data,
scorer and statistics (`ngrow`), study B's seed-independent G0 builder and donor rule (`ngb.ops`, `ngb.object_arm`),
the growth core (`cgrow`) and A2's arc-dsl search (`a2`). Roots come from the environment (GC_REPO, GC_STUDY; a
package copy on Kaggle sets them) or default to Athe's paths.
"""
import hashlib
import json
import os
import re
import sys

REPO = os.environ.get("GC_REPO", "/path/to/repository")
STUDY = os.environ.get("GC_STUDY", os.path.join(REPO, "experiments", "guided_construction_20261106"))
OG_STUDY = os.path.join(REPO, "experiments", "object_growth_20261105")
NG_STUDY = os.path.join(REPO, "experiments", "natural_growth_20261105")
NGB_STUDY = os.path.join(REPO, "experiments", "natural_growth_b_20261105")
for _k, _v in (("OG_REPO", REPO), ("OG_STUDY", OG_STUDY), ("NG_REPO", REPO), ("NG_STUDY", NG_STUDY),
               ("NGB_REPO", REPO), ("NGB_STUDY", NGB_STUDY)):
    os.environ.setdefault(_k, _v)
for _p in (NGB_STUDY, OG_STUDY, STUDY):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from objgrow import env as OE                                 # noqa: E402  (sets up ngrow, cgrow and a2 imports)

PACKAGE = os.environ.get("NG_PACKAGE") == "1"
DATA = OE.NE.DATA

#: never opened by this study's development code (the scorer opens solution files only behind the GO, by path)
DENY = re.compile(r"arc_original|[/\\]re[-_]arc([/\\]|$)|^/tmp/reserved|stepb|step_b|vdcg|gopa.*seal|"
                  r"evaluation_solutions|evaluation_challenges|S_CONFIRM_SEALED|/reserved(/|$)|"
                  r"<companion study folder>|construction_at_scale_20261105|solutions_scorer_only|"
                  r"natural_growth_b_20261105[/\\](runs|checks|rehearsal|records|reviews|logs|power|feasibility)",
                  re.I)


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


def g0_builder():
    """Study B's seed-independent G0 builder (A2's enumeration order made independent of the hash seed)."""
    from ngb import ops as NOPS
    return NOPS.G0Builder()
