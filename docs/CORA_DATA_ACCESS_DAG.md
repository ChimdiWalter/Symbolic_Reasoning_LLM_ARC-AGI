# Data-access dependency DAG — which module may read which split, and when

*Binding for all CORA-TTI / CORA-PARENT development. Violations are protocol breaches,
not bugs. The isolation test (tests/test_cora_parent_isolation.py) mechanically
enforces the FORBIDDEN set on the new packages.*

## Data classes

    D1  ARC public TRAINING tasks + solutions            (open for everything)
    D2  Synthetic tasks (dream/dropout/Forge generators) (open for everything; seeds frozen)
    D3  ARC public EVAL — DEV half (60, eval_split_v1)   (TTI development/gate C2; aggregate
                                                          analysis only; no per-task patches)
    D4  ARC public EVAL — HOLDOUT half (60)              (scored ONLY at gates C3/C4/C5;
                                                          each scoring event logged; never
                                                          inspected per-task)
    D5  Kaggle semi-private/private                      (submission only; unreachable)
    F1  Live Step-B journal                              (FORBIDDEN to everything except the
                                                          frozen runner; line-count only)
    F2  E_transfer split                                 (frozen sequence only: opens at the
                                                          post-pin transfer stage)
    F3  Lockbox / sealed expectation                     (frozen sequence only)
    F4  Provenance firewall (HMAC secret, token map)     (never read by any new module)
    F5  Step-B outputs pre-pin                           (nothing reads before hash+pin)

## Module → allowed inputs

    KaggleRuntimeEmulator        D1, D2                    (never D3/D4 contents; only counts)
    TypedFailureGraph builder    D1, D2, (D3 at gate C2 via the runner only)
    FailureLocalizer (CFL)       D2 (cripple corpus)       train/val families frozen first
    GrammarProposalNetwork       D2 (dropout/holdout corpus)
    ReasoningWorldModel          D2 + executor rollouts on D1/D2
    Fast batched executor        D1, D2 (differential suites; synthetic-first)
    Anytime scheduler            statistics from D1/D2 only
    Attempt-diversity evaluator  D1, D2, D3 (aggregate)
    MicroLanguage engine         task-local demonstrations of the task being solved, only
    SemanticArchive              sanitized records from D1/D2 episodes (no grids, no IDs)
    CORA Forge generator         D2 + aggregate failure statistics from D1/D2
    MetaExtensionEngine core     domain plugins only; no direct data access
    Scoring harness              D3 (dev, freely logged), D4 (gates C3-C5 only, ledgered)

## Promotion-time edges (open only when the frozen sequence reaches them)

    Step-B outputs --pin--> inspection --> separation certificate --> F2 (E_transfer)
    --> promotion --> K_global update --> TTI may then USE promoted productions
    (TTI never reads F2 itself; it receives only the promoted K_global.)

## Hard rules

1. Nothing in the new packages imports from, opens, or globs: level4 journal paths,
   E_transfer paths, Lockbox/sealed paths, provenance firewall, pre-pin Step-B outputs.
2. D4 (holdout) results never feed any training set, prompt, curriculum, or manual
   analysis; only the aggregate score + ledger entry exist.
3. D3 failures inform SYSTEM-level changes only (aggregate statistics); never a
   primitive added for a named public task.
4. Every generator/model records its seeds and split hashes next to its artifacts.
