# Startup hypothesis (one page): a reliability and experimental-verification layer for biological prediction models

**Status: HYPOTHESIS. BIOLOGICAL APPLICATION: UNTESTED.** Nothing here has
been validated on biological data.

## The problem

Models that predict how cells respond to genetic or chemical perturbations
are proliferating. Their predictions are cheap, but the experiments that
check them are slow and expensive. Teams cannot tell which predictions rest
on supported structure and which on memorized coincidence. That is the same
failure CORA measures on ARC, where 27 of 60 development tasks were fitted
by memorizing programs that did not generalize.

## The product hypothesis

A layer that sits on top of an existing prediction model and, for each
prediction:
1. **audits** whether the model's explanation is supported by the training
   evidence, or only fitted;
2. **diagnoses** the unsupported part: which interaction, response rule or
   assumption;
3. **proposes** a bounded, typed correction, and tests it by fold-local
   reconstruction on held-out perturbations;
4. **abstains or flags** when the evidence does not determine the answer,
   and states what experiment would resolve it;
5. **records provenance**, so every claim can be re-checked.

The first product is **prediction assurance and experimental
decision-support**: ranking which predictions to trust before a lab commits
resources. Autonomous correction is the research extension, not the initial
promise.

## Initial application

Auditing cellular perturbation predictions, for example single and combinatorial
gene perturbations measured by Perturb-seq, before follow-up experiments.

## What exists today (ARC only)

- **The contract is implemented:** prediction, failure evidence, diagnosis,
  typed correction, reversible installation, fold-local validation,
  abstention and provenance (`docs/CORA_REPAIR_VERIFY_CONTRACT_v1.md`).
- **On real ARC development tasks:** the verifier certified 6 answers with 0
  false certifications, and the funnel located the dominant failure.
- **On synthetic development tasks:** one end-to-end constructed correction
  was certified and correct. A failure-blind control matched it, so the
  value of the failure record specifically is not yet shown.

## Minimum biological validation before any claim

1. Held-out perturbations, split by perturbation, never by cell.
2. Independent cohorts or cell states, without refitting.
3. Negative controls:
   - matched extra fitting;
   - failure-blind corrections;
   - shuffled failure records.
4. Calibration: certified predictions must be measurably more accurate than
   uncertified ones.
5. A false-correction rate: corrections accepted but wrong on held-out data.
6. Uncertainty and abstention rates, reported alongside accuracy.
7. Only then a small, preregistered prospective wet-lab test.

## Risks

- Biological "explanations" are less constrained than ARC programs.
- Measurement noise can fail correct corrections and pass wrong ones.
- Third-party model and code licences must be cleared before a product.

The ARC work is evidence about the method's mechanics, not about biology.
