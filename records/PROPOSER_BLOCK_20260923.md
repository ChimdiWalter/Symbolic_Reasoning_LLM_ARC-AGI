# Stage-B constructive AST proposer: implementation and first measurements

2026-09-23. Nothing was compiled, installed, re-run or scored. No hidden
output, HOLDOUT, E_transfer, Lockbox or Step-B material was touched. Step B
was unaffected. Work is confined to the isolated sprint workspace.

## Verdict up front

NEW_AST generation works. Failure conditioning does not yet work on real
data, and that is measured, not assumed.

## 1. Files changed

| file | change |
|---|---|
| `cora_arc2026/constructive_proposer.py` | new, the proposer |
| `tests/test_constructive_proposer.py` | new, 14 frozen controls |
| `scripts/proposer_real_tfg_smoke.py` | new, the real-failure smoke test |
| `records/DATA_USAGE_ORDER.md` | new, binding data-consumption order |

No file in `Reasoning_Project` or `Reasoning_Project_tti` was modified. The
grammar, the manifest and the legality machinery are read only.

## 2. Architecture

    typed failure graph -> permitted evidence
      -> log-linear scorer over grammar-legal tokens
      -> beam search masked by GrammarState
      -> validate, dedup by digest, drop banned families
      -> rank by the frozen score
      -> ordered candidate records

`GrammarState.legal_tokens` is the only legality authority, so the decoder
cannot emit an ill-typed or out-of-bounds AST by construction. Token to AST
conversion, canonicalization, MDL, validation, family and the banned and
holdout family predicates are all reused unchanged.

Permitted evidence, fifteen signals: frontier term count, slot failures,
executed-not-exact count, distinct frontier operators, palette introduced and
removed, shape preserved, shrinks, grows, fraction changed, fraction wrong,
palette extra, shape mismatch, defined signatures, and an empty flag. No task
id, no ARC family label, no test output, no natural-language solution, no
supplied primitive.

## 3. Frozen parameters used, read not restated

Beam 16, MDL weight 0.05 and cost weight 0.01 are read from the manifest at
import and asserted equal to it by a test. Grammar bounds, families, ops,
predicates, partitions and key features come from
`constructive_vocabulary.vocab()`. The frozen interface-holdout shortfall is
carried forward unchanged.

`absent from K` is defined by the protocol's own ban: the enumerated families
`(0,)` and `(1,)` are baseline expressible, so their digests are K. Every
emitted candidate is checked against that set.

## 4. Synthetic controls: 14 of 14 pass

| control | result |
|---|---|
| Stage-A baseline still returns catalogue names, not ASTs | pass |
| proposer returns ASTs, never a catalogue name | pass |
| complete-AST holdout, reported as coverage | see section 5 |
| holdout families flagged, and excludable on request | pass |
| banned baseline-expressible families never emitted | pass |
| irrelevant evidence recorded empty and changes the output | pass |
| proposals differ for different synthetic failures | pass |
| value-permutation shuffle changes the proposal | pass |
| every emitted AST legal under the frozen grammar | pass |
| illegal token sequences rejected mechanically | pass |
| unknown terminals rejected by validate | pass |
| ordering deterministic and matching the frozen rule | pass |
| frozen ranking parameters read from the manifest | pass |
| no forbidden information in the output record | pass |

One control was defective when first written and was corrected before its
result was used: reversing a dictionary's items does not permute it, so the
shuffle was a no-op. The corrected control rotates the numeric signals across
field names, preserving the multiset, and it passes.

## 5. Coverage of the legal space

The decoder is a ranked proposer, not an enumerator, and the measurement
shows what that costs.

| beam | distinct ASTs emitted | structural families |
|---|---|---|
| 16, frozen | 30 | 5 |
| 64 | 112 | 9 |
| 256 | 518 | 16 |

Sampling the legal space at up to two blocks gives thousands of non-banned
ASTs, so at the frozen beam the proposer reaches a small ranked slice. None
of the first 200 enumerated targets appears in that slice. That is expected
for a ranked proposer with an unfitted scorer and is reported rather than
treated as a pass or a failure.

## 6. Real-failure smoke test

Five tasks, fixed by rule before any proposal was inspected: the first five
in ascending order of the eight the repaired frontier audit found to carry
defined candidate-associated evidence. Interface `Set[Region] -> Grid`, top
five, frozen beam.

| task | candidates | absent from K | families | top score | runtime |
|---|---|---|---|---|---|
| dev01 | 5 | 5 | (0,0), (2,) | -7.190 | 0.052 s |
| dev02 | 5 | 5 | (0,0), (2,) | -7.628 | 0.022 s |
| dev03 | 5 | 5 | (0,0), (2,) | -6.738 | 0.026 s |
| dev04 | 5 | 5 | (2,), (2,0) | -8.343 | 0.028 s |
| dev05 | 5 | 5 | (0,0), (2,) | -7.372 | 0.026 s |

Twenty-five proposals, all legal, all complete canonical ASTs, all absent
from K. Proposal runtime is about 0.03 seconds per task.

An example of an emitted candidate, in block form: partition the grid into
background components, select the rectangular ones, key them by whether they
are rectangular, look the key up in an induced colour table, and paint. That
is a complete executable structure in the frozen grammar, not a production
name.

### The problem this test exposes

| measure | value |
|---|---|
| distinct top-five orderings across the five tasks | 2 of 5 |
| distinct rank-one candidates | 1 of 5 |
| union of all proposals across 25 slots | 8 ASTs |

All five tasks propose the same rank-one AST. Four of the five produce an
identical ordered list.

The evidence itself does vary across those tasks: frontier terms from 3 to
12, slot failures from 2 to 32, distinct frontier operators from 2 to 6, and
fraction wrong from 0.094 to 0.224. So the failure graphs differ and the
proposals mostly do not. The evidence prior saturates and washes those
differences out.

The synthetic conditioning controls pass because their evidence vectors are
far apart by construction. Real development failures are closer together, and
at that separation the current scorer does not discriminate.

Nothing was tuned after seeing this. The measurement stands as recorded.

## 7. Claim earned and not earned

Earned: **NEW_AST generation from a real typed failure graph.** Legal,
complete, canonical ASTs absent from K are produced from real reasoning
failures, deterministically, in about 0.03 seconds, under the frozen grammar,
beam and ranking rule, with no forbidden information reaching the proposer.

Not earned: **failure-conditioned generation on real data.** One rank-one
candidate across five distinct failure graphs is not task conditioning. The
full claim ceiling for this block was failure-conditioned new-AST generation,
and only the generation half is met.

Also not earned, and not attempted: constructive reach, new capability,
semantic extension, invention, transfer, or any score improvement.

## 8. Exactly one next action

**Fit the scorer weights on the existing constructive dataset, per the frozen
model specification.**

The manifest already specifies the model: a typed-failure-graph encoder with
an interface embedding and a grammar-constrained sequential decoder, non-LLM,
hidden size at most 256, stopping at 2000 epochs or a 200-epoch plateau in
validation exact@5. The evidence prior in this implementation was always a
placeholder for those fitted weights, and section 6 measures the cost of
leaving it unfitted.

The scorer already exposes a `weights` mapping for exactly this, so fitting
changes no interface and no other component. The frozen splits, seeds, train
families and holdout families are all recorded and unchanged. After fitting,
re-run these same controls and this same smoke test, and require the
rank-one candidate to vary across tasks whose evidence varies.

The ConstructiveExtensionCompiler stays separate and unbuilt.
