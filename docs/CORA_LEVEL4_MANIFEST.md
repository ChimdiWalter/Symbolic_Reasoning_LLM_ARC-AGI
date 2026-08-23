# Level 4: Certified Semantic Self-Extension

Frozen 2026-08-22, **before any invention mechanism is written**; reissued 2026-08-22 after the
first version was found to leak the very expectation it required to be withheld. Nothing here
may be revised after the mechanism exists, except by a dated amendment naming the pre-existing
evidence that forces the change.

**This document is mechanism-readable.** It therefore contains no expectation about which
capability is missing, no example of a candidate completion, and no naming of which unresolved
production the project believes will be needed. That material lives in a sealed record outside
`docs/`, described in "Blindness" below.

## The question

Level 3A changed the reusable-abstraction component of the knowledge state: a macro over the
existing kernel, which did not change what the language can denote. The question now is:

> Can systematic certified failure force the invention of a genuinely new semantic capability,
> which the system then certifies and adopts?

Writing `K_t = (V_t, R_t, P_t, A_t, M_t)` for views, relations, grammar, abstractions and
memory, Level 3A altered `A_t`. Level 4 asks whether failure can alter `P_t`, and eventually
`V_t` or `R_t`.

## Blindness

The project holds a private expectation about what the kernel lacks. It is sealed as hashes in
`outputs/cora_breakthrough/level4_withheld_expectation_seal.json`, with plaintext only in the
research ledger, which no mechanism reads.

The invention mechanism, and every file it consumes, must contain:

- no capability name, operator name or label drawn from the sealed record;
- no ARC task id, task-family name or human summary of a failure group;
- no worked example of a candidate completion, since an example is itself a hint;
- no enumeration of which contract-inactive production is expected to matter.

The mechanism may read the semantic contract's inactive set only as an opaque list of names it
must not use. It may not be told which of them anyone expects to become necessary.

A pre-run **sealed-lexeme and task-identifier leak check**,
`scripts/cora_level4_leak_check.py`, verifies these properties against every input the
mechanism reads, and must pass before Step A executes. Its claim is deliberately narrow: it
detects the sealed exact terms and compounds whose hashes were supplied, plus task identifiers
and worked type-transition examples. It cannot prove that no synonym or paraphrase exists. The
stronger protection is structural: the redacted contract, opaque source tokens, the sanitized
corpus, and the explicit input whitelist.

**Input whitelist.** The mechanism reads only:

```
level4_mechanism_inputs/machine_manifest.json
level4_mechanism_inputs/contract_redacted.json
level4_mechanism_inputs/concepts_redacted.json
level4_mechanism_inputs/invention_corpus.jsonl
```

`invention_corpus.jsonl` holds one record per `E_invent` task, carrying its `source_token` and
its demonstration pairs, and nothing else: no task id, no Promotion, no Lockbox, no test
solutions. The raw ARC corpus is keyed by task id and is therefore never read directly.

## Splits

| Split | Status for Level 4 |
|---|---|
| Experience | development pool: frontiers extracted, extensions invented and certified here |
| Promotion | **spent** by the Level-3A confirmatory run; not used for extension design |
| Lockbox | **untouched**, closed for the whole of Level 4 |
| Evaluation 120 | untouched, out of scope |

## The Level-4 baseline language, which is NOT the Level-3A kernel

The Level-3A kernel was minimised on purpose: six productions, derived from the closure of two
source programs, so the macro experiment had the smallest possible baseline. Carrying that
kernel into Level 4 would be a serious error, because the mechanism could then appear to invent
capabilities that were merely amputated for the earlier experiment.

`K_L4` is therefore defined separately as **every previously frozen, contract-ACTIVE,
non-unresolved production that has a pre-Level-4 implementation**, with polymorphic signatures
instantiated at the declared ground types. Five productions whose implementations had not been
ported were ported from the pre-Level-4 prototype before this freeze, so that no Level-4
evidence determined the contents of `K_L4`.

Nothing the contract marks unresolved is included, and **no Level-4 observation may add to
`K_L4`**. Where a contract-active production still has no pre-Level-4 implementation it is
excluded, and that exclusion is listed here rather than left silent.

### Amendment, 2026-08-22: registry membership is not capability

The first freeze of this section counted 22 grounded productions and treated that count as the
baseline's capability. A pre-mechanism admissibility gate, run before any invention code
existed, showed that count to be an overstatement. A production can be listed, correctly typed
and individually evaluable while remaining **unusable by the frozen search**, because an
argument type has neither a terminal vocabulary nor a slot learner, so no value for it can ever
be supplied. Two further productions were found to be evaluable but behaviourally wrong against
synthetic fixtures.

`K_L4*` is therefore defined as the productions that are both pre-Level-4 **and** operationally
reachable under the frozen search, admission being iterated to a fixed point so that a
production whose only argument source is an excluded production is itself excluded. It is
**11 grounded productions**, not 22, against the Level-3A kernel's 6. The knowledge state for
Level 4 is

```
E_L4* = K_L4* + {concept_0001}
```

`concept_0001` was checked to remain viable, since every production its schema uses is admitted.

Per-production evidence, including contract and runtime signatures, historical source and hash,
argument sources, reachability, fixture results and the reason for every exclusion, is in
`outputs/cora_breakthrough/level4_baseline_admissibility.json`. A positive control ran the
frozen inducer on a synthetic task purpose-built for one claimed multi-step chain; the chain was
not rediscovered, and the capability was **excluded rather than repaired**. Inventing corrected
semantics to rescue a failed baseline capability is prohibited: it would move the comparison
line after seeing where it fell.

**This amendment names no capability, and neither does any mechanism input.** The admissibility
artifact does name productions, and is therefore **outside the input whitelist** and never read
by the mechanism. The counts here are safe to state; the identities are not.

