# CORA-PARENT: Certified Cognitive Architecture Plasticity

*User directive of record, 2026-08-31 (third directive; unifies and supersedes-in-scope
the component lists of CORA_TTI_MASTER_PLAN.md and
CORA_ARCHITECTURE_PLASTICITY_ROADMAP.md — those remain valid; this is the parent).
ADDITIVE ONLY. The immutability preamble of the master plan applies verbatim: nothing
here modifies, interrupts, inspects, reinterprets, optimizes, or contaminates the
running frozen Step-B experiment or any pinned artifact, and nothing here may be
retroactively used to change that experiment.*

## 0. The parent question

Beyond "invent a new semantic operator when the DSL is insufficient":

> Can a reasoning system diagnose WHICH PART of its own cognitive architecture caused a
> certified failure and construct a verified modification to that part?

Cognitive state:

    A_t = (R_t, K_t, S_t, M_t, W_t ; V)

    R_t  representations, views, ontology, object systems
    K_t  semantic/program language
    S_t  search strategy and reasoning control
    M_t  memory, abstractions, concepts, stepping stones
    W_t  internal model of reasoning dynamics / consequences of self-modification
    V    IMMUTABLE VERIFIER — outside the self-modifying state, forever

The system may learn to change how it reasons. It may NOT learn to weaken what counts
as correct. Trajectory: program search → abstraction learning → semantic-language
self-extension → representation self-extension → search/control self-adaptation →
certified cognitive architecture plasticity.

## The eleven ideas

### 1. Cognitive Failure Localization (CFL) — the router above all self-extension
Infer latent failure cause z ∈ {PERCEPTION, REPRESENTATION, SEMANTICS,
PARAMETER_LEARNING, SEARCH, CONTROL, MEMORY, COMPOSITION, RESOURCE_LIMIT} via q(z | F),
F a mechanistic failure representation. Must distinguish: expression exists but search
cannot reach it / expression cannot be represented at all / representation hides the
relevant structure. Self-supervised labels by deliberate crippling: remove operation →
semantic; remove view → representation; remove abstraction → memory; cut depth/budget →
search/resource; corrupt slot learner → parameter-learning. Never trained on task IDs
or human family labels. Target: failure → what part of cognition should change — then,
and only then, (F, z) → e_z.

### 2. Representation and ontology invention
Allow proposals of: new object/view types, relations, groupings, coordinate systems,
latent entities, decompositions, representation transforms, abstraction boundaries
(pixels→objects; coordinates→relative; objects→trajectories; structures→ensembles).
Same evidence discipline as semantic invention: forcing failure evidence → generic
proposal → compact semantics → synthetic falsification → LOO reconstruction → held-out
transfer → causal ablation. No human-added task-specific view after inspecting a target
task. LATER PHASE. Never used to rescue the current Step-B experiment.

### 3. Certified Task-Local Micro-Language Induction
Generalize K_j = K ∪ {e} to G_j = the minimal temporary language for task j:

    (G_j*, p_j*) = argmin_{G,p} [ L(p; D_j) + λ·DL(G | K_global) + μ·DL(p | G) ]   s.t. cert

G_j may hold multiple operations, a relation, a temporary representation, a composition
rule. Bounded rounds G_j,0 → … → G_j,R; after the task, discard G_j \ K_global; next
task starts from the exact same K_global. Persistent global knowledge + ephemeral
task-local plasticity. No cross-hidden-task transfer unless competition policy
explicitly allows; the reset makes the scientific claim stronger regardless: each task
must force its own missing abstraction from its own demonstrations.

### 4. Reasoning / Semantic World Model
W(K, F, e) → predicted next failure state F′. Answers: which failure disappears; what
type becomes reachable; will exact-fit probability rise; will search cost fall; what new
failure appears; is e worth expensive certification. NOT an ARC answer predictor — it
predicts consequences of modifying the reasoning architecture. Supports multi-step
planning K →e1→ K1 →e2→ K2: invention becomes planning. The immutable executor/verifier
is the reality model generating its training targets. W may prioritize hypotheses; it
may NEVER certify them.

