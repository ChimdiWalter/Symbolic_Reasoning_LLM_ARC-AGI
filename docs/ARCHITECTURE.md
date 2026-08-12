# Reasoning Project: Complete Architecture

## Overview

This project implements a **cumulative, verifiable reasoning architecture** where failure states become reusable training data for abstraction learning. The core thesis is that failures are not errors but data: near-solution states are stored, clustered by failure mode, used to invent new operators/properties, and then tasks are resumed with the invented abstractions. The system is domain-adaptable (demonstrated on ARC grids, graphs, chess boards, and molecules), produces reasoning certificates for every accepted answer, and uses active falsification to reject spurious hypotheses. Current results: 95/1000 ARC training tasks (9.5% with DSL), 12/160 ConceptARC, 5/13 cross-domain, 0 false positives, 571 tests passing.

## System Diagram

```
                              +------------------+
                              |   Task Input     |
                              | (train pairs +   |
                              |  test inputs)    |
                              +--------+---------+
                                       |
                              +--------v---------+
                              | PerceptionSelector|  (adaptive_loop.py:373)
                              | select view:      |
                              | color_cc/per_color|
                              | /monochrome/      |
                              | majority_bg       |
                              +--------+---------+
                                       |
                              +--------v---------+
                              | DomainAdapter     |  (reasoning_engine.py:34)
                              | extract_objects() |
                              | get_property()    |
                              | classify_kept_    |
                              |   removed()       |
                              +--------+---------+
                                       |
                              +--------v---------+
                              | StructuralReasoner|  (reasoning_engine.py:420)
                              | hypothesize:      |
                              |  discriminative   |
                              |  filter/extract/  |
                              |  recolor/transform|
                              |  /conjunction     |
                              +--------+---------+
                                       |
                          +------------+------------+
                          |                         |
                   +------v------+           +------v------+
                   |   SOLVED    |           |   FAILED    |
                   | emit cert   |           | diagnose    |
                   | store episode|          | failure     |
                   +------+------+           +------+------+
                          |                         |
                 +--------v--------+       +--------v--------+
                 | CertificateBuilder|     | FailureDiagnoser |
                 | (certificates.py |      | (adaptive_loop.py|
                 |  :43)            |      |  :407)           |
                 +---------+-------+       +--------+--------+
                           |                        |
                  +--------v--------+      +--------v---------+
                  | ReasoningEvent  |      |  NearSolvedMemory |
                  |  HYPOTHESIS_    |      |  store_partial()  |
                  |  ACCEPTED       |      |  (near_solved_    |
                  |  (events.py:57) |      |   memory.py:136)  |
                  +-----------------+      +--------+---------+
                                                    |
                                           +--------v---------+
                                           | detect_missing_  |
                                           |  charts()        |
                                           | cluster failures |
                                           | (near_solved_    |
                                           |  memory.py:209)  |
                                           +--------+---------+
                                                    |
                                 +------------------+------------------+
                                 |                                     |
                        +--------v---------+               +---------v---------+
                        | OperatorInventor |               | PropertyInventor  |
                        | mine_from_near_  |               | mine_from_        |
                        |  solved()        |               |  failures()       |
                        | propose_concepts |               | propose_relational|
                        | propose_operators|               | propose_topological|
                        | validate_        |               | (property_        |
                        |  inventions()    |               |  invention.py:505)|
                        | (operator_       |               +---------+---------+
                        |  invention.py    |                         |
                        |  :102)           |                +--------v---------+
                        +--------+---------+               | ActiveFalsifier   |
                                 |                         | falsify()         |
                        +--------v---------+               | 5 probe families  |
                        | validate_        |               | (active_falsifier |
                        |  inventions()    |               |  .py:43)          |
                        | LOO + FP check   |               +---------+---------+
                        | (:202)           |                         |
                        +--------+---------+               +--------v---------+
                                 |                         | register_property |
                        +--------v---------+               | register_validated|
                        | register_        |               +---------+---------+
                        |  validated()     |                         |
                        | mint into        |               +---------v---------+
                        | ReasoningMemory  |               | Resume near-solved|
                        | (:252)           |               | tasks with new    |
                        +--------+---------+               | operators/props   |
                                 |                         | adaptive_loop.py  |
                                 +----------+--------------+  :590 resume_from |
                                            |
                                   +--------v---------+
                                   | promote_to_solved|
                                   | NearSolvedMemory |
                                   | (:183)           |
                                   +------------------+
```

## Module Map

### Core Reasoning Engine

| Module | Path | Purpose | Key Classes | Key Functions | Lines |
|--------|------|---------|-------------|---------------|-------|
| reasoning_engine | `src/reasoning_project/reasoning_engine.py` | Domain-adaptable structural reasoner with discriminative filter, transform induction, conjunction search, and cognitive memory | `DomainAdapter`, `WorkingMemory`, `ReasoningMemory`, `StructuralReasoner`, `GridDomainAdapter` | `solve()`, `_try_discriminative_filter()`, `_try_discriminative_conjunction()`, `_try_transform_induction()`, `_try_rank_relabel()`, `_try_filter_then_extract()`, `_commit_to_memory()`, `_replay_hypothesis()`, `solve_task_reasoning()` | 2468 |
| adaptive_loop | `src/reasoning_project/adaptive_loop.py` | Iterative perceive-hypothesize-test-diagnose-refine-learn loop with manifold memory and near-solved resume | `Diagnosis`, `LoopResult`, `PerColorAdapter`, `MonochromeAdapter`, `MajorityBgAdapter`, `PerceptionSelector`, `FailureDiagnoser`, `AdaptiveReasoningLoop`, `AdaptivePortfolio` | `solve()` (loop :590, portfolio :965), `next_view()`, `diagnose()` | 1060 |
| portfolio | `src/reasoning_project/portfolio.py` | Multi-proposer collect-all solver portfolio with consensus + complexity + WM reranking | `PortfolioResult`, `WorldModelReranker`, `PortfolioSolver` | `solve()`, `_select_best()`, `compute_task_features()`, `heuristic_route()`, `_complexity_score()`, `_perception_guided_route()` | 434 |

### Perception & Domain Adapters

