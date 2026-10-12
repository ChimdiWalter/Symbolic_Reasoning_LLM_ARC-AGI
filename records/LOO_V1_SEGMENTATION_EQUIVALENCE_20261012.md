# Segmentation equivalence and the four-slot cap (2026-10-12)

Status:
- DIAGNOSIS ONLY, at the segmentation and correspondence level. No
  induction was run, no repair was installed and no engine file was edited.
- It follows the post-diagnosis scientific addendum of 2026-10-12, which
  authorizes diagnosis and design only.
- Scope: the 60 development tasks (training demonstrations only, read
  through the isolation hook) and the 24 synthetic negative-control tasks.
- The question was prompted by kf892487f1049, which was examined after its
  failure was seen. The census itself covers every task uniformly.

Sources:

| item | location | commit | sha256 |
|---|---|---|---|
| script | `scripts/loo_v1_probe_equivalence.py` | 4dbfd41, single-process fix 4882e22 | `dc1c664c...` |
| output | `outputs/loo_v1/probe_equivalence.json` | 7d11993 | `90c2a325...` |

## 1. Question and method

The cap keeps the first four coherent views. The question is whether several
views give the reasoner the same input, and so occupy several slots with one
view.

Equal object counts are not enough. Equivalence is computed at five nested
levels, each from the subset's own training pairs only. No held-out pair and
no program is used.

| level | per grid, what must be equal |
|---|---|
| COUNT | the (input, output) object counts |
| PARTITION | the background and the set of object cell sets |
| COLOURED | the background and the objects as cell-to-colour maps |
| TYPED | the ordered object list: id, Python class, colour, cell colours and bounding box |
| INDUCTION | TYPED, plus the engine's own correspondence alternatives (`correspondence.match_pair`, first 6) and the input feature tables (`features.compute_feature_table`) |

Code facts behind the INDUCTION level:
- **Object class changes correspondence.** S3, S4 and S7 build
  `MultiColorObject`; S1, S2, S5 and S6 build plain `ARCObject`.
  Correspondence scores colour differently for the two
  (`correspondence.py:156`). For a multicolour object, same-colour objects
  of different sizes score 0. A plain object uses graded colour similarity.
  So identical coloured partitions can still give different correspondences.
- **The variant's identity is otherwise used only to re-segment a grid
  that a program is rendered on** (`actions.py:945`). Features and
  correspondences read objects, grids and backgrounds; no feature reads the
  variant.
- **INDUCTION-equal views yield the same candidate programs on that
  subset.** The winner key (attempt key, object count, trial order) then
  picks the earlier view. So the engine already ignores a later duplicate's
  programs; the duplicate only takes a slot, and search time before a
  winner exists.

## 2. Findings

**kf892487f1049, the failing pairs.** On demonstration 0, the input is two
single yellow cells and the output is a 5 x 5 yellow square.
- S1 to S5 and S7 see two one-cell objects becoming one.
- S6 sees one two-cell colour layer whose bounding box is the square.

| subset | coherent | searched (cap) | INDUCTION classes | wasted slots | fold-local dedup searches |
|---|---|---|---|---|---|
| (0,2) | all 7 | S1, S2, S3, S5 | {S1, S2, S5}, {S3, S4, S7}, {S6} | 2 | S1, S3, S6 |
| (1,3) | all 7 | S1, S2, S3, S5 | {S1, S2, S5}, {S3, S4}, {S6}, {S7} | 2 | S1, S3, S6, S7 |
| full, every 3-subset, (0,1), (0,3), (1,2), (2,3) | S6, S7 | S6, S7 | {S6}, {S7} | 0 | unchanged |

What this shows:
- **Genuine redundancy exists.** On both failing pairs, S2 and S5 present
  the reasoner with exactly S1's input, down to object type,
  correspondence alternatives and feature tables. The four slots hold only
  two distinct views.
- **Counts, partitions and colours are not enough.** At the COUNT,
  PARTITION and COLOURED levels, S3 and S4 also look identical to S1. At the
  TYPED and INDUCTION levels they are a different view, because they use
  `MultiColorObject` and its correspondence rule.
- **Dedup before the cap would reach S6.** It is computed from the fold's
  two demonstrations alone, with no full-data program as an oracle. It
  would admit S6 on both pairs, and S7 on (1,3).
- **Whether S6 then yields a correct fold program is untested.**

**Equal counts are not sufficient.**

| | development | synthetic |
|---|---|---|
| subsets where equal counts hide distinct reasoner inputs | 177 of 522 | 74 of 96 |
| subsets where identical coloured partitions differ in object type | 167 | 74 |
| wasted slots if judged by counts | 709 | 220 |
| wasted slots at the INDUCTION level | 571 | 156 |

Judging equivalence by counts would overstate the redundancy.

**Redundancy is pervasive.**

