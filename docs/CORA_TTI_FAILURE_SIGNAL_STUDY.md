# Failure-signal study: complete result and decision

Bounded study in `cora-tti-dev`, now finished at all 24 episodes. The v2c census
is unchanged, its 13 admitted supplied-schema examples and every reported
limitation stand, the repeated-Select and three-block NO-GO findings are
retained, and the live Step-B experiment was neither read nor modified.

This document replaces a first version written before the run finished. That
version described the executing source by a commit that did not exist at launch,
and called the second ranking rule a measure of joint coverage. Both are
corrected here and the corrections are described rather than quietly applied.
The measured artifact itself was not rerun or overwritten.

## 1. Provenance, as it actually happened

| item | value |
| --- | --- |
| launched | 2026-09-07T03:21:29Z |
| HEAD at launch | `63602e6f0bb0903bddbe445010551fe819cbd0d0` |
| working tree at launch | that commit plus the study files, uncommitted |
| those files committed as | `73d96ae6c4a6e65c28d2c02abab2ed07322a90b9`, authored 03:22:13Z |
| finished | 2026-09-07T03:35:01Z |
| results | `outputs/tti/failure_signal_study/results.json`, sha256 `339aae08a9376b573861a757c5c4191001c339c722780f16d6389198b122c432` |

The study recorded `git_commit` by calling git at REPORT time, so the result file
names `73d96ae`, a commit authored 44 seconds after the process started. **This
was not a pre-launch clean-tree freeze.** The executed source was the working
tree, whose content is pinned independently by the study's own `code_hash`
(`06cd3799e7d0655e...`) computed at run time over the observer, the study module,
the baseline and the fitter. That hash, not the commit, is what identifies what
ran. The v2c census by contrast was frozen properly, and the difference is
recorded rather than glossed.

## 2. Outcome vocabulary

- **DEMONSTRATION_FIT_FOUND**: a candidate fit every demonstration exactly within
  the fit-attempt budget.
- **HELDOUT_OUTPUT_SUCCESS**: that program also predicted every held-out output
  correctly.
- **FULL_PIPELINE_LOO**: **not measured by this study.**

No result here is a certified ARC solve or a semantic invention. Nothing here
reruns failure extraction, proposal and induction per held-out demonstration.

## 3. All six arms, all 24 episodes

Costs are over ALL episodes, including those that exhausted the budget, not
averaged over successes only.

| arm | fit | held-out success | undefined held-out | exact AST | exhausted | mean units, all episodes |
| --- | --- | --- | --- | --- | --- | --- |
| none | 19/24 | 15/24 | 0 | 0 | 5 | 847.5 |
| aggregate | 19/24 | 15/24 | 0 | 0 | 5 | 1012.6 |
| associated:individual | 7/24 | 7/24 | 0 | 0 | 17 | 2671.8 |
| associated:coverage-sum | 8/24 | 8/24 | 0 | 0 | 16 | 2493.8 |
| shuffled:individual | 6/24 | 6/24 | 0 | 0 | 18 | 2585.5 |
| shuffled:coverage-sum | 6/24 | 6/24 | 0 | 0 | 18 | 2423.5 |

Neither ranking rule is hidden and neither is selected as the headline.

Paired against unconditioned search:

| arm | fit only by arm | fit only by none | cheaper | costlier | median delta units |
| --- | --- | --- | --- | --- | --- |
| aggregate | 0 | 0 | 1 | 18 | +200 |
| associated:individual | 2 | 14 | 0 | 5 | +2455 |
| associated:coverage-sum | 3 | 14 | 1 | 4 | +1254 |
| shuffled:individual | 0 | 13 | 0 | 6 | +1441.5 |
| shuffled:coverage-sum | 0 | 13 | 0 | 6 | +927.5 |

The aggregate arm fits exactly the same 19 episodes as unconditioned search at a
median cost difference of exactly the 200-unit extraction charge. On this
episode set its scoring reordered nothing and paid for the privilege.

## 4. Real trace against the shuffled control

