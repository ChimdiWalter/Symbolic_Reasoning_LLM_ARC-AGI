# Kaggle Submission Pipeline (ARC Prize 2026 — ARC-AGI-2)

Status 2026-07-11: emissions + builder SHIPPED and smoke-verified; full
scored dry runs in flight. Remaining: offline packaging, budget governor.

## The pipeline (3 commands)

```bash
# 1. Run the harness with prediction emission (any split / challenge file)
python3 scripts/run_unified_harness.py --split evaluation --workers 14 \
    --out-dir outputs/unified_harness_emit_evaluation \
    --run-id emit_evaluation --emit-predictions

# 2. Build the submission from the persisted predictions
python3 scripts/make_submission_v2.py \
    outputs/unified_harness_emit_evaluation/progress.jsonl \
    data/arc/arc-agi_evaluation_challenges.json \
    outputs/submissions/submission_evaluation_v2.json

# 3. (local dry runs only) score it — NEVER part of the Kaggle notebook
#    (solutions are unavailable there); see logs/emit_full_status.log
```

## How predictions are captured (no leakage, no new solver behavior)

Harness "solved" has always meant *gate-accepted*; each layer separately
rendered test inputs for offline `test_correct` scoring. `--emit-predictions`
persists those SAME renders:

- `unified_reasoning_system.evaluate_arc_unified` (pipeline layer): the
  submission-mode solved record now carries `predictions` — the grids it
  already rendered to verify the solve offline.
- `harness/geocat_layer.py` / `harness/object_layer.py`: render the accepted
  solution's `apply_fn` on each test input (train-only artifacts).
- `harness/object_layer.py` additionally renders the best UNCERTIFIED
  near-solve partial (`partial_predictions` + its parameter class + failure
  stage) — the attempt_2 material.
- `harness/run_harness.py`: persists per task in progress.jsonl:
  `{"predictions": {"attempt_1": [...], "attempt_1_source": layer,
  "attempt_2": [...], "attempt_2_class": ..., "attempt_2_stage": ...}}`.

## The 2-attempt policy (measured, not guessed)

- **attempt_1 = the certified answer** (LOO-by-reinduction gate; measured
  precision 0.95 on object programs — E1).
- **attempt_2 = the best uncertified train-perfect partial** — measured on
  training: +18 additional correct task-outputs; E2 shows the
  feature/relational subset of gate-off acceptances runs ~0.91 precision.
  Best-of-2 scoring makes extra attempts free, so attempt_2 always emits
  when a partial exists.
- Fallback: the test input unchanged (Kaggle requires every task id with
  both attempts present).

This split is also a paper point: the gap between attempt_1-only and
best-of-2 is the measured leaderboard cost of certification.

## Kaggle constraints vs this system

| Constraint | Status |
|---|---|
| No internet | pure Python/numpy, no downloads — compliant by construction |
| CPU/GPU <= 12 h | needs the BUDGET GOVERNOR (below); local full run = 25 min on 24 cores |
| submission.json schema | make_submission_v2 emits exactly it (verified) |
| Open-source for prizes | matches the publication plan anyway |

## Remaining work

1. **Budget governor** — a global wall-clock deadline shared across tasks:
   stop induction cooperatively and emit best-so-far when the notebook
   budget nears exhaustion (also the proper fix for the 8ee62060
   budget-wall class). Not built yet.
2. **Offline packaging** — vendor `geocat_arc/`, `harness/`,
   `src/reasoning_project/` as a Kaggle dataset; notebook = the 2 commands
   above against `/kaggle/input` paths; pin numpy; no writes outside
   `/kaggle/working`.
3. **Dry-run numbers** — full scored training + evaluation runs in flight
   (logs/emit_full_status.log, `KAGGLE-METRIC` lines).

## Expectation setting (honest)

Frozen-system eval-split baseline was 1/120 certified (the ARC-AGI-2
difficulty cliff, RUN_HISTORY 2026-07-10). The leaderboard play is modest;
the **Grand Prize / Paper Track rubric** (Accuracy is 1 of 6 equal
criteria; Novelty/Theory/Universality are ours) is the real competition —
see paper/PUBLICATION_PLAN.md.
