# CORA × NVARC architectural subsumption audit, part 1 (19 October 2026)

**Status.** A read-only audit. Nothing is a result.
- Nothing was executed, trained or submitted. No GPU was used. No Kaggle kernel was pushed or run.
- No puzzle, summary, mixture or program content was downloaded. Only metadata, NVARC's README, prompts,
  scripts and config (as text), the paper, the viewer notebook (as text) and Kaggle pages were fetched (section 13).
- This file is the only new file in the repository. Nothing was committed.

**The question.** Could either system absorb the other's useful mechanisms, instead of combining answers?
- **(A) NVARC-first:** Qwen learns to propose, execute, diagnose and revise typed executable programs.
- **(B) CORA-first:** CORA keeps reasoning and execution. Neural models supply representation proposals, search
  priorities and revision decisions.

**Labels used below.**
- VERIFIED: read today (2026-10-19) in the cited file, page or API response.
- RECORD: taken from an earlier record in `records/`; not re-checked today.
- ESTIMATE: my judgement from the cited evidence; not measured.

## 0. Summary

**Verified facts:**
1. **NVARC's programs are published**, as LLM completion text, in the Kaggle dataset `sorokin/nvarc-artifacts-puzzles`:
   - 193,793 input-program completions and 2,050,249 output-program completions;
   - each row carries its prompt and the model's reasoning trace [K5].
   - The GitHub repository holds only the prompts and scripts [R1, R2]. The 103k-puzzle dataset holds grids only
     [R2 `make_pairs.py` L119–133; K7].
2. **Licences:**
   - all three NVARC datasets are "unknown" [K5];
   - the GitHub repository has no licence [R1];
   - the checkpoint is Apache 2.0 [K6].
   - The dataset authors flag "License concerns" for rows made with Claude. Their own filter keeps 31,541 of
     193,793 input rows [K5].
3. **Contamination:**
   - every synthetic puzzle descends from public ARC-AGI-2 tasks;
   - the seeds cover all 120 public evaluation tasks and all 1,000 training tasks [R3 §2.1];
   - the evaluation tasks, test outputs included, were the validation set that ranked checkpoints
     [R2 `build_datasets.py` L157, L249–250; `sft_mg.yaml` L14–16, L127].
4. **The released checkpoint has a 16-token grid vocabulary** [R3 §3.1]. It cannot emit program text.

**Estimates:**
5. CORA's current typed vocabulary could express about **1–3%** of NVARC's puzzles in the CORA-v2 / G-grow class,
   and about **5–15%** with all of native v23. Direct syntactic translation of the Python text is close to **0%**.
6. **Program-level supervision from NVARC's data is possible only indirectly:** execute the programs in a sandbox,
   then search CORA's own language ("behavioural labelling"). It would cover a small subset. Licence and
   contamination block its clean use today.

## 1. Architectures as built

### 1.1 NVARC's notebook, stage by stage (VERIFIED)

**Sources:**
- the upstream notebook `kaggle/neural_v1_smoke/upstream/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb`
  (sha256 506b85db…);
- our deployed copy `kaggle/neural_v1/kernel/notebook.ipynb` (sha256 0111f325…).

Line numbers are in the deployed copy, counting cells from 0. Deployed cells 3–8 are upstream cells 2–7.

| # | stage | what it does | where |
|---|---|---|---|
| 1 | runtime guard | end time = start + 12 h − 600 s | upstream cell 0 |
| 2 | task queue | every test task id goes into a queue; 4 workers start, one per L4 GPU | upstream cell 5 (`starter.py`) |
| 3 | model load | Unsloth `FastLanguageModel.from_pretrained` loads `sorokin/qwen3_4b_grids15_sft139`: bf16, no 4-bit | cell 5 L265–268; the path is patched by `kaggle/neural_v1/build_full.py` L115–116 |
| 4 | adapter | one LoRA: r 256, α 32, rsLoRA, dropout 0. It covers q/k/v/o/gate/up/down, `embed_tokens` and `lm_head`. Its initial weights are saved in memory | cell 5 L225–234, L274, L280–281 |
| 5 | per-task test-time training | reset the adapter; build 128 augmented copies of the demonstrations; train 1 epoch on output-grid tokens | cell 5 L315–340; details in section 7 |
| 6 | decoding | 16 augmented views per test input. Batched depth-first search keeps every completion with cumulative probability above 0.2. Caps: 540 s per search, 1,200 s per task | cell 5 L102, L121, L292, L360, L403 |
| 7 | rescoring | each distinct candidate is mapped back to the original frame. It is then scored by log-likelihood under 8 fixed augmentations | cell 5 L441–449 |
| 8 | storage | per view, a list of {`beam_score`, `score_aug`, `solution`} is pickled to `/kaggle/inference_outputs` | cell 5 L461 |
| 9 | selection | `score_kgmon` = times found − mean augmented NLL. The top 2 distinct grids per output are kept. `[[0]]` fills a slot when fewer exist | cell 4 L35, L61; cell 8 L13–17; upstream loader `get_submission` |
| 10 | our deployment additions | identity cell, health check on the training stand-ins, schema repair, `execution_manifest.json` | `records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md` |

**Offline, before the notebook** [R3 §2–3; R2]:
1. The data pipeline: summaries → mixtures → input programs → output programs → grids (section 2).
2. Full supervised fine-tuning of Qwen3-4B-Thinking-2507, cut to 16 tokens:
   - 3,255,481 samples;
   - 4 nodes × 8 H100, 27 h;
   - [R3 §3.1, Table 1; R2 `run_sft_4b.sh` L9–21].

### 1.2 CORA components: inputs and outputs (VERIFIED from code unless marked)

