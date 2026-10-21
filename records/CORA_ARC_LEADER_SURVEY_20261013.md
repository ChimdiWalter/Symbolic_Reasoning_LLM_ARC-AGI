# ARC-AGI-2 leaders survey (2026-10-13), the appendix to records/CORA_ARC_LEADER_METHOD_AUDIT_20261013.md

**Provenance.** A delegated web review compiled this on 2026-10-13. It used WebSearch, WebFetch, read-only raw GitHub, the GitHub API and the Kaggle API; every source is listed with its date in section E.

**Independently re-verified before commit:** the NVARC contamination lines, re-fetched at repository HEAD 846d0198efa7 (2025-12-13):
- `SDG/scripts/build_datasets.py` (sha256 f683f8b5...): L157 `pairs = data["train"] + data["test"]`; L249-250 build `arc2_evaluation6` from `external/ARC-AGI-2/data/evaluation/*.json`;
- `ARChitects/sft_mg.yaml` (34abec38...): the training sets are arc2_training, mini, concept, rearc, nvarc_training and nvarc_full; `val_dataset_path: data/grids_v15/arc2_evaluation6`; `metric_name: val_loss`, `keep_top_k: 3`;
- `ARChitects/run_sft_4b.sh` (f707a4e6...): `EXP_NAME="qwen3_4b_grids15_sft139"`, `sft.max_num_steps=12716`, `sft.val_period=200`.

The rest is the review as delivered.

---


Snapshot: 2026-10-13. Based on web sources only. Every source is listed in section E with its date.

Evidence labels:
- **DOC**: the exact method behind that entry is publicly disclosed.
- **REL**: a method the same team showed elsewhere (another benchmark or year). It is never evidence for the leaderboard score.
- **INF**: a plausible explanation with no direct evidence.
- **UNK**: nothing public.
- **UNVERIFIED**: I could not open or confirm the source.

## 0. Bottom line

- **No 2026 top-10 team has published its ARC-AGI-2 method.** I searched for every name on the board. The rules say prize artifacts must be attached to a Solution Writeup within seven days of the 2 Nov deadline [S2], so methods should appear around 9 Nov.
- **The best documented Kaggle-eligible system is still NVARC (2025).** It scored 27.64 on the public board, 24.03 private, and 29.72 public after the deadline [S3, S5]. Public 2026 forks of its released Qwen3-4B score about 29 to 34 on the public board [S20].
- **The public board is the semi-private half (120 tasks); the private half decides the ranking** [S5, S16]. ARC Prize says the semi-private set "carr[ies] some risk of leakage" [S4]. In 2025, scores dropped by 2.8 to 5.4 points from public to private: NVARC 27.64→24.03, ARChitects 21.67→16.53, MindsAI 15.42→12.64, Barbadillo 11.94→6.53.
- **The field moved very fast.** At an audit dated 2026-09-09 the top three scores were 76.67, 72.08 and 40.83 [S20]. By 13 Oct about 30 teams were above 40. Spread that fast suggests a shared public trigger in September or October, such as a notebook, model or dataset (INF; I did not find it).
- **Symbolic and induction-only systems score about 0 on ARC-AGI-2.** Every independent report I found agrees (section C), which matches CORA's 0.00.

## A. Teams and methods

### A1. 2026 leaderboard (public board, scores as supplied)

| # | Team | Score | Public ARC-AGI-2 method | Closest evidence | Label |
|---|---|---|---|---|---|
| 1 | Tufa Labs | 88.06 | None. Tufa's research and news pages never mention ARC-AGI-2 [S9, S10] | **ARC-AGI-3 "Duck"**: a local Qwen 3.6 27B FP8 writes and runs Python in a REPL, sees grids as image plus text, and evicts old context [S11, S15]. Tufa found "hand-crafted tools actually hurt the model" [S12]. **2025 ARC-AGI-2 entry** (as MindsAI & Tufa Labs): CodeT5-660M with TTT and AIRV, 12.64 private [S3, S8] | ARC-AGI-2: **UNK**; Duck and 2025 entry: **REL** |
| 2 | rabbithole | 80.56 | none found | — | UNK |
| 3 | Yi-Chia Chen | 77.22 | none found | Also 2nd on ARC-AGI-3 (48.59) [S13] | UNK |
| 4 | nvbanana | 77.08 | none found | A link to NVIDIA/NVARC is a guess from the name only | UNK (affiliation INF) |
| 5–10 | _hans 69.03, ALbert RUehlman 67.36, Dawid Kopiczko 66.25, Domdolus Tolus 65.14, ARC Raiders 64.58, Majkel1337 62.08 | | none found | — | UNK |
| 31 | Jack Cole | 38.61 | none found | 2025 MindsAI writeup; he now works independently [S8]. Listed as adviser/reviewer to Tufa's ARC-AGI-3 team [S51] | REL |
| — | Public 2026 notebooks | 29–34 | yes (code) | Forks of the NVARC Qwen3-4B pipeline: 31.39, 31.11 and 29.03 [S20]. Best public score with the sft139 model: 33.89 (search snippet, UNVERIFIED) | DOC |

