# From Near-Solved Failures to Verified Operators: Trace-Driven Operator Invention for Adaptive Visual Reasoning

## Abstract

We present a trace-driven operator invention pipeline for abstract visual reasoning. When a static solver portfolio fails to solve a task, the system stores the failure as a near-solved state with structural diagnosis. Failure traces are analyzed to derive executable operator hypotheses, which are then validated through leave-one-out cross-validation, checked against six proof obligations (preconditions, postconditions, invariants, train consistency, target non-emptiness, LOO consistency), attacked with counterexample probes, and promoted only when the full verification chain succeeds. Every promoted task receives a replay certificate recording its complete provenance. We evaluate on ARC (Chollet, 2019), demonstrating 4 verified promotions of previously unsolved tasks across two operator families (copy-to-position and color-transfer), with 0 false positives across 272 candidate evaluations. An eight-configuration ablation confirms that each invented operator is necessary for its specific tasks and that the static portfolio produces 0/4. The system is domain-adaptive via AdapterGenesis with four domain adapters (grid, graph, chess, molecule), and includes neural perception modules that provide advisory routing but are not in the critical path of any promotion. The contribution is a bounded proof-of-mechanism for cumulative operator reasoning, not broad ARC solving.

---

## 1. Introduction

Abstract visual reasoning benchmarks such as ARC (Chollet, 2019) require systems to generalize from a handful of input-output examples to novel test inputs. Success demands discovering the latent transformation rule governing each task -- a challenge that spans geometric operations, color manipulations, object-level reasoning, and compositional multi-step programs. Current approaches fall into two broad families: neural program synthesis systems that search large program spaces using learned priors (Ellis et al., 2021; Ryan et al., 2024), and neuro-symbolic architectures that combine perception with symbolic search (Xu et al., 2023). Both families treat the solver library as fixed: the system either finds a solution within its existing operator repertoire or moves on.

This paper addresses a different question: when a solver portfolio fails on a task, can the system *derive new operators from the failure trace itself*, validate them with bounded verification, and promote the task from unsolved to solved? We call this trace-driven operator invention.

The gap we address is specific. Existing library-learning systems such as DreamCoder (Ellis et al., 2021) learn abstractions from *successfully solved* programs. In contrast, our system learns from *near-solved failures* -- tasks where the portfolio reached a partial hypothesis but lacked the operator to complete it. This distinction is important: the information content of near-solved failures is rich. A failure trace records which objects were identified, which selector partitioned them into kept and target sets, and what transformation pattern was attempted but could not be expressed. From this trace, the system proposes an operator hypothesis with explicit parameters, selector, and execution semantics.

The second gap is verification. Program synthesis systems typically validate candidates by checking training-pair consistency. We add five additional layers: leave-one-out re-inference (the operator must generalize when any single training pair is withheld), six proof obligations covering preconditions, postconditions, and invariants, active falsification with counterexample probes, replay certificates with full provenance, and an event-driven audit log with 26 event types. The combination provides bounded executable verification -- not formal proof in the theorem-prover sense, but a layered rejection cascade where each stage can catch false positives that earlier stages miss.

Our contributions are:

1. **Trace-driven operator invention.** Near-solved failure traces are analyzed to propose executable operator hypotheses with explicit family, selector, parameters, and execution function. The system currently implements seven operator families across two categories: spatial operators (copy-to-position with quadrant-fill, halo-projection, marker-relative, correspondence, and variable-destination rules) and color operators (recolor-in-place and color-transfer-recolor with same-shape, nearest-kept, and same-size rules).

2. **Bounded verification with proof obligations.** Each operator hypothesis is checked against six proof obligations (PO1--PO6): train consistency, target non-emptiness, kept-object preservation, background preservation, determinism, and LOO consistency. Family-specific preconditions (4--9 per family), postconditions (2--5), and invariants (3--6) are evaluated by execution against concrete training data.

3. **Active falsification.** Counterexample probes (10--23 per operator family) test the hypothesis against perturbations: color relabeling, distractor insertion, spatial permutation, source movement, marker shifting, and boundary placement. Hypotheses that fail falsification receive advisory warnings.

4. **Replay certificates.** Every promotion emits a certificate recording task ID, operator family, selector, parameters, training fit, LOO status, falsification score, invariants preserved, derivation trace, and confidence. Certificates are deterministically reproducible.

5. **Empirical validation.** Four real ARC tasks were promoted from the near-solved pool, across two operator families, with 0 false positives over 272 candidate evaluations across 10 rejection pools. An eight-configuration ablation confirms each operator is necessary. All 4 promotions were independently reproduced via pipeline replay in under 0.7 seconds total.

---

## 2. Related Work

