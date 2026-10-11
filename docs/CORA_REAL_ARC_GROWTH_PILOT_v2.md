# CORA real ARC growth-repair causal pilot v2: protocol

Status: DRAFT, NOT FROZEN. Drafted 2026-10-11 while the reach v1
development measurement was running, before its outcome was read. It is
frozen (section 17) only if that measurement passes the readiness rule of
pilot v1 section 12, after its result is recorded; it is never run without
an explicit go-ahead.

## 1. Question and claim ceiling

Can the reach v1 growth-repair loop (failure evidence from the native object
engine's own memorized growth on the demonstrations; construction from a
frozen generic grammar without an oracle; a canonical extension; reversible
installation into the same native engine; its unchanged acceptance gate;
adaptive leave-one-out rebuilt from scratch; train-only activation) produce
at least one independently scored rescue of a real ARC-AGI-2 training task
that the frozen native reasoner fails, with pilot v1's full B/P/U/L/T/A
witness? And does such a rescue also meet the binding invariant
(docs/CORA_REAL_TASK_REACH_DEV_v1.md section 0, conditions 1 to 8): bounded
semantic separation from K and evidence that the failure conditioning
mattered?

Claim ceiling, as pilot v1 section 1: a small sample from the public
training split, on which the base engine was developed. A positive result
licenses bounded real-task development, nothing more: no ARC-AGI-2
performance or generalization claim, no change to the sealed 185 of 1,000,
no evaluation claim, no claim that the engine discriminates right from
wrong extensions. The growth grammar is human-designed generic machinery
(disclosed): an invention witness means that CORA, from a failure of K and
without the answer, constructed an instance of that machinery that K did not
express within the bounds tested, that was necessary for the rescue, and
that demonstration-only and shuffled-failure constructions did not match.

## 2. Lineage

- Pilot v1 (`docs/CORA_REAL_ARC_CAUSAL_PILOT_v1.md`): NOT FROZEN; blocker
  proposer reach (0 of 60 development tasks at the installed stage). Kept
  unchanged and reused: data (section 3), selection and its frozen order
  (4d3c29b), the bundle format and opaque keys, the isolation hook, the
  native entry, the deployable-output rule, the evaluator's pinned loaders
  and scoring rules, the outcome ladder, the safety rule, the N rule.
- Replaced: pilot v1's reasoner (v1.8 proposer, v1.7 compiler, K*'), built
  for stacked region recolouring, by the reach v1 mechanism.
- Reach v1 (`docs/CORA_REAL_TASK_REACH_DEV_v1.md` sections 4.1 and 5.1;
  frozen c8d8e3a; record `records/REACH_V1_MEASURE_20261011.md`): the
  per-task policy `cora_reach.measure.run_task` is used here unchanged.
  Its development result and readiness verdict are stated in section 12.

## 3. Data

As pilot v1 section 3: the ARC-AGI-2 public training split (1,000 tasks;
challenges sha256 `779eaba8...`, solutions sha256 `9f07a38b...`), the sealed
v23 records read by the evaluator only (union exactly 185). Not used:
synthetic tasks, the evaluation split, the 60 DEV, the 60 HOLDOUT, Step B,
VDCG, E_transfer, the Lockbox.

## 4. Task selection

Pilot v1 section 4 unchanged: the frozen selection
(`records/pilot_v1/selection.json`): 548 of 1,000 in scope; the 60
development tasks are excluded; per stratum the first quota tasks of the
frozen order outside the development set, quota = N x (3, 2, 1) / 6 for
(n3, n4, n5p). The pool (488 candidates: n3 356, n4 109, n5p 23) has not been
run, read for outcomes or scored by anyone. `scripts/pilot_v2_select.py N`
recomputes the selection from the pinned challenges file, refuses on any
difference, and writes `records/pilot_v2/pilot_bundle.json` (opaque keys,
demonstrations and test inputs only) and the evaluator-only
`records/pilot_v2_evaluator/pilot_keymap.json` (fresh salt). N: section 12.

## 5. Processes and isolation

Pilot v1 section 5 unchanged: reasoner workers under `cora_pilot.isolation`
(any refused access, missing log or forbidden directory is PILOT_LEAKAGE);
the coordinator composes and git-commits every prediction, row, failure
evidence file and isolation log before anything reads a target; the blind
evaluator is a separate process that verifies the commit byte for byte and
alone reads the key map, the pinned solutions and the sealed record.

