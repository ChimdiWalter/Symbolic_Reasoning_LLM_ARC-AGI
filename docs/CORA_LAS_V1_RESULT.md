# LAS-v1: learned abstraction selection, result

Implementation committed at `b5d3110`, de-collision rule at `151747f`, both before
FINAL-TRANSFER was opened. Run at `PYTHONHASHSEED=0` on a clean tree.
Frozen libraries sha256 `f2f6c13956b4879d...`; results
`outputs/tti/las_v1/results.json` sha256
`d102b2ae3f1c3a70516c34b8c1254ec724cd332c5b99408f42cbaa2f25cd94c9`.

## Question and answer

> Can CORA select the useful LEVEL of abstraction from discovered source
> programs using only source-side evidence, and does that beat concrete reuse?

**Yes on correctness, no on cost.** The declared primary criterion, LAS held-out
correctness greater than CONCRETE under the same target budget, is met: 16
against 14. LAS also exceeds ordinary search, both previous hand-authored rules,
and the mandatory matched-space control. It does so at a target-time cost higher
than concrete reuse and about equal to ordinary search, and its total system cost
including acquisition and validation is roughly 2.8 times ordinary search.

The margin is **two episodes out of 24** and is not a resolvable effect.

## Pools

| pool | namespace | episodes |
| --- | --- | --- |
| SOURCE-ACQUIRE | 9,100,000 | 16 |
| SOURCE-VALIDATE | 9,400,000 | 16 |
| FINAL-TRANSFER | 9,700,000 | 24 |

Target-identity overlap is zero across all three pairs. That was not free: the
pinned assertion fired on the first launch because source and validate sampled
one identical target schema from disjoint seed namespaces. The schema space is
finite, so this is a collision, not a leak. A de-collision rule declared before
any transfer outcome builds pools in the fixed order source, validate, transfer
and skips an episode whose target identity already appears in an earlier pool.
**Exactly one skip occurred**, in validate family (0,1) at seed 15,542,576,
recorded with its digest. No pool fell short of its count.

## Acquisition, one policy, everything charged

Ordinary smallest-first constructive search, 2,880 fits per source episode.

| item | value |
| --- | --- |
| source episodes | 16 |
| discovered | 13 |
| failed searches | 3 |
| units charged | **20,936** |
| distinct concrete structures | 9 |

## The lattice, and what it excluded

| item | value |
| --- | --- |
| groups (all pairs per family, plus the full family group) | 29 |
| unique candidate abstractions | 15 |
| masks excluded by the expansion cap of 400 | 29 |
| candidates with at least one validation held-out success | 14 |
| retained as LAS | 8, cumulative expansion 950 |

The minimal mask of each group is exactly its anti-unification, so the previous
hand-authored rules are points inside this lattice rather than competitors to it.
Nearly half the enumerated masks were excluded by the expansion cap, which is a
declared bound on the experiment and not a property of the method.

## Validation and selection

21,603 units over 16 validation episodes. Selection used the frozen lexicographic
objective and never saw a transfer task.

The winning concept, `(0,0)|pair(0,2)|m3:1011`, frees both partitions and the
second feature while keeping the first block's feature constant. Its validation
record: 10 demonstration fits, 9 held-out correct, 1 wrong-but-consistent, 0
undefined, expansion 160.

**All eight retained concepts come from family (0,0) pairs.** None came from the
other three families, yet they transfer across families at target time. This is
the third time in this line of work that simple structures prove the reusable
ones.

## FINAL-TRANSFER, 24 targets, common budget 3,000

| policy | demo fits | held-out | wrong-but-consistent | undefined | solved in prior | units |
| --- | --- | --- | --- | --- | --- | --- |
| A ordinary | 18 | 15 | 3 | 1 | 0 | 22,955 |
| B concrete | 18 | **14** | 4 | 0 | 13 | **18,670** |
| C R1 | 18 | 15 | 3 | 1 | 15 | 22,505 |
| D R2 | 18 | 15 | 3 | 1 | 15 | 22,305 |
| E LAS | 18 | **16** | **2** | **0** | 16 | 22,762 |
| F matched control | 18 | 15 | 3 | 1 | 15 | 27,104 |

**No policy improved demonstration-fit coverage.** All six fit the same 18 of 24.
Nothing here extends what the reasoner can solve, only which explanation it
selects and at what cost.

Exact AST recovery: 1 for every arm except the matched control, which recovered 0.

## Where the difference actually comes from

Only three targets separate the policies on held-out correctness:

| target | ordinary | concrete | LAS | LAS units |
| --- | --- | --- | --- | --- |
| 1 | wrong | right | right | 11 |
| 13 | right | **wrong** | right | 13 |
| 17 | right | **wrong** | right | 14 |

LAS beats ordinary on target 1, and beats concrete on targets 13 and 17 where
concrete's cheap first hit was a demonstration-fitting but incorrect program. All
three were solved by the same top-ranked concept.

This is the target-23 phenomenon again, and now it cuts both ways: a learned
prior can rescue a wrong selection, and it can also cause one. Concrete reuse
here is **worse than ordinary search on correctness**, 14 against 15, while being
the cheapest arm. That reverses the direction of the previous experiment, where
concrete gained a held-out success. Cheap first hits are not free.

## The mandatory matched-space control

LAS against a control with identical masks and identical candidate-space
cardinality, differing only in that its constants come from vocabulary order
rather than from any discovery:

| | LAS | control |
| --- | --- | --- |
| held-out correct | 16 | 15 |
| total units | 22,762 | 27,104 |
| cheaper on | 15 of 24 | - |

The learned terminals are worth about 4,300 units and one held-out success
against arbitrary ones. That is the cleanest evidence here that the selection
retained something useful rather than merely exposing search choices, and it is
still a one-episode correctness margin.

## Ablations, five outcomes reported separately

| policy | ablations | fit lost | held-out lost | program identity changed | median cost increase |
| --- | --- | --- | --- | --- | --- |
| B concrete | 13 | 0 | 0 | 7 | +54 |
| E LAS | 16 | 0 | 0 | 11 | +36 |

**No single entry or concept is necessary for either fitting or held-out
correctness.** Every removal left another library member that fitted and
predicted equally well. The concepts do change which program is selected, in 11
of 16 LAS ablations, but redundantly.

So the LAS advantage is a **library-level** effect. The whole-prior comparison is
the evidence that matters: LAS 16 held-out against ordinary 15 and concrete 14.
Two removals actually made a target 6 units cheaper, which is recorded rather
than smoothed away.

## Cost, complete chain

| component | units |
| --- | --- |
| acquisition | 20,936 |
| abstraction generation | negligible, under 0.1 s |
| source validation | 21,603 |
| LAS target-time | 22,762 |
| **LAS total** | **65,301** |
| CONCRETE total (acquisition plus target) | 39,606 |
| ordinary total (no acquisition) | 22,955 |

LAS costs about 2.8 times ordinary search in total, for one additional held-out
success over ordinary and two over concrete. No break-even is projected: the
saving is negative at target time, so the usual extrapolation does not apply, and
the correct statement is that LAS buys correctness with compute rather than
saving it.

## Claims earned

Earned, narrowly:

- **Source discoveries can support an automatically selected reusable
  abstraction whose retained invariants improve predictive selection on disjoint
  tasks.** Selection used only source-side evidence, the libraries were frozen
  and hashed before transfer opened, and the result exceeds concrete reuse,
  ordinary search, both hand-authored rules, and a matched-space control.
- The mask lattice makes the level of abstraction a measured choice rather than a
  researcher's decision, and the selected level was neither the most general
  (the previous R1 failure mode) nor the most specific.

Not earned, and not claimed:

- Any increase in problem-solving reach. Coverage was 18 of 24 in every arm.
- A cost improvement. LAS is more expensive than concrete at target time and far
  more expensive in total.
- That any single learned concept is causally necessary. None is.
- Semantic expressivity growth, primitive invention, Level-4 CORA-SCIENCE
  success, Level-3B capability gain, open-ended self-extension, or any ARC
  leaderboard implication.

**FULL-PIPELINE LOO NOT MEASURED.** The library is frozen from disjoint source
tasks, which is permitted, but per-fold proposal and fitting were not rebuilt
inside each held-out fold.

## Limitations

- The correctness margin is two episodes out of 24. It is not resolvable and
  could reverse on a different pool.
- Concrete reuse underperformed ordinary search on correctness here while
  outperforming it in the previous experiment. The direction of that effect is
  unstable at this sample size.
- All eight retained concepts came from one structural family, so the selection
  had little diversity to choose among.
- The expansion cap of 400 excluded 29 of 44 enumerated masks, including every
  maximally general one.
- Validation cost 21,603 units, comparable to a whole transfer run, so the
  selection procedure is expensive relative to what it buys.
- Results are on a synthetic fixture generator whose distribution determines how
  often simple programs suffice.
- The fitter, lattice, grouping rule, objective and policies are research
  infrastructure. What the system chose was which abstraction level to keep.