| component | takes in | puts out | vocabulary | files |
|---|---|---|---|---|
| native v23 | the task (demonstration pairs, test inputs); the frozen library (2 operators: `crop_to`, `recolor`); learned verbs (1: `mirror_h`) | attempt 1 is the certified render; attempt 2 is the best uncertified object partial; the fallback is the test input. Acceptance = train-exact plus adaptive leave-one-out (RECORD) | 7 segmentation views; 19 typed object deltas; GROW with 13 modes; grid-level layers | `library.json`; `learned_verbs.json`; `geocat_arc/object_reasoning/types.py` L34–44, L63–110; `growth.py` L40–45; I/O from `records/CORA_ARC_LEADER_METHOD_AUDIT_20261013.md` §5 (part) |
| CORA-FHR | demonstrations plus native's failure evidence. Each instance is (object O, added cells A, grid G, demonstration, colour), from native's `pattern` fallbacks | a canonical-first G-grow expression, as a JSON extension {format, version, expr, name}. It is installed reversibly; native's own gate decides | G-grow v1: 10 sources × 50 transforms; depth 1, depth 2 and same-source unions; 37,750 expressions; growth only. A guarded form adds one feature test with two branches | `cora_fhr/construct.py` L1–16; `ggrow.py` L1–38, L162–163, L268–273; `bridge.py` L1–17; `ggrow_guard.py` L1–21 |
| CORA-v2 | demonstration pairs and test inputs; no answers | a decision record: the diagnosis, up to 2 attempts per test input, the fold outcomes and their details, the top hypothesis. It certifies only a unique, fold-robust prediction | hypothesis = (view, one of 7; G-grow expression; colour policy, one of 9; a learned table or constant). Same-size pairs only. The `select` family adds a guard over 5 features. `tst` adds keep, delete or recolour by a feature table; its integration is pending | `cora_revision_v2/scene_reasoner.py` L5–25, L37, L156–163, L223–241, L331–379; `diagnosis.py` L1–39; `selection.py` L1–37; `tst.py` L1–32; `_pending_tst_integration.py` |
| fusion layer | per task: demonstrations, test inputs, and NVARC's candidate grids in NVARC's order | `Proposal` records (source, rank, `explained_by`, executable, verification). The policies N0, FILL_V1 and EXPLAIN_V1 choose the two attempts | CORA-v2's `grow` and `select` families | `cora_neural_fusion/*.py`; 5 unit tests in `tests/test_fusion.py` (commit 99a8147) |

**Notes:**
- G-grow only adds cells on the background. It never deletes, recolours, moves or resizes
  (`ggrow.py` L4–7, L162–163).
- CORA-v2 has no hypothesis when any pair changes size (`scene_reasoner.py` L156–163).
- The v2 diagnosis labels (`diagnosis.py` L35–36):
  - GEOMETRY_GAP, COLOUR_POLICY_GAP;
  - REPRESENTATION_AMBIGUITY, HYPOTHESIS_DISAGREEMENT;
  - MULTIPLE_ACTIONS_NEEDED;
  - FOLD_FRAGILITY;
  - ENGINE_REJECTION, RESOURCE_LIMIT.
- 32 of the 60 development tasks need more than additions: 25 mix several kinds of change, and 7 only recolour or
  delete (`tst.py` L4–7).

### 1.3 Interfaces between them today

- **Grid level only.** NVARC's `submission.json` (2 attempts per output) feeds two consumers:
  - `scripts/nvarc_cora_complementarity.py`;
  - `cora_neural_fusion.explain.explain_task(candidates=…)`.
- **Not saved from the NVARC run** (RECORD, `records/CORA_QWEN_FUSION_FEASIBILITY_20261019.md` §3):
  - the 4,090 decoded candidate files and their scores;
  - logits and hidden states;
  - LoRA states.
  - So EXPLAIN_V1 cannot run on the existing artefacts.
- **No program interface.** NVARC emits grids. CORA emits typed hypotheses. They share no representation.
- **One earlier representation-proposal interface was tried and closed.** CORA-NVG (`cora_neural_view/guides.py`
  L1–30) ranked segmentation views with frozen Qwen2.5-1.5B and I-JEPA guides. No guide beat the fixed-order
  fallback (RECORD, `records/CORA_NEURAL_VIEW_GUIDANCE_RESULT_20261013.md`).
- **The fusion layer is unit-tested only.** It has never run on real candidates.

## 2. NVARC's program data

### 2.1 Availability (VERIFIED)

| asset | what it holds | size and count | last updated |
|---|---|---|---|
| GitHub `1ytic/NVARC` at 846d0198efa7 | the data pipeline's prompts (6) and scripts (10), the training config and the paper. **No programs and no puzzles** | 56 tree entries; 626 KB | HEAD 2025-12-13 |
| Kaggle `sorokin/nvarc-artifacts-puzzles` | the generated text: summaries, mixtures, **input programs, output programs** | 192 files, 47.5 GB listed (the Kaggle size field says 42.0 GB) | 2025-11-20 |
| Kaggle `sorokin/nvarc-synthetic-puzzles` | the 103k puzzles as grids, one JSON per puzzle | size field 338 MB; files of 8–101 KB on the first listing page | 2025-11-13 |
| Kaggle `sorokin/nvarc-augmented-puzzles` | the 3.2M augmented training samples (Arrow), in 7 subsets including `arc2_evaluation6` | 42 files, 1.32 GB | 2025-11-13 |

**Subsets of the artifacts dataset** [K5: dataset card and file listing]:

| subset | rows (card) | files and size (listing) | content (card) |
|---|---|---|---|
| summaries | 3,263 | 2 files, 47 MB | "descriptions of puzzles" |
| mixtures | 266,593 | 20 files, 4.30 GB | "mixtures of two summaries" |
| inputs | 193,793 | 20 files (111–396 MB each), 5.78 GB | "python code of input logic" |
| outputs | 2,050,249 | 150 files (98–637 MB each), 37.38 GB | "python code of output logic", generated 10–20 times per input; column `sid` |

**Counts disagree between the paper and the data, as expected for unfiltered data:**
- The paper says 126,901 input programs passed the filter and 103,253 puzzles were kept [R3 §2.3–2.4].
- The dataset stores the unfiltered completions. Its listed columns contain no acceptance flag [K5].
- So finding the accepted rows needs re-execution, or a join with the puzzle files by seed-pair name (section 12).

### 2.2 Format (VERIFIED from prompts, scripts and the card; no row was read)

- **Row columns:**
  - inputs: `mix_name`, `summary_name1`, `summary_name2`, `puzzle_name1`, `puzzle_name2`, `model_name`,
    `reasoning_level`, `prompt`, `reasoning`, `completion` [K5];
  - outputs: the same plus `sid` [K5].
