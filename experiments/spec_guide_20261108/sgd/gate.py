"""The one-shot gate of the specification-reading guide test (salt custody, as in the day's other reviewed tests).

The coordinator's GO file (runs/GO) is committed alone, after the freeze, and reads:
    GO
    study: spec_guide_20261108
    freeze_commit: <the last commit that changed FREEZE.json>
    freeze_json_sha256: <sha256 of FREEZE.json>
    pre_run_review: <commit of the pre-run review>
    nonce: <a fresh 64-hex nonce>
The SALT is the sha256 of the committed GO file's bytes; the held tasks are drawn from it (held families on held-pool
grids, both reserved since DESIGN_NOTE.md and never used in development), so they cannot exist before the GO.

require_go() (everywhere): the GO starts with the line GO, names this FREEZE.json's sha256 and a 64-hex nonce, and
every file listed in FREEZE.json has its frozen sha256 (inside the Kaggle package, the files the package does not
carry, listed as athe_only, are skipped).
git_checks() (Athe only: before the final package is built, and before scoring): the GO is committed at HEAD and
unchanged since its first commit (one commit touched it), and its freeze commit is the last commit on HEAD that
changed FREEZE.json, whose content there equals the current file.
Rehearsal mode (SG_REHEARSAL=1, smoke tests only) reads runs/REHEARSAL_GO, never generates a held family or uses the
held pool, and writes under runs/rehearsal_held/.
"""
import hashlib
import json
import os
import subprocess

from sgd import env as E

REHEARSAL = os.environ.get("SG_REHEARSAL") == "1"
GO = os.path.join(E.STUDY, "runs", "REHEARSAL_GO" if REHEARSAL else "GO")
PROTOCOL = os.path.join(E.STUDY, "PROTOCOL.md")
FREEZE = os.path.join(E.STUDY, "FREEZE.json")
MARKER = os.path.join(E.STUDY, "runs", "REHEARSAL_SCORED" if REHEARSAL else "SCORED")


class GateRefused(PermissionError):
    pass


def check_freeze():
    if not os.path.exists(FREEZE):
        raise GateRefused("no FREEZE.json")
    fr = E.load(FREEZE)
    skip = set(fr.get("athe_only", [])) if os.environ.get("SG_PACKAGE") == "1" else set()
    bad = [p for p, h in fr["files_sha256"].items()
           if p not in skip and (not os.path.exists(os.path.join(E.REPO, p)) or
                                 E.sha_file(os.path.join(E.REPO, p)) != h)]
    if bad:
        raise GateRefused("frozen files changed or missing: " + ", ".join(sorted(bad)[:20]))
    return fr


def read_go():
    """The GO's fields after the format checks."""
    if not os.path.exists(GO):
        raise GateRefused(f"not authorised: no {os.path.relpath(GO, E.STUDY)} (held families, the held pool and the "
                          "solutions stay closed)")
    if not os.path.exists(FREEZE):
        raise GateRefused("no FREEZE.json")
    lines = open(GO, "rb").read().decode("utf-8").splitlines()
    if not lines or lines[0] != "GO":
        raise GateRefused("the GO file does not start with the line GO")
    f = dict(l.split(": ", 1) for l in lines[1:] if ": " in l)
    if f.get("freeze_json_sha256") != E.sha_file(FREEZE):
        raise GateRefused("the GO names a different FREEZE.json")
    nonce = f.get("nonce", "")
    if len(nonce) != 64 or any(ch not in "0123456789abcdef" for ch in nonce):
        raise GateRefused("the GO's nonce is not 64 hex characters")
    if len(f.get("freeze_commit", "")) != 40:
        raise GateRefused("the GO does not name a freeze commit")
    return f


def require_go():
    """The salt (the sha256 of the GO file) after every check that holds without git."""
    read_go()
    check_freeze()
    return E.sha_file(GO)


def git(*a):
    return subprocess.run(["git", "-C", E.STUDY] + list(a), capture_output=True)


def git_checks():
    """Athe only: the GO committed at HEAD, unchanged since its first commit, and its freeze commit the last commit
    on HEAD that changed FREEZE.json."""
    f = read_go()
    rel = os.path.relpath(GO, E.REPO)
    go = open(GO, "rb").read()
    if git("show", f"HEAD:{rel}").stdout != go:
        raise GateRefused("the GO is not committed at HEAD or differs from it")
    if len(git("log", "--format=%H", "HEAD", "--", GO).stdout.decode().split()) != 1:
        raise GateRefused("the GO was changed after its first commit: the first committed GO is final")
    fz = open(FREEZE, "rb").read()
    last = git("log", "-n", "1", "--format=%H", "HEAD", "--", FREEZE).stdout.decode().strip()
    frel = os.path.relpath(FREEZE, E.REPO)
    if f["freeze_commit"] != last or git("show", f"{last}:{frel}").stdout != fz:
        raise GateRefused("the GO's freeze commit is not the last commit on HEAD that changed FREEZE.json")
    return hashlib.sha256(go).hexdigest(), last


def held_seed():
    """The held generation's seed: the salt (sha256 of the GO file) read as an integer (its first 16 hex digits)."""
    return int(require_go()[:16], 16)


def take_marker():
    require_go()
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    try:
        fd = os.open(E.check_write(MARKER), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    except FileExistsError:
        raise GateRefused("already scored: the marker exists") from None
    return fd


def main(cmd="check"):
    """`run.py gate check`: every check, git ones included (Athe); prints the salt and the freeze commit."""
    if cmd != "check":
        raise SystemExit(cmd)
    salt, fc = git_checks()
    check_freeze()
    print(json.dumps({"salt": salt, "freeze_commit": fc, "go": os.path.relpath(GO, E.STUDY)}))