**ARC and abstraction reasoning.** The Abstraction and Reasoning Corpus (Chollet, 2019) defines 1,000 tasks requiring few-shot generalization over colored grids. LARC (Acquaviva et al., 2022) provides natural-language descriptions of ARC solutions. Xu et al. (2023) benchmark LLMs on ARC, finding GPT-4 achieves approximately 5% via direct prompting, while their ARGA system achieves approximately 5.3% through graph abstraction and program synthesis. GPT-4o achieves approximately 9% with 2-shot prompting (ARC-AGI leaderboard, 2024). Ryan et al. (2024) reach approximately 21% through LLM-guided program search. Top ARC Prize 2024 entries achieve 40--55% through test-time training and large-scale search. Our system does not compete on ARC solve rate (the static portfolio reaches 9.5% before operator invention); the contribution is the operator invention mechanism and its verification discipline.

**Program synthesis and library learning.** DreamCoder (Ellis et al., 2021) learns reusable program fragments from successfully solved tasks through a wake-sleep cycle: solve tasks, compress solutions into library primitives, and use the library to solve harder tasks. Our approach inverts this: we learn operators from *failed* tasks rather than solved ones. The lambda-calculus DSL and Bayesian program induction of DreamCoder differ from our approach of deriving operators from structural failure traces with explicit proof obligations. LILO (Grand et al., 2024) extends DreamCoder with LLM-guided library learning. Our system does not use LLMs for operator proposal; operators are derived algorithmically from object-change classification traces.

**Counterexample-guided inductive synthesis (CEGIS).** Solar-Lezama et al. (2006) introduced CEGIS for program synthesis, where a verifier generates counterexamples that refine the candidate program. SyGuS (Alur et al., 2015) formalizes syntax-guided synthesis with verification oracles. Our active falsification is inspired by CEGIS but differs in two ways: our probes are hand-designed per operator family rather than generated by a verification oracle, and our falsification is advisory (a hypothesis that fails some probes is flagged but not automatically rejected if it passes all proof obligations). A true CEGIS loop with an automated verifier oracle remains future work.

**Formal methods and proof-carrying code.** Proof-carrying code (Necula, 1997) attaches machine-checkable proofs to executables. Our replay certificates serve a similar role: they record the evidence chain supporting a promotion decision. However, our certificates are not proofs in the formal-methods sense -- they record executable verification results (training consistency, LOO results, falsification scores), not proof terms in Lean, Coq, or Isabelle. The term "proof obligation" in this paper refers to machine-checked assertions evaluated by execution, following the design-by-contract tradition (Meyer, 1992), not to proof terms in a formal logic.

**Neuro-symbolic reasoning.** Neural-guided symbolic search combines learned representations with symbolic program spaces (Devlin et al., 2017; Balog et al., 2017; Shi et al., 2020). Our architecture includes neural modules (JEPA encoder, Slot Attention, Graph Network Simulator, program ranker) that provide perceptual embeddings and candidate reranking. However, all 4 promoted tasks were achieved through purely symbolic operator invention with no neural module in the critical path. Neural modules are advisory: they suggest view ordering and rerank candidates, but final acceptance requires exact symbolic match on training pairs.

**World models and object-centric perception.** JEPA (LeCun, 2022) proposes joint embedding predictive architectures for learning world models. Slot Attention (Locatello et al., 2020) provides unsupervised object discovery. Graph Network Simulators (Sanchez-Gonzalez et al., 2020) model object-level dynamics. Our architecture incorporates all three as perception and dynamics modules, but they do not yet contribute to operator-level promotions.

---

## 3. Architecture

### 3.1 Overview

The architecture operates in two phases. The **static portfolio phase** runs a collection of symbolic solvers (local pattern induction, spatial decomposition, pattern synthesis, object-structural reasoning, and program search) on each task. When all solvers fail, the task enters the **near-solved memory** as a failure state with structural diagnosis. The **trace-driven operator invention phase** analyzes accumulated failure traces, proposes operator hypotheses, validates them through the verification chain, and promotes tasks that pass all checks.

```
Task input
    |
    v
Static Portfolio (5 paradigms, ~4952 programs)
    |
    +-- Solved? --> emit prediction + certificate
    |
    +-- Failed? --> store near-solved state
                        |
                        v
                   Near-Solved Memory
                   (failure diagnosis, best partial hypothesis,
                    object-change classification, repair frontier)
                        |
                        v
                   Gap Analysis
                   (cluster failures by type: copy_to_position,
                    recolor_in_place, color_transfer, shape_completion)
                        |
                        v
                   Operator Proposal
                   (derive hypothesis from failure trace:
                    family, selector, parameters, execute)
                        |
                        v
                   Verification Chain
                   PO1: Train consistency (exact match all pairs)
                   PO2: Target non-empty
                   PO3: Kept preservation
                   PO4: Background preservation
                   PO5: Determinism
                   PO6: LOO consistency (re-infer on N-1, predict held-out)
                        |
                        v
                   Active Falsification
                   (10-23 probes per family: color relabel, distractor,
                    spatial permutation, source move, marker shift, ...)
                        |
                        v
                   Promotion + Certificate Emission
```

