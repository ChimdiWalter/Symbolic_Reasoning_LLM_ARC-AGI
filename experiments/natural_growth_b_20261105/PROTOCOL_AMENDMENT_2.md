# Protocol amendment 2 (6 Nov 2026): the object-level growth arms, from the builder's frozen code

Made before any held task, held test output or phase 2 run; no GO was written. Amendment 1 stands; this amendment
adds to it. The version 2 freeze is superseded by version 3 (`FREEZE.json`), which fills the object-growth slot.

## A. The builder's freeze and the contract (PROTOCOL.md section 5, filled)

- **The builder's code** (`experiments/object_growth_20261105/`) is frozen. Its first freeze (`FREEZE.json` sha256
  `7b80302ef502acd795664d39a79781d6a3cdbb9e87a3ad8d4d8f59f630fd3de3`, commit 69fb8415) is superseded by its version-2
  freeze, a documentation-only contract amendment with the code unchanged (`FREEZE_V2.json` sha256
  `f6218c3eaca22e808870e8542eba48b82e74f0563f37cdbedc05097b1cefbd9e`, 115 files, commit d5ac3f1d;
  `CONTRACT_AMENDMENT_1.md` sha256 `d6181a1e682d0f1d29bb003d551193c5b635eaf6ababcb1359ee62f83251462a`; the
  registries' and `objgrow/arm.py`'s digests are unchanged); the version-2
  digest fills `object_growth.code_sha256` of this study's freeze, and the first freeze's digest is recorded beside
  it. The files the arms execute or read are pinned individually by the digests the builder's freeze records,
  verified against the files on disk: every module of `objgrow/`, the three registries
  `runs/v2/<benchmark>/registry.json` (ConceptARC 2 operations, Mini-ARC 0, 1D-ARC 19), the funnel
  `runs/v2/FUNNEL.json`, the reuse records `runs/v2/<benchmark>/reuse.json`, the development report `REPORT_DEV.md`,
  the contract amendment and the builder's freeze file itself. This study read that tree only after the coordinator
  announced the freeze.
- **The contract** (`config/STUDY_CONFIG.json` "object_growth"; `ngb/object_arm.py`): module `objgrow.arm`;
  `ops_from_registry(registry document)` gives the operations; `reuse_answers(task, ops, g0b)` gives G0 plus the
  operations under the base search (two attempts) with its process CPU; `construction_answers(task, ops, g0b)`
  gives the base search with G0 plus the operations and, on a failure, the controller's typed holes from the task's
  own demonstrations, the builder's object-level constructor and the retry of at most three candidates that are
  exact on every demonstration and multi-pair (the edit bound in at least two demonstration pairs; colour tables
  and whole-output forms labelled by construction), with its process CPU. Neither function sees a test output. Every call passes this study's
  seed-independent grammar builder (amendment 1, section C). A registry is loaded only if its digest is the frozen
  one.
- **Cost charged to the object arms,** per benchmark and Athe-measured, scaled by the kernel's speed factor: study
  A's controller CPU on every source task (the holes come from it: ConceptARC 540, Mini-ARC 247, 1D-ARC 797 CPU-s)
  plus the builder's recorded construction, gate and combined-check CPU for the registry (ConceptARC 159 + 5,917
  + 2, Mini-ARC 98 + 1,064 + 0, 1D-ARC 536 + 8,777 + 0 CPU-s): about 6,617, 1,409 and 10,110 CPU-s.

## B. Arms (PROTOCOL.md section 6, extended)

| arm | code label | search on each held task |
|---|---|---|
| 5 | obj | the builder's reuse answers: G0 plus the benchmark's frozen object registry (own holes), base search |
| 6 | obj_shuf | the same with the shuffled object registry: the first R(b) operations of the other benchmarks' registries in sha256("obj-shuffle:" + b + "|" + operation id) order (ConceptARC wants 2 of 19 available; 1D-ARC wants 19 of 2 available, shortfall 17; Mini-ARC wants 0) |
| 7 | construct | the builder's construction answers on the task's own demonstrations: G0 plus the registry, then the holes, the constructor and at most three retries; never a test output |
| 8 | construct_shuf | the same on donor demonstrations: the task's test inputs with the demonstrations of the next held task in sha256("obj-donor:" + id) order from another family (Mini-ARC: the next task); the control for arm 7 |
| 4b | static_obj | G0, no execution limit, CPU cap T(b, obj) per task |
| 4c | static_construct | G0, no execution limit, CPU cap T(b, construct) per task |