- **The code** is a fenced `python` block inside `completion`. NVARC's parser takes the longest fenced block
  [R2 `parser.py` L72–77].
- **Input-program contract** [R2 `generate_puzzle_input.md`]:
  - numpy and basic Python only;
  - a seeded `generate_puzzle_input(seed: int) -> np.ndarray`, plus helper functions;
  - unit tests named `test_*` that take only the generated grid;
  - at most 30 × 30; colours 0–9.
- **Output-program contract** [R2 `generate_puzzle_output.md`]:
  - `generate_puzzle_output(input_grid: np.ndarray) -> np.ndarray`;
  - deterministic; numpy only; prints debug information.
- **Puzzle files:**
  - a JSON list of {"input", "output"} grid pairs [R2 `make_pairs.py` L119–133];
  - path `<subset>/<seed1>/<seed1>_<seed2>.json`, for example `nvarc_full/0934a4d8/0934a4d8_00576224.json`
    [K7 cell 3; K5 listing];
  - at least 12 pairs [R2 `make_pairs.py` L146]; "about 30" per the paper [R3 §2.4].

**Format sample.** This is my reconstruction from the two prompts, as text. It is not a dataset row.

```text
# inputs row -> completion text -> one fenced python block
import numpy as np
def generate_puzzle_input(seed: int) -> np.ndarray:   # seeds numpy, random size and colours, returns the grid
def <helper>(input_grid, ...):                         # optional helpers
def test_<property>(input_grid):                       # model-written checks, e.g. allowed colours
# outputs row (one of 10-20 per input; column sid) -> completion text -> one fenced python block
import numpy as np
def <helper>(input_grid, ...):
def generate_puzzle_output(input_grid: np.ndarray) -> np.ndarray:   # deterministic transform
# synthetic-puzzles file
[{"input": [[int, ...], ...], "output": [[int, ...], ...]}, ...]   # 12 or more pairs, about 30
```

**Why no real row was read:**
- every program shard is 98–637 MB, above this audit's 50 MB sample cap;
- the only small shards (summaries, 20–27 MB) include descriptions of ARC-AGI-2 evaluation tasks;
- every row descends from ARC-AGI-2 public tasks that overlap this project's protected splits (section 5).

### 2.3 Families

**Lineage families (VERIFIED)** [K5 card; R3 §2.1]:

| summary set | written by (card) | seeds (paper) | rows |
|---|---|---|---|
| summary1 | claude-sonnet-4-20250514 (the paper says claude-opus-4-20250514) | 716 ARC-AGI-2 training tasks with H-ARC or BARC descriptions | 716 |
| summary2, summary3 | gpt-oss-120b | the same 716 | 712, 715 |
| summary4 | human | 29 ARC-AGI-2 **evaluation** tasks | 29 |
| summary5 | claude-sonnet-4-5-20250929 | the other 91 **evaluation** tasks | 91 |
| summary6 | claude-sonnet-4-5-20250929 | all 1,000 ARC-AGI-2 **training** tasks | 1,000 |

- **Mixtures mix1–mix10** each combine two summaries. The card attributes mix1 (28,000 rows) to Claude Sonnet 4 and
  the rest to gpt-oss-120b. The paper says mixing used only gpt-oss-120b [K5; R3 §2.2].
- **Every input and output program** was written by gpt-oss-120b [K5; R3 §2.3–2.4].
- **Training subsets:** "NVARC training" has 47,337 puzzles from training seeds only. "NVARC full" has 55,886 from
  training and evaluation seeds [R3 Table 1].
- **mix10** has 9,799 input programs but no row in the card's outputs table [K5].

**Concept families (NOT measured):**
- Each summary has a free-text `puzzle_concepts` field [R2 `summary_v2.md`; `utils.py` L56–75].
- The prompt's examples are "rotation, mirroring, denoising, pattern completion, object detection".
- No tag was read, so this audit has no concept-family counts.
- Mixtures are designed to be "more complex" and to "require compositional reasoning" [R2 `mix_v1.md`].

### 2.4 Execution validity (NOT tested)

**What NVARC's own pipeline did** (VERIFIED code, R2):
- **No sandbox.** Model code runs through in-process `exec()` with a SIGALRM timer. The code carries the comment
  "TODO: use constrained execution" (`puzzle.py` L18–26).
- **Input programs:**
  - up to 60 seeds are tried to get 30 unique grids;
  - every model-written test must pass;
  - all-equal or one-colour sets are rejected;
  - 10 s per program (`generate_input_grids.py` L13–75, L37, L136).
- **Output programs:**
  - at least 20 parsable completions are required (`generate_output_grids.py` L80, L112);
  - each call has 1 s;
  - an output equal to its input counts as a failure (L11–26).
- **Pairing:**
  - for each input grid, the majority output needs at least 8 votes;
  - at least 12 such grids are needed;
  - at least 4 programs must agree on every kept grid (`make_pairs.py` L84–114, L145–147).
- **What "valid" means.** A program executes and agrees with other samples from the same model. Nothing checks the
  program against its description. Nothing checks that 5 or 6 shown pairs determine the rule; training samples show
  5–6 pairs (`build_datasets.py` L228).

**What a sandboxed re-execution test would need** (a design; nothing was run):
1. **A lineage filter first** (section 5). Never run evaluation-derived rows (summary4, summary5, the `nvarc_full`
   seeds).
