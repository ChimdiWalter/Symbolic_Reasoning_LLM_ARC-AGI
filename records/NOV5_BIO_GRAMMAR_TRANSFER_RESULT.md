# Result U5: a literature bioimage grammar admitted from the frozen CORA component's failures, used under verify-or-abstain, and tested for transfer (2 Nov 2026)

This is a fresh, pre-registered evaluation.

- **Protocol.** `experiments/universality_bio_grammar_20261103/PROTOCOL.md` (sha256 `7d5ef686...`, commit ddb0dc89)
  was frozen before any download.
- **Amendments.** Nine dated amendments were each frozen by hash before any evaluation outcome. Amendments 3, 5, 7 and
  9 answer independent reviews.
- **Code.** Frozen by hash in `CODE_FREEZE.json` (`96c22c5d...`, 24 files, 27 regression tests).
- **Policy.** Frozen on calibration parents in `POLICY_FREEZE.json` (`a67326dc...`).
- **Primary decisions.** Frozen in `DECISIONS_FROZEN.json` (`d966993d...`) before any evaluation reference was
  decoded. The Reader's guard enforces this.
- **Primary results.** `results/RESULTS.json` (`45ac3eb9...`, commit c4405c80), written by the detached chain at
  18:26:30Z after the coordinator's GO at 16:10Z.
- **Scope of this record.** Only public data. The private target's results are reported outside git.

## Short answer

- **Procedurally portable, with observed non-degradation through zero-edit abstention; inert on biology.**
  - Failure records from the frozen ARC component specified ten literature operators for LIVECell. The strict
    verify-or-abstain admission accepted none.
  - On held-out parents of LIVECell, NuInsSeg and MoNuSAC, CORA therefore made zero edits: no gain and no harm
    (NON_DEGRADATION_ONLY on all three).
  - There is no learned transfer (LEARNED_TRANSFER false) and no grammar growth.
- **The candidate operator set supports a positive matched-search contrast on MoNuSAC.** Under the same frozen
  protocol, a compute-matched static search over the same operators gave +0.0116 mean per-parent F1 against the strong
  native baseline on MoNuSAC.
  - Its unadjusted 95% CI is [+0.0066, +0.0169]. This is a descriptive contrast: no multiplicity-adjusted test was
    pre-declared for this comparator.
  - Switching every operator on gave -0.0248 [-0.0354, -0.0161] on LIVECell.
- **The bottleneck is the acceptance rule.** The calibration diagnostics show exactly where it lies:
  - specification worked;
  - admission failed on harm to single parents, on leave-one-parent-out instability, and on unanimity. For close, 152
    near-optimal programs agreed on 6 of 23,127 units.

## Notes from the independent pre-result audit (applied here without changing any frozen byte or threshold)

1. **Coverage.** The evaluator's `coverage` is accepted edits per baseline object, not unique-object coverage. It is
   named that way below. For add operations it can exceed 1: ALL_ON has 2.2 to 2.6.
2. **Edit counts.** `growth_gates.b_useful_construction` counts query applications, not beneficial edits. Aggregate
   beneficial and harmful edit counts are reported for every arm before any growth statement. No operator was
   admitted, so no growth claim is made.
3. **Strict and tolerant claims.** The strict grammar and both strict control families admitted no operator, so a
   positive strict learned-transfer label was impossible.
   - The tolerant arm admits add_lowthresh, and so do 4 of 5 failure-blind and 4 of 5 shuffled tolerant seeds.
   - Any tolerant claim must pass the pre-declared control gates.

### Later independent audits (outbox 0194, 0196, 0217; aggregate only)

The audits passed the frozen primary numbers and the negative learned-transfer and growth labels, with all 24
code-freeze entries and 96 decision-artifact hashes matching. Their wording fixes are applied in this revision:
- the matched-search contrasts are descriptive;
- "safe" means observed non-degradation through zero-edit abstention;
- the native contrasts are not CORA's contribution;
- 27 tests.

## Claim for the paper

The four questions are answered separately. Each answer comes from the pre-registered primary arms. The tolerant arm
is secondary and calibration-informed, the private target is reported outside git, and neither changes a primary
answer.

1. **Portability: shown.**
   - The method ran unchanged on three public biology datasets: phase-contrast cells, H&E nuclei from 31 organs, and
     H&E nuclei from 67 TCGA patients. The method here means failure records from the frozen ARC component, an
     admission gate, verify-or-abstain over typed object programs, exact conflict-safe certification, and leak-free
     parent-level splits.
   - The frozen `cast_selective_v2` package ran byte-identical on biology probe tasks.
   - Every decision was frozen by hash before any evaluation reference was decoded.
   - Portability is an engineering result. It is not usefulness.
2. **Cross-domain usefulness: not shown.** On the held-out parents of all three datasets, the strict CORA made zero edits (label
   NON_DEGRADATION_ONLY). Its pooled F1 equals the strong native baseline: LIVECell 0.5628, NuInsSeg 0.5823, MoNuSAC
   0.6745. It neither helped nor harmed.
3. **Learned transfer: not shown, and not testable as a positive result.** The grammar induced on LIVECell is empty, so
   nothing learned was transferred. LEARNED_TRANSFER is false (status TWO_TARGETS).
