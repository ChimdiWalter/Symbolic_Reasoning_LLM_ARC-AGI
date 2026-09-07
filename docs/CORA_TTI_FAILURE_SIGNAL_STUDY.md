# Failure-signal study: does candidate-associated failure evidence help?

Bounded study run in `cora-tti-dev`. The v2c census is unchanged, its 13
admitted supplied-schema examples and every reported limitation stand, and the
live Step-B experiment was neither read nor modified.

Result in one line: **no. Under two declared readings, candidate-associated
failure evidence does not improve constructive proposal ranking. It is far worse
than unconditioned search over the same grammar at the same budget, and it is
barely distinguishable from a wrong-task control. Constructive GPN training is
not justified on this evidence.**

Artifacts: `outputs/tti/failure_signal_study/results.json`, sha256
`339aae08a9376b573861a757c5c4191001c339c722780f16d6389198b122c432`, run at
commit `73d96ae6c4a6` under `PYTHONHASHSEED=0`.

## 1. What was examined first

The identified baseline already retains, for each of its 200 attempted
hypotheses, the candidate triple, the fit status, the failure code and a detail
that localizes the failure. The graph builder was reducing that to marginal
counts by code and by partition. Whenever the baseline fails on everything, the
partition marginal is exactly 50 of 200 for each of the four partitions and
therefore carries no information at all.

So zero frontier terms did not mean zero information. The association was being
discarded, and recovering it required no change to the baseline. The graded
signal it recovers is the coverage shortfall, for example `covered 103 !=
changed 117`, which is near-miss information in a different form.

## 2. Design

Held constant across every arm: the constructive grammar, the fitter and its
options, the evaluator, the acceptance rule of exact fit on every demonstration,
and the demonstration input the proposer may see. Only the failure
representation varies.

| arm | information available to ranking |
| --- | --- |
| none | no search-failure information |
| aggregate | the current view's marginal counts by code and by partition |
| associated:individual | candidate-associated records, scored per block |
| associated:complementary | candidate-associated records, scored per pair |
| shuffled:individual | the same records from a DIFFERENT episode |
| shuffled:complementary | the same records from a DIFFERENT episode |

Proposal space: 57,600 two-block schemas over the frozen terminals, in a fixed
enumeration order that no arm may extend. One budget unit is one candidate fit.
Budget was fixed by a rule declared before measuring, at 5 per cent of the
space, 2,880 units, identical for every arm. The failure-extraction cost of 200
units is charged to every arm that reads a representation, so a representation
must repay its own cost.

Two readings of the association were declared rather than one. `individual`
scores a block by how much it alone explained. `complementary` prefers pairs
whose coverage fractions sum toward a complete joint explanation, because a
block that alone covers almost everything is a near-complete single-block
explanation the baseline has already rejected. `individual` was written first;
`complementary` was added after `individual` ranked poorly on a DEVELOPMENT
episode. The measured run uses a disjoint evaluation seed namespace.

24 fresh evaluation episodes, 6 per two-block family, built before any
measurement. Each has demonstrations for fitting and 4 held-out grids never used
for fitting or ranking.

## 3. Primary measure: useful recovery within budget

| arm | solved | rate | held-out correct | exact AST | mean total units | median rank |
| --- | --- | --- | --- | --- | --- | --- |
| none | 19/24 | 0.79 | 15 | 0 | 312.6 | 59 |
| aggregate | 19/24 | 0.79 | 15 | 0 | 521.2 | 59 |
| associated:individual | 7/24 | 0.29 | 7 | 0 | 2166.3 | 2185 |
| associated:complementary | 8/24 | 0.33 | 8 | 0 | 1721.4 | 2051 |
| shuffled:individual | 6/24 | 0.25 | 6 | 0 | 1702.0 | 1298 |
| shuffled:complementary | 6/24 | 0.25 | 6 | 0 | 1053.8 | 864 |

## 4. Paired against unconditioned search, the matched-budget unlearned baseline

| arm | cheaper | costlier | solved only by arm | solved only by none | median delta units |
| --- | --- | --- | --- | --- | --- |
| aggregate | 1 | 18 | 0 | 0 | +200 |
| associated:individual | 0 | 5 | 2 | 14 | +2455 |
| associated:complementary | 1 | 4 | 3 | 14 | +1254 |
| shuffled:individual | 0 | 6 | 0 | 13 | +1441.5 |
| shuffled:complementary | 0 | 6 | 0 | 13 | +927.5 |

The aggregate arm solves exactly the same 19 episodes as unconditioned search,
with a median cost difference of exactly the 200-unit extraction charge. That is
the arithmetic consequence of a constant marginal: it reorders nothing and pays
for the privilege.

The associated arms solve 3 episodes unconditioned search misses and miss 14 it
solves. The exchange is heavily negative.

## 5. The control decides it

| rule | associated solved | shuffled solved | median delta on both-solved |
| --- | --- | --- | --- |
| individual | 7 | 6 | +149 |
| complementary | 8 | 6 | +1189 |

A representation carrying usable task-specific failure signal should beat a
representation of a DIFFERENT task's failures clearly. It does not: 8 against 6
out of 24, and 7 against 6. Whatever separation exists is within the noise of
this sample. This is the result that decides the question, because it removes
the possibility that the associated arms are merely paying a fixed cost for a
real but small benefit.

