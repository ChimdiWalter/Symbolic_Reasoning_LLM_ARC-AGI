# CORA-ONLY-G3 Kaggle entry: progress

Status as of 2026-10-21 22:55Z. Update this file at every step.

## Done
- CONFIG.md: the configuration, written before any evaluation (pipeline, attempt policy, budgets, pre-written
  development changes C1 to C3, evidence categories, terms).
- cora_only.py: the notebook code (staging, native v23 phase, isolated ncv2-g3 phase, merge, validation, dev scoring).
- build_package.py: package + private dataset + three private kernels (submit, dev_a, dev_b), staged under
  outputs/kaggle_deploy/cora_original_2026/ (git-ignored). Provenance audit passes (305 files: 273 native + 31 CORA +
  manifest).
- emulate.py: offline emulation. `fixtures` mode passed: 3 synthetic tasks, 4 test outputs, 0 schema problems, all 4
  correct, both test inputs of the multi-input task in order (run before the label refinement).
- arm_e.py: arm E entry for the frozen real-task check (records/NEURAL_CORA_REALARC_G2G3G4_PROTOCOL_20261021.md).

## Next
1. Tests (tests/test_kaggle_cora_original_2026.py); rerun the fixtures emulation after the label refinement.
2. Commit; freeze arm E (records/NEURAL_CORA_REALARC_G2G3G4_ARM_E_MANIFEST.json plus an addendum) BEFORE syn-v4 ends
   (outputs/neural_cora_v2g4/synthetic_eval/run.status gets an EXIT line; then it is too late).
3. Upload the private dataset; push the three private kernels (internet off); record slugs and versions here.
4. When the dev kernels finish: score, try C1 to C3 only as CONFIG.md allows, then write
   records/KAGGLE_CORA_ONLY_G3_SUBMISSION_READY_20261021.md. No competition submission without authorization.

## Kaggle runs
(none yet)
