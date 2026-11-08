# Result: a calibrated acceptance rule on 100 fresh held PUMA images (held run of 8 Nov 2026)

CORA is a research program by its sole author, Chimdi Walter Ndubuisi. This record reports the held run of the study
pre-registered in `PROTOCOL.md`, under the conditions of the pre-run review (`reviews/PRE_RUN_REVIEW.md`, section 3).
It was written after the run had finished, from the chain's own outputs. Nothing was rerun. It reads as result, then
lesson, then direction.

## Answer

- **Decision under the frozen rule: HARMFUL.** H1 is not supported. H2 is not supported.
- **P1, CALIBRATED minus STRONG_NATIVE:** -0.0020 in mean per-image F1 over the 100 held ROIs, 95% bootstrap interval
  [-0.0027, -0.0014]. Holm-adjusted one-sided p = 1.0, against the level 0.025.
- **Harmful-edit rate of CALIBRATED:** 430 harmful edits of 605 accepted, 0.711, 95% interval [0.662, 0.757]. The
  bound, 0.60, allowed at most 6 harmful edits in every 10 accepted. About 7 in 10 were harmful, and even the lower end
  of the interval is above the bound. **Bound confirmed: no.**
- **P2, CALIBRATED minus CAL_BLIND (mean of 5 seeds):** -0.0008 in mean per-image F1 over the 100 held ROIs,
  [-0.0011, -0.0006]. Holm-adjusted one-sided p = 1.0. The failure-evidence order (operators ranked by per-class oracle gains) did not beat random orders under stop-at-first-failure testing.
- **Honest framing.** The harmful-rate bound was relaxed from 0.20 to 0.60 during development because 0.20 accepted
  nothing, which makes it a weak safety promise. This study tests a calibrated acceptance rule, not learning from
  failure.

## Names used here

- **GO and the salt.** GO is the go-ahead file `GO_CAL`, written once after the pre-run review. The salt is the
  sha256 of its bytes; it fixes the held ROIs and the control seeds.
- **Held ROIs.** 100 regions of interest (ROIs) from PUMA (Zenodo record 13859989, CC BY 4.0): melanoma images
  stained with haematoxylin and eosin (H&E), of 1024 x 1024 pixels, chosen after GO by the salt. The **reserve** is the
  other 105 ROIs, never opened. The **format ROI** is the one ROI opened before GO, for a format check.
- **CPU-s** means CPU seconds.
- **Per-image F1.** Object F1 of one ROI. A predicted object and a reference nucleus match, one to one, when their
  intersection over union (IoU) is above 0.5. **AP** (average precision) is the mean, over IoU 0.50 to 0.95, of
  matched / (matched + unmatched predicted + unmatched reference).
- **The predecessor study** is the bioimage grammar study of 2 Nov 2026 (`experiments/universality_bio_grammar_20261103`).
  This study reuses its code, its NuInsSeg records and its 12 calibration organs (236 images), read-only.
- **Segmentations.**
  - NATIVE: StarDist `2D_versatile_he` at its own thresholds.
  - TUNED: StarDist at the predecessor study's thresholds, tuned on NuInsSeg calibration images.
  - LOW: StarDist at half the tuned probability threshold.
  - STRONG_NATIVE: TUNED minus the predecessor study's deletion rule (delete objects that touch at least 3 others). It
    is the baseline, and every CORA arm starts from it.
- **Edits.** The operator that mattered is `add_lowthresh`: it adds LOW objects where the current segmentation has
  none. Every accepted edit is replayed and judged alone against the reference: beneficial (more matched objects, or an
  unmatched object removed), harmful (fewer matched objects, or an unmatched object added), neutral otherwise. The
  **harmful-edit rate** is harmful edits / accepted edits.
- **CORA arms.** Each is offered 3 operators and starts from STRONG_NATIVE.
  - STRICT, TOLERANT and CALIBRATED apply three acceptance rules to the same 3 operators, in the failure-evidence
    order: `add_lowthresh`, `split_dt`, `split_int`. STRICT is the predecessor study's verify-or-abstain rule, TOLERANT
    its majority-vote rule, CALIBRATED the calibrated rule of `PROTOCOL.md` section 6.
  - CAL_BLIND: the calibrated rule with 3 operators drawn uniformly from the 11, for 5 seeds.
  - CAL_SHUFFLED: the calibrated rule with operators taken from failure records whose class labels are deranged, for
    5 seeds.
- **Search arms.** MATCHED_SEARCH is the predecessor study's static beam search over all 11 operators, without
  verification, given CALIBRATED's charged calibration CPU (116.3 CPU-s). MATCHED_SEARCH_U5 is the predecessor study's
  own frozen search program, fitted with 858 CPU-s, so not compute-matched.
