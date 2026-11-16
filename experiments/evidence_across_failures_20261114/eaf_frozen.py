"""Hash check of every stage A and operations-study module this experiment imports, then read-only import access.
Author: Chimdi Walter Ndubuisi

Stage A (experiments/visible_failure_20261113) and the operations study (experiments/core_operations_20261113) are
frozen; their FREEZE.json files hold the sha256 of every file. Before anything is imported from them, the sha256 of
each imported file is compared with stage A's FREEZE.json; a difference stops the run (SystemExit). Their folders are
appended (never prepended) to sys.path and nothing in them is edited.
"""
import hashlib
import json
import os
import sys

ROOT = "/path/to/repository"
STAGE_A_REL = "experiments/visible_failure_20261113"
CORE_REL = "experiments/core_operations_20261113"
STAGE_A_DIR = os.path.join(ROOT, STAGE_A_REL)
CORE_DIR = os.path.join(ROOT, CORE_REL)
STAGE_A_FREEZE = os.path.join(STAGE_A_DIR, "FREEZE.json")
# the modules this experiment imports (stage A first, then the operations study's)
IMPORTED = tuple(STAGE_A_REL + "/" + n for n in ("presets_vf1.py", "frozen.py", "vsearch.py", "consumers.py", "gate.py",
                                                  "library.py", "episode.py")) + \
           tuple(CORE_REL + "/" + n for n in ("dslx.py", "gen.py", "search.py", "presets.py", "core.py"))


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def stage_a_files():
    """{path relative to the repository root: sha256} from stage A's FREEZE.json."""
    with open(STAGE_A_FREEZE) as f:
        return json.load(f)["files"]


def verify_imports(root=None, names=IMPORTED):
    """Return {file: sha256}; raise SystemExit when an imported file differs from stage A's FREEZE.json."""
    root = root or ROOT
    want = stage_a_files()
    got = {}
    for rel in names:
        if rel not in want:
            raise SystemExit("imported module %s is not listed in stage A's FREEZE.json: refusing to run" % rel)
        got[rel] = sha256_file(os.path.join(root, rel))
        if got[rel] != want[rel]:
            raise SystemExit("frozen module %s differs from stage A's FREEZE.json (%s != %s): refusing to run"
                             % (rel, got[rel][:12], want[rel][:12]))
    return got


HASHES = verify_imports()
for _d in (STAGE_A_DIR, CORE_DIR):
    if _d not in sys.path:
        sys.path.append(_d)
