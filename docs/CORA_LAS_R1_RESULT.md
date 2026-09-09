# LAS-R1: replication of the frozen LAS-v1 library on 256 new targets

## Verdict

**NOT ROBUSTLY REPLICATED.**

The rule was fixed and committed before any outcome existed: the primary
comparison is LAS against CONCRETE, paired by target on held-out output
success, and the verdict is ROBUSTLY REPLICATED only if the difference is
strictly positive **and** the lower bound of the 95 per cent paired bootstrap
interval is strictly above zero. The difference is +3, the interval is
[-1, 8], and the lower bound is not above zero. The rule is not redefined.

## Provenance

| item | value |
| --- | --- |
| launch commit | `86f1fb521d693a4637027e5281e78220b7778fdc` |
| dirty tree at launch | 0 |
| runtime code hash | `aa85b8eb76b88a86...` |
| LAS-v1 frozen library | `f2f6c13956b4879d...`, verified before the run |
| LAS-R1 pre-outcome freeze | `d1f75475a2e5f82e...` |
| analysis | `outputs/tti/las_r1/analysis.json` |
| ablations | sha256 `daa7dcc00d34ef9419c37c91ad37e2f496b15c7afe8630a0c200049a5f1c12fe` |
| started, finished | 2026-09-08T20:50:02Z, 2026-09-09T02:11:34Z |

The launch commit is the commit that ran, unlike the earlier failure-signal
study. Nothing was learned, reselected or retrained: the LAS-v1 libraries were
loaded verbatim and their hash checked before anything else happened.

## Population

256 targets, 64 per family, namespace 12,000,000, never used by any earlier
study in this line. No shortfalls. 28 candidate targets were skipped by
identity-only de-collision against 116 prior identities, each skip recorded with
its seed, family, digest and reason. The rule never inspects outcome, cost or
difficulty. Final target-identity overlap with the source, validate and transfer
pools of every earlier study is zero.

## Primary and secondary comparisons

| comparison | LAS | other | diff | wins/losses | 95% CI | lower > 0 | exact McNemar |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **vs CONCRETE (primary)** | 164 | 161 | **+3** | 4/1 | **[-1, 8]** | **no** | p = 0.375 |
| vs ORDINARY | 164 | 160 | +4 | 4/0 | [1, 8] | yes | p = 0.125 |
| vs R1 | 164 | 160 | +4 | 4/0 | [1, 8] | yes | p = 0.125 |
| vs R2 | 164 | 160 | +4 | 4/0 | [1, 8] | yes | p = 0.125 |

The primary comparison rests on five targets: 160 where both are correct, 91
where both are wrong, 4 that only LAS gets right, and 1 that only CONCRETE gets
right. That is why an interval computed on 256 paired targets still straddles
zero. The secondary comparisons clear their lower bound, but they are secondary
and cannot substitute for the declared primary.

## Full policy table

| policy | fits | held-out | wrong-but-consistent | undefined | exhausted | solved in prior | units | wall clock |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ordinary | 188 | 160 | 28 | 2 | 68 | 0 | 268,937 | 519.9 s |
| concrete | 188 | 161 | 27 | 2 | 68 | 73 | 254,566 | 484.3 s |
| R1 | 188 | 160 | 28 | 2 | 68 | 160 | 248,695 | 493.7 s |
| R2 | 188 | 160 | 28 | 2 | 68 | 156 | 246,077 | 489.5 s |
| **LAS** | 188 | **164** | **24** | 2 | 68 | 176 | **243,503** | **480.5 s** |

**Every policy fit exactly the same 188 of 256 targets.** Nothing extended solve
reach. All differences are in which explanation was selected.

**Zero bounded search-reach witnesses.** There is no target where ordinary
search failed within budget and LAS succeeded.

## The matched-null distribution: the criterion that did pass

| quantity | value |
| --- | --- |
| controls | 32, all complete |
| null held-out range | 117 to 162 |
| null mean, median | 147.59, 157 |
| LAS held-out | **164** |
| controls strictly beaten by LAS | **32 of 32** (criterion required 31) |
| controls more expensive than LAS | 32 of 32 |

Each control shares LAS's concept count, mask structure, free-slot types,
per-concept and total expansion cardinality, budget and enumeration mechanics.
The only difference is that its fixed terminals come from a frozen
pseudo-random rule rather than from source discoveries. No control was
performance-filtered, and none was rejected under the static legality rule.

LAS exceeds every one of them on correctness and on cost. **This is the
strongest evidence in the study that the retained invariants carry information
rather than merely exposing a larger hypothesis space.** It does not rescue the
primary verdict, because the primary comparator is concrete reuse, not a random
control.

## Per family, descriptive only

| family | n | ordinary | concrete | R1 | R2 | LAS |
| --- | --- | --- | --- | --- | --- | --- |
| (0,0) | 64 | 56 | 56 | 56 | 56 | 57 |
| (1,0) | 64 | 44 | 44 | 44 | 44 | 44 |
| (0,1) | 64 | 39 | 38 | 39 | 39 | 40 |
| (1,1) | 64 | 21 | 23 | 21 | 21 | 23 |