- Arm 8 with no held task of another family in the benchmark (impossible on the real held halves; it happens in a
  two-task dry run) gives a durable "no_donor" failure row.
- The builder did not produce a registry grown with shuffled holes, so arm 6 is the registry-shuffle control
  (operations grown from the other benchmarks' failures, same count), stated as such; the shuffled-holes control at
  the task level is arm 8.
- T(b, arm) as in amendment 1: the arm's source-half cost (section A) plus its CPU on the held half of b, per held
  task. With the object costs these allowances are large (about 80, 19 and 33 CPU-s per held task for ConceptARC,
  Mini-ARC and 1D-ARC for arm 4b, plus the reuse search; arm 4c adds the construction CPU): matched static search
  gets 20 to 60 times the base search's CPU.
- The ARC-AGI-2 check (section 8) gains the arms obj (reuse with the union of the three registries, 21 operations),
  construct (construction with that union), static_obj and static_construct at the pooled allowances.

## C. Analysis (PROTOCOL.md section 7, applied)

- **Primary: arm 5 vs arm 4b** (the pre-registered rule: the builder reported promoted operations on ConceptARC and
  1D-ARC before 6 Nov 12:00Z). The coordinator writes "primary arm5_vs_arm4" on the GO's third line; the gate refuses
  that line while the object slot is empty.
- **Secondaries, Holm-adjusted together:** S0 arm 2 vs arm 1; S1 arm 2 vs arm 4a; S2 arm 2 vs arm 3; S3 arm 5 vs
  arm 6; S4 wrong answers arm 2 vs arm 4a; S5a to S5c arm 2 vs arm 1 per benchmark; S6 ARC-AGI-2 library vs matched
  static; S7 ARC-AGI-2 reuse vs matched static; **S8 arm 7 vs arm 4c; S9 arm 7 vs arm 8; S10 ARC-AGI-2 construction
  vs matched static.** Descriptive: arms 5 to 8 and the static arms against G0, arm 7 vs arm 5, by family, the
  localisable stratum.

## D. The honest expectation and power (from the builder's source-half records; `power/POWER_OBJECT.json`)

**Reuse (arm 5 vs arm 1), by family.** The builder's out-of-sample newly-correct rate on the source half (source
tasks that were neither the motivating nor the validating task of a promoted operation) times the held family size.
1D-ARC, measured: hollow 15 of 15 (24 held), move_2p 6 of 6 (25), move_3p 1 of 1 (25), scale_dp 10 of 10 (26),
mirror 2 of 20 (23; about 2.3), recolor_cnt 1 of 18 (20; about 1.1), recolor_cmp 0 of 9 (20; its operations are
colour-specific), padded_fill 0 of 1 (4), flip 0 of 22 (22): about 103 of 210 held tasks in the measured families.
**Four 1D-ARC families have no out-of-sample estimate** (fill, move_1p, move_2p_dp, move_dp: one operation fits every
source task of the family, so every source task was a motivating or validating task): 99 held tasks whose gain is
unmeasured and plausibly near complete. ConceptARC: the two TopBottom2D operations fit no other source task
(0 of 2 out-of-sample): about 0 to 2 of 80. Mini-ARC: 0 of 75 (empty registry). So arm 5 is expected to add about
100 (measured families alone) to 200 (if the four unmeasured families transfer) correct tasks of 464, against 0 for
G0 at the base budget, almost all on 1D-ARC.

