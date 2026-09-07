# Prospective abstraction-transfer experiment: result

Design pinned at commit `92cf6f7` before any transfer outcome was opened. Run at
`PYTHONHASHSEED=0`, clean tree. Results
`outputs/tti/abstraction_transfer/results.json` sha256
`2d0ca23b7b03ab9bdb87374bcf4bb4948c8c1386510ec47e641c188748be6a38`; ablations
sha256 `d68f73582f7e2b9ce8efaf054c004b94bc448bf7d0a726ba1ad8518b451da217`;
libraries frozen before transfer.

## Hypothesis and answer

> Do abstractions formed from discovered source programs improve correct target
> predictions or search efficiency more than retaining concrete schemas alone?

**No.** Concrete-schema reuse beat both abstraction rules on every measure.
Abstraction rule R1 was degenerate and provably indistinguishable from its
unlearned control. Rule R2 beat its matched control but lost to concrete reuse.

A separate result did survive: **the held-out prediction rescue reproduced
prospectively, and this time it is ablation-necessary.**

## Pools and acquisition, fully charged

| item | value |
| --- | --- |
| source pool | namespace 8,100,000, 16 episodes, 4 per family |
| transfer pool | namespace 8,900,000, 24 episodes, 6 per family |
| target-identity overlap between pools | **0** |
| source searches that discovered a program | 13 of 16 |
| source searches that failed | 3 |
| acquisition units charged, total | **14,995** |
| of which spent on failed searches | 8,640 |
| distinct concrete structures retained | 9 |

Every source search is charged, successful or not. This is the complete cost of
the procedure that produced the library, unlike the retrospective subtotal in
the previous prototype.

## What the two declared abstraction rules produced

| rule | concepts | members | free slots | expansion | identical to its control |
| --- | --- | --- | --- | --- | --- |
| R1, group by family | 1 | 8 | partition, feature, partition, feature | 1,600 | **yes** |
| R2, group by family and first partition | 1 | 7 | feature, feature | 100 | no |

R1 generalized every terminal position, so its concept covers the entire (0,0)
subspace. Its policy rows are **identical to the unlearned control on every one
of the 24 targets**, in units and in the program found. That degeneracy was
predicted from development evidence before this run and is now confirmed
prospectively. It is the failure mode where a concept that frees many choices
simply recreates the search space.

## Transfer, 24 targets, common budget 3,000 candidate fits

| arm | demo fits | held-out | exact AST | solved in prior phase | mean units | total units |
| --- | --- | --- | --- | --- | --- | --- |
| A ordinary | 19 | 16 | 1 | 0 | 965.0 | 23,159 |
| B concrete then ordinary | 19 | **17** | 1 | 13 | **772.2** | **18,533** |
| C concepts R1 | 19 | 16 | 1 | 17 | 965.0 | 23,159 |
| C concepts R2 | 19 | 16 | 1 | 14 | 921.6 | 22,119 |
| D control R1 | 19 | 16 | 1 | 17 | 965.0 | 23,159 |
| D control R2 | 19 | 16 | 1 | 0 | 1006.6 | 24,159 |

**No arm improved demonstration-fit coverage.** All six fit the same 19 of 24.
Nothing here extended what the reasoner can solve.

**Concrete reuse reduced cost.** B is cheaper on 13 targets, costlier on 6,
median delta 47 units cheaper, 4,626 units saved in total against ordinary
search.

**The learned R2 concept beat its matched-size control**, 22,119 against 24,159
units, cheaper on 14 of 24. Since the control frees the same slot positions and
exposes a hypothesis space of identical size, that difference is attributable to
which terminals the abstraction fixed, not to how much space it exposed. But
R2 also beat ordinary search only slightly, 22,119 against 23,159, and was
cheaper than concrete reuse on just 6 of 24.

## The held-out rescue, reproduced and now necessary

Target 23, family (1,1):

