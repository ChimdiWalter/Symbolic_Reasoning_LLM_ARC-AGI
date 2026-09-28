# CORA-TTI Item-2 v1.5: conditional failure-conditioned selection under input variation

Protocol identity is the sha256 of this file, recorded in
`outputs/tti/failure_conditioned_selection_v15_manifest.json`, whose own
sha256 is in `outputs/tti/failure_conditioned_selection_v15_manifest.json.sha256`.
Written and frozen before any v1.5 selector was fitted and before any v1.5
test group existed. It overwrites no v1.2, v1.3 or v1.4 artifact.

## 0. The parent result, preserved exactly

v1.4 (result commit 134e36c, erratum-2 freeze 5ffa56f):
**CURRENT_TFG_IDENTIFYING_UNDER_TWINS**, determining stage S7, confirmatory
at 42 unique groups, 336 primary episodes and 168 rerun controls, sealed
audit reproduced byte for byte.

| stage | hits / n | hit rate | binomial p | randomization p | status |
|---|---|---|---|---|---|
| S0 demonstrations (baseline) | 223/336 | 0.664 | 9.92e-10 | 8.41e-08 | identifying |
| S2 candidate formation | 193/336 | 0.574 | 3.71e-03 | 4.37e-04 | identifying |
| S3 selector induction | 199/336 | 0.592 | 4.25e-04 | 4.47e-07 | identifying |
| S4 parameter fitting | 192/336 | 0.571 | 5.12e-03 | 9.78e-05 | identifying |
| S5 executable candidates | 173/336 | 0.515 | | | not identifying |
| S6 execution x mismatch | 169/336 | 0.503 | | | not identifying |
| S7a TFG graph | 183/336 | 0.545 | 0.0567 | 3.20e-04 | randomization only |
| S7 42-field descriptor | 190/336 | 0.565 | 0.00943 | 0.00173 (Holm 0.00518) | identifying |

Reaction beyond same-input rerun noise: S2 108 against 15, S3 117 against
13, S4 119 against 10, S5 110 against 5, all REACTS. Earned and kept: the
reasoning trajectory reacts to the one-feature semantic perturbation, and
the existing TFG summary contains target-identifying information under
controlled shared-input twins.

Two limitations are load-bearing. v1.4 did not show that failure evidence
adds information beyond demonstrations: S0 (0.664) was stronger than S2,
S3, S4 and S7. And its positive holds only under shared-input twins; v1.3,
on independently rendered inputs, found no identifiability. So v1.5 claims
nothing merely because failure evidence predicts the target: failure
evidence must add something once demonstration evidence is present, and
independent input variation is the primary condition.

## 1. The question

Given a fixed pair of legal constructive candidates that differ in one
FEATURE position, does associated failure evidence improve selection of the
correct candidate beyond demonstration evidence alone, and does that
incremental benefit survive on unseen target pairs under independently
rendered inputs?

This is a selection experiment. It is not construction, capability
installation, reach, compiler evaluation or ARC score. The pair is supplied
by the frozen grammar; the proposer, grammar, K and compiler are not under
test and are not modified.

## 2. The model: the existing scorer, scoring two tokens

Inventory: `cora_arc2026/scorer_fit.py` holds `LogLinearScorer` (one weight
row per grammar terminal; logit of token t is w_t . x with x = [1,
standardized evidence, 5 grammar-state inputs]) and `Standardizer` (fit-set
mean and standard deviation, constant fields dropped, never floored).
`constructive_proposer.py` holds the unfitted proposer and is not used.

The two candidates share every token except one key-feature token of block
0. The grammar state at that position is found by advancing the existing
`GrammarState` through the shared prefix. The selector compares the
`LogLinearScorer` logits of the two legal key-feature tokens there; the
higher logit is chosen. That is the scorer's own operation, so no new
architecture, network, encoder or selector is introduced.

Two minimal adapters, both deterministic:

