# Guided-construction test: independent post-score audit

Auditor: the same independent session that reviewed versions 1 to 4 before the GO. It did not build or run the test.
Written 6 Nov 2026, about 12:55Z to 13:15Z.

This audit did not rescore through the study's scorer. It ran no held task and opened no solution file. It made no
Kaggle call and wrote nothing in the study except this file.

Inputs:
- the committed bytes of the GO commit 40261311, the rows commit 7b41c5c2 and the scoring commit 2797398e, extracted
  with `git archive` into a scratch folder;
- my own scripts, run inside one shared CPU slot at nice 19 (about 8 CPU-s).

Correctness per task was taken only from the scorer's per-task table in `RESULTS.json`. That table is the one sanctioned
opening of the test outputs. I checked it against the rows for internal consistency.

## Verdict

**PASS: the scored result stands as reported.**
- Every custody check holds.
- My own recomputation reproduces every number in `runs/held_run/RESULTS.json`: 21 checks, 0 mismatches. These cover
  the primary, all seven secondaries with the Holm adjustment, the clustered intervals, the descriptive totals, the
  budget curves, the three predictions, the work and CPU totals, and the per-task CPU.
- Every number in the owner's report matches, with one rounding exception. "+8.5%" search CPU is +8.4% computed from
  the unrounded totals.
- The wording points in section 3 must be applied wherever the result is written up.

## 1. Custody

| Check | Evidence | Result |
|---|---|---|
| exactly one GO | `runs/GO` was touched only by commit 40261311 and is unchanged since. Its sha256 is a61406ce.... Line 1 is `protocol_sha256 d5510c8f...` and line 2 is `freeze_sha256 d876eede...`, which are the current PROTOCOL.md and FREEZE.json | holds |
| frozen bytes unchanged | at the scoring commit, every one of the 99 files pinned by FREEZE.json version 4 has its frozen digest. No frozen code, configuration, weight or protocol file changed between the GO and the rows commit | holds |
| final package | `package_final.tar.gz` e3fd6759... equals its manifest (71 files). The only difference from the reviewed candidate (e5d2d77c..., unchanged) is `runs/GO`, byte-identical to the GO file. No solution-like path is inside | holds |
| kernels as pushed | each of the three final notebooks embeds exactly the final archive. Each notebook and metadata file carries the final manifest's digest. Metadata: private, no GPU, no TPU, internet off | holds |
| each kernel ran exactly once | each `PUSHED.json` carries the manifest's notebook digest and the Kaggle output "Kernel version 1 successfully pushed": GC1D 12:19:35Z, GCCM 12:21:04Z, GCARC2 12:36:43Z. There is one fetch folder per kernel, and no push record after an accepted push | holds |
| refused pushes kept, no kernel created | GCCM attempt 1 and GCARC2 attempts 1 to 4 are kept as `PUSH_ATTEMPT_<n>_REFUSED.json`. Each has the same notebook digest and the output "Kernel push error: Maximum batch CPU session count of 5 reached." Each later accepted push is version 1, so no refused attempt created a version | holds |
| returned files bound byte for byte | I reopened each returned archive; its digest equals the fetch receipt's. Every member is a regular file under `run/`, its sha256 equals the fetch receipt's per-file digest, and it is byte-identical to the file used in verification (rows under `runs/held_run/<set>/`, `kernel_run.json` and logs under `<KERNEL>_meta/`). No row file is missing or extra. This closes the reopen-the-archive advisory left open in my pre-run review | holds |
| receipt and marker | the receipt says PASS with 0 failures, mode `held_run`. The joint digest of the 16 row files is bf671f23..., equal to the receipt's and the marker's. The 19 kernel-receipt files equal their bound digests, including the three `kernel_run.json` files. The marker `runs/SCORED` and `RESULTS.json` carry the same nine bound fields | holds |
| exactly one scoring | `runs/SCORED` and `RESULTS.json` appear only in commit 2797398e. The rows, receipt and kernel receipts are unchanged from the rows commit 7b41c5c2 to the scoring commit, and nothing in the study changed after it | holds |
| no rehearsal variable | all three driver records say `rehearsal: false`, with 4 workers, every return code 0, none stopped at the limit. The receipt's mode is `held_run`. The trusted-identity check passed on the held tasks, which a set NGB_REHEARSAL would have broken | holds |
| no solution read before the GO | solution files open only in `gcon/score.py`, after the guard and the O_EXCL marker; the package held none. The marker was created at 12:51:23Z: after the GO commit (12:17:56Z), after the fetches (12:36:44Z to 12:49:40Z) and after the rows commit (12:51:13Z). No solution-like path appears anywhere in the study's git history | holds |

