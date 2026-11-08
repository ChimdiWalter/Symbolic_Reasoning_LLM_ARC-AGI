"""The one-shot gate of study B. Nothing touches a held half, a held test output or the ARC-AGI-2 evaluation set
unless `runs/GO` exists and its first three lines are exactly

    protocol_sha256 <sha256 of PROTOCOL.md>
    freeze_sha256 <sha256 of FREEZE.json>
    primary <arm5_vs_arm4 | arm2_vs_arm1>

every file listed in FREEZE.json still has its frozen sha256, and, when the third line names arm 5, the
object-growth slot of FREEZE.json is filled (code_sha256 and the files' digests) and the contract in the
configuration is set (module, function, cost). The third line applies the pre-registered rule (PROTOCOL.md section
7). The coordinator writes the GO once; it authorises one execution of the phase 2 kernels and of the scoring.
"""
import os

from ngb import env as E

GO = os.path.join(E.STUDY, "rehearsal", "REHEARSAL_GO") if E.REHEARSAL else os.path.join(E.STUDY, "runs", "GO")
REHEARSAL_DATA = os.path.join(E.STUDY, "rehearsal", "REHEARSAL_DATA.json")
PROTOCOL = os.path.join(E.STUDY, "PROTOCOL.md")
FREEZE = os.path.join(E.STUDY, "FREEZE.json")
CONFIG = os.path.join(E.STUDY, "config", "STUDY_CONFIG.json")
PRIMARIES = ("arm5_vs_arm4", "arm2_vs_arm1")


class GateRefused(PermissionError):
    pass


def frozen_hash(rel):
    """The frozen sha256 of a repository path, or None when the path is not frozen."""
    return E.load(FREEZE)["files_sha256"].get(rel) if os.path.exists(FREEZE) else None


def check_freeze():
    """Every frozen file (repository paths) and every benchmark file (paths under the data root) must still have its
    frozen sha256. In a package copy (Kaggle) the files the package does not carry (records and Athe-side tools,
    listed under "athe_only") are skipped; everything a kernel executes or reads is checked. The object-growth
    files, once the slot is filled, are checked too."""
    if not os.path.exists(FREEZE):
        raise GateRefused("no FREEZE.json")
    fr = E.load(FREEZE)
    skip = set(fr.get("athe_only", [])) if E.PACKAGE else set()
    bad = [p for p, h in fr["files_sha256"].items()
           if p not in skip and (not os.path.exists(os.path.join(E.REPO, p)) or
                                 E.sha_file(os.path.join(E.REPO, p)) != h)]
    if E.REHEARSAL:
        bad += rehearsal_data_problems()
    else:
        bad += [p for p, h in fr.get("data_sha256", {}).items() if E.sha_file(os.path.join(E.DATA, p)) != h]
    for p, h in ((fr.get("object_growth") or {}).get("files_sha256") or {}).items():
        if not os.path.exists(os.path.join(E.REPO, p)) or E.sha_file(os.path.join(E.REPO, p)) != h:
            bad.append(p)
    if bad:
        raise GateRefused("frozen files changed or missing: " + ", ".join(bad))
    return fr


def rehearsal_data_problems():
    """Rehearsal mode: the data root and the stand-in evaluation file must be the rehearsal package's (digests in
    rehearsal/REHEARSAL_DATA.json), and the data must hold no held task of the real split."""
    if not os.path.exists(REHEARSAL_DATA):
        return ["rehearsal/REHEARSAL_DATA.json missing"]
    rd = E.load(REHEARSAL_DATA)
    bad = [p for p, h in rd["data_sha256"].items() if E.sha_file(os.path.join(E.DATA, p)) != h]
    st = os.path.join(E.STUDY, "rehearsal", "arc2_standin_challenges.json")
    if not os.path.exists(st) or E.sha_file(st) != rd["arc2_standin_sha256"]:
        bad.append("rehearsal stand-in evaluation file")
    for b in ("concept_arc", "mini_arc", "1d_arc"):
        real_held = {t for _, _, t in E.REAL_HALF("held", (b,))}
        ids = set(E.load(os.path.join(E.DATA, b, "real.json")))
        if ids & real_held:
            bad.append(f"{b}: the rehearsal data hold {len(ids & real_held)} held tasks")
    return bad


def object_slot_filled(fr):
    """The freeze slot carries the builder's code digest and file digests, and the configuration names the contract
    (module, the three functions, the registries and the cost rule)."""
    slot = fr.get("object_growth") or {}
    og = (E.load(CONFIG).get("object_growth") or {}) if os.path.exists(CONFIG) else {}
    fns = og.get("functions") or {}
    return bool(slot.get("code_sha256")) and bool(slot.get("files_sha256")) and \
        bool(og.get("module") and og.get("registries") and og.get("cost")) and \
        all(fns.get(k) for k in ("ops", "reuse", "construction"))


def read_go():
    if not os.path.exists(GO):
        raise GateRefused(f"not authorised: no {os.path.relpath(GO, E.STUDY)} (held halves, their outputs and the "
                          "ARC-AGI-2 evaluation set stay closed)")
    with open(GO, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if len(lines) < 3 or not lines[2].startswith("primary ") or lines[2].split(" ", 1)[1] not in PRIMARIES:
        raise GateRefused("runs/GO must name a valid primary on its third line")
    return lines


def primary():
    return read_go()[2].split(" ", 1)[1]


def require_go():
    """Returns the GO's sha256 after every check passed."""
    lines = read_go()
    want = [f"protocol_sha256 {E.sha_file(PROTOCOL)}", f"freeze_sha256 {E.sha_file(FREEZE)}"]
    if lines[:2] != want:
        raise GateRefused("runs/GO does not name the current protocol and freeze digests")
    fr = check_freeze()
    if lines[2].split(" ", 1)[1] == "arm5_vs_arm4" and not object_slot_filled(fr):
        raise GateRefused("arm 5 cannot be the primary: the object-growth slot of FREEZE.json is empty or the "
                          "contract in the configuration is not set")
    return E.sha_file(GO)
