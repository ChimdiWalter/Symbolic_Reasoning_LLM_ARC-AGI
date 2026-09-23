# ARC-2026 delivery sprint: asset reconciliation (verified 2026-09-23)

Every row was executed or inspected this session, not carried from a summary.

| Asset | Executable version | Measured status | Missing action |
|---|---|---|---|
| Engine code | v23 tree copied by allowlist, workspace commit a44d262, 336 files | imports in a clean environment: geocat_arc, 4 harness layers, reasoning_project | none |
| Frozen library | library.json, sha256 cdacd018da0bd9a3 | byte-identical across v20 to v23 | none |
| Submission writer | scripts/make_submission_v2.py | 60 of 60 dev ids present, all well formed, both attempt keys, fallback fills unsolved | none |
| Budget governor | harness/run_harness.py, chunked rescaling | binds and compresses per-task time (95s to 28s) but overran a 60s budget by 21s, 35 percent | measure overrun at 11.25h scale; add a hard stop before emission |
| Offline notebook | kaggle/kaggle_notebook.py, budget 11.25h | code path verified by reading; never executed on Kaggle | upload dataset, run once publicly |
| Package builder | kaggle/build_dataset.sh | still points at the v22 library path | rebuild from v23 and verify unpack and import |
| Paper writeup | kaggle/writeup.md, 1261 words | headlines 185/1000 training | rewrite without a training headline, per the master directive |
| Development data | data/arc/dev60_challenges.json, sha256 6f36965059bca79a | 60 tasks, extracted by filtered reader; 60 protected members and the holdout key never decoded; solutions never read | none |
| C1 rehearsal | not run | blocked on compute, not on code | run on a quiet host or with allocated cores |

## Baseline diagnostic, 5 distinct development tasks, 1 worker, low priority

Two bounded runs: 3 tasks under a 240s budget (206s wall), 5 tasks under a 60s budget
(81s wall). Nothing solved, which matches the recorded 0 of 120 history.

| Task | attempt 1 | attempt 2 | recorded stage |
|---|---|---|---|
| 13e47133 | none | none | none |
| 142ca369 | none | present | loo |
| 16b78196 | none | present | loo |
| 195c6913 | none | present | matching |
| 20270e3b | none | none | none |

Dominant recorded bottleneck: programs reach the leave-one-out fold and die there.
Three of five tasks produced uncertified attempt-2 material stamped `loo`. That is the
same class as the documented 236-task fold-death pool, and it points at relational
parameter fitting rather than composition. Sample of five; treated as a direction to
test, not a finding.
