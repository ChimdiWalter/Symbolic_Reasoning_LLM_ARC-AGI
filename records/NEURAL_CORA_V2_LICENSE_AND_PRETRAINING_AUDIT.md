# Neural-CORA v2: licence, pretraining, contamination and hardware audit (20 October 2026)

**Read-only audit.** No model was trained or run for it. The tokenizer check below ran on CPU with the tokenizer
files only. Sources are in `records/NEURAL_CORA_V2_PRIOR_ART_AND_GAP_20261020.md` (section F) unless a URL is given
here.

## 1. The exact checkpoint

| item | value | how known |
|---|---|---|
| model | `sorokin/qwen3_4b_grids15_sft139` (Kaggle Models) | the NVARC notebook loads it [L14] |
| local copy | `outputs/neural_cora_v0/models/nvarc_qwen3_4b_grids15_sft139_v1/` (11 files) | — |
| local aggregate sha256 | `c380a8be…` | `records/NEURAL_CORA_V1_FREEZE_MANIFEST.json`, group `nvarc_qwen3_4b_checkpoint` |
| licence | Apache 2.0 | Kaggle model API [L15] |
| base model | Qwen3-4B-Thinking-2507, Apache 2.0 | [L17] |
| architecture | 36 layers; hidden 2560; MLP 9728; 32 query heads, 8 KV heads; head dimension 128; bf16 weights, 6.8 GB | local config.json |
| provenance fields on the model page | training data and provenance are **empty** | [L15] |

## 2. The tokenizer and prompt serialization, verified today

The tokenizer was audited because the joint design pools Qwen states per CORA object, which needs exact alignment.

- **The model:** `tokenizers` WordLevel with **no merges**:
  - vocabulary: `0`–`9` (ids 0–9), `Ċ` (newline, 10), `user` (11), `assistant` (12);
  - added specials: `<|endoftext|>` 13, `<|im_start|>` 14, `<|im_end|>` 15;
  - **16 ids in all**.
- The pre-tokenizer isolates every digit (`\p{N}`). No BOS is added, and `tokenizer_config.json` has no chat
  template.
