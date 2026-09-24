# Item-2 constructive corpus protocol v1.3: contrastive identifiability

Preregistered 2026-09-24, before a single v1.3 episode was generated. v1.1 and
v1.2 are preserved unchanged. The frozen v1.2 scorer verdict, its weights and
its report are untouched.

Supersedes the earlier draft `CORA_TTI_CONSTRUCTIVE_CORPUS_v1.3_PREREG.md`
committed at db6f500, which lacked replicates, a nonlearned audit and frozen
distance laws. That file is retained for history and is not authoritative.

Claim ceiling for the block that wrote this: the protocol is frozen and
statically feasible. No corpus, no fit, no identifiability result and no
capability claim.

## 1. What v1.2 established, and what it did not

v1.2 produced diverse, valid supervision: 215 admitted episodes, 215 distinct
target digests, all eleven corpus gates passed. Its scorer experiment then
returned `FAILURE_CONDITIONING_NOT_ESTABLISHED`, and the preregistered
diagnosis localized the cause.

Not the scorer's capacity: a bounded nonlinear readout gave candidate features
a delta of -0.0156 with one of five folds positive. Not summary compression:
all 180 diagnostic episodes had distinct candidate vectors with zero
collisions, and a 42-field descriptor taken straight from the stored graph was
worse than demonstration statistics, at -0.1006 under the linear model and
-0.0491 under the nonlinear one. The recorded caveat stands, that the 42-field
test carried 42 features against 144 training episodes per fold and is
confounded with overfitting, so it does not prove the graph holds no
information.

Nor do demonstration statistics explain the target. They predict the first
partition token at 0.383 against a 0.411 majority baseline. **No evidence
group recovered the target.**

And the opportunity was there. Of the closest quartile of episode pairs by
demonstration distance, 45 of 45 had different targets. The frontier had
exactly the cases it exists for and did not distinguish them.

### The mechanism this points at

The failure frontier is expressed in the deployed reasoner's vocabulary:
segmentation variants, correspondences, selectors, parameter fitting, and
near-misses built from its operators. The target is expressed in the
constructive grammar's vocabulary: a partition, some selects, a key feature, a
paint. Nothing in v1.2 required these two coordinate systems to be related.
A trace reporting that growth and translation were tried and that a parameter
fit failed carries no particular information about whether the generating
target partitioned by enclosed regions and keyed by area.

v1.3 does not repair that by changing the engine, the grammar, the fitter or
the observer, all of which stay frozen. It is a **data identifiability
repair**: it builds a corpus in which the question can be asked with an exact
null, and it asks that question **without training anything**.

## 2. What changes and what does not

Changed: episodes are generated in **contrastive groups with replicates**, and
the corpus gate becomes a **nonlearned identifiability audit** over frozen
distances.

Unchanged: the constructive grammar, its bounds, operators, terminals and
banned families; the ordinary baseline and its budget, enumeration, ordering
and fitting; the registered occurrence-scoped fitter and its fairness guard;
the deployed reasoner; the repaired full-engine observer and the
candidate-executor compatibility repair; the failure-graph representation; the
verifier and leave-one-out discipline; the eighteen-feature model view; and
the prohibition on reading any hidden output.

No new solver, no task-family dispatch, no hand-authored operator, no new
primitive, no answer predictor and no lookup is introduced. No new scorer is
built in this protocol.

## 3. Contrastive group law

A **group** is two targets and their replicates:

    group = { anchor target A, contrast target B } x R independent instances

The two targets differ in **exactly one** grammar position and are otherwise
identical. Three contrast types, allocated equally across the schedule:

| type | what differs |
|---|---|
| PARTITION | the partition terminal of one block |
| FEATURE | the key-feature terminal of one block |
| SELECT | one select predicate is added to one block |

**Replicate law: R = 4**, frozen. Each target is rendered from four
independent grid-seed sets, so each group holds 8 episodes. Replicates exist
to separate target-specific failure structure from ordinary instance
variation, which v1.2 could not do at one episode per target. Replicates are
generated for every scheduled target, never only for promising or difficult
ones.

**Recorded confound.** A SELECT contrast changes the structural family, for
example from `(0,0)` to `(1,0)`, while PARTITION and FEATURE contrasts stay
within family. The family label is trusted metadata and never a model input,
but a SELECT-driven result could reflect family difference rather than
frontier content. Every audit statistic is therefore reported overall **and
split by contrast type**, and the primary gate must hold for PARTITION and
FEATURE considered together, not on SELECT alone.

