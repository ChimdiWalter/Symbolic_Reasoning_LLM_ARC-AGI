# Item-2 constructive corpus v1.3: contrastive design, preregistration

Written 2026-09-24, before any v1.3 episode was generated and before any v1.3
outcome exists. v1.2 is preserved unchanged and is not regenerated. The frozen
scorer verdict and its weights are untouched. Nothing in this document is
implemented in the block that wrote it.

Claim ceiling for the block that writes this: the design is preregistered and
hashed. No corpus, no fit and no result is claimed.

## 1. Why v1.2 could not answer the question

The v1.2 diagnosis established three things. Scorer capacity is not the
limiting factor, because a bounded nonlinear readout does not rescue the
candidate features. Summary compression is not the limiting factor, because
all 180 episodes carry distinct candidate vectors with zero collisions, and a
richer 42-field descriptor taken straight from the stored graph performs worse
than demonstration statistics. And no evidence group recovers the target at
all: demonstration statistics predict the first partition token at 0.383
against a 0.411 majority baseline.

The corpus was not short of opportunity. Of the closest quartile of episode
pairs by demonstration distance, 45 of 45 had different targets. The frontier
had exactly the cases it exists for and did not distinguish them.

### The mechanism this points at

The failure frontier is expressed in the deployed reasoner's own vocabulary:
segmentation variants, correspondences, selectors, parameter fitting, and
near-miss programs built from its operators. The target is expressed in the
constructive grammar's vocabulary: a partition, some selects, a key feature, a
paint. These are different coordinate systems, and nothing in v1.2 required
them to be related. A trace saying that growth and translation were tried and
that a parameter fit failed carries no particular information about whether
the generating target partitioned by enclosed regions and keyed by area.

v1.3 does not attempt to fix that by changing the engine, the grammar or the
fitter, all of which stay frozen. It changes the **experimental design** so
that the question becomes answerable with a clean null, and so that the answer
is informative either way.

## 2. What v1.3 changes, and what it does not

Changed: episodes are generated in **matched contrastive pairs**, and the
primary test becomes a **paired forced choice** rather than recovery of a
target from a single episode.

Not changed: the constructive grammar, its bounds, operators, terminals and
banned families; the baseline and its budget and ordering; the registered
occurrence-scoped fitter and the fairness guard; the repaired full-engine
observation path; the informative-evidence gate; the prohibition on reading
any hidden output; and the eighteen-feature model view, which is carried
forward unchanged so results remain comparable to v1.2.

No new solver, no task-family dispatch, no hand-authored operator, no answer
predictor and no lookup of any kind is introduced.

## 3. Matched contrastive pairs

A pair is two episodes whose targets differ in **exactly one** grammar choice,
with everything else about the target identical.

Three contrast types, allocated equally:

| contrast type | what differs between the two targets |
|---|---|
| PARTITION | the partition terminal of one block |
| SELECT | the predicate terminal of one select, or the presence of one select |
| FEATURE | the key-feature terminal of one block |

Both members of a pair are generated from the same deterministic seed base, so
the pair is reproducible and the contrast is the only intended difference.

Both members must independently pass the **unchanged v1.2 admission law**:
the baseline must not solve it, the target must be fittable by the registered
occurrence-scoped fitter with exact replay, and the episode's own failure graph
must pass the informative-evidence gate. A pair is admitted only if both
members are admitted. No pair is filtered on any property of its frontiers.

**That last sentence is load bearing.** Selecting pairs whose frontiers happen
to differ would enrich the corpus for the very property under test and make a
positive result circular. v1.3 therefore applies no frontier-based pair
filter, and accepts a lower admission rate as the price.

## 4. The primary test: paired forced choice

For a held-out pair, the model is given the two episodes' evidence and the two
targets, and must decide which evidence belongs to which target. Chance is
exactly 0.5, and the null is therefore exact rather than estimated.

Scored by the same state-conditional log-linear model and the same per-token
target log-likelihood used in the frozen v1.2 experiment. The assignment is
chosen by total log-likelihood over the two possible matchings, which is a
deterministic rule with no tunable component.

This is strictly more powerful than v1.2's ten-way token recovery, and it uses
the contrast structure rather than discarding it.

## 5. Conditions, fixed now

Each condition supplies different evidence to the same trained model on the
same held-out pairs.

