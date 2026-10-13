# OFFICIAL KAGGLE, NATIVE BASELINE: ARC-AGI-2 result (2026-10-13)

| field | value |
|---|---|
| competition | ARC Prize 2026 - ARC-AGI-2 (`arc-prize-2026-arc-agi-2`) |
| submission | **57144804**, submitted 2026-10-13T13:17:12Z, COMPLETE (recorded by the detached watcher at 18:00:39Z) |
| **public score** | **0.00** |
| private score | revealed after the competition |
| label | NATIVE_BASELINE native_v1: CORA native v23 solver only. Not FULL_CORA; no research extension, no invention loop |
| notebook | `chimdiwalter/cora-native-v23-arc-agi-2-october-baseline`, version 1 |
| dataset | `chimdiwalter/arc-native-baseline-v1`, version 1. Tarball sha256 4b320ba2...; solver tree d7856871...; source commit 8cde9f3 |
| committed run (the visible stand-in: 240 ARC-AGI-2 training tasks) | 14,512 s (4.03 h) on 4 CPUs. 240 tasks and 259 positions, all valid; 139 real attempt_1, 45 real attempt_2, 120 fallback |
| hidden re-run | completed (status COMPLETE; no timeout or error). Its runtime and outputs are not exposed by Kaggle |
| previous | 54617562 (2026-07-12, older v10/v11 engine): 0.00 |

## Diagnosis of the 0.00 (no hidden answer was inspected)

1. **Most likely: a generalization gap. This is consistent with every
   recorded measurement.**
   - The same frozen engine scores **0 of 120** on the public ARC-AGI-2
     evaluation set in the project's earlier local check
     (`records/FRONTIER_AUDIT_SELECTION_RULE.md`,
     `records/KAGGLE_NATIVE_V1_DELIVERY_20261012.md`).
   - Its 185 of 1,000 is on training tasks.
   - Independent reports find symbolic and induction-only systems at about
     0 on ARC-AGI-2 (`records/CORA_ARC_LEADER_SURVEY_20261013.md`,
     section C).
2. **Packaging defect: not indicated.**
   - The hidden re-run completed.
   - The notebook's task-file discovery worked on the stand-in.
   - All 240 tasks and 259 positions had valid grids.
   - Identities (flags, assets, solver tree) were verified in the committed
     run.
   - The October and July packages score the same.
3. **Not separable without per-task hidden outputs, which Kaggle does not
   expose:** how many hidden tasks received a real candidate, and whether
   any candidate was close.

**Consequence.** The native CORA solver is not competitive on ARC-AGI-2.
- The competition track continues with the separately labelled
  NEURAL_TTT_BASELINE (`records/KAGGLE_NEURAL_V1_LOG_20261013.md`).
- CORA's scientific claims never rested on this score. They are unaffected,
  and they are unsupported by it.

**Not a basis for:** tuning on leaderboard feedback, or any claim about
CORA's construction loop. That loop is not in the package.