- **The calibrated rule.** It accepts an operator only if, over leave-one-organ-out folds on the 12 calibration
  organs, the one-sided 95% lower bound of the mean per-image F1 change is above 0 AND the one-sided 95% upper bound of
  the harmful-edit rate is at most 0.60. It tests its 3 operators in order and stops at the first one it does not
  accept (stop-at-first-failure testing, also called fixed-sequence testing).
- **Operator statuses.**
  - ACCEPTED: both bounds held.
  - NO_OUT_OF_FOLD_EDIT: no fold made an edit on its left-out organ, so the operator is not accepted.
  - GAIN_NOT_CERTIFIED: the lower bound of the mean gain was not above 0.
  - NOT_TESTED_FIXED_SEQUENCE: not reached, because an earlier operator was not accepted.
  - STRICT's statuses: LOO_FAIL (failed leave-one-organ-out) and NO_FIT (no fitting program). TOLERANT's status
    EVIDENCE means accepted.
- **Hypotheses.**
  - P1 is CALIBRATED minus STRONG_NATIVE, and P2 is CALIBRATED minus CAL_BLIND (the image-by-image mean of its 5
    seeds). Each is the mean per-image F1 difference over the held ROIs.
  - A contrast is supported if its Holm-adjusted one-sided p (P1 and P2 adjusted together) is at most 0.025 AND its
    95% interval lies above 0.
  - H1 (primary): P1 is supported AND CALIBRATED's held harmful-edit rate is at most 0.60. H2 (co-primary): P2 is
    supported.

## 1. Result

### 1.1 Run facts

| item | value |
|---|---|
| freeze | commit `9f283c2c` (`9f283c2c4d000e3dc5627379f7d590cf60d0f219`); `FREEZE.json` sha256 `7e5c55efc625dc684c4a2de9469b605066781fc47cf49859c114dad31c3ef56f` |
| pre-run review | commit `dad82ffd` (`dad82ffd5bb1c53d2b72daef9affe547993c264a`), verdict PASS-WITH-NOTES; the file is unchanged since (sha256 `2d5e4887f004971f3891b4160693725549b60c859c96b228743bb5a5c3603a24`) |
| GO | commit `3d7fc39a` (`3d7fc39a1f421814043ac243220a58b79161652a`) at 07:36:59Z on 8 Nov 2026. It adds only `GO_CAL` (8 lines), written at 07:36:58Z and unchanged since |
| salt | sha256 of the bytes of `GO_CAL` = `0062d9bc5af711f341ee2329411742eb053a3c44f17cbbae1ddeb1644f447395`. The chain recorded it in `data/work/puma/HELD_MANIFEST.json`; recomputed after the run, it is equal |
| held chain | `scripts/run_after_go.py`, detached job `cal_calacc_held`, started from the project root at 07:36:59Z; EXIT 0 at 07:57:55Z, after 20 min 56 s |
| CPU | 1,938.3 CPU-s in all (0.54 CPU-h), 4.5% of the 43,200 CPU-s cap |
| held set | 100 ROIs: 50 of the 102 remaining primary ROIs and 50 of the 103 metastatic ROIs; 48,013 reference nuclei |
| reserve | 105 ROIs (52 primary, 53 metastatic), never opened. The format ROI is in neither set |

The chain's steps, from `data/work/held_chain.run.status` and `data/work/held_steps/CPU.json`:

| step | finished (UTC) | CPU-s |
|---|---|---|
| freeze check: 0 mismatches | 07:37:00 | 1.5 |
| held selection from the salt | 07:37:01 | 0.1 |
| input conversion, 100 ROIs | 07:37:11 | 9.4 |
| StarDist, 100 ROIs | 07:40:43 | 430.4 |
| STRONG_NATIVE, 100 ROIs | 07:40:56 | 12.8 |
| 13 CORA arms, each in its own process (13 of 13 exited 0) | 07:45:42 | 753.3 |
| MATCHED_SEARCH applied | 07:47:03 | 81.4 |
| MATCHED_SEARCH_U5 applied | 07:51:53 | 289.1 |
| frozen-record check and decision hashing | 07:52:04 | 9.8 |
| evaluation | 07:57:55 | 350.4 |
| total | | 1,938.3 |

- **The frozen-record check (stop rule 3) passed.** The held run recomputed the calibration side of STRICT, TOLERANT
  and CALIBRATED. Their statuses, programs and bounds equal the frozen ones, and no mismatch file exists.
- **Decisions were hashed before any reference was decoded.** The label maps and edit logs of all 18 arms went into
  `data/work/puma/DECISIONS_FROZEN.json` (sha256 `9454a9f411452e786d9747a64f9ba79ab2c32ccaed302cde905036b435ea3659`) at
  07:52:03Z. The evaluation re-checked all 36 hashes, then replayed every logged edit from STRONG_NATIVE; the replay
  reproduced the frozen labels.
