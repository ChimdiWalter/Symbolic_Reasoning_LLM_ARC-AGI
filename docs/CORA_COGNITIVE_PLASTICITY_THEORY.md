# Cognitive Plasticity: formal core for CORA-PARENT

*Companion to CORA_PARENT_ARCHITECTURE.md and CORA_SEMANTIC_PLASTICITY_THEORY.md
(which formalizes the K-only special case). Definitions only; no results claimed.*

## 1. Cognitive state and the immutable anchor

    A_t = (R_t, K_t, S_t, M_t, W_t ; V)

R_t (representations/ontology), K_t (semantic language), S_t (search/control),
M_t (memory/abstractions/stepping stones), W_t (model of reasoning dynamics) are the
MUTABLE components. V — the verifier: certification criterion, executor semantics of
frozen experiments, declared observations, hidden labels, frozen protocols — is
IMMUTABLE and lies outside A_t's modifiable region. Formally, every admissible
self-modification operator μ satisfies μ(A_t; V) = (A_{t+1}; V): V is a fixed point of
all learning. The system may change how it reasons; it may never change what counts as
correct.

## 2. Failure localization

A certified failure episode yields a mechanistic trace F (typed failure graph; no task
identity). Localization infers a distribution over latent causes

    q(z | F),   z ∈ {PERCEPTION, REPRESENTATION, SEMANTICS, PARAMETER_LEARNING,
                     SEARCH, CONTROL, MEMORY, COMPOSITION, RESOURCE_LIMIT}

and modification proposals are conditioned on the diagnosis: (F, z) → candidate change
to the z-component only. Ground truth for training is manufactured by controlled
crippling of known components (remove operator / view / abstraction; cut budget;
corrupt learner), giving self-supervised (F, z) pairs with no human labels and no task
IDs. The required calibration property: on held-out crippled systems, argmax_z q(z|F)
recovers the ablated component class.

## 3. Three timescales of plasticity

1. **Inference plasticity** — within one reasoning episode: search state h changes;
   A and K fixed. (Ordinary thinking.)
2. **Task-local semantic plasticity** — within one unseen task j:
   K_global → G_j (micro-language; possibly with temporary representations), bounded
   rounds, full certification per round, then RESET: G_{j+1},0 = K_global.
   (Task-specific conceptual invention.)
3. **Lifelong cognitive plasticity** — across verified experience:
   A_t → A_{t+1} only through the promotion protocol (held-out transfer + causal
   necessity + consolidation). (Durable learning.)

The separation is load-bearing: it distinguishes thinking, inventing-for-now, and
learning-for-good, and each timescale has its own admission rule and evidence bar.

## 4. Cognitive credit assignment

When a capability gain follows modifications ΔR, ΔK, ΔS (etc.), the gain must be
attributed by architecture-level ablation over the modification lattice:

    A + ΔR,  A + ΔK,  A + ΔS,
    A + ΔR + ΔK,  A + ΔR + ΔS,  A + ΔK + ΔS,
    A + ΔR + ΔK + ΔS

yielding main effects (representation / semantic / search contributions) and
interaction effects. Where the full factorial is infeasible, use pre-registered
fractional designs or causal approximations — never post-hoc selection. Long-term
objective: learn the mapping *what kind of self-change tends to repair what kind of
failure* — which is q(z | F) closing the loop with measured credit.

## 5. Cognitive rate–distortion

Arbitrary growth of A is not rewarded. The standing objective for durable admission:

    maximize   capability gain
             − λ · semantic complexity (DL of the admitted change)
             − μ · inference cost (measured search burden it induces)
             − ν · transfer failure (held-out shortfall)

Study the frontier capability vs language complexity vs compute. Consolidation and
forgetting (lifecycle: ephemeral → probationary → global → consolidated → deprecated)
are the mechanisms that keep A on the frontier. The ideal architecture is not the
largest: it is the smallest architecture that efficiently explains and solves the
largest class of tasks.

## 6. Soundness invariants (inherited and extended)

1. V immutable; no learned component (GPN, W, localizer, scheduler, archive policy)
   may weaken, replace, or precondition certification.
2. W and all proposers may prioritize; only V certifies.
3. No task identity, family label, or hidden-corpus statistic enters F, q(z|F), W, or
   any scheduler state.
4. Durable changes to any component of A pass held-out transfer + causal ablation;
   task-local changes die at task end.
5. Every claimed gain carries its credit-assignment artifact (§4) and its ablation.
6. Archives (grammar variants, stepping stones) store sanitized semantics only —
   never answer grids, never task identifiers.