- **The serialization CORA uses** (v1 `prior.task_text`, the same as NVARC's format [L10]): rows of digits joined by
  `\n`, inside `<|im_start|>user\n…<|im_end|>` and `<|im_start|>assistant\n…<|im_end|>` turns.
- **The check:** 300 random multi-grid prompts, grids 1×1 to 30×30, encoded with the checkpoint's own tokenizer.
  Every grid digit is **exactly one token** whose id equals the colour, with character offsets (p, p+1). **0
  misaligned.**

**Consequences:**
1. Per-object pooling is exact: cell (grid g, row r, column c) maps to one token index computable from the offsets.
2. The model is causal. A cell's hidden state sees only the text before it, so early demonstrations never see later
   ones. Design options:
   - pool object slots from the **test input**, which follows every demonstration;
   - or append a second copy of each grid after all demonstrations, a "re-read" segment.
   This must be tested; it is not assumed.
3. The vocabulary cannot express program tokens. Emitting ncv2-g1 needs new embedding and `lm_head` rows (Stage B
   of the adapter design).

## 3. Training data: known vs unknown

| | what | source |
|---|---|---|
| known | NVARC trained on grids_v15: nvarc_training (47,337 puzzles × 24) and nvarc_full (55,886 × 32), plus MINI-ARC, ConceptARC, RE-ARC and **ARC-AGI-2** at 256 samples each; 3,255,481 samples in all | NVARC paper Table 1 [L10]; config [L5] |
| known | the run that bears this name: 1 epoch, 12,716 steps, batch 256 | `run_sft_4b.sh` [L6] |
| inferred, not stated | about one epoch over the 3.2M set (12,716 × 256 ≈ 3,255,296) | arithmetic |
| unknown | the exact examples this checkpoint saw; whether the colour-merging augmentation (C6) built them | no provenance on the model page |
| known | the "103k synthetic / 3.2M augmented" figures are **dataset totals** | README [L2] |

## 4. Contamination

- **ARC-AGI-2 public evaluation (120 tasks):** all 120 seeded NVARC's synthetic descriptions, "'leaked'" in the
  authors' word [L10]. Any Qwen-derived result there is contaminated.
- **ARC-AGI-2 public training (1,000 tasks):** in NVARC's training mix [L10]. **dev60 and every cohort drawn from
  this file are contaminated for Qwen-derived features.** They are also not clean for CORA's symbolic arms, because
  CORA's frozen library and the v23 baseline were built on that file (`records/CORA_REASONING_V2_COHORT_AUDIT_20261019.md`).
- **Clean evidence:**
  - CORA's own generator families, held out by template;
  - genuinely new tasks;
  - the hidden Kaggle set, the only clean real-ARC test.
- NVARC's synthetic completion text is **not used**: its licence is unresolved, and it is contaminated for public
  eval.

## 5. Asset rights

| asset | licence | status |
|---|---|---|
| ARC-AGI-2 data (`arcprize/ARC-AGI-2`) | Apache-2.0 | verified today (GitHub API) |
| checkpoint `qwen3_4b_grids15_sft139` | Apache 2.0 | verified [L15] |
| Qwen3-4B-Thinking-2507 | Apache 2.0 | verified [L17] |
| NVARC repository code | **none** (`license: null`, no LICENSE file) | verified [L11, L12]; read for understanding only |
| NVARC Kaggle notebook and datasets | **unknown** | NOT VERIFIED [L14, L16] |
| local Python stack | torch 2.11.0 (BSD-3-Clause); transformers 4.57.0 (Apache 2.0); accelerate 1.13.0 (Apache) | package metadata, today |
| peft, bitsandbytes, unsloth | **not installed** in `~/.venvs/lesegenv` | checked today |
| CORA code | the author's; ARC Prize 2026: "All code and methods must be open sourced to be eligible for prizes" | arcprize.org/competitions/2026/arc-agi-2, today |

## 6. Competition facts relevant to feasibility

| fact | source |
|---|---|
| exactly 2 predicted outputs per test input; a task scores 1 if either matches; the score averages over test outputs | arcprize.org ARC-AGI-2 page, fetched today |
| no internet during evaluation | the same page |
| hardware and compute limits "will be announced with the competition launch" | the arcprize.org page (not updated) |
| **L4x4 machines, 96 GB of GPU memory, for this competition**; quota at twice the T4x2/P100 rate; internet disabled; restricted to competition notebooks | the Kaggle "Upgraded Accelerators" rules page, fetched 2026-10-12 (`outputs/kaggle_deploy/rules_20261012/Upgraded_Accelerators.txt`). **Correction (20 Oct): an earlier version of this audit said the 2026 hardware was unannounced** |
| CPU notebook ≤ 12 h; GPU notebook ≤ 12 h; pre-trained models allowed; `submission.json` | the Kaggle rules pages, fetched 2026-10-12 (`records/KAGGLE_NATIVE_V1_DEPLOYMENT_LOG_20261012.md` §7) |
| code deadline 2026-11-02 23:59 | Kaggle CLI listing, today |
| paper track deadline 2026-11-09 23:59 (arcprize.org says papers are due 8 November; plan for the 8th) | the same |
| 1 submission per day; 2 final selections | the deployment log |

## 7. Hardware feasibility on Athe

**What the machine has:**
- 2 × RTX 2080 Ti, 11 GB each, compute capability 7.5.
- GPU 1 belongs to another user and is not used.
- **bf16 is not natively supported** on compute 7.5, so use fp16.

**Measured in v1:** fp16 inference peaks at 7.51 GB for prompts of about 800 tokens, at 0.30 s per task.

**Estimated, not measured** (`records/NEURAL_CORA_V2_QWEN_JOINT_PROGRAM_ADAPTER_DESIGN.md` §3):
- LoRA r = 16 on attention, fp16 base: about 8.5–9 GB. Marginal.
- 4-bit NF4 base: about 4–5 GB. It needs **bitsandbytes and peft, which are not installed**. Install them in a
  separate venv rather than altering `lesegenv`.
- NVARC's r = 256 setup on every projection does not fit.

**Proposed bounded smoke test** (not run; not for 20–21 October, per the addendum's schedule):
- load NF4 on GPU 0;
- one forward pass and 3 LoRA steps on 2 synthetic tasks;
- record peak memory and step time;
- about 10 minutes.

**On Kaggle:** L4x4 (Ada, bf16-capable, 96 GB in total) is available to this competition (the saved rules page above). Usable capacity must still be checked inside an actual notebook.