- **CPU against the estimate.** The protocol expected about 1.2 CPU-h (range 0.8 to 3). The run used 0.54 CPU-h:
  StarDist took 4.3 CPU-s per ROI (5.5 on the format ROI), and the 13 arms 753 CPU-s (20 to 35 min expected). No arm
  was skipped.

### 1.2 Primary: P1 and the harmful-edit rate (pre-registered, confirmatory)

- **P1 = -0.0020** (-0.002038), 95% percentile bootstrap interval over the 100 ROIs [-0.0027, -0.0014]
  ([-0.002655, -0.001433]; 10,000 resamples, `default_rng(0)`).
  - 31 of 100 ROIs gained, 69 of 100 lost, 0 of 100 were unchanged.
  - None of the 10,000 resampled means was above 0, so the one-sided bootstrap p is 1.0. The Holm-adjusted p is 1.0,
    against the level 0.025. P1 is not supported.
  - Sensitivity analysis (pre-registered: the bootstrap stratified by primary and metastatic): [-0.0026, -0.0014].
  - Exploratory, per stratum: -0.0016 on the 50 primary ROIs, -0.0025 on the 50 metastatic ROIs.
  - Descriptive: pooled F1 0.8912 against 0.8931; AP changed by -0.0023 [-0.0029, -0.0017], with 19 of 100 ROIs
    gaining.
- **Harmful-edit rate of CALIBRATED on the held ROIs = 430 / 605 = 0.711**, 95% bootstrap interval over ROIs
  [0.662, 0.757].
  - 175 of 605 edits were beneficial (edit precision 0.289 [0.243, 0.338]), and 0 of 605 were neutral. Every accepted
    edit added an object, and each addition either matched a reference nucleus or did not.
  - In words: the bound 0.60 allows up to 6 harmful edits in every 10 accepted. On the held ROIs about 7 in 10
    accepted edits were harmful. The point rate is above the bound, and so is the lower end of its interval.
  - **The bound held: no (0.711 is above 0.60). Bound confirmed, that is, the upper end of the interval at most 0.60:
    no (0.757).**
  - For comparison (development, optimistic): on the calibration organs the out-of-organ rate was 147 of 337 edits
    (0.436), with an upper bound of 0.530.
- **Exploratory: how selective the program was.** CALIBRATED's final program (`add_lowthresh` where contrast > 0.635
  and solidity > 0.973) accepted 605 of the 6,043 LOW candidate objects on the 100 held ROIs (10.0%). On the 236
  calibration images it had accepted 314 of 2,097 (15.0%).

### 1.3 Co-primary: P2, the failure-evidence order against random orders

- **P2 = -0.0008** (-0.000815), 95% interval [-0.0011, -0.0006] ([-0.001062, -0.000573]). 31 of 100 ROIs gained and
  69 of 100 lost. The one-sided p is 1.0; Holm-adjusted together with P1, it is 1.0, against the level 0.025. P2 is not
  supported. Sensitivity analysis (stratified bootstrap): [-0.0011, -0.0006].
- **What H2 tests.** H2 is a test of the failure-evidence order against random orders under stop-at-first-failure
  testing. The failure-evidence order puts `add_lowthresh` first because the per-class oracle gains on the 6 NuInsSeg
  induction organs (the F1 that an oracle fix of each error class would recover there) rank ADD highest: 0.240,
  against 0.116 for SPLIT. This record does not attribute the order to CORA's probes: they found no fitting program for
  any probed class.
- **Each blind seed** (seed = the integer of the first 8 hexadecimal digits of sha256(`"<salt>:blind:<r>"`)):

| r | seed | 3 draws, in order | statuses, in order | `add_lowthresh` drawn | held edits | minus STRONG_NATIVE, 100 ROIs |
|---|---|---|---|---|---|---|
| 1 | 1037436653 | add_lowthresh, close, fill_holes | ACCEPTED; NO_OUT_OF_FOLD_EDIT; NOT_TESTED_FIXED_SEQUENCE | yes, first | 605 | -0.0020 [-0.0027, -0.0014] |
| 2 | 4131755104 | fill_holes, dilate, delete | NO_OUT_OF_FOLD_EDIT; NOT_TESTED_FIXED_SEQUENCE; NOT_TESTED_FIXED_SEQUENCE | no | 0 | 0, equal on 100 of 100 ROIs |
| 3 | 1278462664 | add_lowthresh, close, dilate | ACCEPTED; NO_OUT_OF_FOLD_EDIT; NOT_TESTED_FIXED_SEQUENCE | yes, first | 605 | -0.0020 [-0.0027, -0.0014] |
| 4 | 3096175386 | merge_pairs, erode, add_lowthresh | GAIN_NOT_CERTIFIED; NOT_TESTED_FIXED_SEQUENCE; NOT_TESTED_FIXED_SEQUENCE | yes, third, never reached | 0 | 0, equal on 100 of 100 ROIs |
| 5 | 772396818 | add_lowthresh, clear_border, fill_holes | ACCEPTED; GAIN_NOT_CERTIFIED; NOT_TESTED_FIXED_SEQUENCE | yes, first | 605 | -0.0020 [-0.0027, -0.0014] |

