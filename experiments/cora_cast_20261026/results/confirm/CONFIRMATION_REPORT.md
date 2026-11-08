# CAST v1 core: confirmation on S_confirm (207 tasks). Verdict: **INCONCLUSIVE**

Run `runs/confirm_v1`, protocol `protocols/CONFIRMATION_PROTOCOL.md` (sha256 in `results/confirm/PROTOCOL_SHA256.txt`), integrity audit `results/confirm/INTEGRITY_AUDIT.md`. Written automatically by `confirm/score_confirm.py` after every arm's attempts existed.

| arm | per-query pass@2 | task-mean | strict tasks | queries with an attempt | fitting-but-wrong first attempts | CPU s |
|---|---|---|---|---|---|---|
| A0 original-CORA baseline (CAST L0 grammar, depth 2) | 4/228 | 4.00/207 | 4/207 | 4 | 0 | 230.8 |
| A1 CAST without guarded rewriting | 6/228 | 6.00/207 | 6/207 | 6 | 0 | 240.8 |
| A2 frozen CAST v1 core | 8/228 | 8.00/207 | 8/207 | 11 | 3 | 253.7 |
| A3 matched extra search (A1 + depth-3 L0 at >= A2 compute) | 7/228 | 7.00/207 | 7/207 | 7 | 0 | 452.6 |

| comparison | strict gains / losses | exact McNemar p | strict-rate difference [95% cluster CI] | per-query-rate difference [95% cluster CI] |
|---|---|---|---|---|
| A2_vs_A1 | 2 / 0 | 0.5 | 0.00966 [0.0, 0.02551] | 0.00877 [0.0, 0.02347] |
| A2_vs_A0 | 4 / 0 | 0.125 | 0.01932 [0.00452, 0.04061] | 0.01754 [0.00398, 0.03721] |
| A2_vs_A3 | 2 / 1 | 1.0 | 0.00483 [-0.01026, 0.02073] | 0.00439 [-0.00952, 0.01932] |

Primary (A2 vs A1) gains: 37d3e8b2, 810b9b61; losses: none.
A2 exact predictions (8 queries): 1d0a4b61:0, 37d3e8b2:0, 3c9b0459:0, 74dd1130:0, 810b9b61:0, a740d043:0, c909285e:0, f823c43c:0.
Linked clusters: 193 (largest 12).
Decision rule (pre-declared): CONFIRMED needs gains > losses against A1 with p < 0.05 and A2 strict >= A3 strict; INCONCLUSIVE if gains > losses otherwise; NOT_CONFIRMED if gains <= losses.

## Reading (added after scoring; nothing was tuned or rerun)

- The single authorized confirmation does **not** confirm the guarded-rewrite mechanism at the pre-declared standard:
  the direction holds (+2/-0 against no-guard, +4/-0 against the L0 baseline) but the effect is smaller than on the
  development cohorts (+7/-0 of 176) and the test has little power at this size (p = 0.5).
- Both primary gains (37d3e8b2, 810b9b61) are hole-count programs (a holes-keyed table rewrite; `has_hole -> recolour`).
- The matched extra-search control answers one task the core misses (11852cab, depth-3 L0), so at equal or larger
  compute the core leads by +2/-1.
- The core emitted 3 fitting-but-wrong first attempts (11 tasks attempted, 8 correct); the Kaggle package's
  leave-one-out acceptance rule exists to filter such cases.
- Cost: 0.13 CPU-h for the whole run (all arms); 0 GPU.