| rule | real fits | shuffled fits | fit by real only | fit by shuffled only | both |
| --- | --- | --- | --- | --- | --- |
| individual | 7 | 6 | 6 episodes | 5 episodes | 1 |
| coverage-sum | 8 | 6 | 7 episodes | 5 episodes | 1 |

The two disagree almost completely: they overlap on a single episode. A
representation carrying usable task-specific signal should fit a superset of
what a wrong-task representation fits, or at least overlap heavily with it. That
the real trace and a different episode's trace succeed on nearly disjoint
episodes is what a pair of essentially arbitrary reorderings looks like.

## 5. Episode 18, the positive exception, in full

| property | value |
| --- | --- |
| arm that fit it | `associated:coverage-sum`, and no other arm |
| target family | (1,1) |
| found program family | **(1,0)** |
| is the generator's schema | **no** |
| rank of the solution | 2051 |
| search units | 2052 |
| extraction units | 200 |
| total units | 2252 |
| held-out outputs correct | yes, 4 of 4 defined |
| seconds inside `run_condition` | 5.81, excluding the baseline run |

So episode 18 is a real HELDOUT_OUTPUT_SUCCESS that only one arm achieved, and
the program it found is a simpler two-block program of a different family from
the generator's. Its found family was read from the found schema, not inferred
from the target.

It remains one episode. Episodes 19, 21 and 23 are also (1,1) and unconditioned
search fit them at 52, 53 and 60 units, so the target's family does not
determine difficulty, and the ordering advantage cannot be attributed to family
allocation on this evidence.

## 6. Episode population, stated accurately

`build_episode` enforces: the sampled target instantiates; at least 3
demonstrations render, defined and non-trivial; the target itself fits exactly
under the scoped fitter; at least 4 held-out grids render defined, non-trivial
outputs.

It does **not** enforce: that the single-block baseline fails; local
irreducibility; historical exclusion against the v1.1 attempted set; run-wide
duplicate exclusion; the frozen-probe coverage floor; witness separation. These
episodes therefore do **not** inherit the v2c admission guarantees.

- 24 episodes, 24 distinct target schema digests.
- The baseline itself fit 2 of them, episodes 7 and 17.
- On 22 episodes the baseline completed and failed.
- No evaluation target was among the 2 development episodes actually executed.
- 3 evaluation targets (0, 5, 14) match schemas the development seed namespace
  could produce within the first 400 attempts per family, and 1 (episode 2)
  matches a target admitted by the v2c census. These are schema-identity
  collisions in a finite space, not reuse of inspected material or seed reuse.
  No episode was removed on that account.

**Fresh grid seeds are not a complete-AST holdout**, and this study does not
claim one. The evaluation targets were drawn from a disjoint seed namespace,
which is weaker.

Exploratory subgroup, labelled as such, restricted to the 22 episodes where the
baseline completed and failed:

| arm | fit | held-out success | fit only by arm | fit only by none |
| --- | --- | --- | --- | --- |
| none | 17/22 | 13/22 | - | - |
| aggregate | 17/22 | 13/22 | 0 | 0 |
| associated:individual | 7/22 | 7/22 | 2 | 12 |
| associated:coverage-sum | 8/22 | 8/22 | 3 | 12 |
| shuffled:individual | 6/22 | 6/22 | 0 | 11 |
| shuffled:coverage-sum | 6/22 | 6/22 | 0 | 11 |

Removing the two baseline-solved episodes does not change the picture.

## 7. Exact AST recovery, separately

**Zero, in every arm.** Not one of the 19 unconditioned fits, nor the 8
coverage-sum fits, recovered the generator's schema, while 15 of the 19
unconditioned fits are correct on held-out grids.

The 4 fits that were not held-out correct produced **defined but wrong**
predictions: undefined held-out predictions were 0 across every arm. So fitting
every demonstration exactly is not sufficient for generalization here, and the
failure mode is confident error rather than abstention.

This is the measured reason not to use exact target identification as the
criterion for a future study.

## 8. Cost, correctly interpreted