- **Why P2 is a fixed share of P1.** Seeds 1, 3 and 5 (3 of 5) accepted the same `add_lowthresh` program as
  CALIBRATED and produced the same held labels (identical label hash), so they equal CALIBRATED on 100 of 100 ROIs.
  Seeds 2 and 4 (2 of 5) abstained and equal STRONG_NATIVE. So P2 is exactly 2/5 of P1: -0.0008 = 0.4 x -0.0020.
  `add_lowthresh` was drawn at some position by 4 of 5 seeds, and first by 3 of 5.
- **The failing first operators, on the calibration organs (development).** merge_pairs (seed 4): mean per-image F1
  change -0.0019, lower bound -0.0038, harmful rate 0.571. clear_border (seed 5, second): -0.0002, lower bound
  -0.0005, harmful rate 1.0. fill_holes (seed 2) and close (seeds 1 and 3, second): no out-of-organ edit.
- **The draws were checked.** The 5 seeds and their draws were recomputed after the run from the salt with the frozen
  rule. All 5 equal the recorded ones.
- **Exploratory: an unusual draw.** Under uniform draws a seed puts `add_lowthresh` first with probability 1/11, so 3
  or more of 5 seeds doing so has probability about 0.0065. The review had expected that with probability at least
  0.59 no seed would apply it. The draw made the blind family closer to CALIBRATED. It cannot have changed CALIBRATED's label or H1: both depend only on P1 and the harmful-edit rate, and P1's Holm-adjusted p is 1.0 whatever P2's p is. For H2, any draw in which each seed either copies CALIBRATED or abstains gives P2 = (abstaining seeds / 5) x P1, which is at most 0 here. A draw in which a seed accepted another operator (for example `dilate`, the only other operator that passes alone on the calibration organs) would have edited differently, with an unknown held effect.

### 1.4 CAL_SHUFFLED

**CAL_SHUFFLED is descriptive; abstains for every salt by construction; its contrast equals P1.**

| r | seed | 3 operators, in order | first operator's status | held edits |
|---|---|---|---|---|
| 1 | 3413129579 | delete, clear_border, merge_pairs | GAIN_NOT_CERTIFIED | 0 |
| 2 | 1012084589 | close, dilate, fill_holes | NO_OUT_OF_FOLD_EDIT | 0 |
| 3 | 2436347614 | delete, clear_border, close | GAIN_NOT_CERTIFIED | 0 |
| 4 | 600659341 | merge_pairs, delete, clear_border | GAIN_NOT_CERTIFIED | 0 |
| 5 | 2604265663 | split_dt, split_int, fill_holes | NO_OUT_OF_FOLD_EDIT | 0 |

- 5 of 5 seeds abstained, so CAL_SHUFFLED equals STRONG_NATIVE on 100 of 100 ROIs. Their later operators were not
  tested.
- CALIBRATED minus CAL_SHUFFLED is -0.0020 [-0.0027, -0.0014], the same as P1. The two differ only by floating-point
  rounding (about 3 x 10^-18) from averaging 5 identical arrays. It is not separate evidence.

### 1.5 The other arms (descriptive)

Each change is the mean per-image F1 difference against STRONG_NATIVE over the 100 held ROIs, with its 95% bootstrap
interval.

