# Guided-construction test: protocol amendment 2

Dated 6 Nov 2026, 11:40Z. Written after the companion study's formal review: its notes 0516 and 0517, its
`REPORT.md` against version 1, and its `EARLY_BRANCH_SENTINEL.json` against version 2. It was made before any GO.
This study has run no held task, and has opened no held test output and no solution file.

The earlier freezes are kept byte-identical:
- `FREEZE_V1.json`: 55afe42c68c69efbe712132b00ea70914d12134608af0062c84539d58288e4c5;
- `FREEZE_V2.json`: 32c1652b58598eff9cfb21b1d5beaba9d54561a3a61c23663169654285262b17.

`FREEZE.json` version 3 pins this amendment and amendment 1. `PROTOCOL.md` is unchanged. Where they differ, this
amendment governs, then amendment 1.

## 1. The stage (PROTOCOL.md section 8, invariant 1)

**Gap in version 2.** Version 2 compared a normalised stage, but it mapped every reference stage other than
"construction" to "no fit". A changed reference stage therefore passed.

**Rule now** (`gcon/verify.py`):
- A reference stage is "construction" or "base"; an arm stage is "construction" or "construction_none". Anything
  else fails.
- On every arm, not only the hand-set arm at 20,000, the stage must agree with the fit. An arm has stage
  "construction" with an operation and attempts exactly when it fits. Otherwise it has "construction_none", with
  neither.
- Invariant 1 compares the stage together with the other fields.

## 2. Identities

