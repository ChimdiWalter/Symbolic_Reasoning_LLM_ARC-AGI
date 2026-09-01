# CORA-TTI execution directive (2026-09-01) — work order of record

*User directive; supersedes nothing, sequences everything. All work in this
worktree only. The frozen Step-B experiment is never modified, inspected,
interrupted, or accelerated. Blueprint tier-A wording corrected first:
multi-source certification is SYNTHETICALLY DEMONSTRATED, REAL STEP-B RESULT
PENDING.*

## Execution order

1. **Full-engine integration** — TTI as failure fallback for the REAL
   185-corpus engine (pipeline+geocat+object), not the blind substrate:
   full search -> failed -> evidence -> TFG -> propose -> ephemeral install ->
   re-enter the full learner -> full LOO -> ablation -> reset. TTI only
   proposes/orders/prunes; the certified learner is the sole acceptance
   authority; no base-registry mutation persists between tasks. Measure on
   frozen DEV only: base pass@2, base+TTI pass@2, invention activations,
   certifications, mean/median task time, timeouts, attempt complementarity.
   No tuning on individual DEV identities.
2. **Stage-B constructive proposer** — TFG + interface -> typed production
   AST/sketch from GENERIC constructors (never hand-authored ARC primitives);
   type-directed/constrained decoding so invalid ASTs get no budget; slots
   fitted by the ordinary learners; training targets are productions ABSENT
   from the registered language; full family holdouts; the headline
   experiment: useful ASTs whose complete production was never a training
   label.
3. **Multi-operator / micro-language dropout** — withhold {e1,e2}, then mixes
   of production+relation+view+slot-learner; target minimal temporary
   micro-languages; measure single/multi recovery, minimum recovered language
   size, extra-language penalty, LOO, ablation necessity; MDL-regularized —
   a larger language is never better merely because it fits.
4. **Cognitive failure localizer** — q(z|TFG) on the cripple corpus
   (SEMANTICS / RESOURCE_LIMIT / PARAMETER_LEARNING); seeds frozen before
   training; report accuracy, macro F1, confusion, calibration; baselines
   from search statistics alone; add SEARCH / MEMORY / COMPOSITION only with
   mechanistically clean labels; representation failures later, never with
   vague labels. The localizer routes self-modification budget.
5. **Fast exact execution** — from 5.3x toward 100x on invention workloads:
   DAG-normalized sharing, cross-candidate memoization, cross-fold cache
   reuse where logically valid, batched slot fitting, vectorized grid ops,
   GPU kernels, multi-fidelity rejection. Differential tests on everything;
   zero mismatches; the fast path never certifies.
6. **Multi-round task-local invention** — bounded K_j,0 -> ... -> K_j,R;
   later rounds may depend on the failure AFTER an earlier extension; the
   scheduler decides whether another round earns its compute; full
   provenance (failure_r, extension_r, certificate_r, failure_{r+1});
   complete reset to K_global between hidden tasks.
7. **Scheduler integration** — actions: continue search / switch view /
   extract TFG / more proposals / certify / another round / stop and place
   attempt 2. Priors from allowed synthetic+public evidence only; maximize
   expected pass@2 under ONE global budget; compare vs equal-split, fixed
   sequential, ordinary-only.
8. **Two-attempt system** — diversity policy in the real output writer;
   measure conditional rescue P(A2 correct | A1 wrong), not marginal A2;
   source-pair complementarity.
9. **Kaggle packaging** — offline, two attempts, vendored weights+deps, 12h
   hard guard, memory accounting, graceful per-task failure, deterministic
   writing, exact schema; full 120-task rehearsal <= 8h (>= 4h margin);
   gate C1 = complete end-to-end emulator run.
10. **P1 tooling (prepare, do NOT execute)** — separation certificate vs
    K_L4*, E_transfer runner, promotion machinery, post-promotion
    rediscovery, Level-3 rerun harness. Each script REFUSES to run unless
    the Step-B output hash exists and is pinned; none reads the live journal.
11. **Paper + prior art** — separate ARC Prize manuscript skeleton (never
    centered on training accuracy); results structure: public eval, Kaggle
    score, runtime, base/+global/+GPN/+TTI/+attempt2, invention ablations,
    separation, family holdouts, micro-language, localization, limitations.
    Novelty matrix completed with verified citations before any first-of-kind
    claim.
12. **Evidence rule** — KNOWN OPERATOR RECONSTRUCTION != SEMANTIC INVENTION.
    The 5/12 result is reconstruction. Only a constructively generated
    production surviving the declared separation test may be called an
    invention. Never weakened for presentation.
13. **Holdout discipline** — DEV for engineering; HOLDOUT only under gates
    C3/C4/C5, append-only ledgered; never repeatedly evaluated while tuning.
14. **Completion report** — commit hashes, test counts, DEV scores, runtime,
    constructive-proposal metrics, family-holdout metrics, localizer metrics,
    differential mismatch count (must be 0), full emulator runtime, remaining
    blockers, claims earned vs unearned.

Standing rules: push only to `cora-tti-dev`; no merge to `main` before
explicit evidence review; no AI attribution anywhere; no em dashes in
manuscript prose.

## The two inflection results (user's assessment criteria)

1. Constructive AST proposal succeeds on held-out semantic families.
2. Full 185-engine + TTI produces new DEV ARC solves.

Milestone truth table as of this directive: infrastructure REACHED; mechanism
PARTIAL (certified reconstruction only); invention NOT YET; ARC score NOT
YET; breakthrough NOT YET.
