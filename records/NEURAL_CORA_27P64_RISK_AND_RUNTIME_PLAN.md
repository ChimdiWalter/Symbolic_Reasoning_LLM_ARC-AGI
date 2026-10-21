# What it would realistically take to outperform 27.64%: risks and runtime (20 October 2026)

**Evidence, not optimism.** 27.64% is NVARC's public score, separately reproduced in CORA's frozen NVARC
submission 57160429. It is NVARC's work. The gate structure is `docs/NEURAL_CORA_V2_TO_27P64_DECISION_TREE.md`; this
record adds the arithmetic, the runtime budget and the risk register.

## 1. The size of the gap

**The target:**
- Two attempts per test output; the score is the mean over test outputs (arcprize.org, today).
- Exceeding 27.64% means more than about 28% of hidden test outputs exactly right.
- The 2025 hidden run covered 240 tasks in 12 h on 4 × L4 [NVARC paper]. For 2026, Kaggle offers L4x4 machines with 96 GB of GPU memory to this competition, at twice the GPU-quota rate (the official rules page saved on 12 October; corrected 20 October).

**Where CORA stands:**

| system | evidence |
|---|---|
| native CORA v23, hidden | **0.00%** |
| CORA-FHR, hidden | **0.00%** |
| native CORA, dev60 (public training tasks, which are easier and which CORA's library was built on) | a demonstration-fitting program on 35/60; a correct candidate on 8/60 (13%); certified correct on 6/60 |
| CORA filling NVARC's empty second attempts (stand-in) | +0 tasks, −1 (`records/NVARC_CORA_COMPLEMENTARITY_AUDIT_20261014.md`) |
| learned guide vs hand-designed order (synthetic) | 198 vs 358 of 395 (v1 G1 NO-GO) |

**What it would take:** CORA-executed answers correct on more than a quarter of *hidden* tasks. That is about twice
native's correct-candidate rate on *easier, seen* tasks, and native's hidden rate is zero.

**Inference:** no measured component closes that gap by 2 November.

## 2. Runtime budget (Kaggle: GPU or CPU notebook ≤ 12 h, no internet; rules fetched 2026-10-12)

| component | measured or estimated cost | source |
|---|---|---|
| NVARC full pipeline (test-time training + DFS + re-scoring) | about 4.34 h in CORA's rehearsal | `records/NEURAL_CORA_V1_27P64_COMPETITION_ROADMAP.md` |
| native CORA search | 17,642 CPU-s for 60 dev60 tasks (about 294 CPU-s per task) → about 4.9 h for 240 tasks on 4 cores | `outputs/funnel_v0/eval_dev60_native.json` |
| ncv2-g1 search @3000 | about 2 CPU-s per synthetic task; real tasks unmeasured (G2 measures it; cap 120 CPU-s) | the G2 selftest |
| Qwen forward pass for N2-A slots | 0.30 s per task (2080 Ti, fp16) | v1 |
| N2-A head inference | negligible (about 5–10 M parameters) | design estimate |
| N2-B grid decoding | NVARC-scale; without test-time training its grid quality is unknown | not measured |

**So, on runtime:**
- An N2-A-guided CORA solver fits easily.
- CORA plus the full NVARC pipeline is roughly 9–10 h, which is feasible but tight given runtime variance.
- That combination has so far added 0 tasks.

## 3. Risk register

| risk | likelihood | effect | mitigation | stop rule |
|---|---|---|---|---|
| **coverage**: ncv2-g1 still misses most real transformations | high | caps every learned component | G2 diagnostics; native-exposure increments by measured gap | G2 NO_GO_STOP → no training |
| **Qwen adds nothing beyond hand features** (as in v1) | medium–high | no neural contribution | arm 2 vs arm 3 control | G1b-Qwen NO-GO → no Qwen training |
| **selection**: fits are often wrong (27/60 native FIT_BUT_ALL_WRONG) | high | low pass@2 despite coverage | keep demonstration-equal, test-different alternatives; calibrate on permitted episodes | report coverage and pass@2 separately |
| **over-strict certification** gives zero predictions | medium | 0.00%, as before | two attempts always filled from the best fits, labelled by epistemic status | — |
| **contamination**: no clean local real-ARC validation of Qwen arms | certain | local real-ARC numbers prove nothing for Qwen | synthetic held-out families; the hidden score is the only clean real test | never call local results "unseen" |
| **licence**: NVARC notebook and repo code unlicensed or unverified | high, if reused | prize ineligibility | write own decode and adaptation code; reuse only the Apache-2.0 checkpoint | no NVARC code in a CORA prize entry until cleared |
| **hardware**: bf16 unsupported locally; no bitsandbytes or peft | certain | local adaptation needs fp16 or NF4 setup | separate venv; a 10-minute NF4 smoke test after 21 October | stop if the smoke test exceeds 10 GB |
| **schedule**: 13 days to the code deadline | certain | gates may not finish | one gate at a time, in order | no submission without G6 and the author's approval |
| **Kaggle quota**: 1 submission per day; L4x4 counts double against the 30 h weekly GPU quota | certain | few full rehearsals | CPU-only rehearsals where possible | — |
| **deadline mismatch** for the paper (arcprize.org 8 Nov; Kaggle paper track 9 Nov 23:59) | — | — | plan for 8 November | — |

## 4. Realistic outcomes by 2 November

1. **Most likely:** CORA's paper reports the gates honestly. The linked Kaggle code submission "need not achieve a
   high score" (2026 paper rules). A non-zero hidden score from an original CORA-family solver would be a real step
   (today 0.00%).
2. **If G2 and G1b both pass early:** an N2-A-guided CORA notebook could be rehearsed (G6) and, with the author's
   approval, submitted. Its expected hidden score is low single digits at best, from the dev60 rates above.
3. **Exceeding 27.64%:** only through an official public score. Any NVARC-model involvement would be credited, and
   it is not expected this cycle.
