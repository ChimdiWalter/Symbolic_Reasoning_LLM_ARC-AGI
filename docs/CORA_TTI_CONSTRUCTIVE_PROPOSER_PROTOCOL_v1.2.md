# CORA-TTI Item-2 constructive corpus protocol v1.2

Preregistered 2026-09-23, before a single v1.2 episode was generated. It
supersedes v1.1 for corpus generation only. v1.1 is preserved unchanged and
is not overwritten.

Claim ceiling for the block that produced this document: the protocol is
frozen and feasible. Nothing about a trained scorer, useful construction,
constructive reach, semantic extension, transfer or score is claimed.

## 1. Why v1.1 is impossible

The v1.1 pilot generated all 60 requested slots, attempted 1,500 targets and
admitted zero. The recorded root cause is structural, not incidental:
requirements 4 and 5 were mutually exclusive. The registered slot learner
fitted induced slots by declared type through `meta_ast.bound_values`, which
returns one flat dictionary per type, so several occurrences of
`Map[FeatureValue,Colour]` in one schema collapsed onto the last. Requirement
5 was therefore satisfiable only when a schema reduced to a single
(partition, predicate, feature) triple, and that is exactly the space the
fixed baseline enumerates. Passing R5 implied failing R4.

Measured before the freeze: of 266 family-(2,) targets passing R5, 262 were
solved by the baseline and 4 failed witness separation.

A second v1.1 blocker was recorded: families with no Select stage were
structurally dead, because the type-keyed fitter yielded no predicate and the
feature-colour-map induction refused immediately. Section 6 shows this
blocker does not survive the change of fitter, and section 6 is the reason
this protocol departs from one instruction it was given.

## 2. What changed, and what did not

Changed, all on the target and evidence side:

- the registered constructive fitter is the occurrence-scoped fitter;
- episode failure graphs come from the repaired full-engine observation path;
- the model-view feature allowlist is extended and refrozen;
- seeds and slot schedule are new.

Not changed:

- the baseline K, its productions, its search depth, its budget and its
  ordering;
- the constructive grammar, its bounds, its operators, its terminals;
- the ranking rule, the beam and the MDL definition;
- the banned target families;
- the prohibition on reading any hidden output.

The baseline was not weakened in any respect. It keeps its own budget, and it
is given the same fitter as the target side.

## 3. R4 v1.2, baseline out of reach

PASS iff the ordinary frozen baseline, running its own enumeration with its
own declared budget, produces no exact solution for the demonstrations.

Mechanically: `scoped_slot_fitting.base_search_with_scoped_fitter(pairs)`
over `baseline_single_block_schemas()`, which is exactly 200 schemas, every
one of structural family `(1,)`. PASS iff `exact` is empty.

Recorded for every episode, never inferred from one another: schemas
enumerated; schemas fitted, including inexact constraint-only fits; schemas
exact; the fitter identity hash; the search budget; whether the deadline was
hit; the baseline code identity; the baseline language identity.

A deadline hit is recorded distinctly from certified bounded exhaustion. A
search that did not find is never recorded as semantically impossible. This
corpus trains a proposer; it does not prove semantic invention.

## 4. R5 v1.2, target fittable

PASS iff all of the following hold:

- the target AST is legal under the frozen constructive grammar, by
  `constructive_vocabulary.validate`;
- every required occurrence-scoped slot is fitted from the demonstrations
  alone, by `scoped_slot_fitting.fit_induced_occurrences`;
- the fitted executable target replays every generation demonstration
  exactly;
- no hidden or test output participates at any point;
- the fitted target is the same structural AST, with only permitted slots
  bound.

Registered constructive fitter: `cora_tti/scoped_slot_fitting.py`, identity
`2cc45152c430f8a2`, being the leading 16 hex characters of
`fitter_identity()`.

R5 may not fall back to the type-keyed learner that caused the v1.1
contradiction.

## 5. Why R4 and R5 are now different for a principled reason

R4 asks what the ordinary fixed language can discover. R5 asks whether a
target drawn from the larger constructive grammar can be legitimately
instantiated. That is the experiment's central distinction: fixed-language
search against structures available to language adaptation.

