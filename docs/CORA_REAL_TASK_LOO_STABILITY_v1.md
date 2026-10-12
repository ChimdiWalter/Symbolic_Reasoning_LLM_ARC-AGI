# Real-task adaptive LOO stability v1: protocol

Written 2026-10-12, before any diagnostic run (user directive "REAL-TASK
ADAPTIVE LOO STABILITY PROGRAM", started at a9e4577). DEVELOPMENT on the 60
training-development tasks only. Nothing here is a causal witness, a pilot
or a certified solve.

## 0. Invariant and lineage

The binding invariant of `docs/CORA_REAL_TASK_REACH_DEV_v1.md` section 0
holds unchanged. Input: the reach v1 measurement (frozen c8d8e3a, rows
60ddd04, record `records/REACH_V1_MEASURE_20261011.md`): 4 failure-
conditioned (FC) proposals, 4 installed, 1 accepted and used
(kf892487f1049), 0 of 14 rebuilt leave-one-out folds succeed, 0
activations. Reach v1's rows, record and manifest and pilot v2 (c1906ee,
manifest c93ec1db, FROZEN_NOT_RUN) are not edited. Pilot v2 pins the trees
cora_reach, cora_pilot, cora_pilot2, harness, geocat_arc, cora_arc2026,
src/reasoning_project and three TTI packages; this block adds files only
outside them (`cora_loo/`, new scripts, tests, docs, records, outputs and
logs) and re-checks both freezes after every commit.

## 1. Data boundary

Inputs: the development bundle `records/pilot_v1/dev_bundle.json`
(demonstrations and unlabelled test inputs of the 60 tasks), reach v1's
rows and instance files. Never read: the pilot v2 bundle or key map, the
488 candidates, the evaluation DEV, the HOLDOUT, any solutions file, Step B,
VDCG, E_transfer, the Lockbox. Every worker runs under the pilot isolation
hook with the development bundle as its only task input. Leave-one-out
holds out a DEMONSTRATION; no test output exists here and none is scored.
These 60 tasks are already exposed: results are development evidence.

## 2. Question

Why does the native engine accept the automatically constructed bbox_fill
extension on kf892487f1049 with four demonstrations but reject it in every
outer fold rebuilt from three, and what stops the other three proposals?
Every one of the 14 failed folds and the 3 full-data rejections gets an
observed mechanism, not a guess.

## 3. The instrument (observation only, `cora_loo/`)

