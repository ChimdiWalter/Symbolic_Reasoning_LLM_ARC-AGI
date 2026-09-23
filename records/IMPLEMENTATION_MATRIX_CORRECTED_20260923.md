# Corrected implementation matrix, 2026-09-23

Supersedes the status rows in `records/FEATURE_INVENTORY_20260923.md` and
`records/ASSET_TABLE.md`. Appended, not substituted; the earlier files are
preserved for the record.

## Correction to the earlier inventory

Two rows in the earlier inventory were too strong and are withdrawn.

`mdl_fallback_proposer` is **not** a MetaConstructor. Its contract is
`(TFG, k) -> existing catalogue production names`: it sorts the known
catalogue by cost and name and returns the top k. That is Stage-A known
operator reconstruction. `tti_loop.py` says so itself, noting that Stage B
must swap in constructor-built candidates.

`constructive_vocabulary.py` is the frozen law of legal constructive ASTs.
It answers what constitutes a legal new program. It does not answer which
program to construct given a failed trace, and it is not a proposal
mechanism.

Neither component performs autonomous semantic construction.

## BUILT_AND_TESTED

| component | file |
|---|---|
| Typed Failure Graph extractor | `cora_tti/tfg_extractor.py` |
| constructive vocabulary / AST grammar | `cora_tti/constructive_vocabulary.py` |
| AST token round-trip and canonicalization | `cora_tti/constructive_vocabulary.py` |
| constructive dataset and pilot machinery | `cora_tti/constructive_dataset.py`, `constructive_v2_dataset.py` |
| occurrence-scoped fitting | `cora_tti/scoped_slot_fitting.py` |
| TTI orchestration loop | `cora_tti/tti_loop.py` |
| Stage-A GPN name proposer | `cora_tti/gpn.py` |
| exact verifier and leave-one-out | `cora_tti/tti_loop.py` |
| ablation ledger | `cora_tti/ablation_ledger.py` |
| scheduler and diversity | `cora_tti/anytime.py`, `cora_tti/diversity.py` |
| Kaggle emulator | `cora_tti/kaggle_emulator.py` |

133 component tests pass.

## BUILT_BUT_LIMITED

| component | limitation |
|---|---|
| `mdl_fallback_proposer` | ranks existing catalogue names only |
| GPN-v1 | known-name and result-type prediction, not unseen AST construction |
| real-engine TTI fallback | infrastructure exists, but the historical comparison was not a valid additive K versus K+e test |
| TFG extractor | structurally implemented and correct on its own path, but that path is the 11-primitive blind runtime; measured 2026-09-23 as carrying no task-conditioned candidate evidence on real ARC failures |

## SPECIFIED_ONLY

| component | evidence |
|---|---|
| grammar-constrained constructive AST decoder | no implementation; `gpn.py` has a name head and a result-type head, and defers argument types to a Stage-B sketch head that does not exist |
| ConstructiveExtensionCompiler | identifier occurs only in `docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL.md`; zero Python hits |

These two responsibilities stay separate. The proposer decides what rule to
construct. The compiler only translates that rule into the engine's
task-local representation.

## MISSING

The autonomous real-task path, end to end:

    real failed reasoning
      -> informative TFG
      -> newly constructed AST absent from K
      -> additive ephemeral install
      -> correct ARC solve
      -> leave-one-out
      -> ablation

Most of CORA-TTI exists. The unseen-AST construction path is not yet proven
to exist end to end, and as of 2026-09-23 its first link is measured
defective.

## No "wiring only" claim

That claim is not licensed. It would require all three of an informative real
failure frontier, a constructive unseen-AST proposer and a compiler with an
additive install path to be shown executable. The first is measured
unusable today; the other two are unimplemented.
