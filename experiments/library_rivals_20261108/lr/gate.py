"""The freeze check and the one-use GO of the library-rivals test (PROTOCOL.md section 8).

GO is the file `GO` in this folder, written by the coordinator, four lines exactly:
    protocol_sha256 <sha256 of PROTOCOL.md>
    freeze_sha256 <sha256 of FREEZE.json>
    primary failure_kept_vs_compression
    nonce <a fresh random hex salt of at least 16 characters>
The GO's digest (which the nonce makes unpredictable) is written into every row, the seal and both markers. Any
held-task row, the seal and the scorer require the GO and an unchanged freeze.
"""
import os
import re

from lr import env as E

GO = os.path.join(E.STUDY, "GO")
FREEZE = os.path.join(E.STUDY, "FREEZE.json")
PROTOCOL = os.path.join(E.STUDY, "PROTOCOL.md")
PRIMARY = "failure_kept_vs_compression"


class GateRefused(RuntimeError):
    pass


def check_freeze(launch=True):
    """Every frozen file and benchmark input must have its frozen digest. The two shared launch scripts
    (launch_sha256) are checked at launch only, so an edit to them during the run cannot stop the scoring."""
    if not os.path.exists(FREEZE):
        raise GateRefused("no FREEZE.json")
    fr = E.load(FREEZE)
    items = list(fr["files_sha256"].items()) + (list(fr.get("launch_sha256", {}).items()) if launch else [])
    bad = [p for p, h in items
           if not os.path.exists(os.path.join(E.REPO, p)) or E.sha_file(os.path.join(E.REPO, p)) != h]
    bad += [p for p, h in fr["data_sha256"].items() if E.sha_file(os.path.join(E.DATA, p)) != h]
    if bad:
        raise GateRefused("frozen files changed or missing: " + ", ".join(bad[:8]))
    return fr


def check_loaded_modules(fr=None):
    """Every module loaded from inside the repository must be a frozen file with its frozen digest."""
    import sys
    fr = fr or E.load(FREEZE)
    bad = []
    for name, m in list(sys.modules.items()):
        f = getattr(m, "__file__", None)
        if not f:
            continue
        rp = os.path.realpath(f)
        if not rp.startswith(os.path.realpath(E.REPO) + os.sep):
            continue
        rel = os.path.relpath(rp, E.REPO)
        if rel not in fr["files_sha256"] or E.sha_file(rp) != fr["files_sha256"][rel]:
            bad.append(rel)
    if bad:
        raise GateRefused("loaded modules outside the freeze or changed: " + ", ".join(sorted(bad)[:8]))
    return True


def require_go(at_scoring=False):
    if not os.path.exists(GO):
        raise GateRefused("no GO file: held tasks stay closed")
    lines = open(GO, encoding="utf-8").read().splitlines()
    want = [f"protocol_sha256 {E.sha_file(PROTOCOL)}", f"freeze_sha256 {E.sha_file(FREEZE)}", f"primary {PRIMARY}"]
    if len(lines) != 4 or lines[:3] != want or not re.fullmatch(r"nonce [0-9a-f]{16,}", lines[3]):
        raise GateRefused("GO does not name this protocol, this freeze and the primary with a nonce line")
    fr = check_freeze(launch=not at_scoring)
    if os.path.realpath(E.DATA) != os.path.realpath(fr["data_root"]):
        raise GateRefused("the data root differs from the frozen one")
    return E.sha_file(GO)