| arm | what it applied on the held ROIs | accepted edits: beneficial / harmful / neutral | harmful-edit rate [95% interval] | mean per-image F1 | change against STRONG_NATIVE | ROIs gained / lost / equal | held CPU-s |
|---|---|---|---|---|---|---|---|
| STRONG_NATIVE | the baseline | none | | 0.8892 | | | |
| CALIBRATED | `add_lowthresh` (contrast > 0.635, solidity > 0.973) | 605: 175 / 430 / 0 | 0.711 [0.662, 0.757] | 0.8872 | -0.0020 [-0.0027, -0.0014] | 31 / 69 / 0 | 92.2 |
| STRICT | nothing: `add_lowthresh` LOO_FAIL; `split_dt`, `split_int` NO_FIT | 0 | undefined | 0.8892 | 0 | 0 / 0 / 100 | 59.9 |
| TOLERANT | `add_lowthresh` (its majority program) | 318: 39 / 279 / 0 | 0.877 [0.840, 0.912] | 0.8869 | -0.0023 [-0.0029, -0.0018] | 5 / 83 / 12 | 95.9 |
| CAL_BLIND, mean of 5 seeds | see section 1.3 | 605 in 3 of 5 seeds, 0 in 2 of 5 | 0.711 in each editing seed | 0.8880 | -0.0012 [-0.0016, -0.0009] | 31 / 69 / 0 | 15.8 to 81.1 per seed |
| CAL_SHUFFLED, mean of 5 seeds | nothing | 0 in 5 of 5 seeds | undefined | 0.8892 | 0 | 0 / 0 / 100 | 14.2 to 28.8 per seed |
| MATCHED_SEARCH | `add_lowthresh` (contrast > 0.551, solidity > 0.906), no verification | 3,271: 735 / 2,536 / 0 | 0.775 [0.750, 0.799] | 0.8749 | -0.0143 [-0.0162, -0.0125] | 6 / 94 / 0 | 77.6 to apply |
| MATCHED_SEARCH_U5 | `add_lowthresh`, `delete`, `erode` (the predecessor study's frozen program) | 17,694: 1,279 / 3,018 / 13,397 | 0.171 [0.154, 0.188] | 0.8698 | -0.0194 [-0.0216, -0.0172] | 1 / 99 / 0 | 285.3 to apply |
| NATIVE | StarDist at its own thresholds | | | 0.8610 | -0.0282 (difference of means, no interval) | | |
| TUNED | the tuned thresholds, without the deletion rule | | | 0.8892 | -0.00001 (difference of means, no interval) | | |

- **Strict rule.** STRICT abstained on all 100 ROIs, so it lost nothing. CALIBRATED minus STRICT equals P1.
- **Tolerant rule.** TOLERANT made fewer edits than CALIBRATED (318 against 605), but more of them were harmful (279
  of 318). CALIBRATED minus TOLERANT is +0.0003 [-0.0003, +0.0009], with 50 of 100 ROIs gaining, 46 losing and 4
  equal: no measured difference.
- **Static search.** Both searches lost more than CALIBRATED: CALIBRATED minus MATCHED_SEARCH is +0.0123
  [+0.0107, +0.0139] (96 of 100 ROIs gained), and CALIBRATED minus MATCHED_SEARCH_U5 is +0.0173 [+0.0153, +0.0195]
  (98 of 100). MATCHED_SEARCH_U5's harmful rate is low only because 13,397 of its 17,694 edits were neutral; among its
  4,297 decisive edits, 3,018 were harmful (0.702 [0.685, 0.720]). These matched-search contrasts are descriptive and
  are not claimed as CORA's contribution (protocol section 13).
- **Native baselines.** The tuned thresholds raised mean per-image F1 from 0.8610 (NATIVE) to 0.8892 (TUNED), and the
  deletion rule then changed almost nothing (STRONG_NATIVE 0.88919 against TUNED 0.88918). CALIBRATED minus NATIVE is
  +0.0262 [+0.0211, +0.0314] (85 of 100 ROIs gained); CALIBRATED minus TUNED is -0.0020 [-0.0026, -0.0014] (33 gained,
  66 lost, 1 equal).

### 1.6 The decision under the frozen rule

- **The label order of protocol section 8, applied in order.**
  1. NON_DEGRADATION_ONLY (no accepted held edit): no. CALIBRATED accepted 605 edits.
  2. HARMFUL (the upper 95% bound of P1 is below 0): yes. The upper bound is -0.0014.
- **CALIBRATED's label: HARMFUL.**
- **H1: not supported.** P1 is not supported (Holm-adjusted p 1.0, above 0.025; the interval lies below 0), and the
  harmful-edit rate, 0.711, is above 0.60.
- **H2: not supported** (Holm-adjusted p 1.0; the interval lies below 0). The evaluator's flag
  FAILURE_EVIDENCE_MATTERS, true only if P2 is supported, is false.
- **Claims (protocol section 13).** Neither positive claim may be made. The label is reported with the per-operator
  calibration records (section 1.7). Never claimed: that the bound is guaranteed under dataset shift; that a
  matched-search contrast is CORA's contribution; anything about the reserve.

### 1.7 Per-operator calibration records (development, optimistic)

These records were computed on the 12 NuInsSeg calibration organs (236 images) before GO and frozen. The held run
recomputed them identically. They are optimistic: the in-fold limit 0.40 and the bound 0.60 were chosen while looking
at these organs' out-of-organ results.

| arm | operator | status | leave-one-organ-out estimates | in-sample, 236 calibration images |
|---|---|---|---|---|
| CALIBRATED | `add_lowthresh` | ACCEPTED | mean per-image F1 change +0.0168, one-sided 95% lower bound +0.0044 (t on 11 degrees of freedom); harmful 147 of 337 out-of-organ edits (0.436), upper bound 0.530; 12 of 12 folds had a fold program | final program: contrast > 0.635 and solidity > 0.973; 314 edits (152 beneficial, 121 harmful, 41 neutral); pooled F1 0.5032 to 0.5157 |
| CALIBRATED | `split_dt` | NO_OUT_OF_FOLD_EDIT | no qualifying program in any of the 12 folds | none |
| CALIBRATED | `split_int` | NOT_TESTED_FIXED_SEQUENCE | | |
| STRICT | `add_lowthresh` | LOO_FAIL | | 0 edits |
| STRICT | `split_dt`, `split_int` | NO_FIT | | |
| TOLERANT | `add_lowthresh` | EVIDENCE (accepted) | its top program in 9 of 12 folds | 20 edits; pooled F1 0.5032 to 0.5045 |
| TOLERANT | `split_dt`, `split_int` | NO_FIT | | |

### 1.8 The format ROI: a pre-GO look

- **Choice.** Before anything was opened, the format ROI was fixed as the ROI with the smallest sha256 of
  `"calacc_format:<roi>"`: `training_set_primary_roi_028`. It is in neither the held set nor the reserve.
- **When.** It was opened at 06:38Z to 06:39Z, before the rule reached its final version (final calibration chain,
  07:03Z to 07:10Z), for a format check and one StarDist timing run (5.5 CPU-s).
- **What was seen, counted here as a pre-GO look at the held source.** 292 reference nuclei, against 252 StarDist
  objects at NATIVE, 349 at TUNED and 412 at LOW. Its F1 was not computed.
- **Exploratory, after the result.** On that ROI TUNED already found more objects than there were nuclei (349 for
  292). The held ROIs show the same pattern: 50,894 TUNED objects for 48,013 reference nuclei, and LOW adds about 6,000
  more (56,915). The review had noted before GO that this pattern does not favour an operator that adds objects.

### 1.9 The dry run

- **What it did.** `tests/dryrun_held.py` ran the whole held path on 4 NuInsSeg calibration images posing as held ROIs.
  No PUMA image was touched. It covered STRONG_NATIVE; the five arms CALIBRATED, STRICT, TOLERANT, CAL_BLIND_1 and
  CAL_SHUFFLED_1; MATCHED_SEARCH and MATCHED_SEARCH_U5; the frozen-record check; decision hashing; and the evaluator.
  Its numbers mean nothing as results, because those 4 images are calibration images.
- **A deleted first job.** A first dry-run job folder was deleted at once, because its command line named a temporary
  path.
- **A failed dry run.**
  - Result: `cal_calacc_dryrun2` exited 1 at 07:06:48Z, because the final calibration chain had not yet written
    `MATCHED_SEARCH.json` (written at 07:06:54Z). PROGRESS.md does not mention this run.
  - Lesson: a dry run that reads frozen records must wait until the chain that writes them has exited.
  - Direction: start such a dry run only after that chain's EXIT line.
- **The passing dry run.** `cal_calacc_dryrun3` started at 07:07:12Z, after all 4 final records existed, and exited 0
  at 07:09:56Z. Its stand-in freeze lists the 4 frozen record hashes, which equal those in `FREEZE.json`. It started while the final calibration chain was still running its development arms (that chain exited at 07:10:20Z), so it did not follow the direction above. The 4 final records it read were last written at 07:06:54Z and equal the frozen ones, so the overlap changed nothing.
- **It ran a copy.** The copy, `data/work/dryrun/dryrun_held.py`, differs from the frozen `tests/dryrun_held.py` only
  in its docstring: 2 lines in the frozen file, 1 line in the copy (checked again for this record).
- **Its checks passed.** STRONG_NATIVE reproduced the predecessor study's starting segmentation on 4 of 4 images (pre-run
  review). The recomputed calibration records equalled the frozen ones. The evaluator, run twice on the same frozen
  decisions, wrote identical `RESULTS.json` files apart from the timestamp (checked again for this record).

