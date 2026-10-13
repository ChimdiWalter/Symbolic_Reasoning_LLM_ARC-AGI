# Integrity incident: the evaluation files were hashed during smoke run 1 (2026-10-13)

**Classification: PROTOCOL VIOLATION.** A minor one: the data was read into
sha256 only, never parsed or used. It is recorded permanently.

## What happened

- **Where.** Kaggle kernel `chimdiwalter/nvarc-qwen3-4b-smoke-v1`, version 1,
  pushed 2026-10-13T14:36:37Z, ended with ERROR at about 14:49Z.
- **What.** I added a logging-only "identity" cell. It walked
  `/kaggle/input` and computed sha256 over every file's bytes, to record the
  asset identity. The walk included the competition's
  `arc-agi_evaluation_solutions.json` (223,838 bytes) and
  `arc-agi_evaluation_challenges.json`.
- **What reading means here.** Their bytes were read by the hash function
  only. Nothing was parsed, compared, displayed or used by any solver code.
  A sha256 digest reveals no answer.
- **The rule broken.** The smoke-test requirement (check 11: no
  evaluation-solution file is opened) and the project rule against
  accessing evaluation answers. Opening a file to hash it is still opening
  it.

## Consequences

- **Smoke run 1 is excluded from every evidence tier.** It produced no
  predictions anyway: the solver failed on the model path before any task.
- **No result is affected.** No scientific or competition result uses data
  from that run.
- **The digests are not used.** They sit only in
  `outputs/kaggle_deploy/neural_v1_smoke_run1/asset_identity.json`, which
  is git-ignored and never referenced.

## Correction and confirmation for every later run

**The rule from version 2 on.** The identity cell skips any file whose
name contains "solution" or "evaluation". It records only its size from
`os.stat`, which does not open the file.

| run | evaluation files opened? | evidence |
|---|---|---|
| smoke v2 (14:52Z) | no | `asset_identity.json` lists both evaluation files under "not_opened". The solver read `arc-agi_test_challenges.json` (the stand-in) and, for the functional check, `arc-agi_training_solutions.json` (training, permitted) |
| probe, smoke v3 (15:54Z) | no | the light identity cell skips them; the notebook text has 0 references to `evaluation_challenges` or `evaluation_solutions` (build assertion) |
| full NEURAL_TTT_BASELINE v1 (16:22Z) | no | the same: build assertion of 0 references; light identity cell |
| native_v1 (all runs) | no file is *read* for answers | `notebook.py` copies the competition JSONs into the staged data folder, then **deletes** the copied `arc-agi_evaluation_solutions.json` and writes `{}` before the harness starts. The harness never sees evaluation answers. That copy step moves the file's bytes without parsing them; it is recorded here for completeness |

**Both packages are guarded by build-time assertions:**
- `kaggle/neural_v1/build_full.py` refuses to build if any evaluation file
  name appears in the notebook code;
- `kaggle/neural_v1_smoke/build_smoke.py` checks the same at build time.
