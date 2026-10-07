# CORA real ARC causal pilot v1: protocol

Status: NOT FROZEN. The feasibility rule of section 12, fixed before the
development dry run (commit f47c795), failed: 0 of 60 development tasks
reach the installed stage (`records/REAL_ARC_PILOT_V1_FEASIBILITY.md`). By
that rule no pilot is frozen and the blocker is recorded. Everything else
here stands as the design a later freeze would use unchanged; section 17 is
empty because nothing was frozen.

## 1. Question and claim ceiling

Can the complete CORA loop (failure analysis, proposal without an oracle,
verification, selection, compilation, temporary installation, the same
reasoner) produce at least one independently scored rescue of a real
ARC-AGI-2 task that the frozen native reasoner fails, with the full
B/P/U/L/T/A witness, while abstaining whenever the training evidence is
insufficient?

The pilot is small and drawn from the public training split, on which the
base engine was developed. A positive result licenses bounded real-task
development (section 11), nothing more: no ARC-AGI-2 performance or
generalization claim, no change to the sealed 185 of 1,000, no evaluation
claim, no claim that the engine discriminates right from wrong extensions.

## 2. Starting state (verified 2026-10-07)

- v1.9: ENGINE_STABILITY_REPAIR_ACCEPTED, result commit 2885a04; G1 pass
  (6:0, 8:0), G2 27 of 30, G3 27 against 12, G4 pass; terminal verifier 28 of
  28; claim LEVEL 2, synthetic domain only
  (`records/ITEM2_V19_PROSPECTIVE_RESULT_20261007.md`).
- Preserved unchanged and pinned by the manifest: K* (identity b009a9fb), K*'
  = K* + K*-4 (e4672bfa), the v1.7 compiler, the v1.8 proposer, the v1.9
  repair, the frozen v1.8 selector artifact, geocat_arc and the harness.
- The critical risk carried into this design: K*' accepted 5 of 5 wrong
  seven-demonstration and 28 of 28 wrong four-demonstration extensions. The
  engine is not a discriminator; this protocol puts the safety burden on
  train-only activation and abstention (section 8).

## 3. Data

- ARC-AGI-2 public training split, `Reasoning_Project_tti/data/arc/`:
  challenges sha256 `779eaba8...20f5`, solutions sha256 `9f07a38b...97f9`,
  1,000 tasks (`records/REAL_ARC_PILOT_V1_DATA_AUDIT.md`). DATASET_UNAVAILABLE
  does not apply.
- Not used: synthetic tasks, the evaluation split, the 60 DEV, the 60
  HOLDOUT, Step B outputs, VDCG, E_transfer, the Lockbox.
- Sealed baseline record, read by the evaluator only: v23
  `outputs/unified_harness_v23/results.json` (sha256 `763beefd...f931`) and
  `outputs/v23_arbitration/results.json` (sha256 `35e8f5c9...200b`) in the
  main project; their union must be exactly 185 tasks.
- Exposure: the engine was developed on this split. The CORA components were
  developed on synthetic tasks and on the evaluation split's DEV-60
  extract; no training task was used by them before this block.

## 4. Task selection (fixed before any task was run; commit 4d3c29b)

- Scope, from the demonstrations alone: at least three demonstrations,
  every demonstration keeps its grid shape, every demonstration changes at
  least one cell. 548 of 1,000 tasks (n = 3: 403; n = 4: 120; n >= 5: 25).
- Order: ascending sha256("cora-real-arc-pilot-v1|" + task_id). No outcome,
  target or solver result enters it.
- Development set: the first 60 in-scope tasks in the order (n3 47, n4 11,
  n5p 2). Used only for the reasoner-only dry run of section 12; excluded
  from the pilot.
- Pilot: per stratum, the first quota tasks in the order outside the
  development set, quota = N x (3, 2, 1) / 6 for (n3, n4, n5p), N in {48,
  72, 96, 120} fixed by section 12. The strata over-sample tasks with more
  demonstrations relative to the population (403 : 120 : 25) because the
  leave-one-out leg is not relaxed.
