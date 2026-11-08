# Post-score audit: calibrated acceptance study, held run of 8 Nov 2026

Independent audit written on 8 Nov 2026, after the result record. It covers the result record `RESULT.md` (commit
`57fc53a5`, 08:16Z) and the held outputs (commit `646a622a`). It checks them against the protocol (`PROTOCOL.md`, frozen
at `9f283c2c`) and the pre-run review (`reviews/PRE_RUN_REVIEW.md`, commit `dad82ffd`) with its six conditions. The
predecessor study is the bioimage grammar study of 2 Nov 2026 (`experiments/universality_bio_grammar_20261103`).

- **What this audit did.** It recomputed the custody facts and every reported number from the files, with code written
  for this audit and kept in a scratch folder outside the repository.
- **What it did not do.**
  - It reran no step of the held chain and wrote nothing in this folder except this file.
  - It did not touch CORA Step B, VDCG or other projects' job folders. It read no `*_LOCAL.json` file and nothing under a folder named
    private.
  - It decoded the expert outlines of the 100 held regions of interest (ROIs) only. No reserve ROI was decoded; the
    two PUMA archives were hashed as whole files.
- **CPU.** About 341 CPU seconds (CPU-s) in all, at the lowest priority, on one thread.
- **One boundary was crossed** by this audit (section 8).

## Names used here

- **The images.** PUMA is the melanoma dataset of Zenodo record 13859989 (CC BY 4.0).
  - Held ROIs: the 100 PUMA ROIs chosen after GO.
  - The reserve: the other 105 ROIs, never opened.
  - The format ROI: the one ROI opened before GO, for a format check.
- **GO and the salt.** `GO_CAL` is the go-ahead file, and GO means its commit. The salt is the sha256 of its bytes. It
  fixes the held ROIs and the control seeds.
- **The arms.**
  - STRONG_NATIVE: the baseline every arm starts from. It is StarDist at thresholds tuned on NuInsSeg, minus a deletion
    rule chosen there.
  - CALIBRATED: the calibrated rule applied to `add_lowthresh`, `split_dt` and `split_int`, the 3 operators ranked
    first by per-class oracle gains (the F1 that an oracle fix of each error class would recover on 6 calibration
    organs). `add_lowthresh` adds low-threshold StarDist detections where the baseline has no object.
  - CAL_BLIND: the calibrated rule with 3 operators drawn at random, for 5 seeds.
  - CAL_SHUFFLED: the calibrated rule with operators from failure records whose class labels are deranged, for 5
    seeds.
  - STRICT and TOLERANT: the predecessor study's verify-or-abstain rule and majority-vote rule.
  - MATCHED_SEARCH: an unverified static search over all 11 operators, given CALIBRATED's CPU.
  - MATCHED_SEARCH_U5: the predecessor study's own frozen search program.
  - NATIVE and TUNED: StarDist at its own thresholds and at the tuned thresholds.
- **The contrasts and hypotheses.**
  - P1: CALIBRATED minus STRONG_NATIVE, in mean per-image object F1 over the 100 held ROIs.
  - P2: CALIBRATED minus the image-by-image mean of the 5 CAL_BLIND seeds.
  - A contrast is supported if its Holm-adjusted one-sided p is at most 0.025 and its 95% interval lies above 0.
  - H1 (primary): P1 is supported AND CALIBRATED's held harmful-edit rate is at most 0.60. H2 (co-primary): P2 is
    supported.
- **Edits.**
  - A harmful edit is an accepted edit that, judged alone against the reference, loses a matched object or adds an
    unmatched one.
  - The harmful-edit rate is harmful edits / accepted edits.
- **Operator statuses under the calibrated rule.**
  - ACCEPTED: both bounds held.
  - NO_OUT_OF_FOLD_EDIT: no fold made an edit on its left-out organ.
  - GAIN_NOT_CERTIFIED: the lower bound of the mean gain was not above 0.
  - NOT_TESTED: short for NOT_TESTED_FIXED_SEQUENCE, not reached because an earlier operator was not accepted.

## Verdict: PASS

- **The decision stands.** CALIBRATED's label is HARMFUL. H1 is not supported. H2 is not supported.
- **Custody is intact.**
  - GO was committed once and alone, after the review.
  - Its hash drove the held selection, which recomputes exactly.
  - No reserve ROI was opened.
  - One held chain ran, with no restart.
  - Every frozen hash still matches, including the four calibration listing hashes.
- **Every reported number reproduces exactly.** Independent code rescored all 18 arms from the frozen label maps and
  the expert outlines. 236 of 236 compared quantities equal `results/RESULTS.json`, with a largest difference of 0.
  The edits of all 7 editing records were re-judged, and every count and interval matches.
- **RESULT.md meets the six review conditions in substance.** It frames the study as a test of a calibrated acceptance
  rule, not of learning from failure. It discloses the 0.20 to 0.60 bound change as a weak safety promise.
- **Six text corrections are required** before any paper, poster or abstract quotes it (section 4). None changes a
  number, the label or a hypothesis decision.

