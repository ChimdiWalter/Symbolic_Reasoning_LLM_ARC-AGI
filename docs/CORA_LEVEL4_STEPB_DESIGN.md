# Level 4 Step B: the invention mechanism — DESIGN, K2 DIRECTION FROZEN

**Status: design decision FROZEN 2026-08-23, after Step A and Step A.1, before any
Step-B code exists. No proposal has been generated; the mechanism is NOT implemented.**
The SHA-256 of this file is pinned in
`outputs/cora_breakthrough/level4_stepB_design_hash.txt`. Nothing below may be revised
after Step-B code exists except by a dated amendment naming the pre-existing evidence
that forces it. The concrete constructor inventory (section K2.2) is enumerated by the
mechanism and pinned in a Step-B run manifest **before the single run**; it must satisfy
every constraint in this document, and the run manifest cites this hash.

## The decisive sentence

> K2 is a finite, closed, type-directed semantic-constructor language applied uniformly
> to every eligible Step-A cluster. Its constructor inventory is frozen before proposal
> generation and contains no ARC-family, task-specific, frontier-type-specific, or
> goal-delta-specific branches. Types constrain which constructors are well formed but
> do not select constructors semantically. Every generated candidate is labelled at
> generation time as exactly `SLOT_LEARNER_REPAIR` or `NEW_SEMANTIC_PRODUCTION`; only
> the latter is eligible for the Level-4 semantic self-extension claim.

K2 does not contain candidate ARC solutions. K2 contains generic ways of constructing
candidate semantics. The data determines which constructor survives.

## Inputs and closures

When it runs, Step B reads: the pinned Step-A output (verified against
`level4_stepA_output_hash.txt` first), the frozen A.1 artifact (pin `c6a255ae1337de22`), the four
sanitized mechanism inputs, and the blind runtime. Nothing else.

Step B may know, per cluster and per record: source token; frontier type; goal type;
frontier values and value signatures; the demonstrated input/output relation of the
sanitized demonstrations; the frozen diagnostics (failure class, raw counts, delta
signature, repeated-structure flag).

Step B may NOT know: task ids; hidden test outputs or test correctness of anything;
E_transfer; Promotion; the Lockbox; the sealed human expectation. Test correctness is
examined only by the certification stage, through the ordinary unchanged gates.

## The two candidate kinds (unchanged)

| Kind | Meaning | Counts as Level-4 semantic self-extension? |
|---|---|---|
| `SLOT_LEARNER_REPAIR` | a new or relaxed estimator for an EXISTING induced type, reachable by the EXISTING productions | **No.** Recorded, may be adopted for capability, claims nothing for Level 4 |
| `NEW_SEMANTIC_PRODUCTION` | a new typed production with a new executable mapping not previously available as a production | **Yes**, iff it passes the frozen certification (criteria 1–6) AND the semantic separation certificate below |

The label is fixed at generation time and never changed afterwards. A candidate that
only changes how an already-existing induced slot is estimated is a repair, whatever it
is called.

## Why the broad uniform schema, not a narrow one

Step A.1 made the narrow option scientifically dangerous. 60/62 eligible clusters
terminate at one frontier type, but they are behaviourally diverse (value signatures
median 16 per cluster, AST skeletons median 133), and 156 sources have shape-changing
targets that the existing continuation path cannot express even with perfect slot
fitting. A K2 aimed at "repair the dominant continuation path" would be a mechanism
built after seeing the failure landscape, and its success would be uninterpretable.

K2 therefore says: for any admitted source kind `A` and admissible target kind `B`,
enumerate the SAME closed family of generic semantic constructors. Nothing in K2 reads a
cluster's frontier type, goal type or delta signature to choose WHICH constructors to
try; those values only determine which constructors are well typed.

Forbidden shapes, stated so they can be audited:

```
if <delta signature> == <some value>:   propose <something>
if <frontier type>   == <some type>:    propose <something>
```

## Lane K1: repair (labelled SLOT_LEARNER_REPAIR)

