"""Write FREEZE.json (PROTOCOL.md section 10, step 4): the sha256 of every file the held run executes or reads, of the
development records and rules it rests on, and of the benchmark data; `athe_only` lists the frozen files that the
Kaggle package does not carry (the gate skips them inside a package).

    python3 -s -B gcon/freeze.py
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kaggle_build as KB                                                     # noqa: E402

STUDY, REPO, REL = KB.STUDY, KB.REPO, KB.STUDY_REL
ATHE_ONLY = ([REL + "/gcon/" + m + ".py" for m in ("dev", "devan", "sim", "verify", "score", "kaggle_build", "kaggle_fetch",
                                                  "freeze")]
             + [REL + "/" + p for p in ("DEV_REPORT.md", "PROTOCOL_AMENDMENT_1.md", "PROTOCOL_AMENDMENT_2.md",
                                        "PROTOCOL_AMENDMENT_3.md", "FREEZE_V1.json", "FREEZE_V2.json",
                                        "FREEZE_V3.json",
                                        "launch/smoke_test.py", "launch/score_guard_test.py",
                                        "checks/REVISION1_SAMPLE.json", "dev/STEP2_CHECK.json", "dev/STEP2_SAMPLE.0.json",
                                        "dev/curves.json", "dev/retries.jsonl", "dev/v2_holes.json",
                                        "dev/pass1/units.0.jsonl", "dev/pass1/units.1.jsonl")]
             + [REL + "/dev/models/" + f for f in ("fold0.json", "fold1.json", "fold2.json", "fold3.json", "fold4.json",
                                                  "full.json", "lobo_1d_arc.json", "lobo_concept_arc.json",
                                                  "lobo_mini_arc.json")]
             + ["experiments/object_growth_20261105/FREEZE_V2.json",
                "experiments/object_growth_20261105/CONTRACT_AMENDMENT_1.md",
                "experiments/object_growth_20261105/FREEZE.json"])


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    files = [p for p in KB.CODE if p != REL + "/FREEZE.json"] + ATHE_ONLY
    v3 = json.load(open(os.path.join(STUDY, "FREEZE_V3.json"), encoding="utf-8"))
    now = {p: sha(os.path.join(REPO, p)) for p in sorted(set(files))}
    doc = {
        "study": "guided-construction test (experiments/guided_construction_20261106)",
        "version": 4,
        "version_1": {"file": REL + "/FREEZE_V1.json", "sha256": sha(os.path.join(STUDY, "FREEZE_V1.json"))},
        "version_2": {"file": REL + "/FREEZE_V2.json", "sha256": sha(os.path.join(STUDY, "FREEZE_V2.json"))},
        "version_3": {"file": REL + "/FREEZE_V3.json", "sha256": sha(os.path.join(STUDY, "FREEZE_V3.json"))},
        "amendments": [REL + "/PROTOCOL_AMENDMENT_1.md", REL + "/PROTOCOL_AMENDMENT_2.md",
                       REL + "/PROTOCOL_AMENDMENT_3.md"],
        "changed_since_version_3": {p: {"version_3": v3["files_sha256"][p], "version_4": now[p]}
                                    for p in sorted(now) if p in v3["files_sha256"] and v3["files_sha256"][p] != now[p]},
        "added_in_version_4": sorted(p for p in now if p not in v3["files_sha256"]),
        "removed_since_version_3": sorted(p for p in v3["files_sha256"] if p not in now),
        "protocol_sha256": sha(os.path.join(STUDY, "PROTOCOL.md")),
        "objgrow_freeze_v2_sha256": sha(os.path.join(REPO, "experiments/object_growth_20261105/FREEZE_V2.json")),
        "files_sha256": now,
        "athe_only": sorted(ATHE_ONLY),
        "data_sha256": {f"{b}/{f}": sha(os.path.join(KB.DATA, b, f)) for b in ("1d_arc", "concept_arc", "mini_arc")
                        for f in ("real.json", "meta.json")},
        "arc2_challenges_sha256": sha(KB.ARC2[1]),
        "rules": json.load(open(os.path.join(STUDY, "config", "CONFIG.json"), encoding="utf-8")),
        "budget_rule": json.load(open(os.path.join(STUDY, "dev", "curves.json"), encoding="utf-8"))["budget_rule"],
        "stop_rule": {k: v for k, v in json.load(open(os.path.join(STUDY, "dev", "curves.json"),
                                                      encoding="utf-8"))["stop_rule"].items()},
        "never_opened": ["any held test output", "any solution file", "the ARC-AGI-2 evaluation challenges' content "
                         "(its bytes are hashed and packaged, not parsed)", "study B's held outputs and results"],
    }
    if doc["arc2_challenges_sha256"] != "e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8":
        raise SystemExit("ARC-AGI-2 challenges differ from the pinned digest")
    with open(os.path.join(STUDY, "FREEZE.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    print(json.dumps({"freeze_sha256": sha(os.path.join(STUDY, "FREEZE.json")), "files": len(doc["files_sha256"]),
                      "athe_only": len(doc["athe_only"])}))


if __name__ == "__main__":
    main()
