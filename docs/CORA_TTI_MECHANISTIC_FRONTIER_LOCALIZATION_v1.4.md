# CORA-TTI Item-2 v1.4: mechanistic frontier localization

Information-flow audit of the deployed reasoner's own trajectory.

Protocol identity is the sha256 of this file, recorded in
`outputs/tti/mechanistic_frontier_v14_manifest.json`, whose own sha256 is in
`outputs/tti/mechanistic_frontier_v14_manifest.json.sha256`. This document
was written and frozen before any v1.4 experiment episode existed and before
any stage statistic was computed on any data. It does not overwrite v1.2,
v1.3, the scorer results, the scorer diagnosis or the frontier audits.

## 0. The binding result that motivates v1.4

v1.3 is complete. Official verdict: **V1.3 CONTRASTIVE CORPUS IDENTIFIABILITY
GATE FAIL.**

| quantity | value |
|---|---|
| full slots | 1,200 of 1,200 |
| attempts | 29,763 |
| admitted groups | 21: FEATURE 14, SELECT 7, PARTITION 0 |
| episodes | 168 |
| distinct targets | 41 |
| G1 | 79 of 168 = 0.470 against exact null 3/7 = 0.428571, p = 0.156, FAIL |
| G2 | 0.473, p = 0.195, FAIL |
| G3 | fraction s > 0 = 0.524, p = 0.50, FAIL |
| G4 | mean s 0.188, median 0.025, threshold 0.25, FAIL |
| G5, G6, G7 | 21 < 60; PARTITION 0; 41 < 100; FAIL |
| G8 to G10 | PASS |

Official interpretation: identifiability was not established; an effect of
the preregistered magnitude was excluded; a smaller effect remains possible.
It is not "the frontier contains no information" and not merely "we lacked
enough data". The central failure is that the current observed failure
representation does not identify minimally different constructive targets
strongly enough. Record: `records/ITEM2_V13_CORPUS_RESULT_20260926.md`.

## 1. The question

Not "can a scorer predict the target from the TFG". That route is not
licensed.

When CORA sees two minimally different constructive tasks, at what stage, if
any, does its actual reasoning trajectory begin to differ in a
target-specific way?

    demonstrations -> perception -> candidate formation -> selector induction
      -> parameter fitting -> executable candidates -> execution and mismatch
      -> Typed Failure Graph -> the descriptor the audit consumed

The objective is the first stage carrying a target-identifying signal, or
the finding that no observed stage carries a detectable signal of the
preregistered magnitude.

## 2. Why this is the smallest follow-up

Two mechanisms explain v1.3 equally well and need different repairs.

A. The raw reasoning trajectory differs between target semantics, but the
TFG or its descriptor destroys or aggregates the difference away. Repair the
representation.

B. The search trajectory itself barely reacts to the semantic difference.
Then no encoder or scorer can recover information the reasoner never
generated. Repair frontier elicitation.

v1.4 distinguishes A from B. It trains nothing.

## 3. Branch selection: B, decided mechanically

The stored v1.3 artifacts were inventoried by schema only: key names, node
kinds, attribute keys, edge relations, and the extractor and observer
source. No value was compared across episodes.

| stage | stored in v1.3 |
|---|---|
| S0 demonstrations | PARTIAL: per-demonstration delta, palette and shape summaries; raw grids not stored |
| S1 perception | NOT STORED: never emitted by the observer |
| S2 candidate formation | PARTIAL: a count in the census only |
| S3 selector induction | NOT STORED: failures are never emitted, and the event order that would reveal them was discarded |
| S4 parameter fitting | PARTIAL: failure counts per operator; fitted rules discarded |
| S5 executable candidates | PARTIAL: at most 12 terms, re-sorted by surface size |
| S6 execution and mismatch | PARTIAL: one value signature per retained term, first defined demonstration only |
| S7 TFG | RAW: the graph and the 42-field descriptor |