## 1. Custody

| check | result |
|---|---|
| GO_CAL committed once and alone, after the review | yes |
| salt = sha256 of GO_CAL, and it drove the held selection | yes |
| the 100 held ROIs, recomputed from the salt | equal, 100 of 100; the 105 reserve ROIs equal, 105 of 105 |
| no reserve ROI opened | no trace of any, in files, folders or logs |
| a single held chain, START and EXIT 0, no restart | yes |
| frozen hashes, including the four calibration listing hashes | 63 of 63 freeze checks and 4 of 4 listing hashes match |

### 1.1 GO and the salt

- **The GO commit.** `GO_CAL` was committed in `3d7fc39a` at 07:36:59Z, and that commit adds only `GO_CAL`.
- **After the review.** The review commit `dad82ffd` (07:35:40Z) is an ancestor of the GO commit, 79 s earlier. The 2
  commits between them (`7f4c0f9d`, `849c4b50`) belong to another study and touch no file here.
- **Committed once, never edited.**
  - `git log --all -- GO_CAL` lists only `3d7fc39a`.
  - The file on disk equals the committed blob (`a8bd1535`): 394 bytes, 8 lines, ending in a newline, read-only.
  - The file was written at 07:36:58Z.
- **The salt.** It is `0062d9bc5af711f341ee2329411742eb053a3c44f17cbbae1ddeb1644f447395`. It equals the salt in
  `data/work/puma/HELD_MANIFEST.json` and in the selection step's log.
- **Not verifiable from the files:**
  - that the nonce in `GO_CAL` came from a cryptographic random source;
  - that no one computed the salt before the chain did.
- **What the files do show.**
  - `GO_CAL` was written at 07:36:58Z and committed at 07:36:59Z. The chain started at 07:36:59Z and chose the held
    set at 07:37:01Z.
  - No other version of `GO_CAL` exists in git.
  - The one unusual feature of the draw (section 2.3) is of the kind that a salt chosen to favour H2 would avoid.

### 1.2 The held selection

The selection was recomputed with code written for this audit, from the image archive's member names only.

- **The ROIs.** There are 206 ROIs: 103 primary and 103 metastatic.
- **The format ROI** is `training_set_primary_roi_028`, the smallest sha256 of `"calacc_format:<roi>"`.
- **The held set.** Per stratum, the ROIs were sorted by sha256 of `"<salt>:<roi>"` and the first 50 kept.
  - Held: 100 ROIs (50 primary, 50 metastatic), equal to the manifest's on 100 of 100.
  - Reserve: 105 ROIs (52 primary, 53 metastatic), equal on 105 of 105.
  - The held set, the reserve and the format ROI partition the 206.
- **The outlines.** All 100 held outline files are present in the outline archive.

### 1.3 No reserve ROI was opened

- **Per-ROI files.** They exist for exactly the 100 held ROIs, in each of 6 folders: the inputs, the intensity images,
  and the NATIVE, TUNED, LOW and STRONG_NATIVE segmentations. They are 100 of 100 in each, with 0 reserve ROIs. LOW is
  StarDist at half the tuned probability threshold.
- **Decision label maps.** Each of the 18 decision label-map files has 100 of 100 held keys and 0 reserve keys.
- **The format folder.** `data/work/format_check/` holds only the format ROI.
- **Reserve names.** They appear in no text file of this folder (230 scanned) or of the 8 `cal_calacc_*` detached-job
  folders, except in the reserve list of `HELD_MANIFEST.json`.
- **The dry run** used 4 NuInsSeg calibration images posing as held ROIs.

### 1.4 One held chain, no restart

- **The detached job.** `outputs/detached/cal_calacc_held/run.status` has one START (07:36:59Z) and one EXIT 0
  (07:57:55Z).
  - Its command is `python3 -I -B experiments/calibrated_acceptance_20261108/scripts/run_after_go.py`, run from the
    project root.
  - Its stdout and stderr are empty.
- **The chain's own log.** `data/work/held_chain.run.status` has one START (pid 3477947) and 10 step lines, one per
  step, then EXIT 0 with a total of 1,938.3 CPU-s.
- **Step markers.** The 10 of 10 markers carry times in step order, from 07:37:00Z to 07:57:55Z, equal to the log.
- **No restart.** So condition 2 of the review never applied.
- **Nothing changed after the evaluation.** No file under `data/work/puma/` or `results/` changed after 07:57:55Z. The
  only file of this folder changed after that is `RESULT.md`.

### 1.5 Frozen hashes

- **`FREEZE.json`: 63 of 63 checks match.**
  - The 58 entries, including the 2 PUMA archives. The result record did not re-read the archives after the run; this
    audit did.
  - The second copy of each of the 4 calibration records.
  - The listing hash of the predecessor study's 189 probe records.
- **`FREEZE.json` itself.** Its sha256 is `7e5c55efc625dc684c4a2de9469b605066781fc47cf49859c114dad31c3ef56f`, the
  value recorded in `DECISIONS_FROZEN.json` and named in `GO_CAL`.