**Tufa's two results are separate.**
- **ARC-AGI-3 (documented):** the Duck harness. On Kaggle, ARC-AGI-3 evaluation is "constrained to a single GPU" [S11].
- **ARC-AGI-2 88.06 (undocumented):** no method is public. I found no statement that ARC-AGI-2 details will follow the deadline. The closest is "We will continue to work on the problem until the end of the competition", which is about ARC-AGI-3 [S11].

**Unconfirmed bonus claim.** An ARC Prize X post reportedly says the $150K bonus will be split among all teams over 85%. I could not open it (HTTP 402; UNVERIFIED; ToolNavs repeats it [S14]). The official track page says instead that the bonus goes to "the first eligible solution that scores at least 85% on the private evaluation set" [S2].

### A2. Documented systems and method families

| System (date) | Approach | Model | Data | TTT | Search, then the 2 attempts | Score (benchmark, split) | Compute | Label / source |
|---|---|---|---|---|---|---|---|---|
| NVARC 2025 | Transductive LLM over grid text, trained on synthetic data | Qwen3-4B-Thinking-2507, cut to 16 tokens | 103,253 LLM-generated puzzles, plus RE-ARC, ConceptARC, MINI-ARC and ARC-AGI-2 training: 3.26M samples | Per-task LoRA | Batch DFS, then rescoring over 8 augmentations; top-2 | ARC-AGI-2 Kaggle: 24.03 private, 27.64 public, 29.72 public post-deadline | 4×L4, 12 h; offline SFT on 4×8 H100 for 27 h | DOC [S5, S6, S18] |
| ARChitects 2025 | 2D-aware masked diffusion with recursive soft-mask refinement | LLaDA-8B, 4-bit file | RE-ARC, ARC-GEN-100K, ARC-AGI-1/2 training **and evaluation**, ARC-Heavy, ConceptARC | LoRA, 128 steps | 102 refinement steps; two most-visited states | 16.53 private, 21.67 public | 4×L4; pretraining 39 h on 8×H100 | DOC [S3, S7, S22] |
| ARChitects 2024 | Autoregressive LLM with TTT, DFS and Product-of-Experts | Mistral-NeMo-Minitron-8B, 4-bit + LoRA | RE-ARC only | LoRA r=32, 64 steps, ~51 s/task on a 4090 | DFS at T=9% (~9.3 candidates); PoE over 16 augmentations; top-2 | ARC-AGI-1: 71.6% public eval; 53.5 Kaggle 2024 private | 1×P100, 12 h (2024 rules) | DOC [S28, S29] |
| MindsAI & Tufa 2025 | TTT + AIRV + self-ensemble + BPE dropout | CodeT5 660M (decoder pruned 24→16), 2 checkpoints | 100M+ examples (ARC-AGI Mega), Reasoning Gym, 27 ARC-2-style generators | Full fine-tune on the whole test set (~45K examples) | Beam search; AIRV board-level vote over 10K augmented tasks | 12.64 private; writeup "final score" 15.42 | TPUs for up to 2.5 years | DOC [S8]. Authors: ARC-AGI-2 is "somewhat adversarial" to this paradigm |
| Barbadillo 2025 | ARChitects-2024 TTT; induction "search-and-learn" | ARChitects ARC24 model; BARC Llama-8B | — | Per task | — | 11.94 public, 6.53 private. Induction "does not yet solve any" private ARC-AGI-2 task; BARC induction model 0.8% on ARC-AGI-2 eval | 4 GPUs | DOC [S3, S31] |
| TRM | Tiny recursive latent refinement | 7M parameters plus a per-puzzle embedding table | ARC-1/2 + ConceptARC, 1,000 augmentations | NVARC: pretrain, then fine-tune on test demonstrations for ~2 h | NVARC: changed to emit 10 attempts, rescored by Qwen | ARC-AGI-2: 8% (paper); McGovern 6.67 semi-private; NVARC version 7.5→10.0 public | 3 days on 4 H100 (default) | DOC [S5, S34, S35] |
| HRM | Hierarchical recurrent; purely transductive | 27M | ARC tasks with puzzle-id embeddings | Trains on evaluation-time tasks | Outer-loop refinement | ARC-AGI-2: 2% semi-private (ARC Prize verified) | 12.6 h, $1.68/task | DOC [S36] |
| CompressARC | MDL/VAE per puzzle, no pretraining | 76K parameters | None | The whole method is per-task training | Most frequent sample | ARC-AGI-2: ~4%; ARC-AGI-1 eval 20% | ~20 min/puzzle on an RTX 4070 | DOC [S4, S37] |
| VARC | ARC as image-to-image (ViT) | 18M ViT (+55M U-Net) | ARC-1 training + RE-ARC only | 100 epochs, ~70 s/task on one GPU | 510 views; the two most-populated outputs | ARC-AGI-2: 8.3 single, 11.1 ensemble | ~5 h on 8 GPUs offline | DOC [S38, S39] |
| Akyürek TTT | TTT of an LLM | 8B | — | Per-task fine-tuning on the demonstrations | — | ARC-AGI-1: 53.0% public eval; 61.9% with program synthesis | — | DOC [S32] |
| Li et al. (BARC) | Induction vs transduction | Llama-8B (the BARC induction model, per [S31]) | Synthetic variants of Python programs | — | Ensemble | ARC-AGI-1; induction and transduction solve different tasks | — | DOC [S33] |
| SOAR | LLM evolution plus fine-tuning on its own search traces | Open LLMs | Self-generated | Hindsight fine-tuning | Evolutionary | ARC-AGI-1: 52% public test; no ARC-AGI-2 number | — | DOC [S3] (paper itself not opened) |
| Greenblatt | Sample thousands of programs | GPT-4o | — | — | ~5–8K programs/task, revision, majority vote | ARC-AGI-1: 50% top-3, 48% top-2 | Very high | DOC [S40]; not Kaggle-eligible |
| Berman | Evolving natural-language programs | Grok-4 | — | — | ≤40 candidates/task | ARC-AGI-2: 29.4% | $8.42/task (ARC-AGI-1) | DOC [S41]; API |
| Poetiq | Meta-system refinement | Gemini 3 Pro | — | — | Consensus | ARC-AGI-2: 54% semi-private | $30.57/task | DOC [S42]; API |
| Land | Text/image/code candidates plus a holistic judge | Frontier API LLMs | — | — | ≤29 candidates; LLM judge picks top-2 | ARC-AGI-2: 72.9% semi-private, 76.1% public | $38.99/task | DOC [S43]; API |
| Imbue | Code evolution | Kimi K2.5 (open weights) / Gemini | — | — | Fitness; two best distinct outputs | ARC-AGI-2 public eval: 34.0% (Kimi), 95.1% (Gemini 3.1 Pro) | $2.67–8.71/task | DOC [S44]; API |
| ABPR | LLM + Prolog meta-interpreter with algorithmic debugging | Gemini-3-Flash / GPT-5.5 | — | — | Trace-guided refinement | ARC-AGI-2 public eval, pass@2: 56.67 / 98.33 | — | DOC [S45]; API |
| DeepSeek V4 Flash 0731 | Open-weight reasoning model | 304B, MIT licence | — | — | — | ARC-AGI-2: 61.4% semi-private | $0.04/task | DOC [S46, S47]. At FP8 it needs ~304 GB, far beyond 96 GB (INF) |

