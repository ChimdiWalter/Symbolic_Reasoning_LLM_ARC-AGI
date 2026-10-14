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

## Matched extra search: budget ×3 (COMPLETE, Oct 14)

**Scope.** The 29 dev60 tasks whose search or a LOO fold hit its deadline:
- the cooperative and frame budgets ×3;
- CPU clock;
- 7.97 CPU-h against 3.21 at native budget.

| native → ×3 budget | tasks |
|---|---|
| FIT_BUT_ALL_WRONG → FIT_BUT_ALL_WRONG | 14 (none fixed) |
| NO_FIT_DEADLINE → NO_FIT_DEADLINE | 5 |
| NO_FIT_DEADLINE → NO_FIT_EXHAUSTED (search finished, still no fit) | 6 |
| REJECTED_BUT_CORRECT → CERTIFIED_CORRECT | 1 (kf321d635cf9a) |
| REJECTED_BUT_CORRECT → REJECTED_BUT_CORRECT | 1 |
| CERTIFIED_CORRECT → CERTIFIED_CORRECT | 2 |

- **The one gain is not a budget effect.** The native-budget replicate also
  certified kf321d635cf9a correctly; it is a borderline task.
- **Overall:** 0 robust gains, 0 losses and 0 false acceptances, at 2.5× the
  CPU. More search is not the fix.

## Reproducibility: native-budget replicate of 29 tasks (`native_rep`)

- **Candidates.** The identity-frame first-search candidates were identical
  in 28 of 29 tasks.
- **Categories.** 26 FIT_BUT_ALL_WRONG reproduced. One task flipped to a
  native exception, and kf321d635cf9a flipped from rejected to certified.
- **Oracle replicate.** Identical table.

## Structural contrast (COMPLETE, Oct 14)

**What generates the spurious fits.** 25 FIT_BUT_ALL_WRONG tasks have
recorded program structure.
- **Parameter class.** The rank-1 spurious programs are constant-parameter
  in **21 of 25** (induced_map 2, relational 1, feature 1).
- **The dominant form is GROW with a constant cell-offset pattern:** 54 rule
  instances in **19 of 25 tasks**. Translate and recolor occur in 3 tasks
  each.
- **Constant parameters:** the grow mode/pattern 54, colour 28, vector 6.
- **Selector features:** colour 27 and **exact shape signature 18**.

These programs memorize the drawn cells per case; they are not a rule.

**What the failed folds rebuild.** Of 74 failed identity-frame LOO folds:
- 59 rebuilt a *different* structure, again constant-parameter;
- 11 rebuilt a different structure of another kind;
- only 4, in 2 tasks, kept the skeleton and changed the constants.

So each demonstration subset yields a different memorizing program. Caveat:
the stored JSON is capped at 4,000 characters, but differences inside that
prefix are real.

**The oracle, reread.** The answer-consistent programs are constant-parameter
in the same 21 of 25 tasks. Where rule counts are measurable, they usually
add one rule (7 of 9). The oracle's "expressible" therefore mostly means
"native can memorize one more case". It does not show that a generalizing
rule is in the language. The "same view" finding (24 of 26) stands.

**Native's own revision fails.** Phase C (`inducer.py`) is triggered when a
flat program with constant or map parameters fails LOO. It re-searches with
`force_relational=True`. It ran in 11 of 27 tasks at native budget and in 8
of 14 at ×3 budget, and **returned no program in any of them**.

**Existing constructor coverage.** The reach-v1 census of the same 60 tasks
(`outputs/reach_v1/grammar_coverage.json`) tested the 9 frozen `cora_reach`
growth families. They explain the demonstrated growth in **5 of 27**
FIT_BUT_ALL_WRONG tasks and in 0 of the other 33:
- connect: 2;
- window_fill: 1;
- bbox_fill: 1;
- one task explained by band, bbox_fill or dilate.

## Synthetic funnels (SYNTHETIC; CPU clock)

| corpus | certified correct | certified wrong | REJECTED_BUT_CORRECT | FIT_BUT_ALL_WRONG | no fit | gate-off correct / wrong |
|---|---|---|---|---|---|---|
| C3-dev (25) | 10 | 0 | 5 | 3 | 7 | 14 / 4 |
| C2-dev (60) | 17 | 1 | **16** | 5 | 21 | 32 / 7 |

- **On synthetic families, unlike real tasks, LOO is conservative.** It
  rejects a correct candidate in 16 of 33 C2-dev tasks where one exists.
  These are 3-demonstration families where each demonstration carries
  unique evidence.
