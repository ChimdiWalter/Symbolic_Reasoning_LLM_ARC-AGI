"""Candidate list for the ncv2-g2 real-ARC engineering check: the next 100 in-scope ARC-AGI-2 training tasks, in the
pilot's published order. These are the candidates that go to the metadata-only Step B eligibility checker.

    python scripts/neural_cora_v2g2_realarc_cohort.py
        -> outputs/neural_cora_v2g2/realarc/cohort_candidates_20261020.json

**The rule** is the one `cora_revision_v2/cohort_audit.py` uses:
- scope: `records/pilot_v1/selection.json` (at least 3 demonstrations, grid shape kept, every demonstration changes a
  cell);
- order: ascending sha256('cora-real-arc-pilot-v1|' + id).

**Excluded:**
- dev60;
- the frozen 120-task pilot (its quota rule at N = 120);
- the 240 stand-in tasks;
- every ID mentioned in any CORA-FHR, reasoning-v2 or Neural-CORA output or record;
- **all 100 candidates checked on 19 October** (the additions-only list: the 44 eligible, the 40 of them Phase 2a used,
  and the 56 protected).

It reads the challenges file (demonstrations and test inputs, no answers) and ID lists only. It reads no answers, no
Step B file and no task content beyond the demonstrations.
"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g2", "realarc")
PREV = os.path.join(HERE, "outputs", "cora_revision_v2", "cohort_audit_20261019.json")
N = 100


def main():
    from cora_pilot import bundle as B
    ch = B.load_challenges()                                            # sha-pinned; demonstrations and test inputs only
    sel = json.load(open(os.path.join(HERE, "records", "pilot_v1", "selection.json")))
    assert sel["challenges_sha256"] == B.CHALLENGES_SHA256
    dev = set(sel["dev"])
    order = [t for t, _s in sel["order"]]
    stratum = dict((t, s) for t, s in sel["order"])
    quota, seen, pilot = {"n3": 60, "n4": 40, "n5p": 20}, {"n3": 0, "n4": 0, "n5p": 0}, set()
    for t in order:
        if t not in dev and seen[stratum[t]] < quota[stratum[t]]:
            pilot.add(t)
            seen[stratum[t]] += 1
    standin = set(json.load(open(os.path.join(HERE, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "comp",
                                              "arc-agi_test_challenges.json"))))
    prev = json.load(open(PREV))
    first100 = set(prev["candidates_additions_only_ordered"])
    scan = glob.glob(os.path.join(HERE, "outputs", "cora_fhr", "*.json*")) + glob.glob(os.path.join(HERE, "outputs", "cora_revision_v2", "**", "*.json*"), recursive=True) \
        + glob.glob(os.path.join(HERE, "records", "CORA_FHR_*.md")) + glob.glob(os.path.join(HERE, "records", "CORA_REVISION*.md")) \
        + glob.glob(os.path.join(HERE, "records", "CORA_REASONING_V2*.md")) + glob.glob(os.path.join(HERE, "records", "NEURAL_CORA*.md")) \
        + [f for pat in ("neural_cora_v1", "neural_cora_v2", "neural_cora_v2g2") for ext in ("json", "jsonl", "md", "txt")
           for f in glob.glob(os.path.join(HERE, "outputs", pat, "**", f"*.{ext}"), recursive=True)]
    used = set()
    for f in scan:
        if "cohort_audit" in f or "cohort_candidates" in f or os.path.getsize(f) > 50_000_000:
            continue
        txt = open(f, errors="ignore").read()
        used |= {t for t in ch if t in txt}
    remaining = [t for t in order if t not in dev and t not in pilot and t not in standin and t not in used and t not in first100]
    cands = remaining[:N]
    res = {"rule": f"the first {N} remaining in-scope tasks in the pilot's published order, excluding dev60, the frozen 120 pilot, "
                   "the 240 stand-ins, every ID in any CORA-FHR / v2 / Neural-CORA output or record, and the 100 candidates checked on 2026-10-19",
           "note": "the key name `candidates_additions_only_ordered` is the one the frozen eligibility checker reads; this list is NOT restricted to additions-only tasks",
           "candidates_additions_only_ordered": cands,
           "candidates_sha256": hashlib.sha256(json.dumps(cands).encode()).hexdigest(),
           "counts": {"in_scope": len(order), "dev60": len(dev & set(order)), "frozen_pilot_120": len(pilot), "standin_in_scope": len(standin & set(order)),
                      "used_in_scope": len(used & set(order)), "first100_checked_20261019": len(first100), "remaining": len(remaining), "candidates": len(cands)},
           "overlap_checks": {"vs_dev60": len(set(cands) & dev), "vs_pilot": len(set(cands) & pilot), "vs_standin": len(set(cands) & standin),
                              "vs_used": len(set(cands) & used), "vs_first100": len(set(cands) & first100)},
           "exposure": "public ARC-AGI-2 training tasks; seen by the sealed v23 1000-task baseline run and in NVARC's training mix; Step B protected-split membership is checked separately by tools/stepb_eligibility"}
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "cohort_candidates_20261020.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k in ("counts", "overlap_checks", "candidates_sha256")}, indent=1))


if __name__ == "__main__":
    main()
