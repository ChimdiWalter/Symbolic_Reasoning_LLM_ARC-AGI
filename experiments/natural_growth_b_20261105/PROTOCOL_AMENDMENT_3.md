# Protocol amendment 3 (6 Nov 2026): the corrections after the independent re-review of version 3 (HOLD)

Made before any held task, held test output or phase 2 run; no GO was written. Amendments 1 and 2 stand; this
amendment adds to them, and where they differ it applies. Version 3 is kept byte-identical as `FREEZE_V3.json`
(`a06af3fc6826ff68f1362962b8cd08d79872396d6d95bf333080bb5781517a76`), version 2 as `FREEZE_V2.json`
(`37c36cb032a29369dd944c80a097d0d15112d360258f7a7a3d54bde0a0493828`, recovered byte for byte from commit 9ed05245)
and version 1 as `FREEZE_V1.json`. The new freeze is version 4 (`FREEZE.json`). The review is
`reviews/INDEPENDENT_PRE_RUN_REVIEW_V3.md` (commit 12b48a5a).

## A. The blocker: the matched allowance of arm 4b could not be computed in a kernel

- **What was wrong.** `ngb/object_arm.py` summed study A's controller CPU from study A's two controller record files,
  which were neither frozen nor packaged. In a kernel every object and construction cost would have raised, outside
  the per-task handling, so kernels A and B would have failed at the arm 4b stage after the other arms had run on the
  held halves.
- **Correction.** The three controller-CPU totals were computed once on Athe from study A's records (ConceptARC
  539.458, Mini-ARC 247.153, 1D-ARC 796.694 CPU-s; the records' digests are kept with them) and frozen with the
  builder's recorded registry costs in a packaged record, `feasibility/object_costs.json` (`ngb/object_costs.py`).
  The arms' source costs are ConceptARC 6,617.248, Mini-ARC 1,408.857 and 1D-ARC 10,109.178 CPU-s. `ngb/object_arm.py`
  reads only that record, bound by digest to the freeze and to the registry it was made from. Study A's records are
  frozen too, Athe-only.