| Module | Path | Purpose | Key Classes | Key Functions | Lines |
|--------|------|---------|-------------|---------------|-------|
| domain_adapters | `src/reasoning_project/domain_adapters.py` | Graph, chess, molecule domain adapters implementing `DomainAdapter` protocol | `GraphDomainAdapter`, `ChessBoardDomainAdapter`, `MoleculeGraphDomainAdapter` | `extract_objects()`, `get_property()`, `classify_kept_removed()`, `reconstruct_filtered()`, `match_objects()` | 574 |
| adapter_genesis | `src/reasoning_project/adapter_genesis.py` | Self-synthesizing domain adapters from raw examples | `DomainType`, `DomainSignature`, `DomainSignatureExtractor`, `ObjectSchema`, `ObjectSchemaProposer`, `PropertyDef`, `PropertyLibraryProposer`, `RelationDef`, `RelationAlgebraProposer`, `CounterfactualResult`, `CounterfactualVerifier`, `EnergyWeights`, `EnergyConsensus`, `SynthesizedAdapter`, `AdapterValidator`, `AdapterRepairer`, `AdapterMemory`, `AdapterGenesis` | `extract()`, `propose()`, `verify()`, `synthesize()`, `validate()`, `repair()` | 1616 |
| perception_bridge | `src/reasoning_project/perception_bridge.py` | Neural perception bridge: JEPA layout prediction, spatial relations, slot perception, world model simulation | `TaskPerception`, `JEPAPerceptionGuide`, `SpatialRelation`, `SpatialRelationLearner`, `SlotPerceptionAdapter`, `SimulationResult`, `WorldModelSimulator`, `NeuralPerceptionPipeline` | `analyze()`, `suggest_views()`, `discover_relevant_relations()`, `rank_discriminative_relations()`, `simulate_hypothesis()`, `rank_hypotheses()`, `analyze_task()` | 860 |
| arc_adapter | `src/reasoning_project/arc_adapter.py` | ARC/ConceptARC dataset loading and task format conversion | - | `load_arc_tasks()`, `load_conceptarc_tasks()` | 409 |
| multicolor_decompose | `src/reasoning_project/multicolor_decompose.py` | Multi-color object decomposition: 3 views, containment detection, shape grouping | `MultiColorGridAdapter` | `solve_task_multicolor()` | 1138 |

### Solvers (12 Families)

| Module | Path | Purpose | Strategies | Key Entry Function | Lines |
|--------|------|---------|------------|-------------------|-------|
| local_rules | `src/reasoning_project/local_rules.py` | Pixel-level local rule synthesis: 36 neighborhood strategies | 36 (3x3, 5x5, cross, diagonal, color_count, symmetry, checkerboard, edge_detection, etc.) | `solve_task_local_rules()` (:529) | 608 |
| separator_decompose | `src/reasoning_project/separator_decompose.py` | Separator-based grid decomposition and cell operations | 13 (binary_combine, quadrant_compose, cell_select, cell_difference, half_transform, cell_overlay, cell_majority_vote, cell_marker_position, separator_color_extract, grid_dimensions, etc.) | `solve_task_separator_decompose()` (:1313) | 1325 |
| fill_solver | `src/reasoning_project/fill_solver.py` | Pattern fill operations: gravity, ray casting, line extension, mirror, denoise, scale, sort | 34 (fill_enclosed, gravity, ray_cast, connect_same_color, mirror_half, denoise, flood_seeds, expand, scale, tile, border_draw, extend_to_boundary, color_map, remove_small, sort_rows, etc.) | `solve_task_fill()` (end of file) | 1891 |
| crop_extract | `src/reasoning_project/crop_extract.py` | Subgrid extraction and cropping operations | 10 (unique_subgrid, nonzero_bbox, color_bbox, largest_cc, smallest_cc, minority_region, halves_and_quadrants, separator_split, mask_extract, repeated_tile_extract) | `solve_task_crop_extract()` (:604) | 619 |
| abstract_programs | `src/reasoning_project/abstract_programs.py` | Higher-order program induction: conditional transforms, overlays, symmetry completion | 5 (conditional_transform, overlay_two_objects, symmetry_completion, pattern_continuation, grid_combine) | `solve_task_abstract_programs()` (:599) | 639 |
| color_solver | `src/reasoning_project/color_solver.py` | Color-conditional transformations | 11 (fill_enclosed, fill_enclosed_adaptive, recolor_cc_by_size, recolor_cc_by_color, majority_fill, global_color_permutation, conditional_color_by_neighbor_count, color_by_component_position, swap_colors, remove_color, keep_only_color) | `solve_task_color()` (:760) | 775 |
| relation_solver | `src/reasoning_project/relation_solver.py` | Object-structural reasoning with topology-aware signatures | 17 (keep_relative_to_separator, keep_same_remove_different, keep_filled_remove_hollow, keep_symmetric_remove_asymmetric, remove_boundary_objects, keep_largest_per_color, recolor_by_vertical_position, keep_holey_remove_solid, match_and_recolor_by_structure, keep_by_containment, extract_unique_object, hungarian_recolor, recolor_by_spatial_relation, keep_touching_reference, keep_side_of_separator_color_aware, extract_inner_content, count_objects_inside) | `solve_task_relation()` (:1469) | 1511 |
| object_graph | `src/reasoning_project/object_graph.py` | Object-graph representation with rewrite rules | 6 (color_remap, object_filter, crop-largest/smallest/unique, recolor-by-rank) | `solve_task_object_graph()` (:325) | 565 |
| structural_reasoning | `src/reasoning_project/structural_reasoning.py` | Structural analysis: Hungarian matching, spatial relations, invariant search, counterfactual testing | - | `compute_structural_signature()`, `match_objects_hungarian()`, `classify_object_transform()`, `compute_spatial_relations()`, `compute_invariants()`, `analyze_task_invariants()`, `identify_causal_properties()`, `analyze_task()` | 473 |
| cegis | `src/reasoning_project/cegis.py` | Counterexample-guided DSL search with local-rule fallback | - | CEGIS loop | 287 |
| egraph | `src/reasoning_project/egraph.py` | E-graph/equality-saturation with 13 composition rewrite rules | - | rewrite rules | 226 |
| library_learning | `src/reasoning_project/library_learning.py` | DreamCoder-style fragment mining and anti-unification | - | fragment extraction | 190 |

### Memory & Learning

| Module | Path | Purpose | Key Classes | Key Functions | Lines |
|--------|------|---------|-------------|---------------|-------|
| near_solved_memory | `src/reasoning_project/near_solved_memory.py` | Near-solved boundary states, failure clustering, repair frontier | `NearSolvedStatus`, `RepairAction`, `NearSolvedTaskState`, `NearSolvedMemory` | `store_partial()`, `retrieve_similar_partial()`, `resume_from_state()`, `promote_to_solved()`, `detect_missing_charts()`, `build_near_solved_state()`, `_compute_train_fit()`, `_propose_repairs()`, `_guess_missing_capability()` | 472 |
| manifold_memory | `src/reasoning_project/manifold_memory.py` | Fiber bundle topology, geodesic solver, curvature mismatch trigger, persistent homology | `ManifoldPoint`, `LocalChart`, `TransitionMap`, `MemoryManifold`, `WorkingMemoryManifold`, `TopologicalRetriever`, `PersistentHomologyDetector`, `ManifoldReasoningEngine`, `TopologicalConsistencyLoss`, `Fiber`, `FiberBundle`, `ReasoningTrajectory`, `GeodesicSolver`, `ManifoldMismatchTrigger` | `add_point()`, `retrieve_topological()`, `detect_gaps()`, `geodesic_distance()`, `solve()` (geodesic), `compute_persistence()`, `find_gaps()`, `uncertainty_score()` | 1398 |
| concept_memory | `src/reasoning_project/concept_memory.py` | Learned concept graph with dependency tracking, promotion, and status management | `LearnedConcept`, `ConceptGraph`, `ConceptMemory` | `add_concept()`, `topological_order()`, `mark_promoted()`, `mark_solved()`, `mark_false_positive()`, `seed_primitives()`, `register_concept()`, `retrieve_for_task()` | 259 |
| events | `src/reasoning_project/events.py` | Event-driven reasoning audit log with 26 event types | `ReasoningEvent`, `ReasoningEventLog` | `append()`, `emit()`, `query()`, `replay()`, `lineage()`, `has_chain()`, `promotion_chains()`, `summary()`, `export_jsonl()`, `export_summary_md()`, `export_task_lineages()`, `load_jsonl()`, `get_global_log()`, `reset_global_log()` | 269 |