2. **Isolation:**
   - one process per program, with no network and a read-only filesystem except a temporary directory;
   - no access to the home directory or this repository;
   - a CPU-time limit (`RLIMIT_CPU`, matching Athe's CPU-time budget rule), a memory cap (`RLIMIT_AS`) and a
     process cap (`RLIMIT_NPROC`).
3. **Static gate:** an AST pre-scan that allows only `numpy` and rejects `os`, `sys`, `subprocess`, `open`,
   `eval`, `exec` and `__import__`. Run under `python3 -I`.
4. **A pinned numpy version.** The programs seed numpy's legacy global generator, so grids depend on it.
5. **Checks:** run the output programs on the *published* input grids and compare with the published outputs. Exact
   input regeneration is not expected, because seeds chain across puzzles from a random start
   (`generate_input_grids.py` L87, L125, L140–143).
6. **Measures:** the share that executes, the share that agrees, timeouts and CPU seconds per program.
7. **Where:** a low-priority CPU job on Athe only after Phase 2a, or a Kaggle CPU notebook with the internet off.
   The data licence must be settled first.

### 2.5 Compatibility with CORA

**Verified facts:**
- **Types.** NVARC programs are untyped, free-form numpy (array → array). They use loops, helper functions and
  data-dependent branching [R2 prompts]. CORA programs are small typed terms (section 1.2).
- **Grid size.** NVARC's example randomizes each side over 8–30, and outputs may change size [R2 prompts]. CORA-v2
  handles same-size, additive scenes only.
- **No shared primitives.** The prompts allow "only basic Python commands and the numpy package" [R2].
- **A proxy for the seed distribution** (RECORD, `records/CORA_REASONING_V2_GAP_AUDIT_20261019.md` §2; 240
  ARC-AGI-2 training stand-ins, training pairs only):
  - resize: 71 (30%);
  - additions only: 71 (30%), of which 31 single-colour and 40 multi-colour;
  - mixed, recolour or delete: 98 (41%).

### 2.6 Translation feasibility (ESTIMATES)

| target | estimated share of NVARC puzzles expressible | basis |
|---|---|---|
| G-grow v1 / CORA-v2 (one geometry per object, 9 colour policies, optional guard, same size) | about 1–3% | Additions only are about 30% of seed-like tasks. Within growth-shaped real tasks, only 3–8 of 58 (5–14%) fit one expression (gap audit §1). Mixtures combine two concepts and randomize sizes |
| native v23's whole typed vocabulary | about 5–15% | Native is correct on 12 of 60 development tasks (20%) and 47 of 259 stand-in outputs (18%). Both are in-sample: its library was built on that training set. It scores 0.00 on the hidden set. Mixtures are harder (README; `records/NVARC_CORA_COMPLEMENTARITY_AUDIT_20261014.md` §2) |
| direct syntactic translation of the Python text into CORA terms | about 0%, automatically | There are no shared primitives, and the programs use free loops and conditionals. Translation would need program analysis and equivalence proofs |
| behavioural labelling: execute, then search CORA's language for a program matching many generated pairs | the same as CORA's coverage above | This is the only practical route. It also yields an "inexpressible" set, with code and concept tags, that shows which operations are missing |

**Family mapping (ESTIMATE: families inferred from the seed types and the prompts' concept vocabulary; NVARC's real
family mix was not measured):**

| family | CORA counterpart today | status |
|---|---|---|
| move, rotate, reflect or scale whole objects | TRANSLATE, ROTATE, REFLECT, SCALE, MOVE_TO, MOVE_UNTIL_ADJACENT | translatable when the parameter is a typed feature |
| recolour or delete objects by a feature | RECOLOR, DELETE; `tst` stage-1 tables | translatable for size, colour, h, w, size rank and border |
| crop to an object or region | CROP_TO, EXTRACT_PART | translatable when the region is a typed reference |
| rays and lines to the border or an obstacle; connect objects | G-grow `ray`; FILL_LINE; CONNECT | translatable as a single geometry |
| halo, ring or frame; fill an interior or holes | G-grow `ring`, `hull`, `interior`; GROW halo, frame_minority, fill_interior, fill_holes | translatable |
| mirror or symmetry completion; periodic repetition | G-grow `reflect`, `repeat`; GROW symmetry_complete, mirror_edge, periodic modes | partly; no reasoning about occlusion |
| copy or stamp a template | COPY, PAINT, COPY_PART, SYNTH_COPY | partly |
| output size or colour computed from counts | none in general | missing |
| sorting, ranking or argmax by property; relational selectors (inside, touching, between) | guards over 5 features only | missing |
| per-object rules with several branches; several actions in one task | a guard with 2 branches; `tst` with 2 stages | mostly missing (25 of 60 development tasks need several actions) |
| simulation to a fixed point (gravity, bouncing, flow) | `ray_deflect` and `cavity_leak` only | missing in general |
| grid partition by separator lines; cell-wise logic between sub-grids; tiling with a per-tile transform | none in general | missing |
| paths, mazes, connectivity | none | missing |
| sequence extrapolation; denoising under occlusion | periodic modes only | mostly missing |
| any two of the above combined (which mixtures are designed to be) | composition stops at depth 2 or two stages | mostly missing |

## 3. Licensing table (VERIFIED today unless marked)

| asset | licence and source | what it means for us |
|---|---|---|
| NVARC GitHub code `1ytic/NVARC` | **none**: no LICENSE file; the GitHub API reports `license: null` [R1] | **A public repository with no licence grants no right to redistribute or modify.** GitHub's docs: without a licence, "no one may reproduce, distribute, or create derivative works", though GitHub users may view and fork it [G4]. Read and cite only |
| NVARC paper PDF (in that repository) | none stated | cite; quote briefly |
| Kaggle notebook `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue` v10 | The API has no licence field (RECORD log §7). ARC Prize 2025 rules, "Public Code Sharing": shared competition code is "deemed to have licensed the shared code under an Open Source Initiative-approved license … that in no event limits commercial use" [K4] | probably reusable as a Kaggle fork with attribution, which is what `neural_v1` is. The licence's name is unstated. The page notice is unread |
| checkpoint `sorokin/qwen3_4b_grids15_sft139` v1 | **Apache 2.0** (Kaggle instance `transformers/bfloat16`, versionId 627758). Training data are not declared (`trainingData: []`) [K6] | redistribution and derivatives are allowed under Apache 2.0 terms |
| base model Qwen3-4B-Thinking-2507 | apache-2.0 [H1] | — |
| `sorokin/nvarc-synthetic-puzzles` | **"unknown"** [K5] | no redistribution right is granted |
| `sorokin/nvarc-augmented-puzzles` | **"unknown"** [K5] | the same; it also contains ARC-AGI-2 evaluation tasks with their outputs |
| `sorokin/nvarc-artifacts-puzzles` | **"unknown"**; the card has a "License concerns" section for Claude rows [K5] | the same. The authors' open-weights filter keeps 31,541 of 193,793 input rows |
| program generator gpt-oss-120b | apache-2.0 [H2] | — |
| summary and mixture generators: Claude models | Anthropic's Commercial Terms D.4 bar customers from using the services "to build a competing product or service, including to train competing AI models" [A1] | this binds the customer, NVARC. Its effect on later users is unclear: a legal question |
| seeds: ARC-AGI-2 | Apache-2.0 [G1] | — |
| seeds: H-ARC | CC0 1.0, stated in the README [G2] | — |
| seeds: BARC descriptions | **none**: the API shows no licence and the README states none [G1, G3] | unlicensed seed material |
| RE-ARC / ConceptARC / MINI-ARC | MIT / MIT / Apache-2.0 [G1] | — |
| notebook dependencies | unsloth Apache-2.0, unsloth_zoo LGPL-3.0+, flash-attn BSD, numpy and scikit-learn BSD, transformers Apache-2.0 | RECORD (`records/KAGGLE_NEURAL_V1_LOG_20261013.md` §1, §7) |

## 4. The legal and technical boundary

| thing | legal boundary | technical boundary | may it be redistributed or uploaded as a public Kaggle asset? |
|---|---|---|---|
| NVARC source code (GitHub) | unlicensed (section 3) | data-pipeline scripts, prompts and the training config; no weights, no data | **No.** Link to it. If needed, re-implement from the paper in our own code |
| NVARC Kaggle notebook code | deemed OSI-licensed by the 2025 competition rule; the licence is unnamed | the inference and test-time-training pipeline | **Probably yes,** as a Kaggle fork with attribution (moderate confidence) |
| checkpoint weights | Apache 2.0 | a 16-token vocabulary on the Qwen3-4B architecture | **Yes,** with the licence, the attribution notice and a note of changes. There is no need to re-upload: attach the existing Kaggle model |
| NVARC datasets | "unknown", plus the Claude flag | text and grids | **No.** No re-upload, and no public derived subset or translation, until the authors grant a licence |
| new adapters we train | ours, as a derivative of Apache-2.0 weights | they must match the base architecture. LoRA cannot add tokens: new tokens mean resizing `embed_tokens` and `lm_head`, which changes full weights. One r = 256 task adapter has about 0.53B parameters, about 1.06 GB in bf16 (ESTIMATE from the public Qwen3-4B shape) | **Yes, if the training data are cleanly licensed:** ARC-AGI-2, RE-ARC, ConceptARC, MINI-ARC, H-ARC and CORA's own generators. If they are trained on NVARC data, wait for a licence |

**The competition overlay** [K2]:
- prize eligibility requires open-sourcing the solution;
- the winner licence is "Open Source - CC BY 4.0" (rules L58, L89);
- submissions need an "open source system, open source model, and open source weights/parameters", per the OSI
  checklist (L91);
- data or models "with an incompatible license" are exempt from the licence grant (L95);
- public external data and pre-trained models are allowed (Code Requirements).

## 5. Contamination

**Public evaluation set (120 tasks):**
1. **Their descriptions entered the training data.**
   - 29 human and 91 Claude summaries cover all 120 tasks [R3 §2.1].
   - Their mixtures became "NVARC full": 55,886 puzzles, 54.9% of training samples [R3 Table 1].
   - Table 1's caption: "NVARC full subset uses both training and evaluation puzzles from ARC-AGI-2."
   - §3.5: "Despite the fact that we “leaked” the descriptions of these puzzles to our synthetic dataset, we saw a
     good correlation with public leaderboard."
   - §2.3: input programs from "mixtures of ARC-AGI-2 evaluation puzzles" were accepted at about 50%.
2. **Their answers drove checkpoint selection.**
   - `build_datasets.py` L157 builds pairs as `data["train"] + data["test"]`, so test outputs are included.
   - L249–250 build `arc2_evaluation6` from the evaluation files.
   - `sft_mg.yaml` L127 sets `val_dataset_path: data/grids_v15/arc2_evaluation6`.
   - L14–16 rank checkpoints by `val_loss` with `keep_top_k: 3`.
   - `run_sft_4b.sh` L9 names the run `qwen3_4b_grids15_sft139`, the released model's name [R2].
3. **They were not in the gradient data directly.** The training paths at `sft_mg.yaml` L120–126 exclude
   `arc2_evaluation6`.
4. **A published copy exists.** `arc2_evaluation6` (2.5 MB) sits inside the augmented dataset [K5]. Downloading that
   dataset whole would put evaluation answers on Athe.
5. **The writeup is less explicit than the paper.** The Kaggle writeup keeps Table 1's caption. It drops the "leaked"
   sentence and the 29 + 91 evaluation-summary counts [K1].

**Training set (1,000 tasks):**
1. **Direct:** 609 training tasks (those not in RE-ARC) × 256 samples, test pairs included [R2 `build_datasets.py`
   L157, L257–259; R3 Table 1].
2. **RE-ARC:** 400 generators for ARC-AGI-1 training tasks.
3. **Seeds:**
   - 716 tasks × 3 summaries;
   - all 1,000 tasks summarized by Claude Sonnet 4.5;
   - this became "NVARC training", 47,337 puzzles [R3 §2.1, Table 1].

**Consequences for this project:**
- **DEV 60 and HOLDOUT 60** (the public evaluation) are contaminated for any NVARC-derived model or data, at concept
  level and through checkpoint selection.
- **Step B's ARC-1000 experiment** partitions the same 1,000-task training file (RESUME;
  `records/CORA_REASONING_V2_COHORT_AUDIT_20261019.md`). So Experience, Promotion, Lockbox and E_transfer were all
  seeded or trained on.