## 6. The same-reasoner loop, per task

A. NATIVE_BASELINE: `cora_pilot.native.run_native` (the sealed per-task
   entry, five chain flags, frozen library and learned verbs, solution
   None), unchanged.
B. FAILURE EVIDENCE (phase `instances`): `cora_pilot2.reasoner.run_instances`,
   one identity-frame native induction on the task's demonstrations under
   the observation-only wrapper `cora_reach.instances` (budget 90 s, hard cap
   450 s, as the measurement's leave-one-out folds); every pattern-fallback
   memorization is written to `outputs/pilot_v2/instances/<key>.json`.
   Disclosed difference from the development run: instances2 had no hard
   cap.
C to J (phase `cora`): `cora_reach.measure.run_task`, frozen, unchanged:
   the FAILURE_CONDITIONED construction, the DEMONSTRATION_ONLY and
   SHUFFLED_FAILURE controls (donor: the next pilot key in sorted order,
   cyclic), KALONE, the gates in their frozen order, the adaptive
   leave-one-out rebuilt from scratch in every fold, the pool's unanimity,
   the growth support contract, REMOVED, MATCHED_COMPUTE and the bounded
   separation test (reach v1 section 5.1).

## 7. Arms and the deployable output

| arm | what runs |
|---|---|
| NATIVE_BASELINE | A |
| KALONE | the harness object layer with nothing installed, before the loop |
| CORA_FAILURE_CONDITIONED | B, then the first FC proposal installed (K + e) and the gates |
| DEMONSTRATION_ONLY_CONTROL | the same grammar on the demonstrations alone, first proposal installed in the same reasoner (no leave-one-out) |
| SHUFFLED_FAILURE_CONTROL | the construction on the donor's failure evidence, installed in the same reasoner |
| EXTENSION_REMOVED_ABLATION | KALONE's call again after the loop |
| MATCHED_COMPUTE_CONTROL | K at budget clamp(extraction + construction + K + e seconds, 90, 270) |

Deployable output, pilot v1 section 7 unchanged: native attempts; an
activated CORA prediction takes attempt 2 when native has an attempt 1 for
that test input, attempt 1 otherwise; native attempt 1 is never displaced.

## 8. Activation and abstention (train-only)

The gates of `run_task` in pilot v1's frozen order (compile, accepted, uses,
replay, attribution, prediction, determinism, loo, unanimity, support),
with the growth support contract of reach v1 section 5.1 in place of the
region-key rule. CORA activates only when every gate holds; otherwise its
prediction is not used and the native output stands. No gate reads a
target or a held-out answer.

## 9. The witnesses

For each task, scored by the blind evaluator (`cora_pilot2.evaluator`):
- B: the native attempts do not solve the task and it is not in the sealed
  185.
- P: the failure-conditioned construction proposed an extension and it
  compiled.
- U: K + e accepted, the winner uses e, and direct execution equals the
  engine.
- L: the adaptive leave-one-out passed on every fold.
- T: CORA activated and its committed prediction is exactly right on every
  test output.
- A: neither EXTENSION_REMOVED_ABLATION nor MATCHED_COMPUTE_CONTROL produces
  the right output on every test output.
- Integrity: determinism; REMOVED equal to KALONE in acceptance, program and
  predictions; replay; attribution; engine state restored.
- S: the bounded semantic separation holds (not a renaming of a native
  growth mode, not a cache, not a composition K accepts within these
  budgets).
- F: neither control, installed in the same reasoner, produces the right
  output on every test output (a control without a proposal counts as not
  right).

