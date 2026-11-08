# Amendment 3 to Protocol U5 (2 Nov 2026, before any evaluation outcome)

`PROTOCOL.md` (`7d5ef686...c56cd49`), Amendment 1 (`8e063d54...`) and Amendment 2 (`64dbc05b...`) are unchanged. This
file adds to them and takes precedence where they differ. Its hash, the source hashes and the test results are in
`AMENDMENT_3_FREEZE.json` and `CODE_FREEZE.json`.

**Why.** It answers the independent blind review and its follow-ups, all read-only in
`<companion study folder>/biology_transfer_20261102/`:
- `U5_BLIND_PROTOCOL_REVIEW.md` and `U5_BLIND_REVIEW_CORRECTION_20261102.md`;
- `u5_additivity_audit_v1/U5_ADDITIVITY_CORRECTION_V1.md` and
  `u5_additivity_audit_v2/AMENDMENT_REVIEW_AND_CURRENT_SOURCE_REGRESSION.md`;
- `u5_conflict_repair_v1/REVIEW.md` (sha256 `d6be7495...`).

The evaluation hold (`work/HOLD_FOR_AMENDMENT`, 10:08Z) stays in place until the coordinator releases it.

**State when written (11:15Z).** Calibration-side work only. No evaluation image has been segmented. No evaluation
reference has been decoded. No arm has been applied to any evaluation parent.

## 1. Conflict-aware program scoring (the defect)

**The defect.** Program scoring added each selected unit's isolated effect. `u5core.apply`, however, abstains on every
pair of selected edits whose write sets intersect or that touch the same object. Two adjacent dilations were therefore
scored as F1 2/3 and accepted, but they executed as F1 0. FIT, leave-one-out, admission and the reported acceptance
could rest on edits that never run.

**The invariant used now.** It is conditional, as the correction states. At IoU > 0.5:
- a prediction matches at most one reference, and a reference at most one prediction;
- so if the selected units' write sets are pairwise disjoint and no two touch the same object, `apply` executes all of
  them, each against the unchanged reference and ignore mask;
- and the changes in matched objects (dTP) and counted objects (dN) then add exactly.

F1 is always recomputed from the summed counts, never by adding F1 gains.

**The rule, in the source:**
- **Conflicts.** `u5core.units` records, for each unit and theta, the exact write set that `apply` uses and the objects
  the unit touches. Two units conflict if their write sets intersect or they share an object.
- **Invalid programs.** A program whose selection contains a conflicting pair on any demonstration parent is INVALID.
  It is excluded from FIT, leave-one-out re-derivation, ranking and admission. This is the conservative rule of the
  conflict reference. The same rule applies to the neural proposals (`ProposedSpace`) and to MATCHED_SEARCH's candidate
  scoring. Every valid program's selection is therefore conflict-free, and its scored counts are exact.
- **Runtime certification.** For every operator that reaches evidence, the top program, every leave-one-out fold top
  and up to 50 seeded FIT programs are executed through `u5core.apply` on every demonstration image, and each whole
  segmentation is re-matched. The scored per-parent counts must equal the exact ones, and no edit may be dropped;
  otherwise the run stops with an error. This work is charged (`exact_certified_programs`, `exact_image_matchings`).
- **Consensus.** On query images, the consensus uses each fitting program's executed set: its selection minus the units
  `apply` would abstain on. A unit is accepted only if every fitting program and every fold top executes it with the
  same result. The consensus is therefore conflict-free.
- **Reconciliation.** The consensus is resolved through `u5core.apply`, and accepted == applied == logged is asserted
  for every image and operator. Abstention counts, coverage and logs come from the applied set.
- **Exact arms.** ALL_ON is scored by exact application and whole-segmentation re-matching, as before. MATCHED_SEARCH
  ranks candidates with the conflict-aware scores, then applies and re-matches every kept step exactly.

**Tests** (`tests/test_u5.py`, 12 tests, frozen with the code):
- the independent audit's cases: disjoint delete, disjoint watershed split, disjoint pair merge, ignore region,
  shared-background collision;
- the conflict reference's cases, under the same rule: a mixed collision with one survivor, and merges sharing an
  object;
- random selections on ordinary and crowded synthetic scenes: exact execution equals the executed-set counts;
- conflicting programs are invalid;
- every FIT program and fold top equals exact execution.

## 2. Names of the rule and of the probe outcome (review items 2 and 3)

**The rule.** The FIT rule is a **B3-inspired selective verification with metric-consistent fits**. FIT holds the
programs that:
- lower no demonstration parent's object F1;
- raise the pooled F1;
- reach 0.9 of the best gain.

Leave-one-out requires non-degradation of the held-out parent. The rule does not reproduce demonstration outputs, and
it is not B3: the frozen package's B3 cannot execute these operators. The "(B3: ...)" glosses in protocol section 10 are
analogies only. Exact mask reproduction and exact edit-target recovery are not measured, and are not inferred from F1.

**The probe outcome.** "NOT EXPRESSIBLE" is renamed **NOT_FOUND_WITHIN_BUDGET**: the frozen package's own search found
no fitting program within 15 CPU-seconds, on U1's 21 x 21 encoding of six-window probes. The thresholds are unchanged:
at least 6 resolved probes, at least half of them with no fit.

