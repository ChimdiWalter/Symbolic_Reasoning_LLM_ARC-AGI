# CORA reasoning v2: cohort-eligibility audit (2026-10-19)

**Status (updated 2026-10-19, after the user-authorized check): 44 of the 100 candidates are ELIGIBLE (outside Lockbox, Promotion and E_transfer); the Phase 2a cohort is the first 40 eligible.** See section 7. The original status follows.

**Original status: proposed evaluation cohort UNVERIFIED. Phase 2 is not launched.** The cohort is independent of all v2 and
CORA-FHR development, which is checked, with 0 overlaps. It is very probably **not** independent of Step B's protected
splits, which cannot be checked without protected material (section 4).

- Code: `cora_revision_v2/cohort_audit.py` (commit 4c4c30d).
- Output: `outputs/cora_revision_v2/cohort_audit_20261019.json` (sha256 7c2f807de40cee39; regenerated after the Step B caveat was added, cohort list unchanged).
- No test answer was read, v2 was not run on any candidate, and no Step B file was opened except the protocol text
  `Reasoning_Project/docs/LOCKBOX_PROTOCOL.md`, read for its split rule only.

## 1. Inventory and rule

- **Inventory:** the 1,000-task ARC-AGI-2 public training file `arc-agi_training_challenges.json`
  (sha256 779eaba8…). It holds training pairs and test inputs only.
- **Scope:** the pilot's published rule (`records/pilot_v1/selection.json`): at least 3 demonstrations, grid shape
  kept, and every demonstration changes a cell. 548 tasks are in scope.
- **Order:** ascending sha256('cora-real-arc-pilot-v1|' + task id), as published before any v2 work.
- **Exclusions, by rule:**

| excluded | tasks in scope | how determined |
|---|---|---|
| dev60 (funnel, FHR, autopsy and controller development) | 60 | `selection.json` dev list |
| frozen 120-task pilot | 120 | its own published quota rule at the maximum N = 120 (60/40/20 per stratum), so every allowed N is covered; its outputs were not opened |
| 240 Kaggle stand-in tasks (includes standin58 and the 8 forensic tasks) | 132 | stand-in ID list |
| any ID in a CORA-FHR or v2 output or record | 0 further | grep by ID |

- 288 in-scope tasks remain.
- **Declared filter, from training pairs only:** additions-only, with no resize (v2's hypothesis class). 100 remain.
- **Proposed evaluation cohort:** the first 40 of these in the published order, listed in the output file.

## 2. Overlap checks

| proposed cohort vs | overlap |
|---|---|
| dev60 | 0 |
| frozen 120 pilot (by rule) | 0 |
| 240 stand-ins | 0 |
| any FHR/v2 output or record | 0 |

## 3. Exposure history of the proposed cohort

- These are public ARC-AGI-2 training tasks.
- The base engine lineage (v23) was developed on this split. The sealed v23 baseline run (185 of 1,000) saw every
  task, so the base is exposed to them.
- None was used to develop, tune or debug v2 or CORA-FHR.
- A result on them would therefore be a **development evaluation on reused public training tasks**, not a blind
  prospective test and not unseen-task evidence. The hidden Kaggle evaluation remains the only unseen test.

## 4. Why independence from Step B cannot be established here

- Step B's frozen protocol (`docs/LOCKBOX_PROTOCOL.md`, frozen 2026-08-18) partitions **this same 1,000-task file**:
  - Experience 600, Promotion 200, Lockbox 200;
  - E_transfer, 150 tasks, sits inside Experience. It is chosen by a keyed hash whose secret is behind Step B's
    provenance firewall.
- The protocol's rule 3: Lockbox tasks are "not run, inspected, traced, or analyzed in any way" until the system and
  library are frozen.
- The split is stratified proportionally by family. Any cohort drawn from this file is therefore expected to be about
  20% Lockbox, 20% Promotion and 15% E_transfer. That is about 22 of the 40 tasks, and the probability that all 40 are
  clear is about 1e-14.
- Membership can be checked only against Step B's split manifest (`outputs/lockbox/manifest.json`) and its E_transfer
  list. Both are protected and were not opened.
- **The same limitation applies to every earlier arc2026 cohort.** dev60, the stand-ins, standin58 and the frozen
  pilot were all drawn from the full file before this was noticed.
  - Step B's own measurements are unaffected: it is frozen and running, and no arc2026 result feeds it.
  - If the Lockbox rule is read as covering every CORA lineage, some Lockbox tasks may already have been run here. This
    cannot be checked without the manifest.

## 5. What would make the cohort eligible (needs the user's authorization)

**Recommended: a membership-only check.**
- Authorize one read of Step B's split manifest and its E_transfer list, by the user or by Claude on explicit
  authorization.
- It is restricted to the 100 additions-only candidates in the published order.
- It returns only a clear/not-clear bit per candidate, where clear means Experience and not E_transfer, i.e. in
  E_invent. Nothing else is printed or stored.
- **Declared now:**
  - The evaluation cohort is the first 40 clear candidates in the published order. About 45 are expected to be clear.
  - If fewer than 40 are clear, it is every clear candidate, down to a minimum of 25.
  - If fewer than 25 are clear, it is extended with the remaining in-scope same-shape tasks, in the same order and
    after the same check.

**Alternatives:**
- A cohort from a source outside this file, such as another ARC-format collection. Independence from Step B would then
  hold by construction, but it would not be ARC-AGI-2.
- Explicit acceptance of the unverified cohort. Not recommended, because it very probably runs Lockbox tasks.

## 6. Engineering cohort (exposed tasks)

- **Membership:** dev60 (60), standin58 (58) and the 8 forensic tasks (a subset of standin58).
- **Used for:** geometry, colour policies, hypothesis generation, diagnosis and revision.
- Results on it are in-sample engineering evidence only.

## 7. Eligibility check result (2026-10-19, user-authorized, one isolated run)

- **Checker:** `tools/stepb_eligibility/check_eligibility.py` (5c5401a).
- **Read:** Step B's split manifest only (`task_id` and `split`, after a sha256 match), with E_transfer derived by
  Step B's frozen public rule. The firewall and its secret were not opened.
- **Result:** PASS, **44 of 100 eligible**; eligible-list sha256 6b4ce11f52ee7353.
  - Of the 40 proposed earlier, 22 are eligible. The other 18 are in a protected split, which one is not recorded.
- **Phase 2a cohort:** the first 40 eligible; listed in `records/CORA_REASONING_V2_PHASE2A_EXECUTION_20261019.md`.
- **Independence:**
  - from v2 and FHR development: verified (0 overlaps);
  - from Step B's protected splits: verified (E_invent only).
  - These are still reused public training tasks that the v23 baseline saw. Results are a development evaluation,
    not a blind prospective test.
