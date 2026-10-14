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

## 3. Smoke run 2: COMPLETE, compatibility passed (2026-10-13)

- **Timeline.** Pushed 14:52:13Z; COMPLETE at about 15:50Z.
- **Output.** `outputs/kaggle_deploy/neural_v1_smoke_run2/` (log,
  submission.json, asset_identity.json).
- **Quota.** 1.92 h used in total afterwards; 28.08 h left.

| # | check | result |
|---|---|---|
| 1 | checkpoint loads | yes, on all 4 workers |
| 2 | four L4 GPUs | yes: 4x NVIDIA L4, 23,034 MiB each; unsloth reports 22.034 GB per GPU |
| 3 | unsloth, flash attention | unsloth and unsloth_zoo patched and ran. Flash-attention use is not explicitly logged (UNVERIFIED); speed is as expected |
| 4 | per-task LoRA TTT | ran: per-task 89.2, 112.8, 344.2 and 322.4 s, including TTT and DFS |
| 5 | valid ARC outputs | yes: 0 schema problems; attempt_1 differs from attempt_2 in all 4 |
| 6 | multi-output handling | **NOT EXERCISED** (all 4 tasks have 1 test input), so a probe follows |
| 7 | tokenizer round trip | implicit only: the decoded grids are valid, largest 20x20. **No 30x30 grid exercised**, so a probe follows |
| 8 | GPU memory | peaks 10.39, 9.40, 12.52 and 12.16 GB of 22 GB |
| 9 | output writer | valid submission.json |
| 10 | runtime | measured, see the timeline below |
| 11 | no evaluation file opened | yes. Both evaluation files and the training solutions are listed as not opened by the identity cell. The training solutions were read only by the functional check |
| 12 | no internet | yes (internet disabled) |
| 13 | algorithm unchanged | yes; only the documented patches |
| 14 | licences | model Apache-2.0; dependencies Apache, LGPL (unmodified) and BSD. Notebooks UNVERIFIED (Kaggle default Apache 2.0) |

**Functional check.** 4.0 of 4 training tasks, under both `score_kgmon` and
`score_full_probmul_3`. The model was trained on these tasks, so this is
**not a score**.

**Timeline (log seconds).**
- The identity cell took 43 to 2,479 s, about **40.6 min**. It hashed 44,151
  files, 16.58 GB, at about 7 MB/s on the input mount.
- Setup to the first worker start: 2,488 to 2,630 s.
- The four workers start in sequence about 70 s apart (upstream's
  unsloth-patch lock).
- Tasks end at 2,730 to 3,102 s; selection and output at 3,172 s.
- **The solver needed about 11.5 min** of the 53-min run. The full package
  therefore uses a light identity cell; the full-file sha256 of the
  utility-script tree and of the model shards stands from this run.

## 4. Full package built, and a probe before the expensive committed run

**`kaggle/neural_v1/`** (`build_full.py`).
- Notebook sha256 0111f325...; kernel `chimdiwalter/cora-neural-ttt-baseline-v1`
  (private, internet off, L4, upstream image pin). Label NEURAL_TTT_BASELINE.
- Patches:
  - the 2026 data and model paths;
  - the committed run processes ALL stand-in tasks; the hidden re-run
    processes all tasks;
  - a pipeline-health check on training solutions only;
  - memory logging;
  - a light identity cell;
  - final schema validation and repair, plus execution_manifest.json.
- The 12 h guard, the 20-min per-task cap and the 540-s DFS cap are
  untouched.
- **Not pushed yet.**

**Probe** (the same code with a committed-run filter), version 3 of the
smoke kernel, to exercise checks 6 and 7 before spending about 24 GPU-quota
hours on the 240-task committed run:
- 27a28665: 3 test inputs;
- 12997ef3: 2 test inputs;
- 05a7bcf2 and 09c534e7: 30x30 test inputs.

These are all stand-in (training) tasks.

## 5. Probe (smoke version 3): COMPLETE, checks 6 and 7 passed (2026-10-13)

- **Timeline.** Pushed 15:54:44Z; COMPLETE 16:22Z; notebook 1,431 s. The
  light identity cell takes seconds.