- **The smoke test now covers it.** Inside the extracted package, `ngb/package_smoke.py` computes every input of
  every static allowance (the matched arms' source costs for every benchmark) and calls the builder's reuse and
  construction functions on one source task per benchmark.

## B. A full rehearsal of the real kernel path is mandatory before the GO

- **What it is.** The real kernels, built by `ngb/kaggle_build.py rehearsal` from the same frozen code and the same
  archive layout, with three substitutions and nothing else:
  - the benchmark data are the source-half inputs only (`rehearsal/data/`, made from the prepared files: no held
    task, no test output; the gate checks in the kernel that no held task of the real split is present);
  - the ARC-AGI-2 set is a stand-in file of twelve source tasks (`rehearsal/arc2_standin_challenges.json`, four per
    benchmark, demonstrations and test inputs only);
  - the GO is `rehearsal/REHEARSAL_GO` (the same three lines; it authorises only the rehearsal mode), and the kernels
    run with NGB_REHEARSAL=1, under which every caller sees the source half in place of the held half and no held
    output can be opened.
- **What runs.** Private Kaggle CPU kernels, internet off: rehearsal kernels RA (ConceptARC and Mini-ARC) and RB
  (1D-ARC) end to end through every stage (G0, the four grown arms, the two construction arms, the three static arms
  in two shards each, the retry stages), then kernel RC (the ARC-AGI-2 arms on the stand-in set), built only after
  RA's and RB's outputs verify (section F), then the Athe report in rehearsal mode on RA, RB and RC (source outputs
  decoded in place; markers under `checks/kaggle_rehearsal/`).
- **Records.** Logs, stage records, manifests and the report go to `checks/kaggle_rehearsal/`. Any failure is fixed
  before the freeze; the rehearsed code is the frozen code.
- **Rehearsal 1** (candidate freeze `5bf2d3b42dc7e9fe839af5929d2fcea571face479bb9c86efad48ede6e2bb4a1`; record
  `checks/kaggle_rehearsal/REHEARSAL_1.md` and `REHEARSAL_1_RECORD.json`). RA, RB and RC ran to completion on 4-CPU
  Kaggle machines (4.8, 4.7 and 0.6 h): every stage done with return code 0, one row per task in every arm, no
  "arm_error", "no_donor" or killed-child row (the retry stages had nothing to retry), every output manifest and stage
  record verified under the rehearsal GO, every task id a source-half id, no traceback in any log, and RC's copies of
  RA's and RB's held rows equal to the originals. Kaggle's G0 rows repeat Athe's G0 searches of the same 460 tasks
  exactly (fit, stop, level reached and program; call counts within 3 at the budget edge).
- **What rehearsal 1 found, fixed before the freeze: the speed factor overstated the kernels' slowdown.** The factor
  is measured with one benchmark copy per worker at once (four), while since section E the static children run two at
  a time in kernels A and B and one at a time in kernel C. On the same machines four copies ran about 1.7 to 2 times
  slower per copy than the stages that ran one or two processes: RA measured 2.199 (applied 2.0, the pre-registered
  clip), RB 1.446 and RC 2.138 (applied 2.0), while the G0 searches used 1.10 (ConceptARC), 1.14 (Mini-ARC) and 0.82
  (1D-ARC) times Athe's CPU for the same tasks, and the static children searched at the G0 stage's rate (0.88 to 1.06
  of its executions per CPU-second). The static allowances thus bought about 1.7 to 1.8 times the matched work (for
  ConceptARC's object-matched static search, 169 CPU-s per task where about 95 matches). **Correction:** each kernel
  runs as many workers as its static children run at once, two in kernels A and B and one in kernel C
  (`ngb/kaggle_build.py`, the notebook's argument to `run.py phase2`; this supersedes the four workers of PROTOCOL.md
  section 12). The factor is then measured with two benchmark copies (one in C), and every stage whose CPU enters a
  static allowance (the grown and construction arms' held searches) runs at most two processes at once. The clip
  [0.5, 2] stays; each kernel's STAGES.json records the measured benchmark and the applied factor, and a clipped factor
  is stated with the results. No packaged file changed.
- **Also from rehearsal 1:** the Athe report could not run under its candidate freeze, because three Athe-side files
  frozen in it (the final admission tests, the power record and this amendment's expectation text) had been rewritten
  after it, and the gate refuses any changed frozen file. Rehearsal 2's candidate freeze was written after every
  record was final.
- **Rehearsal 2** (the corrected notebooks): {{REHEARSAL_2}}

## C. The honest expectation for the primary, corrected

Amendment 2's sentence "arm 5 ahead by about 80 to 180 tasks, 'arm 5 beats arm 4b' nearly certain" is withdrawn; it
contradicted its own simulation. What the record supports (`power/POWER_OBJECT.json`, now with both scenarios):

- **The measured families alone** (about 103 held tasks newly correct under reuse; four 1D-ARC families carry the gain):
  against a matched static search that gains what the 4x search gained (27 tasks, 22 of them in 1d_flip, a family
  reuse does not solve), the pre-registered primary is expected to be **inconclusive** even at an advantage of about 80
  tasks, because the family-clustered interval crosses zero: resampling the fourteen 1D-ARC families often leaves out
  the four that carry the gain and keeps 1d_flip, which goes the other way. Simulated: "inconclusive" 99.7%,
  "arm 5 beats arm 4b" 0.3%.
- **"Arm 5 beats arm 4b" needs the four families without an out-of-sample estimate to transfer** (fill, move_1p,
  move_2p_dp and move_dp, 99 held tasks): at their source-half rates of correct tasks under the grown grammar (24,
  25, 25 and 25 held tasks) the expected gain is about 202 held tasks, and the simulated decision is "arm 5 beats
  arm 4b" in 100%.
- **If matched static search re-solves the same families** (its allowance is 20 to 60 times the base CPU), the
  primary is a tie (100% in that scenario).
- Against G0 alone, reuse and construction are expected to win in every scenario (simulated 100%).

The by-family table carries the reading in either case.

## D. Code errors are defects, not outcomes

A row whose stop is "arm_error" (an exception while a task was processed) or "no_donor" (impossible on the real held
halves) is INVALID: the report refuses to score the run and lists the rows. The static children's failure rows
(child_timeout, child_failed, child_unreadable, child_error) stay pre-registered no-answer outcomes, counted and
reported; a killed child is handled by section E.

## E. Static children and the kernel's memory

- The three static arms run in **two shards** each (at most two static children at once, each limited to 12 GB of
  address space, on a kernel of about 30 GB), instead of four. Kernels A and B therefore run with two workers and
  kernel C with one (section B, rehearsal 1).
- A child killed by a signal (for example by the kernel's memory) gives a "child_killed" row. After each static stage
  a retry stage runs every such task once more **alone** (one process, one child, no other stage running), and that
  result stands (`<arm>.retry.jsonl`, the original stop recorded). The report replaces the killed row by its retry
  row, treats a killed row without a retry as INCOMPLETE and a retry without a killed original as INVALID, and
  reports the counts per benchmark and arm.

## F. Kernel C and the report use only verified outputs of kernels A and B

- `ngb/kaggle_build.py arc2` (and `rehearsal_arc2`) builds kernel C only after verifying A's and B's
  `OUTPUT_MANIFEST.json` (every digest, no unlisted file) and `STAGES.json` (this GO's digest, this primary, status
  complete), and records their manifest digests in C's package manifest.
- The report now takes the three downloaded folders, `run.py report A_DIR B_DIR C_DIR`. It verifies all three
  (manifest and stage identity), reads the held rows from A (ConceptARC, Mini-ARC) and B (1D-ARC) themselves and the
  ARC-AGI-2 rows from C, and requires C's packaged copies of A's and B's held rows to equal A's and B's files byte for
  byte.

## G. Smaller corrections

- **S4** compares wrong answers (the library's minus matched static search's); its decision is now written as which
  arm makes more wrong answers.
- **Exclusive scoring:** a claim `SCORING_<GO digest>` is written immediately before the first solution file is
  opened, and scoring is refused when the claim or the completion marker exists.
- **Colour tables** (amendment 2 section A, `ngb/object_arm.py`): a colour table counts a demonstration pair when some
  object in it is bound to any constant recolouring; only whole-output forms are flagged unconditionally (section H,
  wording standard).
- **Study A's records** that feed this study's power and cost figures (`feasibility/FEASIBILITY.json` and the two
  controller record files) are in the freeze (Athe-only).

## H. The companion study's qualifications of version 3 (its note 0489, PASS WITH QUALIFICATIONS), kept

1. **Exclusive scoring and one owner.** The claim `SCORING_<GO digest>` is written immediately before the first
   solution file is opened, and the completion marker `SCORED_<GO digest>` at the end; either refuses a later
   scoring. Markers guard only sequential repeats, so execution and scoring are serialised by one owner: the
   coordinator's single session builds and pushes the kernels, downloads their outputs and runs the one scoring;
   no second session or process scores in parallel.
2. **A failed static child's CPU.** The parent now measures every static child's own CPU (the RUSAGE_CHILDREN delta
   around the child; the children of one shard run one at a time) and records it on every static row
   (`child_cpu_measured_s`); a failure row is charged that measured CPU (`cpu_s_source` says so). The limit: the
   measured figure includes the child's interpreter start-up and grammar build (about 2 to 3 CPU-s) besides the
   search, and a killed or timed-out child is charged what it used before it ended, not what its search would have
   used. A successful row reports the search's own CPU, with the measured child CPU beside it.
3. **The builder's "loo" field** is a source proposal heuristic, not a withheld-pair reconstruction: no candidate is
   rebuilt with a demonstration withheld.

**Wording standard (adopted everywhere in this study; it supersedes amendment 2's wording):** the object step's
retried candidates are **exact on all demonstrations and accepted by the declared proposal heuristic**, with its
exceptions stated: an edit is accepted when it is bound in at least two demonstration pairs (for a two-rule candidate,
each edit); whole-output forms are flagged unconditionally; colour tables count any pair in which some object is
bound to a constant recolouring.

## I. Checks (this amendment)

{{CHECKS}}

## J. Change log

- New: `ngb/object_costs.py`, `feasibility/object_costs.json`, `rehearsal/` (made by the rehearsal build),
  `checks/kaggle_rehearsal/` (each rehearsal's returned files in `rehearsal_<N>/`, its record at the top),
  `FREEZE_V2.json`, `FREEZE_V3.json`. The rehearsal's Athe-side tools are in `launch/` (polling, extraction, the RC
  build, the report run, the record, the freeze comparison); they are not frozen and no kernel runs them.
- Changed: `ngb/object_arm.py` (costs from the record; wording standard), `ngb/env.py`, `ngb/gate.py`,
  `ngb/score.py`, `ngb/arc2.py` (rehearsal mode), `ngb/held.py` (killed-child rows and the retry), `ngb/phase2.py`
  (two static shards, retry stages), `ngb/held.py` and `ngb/arc2.py` (every static child's CPU measured by the
  parent), `ngb/report.py` (three folders, C's copies, defects INVALID, retries, S4 wording, the claim), `ngb/kaggle_build.py` (output verification, rehearsal modes, two workers in kernels A and B and one in kernel C), `ngb/package_smoke.py` (allowance inputs,
  builder calls), `ngb/power_object.py` (the transfer scenario), `ngb/dry_run.py` (stand-in tasks from distinct
  families, so that arm 8 has donors), `ngb/admission_tests.py`,
  `ngb/freeze.py`.
- `FREEZE.json` version 4; its digest is reported in PROGRESS.md and the coordinator's record; the GO must name it.
