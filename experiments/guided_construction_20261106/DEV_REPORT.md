# Guided-construction test: development report (steps 2 and 3)

Status: final for steps 2 and 3, 6 Nov 2026 10:20Z; wording amended 11:00Z and 11:40Z by `PROTOCOL_AMENDMENT_1.md` and
`PROTOCOL_AMENDMENT_2.md` (every number unchanged). Development used the source halves only, but it physically loaded
every task's demonstrations and test inputs, held tasks included, into memory: study A's loader reads each
benchmark's `real.json` whole before the source ids are selected. Held tasks were excluded from every record,
feature, label, fold, model, rule and count; no test output of any half and no solution file was read; the ARC-AGI-2
evaluation challenges file was read as bytes to hash and package it, never parsed; a unit is "fitted" on its
demonstrations. Protocol: `PROTOCOL.md` (commit d5a07f71, sha256 d5510c8f...) with amendments 1 and 2. Code:
`gcon/`. Records: `dev/`. Log: `PROGRESS.md`.

Exposure statement: the held halves were held out from this development, but every task of the three benchmarks was
run and scored once on 2 Nov by the submitted entries and once by the companion's constructor; held halves share
families with source halves; the public evaluation is exposed; no pretrained model is used.

## 1. What was run

- **Pass 1** (`gcon/dev.py pass1`, records `dev/pass1/`): for each of the 425 units and its 3 holes, the frozen
  `objgrow.construct.hole_candidates` live, the test's constructor in the hand-set order at 20,000 operations in the
  same process, their comparison, the comparison with the stored `objgrow` `runs/v2` hole records, the block trace
  (every block run once to its end or to 20,001 operations) and the block features.
- **Models** (`gcon/devan.py train`, `dev/models/`): the guide, the linear model and the frequency table, cross-fitted
  over 5 folds (by task hash within each benchmark), three leave-one-benchmark-out guides, and the full models for the
  held run. Training data: 62,109 blocks from the 1,275 holes, of which 11,820 produced an exact program (a verified
  multi-pair candidate) and 50,289 failed; 4,306 two-rule blocks never run (their view had a single-rule success).
- **Curves** (`gcon/devan.py curves`, `dev/curves.json`): every arm at every budget from the trace, each unit's
  answer through the retry of its first at most 3 multi-pair candidates (434 retries, computed once with the
  seed-independent G0 builder, `dev/retries.jsonl`).

## 2. Step 2: equivalence checks (all passed)

| check | holes | mismatches |
|---|---:|---:|
| test's code, hand-set order, 20,000, against the frozen `hole_candidates` live (candidates, order, fields, operation count) | 1,275 | 0 |
| frozen `hole_candidates` live against the stored `runs/v2` hole records | 1,275 | 0 |
| simulation from the trace, hand-set order, 20,000, against the frozen function | 1,275 | 0 |
| seeded sample: hand-set order at 100, 500, 2,000 and 5,000, frozen function with its cap set = direct execution = simulation; guide and hand rule at 100, 1,000 and 5,000, direct execution = simulation | 71 (12 capped) | 0 of 710 checks |

171 of the 1,275 holes reach the 20,000 cap in the hand-set order; 30 blocks were cut at 20,001 operations in the
trace (simulation treats a cut block as using up any budget of the test, which is exact for budgets up to 20,000).
The fallback (reordering views only) is not needed. Records: `dev/STEP2_CHECK.json`, `dev/STEP2_SAMPLE.0.json`.

## 3. Source budget curves (units fitted, of 425: 74 ConceptARC, 68 Mini-ARC, 283 1D-ARC)

Cross-fitted arms (each unit ordered by models not trained on its fold); hand-set and hand rule need no training.

| arm | budget | all | ConceptARC | Mini-ARC | 1D-ARC | operations | capped holes |
|---|---:|---:|---:|---:|---:|---:|---:|
| hand-set | 100 | 177 | 20 | 9 | 148 | 69,256 | 562 |
| hand-set | 125 | 181 | 20 | 9 | 152 | 83,326 | 537 |
| hand-set | 200 | 188 | 21 | 9 | 158 | 123,151 | 511 |
| hand-set | 500 | 213 | 21 | 9 | 183 | 264,992 | 429 |
| hand-set | 1,000 | 249 | 22 | 9 | 218 | 460,355 | 352 |
| hand-set | 2,000 | 264 | 22 | 9 | 233 | 775,622 | 302 |
| hand-set | 5,000 | 281 | 22 | 9 | 250 | 1,612,063 | 262 |
| hand-set | 20,000 | 298 | 23 | 9 | 266 | 4,842,286 | 171 |
| guide | 100 | 284 | 18 | 8 | 258 | 74,627 | 562 |
| guide | 125 | 284 | 18 | 8 | 258 | 88,831 | 537 |
| guide | 200 | 284 | 18 | 8 | 258 | 128,972 | 511 |
| guide | 500 | 284 | 18 | 8 | 258 | 271,673 | 429 |
| guide | 1,000 | 285 | 19 | 8 | 258 | 466,203 | 352 |
| guide | 2,000 | 286 | 20 | 8 | 258 | 780,799 | 302 |
| guide | 5,000 | 292 | 20 | 9 | 263 | 1,616,070 | 262 |
| guide | 20,000 | 295 | 21 | 9 | 265 | 4,843,290 | 171 |
| linear model | 500 | 286 | 20 | 8 | 258 | 271,530 | 429 |
| frequency order | 500 | 285 | 19 | 8 | 258 | 270,101 | 429 |
| hand rule | 500 | 253 | 21 | 9 | 223 | 265,634 | 429 |
| donor guidance | 500 | 268 | 20 | 9 | 239 | 265,550 | 429 |
| leave-one-benchmark-out guide | 500 | 272 | 19 | 8 | 245 | 267,127 | 429 |