CAUSAL WITNESS: an activated task with B, P, U, L, T, A and integrity
(pilot v1's complete witness). INVENTION WITNESS: a causal witness with S
and F. Mapping to the invariant: 1 = B with KALONE and REMOVED failing; 2 = P
from the failure trace (the isolation hook guarantees no answer); 3 = P's
compilation and U's installation; 4 = S; 5 = L; 6 = T; 7 = U and A; 8 = F.

## 10. Scoring and classes

Pilot v1 section 10 unchanged (task outcomes WRONG_ACTIVATION,
BASELINE_ALREADY_SOLVES, ABLATION_FAILURE, INTEGRITY_FAILURE,
CORRECT_CAUSAL_RESCUE, HELDOUT_MISMATCH, MISSED_RESCUE, NO_CHANGE; mechanism
classes = path classes), plus the invention witnesses, the per-leg counts
and the failure-conditioned arm's correct outputs beside each control's.

## 11. Primary gate and outcome ladder

First that applies:

| outcome | condition |
|---|---|
| PILOT_LEAKAGE | any isolation problem |
| NO_VERDICT_DATASET | a pinned file's sha256 differs, the sealed set is not 185, or the predictions do not cover exactly the pilot keys |
| NO_VERDICT_RUN_ERROR | the reasoner did not finish, or RUN_ERROR on more than 10 percent of tasks |
| REAL_ARC_INVENTION_WITNESS_ESTABLISHED | at least one invention witness |
| REAL_ARC_CAUSAL_WITNESS_ESTABLISHED | at least one causal witness, none with S and F |
| NO_REAL_ARC_WITNESS | otherwise |

Safety, reported with every outcome (pilot v1): SAFE when no native solve is
lost, incorrect activations do not exceed correct ones and the net score is
not negative; UNSAFE otherwise. Licences: pilot v1 section 11; an invention
witness additionally licenses the statement in section 1, bounded as there.
The pilot's held-out outcomes are never used to tune anything.

## 12. N and the development result

The rule of pilot v1 section 12, unchanged: with a = activated development
tasks of the reach v1 measurement, N is the smallest allowed value (48, 72,
96, 120) with N x a / 60 >= 4, and 120 when a = 0 or no allowed value
reaches 4. Development result, readiness verdict, a and N: to be written
here from `records/REACH_V1_MEASURE_20261011.md` before the freeze.

## 13. Runtime and resource caps

Native at the sealed caps (pipeline 150 s, GeoCat 120 s, object 105 s plus
7 x 45 + 30 s for frames); extraction 90 s under a 450 s hard cap; every
object-layer run 90 s under 450 s; matched compute 90 to 270 s under
budget + 360 s; 4 workers per phase at the host's normal load (recorded);
a per-phase wall cap of 8 hours, past which workers are stopped by exact
pid and the run is resumable.

## 14. Run procedure (after the freeze, on an explicit go-ahead only)

Launched once, detached: `setsid nohup .venv_arc2026/bin/python
scripts/pilot_v2_run.py pilot > logs/pilot_v2/coordinator.log 2>&1 < /dev/null &`,
then `setsid nohup bash scripts/pilot_v2_watch.sh <coordinator pid> > /dev/null 2>&1 &`.
Phases native, instances, cora; composition; commit before any target is
read; marker `logs/PILOT_V2_REASONER_DONE`. The watcher then runs
`scripts/pilot_v2_evaluate.py` (report `outputs/pilot_v2/pilot_report.json`,
marker `logs/PILOT_V2_DONE`) and `scripts/pilot_v2_verify.py` (independent
scoring). Resume only after a genuine interruption (start record, no marker,
no live recorded worker; at most 2). Administrative monitoring only. After
the result is sealed: exactly one read-only adversarial review. No sealed
result is edited afterwards.

## 15. What is not claimed

Anything about ARC-AGI-2 evaluation tasks, scores above 185, generalization
beyond the pilot sample, durable learning (Step B's question), self-
improvement, semantic invention beyond section 1's bounded statement, or
that the engine distinguishes right from wrong extensions.

## 16. Disclosures

- PYTHONHASHSEED is 0 in every phase (the sealed runs did not fix it).
- The growth grammar (nine families, 210 settings) and its limits were
  fixed after the development census and coverage (reach v1 section 4.1);
  empty_square was added after a 6-task coverage smoke. Human-designed
  generic machinery, not an invented capability in itself.
- The extension's colour comes from the engine's own colour expressions.
- KALONE, REMOVED and MATCHED are the object layer, not the full harness;
  NATIVE_BASELINE is the full harness.
- Budgets are wall-clock; results can depend on host load (Step B's 20
  workers share the host). The B leg's sealed-record condition guards
  against a native flake creating a rescue; the determinism gate guards
  activation.
- Separation leg iii is bounded by K's budgets; it is not a proof of
  inexpressibility.
- The growth support contract is new (reach v1 section 5.1).
- Phase B has a hard cap; the development extraction (instances2) had none.

## 17. Identities

None: the pilot is not frozen.