No family is promoted as a headline. The 256-target paired comparison is
primary, and this stratification is exploratory.

## Group ablations

Partitions were defined mechanically before any outcome. Family-origin and
whole-LAS both remove all eight concepts, because every LAS-v1 concept came from
family (0,0); removing the whole prior reduces the policy to ordinary search,
which the ordinary arm already measured on every target, so those two are
answered by row-by-row comparison rather than a redundant rerun.

| partition | removes | fits lost | held-out lost | held-out gained | program identity changed | cost change |
| --- | --- | --- | --- | --- | --- | --- |
| A source-group | 4 of 8 | 0 | 1 | 0 | 93 | **-2,617** |
| B invariant-signature | 1 of 8 | 0 | 1 | 0 | 93 | **-2,617** |
| C family-origin | 8 of 8 | 0 | 4 | 0 | 11 | +25,434 |
| D whole-LAS | 8 of 8 | 0 | 4 | 0 | 11 | +25,434 |

The signature for partition B is `feature0=touches_border`, a single retained
invariant.

Three things follow. **No ablation loses a single demonstration fit**, so the
prior never changes what is solvable, only what is selected. **Removing the
whole prior costs exactly the 4 held-out successes** that LAS holds over
ordinary search, and adds back the 25,434 units the prior saves, so the
whole-prior effect is causally coherent. And **partitions A and B are
identical** in every column: removing four concepts does exactly what removing
the single top concept does, so the other three in that source group contribute
nothing measurable, and one concept accounts for one of the four held-out gains
while the remaining seven jointly account for three.

Removing concepts A or B makes the system 2,617 units *cheaper*, because the
prior phase itself costs units and the fallback finds the same program anyway.
That is recorded rather than smoothed away.

## Cost

**LAS-R1 target-time.** LAS used 243,503 units against ordinary search's
268,937, saving 25,434 units over 256 targets while also being correct more
often. This reverses the LAS-v1 finding, where LAS bought correctness with
extra compute.

**Historical learned-system cost**, charging acquisition and validation once and
never re-charging them:

| component | units |
| --- | --- |
| LAS-v1 acquisition | 20,936 |
| LAS-v1 source validation | 21,603 |
| LAS-v1 transfer, 24 targets | 22,762 |
| LAS-R1 transfer, 256 targets | 243,503 |
| **total learned** | **308,804** |
| ordinary search on the same 280 targets | 291,892 |
| difference | +16,912 |

Amortized over all 280 targets the learned system costs 1,102.9 units per target
against ordinary search's 1,042.5. **The learned system has not yet repaid its
acquisition and validation cost**, though the gap has narrowed from a large
deficit to about 6 per cent, and the marginal cost on new targets is now
favourable. A break-even projection would be an extrapolation and is not made.

Candidate-fit units are not wall clock, and both are reported above.

## FULL-PIPELINE LOO NOT MEASURED

This replication evaluates the predictive effect of frozen cross-task knowledge.
No certification procedure was added and none is claimed.

## Claims earned

- The frozen LAS-v1 library **did not robustly replicate** its advantage over
  concrete reuse on 256 new targets, under the rule declared in advance.
- The library's held-out advantage over ordinary search, over both hand-authored
  abstraction rules, and over all 32 matched-null controls **is consistent and
  directionally positive**, and the whole-prior ablation shows it is causally
  attributable to the prior as a whole.
- **LAS beats 32 of 32 matched-space nulls** on correctness and cost, which
  supports the narrower claim that the specific retained invariants carry
  information rather than merely enlarging the search space.
- On new targets the learned prior now **reduces** search cost rather than
  increasing it.

## Claims not earned

- Robust replication of the LAS-v1 primary result. It failed its own test.
- Any increase in problem-solving reach: identical 188 of 256 coverage across
  all policies, and zero search-reach witnesses.
- Repayment of the historical learning cost, which remains 16,912 units negative
  over 280 targets.
- Necessity of any individual concept: no ablation lost a single fit, and one
  concept accounts for only one of four held-out gains.
- Semantic expressivity growth, primitive invention, Level-4 CORA-SCIENCE
  success, Level-3B capability transfer, open-ended self-extension, or any ARC
  leaderboard implication.

## What this means for the direction

The honest reading is that LAS-v1's headline was a small-sample result whose
direction persisted but whose margin did not survive a proper test, while a
different and better-powered claim did survive: the learned invariants beat a
full distribution of matched controls decisively, 32 out of 32, and now do so
while saving compute.

Per the pre-declared decision tree this is CASE A. LAS-v1 is preserved as a
small-sample positive whose direction did not robustly reproduce. No LAS-v2, no
retraining, no mask changes, no objective changes, no GPN, no global promotion.

## Step-B status, quantitative only

At 2026-09-09T02:28:53Z: runner pid 106593 alive, elapsed 12 days 22:19:15,
22 worker processes, phase `propose K2 175/497`, journal 200 lines, zero error
signatures, no final output hash present, host load average 22.66. Nothing in
this study read, modified, accelerated or delayed it.