The existing induced-slot learner has five explicit guards (same-shape pairs; touched
set equals the whole set; single output value per set; full coverage of changed cells;
every key witnessed twice). The repair space is the lattice of guard relaxations,
enumerated exhaustively (2^5 minus the frozen point), each yielding a candidate learner.
No new guard may be invented, only frozen ones dropped, so the space is defined entirely
by what already exists and contains nothing aimed at any cluster. K1 is kept because
A.1 showed every slot_learning record is PURE_SLOT: where the target IS expressible,
a repair is the cheapest honest resolution, and offering only new productions would
misreport repairable gaps as inventions.

## Lane K2: invention, in three layers

These are three levels inside the proposal generator, not three candidate categories.

### K2.1 Typed interface generation

For each cluster, candidate interfaces are generated entirely from evidence:

```
A -> B            from the frontier type and the goal type
A x B -> C        only where the frozen language already justifies binary forms
```

Types come only from the mechanism-visible admitted type universe plus the goal type.
No new type name is invented at this stage. An interface arises because the frontier
has one type and the failed goal has another — never because a transition was
supplied to the mechanism. This distinction is what makes an emergent interface
evidence rather than input.

### K2.2 Uniform data-projection semantics

For each interface, candidates are enumerated from a frozen finite family of generic
operations on runtime values, organised by formal category, for instance:

```
select     choose a sub-collection by a typed predicate
project    { phi(x) : x in S } for a typed map phi
reindex    re-address elements under a structure-preserving map
aggregate  fold a collection under an associative operator
combine    merge two values of compatible kind
embed      place a value into a carrier of the target kind
reduce     collapse a structured value to a summary of the target kind
```

Requirements on the inventory, to be verified mechanically against the pinned run
manifest before the run:

- every constructor is a formal schema over the structured data a value already carries
  in the frozen runtime (its cells, the colours the input assigns those cells, its
  bounding box, its cardinality) and the target kind's already-admitted constructor
  shape; no constructor is admitted by a domain name;
- every admitted kind receives the same applicable constructors BY TYPE; nothing is
  hand-selected for one kind;
- the inventory mentions no shape family, no task, no cluster content, and no name from
  the opaque forbidden pool (the existing executable leak check runs over it);
- parameters a constructor needs (an ordering, an arrangement, a value rule) are not
  chosen by the schema: they become induced slots fitted per task by the ordinary
  slot-learner machinery, so semantics stay demonstration-driven.

### K2.3 Candidate semantic production

Once slots are instantiated from the sanitized demonstrations, K2 emits a proposed
production `e : A -> B` and labels it at that instant:

- `SLOT_LEARNER_REPAIR` if it merely changes how an existing induced slot is estimated;
- `NEW_SEMANTIC_PRODUCTION` if it introduces an executable mapping not previously
  available as a production.

Only the second label proceeds toward the Level-4 claim.

## Semantic separation certificate (additive requirement for Level-4 adoption)

A new name is not new semantics. A candidate `NewThing : A -> B` that is extensionally
equivalent to a composition of frozen productions is a macro, and belongs conceptually
at Level 3. Before Level-4 adoption the candidate must therefore carry a separation
certificate:

```
exists x :  e(x)  not in  { p(x) : p in F(K_L4*) }
```

established on a bounded domain, since global non-definability is not provable:

1. construct generic synthetic witnesses appropriate to the declared types (the witness
   generator is frozen with the run manifest and reads no cluster content);
2. exhaust the frozen baseline grammar F(K_L4*) under its declared bounds
   (MAX_DEPTH, PER_TYPE_CAP, MAX_CANDIDATES, unchanged);
3. show the candidate produces, on at least one witness input, a behaviour no baseline
   program produces;
4. retain that separating witness in the certificate.

This is recorded here as an ADDITIVE tightening of acceptance. The frozen manifest's
criteria 1–6 are unchanged and the manifest file is not edited (its pin `607ed54c305df5f7` is
verified by the runners). A candidate lacking a separation certificate is reported as
`EQUIVALENT_TO_BASELINE_COMPOSITION` and is not a Level-4 result.

## All 62 clusters, deterministically, no early stop

