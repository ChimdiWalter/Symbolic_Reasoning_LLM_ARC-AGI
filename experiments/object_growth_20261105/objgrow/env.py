"""Environment of the object-level construction step: read-only imports of the frozen studies, this study's write
guard, and the data rules.

Reused without change, by import only: the natural-task growth test's adapter (`ngrow`: data, split, G0 builder,
natural plug-in, scorer), the growth core (`cgrow`: search, construction core, probes) and A2's arc-dsl search
(`a2`). Development data: the SOURCE halves of the three benchmarks (ngrow.data.half("source")) and ARC training
tasks of the project's S_train and S_select splits; the held halves, their test outputs and the ARC-AGI-2
evaluation set are never opened (ngrow's gate refuses them; DENY below refuses the paths outright).
"""
import hashlib
import json
import os
import re
import sys

REPO = os.environ.get("OG_REPO", "/path/to/repository")
STUDY = os.environ.get("OG_STUDY", os.path.join(REPO, "experiments", "object_growth_20261105"))
NG_DIR = os.path.join(REPO, "experiments", "natural_growth_20261105")
CGROW_DIR = os.path.join(REPO, "experiments", "capability_growth_20261027")
SWEEP = os.path.join(REPO, "experiments", "architecture_sweep_20261026")
CONTROLLER_RECORDS = [os.path.join(NG_DIR, "feasibility", f"controller_source_shard{i}.jsonl") for i in (0, 1)]

#: never opened or written by this study
DENY = re.compile(r"arc_original|[/\\]re[-_]arc([/\\]|$)|^/tmp/reserved|stepb|step_b|vdcg|gopa.*seal|"
                  r"evaluation_solutions|evaluation_challenges|S_CONFIRM_SEALED|/reserved(/|$)|"
                  r"<companion study folder>|construction_at_scale_20261105|solutions_scorer_only", re.I)

for _p in (NG_DIR, CGROW_DIR, SWEEP):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from ngrow import env as NE                                   # noqa: E402,F401  (import paths, G0, data rules)


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


def dump(path, obj, indent=1):
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


def grid(g):
    return tuple(tuple(int(v) for v in r) for r in g)


def controller_records(bench):
    """The growth controller's phase 1 records of one benchmark's source half (read-only reuse)."""
    recs = {}
    for p in CONTROLLER_RECORDS:
        with open(check_read(p), encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    if r["bench"] == bench:
                        recs[r["task"]] = r
    return recs