## 6. By family

| arm | (0,0) | (0,1) | (1,0) | (1,1) |
| --- | --- | --- | --- | --- |
| none | 6/6 | 6/6 | 4/6 | 3/6 |
| aggregate | 6/6 | 6/6 | 4/6 | 3/6 |
| associated:individual | 3/6 | 1/6 | 2/6 | 1/6 |
| associated:complementary | 3/6 | 1/6 | 2/6 | 2/6 |
| shuffled:individual | 1/6 | 3/6 | 1/6 | 1/6 |
| shuffled:complementary | 1/6 | 3/6 | 1/6 | 1/6 |

There is no family where the association wins. Two episodes suggested one early:
on episodes 18 and 20 the unconditioned arm failed and an associated arm solved.
But episodes 19, 21 and 23 are also (1,1) and unconditioned search solved them at
52, 53 and 60 units, so the target's family does not determine difficulty.

## 7. Exact AST recovery, reported separately

**Not one solved episode in any arm recovered the generator's schema.** Zero out
of 19 for unconditioned search, zero out of 8 for the best associated arm. Yet
15 of the 19 unconditioned solutions are correct on held-out grids.

This is the strongest single reason not to make exact target identification the
prerequisite for a future study. The demonstrations underdetermine the schema:
simpler programs both fit every demonstration and generalize to fresh grids.
Judging a proposer by exact AST recovery would penalize it for finding a valid
alternative explanation. Held-out output correctness is the measure that means
something here.

The gap between 19 solved and 15 held-out correct is also real: 4 solved
programs fit every demonstration and then failed on fresh grids. Fitting the
demonstrations exactly is not sufficient for generalization even inside this
small grammar.

## 8. Cost accounting

| quantity | value |
| --- | --- |
| observer runtime, one episode | 0.00211 s |
| baseline runtime, one episode | 0.521 s |
| observer share of extraction | about 0.4 per cent |
| extraction charged to conditioned arms | 200 units |
| total study wall clock | 806.6 s |

The observer is cheap. Its cost is not why the associated arms lose; their
ranking is.

Observer field coverage over 200 records: 0 unparsed details, 158 records carry
a coverage fraction, 39 carry a conflict block, 4 carry witness counts, and 3 are
fully UNKNOWN. Nothing was invented and nothing was inferred from the target.

## 9. Data-access boundary

The proposer received demonstrations, the constructive grammar, and its arm's
failure representation, which is built only from the baseline's own attempts. It
never received the target schema, the target tables, the target digest, the
family label, generator metadata, or the held-out grids. The target digest and
the held-out grids are used only to score a result after the search has
finished. Tests check the observer's signature and import graph, and confirm it
cannot reach the generator.

## 10. Non-interference of the observer

Observer v1 is additive and versioned. It is a pure function of a completed
trace: it fits nothing, evaluates nothing, performs no I/O and holds no state.
Nine tests confirm that candidate order, per-candidate verdicts, accepted
programs and the trace object are unchanged after observing, that a baseline run
after observing is identical to one before, that an unrecognized detail yields
UNKNOWN rather than a guess, and that the observer cannot turn a rejection into
an acceptance. Failed candidates stayed failed. Exact fitting was not weakened,
no partial solution was fabricated, and acceptance was never changed to populate
the frontier.

## 11. Decision

**Constructive GPN training is not justified on this evidence.**

The blocker is specific and is not "the idea is wrong". It is that no simple
readout of the recovered representation beats unconditioned search over the same
grammar at a matched budget, and no readout separates the true trace from a
wrong-task trace. Training a model on a representation that a direct readout
cannot distinguish from a control would risk attributing to learning whatever
the model extracts from incidental structure.

What this study does NOT establish: that the representation contains no usable
information. It tests two hand-written rules. A learned proposer might extract
signal these rules miss. That possibility is exactly why the next step should be
cheap.

The cheapest decisive next test, if this direction is continued: find any
readout of the candidate-associated records that beats BOTH unconditioned search
and the shuffled control on the same budget and the same 24 episodes. That is a
small experiment on existing artifacts. Until something clears that bar, a
larger model is not warranted.

## 12. What is retained unchanged

The repeated-Select and three-block NO-GO findings stand. The corrected census
found no admissible target in (2,), (2,1) or (0,0,0) among 128 attempts each,
and nothing in this narrower study bears on those families or converts them into
successes. This study concerns proposal ranking within the two-block families
only.

## 13. Limitations

- 24 episodes. Differences of two or three solved episodes are not resolvable.
- The unconditioned arm is smallest-first enumeration, which is a strong prior
  on this generator because simple programs frequently suffice. It is a fair
  unlearned baseline, not a straw man, and that is partly why it is hard to beat.
- Two of the 24 episodes were solvable by the single-block baseline itself, so
  the constructive search was unnecessary there. They are recorded, not removed.
- One ranking rule was added after seeing the other fail on a development
  episode. Both are declared, and the measured run used a disjoint namespace,
  but the second rule had one prior observation behind it.
- Results are on a synthetic fixture generator, and its distribution shapes how
  often a simple program suffices.