**ARC Prize statements:**
- Test-time training "is responsible for the top scores in both ARC Prize 2024 … and 2025" [S4].
- 2025's defining theme was the per-task "refinement loop" [S4].
- Frontier reasoning remains "constrained to knowledge coverage", with ARC-AGI-1/2 overfitting happening "accidentally or intentionally" [S4].
- On ARC-AGI-3, most approaches use a vision-language model with reflection memory [S12].
- ARC Prize has published no 2026 statement on ARC-AGI-2 methods; its blog has no ARC-AGI-2 posts in 2026 [S52].

### A3. NVARC and ARChitects 2025 in detail (DOC)

| | NVARC [S5, S6, S18] | ARChitects 2025 [S7, S22, S23] |
|---|---|---|
| Base model | Qwen3-4B-Thinking-2507, embeddings cut to 16 tokens; full SFT with NeMo-RL/Megatron, 1 epoch of 12,716 steps × 256 | LLaDA-8B-Base with 2D RoPE and a 32×32 pad; rank-512 LoRA for 175K steps; Kaggle file is 4-bit, 3.6 GB, MIT |
| Synthetic data | H-ARC and BARC descriptions → 3,268 summaries (commercial language models, gpt-oss-120b) → 266,593 mixed summaries → 126,901 input programs (unit-tested, ≥30 grids) → 103,253 puzzles whose output programs agree (e.g. 15 of 20) | 150 Qwen-Coder "game" tasks were tried and not used |
| TTT | Per task: LoRA r=256, α=32, rsLoRA on q/k/v/o/gate/up/down + embed + lm_head; lr 5e-5, cosine, 1 epoch, batch 1, 8,192 tokens; ~128 augmented copies, so about 128 steps (INF) | Per task: 128 steps, batch 1, r=32 per the page (r=64 in the Kaggle copy) |
| Augmentation | D8 × 16 colour permutations, with example order shuffled | Random D8, colour and example order at every step |
| Sampling and scoring | "Turbo" DFS with max NLL = −ln 0.2, 16 views per test input, 9-min cap; NLL rescoring under 8 shared augmentations | Soft-mask recursive sampling |
| Output shape | Implicit: the model emits newline and EOS tokens | Separate LLaDA shape model with 8-augmentation PoE, ~85%±2% accurate |
| Iterative refinement | None | 102 steps, as 2×51 with a cold restart (the copy shows 2×71) |
| The 2 attempts | `score_kgmon` = number of times the candidate was found + mean augmented log-probability; top-2 distinct | The two most-visited states |
| Kaggle runtime and memory | 4 workers, one per 24 GB L4; bf16, no 4-bit, no gradient checkpointing; 11h50 guard; 20 min per task; peak memory not reported | 4 workers; 12 h guard; AdamW8bit; memory not reported |
| Official score | 24.03 private (2025) | 16.53 private (2025) |

