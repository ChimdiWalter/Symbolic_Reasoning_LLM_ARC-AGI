# CORA-TTI MASTER PLAN — Certified Test-Time Invention

*User directive of record, 2026-08-31. ADDITIVE master roadmap for Reasoning_Project.
Lives on branch `cora-tti-dev` in the isolated worktree; the live Step-B experiment is
NOT governed, altered, or reinterpreted by anything in this document.*

## 0. Immutability preamble (binding)

This roadmap is NOT permission to alter, restart, inspect, optimize, or reinterpret the
running frozen Step-B experiment. The scientific experiment remains authoritative and
immutable. In particular, never modify:

- scripts/cora_level4_stepB_run.py
- level4_stepB/candidates.py
- outputs/cora_breakthrough/level4_stepB_run_manifest.json
- the Step-B design, inventory, witness generator, firewall, journal, E_transfer split,
  Lockbox, or verifier.

Do not inspect the semantic contents of the live checkpoint journal (quantitative
line-count monitoring only). The frozen sequence remains, unweakened and unreordered:

Step B completion → output hash written → pin before inspection → semantic separation
against K_L4* → E_transfer held-out production transfer → promotion of surviving
production(s) → ordinary rediscovery under enlarged K → automatic anti-unification into
new concepts → Level-3 K vs K+C vs ablation → subsequent self-extension cycle if the
evidence supports one.

## 0.1 The two tracks

- **Track 1 — CORA (science):** the exhaustive, blinded, hash-pinned, uncensored
  self-extension experiment. Exists to answer: *can certified failures cause the system
  to discover new typed semantics?* Slow by design; never optimized for score.
- **Track 2 — CORA-TTI (competition):** an aggressively ranked, GPU-batched, time-aware,
  test-time-adaptive, ensemble-capable system optimized for the two-attempt metric.
  Different system, different question; its existence does not contaminate Track 1.

North star (INTERNAL ONLY): build the strongest non-LLM ARC-AGI-2 system possible and
attempt to exceed the historical 24.03% private score (NVARC, 2025), while preserving a
mechanism result more interesting than leaderboard optimization. Do NOT put "best ever",
"groundbreaking", "first ever" or similar into the paper, README, abstract, or repo.
External claims are earned by results plus a complete prior-art review.

The result being attempted: (1) high ARC-AGI-2 accuracy; (2) task-local semantic
self-extension; (3) exact causal evidence that self-extension produced some of the
additional solves; (4) no LLM, no language-model API, no text-pretrained reasoning
model; (5) a domain-independent meta-reasoning core testable outside ARC later.

## I. Core theory

Ordinary program synthesis: `p* = argmin_{p ∈ F(K)} L(p; D)` with K fixed.

CORA-TTI reasons jointly over programs AND local language extensions:

    (e*, p*) = argmin_{e ∈ E, p ∈ F(K ∪ {e})}  L(p; D) + λ·MDL(e) + μ·Complexity(p)

subject to certification. For evaluation task j:

    K_j,0 = K_global
    search under K_j,0; if ordinary induction succeeds, solve normally
    on certified failure:
        failure trace → typed failure representation → candidate semantic extensions
        → exact execution → leave-one-out certification → K_j,1 = K_j,0 ∪ {e}
    re-search; allow a small bounded number R of rounds: K_j,0 → K_j,1 → … → K_j,R
    after task j: DELETE all task-local extensions; K_{j+1},0 = K_global

No transfer of newly invented semantics between hidden evaluation tasks unless ARC Prize
rules are explicitly confirmed to permit it. The task-local reset is scientifically
desirable even if cross-task adaptation is allowed: it demonstrates construction of the
missing abstraction from each task's own demonstrations. K_global may contain only
capabilities learned before evaluation from allowed public/synthetic material, plus
capabilities admitted through the frozen scientific promotion protocol.

Two forms of learning, central to the theory:

    GLOBAL SEMANTIC MEMORY        K_global
    EPHEMERAL TASK-LOCAL          K_j,r
    SEMANTIC PLASTICITY