## 4. Admission, unchanged from v1.2

Every episode independently must pass the unchanged v1.2 law: the ordinary
baseline must not solve it under the frozen 8 second budget and unchanged
enumeration, which is R4 and stays behavioural; the target must be fittable by
the registered occurrence-scoped fitter with exact replay, which is R5; and
the episode's own failure graph, from the deployed reasoner under the repaired
observer, must pass the informative-evidence gate of at least two frontier
terms plus one candidate-associated evidence class.

A group is admitted only if **all 8** of its episodes are admitted and the
demonstration-match criterion of section 6 holds.

**No group and no episode is ever filtered on any property of its failure
frontier.** Selecting groups whose frontiers happen to separate would
manufacture the correlation under test. The frontier is judged only at corpus
level, after the scheduled generation has run, and a failure is preserved
rather than repaired by discarding groups.

## 5. Calibration phase, which fixes every normalization constant

Distances need a scale, and choosing that scale after seeing contrast results
would be tuning. Phase A therefore runs first and is purely calibrational.

Phase A generates **200 episodes** under the v1.2 schedule with no group
structure, no contrast, no selection and no audit. Its only product is the
per-feature mean and standard deviation of the demonstration features and of
the 42-field frontier descriptor. Those constants are written to the manifest
and published before Phase B begins, and are never recomputed afterwards.
Phase A episodes are not part of the v1.3 corpus and are never used as
evidence for any audit.

## 6. Demonstration distance and the match criterion

`d_demo` operates on six permitted demonstration features:
`n_demonstrations`, `mean_cells_changed`, `mean_fraction_changed`,
`same_shape_all`, `palette_introduced_mean`, `palette_removed_mean`. Each is
standardized by the Phase A constants. A target's demonstration vector is the
**mean over its four replicates**. The metric is Euclidean.

**Match criterion, frozen: `epsilon_demo = 0.5`** standardized units between
the two targets' replicate-mean vectors. A group whose targets exceed it is
rejected as `DEMO_NOT_MATCHED`.

This is selection on demonstration statistics, which is the explicit design
intent, and it is not selection on the frontier.

## 7. Frontier distance, target independent

`d_frontier` uses the 42-field descriptor already defined and already executed
in the v1.2 diagnosis, built only from fields present in the stored graph:
frontier operator identities bucketed by `sha1(op) mod 16`; counts of the six
candidate outcome names; minimum, mean and maximum of frontier `surface_nodes`
and of defined-signature `cells_wrong`, `fraction_wrong` and `palette_extra`;
distinct operator count; defined-signature count; shape-mismatch count; and
the stored search execution counters.

Standardized by the Phase A constants. Metric Euclidean. It uses no target, no
family, no task identifier, no seed as meaning, and no hidden output.

## 8. The nonlearned identifiability audit

This is the corpus gate. Nothing is trained.

**Primary statistic, within-group nearest neighbour.** For each of the 8
instances in a group, find its nearest neighbour among the other 7 by
`d_frontier`. Score a hit if that neighbour shares its target. Each instance
has 3 same-target and 4 different-target companions, so **chance is exactly
3/7 = 0.428571**. The null is exact, not estimated.

**Secondary statistic, separation.** For each group, `W` is the mean
`d_frontier` over same-target instance pairs and `B` the mean over
different-target pairs. Group separation is `s = B - W`. This is the
within-target replicate null of section 9 compared against the cross-target
contrast, per group.

## 9. Null comparisons, frozen

**Within-target replicate null**: same target, independently generated
demonstrations. It estimates how much the frontier moves when the semantics do
not change. It is the `W` term above.

**Cross-target contrast**: different targets, demonstration-matched by section
6. It is the `B` term.

The desired relation is that cross-target frontier distance exceeds ordinary
same-target variation. Requiring merely that two graphs differ is worthless,
since v1.2 showed all 180 episodes already had distinct descriptors.

## 10. Gates, all frozen now