### A4. NVARC contamination audit (repository `1ytic/NVARC`, HEAD `846d0198efa7`, 2025-12-13)

**What the code does.** ARC-AGI-2 evaluation JSON files include the test outputs: in `arcprize/ARC-AGI-2@f3283f7`, `0934a4d8.json` has test keys `input` and `output` [S53]. Quoted from `SDG/scripts/build_datasets.py`:
- L144 `def convert_arc_to_messages(path_mask: str, num_samples: int = 256, seed: int = 42):`
- L157 `pairs = data["train"] + data["test"]`, so **the evaluation TEST outputs are included**.
- L249 `ds = convert_arc_to_messages("external/ARC-AGI-2/data/evaluation/*.json", num_samples=6)`
- L250 `ds.save_to_disk(f"{output_path}/arc2_evaluation6")`
- L269 and L273 build `nvarc_training` and `nvarc_full`.

**Was that data used to train the released checkpoint?** `ARChitects/run_sft_4b.sh` has:
- L9 `EXP_NAME="qwen3_4b_grids15_sft139"`, the same name as the Kaggle model;
- L11 `--config ./configs/sft_mg.yaml` (the repo ships `ARChitects/sft_mg.yaml`; that they are the same file is UNVERIFIED);
- L18 `max_num_steps=12716` and L21 base `/models/Qwen3-4B-Thinking-2507-16t`.

`ARChitects/sft_mg.yaml` L120–126 lists the training data as arc2_training, mini, concept, rearc, nvarc_training and nvarc_full. L127 sets `val_dataset_path: data/grids_v15/arc2_evaluation6`. L14–16 sets `metric_name: "val_loss"`, `keep_top_k: 3`.

12,716 × 256 = 3,255,296, which is about one epoch over the six subsets in the paper's Table 1 (3,255,481 samples). That table excludes the evaluation set.

So:
1. The evaluation test outputs were used for **validation and checkpoint ranking, not gradient training** (DOC). Whether the released step was chosen by val_loss is UNVERIFIED.
2. **nvarc_full** "uses both training and evaluation puzzles from ARC-AGI-2". The authors say they "'leaked' the descriptions of these puzzles": 29 hand-written plus 91 LLM-written summaries cover all 120 evaluation tasks [S5].
3. Whether the summary prompts showed test outputs is UNVERIFIED: the `{PUZZLE}` placeholder in `summary_v2.md` is not resolved in the repo.

**Verdicts:**
- **(a) Competition-eligible: yes.** It is a public Kaggle model under Apache 2.0, and nothing shows that hidden tasks were used.
- **(b) Clean for scientific evaluation on ARC-AGI-2 public eval: no.** The evaluation puzzles leaked at concept level and drove model selection. Do not report sft139 public-eval scores as generalization. The ARChitects 2025 model is also unclean, since it trained on ARC-2 evaluation [S7].
- **Clean neural options:**
  - VARC, trained only on ARC-1 training + RE-ARC, MIT [S38, S39];
  - CompressARC, no pretraining [S37];
  - mindware/arc-codet5-660m, which the writeup says did not use ARC-AGI-2 evaluation [S8]. Its model card does not confirm this [S48].