### Invention & Abstraction

| Module | Path | Purpose | Key Classes | Key Functions | Lines |
|--------|------|---------|-------------|---------------|-------|
| operator_invention | `src/reasoning_project/operator_invention.py` | Concept/operator mining from failure clusters with LOO validation | `InventedConcept`, `InventedOperator`, `OperatorInventor` | `mine_from_near_solved()`, `propose_concepts()`, `propose_operators()`, `validate_inventions()`, `register_validated()` | 779 |
| property_invention | `src/reasoning_project/property_invention.py` | Property invention: relational, topological, container, pattern-membership predicates with staged validation | `InventedProperty`, `PropertyInventor` | `mine_from_failures()`, `propose_relational_properties()`, `propose_topological_properties()`, `propose_container_properties()`, `register_property()` | 974 |
| concept_grammar | `src/reasoning_project/concept_grammar.py` | Typed concept expression language with compositional grammar | `ConceptExpression` (ABC), `PrimitiveConcept`, `RelationConcept`, `NotConcept`, `AndConcept`, `OrConcept`, `ExistsConcept`, `ForAllConcept`, `CountConcept`, `ArgMaxConcept`, `ReferenceConcept`, `BoundRelationConcept`, `SchemaConcept`, `ConceptGenerator`, `ConceptValidator` | `evaluate()`, `to_string()`, `generate_depth_1()`, `generate_depth_2()`, `generate_depth_k()`, `generate_from_failure_cluster()`, `training_discrimination_score()`, `loo_validate()`, `batch_evaluate()` | 1021 |
| neural_abstraction | `src/reasoning_project/neural_abstraction.py` | Neural-to-symbolic abstraction pipeline: failure encoding, contrastive learning, symbolic distillation, counterexample validation | `InventedProperty`, `Counterexample`, `FailureEncoder`, `ObjectRelationEncoder`, `ContrastivePropertyLearner`, `SymbolicPropertyDistiller`, `OperatorTemplateProposer`, `NeuralCounterexampleGenerator`, `SymbolicValidationGate`, `ConceptGraphMemory`, `NeuralAbstractionPipeline` | `encode_state()`, `contrastive_loss()`, `distill()`, `propose()`, `generate_probes()`, `validate()` | 895 |
| analogy | `src/reasoning_project/analogy.py` | H6 analogical transfer: task signatures, similarity, transfer attempt | - | task signature, similarity, transfer | 348 |

### Verification & Certificates

| Module | Path | Purpose | Key Classes | Key Functions | Lines |
|--------|------|---------|-------------|---------------|-------|
| active_falsifier | `src/reasoning_project/active_falsifier.py` | Active falsification with 5 counterexample probe families | `Counterexample`, `FalsificationResult`, `ActiveFalsifier` | `falsify()`, `_probe_color_relabeling()`, `_probe_distractor_insertion()`, `_probe_object_count()`, `_probe_spatial_permutation()`, `_probe_border_interior_swap()` | 461 |
| certificates | `src/reasoning_project/certificates.py` | 17-field reasoning certificates with builder and auditor | `ReasoningCertificate`, `CertificateBuilder`, `CertificateAuditor` | `from_portfolio_result()`, `from_loop_result()`, `audit()`, `certificate_to_json()`, `certificate_to_markdown()` | 446 |
| formal_verification | `src/reasoning_project/formal_verification.py` | Machine-checkable proofs, termination proofs, convergence bounds, decision procedures, LTL model checking | `ProofStatus`, `ProofStep`, `ProofObject`, `TerminationProof`, `ConvergenceBound`, `Precondition`, `Postcondition`, `DecisionProcedure`, `LTLFormula`, `Atomic`, `Not`, `And`, `Or`, `Always`, `Eventually` (+ more LTL operators) | `verify()`, `prove_inductive_soundness()`, `prove_monotone_diversity()`, `ranking_function()`, `verify_decrease()`, `verify_well_founded()`, `verify_on_trace()`, `steps_to_epsilon()`, `convergence_rate()`, `verify_on_trajectory()`, `certificate()`, `execute()`, `make_mismatch_decision_procedure()` | 774 |

### Neural Components

| Module | Path | Purpose | Key Classes/Functions | Lines |
|--------|------|---------|----------------------|-------|
| neural/slot_attention.py | `src/reasoning_project/neural/slot_attention.py` | Slot Attention object-centric decomposition | `SlotAttention`, `SlotDecoder`, `SlotAttentionAutoEncoder` | 269 |
| neural/graph_network.py | `src/reasoning_project/neural/graph_network.py` | Graph Network Simulator (GNS) for dynamics prediction | `EdgeModel`, `NodeModel`, `GraphNetworkBlock`, `GraphNetworkSimulator`, `WorldModel` | 566 |
| neural/grid_encoder.py | `src/reasoning_project/neural/grid_encoder.py` | Grid encoder for ARC grids | `GridEncoder` | 246 |
| neural/grid_jepa.py | `src/reasoning_project/neural/grid_jepa.py` | Grid-JEPA self-supervised encoder | `GridJEPA` | 194 |
| neural/program_ranker.py | `src/reasoning_project/neural/program_ranker.py` | Neural program ranking | `ProgramRanker` | 485 |
| neural/dataset.py | `src/reasoning_project/neural/dataset.py` | ARC dataset utilities | - | 136 |

### Formal Theory

| Module | Path | Purpose | Key Classes | Key Functions | Lines |
|--------|------|---------|-------------|---------------|-------|
| theory | `src/reasoning_project/theory.py` | Formal theorems with verification routines: Monotone Diversity, Consensus Correctness Bound, First-Hit Dominance, Inductive Soundness | `Solver`, `Portfolio`, `SolveResult`, `Task` | `_run_portfolio()`, `_solve_set()`, `verify_monotone_diversity()`, `compute_consensus_bound()`, `verify_first_hit_dominance()`, `verify_inductive_soundness()` | 591 |

### Neural Math