- **Output.** `outputs/kaggle_deploy/neural_v1_smoke_run3_probe/`.
- **Multi-output (check 6).**
  - 27a28665: 3 test inputs gave 3 entries.
  - 12997ef3: 2 test inputs gave 2 entries.
  - Functional check 4.0 of 4 under both selectors (trained-on tasks, not a
    score). So the order of test inputs is preserved.
- **30x30 (check 7).** 05a7bcf2 and 09c534e7 produced valid 30x30 grids.
  - Per-task 1,123.8 and 1,171.2 s, near the upstream 1,200-s cap.
  - Peak memory 17.94 and 15.29 GB of 22 GB.
  - The small tasks took 70.7 and 126.1 s, at 9.92 and 10.68 GB.
- **Whole file.** 0 schema problems over all 240 tasks; 0 repaired.
  execution_manifest.json written (decoded files 112, tasks with outputs 4).
- **Upstream behaviour kept.** When only one distinct candidate exists,
  attempt_2 keeps the default `[[0]]`; 12997ef3 shows this. The
  reproduction keeps the published selector unchanged (directive section
  8).
- **Runtime implication.** Large-grid tasks approach the 20-min cap, so the
  240-task committed run should take about 10-12 h, as NVARC reports. The
  upstream guard (12 h - 600 s) bounds it.

**All 14 compatibility checks are now passed or recorded.** Flash-attention
use is not explicitly logged, and the notebook licences remain UNVERIFIED
(Kaggle default Apache 2.0).

## 6. Full NEURAL_TTT_BASELINE committed run (version 1)

