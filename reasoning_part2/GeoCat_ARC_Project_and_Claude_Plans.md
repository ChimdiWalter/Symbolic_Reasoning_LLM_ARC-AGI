# GeoCat-ARC Project Plan

## Project Title

**GeoCat-ARC: Bayesian-Categorical Program Search with Information-Geometric Memory for Verifiable Abstract Reasoning**

## Core thesis

ARC tasks should be solved by a system that observes examples, converts them into object/relation/proposition structures, searches typed compositional programs using Bayesian optimization, stores solved and failed reasoning traces as information-geometric memory, and invents new operators only when failure clusters are stable and verifiable.

Information geometry treats AI learning as movement through distributions of beliefs, predictions, and uncertainty rather than raw parameters. In the ARC-specific framing, each task can be represented as a probability distribution over reasoning traces, with solved tasks becoming Fisher-weighted memory regions and near-solved failures becoming geometric gaps for operator invention.

ARC-AGI-1 is a useful starting benchmark because it consists of grid-based tasks where systems infer hidden transformations from small numbers of examples.

---

## 1. System Overview

The system should have eight real modules:

```text
GeoCat-ARC
│
├── 1_data_arc/
│   └── real ARC task loading, validation, splits
│
├── 2_perception/
│   └── grid → objects → relations → predicates
│
├── 3_visual_logic_topos/
│   └── finite predicate logic over objects, regions, and relations
│
├── 4_categorical_dsl/
│   └── typed operators/morphisms and valid program composition
│
├── 5_bayesian_program_search/
│   └── real candidate evaluation + Bayesian acquisition
│
├── 6_information_geometric_memory/
│   └── belief distributions, KL/JS retrieval, Fisher-like importance
│
├── 7_operator_invention/
│   └── near-solved failure clustering → typed operator proposal → verification
│
└── 8_experiments/
    └── baselines, ablations, certificates, reports, figures
```

Data flow:

```text
ARC task
  ↓
Grid/object perception
  ↓
Predicate + relation extraction
  ↓
Typed categorical DSL candidate generation
  ↓
Bayesian program search
  ↓
Execute candidate programs on real training examples
  ↓
Exact solve / near-solve / fail classification
  ↓
Information-geometric memory update
  ↓
Operator invention if repeated failure cluster is verified
  ↓
Regression tests against old solved tasks
```

---

## 2. Non-Negotiable Implementation Rules

### Rule 1: Use real ARC JSON tasks

Use the official ARC-AGI task format. Do not replace ARC with toy grids.

Required loader outputs:

```text
task_id
train_pairs
test_inputs
grid_shape_metadata
color_palette
```

Validation checks:

```text
all grids rectangular
all colors in 0–9
train pairs nonempty
input/output grids parsed as integer arrays
```

### Rule 2: Every candidate program must be executable

No semantic-score-only programs. A candidate must produce an output grid.

```python
predicted_output = program.apply(input_grid)
```

### Rule 3: Bayesian optimization must score real candidate evaluations

The optimizer may estimate expected improvement or uncertainty, but its observations must come from real executions:

```text
candidate program → execute on train pairs → compute real fit score
```

No fake objective functions.

### Rule 4: Topos/category theory must compile to working code

The category layer must enforce input/output types. The topos-like layer must produce actual predicates and truth values.

### Rule 5: Operator invention requires verification

A new operator is not accepted because it sounds plausible. It must:

```text
solve at least one target failure cluster
pass train examples exactly
pass negative/reject tests
not break previous solved-task certificates
have preconditions and postconditions
have a typed signature
```

---

## 3. Phase-by-Phase Plan

## Phase 0 — Baseline Audit and Reproducibility

Goal: establish the current baseline before adding new theory.

Deliverables:

```text
baseline_run.py
baseline_results.json
baseline_failures.jsonl
baseline_near_solved.jsonl
run_manifest.json
```

Required metrics:

```text
tasks_attempted
tasks_solved
exact_train_solve_rate
public_eval_attempted if available
average_candidates_tested
median_runtime_per_task
near_solved_count
failure_type_histogram
```

Near-solved definition:

```text
near_solved if:
    normalized_cell_accuracy >= 0.80
    OR object-level match >= 0.70
    OR all examples correct except one localized transformation error
```

Do not add new methods until this baseline is frozen.

---

## Phase 1 — Real ARC Perception Layer

Goal: convert raw grids into object-centric structures.

Implement:

```text
Grid
Cell
ObjectMask
Object
Region
RelationGraph
SceneGraph
```

Object extraction should support:

```text
single-color connected components
multi-color object grouping
background detection
holes
frames
lines
rectangles
symmetry axes
bounding boxes
touching / adjacency
containment
relative position
```

Required outputs per train pair:

```json
{
  "task_id": "...",
  "example_id": 0,
  "input_objects": [],
  "output_objects": [],
  "input_relations": [],
  "output_relations": [],
  "detected_changes": []
}
```

Tests:

```text
test_connected_components.py
test_bounding_boxes.py
test_holes_frames.py
test_relation_graph.py
test_object_matching.py
```

Object matching should compare input/output objects using shape similarity, color similarity, size, location, containment, and relative displacement.

---

## Phase 2 — Finite Visual Logic / Topos-Like Layer

Goal: translate visual objects into logical propositions.

Do not attempt full abstract topos theory first. Implement a finite visual logic engine that is actually usable.

Predicates:

```text
Color predicates:
    Red(x), Blue(x), SameColor(x,y)

Shape predicates:
    SameShape(x,y), Rectangle(x), Line(x), HasHole(x)

Size predicates:
    Largest(x), Smallest(x), SameSize(x,y)

Spatial predicates:
    Inside(x,y), TouchesBorder(x), LeftOf(x,y), Above(x,y)

Relational predicates:
    Aligned(x,y), SymmetricAbout(x,axis), RepeatedPattern(S)
```

Logical operations:

```text
AND
OR
NOT
IMPLIES
FORALL over finite object set
EXISTS over finite object set
```

This gives a finite Boolean/Heyting-style logic over each grid scene.

Example:

```text
Red(x) ∧ Square(x) ∧ Inside(x, Frame)
```

The solver should be able to form rule templates:

```text
∀x: Red(x) ∧ TouchesBorder(x) → MoveToCenter(x)
```

Implementation files:

```text
visual_logic_topos/
    predicates.py
    finite_logic.py
    proposition.py
    quantifiers.py
    rule_templates.py
    truth_table.py
```

Tests:

```text
test_predicates.py
test_quantifiers.py
test_rule_template_matching.py
test_truth_preservation.py
```

---

## Phase 3 — Categorical DSL: Typed Compositional Operators

Goal: make every ARC operation a typed morphism.

Define types:

```text
Grid
Object
ObjectSet
Region
Mask
Color
Vector
Axis
RelationGraph
Program
```

Define morphism interface:

```python
class Morphism:
    name: str
    input_types: tuple
    output_type: Type
    preconditions: list[Predicate]
    postconditions: list[Predicate]
    cost: float

    def applicable(self, scene) -> bool:
        ...

    def apply(self, *args):
        ...
```

Core operators:

```text
segment           : Grid → ObjectSet
select            : ObjectSet × Predicate → Object
filter            : ObjectSet × Predicate → ObjectSet
translate         : Object × Vector → Object
recolor           : Object × Color → Object
rotate            : Object × Angle → Object
reflect           : Object × Axis → Object
copy              : Object → Object
place             : Object × Region → GridPatch
render            : ObjectSet → Grid
crop              : Grid × Region → Grid
fill_region       : Region × Color → GridPatch
complete_symmetry : ObjectSet × Axis → ObjectSet
```

Composition rule:

```text
f : A → B
g : B → C
then g ∘ f : A → C
```

Invalid compositions must be rejected before execution.

Example invalid path:

```text
rotate(Color)
```

should fail at type-checking time.

Implementation files:

```text
categorical_dsl/
    types.py
    morphism.py
    operators_basic.py
    operators_spatial.py
    operators_color.py
    operators_symmetry.py
    composition.py
    type_checker.py
    program.py
```

Tests:

```text
test_type_checker.py
test_operator_contracts.py
test_program_composition.py
test_render_inverse.py
```

---

## Phase 4 — Bayesian Program Search

Goal: replace brute-force search with uncertainty-aware candidate selection.

BoTorch is a strong option because it is a Bayesian optimization framework built on PyTorch, with support for custom models, acquisition functions, GPU/autograd, and scalable Gaussian processes via GPyTorch. However, for ARC, the search space is mostly discrete. So implement discrete Bayesian candidate ranking first, then optionally use BoTorch for acquisition over candidate embeddings.

Candidate program features:

```text
operator sequence
program depth
number of objects touched
predicate matches
relation matches
input/output shape compatibility
color-change signature
spatial-change signature
memory prior score
complexity cost
```

Real objective:

```text
score(program, task)
=
exact_match_bonus
+ normalized_cell_accuracy
+ object_match_score
+ relation_preservation_score
- complexity_penalty
- invalidity_penalty
```

Candidate evaluation:

```python
for program in candidate_pool:
    predicted_outputs = [program.apply(pair.input) for pair in train_pairs]
    real_score = evaluate(predicted_outputs, train_outputs)
    update_bayes_model(program_features, real_score)
```

Acquisition:

