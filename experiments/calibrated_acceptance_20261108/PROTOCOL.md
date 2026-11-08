# Protocol: a calibrated acceptance rule for CORA's learn-from-failure edits, tested on fresh held H&E images (pre-registered before any held image is opened)

CORA is a research program by its sole author, Chimdi Walter Ndubuisi. This protocol was written on 8 Nov 2026,
before any held image was chosen or opened. Its sha256 is in `FREEZE.json`, with the code, the configuration, the
data manifest and every reused file. The protocol is not changed after GO. A change before GO goes into a dated,
hashed amendment. A deviation after GO is reported in the result record.

## 1. Background: result, lesson, direction

The bioimage grammar study of 2 Nov 2026 is called U5 below (`experiments/universality_bio_grammar_20261103`; record
`records/NOV5_BIO_GRAMMAR_TRANSFER_RESULT.md`). It is this study's only predecessor.

- **Result.**
  - On NuInsSeg, CORA's strict verify-or-abstain rule admitted no change. It made no edit on the 429 images of the
    19 held-out organs.
  - U5's looser rule (its eighth amendment, the "tolerant" rule) made 32 edits there: 10 beneficial, 16 harmful,
    6 neutral. Against the strong native baseline it changed mean per-organ F1 by -0.0006 [-0.0025, +0.0005].
  - The same tolerant rule with operators chosen without failure evidence did as well, within -0.0001
    [-0.0005, +0.0001].
- **Lesson.** Neither rule separated help from harm. The strict rule demands zero harm on every demonstration organ
  and unanimous agreement, so it refuses every edit whose benefit varies across organs. The tolerant rule accepts a
  majority-vote program whose harm was never measured.
- **Direction (this study).** Replace both by a calibrated acceptance rule. Its threshold is set on calibration
  images only, to bound the harmful-edit rate and to require a positive lower confidence bound on the per-image F1
  gain. It is frozen, then tested once on fresh held images from a source that no CORA study has used.

## 2. Question and hypotheses

**Question.** Can a calibrated acceptance rule let CORA's failure-grounded edits improve a strong segmentation
baseline on fresh held images, while the harmful-edit rate stays below its calibrated bound? And does the choice of
operators by failure evidence matter under that rule?

- **H1 (primary).** On the fresh held images, CALIBRATED raises mean per-image object F1 above STRONG_NATIVE, AND its
  harmful-edit rate (harmful edits / accepted edits) is at most the calibrated bound, alpha = 0.60.
- **H2 (co-primary).** On the same images, CALIBRATED raises mean per-image object F1 above CAL_BLIND. CAL_BLIND is
  the same rule with the same operator budget, but its operators are chosen without failure evidence.
- **Secondary, descriptive.** CALIBRATED against STRICT, TOLERANT, CAL_SHUFFLED and MATCHED_SEARCH; every arm against
  STRONG_NATIVE.

The result is reported whichever way it falls. Every negative is written as result, then lesson, then direction.

## 3. Data

### 3.1 Calibration and development: NuInsSeg calibration organs only

- **What is used.** U5's 12 NuInsSeg calibration organs, 236 images. Its 6 induction organs hold 92 of them and its
  6 validation organs 144.
- **What is reused, read-only.** U5's starting segmentation, intensity images, low-threshold labels, calibration
  references and failure records (`/path/to/bio_data/work/nuinsseg/`).
- **What is not used.** U5's 19 evaluation organs (429 images), which U5 consumed.

### 3.2 Fresh held data: PUMA (choice and reasons; details in `DATA_MANIFEST.md`)

PUMA is the melanoma dataset of Zenodo record 13859989 (CC BY 4.0). It has 206 regions of interest (ROIs), stained
with haematoxylin and eosin (H&E), of 1024 x 1024 pixels at 40x:
one per specimen, from 103 primary and 103 metastatic melanomas. Each ROI has an expert-corrected nucleus polygon for
every nucleus. It is eligible because:
- its licence is CC BY 4.0, read from the Zenodo record's metadata;
- it has instance-level reference outlines;
- it is not in StarDist `2D_versatile_he`'s training data (MoNuSeg 2018 training and TNBC);
- no CORA study has used it (`records/` and the study documents were searched).