**The defining distinction vs test-time training:** TTT adapts parameters (θ → θ′);
CORA-TTI adapts the reasoning language itself (K → K′). The architecture evolves from
"program induction with a self-growing library" to: **a reasoning system with persistent
knowledge + ephemeral semantic plasticity + failure-conditioned language invention +
formal verification.** That formulation is the architectural idea to build the paper
around, if the evidence supports it.

## II. The computational problem

The exhaustive Step-B implementation is intentionally slow and must NOT be copied into
Kaggle. ARC-AGI-2 private evaluation: 120 tasks; a 12-hour notebook ≈ 6 min/task before
overheads. Target: **< 4 minutes average per task**, with unused time from easy tasks
dynamically reallocated. The research problem: *how can an exhaustive semantic-invention
mechanism be distilled into an anytime proposal-and-verification mechanism without
destroying its generality?* This is itself an important AGI question.

## III. Typed Failure Graph (TFG)

A domain-general intermediate representation of failure. No task IDs or family labels
enter the invention mechanism. Encodes mechanistic evidence only: frontier program
nodes; input/output types; goal type; observed frontier values; output delta signatures;
cardinality/shape changes; palette changes; object/region relation changes; repeated
substructure; which slots fit/fail; non-exact executions; type paths; causal
dependencies between frontier terms; verifier failure class. Represented as a typed
graph/hypergraph, never prose. ARC is merely one producer of a TFG — essential for
eventual cross-domain transfer.

## IV. Grammar Proposal Network (GPN)

A small GRID-NATIVE, NON-LLM proposal model predicting `q(e | TFG, interface)` where e
is a typed candidate production/sketch in the generic semantic-constructor language.
It must NOT predict the answer grid. Permitted: small graph transformer, recursive
network, set network, or similar compact architecture. Forbidden: LLM, natural-language
reasoning, text corpus, API, task-ID prediction, answer-grid generation as primary
purpose. Division of labor is fundamental:

    GPN:  LEARN WHERE TO SEARCH
    CORA: EXECUTE WHAT WAS PROPOSED, VERIFY WHAT SHOULD BE BELIEVED

## V. Self-supervised operator-dropout curriculum

Labels are generated automatically by withholding existing semantics — humans never
label "the missing primitive".

- **Stage A — operator dropout:** remove capability e from a language (K^{-e} = K\{e});
  generate tasks/programs requiring e; run the crippled solver; record the TFG;
  target = reconstruction of e.
- **Stage B — compositional semantic holdout:** randomly construct generic productions
  from the frozen constructor meta-language that are NOT registered as named operators
  (e.g. e* = Compose(Project, Reindex, Embed)); generate tasks requiring e*; remove it;
  train GPN to construct the production AST/sketch from failure evidence.
- **Stage C — family holdout:** hold out entire semantic families during training.
  Validation question: can GPN synthesize a semantic structure from a constructor
  family never represented by named instances during training?
- **Stage D — type-interface holdout:** hold out entire typed interfaces; measure
  whether the proposal system composes a repair from generic constructors.

Goal: learn `failure pattern → semantic construction strategy`, NOT
`failure pattern → known operator ID`. Training/held-out semantic families must be
disjoint. All splits, seeds, and family holdouts frozen before their experiments.

## VI. Fast semantic execution

A SEMANTICS-PRESERVING batched executor. Operator meaning never changes. Compile
compatible operations into tensorized kernels; batch over
[candidate, task, demonstration, parameter hypothesis, H, W]; use L4 GPUs for
throughput. Exact symbolic CPU execution remains the reference oracle. Every
accelerated operation carries differential tests `fast(x) == reference(x)` over large
randomized synthetic suites; zero semantic mismatch tolerated. The GPU is an
accelerator, never an approximate verifier.

## VII. Multi-fidelity verification