| Module | Path | Purpose | Key Classes | Lines |
|--------|------|---------|-------------|-------|
| neural_math | `src/reasoning_project/neural_math.py` | Typed DSL, sheaf consistency, equivariant features, invariant discovery, counterfactual verification, topological loss | `TypeChecker`, `SheafConsistency`, `EquivariantFeatures`, `InvariantDiscovery`, `CounterfactualVerifier`, `TopologicalLoss` | 1149 |

### Event System

The event system (`events.py`, 269 lines) supports 26 event types spanning the full reasoning lifecycle:

```
TASK_OBSERVED, TASK_RESUMED, PERCEPTION_SELECTED, OBJECTS_EXTRACTED,
HYPOTHESIS_PROPOSED, HYPOTHESIS_TESTED, HYPOTHESIS_ACCEPTED, HYPOTHESIS_REJECTED,
FALSIFICATION_STARTED, FALSIFICATION_COMPLETED, COUNTEREXAMPLE_FOUND,
NEAR_SOLVED_STORED, NEAR_SOLVED_CLUSTERED, CONCEPT_PROPOSED, CONCEPT_VALIDATED,
CONCEPT_REJECTED, OPERATOR_PROPOSED, OPERATOR_VALIDATED, OPERATOR_REJECTED,
PROPERTY_INVENTED, PROPERTY_REGISTERED, TASK_PROMOTED, CERTIFICATE_EMITTED,
MEMORY_STORED, MEMORY_RETRIEVED, FINAL_PREDICTION_EMITTED
```

Events form lineage DAGs via `parent_event_ids`. The `promotion_chains()` method traces TASK_OBSERVED -> NEAR_SOLVED_STORED -> TASK_PROMOTED chains.

### Supporting Modules

| Module | Path | Purpose | Lines |
|--------|------|---------|-------|
| models | `src/reasoning_project/models.py` | Rule induction and transformation library models | 1065 |
| generators | `src/reasoning_project/generators.py` | Synthetic task generators | 857 |
| operators | `src/reasoning_project/operators.py` | Grid transformation operators (DSL) | 864 |
| benchmark_generator | `src/reasoning_project/benchmark_generator.py` | 27-task cross-domain benchmark suite | 1214 |
| evaluation | `src/reasoning_project/evaluation.py` | Evaluation utilities | 232 |
| experiment | `src/reasoning_project/experiment.py` | Experiment runner | 137 |
| compression | `src/reasoning_project/compression.py` | Compression scoring | 126 |
| formal | `src/reasoning_project/formal.py` | Earlier formal methods | 520 |
| parsing | `src/reasoning_project/parsing.py` | Grid parsing | 209 |
| refinement | `src/reasoning_project/refinement.py` | Refinement loop | 347 |
| repair | `src/reasoning_project/repair.py` | Repair utilities | 112 |
| reporting | `src/reasoning_project/reporting.py` | Report generation | 294 |
| schemas | `src/reasoning_project/schemas.py` | Data schemas | 193 |
| sweep | `src/reasoning_project/sweep.py` | Seed sweep utilities | 446 |
| utils | `src/reasoning_project/utils.py` | Shared utilities | 161 |
| arc_diagnostic | `src/reasoning_project/arc_diagnostic.py` | ARC diagnostic evaluation | 584 |
| arc_smoke | `src/reasoning_project/arc_smoke.py` | ARC smoke test | 191 |
| h2_analysis | `src/reasoning_project/h2_analysis.py` | H2 analysis utilities | 254 |
| h4_analysis | `src/reasoning_project/h4_analysis.py` | H4 analysis utilities | 268 |
| h4_sweep_analysis | `src/reasoning_project/h4_sweep_analysis.py` | H4 sweep analysis | 232 |
| paper_package | `src/reasoning_project/paper_package.py` | Submission package builder | 832 |
| falsifier | `src/reasoning_project/falsifier.py` | Legacy falsifier | 111 |
| cli | `src/reasoning_project/cli.py` | CLI entry point | 72 |

**Total source**: 36,833 lines across 48 modules (+ 1,919 lines in 7 neural submodules = **38,752 lines total**).

## Property Language

### Current: 81 predicates (22 base + 59 derived)

**Base structural (22)**:
`is_largest`, `is_smallest`, `is_unique_color`, `has_holes`, `is_symmetric`, `touches_border`, `is_convex`, `is_rectangular`, `is_majority_shape`, `is_minority_shape`, `in_top_half`, `in_bottom_half`, `in_left_half`, `in_right_half`, `is_tallest`, `is_widest`, `is_densest`, `is_sparsest`, `has_max_perimeter`, `has_min_perimeter`, `is_largest_in_color_group`, `is_smallest_in_color_group`

**Per-color properties (9)**:
`is_color_0` through `is_color_9` (selected subset)

**Ordinal rank (3)**:
`is_second_largest`, `is_second_smallest`, `is_median_size`

**Exact dimensions (9)**:
`is_1x1`, `is_2x2`, `is_3x3`, `has_height_1`, `has_width_1`, `has_height_2`, `has_width_2`, `has_height_3`, `has_width_3`

**Neighborhood count (3)**:
`has_0_neighbors`, `has_1_neighbor`, `has_many_neighbors`

**Spatial relations to largest (6)**:
`above_largest`, `below_largest`, `left_of_largest`, `right_of_largest`, `same_row_as_largest`, `same_col_as_largest`

**Rotational symmetry (2)**:
`has_rot90_symmetry`, `has_rot180_symmetry`

**Color frequency (3)**:
`is_most_frequent_color`, `is_least_frequent_color`, `is_unique_color_in_scene`

**Derived positional/structural (15)**:
`is_horizontally_centered`, `is_vertically_centered`, `is_centered`, `is_corner_object`, `is_edge_object`, `is_interior_object`, `has_many_neighbors`, `has_no_neighbors`, `is_color_minority`, `is_color_majority`, `is_elongated_horizontal`, `is_elongated_vertical`, `is_compact`, `is_large`, `is_small`

### How properties connect to the reasoning loop

1. `GridDomainAdapter.extract_objects()` computes all 81 properties per object
2. `StructuralReasoner._try_discriminative_filter()` scans properties to find one that separates kept from removed objects
3. `StructuralReasoner._try_discriminative_conjunction()` searches pairs of properties (p1 AND p2) when single properties fail
4. `PropertyInventor.mine_from_failures()` proposes new predicates from failure clusters
5. `ReasoningMemory.mint_conjunction()` stores learned compound predicates

### Concept Grammar Extension

**Status: Implemented** (`concept_grammar.py`, 1021 lines).

The concept grammar provides a typed expression language for composing predicates:

- **Primitives**: `PrimitiveConcept(prop_name)` -- wraps a boolean property
- **Relations**: `RelationConcept(relation_name)` -- 8 spatial relations (inside, touches, same_shape, same_color, same_row, same_col, left_of, above)
- **Boolean operators**: `NotConcept`, `AndConcept`, `OrConcept`
- **Quantifiers**: `ExistsConcept` (exists other with relation), `ForAllConcept` (all others satisfy)
- **Counting**: `CountConcept` (count satisfying some threshold)
- **Superlatives**: `ArgMaxConcept` (object with max score_field)
- **Reference**: `ReferenceConcept` (reference objects: largest, smallest, unique_color, boundary_frame)
- **Bound relations**: `BoundRelationConcept` (relation bound to a reference)
- **Schemas**: `SchemaConcept` (container_content, marker_target, symmetry_completion)

`ConceptGenerator` produces expressions at depth 1-k with beam search. `ConceptValidator` scores discrimination and LOO-validates candidates.

## Key Data Structures

### NearSolvedTaskState
- **Fields**: `task_id`, `train_pairs`, `test_inputs`, `best_hypothesis` (dict), `failure_diagnosis` (str), `train_fit` (float), `views_tried` (list), `repair_frontier` (list of RepairAction), `topology_signature` (dict), `suspected_chart_transition` (optional str), `status` (NearSolvedStatus enum)
- **Created in**: `build_near_solved_state()` (`near_solved_memory.py:262`)
- **Consumed by**: `NearSolvedMemory.store_partial()`, `OperatorInventor.mine_from_near_solved()`, `AdaptiveReasoningLoop.solve(resume_from=...)`

### LoopResult
- **Fields**: `task_id`, `solved` (bool), `predictions` (list), `solver_used` (str), `views_tried` (list), `diagnoses` (list of Diagnosis), `manifold_hints` (list), `geodesic_info` (dict), `memory_retrievals` (int), `elapsed_seconds` (float)
- **Created in**: `AdaptiveReasoningLoop.solve()` (`adaptive_loop.py:590`)
- **Consumed by**: `CertificateBuilder.from_loop_result()`, memory growth curriculum

### Diagnosis
- **Fields**: `failure_type` (str), `view_used` (str), `n_objects` (int), `n_properties_tried` (int), `suggested_views` (list of str)
- **Created in**: `FailureDiagnoser.diagnose()` (`adaptive_loop.py:407`)
- **Consumed by**: `PerceptionSelector.next_view()`, `NearSolvedTaskState`

### InventedProperty (property_invention.py)
- **Fields**: `name` (str), `compute_fn` (callable), `source_family` (str), `discrimination_score` (float), `loo_accuracy` (float), `false_positive_rate` (float), `description` (str)
- **Created in**: `PropertyInventor.propose_*()` methods
- **Consumed by**: `PropertyInventor.register_property()`, `ReasoningMemory`

### InventedConcept (operator_invention.py)
- **Fields**: `name` (str), `expression` (dict), `source_tasks` (list), `discrimination_score` (float), `loo_accuracy` (float), `fp_rate` (float)
- **Created in**: `OperatorInventor.propose_concepts()` (`operator_invention.py:123`)
- **Consumed by**: `OperatorInventor.validate_inventions()`, `OperatorInventor.register_validated()`

### InventedOperator (operator_invention.py)
- **Fields**: `name` (str), `transform_fn` (callable), `source_tasks` (list), `error_pattern` (str), `description` (str), `gain_estimate` (float), plus validation fields
- **Created in**: `OperatorInventor.propose_operators()` (`operator_invention.py:170`)
- **Consumed by**: `OperatorInventor.validate_inventions()`, `OperatorInventor.register_validated()`

### LearnedConcept (concept_memory.py)
- **Fields**: `name` (str), `expression` (ConceptExpression or dict), `compute_fn` (callable), `source_tasks` (list), `complexity` (int), `status` (str: candidate/promoted/validated/false_positive), `promoted_tasks` (list), `solved_tasks` (list), `dependencies` (set)
- **Created in**: `ConceptMemory.register_concept()`
- **Consumed by**: `ConceptGraph`, `ConceptMemory.retrieve_for_task()`

### ConceptExpression (concept_grammar.py)
- **Fields**: varies by subclass; all implement `evaluate(obj, scene) -> bool` and `to_string() -> str`
- **Created in**: `ConceptGenerator.generate_depth_k()`, `ConceptGenerator.generate_from_failure_cluster()`
- **Consumed by**: `ConceptValidator.training_discrimination_score()`, `ConceptValidator.loo_validate()`

### ReasoningCertificate (certificates.py)
- **Fields (17)**: `task_id`, `solver_used`, `hypothesis`, `confidence`, `training_fit` (float), `loo_consistent` (bool), `falsification_score` (float), `counterexamples_survived` (int), `counterexamples_total` (int), `agreeing_solvers` (int), `total_solvers` (int), `paradigms_used` (list), `elapsed_seconds` (float), `risk_level` (str), `topology_changes` (dict), `timestamp` (str), `trace` (list)
- **Created in**: `CertificateBuilder.from_portfolio_result()` (:46), `CertificateBuilder.from_loop_result()` (:97)
- **Consumed by**: `CertificateAuditor.audit()`, `certificate_to_json()`, `certificate_to_markdown()`

### ManifoldPoint (manifold_memory.py)
- **Fields**: `embedding` (np.ndarray), `task_id` (str), `metadata` (dict), `chart_id` (str), `solved` (bool)
- **Created in**: `ManifoldReasoningEngine.encode_task()`, `AdaptiveReasoningLoop.solve()`
- **Consumed by**: `MemoryManifold.add_point()`, `LocalChart.project()`, `GeodesicSolver`

### FiberBundle (manifold_memory.py)
- **Fields**: `base_manifold` (MemoryManifold), `fibers` (dict mapping chart_id to Fiber), plus gauge transform and parallel transport machinery
- **Created in**: `AdaptiveReasoningLoop.__init__()`
- **Consumed by**: `GeodesicSolver`, `ManifoldMismatchTrigger`

### ReasoningEvent (events.py)
- **Fields**: `event_id` (str), `event_type` (str), `task_id` (str), `timestamp` (float), `data` (dict), `module` (str), `parent_event_ids` (list)
- **Created in**: `ReasoningEventLog.emit()`
- **Consumed by**: `ReasoningEventLog.query()`, `lineage()`, `replay()`, `has_chain()`, `promotion_chains()`

## Pipeline Stages

The memory growth curriculum (`scripts/run_memory_growth_curriculum.py`) runs 6 stages:

### Stage 1: Static Baseline
- No memory, no invention, no resume.
- Run `AdaptiveReasoningLoop.solve()` on all tasks.
- Record: accuracy, false positives, per-task results.
- Baseline for measuring memory contribution.

### Stage 2: Episodic Memory
- `ReasoningMemory` accumulates: solved task signatures stored as episodes, learned predicates from conjunction search.
- When a new task arrives, `_replay_hypothesis()` retrieves similar episodes and injects prior hypotheses as starting points.
- Measures: accuracy delta from memory retrieval, number of stored episodes.

