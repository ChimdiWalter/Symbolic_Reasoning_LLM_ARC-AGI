# CORA-TTI feature inventory (audited 2026-09-23, code and tests, not documents)

All paths are in Reasoning_Project_tti. 133 tests were executed this session across
these components; none was taken on trust from a design document.

## ALREADY_BUILT (built and tested)

| Component | Implementation | Test | Evidence |
|---|---|---|---|
| Typed Failure Graph extractor | cora_tti/tfg_extractor.py | tests/test_tfg_extractor.py | passes; populates frontier_term nodes with value signatures |
| Failure-trace instrumentation | level4_blind_runtime.stepA_trace_search via tfg_extractor, cfl_corpus.py | tests/test_tfg_extractor.py | passes |
| TTI loop, end to end | cora_tti/tti_loop.py | tests/test_cfl_and_tti_loop.py | passes; install, re-search, winner-uses, LOO, ablation, reset |
| Ephemeral install and reset into the real engine | cora_tti/tti_fallback.py | tests/test_cfl_and_tti_loop.py | concept file plus env restore in a finally block |
| Baseline full-engine solver | cora_tti/full_engine_solver.py | tests/test_cora_tti_p2.py | passes |
| Constructive vocabulary, the frozen generic grammar | cora_tti/constructive_vocabulary.py | tests/test_constructive_vocabulary.py | passes; AST and token round trip, canonical serialization, family calculus |
| Constructive census machinery, Item 2 v2c | cora_tti/constructive_v2c.py | tests/test_v2c_evidence_contract.py | passes |
| Occurrence-scoped slot fitter | cora_tti/scoped_slot_fitting.py | tests/test_scoped_slot_fitting.py | passes |
| Anonymous target generator, operator dropout | cora_tti/dropout_generator.py | tests/test_constructive_dataset.py | passes |
| Complete-AST and structural holdout law | cora_tti/constructive_dataset.py regimes train_pool / ast_holdout / structural_holdout | tests/test_constructive_dataset.py | passes; R7 split law enforced in code |
| AST canonicalization and witness fingerprinting | constructive_vocabulary.py, dropout_generator.py | test_level4_stepB_item2.py, test_level4_stepB_item1.py | passes |
| Accelerated executor | cora_tti/batched_executor.py | tests/test_batched_executor.py | passes |
| LOO verifier path | tti_loop._loo over the engine's own induction | tests/test_cfl_and_tti_loop.py | passes; verifier itself is the engine's, immutable |
| Ablation ledger | cora_tti/ablation_ledger.py | tests/test_ablation_ledger.py | passes; hash-chained, append-only |
| Anytime scheduler | cora_tti/anytime.py | tests/test_anytime_diversity.py | passes |
| Two-attempt writer and diversity | cora_tti/diversity.py, make_submission_v2.py | tests/test_anytime_diversity.py | passes; 60/60 well formed verified this session |
| Kaggle emulator, gate C0 | cora_tti/kaggle_emulator.py | tests/test_cora_tti_p2.py | passes; two attempts, global budget, offline socket guard |

## PARTIAL

| Component | State | Exact missing behaviour |
|---|---|---|
| GPN-v1 proposer | cora_tti/gpn.py, tests/test_gpn.py pass | Two heads only: production name and result type. The docstring defers argument types to a Stage-B sketch head that does not exist. Structurally cannot emit a held-out name, which is a recorded closed negative, not a defect to re-litigate. |
| tti_loop proposer contract | Built and tested | Both proposers return NAMES from TTIConfig.catalogue, which defaults to the public registry. The code comment states it plainly: "Stage B will swap in constructor-built candidates." The loop is therefore Stage A reconstruction by construction. |

## SPECIFIED_ONLY

| Component | Where specified | Code |
|---|---|---|
| ConstructiveExtensionCompiler | docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL.md | none anywhere in cora_tti |
| Constructive GPN AST decoder, the sketch head | master plan section IV, Item-2 program | none; no sketch_head, ast_decoder or constrained decoding symbol exists |

## CLOSED_NEGATIVE (preserve, do not rerun)

- GPN-v1: known-name reconstruction only; structurally incapable of a held-out name.
- Constructive v1.1: zero admitted under the original fitter.
- Constructive v2/v2c: 896 attempts, 13 admitted, from SUPPLIED candidate schemas, not
  autonomous inventions.
- Failure-signal audit: admitted constructive episodes carried zero frontier_term nodes.
- Real-engine DEV-60 arm: 49 activations, 0 acceptances, and the path was not additive,
  so it answered nothing.
- LAS-R1: not robustly replicated. Synthetic branch closed.

## MISSING (the join, not a subsystem)

No module proposes constructive ASTs FROM a real Typed Failure Graph. The census modules
consume supplied schemas; grep for a proposal function over a TFG in constructive_v2c.py
and constructive_pilot.py returns nothing. Both sides of the join exist and are tested.

## Duplicates identified and withdrawn

The "deterministic MetaConstructor" proposed on 2026-09-23 duplicates Item 2. Withdrawn.
docs/EXPERIMENT_SPEC_CONSTRUCTION.md in this workspace is retained as the experiment
protocol, with its component-building sections superseded by this inventory.
