"""ONE isolated, metadata-only cohort eligibility check against Step B's protected splits.
Authorized by the user on 2026-10-19.

  python3 -I tools/stepb_eligibility/check_eligibility.py CANDIDATES_JSON OUT_JSON

**What it reads:**
- From CANDIDATES_JSON (the cohort audit output): only the ordered candidate list
  `candidates_additions_only_ordered` and its checksum.
- Step B's frozen split manifest (`Reasoning_Project/outputs/lockbox/manifest.json`, v1.0.0), after its sha256 has
  matched the value Step B logged in `logs/lockbox_manifest.log`. Only the `task_id` and `split` fields of each task
  entry are accessed.

**How it derives E_transfer.** It uses Step B's frozen rule (`scripts/cora_level4_prepare_inputs.py` at Step B commit
533e735, lines 46-47 and 72-76): order the 600 Experience tasks by sha256(HOLDOUT_SALT + task id); the last 150 are
E_transfer. The salt is a constant in Step B's code, not a secret. The provenance firewall file, which holds a
secret, is **not** opened.

**What it writes:** only OUT_JSON, holding the eligible IDs in the candidates' order, their count, checksums and the
attestation. It prints one line. On any failed check it writes a FAIL record that carries no membership information.

**Isolation:**
- standard library only; nothing from CORA is imported;
- files are opened read-only, and the manifest hash is checked again afterwards;
- per-candidate split labels and anything about non-candidate tasks are never written.
"""
import hashlib
import json
import os
import sys

STEPB_MANIFEST = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project/outputs/lockbox/manifest.json"
EXPECTED_SHA = "cc797ba80ad781ef930f79c1d332ab4a389e27ee777ea666053ba779cf3f5e5e"   # logs/lockbox_manifest.log, 2026-08-18
HOLDOUT_SALT = "cora-level4-within-stage-holdout-2026-08-22"          # Step B prepare_inputs.py:46 (533e735)
E_INVENT_FRACTION = 0.75                                               # Step B prepare_inputs.py:47 (533e735)
SPLITS = {"experience": 600, "promotion": 200, "lockbox": 200}
ALLOWED_KEYS = ("eligible_ids", "count", "checksums", "attestation")


def _sha_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _sha_list(xs):
    return hashlib.sha256(json.dumps(list(xs)).encode()).hexdigest()


def _fail(out_path, reason, manifest_is_default):
    rec = {"eligible_ids": None, "count": None, "checksums": {},
           "attestation": {"status": "FAIL", "reason": reason, "membership_information": "none written",
                           "stepb_manifest_default_path": manifest_is_default}}
    with open(out_path, "w") as fh:
        json.dump(rec, fh, indent=1)
    print("ELIGIBILITY_CHECK_FAIL " + reason)
    return 1


def check(cand_path, out_path, manifest=STEPB_MANIFEST, expected=EXPECTED_SHA):
    default = manifest == STEPB_MANIFEST and expected == EXPECTED_SHA
    with open(cand_path) as fh:
        doc = json.load(fh)
    cands = doc["candidates_additions_only_ordered"]
    if _sha_list(cands) != doc.get("candidates_sha256") or len(set(cands)) != len(cands) or not cands:
        return _fail(out_path, "candidate list checksum or uniqueness check failed", default)
    before = _sha_file(manifest)
    if before != expected:
        return _fail(out_path, "Step B manifest sha256 does not match the logged value", default)
    with open(manifest) as fh:
        tasks = json.load(fh)["tasks"]
    split = {t["task_id"]: t["split"] for t in tasks}                  # the two fields used; nothing else is read
    del tasks
    counts = {s: sum(v == s for v in split.values()) for s in SPLITS}
    if counts != SPLITS or len(split) != sum(SPLITS.values()):
        return _fail(out_path, "Step B manifest split counts are not 600/200/200", default)
    if any(c not in split for c in cands):
        return _fail(out_path, "a candidate is not in the Step B manifest", default)
    experience = sorted(t for t, s in split.items() if s == "experience")
    ordered = sorted(experience, key=lambda t: hashlib.sha256((HOLDOUT_SALT + t).encode()).hexdigest())
    cut = round(len(ordered) * E_INVENT_FRACTION)
    transfer = set(ordered[cut:])
    if len(transfer) != 150 or cut != 450:
        return _fail(out_path, "derived E_transfer is not 150 tasks", default)
    eligible = [c for c in cands if split[c] == "experience" and c not in transfer]
    del split, experience, ordered, transfer
    if _sha_file(manifest) != before:
        return _fail(out_path, "Step B manifest changed during the check", default)
    rec = {"eligible_ids": eligible, "count": len(eligible),
           "checksums": {"candidates_sha256": doc["candidates_sha256"], "eligible_sha256": _sha_list(eligible),
                         "stepb_manifest_sha256": before,
                         "checker_sha256": _sha_file(os.path.abspath(__file__))},
           "attestation": {
               "status": "PASS",
               "authorized_by": "user, 2026-10-19: ONE isolated metadata-only eligibility check for the previously "
                                "ordered 100 public ARC training task IDs",
               "stepb_manifest_default_path": default,
               "process": "python3 -I (isolated mode), standard library only, no CORA module imported",
               "read": ["the ordered candidate list and its checksum (cohort audit output)",
                        "Step B split manifest v1.0.0: the task_id and split fields only, after its sha256 matched "
                        "Step B's logged value"],
               "derived": "E_transfer by Step B's frozen rule (prepare_inputs.py at 533e735): Experience ordered by "
                          "sha256(salt + id), the last 150 of 600",
               "eligible_rule": "candidate in Experience and not in E_transfer (that is, in E_invent)",
               "not_read": ["the provenance firewall file and its secret", "any task content, demonstration or answer",
                            "any Step B result, run output, journal, family label or certified flag"],
               "not_written": ["per-candidate split labels", "anything about non-candidate tasks",
                               "anything outside this file"],
               "stepb_modified": False,
               "n_candidates": len(cands)}}
    assert tuple(rec) == ALLOWED_KEYS
    with open(out_path, "w") as fh:
        json.dump(rec, fh, indent=1)
    print("ELIGIBILITY_CHECK_DONE count=%d" % len(eligible))
    return 0


def main(argv):
    if len(argv) == 2:
        return check(argv[0], argv[1])
    if len(argv) == 4 and os.environ.get("ELIGIBILITY_SELFTEST") == "1":       # synthetic fixtures only
        return check(argv[0], argv[1], manifest=argv[2], expected=argv[3])
    print("usage: check_eligibility.py CANDIDATES_JSON OUT_JSON")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