| condition | evidence |
|---|---|
| frontier plus demonstration | the full eighteen-feature view |
| demonstration only | the five demonstration features, candidates at the fit-set mean |
| frontier only | the ten candidate features, demonstrations at the fit-set mean |
| swapped | the two members' evidence exchanged before the decision |
| none | the fit-set mean vector for both members |

Ablations are filled with the fit-set mean, which standardizes to zero, for
the reason established in the v1.2 amendment: raw zero is an extreme
extrapolation rather than a neutral value.

## 6. Success rule, frozen

**Primary.** Paired accuracy under *frontier plus demonstration* on held-out
pairs must exceed 0.5 with a one-sided exact binomial p below 0.01.

**The frontier claim.** Paired accuracy under *frontier plus demonstration*
must exceed paired accuracy under *demonstration only* by at least 0.05
absolute, and that difference must hold on at least 4 of 5 folds.

Both are required. The first alone would be satisfiable by demonstration
statistics, which v1.2 already showed carry a little signal, and the frontier
is what is on trial.

*Frontier only* above chance is reported and is not a gate, because it cannot
separate frontier information from information the frontier shares with the
demonstrations. *Swapped* and *none* must not exceed chance materially; if
either does, the result is void and reported as such.

No threshold in this section may be adjusted after seeing any v1.3 outcome.

## 7. The measurement that is valuable either way

The **pair admission rate** is a scientific result in its own right, not
bookkeeping. It answers how often two targets differing in one grammar choice
both survive the admission law. It is reported per contrast type.

If the primary test passes, v1.3 establishes that when the corpus is built
contrastively the frontier can distinguish targets. If it fails, v1.3
establishes that the frontier does not distinguish even minimally different
targets under a clean null, which is a stronger negative than v1.2's and
would point at the vocabulary mismatch in section 1 as the real obstacle.

Neither outcome is a disappointment, and the design is chosen so that both are
publishable.

## 8. Scale, and the sample-size rule

The raw-descriptor test in the v1.2 diagnosis was confounded by carrying 42
features against 144 training episodes per fold. v1.3 fixes that
prospectively.

Required: **at least 200 admitted training pairs**, being at least 400
admitted training episodes, which gives roughly ten episodes per feature for a
42-field descriptor.

Sizing rule, fixed now as a formula rather than a later choice. A bounded
pilot of 300 pair slots measures the pair admission rate p. The full run then
requests `ceil(200 / p)` pair slots, capped at 6,000. If the cap is reached
before 200 pairs are admitted, the corpus is reported as underpowered at its
achieved size and the primary test is still run and reported, with the reduced
power stated. The cap is not raised afterwards.

Validation and structural holdout are allocated after the training target is
met, at 15 percent and 15 percent of admitted pairs respectively, assigned by
ascending pair digest so the split is content-determined.

## 9. Folds and splits

Five folds over admitted training pairs, assigned by ascending pair digest,
fold equal to index modulo five. Both members of a pair always share a fold,
so no pair is split across training and evaluation. Pair digests are disjoint
across training, validation and holdout by construction, asserted at run time.

## 10. Seeds and budgets

Root seed 20260924, disjoint from v1.1's 20260903 and v1.2's 20260923. Pair
seeds from 31000, validation from 32000, holdout from 33000. Budgets unchanged
from v1.2: per target 90 seconds, baseline search 8, graph extraction 2,
full-engine observation 8. Attempts per slot capped at 25 as before.

## 11. Leakage

The eighteen-feature model view is carried forward unchanged, and the hardened
v1.2 leak scanner applies unmodified, requiring zero violations before any
fit. In the paired setting one additional prohibition is explicit: the model
is told that the two targets differ in one grammar choice, which is inherent
to the forced-choice task, and is never told which contrast type applies, nor
any pair identifier, nor either target's digest or family label.

## 12. What v1.3 cannot establish

It cannot establish constructive reach, autonomous construction, semantic
extension, transfer or any ARC score. It cannot establish structural-family
generalization, which remains unmeasured. A positive result would establish
only that failure evidence can distinguish minimally different constructive
targets in a contrastively built corpus, which is the prerequisite the
programme currently lacks and nothing beyond it.

## 13. Stop points

Generation, fitting and testing are three separate blocks. The corpus is
generated and audited before any fit. The extension compiler stays blocked
throughout and is not licensed by any outcome of v1.3 alone.