**Licences and lineage:**
- Repository: no LICENSE file; the GitHub API reports `license: None`.
- Model `sorokin/qwen3_4b_grids15_sft139`: Apache 2.0; Transformers, bfloat16, version 1 (id 627758); 7,267,271,302 bytes; updated 2025-11-02 [S17].
- 2B variant `sft141`: Apache 2.0, 2.82 GB [S24].
- NVARC Synthetic Puzzles dataset: licence "Unknown", 5.79 GB [S25].
- Lineage: Qwen3-4B-Thinking-2507 → 16-token cut → full SFT (4×8 H100, 27 h) → sft139 → per-task LoRA TTT on Kaggle.

### A5. How the L4x4 budget (4×24 GB, 12 h) is used

| System | What runs where | Model size and precision | Time per task |
|---|---|---|---|
| NVARC | 4 independent workers, one task per GPU | 4B bf16; quantization removed | 12 h for 240 tasks; a 10-h variant scored 27.22. That averages about 12 GPU-min per task, with caps of 20 min to decode and 9 min of DFS |
| ARChitects 2025 | 4 workers | 8B at 4-bit plus a shape model | — |
| MindsAI | FSDP; TTT on the whole test set at once | 660M full fine-tune | — |
| 2026 fork | NVARC on GPUs 0–2, TRM training on GPU 3, then a 4th NVARC worker | — | Tasks sorted cheapest first by a work estimate [S21] |
| NVIDIA's view | — | — | Chain-of-thought, tool use and RL agents did not fit the runtime [S26] |

- **Model sizes on Kaggle are small:** 4B in bf16, or 8B at 4-bit. A Qwen3.8-27B FP8 repack lists a best public score of only 1.67 (search snippet, UNVERIFIED).
- **TTT steps:** about 64 to 128 per task.
- **Quota:** a development run on L4x4 uses GPU quota at twice the T4x2 rate [S49].

## B. The common recipe behind scores above 40

**Established**, but only documented up to about 30 public / 24 private:
1. **A transductive grid model:** 2B–8B LLM, or a 660M encoder-decoder, reading grids through a tiny tokenizer.
2. **Large offline pretraining on augmented ARC-like data.** The decisive lever was synthetic puzzles generated by LLMs and checked by execution and agreement. NVARC: "Scaling the pretraining stage with good synthetic puzzles was the right direction" [S5].
3. **Per-task TTT** with high-rank LoRA, or full fine-tuning on the test set.
4. **D8 × colour × example-order augmentation** in every phase: training, TTT, decoding and scoring.
5. **About 10 candidates per test input**, from DFS, beam search or diffusion refinement.
6. **Selection by agreement across augmentations:** PoE or log-probability plus frequency, visit counts, or AIRV votes. The top-2 distinct outputs are submitted.
7. **The budget is spread over 4 GPUs working independently**, about 12 GPU-min per task.

Each part has measured gains. On ARC-AGI-1, the ARChitects went from 18.3% with no TTT, to 44.5% with TTT, to 71.6% with augmentation, PoE and DFS [S28].

**Inferred**, with no public evidence for 77–88:
- The leaders may extend this recipe: more synthetic data aimed at ARC-AGI-2, stronger or larger small models, faster TTT and decoding, better selection.
- They may add local code-writing LLMs that are checked by running on the demonstrations. Tufa's ARC-AGI-3 Duck is the REL precedent.
- Public-board scores sit on a semi-private set with known leakage risk. Expect lower private scores.

## C. Gap analysis vs CORA

| Dimension | Leaders (DOC) | CORA | Consequence |
|---|---|---|---|
| Prior knowledge | 10^5–10^8 ARC-like examples compressed into weights | Hand-built typed DSL with 7 views | Missing the documented main lever |
| Test-time adaptation | Weights adapted per task (TTT) | Program search plus capability construction | Not comparable: CORA adapts symbols, the leaders adapt weights |
| Coverage on ARC-AGI-2 | 24–34 documented | 0.00 | Matches every symbolic baseline: OpenKaggle's leave-one-out-admitted symbolic portfolio produced **0 of 172** outputs and a 29-primitive DSL **0 of 167** [S20]; Barbadillo's induction 0 private, BARC 0.8% [S31] |
| Answering policy | Always fills both attempts | Certifies or abstains | High precision but no recall |
| Verification | Soft agreement across augmentations | Strict leave-one-out on programs | CORA is stronger on verification, which is where the field is weak: NVARC's correct TRM candidates were "not always picked" [S5]; Land's judge recovered 7 more instances than majority vote [S43] |
| Hardware | 4×L4 | CPU only | Rules out every documented scoring method |

## D1. Raising the Kaggle score before 2026-11-02 (ranked)

