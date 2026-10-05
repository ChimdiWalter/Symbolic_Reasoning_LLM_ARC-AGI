# Item-2 v1.8: the no-oracle extension proposer (design record)

Written 2026-10-05, before any development measurement. Every cap, order
and law below was fixed before the first development task was generated.
Starting HEAD 2299c95 (v1.7 COMPILER_ACCEPTED).

## 1. Question

Can CORA construct a useful executable semantic extension from its own
failure and its demonstrations, without being handed the target extension
or a correct candidate pair? v1.6 chose between two oracle candidates; v1.7
compiled an oracle-selected extension. v1.8 removes the oracle itself.

## 2. What the frozen semantics make possible

Three facts from the frozen code decide the mechanism.

1. **Layers.** In `meta_ast.evaluate` every block's Partition, Select and
   Key read the original input grid; only Paint writes. A multi-block
   program is a stack of paint layers computed from the input, and a later
   layer overwrites an earlier one.
2. **Joint coverage.** The occurrence-scoped fitter (frozen, identity
   2cc45152) requires the blocks to explain the change jointly: every
   changed cell covered, every touched region changed entirely and
   uniformly, one colour per (block, key), every key witnessed in at least
   two demonstrations. So on a task that needs two layers every one of K's
   200 single-block programs fails, which is why v1.7's comparison sets were
   empty.
3. **Partial explanations are K's failure state.** A K block that satisfies
   every one of those rules on its own regions but covers only part of the
   change is a precise, mechanically defined near-miss: a partial
   executable structure with a residual. Which blocks are partial, which
   conflict and why, and which cells remain unexplained is K's typed
   failure frontier on this task.

K's 200 programs are every partition (4) x predicate (5) x feature (10)
with exactly one Select. A target block with zero Selects behaves exactly
like K's block with `Select(all)`, so compositions of K's own blocks can
express every target of the frozen families behaviourally.

## 3. The mechanism: residual peeling over K's own blocks

The proposer builds extensions only by composing K's existing productions,
in the grammar's own sequential composition, and only where K's failure
says a layer is missing.

1. **Frontier.** For each of K's 200 blocks, on the demonstrations:
   PARTIAL (consistent on its regions, covers a non-empty proper part of
   the change in at least one demonstration, every key witnessed in at
   least two demonstrations), FULL (consistent and covers everything; K
   would solve), CONFLICT (with the frozen failure code), or UNDEFINED.
2. **Top layer.** Each PARTIAL block is a candidate last layer. A last
   layer owns every cell it selects, so its single-block analysis is
   exact.
3. **Lower layer.** For a top layer b, the residual is the changed cells b
   leaves unexplained. A K block a is a candidate lower layer if, on the
   cells b does not own, it covers the whole residual and is consistent
   (entire, uniform, functional, its unchanged regions keep their colour,
   two witnesses per key). The proposal is the composition [a; b].
4. **Depth.** Two layers first. Three layers (top, middle, bottom by the
   same rule, the middle covering a non-empty part of the residual) only
   if no two-layer proposal verifies. Three is the frozen grammar's block
   limit.

No operator, partition, predicate or feature outside K's frozen vocabulary
can appear. Nothing reads a target, a seed, a family or a held-out pair.

## 4. Frozen bounds (fixed before development)

