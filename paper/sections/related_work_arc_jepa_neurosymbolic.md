# Related Work: ARC, JEPA, and Neuro-Symbolic Search

ARC progress has increasingly depended on disciplined engineering rather than a single universal insight. Refinement loops, synthetic task generation, test-time adaptation, and carefully budgeted search now define much of the practical frontier. We treat that body of work as an engineering lesson rather than a claim that ARC has been solved.

JEPA-style latent prediction offers a different inductive bias from pixel reconstruction. In this project, that motivation supports a bounded Grid-JEPA module that learns latent grid regularities from masked context without claiming that latent prediction by itself yields exact ARC reasoning. The implemented contribution is modest: a small ARC-grid encoder and latent-prediction objective that can be coupled to symbolic search.

Neuro-symbolic ARC systems typically separate perception, proposal, and executable verification. That decomposition aligns naturally with this repository's exact bounded DSL semantics. The neural additions in this phase therefore guide candidate generation and ranking, while symbolic execution remains the only mechanism that can certify train-pair consistency.

Reasoning-manifold work such as REMA motivates latent success/failure geometry as a diagnostic tool. Our implementation is deliberately narrower. We add a REMA-inspired latent failure diagnostic over bounded embeddings from the Grid-JEPA model, the program ranker, and refinement trajectories. We do not claim a general theory of reasoning manifolds.

What prior work does:
- uses large-scale search, refinement, adaptation, or learned perception to improve ARC-style performance;
- studies latent predictive representations without committing to exact symbolic semantics;
- explores neuro-symbolic decomposition or latent failure geometry.

What this repository already implemented before this phase:
- exact bounded finite semantics where operators, DSL fragments, or finite audits are explicitly implemented;
- conditional falsification results on synthetic ambiguity/composition probes;
- bounded repair and ARC external-validity diagnostics with explicit non-claim wording.

What this phase adds:
- variable-size grid encoders with masking and optional transformer layers;
- a small Grid-JEPA latent-prediction pretraining path;
- neural candidate ranking that feeds exact symbolic execution;
- refinement-loop logging, optional task-local adaptation, and REMA-inspired diagnostics on bounded latent spaces.

What remains speculative:
- whether latent world-model pretraining materially closes the ARC transfer gap;
- whether neural guidance changes the broad H5 verdict rather than only improving bounded diagnostics;
- whether local ARC-style files in this environment correspond cleanly to ARC-AGI-2 provenance.
