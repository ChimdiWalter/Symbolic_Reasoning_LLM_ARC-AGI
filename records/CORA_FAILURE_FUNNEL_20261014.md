# CORA failure funnel (v0): where native CORA loses real ARC tasks

**Label: DEVELOPMENT.**
- **Tasks:** the 60 authorized pilot development tasks, which are real
  ARC-AGI-2 training tasks (`records/pilot_v1/dev_bundle.json`; strata n3 45,
  n4 11, n5p 4).
- **Exposure:** CORA was developed on the training split, so this is not a
  generalization result. It locates the failing stage.
- **Status of this record:** the object-layer funnel is COMPLETE
  (2026-10-13, 22:12Z). The whole-harness section is COMPLETE (23:29Z). The oracle and matched-search
  sections are PENDING; the detached driver is running them
  (`outputs/funnel_v0/driver_status.json`).

## Method (cora_funnel/, commits ed3d0fd to 0f2d209)

**What runs.** The frozen native object layer, `harness.object_layer.run_object_task`,
with:
- the sealed v23 flags;
- the 90 s budget;
- the 7 dihedral frames at 45 s each;
- the harness cap of 450 s.

Native code is unchanged. A read-only probe records each top-level
search, the leave-one-out (LOO) folds, the LOO verdicts, native's ranking
and the generative fallback. It restores every patched name on exit.

**Blindness.** The solver receives exactly the source demonstrations and
the true test inputs (content-level test, `tests/test_funnel.py`). Only the
evaluator reads answers: the evaluator-only key map, then the sha256-pinned
training solutions. Every train-exact candidate is rendered on the test
inputs after the task ends and scored by the evaluator.

**Clock.** Athe was about 2× oversubscribed (40–49 runnable threads on 24
cores). Native deadlines are wall-clock, so they would have measured
machine load. In the funnel's own workers, every native deadline and the
cap therefore run on process CPU time. This emulates the dedicated core
each Kaggle worker had. The median CPU share was 0.95, and no task was
starved below 0.7.

**Categories** (mutually exclusive):
- certified correct or wrong;
- REJECTED_BUT_CORRECT: a train-exact candidate was correct but not
  certified;
- FIT_BUT_ALL_WRONG: train-exact candidates exist, none correct;
- NO_FIT_DEADLINE and NO_FIT_EXHAUSTED: no candidate, with the search ending
  at or before its deadline;
- native defects.

## Result (object layer, 60 tasks)

| stage / outcome | tasks |
|---|---|
| S1: no native view coherent on the demonstrations | 1 |
| S3: hypotheses enumerated > 0 | 57 (median 8.8 M per task) |
| S4: a candidate fits every demonstration | **35** |
| S5: certified by LOO | **6** |
| S6: certified and correct on held-out | **6** |
| **certified and wrong (false acceptance)** | **0** |
| **REJECTED_BUT_CORRECT** (a correct candidate failed LOO) | **2** |
| **FIT_BUT_ALL_WRONG** (2–105 train-exact candidates each, none correct) | **27** |
| NO_FIT_DEADLINE | 11 |
| NO_FIT_EXHAUSTED (search ended before its deadline) | 11 |
| native defect: exception in the search (KeyError('window'), reported by native as a segmentation failure) | 1 |
| native defect: the first search overran its 90 s budget to the 450 s cap | 2 |

- **Candidate recall.** A correct program was among the generated
  train-exact candidates in **8 of 60** tasks. No candidate set was larger
  than the 24 rendered, so every candidate was scored.
- **Gate-off counterfactual** (native's rank-1 candidate, committed without
  LOO; a measurement, not a policy): **8 correct, 26 wrong.** LOO turns that
  into 6 correct and 0 wrong.
- **Cost.** 4.9 CPU-hours in total; the median task used 398 CPU-s, near the
  cap.

## Why candidates fail LOO (76 failed identity-frame folds)

| measure | failed folds | passed folds (control) |
|---|---|---|
| the fold rebuilt another train-exact rule that mispredicts the left-out pair | 75 | — |
| the fold rebuilt nothing | 1 | — |
| the fold hit its deadline | 5 | — |
| admission mismatch: the full-data winner's view was not among the fold's admitted views | 7 | 0 of 24 |
| the left-out pair has a colour no other pair shows | 43 (57%) | 12 (50%) |

- **FIT_BUT_ALL_WRONG.** The first LOO passed 0 of 3 folds in 24 of 27
  tasks. The spurious rules do not even predict the other demonstrations, so
  rejecting them is correct.
- **The two REJECTED_BUT_CORRECT cases.** Each failed exactly one fold: the
  one leaving out pair 2, which carries evidence (a colour) the other pairs
  lack. In one, the fold rebuilt nothing; in the other, it rebuilt another
  rule.
- **Admission mismatch at scale.** The admission-mismatch mechanism of
  `records/LOO_V1_DIAGNOSIS_20261012.md` is real but minor here: 7 of 76
  failed folds.

## Where the no-fit searches stop (22 tasks)

- **Stage.** The identity search's failure stage is **matching** in 17,
  parameter in 3, selector in 1 and segmentation in 1. Matching is the
  correspondence between input and output objects.
- **Partial fit.** The median fraction of objects explained is 0.36
  (deadline) and 0.50 (exhausted).