**Reuse against matched static search (arm 5 vs arm 4b), the primary.** Matched static search gets the object
allowance (section B), 20 to 60 times the base search's CPU. What that buys on these tasks is unknown: the 4x search
found 23 1D-ARC and 4 ConceptARC source solutions; the builder's report says deeper search already solves some
1D-ARC families. Two scenarios are simulated: static gains equal to the 4x search's (a lower bound: arm 5 ahead by
about 80 to 180 tasks, "arm 5 beats arm 4b" nearly certain) and static re-solving the same families as reuse does (a
tie or inconclusive). The honest expectation is between them: a large gain of reuse over G0, concentrated in 1D-ARC
families whose source tasks share one operation, and an open contest against a static search given fifty times the
base CPU; the by-family table will show which families carry it.

**Construction (arm 7).** The builder's source-half recovery rates (units recovered with every test output correct
over construction units; the retried candidates are exact on every demonstration and multi-pair), already net of
over-fitting: 1D-ARC 246 of 283 (fill 24 of 24, hollow 24 of 24, move_dp 25
of 25, move_2p_dp 25 of 25, move_1p 22 of 25, move_2p 22 of 25, move_3p 21 of 25, scale_dp 21 of 25, recolor_cmp 18
of 18, recolor_cnt 20 of 20, recolor_oe 13 of 21, mirror 9 of 23, padded_fill 2 of 3), ConceptARC 15 of 74 (about
20% of the failures), Mini-ARC 6 of 68 (about 9%): about 270 of 309 on 1D-ARC, about 15 of 80 on ConceptARC and
about 7 of 75 on Mini-ARC. Against arm 8 (donor demonstrations) the expectation is a clear win (a construction from
the wrong demonstrations rarely predicts the right output). Against arm 4c the same openness as for the primary.

**What the contract amendment changes in this expectation.** Nothing in the counts: the reuse estimate rests on
out-of-sample source tasks and the construction estimate on measured recoveries (fit and correct test output), not on
the label. Two readings change. The multi-pair label is weaker than a leave-one-out check, so the over-fitting already
seen on the source half (ConceptARC 10 of 23 fitting units and Mini-ARC 3 of 9 mispredicted the test) is the
expected rate on the held half too, with colour-table candidates (321 of 835 gated on 1D-ARC) the likeliest to
over-fit; and the small regression sets mean that a grown grammar could lose a held task G0 solves without any gate
noticing, a loss the paired comparison counts against the growth arm.

**ARC-AGI-2 check.** About zero for reuse (the 21 operations are shaped by 1D rows and two ConceptARC concepts);
0 to 3 of 120 tasks for construction (the builder recovered 4 of 76 G0 failures on easier ARC training tasks). A zero
is reported as a zero.

**Simulated decisions** (`power/POWER_OBJECT.json`, Poisson draws per family, the pre-registered test and clustered
interval): reuse vs G0 "arm 5 beats arm 1" in 100%; reuse vs matched static with static gains at the 4x search's level "inconclusive" in 99.7% (the clustered interval reaches 0 because the gain sits in a few 1D-ARC families); with static re-solving the same families, a tie in 100%; construction vs G0 "arm 7 beats arm 1" in 100%. Expected held tasks: reuse newly correct about 103 in the measured families plus an unmeasured 0 to 99 in the four families without an out-of-sample estimate; construction about 273; the 4x search about 27.

## E. The two reviews of version 2 and how each finding is resolved

**Our independent pre-run review** (`reviews/INDEPENDENT_PRE_RUN_REVIEW_V2.md`, PASS WITH FIXES):