- **The predecessor study's `CODE_FREEZE.json`:** 24 of 24 entries match.
- **The four calibration listing hashes** (review, gap 1): 4 of 4 equal, over 236 of 236 files each. The newest file
  dates from 2 Nov 2026 09:34:38Z.
- **`DECISIONS_FROZEN.json`** (sha256 `9454a9f411452e786d9747a64f9ba79ab2c32ccaed302cde905036b435ea3659`):
  - 36 of 36 decision files match;
  - its hashes of `HELD_MANIFEST.json` and `FREEZE.json` match;
  - it was written at 07:52:03Z, before the evaluation step opened any reference.
- **Stop rule 3, redone.** The calibration-side fields of STRICT, TOLERANT and CALIBRATED in the held records equal the
  frozen ones, 3 of 3. These fields are the statuses, programs, bounds and fold programs. No mismatch file exists.
- **Frozen programs.**
  - MATCHED_SEARCH's applied program equals the frozen calibration record.
  - MATCHED_SEARCH_U5's equals the predecessor study's `POLICY_FREEZE.json` (sha256 `a67326dc...`).
- **Commits.**
  - The 7 study commits from `9f283c2c` to `57fc53a5` touch only this folder and carry no trailers.
  - `git status` of this folder is clean, so the 58 files of `646a622a` equal the files on disk.
- **Bytecode.** No bytecode exists in this folder, and the predecessor study's `scripts/__pycache__/` is unchanged
  since 06:48Z.

## 2. Every reported number, recomputed from the held output files

### 2.1 Method

- **Outlines.** The GeoJSON polygons of the 100 held ROIs were decoded and rasterized with code written for this
  audit, under the study's stated rule:
  - each outer ring is filled;
  - the parts of a MultiPolygon form one object;
  - larger objects are painted first, so a smaller one keeps its pixels.
  - The result: 48,013 polygons, 48,013 rasterized objects, none fully covered by others.
- **Matching.** Objects match one to one at an intersection over union (IoU) above 0.5.
  - F1 = 2 x matched / (reference + predicted).
  - AP (average precision) is the mean over IoU 0.50 to 0.95 of matched / (reference + predicted - matched).
- **Bootstraps.**
  - 10,000 resamples over ROIs, seed 0, with percentile intervals.
  - One-sided p = (1 + resampled means at or below 0) / 10,001.
  - The pre-registered sensitivity analysis resamples within primary and metastatic.
  - Holm adjusts P1 and P2 together.
- **Edits of the 6 records that only add objects** (CALIBRATED, TOLERANT, MATCHED_SEARCH, and the 3 blind seeds that
  edited).
  - On 100 of 100 ROIs, every STRONG_NATIVE object is unchanged in the record's labels.
  - On 100 of 100 ROIs, the new objects equal the logged edits in number.
  - A new object is beneficial if it matches a reference nucleus and harmful otherwise. Each addition lies on
    background, so it cannot change another object's match.
- **Edits of MATCHED_SEARCH_U5** (additions, then deletions, then erosions).
  - They were replayed step by step with code written for this audit.
  - Every reconstructed intermediate state equals its logged hash, on 100 of 100 ROIs at each of the 3 steps.
  - The end state equals the frozen labels on 100 of 100 ROIs.
- **What was compared, 236 of 236 quantities, all exact:**
  - mean and pooled F1 and AP of 18 arms;
  - the mean, interval, p and gained/lost/equal counts of 25 F1 contrasts, plus 9 AP contrasts and 9 stratified
    intervals;
  - the edit counts and ratio intervals of the 6 add-only records;
  - the reference count, both Holm p values and the label.
  - MATCHED_SEARCH_U5's 4 edit counts and 3 ratio intervals also match.

### 2.2 Primary and co-primary (pre-registered, confirmatory)

| quantity | RESULT.md | recomputed |
|---|---|---|
| P1, over 100 ROIs | -0.0020 [-0.0027, -0.0014] | -0.002038 [-0.002655, -0.001433] |
| ROIs gained / lost / equal under P1 | 31 / 69 / 0 of 100 | 31 / 69 / 0 of 100 |
| P1 one-sided p; resampled means above 0 | 1.0; none | 1.0; 0 of 10,000 |
| P1 stratified interval | [-0.0026, -0.0014] | [-0.002627, -0.001448] |
| per stratum (exploratory) | -0.0016 primary, -0.0025 metastatic (50 ROIs each) | -0.001551, -0.002525 |
| CALIBRATED edits: harmful / accepted | 430 / 605 = 0.711 | 430 / 605 = 0.7107 |
| its 95% interval | [0.662, 0.757] | [0.66197, 0.75712] |
| beneficial / neutral | 175 / 0 of 605 | 175 / 0 of 605; pooled matched objects rose from 44,159 to 44,334, by exactly 175 |
| bound 0.60 held at the point rate; bound confirmed at the upper end | no; no | no (0.711 above 0.60); no (0.757 above 0.60); the lower end, 0.662, is also above 0.60 |
| P2, over 100 ROIs | -0.0008 [-0.0011, -0.0006] | -0.000815 [-0.001062, -0.000573]; P2 / P1 = 0.4000 |
| Holm-adjusted p of P1 and P2 | 1.0 and 1.0 | 1.0 and 1.0 |
| label | HARMFUL | HARMFUL: 605 accepted edits (not 0), and P1's upper end, -0.00143, is below 0 |
| H1; H2; FAILURE_EVIDENCE_MATTERS (true only if P2 is supported) | not supported; not supported; false | the same |
| reference nuclei | 48,013 | 48,013 |

