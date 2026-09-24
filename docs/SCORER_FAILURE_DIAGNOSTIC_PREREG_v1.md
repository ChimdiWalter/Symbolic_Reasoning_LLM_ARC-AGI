# Scorer-failure diagnostic: preregistration

Written 2026-09-24, before any diagnostic outcome was computed. An earlier
unpreregistered diagnostic script was launched, aborted before it produced a
single fold result, and deleted; its log is preserved at
`logs/scorer_diagnosis_ABORTED_PRE_PREREG.log` and contains only header lines.

This block diagnoses why the candidate-associated features failed to add
value. It cannot earn a positive result of any kind.

## 0. What is frozen and untouched

The scorer-fit verdict `FAILURE_CONDITIONING_NOT_ESTABLISHED` stands, with its
record at `records/SCORER_FIT_RESULT_20260924.md`, report
`outputs/tti/scorer_fit_v1.json`, weights `outputs/tti/scorer_weights_v1.json`,
checkpoint sha256 `22d02bf0643ad2c2`, preregistration v4 sha256
`14f0bdc7...08be448`, result commit `4c75264`. None of these is modified,
regenerated, renamed or reinterpreted.

The v1.2 corpus is not regenerated. The five controls are not changed. The
official scorer is not retrained.

## 1. Data boundary

Only the 180 admitted **training** episodes of the v1.2 corpus.

The 32 validation episodes are excluded from the core diagnosis. They were
already inspected in the frozen result and cannot serve as a fresh
confirmatory set. The 3 structural-holdout episodes are excluded as evidence.
No ARC development data, no protected holdout, no transfer material, no
lockbox, no Step-B information is read.

## 2. Folds

Sort the 180 episodes ascending by immutable target digest. Episode i is
assigned to fold `i mod 5`. Five folds, each used once as held out. Identical
folds for every readout. No random search and no seed sweep. Every fold is
reported.

## 3. Feature groups, frozen

**DEMO_ONLY**, five: `n_demonstrations`, `mean_cells_changed`,
`mean_fraction_changed`, `palette_introduced_mean`, `palette_removed_mean`.

**CANDIDATE_ONLY**, ten: `frontier_term_count`,
`distinct_frontier_operator_count`, `slot_fit_failed_count`,
`slot_fit_ok_count`, `executed_not_exact_count`, `exact_count`,
`defined_value_signature_count`, `fraction_wrong_mean`, `palette_extra_mean`,
`search_deadline_hit`.

**FULL** is their union, fifteen. The three features already dropped as
constant on the fit set stay dropped.

Central quantity, per fold:

    delta_candidate = heldout(FULL) - heldout(DEMO_ONLY)

## 4. Primary diagnostic metric

Mean per-token teacher-forced target log-likelihood on the held-out fold,
the same metric as the frozen result. Higher is better. All models use the
same grammar-state inputs, the same legality mask and the same objective.

## 5. Reproducibility criterion, frozen before any run

A feature group is credited with incremental value only if

    delta > 0 on at least 4 of the 5 folds, AND mean delta >= 0.01 nats/token

The threshold 0.01 is fixed here and is not derived from any result. The same
criterion is applied to every comparison in this document.

## 6. Diagnostic models, both bounded

**M1**: the existing state-conditional log-linear model, unchanged.

**M2**: one hidden layer, 32 tanh units, well inside the frozen ceiling of
256. Inputs, mask and objective identical to M1. Deterministic initialization
by the fixed rule `w[i][j] = 0.1 * sin(9973*i + 101*j)`, which uses no random
number generator and therefore no seed. No architecture search, no comparison
of hidden sizes, no tuning after results.

Both models train full batch, learning rate 0.5, L2 1e-3, for exactly 400
epochs, with no early stopping, so every configuration receives identical
budget. The epoch count is reduced from the official 2000 purely to bound
compute across 30 fits and is fixed here in advance.

## 7. Readouts, all under the same folds