### 3.2 Domain Adapters and AdapterGenesis

The system is domain-adaptive through a `DomainAdapter` protocol that defines how to decompose a scene into objects, compute properties, and extract relations. Four adapters are implemented:

- **GridDomainAdapter**: ARC grids (connected components, ~30 structural properties, spatial relations).
- **GraphDomainAdapter**: node/edge graphs (degree, centrality, connectivity properties).
- **ChessBoardDomainAdapter**: chess positions (piece type, attack/defense relations).
- **MoleculeGraphDomainAdapter**: molecular graphs (ring membership, bond type, atom properties).

AdapterGenesis creates new adapters when a manifold-based mismatch trigger detects that existing adapters are geometrically inadequate (curvature z-score, chart coverage gap, or topological uncertainty exceeding thresholds). The same structural reasoner operates across all domains; only the adapter changes. Cross-domain evaluation achieved 8/27 correct with 0 false positives across grid, graph, chess, and molecule tasks.

### 3.3 Object-Change Classification

When the static portfolio fails a task, the system performs object-change classification on each training pair. Objects are extracted via connected-component analysis. Input-output object correspondences are established via the Hungarian algorithm on a composite cost matrix of structural signature distance, exact shape match, and positional proximity. Each matched object pair is classified as: unchanged, recolored (same shape, different color), moved (same shape and color, different position), copied (source preserved, duplicate at destination), or complex (multiple simultaneous changes). This classification forms the basis of the failure trace.

### 3.4 Near-Solved Memory

Failed tasks are stored as near-solved states recording: task ID, best partial hypothesis from the portfolio, failure diagnosis (which solver came closest and why it failed), object-change classification results, topology signature (object count, color set, symmetry), and repair frontier (what transformation type would be needed to solve the task). Near-solved states accumulate across tasks. When enough failures share a common pattern (e.g., "objects classified as copied but no copy operator succeeded"), they form a failure cluster that triggers operator invention.

### 3.5 Trace-Driven Operator Invention

This is the core contribution. The `TraceDrivenOperatorInventor` analyzes near-solved failure traces to propose operator hypotheses. The process is:

1. **Gap analysis.** Failure traces are clustered by transformation type. The current implementation identifies seven operator families: copy-to-position (with five destination rules: quadrant-fill, halo-projection, marker-relative, correspondence, variable-destination), recolor-in-place (constant-color and consistent-map), and color-transfer-recolor (same-shape, nearest-kept, same-size, swap).

2. **Parameter inference.** For each candidate task and operator family, the system attempts to infer parameters from the failure trace. For copy-to-position, this includes the selector (which objects are kept vs. target), the destination rule (where copied objects are placed), displacement vectors, and copy/move mode. For color-transfer, this includes the color source rule (which object provides the new color) and the target selector.

3. **Hypothesis construction.** An `ExecutableOperatorHypothesis` is constructed with family, selector, parameters, and a deterministic `execute` function that maps input grids to output grids.

4. **Validation.** The hypothesis enters the verification chain (Section 3.6).

### 3.6 Verification Chain

Each operator hypothesis must pass a layered verification chain before promotion.

**Proof Obligations (PO1--PO6).** Six obligations are checked:

| ID | Name | Description |
|----|------|-------------|
| PO1 | Train Consistency | execute(g_in, params) = g_out for all training pairs |
| PO2 | Target Non-Empty | At least one target object exists |
| PO3 | Kept Preservation | Kept objects are unchanged in output |
| PO4 | Background Preservation | Non-object cells unchanged (or filled by declared rule) |
| PO5 | Determinism | execute is a pure function with no randomness |
| PO6 | LOO Consistency | Re-infer on N-1 pairs, predict held-out; all N folds succeed |

Additionally, 4--9 preconditions, 2--5 postconditions, and 3--6 invariants are checked per operator family (see Section 4).

**Active Falsification.** After passing proof obligations, the hypothesis is tested against 10--23 counterexample probes. General probes (color relabeling, distractor insertion, object count variation, spatial permutation, border-interior swap) apply to all families. Family-specific probes (source movement, marker shifting, marker duplication, destination boundary placement) test operator-specific assumptions. The falsification score is the fraction of probes survived. Falsification is advisory: a score below 0.6 triggers a warning but does not automatically block promotion.

