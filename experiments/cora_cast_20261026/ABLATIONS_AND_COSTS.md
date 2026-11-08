# Ablations, costs and independent score reproduction

All numbers come from saved decision records and separate-scorer outputs (`results/tables.md` regenerates the
per-arm tables with `python -m cast.tables`). Per-query pass@2 / task-mean / strict are reported in the module reports;
ARC_eval_dev has 120 tasks and 172 queries.

## Budget actually used (shared ledger rows with family CAST-*; `python -m cast.paths`)

| run (ledger id) | what | CPU-h | GPU-h |
|---|---|---|---|
| cast_m3_exhaustive_tests_v0 | exhaustive contract tests (21 passed) | 0.249 | 0 |
| cast_m3_contract_audit_v2 | duplicate audit, stopped after 29 s | 0.008 | 0 |
| cast_foreground_dev_20261027a | foreground development and smoke runs (estimate, rounded up) | 0.150 | 0 |
| cast_chain_v1 | contract audit + tests, M4 pipeline, M1 pipeline | 0.912 | 0 |
| cast_chain_v2 | M2 screens | 0.024 | 0 |
| cast_chain_v3 | M6 screens, M4/M5 variants, M1 key ablation | 0.569 | 0 |
| cast_chain_v4b | contract checks of the M1/M2/M6 operators, M3 screen | 1.207 | 0 |
| cast_chain_v5 | re-checks with samplers, final tests, report | 0.234 | 0 |
| cast_foreground_dev_20261027b | post-chain evaluation-side steps (estimate) | 0.050 | 0 |
| **total** | | **3.40** | **0** |

No GPU was used: the only trained module (the M1 ranker) is a logistic regression trained on CPU in seconds, and no
backbone or language model is in the loop. Wall time per chain is in each `runs/<id>/EXIT.json`. Failed and stopped
runs are in the ledger (two queued jobs cancelled before they ran, one duplicate stopped after 29 s).

## Mechanism ablations (equal budgets inside each comparison)

| module | full mechanism | control | result on unselected source cohorts | result on ARC_eval_dev |
|---|---|---|---|---|
| M1 | bind_fixed (executable binding, table re-read per input) | frozen_table (no executable binding) | generated held-out 120/120 vs 0/120; real 0/182 vs 1/182 | 0 vs 0 |
| M1 | bind_fixed | bind_shuffled (shuffled key/value) | 120/120 vs 0/120 (generated) | 0 vs 0 |
| M1 | bind_fixed | L0_only (no role module) | 120/120 vs 0/120 (generated); real 0 vs 3 | 0 vs 0 |
| M1 | bind_learned (trained ranker) | bind_fixed / bind_random | same accuracy; first fit at 5 vs 14 / 6 executions; 3.5x CPU | 0 vs 0 |
| M2 | rewrite_joint | rewrite_true_guard (no guards) | 10 vs 3 of 176 tasks (+7 / -0, exact McNemar p = 0.016) | 1 task vs 0 |
| M2 | rewrite_joint | rewrite_fixed_view (one representation) | 10 vs 7 (+3 / -0) | 1 vs 0 |
| M2 | rewrite_joint | L0_only | 10 vs 3 (+9 / -2: different tasks) | 1 vs 0 |
| M3 | contract-first | exact execution (same order) | identical fit sets everywhere; executions: M4 260 vs 9,260, M1 8-13x fewer; CPU lower for symmetry completion, higher for cheap bindings | identical |
| M3 | fwd / fwdbwd / typed / hint / equal-compute depth 3 | exact | at the same execution budget fwd answers 37 vs 29 of 60 generated queries, 5 vs 5 (CAST_select), 0 vs 0 (holdout); 0 lost; 28-36x fewer executions; 0.65x the CPU on real cohorts; typed 37/60 at 2.5x CPU; hint ordering 32/60; equal 5 CPU-s at depth 3: 30 vs 28, 4 vs 4, 0 vs 0 | not run (source only) |
| M4 | topology on | off / shuffled | 10 = 10 / 9 | 1 = 1 = 1 |
| M4 | transport | none | 10 = 10 | 1 = 1 |
| M5 | write precedence | undefined on overlap | 10 = 10 | 1 = 1 |
| M6 | grow_full | grow_one_step / learned_step | generated 100% vs 0-100% (by direction and distance) / 0%; real 1 vs 1 / 0 (learned_step 3 wrong first attempts on ARC_eval_dev) | 0 vs 0 |

## Fixed-pool reranking versus new-program construction

CAST constructs new programs; it does not rerank Run A's pool. The pre-declared combination `cast_then_runA`
(cast/runa.py) only replaces Run A's SECOND attempt where CAST has a complete prediction:

| combination | per-query pass@2 | task-mean (of 120) | strict tasks | losses |
|---|---|---|---|---|
| Run A votes alone | 17 | 13.33 | 12 | - |
| Run A votes + M2 | **19** | 14.33 | 13 | 0 |
| Run A likelihood alone | 22 | 16.67 | 15 | - |
| Run A likelihood + M2 | **24** | 17.67 | 16 | 0 |
| Run A + M4 (either selection) | unchanged (17 / 22) | unchanged | unchanged | 0 |
| CAST union alone (M4 > M1 > M2 > M6 > bind_L0) | 3 | 2.0 | 2 | - |

The +2 outputs are construction, not selection: 62593bfd's answer is absent from Run A's whole pool (oracle 27 stays
the pool's bound, 29 with CAST).

## Independent score reproduction

- Run A recomputed by `cast/score.py` from the saved pools: votes 17, likelihood 22, oracle 27 of 172 (the recorded
  values).
- Every ARC_eval_dev predictions file (38 files: M4, every M1/M2/M6/variant arm, Run A selections, combinations)
  re-scored by the campaign harness's own `score` function: per-query rows identical in all 38
  (`results/score_crosscheck.json`).
- Metric note: `task_mean_query` is my reading of the official rule (per task, the fraction of test outputs answered
  within two attempts, averaged over tasks); it was not checked against the official implementation in this session
  (no download was authorised), so no official-equivalent score is claimed.