- **Phase 2a's 40-task cohort** comes from that file, so the same applies.
- **The 240 stand-ins** are direct training data; the pipeline-health line read 229.5 / 240.
- **Clean measurement** is possible only on the hidden Kaggle set or on fresh private generators (RECORD, leader
  method audit §4).

**Lineage filtering is possible but incomplete:**
- Rows carry `summary_name1/2` and `puzzle_name1/2` [K5]. Puzzle files are named by seed pair [K7].
- A filter must drop summary4 and summary5 rows and every seed id in a protected split.
- Checking membership needs the user-authorized membership-only tool. It was not run here.
- **The licence filter does not remove evaluation lineage.** It keeps summary4, the 29 human evaluation summaries
  [K5 card].
- ESTIMATE: mixing spreads concepts. Seed filtering removes descendants, not look-alikes.

## 6. Qwen interfaces in `kaggle/neural_v1/` (VERIFIED code; line numbers as in section 1.1)

| interface | exposed today? | where | what is needed |
|---|---|---|---|
| token logits | yes, at runtime | `outputs.logits` in the search (cell 5 L150, L174) and in scoring (L211, `log_softmax`) | an instrumented builder that keeps them |
| candidate scores | yes: `beam_score` and 8 `score_aug` values are computed and pickled per candidate | cell 5 L441–461; selection in cell 4 L35–61 | copy `/kaggle/inference_outputs` into the output. `neural_v1` did not, so 4,090 files were lost |
| scoring any grid, such as CORA's | yes, as a function | `calc_scores(queries, answers, tokenizer, model)`, cell 5 L191–221 | build queries from CORA's candidates; call it after test-time training |
| multiple candidates | yes | the search keeps every completion above probability 0.2 (L102, L292), over 16 views per test input | keep the pool |
| hidden states and embeddings | **not used** | `output_hidden_states` appears nowhere. The Transformers API offers `output_hidden_states=True` and `get_input_embeddings()` | instrumentation. Whether Unsloth's fast inference path returns hidden states is unverified |
| LoRA create, reset, train | yes | `FastLanguageModel.get_peft_model` L274; `get_peft_model_state_dict` L280–281; `set_peft_model_state_dict` L315; the trainer L330–340 | — |
| LoRA save and load | **not used** (`save_strategy="no"`, L251) | PEFT's `save_pretrained` and `PeftModel.from_pretrained` are standard calls, not exercised here | new code. At about 1 GB per task adapter (ESTIMATE), saving all 240 is impractical |

