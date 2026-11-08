# Facts: the two Kaggle scores, the neural comparison entry, and CORA's overlap with it

Prepared 8 November 2026, about 06:20 UTC, from records only. Writeup read:
`paper/final_20261108/KAGGLE_DRAFT_PACKAGE/WRITEUP_BODY_v2_candidate.md` (SHA-256 prefix d09794e1, 1,470 words by
`wc -w`; the version `paper/final_push_20261108/INSERTION_BRIEF.md` line 683 targets). Paths are relative to
`<repository>/` unless another project folder is named.

What was done: records were read; the saved lists of correct outputs of the two entries were intersected; the saved
attempt grids of the two entries were compared cell for cell on 3 outputs; small arithmetic. Nothing was scored or
rerun, no answer file was opened, nothing of Step B or under other projects' job folders was touched, and only this file was written.

## Terms used in this file

| Term | Meaning | Source |
|---|---|---|
| test output | the grid a task expects for one test input; the 120 public evaluation tasks have 172 | `records/audit_20261108/NATURAL_ARC_CONSTRUCTION_REVIEW.md` lines 9-12 |
| correct | one of the two submitted attempts equals the expected grid exactly | same, lines 9-10; `records/KAGGLE_2026_CONSTRAINTS.md` line 16 |
| answered | the system gave its own answer; an abstention, or the CORA-only entry's placeholder copy of the test input, is not an answer | `records/NOV2_UNIVERSALITY_SIMILAR_PROBLEMS_RESULT.md` line 38 ("Answered: non-copy answers") |
| precision; coverage | correct divided by answered; answered divided by all test outputs | same, line 39 |
| hidden test tasks | the ARC-AGI-2 tasks Kaggle keeps from competitors and reruns each submitted notebook on (240 in the 2025 run and in the project's runtime projections) | `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 80, 120; `records/NEURAL_CORA_27P64_RISK_AND_RUNTIME_PLAN.md` line 12 |
| public-leaderboard score (Kaggle's "public score") | the score on one half of the hidden tasks, 120 tasks (ARC Prize's "semi-private" set); the other 120 decide the final private ranking, released after the competition (results 4 December 2026) | `records/CORA_ARC_LEADER_SURVEY_20261013.md` line 28; `records/KAGGLE_NEURAL_V1_LOG_20261013.md` line 427; `records/NOV2_FINAL_SUBMISSION_STATUS.md` line 153; `records/KAGGLE_2026_CONSTRAINTS.md` line 22 |
| public evaluation set | the 120 published ARC-AGI-2 evaluation tasks (172 test outputs); exposed to both systems: used in CORA's development, and used, test outputs included, as the validation set that ranked NVARC's checkpoints | `paper/final_push_20261108/REAL_ARC_RESULT_PROVENANCE.md` lines 33-35; `records/CORA_NVARC_SUBSUMPTION_AUDIT_20261019.md` lines 33-37 |
| CORA-only entry | submission 57902131 (project label "O+ v2") | `records/OFFICIAL_SCORE_AND_SELECTION_STATUS.md` lines 8, 29 |
| neural comparison entry | submission 57867631 (project label "H") | same, lines 9, 29 |
| neural core | the frozen re-implementation of NVARC's method that makes the neural comparison entry's attempts (project label "C4") | `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 3-7 |

## Short answers

- **(a)** Both scores are Kaggle public-leaderboard scores on 120 hidden ARC-AGI-2 test tasks. "3 of 172 answered,
  all correct" is the same CORA-only package on a different set, the 120 public evaluation tasks, which we had inspected.
  Neither number can be derived from the other. The sentence for the Writeup is in section (a).
- **(b)** Every first attempt, and every second attempt that CORA did not replace, came from the neural core (our
  re-implementation of NVARC's method on NVARC's checkpoint). On the public evaluation, in two rehearsals, CORA replaced
  no attempt and changed nothing (43 of 172 with and without it). On the hidden tasks behind 24.03%, whether CORA
  replaced any attempt, and its effect on the score, are UNKNOWN and can no longer be measured.
- **(c)** Of the CORA-only entry's 3 correct public evaluation outputs, the neural system was also correct on 2 in
  both of its rehearsals, and missed 1 (the first test output of task 62593bfd), whose correct grid is absent from its
  whole candidate pool. Settled from saved records; no scoring needed. On the hidden tasks: UNKNOWN, not recoverable.
- **(d)** Two different systems. The 2 of 172 are the held-back-half test's construction condition; they are both
  outputs of 62593bfd and equal, cell for cell, the CORA-only entry's own answers. The entry's third answer (task
  981571dc) comes from a module none of that test's seven conditions has fitted. Union over all CORA studies: 3 of 172.
- **(e)** "Answered" is used for "correct" in at least four places, two numbers are wrong as worded (343 and 227 are
  correct counts, not answered counts), and "public score" is read as a public-evaluation score. Terms and a full list
  are in section (e).

## (a) Which test set, and how it relates to "3 of 172 answered, all correct"

| Fact | Source |
|---|---|
| 57902131: CORA only, CPU, public score 0.83, COMPLETE; 57867631: neural core plus CORA's second-attempt step, public score 24.03, COMPLETE; both are the two final selections | `records/OFFICIAL_SCORE_AND_SELECTION_STATUS.md` lines 8-9, 18-19, 27, 29 |
| Records name these "official Kaggle scores (hidden set)" | `paper/final_push_20261108/REAL_ARC_RESULT_PROVENANCE.md` lines 24-28; `paper/final_push_20261108/INDEPENDENT_REAL_ARC_EVIDENCE_AUDIT.md` line 183 |
| The public leaderboard is the 120-task semi-private half; the private half decides the ranking | `records/CORA_ARC_LEADER_SURVEY_20261013.md` line 28; `records/NOV2_FINAL_SUBMISSION_STATUS.md` line 153 |
| Paper 2 already captions its score table "Official public-leaderboard scores on the hidden ARC-AGI-2 test" | `paper/v2_neural_cora/main.tex` lines 1283-1287 |
| The CORA-only package answered exactly 3 of the 172 public evaluation test outputs (both outputs of 62593bfd, the one output of 981571dc), all 3 correct, on our machine and in a Kaggle CPU rehearsal whose answers were byte-identical; the other 169 outputs hold the input-copy placeholder | `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 183-184; `kaggle/score_first_2026/configs/results/op2_rehearsal_v1/check.json` (`attempt_1_from_package` 3, `identical_to_local_run` true); `kaggle/score_first_2026/configs/results/op2_local/score_eval120.json` (`OplusV2.correct`); `paper/final_push_20261108/INDEPENDENT_REAL_ARC_EVIDENCE_AUDIT.md` line 165 |
| Both tasks were inspected in development: 62593bfd shaped the guarded-rewriting module that solves it; 981571dc is an ARC-AGI-1 evaluation task contained in re-arc | `experiments/cora_cast_20261026/FINAL_DECISION.md` lines 8-15; `records/CORA_SYNTHESIS_REVIEW_20261027.md` line 292; `paper/final_push_20261108/INDEPENDENT_REAL_ARC_EVIDENCE_AUDIT.md` lines 179-180 |
| On the public set the same answers give 1.74% per test output (3 of 172) and 1.67% as a mean over tasks (2 of 120 tasks fully correct) | `kaggle/score_first_2026/configs/results/op2_local/score_eval120.json` (`per_output` 0.017442, `task_mean` 0.016667, `strict_tasks` 2) |
| The neural core's public evaluation rehearsals: 43 of 172 (25.0%), task mean 27.1% (31 Oct run) and 26.7% (1 Nov run) | `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 65, 85 |

**Relation.** The two percentages and the public evaluation counts measure the same code on different tasks: hidden
tasks that competitors cannot see (Writeup line 17; "only the hidden-set score is clean",
`records/SUBMISSION_VARIANT_COMPARISON.md` line 11), against public tasks that both systems had been exposed to. The
0.83% is not computed from 3 of 172; on the public set the same answers come to 1.67% as a mean over tasks or 1.74%
per test output, about twice 0.83%.

**UNKNOWN: how many hidden test outputs the CORA-only entry answered, and how many were correct.** Kaggle returned only
a status and a score (`records/OFFICIAL_SCORE_AND_SELECTION_STATUS.md` line 3); no record holds an answer or a count from
the hidden rerun. So it is also unknown whether a placeholder copy of a test input was ever correct there (on the public
set it never was: `paper/final_push_20261108/neural_vs_cora/data/score_summary.json`,
`cora_padding_never_right_without_answer` true). Nothing in the records or in public data can settle this; the private
score due on 4 December adds a second score, not counts. A judge simulation asks for "the count behind 0.83%"
(`paper/final_20261108/reviews/score_plan_20261108/JUDGE_J3.md` line 127): it does not exist and must not be
estimated in the text.

**Not settled by records: whether Kaggle averages over tasks or over test outputs.** The metric text quoted in
`records/COMPETITION_ELIGIBILITY_OPEN_ISSUES.md` lines 239-243 describes a mean over test outputs. The three scores on
this leaderboard (0.83%, 24.03%, and 27.64% for submission 57160429) fit a mean over 120 tasks of each task's fraction
of correct test outputs (1/120; 28 5/6 of 120; 33 1/6 of 120), and no count of test outputs from 100 to 600 reproduces
all three as a mean over outputs (my arithmetic check). Settle with the competition's published metric code. Until
then the Writeup should not turn 0.83% into "one task".

**Same number, different quantity (registry conflict).** The older CORA-only build's Kaggle CPU rehearsal on the public
evaluation, at a 15 CPU-second cap, answered 1 of 172 with a task mean of 0.83%
(`kaggle/score_first_2026/configs/results/op_rehearsal_v1b/score.json`). Registry row 319
(`paper/writeup/RESULTS_TO_SOURCE.md` line 325) marks that row as used in the Writeup. The Writeup's 0.83% is the
official hidden-set score and must trace only to row 402 (line 408). The registry generator should exclude row 319
from Writeup matches.

**The sentence for the Writeup (exact, standalone, 44 words):**

> The two Kaggle scores, 0.83% and 24.03%, are public-leaderboard scores on 120 hidden ARC-AGI-2 test tasks, not on
> the 120 public evaluation tasks, where the CORA-only entry answered 3 of 172 test outputs, all 3 correct, on tasks
> we had inspected while building CORA.

Placement: after the two scores in "Scored entries" (line 3). There the shorter form "Both are Kaggle public-leaderboard
scores on 120 hidden ARC-AGI-2 test tasks, not on the 120 public evaluation tasks, where the CORA-only entry answered 3
of 172 test outputs, all 3 correct, on tasks we had inspected while building CORA." (39 words) is equally exact; then
delete "public score" before 0.83% and 24.03% (minus 4 words), and drop the repeated 3 of 172 from line 33 (item E15).
Paper 1 carries the same "public score" wording (`paper/final_20261108/cora_final.tex` lines 85-88).

## (b) What submission 57867631 was

| Item | Fact | Source |
|---|---|---|
| Identity | kernel `chimdiwalter/sf-h-c4-cast-arc-agi-2` version 1 (scriptVersionId 364496615), notebook SHA-256 `0e09afd4...`; submitted 1 Nov 2026 09:40:37 UTC; COMPLETE at 24.03 by the 2 Nov 08:42 UTC poll | `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 114-117; `records/OFFICIAL_SCORE_AND_SELECTION_STATUS.md` line 29; `kaggle/score_first_2026/configs/results/h_entry_v1/submission_status_log.txt` (last line) |
| Hardware | Kaggle GPU notebook, 4 NVIDIA L4, internet off | `records/NOV2_FINAL_SUBMISSION_STATUS.md` line 20 |
| First attempt | always the neural core's answer, byte for byte; never changed by CORA | same, lines 4-5, 18, 36 |
| Neural core | the parallel sprint's frozen test-time-training code, a re-implementation of NVARC's published method from its public description, with NVARC's released Qwen3-4B checkpoint `sorokin/qwen3_4b_grids15_sft139`; 48 training steps on every task in its rehearsal; decodes under the 8 rotations and reflections | same, lines 4-5, 18; `records/SUBMISSION_VARIANT_COMPARISON.md` line 19; `kaggle/score_first_2026/configs/results/h_rehearsal_v1/summary.json` line 80; `records/CORA_FINAL_PAPER_EVIDENCE_MATRIX.md` rows 72, 77 |
| Second attempt | the neural core's second answer, unless CORA's selective package (`cast_selective_v2`, CORA-CAST version 2) accepts an answer under the merge rule the project calls "Tier 1 B3"; then CORA's answer replaces it. B3 also requires every leave-one-out fold to predict the same test outputs as the full run. Any CORA failure keeps the neural file | `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 6-7, 19, 31-37; `records/CORA_FINAL_PAPER_EVIDENCE_MATRIX.md` row 76 |
| CORA's limits | each task in a fresh child process, 15 CPU-seconds and 30 wall-seconds; whole side process at most 3 hours | `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 25-30 |
| Known risk | the replacement rule can replace a correct neural second attempt | same, lines 139-140 |

**Did CORA contribute any attempt?**
- **Entry's own Kaggle rehearsal on the 120 public evaluation tasks (1 Nov).** CORA finished 119 tasks and stopped at
  its cap on 62593bfd (15.004 CPU-seconds). It answered 1 test output (981571dc), an answer the neural core already
  had ("already C4's attempt", `records/NOV2_FINAL_SUBMISSION_STATUS.md` line 84), so it made 0 proposals and 0
  replacements; the final file equals the neural-only file; 43 of 172 correct with and
  without CORA (task mean 26.7%; 33 correct on the first attempt, 10 only on the second). Sources:
  `kaggle/score_first_2026/configs/results/h_rehearsal_v1/cast_merge_report.json` (`proposals` 0, `applied` 0);
  `.../h_rehearsal_v1/summary.json` lines 19, 21, 163; `outputs/score_first/runs/h_rehearsal_v1/cora_side/0_cast_selective_v2/62593bfd.json`
  (TIMEOUT, 15.004) and `status.json` (`answered_outputs` 1); `.../h_rehearsal_v1/score.json` lines 6-13, 62-69,
  117-118; `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 83-85.
- **The neural core's 31 Oct Kaggle rehearsal, with CORA's step applied afterwards on our machine.** Same pattern: 119
  finished, 1 timeout, 0 proposals; 43 of 172 with and without (task mean 27.1%; 28 tasks fully correct)
  (`kaggle/score_first_2026/configs/results/h_on_c4_exports/merge_summary.json`, `score.json`;
  `records/NOV2_FINAL_SUBMISSION_STATUS.md` lines 58-67). The two neural runs share 42 of their 43 correct outputs
  (intersection of the two saved lists); test-time training on GPUs is not bitwise reproducible (same file, lines
  90-92).
- **Commit run before submission (8 placeholder tasks):** CORA finished all 8, 0 replacements
  (`kaggle/score_first_2026/configs/results/h_entry_v1/entry_check.json`).
- **Hidden tasks behind 24.03%: UNKNOWN** whether CORA replaced any second attempt, and whether it raised, lowered or
  left the score. No record holds the hidden rerun's output or merge report; `h_entry_v1/` holds only the commit run
  and status polls. Settling it would need that merge report, which Kaggle does not return, or a paired neural-only
  submission on the same hidden tasks, which is impossible since submissions were disabled on 6 Nov
  (`experiments/late_submission_cpu_20261106/records/SUBMISSION_REFUSED.md` lines 1-11) and would still differ by GPU
  nondeterminism.

**Attribution.** Credit 24.03% to NVARC's method, as the Writeup does (`records/OFFICIAL_SCORE_AND_SELECTION_STATUS.md`
lines 23-25; `paper/final_push_20261108/INSERTION_BRIEF.md` line 35). CORA's increment is 0 gained and 0 lost on the
public evaluation and unmeasured on the hidden tasks, as Paper 2 (`main.tex` lines 1283-1287, 447) and Paper 1
(`cora_final.tex` line 480) already say. Do not mix the two rehearsals with each other or with 24.03%
(`records/audit_20261108/NATURAL_ARC_CONSTRUCTION_REVIEW.md` lines 165-166). Note: 24.03% equals NVARC's own 2025
private-leaderboard score by coincidence (`records/CORA_ARC_LEADER_SURVEY_20261013.md` line 28); Paper 2 says so
(`main.tex` lines 1297-1299).

**Writeup line 3, proposed (40 words, +11):** "Submission 57867631, the neural comparison entry, runs our
re-implementation of NVARC's published method on NVARC's checkpoint; CORA's checked second attempt replaced no neural
answer in rehearsal and has an unknown effect on the hidden tasks: 24.03%, credited to NVARC's method."

Negative, as result, lesson, direction. Result: CORA's checked second attempt added no correct output to the neural
entry on the public evaluation. Lesson: it can help only where the neural model misses and CORA finishes inside its
cap; on the one such output (62593bfd, first test output) the 15 CPU-second cap stopped it. Direction: set the cap
from Kaggle CPU timings and measure the increment against a paired neural-only run decided in advance.

## (c) Overlap on CORA's 3 correct public evaluation outputs

Method: the saved lists of correct outputs of each run were intersected, and the CORA-only entry's attempt-1 grids were
compared cell for cell with the neural attempts in the saved prediction files (no answer file opened). Both methods
agree.

| Test output | CORA-only entry | Neural core, 31 Oct Kaggle rehearsal | Neural comparison entry, 1 Nov Kaggle rehearsal | Older neural pool, 26 Oct (no per-task training) |
|---|---|---|---|---|
| 62593bfd, first | correct, attempt 1 (guarded-rewriting module) | not correct: neither attempt equals CORA's correct grid | not correct: neither attempt equals it; the grid is absent from the whole candidate pool | absent from the whole pool |
| 62593bfd, second | correct, attempt 1 | correct: attempt 2 equals CORA's grid | correct, attempt 2 (the neural model's own; nothing was replaced) | absent from the whole pool |
| 981571dc, only | correct, attempt 1 (symmetry-completion module) | correct, attempt 1 | correct, attempt 1 | correct (selected pair) |

Sources: `kaggle/score_first_2026/configs/results/op2_local/score_eval120.json`; `.../h_on_c4_exports/score.json`
(`C4_alone.correct`); `.../h_rehearsal_v1/score.json` lines 33, 45; `paper/final_push_20261108/neural_vs_cora/data/outputs_scored.csv`
(rows 62593bfd and 981571dc: `neural_attempt` 0, 2, 1); `kaggle/score_first_2026/configs/h2/results/headroom_eval120.json`
(the 1 Nov pool, per `records/CORA_FINAL_PAPER_EVIDENCE_MATRIX.md` row 79: 46 outputs have a correct grid in it, the
43 plus 142ca369, 3dc255db and b6f77b65 only);
`experiments/cora_cast_20261026/ABLATIONS_AND_COSTS.md` line 58 and `M4_TOPOLOGY_SYMMETRY_REPORT.md` line 10 (older
pool); `records/SUBMITTED_METHOD_TO_CODE_MAP.md` line 56 (modules); prediction files
`kaggle/score_first_2026/configs/results/op2_local/eval120/submission.json`,
`outputs/score_first/runs/h_rehearsal_v1/submission.json` and `submission_A.json`,
`kaggle/score_first_2026/configs/results/h_on_c4_exports/c4_submission.json`.

Consequences:
- CORA's only correct output that the neural system lacks is the first test output of 62593bfd, one of 172. The union
  of the two entries' correct outputs is 44 of 172, and no submitted system reached it: the neural comparison entry
  could have only if its CORA step had finished on that task (`records/NOV1_PAPER_REVIEW.md` lines 116-121).
- The neural system was correct on 41 test outputs (36 tasks) that the CORA-only entry did not answer
  (`neural_vs_cora/data/score_summary.json`, `gap_outputs`, `gap_tasks`).
- **Writeup line 13 invites a false reading.** "bounded typed search could explain none of its guesses" led a judge
  simulation to infer that CORA's 3 correct answers cannot be among the neural model's
  (`paper/final_20261108/reviews/JUDGE_READ_WRITEUP_v2.md` line 35). They are 2 of 3. That test searched the starting grammar at 150,000
  executions and 20 CPU-seconds per search (`experiments/neural_to_program_b_20261103/PROTOCOL.md` lines 127-129) on
  the 1 Nov first attempts (line 63), and stopped at its budget every time
  (`records/audit_20261108/NATURAL_ARC_CONSTRUCTION_REVIEW.md` lines 167-170). The scored solver answers only with a
  program that reproduces every demonstration and survives leave-one-out (Writeup line 21), and its answer on 981571dc
  equals the neural first attempt cell for cell. So one neural first answer does have a CORA program, outside that
  test's search.
- Status of `paper/final_push_20261108/neural_vs_cora/`: the overlap part is complete and its four checks pass
  (`data/score_summary.json`); it is not audited and has no written result; its explanation search was still running
  at 05:58 UTC on 8 Nov (`data/explain/search/driver_status.json`, `state` RUNNING). Its overlap numbers match the
  saved score records exactly, so (c) does not depend on it.
- **Hidden tasks: UNKNOWN.** Which hidden outputs either entry got correct is in no record, and no public data can
  settle it (see (b)).

Optional sentence (Paper 1 now; the Writeup only if words allow, 47 words): "In rehearsal, the neural comparison entry
was also correct on 2 of the CORA-only entry's 3 correct public evaluation test outputs; the third could have raised it
from 43 to 44 of 172, but its own CORA step stopped at its 15 CPU-second limit on that task."

## (d) "2 of 172, every other arm abstained" against the scored solver's 3 of 172

| | 2 of 172 | 3 of 172 |
|---|---|---|
| System | construction condition of the held-back-half test, a research study run on our CPUs on 7 Nov; in no scored entry | the CORA-only entry (scored solver CORA-CAST, then a second package that answered none of the 172) |
| Answers | both test outputs of 62593bfd, both correct | both outputs of 62593bfd and the one output of 981571dc, all correct |
| Sources | `experiments/natural_growth_b_20261105/reviews/INDEPENDENT_POST_SCORE_AUDIT.md` line 181 ("construction 2 correct (2 answered); every other arm 0") | `kaggle/score_first_2026/configs/results/op2_local/score_eval120.json`; `records/CORA_FINAL_PAPER_EVIDENCE_MATRIX.md` row 75 |

- **The 2 are a subset of the 3.** On both outputs, construction's first attempt equals the CORA-only entry's first
  attempt cell for cell, which the entry's score record marks correct
  (`paper/final_push_20261108/COMPANION_EXPERIMENT_RECONCILIATION.md` lines 58-59). Construction added no answer; the
  union over every completed CORA study on this set is the entry's 3 outputs from 2 tasks
  (`paper/final_push_20261108/INDEPENDENT_REAL_ARC_EVIDENCE_AUDIT.md` line 179).
- **"Every other arm" means the test's six other conditions, not CORA.** On ARC-AGI-2 the test ran seven conditions:
  the starting grammar alone, with the learned library, object-level reuse, construction, and static search at three
  matched CPU allowances (row files in `<companion runtime folder>/experiments/natural_growth_b_20261105/runs/C/arc2/`;
  names in `INDEPENDENT_POST_SCORE_AUDIT.md` lines 24-27). Only construction fitted a task (1 of 120)
  (`COMPANION_EXPERIMENT_RECONCILIATION.md` line 56; recount of the row files: construction 1, others 0).
- **Why 981571dc is missing from the test.** None of the seven conditions fitted it: the grammar and library searches
  stopped at their 150,000-execution budget, object-level reuse ended without a fit in its base search, construction
  built 0 candidates, and the three static searches reached their CPU caps (the seven 981571dc rows in the same
  files). The entry answers it with its symmetry-completion module (`records/SUBMITTED_METHOD_TO_CODE_MAP.md` line
  56). Why that test's languages cannot reach it is not stated in the records read; the rows show only where each
  search stopped.
- **The construction answer is real but exposed.** It came from the construction step, which runs only after the base
  search failed (`INDEPENDENT_REAL_ARC_EVIDENCE_AUDIT.md` lines 15-16); the matched static search ran 1,339,667
  executions on 62593bfd (63.1 CPU-seconds, against 8.3 for construction) without a fit (`static_construct.jsonl` and
  `construct.jsonl` rows). The task was analysed while the entry's guarded-rewriting module was designed, and the
  object-level constructor was written after reading that module's code (same file, lines 21-22;
  `experiments/cora_cast_20261026/FINAL_DECISION.md` lines 8-15). Interval 0 to 6, inconclusive; a descriptive,
  exposed example, not a selection result (`paper/final_push_20261108/INSERTION_BRIEF.md` lines 63-71, 555-563).

**Writeup line 44, proposed (39 words, +15):** "Construction answered 2 of 172 public evaluation test outputs, both
correct and both on the task of Section 1, after its base search failed; the test's six other conditions answered
none, and both answers equal the CORA-only entry's own." The task of Section 1 is 62593bfd: objects that share their
size move up, the others to the bottom border (`paper/final_20261108/cora_final.tex` lines 116-121; `FINAL_DECISION.md`
line 10).

Negative, as result, lesson, direction. Result: on the real ARC-AGI-2 set, construction re-found answers the entry
already had and added none. Lesson: on tasks the entry's modules were designed from, construction can only re-find
known answers, and with at most 2 reachable tasks no comparison can reach p below 0.5. Direction: the decisive test
needs tasks where the entry abstains and a budget that binds (`INSERTION_BRIEF.md` lines 106-112).

## (e) "Answered" against "correct"

**Proposed terms (one term for one thing).**

| Use | Term | Not |
|---|---|---|
| the grid expected for one test input | test output | query, query output, output, held output |
| the system gave its own answer | answered (coverage = answered of all) | (never for "correct") |
| an attempt matches exactly | correct (precision = correct of answered) | right, recovered, got, answered |
| every test output of a task correct | task fully correct | solved |
| some candidate, not the committed one, was correct | reached (descriptive only) | recovered, correct |
| gene rule equal to the published rule on every input state | recovered exactly | rebuilt, recovered |
| Kaggle's number | Kaggle score on 120 hidden tasks | public score, accuracy |

Write counts as "correct on X of N", "answered Y of N, Z of them correct" and "recovered exactly X of 595". Define
"test output", "answered" and "correct" once, in Section 2 (line 17).

**Every ambiguous use in Writeup v2.** P0: misleading, wrong, or against a binding audit. P1: term or denominator.
P2: minor. Word changes are counted with `wc -w`.

| # | Line | Exact sentence | Problem | Proposed | Pri. | Words |
|---|---|---|---|---|---|---|
| E1 | 3 | "Kaggle submission 57902131 runs CORA alone, on CPUs, with no neural model: public score 0.83%." | "public score" reads as a score on the public evaluation set | drop "public score"; add the (a) sentence | P0 | -2, +39 |
| E2 | 3 | "Submission 57867631, the neural comparison entry, runs our re-implementation of NVARC's published method on NVARC's checkpoint, with a checked CORA second attempt: public score 24.03%, credited to NVARC's method." | reads as if CORA supplied second attempts; it replaced none in rehearsal, hidden effect unknown (b) | section (b) wording | P0 | +11 |
| E3 | 7 | "CORA (Constructive Operator Reasoning Architecture) shows that the failure itself can say what is missing: on 95 generated tasks with one operation removed, building that operation from the failure recovered 64, against 38 for static search using more than three times the CPU, and 16 with shuffled failure evidence." | "recovered" here means a committed answer was correct (`experiments/construction_at_scale_20261105/PROTOCOL.md` line 82); the table calls it "Correct"; elsewhere "recover" means exact rule recovery | "was correct on 64" | P1 | +2 |
| E4 | 7 | "On the held-back half of three ARC-style benchmarks, reused operations answered 227 against 118 of 624 query outputs, all of the gain on one-dimensional puzzles." | 227 and 118 are correct counts (`INDEPENDENT_POST_SCORE_AUDIT.md` lines 141-148) | "were correct on 227 against 118 of 624 test outputs" | P0 | +2 |
| E5 | 7 | "Through a gene-network adapter the same loop rebuilt 101 of 595 published rules against 66." | "rebuilt" is a second word for exact recovery, defined only in Section 5 | "recovered exactly 101 of 595" | P1 | +1 |
| E6 | 7 | "CORA's CPU-only entry scored 0.83%: usually right when it answers, it rarely answers, and that coverage gap is what this work addresses." | ties the hidden-task score to precision and coverage measured on other sets; both are unknown on hidden tasks | "CORA's CPU-only entry scored 0.83%; where its answers can be checked, they are usually correct but rare, and that coverage gap is what this work addresses." | P0 | +4 |
| E7 | 13 | "Neural systems propose answers well but give no explanation that can be run and checked: on the 172 public evaluation query outputs the neural comparison entry was right on 43, and bounded typed search could explain none of its guesses." | 43 is a rehearsal count on tasks its checkpoint was validated on; "its guesses" are the 172 first attempts, 33 correct; "could explain none" holds only for a budget-limited search in the starting grammar and invites the false disjointness reading (c) | after the colon: "in rehearsal the neural comparison entry was correct on 43 of the 172 public evaluation test outputs, and a budget-limited search in our starting grammar explained none of its first answers." | P0 | +6 |
| E8 | 17 | "A *query* is a test input; *held out* means kept from a study's development; *exposed* means scored before." | defines "query", then counts "query outputs", "outputs" and "held outputs"; never defines "answered" or "correct" | "A *test output* is the grid one test input expects; *answered* means the system gave its own answer, *correct* that an attempt matched exactly; ..." | P1 | +18 |
| E9 | 21 | "The scored solver, CORA-CAST, answers only if a program reproduces every demonstration and, rebuilt without each demonstration, still predicts it." | "answers" is the right sense; "rebuilt" here means refit, unlike "rebuilt" rules in line 7 | "refit without each demonstration" | P2 | 0 |
| E10 | 23 | "Three requirements organise the evidence: *availability* (can the language express the answer), *discovery* (can the system find it within budget) and *selection* (can evidence choose the change)." | "the answer" means the correct output | "express the correct output" | P2 | +1 |
| E11 | 27 | "Leaving out either of two task worlds gives intervals including zero; other families gained nothing (23 against 28)." | no denominator (60 tasks: `cora_final.tex` line 237); 23 is a "reached" count, not a correct count (`experiments/construction_at_scale_20261105/runs/analysis/ANALYSIS.json` `descriptive.oracle_reach_excluded.transfer`; `PROTOCOL.md` lines 83-86); what 28 counts is UNKNOWN from the records read (settle in the construction closeout, inbox 0203) | "(23 against 28 of 60 tasks, descriptive)", once 28 is identified | P1 | +4 |
| E12 | 29 | "The gain is all on 1D-ARC (216 against 88); on ConceptARC static search won (9 against 27)." | unlabeled correct counts; denominators 309 and 240 (`INDEPENDENT_POST_SCORE_AUDIT.md` lines 145, 147) | "(216 against 88 of 309 correct)"; "(9 against 27 of 240)" | P1 | +4 |
| E13 | 29 | "Construction from each task's own failures answered 343." | wrong term: 343 correct of 624; it answered 377, precision 0.91 (same audit, line 171). A judge simulation repeats "answered 343" (`paper/final_20261108/reviews/score_plan_20261108/JUDGE_J2.md` line 39) | "was correct on 343 of 624" | P0 | +4 |
| E14 | 31 | "A learned order beat the hand-set order at 500 counted operations per hole (320 against 234 query outputs), and the hand-set order needed a 40-times larger cap to get 329; frequency and linear orders matched the network." | correct counts of 624 (registry row 1); "the network" is the learned order (banned: `INSERTION_BRIEF.md` line 32; item W3) | "(320 against 234 of 624 test outputs correct) ... to reach 329; ... matched it" | P1 | +3 |
| E15 | 33 | "**Checked answers are usually right.** On three related benchmarks the scored solver was right on 81.5% to 95.8% of its answers; on the public evaluation it answered 3 of 172, all right, so coverage, not precision, sets the 0.83%." | "right" for correct; "sets the 0.83%" links a public-evaluation count to a hidden-task score; coverage on the benchmarks (11.3% to 50.1%: `NOV2_UNIVERSALITY_SIMILAR_PROBLEMS_RESULT.md` lines 44, 50, 56) not given | "**Checked answers are usually correct.** On three related benchmarks the scored solver was correct on 81.5% to 95.8% of the test outputs it answered, but answered only 11% to 50% of them, so where we can check, coverage, not precision, limits it." | P0 | +3 |
| E16 | 35-42 | table header "Correct"; rows "16", "38", "37, against 56 static", "320; 234" | header is consistent; denominators (95 tasks; 624 outputs) missing | add "of 95" and "of 624" to the row labels | P1 | about +6 |
| E17 | 44 | "Construction answered 2 of 172 public evaluation query outputs, from one task, while every other arm abstained: a descriptive example, not a selection result." | does not say both correct; "arm" is an internal label; reads as if CORA abstained elsewhere, against 3 of 172 (d) | section (d) wording | P0 | +15 |
| E18 | 50 | "Inferred regulators raised exact recovery from 66 to 101 in a pre-registered replication, and well-chosen observations from 291 to 320." | denominator 595 missing | "from 66 to 101 of 595" | P1 | +2 |
| E19 | 50 | "Growing the language from failure rebuilt 433 rules against 321, all 112 extra rules needing three or more inputs; a classical learner tied it." | "rebuilt"; no denominator; "from failure" breaks the binding audit's "do not write that a failure ... caused the gain" (`records/SPARSE_COFACTOR_NATURAL_INDEPENDENT_AUDIT_20261108.md` line 133) | "Allowing rules to branch on more inputs recovered exactly 433 of 595 rules against 321 for two-input rules, all 112 extra rules needing three or more inputs; a classical learner tied it." | P0 | +8 |
| E20 | 52 | "The procedure moved; learned content did not, since an order learned on ARC recovered 177 rules against 194 for a static order." | "recovered" means recovered exactly, of 595; the audit says "counted from ARC training tasks" (`records/audit_20261108/COMPLETE_COMPANION_RESEARCH_AUDIT.md` line 122) | "an order counted from ARC tasks recovered exactly 177 of 595 rules against 194" | P1 | +4 |
| E21 | 56 | "A bounded diagnosis loop on 256 constructed Boolean tasks, not ARC puzzles, tied a strong fixed schedule (219 each), though routing by the diagnosed failure used 12.9% less search work, an initial measured signal that reading the failure helps choose (descriptive, post hoc)." | "219 each" unlabeled (recovered exactly, of 256); the binding audit marks this wording FAIL (`COMPLETE_COMPANION_RESEARCH_AUDIT.md` line 120) | "A bounded diagnosis loop recovered exactly 219 of 256 authored Boolean functions, not ARC puzzles, as did a fixed build-then-ask schedule, ..." with the brief's W2 for the rest | P0 | +2 |
| E22 | 56 | "The decisive test routes revisions by the real failure against static access to the same revisions, shuffled routing and equal cost, on real ARC answers." | "answers" means correct test outputs on real ARC tasks | "scored by correct test outputs on real ARC tasks" | P2 | +5 |
| E23 | 64 | "**Accuracy.** 0.83% (CORA only); 24.03% (neural comparison, credited to NVARC)." | set not named | "Kaggle scores on 120 hidden tasks: ..." | P1 | +5 |
| E24 | 65 | "**Universality.** One pipeline in seven domain families; 101 against 66 gene rules." | denominator and term | "101 against 66 of 595 gene rules recovered exactly" | P1 | +4 |
| E25 | 66 | "**Progress.** 64 against 38 tasks with less compute; 227 against 118 held outputs." | denominators and term | "64 against 38 of 95 tasks correct ...; 227 against 118 of 624 held-out test outputs correct" | P1 | +7 |

Uses that are already right in sense: line 7 "it rarely answers" (coverage), line 13 "propose answers" (candidates),
line 21 "answers only if", line 33 "it answered 3 of 172", line 48 "never the answer".

**Word budget.** The P0 items add about 92 words (E1 +37 net, E17 +15, E2 +11, E19 +8, E7 +6, E6 +4, E13 +4, E15 +3,
E4 +2, E21 +2). The Writeup has 30 words of room (1,470 of 1,500) and the brief's cuts C1 and C2 free 12 more
(`INSERTION_BRIEF.md` lines 695-696), so about 50 words must still be cut elsewhere, or the P0 texts shortened. E15's
text assumes the (a) sentence carries "3 of 172". P1 and P2 items also apply to Paper 1, which carries the same
wording (`cora_final.tex` lines 85-88, 480).

## Conflicts flagged (where an audit is involved, the first audit wins)

1. `INSERTION_BRIEF.md` line 692 (W1) keeps "every other arm" and "solves": an internal label and an undefined word.
   Use the (d) text.
2. `INSERTION_BRIEF.md` lines 91, 95 (P2-A2) and 716 (registry row) cite `FINAL_DECISION.md` line 23 for "no
   CORA-only configuration solved any of the 120" (0 of 120); that statement is at
   `experiments/cora_cast_20261026/M2_REWRITE_REPORT.md` line 8 (and `FINAL_DECISION.md` line 11). Line 23 is the
   design-exposed feasibility row, a correct source only for design exposure (as in brief line 81).
3. The first audit calls the 31 Oct run a "local offline rehearsal" (`NATURAL_ARC_CONSTRUCTION_REVIEW.md` lines
   19-20, 160). Its neural predictions came from a Kaggle GPU run; only CORA's step and the merge ran on our machine
   (`NOV2_FINAL_SUBMISSION_STATUS.md` lines 58-63). The audit's numbers stand; name the run plainly.
4. Registry row 319 maps the Writeup's 0.83% to a public-evaluation rehearsal of an older build (section (a)).
5. Writeup line 50 against the 433 audit (E19), and line 56 against the main audit (E21).
6. `JUDGE_READ_WRITEUP_v2.md` line 35 infers that CORA's correct answers are disjoint from the neural model's; the
   records show 2 of 3 shared (c).

Item 1 is the brief's proposed text against the task's wording rules, not a disagreement between the two audits; item
6 is a simulated reader, not a record. Neither should be copied into the papers.

## Not established from records (UNKNOWN), and what would settle it

| Question | What would settle it |
|---|---|
| Hidden test outputs the CORA-only entry answered, and how many were correct | nothing available: Kaggle returns only scores |
| Whether CORA replaced any second attempt in 57867631 on hidden tasks, and the sign of its effect | the hidden rerun's merge report (not returned), or a paired neural-only submission (submissions closed 6 Nov) |
| Overlap of the two entries on hidden tasks | per-output hidden results, not available |
| Whether Kaggle averages over tasks or over test outputs | the competition's published metric code; the three scores fit a mean over 120 tasks |
| What the "28" in "23 against 28" counts | the construction closeout's excluded-task table (inbox 0203) |