| finding | resolution |
|---|---|
| 1 (structural): version 2 cannot carry an arm-5 GO; freeze the registries and their digests; check the contract; dry-run the object arms | the slot is filled (section A); `feasibility/object_registries.json` freezes, per benchmark and arm, the operations and the digest every row must carry (library, shuffled library, registry, shuffled registry, the ARC-AGI-2 unions, the G0 digest), and the report checks each row against it; the builder's operations take no parameter (`ObjOp.param` false, `thetas()` empty), so the integer-parameter rule of `ngb/ops.py` does not apply to them and their productions are the builder's own (`objgrow.gates.ObjPlugin`); the dry run ran arms 5 to 8 and the three static arms with the real registries (section F) |
| 2 (medium): the Holm family shrank when a test could not be computed | the family is the fixed list of thirteen secondaries (`ngb/report.py` SECONDARIES); every one is always computed; a test whose arms are both G0 copies is an exact tie inside the family; the report refuses to score unless every arm of the design has complete rows |
| 3 (medium): the speed factor measured alone, stages run under concurrency | `ngb/phase2.py` runs the benchmark as WORKERS copies at once (median over copies of their medians) and runs every stage at most WORKERS processes at a time (commands chunked) |
| 4 (low): a second report run refused by its own outputs | RESULTS.json and REPORT.md are excepted from the unlisted-file check |
| 5 (low): the two-attempt contract unchecked | a row with more than two attempts, an attempt with the wrong number of grids, an invalid grid, or attempts without a fit (or a fit without attempts) is INVALID before any solution opens |
| 6 (low): the pooled ARC-AGI-2 allowance not rescaled to kernel C | `ngb/arc2.py` re-expresses each benchmark's allowance in kernel C's CPU-seconds from the recorded factors (source cost unscaled then rescaled; held CPU scaled by the ratio of factors) |
| 7 (low): the incident's residue | the incident record pins `logs/dry.log` by sha256 and line counts (140 lines, 95 evaluation-task lines), kept unread and undeleted |

**The companion study's second review** (outbox note 0477, HOLD):

| blocker | resolution |
|---|---|
| 1: the archive omitted FREEZE.json, which the packaged gate loads, and `ngb/library.py`, which `held.library_ops` imports | FREEZE.json is an archive member (bound by the GO, which names its digest). The kernel no longer imports `ngb/library.py` (a phase 1 stage that needs study A's Athe-only `grow.py`): the loader of the frozen library operations moved to `ngb/ops.py`. The package check now extracts the archive into a scratch folder and runs a package-mode smoke test (`ngb/package_smoke.py`): it imports the kernel's modules, exercises every arm's registry loading and grammar for every benchmark (the inference closure, not just imports), runs the freeze check and the refusal without a GO, checks the sorted-tag grammar, the library and registry binding and every loaded module's provenance inside the package, and sweeps for any solution file. Its first run on the draft freeze caught exactly this gap (`ngb.library` failed to import in package mode), which is how the fix was found. |
| 2: reject more than two attempts and invalid shapes or fit inconsistency before any solution access | as finding 5 above; a synthetic six-task run with a third attempt is INVALID, not a win |
| 3: require arm 4b before solutions when arm 5 is the primary | every arm of the design is required: a missing arm 4b (or any arm) is INCOMPLETE before any solution opens; the report takes both run folders and refuses without the ARC-AGI-2 one |
| 4: retain the pre-registered Holm family, including ties; an omitted ARC-AGI-2 folder must not give a complete report | as finding 2 above; the ARC-AGI-2 folder is mandatory |
| also: the held loader's GO check before the combined-file read | `ngb/score.py` asks the gate before reading the file when any held id is requested |
| also: task-level child or exception CPU, not null | a failure row is charged the CPU this process spent on the task and says whether the child's own CPU is unknown |
| also: registry, G0, shuffle and ARC-AGI-2 provenance and resume checks | each row's registry digest, G0 digest and library digests are checked against the frozen record; ARC-AGI-2 rows against the frozen union digests and the three library digests; STAGES.json keeps every attempt and must belong to this GO and primary |
| also: an explicit exclusive execution and scoring claim | scoring is exclusive: the report writes `runs/SCORED_<GO digest>` and refuses a second scoring under the same GO; one kernel per benchmark group, one scoring, stated here |

Admission tests cover each of these (`checks/ADMISSION_TESTS.json`, section F).

**Wording corrections (the companion study's review of the object step, its note 0480, and the builder's contract
amendment 1; code unchanged):**
- The builder's candidate criterion is a multi-pair proposal criterion, not a leave-one-out test: a candidate reaches
  the gates when it is **exact on every demonstration and multi-pair**, that is, its edit is bound in at least two
  demonstration pairs (for a two-rule candidate, each edit; colour tables count a pair with any constant recolouring,
  and whole-output forms are labelled by construction). No candidate is ever rebuilt with a pair withheld. The
  builder's field keeps the name "loo". This wording replaces "leave-one-out" wherever this study describes the
  object step (this amendment, `ngb/object_arm.py`, `ngb/power_object.py`).
- The regression gate (the shared core's, used by this study's library and by the builder) accepts the old first
  prediction anywhere among the two attempts: a candidate is **rolled back when a task of U loses its fit, or when
  its old first prediction is no longer among the two attempts**. This replaces "a lost fit or a changed first
  prediction" in PROTOCOL.md sections 3.3 and 4 (and the combined check's wording there); `ngb/library.py` is
  corrected to match. The behaviour, and every frozen record, is unchanged.
- PROTOCOL.md's section 11 table says "the leave-one-out library": that is the leave-one-source-out estimate (the
  library rebuilt without the task's own contribution), unrelated to the builder's criterion.
- **The builder's regression sets are small:** ConceptARC 1 task, Mini-ARC 6, 1D-ARC 0. On 1D-ARC the check is
  vacuous (G0 solves no 1D-ARC source task at the base budget), so its "no roll-back" carries no information; this
  study's own library regression on 1D-ARC is equally vacuous (U is empty there). Losses of G0's own held answers
  under a grown grammar are therefore guarded only weakly and would show as discordant tasks favouring G0; the
  builder's source-half reuse records show none (no lost fit on any benchmark).
- **Budget accounting:** A2's search checks its execution budget once before each vector evaluation (one candidate
  program on all n inputs of a task) and charges every input; an object operation is one execution (charge 1) whatever
  its internal work, so the last evaluation can exceed the budget by up to n x charge - 1 executions and the work
  inside a macro call is not charged. Every arm uses the same search, so the overshoot is the same rule for all; the
  object arms' internal work is real CPU, which is why the static controls are matched on CPU (as designed). The rows
  record CPU per task; arm 7 and 8 rows also record the constructor's internal counters (segmentations, edit and
  operation applications); the frozen reuse function does not expose its macro-call count, so arm 5 and 6 rows record
  CPU and the program only.

