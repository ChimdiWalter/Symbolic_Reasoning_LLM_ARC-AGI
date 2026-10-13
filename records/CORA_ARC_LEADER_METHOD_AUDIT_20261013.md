# CORA / ARC-AGI-2: leaderboard methods audit and competitive extension (2026-10-13)

**Status: COMPLETE (audit and plan).** Nothing was implemented or submitted.

The audit follows the user's directive of 2026-10-13. Nothing here changed
native_v1, the Kaggle submission, Step B, VDCG, the frozen pilot or any
historical P2/P3 result.

The full survey, with dated sources and evidence labels, is
`records/CORA_ARC_LEADER_SURVEY_20261013.md`. It was compiled by a delegated
web review; the NVARC contamination lines were re-verified independently.

**Evidence labels:**
- DOCUMENTED: the exact method behind that entry is disclosed;
- RELATED: the same team on another benchmark or in another year;
- INFERRED: no direct evidence;
- UNKNOWN: nothing public.

## 1. Leaderboard-method disclosures (as of 2026-10-13)

- **The top 10 have disclosed nothing: UNKNOWN.** That covers Tufa Labs
  88.06, rabbithole 80.56, Yi-Chia Chen 77.22, nvbanana 77.08, _hans 69.03,
  ALbert RUehlman 67.36, Dawid Kopiczko 66.25, Domdolus Tolus 65.14, ARC
  Raiders 64.58 and Majkel1337 62.08. The rules require prize artifacts in a
  Solution Writeup within 7 days of the 2 Nov deadline, so the methods should
  appear around 9 Nov. Nothing about the 77-88 entries is attributed to any
  method here.
