# Certified Architecture Plasticity — the long-range CORA thesis

*User directive of record, 2026-08-31 (second directive, additive to
CORA_TTI_MASTER_PLAN.md). The running Step-B experiment remains untouched; everything
here is post-Step-B / competition / long-range architecture. Same immutability preamble
as the master plan applies verbatim.*

## 1. Frontier context (what the survey found, and the lesson each item carries)

- **DeepMind** — AlphaEvolve (generative proposals + automated evaluators), AlphaGeometry 2
  (learned proposals + fast symbolic engine + knowledge-sharing across searches), Deep
  Think/Aletheia (candidate solutions iterated through a verifier), Genie 3 (world
  simulation as infrastructure). Lesson: generation becomes powerful when paired with an
  executable evaluator; search speed and counterfactual simulation matter enormously.
- **OpenAI** — large-scale RL for reasoning, inference-time compute scaling, learned tool
  orchestration, long-horizon agentic search. Lesson: intelligence is increasingly
  adaptive inference + orchestration, not a single forward pass.
- **Meta** — V-JEPA 2: predictive latent world models used for planning/zero-shot control.
  Lesson: learn how states change under actions — and apply that idea to reasoning itself.
- **Microsoft Research** — Interwhen (real-time test-time verification steering
  reasoning), Universal Verifier; verifier-guided test-time reasoning named a frontier
  problem. Lesson: the verifier should be an active controller, not only a final gate.
- **Sakana / Clune** — Darwin Gödel Machine (open-ended self-code-modification with a
  stepping-stone archive; SWE-bench 20%→50%), AI Scientist v2, a dedicated RSI lab.
  Lessons: (a) don't keep only today's best variant; (b) **"self-improving AI" alone is
  no longer a novelty claim.**
- **Ndea** — guided program synthesis and deep learning as equally fundamental. Lesson:
  "neural-guided program search" is the neighborhood; CORA must go beyond it.
- **ARC Prize** — 2025 the "Year of the Refinement Loop"; TRM refines states; SOAR
  self-improves evolutionary synthesis; an LLM-guided evolutionary program-synthesis
  entry is listed at **26% on ARC-AGI-2 Semi-Private**. Lessons: refinement inside a
  fixed model is mainstream; changing the reasoning language is the logical next
  frontier — and "beat 24.03%" carries an asterisk (the non-LLM qualifier is part of
  CORA's claim, since LLM-guided systems already exceed it).
- **Anthropic (science)** — biology agents became dramatically more reliable with a
  deterministic retrieval/execution layer. Lesson: cross-domain autonomous science needs
  deterministic execution infrastructure — which CORA already has.

## 2. The gap

Frontier systems adapt θ (weights), h_t (reasoning state), p (candidate program), or A
(agent scaffold/code). CORA is beginning to adapt **K — the language in which programs
can exist**. The next jump: **the system should diagnose WHICH PART OF ITS OWN COGNITIVE
ARCHITECTURE is inadequate, and change that component.** No public frontier system found
in the survey combines self-modification with typed causal localization of the failing
component AND an immutable certification boundary. That combination is the larger CORA
thesis (pending the required claim-by-claim prior-art matrix).

## 3. Certified Architecture Plasticity

    A_t = (R_t, K_t, S_t, M_t, W_t; V)

    R_t  representations / ontology          S_t  search & control strategy
    K_t  semantic language                   M_t  memory and abstractions
    W_t  internal model of reasoning dynamics
    V    IMMUTABLE VERIFIER — the anchor; never adapted

The question graduates from "what program am I missing?" through "what operator am I
missing?" to **"why did my reasoning system fail?"** — with diagnoses in {perception,
representation, semantic-language, search, memory/abstraction} and modification applied
only to the implicated layer. Name: **failure-directed architecture plasticity**.

## 4. The ten ideas