## F. Checks (this amendment)

- **Admission tests** (`checks/ADMISSION_TESTS.json`, synthetic inputs only; eleven tests, all pass): the gate
  (arm 5 refused while the slot is empty, a wrong freeze digest refused); the source-only decoder (the held entry
  never decoded, a duplicated key refused); the Holm decision (raw p 0.03125, Holm p 0.1875, "inconclusive"); a
  duplicate row INVALID and a missing row INCOMPLETE; a run with a missing row exits 2 without the solution loader
  being called; static-child time-out and failure rows; the object contract (registry bound by digest, a changed copy
  refused, the donor from another family, a construction call that sees demonstrations and test inputs only); row
  validation (three attempts, a wrong number of grids, an invalid grid, attempts without a fit, a registry or G0
  digest other than the frozen one: each INVALID; a correct row passes); a run missing the ARC-AGI-2 rows and arm 4b
  is INCOMPLETE and nothing is scored; a second scoring under the same GO is refused; a held-id request asks the gate
  before the solution file is read.
- **Dry run v7** (`checks/dry_run_v7/`, on the final code; runs v4 to v6 were the same procedure on intermediate
  code while the fixes went in; two source tasks per benchmark standing in for the held half, two source stand-ins
  for the ARC-AGI-2 set, asserted before any arm runs): all ten held arms, with the real object registries
  for arms 5 to 8, the three static arms in child processes, the seven ARC-AGI-2 arms, STAGES.json and
  OUTPUT_MANIFEST.json, and the report with its manifest, identity, completeness, provenance (frozen registry, G0 and
  library digests) and attempt checks: exit code 0; Holm family of thirteen; arm 7 rows carry the constructor's
  internal counters. Arm 8 gave four "no_donor" rows in the stand-in (its ConceptARC and 1D-ARC stand-ins come from
  one family each), as the rule says; its numbers mean nothing.