Everything stored is downstream of `build_tfg`, which keeps at most 12
frontier terms of two outcome classes and drops the observer's ordered
candidate list. A stored-artifact study could only compare two encodings of
the same post-extraction graph, so it cannot separate mechanism A from B.
**Branch A is not viable; Branch B is selected.** The choice depended only on
what was stored, and was made before any stage outcome was inspected.

## 4. Design: counterfactual twins

### 4.1 Contrast type

FEATURE only. FEATURE admitted groups in v1.3 and stays within the
structural family; SELECT carries the recorded family confound; PARTITION
admitted nothing. SELECT and PARTITION are not generated in v1.4.

### 4.2 Twin target law

Per group, target A is `sample_target(pair_seed, family)` from the frozen
grammar, and target B is `contrast_target(A, "FEATURE", rotation=attempt)`,
the v1.3 constructor. Admissible only if, checked by `twin_law`:

- same structural family, same block count, same MDL (tolerance zero);
- the same partition and select structure in every block;
- the token sequences differ in exactly one position, the key feature of
  block 0.

Both are Grid to Grid. No ARC task family, handwritten semantic category or
target-specific primitive is involved.

### 4.3 Shared inputs

Within replicate r, targets A and B receive the **same demonstration input
grids**, rendered from the same seed by the unchanged v1.2/v1.3 rendering
rule (`grid_seeds = seed * 97 + i`). Only the target transformation differs:
`X_A,r = X_B,r`, `Y_t,r = Execute(e_t, X_r)`. Twin integrity requires the two
input lists to be identical and at least one demonstration output to differ.
The reasoner sees ordinary demonstrations only, never e_A, e_B, the differing
feature, a digest or a contrast label.

### 4.4 Replicates

Four paired replicates per group, so 8 episodes: (t, r) for t in {0, 1} and
r in {0, 1, 2, 3}. For attempt a of slot s, `pair_seed = SEED_BASE + 10000 s +
100 a`; replicate seeds are `pair_seed + k` for k = 0 to 7, tried in order.
The pair is admitted when four twin replicates are admitted and abandoned as
soon as four becomes unreachable. Up to 25 pairs per slot. Slot s uses anchor
family `["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"][s mod 5]`. Replicate
seeds are trusted generation metadata and never model inputs.

### 4.5 Admission

Each target of a twin passes the v1.3 admission law unchanged:
`evaluate_target_v2` (R1 to R8 with the occurrence-scoped fitter, identity
2cc45152c430f8a2, and the unweakened baseline K), then the full-engine
observation with the v1.3 informative gate (frontier_term_count >= 2 and at
least one executed-not-exact, slot-fit-failed or defined value signature).
Plus twin integrity. Budgets are the v1.3 manifest's: base search 8 s,
full-engine observation 8 s, TFG 2 s, 90 s per target. Group admission
depends on nothing else. No frontier property, separability or distance is
examined before or during admission.

### 4.6 The reasoner

The same real engine and the same observer as v1.3, called through
`engine_trace.extract` unchanged, with three isolation measures that change
no reasoning semantics:

- a fresh engine directory `outputs/tti/v14_engine`, not the v1.3 one;
- the engine reads 18 `ARC_*` switches, several of which change behaviour
  across episodes (`ARC_ANALOGY` loads persisted programs, `ARC_OVERLAY`
  rereads the near-solve log, `ARC_GUIDE` keeps module caches). The generator
  refuses to run if any `ARC_*` variable other than `ARC_META_BUDGET_S=8` is
  set, if `PYTHONHASHSEED` is not 0, or if `library.json` or
  `learned_verbs.json` exists in the engine directory. The environment and
  the Python, numpy and scipy versions are recorded in every slot and must
  equal the manifest's;
- every engine memo cache is cleared before every engine run, so no run
  starts warm from an earlier run on the same input;
- the engine task label is an opaque hash with no target, twin or replicate
  identity. The grammar manifest the vocabulary loads from
  Reasoning_Project_tti is hashed with the freeze.

### 4.7 Raw trajectory capture and noninterference

