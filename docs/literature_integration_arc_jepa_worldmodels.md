# Literature Integration Notes: ARC, JEPA, World Models, and Bounded Diagnostics

## Positioning

This phase integrates three external ideas into the existing scientist-model framework without changing the paper's core boundaries.

1. ARC engineering lessons
Modern ARC progress is frequently driven by refinement loops, synthetic curriculum design, test-time adaptation, and careful compute budgeting. We incorporate those ideas operationally through bounded refinement and task-local adaptation logs.

2. JEPA and latent predictive learning
JEPA-style objectives motivate learning object/layout priors without optimizing pixel reconstruction directly. In this repository that motivation becomes a small Grid-JEPA module over ARC-style color grids, with masked latent prediction and optional input-to-output latent prediction.

3. Neuro-symbolic separation
Many ARC systems separate perception, proposal, and executable checking. That separation matches the existing exact DSL framing well. Neural modules may propose or rerank candidates, but exact symbolic execution still decides consistency.

4. REMA-style reasoning geometry
Reasoning-manifold work suggests that success and failure may occupy measurably different latent regions. Here we implement only a bounded diagnostic: kNN success-distance, success/failure separability, and divergence-step analysis over local neural/refinement embeddings.

## Boundaries To Preserve

- No claim that JEPA solves ARC.
- No claim that latent spaces constitute a general theory of reasoning.
- No claim that local ARC-style data is verified ARC-AGI-2 provenance unless the files themselves support it.
- No claim that neural guidance replaces exact symbolic verification.
- No claim that synthetic gains automatically imply benchmark progress.

## Repo Integration Map

- Perception: `src/reasoning_project/neural/grid_encoder.py`
- Latent world model: `src/reasoning_project/neural/grid_jepa.py`
- Neural DSL ranking: `src/reasoning_project/neural/program_ranker.py`
- Refinement and adaptation: `src/reasoning_project/refinement.py`
- Latent failure analysis: `src/reasoning_project/diagnostics/reasoning_manifold.py`
- ARC status audit: `scripts/audit_arc_agi2.py`
- Bounded ARC evaluation: `scripts/run_arc_refinement.py`

## Manuscript Integration Guidance

Use the phrase "Neural-Guided Executable Reasoning" for the new section.

Recommended emphasis:
- the neural modules add visual priors and ranking signals;
- executable DSL verification remains the exact layer;
- refinement and adaptation are evaluated as bounded additions;
- negative transfer and weak ARC gains are scientifically informative outcomes.

Recommended non-claims:
- do not write that the project now solves ARC-AGI-2;
- do not recast the bounded exactness results as general semantics;
- do not turn REMA-inspired diagnostics into a general theory claim.