- `FieldStandardizer`: the v1.2 standardizer rule on an explicit field list,
  because `Standardizer.fit` iterates the fixed v1.2 field list.
- `fit_pairs`: the conditional log-likelihood of the true token restricted to
  the two candidates, with L2 penalty lambda = 0.01 on all weights, identical
  in every condition. The objective is strictly convex, so its optimum is
  unique; Newton's method reaches it to a step of 1e-12 (at most 100
  iterations). This replaces v1.2's early stopping, so no validation split
  and no stopping rule exists to tune. A test shows Newton's optimum equals
  the fixed point of the v1.2 gradient-ascent update to 1e-5. Linear
  algebra runs single-threaded.

## 3. Evidence views

Functions of an episode's evidence only (`demo_features`,
`full_engine_tfg`, `descriptor`, `trajectory`); tested with an episode that
raises on any other key.

- **D_RICH, the primary demonstration baseline (23 fields).** Audit of
  every demonstration-only representation the pipeline already produces:
  `features_v12` (the six S0 fields), the TFG's per-demonstration nodes
  (delta, palette and shape attributes, computed by the extractor from the
  demonstrations alone), and the v1.3 calibration features (the same six).
  D_RICH is the six S0 fields plus mean, minimum and maximum aggregates of
  the per-demonstration nodes. It is the strongest existing view in
  information, since it contains the others.
- **D_AGG (secondary, 6 fields):** the v1.4 S0 features.
- **F_S7, the primary failure view (42 fields):** the v1.4 descriptor, the
  existing downstream representation, the one that passed v1.4.
- **F_NOVSIG (explanatory, 31 fields):** F_S7 without its 11 value-signature
  fields, which compare candidates with the target's own outputs.
- **F_SEARCH (explanatory, 60 fields):** counts from the reasoner's emitted
  trajectory only: candidate formation (typed groups and their delta types,
  19 engine types), selector induction (induced and no-selector counts from
  event order, 16 hashed buckets of selector-predicate operators and
  arguments, mean literals) and fitting (fits, failures and fitted delta
  types).

Capacity is matched: every condition sharing an F block uses the same
standardizer, fitted on the training set with associated evidence, and the
same input width; an inactive block is exactly zero after standardization,
so its weights never leave zero (tested). D+F_ASSOC therefore cannot win
through extra dimensions: D has the same width, and D+F_SHUFFLED has the
same width and the same F values, rearranged.

**Verification diagnostic, descriptive only.** For every test episode the
generator records whether the OTHER candidate would also reproduce the
episode's demonstrations under the existing occurrence-scoped fitter. This
executes candidates, so it is not demonstration evidence and enters no
view; it is reported to show how often plain verification would decide a
pair, with primary accuracies on the verification-ambiguous subset.

## 4. Conditions

