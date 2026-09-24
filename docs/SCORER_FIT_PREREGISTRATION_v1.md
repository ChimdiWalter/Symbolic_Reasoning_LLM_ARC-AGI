# Stage-B scorer fit: preregistration

Written 2026-09-24, before any fitting code was written and before any score
was computed. It fixes the evaluation strategy, the split, the model, the
controls, the metric and the success rule. None of these may be changed after
seeing a result.

Corpus: the v1.2 constructive corpus, 215 admitted episodes, audited PASS on
all eleven frozen criteria. Protocol sha256 `31a74764...bbe6bb98`.

## 1. The holdout decision, taken prospectively

The v1.2 structural holdout admitted 3 episodes of 90 slots, all of family
`(2,1)`, with family `(2,)` admitting none. Three episodes cannot support a
structural-family held-out test. The protocol predicted this before
generation, so it is a known limitation rather than a discovery.

Two options were available. Option A uses a held-out split of the training
families and states plainly that structural-family generalization was not
measured. Option B preregisters a v1.3 designed to make the holdout families
reachable.

**Option A is chosen.** The reason is scope: the question this fit answers is
whether real failure evidence changes what is constructed, and that question
does not require a structural-family holdout. Option B is a separate
experiment and remains available later.

The consequence is stated once here and repeated in every report of this
result: **structural-family generalization is not measured by this
experiment.** Nothing in it licenses a claim about families the model never
saw. The three structural-holdout episodes are reported as a secondary,
explicitly underpowered observation and take no part in the verdict.

## 2. Split, fixed by a deterministic content rule

**Amended 2026-09-24, prospectively, before any fit was run and before any
score existed.** The original version of this section carved the
discrimination test out of the training episodes and used the 32 corpus
validation episodes for early stopping. The instruction is now to use the 32
validation episodes as the same-family discrimination set. That choice is
taken before any result, so it is a legitimate amendment rather than a
revision after data. The superseded version is preserved in git history at
commit 41ac7bc, whose document hashed to
`ed4ac9d2109e499aed0311b86e553db804ba597316a5dee17f3ad7be207dc860`.

The 180 admitted training episodes are sorted ascending by target digest,
which is content-derived and independent of generation order.

| set | rule | size |
|---|---|---|
| discrimination test | the 32 admitted corpus-validation episodes | 32 |
| early stopping | every 5th training episode by digest, from index 0 | 36 |
| fit | the remaining training episodes | 144 |

The discrimination test set is never used to fit weights and never used for a
stopping decision. That is the property that makes it a valid held-out
measurement, and it is stricter than the original plan, under which the
validation episodes influenced when fitting stopped.

**Recorded departure.** The v1.2 corpus split law says validation is used
only for early stopping and permitted model selection. This amendment uses
those episodes as the held-out discrimination set instead, and takes early
stopping from an inner split of the training episodes. The departure is
recorded rather than silent. It does not weaken the measurement: validation
digests are disjoint from training digests, verified in the corpus audit, so
the discrimination set remains genuinely unseen.

Structural-family generalization is still not measured, for the reason in
section 1. Both the fit set and the discrimination set are drawn from the
same five training families.

## 3. Model

The minimal member of the frozen model family: a log-linear conditional
model over grammar-legal tokens, with the grammar state machine supplying the
mask. Non-LLM. No hidden layer, which is permitted because the frozen
specification sets hidden size at most 256 as an upper bound rather than a
requirement.

Parameters: for each of the 21 grammar terminals, a bias and one weight per
allowlisted feature, giving 21 times 19, that is 399 parameters.

Features: exactly the 18 frozen allowlisted features, no others. Booleans map
to 0 and 1. Each feature is standardized to zero mean and unit variance using
statistics computed on the fit set alone, with standard deviation floored at
1e-6. Those statistics are frozen after the fit set is formed and are applied
unchanged to every evaluation set and every control.

Objective: teacher-forced conditional log-likelihood of the target token
sequence, normalized at each step over the grammar-legal tokens only.

Optimizer: full-batch gradient ascent, learning rate 0.1, L2 penalty 1e-3,
weights initialized to zero so the untrained model is exactly uniform over
legal tokens.

Stopping: at most 2000 epochs, or a 200-epoch plateau in early-stopping
exact-at-five, evaluated every 25 epochs. This is the frozen stopping law.

## 4. Decoding

The existing proposer, unchanged, with the fitted weights installed. Beam 16,
top five, the frozen ranking rule. The proposer receives the evidence vector
and the typed interface, and never the target, its digest, its family label,
the split, the seed or any generation metadata.

## 5. Controls, all five, constructed deterministically

Evaluated on the same 36 held-out episodes, sorted by digest, index i.

| control | evidence supplied |
|---|---|
| associated | episode i's own feature vector |
| shuffled | the feature vector of held-out episode (i+1) mod 36 |
| irrelevant | the feature vector of fit episode (i times 7) mod 144 |
| aggregate only | episode i's vector with every candidate-associated feature zeroed |
| none | the all-zero vector |

The candidate-associated features zeroed for the aggregate-only control are
frontier_term_count, distinct_frontier_operator_count, slot_fit_failed_count,
slot_fit_ok_count, executed_not_exact_count, exact_count,
defined_value_signature_count, fraction_wrong_mean, palette_extra_mean and
shape_mismatch_count, with empty_frontier set true. The seven retained
features are the demonstration statistics and the deadline flag.

Every control decodes with the identical fitted model, the identical beam and
the identical ranking rule. Only the evidence vector differs.

## 6. Metric and success rule

Primary metric: exact-at-five, the fraction of held-out episodes whose target
digest appears among the five proposed candidates. Exact-at-one is reported
alongside it.

**Success requires both of these, on the 36 held-out episodes:**

    exact@5(associated) > exact@5(shuffled)
    exact@5(associated) > exact@5(aggregate only)

Strictly greater. No tolerance band is defined, and none may be introduced
afterwards. Irrelevant and none are reported for completeness and do not
enter the success rule, because shuffled and aggregate-only are the
demanding comparisons.

Secondary diagnostic, frozen now and reported whatever it shows: the number
of distinct rank-one target digests across the 36 held-out episodes under
associated evidence must be at least 5. This exists because the unfitted
proposer produced a single rank-one candidate across five real tasks, and
this is the measurement that would detect that failure persisting. It is
reported as a diagnostic and is not part of the primary success rule.

## 7. What a pass and a failure each license

A pass licenses exactly one next action, implementing the already-specified
ConstructiveExtensionCompiler. It licenses no claim about constructive reach,
capability, semantic extension, transfer or score.

A failure is recorded unchanged. The corpus is not regenerated, the controls
are not dropped, the metric is not swapped, and the threshold is not
softened. A failure would mean the next block designs a prospective
amendment, not a rerun.

## 8. What this experiment cannot show

It cannot show structural-family generalization, for the reason in section 1.
It cannot show that a constructed program solves anything, because nothing is
compiled or installed here. It cannot show anything about ARC score. It is a
measurement of whether failure evidence changes what is proposed, and nothing
more.
