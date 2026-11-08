# Verification notebook: the papers' headline numbers

**Kaggle notebook:** `chimdiwalter/cora-verify-the-paper-s-headline-numbers`, titled "CORA: verify the paper's
headline numbers". Author: Chimdi Walter Ndubuisi. It is public:
https://www.kaggle.com/code/chimdiwalter/cora-verify-the-paper-s-headline-numbers

The notebook lets a reader check that the papers' headline numbers come from released code and data. It fetches
everything at run time, recomputes each number and prints MATCH, MISMATCH, NOT RECOMPUTABLE or RECORD ONLY.

## Versions

| Kaggle version | public commit checked | result | output in this folder |
|---|---|---|---|
| 3 | `de74b4f9` (release stage 1) | 26 checks: MATCH 22, MISMATCH 0, NOT RECOMPUTABLE 4 | `run_output_v3/` |
| next push | `95b672d0` (release stage 2b) | 64 checks; the local test of 8 November gave the table below | added after the Kaggle run |

A push on 8 November, about 06:49 UTC, made the kernel public. Kaggle refused to start it as a run because the
account's limit of five concurrent CPU sessions was reached, so no version 4 run exists from that push.

## Files

| file | what |
|---|---|
| `cora_verify_headline_numbers.ipynb` | the notebook |
| `kernel-metadata.json` | the Kaggle settings: CPU, internet on for the downloads, the ARC Prize 2026 competition data attached for the ARC-AGI-2 evaluation files, public |
| `run_output_v3/` | what Kaggle returned for the run of version 3: the log and `verification_summary.json` |

## What it fetches, and what each fetch is checked against

| source | version | checked against |
|---|---|---|
| the public repository, github.com/ChimdiWalter/Symbolic_Reasoning_LLM_ARC-AGI | commit `95b672d0fe38d5d79f266b5f5bbe14ea042ac66c` (branch `arc2026-sprint`, release stage 2b) | git's object hashes, then every file of the three release manifests (291, 118 and 241 files) |
| ARC-AGI-2 training tasks, github.com/arcprize/ARC-AGI-2 | commit `f3283f727488ad98fe575ea6a5ac981e4a188e49` | rebuilt in the competition's file format; must equal the sha256 in the harness's `DATA_MANIFEST.json` and the construction study's `FREEZE.json` |
| ARC-AGI-2 public evaluation tasks | competition data `arc-prize-2026-arc-agi-2`, attached | the sha256 in `DATA_MANIFEST.json` (the GitHub copy differs on 6 tasks, so the competition files are used, as in the studies) |
| 1D-ARC, ConceptARC and Mini-ARC | the commits the studies used, cloned by the released `download_benchmarks.py` | the 1,210 task files and three licence files in `DATA_MANIFEST.json` |
| the Espresso example files (logic study) | github.com/classabbyamp/espresso-logic at `85265139` | the logic study's `FREEZE.json` |
| the SyGuS string benchmarks (spreadsheet study) | github.com/SyGuS-Org/benchmarks at `13c8deb6` | the archive's sha256 and each of the 210 source files in `data/SOURCE_FILES_SHA256.json` |
| the DREAM hepatocyte and toy networks (signalling study) | github.com/saezlab/CellNOptR at `b7df141a` | the signalling study's `FREEZE.json` |

## What it recomputes, and how

- **Construction at scale (64, 38 and 16 of 95):** recounted from the three worlds' `world_results.json`, each checked
  against its kernel's output manifest. The eight-cluster interval (+5.1 to +40.6 points) is recomputed with the
  study's own bootstrap function and cluster rule, taken unchanged from the released code.
- **Held-back-half test (227 against 118, and 343, of 624):** not recomputable. The released split is checked against
  the sha256 its protocol recorded, and its held halves equal the 464 held tasks; the 624 is counted in the public data.
- **Learned search order (320 against 234):** recounted from the per-task rows of `RESULTS.json`, which are checked
  against the public task files.
- **The CORA-only entry (3 of 172 answered, all right):** its saved predictions are scored against the public answers,
  and its submitted notebook reruns six public evaluation tasks.
