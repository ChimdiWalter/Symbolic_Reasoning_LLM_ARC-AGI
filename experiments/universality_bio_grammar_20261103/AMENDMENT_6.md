# Amendment 6 to Protocol U5 (2 Nov 2026, before any evaluation parent is processed): technical corrections and a primary-first schedule

`PROTOCOL.md` and Amendments 1 to 5 are unchanged in substance. This file adds to them. Its hash and the new exact code
freeze are in `AMENDMENT_6_FREEZE.json` and `CODE_FREEZE.json`.

**State.** No evaluation image has been segmented, no evaluation reference has been decoded, and no arm has touched an
evaluation parent. The hold stays in place until the coordinator writes `GO_EVALUATION`.

## 1. Serialization fault in the LIVECell induction (no decision rule changes)

The LIVECell induction (A) finished its computation, then stopped at 12:27:53Z while writing `INDUCTION.json`. One
admission check was a numpy boolean, which `json` cannot write. Nothing was lost except that run's CPU (about 52 CPU
minutes); no partial result was used.

- **Fix.** Admission checks are cast to Python booleans. Numpy scalars and arrays are written as plain JSON values
  (`u5induce._jsonable`). The file is written to a temporary name and then renamed, so a partial file can never be
  read.
- **Records.** The partial file is kept as `INDUCTION.partial_serialization_error.json` and is never read. The earlier
  chain status is kept as `cal_chain.run.status.v1`.
- **Re-run.** The induction is re-run from the start under this freeze.
- **Test.** A regression test checks the serialization.

## 2. A race in the MoNuSAC chain

`monusac_chain.sh` waited for any `EXIT` line in the main chain's status. Once the stopped chain had logged EXIT 1, it
could have started `freeze_target` while the main freeze was still writing `POLICY_FREEZE.json`. It now waits for
`POLICY_FROZEN`.

Roles are recomputed when the main chain restarts. MoNuSAC's gate already exists and passed, so it enters the main
freeze directly as the second transfer target. Its `freeze_target` step then only records completion.

## 3. Primary arms first (the author asked to expedite)

`u5eval.decide` and `u5eval.evaluate` now take a scope.

- **PRIMARY** arms, on A and both transfer targets: NATIVE, TUNED, STRONG_NATIVE (equal to ABSTAIN_ALL), ALL_ON,
  MATCHED_SEARCH, CORA, FAILURE_BLIND x5 and SHUFFLED x5.
  - They are decided and frozen in `DECISIONS_FROZEN.json`, then scored into `results/RESULTS.json` and
    `results/SUMMARY.md`.
  - Every label, contrast, growth gate and transfer conjunction of the protocol uses these arms only.
- **SECONDARY** arms: CORA_FULL, CORA_INDOMAIN, PROGRAM_TRANSFER and, if its frozen proposals arrive, NEURAL_PROPOSER.
  - They are decided afterwards, by the same frozen code and policy, into `DECISIONS_FROZEN_SECONDARY.json`, then
    scored into `results/RESULTS_SECONDARY.json` and `SUMMARY_SECONDARY.md`.
  - Their decisions use only evaluation images and the frozen policy. The decision step never reads an evaluation
    reference, which the Reader's guard enforces. They are fixed whatever the primary results show.
  - They are reported as secondary, and the neural arm as an addendum.

## 4. Evaluation segmentation in parallel

After GO, the evaluation images of the three datasets are segmented in parallel, one CPU slot per job, and nothing else
changes. GPU 0 is not used: the Cellpose 3 environment has CPU-only torch and StarDist runs on CPU, so no GPU path
exists without changing an environment.

The code is re-frozen. `tests/test_u5.py` has 17 tests (the 16 earlier ones and the serialization regression); all
pass.
