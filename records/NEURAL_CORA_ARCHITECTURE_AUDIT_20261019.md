# Neural-CORA architecture audit, Phase 0 (19 October 2026)

**Status:** an audit and a decision record, not a result. It answers the user's Neural-CORA v0.1 directive (section 2)
and the "CONTINUE FROM OCTOBER 19 CHECKPOINT" instruction (Priority 2).

**Sources:**
- the read-only NVARC audit `records/CORA_NVARC_SUBSUMPTION_AUDIT_20261019.md`, cited as SA §n;
- the code paths cited below;
- the probes run today.

## 1. Verified state (19 October, about 19:30Z)

| item | state |
|---|---|
| git | HEAD ede7d35 (then this work). The user's own untracked files `CORA_Research_and_Summit_Package_2026-10-17.zip` and `voice_note/` are untouched |
| Phase 2a | **DONE, NO-GO** under the frozen rule (`records/CORA_REASONING_V2_PHASE2A_EXECUTION_20261019.md` §4). Nothing of this repository is running |
| Step B | its 20 workers keep running in their own repository. This work does not read, touch or load them |
| GPUs | 2 × RTX 2080 Ti, 11 GB each, Turing (fp16, no bf16). GPU 0 is free. GPU 1 holds about 2.5 GB for a process this user cannot see, so it is left alone. A brief GPU job of the user's (`f2_runner.py`) finished before any use here |
| CUDA | driver 13.0; torch 2.11.0+cu128 in `.venv_arc2026` and `~/.venvs/lesegenv`; transformers 4.57; no `peft` (none is needed: section 8) |
| memory | 125 GB RAM, 8–15 GB free under the shared load. Model shards are memory-mapped straight to GPU 0 |
| disk | `/deltos` 4.5 TB free (95 % used); `/` 76 GB free |
| checkpoint cache | before today only Qwen2.5-1.5B-Instruct was cached, from CORA-NVG. **Downloaded today:** `sorokin/qwen3_4b_grids15_sft139` v1 (Apache-2.0; 7.27 GB; the public Kaggle model) into `outputs/neural_cora_v0/models/` (gitignored) |
| probe | fp16 on GPU 0: load 56 s; 3.63 B parameters; one 651-token forward pass 0.22 s; peak 7.9 GB; all 37 hidden layers finite (middle-layer maximum 13,944, inside fp16 range) |

## 2. Qwen interfaces (SA §6, §7)

- **What the NVARC notebook exposes:** token logits, candidate scores (`beam_score`, `score_aug`) and `calc_scores`
  for any grid. It can create, reset and train a LoRA per task (Unsloth/PEFT).
- **Hidden states** are never used there. Plain transformers returns them (`output_hidden_states=True`), verified
  today.
- **The vocabulary is 16 tokens:** digits, newline, user, assistant and the chat specials. **The checkpoint cannot
  emit program text.**
- **What NVARC's per-task adaptation optimizes:** next-token cross-entropy on the output grids of every demonstration,
  over 128 augmented copies (8 dihedral × 16 colour permutations).
  - 1 epoch, AdamW 5e-5.
  - It is **not leave-one-out**: every demonstration is both context and target.
  - It never supervises program choice.
  - **Reusable without misattribution:** the input format, the augmentations and the reset-and-train loop.
- **What Neural-CORA v1 reuses:** only the frozen checkpoint, as a demonstration encoder, in NVARC's own chat format.
  Every trainable weight is new and ours.

## 3. What CORA can already execute, and what it cannot

| transformation | native v23 (`geocat_arc/object_reasoning`) | CORA-v2 | note |
|---|---|---|---|
| recolour | RECOLOR, with colour expressions (`const`, `color_map`, `feature_map`, `feature_affine`) | colour policies on additions only | executable |
| deletion | DELETE; default DELETE | `tst` keep/delete/recolour (integration pending) | executable |
| movement | TRANSLATE (const, `slide_vector`, `vector_to`, `align_vector`, mirror/reflect vectors), MOVE_TO, MOVE_UNTIL_ADJACENT | — | executable |
| additive lines | FILL_LINE (axis, colour, to_border/to_object) | G-grow growth only | **executable but never induced**: no inducer code builds FILL_LINE (grep, 19 Oct) |
| object parts | COPY_PART, EXTRACT_PART; multicolour views S3/S4/S7 | native parts fully explain 2 of 22 partly changed objects (`records/CORA_REASONING_V2_TYPED_TRANSFORM_SLICES_20261019.md` §5) | weak |
| mixed colours | multicolour views, PAINT | — | partial |
| scaling and resizing | SCALE, CROP_TO, output specs | none: same size only | partial |
| sequential composition | first-match rules; ComposedProgram (re-segment, then a further stage); Overlay; Framed | `tst` two stages | executable |
| complex relations | `relation_exists`, RefExpr (nearest, containing, …) | — | partial |

**The bottleneck is induction, not the executor.**
- On 48 or more of 60 development tasks, native never generated a correct candidate (failure funnel).
- In Phase 2a, 33 of 40 tasks had no v2 hypothesis (GEOMETRY_GAP), and native certified 6.
- Probes today show native fitting demonstrations with incidental parameters: a recolour driven by an
  `aligned_col_count` feature map; a translation by `gap_to_nearest_col`.
- So a learned prior can be useful only as a better *proposal order* over programs the executor already runs.
- The audit estimates that native's typed vocabulary covers about 5–15 % of NVARC's synthetic puzzles (SA §2.6).