Admissible cascade: proposal → typecheck → cheap invariant checks → exact demo fit →
counterexample/symmetry checks → partial fold check → complete LOO re-induction →
accepted task-local production. Cheap stages may REJECT candidates; they may never
ACCEPT one as certified. Every final "certified" claim requires the full immutable
LOO gate.

## VIII. Anytime meta-reasoning

A global scheduler treats Kaggle time as one resource. Per task, maintain: probability
ordinary search succeeds; probability invention helps; expected compute of the next
action; uncertainty; remaining attempts. Optimize expected solved outputs per unit
compute. Easy tasks terminate quickly; unsolved tasks earn larger budgets from failure
evidence. No hardcoded task IDs; hidden-task identity must be irrelevant (statistics
may come from public/synthetic training only).

## IX. Two diverse attempts

- **Attempt 1 — CORA-Cert:** highest-confidence output under the strictest available
  evidence (exact demos + LOO + structural consistency).
- **Attempt 2 — CORA-Explore:** best error-diverse alternative — another independently
  induced program, another representation/view, another task-local invention, a compact
  grid-native recursive fallback (e.g. TRM-style), or a strong less-conservative
  uncertified hypothesis.

Optimize `P(A1 correct OR A2 correct)`, not rank-1/rank-2 of one explanation. Measure
complementarity explicitly.

## X. Competition-mode architecture

    ARC demonstrations
      → multi-view perception
      → FAST ordinary CORA induction
         ├─ certified solve ──────────────→ candidate pool
         └─ failure → Typed Failure Graph
                    → Grammar Proposal Network
                    → top-k semantic sketches
                    → induced slot fitting
                    → GPU-batched exact execution
                    → multi-fidelity rejection
                    → full LOO certification
                    → ephemeral K_j,r extension
                    → re-induction ───────→ candidate pool
    candidate pool → calibrated scoring + diversity → attempt_1 / attempt_2

## XI. Score targets and gates

Historical target: 24.03% ARC-AGI-2 private (NVARC 2025). 2026 environment: 12-hour
offline Kaggle notebook, exactly two predictions per test input, L4x4 GPUs (96 GB),
public external data/pretrained models allowed; official 2026 grand target 85%.
Do not optimize toward 24.1% — margin is required (Public / Semi-Private / Private
are not identical).

- **Gate C0:** exact Kaggle runtime emulator working.
- **Gate C1:** full 120-task evaluation comfortably inside 12 h (stretch < 8 h).
- **Gate C2:** task-local invention produces demonstrably new certified solutions on
  held-out development data.
- **Gate C3:** public ARC-AGI-2 pass@2 > 10%.
- **Gate C4:** public pass@2 > 20%.
- **Gate C5:** public pass@2 ≥ 30% (stretch ≥ 35%) on the frozen untouched protocol —
  the point at which exceeding 24.03% privately becomes plausible, not guaranteed.

Also on the scientific side (independent of C-gates): Gate A = 0/120 baseline recorded;
Gate B = promoted Step-B operators alone move eval above 0 (language growth crosses
distribution boundaries).

No manual task-specific patches. Never inspect a failed public task and add a primitive
for it; system-level improvements must be motivated by aggregate/frozen evidence.

## XII. Causal score decomposition

For every development evaluation report:

    score_base      fixed/global CORA
    score_global    + globally promoted certified semantics
    score_gpn       + failure-conditioned proposal ordering
    score_tti       + task-local semantic invention
    score_final     + attempt-2 diversity policy

A TTI-dependent solve requires ALL of: baseline failure + local production proposed +
winning program uses it + LOO success + correct test output (public dev) + ablation
(remove production → failure). If the solve survives ablation, invention gets no credit.

## XIII. Metrics

Keep CSR. Add (only if supported by results) **CSAR — Certified Semantic Adaptation
Rate**: the fraction of evaluation outputs solved correctly only after a task-local
semantic extension surviving full certification. Also report: extension depth;
proposed/certified/causally-necessary counts; compute per certified extension; solve
gain per unit invention compute. Theory question: *how much task-solving capability can
a system acquire by restructuring its hypothesis language per unit compute?*