- **Documented, Kaggle-eligible.**
  - NVARC 2025: 24.03 private, 27.64 public.
  - ARChitects 2025: 16.53 private, 21.67 public.
  - MindsAI & Tufa 2025: 12.64 private.
  - Public 2026 forks of the NVARC Qwen3-4B pipeline: 29-34 public (the
    survey's sources S5, S8 and S20).
- **The public board is the semi-private half; the private half decides.**
  In 2025 scores dropped 2.8-5.4 points from public to private.
- **The field moved fast.** About 3 teams were above 40 on 2026-09-09 and
  about 30 on 2026-10-13. The cause was not found (an INFERRED shared public
  trigger).
- **Symbolic and induction-only systems score about 0 on ARC-AGI-2** in
  every independent report found, consistent with CORA.

## 2. Tufa: ARC-AGI-3 vs ARC-AGI-2

- **ARC-AGI-3, DOCUMENTED.** "The Duck" harness: a local Qwen 3.6 27B FP8
  writes and runs Python in a REPL and sees grids as image plus text. Tufa
  reports that "hand-crafted tools actually hurt the model". It won ARC-AGI-3
  milestone 1 (2026-07-06).
- **ARC-AGI-2 88.06, UNKNOWN.** No method is public, and no statement was
  found that details will follow the deadline.
- **RELATED:** the 2025 MindsAI & Tufa ARC-AGI-2 entry (CodeT5-660M with
  test-time training and AIRV voting, 12.64 private).
- None of these is evidence for how the 88.06 was obtained.

## 3. NVARC and ARChitects 2025 (DOCUMENTED; details in survey section A3)

**NVARC.**
- Qwen3-4B-Thinking-2507 cut to a 16-token grid vocabulary, then full SFT
  (4x8 H100, 27 h) on about 3.26M samples: 103K LLM-written puzzles checked
  by execution, plus RE-ARC, ConceptARC, MINI-ARC and ARC-AGI-2 training.
- Per-task LoRA test-time training: r=256, about 128 augmented steps.
- Depth-first-search decoding, NLL rescoring under 8 augmentations; the two
  attempts are the top-2 by frequency plus log-probability.
- 4 independent L4 workers, about 12 GPU-minutes per task, 12 h.

**ARChitects.**
- A LLaDA-8B masked-diffusion model with 2D RoPE, as a 4-bit Kaggle file.
- 128 LoRA test-time-training steps.
- 102 recursive soft-mask refinement steps.
- A separate output-shape model, about 85% accurate.
- The two attempts are the two most-visited states.

## 4. Model-contamination findings (re-verified at NVARC HEAD 846d0198efa7, 2025-12-13)

- `SDG/scripts/build_datasets.py` L157: `pairs = data["train"] + data["test"]`.
  L249-250 build `arc2_evaluation6` from the ARC-AGI-2 evaluation files, so
  the evaluation **test outputs are included**.
- `ARChitects/sft_mg.yaml`:
  - training sets: arc2_training, mini, concept, rearc, nvarc_training,
    nvarc_full;
  - `val_dataset_path: arc2_evaluation6`;
  - checkpoints kept by `metric_name: val_loss` with `keep_top_k: 3`.
- `ARChitects/run_sft_4b.sh`: `EXP_NAME="qwen3_4b_grids15_sft139"`, the
  released model's name. Its `--config ./configs/sft_mg.yaml` is a different
  path from the repository file; that they are identical is UNVERIFIED.
- **The evaluation answers drove validation and checkpoint ranking, not
  gradient training.** Whether the released step was chosen by val_loss is
  UNVERIFIED.
- `nvarc_full` encodes all 120 evaluation tasks through their descriptions
  (the NVARC paper: "leaked").
- **Verdicts:**
  - COMPETITION-ELIGIBLE: yes. A public Kaggle model, Apache-2.0
    (`sorokin/qwen3_4b_grids15_sft139`, version 1, 7.27 GB, updated
    2025-11-02); no sign that hidden tasks were used.
  - CLEAN FOR SCIENTIFIC EVALUATION: no, on ARC-AGI-2 public evaluation. It
    is also not clean on ARC-AGI-2 training, which it trained on.
  - The ARChitects 2025 model is also unclean: it trained on ARC-2
    evaluation.
  - Clean neural options: VARC (ARC-1 training plus RE-ARC, MIT); CompressARC
    (no pretraining).
- The NVARC repository has no LICENSE file. The NVARC synthetic dataset's
  licence is "Unknown".
- **Consequence for CORA: no public ARC-AGI-2 split is clean for both a
  NVARC-derived model and CORA.** CORA was developed on the training set;
  NVARC trained on the training set and validated on the evaluation set.
  Clean measurements must use either the hidden Kaggle test (aggregate score
  only) or fresh synthetic tasks.

## 5. CORA's actual capability gaps

See the inventory in section 5 (part) below and the survey's section C.

| documented lever | CORA | gap |
|---|---|---|
| 10^5-10^8 ARC-like examples compressed into weights | hand-built typed DSL, seven views | missing (the main documented lever) |
| per-task test-time training | symbolic search plus capability construction | not comparable: CORA adapts symbols, not weights |
| answers in every attempt slot | certifies or abstains (126 of 240 stand-in tasks get no candidate) | high precision, no recall |
| agreement across augmentations | strict leave-one-out on programs | CORA is stronger on verification, the field's documented weak point (NVARC's correct candidates were "not always picked") |
| 4xL4 GPUs | CPU only | every documented scoring method is ruled out |
| output-shape model (ARChitects) | shape-change layers | not the dominant blocker (section 8) |

## 6. Ranked improvements (likely value x cost)

