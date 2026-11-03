# cast_selective_v2: neural-first, evidence-gated CAST candidates (configuration B, versioned)

Does NOT inherit cast_v1's confirmation claim (cast_v1 is unchanged and is what the S_confirm run measured).

**Deployment API.** `from cast_selective_v2 import insert_attempt2, evaluate`.
`insert_attempt2(task, neural, policy="tier0", cpu_s=15.0, wall_s=30.0)` takes one ARC task dict and the neural
attempts per test input (`[[a1, a2], ...]`, `a2` may be `None`) and returns the final `[[a1, a2'], ...]`:
- attempt 1 is always the neural attempt 1, unchanged;
- `policy="tier0"` (the deployment default): attempt 2 is replaced only where the neural attempt 2 is missing or
  identical to attempt 1, by CAST's first complete fitting candidate if it differs from attempt 1. Under per-query
  best-of-two scoring this cannot lower any query's correctness;
- `policy="tier1:B3"` (and B1/B2) replaces attempt 2 wherever that policy accepts a different grid. This CAN lose a
  correct neural attempt 2 and is enabled only if `records/CAST_CANDIDATE_RISK_COVERAGE.md` reports B5 ENABLED;
- any timeout, error, malformed input or off-main-thread call returns the neural attempts unchanged.
`evaluate(task, cpu_s, wall_s, fold_cpu_s=None)` returns the evidence: per module (M4, M2, L0) the fit count,
behaviours, genuine top-1 leave-one-out folds (re-synthesised from scratch, caches cleared, held-out output used only
for the comparison), the cast_v1 top-2 rule (kept for comparison), single-demonstration folds flag, union query
disagreement over every module, fold agreement on the queries, restart stability; per query the first complete
candidate and the B1/B2/B3 acceptances. Statuses: OK, TIMEOUT, TIMEOUT_IN_FOLD, NO_MAIN_THREAD, ERROR:<type>; per
module NO_CANDIDATE, INCOMPLETE, INSUFFICIENT_VALIDATION_EVIDENCE (fewer than two demonstrations), EVIDENCE.

**Caps.** In-process interval timers (process CPU and wall), main thread only; measured in running processes: the
15 s CPU cap fires at 15.08 s, the 30 s wall cap at 30.0 s, a 1 s cap on a real 30 x 30 task at 1.02 s; timers,
handlers and caches are restored or cleared afterwards (`records/CAST_LEAVE_ONE_OUT_CORRECTNESS_AUDIT.md`). Every
call clears CAST's module caches at start and end (no state crosses puzzles).

**Requirements.** numpy (scipy optional, identical results); Python 3.12 tested; Python 3.13 untested locally (must be
tested in the Kaggle environment during the approved rehearsal). No file, network or subprocess access.

**Tests.** `python -m pytest -q tests` (8: the reliability directive's cases plus insertion semantics).
