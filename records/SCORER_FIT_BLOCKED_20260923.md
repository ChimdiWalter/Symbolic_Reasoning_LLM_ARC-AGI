# The scorer fit is blocked, and why

2026-09-23. Reporting an incompatibility with a frozen requirement rather
than changing the requirement after the fact. Nothing was generated, trained,
compiled, installed or scored. Step B untouched.

## What was attempted

The recorded next action was to fit the proposer's scorer weights on the
existing constructive dataset, per the frozen Item-2 v1.1 model
specification. Fitting needs supervised pairs of the form

    informative typed failure graph -> target AST

## Finding 1: protocol v1.1 admitted nothing, and provably cannot

`outputs/tti/constructive_pilot_slots/` holds all 60 generated slots from
2026-09-04, hash-pinned by
`constructive_pilot_generation_manifest_hash.txt`. Every slot hit its
25-attempt cap. 1,500 targets were attempted. Admitted: **0**.

The run recorded its own root cause, and it is structural rather than
incidental:

> Requirements 4 and 5 are mutually exclusive under protocol v1.1. The sole
> registered slot learner fits Map[FeatureValue,Colour] through
> meta_ast.bound_values, which returns ONE (partition, predicate, feature)
> triple; the fixed base search enumerates exactly that 200-triple product
> with the same learner. Therefore any target the learner can fit (R5) is
> findable by the base search (R4 violated).

Measured pre-freeze: of 266 family-(2,) targets passing R5, 262 were solved
by the base search and 4 failed witness separation. Zero admitted.

A second recorded blocker compounds it. Families with no Select stage
anywhere, which includes `(0,)`, `(0,0)` and `(0,0,0)`, are structurally
dead, because the bound-values step yields no predicate and the
feature-colour-map induction refuses immediately. Measured 0 of 240 R5
survivors. Two of those three families are in the frozen train family list.

So the frozen v1.1 corpus is not merely empty. Under the registered slot
learner and the fixed base search it cannot be non-empty.

## Finding 2: the only verified admitted episodes carry empty failure frontiers

The later corrected census did admit episodes.
`outputs/tti/constructive_v2_corrected/admitted/` holds 13, in families
(0,0) seven, (1,0) three, (0,1) two and (1,1) one, each carrying a typed
failure graph and the target token sequence a scorer would be fitted against.

Every one of those 13 graphs contains **zero frontier_term nodes**, and the
frontier operator multiset across all 13 is empty.

That is the same defect diagnosed and repaired earlier this session. Those
graphs came from the restricted proxy runtime, not the deployed reasoner, so
they carry no candidate-associated evidence at all. Fitting a
failure-conditioned scorer on them would be fitting it to evidence that does
not vary with the task, which is precisely the failure mode the repair
existed to remove.

Two further disqualifications apply. They are protocol v2 rather than the
frozen Item-2 v1.1 whose grammar and ranking the proposer is built against,
and their recorded protocol hash is absent. The separate reconstruction
directories, holding 29, 25, 30 and 28 admissions across hash seeds, were
audited earlier and downgraded, so they are not evidence.

Thirteen pairs would in any case be far too few for the scorer's parameter
count.

## Consequence

There is no corpus of informative-failure-graph to target-AST pairs anywhere
in the project, and none can be produced under the frozen v1.1 admission law.
The fit is blocked for two independent reasons.

Real ARC failures now produce informative graphs, but they come with no
target AST, and no hidden answer may be read to supply one. So the real
channel cannot supply supervision either.

## What this does not change

The proposer still works as measured: it emits legal, complete, canonical
ASTs absent from K from real failure graphs, deterministically, in about 0.03
seconds per task. The earned claim is unchanged, and so is the unearned one.
Weak task conditioning stands as recorded, and is now explained: the
mechanism that would fix it has no data to learn from.

## Exactly one next action, and it needs a decision

**Propose and freeze a v1.2 amendment that regenerates the constructive
corpus through the repaired full-engine observation path.**

The amendment has to state three things, and each is a protocol change that
must be frozen before generation rather than chosen afterwards:

1. How R4 and R5 are made jointly satisfiable. The recorded root cause shows
   the base search and the slot learner enumerate the same triple product, so
   either the base search or the registered learner must differ, and that
   choice is a scientific decision about what counts as out of baseline
   reach.
2. That episode failure graphs are produced by the deployed reasoner under
   the repaired observation path, so the frontier is non-empty by
   construction. The current feature allowlist has twelve entries and
   predates the repair, so it does not include the mismatch and value
   evidence the repaired channel now carries. Extending it is part of the
   amendment.
3. That families with no Select stage are either removed from the train
   family list or the induction path that refuses them is changed. Leaving
   both as they are keeps two frozen train families dead.

I am not making any of those choices. They alter a frozen protocol, and the
whole point of the freeze is that they are recorded before results.

The ConstructiveExtensionCompiler remains separate and unbuilt. The data
order in `records/DATA_USAGE_ORDER.md` is unchanged: no 1000-task run until
the end-to-end path works, and no HOLDOUT until everything is frozen.