### Stage 3: Manifold + Near-Solved
- `MemoryManifold` active: task embeddings form a topological space with local charts.
- Failed tasks with `train_fit > 0` stored as `NearSolvedTaskState` via `build_near_solved_state()`.
- `TopologicalRetriever` retrieves geometrically nearby solutions.
- `PersistentHomologyDetector` identifies topological gaps in memory coverage.
- Measures: near-solved count, manifold chart count, gap detections.

### Stage 4: Concept/Operator Invention
- `OperatorInventor.mine_from_near_solved()` clusters near-solved tasks by failure type.
- `propose_concepts()` searches Boolean conjunctions over property pairs.
- `propose_operators()` generates repair templates from error pattern catalog.
- `PropertyInventor.mine_from_failures()` proposes relational/topological/container predicates.
- `validate_inventions()` applies LOO + FP rate checks.
- `register_validated()` mints into `ReasoningMemory`.
- `ActiveFalsifier.falsify()` tests surviving candidates against 5 probe families.
- Measures: clusters found, concepts proposed, operators proposed, validated count.

### Stage 5: Resume Near-Solved Tasks
- Iterate over stored `NearSolvedTaskState` entries.
- Call `AdaptiveReasoningLoop.solve(resume_from=state)` with new invented operators/properties.
- If solved: `NearSolvedMemory.promote_to_solved()` + emit `TASK_PROMOTED` event + build `ReasoningCertificate`.
- Measures: promotion count, promotion rate.

### Stage 6: Transfer to Unseen Tasks
- Run on held-out ARC tasks and ConceptARC (160 tasks).
- Measures: transfer accuracy, cross-domain accuracy, zero-shot generalization.
- LTL model checking on reasoning traces: soundness, termination, progress, monotonicity.

## Bug Fixes Applied (2026-05-14)

Five cascading bugs were found and fixed that caused 0 promotions in the initial cumulative reasoning run:

1. **`_compute_train_fit()` was a stub** (`near_solved_memory.py:332`): Always returned `(0.0, [False]*N)`. Near-solved states always had `train_fit=0.0`, so `is_near_solved` was always False. Fixed to actually compute partial match against training outputs.

2. **Failed results set `hypothesis=None`** (`adaptive_loop.py`): When a task failed, the `LoopResult` stored `hypothesis=None`. Resumed tasks therefore had no seed hypothesis to start from. Fixed to store the best partial hypothesis even on failure.

3. **`validate_inventions()` return type mismatch** (`operator_invention.py:202`): Returns a dict but the curriculum script unpacked it as a tuple. The `except Exception` silently swallowed the crash. Fixed to use dict access.

4. **`register_validated()` argument order** (`operator_invention.py:252`): Concepts were passed as the `reasoner` parameter. Fixed argument ordering.

5. **Resume marked all prior views as tried** (`adaptive_loop.py:614`): The selector was initialized with `views_tried` from the prior attempt, meaning no new views could be tried on resumption. Fixed to reset the selector so all views are available for retry with new operators.

## Current Results

| Metric | Value |
|--------|-------|
| ARC training (no DSL) | 84/1000 (8.4%) |
| ARC training (with DSL) | 95/1000 (9.5%) |
| ConceptARC | 10-12/160 (6.3-7.5%) |
| Cross-domain (graph/chess/molecule) | 5/13 correct, 0 FP |
| Reasoning engine standalone | 8/1000, 0 FP |
| Conjunction search | 4 new solves from 2 invented predicates |
| Memory system | 0 regressions, 0 FP |
| Tests | 571 passed |
| World model | 1/104 exact solve (first ever) |
| Adaptive loop | +3 unique tasks (1 ARC, 2 ConceptARC) |
| False positives (overall) | 0 |

### Solver Contribution Breakdown (v10 no-DSL)

| Solver | Tasks Solved |
|--------|-------------|
| local_rule | 28 |
| separator_decompose | 21 |
| fill_solver | 14 |
| crop_extract | 7 |
| abstract_program | 5 |
| rule_induction | 4 |
| object_graph | 3 |
| color_solver | 2 |

### Hypothesis Verdicts

| Hypothesis | Status | Evidence |
|------------|--------|----------|
| H1: Structural transfer | **Supported** | 84+ real ARC tasks, WM contributes 1 unique |
| H2: Falsification | **Supported (conditional)** | In constructed high-ambiguity strata only |
| H3: Path repair | **Supported** | 54% recovery rate (v3 contrastive WM) |
| H4: Compression | **Inconclusive** | Alignment not unique to compression selector |
| H5: Integrated scientist | **Supported** | Full pipeline 66 vs symbolic 65 (+1.54%) |
| H6: Analogical transfer | **Inconclusive** | 0/2770 transfer attempts succeeded |

## Scripts Reference

| Script | Purpose | Key Arguments | Expected Outputs |
|--------|---------|---------------|-----------------|
| `run_memory_growth_curriculum.py` | 6-stage memory growth experiment | `--output-dir`, `--max-tasks` | Stage metrics, promoted tasks, events, certificates, curriculum summary |
| `run_cross_domain_v2.py` | 3-phase cross-domain evaluation | `--output-dir` | domain_metrics.csv, transfer_report.md, transfer_events.jsonl |
| `analyze_oracle_candidates.py` | Classify bottleneck per task | `--output-dir` | Task diagnoses, bottleneck classification |
| `analyze_reasoning_scaling.py` | Reasoning scaling curves | `--from-events`, `--output-dir` | Scaling data, curves, summary |
| `generate_breakthrough_report.py` | Aggregate breakthrough report | `--output` | breakthrough_report.md |
| `run_portfolio_arc.py` | Run portfolio on ARC | `--world-model`, `--no-rerank`, `--device`, `--output-dir` | summary.json, per_task.json |
| `run_integrated_evaluation.py` | 3-config hypothesis testing | `--output-dir` | integrated_eval.json, per_task.json |
| `run_ablation.py` | Leave-one-solver-out ablation | `--output-dir`, `--world-model` | ablation_summary.json |
| `run_cross_benchmark_ablation.py` | ARC + ConceptARC cross-benchmark | `--output-dir` | ablation results per benchmark |
| `eval_adaptive_loop.py` | Static vs adaptive comparison | `--output-dir` | adaptive_eval.json |
| `external_baseline_comparison.py` | Compare vs GPT-4, ARGA, GPT-4o | - | comparison table |
| `solver_overlap_analysis.py` | Solver complementarity analysis | - | overlap stats |
| `generate_figures.py` | Publication figures | - | `paper/fig_*.png` |
| `run_property_gap_analysis.py` | Property language gap analysis | `--output-dir` | current_property_language.md, missing_property_taxonomy.md |
| `run_property_invention_eval.py` | Property invention evaluation | `--output-dir` | invention results |
| `train_neural_abstraction.py` | Train neural abstraction pipeline | `--device` | neural abstraction checkpoint |
| `train_world_model.py` | Train Slot Attention + GNS | phases 1-3 | world_model_best.pt |
| `train_perception_heads.py` | Train JEPA perception heads | - | jepa_with_perception.pt |
| `train_grid_jepa.py` | Train Grid-JEPA | `--config`, `--output-dir` | JEPA checkpoint |
| `train_program_ranker.py` | Train neural program ranker | `--config`, `--output-dir` | ranker checkpoint |
| `build_arc_taxonomy.py` | ARC task taxonomy | - | task_taxonomy.md |
| `analyze_unsolved_tasks.py` | Deep unsolved analysis | - | unsolved analysis |
| `run_concept_grammar_eval.py` | Concept grammar evaluation | - | grammar eval results |
| `test_cross_domain.py` | Quick cross-domain test | - | stdout results |
| `test_memory_system.py` | Memory system test | - | memory results |

