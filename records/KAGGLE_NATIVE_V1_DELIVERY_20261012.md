# Kaggle ARC-AGI-2 delivery: NATIVE_BASELINE native_v1 (2026-10-12)

**Status: READY FOR USER REVIEW.** Nothing has been uploaded or submitted.
This is the native solver, not the CORA invention loop. Its 185/1,000 is a
training characterization, not a leaderboard prediction.

## 1. Historical Kaggle submission (evidence: Reasoning_Project/RUN_HISTORY.md, 2026-07-12)

| item | value |
|---|---|
| notebook | `arc-certified-solver`, version 334601009 (from the author) |
| submitted | 2026-07-12 |
| engine | the v10/v11 era (153 of 1,000 training), not v23 |
| commit run | completed cleanly in 41 min on a 240-task placeholder set |
| submission.json | 240 tasks: 162 real attempt_1, 100 real attempt_2, 97 fallback |
| hidden rerun | completed; public score 0.0 |
| prior local check | 0 of 120 on the local public-evaluation split, render-verified before submitting |

What these facts allow:
- The pipeline ran end to end, and most outputs were real attempts, so a
  total packaging failure is not indicated.
- The 0.0 cannot be attributed further from these records: to vocabulary, to
  the configuration of that time, or to anything else.
- Separately, the repository notebook lineage lacked the five chain flags and
  the learned_verbs.json asset until 2026-10-07
  (`records/KAGGLE_NOTEBOOK_FLAGS_FINDING_20261007.md`). Whether the July
  Kaggle version had the same gap is not verifiable without Kaggle access.

## 2. Current production solver

**Identity.**
- The sealed v23 chain (RUN_HISTORY 2026-08-19: 183 in-run plus 2
  arbitration recoveries = 185 of 1,000 training).
- The five chain flags `ARC_DIHEDRAL_FRAMES=45 ARC_GENERATIVE=1
  ARC_PATTERN_DERIVE=1 ARC_VARIANT_BUDGET=1 ARC_RAY_EXT=1`.
- The sealed `library.json` (`cdacd018...`) and `learned_verbs.json`
  (`b1f07ba5...`).
- The unified harness with its default per-task budgets. The global governor
  only ever lowers budgets.
- attempt_1 is the solving layer's render, attempt_2 the best uncertified
  object partial, and the test input is the fallback.

**Differences from July:**
- engine v23 instead of v10/v11 (+32 training solves);
- the flags and assets are set and hash-checked;
- the native_v1 deployment robustness below.

## 3. Package

`kaggle/native_v1/`, source commit 8cde9f3, frozen in `DELIVERY_MANIFEST.json`.

| file | sha256 |
|---|---|
| `arc_native_baseline_v1.tar.gz` (272 files: sealed code + 2 assets + MANIFEST.json; byte-reproducible) | `4b320ba2fe92b12bcc4345ef4523ca45115f7694e3ab999dfea6b1cfe3c9a088` |
| `notebook.py` (single cell) | `647594be...` |
| `notebook.ipynb` (the same code, one cell) | `0be06005...` |

**Code identity.** The packaged code is byte-identical to the historical v23
tarball, checked by a test. The staged solver tree sha256 is `d7856871...`.

**Deployment changes only; the reasoning is unchanged:**
- a hard limit on the harness (budget + 600 s, process group killed);
- submission.json is always written, using the same fallback order;
- full schema validation and repair;
- an execution manifest.

**Excluded:** P2, P3, DCC, the diagnosis v0 module, every `cora_*` research
package, and every uncertified extension.

**Dependencies.** The package imports numpy, scipy, sklearn, matplotlib,
torch and pytest, all standard on Kaggle images. torch and `guide` are only
reached behind off flags or try/except. No Python 3.10 or 3.11 syntax issue
was found in any of the 269 files.

## 4. Offline validation

The emulation used a Kaggle-style tree with no solution file of any kind and
a socket guard on the harness.

| run | inputs | result |
|---|---|---|
| fixtures | 4 synthetic tasks, 5 outputs (a two-output task, 1x1, 30x30, non-square) | valid; all 5 attempt_1 correct by construction; 258 s; 548 MB peak |
| fixtures, repeated twice more | | byte-identical submission.json: deterministic |
| failure (harness forced to fail) | | fallback writer; valid submission |
| dev60 | the 60 training-development tasks, inputs only | exit 0; harness completed; 60 of 60 tasks with predictions; 64 of 64 positions valid; 0 repairs; 49 real attempt_1, 26 real attempt_2, 15 fallback; 4,609 s with 4 workers on a host at load about 55-70 (Step B and other jobs); peak 749 MB; per task median 399 s, max 460 s |

- No network attempts in any run.
- 14 tests pass across the three suites: 6 for the package, 5 parity tests,
  3 for diagnosis v0.
- No score is computed: no answer was read.

## 5. Runtime for 240 hidden tasks

**Projection.** At the measured per-task times, (240 / 4) x 399 to 460 s
gives about 6.6 to 7.7 h, inside the 11.25 h budget.

**If Kaggle's cores are slower,** the governor lowers per-task budgets to the
remaining clock. The hard limit (11.42 h) then guarantees that the writer
finishes before the 12 h limit. Unreached tasks get the fallback, and the
submission stays valid.

**Unmeasured.** Hidden-task difficulty and Kaggle CPU speed.

## 6. Readiness: READY (pending user review)

Instructions for the first new official run:

1. Create a NEW Kaggle Dataset, for example `arc-native-baseline-v1`, so the
   historical `arc_certified_solver1` is not overwritten. Upload
   `kaggle/native_v1/arc_native_baseline_v1.tar.gz` and check its sha256
   (`4b320ba2...`).
2. Create a new notebook, or a new version of `arc-certified-solver` (older
   versions stay in its history). Use `kaggle/native_v1/notebook.ipynb`, or
   paste `notebook.py` into one code cell.
3. Notebook settings:
   - Internet OFF.
   - Accelerator None (CPU).
   - Add input: the competition data "ARC Prize 2026 - ARC-AGI-2".
   - Add input: the new dataset.
4. Check that both are mounted. The log must print
   `using task file: arc-agi_test_challenges.json` and the
   `native configuration` line, with the five flags and both asset hashes.
   A successful save is not proof of mounting.
5. Save Version, then Save & Run All (commit). Wait for
   `submission.json written ... harness completed`, and keep
   `execution_manifest.json` from the output.
6. Submit that version to the competition. Record the version number, the
   execution status and the public score, and ask for them to be logged here.