- No baseline-failure-enriched stratum: the sample does not depend on any
  baseline record. The sealed record enters only the B leg (section 9).
- Record: `records/pilot_v1/selection.json` (sha256 in the manifest).

## 5. The two processes and the isolation boundary

- REASONER: worker processes started by `scripts/pilot_v1_run.py`. Their only
  task input is the pilot bundle `records/pilot_v1/pilot_bundle.json`: per
  opaque key (an HMAC of the task id under a secret salt), the
  demonstrations and the test INPUTS. `cora_pilot.bundle.check_bundle`
  refuses anything else.
- Every reasoner process installs `cora_pilot.isolation` before importing
  project code: a CPython audit hook that refuses, and logs, any attempt to
  open or list an ARC data file, a solutions file, the evaluator directory,
  the selection record, any `records/` file other than the bundle, git
  internals, the main project tree (sealed records, Step B) or VDCG, and any
  attempt to start a process. The logs are audited by the coordinator, the
  evaluator and the terminal verifier; any refused access or missing log is
  PILOT_LEAKAGE.
- The coordinator composes the predictions and git-commits them, with the
  rows and isolation logs, before anything reads a target.
- BLIND EVALUATOR: `scripts/pilot_v1_evaluate.py`, a separate process run
  only after the commit. It verifies that the committed files are
  byte-identical to those on disk, then alone reads the key map
  (`records/pilot_v1_evaluator/pilot_keymap.json`), the pinned solutions and
  the pinned sealed record, scores what was committed and never changes a
  prediction.

## 6. The same-reasoner closed loop, per task

A. NATIVE_BASELINE: `harness.run_harness.run_one_task`, the sealed per-task
   entry, with the five v23 chain flags (ARC_DIHEDRAL_FRAMES 45,
   ARC_GENERATIVE, ARC_PATTERN_DERIVE, ARC_VARIANT_BUDGET, ARC_RAY_EXT), the
   sealed default caps, the frozen `library.json` (sha256 `cdacd018...`) in
   the object layer's directory, solution None, emit-predictions on.
   Separate process and environment (`cora_pilot.native`).
B. Failure analysis: the frozen reasoner's typed failure frontier over its
   200 single-block expression programs, built from the demonstrations
   (`v18_proposer.build_input`).
C. Proposal without an oracle: `v18_proposer.solve(train,
   "FAILURE_CONDITIONED")`, frozen limits (180 s, depths 2 and 3, at most 256
   proposals, 32 probed).
D. Compilation: the frozen v1.7 compiler (`compile_selected`).
E. Verification from demonstrations only: the frozen fitter's exact replay
   (in C), the engine's acceptance gate (G), the adaptive leave-one-out (L).
F. Activation decision: section 8, train evidence and test inputs only.
G. Temporary installation into K*' (`v19_repair.run_reasoner`).
H. The same reasoner rerun, twice (determinism).
I. Commit: the coordinator commits every prediction before scoring.
J. Removal and restoration: the compiler's context snapshots, the repair's
   `restored()`, and a per-task state snapshot equality.

## 7. Arms and the deployable output

| arm | what runs |
|---|---|
| NATIVE_BASELINE | A |
| KSTAR_PRIME_WITHOUT_EXTENSION | K*' with nothing installed, 8 s, before the loop |
| CORA_FAILURE_CONDITIONED | B to J |
| DEMONSTRATION_ONLY_CONTROL | the v1.8 DEMO_ONLY proposer, compiled, installed in K*', rerun (no leave-one-out) |
| SHUFFLED_FAILURE_CONTROL | the v1.8 SHUFFLED_FRONTIER proposer with the failure of the next key (cyclic, sorted), compiled, installed in K*', rerun |
| EXTENSION_REMOVED_ABLATION | K*' with nothing installed, after the loop, same budget |
| MATCHED_COMPUTE_CONTROL | K*' with nothing installed at budget clamp(proposer seconds + K*' + e seconds, 24, 240) |

