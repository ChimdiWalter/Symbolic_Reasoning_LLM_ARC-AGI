# CORA × Qwen3-4B fusion: Stage 0 feasibility record (19 October 2026)

**Status:** audit only. No neural run, no Kaggle action. Nothing here is a result.

**Directives:** "CORA × QWEN3-4B — NEURAL–SYMBOLIC FUSION SPRINT" and its detailed Markdown version. Together they
authorize design, small preregistered experiments, and preparing (not submitting) one hybrid notebook.

## 1. Current state, and no interference

- **Phase 2a** (frozen, growth-only v2; 40 eligible tasks) is RUNNING: 85 of 120 arm rows at 12:43 local. This audit
  reads files only and starts no compute, so it does not touch Phase 2a or Step B.
- **The NVARC reproduction is preserved unchanged.** It consists of `kaggle/neural_v1/`, the run artefacts in
  `outputs/kaggle_deploy/neural_v1_full_run1/`, and submission 57160429 (public 27.64).

## 2. What is reused unchanged from NVARC

Source: `records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md`.

| component | identity |
|---|---|
| upstream notebook | `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue`, version 10 (pulled copy sha256 506b85db) |
| checkpoint | `sorokin/qwen3_4b_grids15_sft139` (Transformers/bfloat16/1); pretrained by the NVARC team on their synthetic data; unchanged |
| per-task test-time training | LoRA, r = 256, with augmentations and schedule; unchanged |
| decoding | DFS, 540 s cap; 20-minute per-task cap; unchanged |
| scoring and selection | `score_kgmon`; unchanged |
| runtime guard | 12 × 3600 − 600 s; unchanged |
| our changes | 6, all compatibility, coverage, diagnostics, provenance or robustness; no algorithmic change |

## 3. Neural interfaces actually available

Checked, not assumed.

**Saved from the full run (`neural_v1_full_run1/`):**
- `submission.json`: the final two attempts per output, for 240 tasks and 259 outputs;
  - every output has a genuine attempt 1;
  - only **112 of 259 have a genuine attempt 2**; the rest are not genuine attempts;
  - 0 outputs have identical attempts;
- the notebook log (1.1 MB);
- `execution_manifest.json`, `coverage_audit.json` and an asset identity file.

**Not saved:**
- the decoded candidate pool. 4,090 decoded output files existed in `/kaggle/working` during the run but were not
  downloaded;
- per-candidate scores;
- logits and hidden states;
- the per-task LoRA states;
- any generated DSL or program text. The model emits grids only.

**Consequence.**
- Routes R1 (neural candidates → CORA hypotheses) and R3 (neural-guided selection) both need a **new, instrumented
  NVARC run** that saves the candidate pool and scores. That is a new versioned builder; `neural_v1` stays as it is.
- Route R2 (neural representation proposals) has no direct interface: the checkpoint was trained to emit grids, not
  objects or programs.

## 4. Compute

- **Athe:** 2 × RTX 2080 Ti, 11 GB each (Turing: no bf16, no FlashAttention-2). On Kaggle, NVARC peaked at 11–18 GB per
  GPU over 4 GPUs, so its test-time training cannot run here at parity. **All neural runs must be Kaggle kernels.**
- **The recorded Kaggle run:** 4.34 h for 240 tasks; median 174 s per task, p90 518 s, maximum 1,362 s; 1 task timed
  out.
- **Headroom:** fusion overhead on CPU (CORA) must fit the remaining headroom, about 7 h less a safety margin, on Kaggle's
  CPU budget.

## 5. The decisive constraint: where NVARC can be measured

- **The training stand-ins are saturated for NVARC.** Its pipeline-health check on the 240 training stand-ins was
  **229.5 of 240** (contaminated, not a score). Only about 10 tasks give room for a fusion gain, and they are exposed.
  So no ARC-AGI-2 *training* task can show whether fusion adds correct answers that NVARC misses.
- **The public evaluation set is the closest proxy, but is held back.** Its 120 tasks are split here into DEV 60
  and HOLDOUT 60.
  - HOLDOUT is protected.
  - DEV 60 has been kept unused by the arc2026 pilot rules.
  - Step B's protocol keeps the public evaluation untouched until its Lockbox evaluation.
  - Whether NVARC's own training data includes the public evaluation is undocumented here and must be checked in the
    NVARC write-up.
- **Using DEV 60 for fusion development needs the user's explicit decision** (it consumes that set).
- **Without it,** the only clean tests are the hidden Kaggle set (one submission a day, and official) or new synthetic
  tasks (not ARC).

## 6. Competition rules (re-checked 19 October)

- **From the official ARC Prize 2026 page:**
  - submissions are due **2 November 2026**;
  - Kaggle notebooks run with **no internet**;
  - no API-based systems;
  - open-sourcing is required for prize eligibility;
  - a prize-structure discrepancy exists between ARC Prize pages.
- **Runtime:** the 12-hour cap is from NVARC's notebook guard and last year's rules, and was not found on the pages
  retrieved. **Confirm on the Kaggle rules page before packaging.**
- **Our submissions** so far are 57144804, 57160429 and 57354496. Daily quota and final-selection limits must be
  re-read on Kaggle before any upload.

## 7. Information-boundary risks

1. **Fold leakage.** NVARC adapts LoRA on all of a task's demonstrations. Any neural-assisted leave-one-out
   certificate must re-adapt with the held-out demonstration excluded, which multiplies GPU cost by about the number
   of demonstrations. Otherwise label it "neural-assisted, not independently certified".
2. **Contamination.** As in section 5, training tasks cannot measure generalization for the checkpoint.
3. **Answer-stacking risk.** The 147 non-genuine attempt-2 slots are where a CORA candidate could go. One default
   `[[0]]` was correct in the earlier audit, so these slots are not free.
4. **Licensing.** The checkpoint is Apache-2.0, per the originality audit. Prize eligibility requires open-sourcing.

## 8. Preliminary GO/NO-GO

- **GO** for building the instrumentation: a new `kaggle/cora_qwen_fusion_v1/` builder whose only change is to save
  the candidate pool and scores, verified byte-identical to `neural_v1` otherwise. It is cheap, reversible and
  required by every route.
- **NO-GO for claiming or measuring fusion gains until a measurable cohort is decided.**
  - **Recommended:** a user decision on the public-evaluation DEV 60, after checking NVARC's training-data statement.
  - **Alternative:** a small hidden-set A/B through one official submission. It is costly and only possible after the
    gates.
- **Route priority:**
  1. R3 (selection among NVARC's own candidates, plus CORA candidates for the 147 open slots) is the nearest
     competition lever.
  2. R1 (executable hypotheses grounded on the demonstrations) is the nearest research lever.
  3. R2 needs new supervision and is not a pilot.
- **Timing:** nothing here may delay the 21 October print freeze. Neural runs should wait until Phase 2a has finished.