4. **Grammar growth: not supported.** The failure records specified ten literature operators. Admission on separate
   calibration parents admitted none, because the strict verify-or-abstain rule abstained on every one:
   - five had no harmless fit;
   - four failed leave-one-parent-out;
   - close failed unanimity: 152 near-optimal programs agreed on 6 of 23,127 units.
   Growth gates (b) and (d) fail.

**What the paper may say.**
- The CORA design ports to biological instance segmentation without code changes.
- Its failure-to-specification path ran as designed: every probed class was NOT_FOUND_WITHIN_BUDGET. The specified
  operators included those the matched search later used (add_lowthresh, delete, erode).
- Specification was not selective: 10 of the 11 operators were specified. In the exploratory budgeted-selection
  analysis, prioritizing by failure evidence was only weakly ahead of a random order.
- Its verify-or-abstain rule did not harm the strong baselines. It made no edit on held-out parents, so the safety
  here comes from abstention, not from verified gains.
- The same rule is too strict to admit any operator on LIVECell. The diagnostics show exactly which step blocks each
  operator.
- Paper-safe summary: the same frozen U5 procedure executed across three parent-held-out imaging datasets, but its
  strict source grammar admitted no operator and made no held-out edits. This shows procedural portability, not useful
  learned transfer.
- Under the same frozen protocol, a compute-matched static search over the same literature operators, fitted on
  calibration parents, gave these descriptive changes in mean per-parent F1 against the strong native baseline:
  - MoNuSAC: +0.0116 [+0.0066, +0.0169], 33 of 40 patients better;
  - NuInsSeg: +0.0094 [-0.0063, +0.0225], directionally positive;
  - LIVECell: +0.0002 [-0.0024, +0.0029], neutral.
  Switching every literature operator on (ALL_ON) gave -0.0248 [-0.0354, -0.0161] on LIVECell.
  - These are descriptive, unadjusted parent-bootstrap contrasts. Amendment 3's Holm adjustment covers only the
    contrasts of CORA.
  - The candidate operator set therefore supports a positive matched-search contrast on MoNuSAC, and CORA's admission
    from LIVECell's failures did not find those edits.

**What it may not say.**
- That CORA improves biological segmentation, transfers a learned grammar across datasets, or grows its grammar from
  failures in biology.
- That the comparators had identical search effort. Work equality is the frozen operational criterion.
- That CORA contributed the gains over NATIVE. CORA equals the calibration-tuned STRONG_NATIVE baseline, so its
  positive contrasts against NATIVE come from the baseline's tuning, not from any CORA edit.
- That the matched search's gain is a confirmed inferential result. It is a descriptive contrast.
- Anything about the private target beyond the separately reported, aggregate, private-data results.

**Learning from failure.** The result locates the bottleneck in admission.
- Specification ran but was not selective.
- Admission blocked every operator. Its three requirements were designed for ARC's exact tasks: no harm to any
  demonstration parent, a stable leave-one-parent-out top, and unanimity of the near-optimal programs. They reject
  object edits whose benefit differs across biological parents.
- The tolerant arm tests whether relaxing the last two changes the answer. It is reported below as secondary.

## Primary results (held-out parents; pooled object F1 at IoU 0.5; contrasts are mean per-parent F1 differences with 95% parent-clustered bootstrap CIs, 10,000 resamples)

ABSTAIN_ALL is STRONG_NATIVE. CORA's grammar is empty, so CORA, FAILURE_BLIND and SHUFFLED all equal ABSTAIN_ALL.

- **Native contrasts.** CORA minus NATIVE and CORA minus TUNED measure the calibration-tuned baseline, not any CORA
  edit. On NuInsSeg the strong native deletion filter, chosen on calibration, cost -0.0003 [-0.0006, -0.0000] against
  TUNED.
- **Holm.** Holm-adjusted p values apply only to CORA's separately asserted contrasts. Contrasts of other arms against
  ABSTAIN_ALL are descriptive.
- **Floating point.** Control contrasts of about 1e-17 are floating-point artifacts. Zero edits leave edit precision
  undefined. Beneficial and harmful counts judge each accepted edit alone against the reference; most edits of ALL_ON and MATCHED_SEARCH are neutral.

### LIVECell (A): 19 evaluation parents, 288 images; label **NON_DEGRADATION_ONLY**

| arm | pooled F1 | mean parent F1 | pooled AP | accepted edits | beneficial | harmful | edit precision [95% CI] | accepted edits per baseline object |
|---|---|---|---|---|---|---|---|---|
| NATIVE | 0.5415 | 0.4812 | 0.1869 |  |  |  |  |  |
| TUNED | 0.5628 | 0.5332 | 0.2166 |  |  |  |  |  |
| STRONG_NATIVE | 0.5628 | 0.5332 | 0.2166 |  |  |  |  |  |
| ALL_ON | 0.5410 | 0.5084 | 0.1728 | 124142 | 2492 | 3095 | 0.020 [0.014, 0.029] | 2.206 [2.045, 2.504] |
| MATCHED_SEARCH | 0.5645 | 0.5334 | 0.2083 | 20144 | 308 | 183 | 0.015 [0.009, 0.025] | 0.358 [0.316, 0.426] |
| CORA | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.000 [0.000, 0.000] |
| FAILURE_BLIND (x5) | 0.5628, 0.5628, 0.5628, 0.5628, 0.5628 | | | 0 in all | | | | |
| SHUFFLED (x5) | 0.5628, 0.5628, 0.5628, 0.5628, 0.5628 | | | 0 in all | | | | |

