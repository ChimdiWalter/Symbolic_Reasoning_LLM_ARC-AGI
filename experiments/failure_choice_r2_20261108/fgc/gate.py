"""GO gate of the failure-guided choice test (standard library only; fails closed).

    python3 -I fgc/gate.py STAGE            STAGE: generate | measure | seal | score

1. GO_FGC (in this folder), written by the coordinator after our reviewer's pre-run review, whose first two lines
   are exactly
       protocol_sha256 <sha256 of PROTOCOL.md>
       freeze_sha256 <sha256 of FREEZE.json>
2. every file listed in FREEZE.json has its recorded sha256.
3. one use: stage "generate" writes runs/RUN_CLAIM.json (the GO's sha256 and the time) and refuses if a claim or
   runs/test/ exists; every later stage requires that claim, naming the same GO bytes.
4. the held test set's salt is derived from the GO's bytes (claim_and_salt), so no held task can exist before it.
5. stage "measure" requires the committed test manifest; stage "score" requires the sealed predictions and their
   recorded digest (runs/test/SEALED_SHA256).
"""
import hashlib
import json
import os
import sys
import time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = os.path.join(STUDY, "GO_FGC")
PROTOCOL = os.path.join(STUDY, "PROTOCOL.md")
FREEZE = os.path.join(STUDY, "FREEZE.json")
CLAIM = os.path.join(STUDY, "runs", "RUN_CLAIM.json")
TEST = os.path.join(STUDY, "runs", "test")


def sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def check(stage):
    bad = []
    try:
        with open(GO, encoding="utf-8") as f:
            go = f.read().splitlines()
        if go[:2] != [f"protocol_sha256 {sha(PROTOCOL)}", f"freeze_sha256 {sha(FREEZE)}"]:
            bad.append("GO_FGC does not bind the live PROTOCOL.md and FREEZE.json")
    except OSError:
        bad.append("no GO_FGC")
    try:
        with open(FREEZE, encoding="utf-8") as f:
            frz = json.load(f)
        repo = os.path.dirname(os.path.dirname(STUDY))
        for rel, h in frz["files_sha256"].items():
            if sha(os.path.join(STUDY, rel)) != h:
                bad.append(f"frozen file changed or missing: {rel}")
        for rel, h in frz["dependencies_sha256"].items():
            if sha(os.path.join(repo, rel)) != h:
                bad.append(f"dependency changed or missing: {rel}")
        for path, h in frz.get("data_sha256", {}).items():
            if sha(path) != h:
                bad.append(f"data changed or missing: {path}")
    except (OSError, ValueError, KeyError):
        bad.append("FREEZE.json unreadable")
    go_sha = sha(GO)
    if stage == "generate":
        if os.path.exists(CLAIM):
            bad.append("the GO was already used (runs/RUN_CLAIM.json exists)")
        if os.path.exists(TEST):
            bad.append("runs/test/ exists: held tasks are generated once, never over an earlier attempt")
    else:
        try:
            with open(CLAIM, encoding="utf-8") as f:
                if json.load(f).get("go_sha256") != go_sha:
                    bad.append("RUN_CLAIM.json names other GO bytes")
        except (OSError, ValueError):
            bad.append("no RUN_CLAIM.json")
    if stage in ("measure", "seal", "score") and not os.path.exists(os.path.join(TEST, "TEST_MANIFEST.json")):
        bad.append("no held test manifest")
    if stage == "score":
        sp, dp = os.path.join(TEST, "SEALED_PREDICTIONS.json"), os.path.join(TEST, "SEALED_SHA256")
        try:
            with open(dp, encoding="utf-8") as f:
                if sha(sp) != f.read().strip():
                    bad.append("sealed predictions differ from their recorded digest")
        except OSError:
            bad.append("no sealed predictions")
    if bad:
        print(f"FAIL {stage}: " + "; ".join(bad))
        return False
    if stage == "generate":
        os.makedirs(os.path.dirname(CLAIM), exist_ok=True)
        with open(CLAIM, "x", encoding="utf-8") as f:
            json.dump({"go_sha256": go_sha, "claimed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "protocol_sha256": sha(PROTOCOL), "freeze_sha256": sha(FREEZE)}, f, indent=1)
    print(f"ok {stage}: protocol {sha(PROTOCOL)} freeze {sha(FREEZE)} go {go_sha}")
    return True


def claim_and_salt():
    """Gate stage generate (one use), then the held set's salt from the GO's bytes."""
    if not check("generate"):
        raise SystemExit("gate refused")
    return "fgc2-test-" + sha(GO)[:16]


if __name__ == "__main__":
    sys.exit(0 if check(sys.argv[1]) else 1)
