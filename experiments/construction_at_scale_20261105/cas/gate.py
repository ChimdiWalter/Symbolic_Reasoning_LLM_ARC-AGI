"""GO gate of the construction test at scale (standard library only; fails closed).

    python3 -I cas/gate.py STAGE          STAGE: generate | package | analyse

Checked before every phase 2 stage, from the live files:
1. GO_CAS (in this study folder), written by the coordinator after two independent exact-byte reviews, whose first
   two lines are exactly
       protocol_sha256 <sha256 of PROTOCOL.md>
       freeze_sha256 <sha256 of FREEZE.json>
2. every file listed in FREEZE.json (this study's files, and the S1, A2, CAST and arc-dsl files phase 2 reads)
   has its recorded sha256, and so do the two ARC training data files the generator reads.
3. one use: stage "generate" writes runs/RUN_CLAIM.json (the GO's sha256 and the time) and refuses if a claim
   already exists; later stages require that claim and that it names the same GO bytes.
4. stage "package" also requires runs/generated/BUILD_SUMMARY.json and every world's PARTITIONS_MANIFEST.json
   with matching digests of TASKS_SYSTEM.json, TASKS_EVAL.json and REMOVED.json, the configured worlds and no
   other, and each world's removed set, families and salt equal to the configuration (the task set is fixed before
   any method runs).
5. stage "generate" refuses while runs/generated/ exists: a build that failed after the claim is recovered only by
   the protocol's one-time rule (section 11), never built over.
6. stage "package" also requires that BUILD_SUMMARY.json names the main pool and the asserted source rule, that
   every task source of every world is in the main pool of config/POOLS.json, and that every world was built after
   the GO's claim (so a pilot dry run, or a build made before the GO, cannot be packaged).
Prints "ok STAGE ..." or "FAIL STAGE: ..." and exits 0 only if every check passes.
"""
import hashlib
import json
import os
import sys
import time

STUDY = os.environ.get("CAS_STUDY", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GO = os.path.join(STUDY, "GO_CAS")
PROTOCOL = os.path.join(STUDY, "PROTOCOL.md")
FREEZE = os.path.join(STUDY, "FREEZE.json")
CLAIM = os.path.join(STUDY, "runs", "RUN_CLAIM.json")
GENERATED = os.path.join(STUDY, "runs", "generated")


def sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def check(stage):
    bad = []
    go = None
    try:
        with open(GO, encoding="utf-8") as f:
            go = f.read().splitlines()
    except OSError:
        bad.append("no GO_CAS")
    if go is not None:
        want = [f"protocol_sha256 {sha(PROTOCOL)}", f"freeze_sha256 {sha(FREEZE)}"]
        if go[:2] != want:
            bad.append("GO_CAS does not bind the live PROTOCOL.md and FREEZE.json")
    try:
        with open(FREEZE, encoding="utf-8") as f:
            frz = json.load(f)
        for rel, h in frz["files_sha256"].items():
            if sha(os.path.join(STUDY, rel)) != h:
                bad.append(f"frozen file changed or missing: {rel}")
        repo = os.path.dirname(os.path.dirname(STUDY))
        for rel, h in frz["dependencies_sha256"].items():
            if sha(os.path.join(repo, rel)) != h:
                bad.append(f"dependency changed or missing: {rel}")
        for path, h in frz["data_sha256"].items():
            if sha(path) != h:
                bad.append(f"training data changed or missing: {path}")
    except (OSError, ValueError, KeyError):
        bad.append("FREEZE.json unreadable")
    go_sha = sha(GO)
    if stage == "generate":
        if os.path.exists(CLAIM):
            bad.append("the GO was already used (runs/RUN_CLAIM.json exists)")
        if os.path.exists(GENERATED):
            bad.append("runs/generated/ exists: a partial build must be removed deliberately first (PROTOCOL.md "
                       "section 11, recovery rule), never built over")
    else:
        try:
            with open(CLAIM, encoding="utf-8") as f:
                claim = json.load(f)
            if claim.get("go_sha256") != go_sha:
                bad.append("RUN_CLAIM.json names other GO bytes")
        except (OSError, ValueError):
            bad.append("no RUN_CLAIM.json (generation has not run under this GO)")
    if stage == "package":
        try:
            with open(os.path.join(GENERATED, "BUILD_SUMMARY.json"), encoding="utf-8") as f:
                summ = json.load(f)
            with open(os.path.join(STUDY, "config", "STUDY_CONFIG.json"), encoding="utf-8") as f:
                cfg = json.load(f)
            worlds = [k for k in summ if k.startswith("W")]
            if summ.get("pool") != "main" or summ.get("motivating_sources_disjoint_across_worlds") is not True:
                bad.append("the task set was not built from the main pool with rule 6 asserted")
            with open(os.path.join(STUDY, "config", "POOLS.json"), encoding="utf-8") as f:
                main_pool = set(json.load(f)["main"])
            try:
                with open(CLAIM, encoding="utf-8") as f:
                    claim_utc = json.load(f).get("claimed_utc")
            except (OSError, ValueError):
                claim_utc = None
            if sorted(worlds) != sorted(cfg["world_order"]):
                bad.append(f"built worlds {sorted(worlds)} differ from the configuration {sorted(cfg['world_order'])}")
            for w in worlds:
                with open(os.path.join(GENERATED, w, "partitions", "PARTITIONS_MANIFEST.json"), encoding="utf-8") as f:
                    man = json.load(f)
                if sha(os.path.join(GENERATED, w, "partitions", "TASKS_SYSTEM.json")) != man["tasks_system_sha256"] or \
                        sha(os.path.join(GENERATED, w, "evaluator_only", "TASKS_EVAL.json")) != man["tasks_eval_sha256"] or \
                        sha(os.path.join(GENERATED, w, "evaluator_only", "REMOVED.json")) != man["removed_sha256"]:
                    bad.append(f"{w}: task files differ from their manifest")
                with open(os.path.join(GENERATED, w, "evaluator_only", "TASKS_EVAL.json"), encoding="utf-8") as f:
                    srcs = {v["source"] for v in json.load(f).values()}
                if not srcs <= main_pool:
                    bad.append(f"{w}: {len(srcs - main_pool)} task sources are not in the main pool")
                if claim_utc and not (man.get("built_utc", "") >= claim_utc):
                    bad.append(f"{w}: the task set was built before the GO's claim")
                with open(os.path.join(GENERATED, w, "evaluator_only", "REMOVED.json"), encoding="utf-8") as f:
                    rem = json.load(f)
                if w in cfg["worlds"] and (list(rem["removed"]) != list(cfg["worlds"][w]["removed"]) or
                                           list(rem["families"]) != list(cfg["worlds"][w]["families"]) or
                                           man.get("salt") != cfg["worlds"][w]["salt"]):
                    bad.append(f"{w}: REMOVED.json or salt differ from the configuration")
        except (OSError, ValueError, KeyError):
            bad.append("generated task set missing or unreadable")
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


if __name__ == "__main__":
    sys.exit(0 if check(sys.argv[1]) else 1)