Primary: **D** (D_RICH), **D+F_ASSOC** (D_RICH + the query's own F_S7),
**D+F_SHUFFLED** (D_RICH + a matched other query's F_S7).
Secondary: F_ASSOC (F_S7 alone), D_AGG, D_AGG+F_ASSOC.
Explanatory: D+F_NOVSIG and D+F_SEARCH, each with its matched shuffle.
Only the three primary conditions enter the gates.

## 5. The matched shuffle

One deterministic rule, frozen before any fit. Within each evaluation pool
separately (the training set, the test set, each cross-validation part):
standardize D_RICH with the pool's own mean and standard deviation (no
label); compute all squared distances between queries of DIFFERENT groups;
sort by distance, then index; greedily match unmatched pairs, which swap F.
Any leftover query joins a 3-cycle with the nearest matched pair whose two
members come from other groups. D never moves; F is a permutation of the
pool's own F values; no query receives F from its own group, since that
could copy same-pair evidence. The rule uses D_RICH, group membership and
indices only: no target token, digest, label, outcome or TFG distance
(tested: flipping every label leaves the permutation unchanged).

## 6. Candidate order and ties

Presentation order sorts the two candidates by sha256 of the task's
demonstrations and the token. It never depends on which candidate is true
(tested). Each token's logit depends only on the token, so the choice is the
same under either order (gate F, checked on every query); an exact tie
(logit difference within 1e-12) makes no choice and earns half credit, so a
tie cannot depend on order either.

## 7. Data

**Training resource:** the 42 included v1.4 twin groups (336 episodes), as
listed by `outputs/tti/v14_twin_corpus_sha256_erratum2.txt` (sha256
`792a7beb...`), every listed file verified before use. Rerun controls and the
excluded duplicate (slot 117) are not used. Fixed; no new training data.

**Twin positive control:** grouped 7-fold cross-validation over those 42
groups. Groups sharing a target digest are placed in one fold (components
ordered by their smallest group digest, dealt round-robin). Each fold is
scored by models fitted on the other six. Also reported, descriptively: the
D+F_ASSOC model scored with each query's twin's F (same inputs, other
target).

**Test corpus, the primary regime: new independent-input groups.**

- One FEATURE pair per group from the frozen grammar under the v1.4 twin law
  (same family, block count, partition, selects and MDL; exactly one
  key-feature token differs). Slot s uses family `FAMILIES[s mod 5]`, pair
  attempt a uses `pair_seed = 300,000,000 + 10,000 s + 100 a` and contrast
  rotation a, up to 25 pairs per slot.
- Four admitted episodes per target, each on its OWN seed, so its own input
  grids: target t tries `pair_seed + 10 t + k` for k = 0 to 7, interleaved
  with the other target by a label-independent hash, abandoned when four
  becomes unreachable. The two targets never share a seed or an input grid
  (checked).
- Admission per episode: the v1.3 law unchanged (R1 to R8, occurrence-scoped
  fitter, unweakened baseline K) and the v1.4 real-engine observation
  (caches cleared, informative gate, trajectory capture). No
  demonstration-distance filter and no frontier-based admission.
- Novelty: a pair is skipped before any engine run if its group digest or
  either target digest is in the frozen exclusion set (every target and
  group digest in the v1.2, v1.3 and v1.4 corpora and the v1.4 smoke
  records: 471 targets and 69 groups, `outputs/tti/v15_exclusion_digests.json`,
  sha256 `50349bcf...`, rebuilt exactly by a test), or if either target
  already appears in an earlier test group. Every test target therefore
  appears in exactly one group of one split, and no pair appears twice in
  either order (the group digest sorts its two targets).
- Engine isolation as in v1.4: a fresh engine directory, every `ARC_*`
  switch refused except `ARC_META_BUDGET_S=8`, `PYTHONHASHSEED=0`, versions
  and environment recorded and freeze re-verified after every slot, one
  writer by lock, wall clock counted from the first start across restarts.

**Seeds.** v1.2 and v1.3 pair seeds are below 1.3e7; v1.4 used 1.0e8 to
1.04e8 and its smoke 2.0e8 upward; v1.5 test seeds start at 3.0e8 and
pilot seeds at 4.0e8, and the test's slot cap keeps it below 4.0e8. Grid
seeds are seed times 97 plus a small index, so no two ranges meet (tested).

## 8. Metrics and inference

Per query: the choice; 0-1 selection loss with half credit for a tie; the
negative log-likelihood of the true candidate; the margin, true logit minus
false logit; the tie flag. Per group, accuracy is kept in integer units of
1/16 (8 queries, half credits).

**Primary metric: selection accuracy.** One value per held-out group;
exact one-sided sign-flip tests over groups, computed by integer
convolution (tested against brute force). The exact sign test over group
signs is reported alongside. Negative log-likelihood and margin are
reported, not gated: training on twins and testing on independent inputs
may miscalibrate probabilities, which would move the likelihood without
changing a selection.

Paired comparisons on the same held-out groups:
`Delta_demo = accuracy(D+F_ASSOC) - accuracy(D)` and
`Delta_shuffle = accuracy(D+F_ASSOC) - accuracy(D+F_SHUFFLED)`; positive
means associated failure evidence helps.

## 9. Minimum useful effect and sample size

**delta_min = +0.05 accuracy (5 points) on the pairwise scale**, about 0.026
nats per query for a calibrated selector moving from 0.60 to 0.65. Derived
from pre-v1.5 evidence only: chance is 0.50; the failure summary's whole
standalone twin signal was +6.5 points (S7 0.565) and the strongest search
stage's +9.2 (S3 0.592), and an increment beyond demonstrations cannot
exceed the standalone signal; below about 5 points, a pairwise gain moves the
true key feature by under half a rank position among ten, too little to
build the compiler on. The threshold was set before the compute check below
and is not adjusted to it.

**Variance proxy** (`scripts/v15_power.py`, from completed v1.4 evidence):
on the 42 v1.4 groups, the S0 and S7 decisions on the same queries
(reproducing 0.6637 and 0.5655) disagree on 0.414 of queries, their
group-mean paired difference has standard deviation 0.2286, and the
within-group correlation is 0.005. Two disjoint views disagree more than a
nested D against D+F pair, so the proxy is conservative.

**Power**, exact sign-flip test at one-sided alpha 0.01, simulated with seed
20260928 over 1000 draws: 256 groups 0.868; 272 groups 0.895; **288 groups
0.909**; 68 groups at +0.10: 0.883. A first version of this simulation had a
convolution defect (shift 2v for v) that reported power near 0.1; it was
found by a brute-force check before any number was used.

Frozen: **288 test groups** (the smallest simulated value with power at
least 0.90), **floor 72 groups**. Gate D is a point estimate, so at a true
increment of exactly delta_min the joint probability of gates B and D is
about 0.5; at 1.5 times delta_min it is about 0.96. This is stated, not
fixed by moving a threshold.

## 10. Primary gates, all required

- **A.** D+F_ASSOC selects above chance on the independent-input test:
  mean accuracy above 0.5 and exact sign-flip p < 0.01.
- **B.** D+F_ASSOC beats D: mean Delta_demo above 0 and p < 0.01.
- **C.** D+F_ASSOC beats D+F_SHUFFLED: mean Delta_shuffle above 0 and
  p < 0.01.
- **D.** Mean Delta_demo at least delta_min = 0.05.
- **E.** Zero leakage in every view.
- **F.** No candidate-order shortcut: the choice is identical under both
  presentation orders for every query and condition.
- **G.** No target or group digest shared between the training resource and
  the test, and none repeated within the test.

No partial pass. Associated beating shuffled alone is never success.

## 11. Classification ladder, frozen, first rule wins

| rule | classification |
|---|---|
| any freeze, integrity, leakage (E), order (F) or overlap (G) failure | MIXED_OR_INCONCLUSIVE (integrity; no statistic is computed) |
| test groups below 72 | MIXED_OR_INCONCLUSIVE |
| A, B, C and D all pass on the test | **FAILURE_CONDITIONED_SELECTION_GENERALIZES** |
| the twin positive control passes A, B, C and D | **TWIN_ONLY_SELECTION_SIGNAL** |
| test groups below 288 | MIXED_OR_INCONCLUSIVE (a negative below the powered size) |
| C fails | **FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION** |
| B or D fails | **DEMONSTRATIONS_SUFFICIENT_FOR_SELECTION** (gate statement FAILURE_CONDITIONING_INCREMENT_NOT_ESTABLISHED) |
| otherwise | MIXED_OR_INCONCLUSIVE |

Association is checked before sufficiency because if associated evidence is
no better than matched shuffled evidence, the failure evidence carries no
pair-specific selection information at all, and "demonstrations suffice" is
not the right explanation. The twin control uses the same gates on 42 groups
and so has low power; it can only confirm a large twin effect.

## 12. Leakage boundary

A selector input holds only: the four frozen numeric view blocks, the grammar
state (5 numbers) and the two candidate tokens being scored. The scanner
rejects any other block, any missing or reordered field, any non-numeric
value, and any value equal to a target or group digest prefix or to a
generation seed (injected leaks are caught by tests). Target digest, group
digest, target and replicate index, seed, split label, the trusted target
token and `other_candidate_fits` are trusted metadata used only to build and
score queries. The candidate tokens appear only as the things scored.

## 13. Integrity, checked before any statistic

The evaluator computes nothing unless: protocol, manifest, implementation,
dependency trees, external grammar files, exclusion file and runtime
versions match; every file of the training hash list matches; the test
records are contiguous with no partial file; every test slot recorded the
frozen environment, versions, manifest, a re-verified freeze, a clean engine
state and a start inside the cap; every test group re-derives from the
grammar and seed law, obeys the twin law, differs in one legal key-feature
token, has the eight design cells, follows the per-target seed law with
distinct seeds and no shared input grid, and uses digests absent from the
exclusion set and unique in the test; the training and test sets share no
digest; and no view leaks. `--integrity-only` runs exactly these checks and
exits; it is run and read before the scored evaluation.

## 14. Adversarial questions, answered before freeze

- More dimensions for D+F_ASSOC? No: identical width and standardizer; D's
  F block is zero and inert; D+F_SHUFFLED has the same values rearranged.
- Can order reveal the target? No: hash order independent of the truth,
  order-invariant choice, ties give no choice.
- Can the shuffle distort the demonstration distribution? No: D never moves;
  F moves only between demonstration-similar queries of other groups.
- Does a target digest cross splits? No: exclusion set, within-test
  uniqueness, and the overlap check.
- Can a pair appear twice under reversed order? No: the group digest is
  order-free and deduplicated.
- Does the scorer see target tokens as evidence? No: evidence is numeric and
  scanned; tokens appear only as the candidates scored.
- Is the test independent of v1.4 pairs? Yes: new digests, new seeds,
  independent inputs.
- Is D the strongest existing demonstration view? Yes: the union of every
  demonstration-only representation the pipeline produces; verification is
  reported separately because it executes candidates.
- Does a hyperparameter depend on the test? No: lambda, the fit, views,
  conditions, shuffle, metrics and gates are frozen here; there is no
  validation-based choice at all.
- Can PASS happen when D+F_ASSOC fails to beat D? No: gate B is required
  (tested for every other gate combination).

## 15. Controls, verified on synthetic fixtures before any scientific run

Planted failure signal beyond demonstrations: every gate passes. Pure-noise
failure evidence: gates B and C fail. Failure evidence redundant with
demonstrations: no increment. Permuted training labels: no above-chance
selection. No evidence at all: every balanced group scores exactly one
half. Duplicated candidate: a tie with half credit and negative
log-likelihood log 2. Candidate-order permutation: identical choices.
Leftover shuffle queries: a valid 3-cycle.

## 16. Reproducibility

Generation is deadline-bound and not reproducible (v1.3 erratum 3). The
evaluation is deterministic: pure functions, fixed orders, single-threaded
linear algebra; it is run twice and the reports must be byte-identical.

## 17. Order after freeze

1. One adversarial review of this frozen protocol and implementation;
   blocking findings are corrected by a recorded erratum before any test
   group exists.
2. `scripts/run_v15_generation.sh`, detached, one writer, until 288 unique
   groups or a cap.
3. `scripts/evaluate_v15_selection.py --integrity-only`, read before scoring.
4. `scripts/run_v15_evaluation.sh`: the integrity gate, the sealed
   evaluator twice, byte comparison.
5. Record the classification. STOP.

Not authorized in v1.5: training anything other than the frozen pairwise
fit on the frozen training resource; any change to the proposer, grammar,
K, observer, engine or compiler; new solvers, primitives, DSLs or
task-specific branches; the 1000 ARC tasks; evaluation DEV; protected
HOLDOUT; Kaggle; any Step-B candidate, journal, output, E_transfer or
Lockbox. No threshold, view, condition, law or rule changes after freeze.

## 18. Claim ceiling and what an outcome licenses

Even a full pass earns at most: **FAILURE-CONDITIONED SELECTION WITH
INCREMENTAL VALUE BEYOND DEMONSTRATIONS ON UNSEEN INDEPENDENT-INPUT TARGET
PAIRS.** Not autonomous construction, capability extension, constructive
reach, L3 semantic extension, invention, transfer or ARC-AGI-2 score.

Only FAILURE_CONDITIONED_SELECTION_GENERALIZES licenses the next
preregistered block (the generic ConstructiveExtensionCompiler and
end-to-end K + {e}), and it licenses neither the 1000-task
characterization, evaluation DEV nor protected HOLDOUT. TWIN_ONLY points the
repair at generalization under input variation;
DEMONSTRATIONS_SUFFICIENT_FOR_SELECTION means the scorer must not simply be
made larger; FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION points at which
failure channel is tied to the constructive decision. Every negative is
preserved.

## 19. Deviations from the directive, each with its reason

1. The primary loss is the 0-1 selection loss, not the log-likelihood:
   selection is the decision under test, it is bounded, it has a pre-v1.5
   variance proxy, and it is robust to the calibration shift from twin
   training to independent-input testing. The log-likelihood is reported.
2. Newton's method to the unique optimum replaces v1.2's early stopping, so
   no validation data and no stopping rule exist to tune; equality with the
   v1.2 update rule's fixed point is tested.
3. FAILURE_ASSOCIATION_NOT_CAUSAL is checked before
   DEMONSTRATIONS_SUFFICIENT (section 11), and a negative requires the
   powered size.
4. Candidate verification is reported descriptively rather than used as a
   demonstration baseline, because it executes the candidates.
5. The search-only view uses hashed buckets of selector-predicate operators,
   so it needs no hand-written feature vocabulary.

## 20. Admission pilot and caps

Admission pilot, 2026-09-28, `scripts/generate_v15_pairs.py pilot` on seeds
from 400,000,000, output `logs/v15_pilot/`, never scored: it measured only
admission, runtime and the rejection profile; no selector existed, and the
verification diagnostic was deliberately not computed on pilot pairs.

| quantity | value |
|---|---|
| slots / admitted groups | 34 / 3; per-slot admission 0.088 (exact 95 percent interval 0.019 to 0.237) |
| by family (admitted / slots) | (0,0) 0/7, (1,0) 2/7, (0,1) 1/7, (1,1) 0/7, (0,0,0) 0/6 |
| time | 84.7 s per slot, 960 s per admitted group |
| pair / replicate attempts | 789 / 7,667 |
| rejections | TARGET_NOT_FITTABLE 6,129; TARGET_EXECUTION_UNDEFINED 1,041; PAIR_REPLICATES_SHORT 758; OTHER_FROZEN_CODE 224; BASELINE_SOLVED 44; NO_INFORMATIVE_TFG 7 |
| novelty skips before any engine run | EXCLUDED_TARGET_DIGEST 27; EXCLUDED_GROUP_DIGEST 1 |

Admission is well below v1.4's twin rate. The novelty rule is the likely
reason: the earlier corpora already used the most easily admitted targets,
and every test target must be new.

**Caps, frozen.** Stop at the first of: 288 unique groups; 9,000 slots; 432,000
s (120 h) of wall clock from the first start. At the pilot's point estimate,
288 groups need about 3,260 slots and 77 h; at the upper end of the
admission interval, 29 h; at the lower end, the 120 h cap would yield about 95
groups. The 9,000-slot cap keeps every test pair seed below 390,000,000,
under the pilot base. If a cap binds first, the ladder decides: a positive
at 72 groups or more stands, since power affects only false negatives, and
a negative below 288 is MIXED_OR_INCONCLUSIVE. The effect threshold and the
target group count are not changed to fit compute.

Static tests: `tests/test_v15_selection_feasibility.py`.