Two of these rows needed something beyond the files themselves:
- **Solution-file metadata.** I read only the metadata of the solution files (`stat`, no content). It is uninformative.
  The filesystem uses relatime and the last recorded accesses are on 5 Nov, under 24 hours before the scoring, so a
  read on 6 Nov leaves no trace. The custody conclusion rests on the code path, the package contents and the order of
  events.
- **The retry procedure.** It is documented in `PROGRESS.md` and is safe as run:
  - The Kaggle command-line tool returns 0 even on a refused push.
  - The frozen `kaggle_fetch.py push` therefore wrote a refused attempt's record as `PUSHED.json` with return code 0.
  - A scratch retry loop, not committed, renamed each refused record and called the frozen push again.

  The frozen push-receipt check (`gcon/verify.py`, return code 0) could not by itself tell a refused push from an
  accepted one. In this run the accepted records all say "successfully pushed", and the fetch receipts bind every
  returned file, so nothing depends on that gap.

  Advisory for future runs: commit the retry loop's text with the records, and check the push output text, not only
  the return code.

## 2. Recomputation (independent scripts; inputs: committed rows, the per-task table, SPLIT.json, CONFIG.json)

The rows are exactly the split's held tasks (309 1D-ARC, 80 ConceptARC, 75 Mini-ARC) plus the 120 ARC-AGI-2 tasks,
and they carry the split's families. The per-task table has one entry per row. It is consistent with the rows: every
abstaining arm scores 0, every count lies between 0 and the task's number of test outputs, and identical attempts
always score the same.

Invariants recomputed from the rows with my own comparison:
- 580 construction tasks, with invariant 1 equal on all 580;
- 466 tasks with no capped hole, with invariant 2 equal on all 466; 114 tasks have a capped hole;
- 4 `base_fit` rows (2 ConceptARC, 2 Mini-ARC) and no reference error.

**Primary** (464 held tasks, pass at 2, correct test outputs, 500 counted operations per hole): guide 320, hand-set
order 234.
- 87 tasks gained and 1 lost.
- Exact two-sided sign test p = 89/2^87 ≈ 5.8e-25. RESULTS.json shows 0.0 after rounding to 6 decimals.
- Total difference +86. Family-clustered 95% interval 41 to 136; strata by benchmark, 10,000 draws,
  `random.Random(20261105)`.
- Decision: the guide beats the hand-set order.
- By benchmark: 1D-ARC 275 against 191, ConceptARC 33 against 32, Mini-ARC 12 against 11. All match.

**Secondaries** (Holm over seven, on the reported p-values; the decisions are the same with the exact p-values):

| Comparison | Correct outputs | Tasks only first / only second | p | Holm p | Interval | Decision |
|---|---:|---:|---:|---:|---:|---|
| guide against donor guidance | 320 / 305 | 20 / 3 | 0.000488 | 0.00244 | 0 to 32 | inconclusive (interval not above 0) |
| guide against frequency order | 320 / 318 | 4 / 2 | 0.6875 | 1.0 | -7 to 11 | inconclusive |
| guide against hand rule | 320 / 278 | 44 / 2 | 3.1e-11 | 0.0 | 8 to 89 | guide beats hand rule |
| guide against linear model | 320 / 323 | 1 / 2 | 1.0 | 1.0 | -11 to 2 | inconclusive: "learned guidance" |
| guide against hand-set at 20,000 | 327 / 329 | 4 / 3 | 1.0 | 1.0 | -11 to 6 | inconclusive |
| ARC-AGI-2 at 20,000 | 2 / 2 | 0 / 0 | 1.0 | 1.0 | 0 to 0 | tie |
| leave-one-benchmark-out guide against hand-set | 312 / 234 | 80 / 2 | 1.4e-21 | 0.0 | 34 to 126 | it beats the hand-set order |

All match RESULTS.json and the owner's report.

**Budget curves** (held correct outputs at 125, 500, 2,000 and 20,000):
- hand-set order 207, 234, 296, 329;
- guide 320, 320, 320, 327.

Of the four budgets, the hand-set order first reaches the guide's 320 at 20,000, which is 40 times the test budget.
It falls short at 2,000, which is 4 times the test budget. All match.

**Predictions:**
- guided-1 is **refuted**. At 500 the ARC-AGI-2 attempts differ: the hand-set order solves 1 task (2 outputs) and the
  guide 0. At 20,000 both solve 1 task, with identical attempts.
- guided-2 **holds**. The tasks whose correct count differs at 500 are 84 on 1D-ARC, 3 on ConceptARC and 1 on Mini-ARC.
- guided-3 is **refuted**. 11 held tasks have different attempts at 20,000, and every one of them has a capped hole in
  one of the two arms. All match.

