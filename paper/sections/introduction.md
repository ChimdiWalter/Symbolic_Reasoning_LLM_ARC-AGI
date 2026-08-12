# Introduction

Few-shot abstract reasoning tasks are underdetermined. A model may see several input-output demonstrations, infer a rule that explains them, and still fail because the demonstrations did not expose a decisive counterexample. This paper studies that setting with a bounded scientist-model architecture for colored-grid reasoning, then extends it with a neuro-symbolic layer that adds learned visual priors and neural proposal/ranking without relaxing exact symbolic verification.

The main thesis is:

> A precise scientist-model benchmark can make abstract-reasoning claims more testable by separating exact finite semantic checks from proxy criteria and empirical hypotheses; in this bounded setting, structural program search and conditional falsification show localized benefits, while integrated-stack and ARC-transfer claims remain weak.

The contribution is intentionally not an ARC breakthrough, not a path to AGI, and not a general mathematical unification claim. The paper instead asks what can be made exact inside the implemented finite world, how far a bounded neural-guided extension can be attached to that exact layer, and where the resulting mechanisms do and do not help.
