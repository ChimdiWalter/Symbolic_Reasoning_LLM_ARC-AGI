# Rule-language version 5: engineering comparison (25 October 2026)

**NOT FROZEN. Engineering evidence on newly generated tasks, plus one private Kaggle development run on the 120
public evaluation puzzles (development evidence only).** No protocol was registered before this comparison; the
tasks, arms and metrics were chosen by the builder; no ledger verdict changes because of it (ledger row M13 stays
pending).

## Summary

- On 40 generated target tasks (10 per capability), version 5 is right on 40 at 3,000 candidates; version 4 on 20,
  version 4 given the same CPU on 20, version 3 on 17. Version 5 against version 4: 20 gains, 0 losses.
- All 20 gains are classified as expressivity: they are the stamp tasks (10 of 10 against 0 of 10) and the tasks with
  rays that recolour the obstacle they hit (10 of 10 against 0 of 10). Version 4 with ten times the candidates and
  CPU generated none of these 20 answers.
- The other two capabilities add nothing measurable on their scenes: version 4 already solves every segment task and
  every enclosed-fill task.
- No loss on version 4's own tasks: 14 of 14 for version 4 and for version 5 (version 3: 9).
- The correct prediction is generated first and ranked first wherever version 5 is right. Changed-cell agreement on
  the targets is 1.000 against 0.500. Of all programs that fit the demonstrations, 81.7% predict the test exactly
  (version 4: 66.7%).
- Cost per task (medians): 14.0 s CPU against 10.3 s for version 4, and 5,583 native executions against 2,100.
- The targets are written in version 5's own language, so this shows that the capability works where it applies, not
  that it helps on real puzzles.
- On the 120 public evaluation puzzles (Kaggle development run; development evidence only) version 5 scores 0 of 120,
  the same as versions 3 and 4 and native CORA: 0 gains and 0 losses. **The engineering gate is NOT MET.** A version 5
  rule fitted the demonstrations of one puzzle (97d7923e), but no kept prediction was exact on its test.

## What version 5 adds

Version 5 (`cora_neural_v2g5/`, level L1: the operations are designed by hand) extends version 4 by import only;
version 4 stays frozen at commit 6baf61b. It adds four rule types to version 4's cover vocabulary:

- **stamp**: a copy of one source object's pattern placed at anchor points chosen by evidence (other objects or
  marker cells), aligned by top-left corner, centre or marker cell, in its own colour or the anchor's;
- **ray with obstacles**: a ray from each selected object that stops at the first obstacle (optionally recolouring
  the obstacle cell it hits, or the whole obstacle object) or turns clockwise or anticlockwise there;
- **segment**: a horizontal or vertical segment between the facing sides of two selected objects that are in line;
- **relational fill**: background cells enclosed by the selected objects (not reachable from the grid edge), or lying
  between two of them.

Rules are found with version 4's mechanism. The changed cells of the demonstrations suggest a candidate shape; the
objects are partitioned into members (must be selected), don't-care objects and excluded objects; the selector is
induced with may-sets and confirmed by native execution; each rule is executed alone on every demonstration and is
kept only if every cell it writes equals the output there. Programs are covers of the changed cells, alone or after a
partial program, and every cover contains at least one version 5 rule (version 4's own covers come from version 4's
constructor, which version 5 also runs). Search keeps version 4's budget accounting: the budget counts candidate
evaluations; construction is not counted as candidates, and its native executions are reported separately.

## Tasks

Newly generated DEV-style tasks; their seeds are disjoint from the unit tests' seeds. No evaluation puzzle was used.

- 40 target tasks, 10 per capability (`tests/g5_generators.py`; three demonstrations and one test input each):
  - *stamp*: one five-cell plus and two or three single-cell markers; the output stamps a copy of the plus centred on
    each marker, in the marker's colour;
  - *ray*: a vertical wall and three dots left of it; each dot sends a ray to the right that stops at the wall and
    recolours the wall cell it hits in the dot's colour;
  - *segment*: two pairs of same-coloured dots, each pair in one row or one column; the output joins each pair;
  - *fill*: one or two boxes, each made of four separate bars around a hole; the output fills each enclosed hole.