**Constraints:** one submission per day, so at most about 20 remain. The entry and team-merger deadline is 26 Oct [S20, S49].

1. **Run the NVARC public pipeline as CORA's neural expert.**
   - Expected impact: +29 to +34 public, about +24 to +30 private (INF from 2025 drops).
   - Evidence: [S5, S18, S20].
   - Effort: 2–5 days. Risk: medium-low; the main dangers are dependency drift and timeouts.
   - Falsified if: a clean rerun scores below 29 or takes longer than 11.5 h.
   - Compute: needs L4x4. An 11 GB GPU cannot run 4B bf16 with r=256 LoRA, no gradient checkpointing and 8K tokens (INF). Use it only for smoke tests with `sft141` (2.82 GB). This is probably the paper's 2B model, which scored 22.22 public in 6h10 [S5, S24] (match UNVERIFIED).
2. **Engineer for throughput.**
   - What: order tasks cheapest first, enforce per-task caps, write a fallback submission.
   - Expected impact: 0 to +3.
   - Evidence: the 2026 forks differ by about that much [S20, S21].
   - Effort: 1–2 days. Risk: low.
   - Falsified if: the change is within NVARC's 1–2 point run-to-run variation [S5].
   - Compute: L4x4 only, so each test costs a full 12-h run.
3. **Use CORA as an abstaining override, in attempt 2 only.**
   - When: CORA has a leave-one-out-certified program that is consistent across D8 and colour transforms and disagrees with both neural attempts.
   - Expected impact: 0 to +1 task. Risk: very low.
   - Falsified if: an override is wrong on held-out data.
   - Compute: CPU, in parallel with the GPUs.
4. **Not recommended for score:**
   - A TRM ensemble: 27.22 vs 27.22 at 4B [S5]. The fork's "40.0419%" is a projection, not a score [S21].
   - Plain 27B LLM inference: a Qwen3.8-27B FP8 repack lists a best public score of 1.67 (UNVERIFIED).

**Reproduction plan (the one baseline to reproduce first): NVARC Qwen3-4B, notebook `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue`, version 10.** It is the most reproducible because it:
- has the highest documented Kaggle ARC-AGI-2 score with public weights;
- was run on 2026-10-10, and the model has 104 users (UNVERIFIED);
- has independent 2026 forks scoring 29–34;
- uses a simple 4-worker queue;
- has Apache-2.0 weights;
- includes a built-in self-test on 4 tasks.

What it needs:
- **Assets:**
  - model `sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1` (7.27 GB);
  - utility script `sorokin/pip-install-unsloth-flash-patch`, version 2;
  - competition data `arc-prize-2026-arc-agi-2`. The original attaches `arc-prize-2025`, so the source must be switched.
- **Offline dependencies:**
  - unsloth 2025.9.7 and unsloth_zoo 2025.9.9;
  - the flash-attn wheel `2.8.2+cu128torch2.8-cp311`;
  - numpy 2.2.6 and scikit-learn 1.7.2;
  - a patch to `unsloth/models/qwen3.py`.

  These are installed into `/kaggle/working` with internet on, then attached as a kernel source [S19].
- **Tokenizer:** Qwen3 cut to 16 tokens: digits 0–9, newline, `user`/`assistant`, `<|im_start|>`, `<|im_end|>`, and `<|endoftext|>` as padding [S5]. The files are in `ARChitects/qwen3_configs/`. DFS only allows digits, newline (id 10) and EOS (id 15) [S18].
- **Expected runtime:** 10–12 h for 240 tasks (259 outputs), about 12 GPU-min per task [S5, S18].

Minimal smoke test:
1. The flash-attn wheel matches the 2026 Kaggle image (torch/CUDA/Python), and the patch applies cleanly.
2. The model loads on all four L4s, the vocabulary is 16 tokens, and a 30×30 grid round-trips through encode and decode.
3. Self-test mode on `0934a4d8`, `36a08778`, `981571dc` and `aa4ec2a5` completes. This checks function only, because these evaluation tasks are contaminated.
4. Log seconds for TTT, DFS and rescoring per task, plus `max_memory_allocated` per GPU, then extrapolate to under 11.5 h.
5. Validate `submission.json`: every task and test index present, two attempts each, rectangular 1–30, values 0–9. Include a writer that runs if a worker crashes.
6. The `KAGGLE_IS_COMPETITION_RERUN` path loads the test file.

## D2. Additions that strengthen the thesis (ranked)

