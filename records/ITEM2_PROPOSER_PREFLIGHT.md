# Stage-B constructive AST proposer: preflight

Written 2026-09-23, before any proposer code. Records the authoritative
frozen protocol so it is not silently redesigned, per the standing rule that
a frozen requirement is reported as incompatible rather than changed after
the fact.

## Authoritative sources

| item | path | identity |
|---|---|---|
| protocol document | `Reasoning_Project_tti/docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL.md` | sha256 `b9587eab...e12d8495` recorded in the manifest |
| machine-readable manifest | `Reasoning_Project_tti/outputs/tti/constructive_protocol_manifest.json` | protocol "CORA-TTI Item-2 constructive proposer, v1.1" |
| freeze date | recorded in the manifest | 2026-09-03, before any dataset generation or training |
| grammar authority | `cora_tti/constructive_vocabulary.py` | reads the manifest; sole legality authority |

Both are read-only from this workspace. Neither is modified.

## Frozen parameters, not to be redesigned

Grammar: blocks 1 to 3; selects per block 0 to 2; one induced slot per
block; at most 48 AST nodes; at most 12 stages; family is the tuple of
per-block select counts; MDL is `meta_ast.ast_nodes`. Banned target families
are `(0,)` and `(1,)`, because a single block is baseline expressible.

Operators, seven: Compose, Key, Lookup, Map, Paint, Partition, Select.

Type universe, ten: Grid, Set[Region], Set[Coloured], FeatureValue, Colour,
PartitionExpr, Predicate, FeatureExpr, Map[FeatureValue,Colour], Function.

Ranking: beam 16; score `logp - 0.05*MDL - 0.01*predicted_cost_s`; top k
reported at 1, 3 and 5.

Budgets: baseline failing search 8.0 s; fit per candidate 2.0 s; leave-one-out
8.0 s per fold.

Model family: TFG encoder, interface embedding, grammar-constrained
sequential decoder. Non-LLM. Hidden size at most 256. Stopping at 2000 epochs
or a 200-epoch plateau in validation exact@5.

Splits: root seed 20260903; train families `(0,0)`, `(1,0)`, `(0,1)`,
`(1,1)`, `(0,0,0)`; family holdout `(2,)` and `(2,1)`; sizes train 300,
val 60, test 90, pilot 60; train seeds 11000+, val 12000+, test 13000+.

Negative controls, four: an irrelevant candidate never certifies; a family
`(1,)` target is rejected as baseline expressible; the positive control is
recoverable; a hard negative stays unsolved without a protocol change.

Recorded shortfall already in the manifest, carried forward unchanged:
interface holdout is `INFEASIBLE_V1_SINGLE_INTERFACE`.

## Reusable substrate already present

`constructive_vocabulary` supplies `ast_from_blocks`, `blocks_from_ast`,
`tokens_from_ast`, `ast_from_tokens`, `family`, `mdl`, `canonical`,
`digest`, `validate`, `is_banned_target_family`, `is_holdout_family`,
`GrammarState`, `tokens_are_valid` and `enumerate_asts`. `GrammarState` and
`tokens_are_valid` are the legality mechanism for constrained decoding, so
the decoder does not need its own grammar.

## Contract to implement, and nothing more

    propose_ast(tfg, interface, k, ...) -> ordered candidate ASTs

Each candidate carries the canonical AST, the typed interface, the structural
family, MDL, the proposal score and construction provenance. No test output,
no task id, no ARC family label, no natural-language solution, and no
manually supplied missing primitive.

## Claim ceiling for the proposer block

At most: failure-conditioned new-AST generation, and only if a legal AST
absent from the catalogue is produced from a real typed failure graph. Not
claimable: constructive reach, new capability, semantic extension, invention,
transfer or score improvement.

The extension compiler stays a separate responsibility and is not built in
the same block.