R1 **floor**: no evidence, state inputs only.
R2 **DEMO_ONLY**, R3 **CANDIDATE_ONLY**, R4 **FULL**, each under M1 and M2.
R5 **RAW_TFG**: a richer deterministic descriptor, section 9, under M1 and M2.
R6 **conditional permutation**, section 8.

## 8. Conditional permutation law

Within each held-out fold, pair every episode with the nearest other episode
in the fold by Euclidean distance over the standardized DEMO_ONLY vector,
standardized using the training folds only, with ties broken by ascending
target digest. Substitute only that neighbour's CANDIDATE_ONLY vector. The
target label is never substituted, and DEMO_ONLY is never substituted.

Compare FULL with real candidate features against FULL with conditionally
permuted candidate features, under the section 5 criterion. This asks whether
candidate identity contributes anything once comparable demonstration
statistics are held fixed.

## 9. Richer raw descriptor, readout only

Built only from fields already present in the stored `full_engine_tfg`, with
no new semantic labels, no task identifier, no family label and no target
information:

- frontier operator identities, bucketed deterministically into 16 buckets by
  `sha1(op) mod 16`, counted;
- counts of each of the six candidate outcome names;
- minimum, mean and maximum `surface_nodes` over frontier terms;
- count of distinct frontier operators;
- from defined value signatures: count, and the mean, minimum and maximum of
  `cells_wrong`, `fraction_wrong` and `palette_extra`;
- count of value signatures whose shape did not match;
- the search execution counters already stored.

This descriptor exists only to answer whether the ten-feature summary discards
information the graph already carried. It is not promoted into inference in
this block.

## 10. Redundancy and collision audit

For each candidate feature, fit a least-squares predictor from DEMO_ONLY on
the training folds and report held-out residual variance as a fraction of
total variance. Report each candidate feature's variance, its fraction of zero
values, the correlation matrix among candidate features, and the correlation
of each candidate feature with each demonstration feature.

Report the number of distinct CANDIDATE_ONLY vectors among the 180 episodes,
the number of collisions, and within each colliding group the number of
distinct target digests and distinct structural families. This measures
whether materially different graphs collapse onto the same summary.

## 11. Contrast-pair audit

Using the section 8 nearest-neighbour law, fixed before candidate features are
inspected, report for every pair: the DEMO_ONLY distance, the CANDIDATE_ONLY
distance, the raw descriptor distance, whether the targets differ, and the
token-level edit distance between targets. Report how many pairs have near
identical demonstration evidence but different targets, since those are
exactly the cases the frontier could disambiguate.

## 12. Generator dominance audit

Held-out predictability of the target from DEMO_ONLY alone, reported for the
first partition token, the first feature token and the block count, against
the majority-class baseline. This asks whether the corpus generation law made
the target recoverable from demonstration statistics, which would make a
larger scorer the wrong response. The target digest is never an input, and
nothing here licenses building a family classifier into the system.

## 13. Decision classes, frozen

**A MODEL_CAPACITY_LIMIT**: `delta_candidate` meets the section 5 criterion
under M2 and fails it under M1.

**B MODEL_VIEW_COMPRESSION_LOSS**: `delta_candidate` fails under both models,
and the raw descriptor against DEMO_ONLY meets the criterion under at least
one model.

**C CANDIDATE_SIGNAL_REDUNDANT_ON_V12**: `delta_candidate` fails under both
models, the raw descriptor also fails under both, and DEMO_ONLY beats the
evidence-free floor by the same criterion.

**D MIXED_OR_INCONCLUSIVE**: anything else. D is a permitted outcome and is
not to be avoided by reinterpretation.

## 14. Claim ceiling

This block can establish only why the frozen discrimination test failed, to
the extent the diagnostics support one mechanism. It cannot earn
failure-conditioned selection, constructive reach, autonomous construction,
semantic extension, transfer or any score.

It produces no solver, no dispatch, no hand-authored operator, no answer
predictor and no lookup. The diagnostic models are diagnostic only and are not
part of any submitted system.

## 15. Stop

Diagnosis only. The recommended repair is named and not implemented. The
extension compiler stays blocked.