| contrast (per parent F1) | mean [95% CI] | parents better/worse/equal | Holm-adjusted p |
|---|---|---|---|
| CORA - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] | 0/0/19 | 1.000 |
| CORA - NATIVE | +0.0520 [+0.0299, +0.0760] | 17/2/0 |  |
| CORA - TUNED | +0.0000 [+0.0000, +0.0000] | 0/0/19 |  |
| CORA - ALL_ON | +0.0248 [+0.0161, +0.0354] | 18/1/0 | 0.000 |
| CORA - MATCHED_SEARCH | -0.0002 [-0.0029, +0.0024] | 10/8/1 | 1.000 |
| CORA - FAILURE_BLIND | -0.0000 [-0.0000, +0.0000] | 0/0/19 | 1.000 |
| CORA - SHUFFLED | -0.0000 [-0.0000, +0.0000] | 0/0/19 | 1.000 |
| ALL_ON - ABSTAIN_ALL | -0.0248 [-0.0354, -0.0161] | 1/18/0 | |
| MATCHED_SEARCH - ABSTAIN_ALL | +0.0002 [-0.0024, +0.0029] | 8/10/1 | |
| TUNED - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] | 0/0/19 | |

Growth gates: admitted none; held outputs changed False; beats matched static False; beats blind and shuffled False; growth supported False. Failure-evidence diagnostic WITHHELD_UNMATCHED_WORK. MATCHED_SEARCH work-matched True (CPU 1053.0 s against CORA's upper 857.9 s); controls work-matched False.

Sensitivity, cell lines as clusters (8 groups): CORA - ABSTAIN_ALL +0.0000 [+0.0000, +0.0000]; CORA - ALL_ON +0.0248 [+0.0124, +0.0412]; CORA - MATCHED_SEARCH -0.0002 [-0.0042, +0.0036]; CORA - FAILURE_BLIND -0.0000 [-0.0000, +0.0000]; CORA - SHUFFLED -0.0000 [-0.0000, +0.0000].

### NuInsSeg (B): 19 evaluation parents, 429 images; label **NON_DEGRADATION_ONLY**

| arm | pooled F1 | mean parent F1 | pooled AP | accepted edits | beneficial | harmful | edit precision [95% CI] | accepted edits per baseline object |
|---|---|---|---|---|---|---|---|---|
| NATIVE | 0.4615 | 0.4507 | 0.1548 |  |  |  |  |  |
| TUNED | 0.5824 | 0.5653 | 0.1915 |  |  |  |  |  |
| STRONG_NATIVE | 0.5823 | 0.5650 | 0.1915 |  |  |  |  |  |
| ALL_ON | 0.5848 | 0.5647 | 0.1874 | 36055 | 620 | 669 | 0.017 [0.013, 0.023] | 2.608 [2.459, 2.827] |
| MATCHED_SEARCH | 0.5954 | 0.5744 | 0.1948 | 3963 | 1082 | 842 | 0.273 [0.198, 0.356] | 0.287 [0.243, 0.358] |
| CORA | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.000 [0.000, 0.000] |
| FAILURE_BLIND (x5) | 0.5823, 0.5823, 0.5823, 0.5823, 0.5823 | | | 0 in all | | | | |
| SHUFFLED (x5) | 0.5823, 0.5823, 0.5823, 0.5823, 0.5823 | | | 0 in all | | | | |

| contrast (per parent F1) | mean [95% CI] | parents better/worse/equal | Holm-adjusted p |
|---|---|---|---|
| CORA - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] | 0/0/19 | 1.000 |
| CORA - NATIVE | +0.1143 [+0.0784, +0.1499] | 18/1/0 |  |
| CORA - TUNED | -0.0003 [-0.0006, -0.0000] | 2/4/13 |  |
| CORA - ALL_ON | +0.0003 [-0.0084, +0.0089] | 11/8/0 | 1.000 |
| CORA - MATCHED_SEARCH | -0.0094 [-0.0225, +0.0063] | 5/14/0 | 1.000 |
| CORA - FAILURE_BLIND | +0.0000 [+0.0000, +0.0000] | 0/0/19 | 1.000 |
| CORA - SHUFFLED | +0.0000 [+0.0000, +0.0000] | 0/0/19 | 1.000 |
| ALL_ON - ABSTAIN_ALL | -0.0003 [-0.0089, +0.0084] | 8/11/0 | |
| MATCHED_SEARCH - ABSTAIN_ALL | +0.0094 [-0.0063, +0.0225] | 14/5/0 | |
| TUNED - ABSTAIN_ALL | +0.0003 [+0.0000, +0.0006] | 4/2/13 | |