### 2.3 The blind seeds (H2's control)

Recomputed from the salt with the frozen rule: seed = the integer of the first 8 hexadecimal digits of
sha256(`"<salt>:blind:<r>"`), then 3 of the 11 operators drawn without replacement. All 5 of 5 seeds and draws equal
the records.

| r | seed | draws, in order | statuses | `add_lowthresh` | held edits | label maps |
|---|---|---|---|---|---|---|
| 1 | 1037436653 | add_lowthresh, close, fill_holes | ACCEPTED, NO_OUT_OF_FOLD_EDIT, NOT_TESTED | first | 605 | equal to CALIBRATED on 100 of 100 ROIs |
| 2 | 4131755104 | fill_holes, dilate, delete | NO_OUT_OF_FOLD_EDIT, NOT_TESTED, NOT_TESTED | not drawn | 0 | equal to STRONG_NATIVE on 100 of 100 |
| 3 | 1278462664 | add_lowthresh, close, dilate | ACCEPTED, NO_OUT_OF_FOLD_EDIT, NOT_TESTED | first | 605 | equal to CALIBRATED on 100 of 100 |
| 4 | 3096175386 | merge_pairs, erode, add_lowthresh | GAIN_NOT_CERTIFIED, NOT_TESTED, NOT_TESTED | third, never reached | 0 | equal to STRONG_NATIVE on 100 of 100 |
| 5 | 772396818 | add_lowthresh, clear_border, fill_holes | ACCEPTED, GAIN_NOT_CERTIFIED, NOT_TESTED | first | 605 | equal to CALIBRATED on 100 of 100 |

- **Why P2 = 2/5 x P1.** 3 of the 5 seeds copy CALIBRATED and 2 of the 5 equal STRONG_NATIVE. So P2 = (2 / 5) x P1,
  exactly; the recomputed ratio is 0.4000.
- **How often `add_lowthresh` was drawn.** It was first in 3 of 5 seeds and drawn at some position in 4 of 5.
- **Exploratory: how unusual the draw is.**
  - Under uniform draws, 3 or more of 5 seeds put `add_lowthresh` first with probability 1051 / 161051 = 0.0065.
  - The draw moved P2 toward 0. A salt chosen to favour H2 would avoid such a draw.
  - It cannot have changed CALIBRATED's label or H1 (correction 1).

### 2.4 CAL_SHUFFLED

- **The 5 seeds,** recomputed from the salt, equal the records. So do the 5 derangements and the 5 specified operator
  lists, rebuilt from the oracle gains.
- **Each seed's first operator** fails alone under the final rule:
  - `delete` for seeds 1 and 3, and `merge_pairs` for seed 4: GAIN_NOT_CERTIFIED;
  - `close` for seed 2, and `split_dt` for seed 5: NO_OUT_OF_FOLD_EDIT.
  - All 5 label maps equal STRONG_NATIVE on 100 of 100 ROIs.
- **"Abstains for every salt by construction," checked.**
  - A derangement moves the largest oracle gain away from ADD. So the first operator is always one of `split_dt`,
    `merge_pairs`, `fill_holes`, `close`, `open` or `delete`.
  - In `development/LAMBDA_SCAN_FINAL.json` (in-fold limit 0.40), each of these 6 fails alone. Only `add_lowthresh`
    and `dilate` pass alone, 2 of 11 operators.
- **Its contrast.** CALIBRATED minus CAL_SHUFFLED equals P1, up to a rounding difference of 3 x 10^-18.

### 2.5 The other arms (descriptive)

Each change is the mean per-image F1 difference against STRONG_NATIVE over the 100 held ROIs. All match `RESULT.md`
section 1.5.