The separation is not a fitter privilege. Both sides use the same fitter, and
a mismatch of fitter identity between the two sides is a recorded fairness
violation that rejects the episode. The separation is structural. The
baseline enumerates 200 single-block schemas, all of family `(1,)`. The
constructive grammar admits up to three blocks. Under occurrence-scoped
fitting a multi-block target no longer collapses onto a single triple, so
passing R5 no longer entails baseline reachability.

R4 remains behavioural rather than structural: a multi-block target whose
behaviour a single-block schema happens to reproduce is still rejected as
baseline solved. That is intended and conservative.

The constructive side is frozen by this document before generation. No
target-specific widening is permitted after observing a failure.

## 6. Family feasibility, and the departure from one instruction

This protocol was instructed to remove Select-free families `(0,0)` and
`(0,0,0)` from the train pool, on the ground that they are structurally dead
under the registered fitter, and conditioned on a static pre-generation
feasibility check confirming feasibility for retained families.

The feasibility check was run before this freeze and the premise does not
hold under the v1.2 fitter.

| family | selects | occurrence-scoped slots seen | mechanically dead |
|---|---|---|---|
| (0,) | 0 | 1 | no |
| (1,) | 1 | 1 | no |
| (0,0) | 0 | 2 | no |
| (1,0) | 1 | 2 | no |
| (0,1) | 1 | 2 | no |
| (1,1) | 2 | 2 | no |
| (0,0,0) | 0 | 3 | no |
| (2,) | 2 | 1 | no |
| (2,1) | 3 | 2 | no |

The Select-free blocker was a property of the type-keyed learner, which
required a predicate before it would induce anything. The occurrence-scoped
fitter identifies slots by lexical occurrence in the AST, so a block with
zero selects still carries its own induced-slot occurrence.

Prior recorded evidence agrees. Of the thirteen verified admissions produced
under the occurrence-scoped fitter, seven are family `(0,0)`, which is the
single most admitted family, against three `(1,0)`, two `(0,1)` and one
`(1,1)`.

Removing those two families would therefore discard the most productive
family in the corpus, on a premise the change of fitter voids.

The instruction's constraint is honoured in full: no induction algorithm is
modified, and no family is rescued by changing a reasoning mechanism. The
occurrence-scoped fitter is pre-existing machinery already adopted under
decision A, not a modification made to save a family.

`(0,0)` and `(0,0,0)` are therefore retained in the v1.2 train pool. This
departure is recorded here, before any generation, and reversing it is a
one-line change to the manifest that costs nothing while no data exists.

Prospectively recorded risk, not to be revised after seeing scores: family
`(2,)` is single-block, and under v1.1 it was overwhelmingly baseline solved,
262 of 266. It may admit at a low rate under v1.2 as well. It is retained as
a structural holdout family unchanged, and this risk is recorded now rather
than discovered later.

## 7. v1.2 train, validation and holdout families

Train pool, five families, all retained from v1.1: `(0,0)`, `(1,0)`,
`(0,1)`, `(1,1)`, `(0,0,0)`.

Structural holdout, unchanged from v1.1: `(2,)` and `(2,1)`.

Banned target families, unchanged: `(0,)` and `(1,)`.

## 8. Requested slot counts and deterministic allocation

| split | requested episodes |
|---|---|
| train | 300 |
| validation | 60 |
| structural holdout | 90 |

Train slots are allocated equally across the five feasible train families, 60
each. Validation is allocated equally across the same five families, 12 each.
Structural holdout is allocated equally across the two holdout families, 45
each. Any remainder is assigned lexicographically by family text. Allocation
is fixed here and is never adjusted toward families that admit more easily.

Attempts per slot are capped at 25, as in v1.1.

## 9. Episode generation order, frozen

For each prospective episode, in this order and no other:

1. choose the target AST from the legal constructive grammar, by the frozen
   schedule and seed, before any failure graph exists;
2. generate the demonstrations;
3. run the ordinary baseline;
4. evaluate R4; if the baseline solved it, reject as BASELINE_SOLVED;
5. obtain the failure trace from that same baseline run, through the
   repaired full-engine observation path;
