# Budgeted operator selection on LIVECell (exploratory, post hoc, calibration only)

CORA's failure-evidence order (the specification order recorded before admission) against random orders. Outcomes are read from the recorded admission trails (CORA and the ten controls); every reachable context was observed, so no run was repeated. No evaluation data were used.

## strict rule

CORA's order: split_dt, split_int, add_lowthresh, delete, clear_border, close, dilate, open, erode, merge_pairs. Admitted with the full ceiling: none.

| budget k | CORA order admits | CORA ΔF1 (validation) | P(admitted op within k), random 11 | expected ΔF1, random 11 | P within k, random 10 specified | estimated CPU saved (s) |
|---|---|---|---|---|---|---|
| 1 | none | +0.000000 | 0.000 (sampled 0.000) | +0.000000 | 0.000 | 724 of 804 |
| 2 | none | +0.000000 | 0.000 (sampled 0.000) | +0.000000 | 0.000 | 643 of 804 |
| 3 | none | +0.000000 | 0.000 (sampled 0.000) | +0.000000 | 0.000 | 563 of 804 |

## tolerant rule

CORA's order: split_dt, split_int, add_lowthresh, delete, clear_border, close, dilate, open, erode, merge_pairs. Admitted with the full ceiling: ['add_lowthresh'].

| budget k | CORA order admits | CORA ΔF1 (validation) | P(admitted op within k), random 11 | expected ΔF1, random 11 | P within k, random 10 specified | estimated CPU saved (s) |
|---|---|---|---|---|---|---|
| 1 | none | +0.000000 | 0.091 (sampled 0.088) | +0.000026 | 0.100 | 720 of 800 |
| 2 | none | +0.000000 | 0.182 (sampled 0.181) | +0.000052 | 0.200 | 640 of 800 |
| 3 | add_lowthresh | +0.000289 | 0.273 (sampled 0.278) | +0.000080 | 0.300 | 560 of 800 |

The admitted operator is rank 3 in CORA's order; a random order of the 11 operators ranks it at least as early with probability 0.273 (expected rank 6).

CPU saved is an estimate at equal cost per candidate; per-candidate CPU was not recorded, and early candidates pay for unit tables that later ones reuse, so the saving is an upper estimate.