Growth gates: admitted none; held outputs changed False; beats matched static False; beats blind and shuffled False; growth supported False. Failure-evidence diagnostic WITHHELD_UNMATCHED_WORK. MATCHED_SEARCH work-matched True (CPU 858.4 s against CORA's upper 857.9 s); controls work-matched False.

### MoNuSAC (C): 40 evaluation parents, 169 images; label **NON_DEGRADATION_ONLY**

| arm | pooled F1 | mean parent F1 | pooled AP | accepted edits | beneficial | harmful | edit precision [95% CI] | accepted edits per baseline object |
|---|---|---|---|---|---|---|---|---|
| NATIVE | 0.6439 | 0.6549 | 0.2833 |  |  |  |  |  |
| TUNED | 0.6721 | 0.6977 | 0.2891 |  |  |  |  |  |
| STRONG_NATIVE | 0.6745 | 0.6951 | 0.2922 |  |  |  |  |  |
| ALL_ON | 0.6802 | 0.7040 | 0.2837 | 67566 | 1798 | 1906 | 0.027 [0.022, 0.031] | 2.599 [2.521, 2.684] |
| MATCHED_SEARCH | 0.6843 | 0.7068 | 0.2948 | 2230 | 989 | 1158 | 0.443 [0.387, 0.509] | 0.086 [0.073, 0.100] |
| CORA | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.000 [0.000, 0.000] |
| FAILURE_BLIND (x5) | 0.6745, 0.6745, 0.6745, 0.6745, 0.6745 | | | 0 in all | | | | |
| SHUFFLED (x5) | 0.6745, 0.6745, 0.6745, 0.6745, 0.6745 | | | 0 in all | | | | |

| contrast (per parent F1) | mean [95% CI] | parents better/worse/equal | Holm-adjusted p |
|---|---|---|---|
| CORA - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] | 0/0/40 | 1.000 |
| CORA - NATIVE | +0.0403 [+0.0262, +0.0545] | 34/6/0 |  |
| CORA - TUNED | -0.0026 [-0.0083, +0.0024] | 18/20/2 |  |
| CORA - ALL_ON | -0.0089 [-0.0148, -0.0031] | 11/29/0 | 1.000 |
| CORA - MATCHED_SEARCH | -0.0116 [-0.0169, -0.0066] | 7/33/0 | 1.000 |
| CORA - FAILURE_BLIND | +0.0000 [+0.0000, +0.0000] | 0/0/40 | 0.219 |
| CORA - SHUFFLED | +0.0000 [+0.0000, +0.0000] | 0/0/40 | 0.219 |
| ALL_ON - ABSTAIN_ALL | +0.0089 [+0.0031, +0.0148] | 29/11/0 | |
| MATCHED_SEARCH - ABSTAIN_ALL | +0.0116 [+0.0066, +0.0169] | 33/7/0 | |
| TUNED - ABSTAIN_ALL | +0.0026 [-0.0024, +0.0083] | 20/18/2 | |

Growth gates: admitted none; held outputs changed False; beats matched static False; beats blind and shuffled False; growth supported False. Failure-evidence diagnostic WITHHELD_UNMATCHED_WORK. MATCHED_SEARCH work-matched True (CPU 863.2 s against CORA's upper 857.9 s); controls work-matched False.

### Transfer to the two targets

Status TWO_TARGETS; LEARNED_TRANSFER **False**.

| contrast (mean of the two targets, stratified bootstrap) | mean [95% CI] |
|---|---|
| CORA - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] |
| CORA - ALL_ON | -0.0043 [-0.0096, +0.0008] |
| CORA - MATCHED_SEARCH | -0.0105 [-0.0176, -0.0024] |
| CORA - FAILURE_BLIND | +0.0000 [+0.0000, +0.0000] |
| CORA - SHUFFLED | +0.0000 [+0.0000, +0.0000] |

## Calibration-side record (before any evaluation outcome)

### Induction on A (LIVECell, calibration parents only)

- **Failure records.** Every probed correction class was NOT_FOUND_WITHIN_BUDGET: the frozen package's search found
  no fitting program in its window encoding (40/40 probes per class). There were no FILL instances.
- **Specification.** Ten operators were specified, ordered by the class oracle gain on the induction wells:
  - SPLIT 0.122: split_dt, split_int;
  - ADD 0.069: add_lowthresh;
  - DELETE 0.068: delete, clear_border;
  - GROW 0.012: close, dilate;
  - SHRINK 0.011: open, erode;
  - MERGE 0.0067: merge_pairs.
- **Admission.** None was admitted: each made 0 accepted edits on the six validation wells (F1 0.4622 throughout).
  Each step of the acceptance rule blocked part of the grammar:

  | step of the rule | operators blocked | what failed |
  |---|---|---|
  | fit: positive pooled gain with no demonstration parent harmed | split_int, delete, clear_border, dilate, merge_pairs (NO_FIT) | every program that helped some wells harmed at least one other |
  | leave-one-parent-out: each fold's top program must not harm its held-out well | split_dt, add_lowthresh, open, erode (LOO_FAIL) | a gain found on five wells did not hold on the sixth |
  | agreement: every fitting program and fold top must select the same units | close (EVIDENCE with 152 fitting programs) | the 152 near-optimal programs agreed on none of 23,127 query units |

- **Controls.** The five failure-blind and five shuffled controls (10 candidates each, the same ceiling) admitted
  nothing either.
- **Work.** CORA's admission took 804.3 CPU-s; the controls took 177-293 CPU-s. The controls ran after CORA in the same
  process and reused its cached unit tables (1,518 unit tables for CORA, 0-138 for them). The pre-registered CPU
  factor-of-two rule therefore marks them unmatched, although each validated the same 10 candidates.
- **Probe CPU.** The probes took 53.3 CPU-s, so CORA's induction CPU was 857.6 s.

The frozen CORA grammar is empty. On every target, CORA's decisions therefore equal ABSTAIN_ALL (STRONG_NATIVE).

**Acceptance waterfall for close** (Amendment 9 diagnostic, on the validation wells). Counts at each step:

