# Semantic Plasticity: formal core for CORA-TTI

*Companion to CORA_TTI_MASTER_PLAN.md. Definitions only — no results are claimed here.*

## 1. Languages, programs, and solving

A **reasoning language** K is a finite set of typed productions (operators, learners,
constructors) closed under a fixed typed composition discipline. `F(K)` denotes the set
of programs expressible over K under the frozen search bounds. For a task with
demonstrations `D = {(x_1,y_1),…,(x_n,y_n)}` and test input x*, ordinary certified
induction solves

    p* = argmin_{p ∈ F(K)} L(p; D)      subject to CERT(p, D, K)

where L is exactness on all demonstrations (with MDL tie-breaking) and CERT is the
leave-one-out-by-reinduction certificate: for every held-out fold, the FULL induction
re-run from the remaining pairs must rediscover a program solving the held-out pair.

## 2. Joint program/language search

CORA-TTI replaces the fixed-language objective with a joint objective over programs and
bounded local language extensions e drawn from the generic constructor space E:

    (e*, p*) = argmin_{e ∈ E, p ∈ F(K ∪ {e})}  L(p; D) + λ·MDL(e) + μ·Complexity(p)
               subject to CERT(p, D, K ∪ {e})

MDL(e) prices the extension so that inventing semantics is never free: an extension is
justified only when its description cost is repaid by the induced program's fit and
simplicity. λ and μ are frozen before evaluation.

## 3. Global memory vs ephemeral plasticity

Two language states with different lifetimes and admission rules:

- **K_global** — persistent semantic memory. Admission ONLY through the frozen
  scientific promotion protocol (multi-source LOO certification → semantic separation →
  held-out E_transfer → promotion), or from allowed public/synthetic material learned
  before evaluation. K_global never changes during a hidden evaluation run.
- **K_{j,r}** — the ephemeral language of evaluation task j after r invention rounds:

      K_{j,0} = K_global
      K_{j,r+1} = K_{j,r} ∪ {e_{j,r+1}}     for r < R (R small, frozen)

  where each e must pass the full certification cascade on task j's own demonstrations.

**Reset rule:** after task j terminates (solved or not), every task-local extension is
deleted: `K_{j+1,0} = K_global`. No invented semantics flow between hidden evaluation
tasks. This is maintained even if competition rules would permit accumulation, because
it makes the mechanism claim clean: each solved-by-invention task demonstrates
construction of the missing abstraction from that task's evidence alone.

## 4. The invention step

On certified failure of search under K_{j,r}:

    TFG_j,r  = trace_failure(search state, D)            (typed failure graph; no task identity)
    E_top-k  = GPN(TFG_j,r, interface)                    (proposal distribution q(e | TFG, interface))
    e_{j,r+1} = first e ∈ E_top-k surviving:
                typecheck → invariants → exact demo fit → counterexample checks
                → partial folds → FULL LOO re-induction under K_{j,r} ∪ {e}

Cheap stages are admissible filters: they may reject, never accept. Only the full LOO
gate confers "certified". The GPN orders the search; the verifier decides belief.

## 5. What distinguishes this from test-time training

    TTT:       θ → θ′        (parameter adaptation; opaque; verified only by outcome)
    CORA-TTI:  K → K′        (language adaptation; each step is a typed, auditable,
                              certificate-carrying object with an ablation test)

A TTI-dependent solve is defined by the conjunction: baseline failure under K_global +
production proposed from the failure + winning program uses it + LOO passes + test
output correct + ablation (remove e, re-run) fails. Solves surviving ablation are
credited to search, not invention.

## 6. Metrics

- **CSR** (unchanged): certified solves / tasks.
- **CSAR** — Certified Semantic Adaptation Rate: fraction of evaluation outputs correct
  ONLY via a task-local extension surviving full certification (i.e. TTI-dependent by
  the §5 conjunction).
- Secondary: extension depth r used; proposals/certified/causally-necessary counts;
  compute per certified extension; solve gain per unit invention compute.

The efficiency-native theory question: **how much task-solving capability can a system
acquire by restructuring its hypothesis language, per unit compute?** This aligns
semantic plasticity with ARC's stated efficiency objective.

## 7. Learning where to search (curriculum, in brief)

GPN is trained self-supervised by semantic withholding: remove a known or synthesized
production e from a language, generate tasks requiring e, record the crippled solver's
TFG, and supervise reconstruction of e (Stage A: named operators; Stage B: unregistered
compositions from the constructor meta-language; Stage C: whole-family holdouts;
Stage D: type-interface holdouts). Success criterion is construction of an appropriate
semantic structure for families never seen as named instances — not operator-catalog
recall. All splits/seeds frozen before their experiments.

## 8. Soundness invariants (binding on every implementation)

1. The verifier is immutable; no accelerated or learned component may weaken CERT.
2. GPU/vectorized execution must be bit-equal to the CPU reference on differential
   suites; the GPU is an accelerator, never an approximate verifier.
3. No task identity, family label, or hidden-corpus statistic enters TFG, GPN input,
   or the scheduler's per-task state.
4. K_global admission during the project follows the frozen scientific protocol only.
5. Every claimed TTI solve carries its ablation artifact.