| rank | addition | track | expected effect | cost | risk |
|---|---|---|---|---|---|
| 1 | Reproduce ONE public neural baseline (the NVARC notebook) as a separate expert | Kaggle | public 29-34 if it reproduces (INFERRED from forks) | 2-5 days; L4x4 | dependency drift; runtime; quota (24 of 30 weekly GPU hours per full run) |
| 2 | CORA as an abstaining override in attempt 2 only (a certified program, consistent under D8 and colour transforms, that disagrees with both neural attempts) | Kaggle | 0 to +1 task | 1-2 days; CPU | very low |
| 3 | CORA as verifier and selector over neural candidates: search for a program mapping the demonstrations, and the test input to the candidate, then leave-one-out certify it ("transduction-guided induction") | science, and Kaggle | precision gain; 0 to +2 points | 1-2 weeks | runtime in parallel with the GPUs |
| 4 | Neural candidates as failure evidence: the diff between a stable neural candidate and CORA's nearest program localizes the missing capability, which is constructed and then verified | science | certified coverage on held-out generated tasks | weeks | needs a clean neural model (VARC-18M locally) |
| 5 | I-JEPA view ranking for the four-view cap | science | pending the CORA-NVG final run | in progress | 2 harms on development data |
| 6 | Mine NVARC's 103K executable puzzle programs as a capability library (nvarc_training only) | science | more coverage, after the deadline | 1-2 weeks | licence "Unknown"; contamination of nvarc_full |

**Not recommended for score:** a TRM ensemble (27.22 vs 27.22 in the NVARC
report) or plain 27B-model inference.

## 7. Separate plans

**Kaggle track.**
- Native_v1 stays frozen as the baseline.
- A new, separately versioned artifact reproduces the NVARC notebook:
  a private copy, attached to `arc-prize-2026-arc-agi-2`, internet off,
  L4x4.
- Only after it reproduces may the attempt-2 override be added, as its own
  version.
- No submission before an independent review of each version.

**Science track.**
- CORA-NVG finishes first (one final run).
- Then the verifier-selector and failure-evidence experiments, on clean
  models and fresh synthetic tasks.
- No claim from contaminated splits.

## 8. GPU and runtime needs

- **NVARC on Kaggle.** L4x4, 10-12 h for 240 tasks. A full commit run uses
  about 24 GPU-quota hours (the L4x4 double rate). The weekly quota is 30 h,
  resetting 2026-10-17. So at most about one full run per week, and a
  submission re-run uses no development quota (INFERRED; Kaggle documents
  re-runs as not counting).
- **Local 11 GB GPU.** Only for smoke tests (the 2B `sft141`, 2.82 GB) and
  for clean small models (VARC-18M). It cannot run 4B bf16 with r=256 LoRA
  test-time training (INFERRED).

## 9. Reproducible public-model baseline candidate

- Kaggle notebook `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue`,
  version 10 (run 2026-10-10).
- Model `sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1`.
- Utility kernel `sorokin/pip-install-unsloth-flash-patch`, version 2,
  holding the offline wheels: unsloth 2025.9.7, unsloth_zoo 2025.9.9,
  flash-attn 2.8.2+cu128torch2.8-cp311, numpy 2.2.6, scikit-learn 1.7.2,
  plus a patch to `unsloth/models/qwen3.py`.
- Tokenizer: Qwen3 cut to 16 tokens.
- **The smoke test checks:**
  - that the wheels match the 2026 image;
  - that the model loads on 4 L4s;
  - a 30x30 round trip through the tokenizer;
  - that the built-in 4-task self-test completes. This checks function only:
    those are contaminated evaluation tasks;
  - per-task seconds and peak memory;
  - submission schema validity, including the fallback writer;
  - the `KAGGLE_IS_COMPETITION_RERUN` path.

## 10. Two-attempt complementarity test (proposed, not run)

**No public split is clean (section 4).** The permitted measurements are:
- **(a) Fresh synthetic tasks.** The CORA-NVG generator families, which no
  model has seen. Per task, with labels only in the evaluator, measure:
  - symbolic-only, neural-only, both and neither exact;
  - combined pass@2;
  - wrong output sizes;
  - duplicate attempts;
  - compute.
- **(b) The hidden Kaggle test, aggregate only.** An A/B of two versions on
  separate days:
  - NVARC alone;
  - NVARC plus the CORA attempt-2 override.

  The difference estimates CORA's complementary contribution. It has low
  resolution: 1 task is about 0.8 points, and NVARC reports 1-2 points of
  run-to-run variation.