**The vocabulary is a hard limit.** `ARC_VOCAB` lists digits, a newline and `<|im_end|>`, with user, assistant and
pad ids (cell 5 L28–47). The paper confirms the 16-token cut [R3 §3.1]. The model can emit grids only.

## 7. What NVARC's per-task test-time adaptation optimizes (VERIFIED code)

- **Data:** only the task's own demonstration pairs.
  - With no test answer, the training text is `fmt_train(train, last_is_challenge=True)` (cell 3 L194, L51–64).
  - The test input is not in the training text.
- **Augmentations:**
  - 8 dihedral views: identity or transpose, times rot90^k (cell 3 L251–252);
  - × 16 random permutations of all 10 colours, colour 0 included (L253; `permute_rnd_all_`);
  - so 128 copies. Task-key order and demonstration order are shuffled (L253–254).
  - Copies longer than 8,192 tokens are cut (cell 5 L326).
- **Targets and loss:** causal next-token cross-entropy on the output-grid tokens of **every** demonstration. All
  other tokens get label −100 (cell 5 L88–94).
  - Each output is predicted from its input and all earlier demonstrations in the shuffled order.
  - The first output is predicted from its input alone.
  - **It is not leave-one-out.** Every demonstration is both context and target.
- **Optimizer:** 1 epoch, about 128 steps at batch 1. AdamW, learning rate 5e-5, cosine schedule, warmup ratio 0.1,
  gradient clip 1.0, bf16 (cell 5 L236–261).
- **Parameters:** the LoRA of section 1.1, reset to the same initial weights for every task (L315).

**Reuse for a program-proposal or ranking objective:**
- **Reusable as is:**
  - the augmentation code, the chat format and the per-task reset-and-train loop;
  - `calc_scores`: an augmentation-averaged likelihood for any candidate grid. It can rank CORA's executable
    predictions with no new training (ESTIMATE of usefulness: untested).
- **Reusable with changes:** a leave-one-demonstration-out ranking objective. The correct held-out output would be
  contrasted with CORA's wrong executions. This needs new data construction and a pairwise or listwise loss on the
  same LoRA trainer.
- **New for program proposal:**
  - a program vocabulary: resized embeddings, or a new base model;
  - program-labelled supervision;
  - decoding over program tokens;
  - an executor in the loop, and verification.
  - The present objective (likelihood of the demonstration outputs) never supervises program choice. At best it
    supplies a prior over grids.

## 8. Are the generator programs actually present?

- **In the repository: no.** `SDG/` holds 6 prompts and 10 scripts only [R1 tree]. The scripts read
  `synthetic/inputs/nvarc_training/v1/completions/*.md` and `synthetic/solutions/nvarc_training/*/*`
  (`generate_input_grids.py` L134; `generate_output_grids.py` L109). Neither directory is in the repository.
- **In the datasets: yes, as text,** in `sorokin/nvarc-artifacts-puzzles`:
  - `inputs/data-000NN.parquet`: 20 files, 193,793 rows;
  - `outputs/data-000NN.parquet`: 150 files, 2,050,249 rows;
  - plus `mixtures/` and `summaries/` (section 2.1).
- **In the puzzle dataset: no programs.** It holds grids only (section 2.2).
- **Format sample:** section 2.2. No program was executed, imported or installed.

## 9. The three references the user named

- **https://github.com/1ytic/NVARC** (fetched 2026-10-19):
  - The README says the solution "consists of three main components": the synthetic data pipeline, an improved
    ARChitects solution and an improved Tiny Recursive Model.
  - It says the Artifacts dataset "includes generated text used to construct the synthetic puzzles", the Synthetic
    dataset "includes our 103k synthetic puzzles", and the Augmented dataset "includes few subsets with 3.2M
    augmented puzzles".
  - It mentions no licence, and there is no LICENSE file.
  - HEAD is 846d0198efa7 (2025-12-13). It is the same HEAD the 13 October audit recorded, and three files are
    byte-identical to that audit's copies (`build_datasets.py` f683f8b5, `sft_mg.yaml` 34abec38, `run_sft_4b.sh`
    f707a4e6) [R1, R2].