| step | count |
|---|---|
| programs scored | 3,081 |
| harmless | 1,067 |
| positive pooled gain | 457 |
| admissible | 269 |
| FIT (within 0.9 of the best gain) | 152 |
| units selected by some FIT program | 5,139 of 23,127 |
| units selected by every FIT program | 6 |
| after adding the 2 distinct fold tops (one outside FIT) | 0 |
| folds failing the held-out check | 0 of 6 |
| units removed by the conflict rule from the top program | 0 of 111 |

The near-optimal programs disagreed about which objects to close. The unanimity step removed every unit.

### Policy freeze (POLICY_FREEZE.json, sha256 a67326dc...; calibration parents only)

| target | baseline calibration F1 | ALL_ON | MATCHED_SEARCH (program; CPU, stop) | strict in-domain admission |
|---|---|---|---|---|
| LIVECell (A) | 0.6088 | 0.5852 | 0.6112 (erode, guarded; 1,053 s, budget reached in the first stage) | n/a |
| NuInsSeg | 0.5032 | 0.4975 | 0.5275 (add_lowthresh, delete, erode; 858 s, budget reached inside a step) | none of 10 specified |
| MoNuSAC | 0.6869 | 0.6949 | 0.6988 (add_lowthresh; 863 s, budget reached) | none of 7 specified |

- **Work match.** CORA's conservative calibration CPU is 857.6 + 0.30 s (Amendment 9). Every MATCHED_SEARCH used more
  than half of it, so all three are work-matched by CPU. The failure-blind and shuffled controls are CPU-unmatched (the
  cache effect above).

### CORA_TOLERANT (calibration-informed secondary arm)

- **Admission on LIVECell.** add_lowthresh was admitted (46 validation edits; F1 0.4622 to 0.4625; 5 wells better, 1
  worse; top program in 4 of 6 folds).
  - close was EVIDENCE with 112 edits but changed no F1, so it was not admitted.
  - split_dt, open and erode had no two-thirds majority; the rest were NO_FIT.
- **Controls.** add_lowthresh was admitted in every failure-blind and shuffled seed whose draw contained it (8 of 10).
- **Tolerant in-domain admission.** NuInsSeg admitted add_lowthresh, dilate and erode; MoNuSAC admitted open.
- **Budgeted selection** (exploratory, post hoc, calibration only). CORA's failure-evidence order reaches add_lowthresh
  at a budget of 3; a random order of the 11 operators does so with probability 0.273 (`analysis/`).

## Secondary arms

They were decided after the primary commit and scored into `results/RESULTS_SECONDARY.json` (sha256 `77f349ed...`,
commit 5386fe60).
- **CORA_FULL:** all 11 operators under the strict rule, with each target's calibration parents as demonstrations.
- **CORA_INDOMAIN:** the strict in-domain admission, which admitted nothing on NuInsSeg or MoNuSAC.
- **PROGRAM_TRANSFER:** A's top programs, of which there were none.

| dataset | arm | pooled F1 | accepted edits | beneficial / harmful | arm - ABSTAIN_ALL (per parent) | better/worse/equal |
|---|---|---|---|---|---|---|
| LIVECell | CORA_FULL | 0.5628 | 0 | 0 / 0 | +0.0000 [+0.0000, +0.0000] | 0/0/19 |
| NuInsSeg | CORA_FULL | 0.5819 | 4000 | 1 / 7 | -0.0001 [-0.0003, +0.0000] | 0/3/16 |
| NuInsSeg | CORA_INDOMAIN | 0.5823 | 0 | 0 / 0 | +0.0000 [+0.0000, +0.0000] | 0/0/19 |
| NuInsSeg | PROGRAM_TRANSFER | 0.5823 | 0 | 0 / 0 | +0.0000 [+0.0000, +0.0000] | 0/0/19 |
| MoNuSAC | CORA_FULL | 0.6745 | 0 | 0 / 0 | +0.0000 [+0.0000, +0.0000] | 0/0/40 |
| MoNuSAC | CORA_INDOMAIN | 0.6745 | 0 | 0 / 0 | +0.0000 [+0.0000, +0.0000] | 0/0/40 |
| MoNuSAC | PROGRAM_TRANSFER | 0.6745 | 0 | 0 / 0 | +0.0000 [+0.0000, +0.0000] | 0/0/40 |

None of the secondary arms changes a primary answer. The only edits came from CORA_FULL on NuInsSeg: 4,000 accepted
edits, almost all neutral (1 beneficial, 7 harmful), for -0.0001 [-0.0003, +0.0000].

## CORA_TOLERANT (calibration-informed secondary arm, added after the empty LIVECell grammar was observed, before any evaluation outcome)

It was scored into `results/RESULTS_TOLERANT.json` (sha256 `70fb7b74...`, commit 77fb5d92) against the shared
comparators (STRONG_NATIVE, ALL_ON, MATCHED_SEARCH) and its own tolerant controls. It never replaces the primary CORA
label.

- **Pre-declared control gates.** A tolerant claim needs CROSS_DOMAIN_USEFUL on each target after the Amendment 7 work
  gates. That requires CORA_TOLERANT to beat ABSTAIN_ALL, ALL_ON, MATCHED_SEARCH and both tolerant control families
  with each lower 95% bound above 0, and the controls' work to be matched.
- **No target passes.**

**LIVECell**: label **NO_MEASURED_GAIN** (before work gates NO_MEASURED_GAIN); failure-evidence diagnostic WITHHELD_UNMATCHED_WORK; CORA_TOLERANT pooled F1 0.5627, 1 accepted edits (0 beneficial, 1 harmful).