- **Related benchmarks (295 of 308, 19 of 20, 44 of 54; at most 2.4% with another task's demonstrations):** from the
  released result file.
- **Logic functions (45, 7 and 12 of 217; 34 to 1):** rerun from the released code on the downloaded Espresso files,
  with the salt the run recorded. The policy half needs ClassBench seeds, which are for academic use only, and is not
  run; the circuit numbers do not need it.
- **Spreadsheet text (22 against 17 and 17 of 53):** rerun. The released `t2/prepare.py` rebuilds the task file and the
  split from the downloaded benchmark, and both must equal their records; the released `run_pass` then runs the 53 held
  tasks.
- **Cell signalling (863, 731 and 805 of 1,000), enzyme chemistry (76, 33 and 75 of 200) and scientific images (no
  edits by the strict check; 16 against 10; 4 of 5; 4,000 edits with 1 helpful and 7 harmful):** from the released
  aggregate result files, with every test statistic recomputed from their counts.
- **ARC-AGI-3 probe:** record only. Its numbers come from a private kernel's outputs; the notebook checks that the
  released record states them.

## Local test (8 November 2026; the run that Kaggle will repeat)

The notebook ran on the study machine with the public downloads, the local copy of the four competition files and every
step except the live rerun, which needs an unloaded CPU (its two rows ran on Kaggle in version 3). Result: MATCH 54,
MISMATCH 0, NOT RECOMPUTABLE 5, RECORD ONLY 3; every integrity check matched; no step failed; 40 s.

| # | number | expected | recomputed here | status | how | paper location | source file @ commit |
|---|---|---|---|---|---|---|---|
| 1 | Construction at scale: eligible constructed tasks | 95 | 95 | MATCH | recount | ARC paper abstract, Sec. 5, Table 1 and Fig. 3a; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 2 | Construction from the failure's own holes, tasks recovered (of 95) | 64 | 64 | MATCH | recount | ARC paper abstract, Sec. 5, Table 1 and Fig. 3a; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 3 | Matched static search, tasks recovered (of 95) | 38 | 38 | MATCH | recount | ARC paper abstract, Sec. 5, Table 1 and Fig. 3a; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 4 | Failure evidence shuffled across tasks, tasks recovered (of 95) | 16 | 16 | MATCH | recount | ARC paper abstract, Sec. 5, Table 1 and Fig. 3a; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 5 | Raw demonstrations as the hole, tasks recovered (of 95) | 48, all inside the 64 | 48, all inside the 64 | MATCH | recount | ARC paper Table 1 and Fig. 3a; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 6 | The same 211 operations tried blind, tasks recovered (of 95); in all three repeats | 32; 3 | 32; 3 | MATCH | recount | ARC paper Table 1 and Fig. 3a; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 7 | Own holes, raw demonstrations and another task's holes, in all three repeats | 64, 48, 16 | 64, 48, 16 | MATCH | recount | ARC paper Table 1 and Fig. 3a; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 8 | Difference, construction minus static search (points) | 27.4 | 27.4 | MATCH | recount | ARC paper Sec. 5; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 9 | Exact paired test, two-sided, on the discordant tasks (31 and 5) | 1.29e-5 | 1.29e-5 | MATCH | recount | full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/runs/generated/W*/runs/cas_eval/world_results.json` @ `95b672d0` |
| 10 | Eight-cluster 95% interval of the difference (points) | +5.1 to +40.6 | +5.1 to +40.6 | MATCH | rerun | ARC paper Sec. 5; full paper Sec. 5.5.3 | `experiments/construction_at_scale_20261105/cas/analysis.py` @ `95b672d0` and world_results.json |
| 11 | Held-back-half test: reuse of operations built on the other half, correct (of 624) | 227 | - | NOT RECOMPUTABLE | - | ARC paper abstract, Sec. 5 and Table 1; full paper Sec. 5.8 | `experiments/natural_growth_b_20261105/reviews/INDEPENDENT_POST_SCORE_AUDIT.md` @ `95b672d0` |
| 12 | Held-back-half test: matched static search, correct (of 624) | 118 | - | NOT RECOMPUTABLE | - | ARC paper abstract, Sec. 5 and Table 1; full paper Sec. 5.8 | `experiments/natural_growth_b_20261105/reviews/INDEPENDENT_POST_SCORE_AUDIT.md` @ `95b672d0` |
| 13 | Held-back-half test: construction from each task's own failure, correct (of 624) | 343 | - | NOT RECOMPUTABLE | - | ARC paper abstract, Sec. 5 and Table 1; full paper Sec. 5.8 | `experiments/natural_growth_b_20261105/reviews/INDEPENDENT_POST_SCORE_AUDIT.md` @ `95b672d0` |
| 14 | Held tasks of both held tests, equal to the released split's held halves | 464 | 464 | MATCH | public data | ARC paper abstract, Sec. 5 and Table 1; full paper Sec. 5.8 | `experiments/natural_growth_20261105/split/SPLIT.json` @ `95b672d0` |
| 15 | Held query outputs, 464 held tasks, counted in the public task files | 624 | 624 | MATCH | public data | ARC paper abstract, Sec. 5 and Table 1; full paper Sec. 5.8 | `experiments/natural_growth_20261105/split/SPLIT.json` @ `95b672d0` and the public data |
| 16 | Learned order at 500 counted operations per hole, correct held query outputs (of 624) | 320 | 320 | MATCH | recount | ARC paper abstract, Sec. 5, Table 1 and Fig. 3c; full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 17 | Hand-set order at the same cap, correct held query outputs (of 624) | 234 | 234 | MATCH | recount | ARC paper abstract, Sec. 5, Table 1 and Fig. 3c; full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 18 | Hand-set order at 20,000 operations (40 times the cap) | 329 | 329 | MATCH | recount | ARC paper Sec. 5, Table 1 and Fig. 3c; full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 19 | Frequency table instead of the learned guide, at 500 | 318 | 318 | MATCH | recount | ARC paper Table 1; full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 20 | Linear model instead of the learned guide, at 500 | 323 | 323 | MATCH | recount | ARC paper Table 1; full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 21 | Held tasks gained and lost by the learned order at 500 | 87 gained, 1 lost | 87 gained, 1 lost | MATCH | recount | full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 22 | Learned order at 125, 500, 2,000 and 20,000 operations | 320, 320, 320, 327 | 320, 320, 320, 327 | MATCH | recount | ARC paper Fig. 3c; full paper Table 13 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 23 | Hand-set order at 125, 500, 2,000 and 20,000 operations | 207, 234, 296, 329 | 207, 234, 296, 329 | MATCH | recount | ARC paper Fig. 3c; full paper Table 13 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 24 | Exact sign test, two-sided, on the tasks gained and lost | 5.75e-25 | 5.75e-25 | MATCH | recount | full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 25 | By benchmark, learned against hand-set (1D-ARC; ConceptARC; Mini-ARC) | 275-191; 33-32; 12-11 | 275-191; 33-32; 12-11 | MATCH | recount | full paper Sec. 5.6.1 | `experiments/guided_construction_20261106/runs/held_run/RESULTS.json` @ `95b672d0` |
| 26 | Public evaluation query outputs | 172 | 172 | MATCH | public data | ARC paper Sec. 5, Table 11 and Fig. 6 | the competition's evaluation files |
| 27 | CORA-only entry: public evaluation outputs answered, and right among them | 3 answered, 3 right | 3 answered, 3 right | MATCH | scored | ARC paper Sec. 5, Table 11 and Fig. 6 | `kaggle_entries/expected_predictions/O_plus_v2_eval120_submission.json` @ `95b672d0` |
| 28 | CORA-only entry: official score (Kaggle submission 57902131) | 0.83% | - | NOT RECOMPUTABLE | - | ARC paper abstract, Sec. 5, Table 2 and Table 11 | Kaggle leaderboard |
| 29 | CORA-only entry on 1D-ARC: right among the answered query outputs | 295 of 308 | 295 of 308 | MATCH | aggregate | ARC paper Sec. 5; full paper Fig. 6 | `experiments/universality_similar_problems_20261102/results/RESULTS.json` @ `95b672d0` |
| 30 | CORA-only entry on Mini-ARC: right among the answered query outputs | 19 of 20 | 19 of 20 | MATCH | aggregate | ARC paper Sec. 5; full paper Fig. 6 | `experiments/universality_similar_problems_20261102/results/RESULTS.json` @ `95b672d0` |
| 31 | CORA-only entry on ConceptARC: right among the answered query outputs | 44 of 54 | 44 of 54 | MATCH | aggregate | ARC paper Sec. 5; full paper Fig. 6 | `experiments/universality_similar_problems_20261102/results/RESULTS.json` @ `95b672d0` |
| 32 | With another task's demonstrations, highest precision over the three benchmarks | 2.4% | 2.4% | MATCH | aggregate | ARC paper Sec. 5; full paper Fig. 6 | `experiments/universality_similar_problems_20261102/results/RESULTS.json` @ `95b672d0` |
| 33 | Logic: held real benchmark functions | 217 | 217 | MATCH | rerun | ARC paper abstract and Table 2; full paper Sec. 6.11 | `experiments/transfer_logic_20261108/tlogic` @ `95b672d0` and the Espresso archive |
| 34 | Logic: the loop, functions recovered exactly (of 217) | 45 | 45 | MATCH | rerun | ARC paper abstract and Table 2; full paper Sec. 6.11 | `experiments/transfer_logic_20261108/tlogic` @ `95b672d0` and the Espresso archive |
| 35 | Logic: two-input gates (static), recovered exactly (of 217) | 7 | 7 | MATCH | rerun | ARC paper abstract and Table 2; full paper Sec. 6.11 | `experiments/transfer_logic_20261108/tlogic` @ `95b672d0` and the Espresso archive |
| 36 | Logic: the loop with a shuffled failure description (of 217) | 12 | 12 | MATCH | rerun | ARC paper abstract and Table 2; full paper Sec. 6.11 | `experiments/transfer_logic_20261108/tlogic` @ `95b672d0` and the Espresso archive |
| 37 | Logic: functions only the loop recovered, against only the shuffled control | 34 to 1 | 34 to 1 | MATCH | rerun | ARC paper Sec. 6; full paper Sec. 6.11 | `experiments/transfer_logic_20261108/tlogic` @ `95b672d0` and the Espresso archive |
| 38 | Logic: Holm-adjusted exact McNemar p, loop against the shuffled control | 2.1e-9 | 2.1e-9 | MATCH | rerun | ARC paper Sec. 6; full paper Sec. 6.11 | `experiments/transfer_logic_20261108/tlogic` @ `95b672d0` and the Espresso archive |
| 39 | Spreadsheets: held tasks | 53 | 53 | MATCH | rerun | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_spreadsheet_20261108/t2` @ `95b672d0` and the SyGuS archive |
| 40 | Spreadsheets: the loop, tasks recovered (of 53) | 22 | 22 | MATCH | rerun | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_spreadsheet_20261108/t2` @ `95b672d0` and the SyGuS archive |
| 41 | Spreadsheets: static search at 4 times the budget (of 53) | 17 | 17 | MATCH | rerun | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_spreadsheet_20261108/t2` @ `95b672d0` and the SyGuS archive |
| 42 | Spreadsheets: pieces built from another task's failure (of 53) | 17 | 17 | MATCH | rerun | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_spreadsheet_20261108/t2` @ `95b672d0` and the SyGuS archive |
| 43 | Spreadsheets: Holm-adjusted p of the two primaries (not significant) | 0.125 and 0.125 | 0.125 and 0.125 | MATCH | rerun | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_spreadsheet_20261108/t2` @ `95b672d0` and the SyGuS archive |
| 44 | Signalling: held perturbation conditions | 1000 | 1000 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_signalling_20261108/results_held/RESULT.json` @ `95b672d0` |
| 45 | Signalling: the grown program, conditions predicted exactly (of 1,000) | 863 | 863 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_signalling_20261108/results_held/RESULT.json` @ `95b672d0` |
| 46 | Signalling: the static prior-network program (of 1,000) | 731 | 731 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_signalling_20261108/results_held/RESULT.json` @ `95b672d0` |
| 47 | Signalling: the same loop with a shuffled failure description (of 1,000) | 805 | 805 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_signalling_20261108/results_held/RESULT.json` @ `95b672d0` |
| 48 | Signalling: gain over the shuffled control from one of the removable edges | 44 of 58, 1 of 6 edges | 44 of 58, 1 of 6 edges | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_signalling_20261108/results_held/RESULT.json` @ `95b672d0` |
| 49 | Chemistry: held substrates | 200 | 200 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_chemistry_20261108/runs/score/summary.json` @ `95b672d0` |
| 50 | Chemistry: the loop, exact products (of 200) | 76 | 76 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_chemistry_20261108/runs/score/summary.json` @ `95b672d0` |
| 51 | Chemistry: best single published rule (of 200) | 33 | 33 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_chemistry_20261108/runs/score/summary.json` @ `95b672d0` |
| 52 | Chemistry: nearest-neighbour method (of 200) | 75 | 75 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_chemistry_20261108/runs/score/summary.json` @ `95b672d0` |
| 53 | Chemistry: exact McNemar p, loop against the published rule (43 to 0) | 2.3e-13 | 2.3e-13 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_chemistry_20261108/runs/score/summary.json` @ `95b672d0` |
| 54 | Chemistry: loop minus nearest neighbour, 95% interval (stored) | -0.110 to 0.115 | -0.110 to 0.115 | MATCH | aggregate | ARC paper Table 2; full paper Sec. 6.11 and Table 23 | `experiments/transfer_chemistry_20261108/runs/score/summary.json` @ `95b672d0` |
| 55 | ARC-AGI-3: exact next frames, grown against the fixed language (of 3,168) | 1,204 against 902 | - | RECORD ONLY | record only | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_worldmodel_20261108/RESULT.md` @ `95b672d0` |
| 56 | ARC-AGI-3: pre-registered 95% interval over games (not passed) | 0.0 to 0.232 | - | RECORD ONLY | record only | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_worldmodel_20261108/RESULT.md` @ `95b672d0` |
| 57 | ARC-AGI-3: games where the gains sit | 3 of 12 | - | RECORD ONLY | record only | ARC paper Table 2; full paper Sec. 6.11 | `experiments/transfer_worldmodel_20261108/RESULT.md` @ `95b672d0` |
| 58 | Images: edits made by CORA's strict check on the three held image sets | 0 | 0 | MATCH | aggregate | ARC paper Fig. 4 and Table 2; full paper Fig. 2 and Sec. 6.7 | `experiments/universality_bio_grammar_20261103/results/RESULTS.json` @ `95b672d0` |
| 59 | Images, NuInsSeg: a looser check, harmful against helpful edits | 16 against 10 | 16 against 10 | MATCH | aggregate | ARC paper Fig. 4 and Table 2; full paper Fig. 2 and Sec. 6.7 | `experiments/universality_bio_grammar_20261103/results/RESULTS_TOLERANT.json` @ `95b672d0` |
| 60 | Images, NuInsSeg: controls blind to the failures that made the same edits | 4 of 5 | 4 of 5 | MATCH | aggregate | ARC paper Fig. 4 and Table 2; full paper Fig. 2 and Sec. 6.7 | `experiments/universality_bio_grammar_20261103/results/RESULTS_TOLERANT.json` @ `95b672d0` |
| 61 | Images, NuInsSeg: every operator and no admission step: edits; helpful; harmful | 4,000; 1; 7 | 4,000; 1; 7 | MATCH | aggregate | ARC paper Fig. 4 and Table 2; full paper Fig. 2 and Sec. 6.7 | `experiments/universality_bio_grammar_20261103/results/RESULTS_SECONDARY.json` @ `95b672d0` |
| 62 | Images, PUMA melanoma: a calibrated rule's edits, and harmful ones | 605; 430 | - | NOT RECOMPUTABLE | - | ARC paper Table 2 | not in the public snapshot |

## What it cannot check, and what would change that

- **The held-back-half test's 227, 118 and 343.** The run took place in a companion study's runtime folder, outside the
  repository. Its sealed final aggregate `FINAL_AGGREGATE_SNAPSHOT.json` (sha256 `bfccc683...`) and report (sha256
  `21070825...`) are not public; the released post-score audit records the counts. Releasing that aggregate, which by
  the audit's description holds counts and per-family rows and no per-task rows, would make the counts recomputable.
- **Rescoring against answers in the ARC studies.** The construction study's generated tasks and committed predictions,
  and the learned order's held prediction rows, are not released.
- **Rerunning signalling and chemistry.** The signalling model imports `u6`, a package of
  `experiments/universality_boolean_bbm_20261103/`, which is not public. The chemistry run needs RDKit and the
  published rule library; this notebook does not attempt it.
- **The PUMA melanoma test** of a calibrated acceptance rule (605 edits, 430 harmful) is not in the public repository.
- **The ARC-AGI-3 probe's outputs** are in a private kernel.
- **The official 0.83%:** Kaggle scored it on the hidden test set.

## Data hygiene

- The notebook holds no task grid, held task list or answer.
- Everything fetched goes to a temporary folder outside `/kaggle/working`, and the notebook deletes it at the end.
- The output holds counts, sha256 values, file names, public task identifiers and the summary table.

## Running it elsewhere

You need Python 3 with numpy, git and internet access. Name a local copy of the four competition files (training and
evaluation challenges and solutions) with the environment variable `CORA_ARC_COMPETITION_DIR`.
