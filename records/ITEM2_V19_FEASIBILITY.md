# Item-2 v1.9: prospective thresholds and feasibility

Written 2026-10-07, before any prospective task (seed base 880,000,000) was
generated. Numbers from `scripts/v19_feasibility.py` (exact binomial
arithmetic; output `outputs/tti/v19_feasibility.json`) on the development
ablation (`outputs/tti/v19_repair_dev_report.json`).

## Rules fixed in the script before its inputs existed

- N_TASKS = 30 (the v1.8 corpus size).
- W_MIN = the smallest W with P(X >= W | p0) <= 0.01, p0 = the larger of
  the old-logic rates: v1.8 prospective 11 of 30 and development K* 12 of
  30, so p0 = 0.40.
- DELTA_MIN = ceil(0.2 x N_TASKS) = 6: a material improvement is a net
  adaptive leave-one-out gain of at least a fifth of the tasks.
- Feasible only if G2 power at the development K*' rate minus 0.15 and G3
  power at the development discordance are both at least 0.80.

## Result: N_TASKS 30, W_MIN 19, DELTA_MIN 6, feasible

| gate | quantity | value |
|---|---|---|
| G2 | size at p0 = 0.40 | 0.008 |
| G2 | power at the development K*' rate (26/30 = 0.87) | 0.9997 |
| G2 | power at 0.72 (rate minus 0.15) | 0.89 |
| G2 | power at 0.62 (rate minus 0.25) | 0.51 |
| G3 | power at development discordance (14 new-only, 0 old-only) | 0.9994 |
| G3 | power if the gain halves | 0.73 |
| G3 | size with no gain, q = r = 0.05 / 0.15 | 0.001 / 0.020 |
| G1 | power against transplant / BLIND (v1.8 development rates) | 0.99 / 0.90 |
| G1 | power if the advantage shrinks to q = 0.15 | 0.48 |

G1 is a proposer-level gate the repair does not touch; its rates are the
v1.8 development rates, not any v1.8 prospective outcome. The G2 null rate
uses the v1.8 prospective witness count only as a rate to beat.

## G4 (safety), from protocol section 15a

K*' precision over certified outputs at least 0.95 and at least K*'s minus
0.02 (development: 236 of 238 and 159 of 160); inertness on decisions; no
regression of old-accepted runs or folds; replay, attribution and
restoration on every accepted run. Its risk: one or two extra wrong
certified folds do not move precision appreciably at about 230 certified
outputs; about 12 wrong certified outputs would break the floor.

## Runtime

Development ablation: 573 s per task on average with 4 workers at load 30
to 65 (it also ran the same-e folds and the clause-only runs, which the
prospective test does not). The prospective task adds three proposer arms
and the four-pair control. Estimate: 450 to 600 s per task, 30 tasks with
4 workers in about 60 to 75 minutes.