The other candidates were not chosen:
- BBBC038 (CC0) is reserved by the author's decision record for another of the author's papers.
- CryoNuSeg is MIT-licensed, not CC0 or CC BY, and has only 30 images.
- MoNuSeg and TNBC are StarDist training data.
- PanNuke and Lizard are candidates for that other paper.
- NuInsSeg's evaluation organs, MoNuSAC and LIVECell were consumed by U5.

### 3.3 The format ROI

- **Choice.** Before anything was opened, one ROI was fixed as the one with the smallest sha256 of
  `"calacc_format:<roi>"`: `training_set_primary_roi_028`.
- **What was opened.** Only its image and polygons, to check formats, and one StarDist run, for timing.
- **What was not done.** Its F1 was not computed.
- **Status.** It is excluded from the held set and from the reserve.

### 3.4 Held images, chosen after GO

- **The salt.** The salt is the sha256 of the bytes of `GO_CAL`, the file the coordinator writes in this folder after
  review.
- **Selection.** Within each stratum (primary, metastatic), the 102 or 103 remaining ROIs are sorted by sha256 of
  `"<salt>:<roi>"`. The first 50 are held, so 100 ROIs are held in all.
- **The reserve.** The other 105 ROIs are the reserve. This study never opens them; they are kept for one later
  replication.
- **What may be opened when.** No held image is opened before GO. No held reference is decoded before every arm's
  decisions are hashed in `DECISIONS_FROZEN.json` (`cadata.Reader` enforces both).
- **Parents.** Each held ROI is its own parent. The archive encodes no patient, so a patient who gave both a primary
  and a metastatic specimen cannot be detected (section 12).

## 4. Baseline and the starting segmentation (reused unchanged)

- **NATIVE.** StarDist 0.9.2 `2D_versatile_he` at its own thresholds (probability 0.6925, non-maximum suppression
  (NMS) 0.3).
  - Input: RGB normalized jointly over the three channels at the (1, 99.8) percentiles, as in U5's `seg_stardist.py`.
- **TUNED.** U5's thresholds, tuned on the NuInsSeg calibration images (probability 0.4562, NMS 0.3). Nothing is
  tuned on PUMA.
