# Neural-CORA v2: the Qwen joint program adapter. DESIGN ONLY (20 October 2026)

**No training has been run for this design. Nothing here is a result.**

The goal is to use more of the NVARC Qwen3-4B checkpoint's ARC-relevant capacity. That capacity must go into a
**structured, conditional distribution over whole CORA programs** that CORA compiles, executes and checks. It must
not be an independent grid lane, and it must not be a bag of independent component scores (the v1 failure,
`records/NEURAL_CORA_V2_G1_FAILURE_ANALYSIS_20261020.md`).

## 1. What v1 used, and what it discarded

**The checkpoint** (local config): `sorokin/qwen3_4b_grids15_sft139`, Apache-2.0, as checked in the v1 freeze
manifest.
- 36 layers; hidden 2560; MLP 9728; 32 query heads and 8 KV heads; head dimension 128.
- **Vocabulary: 16 tokens** (grid digits and format). It cannot emit program text.
- bf16 weights, 6.8 GB. The local RTX 2080 Ti (Turing) runs it in fp16: a measured 7.51 GB peak for about
  800-token inputs, 0.30 s per task.

**v1 used:** one 12,800-value vector per task. Mean-pooled hidden states (all tokens, output-grid tokens, the last
token, layers 27 and 18) fed a fresh MLP.

**NVARC's own pipeline** (read-only, from the frozen deployment `kaggle/neural_v1/kernel/notebook.ipynb`):
- **per-task test-time training:**
  - Unsloth LoRA, r = 256, alpha 32, dropout 0;
  - on q, k, v, o, gate, up and down projections, plus `embed_tokens` and `lm_head`;
  - one epoch, lr 5e-5 cosine, warmup ratio 0.1, batch 1, sequence length 8192, no 4-bit loading;
  - over augmentations of the task's demonstrations: transposes, rotations and colour permutations (n = 16);
- then a probability-thresholded depth-first decode of output grids;
- then **selection by scores** that combine the decode score with re-scoring under augmentations.

Its strengths are task-local adaptation and grid-likelihood scoring. v1 kept neither. The released NVARC project's
dataset counts (synthetic and augmented puzzles; see the prior-art record) are dataset sizes, not a record of what
this exact checkpoint saw.

**LoRA sizes, computed from the config:**

| configuration | trainable parameters |
|---|---|
| NVARC's r = 256 on all projections | 528.5 M, plus embeddings |
| r = 16, attention only | 11.8 M |
| r = 16, all projections | 33.0 M |

## 2. Stage A: a joint rule adapter over a frozen encoder (the first G1b experiment)

**Inputs (inference-visible only):**
1. **Qwen object slots.** Per-token hidden states from 2–3 layers are pooled over the tokens of each CORA object's
   cells, in each demonstration input and output and the test input. This *binds* Qwen's representation to CORA's
   objects. In the chat format each cell is one token, so the alignment is exact.