A selection policy is preregistered only if (a) supports one.

## 11. Neural representation-guidance experiment (CORA-NVG)

- Plan, literature and amendments 1-2:
  `records/CORA_NEURAL_VIEW_GUIDANCE_PLAN_20261012.md`.
- **Development results** (debugging only):
  - the frozen Qwen-1.5B guide was at or below the fixed-order fallback
    (B1 8 gains, 0 harms; Qwen C 3/2, D 1/0);
  - the authentic trace mostly raised abstention;
  - I-JEPA ranked useful views well (11 gains), but with 2 harms, and with
    choices identical under trace conditioning.
- The final split is being extended blind (the reference is running); one
  final run follows.

## 12. What would constitute genuine semantic invention

A real ARC task where:
1. the frozen reasoner fails;
2. permitted failure evidence identifies the limitation;
3. a machine-built, typed, executable extension is produced without answer
   leakage;
4. the unchanged reasoner using it passes full adaptive leave-one-out, with
   every fold re-derived independently;
5. the unseen output is committed before scoring and confirmed by an
   independent evaluator;
6. removing the extension removes the gain;
7. matched extra search does not explain it;
8. demonstration-only and shuffled-failure controls fail;
9. novelty is shown against an explicit bounded language.

None of this exists yet. A neural candidate turned into a verified program
(rank 3 or 4) counts only if steps 2-9 hold.

## 13. Scientific novelty relative to prior work

**Not novel:**
- neural guidance of symbolic synthesis;
- a proposer whose output a verifier certifies;
- repair from execution feedback;
- traces beating plain feedback;
- multi-view ARC;
- failure-triggered abstraction fallback;
- an LLM choosing abstractions from the task alone (KAAR: unsatisfactory);
- shuffled-feedback controls;
- test-time training;
- synthetic-data pretraining;
- augmentation voting.

**Possibly novel, and only if shown:**
- that authentic, typed failure evidence improves adaptation decisions
  against demonstration-only, shuffled and type-only controls at matched
  compute, with no new false acceptances;
- that strict leave-one-out program certification improves selection over
  neural candidates beyond augmentation agreement, on clean data;
- that a capability constructed from failure evidence is causally necessary
  and reusable.

## 14. Current Kaggle baseline status (verified 2026-10-13)

- **Submission 57144804.** Notebook
  `chimdiwalter/cora-native-v23-arc-agi-2-october-baseline` version 1;
  dataset `chimdiwalter/arc-native-baseline-v1` version 1.
- Submitted 2026-10-13T13:17:12Z. **Score PENDING.** No newer submission
  exists. The July submission 54617562 scored 0.00.
- **Expectation, stated before the score:** at or near 0%. The frozen v23
  baseline records 0 of 120 on the public ARC-AGI-2 evaluation set
  (`records/FRONTIER_AUDIT_SELECTION_RULE.md`,
  `records/KAGGLE_NATIVE_V1_DELIVERY_20261012.md`).
- **Public test set vs private.** The public leaderboard uses "a
  representative sample of the test data". The private leaderboard alone
  decides the final standing (rules, section 7). Winners are announced
  2026-12-04.

## 8 (part). Native gap audit on permitted data (`scripts/native_gap_audit.py`)

**Data:** the competition's visible stand-in `arc-agi_test_challenges.json`
(training pairs and test inputs only) and native_v1's own committed-run rows.
No answer was read.

**The stand-in is ARC-AGI-2 training data.**
- All 240 stand-in task ids are in the public ARC-AGI-2 training challenges
  (1,000 tasks), with identical training pairs. None matches any of the 120
  public evaluation tasks, by id or content.
- The data page's note ("a placeholder using tasks from
  arc-agi_evaluation-challenges.json") does not describe the file actually
  served.