| contrast (per parent F1) | mean [95% CI] | better/worse/equal |
|---|---|---|
| CORA_TOLERANT - ABSTAIN_ALL | -0.0000 [-0.0000, +0.0000] | 0/1/18 |
| CORA_TOLERANT - ALL_ON | +0.0248 [+0.0161, +0.0354] | 18/1/0 |
| CORA_TOLERANT - MATCHED_SEARCH | -0.0002 [-0.0029, +0.0024] | 10/8/1 |
| CORA_TOLERANT - FAILURE_BLIND_TOLERANT | -0.0000 [-0.0000, +0.0000] | 0/1/18 |
| CORA_TOLERANT - SHUFFLED_TOLERANT | -0.0000 [-0.0000, +0.0000] | 0/1/18 |
| CORA_TOLERANT - CORA | -0.0000 [-0.0000, +0.0000] | 0/1/18 |

**NuInsSeg**: label **NO_MEASURED_GAIN** (before work gates NO_MEASURED_GAIN); failure-evidence diagnostic WITHHELD_UNMATCHED_WORK; CORA_TOLERANT pooled F1 0.5824, 32 accepted edits (10 beneficial, 16 harmful).

| contrast (per parent F1) | mean [95% CI] | better/worse/equal |
|---|---|---|
| CORA_TOLERANT - ABSTAIN_ALL | -0.0006 [-0.0025, +0.0005] | 7/1/11 |
| CORA_TOLERANT - ALL_ON | -0.0003 [-0.0088, +0.0081] | 10/9/0 |
| CORA_TOLERANT - MATCHED_SEARCH | -0.0101 [-0.0224, +0.0040] | 5/14/0 |
| CORA_TOLERANT - FAILURE_BLIND_TOLERANT | -0.0001 [-0.0005, +0.0001] | 7/1/11 |
| CORA_TOLERANT - SHUFFLED_TOLERANT | -0.0001 [-0.0005, +0.0001] | 7/1/11 |
| CORA_TOLERANT - CORA | -0.0006 [-0.0025, +0.0005] | 7/1/11 |
| CORA_TOLERANT - CORA_TOLERANT_INDOMAIN | -0.0006 [-0.0019, +0.0001] | 2/2/15 |
| CORA_TOLERANT_INDOMAIN - ABSTAIN_ALL | +0.0000 [-0.0024, +0.0020] | 6/3/10 |

CORA_TOLERANT_INDOMAIN: pooled F1 0.5825, 516 accepted edits (17 beneficial, 22 harmful).

**MoNuSAC**: label **NON_DEGRADATION_ONLY** (before work gates NON_DEGRADATION_ONLY); failure-evidence diagnostic WITHHELD_UNMATCHED_WORK; CORA_TOLERANT pooled F1 0.6745, 0 accepted edits (0 beneficial, 0 harmful).

| contrast (per parent F1) | mean [95% CI] | better/worse/equal |
|---|---|---|
| CORA_TOLERANT - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] | 0/0/40 |
| CORA_TOLERANT - ALL_ON | -0.0089 [-0.0148, -0.0031] | 11/29/0 |
| CORA_TOLERANT - MATCHED_SEARCH | -0.0116 [-0.0169, -0.0066] | 7/33/0 |
| CORA_TOLERANT - FAILURE_BLIND_TOLERANT | +0.0000 [+0.0000, +0.0000] | 0/0/40 |
| CORA_TOLERANT - SHUFFLED_TOLERANT | +0.0000 [+0.0000, +0.0000] | 0/0/40 |
| CORA_TOLERANT - CORA | +0.0000 [+0.0000, +0.0000] | 0/0/40 |
| CORA_TOLERANT - CORA_TOLERANT_INDOMAIN | -0.0000 [-0.0001, +0.0001] | 1/2/37 |
| CORA_TOLERANT_INDOMAIN - ABSTAIN_ALL | +0.0000 [-0.0001, +0.0001] | 2/1/37 |

CORA_TOLERANT_INDOMAIN: pooled F1 0.6746, 4663 accepted edits (2 beneficial, 1 harmful).

Tolerant transfer block: status TWO_TARGETS; LEARNED_TRANSFER False.

- **Reading.** Relaxing leave-one-out and unanimity let the tolerant rule admit add_lowthresh on LIVECell, but its
  transferred edits were few and not helpful:
  - LIVECell: 1 edit, harmful;
  - NuInsSeg: 32 edits, 10 beneficial and 16 harmful;
  - MoNuSAC: 0 edits.
- **The tolerant controls** (4 of 5 failure-blind and 4 of 5 shuffled seeds admit the same operator) make the same
  decisions. The failure-evidence diagnostic is withheld for unmatched control CPU.
- **Answer.** The strictness of verify-or-abstain is not what kept CORA from helping here. The tolerant rule passes no
  pre-declared gate.

## Private target

The private target is specified in a private addendum outside git (Amendment 8). Its results are private data, not publicly reproducible, and the addendum has not been independently reviewed. They are reported to the coordinator only; none appear in this record.

## What was tested

Can CORA's design, extended by literature operators, improve strong segmentation baselines, and does a grammar induced
on one dataset transfer frozen to others? The design: answer with a typed object program only when it fits the
demonstrations and survives leave-one-out re-derivation, otherwise abstain.

