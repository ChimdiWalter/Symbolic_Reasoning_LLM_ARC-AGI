# ARC Prize 2026: constraints the pipeline must meet (read 2026-10-07)

Sources: arcprize.org/competitions/2026, /competitions/2026/arc-agi-2 and
/competitions/2026/paper (fetched 2026-10-07; the Kaggle page itself renders
only with JavaScript and returned no text), and this repository's earlier
reading recorded in `docs/PAPER_SKELETON.md` section 1.1 and
`kaggle/SUBMISSION_CHECKLIST.md`.

## Competition (ARC-AGI-2 track)

| item | value | source |
|---|---|---|
| submission | Kaggle notebook, `submission.json` | arcprize.org; paper skeleton |
| internet during evaluation | none (no API systems) | arcprize.org |
| runtime | 12 hours CPU or 12 hours GPU per run | paper skeleton 1.1 (arcprize.org: "announced with the competition launch") |
| attempts | exactly 2 per test input; credit if either is exact | arcprize.org |
| coverage | every task id in the challenge JSON must appear | paper skeleton 1.1 |
| external data | freely and publicly available data allowed | paper skeleton 1.1 |
| open source | own code and methods under a public-domain-style licence (CC0, MIT-0) for prize eligibility | arcprize.org |
| ENTRY deadline | 2026-10-26 23:59 UTC (first entry needed to stay eligible) | submission checklist |
| final code submission | 2026-11-02 | arcprize.org (23:59 UTC per checklist) |
| results | 2026-12-04 | arcprize.org |

## Paper Prize

| item | value |
|---|---|
| deadline | 2026-11-08 (arcprize.org; the checklist's 11-09 23:59 UTC predates it; use 11-08) |
| eligibility | linked to a Kaggle code submission (ARC-AGI-2 or ARC-AGI-3); the code need not score high |
| prizes | Top Paper pool $75K (1st $50K, 2nd $20K, 3rd $5K); Outstanding Papers pool $375K for papers scoring above 4.5 of 5 |
| judging | six criteria, equal weight, 0-5 each: Accuracy, Universality, Progress, Theory, Completeness, Novelty |
| required sections | abstract, introduction, prior work, approach, results, conclusion |
| results to report | Kaggle leaderboard and public evaluation; EXCLUDE the training set |
| style | "Shorter and clearer is always better" |

## Consequences for the real ARC work

- Everything runs offline and on CPU; nothing in CORA needs a GPU or a
  network call.
- Time: about 12 hours for the hidden set under the notebook limit. At 120
  tasks that is roughly 6 minutes per task for everything (native solver,
  CORA attempt, two attempts). The pilot records per-task seconds of every
  component so that a deployable activation path can be budgeted.
- The training-set target (>200 of 1000) is engineering evidence only; the
  paper's Results must come from the leaderboard and the public evaluation
  (the 60 DEV and the 60 HOLDOUT in this project's order).
- Calendar from 2026-10-07: entry deadline in 19 days, code deadline in 26,
  paper deadline in 32. The pilot, bounded development, the architecture
  freeze, the 1000-task characterization, the 60 DEV, the 60 HOLDOUT and
  the notebook all have to fit before 2026-11-02.