1. **Verifier-selector over neural candidates.**
   - What: take the neural top-k and rank it with independent certificates:
     - (i) "transduction-guided induction": CORA searches for a program that maps the demonstrations and maps the test input to the candidate, then certifies it by leave-one-out;
     - (ii) consistency across D8 and colour transforms;
     - (iii) a neural leave-one-out, where TTT runs on n−1 demonstrations and must predict the held-out one.
   - Expected impact: +0 to +2 points on Kaggle. More importantly, a measurable gain in precision.
   - Evidence: selection is the documented bottleneck [S5, S43]; PoE alone moved ARC-AGI-1 from 62.5% to 67.6% [S28].
   - Falsified if: on a clean split, CORA-reranked pass@2 is no better than `score_kgmon` at equal compute.
   - Compute: VARC-18M runs locally on 11 GB (clean). NVARC is for Kaggle only, and its 12 h are already used up, so CORA's checks must run on the CPU at the same time.
2. **Neural candidates as failure evidence.**
   - What: a candidate that is stable across augmentations becomes a target. Diff it against CORA's nearest program output to localize the missing capability (object, relation, view). Build that capability, then verify it on leave-one-out and fresh generated instances.
   - Evidence:
     - induction and transduction solve complementary tasks [S33];
     - hindsight relabelling raised ARC-AGI-1 from 23.3% to 28.3% [S31];
     - SOAR's self-improvement [S3];
     - ABPR's algorithmic debugging reached 56.67% on ARC-AGI-2 with a strong proposer [S45].
   - Falsified if: acquired capabilities do not raise certified coverage on held-out tasks that were not used to acquire them.
   - Compute: CPU plus the 11 GB GPU.
3. **Mine NVARC's 103K executable puzzle programs as a library of capabilities and as a curriculum.**
   - Each puzzle has a tested input program plus several output programs that agree [S5].
   - Use nvarc_training only, because nvarc_full encodes the evaluation tasks.
   - Expected impact: more certified coverage, not points on Kaggle before the deadline.
   - Evidence: synthetic-data scale was NVARC's decisive lever [S5].
   - Risk: the dataset's licence is "Unknown" [S25].
   - Falsified if: retrieval does not add certified tasks on a clean evaluation.
   - Compute: CPU, 5.8 GB.
4. **Learned view ranking with I-JEPA** for the four-view cap.
   - Expected impact: a small, cheap rise in coverage within the fixed search budget.
   - Evidence: CORA's internal result, plus the visual priors VARC demonstrates [S38].
   - Falsified if: there is no gain over the fixed order at an equal budget.
   - Compute: 11 GB GPU.

**Venue.** The Paper Prize requires a linked Kaggle submission. It scores Accuracy, Universality, Progress, Theory, Completeness and Novelty, and papers are due 8 Nov [S1, S50] (9 Nov on the Kaggle page, per [S20]). A D1 baseline plus D2 results fits that rubric.

## E. URLs opened (date; reached by WebFetch, or by raw GitHub or the Kaggle API where noted)

