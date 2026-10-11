"""Real ARC growth-repair pilot v2: the blind evaluator (protocol sections 9
to 11).

  python scripts/pilot_v2_evaluate.py

Refuses unless the reasoner marker exists and the committed predictions in
git are byte-identical to the files on disk. Only then does it open the
evaluator key map, the pinned solutions and the pinned sealed v23 records.
Writes outputs/pilot_v2/pilot_report.json and logs/PILOT_V2_DONE.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_pilot import bundle as B                                  # noqa: E402
from cora_pilot import evaluator as EV1                             # noqa: E402
from cora_pilot2 import evaluator as EV                             # noqa: E402

OUT = os.path.join(HERE, "outputs", "pilot_v2")
LOG = os.path.join(HERE, "logs", "pilot_v2")
KEYMAP = os.path.join(HERE, "records", "pilot_v2_evaluator", "pilot_keymap.json")
REASONER_MARKER = os.path.join(HERE, "logs", "PILOT_V2_REASONER_DONE")
MARKER = os.path.join(HERE, "logs", "PILOT_V2_DONE")
REPORT = os.path.join(OUT, "pilot_report.json")
COMMITTED = ("committed_predictions.json", "reasoner_record.json", "native_rows.jsonl", "instances_rows.jsonl",
             "cora_rows.jsonl")


def git_blob_sha(commit, rel) -> str:
    data = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=HERE, check=True,
                          capture_output=True).stdout
    return hashlib.sha256(data).hexdigest()


def read_rows(path) -> dict:
    out = {}
    with open(path) as handle:
        for line in handle:
            if line.strip():
                r = json.loads(line)
                out[r["key"]] = r
    return out


def main() -> None:
    if os.path.exists(MARKER):
        raise SystemExit("already evaluated")
    if not os.path.exists(REASONER_MARKER):
        raise SystemExit("the reasoner has not finished")
    commit = json.load(open(os.path.join(LOG, "predictions_commit.json")))["commit"]
    if open(REASONER_MARKER).read().strip() != commit:
        raise SystemExit("marker and commit record disagree")
    for name in COMMITTED:
        rel = os.path.relpath(os.path.join(OUT, name), HERE)
        if git_blob_sha(commit, rel) != B.sha256_file(os.path.join(OUT, name)):
            raise SystemExit(f"{name} on disk differs from the committed predictions")
    record = json.load(open(os.path.join(OUT, "reasoner_record.json")))
    if record["predictions_sha256"] != B.sha256_file(os.path.join(OUT, "committed_predictions.json")):
        raise SystemExit("predictions sha256 differs from the reasoner record")
    #  only now: the evaluator-side inputs
    sys.path.insert(0, os.path.join(HERE, "scripts"))
    import freeze_pilot_v2 as FZ
    frozen = FZ.freeze_problems("evaluator")
    keymap = json.load(open(KEYMAP))
    report = {"commit_scored": commit, "freeze_problems": frozen}
    try:
        if frozen:
            raise ValueError(f"frozen state changed: {frozen}")
        if keymap["bundle_sha256"] != record["bundle_sha256"]:
            raise ValueError("bundle differs from the key map's bundle")
        solutions = EV1.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)
        sealed = EV1.sealed_solved()
    except (ValueError, KeyError) as exc:
        leak = bool((record.get("isolation") or {}).get("problems", {"missing": 1}))
        report.update(outcome="PILOT_LEAKAGE" if leak else "NO_VERDICT_DATASET", reason=str(exc))
    else:
        preds = json.load(open(os.path.join(OUT, "committed_predictions.json")))
        res = EV.evaluate(keymap, preds, read_rows(os.path.join(OUT, "cora_rows.jsonl")),
                          read_rows(os.path.join(OUT, "native_rows.jsonl")), solutions, sealed,
                          record.get("isolation") or {"problems": {"missing": ["no isolation audit"]}})
        report.update(res)
    with open(REPORT + ".tmp", "w") as handle:
        json.dump(report, handle, sort_keys=True, indent=1)
    os.replace(REPORT + ".tmp", REPORT)
    with open(MARKER, "w") as handle:
        handle.write(f"{report['outcome']} {B.sha256_file(REPORT)}\n")
    s = report.get("summary") or {}
    print(report["outcome"], report.get("safety"), json.dumps({"witnesses": s.get("witnesses"),
                                                               "invention_witnesses": s.get("invention_witnesses")}))


if __name__ == "__main__":
    main()