6. build the typed failure graph from that trace;
7. evaluate the informative-evidence gate of section 11;
8. evaluate R5;
9. admit only if every gate passes.

The target AST is never chosen from an observed failure graph. Doing so would
train the scorer on its own answer-generation process.

No target AST, digest, family label or any other target-derived value may
enter the failure graph.

## 10. Failure evidence comes from the repaired full engine

Every v1.2 episode obtains its failure evidence through the repaired
full-engine observation path in this workspace. The blind-runtime extractor,
the old proxy corpus, the thirteen empty-frontier episodes and the downgraded
reconstruction directories are all excluded as evidence sources.

Training and inference must share evidence semantics. The scorer at inference
consumes repaired real-engine evidence, so the corpus uses the same frontier
node definitions, the same candidate outcome names, the same candidate
renderer, the same mismatch-signature semantics, the same canonicalization
and the same feature extraction. The candidate-executor compatibility repair
is part of the v1.2 data path.

## 11. Informative-evidence admission gate

An episode may supervise failure-conditioned construction only if its
baseline's own failure graph carries evidence. The gate uses the baseline
graph alone and never the hidden target.

ADMIT on evidence iff:

    frontier_term_count >= 2

AND at least one of:

    defined_value_signature_count >= 1
    executed_not_exact_count >= 1
    slot_fit_failed_count >= 1

Otherwise reject as NO_INFORMATIVE_TFG. An empty or constant failure graph is
never admitted to increase sample size.

## 12. Model-view feature allowlist v1.2

The scorer sees these eighteen features and the typed interface. Nothing
else. The whole failure graph object is never handed to a learned scorer
without passing this boundary.

| feature | aggregation |
|---|---|
| n_demonstrations | count |
| mean_cells_changed | mean over demonstrations |
| mean_fraction_changed | mean over demonstrations |
| same_shape_all | boolean |
| palette_introduced_mean | mean over demonstrations |
| palette_removed_mean | mean over demonstrations |
| frontier_term_count | count |
| distinct_frontier_operator_count | count |
| slot_fit_failed_count | count |
| slot_fit_ok_count | count |
| executed_not_exact_count | count |
| exact_count | count |
| defined_value_signature_count | count |
| fraction_wrong_mean | mean over defined signatures |
| palette_extra_mean | mean over defined signatures |
| shape_mismatch_count | count of defined signatures whose shape did not match |
| empty_frontier | boolean |
| search_deadline_hit | boolean |

Aggregation is frozen here. Distributions are summarized by count or mean
only. Minimum and maximum are deliberately not included, so that no
aggregation can be chosen after seeing validation performance.

## 13. Prohibited model inputs

The model view excludes, absolutely: task id; ARC family label; the random
seed as a predictive input; the target AST; its digest; its structural family
label; any correct hidden output; any test output; any natural-language
description; the admission or rejection outcome; any future verifier outcome;
and any Step-B information.

The scorer sees failure evidence and the typed interface. Nothing that tells
it which AST is correct.

## 14. Supervised label

For an admitted episode the supervised target is the canonical target AST
chosen prospectively by the generation schedule. The trusted record stores
the canonical AST tokens, the AST digest, the structural family and the typed
interface. The model view never exposes them, except as the training label at
fitting time. At inference the proposer receives no target AST.

## 15. Split law

- train target digests are disjoint from validation and holdout digests;
- structural holdout families are disjoint from train families;
- generation seeds are deterministic and frozen in the manifest;
- validation examples are never used to fit scorer weights;
- validation is used only for early stopping and for model selection that the
  frozen model specification already permits.

Interface holdout remains infeasible, exactly as recorded in v1.1, because
only one typed interface exists. This protocol does not pretend otherwise and
does not introduce a second interface merely to claim the holdout.

## 16. Seeds and budgets

Root seed 20260923. Train seeds from 21000, validation from 22000, structural
holdout from 23000. These are disjoint from the v1.1 ranges 11000, 12000 and
13000, so no v1.2 episode can collide with a v1.1 one.

Budgets, using the reconciled dictionary already present in the pilot module
rather than a newly invented one: per target 90.0 s, baseline search 8.0 s,
failure-graph extraction 2.0 s, full-engine observation 8.0 s.