### 5. Verifier as active reasoning controller
Keep final LOO certification unchanged; additionally expose deterministic intermediate
obligations (shape relation, palette conservation, component-count relation,
correspondence consistency, bijection, geometric/topology invariants, symmetry,
monotonicity, cardinality). Reasoning = partial hypothesis → obligation → constrained
continuation → new obligation → … When no continuation in the current language can meet
the obligations, that impossibility is itself evidence for semantic or representation
invention. Verifier = truth gate + reasoning sensor. Learned components never touch
verifier semantics.

### 6. Certified Open-Ended Grammar Archive
A bounded Pareto archive 𝒦_t = {K^(1)…K^(m)} of certified language variants, scored on
certified reach, MDL/compression, held-out transfer, runtime, novelty, semantic
diversity, robustness, compositional usefulness. Weaker-today branches may hold
stepping stones. MAP-Elites/Pareto methods are search/control mechanisms ONLY; no
branch persists on benchmark fitness alone; every persistent modification carries
evidence and provenance. Not unconstrained evolutionary code mutation.

### 7. Semantic stepping-stone memory
Near-solve memory lifted from the program level to the LANGUAGE level. An insufficient
extension with a certified local property enters a sanitized archive holding ONLY: type
signature, normalized semantics, proven local property, failure reduced, provenance,
transfer/falsification history, MDL, behavioral fingerprint — never answer grids or
task identifiers. Composition search over stepping stones (e_a fixes correspondence,
e_b fixes placement → e_c = e_a ∘ e_b) enables partial conceptual progress → later
conceptual synthesis.

### 8. CORA Forge / evolving capability worlds
Operator-dropout generalized to an adversarial curriculum. Cycle: current reasoner K_t
→ generate tasks K_t almost solves → locate systematic failures → force invention →
counterexamples separating real abstraction from shortcuts → improve reasoner → evolve
harder worlds. Task generation optimizes: discrimination between semantic hypotheses,
forcing missing representations/operators, shortcut breaking, compositional depth,
novel typed interfaces, transfer prediction. Each new capability e auto-generates
positives requiring e, near-misses where e is wrong, compositions with other
operations, adversarial correlation-exploiters. Capability and curriculum co-evolve.

### 9. Semantic consolidation, compression, forgetting
|K_t| must not grow forever. Lifecycle: EPHEMERAL → PROBATIONARY → GLOBAL →
CONSOLIDATED → DEPRECATED/FORGOTTEN. Promotion weighs independent transfer count,
causal necessity, MDL, overlap, search benefit vs cost, robustness. Related operations
anti-unify/compress (e1,e2,e3 → C); once C certifiably replaces them, redundant
primitives retire. Measure capability gain AND language entropy / search burden.
Lifelong cycle: invent → falsify → transfer → consolidate → compress → forget.

### 10. Cross-domain semantic morphisms
Transfer abstract reasoning structure, not literal operators:

    ARC:      Collection[Region]    → Select → Transform → Weight/Aggregate → Grid
    Protein:  Collection[Conformer] → Select → Perturb   → Weight/Aggregate → Observable
    Schema:   Collection[A] → Predicate[A] → Transformation[A,B] → Aggregation[B] → Observation[C]

Morphism: ARC ontology ↔ abstract meta-types ↔ scientific ontology. Long-term
experiment: discover schema in domain A; erase domain vocabulary; keep structural role;
instantiate in domain B; test acceleration; require independent domain-B verification.
The Universality claim becomes "abstract reasoning structures learned in one domain can
seed reasoning in another" — not "we ran the ARC algorithm on proteins".

### 11. MetaExtensionEngine — deterministic scientific self-extension

    MetaExtensionEngine[Observation, View, Type, Relation, Expression,
                        Executor, Verifier, FailureTrace, Extension]

    hooks: build_views / build_entities / search / execute / verify / trace_failure /
           localize_failure / propose_extension / fit_extension / falsify_extension /
           separate_extension / promote_extension / consolidate_memory