- 14 control tasks: two per version 4 test case (parts of objects, regions, rays: version 4's own language), to see
  whether version 5 loses anything where it adds nothing.

These targets are written in version 5's own language, so they show that the capability works where it applies, not
that it helps on real puzzles (the same limitation as version 4's synthetic study).

## Arms

Each arm is a complete search on each task, run on one shared server with 2 worker processes at low priority. CPU
is process CPU time.

| arm | what it is |
|---|---|
| version 3 | version 3 search, 3,000 candidates |
| version 4 | version 4 search, 3,000 candidates |
| version 5 | version 5 search, 3,000 candidates |
| version 4, same CPU | version 4 given version 5's CPU time on the same task (budget 20,000 candidates, stopped at that CPU time) |
| version 4, ten times | version 4 with 30,000 candidates and ten times version 5's CPU; run only where version 5 was right and neither version 4 arm generated the answer, to classify the gain |

## Metrics

- **pass@2**: one of the two attempts equals the answer.
- **coverage**: one of the kept predictions (up to 50 distinct predictions of fitting programs) equals it;
  **generated**: any program that fits the demonstrations predicts it.
- **first correct candidate**: the candidate number, in generation order, of the first fitting program whose test
  prediction is exact (median over tasks where one exists); and the rank of the correct prediction among the distinct
  predictions in selection order (attempt 2 is chosen with a diversity rule, so rank 2 is not always attempt 2).
- **changed-cell agreement**: of the cells that must change (the answer differs from the test input there), the share
  an attempt gets right; the better of the two attempts, then the first attempt alone; a task without attempts scores
  0. Overall pixel agreement is not used, because most cells of a test grid do not change.
- **fit-to-test generalization**: of all programs that fit every demonstration, the share whose test prediction is
  exact, pooled over tasks. Every fitting program is counted, through a wrapper around each version's selection call
  that records its arguments and returns its result unchanged.
- **gain kind**, for a task that version 5 solves and a version 4 arm does not:
  - *selection*: that arm generated the answer but did not choose it;
  - *construction*: version 4 generated it at some compute (any version 4 arm), or version 5's correct attempt uses
    only version 4's rule types;
  - *expressivity*: the correct attempt needs a version 5 rule type and no version 4 arm, up to ten times the
    compute, generated the answer. This is operational (a search failure), not a proof that no version 4 program
    exists.

## Results

Target tasks (40; generated in version 5's language):

| arm | pass@2 | coverage | generated | changed-cell agreement (better / first) | first correct candidate (median) | correct prediction's rank 1 / 2 / >2 / none | fit-to-test (exact / fitting programs) | CPU s (median) |
|---|---|---|---|---|---|---|---|---|
| version 3 | 17 / 40 | 17 | 17 | 0.448 / 0.448 | 14 | 16 / 1 / 0 / 23 | 0.825 (104 / 126) | 8.7 |
| version 4 | 20 / 40 | 20 | 20 | 0.500 / 0.500 | 1 | 20 / 0 / 0 / 20 | 0.667 (194 / 291) | 10.3 |
| version 4, same CPU | 20 / 40 | 20 | 20 | 0.500 / 0.500 | 1 | 20 / 0 / 0 / 20 | 0.679 (218 / 321) | 14.8 |
| version 5 | 40 / 40 | 40 | 40 | 1.000 / 1.000 | 1 | 40 / 0 / 0 / 0 | 0.817 (759 / 929) | 14.0 |

Control tasks (14; version 4's own cases):

| arm | pass@2 | coverage | generated | changed-cell agreement (better / first) | first correct candidate (median) | correct prediction's rank 1 / 2 / >2 / none | fit-to-test (exact / fitting programs) | CPU s (median) |
|---|---|---|---|---|---|---|---|---|
| version 3 | 9 / 14 | 9 | 9 | 0.667 / 0.667 | 46 | 9 / 0 / 0 / 5 | 0.172 (277 / 1,607) | 6.2 |
| version 4 | 14 / 14 | 14 | 14 | 1.000 / 1.000 | 1 | 14 / 0 / 0 / 0 | 0.311 (633 / 2,034) | 8.3 |
| version 4, same CPU | 14 / 14 | 14 | 14 | 1.000 / 1.000 | 1 | 14 / 0 / 0 / 0 | 0.178 (771 / 4,332) | 12.6 |
| version 5 | 14 / 14 | 14 | 14 | 1.000 / 1.000 | 1 | 14 / 0 / 0 / 0 | 0.365 (860 / 2,358) | 10.3 |

pass@2 by capability (target tasks):

| capability | tasks | version 3 | version 4 | version 4, same CPU | version 5 | gains over version 4 |
|---|---|---|---|---|---|---|
| stamp | 10 | 0 | 0 | 0 | 10 | 10 expressivity |
| ray with obstacles | 10 | 0 | 0 | 0 | 10 | 10 expressivity |
| segment | 10 | 8 | 10 | 10 | 10 | none |
| relational fill (enclosed) | 10 | 9 | 10 | 10 | 10 | none |

**Gains and losses.** Target tasks: version 5 against version 4, 20 gains and 0 losses; against version 4 given the
same CPU, 20 gains and 0 losses; against version 3, 23 gains and 0 losses. All 20 gains over version 4 are
expressivity: in each, the correct attempt uses a version 5 rule, and neither version 4 arm generated the answer.
Version 4 with ten times the candidates and CPU (30,000 candidates; median 63.7 s CPU) also generated none of them.
No gain is construction or selection. Control tasks: no gain and no loss against either version 4 arm; 5 gains and
0 losses against version 3 (version 4's own gains, which version 5 keeps).

**Cost.** Median native executions per task, counting construction and the leave-one-out checks of selection (for
version 5 this includes version 4's construction, which it also runs): 5,583 for version 5 against 2,100 for version 4
on the target tasks, and 7,537 against 4,440 on the controls. Version 5's own execution checks (each rule run alone on
every demonstration) have medians of 156 and 93 per task. Median CPU per task is 14.0 s against 10.3 s (target) and
10.3 s against 8.3 s (control). The longest version 5 search took 40.9 s. The run took 37 minutes with 2 workers.

**Determinism.** A first pass was interrupted after 18 tasks to add metrics. Its pass@2 and coverage are identical,
for every arm, to the complete run's on those 18 tasks. The 22 unit tests pass (`tests/test_neural_cora_v2g5.py`).

## Reading

- Two of the four capabilities carry the whole gain: stamps, and rays that recolour the obstacle they hit. No
  version 4 arm, up to ten times the compute, generated one of these answers, so the gain does not come from budget.
  In the operational sense used here, it is new expressivity.
- Segments and enclosed fills were already within reach on these scenes. Version 3's native line drawing and
  version 4's construction find the segments, and version 4's hole regions find the fills. Version 5's own segment
  and fill rules also fit these tasks, but selection chose a version 4 or native program with the same prediction in
  19 of the 20. Fills between objects, and segments between larger objects, might add expressivity elsewhere; that
  was not measured.
- Nothing was lost. Wherever version 4 or version 5 is right, the correct prediction is ranked first. The extra
  programs that version 5 constructs mostly predict the test exactly: fit-to-test generalization rises from 0.667 to
  0.817 on the targets and from 0.311 to 0.365 on the controls. So the wider vocabulary did not add ambiguity on
  these tasks.
- The price is about 1.2 to 1.4 times version 4's CPU and 1.7 to 2.7 times its native executions.
- Limits:
  - The same author wrote both the rules and the generators that produce the target tasks.
  - The scenes are clean; each task has three demonstrations and one test input.
  - Version 4's synthetic study gave evidence of the same kind (97.3% against 15.4%), and it did not carry over to
    real puzzles.

## Engineering gate for the Kaggle development run

The development run on the 120 public ARC-AGI-2 evaluation puzzles is judged against this gate. The gate was written
before the run's result was read. The run PASSES only if all three conditions hold:

1. **At least one new exact prediction attributable to version 5.** Variant G5 predicts at least one test output
   exactly, with either attempt under the entry's attempt policy. No earlier CORA-only configuration predicted that
   output: G3, C1 and C2 each scored 0 of 120 on 22 October. And the correct attempt's program contains a version 5
   rule, which is checked in `cora_rows.json`.
2. **No comparable loss.** G5 does not lose an exact prediction that an earlier CORA-only configuration or native
   CORA made. All of them made none, so this condition cannot fail on solved puzzles; the record says so rather than
   counting it as evidence. Searches stopped by a limit are reported against G3's 7 of 120.
3. **Within budget.** G3's limits per puzzle apply: 3,000 candidates, 120 s soft CPU, 300 s hard CPU and 600 s of
   wall time. The notebook must also stay within its 12-hour limit, offline and on CPU only.

These 120 puzzles are exposed: the gap analysis that chose these capabilities read their failures. Any result there
is development evidence only. It is expected to be optimistic, and it changes no ledger verdict. The research gate,
a gain on an independent cohort against the strongest matched baseline, is not addressed here.

## Kaggle development run

- Kernel: `chimdiwalter/cora-only-g5-dev-eval`, version 1. It is private, offline and CPU-only, and it was pushed on
  25 October 2026 at 21:24:49 UTC. Dataset: `chimdiwalter/cora-only-g5-solver-2026`, private.
- Package: built by `python kaggle/cora_original_2026/build_package.py --g5`, which passed the provenance audit
  (tarball sha256 562187edd7fdd1f49ed29e2a69d658fc886e244adf34945c73814d28ffc76e56). It holds the unchanged native
  engine and the typed packages, including `cora_neural_v2g5/`. The CORA-ONLY-G3 dataset and kernels are untouched,
  and G3 remains the entry's default configuration.
- Configuration: `K_MODE=dev`, `K_VARIANTS=G5`. As in G3, native CORA runs first. Then the version 5 search runs on
  every puzzle, with G3's limits and attempt policy.
- Reference, G3 development run A (22 October): 0 of 120 (0.0%). Of its searches, 113 finished and 7 stopped at the
  CPU limit. No puzzle had a fitting program, and the run took 9,659 s.
- Status: COMPLETE. The run ended by 23:54 UTC on 25 October. Its output is in `outputs/kaggle_dev_g5/output`, which
  is not tracked. It was scored by `python scripts/kaggle_dev_g5_attribution.py SOLUTIONS_JSON`. The solutions file's
  sha256, 84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1, is identical to the one the run recorded.
  No competition submission was made, and none is part of this work.

### Result (development evidence)

All four configurations ran inside the same entry: native CORA first, then the named search, under the same attempt
policy. G3 is development run A and C1 and C2 are run B, both on 22 October; G5 is this run. Runs on different days
use different Kaggle machines, so their CPU figures are indicative only.

| search inside the entry | score (precision / search-first) | puzzles with a fitting program | searches stopped at the CPU limit | median search CPU per puzzle |
|---|---|---|---|---|
| G3: version 3, 3,000 candidates | 0.0% / 0.0% | 0 | 7 | 29.9 s |
| C1: version 3, 10,000 candidates (300 s soft, 600 s hard CPU) | 0.0% / 0.0% | 0 | 1 | 75.6 s |
| C2: version 4, 3,000 candidates | 0.0% / 0.0% | 1 | 13 | 34.2 s |
| G5: version 5, 3,000 candidates | 0.0% / 0.0% | 1 | 6 | 34.6 s |

- **Exact score.** Version 5 scores 0 of 120 (0.0%) under both attempt policies, and native CORA alone scores 0 of
  120 in the same run. Correct predictions that use a version 5 operation: 0.
- **Gains and losses.** Version 5 against version 3 (G3, C1), version 4 (C2) and native CORA alone (0.0% in every
  run): 0 gains and 0 losses in exact predictions. No configuration predicts any of the 172 test outputs.
- **The one fit.** Versions 4 and 5 fit the same single puzzle, 97d7923e.
  - Version 4 found 98 fitting programs there; version 5 found 162.
  - 64 of the 162 are version 5 rules: rays that stop at and recolour the object they hit. That count comes from a
    local rerun of the same search, which reproduces the 162.
  - Version 5 rules give 7 of the 12 distinct predictions kept, but no kept prediction is exact on the test.
  - Both attempts are wrong. They are a native recolouring program and a version 4 part rule, the same pair that
    version 4 chose.
  - So a version 5 rule fitted a real puzzle's demonstrations once, and it did not generalize to that puzzle's test.
    On the other 119 puzzles, no program of any version fitted the demonstrations.
- **Run.** It took 8,660 s in total: native CORA 6,483 s and the version 5 search 2,175 s, inside the 12-hour limit.
  114 searches finished, and 6 stopped at the 300 s CPU limit. No forbidden module was imported, and the submission
  file passed the schema check. In the provenance, the search's attempt slots are labelled G3_FIT_1 and G3_FIT_2 for
  every variant. The one search attempt used here (G3_FIT_1, on 97d7923e) is version 5's.

**Gate verdict: NOT MET.**

1. New exact prediction attributable to version 5: **no**. There are 0 exact predictions.
2. No comparable loss: holds, but trivially, because no earlier configuration had an exact prediction to lose.
3. Within budget: holds. The run took 2.4 h under G3's per-puzzle limits, and 6 searches stopped at the CPU limit,
   against G3's 7.

**Reading.** The synthetic gain (20 tasks that only version 5 could express) did not carry over to the 120 public
evaluation puzzles, as happened with versions 3 and 4 before it. The new rules are found from evidence and fit one
real puzzle's demonstrations, but that fit is wrong on the test. This run does not establish why the gain did not
carry over. The gap analysis's other ranks are still open: output size and frame inference (39 size-changing
puzzles) and grouping (55 puzzles).

**Decision.** A 40 of 40 result on generated tasks does not justify a competition submission. Version 5 made no
exact prediction on the 120 evaluation puzzles, and G3 remains the entry's default configuration. Following the
author's decision, neural generation of complete typed programs (ledger row M11) is now the priority, ahead of
further hand-designed rule types.

## Reproduce

```
python -m pytest -q tests/test_neural_cora_v2g5.py         # 22 tests
python scripts/neural_cora_v2g5_engineering.py run          # 2 workers, low priority; resumable
python scripts/neural_cora_v2g5_engineering.py summary      # summary.json and summary.md
python kaggle/cora_original_2026/build_package.py --g5      # the separate G5 development package
```

Files: `cora_neural_v2g5/` (program, construct, select, search, PROGRESS.md), `tests/test_neural_cora_v2g5.py`,
`tests/g5_generators.py`, `scripts/neural_cora_v2g5_engineering.py`. Rows and summaries are written to
`outputs/neural_cora_v2g5_engineering/`, which is not tracked.