## XIV. Evidence tiers (external language bar)

- **A:** new semantic candidates exist — engineering only.
- **B:** candidates survive multi-source LOO — strong mechanism evidence, not enough.
- **C:** pass semantic separation + held-out transfer — strong research result.
- **D:** promoted semantics cause new ARC solves and new anti-unified abstractions —
  major result.
- **E:** task-local invention causes new public/Kaggle solves that disappear under
  ablation — potentially category-defining.
- **F:** CORA-TTI exceeds 24.03% private without an LLM while retaining auditable
  invention evidence — the result to pursue aggressively.
- **G:** the invention → solve → abstraction → invention loop turns repeatedly with
  causal gains AND the system remains competitive — justifies very strong claims.

## XV. Domain-general architecture

The meta-layer must not be intrinsically about grids. Target (conceptually; never
inside the frozen experiment):

    MetaExtensionEngine[Observation, Type, Expression, Executor, Verifier, FailureTrace]
    plugin interface: build_views / search / execute / verify / trace_failure /
                      propose_extension / fit_slots / separate_extension / promote_extension

ARC plugin: Grid, Region, Entity, Colour, Placement, Transform, …
Future plugin (proof-of-principle AFTER the ARC mechanism is established — do not
derail): protein conformational reasoning (Structure, Conformer, ConformerSet,
MotionMode, Sampler, Constraint, Weighting, Observable, SAXSProfile), where the loop
becomes failed conformer hypothesis → physical/experimental failure trace → propose
sampling/selection/weighting operator → validate against structural constraints →
held-out proteins → retain only transferable operators. A small second-domain
demonstration of recovering a withheld operator is what strengthens Universality.

## XVI. Prior work and the novelty conjunction

Never claim "nobody has invented from failures". Prior art includes: DreamCoder /
library learning; LILO; learning-from-failures / predicate invention; POPPI; ADVENT;
ARC evolutionary program synthesis; SOAR; TRM and recursive refinement; NVARC;
test-time training/adaptation. The claimed novelty must be the CONJUNCTION:
failure-frontier-triggered + typed semantic production synthesis + non-LLM + frozen
prior language + certificate-carrying invention + task-local language adaptation +
reset between evaluation tasks + exact causal ablation + held-out transfer + efficient
test-time deployment + domain-independent meta-extension interface. Before any
precedence claim: comprehensive related-work search + claim-by-claim novelty matrix.

## XVII. ARC Prize paper

Separate from the research manuscript. Centers on: semantic plasticity; task-local
invention; causal score gains; public/Kaggle accuracy; universality; efficiency;
theory. NO training-set score in the competition paper (the research manuscript keeps
the training census). The paper answers WHY semantic-language adaptation works, not
merely HOW the solver is implemented. Strongest possible form:

    fixed CORA = A%  → +global learned language = B%  → +guided proposal = C%
    → +task-local invention = D%  → +diverse second attempt = E%
    with E > 24.03% and, critically, D − C > 0 under task-level causal ablation.

Paper Prize rubric weights Accuracy, Universality, Progress, Theory, Completeness,
Novelty equally — favorable to this direction; a score alone wins nothing.

## XVIII. Authorized now, while Step B runs (isolated worktree ONLY)

1. This document.
2. docs/CORA_SEMANTIC_PLASTICITY_THEORY.md (K_global, K_j,r, reset, adaptation,
   verifier role, compute efficiency).
3. The cora-tti-dev worktree from clean HEAD; frozen-file hashes verified before/after.
4. Exact Kaggle-runtime emulator (120 tasks, 2 attempts, 12 h budget, CPU/GPU
   accounting, no-internet assumptions).
5. Typed Failure Graph schema.
6. Operator-dropout / compositional-holdout synthetic dataset GENERATOR using only
   already-public/frozen semantics; it must not read the live Step-B journal,
   E_transfer, Lockbox, or hidden expectation.