| gate | requirement |
|---|---|
| G1 primary identifiability | nearest-neighbour hit rate above 3/7, one-sided exact binomial p < 0.01, over all admitted training instances |
| G2 contrast-type robustness | G1 also holds on PARTITION and FEATURE instances pooled, excluding SELECT |
| G3 separation | the fraction of admitted training groups with `s > 0` exceeds 0.5, one-sided exact binomial p < 0.01 |
| G4 separation magnitude | mean `s` over admitted training groups is at least 0.25 standardized units |
| G5 scale | at least 60 admitted training groups, being 480 admitted training episodes |
| G6 coverage | at least 3 groups admitted for each of the three contrast types |
| G7 distinct targets | at least 100 distinct target digests among admitted training episodes |
| G8 splits | group digests disjoint across training, validation and holdout, asserted mechanically |
| G9 leakage | zero violations from the hardened scanner, extended to the new metadata fields |
| G10 evidence | every admitted episode passes the unchanged informative-evidence gate |

All ten are required for a PASS. Any failure is recorded and preserved, and
no threshold in this table may be adjusted after any v1.3 outcome.

## 11. Sample size, justified rather than inherited

The v1.2 criterion of 120 training episodes is **not** reused. The requirement
is derived from the intended readout.

The diagnostic descriptor is 42 fields wide. At ten observations per feature,
a later readout over it needs about 420 training episodes. Five folds leave
roughly 384 per training split at that size, which removes the v1.2 confound
of 42 features against 144 episodes.

The primary gate needs power against an exact null of 0.428571. Detecting a
hit rate of 0.55 one-sided at p < 0.01 with about 90 percent power needs on
the order of 400 instances.

Both point the same way. **G5 requires 60 training groups, being 480
episodes**, which satisfies the descriptor requirement and the power
requirement together. Validation and holdout add 12 groups each, so the target
schedule is 84 admitted groups and 672 admitted episodes.

## 12. Sizing rule, a formula fixed in advance

A bounded pilot of **40 group slots** measures the group admission rate `q`.
The full run then requests `ceil(84 / q)` group slots, capped at **1,200**. If
the cap is reached before 84 groups are admitted, the corpus is reported at its
achieved size, every gate is still evaluated, and the reduced power is stated.
The cap is never raised afterwards, and `q` is never re-estimated to obtain a
more convenient size.

## 13. Splits

Admitted groups are ordered by ascending group digest, which is content
derived. The first 60 are training, the next 12 validation, the next 12
holdout, and any surplus is retained and marked unused. Both targets and all
replicates of a group always share its split, so no group is ever divided.

v1.3 measures failure-target identifiability. It does **not** measure
structural-family generalization, which remains unmeasured and needs its own
prospective experiment later.

## 14. Seeds and budgets

Root seed 20260924, disjoint from v1.1's 20260903 and v1.2's 20260923. Phase A
seeds from 30000, group seeds from 31000, validation from 32000, holdout from
33000. Replicate `r` of a target uses grid seeds derived deterministically
from the group seed and `r`.

Budgets unchanged: per target 90 seconds, baseline search 8, graph extraction
2, full-engine observation 8, attempts per episode slot capped at 25.

## 15. Leakage boundary

Trusted metadata, never a model input: target AST, its digest, its tokens, its
structural family, the contrast type, which grammar position differs, the
group identifier, the replicate index, the generation seed, the split, the
admission outcome.

Model view, unchanged from v1.2: the eighteen features plus the typed
interface.

The hardened v1.2 scanner applies unmodified and is **extended** to the three
new fields, being group identifier, contrast type and replicate index. Zero
violations are required before the audit runs.

The generator knows the target. The deployed reasoner, the observer, the
failure-graph construction and every distance computation do not. The path is
always demonstrations, then the reasoner, then its failure, then the graph.
Never the target to the graph.

## 16. Autonomy limitation, restated

The typed interface is still supplied. v1.3 is an intermediate experiment and
is not autonomous gap inference. The final target remains a failure graph, to
an inferred missing typed contract, to a constructed AST.

## 17. What v1.3 cannot establish

It cannot establish failure-conditioned selection, constructive reach,
autonomous construction, semantic extension, transfer, structural-family
generalization or any ARC score. A PASS establishes only that a
demonstration-matched contrastive corpus exists in which the frontier
distinguishes minimally different targets better than chance, which is the
prerequisite the programme currently lacks.

## 18. Order after this freeze

Generate the scheduled corpus. Run the frozen audit. Stop and record PASS or
FAIL. Only on a PASS may a new failure-conditioned scorer experiment be
separately preregistered. Only if that scorer shows incremental value from the
real associated frontier over matched controls does the
ConstructiveExtensionCompiler become licensed. It stays blocked throughout.