- **Seed check with construction probes** (`checks/SEED_CHECK.json`): PASS. The three search probes are identical across hash seeds 0, 1 and 2 under the sorted builder (the plain builder again differs in program text and execution count, with fits and predictions equal). The three construction probes (arm 7's call with the frozen registries: ConceptARC co0003 and 1D-ARC 1d0143 reach and fit by construction, Mini-ARC mi0002 runs the constructor without a fitting retry) give identical fit, stage, constructed operation, predictions and candidate counts across the seeds, so the builder's construction is seed-independent on these probes as well.
- **Package check** (`ngb/kaggle_build.py check`, `checks/PACKAGE_CHECK.json`, run against the version 3 freeze and
  reported in PROGRESS.md; not frozen because it checks the freeze itself): every required file present with its
  frozen digest, FREEZE.json and `ngb/library.py` in the archive, and the extracted package passing the package-mode
  smoke test (import closure, freeze check, refusal without a GO, sorted-tag grammar, library and registry binding,
  module provenance inside the package, no solution file).

**A correction to PROTOCOL.md's feasibility table** (section 10): Mini-ARC's library construction CPU is 0.8 CPU-s,
not 7, and its whole source-half cost 298 CPU-s, not 304 (`feasibility/library/mini_arc/library.json`); the code
always used the record.

## G. Compute

Arms 7 and 8 cost up to a base search plus construction and three retries per held task (the builder's source-half
construction ran at about 2 to 8 CPU-s per unit); the three static arms cost their allowances, which equal the
matched arms' whole costs: about 2,000 (library), 18,500 (object reuse) and 19,000 (construction) CPU-s over the 464
held tasks, plus the ARC-AGI-2 arms at the pooled allowances (about 120 x 40 CPU-s each for the object arms). The
whole of phase 2 is about 20 CPU-h over the three kernels (1D-ARC's kernel the largest, about 10 CPU-h), under the
30 CPU-h ceiling per kernel; with four workers and stages capped at four processes, kernels A and B are expected to
take 3 to 5 hours of wall time. A static child at an allowance of 30 to 80 CPU-s may approach its 12 GB address-space
limit; a child that hits it gives a durable failure row (no answer), which counts against arm 4 in the comparisons.

## H. Change log

- `config/STUDY_CONFIG.json`: the object-growth contract filled; arms 7, 8 and 4c; the ARC-AGI-2 arms.
- `ngb/object_arm.py`: the contract adapter (registry binding, shuffled registry, union, donor rule, source cost).
- `ngb/held.py`, `ngb/arc2.py`, `ngb/phase2.py`, `ngb/report.py`, `ngb/dry_run.py`, `ngb/admission_tests.py`,
  `ngb/kaggle_build.py` (the builder's environment in the kernel), `ngb/freeze.py` (the slot from the builder's
  freeze), new `ngb/power_object.py`.
- After the two reviews of version 2: `ngb/report.py` (fixed Holm family, every arm and both run folders required,
  frozen provenance per row, attempt and grid validation, own outputs excepted, exclusive scoring),
  `ngb/score.py` (gate before the held read), `ngb/held.py` and `ngb/arc2.py` (failure-row CPU, no-donor rows, pooled
  allowance rescaled), `ngb/phase2.py` and new `ngb/bench_probe.py` (concurrent speed benchmark, chunked stages),
  `ngb/kaggle_build.py` and new `ngb/package_smoke.py` (FREEZE.json in the archive, extracted smoke test),
  `ngb/freeze.py` (library.py packaged; the frozen registry record), new `ngb/object_registries.py` and
  `feasibility/object_registries.json`, `ngb/seed_check.py` (construction probes), `ngb/admission_tests.py`,
  `records/INCIDENT_20261105_DRY_RUN.md` (the unread log pinned).
- `FREEZE.json` version 3; its digest is reported in PROGRESS.md and the coordinator's record (a file cannot carry
  its own digest); the GO must name it.