"Operations" counts every operation application, including the frozen symmetry forms and the agreement keys on the
test inputs, which no budget caps; that is why an arm can exceed budget x holes slightly.

## 4. Step 3: the frozen rules

**Budget rule.** F(20,000) = 298, so the threshold is 0.75 x 298 = 223.5. F(500) = 213 is at most 223.5 and
F(1,000) = 249 is not, so the **test budget is B = 500 operations per hole**. The held run's four budgets are 125,
500, 2,000 and 20,000.

**Stop rule (cross-fitted, at 500): GO.** The guide fits 284 units and the hand-set order 213: 75 gains and 4
losses, net +71 (threshold +10), and 75 is at least 3 x 4 = 12. All 75 gains are on 1D-ARC; the 4 losses are on
ConceptARC (co0036, co0061, co0066) and Mini-ARC (mi0143). Unit lists: `dev/curves.json`, `stop_rule`.

## 5. What else development shows (descriptive; none of it changes a rule)

- **Fewer counted operations for the same exact answers.** (Counted operations only: the pair analysis, the
  features, the admissibility checks and the crop-precondition comparisons are outside the counter and are not
  measured here; the held run reports CPU and these counts for every arm, amendment 1 section 2.) The hand-set order
  needs 20,000 operations, 40 times the test
  budget, to fit at least the 284 units the guide fits at 500 (it fits 281 at 5,000). The guide's 1D-ARC count is
  already 258 at 100 operations per hole.
- **The network adds nothing over simpler learned orders here.** At 500 the linear model fits 286 (2 more units than
  the guide, none fewer) and the static frequency order 285 (1 more, none fewer). On the source halves, the learned
  gain is a reordering that a fixed table of success rates per (block kind, view, edit type) already captures. Unless
  the held secondaries say otherwise, the paper's wording is "learned guidance".
- **Task-specific guidance helps beyond a generic reordering.** Against donor guidance the guide gains 19 units and
  loses 3; against the hand rule it gains 35 and loses 4.
- **Transfer across benchmarks is partial.** The guide trained without 1D-ARC fits 245 of its 283 units at 500 (the
  hand-set order 183, the cross-fitted guide 258).
- **At 20,000 the orders agree wherever the cap never binds.** On the 342 units with no capped hole, the two orders
  give the same fit and the same retried candidate on every unit. On the 83 units with a capped hole, 8 retried a
  different candidate and 3 lost their fit (298 against 295).
- **The guide's order is worse on ConceptARC and Mini-ARC at small budgets** (18 and 8 against 21 and 9 at 500):
  most training blocks come from 1D-ARC.

## 6. Limits

These are development numbers on the source halves, which are also the full model's training data; the cross-fitted
estimates hold the unit's own fold out but not its family. A unit is fitted on its demonstrations, so a fit is not a
correct answer; correctness is measured once, on the held run. Operations are the step's capped quantity; the work
inside an operation and the pair analysis are not capped and show in CPU (the held run records it per arm and hole).

## 7. Compute

About 21 CPU-minutes on Athe of the 2 CPU-hours allowed (pass 1: 849 s; models: 47 s; sample check: 69 s; curves
and retries: 211 s; smoke tests and summaries: about 60 s), at most two processes, each through
`scripts/with_cpu_slot.sh` at nice 19.

## 8. Implementation notes for the reviewers (step 4)

- **Shared work in the held run.** The reference call builds its holes inside the frozen function; the arms share a
  second computation of the same holes (the controller's sketches are deterministic under the seed-independent
  builder). The base search runs once, inside the reference call, and every arm takes its result.
- **Retries.** One cache per worker, keyed by (task, candidate), seeded with the reference's own retries (their fits,
  and the attempts and program of the fitting one), so the hand-set arm at 20,000 and the reference use the same
  retry results even where a search stops on CPU time.
- **Features** are rounded to 5 decimals in the held run, as in the training records.
- **Donor guidance.** When the donor has fewer holes than the task, the donor's last hole is used.
- **Abort rule.** As in the frozen step, once a single-rule block meets the cap check, no later single-rule block
  and no two-rule block of that view runs; once the counter passes the budget, no later block runs (the frozen step
  would still walk them but could apply no operation, so candidates and operation counts are the same).
- **Smoke test and gate refusal check** (`launch/smoke_test.py`; records `checks/SMOKE_TEST.json`,
  `checks/GATE_REFUSAL.json`): the candidate package, unpacked on Athe, runs every set in rehearsal mode on source
  stand-ins and passes every check of `gcon/verify.py`; without a GO, with a GO naming another protocol, with one
  frozen file changed, and for the scorer in rehearsal mode, the gate refuses.
- **Amendment 1** (`PROTOCOL_AMENDMENT_1.md`, after the companion's review): the scorer now runs the checks again on
  the exact row bytes it scores and refuses unless the invariant receipt binds to those bytes, the GO, the freeze, the
  protocol, the configuration and the mode, all before the marker and before any solution access (regression tests
  `checks/SCORE_GUARD_TESTS.json`); invariant 1 compares the stage, and rows must carry the split's benchmark and
  family; uncounted work (constructor CPU, segmentations, edit applications, crop-precondition content comparisons;
  the features' CPU and comparisons for the learned arms) is recorded and reported beside the counted operations; the
  model's loss is stated exactly (amendment section 3). All 75 development gains at 500 came through single-rule paint
  candidates, none through a whole-output form.