2. **Correspondence evidence** (the source of C+H's strength): per matched object pair, the displacement, the recolour
   pair, deletion and addition; plus the 103 v1 hand features.
3. **CORA's candidate rule set** for the task: `cora_neural_v2.search` selectors × actions after the firing filter.
   Each candidate is encoded from its AST: an S-expression token embedding, plus the slots of the objects its
   selector actually selects in each demonstration.

**The model** (about 5–10 M trainable parameters):
- a small transformer (2–4 layers, d = 256) over object slots and evidence tokens;
- a **joint rule scorer**: the score of rule j given the demonstrations, the view and the earlier rules;
- this produces scores for whole (selector, bound action, parameters, slot) rules, conditioned on rule order. It is
  not a product of independent bags.

**Output:** the `rule_scores` hook of `cora_neural_v2.search.enumerate_programs`. A residual on C+H is also tested:
`score = G1-CH(rule) + f_theta(rule)`. CORA still enumerates, executes, checks and selects.

**Training data:** a **v2 generator** of CORA's own execution-verified programs over ncv2-g1, with structural
diversity:
- parts and multicolour objects;
- relational guards and bindings;
- copying, deletion and resizing (crop and constant shape);
- two-stage `seq` sequencing.

The splits are by program *template* and composition, with equivalence classes defined by execution on the
demonstrations and the test input. There are contrastive pairs: identical-looking demonstrations whose test
behaviour differs.

**Loss:** listwise softmax over each task's candidate rules. Positives are the rules of every program that fits
every demonstration, grouped by execution equivalence. Hard negatives come from execution: swapped pairings, wrong
order, near-miss parameters.

**Compute:**
- feature extraction: about 0.3–0.5 s per task on GPU 0;
- cached object slots: about 100 KB per task;
- training: on GPU, under 1 GB, minutes.

**G1b arms:** all use the same candidate set, interpreter, checker and budget, with full GPU and CPU time charged.

| arm | what it is |
|---|---|
| G1-CH | the symbolic, pairing-aware order |
| G1-CH + non-neural residual | logistic regression on the hand and evidence features |
| joint-hand | the same joint model with no Qwen inputs |
| joint-Qwen+hand | the hypothesis |
| Qwen-ablated | slots zeroed |
| shuffled labels | — |
| untrained | — |

**Go rule (to freeze before any run):** joint-Qwen+hand beats G1-CH, G1-CH + residual and joint-hand on held-out
compositional families, with paired tests and harms counted.

## 3. Stage B (PROPOSED, not launched): grammar-constrained Qwen sketch decoding

**Change:** extend the vocabulary with new embedding and `lm_head` rows for ncv2-g1 tokens (about 200 ops and
symbols, about 1 M parameters). Adapt with LoRA r = 16, attention only (11.8 M).

**Decoding:** typed holes, `select → bind → transform → colour → compose`. Only grammar-valid tokens are allowed at
each step: the type checker's signature table defines a deterministic automaton.

**Training:** on execution-verified v2 programs, with execution-generated hard negatives.

**Its output is an AST or search guidance, never trusted code.** CORA compiles, executes and checks it.

**Memory on the local 11 GB card:**

| setting | estimate |
|---|---|
| fp16 base | 6.8 GB |
| LoRA weights and AdamW state | about 0.15 GB |
| activations, sequence about 1,500, gradient checkpointing | about 1–2 GB |
| **total, fp16** | **about 8.5–9 GB (marginal)** |
| total, 4-bit NF4 base (QLoRA; bitsandbytes supports sm75) | about 4–5 GB (feasible) |

NVARC's own r = 256 on every projection plus embeddings (528.5 M parameters plus fp32 optimizer state) **does not
fit** the local card.

## 4. Stage C (PROPOSED): fold-local task adaptation of the adapter, not of Qwen

**What adapts:** a few steps on the task's own demonstrations, under augmentations that commute with CORA programs:
- colour permutations, with constants remapped;
- dihedral transforms, with directions and axes remapped in the program.

**Leave-one-out discipline:** adapt again without the withheld demonstration for each fold. Otherwise the fold check
is labelled neural-assisted.

**A caution:** LoRA that fits *output grids* is not program learning. Stage C adapts the program scorer only.

## 5. Failure modes to test for

- **Qwen slots add nothing beyond hand evidence**, as in v1 where L1h beat L1. The joint-hand arm is the control.
- **Overfitting.** v1's L1 reached its best validation loss at epoch 6. Use early stopping and small heads.
- **Narrow training families.** The generator's diversity audit is a gate before training.
- **The language does not express the real task.** No guide can fix that. G2 comes first
  (`records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md`).

## 6. Licences and data

- The checkpoint is Apache-2.0.
- NVARC's synthetic completion text (licence unresolved; covers the public splits) is **not used**.
- NVARC's notebook code is read for understanding only. Its licence is unverified, and none of it is copied into
  CORA.
- No protected split and no hidden competition output is used.