- **Grammar.** 11 operators, each with a cited source:
  - re-detection (add_lowthresh);
  - hole filling;
  - two watershed splits, on the distance transform and on intensity;
  - merging of touching pairs;
  - closing, opening, dilation and erosion;
  - deletion filters;
  - border clearing.
- **Failure records.** The frozen `cast_selective_v2` (byte-identical, from the submitted entry) was run on probe tasks
  built from calibration images, one correction class at a time.
  - A class counts as NOT_FOUND_WITHIN_BUDGET when the package's own search found no fitting program in at least half
    of the probes.
  - Operators of such classes were candidates if the class's oracle gain was at least 0.005. A candidate was admitted
    only if it raised validation F1 on separate calibration parents, improved more of those parents than it worsened,
    and was not an alias.
- **Acceptance rule.** B3-inspired selective verification with metric-consistent fits. It is not exact reproduction
  of the demonstrations:
  - fitting programs harm no demonstration parent and reach 0.9 of the best pooled gain;
  - leave-one-parent-out top programs must harm no held-out parent;
  - every fitting program and fold top must agree on an edit;
  - a reversed-order restart must give the same answer.
  Programs whose selections conflict under the executor's rule are invalid. Decisive programs were certified by exact
  execution, and accepted == applied == logged.
- **Transfer.** The grammar and policy induced on A were frozen. They were applied to B and C with only those
  datasets' calibration parents as demonstrations.

## Why this design (and what it changed relative to earlier studies)

The earlier grammar-induction studies (single-cell, a private image study, BBBC039) accepted no production, and U5 was built to avoid
their causes:
- **Productions added nothing.** Earlier productions were inlined compositions of existing primitives. U5's operators
  are new primitives with new effect classes, each from the literature, plus an alias check.
- **The penalty was too high.** Earlier, a fixed growth penalty demanded 4 to 6% of the residual. U5 admits an operator
  by its measured oracle gain and a paired validation on separate calibration parents.
- **Proposals were malformed.** Earlier language-model proposals were ill-typed. U5 enumerates typed programs, and its
  neural interface is schema-checked.
- **Compute was unmatched.** U5 charges the work of every arm. Its matched search gets CORA's measured CPU, and its
  controls get CORA's candidate ceiling.
- **There was no headroom.** U5 applies a calibration gate per dataset.
- **Deletion gains were trivial.** The earlier StarDist repair's gain came from a dim-object deletion that every order
  found. U5's start already includes the best single-feature deletion filter, and deletion edits are aliases by rule.

The independent blind review then found that the first scoring summed isolated edit effects that the executor would
drop when write sets collided. Amendment 3 made programs with colliding selections invalid, certified decisive
programs by exact execution, and asserted accepted == applied == logged. Amendment 5 extended this to the matched
search and to the claim gates.

## Data, parents and baselines

| dataset | role | modality | licence | parents (calibration / evaluation) | images (calibration / evaluation) | baseline | calibration gate |
|---|---|---|---|---|---|---|---|
| LIVECell (Edlund et al. 2021), all three official subsets | A (induction) | phase contrast, 8 cell lines | CC BY-NC 4.0 | 31 wells (cell line, well): 12 / 19 | 276 / 288; 149 dropped by the leak-free rule | Cellpose 3.1.1.2 cyto2; tuned flow 0.6, cell-probability -2 | PASS: error share 0.276, F1 0.609, oracle gain 0.272 |
| NuInsSeg (Mahbod et al. 2024) | B (transfer) | H&E nuclei, 31 organs | CC BY 4.0 | 31 organs: 12 / 19 | 236 / 429 | StarDist 2D_versatile_he; tuned prob 0.456, nms 0.3; strong native: delete contact >= 3 | PASS: 0.392, 0.503, 0.289 |
| MoNuSAC 2020 (Verma et al. 2021) | C (transfer) | H&E nuclei, TCGA, 4 organs | CC BY-NC-SA 4.0 | 67 TCGA patients (69 unique, 2 MoNuSeg-training patients excluded): 27 / 40 | 132 / 169 | StarDist 2D_versatile_he; strong native: delete area < 183 px | PASS: 0.266, 0.687, 0.116 |
| FluoEcoli-Instance | ineligible | fluorescence bacteria | CC BY 4.0 | names encode no source image | | | |
| FNC v2 green | ineligible | fluorescence neurons | CC BY 4.0 | 22 animals, fewer than 10 + 15 | | | |

**Private data:**
- A private image cohort: NOT OPENED. Its records describe unprocessed camera originals with no reference annotations, so no edit could be
  scored. It stays untouched.
