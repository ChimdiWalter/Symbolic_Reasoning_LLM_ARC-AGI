# Module Reference

Per-module reference for `src/reasoning_project/`. Each entry gives a one-line description derived from the module docstring. Modules are grouped by subsystem.

---

## Core Pipeline

| Module | Description |
|--------|-------------|
| `reasoning_engine.py` | Domain-adaptable structural reasoning engine with pluggable DomainAdapter protocol and 81 boolean properties. |
| `adaptive_loop.py` | Iterative perceive-hypothesize-test-diagnose-refine-learn loop with failure-driven view switching. |
| `portfolio.py` | Multi-proposer collect-all solver: all solvers propose candidates, best selected via consensus and complexity. |
| `models.py` | Baseline and scientist-model variant definitions for experiment runners. |
| `experiment.py` | Resumable end-to-end experiment runner orchestrating generation, evaluation, and reporting. |
| `cli.py` | Command-line entry points for experiments, dataset generation, and reporting. |
| `schemas.py` | Shared dataclasses and JSON helpers for reasoning experiments. |
| `utils.py` | Small reproducibility and artifact helpers (hashing, JSON I/O, timestamps, matplotlib config). |

---

## Geometry / Perception

| Module | Description |
|--------|-------------|
| `domain_adapters.py` | Cross-domain adapters (graph, chess, molecule) implementing the DomainAdapter protocol. |
| `adapter_genesis.py` | Self-synthesizing domain adapters: detect domain type, propose schemas, validate, repair, store. |
| `adapter_feedback.py` | Adapter repair feedback from near-solved failure clusters to AdapterGenesis. |
| `perception_bridge.py` | Neural perception bridge: JEPA layout prediction, spatial relation discovery, slot-attention objects, world model simulation. |
| `parsing.py` | Deterministic object and relation parsing for colored grids (connected components, properties). |
| `multicolor_decompose.py` | Multi-color object decomposition: color components, silhouette components, part-whole, containment, same-different grouping. |
| `object_graph.py` | Object-graph representation: extract objects, compute spatial relations, infer graph rewrite rules. |
| `structural_reasoning.py` | Structural analysis toolkit: topology-aware signatures, Hungarian matching, transform classification, invariant detection. |

---

## Operator Invention

| Module | Description |
|--------|-------------|
| `trace_operator_invention.py` | Trace-driven operator invention: derive executable operators from near-solved failure traces with LOO validation and falsification. |
| `operator_invention.py` | Cluster-based concept and operator invention from near-solved boundary memory. |
| `operator_schemas.py` | Reusable task-level operator schemas (marker-target, container-content, separator-cell, symmetry completion). |
| `operator_semantics.py` | Formal operator semantics: typed preconditions, postconditions, invariants, and proof obligations. |
| `operators.py` | Transformation library and finite candidate program generation (DSL primitives). |
| `color_transfer.py` | Context-dependent color-transfer inference and execution (nearest, same-shape, same-size, neighbor, container). |
| `correspondence_inference.py` | Per-object source-to-target correspondence rule learning with ambiguity rejection. |
| `destination_policy.py` | Variable Destination Policy Learning (VDPL): per-object destination rules with LOO validation. |
| `marker_projection.py` | Marker-projection operator family: removed objects project information onto kept objects via color stamp, line projection, ray, or region fill. |
| `property_invention.py` | Property invention from failure analysis: relational, topological, and container predicates with staged validation. |

---

## Verification

| Module | Description |
|--------|-------------|
| `active_falsifier.py` | Popper-style active falsification with 5 counterexample probe families (color relabeling, distractor insertion, object count, spatial permutation, border-interior swap). |
| `falsifier.py` | Candidate falsification checks for passive and interactive settings. |
| `certificates.py` | 17-field reasoning certificates for every accepted prediction, with risk/confidence auditing. |
| `formal.py` | Finite operational formalization: exact bounded DSL code length, small-category checks, path witnesses, topology audits, AID profiles. |
| `formal_verification.py` | Machine-checkable verification: constructive proofs, termination proofs, convergence bounds, Hoare-style decision procedures, bounded LTL model checking. |
| `theory.py` | Four formal theorems (monotone diversity, consensus correctness, first-hit dominance, inductive soundness) with executable verification. |
| `events.py` | Event-driven reasoning audit log with 26 event types, lineage DAGs, JSONL export, and promotion chain tracking. |

---

## Memory

