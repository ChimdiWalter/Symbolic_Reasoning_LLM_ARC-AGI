# Amendment 5 to Protocol U5 (2 Nov 2026, before any evaluation parent is processed)

`PROTOCOL.md` and Amendments 1 to 4 are unchanged. This file adds to them and takes precedence where they differ. Its
hash and the new exact code freeze are in `AMENDMENT_5_FREEZE.json` and `CODE_FREEZE.json`.

**Why.** It answers the independent re-review, read-only in
`<companion study folder>/biology_transfer_20261102/`:
- `u5_amendment3_independent_review_v1/REVIEW.md`;
- `u5_amendment3_independent_review_v1/PATCH_SKETCH_V1.md`;
- `u5_amendment4_metadata_review_v1/REVIEW.md`.

**State.** No evaluation image has been segmented. No evaluation reference has been decoded. No arm has touched an
evaluation parent. The hold (`work/HOLD_FOR_AMENDMENT`) stays in place until the coordinator writes `GO_EVALUATION`.

## 1. MATCHED_SEARCH ranks only valid programs, and reports all its work

**The defect.** `u5static._step_candidates` ranked programs by additive gain without removing the conflicting ones. In
the review's synthetic collision, the invalid all-units dilation ranked first, at a predicted gain of 0.6667 against an
exact gain of 0.

**The fix.**
- Programs whose selection contains a conflicting pair (`Space.conflicted`, the executor's abstention rule) are removed
  before ranking and beam truncation.
- Every program whose gain is computed is counted (`candidates_scored`; 57 in the review's case, not 2). The record
  separately counts the eligible candidates returned, the conflicting programs excluded and the exact beam
  applications, and it includes the charged-work counters.
- The CPU budget is checked before each operator's program space is built. Any overrun is reported
  (`cpu_over_budget_s`), as is the wall time.

## 2. Transfer labels

- The learned-transfer conjunction is evaluated only when there are exactly two eligible transfer targets, which needs
  both NuInsSeg and MoNuSAC to pass calibration eligibility and their gates.
- With one target the result is **TRANSFER_SINGLE_TARGET** (descriptive); with none it is **INSUFFICIENT_TARGETS**.
- No field named `LEARNED_TRANSFER`, and no "two targets pooled" heading, can appear with fewer than two targets.

## 3. Executable growth gates

- **(c) Alias.** True only if every operator admitted on A had its alias check actually run (at least one accepted
  validation edit compared) and passed. It is False when nothing was admitted, since no comparison ran.
- **Work match.**
  - A FAILURE_BLIND or SHUFFLED seed is matched only if it validated the same number of candidates as CORA and its
    measured admission CPU is within a factor of 2 of CORA's.
  - MATCHED_SEARCH is matched if its CPU is at least half of CORA's, or if it exhausted its schedule, which is
    reported.
- **GROWTH_SUPPORTED** requires all of: at least one admitted operator, (c), changed held-out outputs, lower bounds
  above 0 against MATCHED_SEARCH, ALL_ON, FAILURE_BLIND and SHUFFLED, and both work matches. Otherwise the growth claim
  is withheld.
- **Unmatched controls.** If any control is unmatched, the failure-evidence gate is reported as
  WITHHELD_UNMATCHED_WORK, and CROSS_DOMAIN_USEFUL cannot be awarded; the label becomes INCOMPLETE_CONTROLS.

## 4. The neural-proposal arm

`run_policy_proposals` now runs the same exact certification of decisive programs as `run_policy`, before any query
edit: the top program, every fold top and up to 50 seeded fitting programs. It also asserts accepted == applied ==
logged.

**Exposure note** (coordination outbox 0116). The proposer read the calibration packets of every dataset, including the
transfer targets' calibration aggregates. Its transfer is therefore labelled **limited target-calibration aggregate
exposure**: it is neither zero-shot nor held-out-blind on B and C. The arm stays secondary and outside the primary
claim.

## 5. Corrections to Amendment 4

- **Parents.** MoNuSAC has **67 independent parents**. Its two releases share two patient barcodes (TCGA-A2-A0ES and
  TCGA-MP-A4T7), so their union holds 69 unique patients, not 46 + 25. Excluding the 2 patients of the baseline's
  MoNuSeg training data leaves 67: 27 calibration and 40 evaluation, each patient wholly on one side.
- **Chronology.**
  - Amendment 4 was committed at 11:24:29Z (845e361e), before the download.
  - The reader was written after the download.
  - One calibration mask (`TCGA-69-7760-01Z-00-DX1_001`: 30 objects, no ambiguous region) was decoded for a format
    check before the reader and code re-freeze at 11:27:27Z (59236a10).

  Amendment 4's phrase "before any MoNuSAC mask is decoded" is corrected accordingly.
- **Ambiguous regions.** The downloaded archives contain no separate binary ambiguity masks. The rule is therefore
  **XML-only**: annotation layers whose attribute names contain "ambig". **Limitation:** if the organisers' external
  binary masks mark regions that the XML does not, those regions are scored like any other.

## 6. Tests and what is unchanged

`tests/test_u5.py` now has 16 tests; all pass. The four new ones are:
- the review's collision through MATCHED_SEARCH's candidate step;
- one- and two-target transfer labels;
- executable alias and work-match gates;
- certification and reconciliation in the neural-proposal arm.

The CORA path itself is byte-identical in behaviour to Amendment 3: `u5core`, `u5policy`, `u5induce`, `u5probe`,
`u5tax`, and `run_policy` and `certify` in `u5run`. The LIVECell induction started under the previous freeze therefore
runs the same code.
