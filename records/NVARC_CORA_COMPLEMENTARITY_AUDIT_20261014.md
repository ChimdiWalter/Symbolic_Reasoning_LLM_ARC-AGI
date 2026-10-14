# NVARC / CORA complementarity audit (2026-10-14, DEVELOPMENT; no submission)

**Question** (user directive "NVARC COMPLEMENTARITY AUDIT"). Can CORA raise the official 27.64
(NEURAL_TTT_BASELINE) without losing NVARC answers? The official baseline and its notebook are
unchanged.

**Code and outputs.**
- `scripts/nvarc_cora_complementarity.py`, which writes `outputs/complementarity/standin_paired.json`.
- The inputs are the two committed Kaggle runs' `submission.json` files: NVARC
  `neural_v1_full_run1`, and native CORA v23 `native_v1/kaggle_run_v1`.
- Answers come only from the pinned ARC-AGI-2 training solutions. They are used for scoring, never
  for selection.

## 1. NVARC's attempts (259 test outputs, 240 stand-in tasks; structural, no answers used)

| attempt_2 | positions |
|---|---|
| distinct genuine second candidate | 112 |
| empty placeholder `[[0]]` (upstream default) | 147 |
| identical copy of attempt_1 | **0** |

Every attempt_1 is genuine. The conservative slot is therefore the **empty** second attempt, not a
duplicate. NVARC's logs record no task-level confidence or disagreement score.

## 2. Paired correctness on the stand-in (contaminated for both systems)

The stand-in tasks are ARC-AGI-2 **training** tasks. NVARC's checkpoint was trained on that set, and
CORA's frozen library was built on it. This measures mechanics, **not** generalization.

| arm | test outputs correct (of 259) | task score |
|---|---|---|
| A: NVARC alone | 248 | 95.62 |
| B: native CORA alone | 47 | 18.33 |
| C: NVARC, with CORA filling only the empty second attempts | 247 | 95.42 |

**Paired breakdown:**
- solved only by CORA: **0**;
- solved only by NVARC: 201;
- solved by both: 47.

**What C changes:**
- C adds **0** outputs and loses **1**. The loss is task `239be575`, whose answer is the 1×1 grid
  `[[0]]`, which NVARC's empty placeholder matched by coincidence.
- CORA filled 146 of the 147 empty slots. 37 of those fills were correct, but every one was already
  solved by NVARC's attempt_1.

**CORA's claims:**
- precision 47 of 258 (18%);
- a certificate flag is not in the submission, so certificate-gating could only remove fills, not
  add gains.

**Runtime.** C would add native CORA's CPU run to the GPU notebook. The native committed run fit
within Kaggle's limit on its own; combining them is untested.

## 3. Unseen data

The official public scores are NVARC 27.64 and native CORA **0.00**, both over two attempts, on the
same semi-private half.
- A score of 0.00 means none of CORA's submitted answers was correct on any of those tasks.
- Arm C would therefore add exactly 0 there. It could lose placeholder coincidences like `239be575`.

## Verdict: NO-GO for a hybrid submission

- There is no measured complementarity: 0 CORA-only solutions on the paired development material,
  and 0 possible on the public half.
- What would change this:
  - a CORA component that is certified-correct on unseen tasks NVARC misses, measured fold-locally;
  - a contamination-free paired split, i.e. tasks that neither system's training touched.
- Neither exists today.
- Kept for later, not implemented: using NVARC outputs as untrusted hypotheses that CORA must explain
  (`records/CORA_NEURAL_CANDIDATE_EVIDENCE_PLAN_20261013.md`).