### 4.1 Cognitive Failure Localization (CFL)
Learn `q(z | F)`, z ∈ {representation, semantics, search, memory}, before proposing any
repair: `F → z` first, then `F, z → e_z`. Labels are free by controlled crippling:
remove an operator → semantic failure; remove a view → representation failure; restrict
depth/budget → search failure; remove an abstraction → memory failure. Step A's own
lesson motivates this: the first observed blocker ("slot learning") was not proof of the
sufficient repair. CFL generalizes the GPN (which maps F → e directly).

### 4.2 Representation / ontology invention
A system may fail because the correct solution is awkward or impossible in its current
ontology, not because an operation is missing (coordinates → polar; particles → fields;
sequence → graph). Allow invention of: new object types, relations, groupings/views,
coordinate systems, latent entities, and conversions between representations. For ARC:
`Grid → derived object system → simple program` instead of a huge pixel program.
**Representational plasticity** is the stronger AGI direction beyond semantic plasticity.

### 4.3 Certified Micro-Language Induction (generalizes CORA-TTI)
Not one operator but the smallest temporary language in which the task becomes easy:

    (G_j*, p_j*) = argmin_{G,p} [ L(p; D_j) + λ·DL(G|K) + μ·DL(p|G) ]   s.t. LOO cert

G_j may contain {e_1, e_2, new relation, new view}; G_j is discarded after the task.
Central theoretical reframing: **ARC tasks may be better viewed not as program induction
under a universal DSL, but as joint induction of a small task-specific language and a
program within it.**

### 4.4 Semantic World Model (Reasoning World Model)
Learn `W: (K, F, e) → F̂′` — predict the consequence of a semantic modification on the
failure landscape, instead of exhaustively executing thousands of candidates. Score
`P(extension reduces failure | F, K, e)`; plan multi-step language moves
`K →e1→ K_1 →e2→ K_2`. This turns language invention into planning. It predicts the
consequences of modifying the reasoning system — not the ARC answer. (V-JEPA/Genie idea
applied to reasoning dynamics.)

### 4.5 Verifier as active reasoning controller
Exploit the strong verifier DURING search, not only at the end: `p_1 → V_1 → p_2 → V_2 → …`
with proof obligations (palette cannot grow; shape must shrink; component count
conserved; regions congruent; mapping bijective; boundary relation preserved) actively
constraining continuation. When NO continuation satisfies the obligations, **that itself
is failure evidence for invention**. Verification = truth gate + reasoning sensor.
Strictly stronger than multi-fidelity filtering.