```text
UCB:
    acquisition = mean + kappa * uncertainty

Expected improvement:
    acquisition = expected improvement over best observed candidate

Thompson:
    sample candidate utility from posterior
```

Implementation files:

```text
bayesian_program_search/
    candidate_generator.py
    program_features.py
    real_objective.py
    bayes_ranker.py
    acquisition.py
    search_loop.py
    search_trace.py
```

Search trace output:

```json
{
  "task_id": "...",
  "iteration": 12,
  "candidate_program": "...",
  "posterior_mean": 0.74,
  "posterior_uncertainty": 0.18,
  "acquisition_score": 0.92,
  "real_score": 0.81,
  "exact_match": false
}
```

Tests:

```text
test_candidate_generation.py
test_real_objective.py
test_bayes_ranker_updates_from_real_scores.py
test_acquisition_orders_candidates.py
```

---

## Phase 5 — Information-Geometric Memory

Goal: store solved and failed tasks as distributions, not just examples.

Memory atom:

```json
{
  "task_id": "...",
  "status": "solved",
  "program": "...",
  "trace": [],
  "operator_distribution": {},
  "predicate_distribution": {},
  "relation_distribution": {},
  "parameter_distribution": {},
  "failure_distribution": null,
  "importance_weights": {},
  "certificate_path": "..."
}
```

Belief distributions:

```text
p(operator | task)
p(predicate | task)
p(relation | task)
p(parameter_family | task)
p(failure_type | near_solved_trace)
```

Distance metrics:

```text
KL divergence
Jensen-Shannon divergence
Hellinger distance
Fisher-Rao approximation for categorical distributions
```

Retrieval:

```python
similar_memories = memory.retrieve(
    query_distribution=current_task_belief,
    metric="js",
    top_k=20
)
```

Fisher-like importance:

For a learned router/ranker:

```text
importance(parameter_j) = squared gradient of log probability of successful trace
```

For symbolic-only version:

```text
importance(operator/predicate/relation) =
    sensitivity of solve score when that component is removed or perturbed
```

Implementation files:

```text
information_geometric_memory/
    belief_distribution.py
    distance_metrics.py
    memory_atom.py
    memory_store.py
    importance_estimator.py
    retrieval.py
    drift_monitor.py
```

Tests:

```text
test_distribution_normalization.py
test_js_distance.py
test_memory_retrieval.py
test_importance_ablation.py
test_memory_serialization.py
```

---

## Phase 6 — Failure Clustering and Operator Invention

Goal: invent operators from repeated real failures.

Near-solved failure atom:

```json
{
  "task_id": "...",
  "candidate_program": "...",
  "predicted_outputs": [],
  "target_outputs": [],
  "cell_error_map": [],
  "object_error_map": [],
  "failure_distribution": {
    "missing_operator": 0.72,
    "wrong_parameter": 0.15,
    "wrong_object_binding": 0.08,
    "perception_failure": 0.05
  }
}
```

Cluster near-solved failures by:

```text
operator distribution similarity
predicate distribution similarity
relation distribution similarity
error map similarity
missing transformation signature
```

Trigger operator invention only when:

```text
cluster_size >= threshold
average_near_solved_score >= threshold
failure_distribution entropy is low
existing operators cannot solve cluster
candidate invented operator has clear typed signature
```

Example invented operator:

```text
copy_to_position : Object × Region → Object
```

Preconditions:

```text
source object exists
target region exists
target region is empty or overwrite_allowed
source object shape is renderable inside target
```

Postconditions:

```text
same_shape(output_object, source_object)
same_color(output_object, source_object)
inside(output_object, target_region)
```

Verification:

```text
solve all examples in cluster
leave-one-task-out validation
counterexample rejection
old solved-task regression
certificate emitted
```

Implementation files:

```text
operator_invention/
    failure_atom.py
    failure_clustering.py
    operator_schema_induction.py
    prepostcondition_miner.py
    invented_operator.py
    verifier.py
    promotion_registry.py
```

Tests:

```text
test_failure_clustering.py
test_prepostcondition_mining.py
test_invented_operator_execution.py
test_operator_promotion_requires_certificate.py
test_old_task_regression.py
```

---

## Phase 7 — Neuro-Cognitive Grounding Layer

This should be a real diagnostic layer, not the core solver at first.

For this project, implement the cognitive abstraction first:

```text
Hebbian association table:
    predicate/operator coactivation counts

Predictive coding:
    predicted output vs target output
    localized error map

Vicarious reward:
    successful examples increase priors for responsible operators
```

Implementation:

```text
neuro_cognitive/
    hebbian_memory.py
    predictive_error.py
    vicarious_reward.py
    cognitive_trace.py
```

Only after the symbolic/geometric system works, add optional experiments:

```text
Brian2 spiking associative memory for predicate/operator coactivation
Nengo working-memory model for maintaining candidate rule beliefs
```

Do not make Brian/Nengo a dependency for the main ARC solver.

---

## 4. Experimental Plan

Baselines:

```text
A0: existing baseline solver
A1: baseline + improved perception only
A2: A1 + typed categorical DSL
A3: A2 + visual logic predicates
A4: A3 + Bayesian program search
A5: A4 + information-geometric memory retrieval
A6: A5 + failure clustering
A7: A6 + verified operator invention
A8: A7 + cognitive Hebbian/predictive update diagnostics
```

Metrics:

```text
train tasks solved
public eval tasks solved if available
exact match solve rate
median search iterations
median runtime
candidate evaluations per solve
old solved-task retention
certificate re-pass rate
operator forgetting rate
KL/JS drift of operator distribution
memory retrieval precision
number of invented operators
number promoted
promotion precision
false positive rate
near-solved to solved conversion
tasks solved uniquely by invented operators
Bayesian search vs brute-force candidate count
time-to-first-exact-solve
best score after N evaluations
acquisition calibration
```

Ablation table:

| System | Solved | Near-solved | Candidate evals | Runtime | False promotions | Retention |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | | | | | | |
| + typed DSL | | | | | | |
| + visual logic | | | | | | |
| + Bayesian search | | | | | | |
| + info-geometry memory | | | | | | |
| + operator invention | | | | | | |

---

## 5. Repository Structure

```text
geocat_arc/
├── data/
│   ├── arc_loader.py
│   ├── arc_task.py
│   └── validate_arc.py
│
├── perception/
│   ├── grid.py
│   ├── objects.py
│   ├── segmentation.py
│   ├── relations.py
│   ├── matching.py
│   └── change_detection.py
│
├── visual_logic_topos/
│   ├── predicates.py
│   ├── proposition.py
│   ├── finite_logic.py
│   ├── quantifiers.py
│   └── rule_templates.py
│
├── categorical_dsl/
│   ├── types.py
│   ├── morphism.py
│   ├── program.py
│   ├── type_checker.py
│   ├── operators_basic.py
│   ├── operators_spatial.py
│   ├── operators_color.py
│   └── operators_symmetry.py
│
├── bayesian_program_search/
│   ├── candidate_generator.py
│   ├── program_features.py
│   ├── real_objective.py
│   ├── bayes_ranker.py
│   ├── acquisition.py
│   └── search_loop.py
│
├── information_geometric_memory/
│   ├── belief_distribution.py
│   ├── distance_metrics.py
│   ├── memory_atom.py
│   ├── memory_store.py
│   ├── importance_estimator.py
│   └── retrieval.py
│
├── operator_invention/
│   ├── failure_atom.py
│   ├── failure_clustering.py
│   ├── operator_schema_induction.py
│   ├── prepostcondition_miner.py
│   ├── verifier.py
│   └── promotion_registry.py
│
├── neuro_cognitive/
│   ├── hebbian_memory.py
│   ├── predictive_error.py
│   ├── vicarious_reward.py
│   └── cognitive_trace.py
│
├── experiments/
│   ├── run_baseline.py
│   ├── run_ablation.py
│   ├── run_full_system.py
│   ├── evaluate_results.py
│   └── make_figures.py
│
├── tests/
│   └── ...
│
└── artifacts/
    ├── runs/
    ├── certificates/
    ├── failures/
    ├── memory/
    └── figures/
```

---

## 6. What Makes This Novel

The novelty is the integration:

1. Visual topos-like logic converts ARC scenes into propositions.
2. Categorical DSL ensures only valid typed transformations are composed.
3. Bayesian optimization searches over real executable programs using real ARC feedback.
4. Information-geometric memory stores solved/failure traces as distributions.
5. Verified operator invention converts stable failure geometry into new DSL operators.
6. Neuro-cognitive layer gives an interpretable model of prediction, error, association, and memory.

Strong paper claim:

> We introduce a neuro-cognitive geometric-categorical ARC solver in which task examples are represented as visual propositions, candidate rules are typed morphism compositions, program search is guided by Bayesian acquisition over real execution feedback, and repeated near-solved failures induce verified operator invention through information-geometric memory.

---

## 7. Final Implementation Priority

Build in this order:

```text
1. ARC loader + baseline
2. perception + predicates
3. typed categorical DSL
4. executable candidate programs
5. real candidate scoring
6. Bayesian search
7. information-geometric memory
8. near-solved failure clustering
9. verified operator invention
10. full ablation experiments
```

The most important rule:

> Do not let category theory, topos theory, information geometry, or neuroscience remain as labels. Each one must become a working module with inputs, outputs, tests, metrics, and failure cases.


---

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
