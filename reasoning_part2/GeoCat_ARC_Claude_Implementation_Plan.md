# GeoCat-ARC Claude Code Implementation Plan

Use this as a Claude Code implementation prompt.

---

You are working inside an ARC-style reasoning solver repository. Your task is to implement a real, robust, non-surrogate system called **GeoCat-ARC: Bayesian-Categorical Program Search with Information-Geometric Memory for Verifiable Abstract Reasoning**.

Do not create toy replacements, fake objectives, fake ARC data, random surrogate scores, or purely conceptual stubs. Every implemented component must either execute on real ARC task JSON files, transform real grids, evaluate real candidate programs, store real traces, or run real tests. If a component cannot be completed in one pass, implement the smallest real version that works end-to-end and document what remains incomplete.

Core principle:

- ARC tasks are not treated as raw grids only.
- Each task must be parsed into objects, relations, predicates, candidate transformations, belief distributions, executable programs, and verifiable traces.
- Candidate programs must actually run on input grids and produce output grids.
- Bayesian search must use real candidate-program scores from real task examples.
- New operators must be promoted only after verification and regression checks.

---

## PHASE 0 — Audit and Baseline

1. Inspect the repository structure.
2. Identify existing ARC loaders, solvers, DSL operators, tests, experiment runners, and output directories.
3. Do not overwrite existing work. Create a new module namespace or project folder named `geocat_arc` unless the repo already has a suitable architecture.
4. Add a baseline runner:
   - loads real ARC JSON tasks,
   - runs the existing solver if available,
   - records solved/near-solved/failed tasks,
   - writes `artifacts/geocat_arc/baseline_results.json`,
   - writes `artifacts/geocat_arc/baseline_failures.jsonl`,
   - writes `artifacts/geocat_arc/run_manifest.json`.
5. Define near-solved concretely using normalized cell accuracy and object-level similarity.
6. Add tests proving the baseline runner can load and evaluate at least a small real subset of ARC tasks.

---

## PHASE 1 — ARC Data and Perception

Implement:

```text
geocat_arc/data/arc_loader.py
geocat_arc/data/arc_task.py
geocat_arc/data/validate_arc.py
geocat_arc/perception/grid.py
geocat_arc/perception/segmentation.py
geocat_arc/perception/objects.py
geocat_arc/perception/relations.py
geocat_arc/perception/matching.py
geocat_arc/perception/change_detection.py
```

Requirements:

- Load real ARC task JSON files.
- Validate rectangular integer grids with colors 0–9.
- Extract connected components using configurable 4-connectivity and 8-connectivity.
- Detect bounding boxes, masks, holes, frames, lines, object sizes, colors, and positions.
- Build relation graphs: left/right/above/below, containment, adjacency, overlap, same color, same shape, same size.
- Match input objects to output objects using shape/color/size/location similarity.
- Emit a scene graph for each input and output.
- Add unit tests for all core perception functions.

---

## PHASE 2 — Finite Visual Logic / Topos-Like Predicate Layer

Implement:

```text
geocat_arc/visual_logic_topos/predicates.py
geocat_arc/visual_logic_topos/proposition.py
geocat_arc/visual_logic_topos/finite_logic.py
geocat_arc/visual_logic_topos/quantifiers.py
geocat_arc/visual_logic_topos/rule_templates.py
geocat_arc/visual_logic_topos/truth_table.py
```

Requirements:

- Implement real finite predicates over extracted ARC objects and regions.
- Predicates must include color, shape, size, spatial, containment, border, symmetry, and relation predicates.
- Implement AND, OR, NOT, IMPLIES, EXISTS, and FORALL over finite object sets.
- Rule templates must be evaluable against real scene graphs.
- Do not claim full mathematical topos implementation. Call this a finite visual-logic/topos-inspired layer.
- Add tests where visual objects are translated into propositions and truth values.

---

## PHASE 3 — Typed Categorical DSL

Implement:

```text
geocat_arc/categorical_dsl/types.py
geocat_arc/categorical_dsl/morphism.py
geocat_arc/categorical_dsl/program.py
geocat_arc/categorical_dsl/type_checker.py
geocat_arc/categorical_dsl/operators_basic.py
geocat_arc/categorical_dsl/operators_spatial.py
geocat_arc/categorical_dsl/operators_color.py
geocat_arc/categorical_dsl/operators_symmetry.py
geocat_arc/categorical_dsl/composition.py
```

Requirements:

- Define real typed objects: Grid, Object, ObjectSet, Region, Mask, Color, Vector, Axis, RelationGraph, Program.
- Each operator must have input types, output type, preconditions, postconditions, cost, and executable apply method.
- Implement real operators: segment, select, filter, recolor, translate, rotate, reflect, copy, place, crop, fill_region, complete_symmetry, render.
- Type-check candidate compositions before execution.
- Invalid compositions must be rejected.
- Programs must execute on ARC input grids and return output grids.
- Add tests for type checking, operator execution, and program composition.

---

## PHASE 4 — Bayesian Program Search

Implement:

```text
geocat_arc/bayesian_program_search/candidate_generator.py
geocat_arc/bayesian_program_search/program_features.py
geocat_arc/bayesian_program_search/real_objective.py
geocat_arc/bayesian_program_search/bayes_ranker.py
geocat_arc/bayesian_program_search/acquisition.py
geocat_arc/bayesian_program_search/search_loop.py
geocat_arc/bayesian_program_search/search_trace.py
```

Requirements:

- Generate candidate programs from the typed DSL, not arbitrary strings.
- Extract real candidate features: operator sequence, depth, predicate matches, relation matches, shape/color/spatial signatures, complexity, memory prior.
- Evaluate every selected candidate by actually executing it on the ARC training input grids.
- Objective must include exact match, normalized cell accuracy, object match score, relation preservation score, and complexity penalty.
- Implement a real Bayesian ranking/acquisition loop over discrete candidate programs.
- If BoTorch is available, use it for GP/acquisition over candidate embeddings. If not, implement a real Bayesian linear or Gaussian-process-style ranker using available dependencies. Do not use random scores.
- Store every search iteration as JSONL with posterior mean, uncertainty, acquisition score, real evaluation score, and exact-match status.
- Add tests proving that the Bayesian ranker updates from observed real scores and changes candidate ordering.

---

## PHASE 5 — Information-Geometric Memory

Implement:

```text
geocat_arc/information_geometric_memory/belief_distribution.py
geocat_arc/information_geometric_memory/distance_metrics.py
geocat_arc/information_geometric_memory/memory_atom.py
geocat_arc/information_geometric_memory/memory_store.py
geocat_arc/information_geometric_memory/importance_estimator.py
geocat_arc/information_geometric_memory/retrieval.py
geocat_arc/information_geometric_memory/drift_monitor.py
```

Requirements:

- Represent task belief distributions over operators, predicates, relations, parameters, and failure types.
- Implement KL divergence, Jensen-Shannon divergence, Hellinger distance, and categorical Fisher-Rao approximation.
- Store solved tasks as memory atoms with program, trace, belief distributions, importance weights, and certificate path.
- Store near-solved failures as failure memory atoms.
- Implement memory retrieval by distributional distance.
- Estimate symbolic importance using ablation sensitivity: remove/perturb operator, predicate, or relation and measure solve-score degradation.
- If a learned router exists, add diagonal Fisher-like importance from squared log-probability gradients.
- Add tests for distribution normalization, distance metrics, memory serialization, memory retrieval, and importance estimation.

---

## PHASE 6 — Failure Clustering and Verified Operator Invention

Implement:

```text
geocat_arc/operator_invention/failure_atom.py
geocat_arc/operator_invention/failure_clustering.py
geocat_arc/operator_invention/operator_schema_induction.py
geocat_arc/operator_invention/prepostcondition_miner.py
geocat_arc/operator_invention/invented_operator.py
geocat_arc/operator_invention/verifier.py
geocat_arc/operator_invention/promotion_registry.py
```

Requirements:

- Convert near-solved traces into failure atoms with cell error maps, object error maps, and failure distributions.
- Cluster failures using operator/predicate/relation/failure-distribution distances.
- Propose a new operator only when a stable cluster exists.
- Induce typed signatures, preconditions, and postconditions.
- Implement at least one real invented-operator path, such as `copy_to_position : Object × Region → Object` or `complete_symmetric_partner : ObjectSet × Axis → ObjectSet`, only if supported by actual failure clusters.
- Verify invented operators on real tasks.
- Promotion requires:
  1. exact training-example solve on target tasks,
  2. leave-one-task-out cluster validation when cluster size permits,
  3. negative/reject tests,
  4. old solved-task regression,
  5. written certificate JSON.
- Add tests proving an invented operator cannot be promoted without a certificate.

---

## PHASE 7 — Neuro-Cognitive Diagnostics

Implement:

```text
geocat_arc/neuro_cognitive/hebbian_memory.py
geocat_arc/neuro_cognitive/predictive_error.py
geocat_arc/neuro_cognitive/vicarious_reward.py
geocat_arc/neuro_cognitive/cognitive_trace.py
```

Requirements:

- Hebbian memory updates predicate/operator association strengths after successful solves.
- Predictive error computes localized mismatch between predicted and target output grids.
- Vicarious reward updates priors for operators responsible for successful transformations.
- Cognitive trace records observe → predict → compare → update → verify steps.
- This layer should not be required for the solver to run; it should add interpretable diagnostics.
- Do not add Brian/Nengo as required dependencies. They can be optional later experiments only.

---

## PHASE 8 — Experiments and Reports

Implement:

```text
geocat_arc/experiments/run_baseline.py
geocat_arc/experiments/run_ablation.py
geocat_arc/experiments/run_full_system.py
geocat_arc/experiments/evaluate_results.py
geocat_arc/experiments/make_figures.py
```

Required ablations:

```text
A0 existing baseline
A1 perception only
A2 typed categorical DSL
A3 visual logic predicates
A4 Bayesian program search
A5 information-geometric memory retrieval
A6 failure clustering
A7 verified operator invention
A8 neuro-cognitive diagnostics
```

Required metrics:

```text
tasks attempted
tasks solved
near-solved count
exact train solve rate
candidate evaluations per task
runtime per task
memory retrieval precision
old solved-task retention
false promotion rate
near-solved-to-solved conversion
tasks solved uniquely by invented operators
```

Required artifacts:

```text
artifacts/geocat_arc/results/ablation_table.csv
artifacts/geocat_arc/results/summary.json
artifacts/geocat_arc/certificates/*.json
artifacts/geocat_arc/failures/*.jsonl
artifacts/geocat_arc/memory/*.json
artifacts/geocat_arc/figures/*.png
artifacts/geocat_arc/PROJECT_STATUS.md
```

Quality requirements:

- Every module must have tests.
- Every experiment must write a run manifest.
- Do not silently skip failures.
- If a dependency is missing, implement a dependency-light real fallback or document the missing dependency clearly.
- Do not overwrite old results; timestamp run directories.
- At the end, run the test suite and at least one real ARC subset experiment.
- Write a final status report summarizing implemented modules, passing tests, solved tasks, failures, limitations, and next steps.
