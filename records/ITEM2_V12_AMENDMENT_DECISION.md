# Item-2 v1.2 amendment: decision record

Written 2026-09-23, before any v1.2 episode was generated.

| artifact | identity |
|---|---|
| protocol | `docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL_v1.2.md` |
| protocol sha256 | `31a74764019c7ecef9d456258c9df3b6ee81d81a14c4703ee878d023bbe6bb98` |
| manifest | `outputs/tti/constructive_protocol_v1.2_manifest.json` |
| manifest sha256 | `3355c9c5895c042ff397f22f1723a581ff4545bdd6041dc142e14a00d7766ba1` |
| registered fitter identity | `2cc45152c430f8a2` |
| v1.1 preserved | yes, not overwritten |

## Why v1.1 is impossible

Requirements 4 and 5 were mutually exclusive. The type-keyed slot learner
returned one dictionary per declared type, collapsing several
`Map[FeatureValue,Colour]` occurrences onto the last, so requirement 5 was
satisfiable only when a schema reduced to a single (partition, predicate,
feature) triple. That is exactly the space the fixed baseline enumerates, so
passing R5 implied failing R4. Zero of 1,500 attempted targets were admitted,
and of 266 family-(2,) targets passing R5, 262 were baseline solved.

## What changed

The target and evidence side only. The registered constructive fitter is the
occurrence-scoped fitter. Episode failure graphs come from the repaired
full-engine observation path. The model-view feature allowlist is extended
from twelve entries to eighteen and refrozen. Seeds and the slot schedule are
new and disjoint from v1.1.

## What did not change

The baseline K, its productions, its search depth, its budget and its
ordering. The constructive grammar, its bounds, operators and terminals. The
ranking rule, the beam and the MDL definition. The banned target families.
The prohibition on reading any hidden output.

## Why baseline K was not weakened

Nothing was removed from the baseline, its depth was not lowered, its compute
was not reduced for generation, no fitting available to it was disabled, and
its ordering was not changed. It keeps its own 8 second budget and its own
200-schema enumeration.

The separation comes from the target side, and it is not a fitter privilege.
Both sides use the same occurrence-scoped fitter, and an identity mismatch
between them is a recorded fairness violation that rejects the episode. The
baseline enumerates 200 single-block schemas, all of family `(1,)`, while the
constructive grammar admits up to three blocks. Under occurrence-scoped
fitting a multi-block target no longer collapses onto a single triple, so
passing R5 no longer entails baseline reachability.

R4 remains behavioural rather than structural, which is the conservative
choice: a multi-block target whose behaviour a single-block schema happens to
reproduce is still rejected as baseline solved.

## Select-free families: the instruction was not followed, and why

The amendment was instructed to remove `(0,0)` and `(0,0,0)` from the train
pool because they are structurally dead under the registered fitter, and the
instruction conditioned retention of families on a static pre-generation
feasibility check. The check was run before the freeze and the premise does
not hold under the v1.2 fitter.

Static check, occurrence-scoped slots seen per family: `(0,)` 1, `(1,)` 1,
`(0,0)` 2, `(1,0)` 2, `(0,1)` 2, `(1,1)` 2, `(0,0,0)` 3, `(2,)` 1, `(2,1)` 2.
None is mechanically dead. The select-free blocker was a property of the
type-keyed learner, which required a predicate before inducing anything. The
occurrence-scoped fitter identifies slots by lexical occurrence, so a block
with zero selects still carries its own induced-slot occurrence.

Prior recorded evidence agrees. Of the thirteen verified admissions produced
under the occurrence-scoped fitter, seven are family `(0,0)`, more than any
other family, against three `(1,0)`, two `(0,1)` and one `(1,1)`.

Removing them would discard the most productive family on a premise the
change of fitter voids, and would encode a known-false assumption into a
frozen protocol, which is the one error a freeze must not make.

The instruction's constraint is honoured in full. No induction algorithm was
modified and no family was rescued by changing a reasoning mechanism. The
occurrence-scoped fitter is pre-existing machinery already adopted under
decision A.

`(0,0)` and `(0,0,0)` are retained. The departure is recorded here before any
generation, and reversing it is a one-line manifest change that costs nothing
while no data exists.

## Why training failure graphs now come from the repaired full engine

The scorer at inference consumes repaired real-engine evidence. Training on a
different representation than inference would reproduce the defect this whole
line of work exists to remove. The only existing admitted episodes carry
empty frontiers precisely because they came from the proxy runtime. Training
and inference therefore share the frontier node definitions, the candidate
outcome names, the candidate renderer, the mismatch-signature semantics, the
canonicalization and the feature extraction, and the candidate-executor
compatibility repair is part of the v1.2 data path.

## The rest of the law, in one place

Train families `(0,0)`, `(1,0)`, `(0,1)`, `(1,1)`, `(0,0,0)`. Structural
holdout `(2,)` and `(2,1)`. Banned `(0,)` and `(1,)`. Requested 300 train, 60
validation, 90 structural holdout, allocated equally with lexicographic
remainder, 25 attempts per slot. Root seed 20260923, train seeds from 21000,
validation from 22000, holdout from 23000. Budgets per target 90 s, baseline
search 8 s, graph extraction 2 s, full-engine observation 8 s. Eighteen
allowlisted features, counts and means only. Eight rejection codes, all
retained as diagnostics. Stopping at 2000 epochs or a 200-epoch plateau in
validation exact-at-five, non-LLM, hidden at most 256.

Recorded risk, not revisable after scores: family `(2,)` is single-block and
was baseline solved 262 of 266 times under v1.1, so it may admit at a low
rate. It is retained unchanged.

Interface holdout remains infeasible with a single interface, carried forward
as a limitation rather than pretended away.

## Claim ceiling

This block may earn only that the protocol is frozen and feasible. It does
not earn a trained scorer, useful construction, constructive reach, semantic
extension, transfer or any score gain.
