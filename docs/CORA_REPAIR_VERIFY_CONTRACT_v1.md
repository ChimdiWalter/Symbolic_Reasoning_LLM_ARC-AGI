# The CORA repair-and-verification contract, v1 (domain-neutral)

**Status.** The contract is implemented and exercised on ARC only (CORA-FHR,
`cora_fhr/`). For any other domain it is a specification.

**BIOLOGICAL APPLICATION: UNTESTED.**

## The seven parts

| part | what it is | ARC implementation (exists) | what another domain must supply |
|---|---|---|---|
| **1. Prediction** | a frozen model K maps an input to a prediction, with a native acceptance gate | native object layer; train-perfect plus LOO by re-induction | the model, and its own notion of "fits the evidence" |
| **2. Failure evidence** | a typed, auditable record of where K's explanation fails; read from K's own behaviour on the training evidence only | `pattern` fallbacks: objects whose change K could only memorize (`cora_reach/instances.py`) | an instrumented model: which units or relations it explained, which it fitted only by memorization or residual |
| **3. Diagnosis** | a classification of the failure (search, representation, operation, evidence, certification) with counterfactual probes | the failure funnel: native fits by memorizing; more search does not help (`cora_funnel/`) | domain probes: extra compute, alternative representations, held-out checks |
| **4. Typed executable correction** | a bounded, declared grammar of corrections; canonical form; content-addressed name; no literals copied from the evidence | G-grow: 37,750 expressions, no cell literals (`cora_fhr/ggrow.py`) | a typed correction language (e.g. a pathway relation, a combination rule), declared before use |
| **5. Installation** | the correction is added to the same model by a reversible overlay; the original state is restored and checked by identity | `cora_fhr/bridge.py` | an extension point in the model; identity-checked restore |
| **6. Independent validation** | the model's own gate, plus fold-local reconstruction: every fold rebuilds evidence, diagnosis and correction without the held-out unit, then must predict it exactly or within tolerance; the commitment comes before scoring | `cora_fhr/measure.py` (adaptive LOO), `cora_fhr/evaluate.py` (only reader of answers) | held-out units (perturbations, genes, cell states, cohorts); a tolerance and calibration rule |
| **7. Abstention and provenance** | the system abstains when the evidence does not determine the answer (a tie between equally simple corrections) or verification fails; every run records code, data and correction hashes | tie abstention; per-task rows with hashes; the witness audit (`cora_fhr/witness.py`) | the same: an abstention rule, and a provenance record for every claim |

## Controls every claim must survive

1. **Matched extra compute**, without correction.
2. **Failure-blind construction:** the same correction language and the same
   evidence access, without the failure record (C').
3. **Shuffled failure evidence:** from an unrelated unit, with the evidence
   reduced fold by fold like the authentic arm's.
4. **Removal:** without the correction, the gain must disappear.
5. **Novelty:** the correction must not be equivalent, on perturbed inputs,
   to an existing model capability.

## Reusable, versus domain-specific

- **Reusable as is:**
  - the control flow (parts 1–7);
  - the evaluator separation;
  - the content-addressed extension form;
  - the identity-checked overlay;
  - fold-local reconstruction;
  - the abstention rule;
  - the provenance record;
  - the five controls.
- **Must be built per domain:**
  - the representation of units and relations;
  - the correction grammar;
  - the failure-evidence instrument for the specific model;
  - validators and tolerances;
  - data splits that keep held-out units truly unseen.
