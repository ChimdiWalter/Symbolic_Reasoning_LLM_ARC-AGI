# NEURAL_TTT_BASELINE (submission 57160429): originality and licence audit (2026-10-14)

**Upstream.** The submitted notebook is built from the public NVARC Kaggle
notebook `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue`, version 10.
- **Pulled copy:** `kaggle/neural_v1_smoke/upstream/`, sha256 506b85db.
- **Build:** `kaggle/neural_v1/build_full.py` applies asserted exact-string
  patches to it.

## Faithfully reproduced (NVARC's method; not ours)

The following are untouched:
- the Qwen3-4B checkpoint `sorokin/qwen3_4b_grids15_sft139`, pretrained by
  the NVARC team on their synthetic data;
- per-task LoRA test-time training: r = 256, augmentations, schedule;
- the DFS decoding (540 s cap) and the 20-minute per-task cap;
- candidate scoring and selection (`score_kgmon`);
- the 12 h guard (12 × 3600 − 600 s).

## Our changes: compatibility and deployment only

| # | change | kind |
|---|---|---|
| 1 | find the competition and model directories under `/kaggle/input` (the 2026 mount layout) | compatibility |
| 2 | committed run over all visible stand-in tasks, instead of upstream's 4 self-test tasks; no evaluation file opened | coverage |
| 3 | pipeline-health check on the stand-in's training solutions; reported as contaminated, never a score | diagnostics |
| 4 | peak GPU memory logged per worker | diagnostics |
| 5 | a light identity cell: hashes of the small files and the task file, plus shard sizes | provenance |
| 6 | a final cell: schema validation and repair of submission.json, plus `execution_manifest.json` | robustness |

**Outside the notebook,** the coverage audit (`kaggle/neural_v1/audit_run.py`)
does three things:
- separates genuine predictions from defaults and repaired input copies (the
  fallback gate fix, commit 25b346e);
- checks runtime and memory;
- runs the gated single-submission watcher (`kaggle/ops/detached_watch.py`).

**No genuinely new algorithmic change** was made: no new training
objective, no new LoRA or TTT procedure, no new candidate selection.

**Correction to an external summary.** The hand-written chat template was a
local workaround in the earlier CORA-NVG experiment on Athe (a jinja2 version
clash). It is not a change to the submitted notebook.

## Licences (from `records/KAGGLE_NEURAL_V1_LOG_20261013.md` section 7)

- **Model checkpoint:** Apache-2.0.
- **Notebook dependencies:** Apache, LGPL (unmodified) and BSD.
- **NVARC GitHub repository:** no LICENSE file, so no reuse of that
  repository's code is assumed. Only Kaggle-published assets are used.
- **Kaggle notebooks:** the competition rules deem submitted notebooks
  licensed under an OSI-approved licence that does not limit commercial use.
  The specific licence of the upstream public notebook is recorded as
  UNVERIFIED in the API.

Check the competition's open-source and private-sharing rules before
reusing any of this code in a product.

## What the score will and will not show

- **It shows** how a faithfully reproduced, third-party neural TTT pipeline
  performs on the hidden ARC-AGI-2 tasks, deployed and audited by us.
- **It does not show** anything about CORA's diagnosis, construction or
  verification mechanism. It must be labelled NEURAL_TTT_BASELINE (NVARC
  reproduction) wherever it appears.

## Possible later use

The model's outputs could serve CORA as **untrusted hypotheses**: a proposed
output that CORA then tries to explain with a certified executable program,
verified on the demonstrations alone, with fold-local regeneration. This has
not been implemented or tested. The protocol is in
`records/CORA_NEURAL_CANDIDATE_EVIDENCE_PLAN_20261013.md`.

## Result (2026-10-14)

Public score **27.64**, equal to NVARC's own 2025 public score; see section 11.2 of
`records/KAGGLE_NEURAL_V1_LOG_20261013.md`. It is labelled NEURAL_TTT_BASELINE everywhere.