**Work and CPU**:
- Every per-arm and shared total in RESULTS.json is reproduced to the reported precision, for the held halves and for
  ARC-AGI-2.
- At 500 counted operations per hole:

  | | guide | hand-set order | difference |
  |---|---:|---:|---:|
  | search CPU (constructor plus the retries the arm computed first) | 115.25 s | 106.35 s | +8.4% |
  | constructor CPU alone | 113.78 s | 102.61 s | +10.9% |
  | counted operations | 295,993 | 289,225 | +2.3% |
  | edit applications | 3,925,625 | 3,668,955 | +7.0% |

  The guide's arms also use the shared features: 1.04 s and 984 content comparisons.
- Hand-set order at 20,000: 629.84 s search CPU.
- Shared work:
  - hole setup 289.11 s, of which pair analysis 273.25 s and sketches 10.56 s;
  - reference calls 2,146.65 s;
  - retries 126.46 s;
  - donor features 280.93 s and 1,081 comparisons (donor arm only).
- Task totals: 5,387.74 CPU-s on the held halves and 2,570.08 CPU-s on ARC-AGI-2.
- Kaggle wall time: 830 s, 595 s (425 s plus 170 s) and 715 s. All match the owner's report, except that "+8.5%" is
  +8.4% from unrounded totals.

## 3. Wording (what the protocol and its amendments allow)

The owner's report keeps the main rules. It says "learned guidance", since the linear model ties. It claims no new
reach. It discloses the CPU cost at equal budget. When the result is written up:

1. **Write "counted operations" every time**: "500 counted operations per hole", not "500 operations per hole" (the
   `PROGRESS.md` entry and the scoring commit's message use the latter).
2. **"Fewer counted operations for the same exact answers" is a statement about budgets, not about this run's
   totals.** At the equal budget of 500, the guided search used slightly more:
   - counted operations +2.3%, because capped holes reach 501 in both arms;
   - edit applications +7.0%;
   - constructor CPU +10.9%;
   - search CPU +8.4%, plus 1.0 s of features.

   The supported claim: at an equal counted budget the guided order answers 86 more held outputs, and of the budgets
   tried the hand-set order first matches it at 40 times the budget (it still falls short at 4 times). Always print
   both arms' CPU beside it. Never write that the guide used fewer operations or less CPU at the test budget.

   If a CPU comparison at equal answers is given, use both search-CPU figures: hand-set at 20,000 used 629.8 s, the
   guide at 500 used 115.3 s plus 1.0 s of features.
3. **Report constructor CPU beside search CPU.** The search-CPU figure includes the retries each arm computed first,
   and that depends on the order in which arms run (the hand-set arms run first). Constructor CPU is the order-free
   comparison: +10.9%.
4. **"Learned guidance", not "neural".** The network ties the linear model (320 against 323) and the frequency order
   (320 against 318), so the gain is a learned reordering that a fixed table of success rates also captures.
5. **No new reach.** At 20,000 the orders give 327 against 329. That result is inconclusive. Write "inconclusive; the
   protocol had predicted a tie", not "the predicted tie".

   The 11 tasks whose attempts differ all have a capped hole. On the 466 tasks with no capped hole the two orders are
   identical.

   On ARC-AGI-2 both solve 1 task at 20,000, and at 500 the guide lost the one task the hand-set order solved.
6. **Where the gain is.** It is on 1D-ARC (275 against 191). ConceptARC (33 against 32) and Mini-ARC (12 against 11)
   barely change.
7. **The positive outcome paragraph** (`PROTOCOL.md` section 9) needs three changes:
   - say "counted operations";
   - say the budget rule keeps at most three quarters of the source units fitted at 20,000;
   - replace "Learning bought efficiency, not reach" with wording that does not imply less work. For example: "Learning
     bought fewer counted operations, not reach", with the CPU figures.

   Every table carries the exposure statement.

## 4. Other notes (no effect on the result)

- **Fetched copies of the package.** The kernels' working copies of the package were fetched and committed under
  `runs/kaggle_out/*/pkg/`. They include the three benchmarks' `real.json` files: demonstrations and test inputs, no
  outputs. Keep them out of any public snapshot.
- **Python version.** The kernels ran CPython 3.13.18, while development ran 3.12.3. The run's invariants held within
  the run; record the version for reproducibility.
- **Launch time.** The held run was launched at about 12:20Z instead of the planned 7 Nov 00:00Z. This came after both
  bounded re-reviews passed, is documented in `PROGRESS.md`, and is not a slip.