## 17. Rejection codes, recorded separately as diagnostics

`BASELINE_SOLVED`, `NO_INFORMATIVE_TFG`, `TARGET_NOT_FITTABLE`,
`TARGET_EXECUTION_UNDEFINED`, `WITNESS_NOT_SEPARATED`,
`STRUCTURALLY_INFEASIBLE_FAMILY`, `TIMEOUT`, `OTHER_FROZEN_CODE`.

Rejected episodes are retained as diagnostic records and are not discarded.
Only admitted episodes become positive supervision. No negative-example
objective exists in the frozen model specification, and none may be invented
after generation.

## 18. Stopping law for the later fit

Unchanged from the frozen model specification: at most 2000 epochs, or a
200-epoch plateau in validation exact-at-five, whichever comes first. Non-LLM,
hidden size at most 256.

## 19. Corpus quality criteria, frozen before generation

A non-zero admission count is not success. The corpus exists to teach that
different failures imply different constructive structures, so it is judged
against these criteria, all fixed here and none revised after generation.

| criterion | requirement |
|---|---|
| admission | non-zero in at least three of the five train families |
| training size | at least 120 admitted train episodes, being 40 percent of the 300 requested |
| structural diversity | at least three distinct structural families among admitted train episodes |
| target diversity | at least 60 distinct target AST digests among admitted train episodes |
| evidence quality | every admitted episode passes the section 11 gate on the baseline's own graph |
| evidence variation | the interquartile range of `frontier_term_count` across admitted train episodes is at least 2, and at least two distinct values occur for `distinct_frontier_operator_count` |
| label non-reconstructibility | no admitted target digest is predictable from the model view alone, checked by verifying that no single allowlisted feature is in bijection with the target family across the admitted set |
| separation | train digests disjoint from validation and holdout digests, enforced mechanically |
| leakage | the leak scan passes on every model view, with zero hidden-answer paths |
| no collapse | the unfitted proposer does not already emit the same rank-one AST for every admitted episode, measured and recorded before any fitting |

If the corpus fails a criterion, that is recorded as a measured outcome of
v1.2 and the protocol is amended prospectively as v1.3. The criteria are not
relaxed to accommodate the corpus that was produced.

## 20. What the later fit must beat

The learned scorer is not validated by emitting legal ASTs. That is already
demonstrated and is not in question. It is validated by showing that changing
the failure evidence changes what is constructed, usefully and reproducibly.

On frozen held-out constructive tasks the fitted scorer must outperform all
of these controls, which are fixed here:

| control | evidence supplied to the scorer |
|---|---|
| real associated | the episode's own failure graph |
| shuffled | another admitted episode's failure graph |
| irrelevant | a failure graph from a structurally unrelated episode |
| aggregate only | the demonstration statistics with every candidate-associated feature zeroed |
| none | the empty evidence vector |

The comparison metric is exact-at-five recovery of the held-out target AST,
and the ordering requirement is that real associated evidence beats shuffled
and aggregate-only evidence. No threshold is tuned after seeing holdout
results, and no control is dropped after seeing which one is competitive.

## 21. Relationship to the autonomous end state

This protocol supplies the typed interface to the proposer. That is an
intermediate experiment and not the final system.

The end state requires CORA to infer the missing typed capability from its
own failure frontier, rather than being handed it: ranked gap hypotheses
derived only from permitted failure evidence such as frontier types, failed
parameter classes, executable near misses, mismatch geometry, object and
region preservation, cardinality, shape, palette, relation failures and the
verification stage at which the attempt died.

Nothing in v1.2 may be built in a way that assumes the interface will always
be supplied. The model view is already interface-agnostic apart from the two
type names, and the supervised label carries the interface so that a later
gap-inference stage can be trained against it.

Autonomous gap inference may never be implemented by task-id lookup, family
lookup, target supervision at inference, or comparison against a hidden
answer.

## 22. What this protocol does not authorize

It does not authorize generating the corpus in the same block that froze it,
training the scorer, building the extension compiler, running the 1000
training tasks, touching the 60 protected holdout tasks, or reading anything
belonging to Step B.