- **Perception.** Most of these tasks had 4–7 coherent views. A few had only
  1–3.

## Reading so far

**Observations.**
- On real development tasks, native's certification is **not** the
  bottleneck. It accepted nothing wrong. It rejected a correct candidate
  only twice, while rejecting the spurious candidates of 27 tasks.
- Removing it would add 2 correct and 26 wrong commitments.

**The dominant failure is generating a generalizing hypothesis.**
- In 27 of 60 tasks, the native language and search produce many programs
  that fit every demonstration (median about 32), and none is the rule.
- In a further 22 tasks, no program fits; most stop at object matching.

**Not yet established (hypotheses).**
- Whether a correct rule is reachable in the native space at all. The
  pending oracle probe appends the answer as a demonstration; a failed
  bounded search would still not prove inexpressibility.
- Whether more search helps: the pending budget ×3 step.
- How the whole harness behaves on the same tasks: the pending
  whole-harness step. On synthetic C2 the pipeline layer, which answers
  first, accepted 53 wrong of 100 (`records/C2_CORA_ONLY_SCORE_20261013.md`).

## Whole native harness on the same 60 tasks (COMPLETE, 23:29Z)

**Method.** `cora_funnel/harness_run.py` ran the frozen native_v1 notebook
unchanged, with blind input, in 4,652 s on 4 workers. The harness's own
budgets are wall-clock under shared load, as in the C2 and ceiling runs;
that is a caveat.

| measure | tasks |
|---|---|
| exact under the two-attempt rule | **12 / 60** (object layer alone: 6) |
| claimed by some layer | 29 |
| claimed and correct | 11 |
| **claimed and wrong** | **18** (62% of claims) |
| unclaimed but correct (the object layer's uncertified attempt_2) | 1 |

**Pipeline sub-layer, for attempt_1 of every task the pipeline claimed:**

| sub-layer | correct | wrong |
|---|---|---|
| loo_replace | **0** | **15** |
| adaptive_synthesizer | 5 | 1 |
| fill_solver | 2 | 0 |
| adaptive_reasoner | 0 | 2 |
| reasoning_v2 | 0 | 1 |

**Answer order loses certified answers.** In **2 tasks** the object layer's
LOO-certified answer was correct (CERTIFIED_CORRECT in the funnel). The
pipeline also claimed those tasks; its wrong render became attempt_1 and the
correct certified answer was not submitted.

**Reading.** At the whole-harness level the failure is **false acceptance**
by the pipeline layer. It answers first; loo_replace alone produced 15
wrong claims and none right. Meanwhile, the one layer with adaptive LOO by
re-induction (the object layer) accepted nothing wrong. This matches the
synthetic C2 picture (53 of 100 claims wrong).

## Oracle expressibility probe (COMPLETE, 00:44Z Oct 14)

**ORACLE: evaluator-side; never a prediction.** Each held-out answer pair
was appended as an extra demonstration. The same frozen native object layer
then ran (CPU clock, same budgets) on the 51 tasks in the four failure
categories below (`oracle_dev60.json`).

| native category | expressible within budget | no fit within bounds | undetermined (deadline) |
|---|---|---|---|
| FIT_BUT_ALL_WRONG (27) | **26** | 1 | 0 |
| REJECTED_BUT_CORRECT (2) | 2 | 0 | 0 |
| NO_FIT_EXHAUSTED (11) | 0 | 9 | 2 |
| NO_FIT_DEADLINE (11) | 0 | 1 | 10 |

**Same view, different rule.** Of the 26 expressible FIT_BUT_ALL_WRONG
tasks, the answer-consistent fit came from **the same frame and segmentation
view as native's spurious first fit in 24**; only 2 changed view. The two
REJECTED_BUT_CORRECT tasks were the same.

**Certification under the oracle is not informative.** No oracle run was
certified except one REJECTED_BUT_CORRECT task. This is expected by
construction: the fold that leaves out the appended answer is the original
problem, which fails.

**Reading (observation, then hypothesis).**
- **For 26 of 60 tasks**, native's executable language and search contain a
  rule consistent with the answer, in the view it already chose.
- From the real demonstrations alone, its rule induction returns spurious
  rules first and never reaches the answer-consistent one.

So the dominant addressable gap is at the **rule level**: selector, action
and parameters. It is not perception, and not verification. This favours
failure-conditioned hypothesis revision (CORA-FHR) over new representations
(CORA-RG).

**The 22 no-fit tasks are a separate, smaller target.** The answer did not
help any of them. In 10 there is no fit within bounds, a candidate for a
missing operation or correspondence (not proof of inexpressibility). In 12
the result is undetermined at the deadline; the budget ×3 step tests these.

## Pending sections

These are filled when the driver finishes.
1. **Matched extra search:** budget ×3, on tasks that hit a deadline.
2. **C3-dev and C2-dev funnels:** SYNTHETIC; their mechanisms are known.
   C2-dev also replicates the arbitration shadow.
3. **Structural contrast** (`cora_funnel/contrast_driver.py`, queued): the
   spurious rules vs. each fold's rebuilt rule vs. the answer-consistent rule,
   for the 29 tasks with fits.
4. **The single bottleneck, and the one intervention it justifies.** Decision
   due Oct 16.
