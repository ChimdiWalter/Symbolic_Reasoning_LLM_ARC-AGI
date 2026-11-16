"""Hash check of every frozen file this experiment imports or loads, then read-only import access.
Author: Chimdi Walter Ndubuisi

Stage A (experiments/visible_failure_20261113) and the operations study (experiments/core_operations_20261113) are
frozen; stage A's FREEZE.json holds the sha256 of every file of both. Before anything is imported from the two
folders, the sha256 of each imported module, and of the three data files the frozen loader reads from the
data folder (library text, grammar, families), is compared with stage A's FREEZE.json. A difference stops
the process (SystemExit). The two folders are appended (never prepended) to sys.path and nothing in them is edited.

The list IMPORTED holds every module whose hash is checked here. The modules of this experiment import two of
them: stage A's presets (presets_vf1) and the frozen loader of the operations study (dslx). The originals of the
enumerator and of the generator (search, gen) are imported only by the tests and by check_generator_copy.py, to be
compared with this experiment's copies (search_bl, gen_bl). The other modules of the two studies are not imported
by this experiment (a test asserts it for the modules of the run); their hashes are checked all the same. The
download of the library itself is not read here: it is touched only through the frozen loader (dslx), and its
hashes are checked with the whole table by the runner's freeze check.
"""
import hashlib
import json
import os
import sys

ROOT = "/path/to/repository"
STAGE_A_REL = "experiments/visible_failure_20261113"
CORE_REL = "experiments/core_operations_20261113"
SELF_LESION_REL = "experiments/proposer_20261109/selflesion"
STAGE_A_DIR = os.path.join(ROOT, STAGE_A_REL)
CORE_DIR = os.path.join(ROOT, CORE_REL)
STAGE_A_FREEZE = os.path.join(STAGE_A_DIR, "FREEZE.json")
# the modules this experiment imports (stage A's first, then the operations study's)
IMPORTED = tuple(STAGE_A_REL + "/" + n for n in ("presets_vf1.py", "frozen.py", "vsearch.py", "consumers.py", "gate.py",
                                                  "library.py", "episode.py")) + \
           tuple(CORE_REL + "/" + n for n in ("dslx.py", "gen.py", "search.py", "presets.py", "core.py"))
# the data files the frozen loader reads besides the download (library text, grammar, families)
DATA = tuple(SELF_LESION_REL + "/" + n for n in ("library/LIBRARY.json", "grammar/SYSTEM_GRAMMAR.json",
                                                  "families/FAMILIES.json"))


def sha256_file(path):
    """sha256 of the bytes of a file (the bytes are hashed, never decoded or parsed)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_a_files():
    """{path relative to the repository root: sha256} from stage A's FREEZE.json."""
    with open(STAGE_A_FREEZE) as f:
        return json.load(f)["files"]


def verify_imports(root=None, names=IMPORTED + DATA):
    """Return {file: sha256}; raise SystemExit when a file differs from stage A's FREEZE.json or is not listed in it."""
    root = root or ROOT
    want = stage_a_files()
    got = {}
    for rel in names:
        if rel not in want:
            raise SystemExit("frozen file %s is not listed in stage A's FREEZE.json: refusing to run" % rel)
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            raise SystemExit("frozen file %s does not exist: refusing to run" % rel)
        got[rel] = sha256_file(path)
        if got[rel] != want[rel]:
            raise SystemExit("frozen file %s differs from stage A's FREEZE.json (%s != %s): refusing to run"
                             % (rel, got[rel][:12], want[rel][:12]))
    return got


HASHES = verify_imports()
for _d in (STAGE_A_DIR, CORE_DIR):
    if _d not in sys.path:
        sys.path.append(_d)
