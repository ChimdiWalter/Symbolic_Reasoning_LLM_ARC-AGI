"""The phase 2 gate. Nothing touches a held half, its test outputs or the ARC-AGI-2 evaluation set unless
`runs/GO_PHASE2` exists and its first two lines are exactly

    protocol_sha256 <sha256 of PROTOCOL.md>
    freeze_sha256 <sha256 of FREEZE.json>

and every file listed in FREEZE.json still has its frozen sha256. The coordinator writes the GO file once. It
authorises one execution of each phase 2 kernel (A, B, then C) and of the scoring on Athe; every output records the
GO's sha256 (STAGES.json). A kernel that fails is resumed from its durable records, never restarted with changed
code, and only with the coordinator's written approval.
"""
import os

from ngrow import env as E

GO = os.path.join(E.STUDY, "runs", "GO_PHASE2")
PROTOCOL = os.path.join(E.STUDY, "PROTOCOL.md")
FREEZE = os.path.join(E.STUDY, "FREEZE.json")


class GateRefused(PermissionError):
    pass


def check_freeze():
    """Every frozen file (repository paths) and every benchmark file (paths under the data root) must still have its
    frozen sha256. In a package copy (Kaggle) the files the package does not carry (records and Athe-side tools,
    listed under "athe_only") are skipped; everything a kernel executes or reads is checked."""
    if not os.path.exists(FREEZE):
        raise GateRefused("no FREEZE.json")
    fr = E.load(FREEZE)
    skip = set(fr.get("athe_only", [])) if E.PACKAGE else set()
    bad = [p for p, h in fr["files_sha256"].items()
           if p not in skip and (not os.path.exists(os.path.join(E.REPO, p)) or
                                 E.sha_file(os.path.join(E.REPO, p)) != h)]
    bad += [p for p, h in fr.get("data_sha256", {}).items() if E.sha_file(os.path.join(E.DATA, p)) != h]
    if bad:
        raise GateRefused("frozen files changed or missing: " + ", ".join(bad))
    return fr


def require_phase2():
    if not os.path.exists(GO):
        raise GateRefused("phase 2 not authorised: no runs/GO_PHASE2 (held halves, their outputs and the ARC-AGI-2 "
                          "evaluation set stay closed in phase 1)")
    with open(GO, encoding="utf-8") as f:
        lines = f.read().splitlines()
    want = [f"protocol_sha256 {E.sha_file(PROTOCOL)}", f"freeze_sha256 {E.sha_file(FREEZE)}"]
    if lines[:2] != want:
        raise GateRefused("GO_PHASE2 does not name the current protocol and freeze digests")
    check_freeze()
    return E.sha_file(GO)
