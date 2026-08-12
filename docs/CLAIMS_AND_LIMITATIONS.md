# Claims and Limitations

This document states what we claim, what we do not claim, the specific limitations of the current system, and how to verify every assertion. It is intended to be read alongside `claim_traceability.md` and `limitations.md` in the project root.

---

## What We Claim

### 1. Cumulative reasoning through failure memory

The system stores structured records of every failed reasoning attempt -- the task signature, the candidate hypotheses that were tried, why they failed, and what properties were missing. On subsequent tasks, the memory is queried by structural similarity, and prior failures guide the search away from known dead ends and toward successful strategies observed on related tasks. This is not a prompt cache or a retrieval-augmented generation trick; it is a persistent, growing knowledge base of reasoning failures that changes the system's behavior over time.

**Evidence**: Memory growth curriculum results in `outputs/memory_growth/`, event log entries showing memory-guided solves, and the `StructuralReasoner` memory system producing 8/1000 correct with 0 false positives (4 from conjunction search, 4 from legacy solves).

### 2. Verifiable reasoning with certificates

Every solve produces a certificate: the exact program that was found, the input-output pairs it was verified against, and the verification result. The system does not output opaque confidence scores; it outputs executable programs that can be independently re-run. When the system says it solved a task, you can check by running the program yourself.

**Evidence**: All portfolio solver outputs include the candidate program, verification status, and per-pair match results in `per_task_results/`. The DSL, local-rule, and CEGIS solvers all produce executable candidate programs.

### 3. Cross-domain transfer with a single engine

The same reasoning engine -- without domain-specific modules, retraining, or prompt engineering -- operates on colored grids, graph problems, chess positions, molecular structures, counterfactual reasoning, and recombination tasks. The engine solves 8/27 cross-domain tasks with 0 false positives across all six domains.

**Evidence**: Cross-domain evaluation in `scripts/run_cross_domain_v2.py` and `scripts/test_cross_domain.py`. Per-domain breakdown: Grid 1/5, Graph 2/3, Chess 2/3, Molecule 1/2, Counterfactual 2/10, Recombination 0/4. Zero false positives.

### 4. Reasoning scaling without parameter scaling

Accuracy improves as the memory grows and as new abstractions are invented, without changing the model's parameters. This is a new scaling axis: the system gets better by accumulating experience, not by growing the network. The scaling analysis measures accuracy as a function of memory entries and abstraction count.

**Evidence**: Reasoning scaling analysis in `outputs/reasoning_scaling/`, memory growth curves, and the observation that the portfolio grew from 31 to 84+ solvable ARC tasks through solver family additions and memory-guided strategies, not through parameter changes.

---

## What We Do NOT Claim

### 1. We do not claim AGI

The system solves 84/1000 ARC training tasks (8.4%). State-of-the-art systems solve approximately 210/1000. The system fails on 916 tasks. It cannot do visual analogy, abstract pattern completion, multi-step conditional reasoning, or object-level semantic understanding beyond its operator vocabulary. This is a research architecture, not artificial general intelligence.

### 2. We do not claim a successor to the Transformer

The system is a reasoning scaffold built on top of standard components (program search, memory retrieval, neural encoders). It does not propose a new neural network architecture. The neural components (Slot Attention, GNS, Grid-JEPA, program rankers) are existing architectures applied to the reasoning pipeline. The contribution is the cumulative reasoning loop, not the individual components.

### 3. We do not claim that manifolds alone explain reasoning

The manifold-theoretic formalization (fiber bundles, geodesic reasoning, curvature triggers) provides a mathematical framing for the memory system and adapter genesis. These are organizational abstractions, not empirical claims. The system works because of concrete mechanisms (program search, failure memory, conjunction learning), not because reasoning lives on a manifold.

### 4. We do not claim a formal proof of intelligence

The exact bounded formal results (DSL minimality, small-category law checks, operator topology audits) are verified only inside declared finite systems. They do not establish exact Kolmogorov complexity, full category theory, HoTT, or broad topological invariant theorems. The formal layer is a diagnostic tool, not a proof system for intelligence.

### 5. We do not claim that ARC score proves AGI

ARC is used as an external-validity diagnostic, not as a benchmark for general intelligence. Our 8.4% coverage is a bounded positive on geometric and color primitives. It says nothing about the system's capacity for visual analogy, natural language reasoning, social cognition, or any of the other dimensions that AGI would require.

---

## Specific Limitations

### Property language coverage

