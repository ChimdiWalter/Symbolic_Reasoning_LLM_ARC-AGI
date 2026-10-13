# CORA / ARC-AGI-2: leaderboard methods audit and competitive extension (2026-10-13)

**Status: DRAFT, in progress.**

The audit follows the user's directive "Leaderboard methods audit and
competitive extension" of 2026-10-13. Nothing in it changes native_v1, the
Kaggle submission, Step B, VDCG, the frozen pilot, or any historical P2/P3
result.

**Sections still pending:**
- the competitor-method survey (sections 1-3): a delegated web review is
  running;
- the contamination audit (section 4);
- the ranked plan (sections 6-13).

## 14. Current Kaggle baseline status (verified 2026-10-13)

- **Submission 57144804.** Notebook
  `chimdiwalter/cora-native-v23-arc-agi-2-october-baseline` version 1;
  dataset `chimdiwalter/arc-native-baseline-v1` version 1.
- Submitted 2026-10-13T13:17:12Z. **Score PENDING.** No newer submission
  exists. The July submission 54617562 scored 0.00.
- **Expectation, stated before the score:** at or near 0%. The frozen v23
  baseline records 0 of 120 on the public ARC-AGI-2 evaluation set
  (`records/FRONTIER_AUDIT_SELECTION_RULE.md`,
  `records/KAGGLE_NATIVE_V1_DELIVERY_20261012.md`).
- **Public test set vs private.** The public leaderboard uses "a
  representative sample of the test data". The private leaderboard alone
  decides the final standing (rules, section 7). Winners are announced
  2026-12-04.

## 8 (part). Native gap audit on permitted data (`scripts/native_gap_audit.py`)

**Data:** the competition's visible stand-in `arc-agi_test_challenges.json`
(training pairs and test inputs only) and native_v1's own committed-run rows.
No answer was read.

**The stand-in is ARC-AGI-2 training data.**
- All 240 stand-in task ids are in the public ARC-AGI-2 training challenges
  (1,000 tasks), with identical training pairs. None matches any of the 120
  public evaluation tasks, by id or content.
- The data page's note ("a placeholder using tasks from
  arc-agi_evaluation-challenges.json") does not describe the file actually
  served.
- **So the committed run used tasks from the set CORA was developed on.** Its
  behaviour there is optimistic and does not predict the hidden score.

| shape rule implied by the demonstrations | tasks | certified (harness "solved": train-exact plus LOO; no answers were available to it) | no candidate |
|---|---|---|---|
| same size as input | 169 | 93 (55%) | 76 |
| one constant output size | 38 | 14 (37%) | 24 |
| other size change | 29 | 6 (21%) | 23 |
| scaled | 4 | 1 | 3 |
| **all** | **240** | **114 (47.5%)** | **126** |

- **Shape consistency.** Every produced candidate has the output size the
  demonstrations' rule implies (113 checkable outputs: 95 same, 17
  constant, 1 scaled). The native solver does not emit wrong-size grids. It
  emits nothing.
- **Output shape is not the dominant blocker.** 76 of the 126 no-candidate
  tasks (60%) keep the input size. Size-changing tasks are certified about
  half as often (21 of 71, 30%, against 55%).
- **Close misses.** In the no-candidate tasks the best near-solve fits a
  median 78% of training pixels, and 31% of them fit at least 90%.
- **Certifying layers:**
  - loo_replace 56;
  - adaptive_synthesizer 25;
  - object 9;
  - meta_reasoning 8;
  - adaptive_reasoner 5;
  - reasoning_v2 3;
  - spatial_reasoner 2, composable_reasoner 2, different_shape 2;
  - object_correspondence 1, geocat 1.
- **Not measurable from permitted data:**
  - correctness of any candidate;
  - wrong output dimensions among wrong answers (there are no answers);
  - missing global structure, diagonal relations, multi-object dependencies.

  These need a labelled permitted fixture: an ARC-AGI-2 training subset never
  used to tune v23, if one can be shown to exist, or a synthetic corpus.

## 5 (part). What CORA has, for the gap analysis

- **Object representation:** seven segmentation views (S1-S7), a four-view
  cap, cross-variant parsimony, correspondence and typed parameter classes.
- **Whole-grid representation:** pixel-rule and table layers (for example
  the leave-one-out `neighbor_pattern` lookup programs), a geocat layer, and
  a spatial reasoner. There is no learned whole-grid model.
- **Candidate generation:** the typed DSL search per layer; the
  object-reasoning partial is the second attempt.
- **Program synthesis:** symbolic. No neural prior is active in the sealed
  chain; GuideNet and the TRM are off by default.
- **Synthetic pretraining and test-time training:** none in the native
  solver.
- **Output-shape prediction:** shape-change layers (for example
  `different_shape`); no separate shape predictor.
- **Recursive refinement:** none.
- **Candidate ranking:** the parameter-class rank and winner key; no
  learned ranking.
- **Two-attempt selection:** attempt_1 is the certified render, attempt_2
  the best uncertified object partial, and the fallback is the test input.
- **Ensembles:** none across paradigms.
- **Independent verification:** train-exact plus adaptive leave-one-out
  certification. This is CORA's distinctive strength.
- **Compute:** CPU only, 4 workers, 4.03 h for 240 tasks on Kaggle. Kaggle
  offers L4x4 GPUs (96 GB); the native solver uses none.
