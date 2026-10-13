# Kaggle neural track log: NEURAL_TTT_BASELINE (2026-10-13)

**Track A** of the user's directive "Strong second Kaggle submission" of
2026-10-13.
- This reproduces the public NVARC Qwen3-4B test-time-training pipeline. It
  is not CORA, and not capability invention.
- Native_v1 and its pending submission 57144804 are untouched.

## 1. Smoke test (compatibility only; never submitted)

| item | value |
|---|---|
| kernel | `chimdiwalter/nvarc-qwen3-4b-smoke-v1`, version 1, pushed 2026-10-13T14:36:37Z |
| link | https://www.kaggle.com/code/chimdiwalter/nvarc-qwen3-4b-smoke-v1 |
| settings stored by Kaggle (`kernels pull -m`) | private; internet false; GPU; machine_shape NvidiaL4; competition arc-prize-2026-arc-agi-2; kernel source sorokin/pip-install-unsloth-flash-patch; model sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1; docker gcr.io/kaggle-private-byod/python@sha256:320043e1... (the upstream pin) |
| upstream | sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue, version 10 (run 2026-10-10); pulled ipynb sha256 506b85db... |
| our notebook | `kaggle/neural_v1_smoke/kernel/notebook.ipynb` sha256 d10e575c..., built by `kaggle/neural_v1_smoke/build_smoke.py` with asserted exact-string patches |
| GPU quota before launch | 30.00 of 30.00 h (resets 2026-10-17T00:00Z); L4 counts double |

**Patches (compatibility only).** Model, LoRA test-time training, decoding
and selection code are unchanged.
1. **Data path.** The 2026 competition directory is found by locating
   `arc-agi_test_challenges.json` under /kaggle/input.
2. **Self-test tasks.** The first 4 ids of the visible stand-in file. These
   are ARC-AGI-2 training tasks; upstream used 4 evaluation tasks.
3. **Functional check.** Against `arc-agi_training_solutions.json` only.
   NVARC trained on these tasks, so this is contaminated and not a score.
   No evaluation file is opened.
4. **Time cap.** 90 minutes.
5. **Logging.** Per-GPU peak memory.
6. **Identity cell (logging only).** nvidia-smi, the Python version, and the
   size and sha256 of every attached input in `asset_identity.json`.

**Model checkpoint (Kaggle API file list, version 1, created 2025-11-02).**
- Two safetensors shards: 4,996,836,472 and 2,270,397,024 bytes.
- Tokenizer files: vocab.json is 94 bytes, the 16-token grid vocabulary.
- 10 files in all. The content sha256 is recorded at runtime by the identity
  cell.

**Licences.**

| asset | licence |
|---|---|
| model | Apache-2.0 (Kaggle API) |
| unsloth 2025.9.7 | Apache-2.0 |
| unsloth_zoo 2025.9.9 | LGPL-3.0-or-later (used unmodified; the upstream patch edits unsloth's qwen3.py) |
| flash-attn 2.8.2 | BSD |
| numpy 2.2.6, scikit-learn 1.7.2 | BSD |
| the two upstream notebooks | UNVERIFIED (the pages do not render without JavaScript). Kaggle's default notice for public notebooks is Apache 2.0 |
| NVARC GitHub repository | no LICENSE file, so no reuse is assumed. Only Kaggle-published assets are used |

**Attribution** to Sorokin and Puget (NVARC) is required in any write-up.

**Contamination.** The checkpoint saw ARC-AGI-2 training data, and its
evaluation answers were used for validation and checkpoint selection
(`records/CORA_ARC_LEADER_METHOD_AUDIT_20261013.md`, section 4). It is
competition-eligible. No scientific generalization claim may rest on public
splits.

**Status:** QUEUED at 2026-10-13T14:37Z. Poller log:
`outputs/kaggle_deploy/neural_v1_smoke_status.log`.

## 2. Smoke run 1: ERROR, classified as a deployment path defect (2026-10-13)

- **Timeline.** Queued at 14:37Z, running by 14:46Z, ERROR at 14:49Z.
- **Quota.** 0.15 h used. 29.85 h remained.
- **Output.** `outputs/kaggle_deploy/neural_v1_smoke_run1/` (log,
  asset_identity.json, generated modules).

**Established by run 1:**
- 4x NVIDIA L4 GPUs (23,034 MiB each), Python 3.11.13, 48 CPUs (check 2).
- The utility kernel is mounted as a utility script under
  `/kaggle/usr/lib/notebooks/sorokin/pip_install_unsloth_flash_patch/`. Its
  torch and unsloth were the ones imported. Unsloth and Unsloth Zoo loaded
  and patched (check 3, partial: flash attention has not yet been
  exercised).
- The 2026 mount layout is `/kaggle/input/competitions/<slug>/` and
  `/kaggle/input/models/<owner>/<model>/<framework>/<variation>/<version>/`.
  Path discovery found the competition file.
- **The model checkpoint content.** The model directory's files are
  recorded at runtime in `asset_identity.json` under
  `models/sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1/`. Sizes
  equal the Kaggle API list: 4,996,836,472 and 2,270,397,024 bytes.

**Failure.**
- Worker 0: `RuntimeError: Unsloth: No config file found`. The upstream
  hard-codes `model_name="/kaggle/input/qwen3_4b_grids15_sft139/..."`, which
  is not the 2026 mount path. Classification: **wrong asset path
  (deployment)**.
- The final cell then failed with `FileNotFoundError: /kaggle/inference_outputs`.
  That is a consequence: no task ran.

**Deviation from check 11 (no evaluation-solution file opened), caused by
the identity cell.**
- The logging-only cell hashed every file under /kaggle/input. That
  included the competition's `arc-agi_evaluation_solutions.json` (223,838
  bytes) and `arc-agi_evaluation_challenges.json`.
- Their bytes were read only into sha256. They were not parsed, compared,
  displayed or used, and the hashes reveal no answers.
- Strictly, the file was opened. This is recorded as a breach of the
  smoke-test rule.
- **Fixed in version 2:** the identity cell skips any file whose name
  contains "solution" or "evaluation", listing only its size from
  `os.stat`. No solver code ever opened those files.

**Repair for version 2 (deployment only):**
- patch 7: model path by discovery, the directory under /kaggle/input that
  holds `model.safetensors.index.json` and the model name;
- the identity cell restricted as above, and extended to hash the
  utility-script tree (dependency hashes).

The solver algorithm is unchanged.
