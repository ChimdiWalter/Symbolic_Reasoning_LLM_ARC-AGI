# CORA experiment ladder, Levels 5–9 (future; falsifiable criteria fixed in advance)

*Extends the existing evidence ladder (L1 task discovery — ACHIEVED; L2 abstraction
invention — ACHIEVED; L3 causal abstraction transfer — NOT ACHIEVED, blocked on reach;
L4 semantic-language self-extension — RUNNING). No Level below may be claimed until its
experiment exists, its splits/seeds are frozen BEFORE running, and its criteria are met
verbatim. Negative outcomes are recorded and published, never patched.*

## Level 5 — Task-local micro-language induction

**Question.** Can the system construct multiple interacting temporary semantics for an
unseen task?

**Success criteria (ALL required):**
1. On a frozen held-out task set, ≥1 task where certified solving requires |G_j \ K| ≥ 2
   (at least two task-local extensions used by the winning program).
2. Full LOO certification passes with G_j installed; baseline (K only) fails the task.
3. Joint ablation: removing EITHER extension breaks the solve (interaction is real,
   not two independent repairs).
4. The reset rule held: nothing from G_j appears in any later task's search state.
5. Budget: the whole episode inside the frozen per-task budget of the run.

**Falsified for a task set if** exhaustive-eligible tasks yield only single-extension or
zero-extension solves — then L5 reduces to L4-at-test-time and must be reported as such.

## Level 6 — Representation self-extension

**Question.** Can certified failure force invention of a new ontology/view/type that
enables solving?

**Success criteria:**
1. A task (or synthetic family, pre-frozen) where search under every existing view
   fails exhaustively (not budget-censored, or masked per the deadline boundary).
2. A machine-proposed representation transform/view/type — from generic constructors,
   with no human-authored task-specific view added after inspecting any target task —
   under which the certified search finds a program passing full LOO.
3. Separation: the winning program's semantics are not expressible over existing views
   within the frozen bounds (view-level separation certificate).
4. Causal ablation: removing the invented view restores failure.
5. Held-out transfer of the VIEW to tasks that played no part in inventing it.

## Level 7 — Cognitive failure localization and targeted repair

**Question.** Can the system identify whether representation, semantics, search or
memory is responsible for a failure, and modify the correct layer?

**Success criteria:**
1. Localizer q(z|F) trained ONLY on self-supervised cripple data (no task IDs).
2. On a frozen held-out cripple suite (components withheld during training):
   localization accuracy significantly above the majority-class baseline, with
   confusion matrix published.
3. End-to-end: on ≥1 pre-frozen evaluation family per failure class, repair conditioned
   on the diagnosed layer solves tasks that repair conditioned on a WRONG layer (or
   unconditioned repair at equal budget) does not — the diagnosis is causally useful,
   not decorative.
4. Negative control: on solvable tasks the localizer does not trigger spurious
   architecture changes.

## Level 8 — Open-ended cumulative architecture growth

**Question.** Can several cycles produce genuinely new capabilities while controlling
language complexity and avoiding catastrophic search expansion?

**Success criteria:**
1. ≥3 complete cycles of invent → falsify → transfer → consolidate → compress → forget,
   each admitting at least one durable change through the full promotion protocol.
2. Monotone capability: certified reach strictly grows across cycles on a frozen
   benchmark, with each cycle's gain surviving causal ablation of that cycle's
   admissions.
3. Complexity control: language entropy / mean search burden stays within a pre-frozen
   envelope (growth of |K| offset by consolidation; no super-linear blowup of typed
   candidates at fixed depth).
4. Stepping-stone evidence: ≥1 admitted capability whose provenance passes through the
   stepping-stone or grammar archive (a branch not maximal at its creation time).
5. Later-cycle inventions must depend on earlier-cycle admissions (chain ablation:
   removing cycle-1 admissions breaks a cycle-3 solve).

## Level 9 — Cross-domain reasoning-structure transfer

**Question.** Can an abstract reasoning schema learned in one domain causally
accelerate semantic invention in a different domain?

**Success criteria:**
1. A schema discovered in domain A (ARC), abstracted to meta-types with ALL
   domain-specific vocabulary erased (audited lexeme check).
2. A second domain B with its own deterministic executable verifier, its own frozen
   holdout, and a withheld semantic capability recoverable in principle.
3. The SAME MetaExtensionEngine, seeded with the abstract schema, recovers the withheld
   capability in B faster / with fewer proposals than the unseeded engine (pre-frozen
   comparison protocol, seeds fixed).
4. Domain-B verification is independent: no ARC artifact, no shared learned weights
   carrying domain-A surface features.
5. Ablation: destroying the morphism (shuffling the schema's role structure) removes
   the acceleration.

## Reporting discipline

Each level gets: a pre-registered protocol file (frozen + hashed before the first run),
an append-only results ledger, and a single artifact-backed number per claim. The
external-language bar of CORA_PARENT_ARCHITECTURE.md ("Breakthrough bar") governs all
wording. A level not attempted is NOT ACHIEVED; a level attempted and failed is
reported with its evidence.
