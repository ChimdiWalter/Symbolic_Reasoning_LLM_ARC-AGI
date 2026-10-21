# syn-v3: ncv2-g3 versus ncv2-g2 on held-out synthetic tasks. FINAL: GO_ENGINEERING (21 October 2026)

**It is not evidence about real ARC tasks.** The families are designed by the author of the generator and the solver,
inside the ncv2-g2 language (protocol, line 13). The study cannot test representation, the largest real failure class
(protocol §6). **What a GO licenses:** only proposing a real-task check of ncv2-g3 on a fresh eligible cohort, which
needs its own protocol and authorization; never a claim about real ARC or the leaderboard (protocol, line 78).

## Run

- Protocol `records/NEURAL_CORA_V2G3_SYNTHETIC_PROTOCOL_20261021.md`, frozen at f2a2ef4 (manifest
  `records/NEURAL_CORA_V2G3_SYNTHETIC_FREEZE_MANIFEST.json`, sha ca22174c...); preflight PASS
  (`records/NEURAL_CORA_V2G3_SYNTHETIC_PREFLIGHT_20261021.md`, commit 9d86bbf).
- Authorized by the author (21 October). Run once:
  started 2026-10-21T17:21:57Z, exit 0 at 19:05:42Z; lock check OK (lock manifest ca22174c, HEAD 9d86bbf); 2 workers
  at nice 10; scoring by the evaluator-only `score` step of `scripts/neural_cora_v2g3_synthetic_eval.py`.
- Tasks: 296 HELDOUT (15 families x 20 seeds minus the 4 missing trap tasks recorded at freeze; never replaced). All
  296 rows written; 0 errors. Outputs: `outputs/neural_cora_v2g3/synthetic_eval/` (`rows.jsonl`, `score.json`,
  `score.log`, `solve.log`, `run.status`, `run_manifest.json`).

## Results at the decision budget (3,000 candidates)

| group (n) | g2 pass@2 | g3 pass@2 | g3_find pass@2 | g3_g2stream pass@2 | g2 top-1 | g3 top-1 | g2 wrong | g3 wrong | g2 coverage | g3 coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| composition (80) | 0.0% | 87.5% | 80.0% | 0.0% | 0.0% | 73.8% | 11.3% | 7.5% | 0.0% | 88.8% |
| binding (60) | 98.3% | 100% | 100% | 98.3% | 95.0% | 98.3% | 0.0% | 0.0% | 98.3% | 100% |
| trap (36) | 58.3% | 69.4% | 55.6% | 63.9% | 0.0% | 61.1% | 41.7% | 30.6% | 63.9% | 72.2% |
| ambiguity (40) | 65.0% | 97.5% | 65.0% | 97.5% | 30.0% | 50.0% | 35.0% | 2.5% | 100% | 100% |
| additive (40, descriptive) | 50.0% | 92.5% | 80.0% | 50.0% | 47.5% | 82.5% | 0.0% | 0.0% | 50.0% | 92.5% |
| control (40) | 100% | 100% | 100% | 100% | 85.0% | 100% | 0.0% | 0.0% | 100% | 100% |
| **pooled (296)** | **56.1% (166)** | **91.6% (271)** | 81.8% | 61.1% | 41.2% | 78.7% | 12.8% | 6.1% | 61.5% | 92.6% |

Coverage = retained-candidate coverage (the correct output among the predictions kept within 3,000 candidates).
"wrong" = share of tasks that submitted attempts, none of them correct (scorer: `bool(attempts) and not pass2`). Arms: `g2`
(byte-identical to the GO version), `g3_find` (ncv2-g3 construction with ncv2-g2's selection), `g3` (full ncv2-g3),
`g3_g2stream` (ncv2-g3 selection over ncv2-g2's candidate stream).

Paired over the 296 tasks (g3 vs g2, pass@2): 106 gains, 1 loss. Selection, g3 vs g3_find: 30 gains, 1 loss.
Coverage at smaller budgets (pooled): g2 31.4% at 300, 50.0% at 1,000; g3 61.8% at 300, 78.0% at 1,000.

## Frozen criteria (all must hold for GO_ENGINEERING)

| criterion | gate | measured | pass |
|---|---|---|---|
| pooled pass@2 gain, g3 - g2 | ≥ 15 points | +35.5 points (56.1% → 91.6%) | yes |
| composition correct-coverage gain | ≥ 25 points | +88.8 points (0.0% → 88.8%) | yes |
| trap top-1 gain | ≥ 20 points | +61.1 points (0.0% → 61.1%; n = 36) | yes |
| paired losses | ≤ 2% | 1 of 296 (0.3%) | yes |
| control groups, g3 ≥ g2 | no regression | 100% = 100% | yes |
| median g3 CPU | ≤ 60 s | 9.6 s (p95 34.3 s; g2 5.4 s, p95 30.4 s) | yes |
| peak memory | ≤ 4 GB | 98.9 MB | yes |

**Decision (frozen rule): GO_ENGINEERING.**

## Pre-specified post-run checks (preflight §2-6)

1. Tasks with exactly 50 retained predictions (the retention cap): **0** for every arm (most retained for any task: g2
   5, g3 15, g3_g2stream 5). The cap never bound, so no coverage number is truncated by it.
2. Tasks with pass@2 true while retained coverage is false: **0** for g2 and for g3.

## Reading (descriptive, after the decision)

- Most of the gain comes from construction, not selection: ncv2-g3's construction with ncv2-g2's selection reaches
  81.8% pooled, and ncv2-g3's selection over ncv2-g2's candidate stream only 61.1%; full ncv2-g3 adds 9.8 points over
  construction alone (30 gains, 1 loss).
- Composition, the class ncv2-g2 never solved here, goes from 0 to 87.5% pass@2; evidence-aware selection removes most
  wrong attempts on the ambiguity group (35.0% → 2.5%).
- Traps stay hard: top-1 rises from 0 to 61.1%, but 30.6% of trap tasks still get only wrong attempts.
- None of this concerns representation or real tasks. The real-ARC check of 20 October (NO_REAL_GAIN) and its failure
  analysis place most real failures in representation (parts of objects, line-like additions), which ncv2-g3 does
  not address; ncv2-g4 is aimed there and its own frozen study has not been run.

## Not claimed

No claim about real ARC tasks, the leaderboard, representation, any trained model (no model was trained or loaded),
or any learned revision advantage. Next step under this licence: a proposed real-task check on a fresh eligible
cohort, which needs a new protocol, the separately authorized eligibility check, and authorization to run.