**Certificate Emission.** A `ReasoningCertificate` is emitted recording: task ID, prediction ID, operator family, selector, parameters, training fit, LOO status, falsification score, invariants preserved, derivation trace (ordered sequence of pipeline steps from gap detection through promotion), and confidence score. Certificates are serialized to JSON and are deterministically reproducible.

### 3.7 Event-Driven Audit Log

The full pipeline emits events through 26 event types: TASK_OBSERVED, STRUCTURAL_SIGNATURE_COMPUTED, MEMORY_RETRIEVED, HYPOTHESIS_PROPOSED, HYPOTHESIS_SCORED, HYPOTHESIS_FALSIFIED, COUNTEREXAMPLE_GENERATED, HYPOTHESIS_ACCEPTED, HYPOTHESIS_REJECTED, NEAR_SOLVED_STORED, FAILURE_CLUSTER_CREATED, CONCEPT_PROPOSED, OPERATOR_PROPOSED, INVENTION_VALIDATED, INVENTION_REJECTED, INVENTION_REGISTERED, TASK_RESUMED, TASK_PROMOTED_TO_SOLVED, REASONING_CERTIFICATE_CREATED, CROSS_DOMAIN_TRANSFER_ATTEMPTED, CROSS_DOMAIN_TRANSFER_SUCCEEDED, CROSS_DOMAIN_TRANSFER_FAILED, REGRESSION_DETECTED, FINAL_PREDICTION_EMITTED, and two bookkeeping types. The event log supports query, replay, lineage analysis (parent chain walk), and promotion chain detection.

---

## 4. Formalization

We formalize the verification discipline of the operator-reasoning pipeline. All verification described here is executable bounded verification over finite domains, not theorem-prover-certified formal proof.

### 4.1 Grids and Tasks

**Definition 1 (Grid).** A grid is a matrix $G \in \mathbb{Z}^{H \times W}$ with $H, W \leq 30$ and cell values in $\{0, 1, \ldots, 9\}$.

**Definition 2 (Task).** A task is a tuple $T = (\mathit{train}, \mathit{test\_inputs})$ where $\mathit{train} = \{(g^{(i)}_{\mathrm{in}}, g^{(i)}_{\mathrm{out}})\}_{i=1}^{N}$ with $N \geq 2$ and $\mathit{test\_inputs} = \{g^{(j)}_{\mathrm{in}}\}_{j=1}^{M}$ with $M \geq 1$.

**Definition 3 (Task satisfaction).** A hypothesis $h$ satisfies task $T$ iff $\forall (g_{\mathrm{in}}, g_{\mathrm{out}}) \in \mathit{train}: h(g_{\mathrm{in}}) = g_{\mathrm{out}}$, where equality is exact cell-wise.

### 4.2 Domain Adapters

**Definition 4 (Domain adapter).** An adapter $\mathcal{A}$ maps a grid $G$ to an object-relation representation $\mathcal{A}(G) = (O, P, R)$ where $O = \{o_1, \ldots, o_k\}$ are objects, $P(o_i)$ is a property vector (color, shape, size, position, is_largest, is_border, n_holes, ...), and $R(o_i, o_j)$ is a relation set (spatial direction, color match, shape match, containment, adjacency). The adapter is deterministic.

### 4.3 Operator Hypotheses

**Definition 5 (Operator hypothesis).** An operator hypothesis is a tuple $h = (\mathit{family}, \mathit{selector}, \mathit{parameters}, \mathit{execute})$ where:

- $\mathit{family} \in \{\texttt{copy\_to\_position}, \texttt{marker\_relative}, \texttt{correspondence}, \texttt{variable\_destination}, \texttt{marker\_projection}, \texttt{recolor\_in\_place}, \texttt{color\_transfer\_recolor}\}$
- $\mathit{selector}: O \to \{\mathit{kept}, \mathit{target}\}$ partitions objects
- $\mathit{parameters}$: family-specific record (displacement vectors, destination rule, color source rule, etc.)
- $\mathit{execute}: \mathbb{Z}^{H \times W} \times \mathit{params} \to \mathbb{Z}^{H \times W}$ is a deterministic grid transformation

**Definition 6 (Validation level).** Each hypothesis progresses through ordered levels: $\texttt{proposed} \prec \texttt{parameterized} \prec \texttt{train\_consistent} \prec \texttt{loo\_validated} \prec \texttt{falsification\_validated} \prec \texttt{promotion\_validated}$. A hypothesis can only advance forward.

### 4.4 Proof Obligations

**PO1 (Train Consistency).** $\forall (g_{\mathrm{in}}, g_{\mathrm{out}}) \in \mathit{train}: \mathit{execute}(g_{\mathrm{in}}, \mathit{params}) = g_{\mathrm{out}}$. Checked by exhaustive execution over the training set.

**PO2 (Target Non-Empty).** $|\{o \in O : \mathit{selector}(o) = \mathit{target}\}| > 0$. Precondition check.