Every engine run is the harness object layer (`run_object_task`, as reach
v1) with, at most, one extension installed by the reach v1 bridge, under:
- the v1.9 tracer (`cora_v19.v19_trace.traced`): every `induce_program`
  (the identity frame and each dihedral frame), the engine's own
  leave-one-out per fold (`loo_validate`: held-out index, subset size,
  the fold's result), the ranked candidate pool per context;
- a deadline spy on `inducer._check_deadline`: every `_BudgetExhausted`,
  with the context (top-level search or an inner fold) it occurred in;
- a substitution spy on the bridge's `detect_grow`: how often the installed
  relation replaced a `pattern` memorization;
- process CPU time and wall time, host load, the hard cap and where it hit.
No decision is changed: every spy returns its wrapped function's value and
is removed on exit; the bridge's own restoration check still applies.

## 4. Arms

Full data, per FC task (4): A_E = K + e_full on all demonstrations; A_K = K
alone; both under clock WALL and clock CPU1 (section 5).

Per outer fold (14 folds: demonstration i held out):
- B: the complete construction rebuilt from the remaining demonstrations
  (identity-frame extraction, `construct.propose`, first proposal, K + e_i),
  as reach v1, traced; under WALL and under CPU1 (extraction and engine).
- C (FORENSIC ONLY): K + e_full on the remaining demonstrations. e_full was
  built with the held-out demonstration, so C never counts as an adaptive
  leave-one-out witness or a deployment result; it separates proposal
  instability from engine acceptance instability. When B's e_i equals
  e_full, C is B's own engine run (recorded once, marked C = B).
- D: K alone on the remaining demonstrations.
- E: K alone on the remaining demonstrations at matched compute, budget
  clamp(B's extraction + construction + engine seconds, 90, 270), WALL.
- Evidence analysis (no engine): `construct.propose` on reach v1's
  full-data instances restricted to the remaining demonstrations; per
  segmentation variant: instances, demonstrations, settings reproducing
  all, whether e_full reproduces them; and whether each fold candidate
  reproduces the held-out demonstration's own instances.
Held-out exactness is recorded for every engine arm (the held-out
demonstration's output; no test output).

## 5. Clock conditions

- WALL: reach v1's condition (wall-clock budgets, hard cap budget + 360 s).
- CPU1: the engine's deadlines read process CPU time (v1.9 tracer clock
  CPU1), so host contention cannot move them; budgets unchanged in CPU
  seconds; wall hard cap 3,600 s (diagnostic only).
CPU1 is the permitted low-contention condition: Step B and other jobs keep
running. A difference between WALL and CPU1 measures contention, not a
larger budget; no budget is increased in either.

## 6. Classification (fixed before the run)

Per outer fold, first that applies:
- H5 RESOURCE: under WALL the decisive run hit the hard cap or a
  `_BudgetExhausted` in the top-level search or an inner fold, and under
  CPU1 the same arm accepts or reaches a later stage. Sub-label
  NESTED_DEADLINE when the exhausted deadline was an inner fold's.
- H1 IDENTIFIABILITY: B proposes nothing, and the restricted full-data
  instances also propose nothing (support below 2 demonstrations, or no
  single setting).
- H3 EVIDENCE_INSTABILITY: B proposes nothing, but the restricted full-data
  instances would propose (the engine memorizes differently on fewer
  demonstrations); or B and C reach train-exactness on different
  segmentation variants or selector structures.
- H4 ORDERING: B's e_i differs from e_full, e_full is among the fold's
  proposals (indistinguishable on the remaining demonstrations by
  construction) and the held-out demonstration's instances distinguish
  them.
- H2 RE-INDUCTION: e_i equals e_full (or C), the engine finds a
  train-exact program on the remaining demonstrations, and its own
  leave-one-out rejects it without a deadline (an inner fold re-induces a
  wrong program or none).
- H6 INSUFFICIENT_RELATION: with e installed no train-exact program exists
  on the remaining demonstrations and the near-solve's residual holds
  deltas no installed or native rule explains.
- UNRESOLVED: none applies; recorded with the evidence.
The same rules classify the full-data rejections of A_E. Frequencies are
reported per hypothesis; folds are never pooled into one cause.

## 7. Resource accounting

Per run: wall seconds, CPU seconds, CPU share, hypotheses enumerated,
candidates in the top pool, budget exhaustions by context, frames run,
whether and where the hard cap hit. A budget increase is never a repair
here; WALL against CPU1 is the only comparison made.

## 8. Novelty labels

Reach v1's separation legs are re-labelled for this block's reports (the
reach v1 record is not edited):
- GROW_SUBLANGUAGE_ABSENT: the engine's own `detect_grow` reproduces none
  of the instances with any native growth mode (it falls back to the
  constant pattern); this is a complete check within the growth-mode
  vocabulary, for these instances only.
- NOT_A_CACHE: the extension's body holds scalar parameters only.
- SEARCH_INACCESSIBLE_WITHIN_BUDGET: K alone, at the tested budgets and
  clocks (WALL, CPU1, matched compute), accepts no program.
- BOUNDED_SEMANTIC_EXTENSION_CERTIFIED would need a complete, declared,
  independently verified bounded semantic-absence procedure over the whole
  native engine (every phase: object programs, composition, pixel rules,
  symmetry, counting, generative, expression); none exists here, so the
  label is not used, and the weaker labels above are the claim.

## 9. Repair licence

The diagnosis record is written and committed before any repair code. If
it establishes a generic defect, exactly one bounded repair is proposed,
implemented in a new versioned package outside the pinned trees, tested
(unit and mutation tests) and described in an amendment to this protocol
before the development recheck. Forbidden: task-specific branches,
memorized outputs, supplied programs, forced acceptance, disabled native
verification, a lowered leave-one-out standard, a full-data extension
treated as rebuilt inside a fold, more than one component changed. If the
reduced demonstrations cannot identify a relation, that is the finding.

## 10. Development recheck and screen

Only after section 9: one run on the same 60 tasks, the original reach v1
mechanism and its successor as two arms of one run, reporting proposals,
installations, acceptances, use, replay, adaptive leave-one-out, support,
abstentions, false acceptances (accepted e rejected by the held-out
demonstration), restoration, compute, matched controls and conditions 1 to
5. SCREEN for any new pilot (fixed now): at least one development task with
conditions 1 to 5 together (1 K fails; 2 the repair is generated from
failure evidence; 3 a canonical executable extension installed; 4 the
novelty claim at the level section 8 supports; 5 complete adaptive
leave-one-out), with no answer access, no change to frozen native
behaviour (K alone unchanged), exact attribution, restoration and matched
controls recorded; more than one structurally distinct success preferred.
If the screen fails, no pilot is designed and the 488 candidates stay
untouched.

## 11. Run procedure

One coordinator (`scripts/loo_v1_run.py diagnose`), 4 workers, units = 4
full-data units and 14 fold units, atomic rows
`outputs/loo_v1/diagnose_rows.jsonl`, start record (pid, start ticks, pgid,
boot id, head), freeze check against `outputs/loo_v1/diagnose_manifest.json`,
resume only after a genuine interruption (2 at most), marker
`logs/loo_v1/DIAGNOSE_0_DONE`, a detached checkpointer committing rows every
15 minutes. Run once.