### 4.6 Certified Open-Ended Grammar Archive
Replace the single lineage K_t → K_{t+1} with a population
𝒦_t = {K^(1), …, K^(m)} scored on certified reach, MDL/compression, novelty, transfer,
runtime, diversity. A grammar weaker today may hold the representation enabling a later
invention (DGM's stepping-stone lesson) — but unlike DGM, **every admitted branch
carries certificates**, not just benchmark fitness. Fusion: open-ended evolution +
formal auditability.

### 4.7 Semantic stepping stones
Do not discard every failed proposal. Keep a sanitized archive of
interesting-but-insufficient extensions that demonstrate a certified partial property
(e_a fixes representation but not placement; e_b fixes placement but not grouping;
later discover e_c = e_a ∘ e_b). Extends the existing program-level near-solve idea to
the language level — the path to compounding conceptual invention.

### 4.8 Capability Worlds ("CORA Forge")
The training environment evolves AGAINST CORA (Echoverse/Genie lesson). After CORA
invents e: generate tasks that distinguish true understanding of e from correlated
shortcuts, then mutate toward tasks CORA almost solves. CORA improves the curriculum;
the curriculum improves CORA. Unlimited targeted training data at the capability edge —
without ever hand-patching ARC tasks.

### 4.9 Semantic consolidation and forgetting
Unbounded growth of |K_t| explodes search. Lifecycle for every invention:

    ephemeral → probationary → global → compressed → deprecated

Task-local start; cross-task transfer earns probation; repeated utility promotes;
anti-unification compresses (e_1,e_2,e_3 → C); redundant primitives are deprecated.
Intelligence = invent → test → consolidate → compress → forget. Lifelong learning, not
mere accumulation.

### 4.10 Cross-domain semantic morphisms
Transfer abstract structural roles, not literal operators:

    ARC:      Set[Region]  → Select → Transform → Aggregate → Grid
    Protein:  ConformerSet → Select → Perturb   → Weight    → Observable
    Schema:   Collection[A] → Predicate[A] → Transformation[A,B] → Aggregation[B] → Observation

Learn the typed schema once; instantiate per domain. Turns CORA from "an ARC system
also applied to biology" into "a system that transfers discovered reasoning structures
between domains" — the eventual Universality result.

## 5. The deterministic-execution insight (Anthropic biology)

Stronger reasoning cannot compensate for unreliable execution infrastructure. CORA
already owns the thing many agent systems lack: deterministic execution + verification.
For the protein extension, validators are executable, never vibes: MolProbity, bond
geometry, R_g, SAXS forward model, experimental likelihood, energetic/physical
constraints. Scientific self-extension then reads:
hypothesis → physical execution → observable → failure trace → new scientific operator.
A route toward an automated scientific method, not a text-manipulating LLM scientist.

## 6. Target architecture (long-range)

                               IMMUTABLE VERIFIER
                                      │
    Observation ──► Representation ──► Reasoning ──► Execution
                       │                  │ failure
                       │                  ▼
                       │          Causal Failure Graph
                       │        "what part of me failed?"
              ┌────────┴──────────┬───────┴─────────┐
              ▼                   ▼                 ▼
      representation          semantic          search/control
        invention             invention           adaptation
              └──────────────┬────┴─────────────────┘
                             ▼
                    Reasoning World Model  (predict consequences)
                             ▼
                task-local micro-language(s)
                             ▼
                    certified execution → solution → causal ablation
                             ▼
                semantic stepping-stone archive
                             ▼
                 transfer / consolidation → persistent knowledge

**A system that can modify the architecture of its own reasoning while keeping truth
evaluation fixed.**

## 7. Differentiation ledger (one line each; keep for the paper's related-work matrix)

- AlphaEvolve evolves algorithms against an evaluator → CORA diagnoses WHY reasoning
  failed and invents the missing language.
- DGM modifies agent code, selects empirically → CORA's self-modification is typed,
  separated, certificate-carrying, under an immutable verifier.
- TRM refines h_t → h_{t+1} → CORA changes K_t → K_{t+1} (eventually R,K,S jointly).
- World models predict (s_t, a_t) → s_{t+1} → the Semantic World Model predicts
  (K_t, F_t, e_t) → F_{t+1}.
- MSR verifier-guided reasoning steers answers → CORA's verifier steers modification of
  the reasoning architecture itself.
- Ndea: learning guides program synthesis → CORA: **learning guides the synthesis of the
  language in which program synthesis occurs.**

## 8. Priority sequence (do NOT implement all ten now)

    Current Step B (untouched, finishes first)
      → Cognitive Failure Localization
      → Task-local Micro-Language Induction
      → Semantic World Model + fast GPN
      → Verifier-guided test-time invention
      ---------------- ARC-relevant line ----------------
      → Certified open-ended grammar archive
      → Representation / ontology invention
      → Cross-domain structural transfer (protein proof-of-principle)

The first four serve the ARC competition directly; the last three turn it into the
broader research program.

## 9. The larger hypothesis (internal formulation)

> Intelligence requires plasticity not only in weights and states, but in the
> representations and languages in which reasoning occurs.

Stronger form:

> A sufficiently general reasoner should be able to identify which component of its own
> cognition is causing failure and construct a verified modification to that component.

Demonstrating even a constrained version on ARC, followed by a structurally analogous
result in protein/scientific reasoning, is the target that outranks any leaderboard
number. All external claim language remains governed by the evidence tiers and the
novelty-conjunction rule in CORA_TTI_MASTER_PLAN.md §XIV/§XVI — nothing in this
document lowers that bar.