The property language covers approximately 59 features (color histograms, symmetry detection, size statistics, spatial relations, connected-component properties, etc.). However, 46.7% of ARC tasks fail at the property-language stage -- the system cannot even describe the relevant structure, let alone solve the task. The missing features include object counting by shape, relative position encoding, pattern periodicity detection, and hierarchical part-whole decomposition.

### World model contribution

The Slot Attention + GNS world model, even after contrastive training (v3), contributes only 1-2 unique ARC task solves beyond what the symbolic solvers achieve. Its primary value is as a candidate reranker (H3 recovery rate 50%) and as a proof of concept for learned dynamics integration. It is not currently a significant source of new solves.

### Inconclusive hypotheses

- **H4 (causal compression)**: Weak/inconclusive. Exact bounded minimum alignment repeats across seeds, but several non-compression selectors also achieve exact minima. The causal/intervention metrics remain proxies, not true causal discovery.
- **H6 (analogical transfer)**: Inconclusive. 0 out of 2,770 analogical transfer attempts succeeded. The transfer function needs structural pattern matching beyond color remapping.

### Cumulative reasoning loop status

The promotion microcycle (near-solved → concept invention → validation → resume → solve) is mechanically sound: 2/2 promotions on synthetic tasks, 0 false positives. However, **0 promotions have been achieved on real ARC tasks**. The 24h all-in-one pipeline (job 13563935) produced 0 promotions due to cascading bugs (now fixed). Until nonzero real-ARC promotions are observed, the manuscript uses conditional language ("supports," "designed to") rather than "demonstrates" or "validates."

### Concept invention limitations

The conjunction search mechanism has invented 2 learned predicates (`any_sym_AND_is_largest_in_color_group`, `is_majority_shape_AND_in_top_half`) that contributed 4 new task solves. However, 0 invented concepts have been transferred to tasks outside their originating family. Concept invention exists but concept transfer does not, yet.

### ARC coverage gap

The system solves 84/1000 ARC training tasks (8.4%). The best published systems solve approximately 210/1000 (21%). The gap of 126 tasks represents the system's inability to handle:

- Color permutation tasks (283 unsolved out of 284 in this category)
- Crop/extract tasks (203 unsolved after separator solver)
- Local-rule tasks (161 unsolved out of the category)
- Tasks requiring visual analogy or abstract pattern completion
- Tasks requiring multi-step conditional reasoning
- Tasks requiring object-level semantic understanding

### DreamCoder-style library learning

Library learning (`scripts/run_library_learning.py`) currently finds 0 reusable program fragments. Most solutions are depth-1 programs, making fragment mining a readiness artifact rather than evidence of abstraction growth.

### Neural-guided reasoning

The neural pipeline (Grid-JEPA, program rankers, refinement loops) is implemented and traceable but has not demonstrated ARC-transfer gains. Synthetic held-out top-1 accuracy reaches 0.833-1.000, but ARC exact/pass@2 remains 0.000/0.000 on the current evaluation slices.

---

## Reproducibility

### All experiments are reproducible via scripts

Every result in this project was produced by a script in `scripts/` with a configuration in `configs/`. No result depends on interactive notebook sessions, manual parameter tuning, or unreproducible ad-hoc commands. To reproduce any result, activate the environment, find the corresponding script and config, and run it.

### All claims point to artifacts

Every claim in `claim_traceability.md` maps to a specific artifact (a JSON file, a markdown summary, or a figure) in `outputs/`. The traceability table lists: hypothesis, active wording, implementing modules, task families, primary metrics, supporting artifacts, and current verdict. If a claim cannot point to an artifact, it is not made.

### Event log provides full audit trail

Every experiment writes an event log (`event_log.jsonl`) that records, in chronological order: task ID, solver attempted, candidates generated, candidate selected, verification result, memory operations, abstraction operations, and timing. This log is the ground truth for what happened during any experiment. It can be replayed, filtered, and audited independently of the summary statistics.

### Seed sweeps and paired contrasts

Key results use multi-seed sweeps (5, 10, or 20 seeds) with paired contrasts -- the same seed runs with and without the mechanism under test. Paired deltas are reported with per-seed breakdowns. This controls for task sampling variance and makes the evidence auditable at the individual-seed level.

### Pre-registered protocol

The ARC evaluation follows a pre-registered protocol (`docs/pre_registered_arc_protocol.md`) that specifies allowed and disallowed data usage, candidate budgets per solver, maximum runtime per task, and the separation between development (training split) and evaluation (evaluation split) data.