The budget unit is one candidate fit attempt. It is **not** wall clock.

- One baseline fit is single-block and one proposal fit is two-block. They are
  charged one unit each, and they are **not** established to cost the same. No
  execution speedup may be inferred from equal fit counts.
- `run_condition.seconds` measures ranking, fitting and held-out scoring inside
  that call. The baseline traces were computed **before** the call, so that
  figure **excludes** baseline execution and must not be read as end-to-end cost.
- Every conditioned arm sorts the full 57,600-candidate space before its first
  fit. That sort is inside `seconds` but is charged no fit units.
- Observer processing costs 0.00211 s against the baseline's 0.521 s on one
  episode, about 0.4 per cent.
- Incremental against complete: if a parent solver has already run the baseline,
  the incremental cost of reusing its trace is the observer's parse alone. If it
  has not, the complete-pipeline cost includes the entire baseline enumeration,
  which is what the 200-unit charge represents.

## 9. How narrowly to read this

The **coverage-sum** rule sums two recorded coverage fractions and prefers sums
near one. It does **not** measure cell-set union, overlap, or jointly consistent
colour assignment. Two candidates each covering half the changed cells score
perfectly whether they cover complementary halves or the same half.

Worse, the recorded fractions need not describe the same demonstration.
Confirmed by reading the fitter: the coverage check sits inside the
per-demonstration loop and returns on the FIRST demonstration whose coverage
fails, and observer v1 records no demonstration index. So a coverage fraction
summarizes one demonstration, not all of them, and two fractions being summed
may come from different ones. This is a plausible contributor to misranking. It
is an explanation to test, not an established cause.

The **aggregate** rule uses only partition-failure counts. Code counts are
available in that view and its scoring does not use them, so this is a limited
projection of the aggregate information, not its maximum value.

Therefore this negative result establishes: **these ranking rules did not improve
the measured search outcome under this protocol.** It does not establish that the
aggregate graph contains no useful information, nor that candidate-associated
failure information cannot be learned from. Equally, episode 18 concerns the
tested ordering and budget, not new primitive semantics.

## 10. Decision

**Constructive GPN training is not justified by this evidence, and this is not a
finding that learned failure conditioning is impossible.**

Where the associated representation helps: 3 episodes that unconditioned search
missed, including one, episode 18, that no other arm fit and that generalized.
Where it hurts: 14 episodes unconditioned search fit and it missed, at roughly
three times the mean cost over all episodes.

Does the real trace beat the shuffled control? Not clearly: 8 against 6 out of
24, overlapping on one episode, with each fitting several the other missed. That
is the specific reason not to scale these heuristics into a large model. Training
on a representation whose direct readout is not separable from a wrong-task
control risks crediting learning for incidental structure.

Two future comparisons are proposed and neither is launched or tuned here:

1. **An unlearned family-interleaved policy.** The unconditioned arm ranks by
   program size and fixed enumeration order, and with 2,880 attempts it cannot
   exhaust the smaller families before reaching the 40,000-candidate one. Any
   future claim that failure evidence allocates search well must be separated
   from a policy that simply gives every family a share of the budget. That
   control must be specified before it is run, and must not be tuned against
   this evaluation set.
2. **A prospective shared-budget portfolio**, if the arms prove complementary.
   At least one arm fit 22 of 24 episodes and at least one achieved held-out
   success on 19 of 24. **That is an oracle union over separately budgeted arms
   and is not a deployable system score.** A real portfolio divides one budget
   and fixes its allocation without knowing which arm will succeed.

The genuine implementation gain stands independently of the negative ranking
result: the proposer can now retain which candidate produced which failure, the
observer is additive, versioned and non-interfering across nine tests, and it
costs 0.4 per cent of extraction. That capability is reusable by any future
readout.

## 11. Stop point

No model was trained, no holdout changed, no learner added, no D3 run, no ARC
holdout opened, and nothing merged into main. The next research decision belongs
to the complete comparison above, not to the first eighteen losses and not to
episode 18 alone.