- S1 https://arcprize.org/competitions/2026 (undated)
- S2 https://arcprize.org/competitions/2026/arc-agi-2 (undated)
- S3 https://arcprize.org/blog/arc-prize-2025-results-analysis (2025-12-05)
- S4 https://arxiv.org/abs/2601.10904 and https://arxiv.org/html/2601.10904v1 (2026-01-15)
- S5 https://raw.githubusercontent.com/1ytic/NVARC/main/nvarc_2025.pdf (Nov 2025)
- S6 https://github.com/1ytic/NVARC, plus `SDG/scripts`, `ARChitects/`, raw `build_datasets.py`, `run_sft_4b.sh`, `sft_mg.yaml`, `run_sft.py`, `SDG/README.md`, `SDG/prompts/summary_v1.md` and `summary_v2.md`, and the GitHub API (HEAD 2025-12-13)
- S7 https://lambdalabsml.github.io/ARC2025_Solution_by_the_ARChitects/ (2025)
- S8 https://github.com/jcole75/arc_2025_mindsai and its PDF `MindsAI_Tufa_Labs_2025_Solution.pdf` (late 2025)
- S9 https://tufalabs.ai/research/ (accessed 2026-10-13)
- S10 https://tufalabs.ai/news/ (accessed 2026-10-13)
- S11 https://tufalabs.ai/research/duck-harness/ (2026-07-01)
- S12 https://arcprize.org/blog/arc-prize-2026-milestone-1 (2026-07-06)
- S13 https://www.metirai.com/blog/arc-agi-3-kaggle-scores-surge-harnesses-arc-prize-2026 (2026-10-05)
- S14 https://toolnavs.com/article/2447-arc-agi-2-high-score-refresh-tufa-labs-tops-the-board-at-8806-past-the-85-bonus (2026-10-10)
- S15 https://github.com/Tufalabs/duck-harness (undated; no LICENSE file seen)
- S16 https://arcprize.org/guide/1 (undated)
- S17 https://www.kaggle.com/api/v1/models/sorokin/qwen3_4b_grids15_sft139/get (updated 2025-11-02). The model web page did not render.
- S18 Kaggle API `kernels/pull` for sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue (version 10, run 2026-10-10)
- S19 Kaggle API `kernels/pull` for sorokin/pip-install-unsloth-flash-patch (2026-10-10)
- S20 https://github.com/OpenKaggle/arc-agi-2-paper-track-research (checked 2026-09-09; commits 2026-09-26 to 28)
- S21 Kaggle API `kernels/pull` for christopherdaleman/arc-2026-nvarc-trm-evidence-cost-v1 (2026-10-10)
- S22 Kaggle API `kernels/pull` for gregkamradt/arc-2025-diffusion (undated)
- S23 Kaggle API model dfranzen/lladamix1400k-l45-m20-k1-gg2m-3uof4lei-s175k-4bit (2025-10-26)
- S24 Kaggle API model sorokin/qwen3_2b_grids15_sft141 (2025-11-02)
- S25 Kaggle API dataset sorokin/nvarc-synthetic-puzzles (2025-11-13)
- S26 https://developer.nvidia.com/blog/?p=109968 (2025-12-05)
- S27 https://trelis.substack.com/p/nvarc-2025-arc-prize-winners (undated)
- S28 https://arxiv.org/abs/2505.07859 and https://arxiv.org/html/2505.07859v2 (2025-05)
- S29 https://arxiv.org/html/2412.04604v2 (2024-12)
- S30 https://arxiv.org/abs/2506.14276 (2025-06-17)
- S31 https://ironbar.github.io/arc25/05_Solution_Summary/ (late 2025)
- S32 https://arxiv.org/abs/2411.07279 (2024-11-11)
- S33 https://arxiv.org/abs/2411.02272 (2024-11-04)
- S34 https://arxiv.org/abs/2510.04871 (2025-10-06)
- S35 https://arxiv.org/abs/2511.02886 (2025-11-04)
- S36 https://arcprize.org/blog/hrm-analysis (2025-08-15)
- S37 https://iliao2345.github.io/blog_posts/arc_agi_without_pretraining/arc_agi_without_pretraining.html (2025)
- S38 https://arxiv.org/abs/2511.14761 and https://arxiv.org/html/2511.14761v1 (2025-11-18)
- S39 https://github.com/lillian039/VARC (MIT)
- S40 https://blog.redwoodresearch.org/p/getting-50-sota-on-arc-agi-with-gpt (2024-06-17)
- S41 https://jeremyberman.substack.com/p/how-i-got-the-highest-score-on-arc-agi-again (2025-09-16)
- S42 https://poetiq.ai/posts/arcagi_verified/ (2025-12-05)
- S43 https://arxiv.org/pdf/2606.31543 (dated 2026-02-03; arXiv 2026-06-30)
- S44 https://imbue.com/blog/2026-02-27-arc-agi-2-evolution (2026-02-27)
- S45 https://arxiv.org/abs/2603.20334 (2026-03-20; v4 2026-05-23)
- S46 https://arcprize.org/results/deepseek-v4-flash-0731 (model 2026-07-31)
- S47 https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731
- S48 https://huggingface.co/mindware/arc-codet5-660m
- S49 https://github.com/johnsonhk88/kaggle-ARC-Prize-2026-ARC-AGI-2 (copy of the rules)
- S50 https://arcprize.org/competitions/2026/paper
- S51 https://alphasignal.ai/news/tufa-labs-wins-25k-beating-frontier-ai-on-the-world-s-hardest-benchmark (2026-07-02)
- S52 https://arcprize.org/blog (index)
- S53 https://raw.githubusercontent.com/arcprize/ARC-AGI-2/main/data/evaluation/0934a4d8.json (repo HEAD f3283f7, 2025-05-15)
- Also opened, with low weight:
  - https://arxiv.org/html/2603.13372v1 (secondary survey)
  - https://arxiv.org/abs/2603.06590 and https://arxiv.org/abs/2606.26530 (no numbers in abstracts)
  - https://arxiv.org/abs/2505.11831
  - https://github.com/Hisernberg/arc-agi-2-solver (unreliable)

**Opened but empty or blocked (UNVERIFIED):**
- the Kaggle leaderboard, code, discussion and models pages and the writeups (only the title rendered);
- https://x.com/arcprize (HTTP 402);
- the Google Drive NVARC PDF;
- the SOAR paper on OpenReview (browser check);
- newhotness.arcprize.org (SSL error);
- the Kaggle `kernels/list` API (401) and the sorenravn notebook (403).