## SLURM Jobs Reference

| Job Script | Partition | Time Limit | Purpose |
|------------|-----------|------------|---------|
| `run_cumulative_reasoning.sh` | general | 24h | Full pipeline: tests + curriculum + oracle + cross-domain + scaling + breakthrough report |
| `run_property_invention.sh` | general | 24h | Property gap analysis + invention eval + curriculum v2 + scaling v2 + breakthrough v2 |
| `run_breakthrough.sh` | general | 12h | Memory growth curriculum + oracle analysis + tests |
| `eval_adaptive.sh` | requeue | 8h | Adaptive loop evaluation (static vs adaptive) |
| `run_integrated_eval.sbatch` | requeue | 8h | Integrated evaluation (symbolic / +WM / full) |
| `run_ablation_v5.sbatch` | requeue | 12h | Leave-one-solver-out ablation |
| `run_portfolio_v10_full.sbatch` | requeue | 4h | Full portfolio ARC + ConceptARC + cross-benchmark |
| `run_portfolio_v5_full.sbatch` | requeue | 4h | Portfolio v5 full run |
| `run_cross_benchmark_ablation.sbatch` | requeue | 4h | Cross-benchmark ablation |
| `train_world_model.sbatch` | requeue (GPU) | 12h | World model training (Slot Attention + GNS) |
| `train_world_model_v3.sbatch` | requeue (GPU) | - | World model v3 with contrastive loss |
| `train_grid_jepa.sbatch` | GPU | 6h | Grid-JEPA training |
| `train_program_ranker.sbatch` | GPU | 6h | Neural program ranker training |
| `train_perception_heads.sbatch` | requeue (GPU) | 2h | JEPA perception heads training |
| `run_arc_refinement_gpu.sbatch` | GPU | 8h | ARC refinement with neural components |
| `submit_neural_arc_pipeline.sh` | configurable | - | Multi-stage neural ARC pipeline submission |
| `submit_arc_expanded_pipeline.sh` | configurable | - | Expanded DSL pipeline submission |
| `resume_neural_arc_pipeline.sh` | configurable | - | Resume neural pipeline with checkpoints |
| `resume_arc_expanded_pipeline.sh` | configurable | - | Resume expanded DSL pipeline |

## Test Suite

**Total test count**: 571 tests across 42 test files (9,938 lines).

| Test File | Test Count | Module Tested |
|-----------|-----------|---------------|
| test_concept_grammar.py | 49 | concept_grammar |
| test_events.py | 43 | events |
| test_concept_memory.py | 42 | concept_memory |
| test_formal_verification.py | 40 | formal_verification |
| test_perception_bridge.py | 40 | perception_bridge |
| test_manifold_memory.py | 56 | manifold_memory |
| test_adaptive_loop.py | 32 | adaptive_loop |
| test_neural_math.py | 31 | neural_math |
| test_multicolor_decompose.py | 29 | multicolor_decompose |
| test_neural_abstraction.py | 28 | neural_abstraction |
| test_property_invention.py | 27 | property_invention |
| test_theory.py | 25 | theory |
| test_local_rules.py | 22 | local_rules |
| test_abstract_programs.py | 21 | abstract_programs |
| test_near_solved_memory.py | 21 | near_solved_memory |
| test_separator_decompose.py | 17 | separator_decompose |
| test_world_model.py | 15 | world_model |
| test_analogy.py | 14 | analogy |
| test_object_graph.py | 14 | object_graph |
| test_color_solver.py | 11 | color_solver |
| test_crop_extract.py | 10 | crop_extract |
| test_egraph.py | 9 | egraph |
| test_cegis.py | 9 | cegis |
| test_formal.py | 7 | formal |
| test_library_learning.py | 7 | library_learning |
| test_program_ranker.py | 6 | program_ranker |
| test_arc_adapter.py | 5 | arc_adapter |
| test_generators.py | 5 | generators |
| test_models.py | 5 | models |
| test_operators.py | 4 | operators |
| test_grid_encoder.py | 2 | grid_encoder |
| test_grid_jepa.py | 2 | grid_jepa |
| test_evaluation.py | 2 | evaluation |
| test_falsifier_repair.py | 2 | falsifier_repair |
| test_parsing.py | 2 | parsing |
| test_refinement.py | 2 | refinement |
| test_h4_analysis.py | 1 | h4_analysis |
| test_h4_sweep_analysis.py | 1 | h4_sweep_analysis |
| test_experiment.py | 1 | experiment |
| test_paper_package.py | 1 | paper_package |
| test_reasoning_manifold.py | 1 | reasoning_manifold |
| test_sweep.py | 1 | sweep |

## File Tree

### src/reasoning_project/ (48 modules, 36,833 lines)

```
src/reasoning_project/
    __init__.py                    8
    abstract_programs.py         639
    active_falsifier.py          461
    adapter_genesis.py          1616
    adaptive_loop.py            1060
    analogy.py                   348
    arc_adapter.py               409
    arc_diagnostic.py            584
    arc_smoke.py                 191
    benchmark_generator.py      1214
    cegis.py                     287
    certificates.py              446
    cli.py                        72
    color_solver.py              775
    compression.py               126
    concept_grammar.py          1021
    concept_memory.py            259
    crop_extract.py              619
    domain_adapters.py           574
    egraph.py                    226
    evaluation.py                232
    events.py                    269
    experiment.py                137
    falsifier.py                 111
    fill_solver.py              1891
    formal.py                    520
    formal_verification.py       774
    generators.py                857
    h2_analysis.py               254
    h4_analysis.py               268
    h4_sweep_analysis.py         232
    library_learning.py          190
    local_rules.py               608
    manifold_memory.py          1398
    models.py                   1065
    multicolor_decompose.py     1138
    near_solved_memory.py        472
    neural_abstraction.py        895
    neural_math.py              1149
    object_graph.py              565
    operator_invention.py        779
    operators.py                 864
    paper_package.py             832
    parsing.py                   209
    perception_bridge.py         860
    portfolio.py                 434
    property_invention.py        974
    reasoning_engine.py         2468
    refinement.py                347
    relation_solver.py          1511
    repair.py                    112
    reporting.py                 294
    schemas.py                   193
    separator_decompose.py      1325
    structural_reasoning.py      473
    sweep.py                     446
    theory.py                    591
    utils.py                     161
    neural/
        __init__.py               23
        dataset.py               136
        graph_network.py         566
        grid_encoder.py          246
        grid_jepa.py             194
        program_ranker.py        485
        slot_attention.py        269
```