| arm | edits: beneficial / harmful / neutral | harmful-edit rate [95%] | mean F1 | change [95%] | gained / lost / equal |
|---|---|---|---|---|---|
| STRONG_NATIVE | none | | 0.8892 | | |
| STRICT | 0 | undefined | 0.8892 | 0 | 0 / 0 / 100 |
| TOLERANT | 318: 39 / 279 / 0 | 0.877 [0.840, 0.912] | 0.8869 | -0.0023 [-0.0029, -0.0018] | 5 / 83 / 12 |
| CAL_BLIND, mean of 5 seeds | 605 in 3 of 5 seeds, 0 in 2 | 0.711 in each editing seed | 0.8880 | -0.0012 [-0.0016, -0.0009] | 31 / 69 / 0 |
| CAL_SHUFFLED, mean of 5 seeds | 0 in 5 of 5 seeds | undefined | 0.8892 | 0 | 0 / 0 / 100 |
| MATCHED_SEARCH | 3,271: 735 / 2,536 / 0 | 0.775 [0.750, 0.799] | 0.8749 | -0.0143 [-0.0162, -0.0125] | 6 / 94 / 0 |
| MATCHED_SEARCH_U5 | 17,694: 1,279 / 3,018 / 13,397 | 0.171 [0.154, 0.188] | 0.8698 | -0.0194 [-0.0216, -0.0172] | 1 / 99 / 0 |
| NATIVE | | | 0.8610 | -0.0282 (difference of means) | |
| TUNED | | | 0.8892 | -0.00001 (difference of means) | |

- **MATCHED_SEARCH_U5 by operator.**
  - Additions: 499 beneficial and 1,432 harmful.
  - Deletions: 763 beneficial and 1,491 harmful.
  - Erosions: 17 beneficial, 95 harmful and 13,397 neutral.
  - Its harm share among decisive edits is 3,018 of 4,297 (0.702 [0.685, 0.720]).
- **CALIBRATED's other contrasts** match `RESULT.md`:
  - minus TOLERANT: +0.0003 [-0.0003, +0.0009], with 50 / 46 / 4 ROIs gained, lost and equal;
  - minus MATCHED_SEARCH: +0.0123 [+0.0107, +0.0139], 96 of 100 gained;
  - minus MATCHED_SEARCH_U5: +0.0173 [+0.0153, +0.0195], 98 of 100 gained;
  - minus NATIVE: +0.0262 [+0.0211, +0.0314], 85 of 100 gained;
  - minus TUNED: -0.0020 [-0.0026, -0.0014], 33 / 66 / 1.
- **AP of P1:** -0.0023 [-0.0029, -0.0017], with 19 of 100 ROIs gaining. Pooled F1 is 0.8912 against 0.8931.

### 2.6 Other numbers in RESULT.md, checked

- **The CPU table.**
  - 10 of 10 step times and CPU values equal `data/work/held_steps/CPU.json` and the step markers. The total is
    1,938.3 CPU-s, 4.5% of the 43,200 CPU-s cap.
  - The per-arm CPU equals the decision records: CALIBRATED 92.2, STRICT 59.9 and TOLERANT 95.9 CPU-s; CAL_BLIND
    15.8 to 81.1 and CAL_SHUFFLED 14.2 to 28.8 CPU-s per seed; MATCHED_SEARCH 77.6 and MATCHED_SEARCH_U5 285.3 CPU-s
    to apply.
- **Object counts on the held ROIs.**
  - 50,894 TUNED objects, 50,872 STRONG_NATIVE objects and 56,915 LOW objects.
  - 6,043 `add_lowthresh` candidates on the held ROIs and 2,097 on the 236 calibration images. Both were recomputed from
    the candidate rule: at least 5 free pixels, and at least 90% of the low-threshold object free.
  - So CALIBRATED accepted 605 of 6,043 candidates (10.0%) on the held ROIs and 314 of 2,097 (15.0%) on the
    calibration images.
- **The format ROI.** 292 polygons and 292 rasterized objects; 252 NATIVE, 349 TUNED and 412 LOW objects.
  - Its format-check record was written at 06:38:20Z and its segmentations between 06:39:12Z and 06:39:15Z.
- **Job times.**
  - `cal_calacc_chain`: START only.
  - `cal_calacc_chain2`: 06:48:19Z to 06:56:51Z, EXIT 0.
  - `cal_calacc_chain3`: 07:03:30Z to 07:10:20Z, EXIT 0.
  - `cal_calacc_dryrun2`: EXIT 1 at 07:06:48Z. `MATCHED_SEARCH.json` was written at 07:06:54Z.
  - `cal_calacc_dryrun3`: 07:07:12Z to 07:09:56Z, EXIT 0.
  - The dry-run copy differs from `tests/dryrun_held.py` only in its docstring: 2 lines against 1.
- **Development records (section 1.7 of RESULT.md).**
  - CALIBRATED's certificate: 147 of 337 out-of-organ edits harmful (0.436), upper bound 0.530; mean change +0.0168,
    lower bound +0.0044.
  - Its final program made 314 edits in-sample: 152 beneficial, 121 harmful, 41 neutral.
  - TOLERANT: its top program in 9 of 12 folds; 20 edits.
  - The failing first operators: `merge_pairs` -0.0019, lower bound -0.0038, harmful rate 0.571; `clear_border`
    -0.0002, lower bound -0.0005, harmful rate 1.0.

## 3. RESULT.md against the review's six conditions and the frozen rule