## 4. The legal and technical boundary (SA §3–4)

| thing | status | use here |
|---|---|---|
| checkpoint weights | Apache-2.0 | used frozen. Attribution: the NVARC team. Not redistributed (the public Kaggle model can be attached) |
| NVARC Kaggle notebook code | deemed OSI-licensed by the 2025 competition rules | not used by Neural-CORA v1 |
| NVARC GitHub code | **no licence** | read and cited only. Nothing is copied |
| NVARC datasets (synthetic, augmented, artifacts, programs) | **"unknown"**, plus the Claude-rows flag | **not used.** No supervision is drawn from them |
| new adapter (head) weights | ours; a derivative only in being trained on frozen Apache-2.0 features | publishable, because the training data are CORA's own generator |

## 5. Program-data provenance and contamination

**NVARC programs:**
- They are LLM-written Python (gpt-oss-120b), with seeds covering all 1,000 public training and all 120 public
  evaluation tasks.
- The evaluation outputs ranked checkpoints (SA §5).
- So they are unusable for clean supervision now. A licence request to the authors and a sandbox would come first.

**Neural-CORA v1 supervision:**
- It comes from CORA's own typed generator (`cora_neural_v1/generator.py`). Native `render_program` executes every
  program, so all programs are execution-validated.
- There is no third-party data and no ARC task content.
- **Contamination of the encoder:** it saw public ARC training and evaluation material. That is irrelevant for
  synthetic tasks, and it makes **every public real ARC split contaminated** for any claim made with this encoder:
  DEV 60, HOLDOUT 60, Step B's partitions and the Phase 2a cohort. Real-task numbers would be engineering only.

## 6. The earlier CORA-NVG negative, and why v1 is not that experiment

CORA-NVG (`records/CORA_NEURAL_VIEW_GUIDANCE_RESULT_20261013.md`):
- a frozen, prompted Qwen2.5-1.5B (and a frozen I-JEPA) ranked native's 7 segmentation views on a private synthetic
  split;
- the fixed-order fallback got 35 of 35 warranted decisions;
- Qwen with demonstrations 19; with authentic failure traces 1, the same as with shuffled traces. Rejected.

| | CORA-NVG (rejected) | Neural-CORA v1 prior |
|---|---|---|
| learning | none: frozen, prompted | gradient-trained heads on encoder features |
| what is chosen | 1 of 7 views. The fixed order was optimal by construction in the only family with warranted decisions | an order over about 16,000 one-rule and about 18 million two-rule typed programs. No fixed order can be optimal for both single rules and compositions |
| supervision | none | extensional, execution-derived component targets |
| failure traces | the tested ingredient (H1), which hurt | **not used**. Revision control is deferred until proposal learning works |
| outcome measured | view admission | demonstration-consistent programs found within a budget, and exact test predictions (pass@2), against matched symbolic search |
| controls | fixed order, random | C+ (Occam, 2× budget), C+H (hand-designed delta analysis, 2× budget), L0 (untrained), L0s (shuffled targets), L1h (the same heads on hand features), C0 (native inducer) |

If the learned prior does not beat C+ under matched resources, the pilot records NO-GO and the bottleneck. It is not
rerun under another name.

## 7. Resource commitments

- **CPU:** at most 2 worker processes at nice 10, replacing Phase 2a's finished 2-worker footprint. Step B and the
  user's other jobs are untouched.
- **GPU:** GPU 0 only, for encoder features (about 0.25 s per task) and head training (seconds). The pilot is far below
  its 6 h cap.

## 8. Architecture decision: one initial executable path

**Chosen path: a learned typed program prior that orders CORA's own search.** One inference algorithm, owned by CORA:
1. **State:** CORA's typed hypothesis space `ncv1-g0`.
   - native segmentation view (7);
   - 1–2 first-match rules, each = selector (31) × native action (93): keep, delete, recolour, translate, slide,
     fill_line (additive), reflect;
   - default keep or delete.
2. **Shared pruning** of the domains from the demonstrations (`space.domains`), the same for every arm.
3. **Learned prior:** frozen NVARC Qwen3-4B encoder features, then the trained heads. The output is component
   log-probabilities (`prior.head_scores`).
4. **Best-first enumeration** of whole programs (`space.enumerate_programs`).
5. **Fixed native interpreter:** each candidate runs on the demonstrations (`interp.fit`). Every consistent program
   predicts the test.
6. **One selection rule** for every arm: attempt 1 is the first consistent prediction; attempt 2 is the next distinct
   one. Certification is unchanged and reported separately.

Qwen supplies a trained proposal distribution. CORA owns representation, search, execution, evidence, selection and
the two attempts. No neural grid reaches an attempt.

**Rejected alternatives, and why:**
- Free-form program decoding from the NVARC checkpoint: impossible, because of the 16-token vocabulary.
- Free-form decoding from base Qwen3-4B: it needs new tokens and fine-tuning beyond the pilot budget. Deferred.
- Supervision from NVARC's programs: unlicensed, contaminated and untyped Python.
- Neural view ranking: the rejected CORA-NVG. Not repeated.
- Answer-level fusion, routers and second-attempt fillers: excluded by the directive.
- A learned revision controller now: deferred until proposal learning works (the user's Priority 3).
- LoRA on the encoder now: not needed for the first test. If the heads-only prior fails, LoRA is a later, separately
  registered step.

**Protocol:** `records/NEURAL_CORA_PILOT_v0_PROTOCOL.md`, frozen before the scored run.
