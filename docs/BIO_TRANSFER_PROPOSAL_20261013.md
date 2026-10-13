# CORA for scientific prediction: a transfer hypothesis (one page)

**Status: FUTURE APPLICATION. BIOLOGICAL APPLICATION: UNTESTED.**

No biological transfer has been established. Nothing CORA does on ARC is
evidence that it works on biological data. This page states the hypothesis
and the experiments that would test it. No biological experiment or
repository is involved.

## The idea

CORA is built around one loop:
1. a reasoner commits to an executable explanation;
2. it detects that the explanation fails;
3. it diagnoses which component is insufficient;
4. it makes one specific change;
5. it accepts the change only if independent, held-out verification
   confirms it.

Perturbation biology has the same structure. A model predicts how cells
respond to a genetic or chemical perturbation; most predictions are never
tested; experiments are expensive. A system that flags which predictions are
unsupported, and proposes a checkable correction, would decide where wet-lab
effort goes.

## The loop, translated

| stage | in perturbation prediction |
|---|---|
| **Input** | A model's predicted response, e.g. an expression change after a gene knockdown or a drug in a given cell line. The model is any predictor: an additive baseline, a graph model, a foundation model |
| **Failure signal** | Three kinds:<br>- a discrepancy with held-out measured responses;<br>- an inconsistency with stated constraints, e.g. replicate agreement, dose monotonicity, or a double perturbation implied by its singles;<br>- an explanation that relies on a relation the data do not support |
| **Diagnosis** | Which part is insufficient:<br>- the representation: gene modules, cell-state features;<br>- a relation: a missing or wrongly signed pathway edge;<br>- the combination rule: additive vs. epistatic for double perturbations;<br>- calibration |
| **Adaptation** | One typed, executable correction: a new module grouping, a pathway relation, or a combination operator. It is stated so that it can be re-derived without the held-out data |
| **Verification** | Four checks:<br>- held-out perturbations, never seen when the correction was built;<br>- leave-one-perturbation-out reconstruction (the analogue of CORA's leave-one-out by re-induction);<br>- an independent dataset;<br>- calibrated uncertainty, with abstention when the evidence is insufficient |
| **Value** | A ranked, auditable list of which predictions to trust before an experiment is run |

## What would have to be shown, in order

1. **A retrospective benchmark.**
   - Use public Perturb-seq data, e.g. CRISPRa double perturbations (Norman
     et al. 2019) and genome-scale screens (Replogle et al. 2022).
   - Split by perturbation, not by cell.
   - The question: do failure-typed corrections improve held-out error over:
     - the base model;
     - matched additional fitting with the same compute;
     - failure-blind corrections;
     - corrections driven by shuffled failure evidence?

   These are the same controls as CORA's ARC experiments.
2. **Certification value.** Predictions the verifier certifies should be
   measurably more precise than those it does not. Abstention rates must be
   reported.
3. **Transfer.** The corrections must hold on an independent dataset (a
   different lab or cell line) without refitting.
4. **Prospective validation**, only after 1–3: a small, preregistered wet-lab
   test of certified vs. uncertified predictions.

## Risks, stated now

- Biological "explanations" are far less constrained than ARC programs.
- Measurement noise can make a correct correction fail verification, and a
  wrong one pass it.
- On ARC the analogous verifier is conservative in a specific, measured way
  (see `records/CORA_FAILURE_FUNNEL_20261014.md`). That behaviour must be
  re-measured in biology, not assumed.

**Levels of evidence, kept separate:**
1. benchmark performance (Kaggle);
2. a reasoning contribution (independently verified capability construction
   on ARC);
3. biological relevance (held-out perturbation data).

Only Level 3 evidence would support a biological claim.
