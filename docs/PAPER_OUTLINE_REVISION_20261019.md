# Paper outline: reorganized around construct, diagnose, revise (DRAFT 2026-10-19)

- **For:** the ARC Prize paper award (deadline 2026-11-09 23:59 UTC, per the Kaggle listing). It reorganizes `docs/PAPER_SKELETON.md`; it does not
  replace it.
- **Rule:** every number comes from `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md`, cited by row.

**Working title:** *When a Hypothesis Is Not Enough: Constructing, Diagnosing and Revising Executable Hypotheses on
ARC-AGI-2*

**Thesis.** Three achievements are routinely conflated:
1. **constructing** an executable hypothesis that fits the demonstrations;
2. **diagnosing** why a fitting (or failing) hypothesis is not enough: representation, rule, evidence or resources;
3. **learning a revision** that improves independently tested predictions.

CORA makes all three executable and measurable against matched controls. The evidence:
- (1) shown in narrow forms;
- (2) partly shown;
- (3) not yet shown.

The paper reports where it is not.

## 1. Introduction

- Fitting is not explaining. Running example: several programs fit every demonstration and disagree on the test.
- The three achievements and the claim ladder.
- What is **not** claimed:
  - no unseen-task accuracy;
  - no autonomous grammar invention;
  - the NVARC score is not CORA's.
- Toni's broader question: representation induction, grammar induction, failure diagnosis, and transfer across
  semantic domains.

## 2. Setting and evidence discipline

- ARC-AGI-2, Kaggle constraints, two attempts.
- Evidence tiers: synthetic, real development (exposed), forensic (evaluator-only), untested.
- Protected splits and Step B's separation, including the cohort-eligibility limitation
  (`records/CORA_REASONING_V2_COHORT_AUDIT_20261019.md`).

## 3. Constructing executable hypotheses

- Native v23: search plus leave-one-out re-induction (ledger 1–5).
- The G-grow grammar and CORA-FHR construction (ledger 7–8, 12c).
- **v2, the version-space reasoner:** a hypothesis is (representation, geometry, colour policy). It keeps every
  consistent hypothesis and abstains on disagreement (gap audit, section 7; smoke results).

## 4. Diagnosing inadequacy

- **Failure funnel:** memorization dominates. A correct candidate is absent on 48 or more of 60 tasks (ledger 1–3; gap
  audit, section 5).
- Root-cause autopsy and re-extraction (ledger 12, 12b).
- Forensic expressibility ceiling: 50 of 58 inexpressible in the single-expression class (ledger 12g).
- **The typed diagnosis interface** (`cora_revision_v2/diagnosis.py`). Each diagnosis records the symptom, competing
  causes, a bounded probe, its result, what stays uncertain, and the next action.
- **Case study, 00dbd492:**
  - a correct but uncertified prediction;
  - the fold fragility is a single-demonstration table entry the test needs, i.e. insufficient evidence;
  - it is not ambiguity, representation or a defect;
  - a failure-blind reasoner gives the same answer
  (`records/CORA_REASONING_V2_FOLD_FRAGILITY_00dbd492_20261019.md`).
- Engineering distribution of diagnoses on the exposed tasks: from `eval_*_eng.json` when complete.

## 5. Revising: what has and has not worked

- Constructed operators and the failure-blind controls that match them (ledger 9–11).
- Guarded revision: one real solve that does not generalize, 0 of 58 (ledger 12c, 12d, 12f).
- The hand-designed controller: negative (ledger 12e).
- **Phase 2 design** (`records/CORA_REASONING_V2_PHASE2_PROTOCOL_20261019.md`):
  - authentic diagnosis vs strong failure-blind, matched-compute and shuffled-diagnosis revision selection;
  - GO and causal gates;
  - status (not run).

## 6. Verification and the two prediction tiers

- Certification is unchanged: unique, rebuilt in every fold, no tie.
- Exploratory (uncertified) predictions are kept separate and tiered by fold-failure type.
- Two-attempt accounting: how the tiers could map onto Kaggle attempts. Not submitted.
- **Kaggle entries:**
  - native 0.00;
  - CORA-FHR 0.00;
  - the NVARC reproduction, 27.64, is not CORA (ledger 13–16).

## 7. Transfer across semantic domains (proposed)

- What could transfer: the revision policy and the verification interface, not ARC operators (ledger 17).
- The biological problem contract with Pierce and Toni. **BIOLOGICAL APPLICATION: UNTESTED.**

## 8. Related work

- Learning from failures (Popper; Cropper and Morel).
- Library learning (DreamCoder; LILO).
- Model inadequacy and experiment design (Model Discovery Agent).
- Version spaces (Mitchell).
- ARC program synthesis.

## 9. Limitations

- Exposed tasks and in-sample engineering.
- Small denominators.
- A researcher-designed language expansion is not grammar induction.
- Step B membership is unverifiable without protected material.

## 10. Conclusion

Constructing, diagnosing and revising are different achievements. CORA measures each, and so far shows where
learning a revision has **not** yet been demonstrated.

## Figures (data-derived only)

1. The failure funnel (existing).
2. The synthetic witness (existing).
3. The real guarded witness (existing).
4. **New:** the v2 00dbd492 panel, with the demonstrations, test, uncertified prediction and fold table.
5. The diagnosis distribution, after the engineering run.
