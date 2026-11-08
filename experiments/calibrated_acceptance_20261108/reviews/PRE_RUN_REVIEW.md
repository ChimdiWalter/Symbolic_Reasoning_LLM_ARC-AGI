# Pre-run review: calibrated acceptance study on fresh held PUMA images (8 Nov 2026)

Independent review written before GO, on 8 Nov 2026 between about 07:15Z and 07:45Z. It covers the frozen study in this folder
at freeze commit `9f283c2c4d000e3dc5627379f7d590cf60d0f219` and its two follow-up commits (`810044ed`, `8a8dbd61`).
U5 below means the bioimage grammar study of 2 Nov 2026 (`experiments/universality_bio_grammar_20261103`), whose code
and NuInsSeg records this study reuses read-only.

Names used below, as in PROTOCOL.md sections 4 and 5:
- **The held images** are PUMA regions of interest (ROIs).
- **The segmentations:**
  - NATIVE: StarDist at its own thresholds;
  - TUNED: StarDist at U5's NuInsSeg-tuned thresholds;
  - LOW: StarDist at half the tuned probability threshold;
  - STRONG_NATIVE: TUNED minus U5's deletion rule. It is the baseline every arm starts from.
- **The CORA arms** each receive 3 operators:
  - STRICT, TOLERANT and CALIBRATED: the three acceptance rules, on the 3 operators that failure evidence puts first;
  - CAL_BLIND: the calibrated rule with 3 operators drawn at random;
  - CAL_SHUFFLED: the calibrated rule with operators taken from failure records whose class labels are deranged.
- **MATCHED_SEARCH** is a search without verification, given CALIBRATED's CPU. MATCHED_SEARCH_U5 is U5's own
  frozen search program.

What this review did not do: it did not read or create any GO file (it only tested that `GO_CAL` does not exist), it
opened no PUMA image or reference, it computed no salt-derived selection, and it changed nothing outside `reviews/`.
Every Python check ran with `-I -B`, so no bytecode was written in this study's or U5's folders. The archive hashing,
the tests and the freeze check ran in a shared CPU slot; the lighter checks ran at the lowest priority.

## Verdict: PASS-WITH-NOTES

No blocker was found. The freeze holds, the held data are fresh, licensed CC BY 4.0 and unopened, calibration touches
only NuInsSeg calibration organs, and the primary analysis, the stop rules and the CPU cap are in place and match the
code. GO may be written once the six conditions in section 3 are accepted. They need no code change.

The notes that matter most for what may later be claimed:
- **The shuffled-failure arm cannot edit, whatever the salt.** CALIBRATED minus CAL_SHUFFLED therefore equals the
  primary contrast exactly. It is not separate evidence.
- **The co-primary mostly repeats the primary.** It tests whether the failure-evidence order beats a random order under
  stop-at-first-failure testing. It does not test whether CORA's probes chose a better operator.
- **The 0.60 harm bound is weak and was set after looking.** It allows up to 6 in 10 accepted edits to be harmful.

## 1. Evidence for each check

### Check 1. The freeze binds the code, configuration, protocol, data manifest and reused files

- **FREEZE.json.** Its sha256 is `7e5c55efc625dc684c4a2de9469b605066781fc47cf49859c114dad31c3ef56f` on disk. The bytes are
  identical in git at `9f283c2c`, `810044ed` and `8a8dbd61`.
- **Every hash recomputed on disk.** An independent script recomputed every hash. 62 of 62 file hashes match:
  - the 58 entries of FREEZE.json, with the 4 calibration records checked in both of their copies;
  - what the entries cover: 15 own files; 24 reused files; 2 archives; the Zenodo record; the format check; 3 model
    files; 4 calibration records; 8 development records.
  - The folder listing hash of U5's probe records also matches, over 189 of 189 files.
  - All 24 of 24 entries of U5's own `CODE_FREEZE.json` match.
