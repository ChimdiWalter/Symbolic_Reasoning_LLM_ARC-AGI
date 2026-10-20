# Neural-CORA capability and subsumption audit (19 October 2026)

**Is Neural-CORA fully autonomous at diagnosis, revision, verification, learning and semantic invention? NO.**

| term | meaning here |
|---|---|
| IMPLEMENTED | callable code with tests |
| TRAINED | it has fitted weights |
| DEMONSTRATED (dev) | shown on exposed development tasks |
| GENERALIZED | shown on an independent cohort |
| CAUSAL | shown better than matched controls |

An internal leave-one-out certificate is **not** proof that a new prediction is correct. In Phase 2a, frozen native
and matched search each certified one wrong answer (claim ledger row 23).

Evidence references are rows of `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md` (L#) and the named records.

## 1. Capability table

### Representation induction (objects, views)

| aspect | status |
|---|---|
| implementation | A choice among 7 fixed native segmentation views (`geocat_arc/object_reasoning/segmentation.py`). CORA-v2 keeps view hypotheses; the v1 guide scores views |
| executable test | `tests/test_neural_cora.py`; LOO_V1_SEGMENTATION_EQUIVALENCE |
| trained weights | the v1 view head (this pilot) |
| development demonstration | the views supported ka95aa62f67d9 (S2/S6/S4; L12c) |
| independent generalization | none |
| causal evidence | a negative: a frozen, prompted Qwen view ranker did worse than a fixed order (CORA_NEURAL_VIEW_GUIDANCE_RESULT_20261013) |
| limitation | a fixed menu; no part-level or relational representation learning |

### Program induction (a rule that fits)

| aspect | status |
|---|---|
| implementation | the native inducer (`inducer.py`); the typed best-first enumerator (`cora_neural_v1/space.py`); the CORA-v2 version space |
| executable test | `test_neural_cora.py` (enumeration, validity); Phase 2a |
| trained weights | the v1 guide (this pilot) |
| development demonstration | 6 correct object-branch answers on dev60 (L2) |
| independent generalization | Phase 2a fresh cohort: no new correct certified answer from v2 (L23). Kaggle 0.00% for native CORA and CORA-FHR (L13, L15) |
| causal evidence | — |
| limitation | **Bottleneck 1:** often no program fits. Phase 2a had 33 of 40 GEOMETRY_GAP, and on dev60 26 tasks had fitting programs that failed the test (L3) |

### Executable composition (a new composition of existing operations)

| aspect | status |
|---|---|
| implementation | the CORA-FHR constructor (a G-grow grammar of 37,750 expressions) with a typed applicability guard (`cora_fhr/`) |
| executable test | `tests/test_fhr.py` |
| trained weights | no |
| development demonstration | **ka95aa62f67d9 solved: one exposed task** (L12c) |
| independent generalization | **0 of 58** (L12f) |
| causal evidence | **none:** the failure-blind constructor found the same rule (L12c, L12d) |
| limitation | a NEW_COMPOSITION only; one in-sample task |

### Uncertainty and abstention

| aspect | status |
|---|---|
| implementation | CORA-v2: certified, exploratory or none, with diagnoses (`cora_revision_v2/`). v1: the observable diagnoses (`cora_neural_v1/state.py`) |
| executable test | v2 tests; `test_neural_cora_v1_pilot.py` |
| trained weights | no |
| development demonstration | 00dbd492: correct but uncertified (L19). Phase 2a: v2 exploratory answers 2 correct, 0 wrong (L23) |
| independent generalization | Phase 2a: certification ≠ correctness (A and B each had 1 certified wrong) |
| causal evidence | — |
| limitation | calibration not established. v2 certified 0 of 40 |

### Causal failure diagnosis

| aspect | status |
|---|---|
| implementation | CORA-FHR reads native's failure trace; the CORA-v2 diagnoses (GEOMETRY_GAP, …) |
| executable test | `test_fhr.py`, `test_cora_diag.py` |
| trained weights | no |
| development demonstration | diagnoses are produced: 33 GEOMETRY_GAP, 4 COLOUR_POLICY_GAP, … (L23) |
| independent generalization | none |
| causal evidence | **NOT ESTABLISHED.** Failure-blind arms did as well (L9, L10, L12d) |
| limitation | the labels describe failures; they have not been shown to improve outcomes |

### Revision-action selection (what to revise)

| aspect | status |
|---|---|
| implementation | a hand-designed controller (`cora_fhr/revision_controller.py`). The learned pi_phi is **not implemented** |
| executable test | the root-cause record, section 4 |
| trained weights | no |
| development demonstration | NEGATIVE: it missed the one extra-search rescue, 6 vs 7 (L12e) |
| independent generalization | none |
| causal evidence | none |
| limitation | gated behind G1 |

### Reversible revision (install, test, restore)

| aspect | status |
|---|---|
| implementation | CORA-FHR installs operators reversibly in the unchanged engine and restores it |
| executable test | `test_fhr.py`; purity tests |
| trained weights | no |
| development demonstration | ka95aa62f67d9: accepted, used, restored (L12c) |
| independent generalization | the 58-task test: 3 proposals were rejected by the checks and there were 0 wrong answers (L12f). The machinery worked; nothing was gained |
| causal evidence | — |
| limitation | what to revise is not learned |

### Fold-local reconstruction (leave-one-out)

| aspect | status |
|---|---|
| implementation | native leave-one-out certification (`cora_loo/`); CORA-FHR fold rebuilds; CORA-v2 folds |
| executable test | `test_loo_v1.py`, `test_fhr.py` |
| trained weights | no |
| development demonstration | ka95aa62f67d9 rebuilt in 3 of 3 folds (L12c) |
| independent generalization | Phase 2a: certified does not mean correct (L23) |
| causal evidence | — |
| limitation | a fold check is internal evidence, not the truth |

### Semantic operation invention

| aspect | status |
|---|---|
| implementation | — (Step B is a separate experiment, not used) |
| executable test | — |
| trained weights | — |
| development demonstration | **NOT ESTABLISHED.** Only new compositions |
| independent generalization | — |
| causal evidence | — |
| limitation | a bounded-novelty protocol needs approval |

### Cross-task reuse (a reusable abstraction)

| aspect | status |
|---|---|
| implementation | no library promotion in the evaluated runs |
| executable test | — |
| trained weights | — |
| development demonstration | **NOT DEMONSTRATED** |
| independent generalization | 0/58 transfer of guarded construction (L12f) |
| causal evidence | — |
| limitation | — |

### Independently checked execution

| aspect | status |
|---|---|
| implementation | the fixed native interpreter; a separate evaluator that alone reads the answers |
| executable test | `test_neural_cora.py`; every pilot evaluator |
| trained weights | no |
| development demonstration | in every pilot |
| independent generalization | in every pilot |
| causal evidence | — |
| limitation | — |

### Learned program proposal (Neural-CORA v1)

| aspect | status |
|---|---|
| implementation | a frozen Qwen3-4B encoder plus trainable heads that order CORA's typed search (`cora_neural_v1/prior.py`) |
| executable test | `test_neural_cora_v1_pilot.py` |
| trained weights | **YES.** 1,560 optimizer steps; the weight hashes changed (`974dc51c…` → `2aa5af84…`) |
| development demonstration | the v1 pilot (`records/NEURAL_CORA_V1_PILOT_REPORT.md`) |
| independent generalization | held-out synthetic compositions: L1 198/395 |
| causal evidence | **G1 NO-GO.** Learning helps over plain, untrained and shuffled search: L1 198/395 vs C+ 104, L0 30, L0s 51. It is **worse** than hand features (L1h 235, p = 0.0009) and strong symbolic search (C+H 358) |
| limitation | ranks a fixed, small language. It cannot propose outside it. The factorized heads cannot express selector–action pairing |

### Learning from failure (a revision policy learned from experience)

| aspect | status |
|---|---|
| implementation | **not implemented** |
| executable test | — |
| trained weights | — |
| development demonstration | — |
| independent generalization | — |
| causal evidence | — |
| limitation | the central open question (G3) |

### Biological transfer

| aspect | status |
|---|---|
| implementation | proposal only (`docs/BIO_TRANSFER_PROPOSAL_20261013.md`) |
| executable test | — |
| trained weights | — |
| development demonstration | **PROPOSED, UNTESTED** (L17) |
| independent generalization | — |
| causal evidence | — |
| limitation | the evidence, causal interpretation and validators all differ |

## 2. What was subsumed from Qwen and NVARC, and what was not

**Reused inside CORA:**
- the NVARC Qwen3-4B checkpoint `sorokin/qwen3_4b_grids15_sft139` (Apache-2.0) as a **frozen** encoder;
- NVARC's grid chat format, used only to feed that encoder.

**Not reused:**
- NVARC's per-task test-time LoRA;
- its decoding, augmentation scoring and voting;
- its output grids;
- its synthetic program completions, which are unlicensed, and whose seeds cover the public ARC splits
  (CORA_NVARC_SUBSUMPTION_AUDIT_20261019).

**NVARC stays a frozen third-party baseline:** 27.64% public, submission 57160429, the deployment in
`kaggle/neural_v1/`, unchanged. It is not part of Neural-CORA's answers.

## 3. Frozen baselines

The baselines are hashed in `records/NEURAL_CORA_V1_FREEZE_MANIFEST.json` (`python -m cora_neural_v1.pilot freeze`):
- native CORA v23 (`geocat_arc/`);
- CORA-FHR (`cora_fhr/`);
- CORA-v2 (`cora_revision_v2/`);
- the Phase 2a frozen outputs: eval `76783bb8…`, report `a43f64b5…`;
- the CPU clock (`cora_funnel/`);
- the NVARC deployment (`kaggle/neural_v1/`);
- the NVARC checkpoint;
- the v1 code at freeze.

None of these is modified by the v1 pilot.