- Protected third-party data: STOPPED. The written third-party terms are "NOT_CONFIRMED ... treat as prohibited" (the data's provider), and
  the data have no human reference.
- The author's own lesion-phenotyping data: used, on the author's explicit approval, as an extra private target
  (Amendment 8), under a private addendum outside git. Its results are reported to the coordinator only.

## Failure records (the frozen cast_selective_v2 on calibration probes; 15 CPU-s per task)

| dataset | SPLIT | MERGE | FILL | GROW | SHRINK | DELETE | ADD |
|---|---|---|---|---|---|---|---|
| LIVECell (no fit / resolved) | 40/40 | 40/40 | no instances | 40/40 | 40/40 | 40/40 | 40/40 |
| NuInsSeg | 40/40 | 22/22 | none | 26/26 | 21/21 | 32/40 | 40/40 |
| MoNuSAC | 6/6 | 6/6 | none | 6/6 | 9/9 | 21/40 | 40/40 |

Every probed class is NOT_FOUND_WITHIN_BUDGET on all three datasets. The frozen package's search found no program that
reproduces these corrections in its window encoding: B3 accepted none of the LIVECell probes; on NuInsSeg 8 DELETE
queries were accepted, 6 of them correct.

## Deviations (all before any evaluation outcome unless stated)

- Nine dated amendments, each frozen by hash:
  - Amendment 1: LIVECell pool.
  - Amendment 2: FluoEcoli ineligible and FNC backup; SPLIT for matched merges; h-maxima; ALL_ON objective; compute
    accounting.
  - Amendment 3: conflict-aware scoring; wording; independent units with the leak-free drop; FNC ineligible; equal-work
    controls; claim family.
  - Amendment 4: MoNuSAC as a pre-registered third target.
  - Amendment 5: matched-search ranking and work counts; transfer labels; executable gates; certification of the neural
    arm; MoNuSAC wording.
  - Amendment 6: a serialization fault in the LIVECell induction (re-run from the start; no rule changed); a race in
    the MoNuSAC chain; primary arms decided and scored before the secondary arms; evaluation segmentation in parallel.
  - Amendment 7: an underworked MATCHED_SEARCH downgrades the label before the transfer block; an in-step budget stop
    is "budget reached"; factor-of-two decisions on unrounded CPU or the worst rounding case.
  - Amendment 8, after the empty LIVECell grammar was observed: the CORA_TOLERANT secondary arm; an alias-check fix
    for add_lowthresh edits; the private target.
  - Amendment 9: a 0.30 s legacy CPU slack covering the probe-child roundings; renamed CPU fields; an acceptance
    waterfall diagnostic.
- After amendments 1 to 3, calibration-side work was recomputed from scratch. Only deterministic network outputs were
  reused.
- **Status line.** LIVECell's calibration segmentation finished correctly (exact recompute 276/276). Its chain then
  logged EXIT 1, because `seg_chain.sh` was edited while it ran. A corrective status line was appended after checking
  the outputs. Rule adopted: no edits to running scripts.
- **Re-runs.** The NuInsSeg probes were re-run after their folder was moved; the task file was identical (sha256
  f4c34bb9). The evaluation chain was restarted twice while waiting, never after any evaluation step.

## Limits

- **Modality.** MoNuSAC is H&E, as is NuInsSeg. Transfer to C tests a new histology source, not a new modality.
- **NuInsSeg parents** are organs, which may share donors (the 8 mouse organs probably share animals). The archive does
  not encode donors.
- **LIVECell.** Wells are parents, and 149 images were dropped by the leak-free rule. Cell lines are the coarser
  sensitivity clustering (8 groups).
- **The acceptance rule** is a B3-inspired re-implementation over object programs, not the frozen package. It does not
  reproduce demonstrations exactly.
- **Probes** are bounded searches (15 CPU-s, U1's window encoding). NOT_FOUND_WITHIN_BUDGET is not inexpressibility.
- **Transfer** uses the targets' calibration demonstrations: it is vocabulary transfer with target adaptation, not
  zero-shot program transfer. PROGRAM_TRANSFER is the zero-shot diagnostic.
- **Baseline training data:**
  - cyto2 and LIVECell: no documented overlap found, but no item-level manifest exists.
  - StarDist HE: MoNuSeg-training patients were removed from MoNuSAC.
- **Pools.** Both public pools are re-partitioned by parent. These are not official benchmark scores.
- **Work equality.** It is operationalized as equal candidate counts plus CPU bounds for the controls, and as the
  CPU-or-full-schedule rule for MATCHED_SEARCH. That is the frozen criterion, not a proof of equal search difficulty.
  The controls' CPU is lowered by unit-table reuse in the same process.
- **CORA_TOLERANT.** It was designed after the empty LIVECell grammar was seen, before any evaluation outcome. It is
  calibration-informed and secondary.
- **Private target.** It is specified in a private addendum outside git. Its results are reported to the coordinator
  only and appear nowhere in git or the public release.

## Reproduction

All commands run from `experiments/universality_bio_grammar_20261103/` with the project's Python environment
(`python -I`). Heavy steps take a shared CPU slot through `scripts/with_cpu_slot.sh`.

1. Data: `scripts/u5data.py` downloads, checks licence and checksum records (`DATA_MANIFEST_*.json`), and builds
   parent-level splits with the leak-free drop rule.
2. Segmentation: `scripts/seg_chain.sh DS cal|eval` (Cellpose 3.1.1.2 cyto2 for LIVECell, StarDist 0.9.2
   2D_versatile_he for NuInsSeg and MoNuSAC; CPU).
3. Calibration: `scripts/cal_chain.sh` (strong native rule, gate, probes of the frozen `cast_selective_v2`, roles,
   induction on A with the controls, policy freeze) and `scripts/monusac_chain.sh`.
4. Evaluation: `scripts/eval_chain.sh` (waits for the freeze and for the go flag; evaluation segmentation, strong
   native, decisions frozen by hash in `DECISIONS_FROZEN.json` before the evaluator opens, scoring).
5. Checks: `python -I scripts/verify_code.py` (exact code freeze), `python -I -m pytest tests/test_u5.py` (27 tests).

Every decision file is hashed before any evaluation reference is decoded; `u5eval.evaluate` re-checks each hash
before scoring.