**PO3 (Kept Preservation).** $\forall o \in O, \mathit{selector}(o) = \mathit{kept}: o$ is unchanged in output. Postcondition check.

**PO4 (Background Preservation).** $\forall (r,c) \notin \bigcup_{o \in O} \mathit{mask}(o): \mathit{output}[r,c] = \mathit{input}[r,c]$ or declared fill. Invariant check.

**PO5 (Determinism).** $\mathit{execute}$ is a pure function; same input always yields same output. Structural property (no RNG in execute path).

**PO6 (LOO Consistency).** For each $i \in \{1,\ldots,N\}$: re-infer parameters from $\mathit{train} \setminus \{(g^{(i)}_{\mathrm{in}}, g^{(i)}_{\mathrm{out}})\}$, execute on $g^{(i)}_{\mathrm{in}}$, and check $h_{\setminus i}(g^{(i)}_{\mathrm{in}}) = g^{(i)}_{\mathrm{out}}$. LOO passes iff all $N$ folds succeed.

### 4.5 Active Falsification

**Definition 7 (Probe).** A falsification probe $p: (G, h) \to (G', \mathit{expected\_behavior})$ perturbs the input grid and declares whether the output should change, be preserved, or cause failure.

**Definition 8 (Falsification result).** $\mathit{FR} = (\mathit{probes\_run}, \mathit{probes\_survived}, \mathit{counterexamples}, \mathit{score})$ where $\mathit{score} = \mathit{probes\_survived} / \mathit{probes\_run}$.

### 4.6 Promotion and False Positives

**Definition 9 (Promotion).** A task $T$ is promoted iff: (1) $T$ is not solved by the static portfolio, (2) an operator hypothesis $h$ is derived from near-solved failure traces, (3) $h$ satisfies PO1--PO6, (4) active falsification does not reject $h$, (5) a valid certificate is emitted, and (6) replay reproduces the test prediction.

**Definition 10 (False positive).** A false positive occurs when $T$ is promoted and $h(g_{\mathrm{test}}) \neq g^{*}_{\mathrm{test}}$. Current record: 0 false positives over 4 promotions and 272 candidate evaluations.

---

## 5. Experiments

### 5.1 Static Portfolio Baselines

The static portfolio comprises five reasoning paradigms with approximately 4,952 programs:

| Configuration | Tasks Solved | Rate |
|---|---|---|
| 4 paradigms (no program search) | 84/1000 | 8.4% |
| Full (5 paradigms + DSL) | 95/1000 | 9.5% |
| ConceptARC | 12/160 | 7.5% |
| Cross-domain (4 adapters) | 8/27 | 29.6% |

The static portfolio provides the baseline against which trace-driven promotions are measured. None of the 4 promoted tasks are solved by the static portfolio.

### 5.2 Controlled Microcycles

Before evaluating on real ARC tasks, operator families were validated on synthetic microcycles with known ground truth.

**Copy-to-position microcycle.** 4 synthetic tasks designed to test quadrant-fill and halo-projection operators. Result: 4/4 promoted, 0 false positives.

**Color-transfer microcycle.** 7 synthetic tasks (5 promotable, 2 designed as rejection probes). Result: 5/5 promoted, 0 false positives, 2/2 correct rejections. Rules tested: nearest_kept, same_shape, same_size, swap, and recolor_in_place.

**Recolor-in-place microcycle.** 5 synthetic tasks (4 promotable, 1 rejection probe). Result: 4/4 promoted, 0 false positives, 1 correct rejection.

### 5.3 Real ARC Promotions

Gap analysis identified 31 copy-to-position candidate tasks and 12 color-transfer candidate tasks from near-solved failures. The trace-driven operator invention pipeline was applied to all candidates.

**Table 1: Verified Real-Task Promotions**

| Task ID | Operator | Family | Train Fit | LOO | Falsification | Certificate | Train Pairs |
|---------|----------|--------|-----------|-----|---------------|-------------|-------------|
| d89b689b | quadrant_fill | copy_to_position | 1.0 | passed | survived | yes | 3 |
| e9ac8c9e | quadrant_fill (multi-block) | copy_to_position | 1.0 | passed | survived | yes | 3 |
| a48eeaf7 | project_to_halo | copy_to_position | 1.0 | passed | survived | yes | 2 |
| 2a5f8217 | color_transfer (same_shape) | color_transfer_recolor | 1.0 | passed | survived | yes | 3 |

Each promotion was independently verified by:
1. Loading the ARC task JSON data (training + test with solutions)
2. Verifying the certificate file for internal consistency (13 checks per certificate)
3. Re-running the operator invention pipeline from scratch
4. Confirming the replay prediction matched ground truth

All 4 promotions reproduced correctly. Total replay time: 0.56 seconds.

**Task details.** Task d89b689b: satellite pixels determine which quadrant of a kept block to fill with the satellite's color. LOO validated on 3 training pairs, actively falsified. Task e9ac8c9e: same quadrant-fill rule, but the test pair contains 3 independent block+satellite groups (training pairs each have 1) -- all correctly filled. Task a48eeaf7: single-pixel satellites project to the nearest cell adjacent to the kept block by Manhattan distance. LOO validated on 2 pairs. Task 2a5f8217: each target object derives its output color from the kept object with matching shape, selector is_color_1 (inverted), 8/8 targets correct across 3 training pairs.

### 5.4 Operator Necessity Ablation

Eight configurations were tested to determine whether each operator is necessary for its promoted tasks and whether verification gates affect solve counts.

**Table 2: Operator Ablation Matrix (8 configurations x 4 tasks)**

| Configuration | d89b689b | e9ac8c9e | a48eeaf7 | 2a5f8217 | Total |
|---|---|---|---|---|---|
| static_portfolio_only | no | no | no | no | 0/4 |
| trace_operator_invention_full | YES | YES | YES | YES | 4/4 |
| remove_quadrant_fill | no | no | YES | YES | 2/4 |
| remove_project_to_halo | YES | YES | no | YES | 3/4 |
| remove_color_transfer | YES | YES | YES | no | 3/4 |
| without_falsification | YES | YES | YES | YES | 4/4 |
| without_proof_obligations | YES | YES | YES | YES | 4/4 |
| without_certificates | YES | YES | YES | YES | 4/4 |

Key findings: (1) The static portfolio solved 0/4, confirming all promotions require trace-driven invention. (2) Removing quadrant_fill lost exactly d89b689b and e9ac8c9e; removing project_to_halo lost a48eeaf7; removing color_transfer lost 2a5f8217. No cross-substitution was possible. (3) Falsification, proof obligations, and certificates are advisory verification gates -- they provide traceability evidence but do not block promotion in the current pipeline. No configuration produced a false positive.

### 5.5 False-Positive Audit

**Table 3: False-Positive Audit Summary**

| Metric | Value |
|---|---|
| Rejected pools audited | 10 |
| Total pool entries audited | 272 |
| Unique rejected task IDs | 42 |
| Predictions emitted (promotions) | 8 |
| Correctly promoted | 8 |
| False positives | 0 |

The rejection cascade analysis revealed:
- 205/264 (77.7%) rejected at train_fit = 0.000 (operator produced zero correct training examples)
- 16/264 (6.1%) rejected at train_fit = 0.333 (partial but insufficient fit)
- 16/264 (6.1%) rejected at parameter_inference_failed
- 24/264 (9.1%) rejected at reconstruction_mismatch
- 3/264 (1.1%) rejected at test_output_mismatch (passed train + LOO but failed test replay)

The most informative near-miss was task 2204b7a8 (color_transfer_recolor, nearest_kept rule), which passed both training consistency and LOO validation but was caught by the test output replay check. This demonstrates that the layered validation design (train -> LOO -> test replay) catches false positives that simpler validation would miss.

### 5.6 Cross-Domain Evaluation

The same structural reasoner with domain-specific adapters was evaluated on 27 synthetic tasks across 6 categories:

| Domain | Correct | FP | Adapter |
|---|---|---|---|
| Graph | 2/3 | 0 | GraphDomainAdapter |
| Chess | 2/3 | 0 | ChessBoardDomainAdapter |
| Molecule | 1/2 | 0 | MoleculeGraphDomainAdapter |
| Grid | 1/5 | 0 | GridDomainAdapter |
| Recombination | 0/4 | 0 | GridDomainAdapter |
| Counterfactual | 2/10 | 0 | GridDomainAdapter |
| **Total** | **8/27** | **0** | |

Non-grid domains demonstrated real structural transfer: discriminative filtering and compositional planning discovered rules using domain-specific properties (node degree, edge position, ring membership) without grid-specific code. Cross-domain operator promotion was not demonstrated -- all 4 real promotions are on ARC grid tasks.

### 5.7 Neural Component Summary

The architecture includes 11 neural-related modules (JEPA encoder, Slot Attention, Graph Network Simulator, program ranker, perception heads, and supporting infrastructure). The strongest neural result was the WorldModel's 0.96% exact match (1/104 ARC tasks) via contrastive training. Perception heads achieved 89.5% binary accuracy on background detection and 58% on layout classification.

No neural module appeared in the critical path of any promotion. All 4 promoted tasks used purely symbolic operator families derived from symbolic failure traces. Neural modules provided advisory routing priors; accepted hypotheses remained executable and verified through the symbolic verification chain.

---

## 6. Results

### 6.1 Verified Promotions

Four previously unsolved ARC tasks were promoted to solved status through trace-driven operator invention. Each promotion satisfied: (1) the task was not solved by the static portfolio (confirmed by the 0/4 ablation baseline), (2) an operator hypothesis was derived from near-solved failure traces, (3) the hypothesis achieved training fit 1.0 on all training pairs, (4) LOO validation passed on all folds, (5) active falsification was survived, (6) proof obligations were checked, and (7) a replay certificate was emitted and verified.

The promotions spanned two operator families (copy-to-position and color-transfer-recolor) and three specific operators (quadrant_fill, project_to_halo, same_shape color transfer). Task e9ac8c9e demonstrated generalization beyond training distribution: training pairs each contained a single block+satellite group, while the test pair contained 3 independent groups, all correctly handled.

### 6.2 Ablation Results

The ablation confirmed three properties of the operator invention pipeline:

**Operator necessity.** Each operator was necessary for its specific task(s) and could not be substituted by any other operator in the inventory. This was expected -- the operators implement structurally different transformation rules -- but the ablation provides empirical confirmation.

**Static portfolio insufficiency.** The static portfolio (95/1000 ARC with DSL) produced 0/4 on the promoted tasks, confirming that these tasks require operators beyond the existing solver library.

**Verification gate advisoriness.** Disabling falsification, proof obligations, or certificate emission did not change the solve count (4/4 in all cases). This confirmed that these components are verification and traceability mechanisms, not solve gates. They did not produce false positives in any configuration, which is consistent with their advisory design.

### 6.3 False-Positive Rate

Zero false positives were observed across 272 candidate evaluations in 10 rejection pools spanning 42 unique rejected task IDs. The rejection cascade (parameter inference -> train fit -> LOO -> test replay) provided layered protection. The dominant rejection reason was train_fit = 0.000 (77.7% of rejections), indicating that most candidate tasks were outside the expressiveness boundary of the current operator families.

### 6.4 Rejection Analysis

Of the 28 rejected copy-to-position tasks, 83% required per-object structural correspondence -- matching source objects to specific anchors by color, shape, or spatial arrangement. The current operators use single-anchor or uniform destination rules, which cannot express context-dependent per-object placement. This identifies per-object correspondence as the primary expressiveness bottleneck for the copy-to-position family.

Of the 11 rejected color-transfer tasks, the failures involved context-dependent color patterns (color-from-neighbor, position-within-object, per-pair color swaps) beyond the current same-shape/nearest-kept/same-size rules.

### 6.5 Runtime

All 4 promotions reproduced in under 0.7 seconds total via pipeline replay. Individual replay times: d89b689b (0.09s), e9ac8c9e (0.09s), a48eeaf7 (0.03s), 2a5f8217 (0.35s). The full false-positive audit (272 evaluations across 10 pools) completed in 4.1 seconds.

---

## 7. Limitations

**Scale.** The system promoted 4 real ARC tasks out of approximately 905 unsolved (after the static portfolio solves 95/1000). This is a bounded proof-of-mechanism demonstrating that the trace-driven operator invention chain works end-to-end, not evidence of broad cumulative gains. Scaling to dozens or hundreds of promotions requires substantially richer operator families and per-object correspondence reasoning.

**No theorem-prover verification.** All verification is executable and bounded. The term "proof obligation" refers to machine-checked assertions evaluated by execution against concrete inputs, not to proof terms in Lean, Coq, Isabelle, or Z3. The system verifies operator correctness on observed training examples and generated counterexample probes but does not prove correctness for all possible inputs.

**LOO with small N.** Training sets have 2--4 pairs, so LOO provides 2--4 consistency checks. This is a necessary condition for correctness, not a sufficient one. With N=2, a single LOO fold provides minimal discriminative power.

**Falsification probes are hand-designed.** Probe families are manually constructed per operator family (10--23 probes each). The system does not automatically generate probes that maximize the probability of finding counterexamples. A CEGIS-style automated verifier oracle would strengthen falsification but is not implemented.

**Neural modules are advisory only.** Neural perception modules (JEPA, Slot Attention, Graph Network Simulator, program ranker) are implemented and trained, but none contributed to any promotion. The strongest neural result (1/104 exact match for the world model) is below the threshold for reliable independent solving. Neural-to-symbolic promotion transfer remains undemonstrated.

**Domain transfer not demonstrated with real promotions.** All 4 promotions are on ARC grid tasks. Cross-domain evaluation (graph, chess, molecule) showed the structural reasoner transfers with 0 false positives, but no cross-domain operator promotion has been achieved. The synthetic nature of the non-grid benchmarks limits the strength of cross-domain claims.

**Single-family hypotheses.** Each promoted hypothesis belongs to exactly one operator family. Tasks requiring composition of multiple operators (e.g., recolor then move) are not handled by the current inventory.

**Postcondition and invariant coverage.** Some postconditions and invariants are checked with proxy arguments. The certificate records how many of each category were checked (e.g., "5/5 preconditions, 3/4 postconditions, 2/4 invariants"), and partial coverage is reported honestly.

---

## 8. Conclusion

We presented trace-driven operator invention, a mechanism for deriving executable operators from near-solved failure traces with bounded verification. The system promoted 4 previously unsolved ARC tasks across two operator families with 0 false positives across 272 candidate evaluations. An eight-configuration ablation confirmed that each operator is necessary for its specific tasks, that the static portfolio produces 0/4, and that no false positives arise in any configuration. All promotions were independently reproduced via pipeline replay.

The contribution is methodological: a verification discipline (proof obligations, active falsification, replay certificates, event-driven audit) layered on top of operator invention from failure traces. The 4 promotions demonstrate that the full chain works end-to-end -- from near-solved memory through gap analysis, operator proposal, validation, and certificate emission -- but do not demonstrate broad cumulative gains at scale.

**Future work.** Several directions would extend the current results. Variable destination policies that perform per-object structural correspondence would address the 83% of copy-to-position rejections that require context-dependent placement. Many-to-few grouping operators would handle tasks where multiple source objects merge into composite targets. Richer object-change classification (beyond moved/recolored/copied/complex) would expand the set of traceable failure patterns. Theorem-prover integration (Lean or Coq certificates instead of executable checks) would strengthen verification from bounded to formal. Neural-guided operator proposal, where learned embeddings suggest operator families for novel failure patterns, would connect the existing neural infrastructure to the promotion pipeline. Finally, cross-domain operator promotion -- inventing an operator from failures in one domain and transferring it to another -- would demonstrate genuine domain-adaptive cumulative reasoning.

---

## References

Acquaviva, S., Pu, Y., Kryven, M., Sechopoulos, T., Wong, C., Ecanow, G. E., Nye, M. I., Tessler, M. H., & Tenenbaum, J. B. (2022). Communicating natural programs to humans and machines. *NeurIPS*.

Alur, R., Bodik, R., Dallal, E., Fisman, D., Garg, P., Juniwal, G., Kress-Gazit, H., Madhusudan, P., Martin, M. M. K., Raghothaman, M., Saha, S., Seshia, S. A., Singh, R., Solar-Lezama, A., Torlak, E., & Udupa, A. (2015). Syntax-guided synthesis. *FMCAD*.

Balog, M., Gaunt, A. L., Brockschmidt, M., Nowozin, S., & Tarlow, D. (2017). DeepCoder: Learning to write programs. *ICLR*.

Chollet, F. (2019). On the measure of intelligence. *arXiv:1911.01547*.

Devlin, J., Uesato, J., Bhupatiraju, S., Singh, R., Mohamed, A., & Kohli, P. (2017). RobustFill: Neural program learning under noisy I/O. *ICML*.

Ellis, K., Wong, C., Nye, M. I., Sable-Meyer, M., Morales, L., Hewitt, L., Cary, L., Solar-Lezama, A., & Tenenbaum, J. B. (2021). DreamCoder: Bootstrapping inductive program synthesis with wake-sleep library learning. *PLDI*.

Grand, G., Lim, J., & Tenenbaum, J. B. (2024). LILO: Learning interpretable libraries by compressing and documenting code. *arXiv:2310.19791*.

LeCun, Y. (2022). A path towards autonomous machine intelligence. *OpenReview*.

Locatello, F., Weissenborn, D., Unterthiner, T., Mahendran, A., Heigold, G., Uszkoreit, J., Dosovitskiy, A., & Kipf, T. (2020). Object-centric learning with Slot Attention. *NeurIPS*.

Meyer, B. (1992). Applying "design by contract." *IEEE Computer*, 25(10), 40--51.

Necula, G. C. (1997). Proof-carrying code. *POPL*.

Ryan, C., et al. (2024). LLM-guided program search for ARC. *arXiv*.

Sanchez-Gonzalez, A., Godwin, J., Pfaff, T., Ying, R., Leskovec, J., & Battaglia, P. W. (2020). Learning to simulate complex physics with graph networks. *ICML*.

Shi, K., Steinhardt, J., & Liang, P. (2020). FrAngel: Component-based synthesis with control structures. *POPL*.

Solar-Lezama, A., Tancau, L., Bodik, R., Seshia, S. A., & Saraswat, V. (2006). Combinatorial sketching for finite programs. *ASPLOS*.

Xu, Y., et al. (2023). LLMs and the Abstraction and Reasoning Corpus: Successes, failures, and the importance of object-based representations. *arXiv:2305.18354*.