Deployable output (the system the net score measures): native attempts;
when CORA activates, its prediction takes attempt 2 if native has an attempt
1 for that test input, attempt 1 otherwise (native attempt 2 kept). Native's
attempt 1 is never displaced.

## 8. Activation and abstention (train-only)

CORA activates only when every gate holds, checked in this frozen order; the
mechanism class is the class of the first failing gate. Every gate is
recorded even after an earlier failure.

| gate | requirement | class if it fails |
|---|---|---|
| proposal | the FAILURE_CONDITIONED proposer SELECTED an extension | NO_PROPOSAL (also K's single-block search already exact), NO_VERIFIED_PROPOSAL, AMBIGUOUS_CANDIDATES, RESOURCE_EXHAUSTED, LEAKAGE |
| compile | the frozen compiler accepts it | COMPILER_FAILURE |
| accepted | K*' + e accepts a program on all demonstrations | ENGINE_REJECTION |
| uses | the winning program is the compiled production (`uses_extension`) | ROUTING_FAILURE |
| replay | the accepted program reproduces every demonstration | ROUTING_FAILURE |
| attribution | direct execution of the winning AST equals the engine on every test input | ROUTING_FAILURE |
| prediction | a prediction exists for every test input | ROUTING_FAILURE |
| determinism | a second K*' + e run gives the same acceptance, program and predictions | ABSTAINED |
| loo | the adaptive leave-one-out under K*' passes on every fold: the held-out demonstration removed first, failure rebuilt, proposal, selection, compilation, installation and the same reasoner from scratch, the held-out output exact | LOO_FAILURE |
| unanimity | every member of the proposer's verified, behaviour-deduplicated pool predicts exactly the committed output on every test input | AMBIGUOUS_CANDIDATES |
| support | every region each block of e selects on each test input has a key the same block selected in at least two demonstrations | INSUFFICIENT_WITNESSES |

No gate reads a target or a held-out answer. When a gate fails, CORA's
prediction is not used and the native output stands.

## 9. The witness

For each task, scored by the blind evaluator:
- B: the native attempts do not solve the task (every test output matched by
  attempt 1 or 2) AND the task is not in the sealed 185.
- P: the proposer SELECTED an extension and it compiled.
- U: K*' + e accepted, the winner uses e, and direct execution equals the
  engine.
- L: the adaptive leave-one-out passed on every fold (not relaxed for small
  n).
- T: CORA activated and its committed prediction is exactly right on every
  test output.
- A: neither EXTENSION_REMOVED_ABLATION nor MATCHED_COMPUTE_CONTROL produces
  the right output on every test output.
- Per-witness integrity: determinism, unchanged baseline (the removed run
  equals the KSTAR_PRIME_WITHOUT_EXTENSION run in acceptance, program and
  predictions), replay, attribution, restoration.

A complete witness is all six legs plus integrity on an activated task.

## 10. Scoring and classes

Task outcome (first that applies): WRONG_ACTIVATION (activated, not exact);
BASELINE_ALREADY_SOLVES (native solves it in the run, or it is in the
sealed 185); ABLATION_FAILURE; INTEGRITY_FAILURE; CORRECT_CAUSAL_RESCUE (a
complete witness); HELDOUT_MISMATCH (not activated; K*' + e's unused
prediction wrong: a correct abstention); MISSED_RESCUE (not activated; that
prediction right); NO_CHANGE. Mechanism classes are section 8's, plus
RUN_ERROR. Errors are grouped by mechanism, never by task id.

Reported counts: genuine rescues, baseline solves retained, correct and
incorrect activations, abstentions, additional correct answers, additional
incorrect answers, lost solves, net score (system solved minus native
solved), control arms' correct outputs, per-stratum breakdowns, runtimes.

## 11. Primary gate and outcome ladder

First that applies:

| outcome | condition |
|---|---|
| PILOT_LEAKAGE | any isolation problem or proposer LEAKAGE_FAILURE |
| NO_VERDICT_DATASET | a pinned file's sha256 differs, the sealed set is not 185, or the predictions do not cover exactly the pilot keys |
| NO_VERDICT_RUN_ERROR | the reasoner did not finish, or RUN_ERROR on more than 10 percent of tasks |
| REAL_ARC_CAUSAL_WITNESS_ESTABLISHED | at least one complete witness |
| NO_REAL_ARC_WITNESS | otherwise |

Safety, reported with every outcome: SAFE when no native solve is lost,
incorrect activations do not exceed correct ones and the net score is not
negative; UNSAFE otherwise.

Licences: WITNESS_ESTABLISHED licenses bounded real-task development
(high-precision activation, preserved native solves, rescue of baseline
failures, selection ambiguity, execution cost) on data other than the pilot
tasks, then a final architecture freeze before ARC-1000; if UNSAFE, that
development starts with activation precision. NO_REAL_ARC_WITNESS licenses
no development claim; the mechanism counts name the blocker. The pilot's
held-out outcomes are never used to tune anything.

## 12. Static feasibility and N (rule fixed before the dry run)

Development dry run, reasoner only, under the isolation hook, never
scored: the CORA phase on all 60 development tasks, and the native phase on
the first 6 development keys (sorted) for engineering only.

READY requires: no isolation problem; no RUN_ERROR in either phase; the
native phase completes its 6 tasks; and at least one development task
reaches the compiled-and-installed stage (the loop is operable on real
tasks). Otherwise the block ends with the blocker recorded and no pilot is
frozen.

N: with a = activated development tasks and e = tasks reaching the installed
stage, N is the smallest allowed value (48, 72, 96, 120) with N x a / 60 >=
4, and 120 when a = 0 or no allowed value reaches 4.

Measured (2026-10-07, 675.7 s, `outputs/pilot_v1_dev/feasibility.json`):
isolation clean (8 logs, 0 refused accesses); CORA phase 60 of 60, native 6
of 6; one native RUN_ERROR (a library-install race between workers, fixed
after the run and covered by a test); installed stage reached by 0 of 60
(path class NO_PROPOSAL 60; proposer NO_PROPOSAL 59, K_ALREADY_SOLVES 1;
consistent single blocks on 13 of 60 tasks). READY fails on "loop
operable"; N would have been 120 (a = 0). Verdict: NOT READY, blocker
recorded, no pilot frozen.

## 13. Runtime and resource caps

Proposer 180 s per call (frozen); K*' 8 s per run (frozen); matched compute
24 to 240 s; native at the sealed caps (pipeline 150 s, GeoCat 120 s, object
105 s plus 7 x 45 + 30 s for frames); 4 workers per phase at the host's
normal load; a per-phase wall cap of 8 hours, past which workers are stopped
by exact pid and the run is resumable.

## 14. Run procedure (next session)

Launched once, detached (setsid nohup), by `scripts/pilot_v1_run.py pilot`;
resume only after a genuine interruption (start record present, marker
absent); a watcher runs the evaluator after the reasoner marker and the
terminal verifier after the evaluator marker. Administrative monitoring
only. After the result is sealed: exactly one read-only adversarial review
of that result. No sealed result is edited afterwards.

## 15. What is not claimed

Anything about ARC-AGI-2 evaluation tasks, scores above 185, generalization
beyond the pilot sample, self-improvement, semantic invention, or that the
engine distinguishes right from wrong extensions.

## 16. Disclosures

- PYTHONHASHSEED is 0 in both phases (the sealed runs did not fix it).
- The native baseline runs the five-flag v23 chain; learned generators
  (ARC_LEARNED_GENERATORS_DIR) are not loaded, as in the CORA-TTI
  full-engine solver; the deployed Kaggle notebook sets none of the five
  flags, so it runs below the sealed configuration (a separate finding).
- Native and K*' budgets are wall-clock; results can depend on host load.
  The B leg's sealed-record condition guards against a native flake
  creating a rescue.
- The proposer's grammar is the v1.8 constructive grammar (stacked region
  recolouring keyed on a region feature); tasks outside it end at
  NO_PROPOSAL by design.

## 17. Identities

None: the pilot was not frozen (section 12).
