# Why the candidate-associated features failed: diagnosis

Run 2026-09-24 under `docs/SCORER_FAILURE_DIAGNOSTIC_PREREG_v1.md`,
sha256 `6e95a7a8d26a8e1f42609b8548cab132b1e1081bb754b0fce461a6e80f4a128e`,
sealed before any outcome was computed. Diagnosis only. The corpus, the five
controls, the official scorer weights and the frozen verdict
`FAILURE_CONDITIONING_NOT_ESTABLISHED` are all unchanged.

180 training episodes, five deterministic folds of 36 by target digest, 400
epochs per fit, 30 fits. Criterion fixed in advance: a group is credited only
if its delta is positive on at least 4 of 5 folds and averages at least 0.01
nats per token.

## Preregistered classification

**CANDIDATE_SIGNAL_REDUNDANT_ON_V12**, by the rule frozen in advance. Section
"How to read that label" below qualifies it, because one supporting audit
points somewhere the label's usual reading does not.

## Held-out mean per-token target log-likelihood

| readout | log-linear M1 | one hidden layer M2 |
|---|---|---|
| floor, no evidence | -1.3413 | -1.2832 |
| demonstration only | -1.3363 | -1.2593 |
| candidate only | -1.3792 | -1.2819 |
| full | -1.4069 | -1.2750 |
| richer raw graph descriptor | -1.4370 | -1.3084 |

## Incremental value against the frozen criterion

| comparison | mean delta | folds positive | meets |
|---|---|---|---|
| M1 candidate over demonstration | -0.0706 | 0 of 5 | no |
| M2 candidate over demonstration | -0.0156 | 1 of 5 | no |
| M1 raw graph over demonstration | -0.1006 | 1 of 5 | no |
| M2 raw graph over demonstration | -0.0491 | 0 of 5 | no |
| M1 demonstration over floor | +0.0050 | 4 of 5 | no |
| M2 demonstration over floor | +0.0239 | 5 of 5 | **yes** |
| M1 candidate only over floor | -0.0379 | 4 of 5 | no |
| M2 candidate only over floor | +0.0014 | 4 of 5 | no |

Adding candidate features does not merely fail to help. It **hurts**, under
both model classes, on nearly every fold.

## Conditional permutation

Replacing each held-out episode's candidate features with those of its nearest
neighbour by demonstration evidence, target untouched, **improves** prediction:
real -1.4069 against permuted -1.3891, a delta of -0.0178 with only 3 of 5
folds favouring the real features.

Candidate identity is not merely uninformative about the target. Substituting
a comparable episode's candidate evidence is better than using the episode's
own.

## The three hypotheses

**H2 model capacity: not supported.** The nonlinear model does not rescue the
candidate features. Its candidate-over-demonstration delta is -0.0156 with 1
of 5 folds positive. A larger scorer is not the missing piece.

**H1 model-view compression: not supported, with one caveat.** All 180
episodes have **distinct** candidate-feature vectors, with zero colliding
groups, so the ten-feature summary is not merging different graphs together.
The richer 42-field descriptor built directly from the stored graph performs
**worse** than demonstration statistics under both models. The caveat is real
and is recorded rather than hidden: that descriptor carries 42 features
against 144 training episodes per fold, so its failure is confounded with
overfitting and does not by itself prove the graph holds no information.

**H3 corpus: supported as "no group carries target information", not as
"demonstration statistics determine the target".** See below.

## How to read that label

The label's usual reading is that demonstration statistics already explain the
target, leaving the frontier nothing to add. The generator-dominance audit
does not support that reading.

Predicting the target from demonstration statistics alone, held out:

| target quantity | accuracy | majority baseline | classes |
|---|---|---|---|
| first partition token | 0.383 | 0.411 | 4 |
| first feature token | 0.183 | 0.161 | 10 |
| block count | 0.967 | 0.961 | 2 |

Demonstration statistics predict the first partition **below** the majority
baseline and the first feature barely above it. They do not determine the
target either.

So the accurate statement is narrower and more useful: **on this corpus, at
this readout, no evidence group recovers the target.** Demonstration features
give a small lift over the evidence-free floor under the nonlinear model, but
that lift does not correspond to predicting the target's actual tokens.
Candidate features behave as noise that both models overfit.

The contrast-pair audit sharpens it. Of the 45 pairs in the closest quartile
by demonstration distance, **45 of 45 have different targets.** The corpus is
full of cases where demonstration evidence is nearly identical and the answer
differs, which is precisely the situation the failure frontier exists to
disambiguate. It does not disambiguate them.

## What this establishes

The frozen discrimination test did not fail because the scorer was too small,
and not because the ten-feature summary threw away distinguishable graphs. It
failed because the failure evidence in this corpus, in either the summary or
the richer form tested, does not carry information about which constructive
target generated the episode.

## What this does not establish

It does not show that a reasoning frontier can never inform construction. It
shows this corpus cannot test that question, because its targets are not
recoverable from its failure evidence by any readout tried here. The raw-graph
test is additionally confounded by its feature count against the sample size.

## Claim earned

None. Diagnosis only. `NEW_AST_GENERATION` remains the standing earned
result and `FAILURE_CONDITIONING_NOT_ESTABLISHED` remains the verdict.

## Next action

Preregister v1.3 as a contrastive corpus, designed so that failure evidence
can in principle identify the target. The concrete requirement the evidence
sets is that the corpus must contain episode groups whose demonstration
statistics are close while their targets differ, **and** whose failure
frontiers differ systematically with the target. The v1.2 corpus satisfies
the first half already, 45 of 45 in the closest quartile, and fails the
second.

A v1.3 design should also fix the sample-size confound before any richer
readout is judged, by ensuring enough admitted episodes to support a
descriptor of that width.

The ConstructiveExtensionCompiler stays blocked.