| item | met | evidence |
|---|---|---|
| condition 1, the salt | yes, as far as files show | GO alone in `3d7fc39a`, never edited; the salt is recomputed; RESULT.md section 1.1, and the GO display it discloses in section 1.11 |
| condition 2, restarts | yes | no restart; section 1.11 says so |
| condition 3, the four listing hashes | yes | section 1.10; recomputed here, 4 of 4 |
| condition 4, CAL_SHUFFLED | yes | the exact sentence is in section 1.4 |
| condition 5, H2 | yes, in section 1.3 | the summary sentence in the Answer leaves out "under stop-at-first-failure testing" (correction 3) |
| condition 6, disclosures and labels | yes, with one gap | the rate, its interval, the bound in words and "bound confirmed: no" are present; so are the format ROI counts and the dry-run facts. The calibration certificate is quoted without "development, optimistic" in lessons 1 and 2 (correction 4) |
| the decision under the frozen rule | yes | the label order of protocol section 8 is applied in order: HARMFUL; H1 and H2 not supported |
| framed as a calibrated acceptance test, not learning from failure | yes | the Answer and lesson 6 |
| 0.20 to 0.60 disclosed as a weak safety promise | yes | the Answer and lesson 6 |
| no overclaim | yes, except two sentences | none of the review's check 7 risks appears. One sentence is broader than the evidence (correction 1), and one understates the failure of the bound (correction 2) |

## 4. Required corrections (exact text)

Each old text is quoted as it reads in `RESULT.md`, with its line breaks joined by one space.

1. **Section 1.3, "Exploratory: an unusual draw," last sentence.**
   - Result: "the decision" covers H2. But a different draw can change P2, and so H2.
   - Lesson: name which decision a fact cannot change.
   - Old: ``It cannot have changed the decision, because P1 itself is negative.``
   - New: ``It cannot have changed CALIBRATED's label or H1: both depend only on P1 and the harmful-edit rate, and
     P1's Holm-adjusted p is 1.0 whatever P2's p is. For H2, any draw in which each seed either copies CALIBRATED or
     abstains gives P2 = (abstaining seeds / 5) x P1, which is at most 0 here. A draw in which a seed accepted another
     operator (for example `dilate`, the only other operator that passes alone on the calibration organs) would have
     edited differently, with an unknown held effect.``
2. **Section 3, direction 1, the sentence on the bound.**
   - Result: "not confirmed" can be read as "inconclusive". In fact the bound was exceeded at the point rate and at the
     lower end of the interval.
   - Lesson: state a failed bound as exceeded, with its numbers.
   - Old: ``Its harm bound was not confirmed.``
   - New: ``Its harm bound was exceeded: 430 of 605 accepted edits were harmful (0.711), against a bound of 0.60, and
     even the lower end of the 95% interval, 0.662, is above it.``
3. **The Answer, P2 bullet, last sentence** (condition 5).
   - Result: the summary drops the qualifier that condition 5 requires.
   - Lesson: the summary is what papers copy.
   - Old: ``The failure-evidence order did not beat random orders.``
   - New: ``The failure-evidence order (operators ranked by per-class oracle gains) did not beat random orders under
     stop-at-first-failure testing.``
4. **Section 2, lessons 1 and 2** (the labels of review check 7, and which program is meant).
   - Result: the certificate is quoted without its label. "The same program" is also inexact: the out-of-organ rate
     comes from the 12 fold programs (5 distinct programs; the final program is the fold program in 6 of 12 folds).
   - Lesson: development numbers always carry their label.
   - Old: ``Result: on the calibration organs, the out-of-organ harmful rate of `add_lowthresh` was 147 of 337 (0.436),
     with an upper bound of 0.530. On the held PUMA ROIs, the same program's rate was 430 of 605 (0.711) [0.662,
     0.757].``
   - New: ``Result: on the calibration organs (development, optimistic), the out-of-organ harmful rate of
     `add_lowthresh`'s fold programs was 147 of 337 (0.436), with an upper bound of 0.530. On the held PUMA ROIs, the
     final program's rate was 430 of 605 (0.711) [0.662, 0.757].``
   - Old: ``On the calibration organs pooled F1 was 0.503, so the break-even share was about 0.75, and a rate of 0.44
     helped.``
   - New: ``On the calibration organs (development) pooled F1 was 0.503, so the break-even share was about 0.75, and
     an out-of-organ rate of 0.44 (development, optimistic) went with a gain.``
5. **Section 1.11, the autosave bullet.**
   - Result: "a few files" gives no count.
   - Lesson: every number has its denominator.
   - Old: ``including a few files under `data/`. No image, mask or archive was among them.``
   - New: ``including 24 files under `data/`: the 3 files of the StarDist model copy (among them the 5,774,704-byte
     `weights_best.h5`); 4 text files of the download folder (the Zenodo record, the download script and the 2
     observed checksum lists); 14 calibration records from version 1 of the rule (4 final, 10 development), since
     updated in `8a8dbd61`; the calibration chain's status file; and the 2 format-check records. No image, mask or
     archive was among them.``