Step B processes every eligible cluster in the frozen order

```
( -N_distinct_sources, -N_records, canonical(cluster_key) )
```

and never a human-selected one. It does NOT stop at the first success. Stopping early
would make K2 indistinguishable from a best-cluster repair engine. Processing all
clusters under the same mechanism makes the following reportable:

- proposal rate (clusters yielding >= 1 candidate);
- candidate-category rate (repair vs new semantics);
- semantic-production rate;
- certification rate;
- convergence: how many distinct clusters independently propose equivalent semantics;
- divergence: whether distinct failure clusters suggest different inventions.

Independent convergence of many clusters on one semantic is the strongest available
evidence that the capability was forced by failure rather than embedded in K2.

## Deduplication before certification

Candidates from different clusters may be extensionally equivalent. They are NOT
counted as separate inventions. Canonicalise by:

1. typed signature;
2. normalised program/schema (alpha-renamed, slot positions typed);
3. behavioural fingerprint over a frozen synthetic probe set (the same generator as the
   separation certificate).

Merge equivalence classes `[e_i]~`, keeping every source cluster as provenance. A merged
candidate record carries:

```
candidate_id
signature                    A -> B
kind                         SLOT_LEARNER_REPAIR | NEW_SEMANTIC_PRODUCTION
proposed_from                [cluster ids]
independent_source_tokens    N   (union over proposing clusters, deduplicated)
semantic_fingerprint
resolution_evidence          per proposing cluster
```

## Selection by resolution, never by resemblance

A candidate is kept only if, installed into the blind environment, the ordinary
unchanged search + LOO-by-rediscovery certifies at least 2 distinct source tokens of a
cluster that proposed it (criteria 1 and 2, run inside the blind environment on
sanitized demonstrations; no task identity needed). Ties are broken by frozen MDL of
the candidate's definition, then lexicographically. No score reads a
`goal_delta_signature` as a target to imitate; delta signatures only key clusters,
resolution decides.

## After a candidate survives

Criteria 3 (no regression), 5 (synthetic counterexamples), 6 (transfer outside
invention provenance) and the separation certificate require the trusted harness and,
for 6 only, E_transfer. The firewall opens ONLY after a candidate is frozen with its
provenance. Step B's own output stops at: frozen candidate list + per-candidate
resolution evidence + kind labels + dedup provenance, hashed before any semantic
inspection, same discipline as Step A.

## Determinism and output discipline

Same rules as Step A: pinned-input verification before reading; counts-only stdout;
all outputs written to files and SHA-256-pinned before inspection; byte-determinism
required on untruncated work; the runner, the constructor inventory, the witness
generator and any generated instrumentation added to the executable leak check; a
Step-B run manifest pinning every hash (including this document's) before the single
run.

## The complete experimental sequence from here

```
Step A + A.1                                   COMPLETE, frozen
freeze Step-B mechanism + run manifest          next
62 eligible clusters -> automatic proposals
deduplicate semantic candidates
label repair vs new semantics (at generation)
certification on invention provenance (1, 2, separation certificate)
  -> candidate frozen with provenance
  -> 150 E_transfer opened: criteria 3, 5, 6
  -> 200 Lockbox, ONCE, only if transfer holds and no frozen criterion fails
freeze the final CORA system
1000-task final training census
120-task public evaluation
```

The 120/1000 experiment is run only at the end of this sequence; before then it would
measure an unfrozen system.

## Frozen interpretations specific to Step B

| Outcome | Meaning |
|---|---|
| >= 1 `NEW_SEMANTIC_PRODUCTION` certifies with separation certificate and criterion 6 | failure-triggered semantic self-extension demonstrated |
| certifies but fails separation | a macro over the frozen language; a Level-3 result, recorded, not a Level-4 result |
| only `SLOT_LEARNER_REPAIR` candidates survive | the located gap was an estimator gap; real negative for Level 4, recorded |
| K2 cannot express what the clusters need | a real negative about THIS schema, recorded as such; K2 is not widened after the fact |
| a certified candidate matches the sealed record | independent rediscovery, with the seal date as evidence |