### 1.10 The four calibration listing hashes, recomputed after the run

Condition 3 of the review: after the run, the listing hashes of the per-image arrays the calibrated rule reads were
recomputed with the review's rule (the sha256 of the sorted lines `"<file> <sha256>"`, as in `make_freeze.tree_sha`),
over the 236 calibration images' files in each folder under `/path/to/bio_data/work/nuinsseg/`.

| folder | files | sha256 of listing, after the run | equal to the review's |
|---|---|---|---|
| `seg/S` (starting segmentation) | 236 of 236 | `2c07111cb2d838bf8abab5e193adeb6528cdded645a58909f65f68c495fa58c4` | yes |
| `seg/low` (low-threshold labels) | 236 of 236 | `13a1fbdb24984d2350e2492fdcfad58cb4849809811a03214108a1274e98ccae` | yes |
| `int` (intensity images) | 236 of 236 | `7e9e53f37645beb9f69aefd6e3e9e164e9ce609a3be60f959c84e0f4d374cb63` | yes |
| `ref_cal` (calibration references) | 236 of 236 | `f9e0134a07dee47fa790c03b5ab5c6255d819a1fc997014138c2b78db663bcd8` | yes |

- **All 4 of 4 match, so there is no deviation.** The newest of these files dates from 2 Nov 2026.
- **Other checks after the run.**
  - `FREEZE.json`: 61 of 61 checks match. They are the 56 file entries other than the 2 PUMA archives, the second
    copy of each of the 4 calibration records, and the listing hash of the predecessor study's 189 probe records. The
    archives were not re-read after the run; the chain's freeze check matched them at 07:37:00Z.
  - The predecessor study's `CODE_FREEZE.json`: 24 of 24 entries match.
  - `DECISIONS_FROZEN.json`: 36 of 36 decision files match, and so do the hashes it records for `HELD_MANIFEST.json`
    and `FREEZE.json`.

