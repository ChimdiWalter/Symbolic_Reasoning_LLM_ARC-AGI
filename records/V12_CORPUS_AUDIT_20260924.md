# v1.2 constructive corpus: generation and audit

Generated and audited 2026-09-23 into 2026-09-24 under the frozen protocol,
sha256 `31a74764...bbe6bb98`, manifest sha256 `3355c9c5...d7766ba1`. No
threshold was changed after generation. Nothing was trained, compiled or
scored. Step B untouched.

## Verdict

**PASS**, on all eleven frozen criteria, with the corpus complete at 450 of
450 slots.

| criterion | measured | frozen threshold | result |
|---|---|---|---|
| admitted train episodes | 180 | >= 120 | PASS |
| families admitting | 6 | >= 3 | PASS |
| structural families among admitted train | 5 | >= 3 | PASS |
| distinct target digests in train | 180 | >= 60 | PASS |
| frontier_term_count interquartile range | 7.0 | >= 2 | PASS |
| distinct values of operator-count feature | 8 | >= 2 | PASS |
| share of the most common target | 0.0047 | < 0.5 | PASS |
| every admitted episode passes the evidence gate | 215 of 215 | all | PASS |
| train digests disjoint from validation | 0 overlap | 0 | PASS |
| train digests disjoint from structural holdout | 0 overlap | 0 | PASS |
| holdout families absent from train | 0 overlap | 0 | PASS |

## Scale and cost

7,947 targets attempted across 450 slots. 215 admitted, being 47.8 percent of
slots and 2.7 percent of attempts. Total wall time 2,811 seconds, 6.25 seconds
per slot, 13.07 seconds per admitted episode, single process at lowest
priority. Version 1.1 admitted zero of 1,500 attempts, so this is the first
Item-2 corpus to produce supervision at all.

## Admissions by family

| family | admitted |
|---|---|
| (0,0) | 65 |
| (0,1) | 51 |
| (1,0) | 47 |
| (1,1) | 42 |
| (0,0,0) | 7 |
| (2,1) | 3 |
| (2,) | 0 |

Requested family and realized structural family agree exactly on every
admitted episode, so no target drifted from its schedule slot.

## Rejections

| reason | count |
|---|---|
| TARGET_NOT_FITTABLE | 5,230 |
| TARGET_EXECUTION_UNDEFINED | 1,790 |
| BASELINE_SOLVED | 382 |
| OTHER_FROZEN_CODE | 327 |
| NO_INFORMATIVE_TFG | 2 |
| WITNESS_NOT_SEPARATED | 1 |

Two observations matter. Only 382 targets were solved by the unweakened
baseline, so the structural separation argument holds empirically: multi-block
targets are mostly outside baseline reach without the baseline being touched.
And only 2 episodes failed for want of informative evidence, so the repaired
full-engine path supplies usable failure evidence almost always. The erratum
filed before generation predicted that the deployed reasoner might solve these
synthetic tasks and starve the corpus. It does not.

## Diversity

215 distinct target digests from 215 admitted episodes, a duplicate rate of
zero. Blocks per target range 2 to 3, mean 2.03. MDL ranges 11 to 16, mean
12.05. Frontier terms range 2 to 12 with mean 7.87 and interquartile range
7.0. Distinct frontier operators range 1 to 9, mean 3.66. Defined value
signatures range 0 to 12, mean 3.18. Executed-but-non-exact candidates range 0
to 78, mean 6.53.

The evidence therefore varies widely across episodes, which is the property
the scorer needs in order to learn anything conditional.

## Material limitation the frozen gates did not cover

**The structural holdout arm is too thin to use as designed.** Of 90 requested
holdout slots, 3 admitted, all of family `(2,1)`. Family `(2,)` admitted
nothing at all.

This is exactly the risk recorded in the protocol before generation: `(2,)` is
single-block, and under v1.1 it was baseline-solved 262 times out of 266. It
is now measured at zero admissions, which confirms the prediction rather than
discovering a surprise. Single-block targets sit inside the baseline's own
enumeration, so they are the hardest family to place outside baseline reach.

No frozen criterion constrains holdout size, so the corpus passes as written.
But three episodes cannot support a structural-family held-out discrimination
test. That is a limitation of what the next experiment can measure, not a
reason to relax anything here, and the holdout families are not to be changed
to make the result easier.

## Claim earned

The v1.2 constructive corpus passes the frozen quality gate.

## Claims not earned

Nothing about learned failure conditioning, autonomous construction,
constructive reach, semantic extension, transfer or any score. A corpus that
can support the experiment is not the experiment.

## Next action

Fit the existing Stage-B scorer on this corpus. The fitted scorer must then
beat the five frozen evidence controls, being associated real evidence,
shuffled, irrelevant, aggregate-only and none, on exact-at-five recovery of
held-out targets.

The holdout thinness has to be confronted when that test is designed. The
honest options are to run the discrimination test on a held-out split of the
training families instead, and to state plainly that structural-family
generalization was not measured, or to preregister a v1.3 that makes the
holdout families reachable. Choosing between them is a prospective decision,
not one to make after seeing a score.