6. **Section 1.9, the passing dry run.**
   - Result: the passing dry run did not follow the direction written just above it, and the record does not say so.
   - Lesson: a process note covers every run it describes.
   - Old: ``Its stand-in freeze lists the 4 frozen record hashes, which equal those in `FREEZE.json`.``
   - New: ``Its stand-in freeze lists the 4 frozen record hashes, which equal those in `FREEZE.json`. It started while
     the final calibration chain was still running its development arms (that chain exited at 07:10:20Z), so it did
     not follow the direction above. The 4 final records it read were last written at 07:06:54Z and equal the frozen
     ones, so the overlap changed nothing.``

## 5. Recommended, not required

- **Section 1.5, tolerant rule.** Replace ``but more of them were harmful (279 of 318)`` with ``but a larger share of
  them were harmful (279 of 318, 0.877, against 430 of 605, 0.711)``. In count, TOLERANT made fewer harmful edits
  (279 against 430).
- **Section 2, lesson 4.** Add ``(Descriptive.)`` after its heading, because it compares descriptive arms.
- **Section 3, direction 6.** Replace ``one where failure evidence, not oracle gains, chooses the edit`` with ``one
  where CORA's own failure analysis (its probes), not per-class oracle gains, chooses the edit``. The protocol counts
  the oracle gains as part of the failure evidence.
- **The Answer, honest framing.** After ``relaxed from 0.20 to 0.60``, add ``(and the in-fold limit from 0.20 to
  0.40)``. Both moved in version 2.
- **`PROGRESS.md`** still says the study is frozen and waiting for GO. Update it with the result and this audit.

## 6. Sentences the papers may use (exact)

These sentences use no internal label, and every number has its denominator. A paper that uses one keeps its label:
confirmatory, descriptive, exploratory, or development, optimistic.

### 6.1 Short form (abstract, poster)

1. "A pre-registered calibrated acceptance rule for CORA's nucleus-segmentation edits failed its single test on fresh
   data: on 100 held-out melanoma image regions from a public dataset that no CORA study had used (PUMA), it accepted
   605 edits, 430 of them harmful, and lowered mean per-image F1 by 0.0020 (95% interval 0.0014 to 0.0027) against a
   strong baseline."
2. "Lesson: its limit on the share of harmful edits, 0.60, set on organs of one dataset, did not hold on the new
   source (430 of 605, 0.711); next, any such limit is tied to the target's baseline accuracy and fixed before
   looking, and the default on a new source is to abstain."

### 6.2 Paper paragraph

1. "This experiment tested a calibrated acceptance rule, not learning from failure: the order of CORA's candidate
   operators came from per-class oracle gains (the F1 an oracle fix of each error class would recover) on 6 of 12
   NuInsSeg calibration organs, CORA's failure probes found no fitting program for any probed class, and acceptance
   was a statistical certificate computed on the 12 calibration organs (236 images)."
2. "An operator was accepted only if, across leave-one-organ-out folds on those 12 organs, the one-sided 95% lower
   bound of the mean per-image F1 change was above 0 and the one-sided 95% upper bound of the harmful-edit rate was at
   most 0.60; operators were tested in order, stopping at the first one not accepted."
3. "The bound of 0.60 is a weak safety promise: it allows up to 6 harmful edits in every 10 accepted, and it was
   relaxed from 0.20 during development, on the same calibration organs, because 0.20 accepted nothing."
4. "The rule was frozen and pre-registered, then tested once on 100 held-out PUMA melanoma image regions (50 primary,
   50 metastatic; 48,013 expert-corrected nucleus outlines) chosen after the go-ahead by a hash of the go-ahead file;
   the other 105 regions remain unopened for one replication."
5. "Every rule started from a strong baseline, StarDist with detection thresholds tuned on NuInsSeg plus a deletion
   rule chosen there, whose mean per-image F1 over the 100 regions was 0.889."
6. (Confirmatory) "The rule accepted one operator, which adds low-threshold StarDist detections, and made 605 edits on
   the 100 regions: 430 of the 605 were harmful (0.711, 95% interval 0.662 to 0.757), mean per-image F1 fell by 0.0020
   (95% interval 0.0014 to 0.0027), and 69 of the 100 regions lost F1 while 31 gained."
7. (Confirmatory) "Under the pre-registered decision rule the label is 'harmful', because the whole 95% interval of
   the F1 change lies below 0; the gain hypothesis is not supported, and the harm bound was exceeded, with even the
   lower end of the observed rate's interval, 0.662, above 0.60."
8. (Confirmatory) "The oracle-gain order did not beat random operator orders under stop-at-first-failure testing: the
   mean per-image F1 difference was -0.0008 (95% interval -0.0011 to -0.0006) over the 100 regions."
9. "Because 3 of the 5 random orders also drew the adding operator first and reproduced the calibrated rule's edits
   exactly, while the other 2 made no edit, this contrast is exactly 2/5 of the primary one and is not separate
   evidence about CORA's failure analysis."
10. (Descriptive) "The strict verify-or-abstain rule made no edit on the 100 regions and lost nothing, while every rule
    that edited lost F1 against the baseline: the calibrated rule (605 edits) by 0.0020, a majority-vote rule (318
    edits) by 0.0023, and two unverified searches (3,271 and 17,694 edits) by 0.0143 and 0.0194."