- **STRONG_NATIVE.** TUNED minus U5's calibration-chosen deletion rule: delete objects that touch at least 3 others
  (`STRONG_NATIVE_RULE.json`, applied with U5's features).
- **LOW.** Probability 0.2281 (the tuned threshold halved). It supplies `add_lowthresh`'s candidates.
- **Intensity image.** Haematoxylin optical density (`rgb2hed`, channel 0), normalized at (1, 99.8), as in U5.
- **No ignore regions.** PUMA has no ambiguous-area masks, so nothing is excluded from matching.
- **Every grammar arm starts from STRONG_NATIVE.** An arm that abstains everywhere equals STRONG_NATIVE exactly.

## 5. Arms

### 5.1 Operators and failure evidence (U5's, unchanged)

- **Operators.** U5's 11 literature operators (`u5core.py`), with U5's typed programs (theta, guard) and conflict
  rule.
- **Failure evidence on the NuInsSeg induction organs, computed by `u5induce.specify('nuinsseg')`.** It has two
  parts.
  - U5's probes of the frozen CORA component found no fitting program for any probed class. Every probed class was
    "not found within budget".
  - Per-class oracle gains: ADD 0.240, SPLIT 0.116, DELETE 0.059, GROW 0.046, SHRINK 0.038, MERGE 0.022, FILL 0.
- **Priority order.** `add_lowthresh`, `split_dt`, `split_int`, `delete`, `clear_border`, `close`, `dilate`, `open`,
  `erode`, `merge_pairs`.

### 5.2 Equal budget

- **Every CORA arm gets K = 3 operators.**
  - Each arm receives exactly 3 operators on the same 236 images. Under fixed-sequence testing (section 6) it stops
    at its first operator that is not accepted.
  - Each arm runs in its own process, so no arm reuses another's cached unit tables. In U5, the controls were
    CPU-unmatched because they did.
  - Each arm's CPU is measured and reported.
- **Why K = 3.** U5 found specification not selective: 10 of 11 operators were specified. So failure evidence can
  matter only through priority under a budget, and 3 is the budget of U5's exploratory budgeted-selection analysis.
- **The failure-evidence operators** for K = 3 are `add_lowthresh`, `split_dt` and `split_int`.
- **A disclosed look.** During development, U5's fixed control seeds were drawn for K in {3, 4, 5}. For K = 3, none
  of their 10 draws contains `add_lowthresh`. So that no one could have chosen the draws, the held run's control seeds
  come from the GO salt (section 5.3).
- **MATCHED_SEARCH's budget** is CALIBRATED's measured calibration CPU plus the 59.7 CPU-s of U5's failure probes on
  the NuInsSeg induction organs, which CALIBRATED's operator order uses.

### 5.3 The arms

| arm | operators | acceptance |
|---|---|---|
| STRONG_NATIVE | none | none (the baseline, equal to abstaining everywhere) |
| STRICT | failure-evidence first 3 | U5's verify-or-abstain rule (`u5policy.verify`, unchanged): harmless fit on every demonstration organ, leave-one-organ-out, unanimity, restart |
| TOLERANT | failure-evidence first 3 | U5's tolerant rule (`u5policy.verify_tolerant`, unchanged): top program in at least 2/3 of the leave-one-organ-out folds, harming no demonstration organ |
| CALIBRATED | failure-evidence first 3 | the calibrated rule, section 6 (new) |
| CAL_BLIND (5 seeds) | 3 drawn uniformly from the 11 | the calibrated rule |
| CAL_SHUFFLED (5 seeds) | first 3 specified from failure records and oracle gains whose class labels are deranged (U5's procedure), padded at random if fewer | the calibrated rule |
| MATCHED_SEARCH | all 11 | none: U5's static beam search (`u5static.fit_matched`, unchanged) by pooled calibration F1, with CALIBRATED's charged CPU (section 5.2) |
| MATCHED_SEARCH_U5 (descriptive) | U5's frozen program | U5's own NuInsSeg matched-search program (`POLICY_FREEZE.json`, sha256 `a67326dc...`): add_lowthresh, delete, erode, fitted by U5 on the same 12 calibration organs with 858 CPU-s. Not compute-matched |
| NATIVE, TUNED | | descriptive |

- **Demonstrations.** Every arm uses all 12 calibration organs. U5's section 9 admission step is not used: every
  CORA arm receives its 3 operators directly and differs only in the acceptance rule (STRICT, TOLERANT, CALIBRATED) or
  in the operator choice (the controls).
- **Control seeds in the held run.** The seeds are the integer value of the first 8 hexadecimal digits of
  sha256(`"<salt>:blind:<r>"`), sha256(`"<salt>:shuffled:<r>"`) and sha256(`"<salt>:pad:<r>"`), for r = 1 to 5.
  Development uses U5's seeds, 7000 + r, 8000 + r and 9000 + r. A control family's score is the mean over its 5
  seeds, image by image.

## 6. The calibrated acceptance rule (exact; `scripts/calrule.py`)

The operators are processed in the arm's order, each on the current segmentation of the calibration images, after
the earlier operators' accepted edits. For operator w:

1. **Programs.** These are U5's programs for w, enumerated by `u5policy.Space`, unchanged: a theta value and a guard
   of 0 to 2 decile predicates on the unit features.
   - Every calibration image is its own parent, so each program's per-image F1 change is the exact sum of its units'
     effects.
   - Each selected unit is also judged alone, as U5's evaluator judges edits:
     - beneficial: more matched objects, or an unmatched object removed;
     - harmful: fewer matched objects, or an unmatched object added;
     - neutral: otherwise.
2. **Leave-one-organ-out cross-fitting over the 12 calibration organs.**
   - **The fold program.** In the fold of organ o, the fold program is the program with the largest pooled F1 gain
     on the other 11 organs among programs that meet four conditions there:
     - they make at least one edit;
     - they have no conflicting selection (U5's executor rule);
     - they raise the pooled F1;
     - their harmful-edit rate is at most the in-fold limit lambda = 0.40.
   - **Ties** are broken as in U5: fewer edits, then fewer predicates, then enumeration order.
   - **Out-of-fold outcomes.** The fold program is applied to organ o's images. This gives out-of-organ per-image F1
     changes and edit counts. A fold without a program abstains there.
3. **Certification, the calibrated threshold.** w is accepted only if both bounds hold, each one-sided at level 0.05:
   - (a) the lower bound of the mean out-of-organ per-image F1 change is above 0;
   - (b) the upper bound of the out-of-organ harmful-edit rate is at most the bound alpha = 0.60.
   - **How the bounds are computed.** Both are organ-clustered t bounds: cluster-robust standard errors over the 12
     organs (organ sums of residuals, factor G / (G - 1)) with a Student t quantile on G - 1 = 11 degrees of freedom.
     The harmful-edit rate's standard error comes from linearizing the ratio.
   - **Edge cases.** An operator with no out-of-organ edit is not accepted.
   - **Fixed sequence.** An arm tests its 3 operators in its own order and stops at the first operator that is not
     accepted. This fixed-sequence testing keeps the family-wise error at 0.05 without splitting it, and gives the
     operator order a real role.
   - **Descriptive only.** Organ-cluster percentile bootstrap bounds (10,000 resamples, `default_rng(0)`) are
     recorded beside the t bounds.
4. **The final program and its application.**
   - The final program is chosen by step 2's rule on all 12 organs.
   - It is certified by exact execution (`u5run.certify`, unchanged): scored counts must equal executed counts.
   - It is applied with U5's executor, which asserts accepted == applied == logged.
   - It is applied to the calibration images (so later operators see its edits) and, in the held run, to the held
     images.

- **What the bound means.** Under exchangeable organs, (b) bounds the harmful-edit rate on new organs of the same
  source at 95% confidence. PUMA is a new source (another institution, scanner and annotation process), so the held
  test asks whether the bound survives that shift. It is not guaranteed to.

### 6.1 How the constants were reached (development on the 12 calibration organs only, before GO)

1. **Version 1, fixed first.**
   - One value, 0.20, served as both the in-fold limit and the certified bound. The bounds were percentile organ
     bootstraps at 0.05 / 3 (Bonferroni over the 3 operators).
   - Result: it accepted no operator (`development/v1_alpha020/`).
   - `add_lowthresh` made 8 out-of-organ edits on the 236 images: 4 beneficial, 3 harmful.
   - On the development split, CALIBRATED made no edit. TOLERANT raised per-image F1 by +0.0147 [+0.0064, +0.0241] on
     the 144 validation images, with 91 harmful edits among 185 accepted edits (73 beneficial).
2. **The scan** (`development/ALPHA_SCAN.json`; each operator alone; version 1's semantics).
   - Only `add_lowthresh` had an out-of-organ gain: up to +0.020 mean per-image F1.
   - Its out-of-organ harmful rate was higher than the in-fold limit at every setting: 0.375 at a limit of 0.2, 0.413
     at 0.3, 0.436 at 0.4, and 0.546 at 0.5. A program chosen on some organs is more harmful on the others.
   - No other operator had a certified gain:
     - `dilate`: +0.0006, lower bound 0;
     - `open`: +0.0001;
     - `erode`, `delete` and `merge_pairs`: negative;
     - the two splits, `close` and `fill_holes`: no qualifying program.
3. **Lesson.**
   - The limit used to choose a program must be stricter than the bound it is certified against.
   - Re-detected nuclei raise F1 even when about 4 in 10 of them are false. At an F1 near 0.5, a true addition gains
     more than a false one costs: the break-even false share is 1 - F1 / 2, about 0.75.
4. **Version 2.** The in-fold limit became 0.40 (the scanned limit with the largest out-of-organ gain lower bound) and
   the bound 0.60 (that setting's out-of-organ upper bound, 0.581, rounded up to the next tenth).
5. **A noise check.** On a synthetic test with 6 organs, operators whose edits are pure noise were sometimes accepted
   by the percentile bootstrap:
   - 2 of 5 at first;
   - 20 of 120 at a nominal 5% in a larger check.
   - Organ-clustered t bounds accepted 9 of 120.
6. **Version 3, final.** The rule switched to the t bounds at one-sided 0.05, with fixed-sequence testing over the
   operators (`tests/test_calacc.py` keeps the noise check).
   - The final-rule scan is `development/LAMBDA_SCAN_FINAL.json`. With in-fold limits of 0.3 and 0.4,
     `add_lowthresh` is accepted:
     - at 0.3: gain +0.0055, lower bound +0.0007; harmful rate 0.413, upper bound 0.485;
     - at 0.4: gain +0.0168, lower bound +0.0044; harmful rate 0.436, upper bound 0.530.
   - With limits of 0.5 and above it is not accepted, because the harmful-rate upper bound reaches 0.68.
   - So 0.40 and 0.60 stand.
   - Under the final rule, `dilate` alone is also accepted: +0.0006 mean per-image F1, 48 out-of-organ edits, none
     harmful. It is not among the failure-evidence operators.
7. **What this means for the certificate.** Every choice was made on the 12 NuInsSeg calibration organs. No PUMA image
   other than the format ROI was opened. The limit and the bound were chosen while looking at the same organs'
   out-of-organ results, so the calibration certificate of the final configuration is optimistic. The held test on
   fresh PUMA ROIs is the clean check.

## 7. Development (calibration organs only; every number labelled DEVELOPMENT)

- **The final policy.** It uses demonstrations = all 12 calibration organs (236 images), with no queries.
  - It gives the frozen records in `data/work/cal/final/`, hashed in `FREEZE.json`; a copy is in
    `calibration/final/`.
  - **CALIBRATED** accepted `add_lowthresh`. Its leave-one-organ-out estimates come from all 12 folds:
    - mean per-image F1 change +0.0168, one-sided 95% lower bound +0.0044;
    - harmful-edit rate 147 of 337 out-of-organ edits (0.436), one-sided 95% upper bound 0.530.
  - **CALIBRATED's final program** is `add_lowthresh` where contrast > 0.635 and solidity > 0.973.
    - In-sample it makes 314 edits on the calibration images: 152 beneficial, 121 harmful, 41 neutral.
    - It raises pooled calibration F1 from 0.5032 to 0.5157.
  - **CALIBRATED's other operators.** `split_dt` had no qualifying program in any fold, so the fixed sequence stopped
    there and `split_int` was not tested.
  - **CALIBRATED's CPU** was 56.6 s, plus 59.7 s of U5's failure probes, so 116.3 s are charged.
  - **STRICT** made no edit: `add_lowthresh` failed leave-one-organ-out, and both splits had no fit. CPU 62.0 s.
  - **TOLERANT** accepted `add_lowthresh`. It made 20 calibration edits and raised pooled calibration F1 from 0.5032
    to 0.5045. CPU 68.5 s.
  - **MATCHED_SEARCH,** with 116.3 s, found one step: `add_lowthresh` where contrast > 0.551 and solidity > 0.906. It
    raises pooled calibration F1 from 0.5032 to 0.5217 in-sample. Its CPU was 122.6 s, stopped by the budget.
- **The development split.** Demonstrations are the 6 induction organs and queries the 6 validation organs
  (144 images).
  - All 13 CORA arms run, with U5's seeds for the controls, plus MATCHED_SEARCH with the development CALIBRATED CPU
    plus the probes' 59.7 s.
  - Scoring uses per-image contrasts with a 95% image bootstrap and a within-organ stratified bootstrap
    (`development/DEV_RESULTS.json`).
  - **CALIBRATED made no edit.** With 6 demonstration organs its `add_lowthresh` certificate failed:
    - mean +0.0081, lower bound -0.0021 (t on 5 degrees of freedom);
    - harmful rate 119 of 221 (0.538), upper bound 0.810.
  - **STRICT and all 10 control seeds** made no edit either.
  - **TOLERANT** changed per-image F1 by +0.0147 [+0.0064, +0.0241] over the 144 validation images. It accepted 185
    edits: 73 beneficial, 91 harmful (0.492).
  - **MATCHED_SEARCH** (63.9 CPU-s budget; one step, `add_lowthresh` with contrast > 0.653 and solidity > 0.906)
    changed per-image F1 by +0.0290 [+0.0178, +0.0408]. It accepted 395 edits: 154 beneficial, 194 harmful (0.491).
  - **Result, lesson, direction.**
    - Result: with only 6 organs, the calibrated rule abstained where two uncertified rules gained on held-out organs,
      with harmful rates near 0.49 (inside the 0.60 bound).
    - Lesson: the rule's price is power when organs are few.
    - Direction: the held run calibrates on all 12 organs, where the certificate holds (above).
- No held image enters development, and no development number is a held result.

## 8. Outcomes and analysis (held images; `caharness.py evaluate`)

- **Per held ROI.**
  - Object F1 at IoU > 0.5 (U5's matching; strict >, one-to-one).
  - AP: the mean over IoU 0.50 to 0.95 of TP / (TP + FP + FN).
- **Edits.** Every logged edit is replayed from STRONG_NATIVE and judged alone against the reference (U5's replay).
  The replayed final labels must equal the frozen labels.
  - Counts: accepted, beneficial, harmful, neutral.
  - Harmful-edit rate = harmful / accepted. Harm share = harmful / (beneficial + harmful). Edit precision =
    beneficial / accepted.
  - Each has a 95% bootstrap interval over ROIs. An empty denominator is undefined, never 0.
- **Contrasts.**
  - Each contrast is the mean over held ROIs of per-image F1 differences, with a 95% percentile bootstrap over ROIs
    (10,000 resamples, `default_rng(0)`; U5's `boot`).
  - A one-sided bootstrap p value comes from the same resamples. A bootstrap stratified by primary and metastatic is
    a sensitivity analysis.
  - Pooled F1 and AP are reported.
- **Primary family.** P1 is CALIBRATED minus STRONG_NATIVE. P2 is CALIBRATED minus CAL_BLIND (the mean over its 5
  seeds). Both p values are Holm-adjusted together. A hypothesis is supported if its Holm-adjusted one-sided p is at
  most 0.025 (two-sided family-wise 0.05) and its 95% interval lies above 0.
- **H1 needs both parts.** P1 must be supported, AND CALIBRATED's held harmful-edit rate (pooled over held ROIs) must
  be at most 0.60. The bound is "confirmed" if the upper end of the rate's 95% interval is also at most 0.60.
- **Label of CALIBRATED, applied in this order.**
  1. NON_DEGRADATION_ONLY: no accepted held edit.
  2. HARMFUL: the upper 95% bound of P1 is below 0.
  3. SUPPORTED: P1 is supported and the bound holds.
  4. GAIN_BUT_BOUND_EXCEEDED: P1 is supported, but the rate is above 0.60.
  5. BOUND_HELD_NO_MEASURED_GAIN: the rate is at most 0.60, but P1 is not supported.
  6. NO_MEASURED_GAIN: anything else.
- **FAILURE_EVIDENCE_MATTERS** is true only if P2 is supported.

## 9. Stop rules and the CPU cap

1. **Without GO_CAL,** the held chain exits (code 2) and opens nothing.
2. **The freeze check.** If any hash in `FREEZE.json` differs from the file on disk, the chain stops before choosing
   the held images.
3. **The record check.** The held run recomputes the calibration side of STRICT, TOLERANT and CALIBRATED. Its
   records (statuses, programs, bounds) must equal the frozen ones. Otherwise the chain stops before any held
   reference is decoded, and the difference is reported.
4. **A failed step** (for example the segmentation of any held ROI) stops the chain. Nothing is claimed from a
   partial run, and the failure is reported.
5. **The CPU cap** for the held chain is 43,200 CPU-s (12 CPU-h), checked before each step. At the cap no new step
   starts; the missing arms are reported, and a label that needs them is not given. About 1.2 CPU-h is expected
   (section 11).
6. **No re-run after a held reference is decoded,** except to finish an interrupted evaluation from the same frozen
   decisions.
7. **The reserve** of 105 ROIs is not opened by this study.

## 10. Freeze

`FREEZE.json` holds the sha256 of:
- this study's code, tests, `CONFIG.json`, this protocol, `ADAPTER_CARD.md` and `DATA_MANIFEST.md`;
- every reused U5 file: code, NuInsSeg records, failure-record files and the model;
- the downloaded archives and the format check;
- the frozen calibration records.

It also records that every file in U5's own `CODE_FREEZE.json` still matches. The held chain's first step is
`scripts/verify_freeze.py`.

## 11. Compute

- **Heavy steps** run in the project's shared CPU slots (`scripts/with_cpu_slot.sh`, nice 19), on CPU only.
- **Arm processes.** Up to 3 run at a time, with one BLAS thread each.
- **Expected held-chain CPU.** About 1.2 CPU-h, within a range of 0.8 to 3 CPU-h. The components:

| step | expected CPU |
|---|---|
| input conversion of 100 held ROIs | 2 to 3 min |
| StarDist on 100 ROIs, at 5.5 CPU-s per ROI (measured on the format ROI) | 10 min |
| STRONG_NATIVE | 3 to 5 min |
| 13 CORA arms: each recomputes its calibration side (56.6 to 68.5 CPU-s per arm measured) and computes held unit tables for the operators it accepts | 20 to 35 min |
| MATCHED_SEARCH and MATCHED_SEARCH_U5 applied to the held ROIs | 5 to 10 min |
| evaluation: reference rasterization, matching, replay of every edit | 5 to 10 min |

- **The cap** is 12 CPU-h (section 9).

## 12. Limits, fixed in advance

- **Reference.** PUMA's reference started from HoVer-Net outlines that experts corrected. Uncorrected traces of
  HoVer-Net's style could favour edits that move outlines toward it.
- **Parents.** ROIs are parents. Specimens from the same patient, if any, are correlated, and the archive cannot show
  it.
- **Domain proximity.** NuInsSeg's calibration organs include 12 melanoma images. PUMA is melanoma from another
  source.
- **One source.** Held images come from one source. A positive result shows transfer to one new source, not to
  histology in general.
- **The bound** is calibrated across organs of one dataset. Its validity on a new source is what is tested, not
  assumed.
- **Equal work** means equal operator budgets with measured CPU, and CALIBRATED's charged CPU for MATCHED_SEARCH. It
  does not prove equal search difficulty.

## 13. What may be claimed

- **If H1 is supported:** on 100 fresh held melanoma ROIs from a source no CORA study had used, the calibrated rule
  accepted edits that raised mean per-image F1 over the strong baseline, with the harmful-edit rate at or below its
  calibrated bound.
- **If H2 is also supported:** the failure-evidence choice of operators mattered under that rule.
- **Otherwise,** the label is reported with the per-operator calibration records, written as result, then lesson,
  then direction.
- **What is never claimed:**
  - that the bound is guaranteed under dataset shift;
  - that a matched-search contrast is CORA's contribution;
  - anything about the reserve.

## 14. Boundaries

- **Never touched:** CORA Step B, VDCG and other projects' job folders.
- **Never read:** files named `*_LOCAL.json`, authorization or answer-key files, anything under a folder named
  private, and a reserved private image folder. GO files are not read either. The held chain only hashes the bytes of
  `GO_CAL` to obtain the salt (section 3.4).
- **Read-only:** U5's study folder and its data folder. Every U5 module is imported with Python's `-B` flag, so no
  bytecode is written there.
- **Commits** include this study's own paths only, without trailers.
