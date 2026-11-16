"""Read-only access to the frozen operations-study modules, with a hash check at start-up.
Author: Chimdi Walter Ndubuisi

The modules dslx.py, gen.py, search.py, presets.py (and core.py) of experiments/core_operations_20261113 are frozen
(FREEZE.json). They are imported from there, never copied or edited. If one of the four required files differs
from its recorded sha256, the import stops with SystemExit. The folder is appended (not prepended) to sys.path.
"""
import hashlib
import json
import os
import sys

ROOT = "/path/to/repository"
CORE_DIR = ROOT + "/experiments/core_operations_20261113"
REQUIRED = ("dslx.py", "gen.py", "search.py", "presets.py")
ALSO = ("core.py",)


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify(core_dir=None, names=REQUIRED + ALSO):
    """Return {file: sha256}; raise SystemExit when a file differs from FREEZE.json."""
    core_dir = core_dir or CORE_DIR
    with open(os.path.join(core_dir, "FREEZE.json")) as f:
        want = json.load(f)["own_files_sha256"]
    got = {}
    for n in names:
        got[n] = sha256_file(os.path.join(core_dir, n))
        if got[n] != want[n]:
            raise SystemExit("frozen module %s differs from FREEZE.json (%s != %s): refusing to run"
                             % (n, got[n][:12], want[n][:12]))
    return got


HASHES = verify()
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)