| | development | synthetic |
|---|---|---|
| kept slots that duplicate an earlier view (INDUCTION level) | 571 of 1,849 (31%) | 156 of 341 (46%) |
| subsets with at least one wasted slot | 392 of 522 | 83 of 96 |
| subsets where the cap binds | 323 | 74 |

**Dedup is broad, not narrow.** Fold-local INDUCTION-level dedup would
change the searched set on 277 of 522 development subsets and 74 of 96
synthetic subsets.

| view admitted by dedup | development subsets | synthetic subsets |
|---|---|---|
| S6 | 155 | 59 |
| S4 | 125 | 0 |
| S7 | 72 | 71 |

It would change the full-data search of 4 of the 6 natively solved
development tasks:

| task | view added |
|---|---|
| k328b173af636 | S4 |
| k553a7e98f13d | S6 |
| kc8866e481747 | S4 |
| kf105d51e18c5 | S6 and S7 |

It would also change some fold subsets in 5 of those 6 tasks.

## 3. Is a fold-local, certification-preserving repair structurally feasible?

**Structurally, yes.** Canonical deduplication at the INDUCTION level,
before the cap:
- is computed only from the training pairs the induction receives, so it
  respects the validation boundary in every fold, inner and outer;
- leaves unchanged:
  - the eligibility predicate and its threshold;
  - the trial order;
  - the acceptance gate;
  - the leave-one-out procedures;
- cannot change the selected program among exact duplicates, because the
  engine already prefers the earlier one;
- makes the cap bound the number of distinct views searched, which is its
  evident budget role.

**Safety is not shown, and it is not narrow:**
- It admits new views in more than half of the development subsets, mostly
  S6, S4 and the last-resort proximity view S7.
- On ties the winner key prefers the view with fewer objects. So the harm
  channel seen in the negative controls applies: a coarser view's program
  can pass every gate and still be wrong.
- It touches 4 of the 6 native successes at full data.
- Its side-effect channels also include:
  - newly admitted views changing the winner;
  - fewer cheap-first probe slices, and a changed probe-skip condition;
  - time freed by not re-searching duplicates before a winner exists;
  - different near-solve partials passed to composition;
  - removal of timing-noise ties between duplicates.

**Conclusion.** Dedup could recover a view using only the fold's data, and
it preserves certification by construction. Whether it is safe is an open
empirical question with a broad surface. It is not authorized, and it is
not to be tuned toward kf892487f1049.

## 4. What remains untested

- Whether searching S6 on (0,2) and (1,3) yields any program, and which one
  wins.
- Whether any outer fold of kf892487f1049 then passes. Fold f1 still selects
  window_fill, which its held-out demonstration refutes, so the screen is
  again predicted to fail.
- The effect on the 6 native successes.
- The false-acceptance rate on synthetic and adversarial controls.
- CPU cost.
- The coverage losses of section 2 of Clarification 01, under any repair.

## 5. Next proposed experiment: P3, fold-local view deduplication (NOT EXECUTED; design only)

**Implementation, if authorized:**
- A separately versioned overlay on a generated copy of
  `_induce_candidate`, with marked lines and a `--check` equality test. No
  engine file is edited, and pilot v2 and the frozen trees are unchanged.
- It deduplicates the coherent views at the INDUCTION level, in trial order,
  before the cap.
- Everything else is untouched.

**Fixed before any run:**
1. **Static exposure, committed first.** This record's lists of changed
   subsets.
   - Outside them, the program sha, failure stage and acceptance must be
     byte-identical (implementation check S2).
2. **S1, synthetic safety.**
   - Fixtures:
     - the 24 negative-control tasks (same seeds, 20 s);
     - at least 12 new adversarial tasks, generated and committed before
       the run, in which dedup admits a coarser decoy view whose rule is
       train-exact but wrong on held-out demonstrations.
   - Required: 0 new false acceptances and 0 regressions against the same
     engine without P3.
   - Findings are reported per task. The runs are correlated comparisons
     on those tasks.
3. **S3, native successes.** All 6 natively solved development tasks keep
   acceptance and program sha. Any change fails the criterion.
4. **S4, matched resources.** Both arms run under the same `budget_s` and
   the CPU1 clock, and the report gives CPU totals.
5. **E1, mechanism prediction.**
   - On kf892487f1049's inner pairs (0,2) and (1,3), S6 is searched. This is
     certain from the static census.
   - The fold winner reproduces the held-out demonstration. This is a
     prediction, not an oracle.
   - Outer fold f1 still fails. The screen (conditions 1 to 5 on one
     development task) is predicted to FAIL.
6. **Kill rule.**
   - Any failure of S1 to S4 rejects P3, and the rejection is recorded.
   - No tuning, and no fallback repair to make the known case pass.
   - Pilot v2 and the 488 untouched candidates stay untouched whatever the
     outcome.

**Label.** If P3 were kept, it would be a REPRESENTATION CORRECTION (search
layer), never semantic invention.