| | ordinary search | concrete library |
| --- | --- | --- |
| demonstrations fit | yes, at 1,861 units | yes, at 5 units |
| held-out outputs correct | **no** | **yes** |

Ordinary search found a program that fit every demonstration and predicted the
held-out grids wrongly. The library found a different program at 5 units that
predicted them correctly. This is the second instance of the episode-8
phenomenon, now in a prospectively frozen setting with disjoint pools.

Unlike episode 8's case, this one is **ablation-necessary**. Removing that single
entry and rerunning the same policy: the demonstration fit persists, but the
held-out prediction flips to wrong and the cost rises from 5 to 1,861 units.

## Ablations, fitting and held-out reported separately

13 entry ablations, each removing one entry that had solved a target in the
prior phase and rerunning the same policy.

| outcome | count |
| --- | --- |
| demonstration fits lost | **0** |
| demonstration fits that persist | 13 |
| held-out correctness lost | **1** |
| median unit increase on removal | 55 |

No single entry is necessary for FITTING: the library has redundant support
everywhere. Exactly one entry is necessary for a CORRECT PREDICTION. These are
different questions and they diverge here, which is why the previous report's
single "attributable" column was inadequate.

At the library level, where redundant entries can share responsibility even when
none is individually necessary: B against A is 18,533 units against 23,159, and
17 held-out successes against 16.

Concept ablation: both rules produced exactly one concept, so removing it reduces
policy C to ordinary search, which arm A already measures. R1 collapses to
exactly A. R2 gives back 1,040 units.

## Cost, honestly amortized

Acquisition charged 14,995 units. Concrete reuse saved 4,626 units across 24
targets, about 193 per target. At that rate acquisition would be repaid after
roughly 78 targets.

That figure is an **extrapolation from 24 targets, not a deployment
prediction.** It assumes the saving rate holds on unseen tasks, which this
experiment cannot establish. It is reported because the previous prototype's
break-even figure was computed from a retrospective subtotal and was withdrawn;
this one at least charges every source search including the three that failed.

Correctness travels with cost: the cheaper arm is also the arm with one more
correct held-out prediction, so this is not a cheap-but-wrong result.

## Exact AST recovery

One target in every arm, episode 5, where ordinary search found the generator's
own schema at 1,249 units and it was held-out correct. This is the first exact
recovery seen in this line of work; every previous run reported zero. It remains
secondary, since several programs explain the same demonstrations and 16 of the
19 fits generalize without being the generator's schema.

## Claims earned

Earned:

- Source-derived **concrete** schemas, acquired without the target being shown,
  reduce search cost on a disjoint set of tasks under a matched budget, and in
  one case changed a demonstration-fitting but incorrect explanation into a
  correct held-out prediction, with that entry shown necessary by ablation.
- A learned abstraction can beat an unlearned control exposing the same
  hypothesis space, which distinguishes choosing useful terminals from merely
  exposing more choices.

Not earned, and not claimed:

- Any increase in what the reasoner can solve. Coverage was identical at 19 of
  24 across all six arms.
- That abstraction beats concrete reuse. The measured answer is the opposite.
- Globally new primitive semantics, greater evaluator expressivity, an ARC
  leaderboard result, or repeated open-ended self-extension.
- Full-pipeline leave-one-out certification. The library is frozen from disjoint
  source tasks, which is permitted, but per-fold proposal and fitting were not
  rebuilt inside each held-out fold, so no certification is claimed.

## Limitations

- 24 transfer targets and 16 source episodes. Differences of one held-out
  success are single episodes, not resolvable effects.
- Both rules produced exactly one concept each, so the abstraction arm is thin.
  A grouping rule yielding several concepts was not tested.
- The unlearned control fixes non-free positions to the first vocabulary
  terminal. Another control choice could change the R2 comparison.
- Results are on a synthetic fixture generator whose distribution determines how
  often simple programs suffice.
- The human-designed fitter, anti-unifier, grouping rules and policies are
  research infrastructure, not machine-invented operations.
