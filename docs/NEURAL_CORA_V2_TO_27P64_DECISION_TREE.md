# Neural-CORA: the decision tree toward 27.64% (updated 20 October 2026, after G2)

**27.64% is NVARC's score**, separately reproduced in CORA's frozen NVARC submission (57160429). It is NVARC's work,
not CORA's. Exceeding it with an original CORA-family solver is a **stretch target, not a plan with a promised
outcome**.

## 1. Where things stand

| evidence | number | source |
|---|---|---|
| native CORA v23, hidden ARC-AGI-2 (Kaggle) | **0.00%** | submission 57144804 |
| CORA-FHR, hidden | **0.00%** | 57354496 |
| CORA added to NVARC on the stand-in | **+0**, −1 | `records/NVARC_CORA_COMPLEMENTARITY_AUDIT_20261014.md` |
| v1 learned guide vs hand-designed search (synthetic) | 198, 235 vs 358 of 395: **G1 NO-GO** | `records/NEURAL_CORA_V1_PILOT_REPORT.md` |
| **G2: ncv2-g1 on dev60 (exposed)** | **1/60, the same task as v1: NO_GO_STOP** | `records/NEURAL_CORA_V2_G2_REPORT.md` |
| native CORA on dev60 | 35 fits; 8 correct candidates; 6 certified | the same |
| ncv2-g2 (capability recovery), DEV synthetic families | 10/10 pass@2 vs ncv2-g1's 1/10, engineering only | `records/NEURAL_CORA_V2G2_CAPABILITY_RECOVERY_REPORT_20261020.md` |

**The arithmetic:**
- Exceeding 27.64% means a correct answer on more than about a quarter of hidden test outputs.
- Native CORA reaches a correct candidate on 13% of easier, seen tasks, and scores 0.00% hidden.
- For a program-only solver, **pass@2 ≤ correct-candidate coverage**. A better ranker cannot add an answer that no
  candidate produces.

## 2. The tree

```
G2 = NO_GO_STOP (final). The binding constraint is candidate GENERATION, not ranking.
 |
 v
Capability recovery: ncv2-g2  [IMPLEMENTED, unit-tested; engineering only]
  native reduction / generative classes + a generator completed over compiled constructs
 |
 v
Synthetic coverage study (FROZEN: records/NEURAL_CORA_V2G2_SYNTHETIC_PROTOCOL_20261020.md; NOT RUN; needs authorization)
 |
 +-- NO_GAIN        -> more generator work. No real-ARC claim. No training.
 |
 +-- GO_ENGINEERING -> propose a permitted real-ARC cohort (eligibility-checked; needs authorization)
        |
        v
      Real-ARC coverage vs native and ncv2-g1 (development evidence, not unseen)
        |
        v
      Qwen interface A: joint proposals of references, parameters and classes OUTSIDE the symbolic candidate set
        (residual over C+H; controls: C+H, hand-only, Qwen-shuffled, untrained)
        |
        v
      Qwen interface B: neural evidence -> sketches and constraints, with causal ablations
        (docs/NEURAL_CORA_V2_QWEN_EVIDENCE_TO_PROGRAM_SPEC.md)
        |
        v
      G3: observable-failure revision vs failure-blind, shuffled, try-all and matched-compute controls
        |
        v
      G5 (fresh eligible cohort) -> G6 (full offline Kaggle rehearsal) -> the author approves the exact notebook
```

## 3. Which mechanism could answer what current CORA and strong symbolic search both miss?

- **More symbolic recovery caps at native's reach.** Exposing every native class and operator lets ncv2-g2 match
  native, but no more: 6/60 certified on exposed dev60, 0.00% hidden. It is necessary, not sufficient.
- **Mechanisms that can exceed native:** those that propose hypotheses no hand-written generator contains.
  1. **Interface B: neural-to-symbolic construction.** Qwen's grid knowledge, which is the source of NVARC's
     27.64%, is turned into constraints and sketches that CORA completes and verifies. This is the only route that
     brings that knowledge inside an executable explanation.
  2. **Interface A: learned proposals of references and parameters**, conditioned on aligned Qwen object states.
  3. **Program-conditioned neural operators**, invoked by a CORA program under typed constraints. They are reported
     as neural-assisted, never as certified.
- None is implemented. Each needs a frozen protocol, and each must beat C+H plus a hand-feature control.

## 4. Two objectives, kept separate

**Path A (competition): maximize the hidden score.**
- Preserve the NVARC-derived predictive capacity, using CORA's own decode code and the Apache-2.0 checkpoint.
- Add CORA program-conditioned constraints and reranking only where they win paired gains over losses.
- Credit it as **NVARC-checkpoint-assisted**.
- Risk: requiring a program for every output could destroy the 27.64% strength.

**Path B (science): an original executable reasoner.**
- Every answer comes from a CORA program.
- Qwen guides construction and revision.
- This is the clearer scientific claim, but today's coverage makes 27.64% unrealistic near-term.

**Never** present a competition-driven neural predictor as evidence of CORA's reasoning.

## 5. Calendar

| date | what |
|---|---|
| 21 Oct | poster print freeze: no new scoring claims |
| 23 Oct | Research Summit: verified results only (the guarded-rule demo is an offline recorded replay) |
| 26 Oct | entry and team-merger deadline |
| 2 Nov, 23:59 UTC (Kaggle) | code deadline: only a G6-rehearsed, user-approved notebook |
| 8 Nov | paper (arcprize.org); the Kaggle paper track lists 9 Nov 23:59 |

**Kaggle hardware:** L4x4 with 96 GB of GPU memory, a 12 h limit and no internet (the rules saved on 12 October).

## 6. Never done to reach the number

- No hidden outputs.
- No protected or sealed splits.
- No NVARC synthetic text or unlicensed NVARC code.
- No changes to the native verifier to create certificates.
- No presenting NVARC's score as CORA's.
- No automatic submission.
- No push of the unpublished maize crop.