ARC plugin: Grid, Cell, Region, Entity, Colour, Placement, Transform, Relation, ….
Future biomolecular plugin: Protein, Structure, Conformer, ConformerSet, MotionMode,
Sampler, Perturbation, PhysicalConstraint, Weighting, Observable, SAXSProfile — with an
executable deterministic verifier (bond geometry, clashes, torsion validity, chain
continuity, R_g, RMSD/diversity, physical constraints, SAXS forward calculation,
held-out measurement agreement). Do NOT build the full biomolecular implementation
until the ARC mechanism is established; the initial universality demonstration is a
minimal second-domain proof that a WITHHELD semantic capability is recovered by the
SAME engine.

## The unified parent loop

    OBSERVE → REPRESENT → SEARCH → VERIFY → FAILURE
      → typed/causal failure representation
      → COGNITIVE FAILURE LOCALIZATION
      → decide what must change: representation | semantics | search/control |
                                 parameter learner | memory/abstraction
      → generate candidate self-modifications
      → REASONING WORLD MODEL ranks predicted consequences
      → VERIFIER generates constraints, rejects invalid hypotheses
      → task-local micro-language / architecture
      → re-induce solution → FULL CERTIFICATION → CAUSAL ABLATION
      → not solved: useful partial modifications → STEPPING-STONE ARCHIVE
      → solved:     local use → held-out transfer → probationary/global promotion
                    → OPEN-ENDED GRAMMAR ARCHIVE
                    → consolidation / compression / forgetting
                    → CORA FORGE generates harder capability worlds
                    → next cycle

Cross-domain morphisms sit above domain-specific types, below the universal engine.

## Architectural principle

    WHAT MAY CHANGE:        representation, ontology, semantic language, memory,
                            search, controller, proposal model, reasoning world model
    WHAT DETERMINES TRUTH:  declared task observations; executor semantics of any
                            active frozen experiment; the certification criterion;
                            hidden labels; any experimental protocol once frozen

A general self-improvement architecture that cannot redefine success.

## Three layers — never collapsed into one system

    CORA-SCIENCE  exhaustive, offline, evidence-generating, slow (the running track)
    CORA-TTI      learned proposal, fast execution, task-local, competition-constrained
    CORA-PARENT   architecture plasticity, open-ended memory, multiple timescales,
                  representation+semantics+search adaptation, cross-domain reasoning

## Priority phases (implement in order unless evidence forces change)

    P0  finish frozen Step B (nothing above changes it)
    P1  semantic separation → E_transfer → promotion → Level-3 causal transfer
    P2  TFG, Cognitive Failure Localization, GPN, fast exact executor, CORA-TTI
        (directly relevant to ARC-AGI-2 performance)
    P3  Certified Micro-Language Induction, active verifier controller,
        Reasoning World Model (deeper test-time plasticity)
    P4  stepping-stone memory, open-ended grammar archive,
        consolidation/compression/forgetting (cumulative open-ended learning)
    P5  representation/ontology invention (next major scientific leap)
    P6  CORA Forge / evolving capability worlds
    P7  MetaExtensionEngine extraction, cross-domain morphisms,
        minimal second-domain proof (only after ARC mechanisms are established)

## Breakthrough bar (external language remains evidence-bound)

Never write "first AGI", "best ever", "nobody has done this", "breakthrough",
"self-aware", "autonomous scientist" without evidence appropriate to the claim.
Progression: A semantic production invented+transferred → B task-local invention causes
new ARC solves → C multiple inventions compose → D representation invention causes
solves unavailable to semantic extension alone → E correct localization of different
failure classes → F several self-extension cycles with cumulative gains and controlled
complexity → G the same meta-extension mechanism shows causal transfer in a second
domain → H CORA-TTI competitive with or exceeding leading non-LLM ARC-AGI-2 approaches.
**F + G + H together justify treating this as a general reasoning architecture.**

## Final parent-system thesis

> Intelligence requires plasticity not only in parameters, hidden states and candidate
> programs, but in the representations and languages in which reasoning occurs.

> A sufficiently general reasoner should be able to detect which component of its own
> cognitive architecture is causing systematic failure, construct a candidate
> modification to that component, and retain the modification only when an external
> immutable verifier and held-out evidence show that it causes transferable capability.

Design principle: **SELF-MODIFYING REASONER + NON-SELF-MODIFYING TRUTH CRITERION.**
ARC is the laboratory; CORA-TTI the fast implementation; CORA-PARENT the general
architecture; future scientific domains the universality test.