| bound | value |
|---|---|
| layers per proposal | 2, then 3 only if no 2-layer proposal verifies |
| Select stages per block | 1 (K's own blocks) |
| top layers considered (depth 2) | 32 |
| lower layers per top (depth 2) | 16 |
| tops x middles (depth 3) | 8 x 8, bottoms per middle 16 |
| proposals per depth (verification attempts) | 256 |
| verified candidates probed | 32 |
| wall time per proposer call | 180 s (RESOURCE_EXHAUSTED) |
| order of tops | covered cells descending, table entries ascending, K index |
| order of lower layers | table entries ascending, K index |
| duplicate law | a block is never composed with itself; syntactically equal compositions once; verified candidates with the same probe fingerprint collapse to the first in MDL order |
| MDL order | total table entries, then AST nodes, then canonical text |

## 5. Selection (the frozen v1.6 hierarchy, extended only where v1.6 never applied)

1. **Verification:** the occurrence-scoped fitter fits the candidate
   exactly on every demonstration.
2. **Duplicates:** verified candidates with the same fitted fingerprint on
   the frozen probe grids collapse to one.
3. **P0 (pure CFR rule, unchanged):** v1.6's probe gives each candidate its
   response (LOO exact, LOO cell error, LOO fit failures, table entries).
   P0's lexicographic order picks the unique maximum.
4. **D (demonstration selector, only on P0 ties):** v1.6's D model, refitted
   once on v1.6's frozen training resource by v1.6's own code and pinned.
   D applies to a tie set whose members differ only in key-feature tokens;
   each member scores the sum of D's logits at the positions that differ.
   With one differing position this is exactly v1.6's D decision.
5. **MDL guess (new, declared here):** when D does not apply or ties, the
   first candidate in MDL order. v1.6 never faced N-way ties outside D's
   domain; this level is a deterministic Occam guess and every selection
   records the level that decided it.

The pure arm stops after P0 and abstains on a tie (SELECTION_ABSTAINED).

## 6. The pipeline and its isolation

failure evidence -> proposer candidates -> verification and probe ->
selection -> v1.7 compiler -> temporary installation in K* -> rerun.

- The proposer input is one closed object: the training demonstrations,
  the frontier computed from them, the frozen grammar limits and the K*
  identity. A leakage scanner refuses any other key, any task, seed,
  family, target or held-out field, and any 64-hex string other than the
  K* identity. Leakage is a blocking failure.
- The compiler receives the selected schema with provenance: the
  proposer's code hash and the hash of the proposer input.
- **Real S5:** each leave-one-out fold removes its held-out demonstration
  first, recomputes the frontier from the remaining demonstrations, runs
  the proposer and the selection from scratch, compiles from scratch,
  installs into a fresh K*, reruns, and predicts the held-out
  demonstration. Fold engine events are recorded. Nothing from the
  full-data proposal enters a fold.

## 7. S6 separation law

- A, syntactic: the extension is not one of K's 200 programs.
- B, bounded search: K's search has no exact fit on the demonstrations.
- C, behavioural: on the frozen probe grids the fitted extension differs
  from every relevant existing K program. The relevant set is K's PARTIAL
  blocks on this task, each fitted on its own consistent regions, plus any
  K program that fits loosely. It must be non-empty; an empty set makes C
  untestable and the claim is downgraded, never called novel.

## 8. Failure classes

K_ALREADY_SOLVES, NO_PROPOSAL, PROPOSAL_LIMIT, UNTYPEABLE_PROPOSAL,
DUPLICATE_EXISTING_SEMANTICS, NO_VERIFIABLE_PROPOSAL, SELECTION_ABSTAINED,
COMPILE_FAILURE, ENGINE_REJECTED, LOO_FAILURE, LEAKAGE_FAILURE,
RESOURCE_EXHAUSTED, SUCCESS.

Infrastructure failures (RESOURCE_EXHAUSTED, COMPILE_FAILURE,
UNTYPEABLE_PROPOSAL, LEAKAGE_FAILURE, any crash) are reported apart from
scientific negatives.

## 9. Ablations

| arm | what changes |
|---|---|
| no proposer | K* alone |
| DEMO_ONLY | candidates from a demonstration statistic only: K blocks ranked by the share of changed cells their selected regions touch, composed in that order, same caps; no consistency, conflict or residual information |
| FAILURE_CONDITIONED | the proposer of section 3 |
| SHUFFLED_FRONTIER | the frontier of another task (a fixed derangement) replaces the task's own; the demonstrations stay |
| NO_RESPONSE | selection without the probe: verification, D, MDL |
| compiler ablated | the selected extension is not compiled or installed (K* alone) |
| extension removed | after a solve, K* is rerun without e (the paired ablation's K* arm) |

## 10. Development plan

- Corpus: seed 840,000,000 + 100k, family S.FAMILIES[k mod 5], the v1.7
  acceptance filter unchanged (at least 2 blocks, 8 demonstrations, 7 for
  training and 1 held out, exact scoped fit of the generator's schema on
  the 7, no exact K fit, scoped leave-one-out re-derivation). The first 40
  tasks for the proposer-level audit, the first 8 of them also through the
  engine with real S5.
- The generator's schema is used only after the fact, to measure whether
  an equivalent extension was proposed, verified and selected. That is
  engineering evidence, not a result.
- Reserved for the prospective test: seed 860,000,000 + 100k, excluded:
  every development task, the v1.7 fixtures and every digest in the v1.5
  and v1.6 exclusion sets.