- **https://www.kaggle.com/c/arc-prize-2025/writeups/nvarc** (2026-10-19):
  - **The page did not render.** WebFetch returned only the title, "ARC Prize 2025 | Kaggle".
  - The Kaggle API returns a forum topic, "NVARC solution" (#651671): author "ivan", posted 2025-12-04 17:21 (the
    API gives no time zone), 123 votes. Its text matches the paper.
  - This audit treats that topic as the writeup. That the two URLs show the same document is inferred, not proven.
  - Quotes:
    - "we generated and filtered 126901 input grid programs in Python code";
    - "After filtering we had 103253 puzzles, where each puzzle has 1 input grid program and multiple output grid
      programs";
    - "NVARC full subset uses both training and evaluation puzzles from ARC-AGI-2";
    - "The local validation loss measured on an augmented version of 120 evaluation puzzles".
  - In comments, the author points to the artifacts dataset for "all generated texts" [K1].
- **https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/description** (2026-10-19):
  - **WebFetch returned only the title.** The pages were read through the Kaggle CLI instead. Code Requirements,
    Timeline and rules are byte-identical to the 12 October copy in `outputs/kaggle_deploy/rules_20261012/` [K2].
  - **Offline:** "No internet access enabled".
  - **Runtime cap:** "CPU Notebook <= 12 hours run-time" and "GPU Notebook <= 12 hours run-time". This answers the
    open point in `records/CORA_QWEN_FUSION_FEASIBILITY_20261019.md` §6.
  - **Public models and data:** "External data, freely & publicly available, is allowed, including pre-trained
    models". The rules add that external data must be "publicly available and equally accessible to use by all
    Participants … at no cost" (rules L101).
  - **Entry and team-merger deadlines:** "October 26, 2026 - Entry Deadline" and "October 26, 2026 - Team Merger
    Deadline". The account has already entered (CLI `userHasEntered: True`) [K3].
  - **Final deadline:** "November 2, 2026 - Final Submission Deadline", with "All deadlines are at 11:59 PM UTC".
    The CLI reports 2026-11-02 23:59:00 [K3].
  - **Also:**
    - the Description calls this "a relaunch of ARC Prize 2025";
    - the Prizes page says prize-eligible participants "will be removed from the competition if they do not open
      source their solutions".

## 10. What this means for routes A and B

**(A) NVARC-first: Qwen proposes, executes, diagnoses and revises typed programs.**
- **Blocked by the architecture.** The checkpoint has 16 tokens and was trained to emit grids (sections 6–7).
- **It would need a new program model.** NVARC's grid training alone took 4 × 8 H100 for 27 h [R3 §3.1].
  - Athe has 2 × 11 GB Turing GPUs (RECORD fusion feasibility §4).
  - The Kaggle quota is 30 GPU hours a week (RECORD).
- **Python supervision exists** (sections 2 and 8) but is unlicensed and contaminated (sections 3 and 5).
- **Test-time execution and revision** would compete for the same 12-hour budget that NVARC already uses.
- **Verdict:** not feasible before 2 November. It is a research-scale project.

**(B) CORA-first: neural models supply representation proposals, search priorities and revision decisions.**
- **Available now:**
  - the NVARC model as a likelihood scorer of CORA's candidates (`calc_scores`);
  - candidate pools, after instrumentation;
  - hidden states as a task embedding, after instrumentation (section 6).
- **Supervision:** CORA's own search outcomes on generated tasks. NVARC programs help only through behavioural
  labelling. They would supply fresh generated pairs (a strong generalization check) and concept tags.
- **Prior evidence is negative for frozen guides:** CORA-NVG was rejected (section 1.3). A *trained* guide is
  untested.
- **Verdict:** the nearer and cheaper route. It does not need NVARC's programs.

**Recommendation on program-level supervision from NVARC's data:**
- **Not feasible now as a clean, publishable path.**
- It is technically possible only indirectly (sandboxed execution plus CORA search), on an estimated 1–15% subset.
- **To unblock it, without compute:**
  1. ask Sorokin and Puget for an explicit licence for the code and the datasets;
  2. let the user decide a lineage filter, using the membership-only tool;
  3. write the sandbox specification (section 2.4).

## 11. Risks

