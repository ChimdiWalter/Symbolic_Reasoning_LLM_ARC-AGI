"""Neural-CORA v1 (Neural-CORA v0.1 directive, 19 October 2026): one CORA-owned reasoner with a learned program prior.

CORA owns the typed hypothesis state, the program space, the fixed interpreter (native `render_program`), the evidence
check, the search and the final choice of two attempts. A trained neural component only ORDERS the search: it scores
typed program components from the demonstrations. It never emits a grid and never verifies its own proposals.

Modules:
- `ir`: the typed hypothesis language and its compiler to native ObjectProgram dicts;
- `interp`: the fixed interpreter (native, unchanged) and the demonstration evidence;
- `space`: component domains, data-driven pruning shared by every arm, and the enumerators;
- `generator`: CORA's own synthetic task families (execution-validated; no third-party data);
- `search`: the budgeted CORA search loop;
- `prior`: the learned component (encoder features + trainable heads) and its controls.

Status: DEVELOPMENT. Nothing here is a result until the preregistered pilot
(`records/NEURAL_CORA_PILOT_v0_PROTOCOL.md`) has run and been evaluated.
"""
VERSION = "neural_cora_v1/0.1"