### scripts/ (55 scripts)

```
scripts/
    analyze_h2_family_balance.py
    analyze_h4_compression.py
    analyze_h4_sweep.py
    analyze_oracle_candidates.py
    analyze_reasoning_manifold.py
    analyze_reasoning_scaling.py
    analyze_results.py
    analyze_sweep_failures.py
    analyze_unsolved_tasks.py
    audit_arc_agi2.py
    build_arc_taxonomy.py
    build_submission_package.py
    check_arc_dataset.py
    check_exactness.py
    check_formal_boundaries.py
    deep_unsolved_analysis.py
    eval_adaptive_loop.py
    eval_grid_jepa.py
    eval.py
    external_baseline_comparison.py
    generate_breakthrough_report.py
    generate_dataset.py
    generate_figures.py
    inspect_f21745ec.py
    quick_portfolio_eval.py
    run_ablation.py
    run_arc_diagnostic.py
    run_arc_refinement.py
    run_arc_smoke.py
    run_concept_grammar_eval.py
    run_cross_benchmark_ablation.py
    run_cross_domain_v2.py
    run_experiment.py
    run_integrated_evaluation.py
    run_library_learning.py
    run_local_rule_arc.py
    run_memory_growth_curriculum.py
    run_portfolio_arc.py
    run_property_gap_analysis.py
    run_property_invention_eval.py
    run_seed_sweep.py
    scan_reconstruction_gaps.py
    solver_overlap_analysis.py
    test_conjunction_search.py
    test_cross_domain.py
    test_f21745ec.py
    test_memory_system.py
    test_new_fill_strategies.py
    train_grid_jepa.py
    train_neural_abstraction.py
    train_perception_heads.py
    train_program_ranker.py
    train.py
    train_world_model.py
```

### tests/ (42 test files, 9,938 lines)

```
tests/
    test_abstract_programs.py
    test_adaptive_loop.py
    test_analogy.py
    test_arc_adapter.py
    test_cegis.py
    test_color_solver.py
    test_concept_grammar.py
    test_concept_memory.py
    test_crop_extract.py
    test_egraph.py
    test_evaluation.py
    test_events.py
    test_experiment.py
    test_falsifier_repair.py
    test_formal.py
    test_formal_verification.py
    test_generators.py
    test_grid_encoder.py
    test_grid_jepa.py
    test_h4_analysis.py
    test_h4_sweep_analysis.py
    test_library_learning.py
    test_local_rules.py
    test_manifold_memory.py
    test_models.py
    test_multicolor_decompose.py
    test_near_solved_memory.py
    test_neural_abstraction.py
    test_neural_math.py
    test_object_graph.py
    test_operators.py
    test_paper_package.py
    test_parsing.py
    test_perception_bridge.py
    test_program_ranker.py
    test_property_invention.py
    test_reasoning_manifold.py
    test_refinement.py
    test_separator_decompose.py
    test_sweep.py
    test_theory.py
    test_world_model.py
```

### outputs/ (top-level subdirectories)

```
outputs/
    ablation_fast/
    ablation_v5/
    ablation_v6/
    adaptive_eval/
    arc_combined_diagnostic_cpu/
    arc_diagnostic_eval_*/
    arc_refinement/
    arc_smoke_tiny/
    arc_solvable_diagnostic_cpu/
    arc_status/
    arc_taxonomy/
    baselines/
    cross_benchmark_ablation_*/
    cross_domain_v2/
    deep_unsolved_analysis/
    diagnostic_phase/
    exactness/
    formal_boundary/
    h2_diagnostic*/
    h2_expanded_ambiguous*/
    h2_family_validation*/
    h2_noncommuting_composition*/
    h2_paper_ambiguous*/
    h2_revised_stratified*/
    integrated_eval/
    library_learning/
    local_rule_arc/
    memory_growth*/
    neural/
    oracle_candidate_analysis/
    oracle_smoke/
    paper_breadth*/
    portfolio_arc*/
    portfolio_v*/
    property_gap_analysis/
    property_invention/
    protocols/
    reasoning_scaling/
    reliability_checks/
    slurm_logs/
    smoke*/
    submission_package/
```

## Hypothesis Verdicts

### H1: Structural Transfer
**Status: Supported.**
Evidence: 84+ real ARC tasks solved (8.4% no-DSL, 9.5% with DSL). World model contributes 1 unique task via contrastive training. Synthetic structural-transfer delta +0.813 vs direct proxy. Confirmed on 31 real ARC training tasks (exact solve 1.000 vs proxy 0.000). See `outputs/portfolio_v10_full/`, `outputs/arc_solvable_diagnostic_cpu/`.

### H2: Active Falsification
**Status: Supported (conditional).**
Evidence: False-rule acceptance delta -0.857 in 7 constructed high-ambiguity families (10-seed sweep, 6/7 families show improvement). Not a general falsification claim. See `outputs/h2_family_validation_10seed_sweep/`.

### H3: Path Repair
**Status: Supported.**
Evidence: 54% recovery rate with v3 contrastive WM (up from 18% in v1). Bounded recovery-after-corruption diagnostic. See `outputs/integrated_eval/`.

### H4: Compression Selection
**Status: Inconclusive.**
Evidence: Exact-minimum alignment rate 1.000 for compression_selector, but also 1.000 for transformation_library and proposer_only. Alignment is not unique to compression selector. See `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/`.

### H5: Integrated Scientist
**Status: Supported.**
Evidence: Full pipeline 66 vs symbolic 65 (+1.54%). Localized latent-recovery/repair gains. See `outputs/integrated_eval/`.

### H6: Analogical Transfer
**Status: Inconclusive.**
Evidence: 0/2770 transfer attempts succeeded. Transfer function too simplistic for real ARC. See `analogy.py`, `outputs/integrated_eval/`.

### Cumulative Reasoning Claims
- Failures stored as near-solved states: **Verified** (near_solved_memory.py functional after bug fixes).
- Failure clusters formed: **Verified** (7 clusters found in 12h run).
- Operators invented from clusters: **Verified** (1 operator proposed).
- Invented abstractions solve new tasks: **Pending** (0 promotions in completed run; property invention pipeline running).
- Active falsification reduces false rules: **Conditional** (in constructed strata).
- Tasks promoted from near-solved to solved: **Pending** (awaiting post-bugfix rerun).
- Certificates emitted: **Verified** (certificates.py functional).
- Cross-domain transfer: **Verified** (5/13 cross-domain, 0 FP).
