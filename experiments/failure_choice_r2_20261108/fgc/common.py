"""Shared setup of the failure-guided choice test, revision 2: the construction-at-scale machinery, imported read-only.

The study reuses, unchanged, the construction test at scale (experiments/construction_at_scale_20261105/cas/) and,
through it, S1's code (cgrow: base search, failure record, typed-hole construction) and A2's arc-dsl search. Its
`cas.env` is pointed at THIS folder (CAS_STUDY), so every write stays here, and `E.use_world(wd)` points S1's folder
constants at one of the three world copies in runs/worlds/ (copied byte for byte from the construction test's
generated worlds: task files, removed sets, controller records; no other output).
"""
import hashlib
import json
import os
import sys

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(STUDY))
CAS_DIR = os.path.join(REPO, "experiments", "construction_at_scale_20261105")
os.environ.setdefault("CAS_STUDY", STUDY)
if CAS_DIR not in sys.path:
    sys.path.insert(0, CAS_DIR)

from cas import env as E                                                                   # noqa: E402
from cgrow import experiment as X, controller as CT, search as S, schema as SG, s1        # noqa: E402
from cgrow import evaluate as EV                                                           # noqa: E402
from a2 import arcdsl as D                                                                 # noqa: E402

WORLDS = ("W1", "W2", "W3")
INTERVENTIONS = ("search", "view", "construct")  # the bank: deeper search, alternative object views, construction
CAUSE_FIX = {"search": "search", "view": "view", "operation": "construct"}
#: the four alternative object views the view intervention adds (arc-dsl objects(grid, univalued, diagonal,
#: without_bg) flag sets attested in A2's S_train corpus besides the most common (True, False, True))
VIEWS = {"OBJS_TFF": (True, False, False), "OBJS_TTT": (True, True, True), "OBJS_FTT": (False, True, True),
         "OBJS_FFT": (False, False, True)}
DEFAULT_VIEW = (True, False, True)


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    E.dump(path, obj)


def world_dir(w):
    return os.path.join(STUDY, "runs", "worlds", w)


def config():
    return load(os.path.join(STUDY, "config", "STUDY_CONFIG.json"))


def grid(x):
    return D.to_grid(x)


def as_lists(g):
    return [list(r) for r in g]
