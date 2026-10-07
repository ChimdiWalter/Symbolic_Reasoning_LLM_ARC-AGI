# Item-2 v1.9: prospective engine-stability result

**ENGINE_STABILITY_REPAIR_ACCEPTED** (G1, G2, G3 and G4 all pass), run once on
2026-10-07 on new synthetic data (seeds 880,000,000 + 100k). Independent
terminal verification: all 28 verifier checks pass, and a separate
recomputation from the raw rows agrees with the report on every quantity.

Claim: LEVEL 2, SYNTHETIC DOMAIN ONLY, under the frozen witness-support regime
(every key of the extension witnessed at least twice in each run; on this
corpus every task's smallest key witness count on the seven pairs was 3 or
more). Not a real ARC result. The real ARC causal pilot is licensed as the
next block, to be designed and frozen under its own protocol.

## Identities

| object | value |
|---|---|
| re-frozen commit (after erratum 01) | 44a64f0 |
| manifest | `outputs/tti/engine_stability_v19_manifest.json`, sha256 `528981ddd2827aaf822e43e9e52655cbbed0b42f51778849a319c61021307e0b` |
| protocol | `docs/CORA_TTI_ENGINE_STABILITY_AUDIT_v1.9.md`, sha256 `8cec8e37...` (pinned) |
| K* / K*' (K* + K*-4) | `b009a9fb...` / `e4672bfa...` |
| report | `outputs/tti/v19_prospective_report.json`, sha256 `987ab9ea074ac82bf72cc70ac109168534c61693e813656e83880783c4ddaf6c` |
| rows | `outputs/tti/v19_prospective_rows.jsonl`, sha256 `aad86def227a6c50e4d1c7e0e7e2819654385c40286e35102004bcf0985e8e48` |
| task file | `outputs/tti/v19_prospective_tasks.json`, sha256 `59a9c7c7432099660b7e8c846f975ed9f025ab3a42580cde179b52d3ee39c043` |
| verifier | `logs/v19/verify_prospective.py` -> `logs/v19/verify_prospective.json` (sha256 `4cabfef5...`) |
| recomputation | `logs/v19/recompute_prospective.py` -> `logs/v19/recompute_prospective.json` |

## Run

- Launched once at 2026-10-07T18:07:49Z (start record 18:07:57Z) with
  `setsid nohup .venv_arc2026/bin/python scripts/v19_prospective.py`;
  coordinator pid 1360853 (own session and group, start ticks 61938419),
  workers 1362497, 1362512, 1362513, 1362514; boot
  5c543236-c905-416e-9e7f-af441c8fc4b5; HEAD df6340c; load 50 at launch and
  44 at the end on 24 CPUs. Launch record `logs/v19/prospective_launch.json`.
- 3,159.8 s (52.7 minutes). Marker at 19:01:05Z; the detached watcher (v2,
  pid 1371476, installed at 18:13:28Z on the user's instruction to run even
  when interrupted) ran the verifier (exit 0, 19:01:56Z) and removed its
  `@reboot` hook.
- No resume, no interruption, worker exit codes 0, 0, 0, 0, no unparsable
  row, no duplicate row, no error row, no reported-control failure.
  Administrative monitoring only during the run.

## Freeze and corpus

- Before launch and after the marker: v1.9 and v1.8 `freeze_problems()`
  return []; status FROZEN_AFTER_ERRATUM_01_NOT_PROSPECTIVELY_TESTED; K* and
  K*' identities unchanged.
- 30 rows, indices 0..29, 30 distinct seeds and 30 distinct target digests,
  all in the 880M range, none in the 3,901 exclusion digests, equal to the
  task file and to the corpus law re-derived by the verifier. No leakage in
  any arm or fold.
- Families (1,1) 15, (0,1) 9, (1,0) 6. Selection level of e: MDL 23,
  VERIFICATION_UNIQUE 3, D 2, P0 2.

## G1, failure specificity: PASS

| control | main useful | control useful | main only | control only | p (one-sided) |
|---|---|---|---|---|---|
| SHUFFLED_FRONTIER | 30 | 24 | 6 | 0 | 0.0156 |
| BLIND | 30 | 22 | 8 | 0 | 0.0039 |

## G2, end to end: PASS

27 of 30 complete K*' witnesses (19 required); 12 of 30 under K*.