7. GPN training prototype.
8. Semantics-preserving batched executor with differential tests vs the exact
   interpreter.
9. Anytime scheduler simulator.
10. Attempt-1/attempt-2 diversity evaluation.
11. Complete ablation ledger.

Nothing here may be scored or tuned using E_transfer, Lockbox, or sealed Level-4
results before the frozen sequence permits access.

## XIX. Engineering quality bar

Deterministic seeds; exact artifact hashes; unit tests; differential tests for
accelerated semantics; no task-ID branches; no hidden task-family branches; no
hand-written target primitives; no manual eval fixes; no semantic result leakage;
explicit negative controls; resource accounting; reproducible Kaggle notebook;
open-source-compatible dependencies; exact ablations; append-only evidence ledger.
The immutable verifier remains the source of truth.

## XX. Final north star

Do not optimize for a flashy demo. Build the strongest evidence for:

> A reasoning system need not be confined to searching for solutions inside a language
> supplied by its designers. When its current language fails, it can diagnose the
> failure, construct a new semantic operation, verify the operation, use it to solve
> the problem, and discard or retain the operation according to causal evidence.
> Learning therefore occurs not only in parameter space or program space, but in the
> space of reasoning languages themselves.

ARC is the controlled experimental environment. CORA-TTI is the efficient test-time
realization. The long-term claim is a general mechanism for semantic plasticity; the
short-term objective is to make it fast and strong enough to exceed 24.03% without an
LLM. Do not promise that result; engineer the system so that, if the hypothesis is
true, the experiment has a real chance to demonstrate it.

## Appendix A. Component summary (what is new and why it matters)

| Component | What is new | Why it matters |
|---|---|---|
| CORA-TTI | invents a semantic operation inside a single unseen task at inference, from demonstrations only | turns self-extension from an offline weeks-long process into a competition mechanism |
| Global + ephemeral language states | K_global vs task-local K_j,r; local inventions deleted per task | prevents hidden-task leakage; clean theory of semantic plasticity |
| Typed Failure Graph | failure traces as a domain-independent typed graph | makes invention learnable and transferable beyond grids |
| Grammar Proposal Network | small non-LLM model predicts which extension to try, never the answer grid | neural guidance without surrendering symbolic verification |
| Operator-dropout / semantic-holdout curriculum | remove operations, cause failures, train reconstruction of the missing semantics | millions of self-supervised invention examples, zero human labels |
| GPU symbolic executor | batch thousands of exact candidates on GPU; CPU semantics as oracle | multi-day invention → minutes |
| Multi-fidelity certification | cheap rejection before full LOO; cheap stages never accept | preserves the certificate while making TTI practical |
| Anytime scheduler | allocates the 12-h budget by expected value of further reasoning | easy tasks stop early; hard tasks get invention time |
| Error-diverse two attempts | attempt 2 from a different explanation | optimizes P(A1 ∨ A2), not top-2 of one theory |
| MetaExtensionEngine | formal plugin architecture over observations/types/executor/verifier/failure | route from ARC to other scientific domains |
| CSAR | certified semantic adaptation rate | measures accuracy specifically from task-local invention |
| Causal score decomposition | base → global → GPN → TTI → diversity | proves WHY score increased |

## Appendix B. Timeline (internal; reconfirm deadlines near submission)

- Now → Step-B completion: leave the scientific run untouched; build in parallel the
  GPU executor, Kaggle emulator, dropout generator, and proposal-model dataset.
- Mid-September: separation → E_transfer → promotion; train the failure-conditioned
  proposer.
- Late September: CORA-TTI v1; first task-local invention experiments; measure
  public/held-out score and wall clock.
- Early October: neural proposer + synthetic curriculum + attempt-2 diversity; full
  inference under 12 h.
- Mid-October: frozen competition ablations; first serious Kaggle submissions.
- Late October: efficiency/reliability/ranking only; no conceptual redesign.
- 2026-11-02: final Kaggle submission. 2026-11-08 (internal): final paper/writeup.