| item | value |
|---|---|
| kernel | `chimdiwalter/cora-neural-ttt-baseline-v1`, version 1, pushed 2026-10-13T16:22:52Z |
| link | https://www.kaggle.com/code/chimdiwalter/cora-neural-ttt-baseline-v1 |
| settings stored by Kaggle | private; internet false; GPU; NvidiaL4; competition arc-prize-2026-arc-agi-2; kernel source sorokin/pip-install-unsloth-flash-patch; model sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1 |
| notebook | `kaggle/neural_v1/kernel/notebook.ipynb` sha256 0111f325... |
| quota before the push | 2.73 h used, 27.27 h left (the probe's use not yet reflected); expected use about 24 h |
| committed run | all 240 stand-in (training) tasks; measures the real runtime |
| status | QUEUED at 16:23Z; poller log `outputs/kaggle_deploy/neural_v1_full_status.log` |

**After completion:**
1. Download the log, submission.json, execution_manifest.json and
   asset_identity_light.json.
2. Verify the schema against the stand-in file.
3. Record the measured runtime, per-task times, timeouts and memory.
4. Then, if every gate passes, submit this version as **NEURAL_TTT_BASELINE**
   under the user's one-entry authorization, at most 1 submission per UTC
   day. The native submission 57144804 is not replaced.

## 7. Licensing gate (2026-10-13)

- **Model** `sorokin/qwen3_4b_grids15_sft139`: Apache-2.0 (Kaggle API).
- **Runtime dependencies are all OSI-approved:**
  - unsloth 2025.9.7: Apache-2.0;
  - unsloth_zoo 2025.9.9: LGPL-3.0-or-later, used unmodified;
  - flash-attn 2.8.2: BSD;
  - torch, numpy, scikit-learn: BSD;
  - transformers: Apache-2.0.
- **Upstream notebooks.** `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue`
  and `sorokin/pip-install-unsloth-flash-patch` are **public** (Kaggle API,
  `is_private: False`). The Kaggle API and SDK expose no licence field for
  notebooks, and the pages need JavaScript, so a page-level notice could not
  be read.
- **The basis is the competition rules** (`outputs/kaggle_deploy/rules_20261012/rules.txt`):
  - section 6b "Public Code Sharing": code shared publicly in Kaggle
    competition notebooks is "deemed ... licensed ... under an Open Source
    Initiative-approved license ... that in no event limits commercial use";
  - section 6c "Use of Open Source": open-source code used to generate a
    submission must be OSI-licensed, which every dependency above is.
- **Verdict: the licensing gate PASSES under the rules.** Residual
  uncertainty: the page-level licence notice is unread.
- **Attribution** to Ivan Sorokin and Jean-Francois Puget (NVARC) is kept
  in the notebook title context, this log, and any write-up.

## 8. Coverage audit tool (`kaggle/neural_v1/audit_run.py`)

- **What it counts:**
  - tasks started, finished, timed out and never started (from the worker
    log);
  - positions with a genuine attempt_1 or attempt_2 (not the default
    `[[0]]`), and default-only positions;
  - identical attempts;
  - schema problems;
  - runtime against 12 h, per-task quantiles, per-rank peak memory.
- **Why.** A valid submission.json is not coverage: upstream fills
  unprocessed positions with `[[0]]`.
- **Self-test on the probe:**
  - 4 of 240 tasks started;
  - 7 of 259 positions with a genuine attempt_1, 2 with a genuine attempt_2;
  - 252 positions default only;
  - schema valid.

## 9. Gate audit before completion (2026-10-13, 19:05Z; commit 25b346e)

The October 23 sprint directive asked for a check that the watcher and the
coverage audit agree on metric names, units and thresholds before any
automatic submission.

**Agreements confirmed:**
- **Field names.** `schema_problems`, `log_span_s`, `tasks_never_started`,
  `positions_default_only` and `positions` are written by the audit and read
  by the watcher with identical names.
- **Units.** `log_span_s` is in seconds: the probe gave 1,446.8 s from log
  event times, against per-task "finished in S s" values of up to 1,171 s.
  The threshold is 11.9 × 3600 s.
- **Task keys.** The "finished KEY" regex yields challenge task IDs, not
  subkeys. The probe's 4 finished tasks gave 236 never started out of 240.
- **Slot check.** The `submission-limits` output format ("Remaining today:
  N") matches the watcher's test.

**Defect found and fixed.** The notebook's repair cell replaces a missing
or invalid attempt with the test input. The audit counted those
input-copies (and missing entries) as genuine predictions. A run whose
submission.json was lost after decoding would therefore have passed every
gate:
- default-only 0;
- never-started 0;
- schema 0.

**Fix.**
- The audit adds:
  - `positions_fallback`: default [[0]], missing, or the repair input-copy
    signature;
  - `positions_genuine`;
  - `repaired_attempts`, from the manifest;
  - `tasks_with_decoded_outputs`, from the manifest's count of decoded
    output files.
- The watcher also blocks when:
  - fallback exceeds 10% of positions;
  - fewer than 90% of tasks have decoded outputs;
  - either field is absent (fail closed).

**Dry run of the patched audit and gates:**

| case | gates |
|---|---|
| real probe | blocks: never-started 236, default 252, fallback 252, decoded 4 |
| lost submission repaired to input copies | blocks: fallback 259 (the old gates passed it) |
| the same without a manifest | blocks: fallback, decoded |
| all genuine | passes |

**Watcher replacement.** The watcher was replaced in place, so only one
copy runs:
- the old PID 3663047 was stopped during its sleep;
- the new PID 3853904 resumed from detached_status.json, with native and C2
  done and neural running.

No gate was relaxed.

## 10. Full committed run: COMPLETE and audited (2026-10-13, 20:56Z)

**Kernel:** `chimdiwalter/cora-neural-ttt-baseline-v1`, version 1.
- Status COMPLETE, first seen at 20:49Z.
- Outputs downloaded by the watcher into
  `outputs/kaggle_deploy/neural_v1_full_run1/`.

**Coverage audit** (`coverage_audit.json`; from the worker log and the
manifest, not from submission.json alone):

| measure | value |
|---|---|
| tasks started / finished / never started | 240 / 240 / 0 |
| tasks with a logged timeout (outputs still emitted) | 1 |
| tasks with decoded output files (manifest) | 240 of 240 (4,090 files) |
| positions | 259 |
| genuine attempt_1 | **259 of 259** |
| genuine attempt_2 | 112 |
| default-only, fallback, repaired | 0, 0, 0 |
| schema problems | 0 |
| runtime (log span) | 15,624 s = **4.34 h** (limit 12 h) |
| per-task time: median, p90, max | 174 s, 518 s, 1,362 s; 6 tasks over 1,000 s |
| peak GPU memory by rank | 17.7, 11.4, 14.5, 11.6 GB (L4 has 24 GB) |

**Why the runtime is 4.3 h, not the 10-12 h feared.** The 4 probe tasks
were slow ones, with a median of 1,124 s. The 240-task median is 174 s.

**The pipeline-health line is not a score.** It reads 229.5 / 240 on the
training stand-in. Those training tasks are contaminated for this model, so
no accuracy may be inferred from them.

**Gates.** All pass except the daily slot:
- the stored metadata has internet off;
- no earlier NEURAL_TTT_BASELINE submission exists;
- today's slot is taken by native (submitted 13:17Z).

The watcher therefore waits (`gates_waiting_for_slot`). It will submit once
after 00:00Z, then record the official score in
`outputs/kaggle_deploy/neural_v1_official_score.json`.

**GPU quota.** The Kaggle CLI does not report the remaining quota.
- This run used 4.34 h on L4×4.
- The quota reset is 2026-10-17.
- The weekly figure must be read on the Kaggle site.

## 11. Official submission (2026-10-14, 00:08Z)

**Submitted** by the detached watcher under the user's one-entry
authorization of 2026-10-13. Every gate passed (section 10), and the daily
slot reopened at 00:00Z.

| field | value |
|---|---|
| submission ID | **57160429** |
| time | 2026-10-14 00:08:23Z (7:08 PM CT, Oct 13) |
| kernel | `chimdiwalter/cora-neural-ttt-baseline-v1`, version 1 |
| description | NEURAL_TTT_BASELINE neural_v1: public NVARC Qwen3-4B TTT pipeline reproduced (sorokin/qwen3_4b_grids15_sft139); not CORA, not FULL_CORA |
| CLI | rc 0, "0 submissions remaining today." |
| status at 00:08:44Z | SubmissionStatus.PENDING; the hidden-set re-run is in progress |

**Submission tally:** lifetime 3 (July 54617562, native 57144804, this one);
today 1 of 1.

The watcher follows the status and writes the official score to
`outputs/kaggle_deploy/neural_v1_official_score.json`.

**Attribution.** Any score here is a NEURAL_TTT_BASELINE result: a
reproduction of a published NVARC-style pipeline. It is not evidence of CORA
capability construction.

### 11.1 Pending check (2026-10-14, 20:05Z: 19 h 57 min after submission)

| item | finding |
|---|---|
| live CLI status | 57160429 `SubmissionStatus.PENDING`, no score, no error |
| watcher | PID 3853904 alive (up 1 day 1 h). It polls every 600 s; its last check was 19:59:59Z. On `COMPLETE` **or** `ERROR` it writes `neural_v1_official_score.json` and logs "neural scored", so an error is caught, not missed |
| notebook guard | cell 0 sets `global_end_time` = notebook start + 12 h − 600 s and passes it to `starter.py --end-time`. The DFS loop exits at 540 s or at the end time; the per-task loop stops a task at 1,200 s or at the end time. The notebook's own loops therefore stop by 11 h 50 min of execution |
| not covered by the guard | a hang outside those loops (installation, model load, a stuck CUDA call, the final cells), an exception, or a platform fault |
| reference timings | the committed run took 4.34 h over 240 tasks; the native v23 submission went from submission (13:17Z) to COMPLETE by the watcher's 18:00Z poll, under 4 h 43 min |

**Reading.**
- Kaggle's 12-hour limit applies to notebook execution, not to the time since submission.
- `PENDING` covers both queued and running.
- A timeout, an exception or a resource-limit violation is reported as `ERROR`, with a category.
- Twenty hours of `PENDING` with no `ERROR` fits a queue delay (the hidden-set rerun needs a GPU machine). It also fits a stall that Kaggle has not reported yet. The two cannot be told apart from the API.
- The guard reduces the timeout risk but does not guarantee scoring.

**Actions.**
- No cancellation and no resubmission: neither would tell us anything, and a resubmission would use a daily slot.
- The watcher is left running.
- If the submission is still `PENDING` at 24 h (2026-10-15 00:08Z), the user posts
  `records/KAGGLE_NEURAL_V1_PENDING_INQUIRY_DRAFT_20261014.md` to the competition discussion.
- If it is `ERROR`, read the error category in the Kaggle UI before spending another submission.
