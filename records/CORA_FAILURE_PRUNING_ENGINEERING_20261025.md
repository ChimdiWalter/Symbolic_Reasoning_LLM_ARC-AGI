# Failure-derived pruning: an on/off test at equal budget (engineering, not frozen)

25 October 2026. Engineering evidence only. This is not a frozen or pre-registered study. It uses no real ARC
puzzles and no Kaggle run. Every task here is a generated development task written in CORA's own rule languages.

## What was tested

When CORA runs a candidate rule and the rule fails, the cells it got wrong also tell CORA about candidates it has not
run yet. Failure-derived pruning turns those wrong cells into constraints. CORA then skips any later candidate that
is certain to fail, without running it. The idea comes from Popper (Cropper and Morel, "Learning programs by learning
from failures", Machine Learning, 2021). In Popper, a hypothesis that is too general rules out its generalizations,
and a hypothesis that is too specific rules out its specializations. Here the evidence is the wrong cells of each
object, and "more general" means "picks more objects", read from the objects each selector actually picks.

Words used here:
- A candidate **picks** the objects its selector selects. CORA's own interpreter computes this set, the **pick set**.
- A candidate **fits** when it reproduces every example output exactly.
- A **correct candidate** is a fitting candidate whose output for the test input is also right.
- **Coverage** at a budget is the number of tasks with a correct candidate among the first that many executed
  candidates.
- **Program-class candidates** are CORA's built-in program types. They open version 2's candidate stream, before the
  object rules.

**Exactly which candidates can be pruned.** Only programs of these two forms can be pruned, and only by evidence
from the same view (c is a literal colour):

    (program VIEW (list (rule SEL (delete))) keep (same_as_input))
    (program VIEW (list (rule SEL (recolor (color c)))) keep (same_as_input))

That is: a single rule, objects not picked kept as they are, the input's frame, and a local action. Nothing else in
the stream is ever pruned, and nothing else is used to learn a constraint. The excluded candidates include:
- programs with two or more rules, and rules with bound variables (`rule_with`);
- colours computed from other objects (`color_of`, `color_map`);
- programs that delete the objects they do not pick;
- non-local actions (moves, copies, composites, lines), other output frames, and the program-class candidates.

No general monotonicity assumption is made. The argument below rests on locality, which holds for these two forms
and is not claimed for any other. `tests/test_cora_neural_prune.py` checks the class on the first 3000 candidates of
one task's stream: the pruning's own class test agrees with an independently written one on every candidate, and
every pruned candidate is inside the class.

Pruning is applied to the candidate stream of rule language version 2
(`cora_neural_v2g2.search.enumerate_programs`), imported unchanged. Versions 3 and 4 also read this stream, but
their own constructed candidates are not pruned, because that would need new versions of those modules.

## The four rules, and why a pruned candidate cannot fit

**Locality.** CORA's interpreter paints every output object over the view's background colour. Every non-background
cell belongs to exactly one object, and views with overlapping objects are excluded. So for this family, the output
on an object's cells depends only on three things: the action, whether the object is picked, and the input.

Take a failed candidate (view V, selector S, action X) and an example on which it got some cells of object o wrong:

1. **Too general.** o was picked. Every candidate with the same view and action that picks o writes the same wrong
   cells, so it is pruned.
2. **Too specific.** o was not picked. Objects that are not picked keep their input cells, so every candidate in view
   V that leaves o unpicked is wrong there. Only candidates that pick o remain.
3. **Must stay unchanged.** o was picked, and the example output equals the input on o. Every candidate that picks o
   with an action that would change it (delete, or recolour to a colour o does not already have everywhere) is
   wrong there.
4. **Dead view.** A wrong cell lies outside every object. No candidate of the family writes such a cell, so no
   candidate of the family in view V can fit.

Each rule points to a cell that the pruned candidate gets wrong, so no pruned candidate fits. The proof and its
assumptions are in `cora_neural_prune/prune.py`: exact pick sets, disjoint objects, and the family's form.

A general "stronger action" order is not implemented, because no sound order exists between, for example, delete
and recolour. Only rule 3, which is sound, prunes across actions.

**Checked by execution.** The tests (`tests/test_cora_neural_prune.py`, 7 passing) run every pruned candidate. In this
experiment, all 10,129 pruned candidates were also run afterwards. None fits.

## How it was measured

- **Tasks.** 170 generated development tasks: ten fresh seeds (1000 to 1009) of each of the 17 development families,
  10 from version 2 and 7 from version 3. Held-out families were not used. The expected test outputs were read only
  for scoring.
- **Arms.** OFF is version 2's stream as it is. ON is the same stream with pruning. "Equal budget" means the same
  number of executed candidates, 3000 in each arm. Pruned candidates are not executed, so ON reads further into the
  stream.
- **Same stream.** Both arms make the same stream call. The program-class prefix is generated under a wall-clock
  deadline, so its fingerprint was compared, and it matched in all 170 tasks.
- **One run per arm.** Each arm ran once at 3000. The figures at 300 and 1000 are read from the positions at which
  candidates were executed. This is exact, because the stream's order does not depend on the budget.
- **Measures.** For each arm: executed candidates to the first fitting candidate and to the first correct candidate;
  coverage at 300, 1000 and 3000; process CPU time; and pick-set runs. Each pick set costs one native run per example
  (three here). Pick-set runs are reported on their own, and a conservative comparison also counts each pick set as
  one more candidate.
- **Machine.** Each (task, arm) ran in its own process, with no shared caches, at nice 10, two at a time, on a shared
  machine with a load of about 32 on 24 cores. CPU times therefore vary by a few percent.
- **Sample size.** The sample size changed once. The plan was two seeds. Those finished in 10 minutes, so the sample
  was extended to ten seeds because the run time allowed it. Per-task progress lines had been seen by then, but no
  summary had been computed. The first two seeds alone give: 24 vs 25 correct at 300; 27 vs 27 at 3000; the first
  correct candidate earlier with pruning in 11 tasks, the same in 16, later in 0; 1,885 pruned, none fits.

## Results (170 tasks)

| budget (executed candidates) | tasks with a fitting candidate, OFF / ON | tasks with a correct candidate, OFF / ON | gains / losses (correct) |
|---|---|---|---|
| 300 | 134 / 137 | 119 / 121 | 2 / 0 |
| 1000 | 140 / 140 | 125 / 125 | 0 / 0 |
| 3000 | 144 / 144 | 127 / 127 | 0 / 0 |

**Lost correct programs: 0.**
- By task: no task had a correct candidate within the budget without pruning and lost it with pruning, at 300, 1000
  or 3000.
- By program: all 10,129 candidates that pruning skipped were executed afterwards, and none fits. So every fitting
  program that OFF executed, ON also executed, at the same or an earlier position.
- In every task, both arms found the same number of distinct fitting outputs.

**Candidates to the first correct candidate.** Both arms found one in 127 tasks.
- With pruning, ON reached it earlier in 53 of the 127 tasks, at the same position in 74, and later in 0. It saved
  1,267 executed candidates in total.
- In 64 of the 127, the first correct candidate is a program-class candidate at the start of the stream
  (position 28 at the latest), which pruning does not touch. In the other 63, the median position moved from 186 to 162, a
  median saving of 15%, and ON was earlier in 53 of them.
- Counting every pick set as one more candidate: earlier in 43, the same in 76, later in 8, with 665 saved.
- The first fitting candidate (144 tasks) came earlier in 48, at the same position in 96 and later in 0, with 1,138
  saved.

**Cost.**
- Total CPU: 1,585 s OFF and 1,560 s ON (ratio 0.98).
- CPU to the first correct candidate, ON divided by OFF: median 1.01, quartiles 0.97 and 1.05. In the 63 tasks past
  the program-class prefix the median was 1.02, and ON was slower in 43 of them.
- Pruned candidates: 10,129, which is 1.9% of the 520,129 that ON read. Pruning acted in 102 of the 170 tasks. By
  rule: too specific 5,865; dead view 2,095; too general 1,804; must stay unchanged 365.
- Pick-set runs: 8,511 (2,837 pick sets). Executing the pruned candidates for the check took 17 s, outside the timed
  arms.

**Where it acts.** Six families gain. In each of them, the correct program is a single delete or recolour rule in
the object part of the stream: `feature_map_recolour`, `most_common_recolour`, `negated_selector_delete` and
`relational_feature_recolour` (version 2); `v3d_bind_adopt_nearest_ring` and `v3d_ctrl_ring_recolour` (version 3).
Nothing changes elsewhere. Both coverage gains at 300 are from `most_common_recolour`.

## What it means

- **Sound in practice as well as on paper.** None of the 10,129 pruned candidates fits.
- **The direction is guaranteed; the size is what was measured.** Pruning is sound and both arms read the same
  stream, so at an equal executed budget ON can never reach a correct candidate later than OFF. With pruning, the
  first correct candidate came earlier in 42% of the tasks that have one, with about 15% fewer candidates where
  pruning acts.
- **More puzzles solved only at the smallest budget.** At 300, 2 more of 170 tasks were solved. At 1000 and 3000
  nothing changed, because the first correct candidate is usually either early or out of reach at any of these
  budgets. Pruning removes only candidates that do not fit, so it cannot help choose among fitting candidates (17
  tasks have a fitting candidate but no correct one).
- **No CPU gain.** Version 2's candidates are cheap, about 1 ms each, which is roughly the cost of a pick set. The
  pick-set runs cost back what the saved candidates would have cost. Pruning should pay off where executing a
  candidate costs much more than computing a pick set, as with multi-rule, constructed or non-local candidates in
  versions 3 to 5. That is untested.
- **Novelty.** The idea is Popper's. What is adapted is the ordering (pick sets of typed object selectors) and the
  evidence (wrong cells per object). Ledger row M16 records it as an L1/L2 candidate, PRIOR_ART_OVERLAP, verdict
  pending.

## Limitations

- The tasks are generated in CORA's own languages. There are no real puzzles, and the study is not frozen.
- One stream (version 2) is pruned. The family is limited to single-rule local actions, and there is no way yet to
  attribute a failure to one rule of a multi-rule program.
- CPU was measured on a loaded shared machine.

## Next falsifying test

Build pruning for the constructed candidates of versions 3 and 4 as new modules, without editing the existing ones.
Then run a pre-registered comparison at matched CPU on real puzzles. The claim fails if coverage at matched CPU does
not improve.

## Files and reproduction

- Code: `cora_neural_prune/` (`prune.py`, `search.py`, `PROGRESS.md`); `tests/test_cora_neural_prune.py`;
  `scripts/cora_failure_pruning_ablation.py`.
- Raw results, one line per (task, arm): `records/cora_failure_pruning_20261025/ablation_shard0.jsonl` and
  `ablation_shard1.jsonl`. Aggregate: `records/cora_failure_pruning_20261025/ablation_summary.json`.
- Reproduce: `nice -n 10 python scripts/cora_failure_pruning_ablation.py run OUT_I.jsonl I/2` for I in 0 and 1,
  then `python scripts/cora_failure_pruning_ablation.py summary OUT_0.jsonl OUT_1.jsonl`.