### 1.11 Restarts and deviations

- **Held chain: no restart.** It started once and ran each of its 10 steps once. Condition 2 of the review (delete the
  `verify_freeze` marker before any restart) never applied.
- **Frozen files: no change after GO.** No tracked file of this folder changed. The only files written after GO are
  under `data/work/` and `results/`, and the checks of section 1.10 match.
- **Deviations from the protocol in the held run: none found.**
- **Restarts and process notes before GO** (from PROGRESS.md and the review; none touched a held image):
  - The first calibration chain, `cal_calacc_chain`, was stopped while it waited for a CPU slot, before it ran
    anything, so that Python's `-B` flag could be added. Its status file has no EXIT line. The chain then ran as
    `cal_calacc_chain2` (version 1 of the rule, EXIT 0) and `cal_calacc_chain3` (final version, 07:03:30Z to 07:10:20Z,
    EXIT 0).
  - The dry run was started three times (section 1.9).
  - An early smoke test wrote one bytecode file into the predecessor study's git-ignored `scripts/__pycache__/`
    folder (06:44Z) and it was deleted at 06:48Z. No source changed: 24 of 24 entries of that study's
    `CODE_FREEZE.json` still match after the run.
  - The project's autosave committed this folder's early files (commit `3e2d8d37`) before its `.gitignore` existed,
    including 24 files under `data/`: the 3 files of the StarDist model copy (among them the 5,774,704-byte `weights_best.h5`); 4 text files of the download folder (the Zenodo record, the download script and the 2 observed checksum lists); 14 calibration records from version 1 of the rule (4 final, 10 development), since updated in `8a8dbd61`; the calibration chain's status file; and the 2 format-check records. No image, mask or archive was among them.
- **Notes that are not deviations of the held run.**
  - `evaluate()` does not compute "bound confirmed". It was computed here from `harmful_rate_ci95`, as condition 6
    requires.
  - The CPU, 0.54 CPU-h, was below the protocol's expected range of 0.8 to 3 CPU-h. The range was an estimate, not a
    rule.
  - `development/LAMBDA_SCAN_FINAL.json` says "level 0.05/3 one-sided", but its final mode used 0.05 (review,
    section 2). The record is hashed, so it is left as is.
  - The held run's records were committed on purpose past this folder's `.gitignore`, which keeps new files under
    `data/` out of git. PROGRESS.md had said that the held run's PUMA-derived files would never be committed. Only
    records went in (58 files in commit `646a622a`: JSON records, logs and step markers). No image, label map,
    intensity array or archive was committed.
- **One boundary crossed while this record was written.**
  - Result: after the evaluation had finished, the text of `GO_CAL` was displayed once, together with other files of
    this folder. Section 14 of the protocol says GO files are not read, only hashed. The display showed that `GO_CAL`
    names the review by its commit (`dad82ffd`) rather than by the file sha256 that the review's section 4 suggested;
    the review file is unchanged since that commit.
  - Lesson: it happened after the held set, the control seeds, every decision and the evaluation were fixed and
    hashed, so it could not change any number here. It still breaks the stated rule.
  - Direction: later steps hash `GO_CAL` and never display it.

## 2. Lesson

1. **The certificate did not survive the move to a new source.**
   - Result: on the calibration organs (development, optimistic), the out-of-organ harmful rate of `add_lowthresh`'s fold programs was 147 of 337 (0.436), with an upper bound of 0.530. On the held PUMA ROIs, the final program's rate was 430 of 605 (0.711) [0.662, 0.757].
   - Lesson: a bound calibrated across organs of one dataset did not hold on a source with another institution,
     scanner and annotation process. The protocol said it was not guaranteed to, and it did not.