11. "Lesson: a harm bound calibrated across organs of one dataset did not hold on a new source; the adding operator's
    harmful-edit rate was 147 of 337 (0.436) on left-out calibration organs (development, optimistic) and 430 of 605
    (0.711) on the new source."
12. (Exploratory) "An added object raises F1 on average only if the share of false additions is below about 1 - F1/2,
    so a fixed bound of 0.60 left room for gain at the calibration organs' pooled F1 of 0.503 (break-even about 0.75)
    but not at the new source's baseline pooled F1 of 0.893 (break-even about 0.55)."
13. "Direction: tie any future harm bound to the target's break-even accuracy, estimated on a small labelled pilot set
    kept apart from the test images and fixed before looking; abstain by default on a new source; and test a revised
    rule once, under a new pre-registration, on the 105 unopened PUMA regions or on another fresh source."
14. "The result concerns nuclei in melanoma image regions from one source, PUMA, with StarDist as the baseline
    segmenter."

## 7. Do not write

| do not write | why | write instead |
|---|---|---|
| "CORA learned from failure on PUMA", "learning from failure did (or did not) improve segmentation", or "CORA's learn-from-failure edits" (the protocol's title) for this test | the study tested a calibrated acceptance rule; the probes found nothing | sentence 6.2.1 |
| "failure evidence chose the operator", "CORA's reasoning found the fix", "the probes chose the adding operator" | the order came from per-class oracle gains | "per-class oracle gains put the adding operator first" |
| "the rule controls harm", "safe", "harm-bounded", "certified safe", "guaranteed", "the bound held" | the bound was exceeded: 430 of 605 (0.711), interval 0.662 to 0.757 | sentences 6.2.6 and 6.2.7 |
| "a pre-specified bound of 0.60", with no mention of the change from 0.20 | it was set after looking, on the same organs | sentence 6.2.3 |
| "the calibrated rule raised F1 by 0.026 over StarDist" | that contrast (+0.0262 against NATIVE) is the tuned thresholds' work; against the strong baseline the rule lost 0.0020 | sentence 6.2.6 |
| "the calibrated rule beat the search baselines" as CORA's contribution (+0.0123, +0.0173) | descriptive; both searches lost more than the rule; protocol section 13 excludes it | sentence 6.2.10 |
| "the rule beat (or matched) the shuffled-failure control", as evidence | that contrast equals the primary by construction; the shuffled control abstains for every salt | nothing, or "the shuffled control could not edit under this design" |
| "failure evidence matters" or "does not matter", in general | only the order against random orders under stop-at-first-failure testing was tested, and 3 of 5 random orders copied the rule | sentences 6.2.8 and 6.2.9 |
| "the random control was unlucky", or any use of the unusual draw (3 of 5 seeds, chance about 0.0065) toward a different conclusion | exploratory; it changes neither the label nor H1 | nothing |
| "the calibrated and tolerant rules perform the same" | +0.0003 (interval -0.0003 to +0.0009) over 100 regions is no measured difference, not equivalence | "no measured difference over 100 regions" |
| "tumour-cell nuclei", "melanoma cells", "histology in general", "generalizes across sources" | PUMA outlines every nucleus, and this is one source | sentence 6.2.14 |
| anything about the 105 reserve regions beyond "unopened" | they were never opened | sentence 6.2.4 |
| +0.0168 (lower bound +0.0044), 147 of 337 (0.436) or the upper bound 0.530, without "development, optimistic" | chosen while looking at the same organs | sentence 6.2.11 |
| "abstention is always best" or "the strict rule is safe" | one source and 100 regions; abstaining only means making no edit | sentence 6.2.10 |
| "the calibrated rule abstained" | it accepted one operator and made 605 edits | sentence 6.2.6 |
| "p = 1.0 shows no effect" | the effect was measured, and it was negative; p is one-sided, for a gain | sentences 6.2.6 and 6.2.7 |
| P1, P2, H1, H2, STRONG_NATIVE, CALIBRATED, CAL_BLIND, CAL_SHUFFLED, MATCHED_SEARCH_U5, U5 (the predecessor study's code name), LOO_FAIL (the strict rule's leave-one-organ-out failure status) or `add_lowthresh`, undefined in a paper | internal labels | "the calibrated rule", "random operator orders", "the strong baseline", "the operator that adds low-threshold detections" |

## 8. A boundary crossed by this audit

- **Result.** At the start of this audit, one listing command printed the text of `GO_CAL` together with
  `.gitignore`. Protocol section 14 says GO files are hashed, not read.
- **Lesson.** It happened after the held set, the seeds, every decision and the evaluation were fixed, hashed and
  committed, so it cannot change any number. It still breaks the stated rule, as the result writer's display did.
- **Direction.** Later audits check `GO_CAL` only by its sha256 and by comparing its git blob with the file. They never
  print it.