| Module | Description |
|--------|-------------|
| `near_solved_memory.py` | Near-solution boundary memory: store, retrieve, resume, and promote near-solved task states with failure clustering. |
| `manifold_memory.py` | Topological manifold memory with local charts, transition maps, geodesic solver, persistent homology, and curvature mismatch detection. |
| `concept_grammar.py` | Generative concept grammar: compositional typed expressions (primitives, relations, quantifiers, superlatives, schemas) with beam-search enumeration. |
| `concept_memory.py` | Graph-structured concept storage with dependency tracking, lifecycle management, and task-conditioned retrieval. |

---

## Neural

| Module | Description |
|--------|-------------|
| `neural_abstraction.py` | Neural-to-symbolic abstraction pipeline: encode failures, learn contrastive properties, distill to symbolic predicates, validate through 5-stage gate. |
| `neural_math.py` | Typed DSL type checking, sheaf consistency, D4-equivariant features, invariant discovery, counterfactual verification, topological loss. |
| `refinement.py` | Neural-guided but exactly verified candidate refinement loops. |
| `reasoning_policy.py` | Event-log policy learner for reasoning action selection (which view/concept/operator to try next). |

### `neural/` subpackage

| Module | Description |
|--------|-------------|
| `neural/__init__.py` | Optional neural guidance modules for bounded neuro-symbolic experiments. |
| `neural/dataset.py` | Dataset helpers for grid encoders, JEPA pretraining, and neural ranking. |
| `neural/graph_network.py` | Graph Network Simulator (GNS) for object-level dynamics prediction. |
| `neural/grid_encoder.py` | Variable-size grid encoders with optional torch-backed transformer layers. |
| `neural/grid_jepa.py` | Small JEPA-style latent prediction model for ARC-like colored grids. |
| `neural/program_ranker.py` | Neural or heuristic ranking of DSL candidates from grid/task embeddings. |
| `neural/slot_attention.py` | Slot Attention for unsupervised object-centric grid decomposition. |

---

## Solvers

| Module | Description |
|--------|-------------|
| `fill_solver.py` | 34-strategy pattern solver: enclosed-region fill, gravity, ray casting, line extension, mirror completion, denoising, and more. |
| `relation_solver.py` | Object-structural reasoning with topology-aware signatures: 17 strategies for filtering, recoloring, and extraction. |
| `separator_decompose.py` | Separator-based grid decomposition: detect separator lines, split into cells, apply per-cell operations (combine, select, overlay, vote). |
| `color_solver.py` | Color-conditional transformations: fill enclosed, recolor by size/color, majority fill, global permutation, swap/remove/keep. |
| `crop_extract.py` | Subgrid extraction and cropping: unique subgrid, bounding box, connected components, halves/quadrants, tile extraction. |
| `abstract_programs.py` | Higher-order program induction: overlay, symmetry completion, pattern continuation, conditional transform, grid combine. |
| `local_rules.py` | Pixel-level local rule synthesis: 36 strategies covering 3x3/5x5/cross/diagonal neighborhoods. |
| `cegis.py` | Counterexample-Guided Inductive Synthesis (CEGIS) loop for ARC tasks. |
| `egraph.py` | Lightweight e-graph/equality-saturation layer for DSL program equivalence and cost minimization. |
| `library_learning.py` | DreamCoder-style library learning: mine repeated program fragments, anti-unify, propose macro-operators. |
| `analogy.py` | Analogical transfer: recognize shared abstract structure between tasks for solution transfer. |

---

## Analysis and Reporting

| Module | Description |
|--------|-------------|
| `evaluation.py` | Evaluation metrics for hidden-rule reasoning tasks. |
| `compression.py` | Compression and intervention-aware scoring proxies. |
| `reporting.py` | Artifact generation for experiment summaries and manuscript sections. |
| `paper_package.py` | Build a submission-ready paper package from existing local artifacts. |
| `h2_analysis.py` | Post-hoc H2 family-balanced analysis for seed sweeps. |
| `h4_analysis.py` | H4 compression analysis against exact bounded DSL minima. |
| `h4_sweep_analysis.py` | Aggregate H4 bounded-compression alignment across completed sweep child runs. |
| `sweep.py` | Repeated-seed experiment sweeps and aggregate reporting. |
| `repair.py` | Operational path corruption and repair experiments. |

---

## ARC Interface

| Module | Description |
|--------|-------------|
| `arc_adapter.py` | Local ARC/ARC-AGI loading and ARC-only evaluation helpers. |
| `arc_diagnostic.py` | Bounded local ARC diagnostic evaluation (external-validity diagnostic, not a performance claim). |
| `arc_smoke.py` | Tiny ARC smoke evaluation runner. |
| `benchmark_generator.py` | Cross-domain benchmark generator: 27 tasks across 6 categories (grid, graph, chess, molecule, recombination, counterfactual). |
| `generators.py` | Synthetic hidden-rule benchmark generation. |
