# Item-2 v1.8: feasibility and the prospective thresholds

Written 2026-10-06 (UTC), after the development audit and before any
prospective task was generated. Numbers from `scripts/v18_feasibility.py`
(exact binomial arithmetic; output `outputs/tti/v18_feasibility.json`).

## Development rates used

| quantity | development value |
|---|---|
| proposer useful (selection predicts the held-out pair at fitter level), FAILURE_CONDITIONED | 40 of 40 |
| same, SHUFFLED_FRONTIER | 0 of 40 |
| same, DEMO_ONLY | 0 of 40 |
| complete synthetic B/P/U/L/T/A witness, engine subset | 6 of 8 (0.75) |
| mean wall time per task with the engine stage and real leave-one-out | 163 s at load about 40 on 24 CPUs |
| corpus yield | 40 qualifying tasks within the first 799 seeds |

## Gate G1: failure specificity

One-sided exact sign test on tasks discordant in fitter-level usefulness,
FAILURE_CONDITIONED against SHUFFLED_FRONTIER and against DEMO_ONLY, alpha
0.05 each. Five discordant tasks one way are enough (p = 1/32). Development
discordance was 40 to 0 against both controls.

## Gate G2: complete witnesses

Rule: at least W_MIN of N_TASKS tasks give a complete synthetic witness
(B, P, U, L, T, A all true).

| N, W | size at a true rate of 0.25 | size at 0.33 | power at 0.60 | power at 0.75 | minutes |
|---|---|---|---|---|---|
| 30, 9 (draft) | 0.326 | 0.714 | 1.000 | 1.000 | 82 |
| 24, 12 | 0.007 | 0.068 | 0.886 | 0.998 | 65 |
| **30, 15 (frozen)** | **0.003** | **0.044** | **0.903** | **0.999** | **82** |

The draft value W = 9 of 30 was written into `scripts/v18_prospective.py`
by an earlier instance of this session and replaced before the freeze: its
size against a 25 percent witness rate is 0.33, so it would not separate
"works reliably" from "works sometimes". The frozen rule is half the tasks,
N = 30 and W = 15. Both values were fixed before any prospective data
existed; no prospective task has been generated.

## Corpus

- Prospective seed base 860,000,000 + 100k, the v1.7 filter unchanged, the
  first 30 qualifying tasks, searching at most 2,000 seeds. At the
  development yield (40 in 799) this needs about 600 seeds.
- Exclusion: every target digest in
  `outputs/tti/v18_prospective_exclusion.json` (3,817 digests: the v1.6
  exclusion set, which contains v1.5; the v1.6 test corpus; the v1.7
  fixtures and acceptance tasks; the 38 distinct digests of the v1.8
  development corpus).
- Fewer than 30 tasks within 2,000 seeds gives NO_VERDICT_FIXTURE_SHORTFALL.

## Runtime

30 tasks at 163 s each is about 82 minutes under development load, as one
process at default priority. The proposer's own bound is 180 s per call.