This amendment is admissible under the freeze rule because the evidence forcing it is
pre-existing, mechanism-blind, and derived from no ARC development task.

## What stays frozen

`K_L4*` as amended above; `concept_0001` with its cost and macro accounting; the semantic
contract, its polymorphism policy and its entire inactive set; the search implementation,
MAX_DEPTH, PER_TYPE_CAP, MAX_CANDIDATES, budget and ranking; and the immutable leave-one-out
verifier. An extension changes what may be **proposed**. It may never change what is
**required to accept**.

## Within-stage holdout

Experience is split before extraction, deterministically and outcome-blind, by a keyed hash of
the task id with a frozen salt:

```
E_invent    75 percent   the only tasks that may generate frontier records
E_transfer  25 percent   never seen until a candidate extension is frozen
```

Criterion 6 is evaluated on `E_transfer`. Without this, a later Experience task could sit
outside the final source-task list while still having shaped cluster formation, type-gap
frequencies and proposal selection, which is not a clean transfer test.

## Source tokens

The mechanism must be able to tell whether three frontier records came from one task or three,
or a single task with three incomparable maximal frontiers could satisfy a three-record
cluster. Each record therefore carries

```
source_token = HMAC(frozen_secret, task_id)
```

which is stable, opaque, and mapped back to a task id only behind the firewall. Cluster
eligibility is `|distinct source tokens| >= 3`, checked by the mechanism itself on tokens, not
reported to it as a bare verdict by the certification stage.

## Failure-frontier record, frozen

For every training-exact near-solve under `K_t` that cannot reach the target, record exactly:

```
source_token             opaque, stable, task identity only behind the firewall
frontier_ast             the maximal typed partial term (definition below)
frontier_type            its result type
goal_type                the required output type
frontier_value_signature canonical for frontier_type
goal_delta_signature     derived from the demonstration input and output
behavioural_residual     only when frontier_type == goal_type, else NOT_DEFINED
repeated_structure       whether the goal delta repeats across demonstrations
failure_class            one of the five below
fold_index               which failed leave-one-out fold produced it
```

**Frontiers come from failed leave-one-out folds, not from free enumeration.** Extraction runs
per failed fold: induce on the N-1 demonstrations, record the typed derivation, and take the
maximal typed partial terms that arose on a path toward the goal type. Defining a frontier as
"the deepest executable term" would instead measure enumeration artefacts, since many deep
terms execute perfectly while having nothing to do with the transformation. This also ties the
stage to the acceptance gate: **the same leave-one-out failure that blocks certification
becomes the evidence for self-extension.**

Among the terms that arose, a frontier is one of greatest `surface_depth` that executes on
every demonstration input and is not a sub-term of another such term. Incomparable maxima are
all recorded, and ties are never broken by preference, since a preference would encode a hint.

**Two signatures, not one residual.** A frontier's result type need not be the goal type, so it
generally cannot be differenced against the target at all. Each record therefore carries:

```
frontier_value_signature   canonical serialization appropriate to frontier_type
goal_delta_signature       derived independently from the demonstration input and output
behavioural_residual       computed ONLY when frontier_type == goal_type, else NOT_DEFINED
```

No projection from an arbitrary type onto Grid is invented to make residuals comparable. Such a
projection would itself smuggle in the kind of semantic bridge this stage is meant to test for.
Both signatures are normalised so that two tasks differing only in size, palette or position
produce the same value.

**Failure classes**, fixed now: `semantic` (the frontier executes but no continuation matches),
`slot_learning` (a slot could not be fitted), `routing` (no production's result type was
sought), `type_connectivity` (no typed path exists from `frontier_type` to `goal_type`),
`budget` (the search was cut off).

## Clustering, and the provenance firewall

Clustering is by `(frontier_type, goal_type, goal_delta_signature, failure_class)` and **never
by task identity**. A missing capability is therefore evidence about types and compositional dead
ends, not about a named group of puzzles.

Task identity is nevertheless required later, for provenance and for the transfer criterion.
It is kept behind a **firewall**: a separate provenance map from frontier-record id to task id,
written to a file the clustering and invention stages do not read, and opened only when an
extension has already been proposed and must be certified. The invention mechanism therefore
never learns which tasks, or how many distinct ones, motivated a cluster beyond the count it is
given.

**Cluster threshold, frozen before any cluster is seen:** a cluster is eligible when it
contains records carrying **at least three distinct source tokens**, which the mechanism can
verify itself without learning any task identity.

## Certification, frozen

An extension `e` is adopted, giving `K_{t+1} = K_t ∪ {e}`, only when all hold:

1. it resolves the failures of at least two independent source tasks;
2. every one survives full leave-one-out by complete rediscovery under the unchanged verifier;
3. no previously certified task regresses;
4. its semantics are compact and contain no task id, family name or literal answer;
5. it survives synthetic counterexamples designed to break it;
6. it transfers to at least one task **outside its invention provenance**.

Criterion 6 separates an invented capability from a retrofit.

## Frozen interpretations

| Outcome | What it means |
|---|---|
| An extension certifies and satisfies criterion 6 | failure-triggered semantic self-extension demonstrated |
| An extension certifies but fails criterion 6 | invention without demonstrated transfer; recorded, not adopted |
| Candidates proposed, none certifies | the analysis located a gap the mechanism could not fill; a real negative |
| No cluster reaches the threshold | the failures are not compositional dead ends of this kind; the premise is wrong, and that is informative |
| A proposal matches the sealed record | reported as independent rediscovery, with the seal date as evidence |

## Standing prohibitions

No human-written target primitive. No task-family branch. No relaxation of the verifier. No
Lockbox. No score chasing during Level 4. No concept retrieval or routing mechanism until
library growth is measured to cause interference.