The records now report, per class:
- resolved probes;
- unresolved probes (timeout or error);
- probes with no fit;
- probes with a fit that was not accepted;
- accepted queries, correct and incorrect.

NuInsSeg's statement now reads: on its induction parents, no probed class's correction was found by the frozen package
within its budget. DELETE had no fitting program in 32 of 40 probes (8 accepted queries: 6 correct, 2 incorrect). Every
other probed class had none in any probe: SPLIT 40, MERGE 22, GROW 26, SHRINK 21 and ADD 40.

An operator admitted from this evidence is failure-guided vocabulary growth, subject to the alias and held-out checks.
It is not proof of new expressive power.

## 3. Baseline provenance

- **Cellpose 3 `cyto2`** was trained on the Cellpose dataset plus user-submitted images, and no item-level manifest is
  public. Its relation to LIVECell is **no documented overlap found**, not "LIVECell is not in it".
- **StarDist `2D_versatile_he`** has documented training data MoNuSeg 2018 and TNBC, which do not include NuInsSeg.

## 4. Independent units, frozen before any evaluation reference is decoded (review item 4)

**LIVECell.** The parent is now **(cell line, well)**: 31 wells, split in sha256 order into 12 calibration and 19
evaluation wells.
- **Leak-free rule.** An image whose reference was decoded under the earlier grouping never enters evaluation. The 149
  such images in evaluation wells are dropped from the study; their references are quarantined and never read.
- **Counts.** Evaluation has 288 images in 19 wells. Calibration has 276 images in 12 wells (6 induction, 6
  validation): 115 decoded before, 161 decoded now. The cap rule is unchanged: 720 images, giving 23 per well.
- **Recomputed.** Thresholds, the strong native filter, the gate and the probes are all recomputed on the new
  calibration set. Only network outputs (deterministic, label-free) are reused.

**NuInsSeg.** The archive encodes neither patient nor slide, only the organ folder and an image index, so the organ
remains the parent: 31 organs, 12 calibration and 19 evaluation, unchanged.
- **Limitation.** Organs may share donors (the 8 mouse organs probably share animals), and the archive gives no way to
  group them.

**FNC v2.** The coarsest encoded unit is the animal: 22 animals, fewer than 10 + 15. FNC is therefore **INELIGIBLE**.

**Consequences.**
- No further backup exists. The study continues with two datasets: A = LIVECell if its gate passes, otherwise
  NuInsSeg; and one transfer target.
- The learned-transfer conjunction over B and C cannot be tested. Transfer is reported for the single target as
  **TRANSFER_SINGLE_TARGET** (descriptive), and never as learned transfer.
- The groupings are committed with this amendment (`DATA_MANIFEST_*.json`); the earlier ones are kept as
  `DATA_MANIFEST_v1_*.json`.
- Scores are reported as a new parent-held-out partition of a public pool (LIVECell: all three official subsets;
  NuInsSeg: the whole release), not as an official benchmark score.
- For LIVECell, a sensitivity analysis also clusters the bootstrap by cell line (8), descriptive.

## 5. Equal-work controls (review item 5)

**Candidate ceiling.** FAILURE_BLIND and SHUFFLED are pinned to CORA's candidate-validation ceiling: each seed
validates exactly n_spec candidate operators, the number CORA's failure records specified.
- FAILURE_BLIND draws n_spec of the 11 operators with `default_rng(7000 + r)`.
- SHUFFLED truncates its specified list to n_spec, or pads it with draws from the remaining operators using
  `default_rng(9000 + r)`.

**Charged work.** Every admission records:
- candidate validations, policy runs and unit tables;
- programs scored, fits and program selections;
- exact image matchings and certified programs;
- CPU and wall time.

Every arm records its CPU and wall time. MATCHED_SEARCH reports its schedule stage, the candidates it scored and its CPU
against CORA's.

**Unmatched work.** If a control's measured admission CPU differs from CORA's by more than a factor of 2, its work is
labelled UNMATCHED, and the failure-evidence (H3) gate is withheld for that comparison.

## 6. The claim family (review item 4, as corrected)

- **CROSS_DOMAIN_USEFUL** requires all five lower bounds above 0. It is an intersection-union test: each two-sided 95%
  bound is a one-sided 0.025 test, so no multiplicity adjustment is needed. A learned-transfer claim would likewise be a
  conjunction over targets; it is not testable here (section 4).
- **Separately asserted single contrasts** (for example, "CORA beats ALL_ON on A") carry Holm-adjusted one-sided
  parent-bootstrap p-values over the five contrasts of their dataset. Raw intervals are descriptive.
- No dataset is selected after outcomes: every dataset's label is reported.

## 7. Validation independence and transfer wording (review, further clarifications)

- **Validation.** S (the thresholds and the strong native filter) is tuned on all calibration parents, including the
  validation parents. Admission is therefore operator-held-out, conditional on a baseline tuned with those parents.
- **Transfer.** On the transfer target, a positive result supports transfer of the admitted operator vocabulary with
  target-specific adaptation: the target's calibration parents fit the programs and S. It does not support zero-shot
  program transfer. PROGRAM_TRANSFER, A's fitted programs applied without the target's demonstrations, is the zero-shot
  diagnostic.