- **So the committed run used tasks from the set CORA was developed on.** Its
  behaviour there is optimistic and does not predict the hidden score.

| shape rule implied by the demonstrations | tasks | certified (harness "solved": train-exact plus LOO; no answers were available to it) | no candidate |
|---|---|---|---|
| same size as input | 169 | 93 (55%) | 76 |
| one constant output size | 38 | 14 (37%) | 24 |
| other size change | 29 | 6 (21%) | 23 |
| scaled | 4 | 1 | 3 |
| **all** | **240** | **114 (47.5%)** | **126** |

- **Shape consistency.** Every produced candidate has the output size the
  demonstrations' rule implies (113 checkable outputs: 95 same, 17
  constant, 1 scaled). The native solver does not emit wrong-size grids. It
  emits nothing.
- **Output shape is not the dominant blocker.** 76 of the 126 no-candidate
  tasks (60%) keep the input size. Size-changing tasks are certified about
  half as often (21 of 71, 30%, against 55%).
- **Close misses.** In the no-candidate tasks the best near-solve fits a
  median 78% of training pixels, and 31% of them fit at least 90%.
- **Certifying layers:**
  - loo_replace 56;
  - adaptive_synthesizer 25;
  - object 9;
  - meta_reasoning 8;
  - adaptive_reasoner 5;
  - reasoning_v2 3;
  - spatial_reasoner 2, composable_reasoner 2, different_shape 2;
  - object_correspondence 1, geocat 1.
- **Not measurable from permitted data:**
  - correctness of any candidate;
  - wrong output dimensions among wrong answers (there are no answers);
  - missing global structure, diagonal relations, multi-object dependencies.

  These need a labelled permitted fixture: an ARC-AGI-2 training subset never
  used to tune v23, if one can be shown to exist, or a synthetic corpus.

## 5 (part). What CORA has, for the gap analysis

- **Object representation:** seven segmentation views (S1-S7), a four-view
  cap, cross-variant parsimony, correspondence and typed parameter classes.
- **Whole-grid representation:** pixel-rule and table layers (for example
  the leave-one-out `neighbor_pattern` lookup programs), a geocat layer, and
  a spatial reasoner. There is no learned whole-grid model.
- **Candidate generation:** the typed DSL search per layer; the
  object-reasoning partial is the second attempt.
- **Program synthesis:** symbolic. No neural prior is active in the sealed
  chain; GuideNet and the TRM are off by default.
- **Synthetic pretraining and test-time training:** none in the native
  solver.
- **Output-shape prediction:** shape-change layers (for example
  `different_shape`); no separate shape predictor.
- **Recursive refinement:** none.
- **Candidate ranking:** the parameter-class rank and winner key; no
  learned ranking.
- **Two-attempt selection:** attempt_1 is the certified render, attempt_2
  the best uncertified object partial, and the fallback is the test input.
- **Ensembles:** none across paradigms.
- **Independent verification:** train-exact plus adaptive leave-one-out
  certification. This is CORA's distinctive strength.
- **Compute:** CPU only, 4 workers, 4.03 h for 240 tasks on Kaggle. Kaggle
  offers L4x4 GPUs (96 GB); the native solver uses none.

## 15. Single next authorized implementation step

**A compatibility smoke test of the NVARC public notebook,** as a NEW private
Kaggle kernel, version-tracked in `kaggle/neural_v1_smoke/`:
- attached to the 2026 competition data, internet off, L4x4;
- self-test mode only (the 4 built-in tasks), with per-task time and memory
  logged;
- no submission.

Cost: an estimated 1-2 of the 30 weekly GPU-quota hours. Native_v1 and its
pending submission are untouched.

NEXT: ESTABLISH A REPRODUCIBLE NEURAL ARC BASELINE, MEASURE ITS INDEPENDENT COVERAGE RELATIVE TO CORA, AND TEST WHETHER FAILURE EVIDENCE ENABLES SAFER REPRESENTATION ADAPTATION.
