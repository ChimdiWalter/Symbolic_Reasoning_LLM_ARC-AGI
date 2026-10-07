# Item-2 v1.9: the K*-4 repair, development result (DEVELOPMENT ONLY)

Repair K*-4, installed-extension re-induction (`cora_v19/v19_repair.py`,
protocol section 14): while an extension is installed, the installed concept
is fitted with every consistent witness and ranks first in every ranking of
the run; the engine's gate is unchanged; with nothing installed every patched
function returns the native value. Development data: the 30 tasks of the
diagnosis prefix (seeds 870,000,000 + 100k), the same byte-identical e.

## Ablation (protocol section 15, pre-registered at 1e5937e; result af4b7c1)

Pipeline `logs/v19/run_repair_dev.sh` (pid 1546874, 4 workers, launched
2026-10-06T22:53:57Z, phase 2 done 2026-10-07T00:21:44Z). Report
`outputs/tti/v19_repair_dev_report.json`; rows
`outputs/tti/v19_repair_dev_rows.jsonl`. No run error.

| measure | K* (old logic) | K*' (K* + K*-4) |
|---|---|---|
| complete synthetic witnesses (B, P, U, L, T, A) | 12 of 30 | 26 of 30 |
| FULL accepted, winner uses e, held-out exact | 27 of 30 | 30 of 30 |
| same-e six-pair folds accepted | 134 of 210 | 210 of 210 |
| adaptive leave-one-out passed (proposal rebuilt per fold) | 12 of 30 | 26 of 30 |
| adaptive leave-one-out folds SUCCESS | 132 of 210 | 206 of 210 |
| D (K*' alone, 8 s) / E (K*' alone, 24 s) accepted | | 0 / 0 |

- Rescues (directive section 12: A fails, old witness incomplete, C accepted
  using e with the held-out pair exact, D not accepted, E does not reproduce
  the held-out output, K*' adaptive leave-one-out passes): 14 (category A 12
  of 15, R 2 of 3); category B 12 of 12 stay witnesses.
- The four K*' tasks without a witness: two have a K_ALREADY_SOLVES fold
  (K solves the six pairs; unchanged by the repair); two have a wrong
  certified fold (below).
- No residual K*' rejection of the installed extension (FULL or same-e fold).
- Clause by clause, on the 18 category A and R tasks: fitting alone fully
  stable 9, ranking alone 7, both 18; neither clause is a repair by itself.

## Safety gates (protocol section 15)

| gate | checked | result |
|---|---|---|
| 1 inertness: D equals A in acceptance, program, events | 30 | FAILED on 1 (events only, see below) |
| 2 no regression: every old-accepted run accepted with the identical program | 161 | pass |
| 3 every K*'-accepted program replays its training pairs | 240 | pass |
| 4 attribution: winner uses e and its direct execution equals the engine's prediction | 240 | pass |
| 5 no residue (K* snapshot, no K*-4 patch after a run) | 300 | pass |
| 6 no protected-data access | | pass |
| 7 fresh-process reproduction of C (FULL and same-e folds) | 240 | pass |
| 8 false acceptances of e_wrong do not increase | 0 trials | vacuous |

Gate 1. On task 3 both D and A reject with no program; D also stored a
near-solve. `logs/v19/inert_probe.py` repeated that task's K* alone run
three times without the repair module: the near-solve appeared once in
three, decisions identical in all six runs. The event records how far the
search got inside the 8 s wall-clock budget: base-engine timing
variability, not a K*-4 effect. The pre-registered gate is still reported
as failed; the prospective inertness check compares decisions and reports
events (protocol sections 15b and 16).

Gate 8 had no trial: on these tasks no verified candidate mispredicts the
held-out pair with seven demonstrations.

## False-acceptance measurements (protocol section 15a)

| measurement | right extensions accepted | wrong extensions accepted |
|---|---|---|
| seven pairs, wider rule (pool, transplant, BLIND) | (none needed) | 0 trials in 30 tasks |
| four pairs, K* (old) | 8 of 24 | 6 of 19 |
| four pairs, K*' | 24 of 24 | 19 of 19 |
| four pairs, fitting clause only | 13 of 24 | 9 of 19 |
| four pairs, ranking clause only | 17 of 24 | 10 of 19 |

Rows: `outputs/tti/v19_falseaccept_dev_rows.jsonl`,
`outputs/tti/v19_falseaccept_reduced_dev_rows.jsonl`,
`outputs/tti/v19_clause_safety_dev_rows.jsonl` (each script committed
before it ran: 8c668f8, 6924756).

Reading: under four demonstrations the engine's own gate does not
discriminate right from wrong installed extensions in any logic. The old
logic accepts about a third of each; K*' accepts every verified,
leave-one-out-stable installed extension. In the system's own pipeline
(the proposer's selection, six and seven pairs) wrong certified outputs
are rare in both logics: adaptive leave-one-out folds certified with a
wrong held-out prediction, K* 1 of 133 certified (task 17 fold 3, accepted
by both), K*' 2 of 208 (also task 18 fold 0, a D selection the old logic
happened to reject). Precision over all certified outputs: K* 159 of 160,
K*' 236 of 238.

Consequence for the prospective gate (protocol sections 15a and 16): the
safety gate is precision over everything K*' certifies (at least 0.95,
and at most 0.02 below K*), with every count of wrong certified outputs
reported; the four-pair control runs prospectively and is reported with
its pre-registered expectation, not gated. For real ARC tasks (two to five
demonstrations) this means K*' will certify whatever verified,
leave-one-out-stable extension the proposer installs; correctness rests on
the proposer's selection and the held-out checks.

## Module move

The v1.9 modules were first written into `cora_arc2026/`, which changed the
tree digest that the v1.8 manifest pins. After the development runs they
were moved to `cora_v19/` (df851c7): `v19_trace.py` and `v19_repair.py`
byte-identical, `v19_audit.py` changed in its one import line. Afterwards
the v1.8 `freeze_problems()` returns [] again and K* is b009a9fb. (The v1.7
manifest's pin of the same tree has not matched since v1.8 added its
proposer; v1.7 is terminal.) The diagnosis ran at 81065a3 and the ablation
at 1e5937e, both with the modules under `cora_arc2026/`.

## What this shows and does not show

- Shown on development data: K*-4 removes the diagnosed rejections (210 of
  210 same-e folds accepted against 134), more than doubles complete
  witnesses (26 against 12) and adaptive leave-one-out passes (26 against
  12), changes no old-accepted program, keeps K* alone's decisions, and
  keeps precision over certified outputs at 0.99.
- Not shown: anything prospective; anything on real ARC data; that the
  engine can discriminate wrong installed extensions (it cannot, in either
  logic, when demonstrations are scarce).