Every row is reconciled against trusted identities. They are computed behind the GO from task data whose digests the
freeze pins: the split and the benchmark files, and the ARC-AGI-2 challenges, whose digest is pinned separately.
- **Per row:** the task, the benchmark, the family (the primary's bootstrap cluster), the number of demonstrations and
  the number of test inputs. Rows now record their demonstration count; the producer change is in `gcon/held.py`.
  Both counts must match.
- **The role of each set:** each held benchmark set holds exactly the split's held tasks of that benchmark, and the
  ARC-AGI-2 set holds exactly the evaluation tasks.
- No identity is taken from a row.
- The receipt binds the digest of the identities, and the scorer requires that digest to be unchanged.

## 3. Kernel receipts (held run)

Verification requires the following receipts, and the receipt binds their exact current bytes:
- the final package manifest, which must name exactly GC1D, GCCM and GCARC2 with their identifiers and sets, and
  must carry the current GO, freeze and protocol.
- For each kernel:
  - its metadata, with the manifest's digest, saying private, CPU only, no TPU, internet off;
  - its notebook, with the manifest's digest;
  - its push receipt, with return code 0 and the notebook's digest;
  - its fetch receipt, giving the sets, the archive's path and digest, and the digest of every returned file;
  - the archive's bytes;
  - the kernel driver's record: every worker returned 0, none stopped at the limit, and it is not a rehearsal.

Every row file of a set must be, byte for byte, one that the set's kernel returned, and none may be missing.

Missing receipts, an empty receipt set or a substituted kernel role fail. No parameter can skip this check in a held
run. Rehearsal mode does not check kernels, and it never scores.

The scorer's binding now also includes the joint digest of the kernel receipts. `gcon/kaggle_fetch.py` now writes the
per-file digests and the archive's path into the fetch receipt.

## 4. Branch evidence

Every row must be exactly one permitted branch, with that branch's evidence:

| branch | evidence required |
|---|---|
| reference error | `ref_error` is a record with a non-empty exception type, a message and a traceback tail. The row has no answer, no shared stage and no arms. `gcon/held.py` now writes this record instead of a bare traceback string. |
| `base_fit` | The reference fitted at the base stage: fit true, stage "base", attempts present. There is no construction evidence: no retry, no candidate, no constructed operation. The row has no arms. |
| `under_two_demonstrations` | The trusted demonstration count is below 2. The reference did not fit: fit false, stage "base", no retry, no candidate. The row has no arms. |
| construction | At least 2 trusted demonstrations. The reference either failed (fit false, stage "base") or fitted by construction (fit true, stage "construction", an operation). Every arm of the configuration is present and none is an error. Each arm's stage agrees with its fit, it has at most 3 retries, and it has one hole record per hole. |

Each of the following now fails:
- an unknown shared stage;
- a `base_fit` row without a base-stage fit, or with construction evidence;
- an `under_two_demonstrations` row with two or more trusted demonstrations, or with a fit;
- a reference error that is empty, False or a bare string;
- a reference error next to an answer, a shared stage or arms.

## 5. Disclosure of uncounted work

**The counted budget.** The budget counts the frozen step's operations: applications of a candidate program to a
grid. An application is allowed while the counter is at most the budget, so a capped hole reaches B + 1. The
symmetry forms and the agreement keys on the test inputs add uncapped applications.

**Work outside the count:**
- **Once per task, before any arm's search:** the sketches, the pair analysis of the 12 views of each hole, and the
  features. The features' W flag is a demonstration-only compatibility prefilter. It compares the content of input
  object crops with the targets, which is the same comparison the frozen W block makes as its crop precondition. It
  runs before `run_hole`, it is not an operation, and its comparisons are now counted for reporting.
- **Inside each arm's search:** edit applications (admissibility), segmentations, crop-precondition comparisons, and
  the work inside each operation.

**Reported per task and arm** (`RESULTS.json`, "work" and each task's "cpu"):
- the shared `holes_setup_cpu_s` (sketches, pair analysis and features), and the features' CPU and comparisons;
- the reference call's CPU;
- each arm's search CPU (its constructor plus the retries it computed first), its constructor CPU, counted
  operations, segmentations, edit applications and content comparisons;
- each task's total CPU.

The counted-operation budget alone is never read as total CPU efficiency.

**Smoke evidence.** On one capped 1D-ARC hole at budget 500, both orders used 501 counted operations. The guide
also made 5,662 edit applications and used 0.040 CPU-s; the hand-set order made 1,310 and used 0.011.

## 6. The cost standardisation, exactly

- The cost loss is the squared log-cost error divided by the training cost variance, (c_hat - c)^2 / s^2, and it is
  added to the mean cross-entropy.
- Here c = log(1 + operations), and s^2 is the variance of c over the training rows: 7.38 for the full model. Each
  fold's model uses its own variance.
- The network outputs z = (c - m) / s, and predictions are mapped back as c_hat = output x s + m.
- This differs from the protocol's description, which is the cross-entropy plus the unscaled squared log-cost error.
- No claim is made that either form is better. The frozen weights were trained with the standardised form, and that
  is the form the test uses.
- Amendment 1's sentence "read with this standardisation that is what was done" is withdrawn.

## 7. Custody wording

**Development loaded held inputs into memory.** Study A's loader (`ngrow.data.tasks`) reads each benchmark's
`real.json` whole. Through it, development loaded the demonstrations and test inputs of every task of the three
benchmarks, held tasks included, before the source ids were selected. This happened in every development process
that called `objgrow.grow.setup`: pass 1, the analysis and the sample checks. The smoke tests load their source
stand-ins the same way, inside the scratch copy of the package.

**What was kept out.** Source selection, labels, folds, features, models, rules and counts exclude the held tasks.
No held solution and no test output of any half was loaded.

**Withdrawn.** The statement "no held task was opened" (DEV_REPORT.md, version 1) is not supported and is withdrawn.
This physical loading is not described as absent anywhere.

**ARC-AGI-2.** The evaluation challenges file was read as bytes, to hash and package it. It was never parsed on
Athe.

## 8. Regression tests (`launch/score_guard_test.py`, run by `launch/smoke_test.py`; `checks/SCORE_GUARD_TESTS.json`)

All cases run in rehearsal mode on source stand-in rows, inside an unpacked package that holds no solution file. The
solution functions are replaced by raising sentinels, and the marker call is watched.

1. **Scorer boundary: 7 cases** (amendment 1). Six must refuse before the marker; the positive control must reach
   it.
2. **Verification sentinels: 17 cases, each on a fresh copy with one construction row changed.**
   - The companion's cases: a changed hand-set stage at 20,000, family or benchmark; `base_fit` without a base stage
     or without a fit; an empty or False reference error; a reference error next to an answer and arms;
     `under_two_demonstrations` with two or more trusted demonstrations; an unknown shared stage.
   - This study's cases: a changed reference stage; an arm whose stage contradicts its fit; a changed test count or
     demonstration count; the old string form of a reference error.
   - Each negative case must give verify INVALID. With a forged receipt that claims PASS and carries every current
     digest, it must also be refused before the marker, with no solution call.
   - Two positive controls, a consistent `base_fit` row and a consistent reference-error row, must verify PASS and
     reach the marker.
3. **Kernel receipts: 17 cases on an invented tree.**
   - The consistent tree must pass.
   - Each of these must fail: a missing tree, kernel, push receipt or fetch receipt; a substituted role; internet on;
     not private; a GPU; metadata changed after the manifest; a failed push; a failed worker; a rehearsal record; a
     changed archive; a package naming another GO; a row file the kernel did not return; an extra row file.

## 9. What did not change

- **Unchanged:** the rules (the budget rule and the test budget of 500, the stop rule), the arms, the analysis, the
  predictions, the trained weights, the configuration, the engine and the features' values, the held tasks and the
  kernel layout.
- **Changed files:** `gcon/verify.py`, `gcon/score.py`, `gcon/held.py` (the reference-error record and the
  demonstration count in rows), `gcon/kaggle_fetch.py`, `gcon/freeze.py`, `launch/score_guard_test.py`,
  `launch/smoke_test.py` and `DEV_REPORT.md` (custody wording).
- **New files:** this file and `FREEZE_V2.json`.