- **The C2-dev oracle:** all 16 REJECTED_BUT_CORRECT are expressible; the
  no-fit tasks are mostly undetermined (13) or no fit within bounds (6).

## Arbitration shadow, replicated (C2-dev, SYNTHETIC)

| policy | exact |
|---|---|
| frozen | 31 / 60 (matches the ceiling test's arm A) |
| object-certificate-first | 36 (+5, 0 lost) |
| conservative attempt_2 | 36 (+5, 0 lost) |
| complementarity | 39 (+8, 0 lost) |

**Harness–funnel object-certification agreement:** 56 of 60. The harness runs
on the wall clock under load, so 4 certifications differ.

**Availability in the deployment path.**
- The object layer's certified render exists inside the harness worker
  (`run_object_task` returns it). It is discarded at the merge when the
  pipeline claims first, so policies B and C need a change to the merge,
  which means a new native version.
- The rank-1 uncertified candidate used by D is not exposed by native.

This remains an engineering result. No submission is justified on 2 + 5
development tasks.

## Verdict (evidence complete, Oct 14)

1. **Certification is not the real-ARC bottleneck.** The object layer
   accepted 0 wrong answers. Removing LOO would add 2 correct and 26 wrong
   on dev60. (On synthetic C2-dev it is conservative: 16 rejections.)
2. **The dominant real-ARC failure is rule induction by memorization.**
   - In 27 of 60 tasks, native fits the demonstrations with constant-
     parameter rules, mostly GROW with memorized cell patterns keyed to
     colour or an exact shape. These rules change with every demonstration
     subset and never generalize.
   - Its own relational revision finds no alternative (0 of 11).
   - More search does not help (0 of 14).
   - The existing growth grammar covers 5 of the 27.
3. **The second failure is matching.** 17 of 22 no-fit tasks stop at object
   correspondence. Neither the answer nor ×3 budget helps.
4. **Excluded as primary:**
   - representation (24 of 26 already in the right view; 1 of 60 has no
     coherent view);
   - candidate selection (no correct candidate to select in 27 tasks);
   - premature certification on real tasks (2);
   - search budget.

**The single intervention this justifies.** Failure-conditioned construction
of a **derived executable pattern operator** for GROW. This is CORA-FHR
whose construction step is a bounded typed operation extension.
- **Trigger, from inference-time evidence only:** a constant GROW pattern
  that LOO cannot rebuild.
- **Construction:** from a declared bounded grammar of pattern derivations
  over object geometry and context, compositional and reusing the
  `cora_reach` families and the extension compiler.
- **Installation:** fold-locally.
- **Verification:** native re-induction plus full adaptive LOO.
- **Controls:** matched search, failure-blind construction and shuffled
  failure evidence.

It targets the largest measured failure (19 of 25 analysable tasks). It
changes one component (the GROW parameter), and native's own revision has
been shown not to reach it.

**Open risk, stated now.** Coverage by the current growth grammar is 5 of 27,
so the declared grammar must grow, and that grammar must be fixed before the
prospective corpus is built. A positive result would be compositional growth
(L2), not a new primitive, unless a bounded-language novelty test says
otherwise.

## Asset audit (2026-10-14, 21:17Z): the submitted configuration

`cora_funnel.run --mode native_assets` loads the frozen library (cdacd018) and learned verbs (b1f07ba5)
through `cora_pilot.native.prepare_object_dir`, as the harness and the Kaggle notebook do.

| category | without assets (headline) | with assets |
|---|---|---|
| CERTIFIED_CORRECT | 6 | 6 |
| FIT_BUT_ALL_WRONG | 27 | 26 |
| NATIVE_ERROR | 1 | 2 |
| NO_FIT_DEADLINE | 11 | 11 |
| NO_FIT_EXHAUSTED | 11 | 11 |
| NO_SEARCH | 2 | 2 |
| REJECTED_BUT_CORRECT | 2 | 2 |

**The one change** is `kd506f38dd7d6`, from FIT_BUT_ALL_WRONG to NATIVE_ERROR. It is a
`ValueError("invalid literal for int() with base 10: 'h'")` in `_induce_composed`, in every frame:
an asset-triggered parsing defect in the frozen native engine. It is recorded, not fixed, because
native v23 is frozen.

The correct count stays at 6 of 60, and the funnel's conclusions are unchanged:
- memorization dominates;
- the verifier is precise;
- more search does not help.

Sources: `outputs/funnel_v0/eval_dev60_native_assets.json`, `outputs/funnel_v0/eval_assets.out`.