1. **Contamination of every public split.** Any NVARC-derived model, data or supervision touches all 120
   evaluation tasks (including HOLDOUT) and all 1,000 training tasks (including Step B's protected partitions).
   Evaluation answers also chose the checkpoint (section 5).
2. **Licence.**
   - The datasets are "unknown" and the repository is unlicensed.
   - Claude-made rows are flagged by the authors themselves. Most input rows (162,252 of 193,793) fail the authors'
     open-weights filter.
   - No derived artefact may be published without a grant (sections 3–4).
3. **Expressivity and safety.**
   - The programs are free-form Python.
   - CORA's typed vocabulary may cover only about 1–15% (ESTIMATE), biased towards easy families.
   - NVARC itself executed this code without a sandbox (section 2.4).
4. **Practical.**
   - The artifacts are 47.5 GB, which matters on a shared, oversubscribed machine while Phase 2a runs.
   - The augmented dataset carries evaluation answers (section 5).
5. **Verification gap.** NVARC's "valid" means self-agreement, not correctness or identifiability (section 2.4).

## 12. Open questions

1. Is each published puzzle a unique (`puzzle_name1`, `puzzle_name2`) mixture? The puzzle path omits `mix_name`, so
   two mixes on the same seed pair could collide.
2. Which output `sid`s define each published puzzle? Neither the card nor the puzzle files record it. The
   intermediate `grids30_output` files are not published.
3. Did the prompts for the 91 Claude evaluation summaries include test outputs? `{PUZZLE}` in `summary_v2.md` is
   unresolved [R2].
4. Was the released step chosen by `val_loss` on `arc2_evaluation6`? Is `./configs/sft_mg.yaml` in
   `run_sft_4b.sh` L11 the repository file?
5. The paper and the card disagree in several places:
   - Claude Opus 4 or Sonnet 4 wrote summary1;
   - mix1 was written by Claude, against "only gpt-oss-120b";
   - 160 or 156 BARC descriptions (BARC's README says 162 seeds);
   - 3,268 or 3,263 summaries;
   - 103,253 puzzles, or 47,337 + 55,886 = 103,223 in Table 1.
6. Why does mix10 have input programs but no outputs in the card?
7. Will the authors grant a licence? What is the downstream effect of Claude-generated rows?
8. How would ARC Prize 2026 rule L91 (open model and weights) interact with L95 (exemption for incompatible data)
   for a model trained on data of unknown licence?
9. Does Unsloth's patched inference return hidden states?
10. The synthetic dataset's size: the Kaggle field says 338 MB; the 13 October survey said 5.79 GB. They are not
    reconciled.
11. Is the 2026 hidden set the same as 2025's? Equal 27.64 scores suggest so; it is undocumented.

## 13. Sources (all accessed 2026-10-19)

**Web and API:**
- [R1] https://github.com/1ytic/NVARC; the API https://api.github.com/repos/1ytic/NVARC (`license: null`, created
  2025-11-13, pushed 2026-01-15); the commits and tree APIs (HEAD 846d0198efa752534594e321fc3289fc0a06c657,
  2025-12-13T15:02:38Z).
- [R2] Raw files at that commit, from https://raw.githubusercontent.com/1ytic/NVARC/846d0198efa752534594e321fc3289fc0a06c657/…:
  - `README.md` bc8bc639; `.gitmodules`;
  - `SDG/README.md` 8937972e;
  - `SDG/prompts/generate_puzzle_input.md` c3c66d76; `generate_puzzle_output.md` c24bd6ea; `mix_v1.md` 43252dce;
    `mix_v2.md`; `summary_v1.md`; `summary_v2.md` a8b02341;
  - `SDG/scripts/build_datasets.py` f683f8b5; `generate_input_grids.py` 307b4b6e; `generate_output_grids.py`
    c7bc28e4; `make_pairs.py` b2e6afa5; `parser.py` 68bb6703; `puzzle.py` eba67b62; `utils.py` 7c3b952e;
  - `ARChitects/sft_mg.yaml` 34abec38; `ARChitects/run_sft_4b.sh` f707a4e6.
  - The prefixes are sha256.
- [R3] `nvarc_2025.pdf` at that commit (sha256 946ebe53…, 11 pages): "NVARC solution to ARC-AGI-2 2025", Sorokin
  and Puget, November 2025.
- [K1] https://www.kaggle.com/c/arc-prize-2025/writeups/nvarc (title only), and Kaggle CLI
  `competitions topics show arc-prize-2025 651671`.
- [K2] https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/description (title only), and Kaggle CLI
  `competitions pages … --content`: Description, Code Requirements, Timeline, rules, Prizes.
- [K3] Kaggle CLI `competitions list -s arc-prize-2026`.
- [K4] ARC Prize 2025 rules, via Kaggle CLI `competitions pages arc-prize-2025 … rules`.
- [K5] The three datasets, via Kaggle CLI `datasets list`, `datasets files` and `datasets metadata`:
  - https://www.kaggle.com/datasets/sorokin/nvarc-artifacts-puzzles
  - https://www.kaggle.com/datasets/sorokin/nvarc-synthetic-puzzles
  - https://www.kaggle.com/datasets/sorokin/nvarc-augmented-puzzles
- [K6] https://www.kaggle.com/models/sorokin/qwen3_4b_grids15_sft139, via `models get` and
  `models instances get …/transformers/bfloat16`.
- [K7] https://www.kaggle.com/code/sorokin/nvarc-viewer, via `kernels pull -m` (read as text).
- [H1] https://huggingface.co/api/models/Qwen/Qwen3-4B-Thinking-2507, and its `config.json`.
- [H2] https://huggingface.co/api/models/openai/gpt-oss-120b
- [G1] The GitHub API `license` field for arcprize/ARC-AGI-2, michaelhodel/re-arc, victorvikram/ConceptARC,
  KSB21ST/MINI-ARC, xu3kev/BARC and Le-Gris/h-arc.
- [G2] https://github.com/Le-Gris/h-arc (README: CC0 1.0).
- [G3] https://github.com/xu3kev/BARC (README).
- [G4] https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- [A1] https://www.anthropic.com/legal/commercial-terms (effective 2025-06-17).

**Local files (read only):**
- `records/`:
  - `KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md`, `KAGGLE_NEURAL_V1_LOG_20261013.md`;
  - `CORA_QWEN_FUSION_FEASIBILITY_20261019.md`, `NVARC_CORA_COMPLEMENTARITY_AUDIT_20261014.md`;
  - `CORA_ARC_LEADER_METHOD_AUDIT_20261013.md`, `CORA_ARC_LEADER_SURVEY_20261013.md`;
  - `CORA_REASONING_V2_GAP_AUDIT_20261019.md`, `CORA_NEURAL_VIEW_GUIDANCE_RESULT_20261013.md`;
  - `README.md`, `RESUME.md`.
- Code:
  - `kaggle/neural_v1/`, `kaggle/neural_v1_smoke/upstream/`;
  - `cora_fhr/`, `cora_revision_v2/`, `cora_neural_fusion/`, `cora_neural_view/guides.py`;
  - `geocat_arc/object_reasoning/types.py`, `growth.py`;
  - `library.json`, `learned_verbs.json`, `outputs/kaggle_deploy/neural_v1_full_run1/*.json`,
    `outputs/kaggle_deploy/rules_20261012/`.

**Scratch copies** (untrusted data; nothing executed). Everything is under
`/tmp/claude-100350790/-deltos/d176233f-629a-4081-b493-4e2eb8db171a/scratchpad/nvarc_audit/`:
- `github_sdg_846d0198efa7/`, `paper_846d0198efa7/`;
- `meta_{synthetic,augmented,artifacts,model}/`, `kernel_nvarc_viewer/`;
- `kaggle_topic_651671/`, `comp2026_pages_20261019/`, `comp2025_pages_20261019/`;
- `artifacts_files.csv`, `synth_page1.csv`.

The three top-level files `build_datasets.py`, `sft_mg.yaml` and `run_sft_4b.sh` predate this audit (2026-10-13).
They were not used.
