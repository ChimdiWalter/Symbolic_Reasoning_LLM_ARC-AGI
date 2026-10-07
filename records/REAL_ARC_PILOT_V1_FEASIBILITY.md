# Real ARC pilot v1: static feasibility (2026-10-07)

**Result: NOT READY. Blocker: the frozen proposer does not reach real
tasks. 0 of 60 development tasks reach a verified proposal, so the
compile-and-install stage is never entered.** By the rule fixed in protocol
section 12 before the dry run (commit f47c795), the pilot is not frozen and
the block ends with this blocker. No pilot task was run, and nothing was
scored. The selection (4d3c29b) keeps the 488 pilot candidates untouched for
a later block.

## The development dry run

Reasoner only, under the isolation hook, on the frozen development bundle
(the first 60 in-scope tasks in the salted hash order; n3 47, n4 11, n5p
2). Coordinator `scripts/pilot_v1_run.py dev`, 4 workers per phase, host
load about 45 on 24 cores, 675.7 s in total. Outputs in
`outputs/pilot_v1_dev/` (rows, `feasibility.json`, `frontier_census.json`).

| criterion (section 12) | result |
|---|---|
| no isolation problem | PASS: 8 worker logs, every one installed, bundle opened, 0 refused accesses |
| CORA phase complete | PASS: 60 of 60 rows |
| native phase complete | PASS: 6 of 6 rows |
| no RUN_ERROR | FAIL (engineering): 1 native task, a race between workers installing the frozen library into the shared object directory; fixed after the run (the coordinator installs it once before the workers start; per-process temporary names) and covered by a concurrency test |
| loop operable: at least one task at the installed stage | **FAIL: 0 of 60** |

## Where the closed loop stops on real tasks

| quantity | value |
|---|---|
| CORA path class | NO_PROPOSAL 60 of 60 |
| proposer class | NO_PROPOSAL 59, K_ALREADY_SOLVES 1 |
| reasoner's own single-block search (k class) | no consistent program 58, consistent but inexact 1, exact 1 |
| tasks with any consistent single block (a partial top layer) | 13 of 60 (47 have none) |
| compiled / installed / activated | 0 / 0 / 0 |
| DEMONSTRATION_ONLY_CONTROL | PROPOSAL_LIMIT 59 (256 proposals each, none verified), K_ALREADY_SOLVES 1 |
| SHUFFLED_FAILURE_CONTROL | NO_PROPOSAL 59, K_ALREADY_SOLVES 1 |
| KSTAR_PRIME_WITHOUT_EXTENSION accepted | 4 of 60 |

Frontier census (`scripts/pilot_v1_dev_frontier.py`), 60 tasks x 200
single-block programs, the fitter's own rejection codes:

| code | blocks | meaning |
|---|---|---|
| slot_unobservable | 4,280 | no selected region is ever changed: the change lies outside the regions the block selects |
| region_colour_conflict | 3,688 | a changed region changes only partly, or to more than one colour |
| scoped_fit_failed | 2,947 | the partition or the key does not apply to the grid |
| slot_key_unobserved | 488 | a key seen in fewer than two demonstrations |
| slot_nonfunctional | 391 | one key, two colours |
| final_execution_mismatch | 103 | an untouched region with a table key changes colour |

Dominant reason per task: slot_unobservable 33, region_colour_conflict 21,
scoped_fit_failed 6. The best consistent block covers none of the change on
at least three quarters of the tasks (quartiles 0, 0, 0, 0, 1.0); the
changed share of cells has quartiles 0.02, 0.08, 0.16, 0.32, 1.0.

Reading: the v1.8 grammar builds only stacked layers of whole-region
recolouring keyed on a region feature (the family its synthetic corpus was
generated from). In these real tasks the change does not take that form:
cells change inside or outside the regions K's partitions produce, not as
whole regions. The proposer is working as designed; its grammar does not
cover these tasks.

## Positive control of the harness

To separate "the harness is broken" from "the grammar does not reach real
tasks", the unchanged `run_cora` ran under the isolation hook on the first
four synthetic v1.9 DEVELOPMENT tasks (`outputs/tti/v19_dev_corpus.json`;
seven demonstrations, one held-out pair; the grammar applies by
construction). Script `scripts/pilot_v1_positive_control.py`, outputs
`logs/pilot_v1_dev/positive_control_{0..3}.json`, 185 to 358 s per task.

| task | proposer | gates passed | path class | K*' + e prediction |
|---|---|---|---|---|
| 0 | SELECTED (MDL) | all but support | INSUFFICIENT_WITNESSES | right |
| 1 | SELECTED (D) | all 10 | ACTIVATED | right (committed and correct) |
| 2 | SELECTED (MDL) | all but support | INSUFFICIENT_WITNESSES | right |
| 3 | SELECTED (MDL) | all but support | INSUFFICIENT_WITNESSES | right |

Every task passed compile, acceptance, use, replay, attribution,
prediction, determinism, all 7 leave-one-out folds and candidate
unanimity; isolation was clean and state restored on all four. The harness
therefore reaches activation when the grammar applies, and the 0 of 60 on
real tasks is the proposer's reach, not a harness fault.

Design note for any later block (not acted on here): the witness-support
gate abstained on 3 of these 4 tasks although the prediction was right. It
counts every region a block selects on the test input, painted or not, so a
new key on an unpainted region forces abstention. It is conservative by
intent and costs recall; any refinement belongs to bounded development and
must not be tuned on pilot tasks.

## Runtime measured (for any later pilot)

CORA phase 12.5 s per task (mean; max 21.2) when nothing is proposed;
native 214 s per task (mean of 5; median 95, max 460 at the object layer's
frames cap; 2 of 5 hit object_hard_timeout). At N = 120 the projected
reasoner wall time is about 113 minutes with 4 workers, plus leave-one-out
time for any task that reaches installation.

## What this blocks and what it does not

- Blocked: freezing and running the real ARC causal pilot with the frozen
  v1.8 proposer. With 0 of 60 (95 percent upper bound on the per-task rate
  about 4.9 percent), a 120-task pilot would most likely end at
  NO_REAL_ARC_WITNESS by NO_PROPOSAL, which this record already shows
  without spending the one-shot pilot.
- Not affected: the pilot harness (selection, bundle, isolation, native
  baseline, closed loop with 11 recorded gates, blind evaluator, verifier,
  33 tests) is built and committed and can be frozen unchanged once a
  proposer reaches real tasks; the pilot candidates remain unused.
- Not concluded: anything about the v1.9 synthetic result, which stands
  (LEVEL 2, synthetic only), or about whether failure-conditioned
  construction can work on real tasks with a grammar that covers them.