- **The same files as git blobs at the freeze commit.** 47 of 47 tracked files match FREEZE.json:
  - the 15 own files;
  - the 15 reused code files inside this repository (10 U5 scripts, U5's `CODE_FREEZE.json` and `PROTOCOL.md`, the
    S-BSST265 study's `adapter.py` and `masks.py`, `cora_cross_domain_transfer/adapters/bbbc039.py`);
  - the Zenodo record, the format check and the 3 model files;
  - the 4 copies in `calibration/final/` and the 8 development records.
  - The 9 reused U5 data files live outside the repository, so they were checked on disk only.
- **One explained difference.** At the freeze commit, git's copies of `data/work/cal/final/*.json` (4 of 4) were still
  the version-1 records. They equal `development/v1_alpha020/FINAL_*.json`. `8a8dbd61` brought them in line.
  - The binding copies at the freeze commit are `calibration/final/*.json`, which match.
  - The on-disk files that the held chain reads match as well.
- **The follow-up commits change no frozen file.** `810044ed` changes only `PROGRESS.md`. `8a8dbd61` changes only 15
  files under `data/work/`.
- **Re-runs.**
  - `scripts/verify_freeze.py` reports no mismatch.
  - `tests/test_calacc.py` passes 13 of 13 tests in 3.7 s.
  - `git status` for this folder was clean before this review.
- **The reimplemented baseline matches.** On the 4 dry-run images, `caharness.strong_native_held` reproduces U5's
  starting segmentation exactly (4 of 4 label images identical).
- **Gap 1: the per-image calibration arrays are not hashed.**
  - Result: FREEZE.json does not hash the per-image arrays the rule reads for the 236 calibration images: starting
    labels, low-threshold labels, intensity images and references (4 x 236 files). They are bound only indirectly, by
    stop rule 3: the recomputed STRICT, TOLERANT and CALIBRATED records must equal the frozen ones.
  - Lesson: a freeze of records and code does not by itself freeze the arrays those records were computed from.
  - Direction: their listing hashes are recorded below. They use the same rule as `make_freeze.tree_sha`: the sha256 of
    the sorted lines `"<file> <sha256>"`. The newest of these files dates from 2 Nov 2026, before this study began.

| U5 folder (under `/path/to/bio_data/work/nuinsseg/`) | files | sha256 of listing |
|---|---|---|
| `seg/S` (starting segmentation) | 236 of 236 | `2c07111cb2d838bf8abab5e193adeb6528cdded645a58909f65f68c495fa58c4` |
| `seg/low` (low-threshold labels) | 236 of 236 | `13a1fbdb24984d2350e2492fdcfad58cb4849809811a03214108a1274e98ccae` |
| `int` (intensity images) | 236 of 236 | `7e9e53f37645beb9f69aefd6e3e9e164e9ce609a3be60f959c84e0f4d374cb63` |
| `ref_cal` (calibration references) | 236 of 236 | `f9e0134a07dee47fa790c03b5ab5c6255d819a1fc997014138c2b78db663bcd8` |

- **Gap 2: the freeze check skips 10 entries.**
  - Result: `verify_freeze.py` does not re-check the Zenodo record, the format check or the 8 development records,
    10 of the 58 entries.
  - Lesson: none of the 10 is an input to the held chain. The format ROI is recomputed from the archive's member names.
  - Direction: no change needed. All 10 were recomputed here and match.

### Check 2. The held data are fresh, licensed CC0 or CC BY, and unopened, with the salt taken from GO

- **Licence.** The saved Zenodo metadata, which is bound by its hash, gives `{"id": "cc-by-4.0"}` and open access.
  Figures are allowed with attribution.
- **Integrity.** The MD5 values observed now equal the published ones in that record:
  - `0310c5a303b986eb4ff2dba4ddbfb70e` for the 647,205,575-byte image archive;
  - `595d8ec2f8bb8e09e1e9fc1df2c4c09e` for the 15,958,208-byte outline archive.
- **Unused by CORA.** The project's records, study folders, documents and papers were searched for "puma", "13859989"
  and "Schuiveling":
  - folders searched: `records/`, `experiments/`, `cross_domain/`, `cora_cross_domain_transfer/`, `docs/`, `paper/`
    and the top-level notes;
  - the only match outside this folder is the autosave status line of this study's own download job;
  - there is no PUMA folder under `/path/to/data/`.
- **Not in the baseline's training data.** StarDist `2D_versatile_he` was trained on MoNuSeg 2018 training images and
  TNBC, and PUMA comes from routine diagnostics, not from The Cancer Genome Atlas.
- **Unopened.**
  - The archives are not extracted.
  - `data/work/puma/` does not exist.
  - The only PUMA-derived files are the format ROI's: its image copy, 3 StarDist label maps and 2 JSON records.
- **Archive and selection rule, checked from member names only.**
  - The image archive has 206 TIFF members (103 primary, 103 metastatic), with 206 matching outline files.
  - The format ROI, recomputed as the smallest sha256 of `"calacc_format:<roi>"`, is `training_set_primary_roi_028`.
  - With a dummy salt (64 zeros, not the GO salt), `held_selection` gives 100 held ROIs (50 primary, 50 metastatic) and
    105 reserve ROIs (52 primary, 53 metastatic). The format ROI is in neither set, and the three sets cover all 206.
- **Salt.**
  - `cadata.go_salt` hashes the bytes of `GO_CAL` and never interprets them.
  - `select` refuses to run without `GO_CAL`.
  - `held` asserts that the salt has not changed since selection.
  - The control seeds come from the same salt.
  - `GO_CAL` does not exist; this was tested for existence only.
- **Disclosure needed: the format ROI counts.**
  - Result: before the rule reached its final version (format check 06:38Z to 06:39Z; final chain 07:03Z), the format
    ROI's counts were visible: 292 reference nuclei, against 252 (NATIVE), 349 (TUNED) and 412 (LOW) StarDist
    objects. Its F1 was not computed.
  - Lesson: one ROI's counts are a small look at the held source. They show over-detection at the tuned threshold,
    which does not favour `add_lowthresh`.
  - Direction: the result record states these counts as a pre-GO look (condition 6).

### Check 3. Calibration uses NuInsSeg calibration organs only

- **Organs and images.** U5's manifest has 236 calibration images in 12 organs:
  - 92 induction images in 6 organs;
  - 144 validation images in 6 organs.
  - The 429 evaluation images in 19 organs share no organ with them.
- **Code.**
  - `caharness.cal_uids` keeps only `side == "calibration"`.
  - Every arm's demonstrations are these 236 images. The development queries are the 144 validation images.
- **Failure evidence.**
  - It comes from the induction organs (`GATE.json` and the 189 probe records).
  - It gives the order `add_lowthresh`, `split_dt`, `split_int`, `delete`, `clear_border`, `close`, `dilate`, `open`,
    `erode`, `merge_pairs`.
  - Its per-class oracle gains are ADD 0.240, SPLIT 0.116, DELETE 0.059, GROW 0.046, SHRINK 0.038, MERGE 0.022,
    FILL 0.
- **Nothing is tuned on PUMA.** The thresholds and the deletion rule were tuned on NuInsSeg calibration images.
- **The certificate, recomputed.** CALIBRATED's certificate was recomputed independently from its per-organ record,
  and it matches the frozen record and PROTOCOL.md section 7:
  - mean out-of-organ per-image F1 change +0.01682, one-sided 95% lower bound +0.00439 (t quantile 1.796, 11 degrees
    of freedom);
  - harmful-edit rate 147 of 337 (0.436), upper bound 0.530;
  - 12 of 12 folds have a fold program.

### Check 4. The arms differ only in the intended factor, with equal budgets; the controls are real

- **The three rules.** STRICT, TOLERANT and CALIBRATED receive the same 3 operators, in the same order, on the same 12
  organs and the same starting segmentation. They differ only in the acceptance rule.
- **Equal budget** means 3 operators offered to every CORA arm.
  - Under fixed-sequence testing, CALIBRATED tested 2 of its 3 operators.
  - Calibration CPU is measured: 56.6 s (CALIBRATED), 62.0 s (STRICT), 68.5 s (TOLERANT).
  - MATCHED_SEARCH's budget, 116.3 s, is CPU time, not wall-clock time, so machine load does not change it. It used
    122.6 s and stopped at the budget. The held run applies its frozen program, whose hash is asserted.
- **CAL_BLIND is a real control: the same rule and the same budget of 3 operators, drawn uniformly from the 11.**
  - Result: under fixed-sequence testing, a blind arm can edit only if its first draw is accepted alone on the
    calibration organs. In the final-rule scan (`development/LAMBDA_SCAN_FINAL.json`, in-fold limit 0.40) that is
    `add_lowthresh` or `dilate`, 2 of the 11 operators.
  - A given seed applies `add_lowthresh` with probability at most 1/11 + 1/110 = 0.10. So with probability at least
    0.9^5 = 0.59, none of the 5 seeds applies it.
  - Lesson: a blind arm that draws `add_lowthresh` second or third never reaches it.
  - Direction: see check 5 and condition 5.
- **CAL_SHUFFLED is real in design but degenerate.**
  - Result: a derangement moves ADD's oracle gain, the largest, to another class, so `add_lowthresh` is never first.
    Over all 1,854 of 1,854 derangements of the 7 classes, the first operator is `open`, `delete`, `fill_holes`,
    `close`, `split_dt` or `merge_pairs` (309 each). Each fails alone on the calibration organs, by lack of
    out-of-organ edits or of a certified gain. So every shuffled seed abstains, for any GO salt, and CAL_SHUFFLED
    equals STRONG_NATIVE exactly on the held ROIs. The development split showed this: 0 edits in 5 of 5 seeds.
  - Lesson: under stop-at-first-failure testing, a derangement control cannot reach the single useful operator, so its
    outcome is fixed before any held image is seen.
  - Direction: report it as descriptive, equal to the primary contrast by construction (condition 4). A later design
    should test all 3 operators with a Holm adjustment, or derange within the specified list.

### Check 5. The primary and co-primary are sound and pre-registered

- **What is pre-registered (PROTOCOL.md section 8, with `CONFIG.json`), and how `caharness.evaluate` implements it.**
  - **P1:** CALIBRATED minus STRONG_NATIVE, the mean per-image object F1 difference over the 100 held ROIs. Objects
    match at an intersection over union above 0.5.
  - **P2:** CALIBRATED minus CAL_BLIND, with CAL_BLIND the image-by-image mean of its 5 seeds.
  - **The interval:** a 95% percentile bootstrap over ROIs (10,000 resamples, `default_rng(0)`, U5's `boot`).
  - **The p value:** a one-sided bootstrap p = (1 + resampled means at or below 0) / 10,001.
  - **Holm over P1 and P2:** each is supported if its Holm-adjusted p is at most 0.025 and its interval lies above 0.
  - **H1 (primary):** P1 is supported AND CALIBRATED's pooled held harmful-edit rate is at most 0.60.
  - **The label order:** NON_DEGRADATION_ONLY, HARMFUL, SUPPORTED, GAIN_BUT_BOUND_EXCEEDED, BOUND_HELD_NO_MEASURED_GAIN,
    NO_MEASURED_GAIN. The code follows this order exactly.
  - **Edits** are judged alone by replaying every log from STRONG_NATIVE. The replay must reproduce the frozen labels.
  - **The dry run** exercised all of this. The evaluator ran twice on the same frozen decisions with identical output.
- **The co-primary repeats the primary when no blind seed applies `add_lowthresh`.**
  - Result: in that case, P2's per-image differences equal P1's except where a dilate-first seed edited. The two p
    values are then close, and Holm gives both about twice the smaller one. So H1 and H2 usually stand or fall together.
  - Lesson: the co-primary measures whether the failure-evidence ORDER beats a random order under stop-at-first-failure
    testing. That order comes from the per-class oracle gains on 6 induction organs. CORA's probes found no fitting
    program for any class, so they did not shape it.
  - Direction: report H2 in those words, with each blind seed's draw and statuses (condition 5).
- **The bound was set after looking, and it is weak.**
  - Result: 0.60 is the version-1 out-of-organ upper bound, 0.581, rounded up to the next tenth (PROTOCOL.md section
    6.1). It allows 6 in 10 accepted edits to be harmful. H1's harm part uses the point rate. `evaluate()` does not
    write the "bound confirmed" test of section 8: the upper end of the rate's 95% interval at most 0.60.
  - Lesson: a bound chosen after looking at the same organs is a description, not a guarantee.
  - Direction: report the held rate with its interval, the bound in words, and "bound confirmed: yes or no", computed
    from `harmful_rate_ci95` (condition 6).

### Check 6. Stop rules, the CPU cap and the detached run command

| stop rule (PROTOCOL.md section 9) | where it is enforced |
|---|---|
| 1. Without GO_CAL, exit 2 and open nothing | `run_after_go.py` lines 51 to 53; `cadata.select` and `cadata.held` refuse |
| 2. Freeze check before selection | `verify_freeze` is step 1; a non-zero exit stops the chain (lines 74 to 76) |
| 3. Recomputed calibration records must equal the frozen ones | `caharness.freeze_decisions`: statuses, programs and bounds of STRICT, TOLERANT and CALIBRATED; it stops before `DECISIONS_FROZEN.json` exists, and `Reader.open_evaluator` refuses without that file |
| 4. A failed step stops the chain | any non-zero exit gives EXIT 1; `pool` exits 1 if any arm fails |
| 5. CPU cap 43,200 CPU-s, checked before each step | `run_after_go.py` lines 57 to 64 (child CPU from `getrusage`); about 4,300 CPU-s expected, so the cap is 10 times that |
| 6. No re-run after references are decoded, except to finish the evaluation | finished steps are skipped; `evaluate` re-checks the hashes of all decisions |
| 7. The reserve is never opened | `Reader._guard_image` refuses any ROI that is neither held nor the format ROI |

- **The detached command.** It is in PROGRESS.md and in the docstring of `run_after_go.py`, to be run from the project
  root without `--slot`. At review time:
  - the job name `cal_calacc_held` was unused;
  - both shared CPU slots were free;
  - both interpreters (`<python environment>` and the StarDist environment) exist.
- **Gap 3: a restart skips the freeze check.**
  - Result: on a restart the chain skips every finished step, and the freeze check is one of them. Code edited after a
    failure would run unchecked.
  - Lesson: the freeze check must run at every start, not once.
  - Direction: before any restart, delete the marker `data/work/held_steps/verify_freeze`, so that the chain checks the
    freeze again. Record every restart in the result record (condition 2).

### Check 7. Leakage, overclaim and labels

- **Leakage paths checked and closed.**
  - Decisions never read held references: `PumaSet.ref` raises.
  - References are decoded only after every decision is hashed.
  - The calibrated rule touches the held ROIs only to apply its final program.
  - MATCHED_SEARCH and MATCHED_SEARCH_U5 apply frozen programs, and their hashes are asserted.
  - The selection depends only on ROI names and the salt.
- **Remaining path 1: the salt.**
  - Result: whoever writes `GO_CAL` fixes the held set and all 10 control seeds. If the text can be predicted or tried
    again, the held set and the seeds can be chosen. For example, one could pick a text whose 5 blind seeds all start
    with an operator that fails, which favours P2.
  - Lesson: the salt must be unpredictable and used once.
  - Direction: GO is written once, with a fresh random nonce, and committed at once. No one computes the salt, the held
    set or the seeds before the chain does (condition 1).
- **Remaining path 2: the format ROI.** Its counts were seen before the final rule (check 2). They are disclosed in the
  result record.
- **Disclosed limits that stay.**
  - The in-fold limit and the bound were chosen while looking at the same 12 organs, so the calibration certificate is
    optimistic.
  - A patient may have given both a primary and a metastatic ROI.
  - PUMA's reference began as HoVer-Net outlines.
  - NuInsSeg's calibration organs include 12 melanoma images.
- **Overclaim risks: wording the result record must avoid.**
  - "Failure evidence chose the operator" or "CORA's reasoning found the fix". Say instead: the per-class failure costs
    put ADD first, and that order beat random orders under stop-at-first-failure testing.
  - "Harm was controlled" or "safe". Say the held harmful-edit rate with its interval, and that the bound allows up to
    6 in 10 harmful edits.
  - "CALIBRATED beat the shuffled-failure control" offered as separate evidence. That contrast equals P1 by
    construction.
  - "Tumour-cell nuclei". PUMA outlines every nucleus in the ROI, so say "nuclei in melanoma ROIs".
  - A positive result shows transfer to one new source of one cancer type, not to histology in general (PROTOCOL.md
    section 12).
- **Labels.**
  - **Pre-registered, confirmatory:** P1, P2, H1, H2, the CALIBRATED label, "bound confirmed", and the stratified
    bootstrap as the named sensitivity analysis.
  - **Descriptive:** average precision, pooled F1, NATIVE and TUNED, STRICT, TOLERANT, MATCHED_SEARCH,
    MATCHED_SEARCH_U5, CAL_SHUFFLED, and every arm against STRONG_NATIVE.
  - **Must read "exploratory":** per-stratum means read as findings; which guards fired on PUMA; harm by stratum, ROI or
    nucleus type; and any analysis chosen after the result is seen.
  - **Must read "development, optimistic":** the calibration certificate (lower bound +0.0044, upper bound 0.530).

## 2. Process notes, checked against the record

- **A failed dry run that PROGRESS.md does not mention.**
  - Result: `cal_calacc_dryrun2` exited 1 at 07:06:48Z. `MATCHED_SEARCH.json` had not yet been written by the final
    chain; it was written at 07:06:54Z.
  - The passing dry run, `cal_calacc_dryrun3`, started at 07:07:12Z, after all 4 final records existed. Its stand-in
    freeze lists the 4 frozen record hashes.
  - It ran a copy, `data/work/dryrun/dryrun_held.py`, that differs from the frozen `tests/dryrun_held.py` only in 2
    docstring lines.
  - Lesson and direction: name both facts in the result record.
- **A stale label.**
  - Result: `development/LAMBDA_SCAN_FINAL.json` says "level 0.05/3 one-sided", but its final mode used 0.05. Its
    `add_lowthresh` row at the 0.40 limit reproduces CALIBRATED's lower bound, +0.0044, which was computed at 0.05.
  - Lesson and direction: cite 0.05. The record is hashed, so it is left as is.
- **The bytecode incident** agrees with the folder times. U5's `scripts/__pycache__` folder last changed at 06:48Z, and
  no `u5eval` bytecode file remains. This review wrote none.
- **CPU footprint.** The arm step runs 3 processes in one shared slot, and segmentation uses up to 4 threads in one
  slot, as in the calibration chain. The load average was about 20 on 24 cores at review time. No change is needed.

## 3. Conditions for GO (non-blocking; accepted by writing GO)

1. **The salt.**
   - Write `GO_CAL` once, ending in a newline, with the UTC time of writing and a fresh nonce: 32 hexadecimal
     characters from a cryptographic random source.
   - Commit it at once with a path-limited commit.
   - Never edit it.
   - No one computes the salt, the held set or the control seeds before the chain does.
2. **Restarts.** Before any restart, delete `data/work/held_steps/verify_freeze`, so that the freeze check runs again.
   Record every restart, and any change to a frozen file, as a deviation in the result record.
3. **The calibration arrays.** After the run, recompute the four listing hashes of section 1 (gap 1). A difference is a
   deviation.
4. **CAL_SHUFFLED.** Report it as "descriptive; abstains for every salt by construction; its contrast equals P1".
5. **H2.** Report it as a test of the failure-evidence order against random orders under stop-at-first-failure testing.
   List each blind seed's 3 draws, its statuses, and whether `add_lowthresh` was drawn at any position. Do not
   attribute the order to CORA's probes.
6. **Disclosures and labels.**
   - Report the held harmful-edit rate with its 95% interval, the bound 0.60 in words, and "bound confirmed: yes or no".
   - State the format ROI counts as a pre-GO look.
   - Give the dry-run facts of section 2.
   - Apply the labels of check 7.

## 4. GO lines this review would accept

The bytes of `GO_CAL` become the salt. Fill in the review's sha256 as committed. Fill in the last two lines at the
moment of writing, and never reuse them:

```
GO calibrated_acceptance_20261108
freeze_commit 9f283c2c4d000e3dc5627379f7d590cf60d0f219
freeze_json_sha256 7e5c55efc625dc684c4a2de9469b605066781fc47cf49859c114dad31c3ef56f
pre_run_review_sha256 <sha256 of reviews/PRE_RUN_REVIEW.md as committed>
review_verdict PASS-WITH-NOTES; conditions 1 to 6 of section 3 accepted
written_utc <UTC time of writing>
nonce <32 hexadecimal characters drawn at writing time from a cryptographic random source>
```

Then start the held chain from the project root, without `--slot`:
`sh scripts/run_detached.sh cal_calacc_held python3 -I -B experiments/calibrated_acceptance_20261108/scripts/run_after_go.py`