| leg | K*' | K* |
|---|---|---|
| B (alone not accepted) | 30 | 30 |
| P (selected) | 30 | 30 |
| U (winner uses e) | 30 | 24 |
| L (adaptive leave-one-out, every fold) | 27 | 12 |
| T (held-out pair exact) | 30 | 24 |
| A (K* at 3x budget does not reproduce) | 30 | 30 |

## G3, leave-one-out stability gain: PASS

Adaptive leave-one-out (proposal rebuilt in every fold) passed on 27 tasks
under K*' and 12 under K*: 15 tasks pass only under K*', 0 only under K*
(net 15 against 6 required; one-sided p = 3.05e-5). Folds SUCCESS 207 of 210
against 133. Pairing mismatches (fold selection or production differing
between the two logics): 0 of 210.

## G4, safety: PASS

| check | result |
|---|---|
| inert: K*' alone equals K* alone in decisions (events differed on 0 tasks) | pass |
| no regression of seven-pair runs accepted with the held-out pair exact | pass |
| no regression of adaptive folds that succeeded under K* | pass |
| every K*'-accepted program replays its training pairs | pass |
| attribution: winner uses e and direct execution equals the engine | pass |
| restoration: no K*-4 patch survives a run | pass |
| precision of K*' certified outputs >= 0.95: 237 of 239 = 0.992 | pass |
| K*' precision >= K* precision - 0.02: 0.992 against 1.000 (157 of 157) | pass |
| marginal precision: added wrong <= 0.05 x added correct: 2 against 80 | pass |

Wrong certified outputs: K* 0 (seven-pair runs 0, folds 0); K*' 2 (seven-pair
runs 0, folds 2). Wilson 95 percent lower bounds: K*' 0.970, K* 0.976.

## Reported, not gating

- Seven-pair wrong-extension trials (pool candidates and control selections
  that verify the seven pairs but mispredict the held-out pair): 5 trials
  (4 pool, 1 BLIND); accepted with the held-out pair wrong: K* 1, K*' 5.
- Four-demonstration control (train on pairs 0-3, evaluate on 4-6 and the
  held-out pair): 50 trials, 22 right (selections) and 28 wrong (pool
  candidates, from 13 tasks). True acceptances K* 5 of 22, K*' 21 of 22;
  false acceptances K* 9 of 28, K*' 28 of 28. Discrimination (right minus
  wrong acceptance rate): K* -0.09, K*' -0.05. The pre-registered expectation
  held: K*' accepted at least as many wrong extensions as K*; no
  discrimination was detected in either logic.
- Witness-support strata (smallest witness count of e's keys on the seven
  pairs): 3 in 7 tasks (K*' witnesses 6, K* 0; adaptive leave-one-out 6
  against 0); 4 or more in 23 tasks (21 against 12; 21 against 12).
- By family: (1,1) 14 of 15 K*' witnesses against 5; (0,1) 9 of 9 against
  6; (1,0) 4 of 6 against 1.

## Disclosures that bound the claim (erratum 01, preserved)

- K*-4 lowers the effective evidence requirement for installed extensions
  from three witnesses per key to two, and gives a verified installed
  extension priority in every ranking.
- K*' accepted every installed extension it was given in development; here
  it accepted all 5 seven-pair wrong extensions and all 28 four-pair wrong
  extensions. The engine does not discriminate right from wrong installed
  extensions; the system's correctness rests on the proposer's selection
  and on the held-out and adaptive leave-one-out checks, which held:
  precision 0.992 over what the system certified.
- Much of the synthetic gain follows from the corpus witness-count law
  (every target key has at least three witnesses by construction; K*' needs
  two of six): the 3-witness stratum went from 0 to 6 witnesses.
- The LEVEL 2 claim is synthetic and limited to that witness-support regime.

## What this licenses and what it does not

- Licensed: designing and freezing the same-reasoner real ARC causal pilot,
  under its own protocol, to seek the first genuine real-task
  B/P/U/L/T/A witness. On real tasks (two to five demonstrations) the
  engine will certify any verified, leave-one-out-stable extension the
  proposer installs, so the pilot's protocol must carry the safety burden
  (selection quality, held-out checks, abstention).
- Not shown and not claimed: any real ARC improvement, any change to the
  sealed 185 of 1000, >200 of 1000, ARC-AGI-2 evaluation success,
  self-improvement, or general ARC invention.
- ARC-1000, the 60 DEV and the 60 HOLDOUT stay blocked.