2. **A harmful-rate bound is not a promise of gain when the baseline is strong.** (Exploratory, computed after the
   result with the break-even rule of protocol section 6.1.)
   - Added objects raise F1 on average only if the share of false additions is below about 1 - F1 / 2.
   - On the calibration organs (development) pooled F1 was 0.503, so the break-even share was about 0.75, and an out-of-organ rate of 0.44 (development, optimistic) went with a gain.
   - On PUMA, STRONG_NATIVE's pooled F1 is 0.893, so the break-even share is about 0.55. The held rate, 0.711, is above
     it, and so is the bound itself, 0.60. At this baseline even an edit set exactly at the bound would lower F1.
   - Lesson: a bound written as a fixed rate, blind to the target's baseline accuracy, cannot carry a gain from a weak
     baseline to a strong one.
3. **The baseline already found about as many objects as there were nuclei.** (Exploratory.) TUNED gave 50,894
   objects for 48,013 reference nuclei on the held ROIs. Adding LOW objects mostly added false ones: 430 of the 605
   accepted additions were harmful.
4. **Abstention was the best CORA outcome on this source.** STRICT made no edit and lost nothing. Every rule that
   edited lost: CALIBRATED -0.0020 (605 edits), TOLERANT -0.0023 (318 edits), MATCHED_SEARCH -0.0143 (3,271 edits),
   MATCHED_SEARCH_U5 -0.0194 (17,694 edits), each over the 100 held ROIs.
5. **The co-primary could not isolate the order.**
   - With one useful operator and stop-at-first-failure testing, a blind seed either draws `add_lowthresh` first and
     copies CALIBRATED, or abstains. So P2 is a fixed share of P1 (here 2/5), and its sign follows P1's.
   - H2 measured whether putting `add_lowthresh` first beat random orders. Because that operator's edits hurt on
     PUMA, putting it first did worse.
   - It says nothing about CORA's probes, which found nothing. The shuffled control was decided before any held image
     was seen.
6. **The bound was weak, and it was set after looking.**
   - The harmful-rate bound was relaxed from 0.20 to 0.60 during development, on the same 12 calibration organs,
     because 0.20 accepted nothing. A bound that allows 6 harmful edits in every 10 accepted is a weak safety promise.
   - This study tested a calibrated acceptance rule, not learning from failure. The operator order came from per-class
     oracle gains, CORA's probes found no fitting program, and acceptance was a statistical certificate computed on
     the calibration organs.

## 3. Direction

1. **Report the negative as it fell.** Any paper, poster or abstract statement about the calibrated rule uses this
   result. On 100 fresh held melanoma ROIs from a source no CORA study had used, the calibrated rule accepted 605
   edits, 430 of them harmful, and lowered mean per-image F1 by 0.0020 [0.0014, 0.0027] against the strong baseline.
   Its harm bound was exceeded: 430 of 605 accepted edits were harmful (0.711), against a bound of 0.60, and even the lower end of the 95% interval, 0.662, is above it. The rule is not described as safe or as controlling harm, and the result is
   stated for nuclei in melanoma ROIs from one source.
2. **Tie any future bound to the target's break-even, and fix it before looking.** A next rule would require the
   harmful-rate bound to sit below 1 - F1 / 2 at the target's baseline accuracy. That accuracy would be estimated from
   a small labelled pilot set from the target source, fixed in advance and kept apart from the test images. If no
   operator passes, the result is abstention, reported as such. The bound is not relaxed until something passes.
3. **Abstain by default on a new source.** Until a rule has passed a pre-registered test on fresh data, CORA's edits
   are not applied to a new source's segmentations. STRICT's behaviour, abstention, is the default.
4. **Repair the controls, as the review proposed.** Test all 3 operators with a Holm adjustment instead of stopping
   at the first failure, or derange within the specified list. Then the controls are not decided before the held
   images are seen, and the co-primary is not a fixed share of the primary.
5. **Keep the reserve for one clean replication.** The 105 reserve ROIs stay unopened. No rule is tuned on these 100
   held ROIs and then tested on them again. A rule informed by this result is tested once, under a new
   pre-registration, on the reserve or on another fresh source.
6. **A test of learning from failure needs a different design:** one where failure evidence, not oracle gains,
   chooses the edit, and where the controls can reach the same operators.

## Files

- `results/RESULTS.json`, `results/SUMMARY.md`: the evaluator's aggregates (written at 07:57:55Z).
- `data/work/puma/DECISIONS_FROZEN.json`: the hashes of all 18 arms' decisions.
- `data/work/puma/decisions/*.json`: each arm's decision record (operators, statuses, programs, bounds, edit logs). The
  label maps (`*.npz`) are not in git.
- `data/work/puma/HELD_MANIFEST.json`: the salt, the 100 held ROIs and the names of the 105 reserve ROIs.
- `data/work/puma/seg/MANIFEST.json`: the thresholds, and each held ROI's object counts and label hashes.
- `data/work/held_chain.run.status`, `data/work/held_steps/`, `data/work/cal/logs/held_*.log`: the chain's step log,
  step markers, CPU record and per-arm logs.
- These 58 files are committed in `646a622a`. This record is committed after them.
