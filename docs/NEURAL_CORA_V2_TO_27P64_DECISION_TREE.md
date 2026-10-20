# Neural-CORA v2: the decision tree toward 27.64% (20 October 2026)

**27.64% is NVARC's score**, separately reproduced in CORA's frozen NVARC submission (57160429). It is NVARC's work,
not CORA's. Exceeding it with an original CORA-family solver is a **stretch target, not a plan with a promised
outcome**. This page says what would have to pass, in what order, and why the target is unlikely by 2 November.

## 1. Where things stand

| evidence | number | source |
|---|---|---|
| native CORA v23 on hidden ARC-AGI-2 (Kaggle) | **0.00%** | submission 57144804 |
| CORA-FHR on hidden ARC-AGI-2 | **0.00%** | submission 57354496 |
| CORA filling NVARC's empty second attempts, on the stand-in (ARC-AGI-2 training, contaminated for both) | adds **0** tasks, loses 1 | `records/NVARC_CORA_COMPLEMENTARITY_AUDIT_20261014.md` |
| tasks solved only by CORA on that stand-in | **0** | the same |
| v1 learned guide vs hand-designed order (synthetic) | 198 and 235 vs 358 of 395: G1 NO-GO | `records/NEURAL_CORA_V1_PILOT_REPORT.md` |
| the v1 language on dev60 (exposed, same-shape) | fits 1/60 | `records/NEURAL_CORA_V1_EXPRESSIVITY_AND_FAILURE_ATLAS.md` |
| native CORA on dev60 (exposed public training tasks) | fits 35/60; a correct candidate on 8; certified correct on 6 | `records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md` §2 |
| ncv2-g1 on dev60 | **not measured**: G2 is frozen and awaits authorization | the same |

**The arithmetic of the gap:**
- Exceeding 27.64% over two attempts needs a correct answer on more than about a quarter of the *hidden evaluation*
  tasks.
- Native CORA reaches a correct candidate on 8/60 (13%) of *public training* tasks, which are easier. Its hidden
  score is 0.00%.
- A learned guide can only reorder what the language expresses.

So no current route reaches 27.64% with an original solver by 2 November. The tree below is how that judgment could
change, gate by gate.

## 2. The tree

```
G2  dev60 language ceiling, ncv2-g1 vs ncv1-g0, native as reference
    (FROZEN: records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md; awaiting authorization; CPU only, at most 3.7 CPU-hours)
 |
 +-- NO_GO_STOP  (g1 pass@2 <= 1)
 |     -> No training. Record the expressivity gaps. The language is the bottleneck.
 |     -> Competition: the paper links an honest CORA code submission (it "need not achieve a high score").
 |
 +-- WEAK_EXPRESSIVITY_ONLY  (anything between)
 |     -> Extend ncv2-g1 where the diagnostics cluster (new grammar version, parity tests).
 |     -> Re-measure on a FRESH, predeclared, eligible cohort under a new protocol version, never dev60 again as evidence.
 |     -> No training.
 |
 +-- GO  (g1 fits >= 6, pass@2 >= 4, paired gains >= 3, losses <= 1)
       -> Write and freeze G1b (needs separate authorization).
          Stage A joint rule scorer over frozen Qwen object slots + correspondence evidence, trained on
          execution-verified synthetic ncv2-g1 programs. G1-CH (symbolic) is a first-class baseline.
       |
       +-- G1b NO-GO -> keep the symbolic G1-CH order; continue to G5 with symbolic search only
       +-- G1b GO    -> the learned joint guide enters the search
       |
       v
     G3  revision baseline: transparent rule-based controller vs failure-blind, try-all, shuffled-trace and
         matched-compute controls (spec: docs/NEURAL_CORA_V2_RELATIONAL_AST_AND_LOOP.md section 4). Optional by the deadline.
       |
       v
     G5  real ARC: extra exact correct predictions on a FRESH, predeclared, eligible development cohort,
         with no unacceptable harmed outputs. Paired against native CORA and against NVARC where both run.
       |
       v
     G6  Kaggle candidate: full offline rehearsal (runtime, integrity, licences, accuracy).
       |
       v
     The user approves the exact notebook version -> submission (the user's decision, never automatic).
```

**G4** (reusable capability, i.e. library learning) is off the critical path. It is proposed only after G5 passes.

## 3. Three routes to a competition number, ranked by honesty

1. **An original CORA or Neural-CORA solver** (the research goal).
   - Every gate above must pass.
   - The honest near-term outcome is a *non-zero* hidden score, which would itself be new for CORA (today 0.00%).
   - Exceeding 27.64% this way by 2 November is very unlikely.
2. **NVARC plus CORA** (an ensemble).
   - A score above 27.64% would come from NVARC's answers plus CORA's extras. It must be reported as "NVARC + CORA",
     with NVARC credited. It must never be reported as CORA beating NVARC.
   - Today it adds **0**: there are no CORA-only solves on the stand-in, and 0.00% hidden.
   - It needs a G5 pass with tasks CORA solves that NVARC misses.
   - **Licence risk:** the NVARC repository has no licence, and the notebook's and datasets' licences are
     unverified (`records/NEURAL_CORA_V2_PRIOR_ART_AND_GAP_20261020.md` C8). The 2026 rules require third-party code
     under an open-source licence that allows public sharing. This must be resolved before any prize-eligible
     submission contains NVARC code.
3. **Qwen emitting programs** (Stage B: new vocabulary rows, LoRA and grammar-constrained decoding).
   - It is behind G2 and G1b.
   - Training plus validation does not fit before 2 November alongside the gates.
   - It is post-deadline research.

## 4. The calendar

| date | what | Neural-CORA work allowed |
|---|---|---|
| 20 Oct | G2 frozen | the G2 run, **after authorization** |
| 21 Oct | poster print freeze | **no new scoring claims on the poster** |
| 23 Oct | Research Summit | only already-audited claims |
| 26 Oct | entry and team-merger deadline | — |
| 2 Nov, 23:59 UTC | code deadline (the time zone is not stated on arcprize.org; the project records use UTC) | only a G6-rehearsed, user-approved notebook |
| 8 Nov | paper | report every gate's outcome, failures included |

**Rough durations, if every gate passes the first time:**
- G2: about 2–4 h of wall time.
- G1b protocol, generator and Stage A training: about 3–5 days.
- G5 cohort selection and run: 1–2 days.
- G6 rehearsal: about 1 day (NVARC's own rehearsal took about 4.34 h).

So the GO path only just fits before 2 November, and only with no failed gate.

## 5. What is never done to reach the number

- No hidden outputs.
- No protected or sealed splits.
- No NVARC synthetic completion text.
- No changes to the native verifier to create certificates.
- No presenting NVARC's score as CORA's.
- No automatic submission.
- No Git push without the user's approval.
