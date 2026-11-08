"""The one-shot gate of the guided-construction test. No held task, held test output, ARC-AGI-2 evaluation task or
solution is touched unless `runs/GO` exists and its first two lines are exactly
    protocol_sha256 <sha256 of PROTOCOL.md>
    freeze_sha256 <sha256 of FREEZE.json>
and every file listed in FREEZE.json still has its frozen sha256 (in a Kaggle package, the files the package does
not carry, listed under "athe_only", are skipped). The coordinator writes the GO once; it authorises one execution of
the held kernels and one scoring. Rehearsal mode (GC_REHEARSAL=1, smoke tests on source tasks only) reads
`runs/REHEARSAL_GO` instead and never opens a held task or any solution.
The scorer also takes an exclusive marker (`runs/SCORED`, created with O_EXCL), so the scoring runs once.
"""
import os

from gcon import env as E

REHEARSAL = os.environ.get("GC_REHEARSAL") == "1"
GO = os.path.join(E.STUDY, "runs", "REHEARSAL_GO" if REHEARSAL else "GO")
PROTOCOL = os.path.join(E.STUDY, "PROTOCOL.md")
FREEZE = os.path.join(E.STUDY, "FREEZE.json")
MARKER = os.path.join(E.STUDY, "runs", "SCORED")


class GateRefused(PermissionError):
    pass


def check_freeze():
    if not os.path.exists(FREEZE):
        raise GateRefused("no FREEZE.json")
    fr = E.load(FREEZE)
    skip = set(fr.get("athe_only", [])) if E.PACKAGE else set()
    bad = [p for p, h in fr["files_sha256"].items()
           if p not in skip and (not os.path.exists(os.path.join(E.REPO, p)) or
                                 E.sha_file(os.path.join(E.REPO, p)) != h)]
    bad += ["data/" + p for p, h in fr.get("data_sha256", {}).items()
            if not os.path.exists(os.path.join(E.DATA, p)) or E.sha_file(os.path.join(E.DATA, p)) != h]
    if bad:
        raise GateRefused("frozen files changed or missing: " + ", ".join(sorted(bad)[:20]))
    return fr


def read_go():
    if not os.path.exists(GO):
        raise GateRefused(f"not authorised: no {os.path.relpath(GO, E.STUDY)} (held halves, their outputs and the "
                          "ARC-AGI-2 evaluation set stay closed)")
    if not os.path.exists(FREEZE):
        raise GateRefused("no FREEZE.json")
    with open(GO, encoding="utf-8") as f:
        lines = f.read().splitlines()
    want = [f"protocol_sha256 {E.sha_file(PROTOCOL)}", f"freeze_sha256 {E.sha_file(FREEZE)}"]
    if lines[:2] != want:
        raise GateRefused(f"{os.path.relpath(GO, E.STUDY)} does not name this protocol and this freeze")
    return lines


def require_go():
    """Returns the GO's sha256 after every check passes (the GO first, then every frozen digest)."""
    read_go()
    check_freeze()
    return E.sha_file(GO)


def take_marker():
    """The scorer's exclusive marker; a second scoring is refused."""
    if REHEARSAL:
        raise GateRefused("rehearsal mode never scores")
    require_go()
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    try:
        fd = os.open(E.check_write(MARKER), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    except FileExistsError:
        raise GateRefused("already scored: runs/SCORED exists") from None
    return fd
