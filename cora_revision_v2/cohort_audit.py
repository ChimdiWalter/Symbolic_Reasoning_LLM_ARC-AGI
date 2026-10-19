"""Cohort-eligibility audit over the 1,000-task ARC-AGI-2 training split (DEVELOPMENT; no answers, no v2 runs).

  python -m cora_revision_v2.cohort_audit   -> outputs/cora_revision_v2/cohort_audit_20261019.json

**Sources** (non-protected, read for IDs and demonstrations only):
- `arc-agi_training_challenges.json` (sha 779eaba8): training pairs and test inputs, no test outputs;
- `records/pilot_v1/selection.json`: the pilot's documented rule, order and ID lists;
- the 240 stand-in IDs (Kaggle rehearsal);
- the dev60 bundle;
- every row and record of `cora_fhr` and `cora_revision_v2`, grepped by ID.

**Exclusions, by rule:**
- dev60;
- the frozen 120-task pilot: per stratum, the first quota of pilot candidates in the published order, at the
  maximum N = 120, i.e. (60, 40, 20). This covers every allowed N;
- the 240 stand-in tasks, which include standin58;
- any task ID appearing in a CORA-FHR or v2 output or record.

**Not checkable here: Step B's protected splits.** Step B's frozen protocol (`docs/LOCKBOX_PROTOCOL.md`) partitions
this same file into Experience 600 / Promotion 200 / Lockbox 200, with E_transfer (150, keyed hash) inside
Experience. Membership needs Step B's manifest and firewall, which are protected and not read, so the proposed
cohort is UNVERIFIED. Every earlier arc2026 cohort (dev60, stand-in) has the same status.

**Cohorts:**
- **ENGINEERING (exposed):** dev60 + standin58 + the 8 forensic tasks.
- **PROPOSED EVALUATION:** the remaining in-scope tasks whose training pairs are additions-only with no resize
  (v2's class; decided from demonstrations only, before any v2 run), taken in the pilot's published hash order.
"""
import glob
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_revision_v2")


def additions_only(task):
    for p in task["train"]:
        A, B = np.asarray(p["input"]), np.asarray(p["output"])
        if A.shape != B.shape:
            return False
        vals, cnt = np.unique(A, return_counts=True)
        bg = vals[int(np.argmax(cnt))]
        ch = A != B
        if not ch.any() or (A[ch] != bg).any():
            return False
    return True


def main(k_eval=40):
    from cora_pilot import bundle as B
    ch_path = B.CHALLENGES
    assert hashlib.sha256(open(ch_path, "rb").read()).hexdigest() == B.CHALLENGES_SHA256
    ch = json.load(open(ch_path))
    sel = json.load(open(os.path.join(HERE, "records", "pilot_v1", "selection.json")))
    assert sel["challenges_sha256"] == B.CHALLENGES_SHA256
    dev = set(sel["dev"])
    order = [t for t, _s in sel["order"]]
    stratum = dict((t, s) for t, s in sel["order"])
    quota = {"n3": 60, "n4": 40, "n5p": 20}                     # N = 120 (the maximum allowed): every possible pilot task
    pilot, seen = set(), {"n3": 0, "n4": 0, "n5p": 0}
    for t in order:
        if t in dev:
            continue
        s = stratum[t]
        if seen[s] < quota[s]:
            pilot.add(t)
            seen[s] += 1
    standin = set(json.load(open(os.path.join(HERE, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "comp",
                                              "arc-agi_test_challenges.json"))))
    used = set()
    for f in glob.glob(os.path.join(HERE, "outputs", "cora_fhr", "*.json*")) + glob.glob(os.path.join(HERE, "outputs", "cora_revision_v2", "*.json")) \
            + glob.glob(os.path.join(HERE, "records", "CORA_FHR_*.md")) + glob.glob(os.path.join(HERE, "records", "CORA_REVISION*.md")) \
            + glob.glob(os.path.join(HERE, "records", "CORA_REASONING_V2*.md")):
        if "cohort_audit" in f:
            continue
        txt = open(f, errors="ignore").read()
        used |= {t for t in ch if t in txt}
    in_scope = set(order)
    remaining = [t for t in order if t not in dev and t not in pilot and t not in standin and t not in used]
    growth = [t for t in remaining if additions_only(ch[t])]
    eval_cohort = growth[:k_eval]
    res = {"tasks_total": len(ch), "in_scope": len(in_scope), "excluded": {"dev60": len(dev), "frozen_pilot_max120": len(pilot),
           "standin240_in_scope": len(in_scope & standin), "cora_fhr_or_v2_used_in_scope": len(in_scope & used - dev - pilot - standin)},
           "remaining_in_scope": len(remaining), "remaining_additions_only": len(growth),
           "proposed_eval_cohort": eval_cohort, "eval_rule": f"first {k_eval} of the remaining additions-only tasks in the pilot's published order",
           "candidates_additions_only_ordered": growth,
           "candidates_sha256": hashlib.sha256(json.dumps(growth).encode()).hexdigest(),
           "exposure": "public ARC-AGI-2 training tasks; seen by the sealed v23 1000-task baseline run; not in dev60, the frozen 120 pilot "
                       "(by rule, N=120), the 240 stand-in tasks, or any CORA-FHR/v2 output or record; Step B Lockbox/Promotion/E_transfer membership NOT checkable (protected; expected ~55% of any cohort from this file)",
           "overlap_checks": {"eval_vs_dev60": len(set(eval_cohort) & dev), "eval_vs_pilot": len(set(eval_cohort) & pilot),
                              "eval_vs_standin": len(set(eval_cohort) & standin), "eval_vs_used": len(set(eval_cohort) & used)},
           "engineering_cohort": {"dev60": len(dev), "standin58": 58, "forensic8": 8}}
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "cohort_audit_20261019.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("proposed_eval_cohort", "candidates_additions_only_ordered")}, indent=1))
    print("proposed eval cohort:", " ".join(eval_cohort))


if __name__ == "__main__":
    main()