No new engine hook is added. The existing observer already records the
ordered list of (candidate, outcome) the engine emits. v1.4 persists that
list, and after the engine has returned evaluates every distinct
executed-not-exact program (at most 64, in order of first emission) on every
demonstration with the engine's own executor. Nothing is generated, ranked,
pruned or accepted by either step. Tests prove the stored trajectory is the
observer's own list, that post-hoc evaluation leaves it unchanged and is
deterministic, and that the engine result with observation equals the result
without it.

**Self-rerun control.** On unsolved tasks the engine runs to its 8 s
deadline: every episode admitted in the feasibility smoke ran 8.03 to 8.08 s
and formed only 9 to 21 candidate groups. Each stored trajectory is therefore
a prefix whose length depends on machine load. To separate a reaction to the
semantic change from timing noise, target A of every twin is observed a
second time on the same input (A'), not admission-gated.

**Balanced run order.** The three engine runs of a replicate (A, B, A') use
one of all six orders, chosen by a hash of the replicate seed before any
outcome. If A always ran first, any systematic effect of run position, such
as load drift, would be perfectly confounded with target identity and would
read as target signal. Over the six orders, A precedes B in exactly half, and
B is closer in time to A than A' in two, farther in two, equally close in
two. (In v1.3 all anchor episodes of an attempt were generated before all
contrast episodes; since v1.3 found no signal, this could not have produced
its negative.)

### 4.8 Seeds

`SEED_BASE = 100,000,000`; feasibility-smoke seeds from 200,000,000. v1.4
grid seeds start at 9.7e9, above every stored v1.2 and v1.3 seed times 97, and
the full run's highest pair seed stays below the smoke base. Tested.

## 5. Stage descriptors

Each descriptor is a function of the model view only: `demo_features`,
`trajectory`, `mismatch`, `full_engine_tfg`, `descriptor`. Nothing else in an
episode is readable by a descriptor. One canonicalization everywhere:
`skeleton` replaces every numeric literal with `#` and keeps operator names,
feature names, modes and nesting, so descriptors compare what the reasoner
did rather than the grid it did it on.

| stage | descriptor | distance |
|---|---|---|
| S0 demonstrations (baseline, not a reasoning stage) | the six v1.3 demonstration features | Euclidean after v1.3 Phase-A standardization |
| S1 perception | unobservable without a new hook; not added | none |
| S2 candidate formation | multiset of skeletons of `typed` groups | Ruzicka |
| S3 selector induction | per `typed` event, from order: selector induced, with the skeleton of the selector carried by the next `slot_fit_failed` or `slot_fit_ok`, or no selector | Ruzicka |
| S4 parameter fitting | `slot_fit_failed` by operator; `slot_fit_ok` by skeleton of the fitted action | Ruzicka |
| S5 executable candidates | every `executed_not_exact` and `exact` program skeleton, uncapped | Ruzicka |
| S6 execution and mismatch | (program skeleton, mismatch class) per demonstration, classes undefined, shape_mismatch, palette_extra, cells_wrong, exact_on_demo | Ruzicka |
| S7a TFG graph | (outcome, term skeleton) per frontier term, and (term skeleton, value-signature class) per signature | Ruzicka |
| S7 descriptor the v1.3 audit consumed | the 42-field descriptor | Euclidean after v1.3 Phase-A standardization |

Ruzicka distance is `1 - sum(min) / sum(max)` over multiset counts, zero for
two empty multisets; it needs no normalization constants. S0 and S7 reuse the
committed v1.3 calibration (sha256 `ba82865e...51c7c02`, erratum-1 divisor 1.0
for constant fields). No constant is computed from v1.4 data.

Known limitation of S3: if the search deadline expires inside selector
induction or action fitting, the last group reads as "no selector". S3 is
interpreted with this stated. CPU time of every engine run is recorded, so
truncation can be related to CPU share.

## 6. Statistics

### 6.1 The exact null under shared inputs

The v1.3 statistic compared each episode with its 7 group companions against
an exact null of 3/7. **Under shared inputs that null is no longer exact.**
Replicate r of A and of B see identical inputs, so under the null the query's
own twin tends to be nearest, the rate falls below 3/7 by an unknown amount,
and a test against 3/7 becomes conservative by an unknown amount. The same
null hypothesis, that the stage descriptor carries no information about the
target beyond the input, has an exact form in this design.

**Twin-excluded nearest neighbour.** For query (t, r) the companions are the
six episodes of the other three replicates: three of the same target, three
of the other. Under the null the two members of every twin are exchangeable.
For any distance matrix, a uniform random swap of target labels within each
twin makes every companion's label agree with the query's with probability
exactly 1/2, independently of distances, because the query's and the
companion's swaps are independent fair coins. **The exact null expected
credit is therefore 1/2 per query**, not 3/7, and the probability of a
strict hit is at most 1/2. Tested for arbitrary distance matrices with and
without ties.

### 6.2 Ties

Ties at the minimum distance share credit: a query's credit is the fraction
of its tied nearest companions that share its target. A **hit** breaks ties
by a sha256 hash of (stage, group position, query, companion), which depends
on no label, so its null probability is exactly 1/2 and its expectation
equals the credit. A strict hit, reported descriptively, requires every tied
nearest companion to share the target; strict hits undercount under ties,
and on coarse descriptors can stay below 1/2 at any sample size even when
the signal is strong. v1.3 broke ties by episode index, which is not neutral:
it adds hits for target-0 queries and removes them for target-1 queries, so
its net effect can have either sign. The number of tied queries in v1.3 was
not measured.

### 6.3 Stage qualification (primary)

For each stage, over all admitted groups:

1. hits, total, hit rate, exact one-sided binomial p against 1/2, and the
   exact two-sided 95 percent Clopper-Pearson interval;
2. total credit, and its exact one-sided randomization p: the probability,
   under independent uniform within-twin label swaps in every group (16
   patterns per group), that total credit is at least the observed value,
   computed by exact convolution. This test is exact under within-group
   dependence; the binomial is not.

A stage is **TARGET_IDENTIFYING** only if hit rate > 1/2, binomial p < 0.01
and randomization p < 0.01. The binomial alone is not valid under
within-group dependence, and the randomization test alone would drop the
directive's statistic, so both are required. Stricter than the directive,
never looser. p < 0.05 is never used.

### 6.4 Secondary, explanatory only

- Separation per stage and group: W = mean same-target distance, B = mean
  different-target distance, both across different replicates; s = B - W.
  Mean, median, fraction s > 0, minimum, maximum and per-group values. Under
  the null E[s] = 0 exactly.
- Reaction beyond timing noise, per reasoning stage: for each replicate, the
  twin distance d(A, B) is compared with the rerun distance d(A, A'). If the
  stage does not depend on the target, B and A' are exchangeable given A, so
  among untied replicates the twin is farther with probability 1/2; replicates
  are independent. Exact one-sided sign test, Holm-adjusted over S2 to S5;
  the stage REACTS if the adjusted p < 0.01. Replicates whose rerun solved
  the task are excluded and counted. Counts are also reported by time-gap
  stratum: twin closer in time to A, rerun closer, equal gaps. The rerun is
  not admission-gated while B is, which biases toward "rerun farther", that
  is, against finding a reaction.
- **Only S2 to S5 can establish a reaction.** S6, S7a and S7 also score each
  target's candidates against that target's own outputs, so they differ
  between twins even when the trajectory is identical. Their twin-versus-rerun
  counts are reported but never enter the qualifier. For the same reason an
  execution-stage classification means target information is present in the
  candidate-to-mismatch evidence; it does not by itself show that the search
  reacted. This separates
  "does not react to the semantic change" from "reacts, but not consistently
  across inputs", which the nearest-neighbour test cannot. S0 is excluded
  because the rerun has identical demonstrations.
- The fraction of queries with tied nearest companions.

None of these can redefine qualification or the classification.

### 6.5 Multiplicity

Seven reasoning stages are tested at 0.01 each, so the family-wise error is
at most about 7 percent. Holm-adjusted randomization p-values are reported,
and the classification states whether its determining stage survives Holm.
The qualification criterion itself is not adjusted.

## 7. Classification ladder, frozen

Pipeline order: search stages S2, S3, S4; execution stages S5, S6; TFG
stages S7a, S7. S0 never enters the ladder. First matching rule wins.

| rule | classification | next repair |
|---|---|---|
| admitted groups < 14 | MIXED_OR_INCONCLUSIVE | the smallest experiment resolving the unresolved stage |
| S7 qualifies | CURRENT_TFG_IDENTIFYING_UNDER_TWINS | the current representation identifies targets once input variation is controlled; the v1.3 negative is then attributable to instance noise, and the next step is the smallest test of whether that signal survives realistic input variation |
| a reasoning stage before the first qualifying stage has randomization p < 0.01 but fails the binomial | MIXED_OR_INCONCLUSIVE | resolve that earlier stage |
| a search stage qualifies | RAW_TRAJECTORY_SIGNAL_TFG_LOSS, at the earliest qualifying stage | the smallest TFG-preservation repair for that stage |
| an execution stage qualifies | LATE_EXECUTION_SIGNAL_ONLY | candidate-to-mismatch association preservation |
| only S7a qualifies | TFG_AGGREGATION_LOSS | preserve the graph structure the 42-field aggregation loses |
| a reasoning stage has randomization p < 0.01 but fails the binomial | MIXED_OR_INCONCLUSIVE | resolve that stage |
| nothing qualifies and admitted groups >= 42 | REASONER_TRAJECTORY_INSENSITIVE, at every observed stage, qualified REACTS_BUT_NOT_CONSISTENTLY if any reasoning stage REACTS and NO_REACTION_BEYOND_TIMING_NOISE otherwise | a frontier-elicitation experiment that changes how the same reasoner explores near misses, not another scorer |
| nothing qualifies and admitted groups < 42 | MIXED_OR_INCONCLUSIVE | underpowered negative |

A qualifying stage is valid at any sample at or above the floor, since power
affects only false negatives. For RAW_TRAJECTORY_SIGNAL_TFG_LOSS and
LATE_EXECUTION_SIGNAL_ONLY the loss point is reported: the 42-field
aggregation if S7a qualifies, TFG construction otherwise. With seven stages
at 0.01 each, the family-wise error of a positive label is at most about 7
percent; whether the determining stage survives Holm is reported. REASONER_TRAJECTORY_INSENSITIVE applies to
observed stages only: S1 is not observed.

S0 is interpreted separately. S0 identifying while later stages do not:
the reasoner discards a distinction the task makes easy. S0 not identifying
while a later stage does: the reasoner extracts latent structure. Neither
identifying: the pairs may be too weakly different, which the twin
sensitivity figures qualify.

## 8. Sample size, exact

Null 1/2, planned effect p1 = 0.60 (the directive's localization target;
v1.3 already excluded about 0.55 in its noisier design), one-sided alpha
0.01, power at least 0.90, exact binomial, in whole groups of 8: **336
instances = 42 groups**, critical value 190 strict hits, size 0.00943, power
0.9106. 328 instances do not reach 0.90. Tested with exact rational
arithmetic.

This power assumes independent instances. Instances within a group are
dependent and ties count as strict misses, so the achieved power of the
joint criterion is lower than 0.91. For comparison, 0.60 against 3/7 would
need 112 instances; the twin null of 1/2 makes the same p1 a smaller effect.

The floor below which nothing is interpreted is **14 groups** (112
instances), the size of the v1.3 FEATURE population. One group can never
qualify: a swap pattern and its complement give the same total, so its
randomization p is at least 1/8.

## 9. Leakage boundary

- The engine receives only the demonstration grids and an opaque label.
  Tested by intercepting the engine call.
- Descriptors read only the five-key model view. Tested with an episode that
  raises on any other key.
- The auditor rejects any view containing a target digest (8, 12 or 16
  character prefix), the group digest, or a generation seed, in the episode's
  view or in its rerun's view.
- Engine vocabulary is not checked against grammar token names: the engine's
  own feature names legitimately overlap them, and the engine never receives
  a token.
- Trusted metadata (target index, replicate index, group) is used only to
  score the diagnostic after descriptors are computed.

## 10. Integrity preconditions

The auditor computes nothing unless: the protocol, manifest, implementation
files, all five dependency trees and the v1.3 calibration match their frozen
hashes; every admitted group is FEATURE, has exactly the eight design cells,
two distinct target digests consistent across episodes, one family and one
MDL, identical twin inputs, at least one differing twin output, identical twin seeds
and a complete self rerun with its run order on every target-0 episode; no
view leaks; slot records contiguous from 0, group digests unique, no more
groups than the target, and every slot recording the frozen environment,
the frozen runtime versions and a freeze re-verified at that slot; and no slot recorded an engine state problem. Any
violation gives AUDIT_BLOCKED and no statistic.

## 11. Reproducibility

The generator is not reproducible, as erratum 3 established for v1.3: two
admission stages and the observation itself are wall-clock deadline bound.
The audit is deterministic and is run twice; the two reports must be
byte-identical.

## 12. Order after freeze

1. One adversarial review of the frozen protocol and its implementation:
   done before any experiment episode existed; its corrections are in this
   version (section 16). No second review round.
2. Run the generator in full mode: single writer enforced by a file lock,
   nice 19, detached, until 42 admitted groups, the slot cap or the
   wall-clock cap, which counts from the first start across any restart. The
   freeze is re-verified after every slot.
3. Run the sealed auditor twice; require byte-identical reports.
4. Record the classification with every stage row. STOP.

Not authorized at any point in v1.4: scorer fitting, MLP, GNN, contrastive
or embedding training, target classifiers, TFG repairs, search changes,
ConstructiveExtensionCompiler, new solvers, primitives, grammars or DSLs,
the 1000 ARC tasks, evaluation DEV, protected HOLDOUT, Kaggle, and any Step-B
candidate, journal, output, E_transfer or Lockbox. No v1.4 information enters
Step B and no Step-B information enters v1.4. No threshold, descriptor,
distance, cap or classification rule changes after freeze.

## 13. Deviations from the directive, each with its reason

1. Null 1/2 with twin exclusion instead of 3/7: 3/7 is not the exact null
   under shared inputs (section 6.1). The null hypothesis is unchanged.
2. Randomization test required in addition to the binomial: the binomial is
   not valid under within-group dependence (section 6.3). Only stricter.
3. Two classifications added, CURRENT_TFG_IDENTIFYING_UNDER_TWINS and
   TFG_AGGREGATION_LOSS: both are clean localizations the directive's four
   labels did not name, and forcing them into A to D would misreport them.
4. Fitted executable candidates (S5) count as execution stages for rules B
   versus A, because they exist only once an executable near miss exists.
5. S1 is unobserved: adding a hook would change the instrument, and the
   directive allows observation only where the observer already exposes
   internal reasoning.
6. Branch A not viable (section 3).
7. The self-rerun control (sections 4.7 and 6.4) was added after the
   feasibility smoke showed that every admitted run is deadline bound. It
   qualifies the negative label only and adds one engine run per replicate.
8. Run order balanced over six permutations (section 4.7), to remove a
   run-position confound the directive's design would have carried.
9. Hits break ties by a label-independent hash rather than counting ties as
   misses (section 6.2): the null stays exactly 1/2, and coarse stages can
   qualify at all.

## 14. Claim ceiling

This block: **V1.4 MECHANISTIC FRONTIER LOCALIZATION PROTOCOL FROZEN AND
STATICALLY FEASIBLE.** Nothing about trajectory identifiability, TFG
information loss, search-policy insufficiency, constructive reach,
autonomous reasoning, semantic invention or score.

The run itself can establish at most where, among the observed stages, a
target-identifying signal first appears under controlled twins, or that none
of the observed stages carries one of the planned magnitude. It cannot
establish that a repair works, that a scorer can learn the signal, or
anything about ARC performance. The ConstructiveExtensionCompiler stays
SPECIFIED_ONLY whatever the outcome.

## 15. Static feasibility and caps

Feasibility smoke, 2026-09-27, on seeds from 200,000,000 under the pre-rerun
implementation, output under `logs/v14_feasibility/`, never audited. Load
average about 42 from other work on the host.

| quantity | value |
|---|---|
| slots completed | 11 (stopped by exact PID once sizing was settled) |
| admitted groups | 6, rate 0.545, exact 95 percent interval 0.23 to 0.83 |
| pair attempts / replicate attempts | 201 / 1,021 |
| mean time per slot | 91.6 s |
| rejections | TARGET_NOT_FITTABLE 509, TWIN_OUTPUTS_IDENTICAL 297, PAIR_REPLICATES_SHORT 195, TWIN_DEMONSTRATIONS_UNDEFINED 104, OTHER_FROZEN_CODE 42, TWIN_INPUTS_DIFFER 20, BASELINE_SOLVED 11, NO_INFORMATIVE_TFG 2 |
| engine runs of admitted episodes | 8.03 to 8.08 s each, all at the deadline |

Every admitted smoke group passed the integrity and leak checks with a clean
engine state. A one-feature swap often leaves every demonstration output
unchanged on the same inputs (297 replicate attempts), which is why twin
integrity requires a differing output. The rerun path was then exercised on
the real engine for two replicates of an admitted smoke pair: both admitted
in about 30 s for three engine runs, with the run order recorded and no
leaks. No distance or neighbour between any two episodes was computed.

**Caps, frozen.** Stop at the first of: 42 admitted groups; 400 slots; 86,400
s wall clock. At the smoke rate, 42 groups need about 77 slots, about 2.4
hours including the reruns; at the lower end of the interval, about 180
slots and 5 hours. 400 slots keep every full-run pair seed below
104,000,000, under the smoke base. If a cap is reached with fewer than 42
groups, a negative is MIXED_OR_INCONCLUSIVE by the ladder, and a positive at
14 groups or more stands.

Static tests: `tests/test_v14_localization_feasibility.py`.

## 16. Erratum 1: the pre-run adversarial review

The protocol was first frozen at commit 50841e3 (protocol sha256
43e798fa..., manifest dd481b31...). One adversarial review of that freeze,
run before any experiment episode existed, confirmed the exact null, the
exactness of the randomization test, the S3 and S7a derivations, seed
disjointness, the abandonment rule, leakage and auditor determinism, and
found the following. Every correction was made before any experiment
episode exists; none relaxes a threshold.

| finding | severity | correction |
|---|---|---|
| a stage with exact-test signal but failing the binomial, placed before the first qualifying stage, did not stop a later localization; with ties counted as misses, coarse stages such as S2 and S4 could never qualify | blocking | hits break ties by a label-independent hash (section 6.2), and the ladder returns MIXED_OR_INCONCLUSIVE when such an earlier stage exists (section 7) |
| S6, S7a and S7 re-score candidates against each target's own outputs, so they differ between twins even with identical trajectories, making the reaction qualifier near-automatic | major | reaction qualifier from S2 to S5 only, Holm-adjusted; execution-stage labels documented as not showing a search reaction (section 6.4) |
| only two of the engine's 18 `ARC_*` switches were refused, none recorded | major | all `ARC_*` refused except `ARC_META_BUDGET_S=8`; environment and runtime versions recorded per slot and checked by the auditor (section 4.6) |
| only target A ever followed an identical-input run, and engine memo caches persist across runs | minor | every engine cache cleared before every run |
| a solved rerun biases the sign test | minor | such replicates excluded and counted |
| freeze checked only at start and audit; grammar manifest unhashed; wall clock reset on restart; no writer lock; slot contiguity and duplicate groups unchecked; run-end record not atomic | minor | per-slot freeze re-verification, grammar manifest hashed, persistent wall clock, file lock, auditor corpus checks, atomic write |
| the S3 limitation also applies when the deadline expires during action fitting; CPU time not stored; the v1.3 tie-break statement was wrong | minor | text corrected, CPU time recorded |

Record: `records/ITEM2_V14_ERRATUM_01.md`.
