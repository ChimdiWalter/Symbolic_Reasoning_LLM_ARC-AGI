# Operations from blocks below the library: results

Author: Chimdi Walter Ndubuisi. 15 November 2026.

**Audit status (15 November 2026).** The independent review audited the saved numbers and the custody of this run
on the day it ended, without running any project code: both pass, and the declared criterion is not met. It
confirmed the reading of the three favourable operations given below and the slip recorded in section 1, and
asked for four documentary changes, which are applied and listed in section 10. The run is closed and is not
replayed. Agreement on a finite panel stays distinct from recovery of an operation's full meaning, and from
accuracy on ARC tasks, transfer or autonomous growth.
The appendix is written by `results_tables/render_results_tables.py` from the run's records and is appended to
this file unchanged; no number in it was typed by hand. The run's numbers in the text above it are taken from it;
the numbers of the design (blocks, examples, budgets, limits) are the protocol's.

## 0. Summary

**The declared criterion is not met.** The comparison was fixed before any outcome. An operation of the library is
hidden with its whole family and is known only through 36 examples of its inputs and outputs. One system searches
the remaining library, first up to four nodes and then up to five. The other may also use 68 smaller blocks below
the library, up to four nodes. Both are allocated the same number of candidate combinations. On the 80 eligible
operations outside the development names whose source body has at least seven nodes, the system with smaller
blocks rebuilt 10 and the library alone 7. Three operations are favourable (`difference`, `rot270`, `rot90`) and
none is unfavourable. The exact two-sided sign test gives p = 0.25, above the declared 0.05. The calibration was
valid and passed (19 of 19 controls; 18 were needed) and the cohort is complete, so the result can be read, and it
reads: the prespecified superiority criterion was not met under these blocks, examples and limits. That does not
mean that the blocks add little, and it does not mean that the two systems are equivalent.

**One amendment was made before any outcome and is part of every report of this experiment.** The protocol's
drafts required at least 20 calibration controls. The setup pass over all operations gave 19. The author lowered
the minimum to 19 on 15 November 2026, after that count was known and before any search outside the development
names or any outcome on a control. Section 1 gives the details.

What the three favourable operations consist of. `rot90` and `rot270` are each a composition of two blocks, a
transposition and a reversal. `difference` is rebuilt by one block, Python's set difference, which is the operation
itself for sets: a rebuild by the declared rule, and not a composition.

Where both systems were wrong. Both selected the same three wrong expressions, for `extract`, `paint` and
`underpaint`. Each fits all 36 examples and agrees with the operation on all 30 inputs of the final panel that come
from the same generator. Only the inputs pooled from other draws expose them.

How the searches ended. Every four-node search that found nothing completed its size limit with no cap reached:
under the declared merging of expressions with equal values and the declared types, the implemented enumeration
was run to its end. That is a limit of search coverage. It is not proof that these operations cannot be expressed.
Every fruitless five-node search of the library ended by its budget of combinations inside the fifth level.

Level. At best this restores removed operations from a restricted language that was chosen by reading the
library's own source. It is a result about rebuilding removed library operations from examples of their own
inputs and outputs. It says nothing about accuracy on ARC tasks and nothing about autonomous growth. No rung of
the project's plan is earned by this run.

## 1. What was run

**The question** (protocol, section 1). At a matched allocated search budget, counted in candidate combinations,
does a fixed two-stage search that may also use blocks below the library rebuild more of the hidden operations
than a fixed two-stage search of the library alone that goes one node deeper?

**Terms.**

- *The library* is every library operation outside the hidden family, with the grammar's named constants.
- *The blocks* are a restricted language below the target operations: 68 small functions (a length, a first
  element, a reversal, a set union, a comparison, a map over a tuple, and so on), eager, immutable and without
  variables, together with seven higher-order library operations that are kept (`compose`, `chain`, `matcher`,
  `rbind`, `lbind`, `power`, `fork`). The blocks were chosen by reading which constructs the source of the whole
  library uses, the targets' bodies included. No block carries a target's name, and several blocks are equivalent
  to a short target operation, which is why the primary is read on the stratum of longer source bodies.
- A *search* is a typed bottom-up enumeration by size that merges expressions with equal typed values on the
  examples in use and returns its first fit in a fixed order. Six searches run for every target, each with a fresh
  state:

| search | what it may use | examples | size limit (nodes) |
|---|---|---|---|
| L4-9 | the library | 9 | 4 |
| LC4-9 | the library and the blocks | 9 | 4 |
| L4-36 | the library | 36 | 4 |
| L5-36 | the library | 36 | 5 |
| LC4-36 | the library and the blocks | 36 | 4 |
| C-36 | the blocks | 36 | 4 |

- *Library only* is the system that selects the first fit of L4-36, else that of L5-36, else nothing. *Smaller
  blocks* is the system that selects the first fit of LC4-36, else that of C-36, else nothing. A selection is made
  on fit alone and is sealed before the final panel is opened. A selected expression that is wrong on the final
  panel remains the system's answer.
- *Found*: the first expression of a 36-example search that agrees with the hidden operation on all 36 examples.
  *Right*: it agrees, as typed values, on every input of the final panel. *Wrong*: it does not. *Rebuilt by a
  system*: the system's selected expression is right.
- *The final panel* of a target is 30 further examples from the generator followed by the usable inputs of a slice
  pooled from other draws (at most 400). No search sees it.
- *The budget* of a search is N = 1,900,000 offered argument tuples, counted by the enumerator; each system is
  allocated 2N for a target. A search that ended by the budget counted and offered exactly N argument tuples.
  Processor time is a safety limit only (600 seconds for a search); reaching it would be an infrastructure stop.
- *The longer stratum* is the operations whose source body has at least seven census nodes; *the short stratum*,
  at most six. The strata were fixed from the census of the library's source before any search.

**Kind of study** (protocol, section 0). A development comparison on a known constructed benchmark. Every operation
of this library has been through three earlier studies (the operations study and the visible-failure study of 13
November, and the run of 14 November on evidence across several failures); their outcomes were
known, and the whole library's source informed this design. No number here is an untouched test. The examples are
teacher examples of a known missing operation, supplied by the evaluator; the system does not infer what a failure
means. The study is about finding programs. It does not test diagnosis of a failing step, autonomous growth,
admission, retention, reuse or transfer. CPU only, invented inputs, no model.

**Freeze, review, launch.** The protocol, sources, tests, strata, control names, witness manifest and setup record
were frozen by hash on 15 November 2026: `FREEZE.json` 391915c4...7144, commit 336eed8f8; setup record
`SETUP_RECORD_ALL_2.json` 1c7018c4...1732; `PROTOCOL.md` b7d8052e...cd5a. The independent review read the design
before any code and passed the exact freeze before the launch. The full roster was launched once, at 13:25:49Z on
15 November 2026, as detached job `bl1_full`, and ended with exit 0 at 17:14:33Z. The receipt
`RECEIPT_ALL_ROSTER.json` (37cd4903...6081, read-only) was written before the first target. The run is not
resumed, reset or replayed.

**The amendment of the calibration minimum** (protocol, section 9, stated here as that section requires). The
calibration set is the pinned known-answer controls that are eligible in the committed setup record and whose
witness, the source expression lowered by hand into the blocks, has at most four nodes. Its size K is committed
with the freeze. The drafts required K of at least 20. The setup pass over all names gave K = 19: of the 28 pinned
controls, 4 are excluded by the generator, which finds too few distinct inputs for them (`even`, `positive`,
`toivec`, `tojvec`), 2 are excluded for too few usable pooled inputs (`maximum`, `minimum`), and 3 are eligible
with witnesses of five or six nodes (`valmax`, `valmin`, `leastcommon`). With a minimum of 20 the calibration
could not have been valid and the primary could only have read "not interpretable". The author lowered the minimum
to 19 on 15 November 2026, after that count was known and before any search outside the development names or any
outcome on a control. The rule for K, the controls, the witnesses, the blocks, the exclusions and the required
share (0.9) are unchanged. The calibration then passes with at least 18 of 19 right: one failure is allowed where
20 controls would have allowed two. This is a limited procedural repair. It is not a claim that the two
calibrations are statistically the same, and the frozen protocol is the amended one. The independent review
supported the amendment before the freeze. The setup pass was made again on the amended source and gave the same
cohort (`setup_reconcile_1_2.json`).

**The cohort, committed before the run.** 145 operations, 20 of them development names. 125 are eligible and 20 are
excluded at setup. Outside the development names: 80 of the 90 longer operations are eligible (10 have too few
usable pooled inputs) and 28 of the 35 short ones (4 excluded by the generator, 3 for too few usable pooled
inputs). Of the development names 17 are eligible (`sign` and `vfrontier` have too few usable pooled inputs; all 66
generator examples of `rapply` hold a function inside a container argument and are unusable). These are exclusions
from the cohort; they are not operations that a search failed to build. The primary is read on the 80.

**The run and its checks.** The appendix section "Run" gives the counts, the denominators, the costs and the nine
checks of `after_run_bl.py`, all of which pass: the freeze still verifies; one read-only receipt names the freeze,
the setup record and the output folder; the job started once and ended with exit 0; the run's manifest names the
freeze, the setup record, the whole roster and the frozen policy; there is one record for every listed target and
no other; every journal holds its path's events and seals in order; the stored summary equals one made again from
the records; the calibration set equals the one committed with the freeze; the setup decisions and counts equal the
committed record. 125 records are done, 20 excluded, none incomplete. The primary is not provisional.

**Resources.** Whole job, from the outer timing record: 13,572.99 seconds of user time and 143.71 of system time, 3
hours 48 minutes 44 seconds elapsed, peak memory 2,737,936 kB. One process in one CPU slot. No GPU, no model.

**Budgets and guards in this run.** No search reached a safety limit: the longest took 87.26 processor seconds
(`move`, the four-node search with blocks) against 600. No search ended at the cap on bank entries or at the cap on
function-valued entries. No final check ran out of time, no guarded step lacks its mark, and by the recorded times
no guard of 20 seconds can have fired for any of the 145 targets. Of the 750 searches of the 125 done targets, 178
found a fit, 467 completed their size limit with no cap reached, and 105 ended by the budget of combinations; the
105 are the fruitless five-node searches of the library, all of them.

**Comparison with the operations study** (protocol, section 9; `EARLIER_RESULT_CHECK.json`). The four-node library
search on 36 examples is the search of that study's second condition. Of the 145 operations, 125 are compared and
agree (the same expression for 18, none found by either for 107), none differs, and 20 are not compared because
they are excluded here. The 18 include the four wrong expressions of that search (`extract`, `first`, `paint`,
`underpaint`): the earlier study met the same ones.

**A slip found after the run.** After the freeze and before the launch, a script that prints the found expressions
for reading was added to the folder under a name ending in `_bl.py`. A frozen test of the folder requires every
such file to be a file of the freeze, so that one test failed on the folder from then on, and the suite was not run
again after the file was added. Nothing imports the script and the run executes no test, so the run is not
touched; but "the suite passes on this folder" was not true of the tree at the launch for that one test. It was
found by the author after the run, repaired by renaming the script with its bytes unchanged
(`read_expressions.py`, commit b33577f3a), and reported to the independent review the same hour. The whole suite
then passed on the post-run tree (451 passed; the log is `BUILD_PROGRESS.txt`).

## 2. Primary comparison

Longer stratum, outside the development names, 80 targets, all with a complete record (appendix, "Primary
comparison").

| | right | selected and wrong | selected nothing |
|---|---|---|---|
| Library only | 7 | 3 | 70 |
| Smaller blocks | 10 | 3 | 67 |

- Rebuilt by both: `asobject`, `hconcat`, `leftmost`, `lowermost`, `product`, `rightmost`, `uppermost`, with the
  same expression in both systems for each.
- Rebuilt by smaller blocks only: `difference`, `rot270`, `rot90`. They are of two kinds and are named apart: two
  compositions of two blocks (`rot90`, `rot270`) and one direct alias (`difference`, a single block that is the
  operation itself for sets; section 5, item 3). Rebuilt by library only and not by smaller blocks: none.
- Exact two-sided sign test on 3 against 0: p = 0.25. With none against, six favourable operations would have been
  needed for p below 0.05 (five give 0.0625).
- The four parts of the criterion: more favourable than unfavourable, true; p below 0.05, false; calibration valid
  and passed, true; cohort complete, true. The criterion is not met.

The p-value is the declared decision rule for this finite benchmark. The operations of one library are related, so
it is not evidence about a population of operations.

## 3. Calibration

K = 19 and all 19 witnesses agree with their operations on the 36 examples and on the whole final panel, so the
calibration is valid. The search of the blocks alone was right for 19 of the 19 (18 were needed), so it is passed
(appendix, "Calibration"). The 19 controls validate short expressions of plain blocks, one to four nodes. They
validate nothing about longer or higher-order programs, and they are not evidence about the whole library.

## 4. Secondary readings (descriptive, uncorrected)

None of these can replace the primary or carry a headline. The tables are in the appendix.

**The short stratum is the calibration, read again.** Of the 28 short operations outside the development names,
smaller blocks rebuilt 20 and library only 7 (13 against 0). All 20 are pinned controls: the 19 of the calibration
and `valmax`. The blocks hold a counterpart of each of them by design. None of the six short operations that are
not controls (`adjacent`, `cover`, `mpapply`, `portrait`, `shape`, `subgrid`) was rebuilt by either system. For the
same reason the table over all strata (30 against 14 of 108) is carried by the controls and says nothing beyond the
primary and the calibration.

**By length of the source body.** 7 to 15 nodes: 8 against 6 of 32 (`difference`, `rot90`). More than 15 nodes: 2
against 1 of 48 (`rot270`).

**The stages.** In the longer stratum the five-node library search added nothing to the four-node one (7 and 7; all
10 selections of the library-only system come from its first stage). Over all strata it added one right expression
(`contained`, a control). The search of the blocks alone never selected: wherever it found a fit, the four-node
search with blocks had found one first. There is no target where the four-node library search is right and the
search with blocks ended by its budget.

**Nine examples against 36.** In the longer stratum the four-node library search gave 7 right and 12 wrong first
fits on nine examples, and 7 right and 3 wrong on 36. With the blocks: 10 right and 12 wrong on nine, 10 right and
3 wrong on 36. In each, nine first fits that were wrong on nine examples became no fit on 36, three stayed wrong
(`extract`, `paint`, `underpaint`), and no first fit that was right on nine was lost. None of the nine became a
right one: more examples of the same kind removed wrong answers and did not supply right ones.

**Development names** (development only, never a result): of 17, smaller blocks rebuilt 2 (`color`, `rot180`) and
library only 1 (`color`). The library-only system selected a wrong five-node expression for `other`.

**Costs.** In the longer stratum the four-node search with blocks took 3,194 processor seconds in all and the
four-node library search 795; the five-node library search took 4,099 and the search of the blocks alone 305. A
matched budget of combinations is not equal processor time.

## 5. The found expressions, read

Every found expression of the run was read by the author before any count was reported (`READING_FULL_OUT.md`,
written by `read_expressions.py`; the appendix lists every selected expression). 47 operations have at least one
found expression; 78 run operations have none in any of the six searches. "Right" below is the record's verdict on
the final panel. The explanations are the author's reading of the source.

1. **`rot90` as `c_zip_star(c_reverse(x0))`.** Reverse the rows, then transpose. This is the operation's own source
   text, `zip(*grid[::-1])`, met as two blocks.
2. **`rot270` as `c_reverse(c_zip_star(x0))`.** Transpose, then reverse the rows. Shorter than the source body and
   equal to it: cell (i, j) of both is cell (j, w - 1 - i) of the grid of width w.
3. **`difference` as `c_set_difference(x0, x1)`.** One block, Python's `a - b`. The source body,
   `type(a)(e for e in a if e not in b)`, is the same thing when `a` is a set and also accepts a tuple. The
   expression is right on the panel, so no panel input holds a tuple there. This is the operation under another
   name, restricted to sets. It counts as a rebuild by the frozen rule and is reported with that qualification.
4. **The seven rebuilt by both systems** are compositions of library operations, the same in both systems:
   `asobject` as `merge(partition(x0))`, `hconcat` as `papply(combine, x0, x1)`, `product` as
   `prapply(astuple, x0, x1)`, and the four extremes of a patch as `valmin` or `valmax` of its indices by `first`
   or `last`. The blocks alone also give `product` as `c_frozenset(c_pairs(x0, x1))`, which is not selected because
   the first stage had a fit.
5. **`extract` as `argmin(x0, flip)`, wrong in both systems** (agrees on 283 of 292 final inputs). The expression
   does not use the condition at all: it returns the first element that is not false, or the first element if all
   are. On all 36 examples, and on all 30 generator inputs of the final panel, that is the element the condition
   picks. The pooled inputs expose it (253 of 262).
6. **`paint` and `underpaint` as `x0`, wrong in both systems** (139 and 138 of 430). The unchanged grid fits all 36
   examples and all 30 generator inputs of the final panel: in every one of them the painting changes nothing. The
   pooled inputs expose it (109 and 108 of 400). The generator's own inputs for these two operations do not
   exercise them.
7. **Controls rebuilt by the library alone, and how.** `argmin` as `first(order(x0, x1))`, `equality` as
   `contained(x0, initset(x1))`, `pair` as `papply(astuple, x0, x1)`, `vconcat` as `combine(x0, x1)`, `identity`
   as `x0`. Two are right for reasons worth naming. `totuple` as `order(x0, initset)` sorts by one-element sets,
   none of which is below another, so the order is kept. `contained` as `valmax(x1, matcher(identity, x0))` (five
   nodes, second stage) asks for the largest truth value of "equals x0" over the container; by the source it
   differs from the operation when the container is empty and the value equals 0, so the panel holds no such
   input. "Right" is agreement on a finite panel.
8. **A control the library alone got wrong.** `first` as `argmax(x0, flip)` (204 of 213): the first false element
   if there is one, else the first element.
9. **Controls rebuilt with the blocks.** In the search of the blocks alone, which is the calibration's search, the
   found expression is the witness itself for 17 of the 19. The two others are equivalents met first: `greater`
   as `c_lt(x1, x0)` where the witness is `c_gt(x0, x1)`, and `last` as `c_first(c_reverse(c_tuple(x0)))` where
   the witness is `c_item1(c_max(c_enumerate(x0)))`. The system's selection comes from the four-node search over
   the library and the blocks, and differs from the witness in one more case: `vconcat` is selected as
   `combine(x0, x1)`, because at equal size a library expression is met first. `valmax`, whose witness has five
   nodes and is not counted in the calibration, is rebuilt in four as `c_max(c_map_tuple(x1, x0))`; by the source
   the two differ on an empty container, so the panel holds none.
10. **Development names.** `color` as `first(first(x0))` in both systems. `rot180` as
    `apply(c_reverse, c_reverse(x0))` with the blocks: a library operation applied to a block. `other` as
    `argmin(x0, matcher(identity, x1))` by the library's second stage, wrong (395 of 411).
11. **Nine-example first fits that did not survive 36 examples** are listed in the appendix ("Nine examples against
    36"). Typical: `dedupe` as `x0`, `mostcolor` as `minimum(palette(x0))`, `hline` as `equality(T, size(x0))`.

## 6. What this shows and what it does not

On this benchmark, under these blocks, examples and limits, a search that may also use blocks below the library
did not show the specified gain over a deeper search of the library alone. The difference is three more rebuilt
operations of 80, with no loss, and the declared test does not separate it from chance.

The expressions show what the difference is. Two operations whose source bodies come down to two primitives were
rebuilt from those primitives, and one operation was matched by a block that is the operation itself for sets.
The extra successes consist of these two-block rotations and the direct set-difference block. The length of a
source body is not the length of the shortest program: `rot270` is in the stratum of more than 15 source nodes.
Where the two systems share a wrong answer, the blocks did not correct it, because the selection is made on fit
alone and the first fit is the same expression over the library.

It does not show that blocks below the library cannot help. Another set of blocks, a larger size limit, a search
that is guided, examples that are chosen to tell candidates apart, or another library could behave differently, and
"not met" never means "cannot help". "Not rebuilt" always means not rebuilt within these blocks, sizes, caps and
budgets. Neither outcome would have shown that a guided search is the only next method.

Level (protocol, section 11). At best this restores removed operations, as restoration, from a restricted language
that was informed by the library's source and from seven retained library operations, on one library, with
invented inputs, finite panels and bounded search. It is not an independently discovered core, a new primitive
capability, learning without the source, localization of a failure, growth over cycles, retention or transfer. No
rung of the project's plan is earned by this run.

Limits that hold whatever the outcome. One library; one generator; invented inputs; at most four nodes with the
blocks and five without; one committed setup; known operation families; blocks written by the author with the
library in view. "Right" is agreement of typed values on a finite panel, not proof that the operation was
recovered; items 3, 7 and 9 of section 5 name three expressions that are right on the panel and differ from the
operation, by the source, on inputs the panel does not hold. One run.

## 7. Declared before the run and carried here

- **The calibration minimum** was amended from 20 to 19 before any outcome (section 1).
- **The budget is counted in combinations.** N was set by a rule written before it was applied, from the
  development names. Under a competing load that made each search take 1.6 to 2.0 times the processor seconds,
  the development run was the same in every field except times and memory readings. No search in this run ended
  at a processor-time safety limit; the implemented tuple and size limits determined the recorded endings. That
  does not establish invariance across all machines.
- **The size limit of the searches with blocks is four**, by a numeric rule applied on the development names
  before the freeze: at five and at six nodes every fruitless development search ended by the budget with only
  four nodes completed.
- **Function-making.** A rule on the number of parameters and a cap of 16,000 function-valued entries apply to
  every search. At a limit of four nodes no function is made, so they bear on the five-node library search only.
  The cap was not reached in any search of this run.
- **A container never holds a function** in any search, a declared departure from the earlier studies.
- **A final check that runs out of time** counts as wrong by convention and is listed. There is none in this run.
- **Order of sets** is an interface reading kept apart from "right" (appendix, "Order of sets").
- **Process dependence.** Checks before the run found no difference between processes with changed memory layouts.
  They are finite support, not proof.
- **Known benchmark.** The strata, the controls and the blocks were fixed with the library's source and all
  earlier outcomes in view.

## 8. What it leads to

The protocol (section 13) fixed this in advance for a criterion that is not met with the calibration passed: the
specified gain was not demonstrated under these blocks, examples and limits. The effect, the disagreeing targets
and the practical limits of the searches are to be reported before a next direction is chosen.

- **Effect.** Three more rebuilt operations of 80 (7 to 10); three favourable targets, none unfavourable.
- **The disagreeing targets.** `rot90` and `rot270`, compositions of two blocks; `difference`, one block.
- **Limits of the searches.** In the longer stratum 67 of the 80 four-node searches with blocks found nothing and
  completed their size limit with no cap reached, and 3 found a wrong expression. The five-node library search,
  bounded by its budget, added nothing there. The source bodies of this stratum have at least seven nodes, and
  the searches with blocks reach four. At five and at six nodes the pilot's searches of the blocks, on the
  development names, ended by the same budget inside the fifth level.
- **Wrong answers that fit.** Three of the 13 selections with blocks are wrong, all three because the 36 examples
  do not tell the operation from something simpler, and all three are exposed only by inputs of a different
  origin. This repeats what the earlier studies found about evidence of one kind.

The choice of the next direction is the author's.

## 9. Reproduce

The procedure is in `PROTOCOL.md` (sections 5, 6 and 10) and the commands in `README.md`. Per-target records:
`full_out/targets/`; journals: `full_out/journal/`; summary:
`full_out/SUMMARY.json` (80557a43...c283). The 293 files of the output folder are listed with their hashes in
`FULL_OUT_MANIFEST.sha256` (b7a846e7...1a49; paths relative to `experiments/`). The checks after the run are in
`AFTER_RUN_CHECK.json` (4909c2f4...a0af, written by `after_run_bl.py`), the comparison with the operations study in
`EARLIER_RESULT_CHECK.json` (9427e9f1...6ce3), the reading in `READING_FULL_OUT.md` (0a4dec55...3e34). The detached
job's own files (outer timing record `time.txt`, `run.status`, `stdout.log`, `cmd.txt`) are copied into
`detached_job_record/`. The outputs are at commit 2a523b11f. The run was launched once and is not run again.

The appendix is the output of

    python3 -I results_tables/render_results_tables.py full_out --check AFTER_RUN_CHECK.json --earlier EARLIER_RESULT_CHECK.json --time detached_job_record/time.txt --out RESULTS_TABLES.md

run in this folder. The script reads the records and the summary, counts from the records whatever the summary
also holds, and refuses to write if the two differ. `RESULTS_TABLES.md` is kept beside this file, and the appendix
equals it byte for byte: the last bytes of this file, as many as `RESULTS_TABLES.md` has, are that file.

## 10. Corrections to this record

- 15 November 2026, on the independent review's note acknowledging the run, before its completed audit: the
  summary now says that the result is not about accuracy on ARC tasks or about autonomous growth, and section 2
  names the direct alias (`difference`) apart from the two compositions (`rot90`, `rot270`) at the primary table
  itself. No number changed, and the appendix is unchanged.
- 15 November 2026, after the independent review's completed audit (saved numbers and custody: pass; criterion
  not met). Four documentary changes, none to a number of the run. (a) The cost table of the appendix now says
  what each row covers: every listed operation of its block, done or excluded at setup, with the setup time of
  the excluded ones in the total; and that the two system columns sum that system's two 36-example searches
  only. The first row had been labelled "Primary cohort" although it covers the 90 listed longer operations.
  Changed in the renderer; the appendix again equals `RESULTS_TABLES.md` byte for byte. (b) Section 6 said
  "Nothing longer was rebuilt", which was ambiguous, because `rot270` is in the stratum of more than 15 source
  nodes; it now names the extra successes. (c) Section 7 said that no ending depends on the machine's load; it
  now says what was observed. (d) The audit status at the top. Sections 5 and 6 keep their statement that three
  expressions differ from their operations on inputs the panel does not hold; those are deductions from the
  source and the verdicts, not observed cases.

## Appendix. Rendered tables

### Names used in these tables

- **Library only**: searches the retained library operations, first up to 4 nodes on 36 examples (L4-36), then up to five nodes (L5-36).
- **Smaller blocks**: searches the library together with the smaller blocks up to 4 nodes on 36 examples (LC4-36), then the blocks with the retained operations alone (C-36).
- **L4-9** and **LC4-9**: the same 4-node searches on nine examples.
- **Right** and **wrong**: the record's verdict on the final panel.
- **Selected nothing**: neither stage of the system found an expression that fits all 36 examples.

### Run

Listed 145, records 145, done 125, excluded 20, incomplete 0.

| stratum | original | eligible | excluded | generator | too few usable pooled inputs |
|---|---|---|---|---|---|
| Short | 35 | 28 | 7 | 4 | 3 |
| Longer | 90 | 80 | 10 | 0 | 10 |
| Longer, 7 to 15 nodes | 35 | 32 | 3 | 0 | 3 |
| Longer, more than 15 nodes | 55 | 48 | 7 | 0 | 7 |

Development names: 20 listed, 17 done, 3 excluded.

Longer stratum outside development (10):

- `crement`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `decrement`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `dneighbors`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)
- `double`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `halve`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `hfrontier`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)
- `increment`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `ineighbors`: too few usable pooled inputs (usability slice: 23 of 23 draws usable, need 30)
- `invert`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `merge`: too few usable pooled inputs (usability slice: 9 of 9 draws usable, need 30)

Short stratum outside development (7):

- `even`: generator: only 51 of 66 valid examples in 4000 draws
- `maximum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `minimum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `neighbors`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)
- `positive`: generator: only 51 of 66 valid examples in 4000 draws
- `toivec`: generator: only 41 of 66 valid examples in 4000 draws
- `tojvec`: generator: only 41 of 66 valid examples in 4000 draws

Development names (3):

- `rapply`: 66 of 66 generator examples are unusable (a container argument holds a function: 66; the output is or holds a function: 0)
- `sign`: too few usable pooled inputs (usability slice: 15 of 15 draws usable, need 30)
- `vfrontier`: too few usable pooled inputs (usability slice: 22 of 22 draws usable, need 30)

Final panels of the primary cohort (80 done targets): generator minimum 30, pooled median 323.0, pooled minimum 34, pooled discarded sum 1197, pooled short: none, pooled not evaluated: none.

- Job costs from detached_job_record/time.txt: user 13572.99 s, system 143.71 s, wall clock 3:48:44, peak resident 2737936 kB, exit status 0.
- From full_out/RUN_COSTS.json: cpu_process_s 13713.60, wall_s 13720.10.

After-run checks (passed: True):

- 1 the freeze verifies: passed
- 2 one read-only receipt naming the freeze, the setup record and the output folder: passed
- 3 the job started once and ended once with exit 0: passed
- 4 the run's manifest names the freeze, the setup record, the whole roster and the frozen policy: passed
- 5 one record for every listed target and no other: passed
- 6 every journal holds its path's events and seals, in order, equal to the record: passed
- 7 SUMMARY.json equals a summary made now from the records: passed
- 7b the calibration set (K and its names) equals the one committed with the freeze: passed
- 8 setup decisions and counts equal the committed record: passed

- Searches within 20% of the safety limit: none.
- Guard timeouts: none.
- Guarded steps without a mark: none.
- Guard bound: shortest guard 20.0 s, margin 0.01 s, 145 targets below the bound, not excluded: none, unknown time: none.

- Freeze sha256: `391915c42f629661ba9d47d641ec186847c8ac2600128c35307ac12d09427144`.
- Setup record sha256: `1c7018c478ff88bfaf48f6d331929e43e9ac13da50d1a9e99015e701ba3a1732`.

### Primary comparison

Cohort: done records with stratum longer, outside the development names (N = 80).

| system | right | selected and wrong | selected nothing | of |
|---|---|---|---|---|
| library only | 7 | 3 | 70 | 80 |
| smaller blocks | 10 | 3 | 67 | 80 |

- Right in both (7): `asobject`, `hconcat`, `leftmost`, `lowermost`, `product`, `rightmost`, `uppermost`.
- Right in smaller blocks only (3): `difference`, `rot270`, `rot90`.
- Right in library only only (0): none.
- Right in neither (70): `apply`, `asindices`, `bordering`, `bottomhalf`, `canvas`, `cellwise`, `center`, `centerofmass`, `cmirror`, `colorcount`, `colorfilter`, `combine`, `connect`, `corners`, `crop`, `dedupe`, `delta`, `divide`, `dmirror`, `extract`, `fgpartition`, `fill`, `frontiers`, `gravitate`, `height`, `hline`, `hmatching`, `hperiod`, `hsplit`, `hupscale`, `inbox`, `index`, `leastcolor`, `llcorner`, `lrcorner`, `manhattan`, `mostcolor`, `move`, `multiply`, `normalize`, `occurrences`, `outbox`, `paint`, `palette`, `papply`, `partition`, `position`, `prapply`, `recolor`, `remove`, `repeat`, `replace`, `sfilter`, `shift`, `shoot`, `sizefilter`, `square`, `subtract`, `toindices`, `toobject`, `ulcorner`, `underfill`, `underpaint`, `urcorner`, `vline`, `vmatching`, `vmirror`, `vperiod`, `vsplit`, `vupscale`.

- Two-sided exact sign test: p = 0.25.
- W (rebuilt by smaller blocks only): 3. L (rebuilt by library only only): 0. W minus L: 3.
- Concordant: both right 7, neither right 70.

Criterion parts:

- W greater than L: True
- p below 0.05: False
- calibration valid and passed: True
- cohort complete: True

- Status: not met. Provisional: False.

### Calibration

- K = 19. Minimum K: 19.
- Minimum K note: amendment of 15 November 2026 by the author: the minimum was 20 in the drafts; it was lowered to 19 after the setup pass over all names gave K = 19 and before any search outside the development names or any outcome
- Share: 0.9. Threshold (right): 18. Right: 19. Passed: True. Valid: True. State: passed.

| operation | witness | nodes | within limit | agrees on all 36 | agrees on the final panel | C-36 expr | C-36 verdict | smaller blocks expr | smaller blocks verdict | library only expr | library only search | library only verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| argmax | `c_max_key(x0, x1)` | 3 | yes | yes | yes | `c_max_key(x0, x1)` | right | `c_max_key(x0, x1)` | right |  |  | selected nothing |
| argmin | `c_min_key(x0, x1)` | 3 | yes | yes | yes | `c_min_key(x0, x1)` | right | `c_min_key(x0, x1)` | right | `first(order(x0, x1))` | L4-36 | right |
| astuple | `c_pair(x0, x1)` | 3 | yes | yes | yes | `c_pair(x0, x1)` | right | `c_pair(x0, x1)` | right |  |  | selected nothing |
| branch | `c_if_else(x0, x1, x2)` | 4 | yes | yes | yes | `c_if_else(x0, x1, x2)` | right | `c_if_else(x0, x1, x2)` | right |  |  | selected nothing |
| contained | `c_in(x0, x1)` | 3 | yes | yes | yes | `c_in(x0, x1)` | right | `c_in(x0, x1)` | right | `valmax(x1, matcher(identity, x0))` | L5-36 | right |
| equality | `c_eq(x0, x1)` | 3 | yes | yes | yes | `c_eq(x0, x1)` | right | `c_eq(x0, x1)` | right | `contained(x0, initset(x1))` | L4-36 | right |
| first | `c_first(x0)` | 2 | yes | yes | yes | `c_first(x0)` | right | `c_first(x0)` | right | `argmax(x0, flip)` | L4-36 | wrong |
| greater | `c_gt(x0, x1)` | 3 | yes | yes | yes | `c_lt(x1, x0)` | right | `c_lt(x1, x0)` | right |  |  | selected nothing |
| identity | `x0` | 1 | yes | yes | yes | `x0` | right | `x0` | right | `x0` | L4-36 | right |
| initset | `c_set1(x0)` | 2 | yes | yes | yes | `c_set1(x0)` | right | `c_set1(x0)` | right |  |  | selected nothing |
| insert | `c_union(x1, c_set1(x0))` | 4 | yes | yes | yes | `c_union(x1, c_set1(x0))` | right | `c_union(x1, c_set1(x0))` | right |  |  | selected nothing |
| intersection | `c_intersection(x0, x1)` | 3 | yes | yes | yes | `c_intersection(x0, x1)` | right | `c_intersection(x0, x1)` | right |  |  | selected nothing |
| interval | `c_range3(x0, x1, x2)` | 4 | yes | yes | yes | `c_range3(x0, x1, x2)` | right | `c_range3(x0, x1, x2)` | right |  |  | selected nothing |
| last | `c_item1(c_max(c_enumerate(x0)))` | 4 | yes | yes | yes | `c_first(c_reverse(c_tuple(x0)))` | right | `c_first(c_reverse(c_tuple(x0)))` | right |  |  | selected nothing |
| leastcommon | `c_min_key(c_frozenset(x0), lbind(c_count, x0))` | 6 | no | yes | yes |  | none |  | selected nothing |  |  | selected nothing |
| order | `c_sorted_key(x0, x1)` | 3 | yes | yes | yes | `c_sorted_key(x0, x1)` | right | `c_sorted_key(x0, x1)` | right |  |  | selected nothing |
| pair | `c_zip(x0, x1)` | 3 | yes | yes | yes | `c_zip(x0, x1)` | right | `c_zip(x0, x1)` | right | `papply(astuple, x0, x1)` | L4-36 | right |
| size | `c_len(x0)` | 2 | yes | yes | yes | `c_len(x0)` | right | `c_len(x0)` | right |  |  | selected nothing |
| totuple | `c_tuple(x0)` | 2 | yes | yes | yes | `c_tuple(x0)` | right | `c_tuple(x0)` | right | `order(x0, initset)` | L4-36 | right |
| valmax | `c_call1(x1, c_max_key_default0(x0, x1))` | 5 | no | yes | yes | `c_max(c_map_tuple(x1, x0))` | right | `c_max(c_map_tuple(x1, x0))` | right |  |  | selected nothing |
| valmin | `c_call1(x1, c_min_key_default0(x0, x1))` | 5 | no | yes | yes |  | none |  | selected nothing |  |  | selected nothing |
| vconcat | `c_concat(x0, x1)` | 3 | yes | yes | yes | `c_concat(x0, x1)` | right | `combine(x0, x1)` | right | `combine(x0, x1)` | L4-36 | right |

- Blocks-alone search (C-36) expression equals the witness expression for the 19 calibration names: 17 match, 2 differ.
  - `greater`: found `c_lt(x1, x0)`, witness `c_gt(x0, x1)`
  - `last`: found `c_first(c_reverse(c_tuple(x0)))`, witness `c_item1(c_max(c_enumerate(x0)))`
- Smaller-blocks selection expression equals the witness expression: 16 match, 3 differ.
  - `greater`: selected `c_lt(x1, x0)`, witness `c_gt(x0, x1)`
  - `last`: selected `c_first(c_reverse(c_tuple(x0)))`, witness `c_item1(c_max(c_enumerate(x0)))`
  - `vconcat`: selected `combine(x0, x1)`, witness `c_concat(x0, x1)`

Eligible controls without a witness within the size limit (3):

- `leastcommon`: the witness has more than 4 nodes (6)
- `valmax`: the witness has more than 4 nodes (5)
- `valmin`: the witness has more than 4 nodes (5)

Controls not eligible (6):

- `even`: generator: only 51 of 66 valid examples in 4000 draws
- `maximum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `minimum`: too few usable pooled inputs (usability slice: 7 of 7 draws usable, need 30)
- `positive`: generator: only 51 of 66 valid examples in 4000 draws
- `toivec`: generator: only 41 of 66 valid examples in 4000 draws
- `tojvec`: generator: only 41 of 66 valid examples in 4000 draws

### Secondary comparisons (descriptive, uncorrected)

| block | N | library only right | smaller blocks right | both | smaller blocks only | library only only | neither | p | library only selected and wrong | smaller blocks selected and wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| Short stratum | 28 | 7 | 20 | 7 | 13 | 0 | 8 | 0.0002441 | `first` | none |
| Longer, 7 to 15 nodes | 32 | 6 | 8 | 6 | 2 | 0 | 24 | 0.5 | `extract` | `extract` |
| Longer, more than 15 nodes | 48 | 1 | 2 | 1 | 1 | 0 | 46 | 1 | `paint`, `underpaint` | `paint`, `underpaint` |
| All strata outside development | 108 | 14 | 30 | 14 | 16 | 0 | 78 | 3.052e-05 | `extract`, `first`, `paint`, `underpaint` | `extract`, `paint`, `underpaint` |
| Development names (development only) | 17 | 1 | 2 | 1 | 1 | 0 | 15 | 1 | `other` | none |

- Short stratum: smaller blocks only: `argmax`, `astuple`, `branch`, `first`, `greater`, `initset`, `insert`, `intersection`, `interval`, `last`, `order`, `size`, `valmax`. Library only only: none.
- Longer, 7 to 15 nodes: smaller blocks only: `difference`, `rot90`. Library only only: none.
- Longer, more than 15 nodes: smaller blocks only: `rot270`. Library only only: none.
- All strata outside development: smaller blocks only: `argmax`, `astuple`, `branch`, `difference`, `first`, `greater`, `initset`, `insert`, `intersection`, `interval`, `last`, `order`, `rot270`, `rot90`, `size`, `valmax`. Library only only: none.
- Development names (development only): smaller blocks only: `rot180`. Library only only: none.

Short operations outside development that are not controls (6):

- `adjacent`: library only: selected nothing; smaller blocks: selected nothing.
- `cover`: library only: selected nothing; smaller blocks: selected nothing.
- `mpapply`: library only: selected nothing; smaller blocks: selected nothing.
- `portrait`: library only: selected nothing; smaller blocks: selected nothing.
- `shape`: library only: selected nothing; smaller blocks: selected nothing.
- `subgrid`: library only: selected nothing; smaller blocks: selected nothing.

### The six searches

Primary cohort (longer stratum outside development, N = 80):

| search | n | right | wrong | none | found | size limit completed | combination budget used up | sum (s) | median (s) | largest (s) | largest operation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L4-9 | 80 | 7 | 12 | 61 | 19 | 61 | 0 | 253.17 | 2.92 | 8.90 | `manhattan` |
| LC4-9 | 80 | 10 | 12 | 58 | 22 | 58 | 0 | 892.49 | 12.12 | 26.75 | `manhattan` |
| L4-36 | 80 | 7 | 3 | 70 | 10 | 70 | 0 | 795.15 | 8.16 | 24.27 | `move` |
| L5-36 | 80 | 7 | 3 | 70 | 10 | 0 | 70 | 4098.50 | 56.42 | 80.86 | `fill` |
| LC4-36 | 80 | 10 | 3 | 67 | 13 | 67 | 0 | 3194.24 | 38.81 | 87.26 | `move` |
| C-36 | 80 | 4 | 2 | 74 | 6 | 74 | 0 | 305.09 | 3.76 | 7.69 | `move` |

All done records outside the development names (N = 108):

| search | n | right | wrong | none | found | size limit completed | combination budget used up | sum (s) | median (s) | largest (s) | largest operation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L4-9 | 108 | 13 | 17 | 78 | 30 | 78 | 0 | 310.91 | 2.75 | 8.90 | `manhattan` |
| LC4-9 | 108 | 29 | 15 | 64 | 44 | 64 | 0 | 1021.79 | 10.81 | 26.75 | `manhattan` |
| L4-36 | 108 | 13 | 4 | 91 | 17 | 91 | 0 | 979.33 | 7.48 | 24.27 | `move` |
| L5-36 | 108 | 14 | 4 | 90 | 18 | 0 | 90 | 5209.09 | 53.88 | 80.86 | `fill` |
| LC4-36 | 108 | 30 | 3 | 75 | 33 | 75 | 0 | 3655.19 | 35.74 | 87.26 | `move` |
| C-36 | 108 | 24 | 2 | 82 | 26 | 82 | 0 | 344.13 | 3.54 | 7.69 | `move` |

All done records, development names included (N = 125):

| search | n | right | wrong | none | found | size limit completed | combination budget used up | sum (s) | median (s) | largest (s) | largest operation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L4-9 | 125 | 14 | 17 | 94 | 31 | 94 | 0 | 367.52 | 2.75 | 8.90 | `manhattan` |
| LC4-9 | 125 | 31 | 15 | 79 | 46 | 79 | 0 | 1234.83 | 11.28 | 26.75 | `manhattan` |
| L4-36 | 125 | 14 | 4 | 107 | 18 | 107 | 0 | 1132.14 | 7.52 | 24.27 | `move` |
| L5-36 | 125 | 15 | 5 | 105 | 20 | 0 | 105 | 6104.51 | 53.95 | 80.86 | `fill` |
| LC4-36 | 125 | 32 | 3 | 90 | 35 | 90 | 0 | 4298.82 | 35.95 | 87.26 | `move` |
| C-36 | 125 | 26 | 2 | 97 | 28 | 97 | 0 | 402.64 | 3.54 | 7.69 | `move` |

Counted from the records; the summary has no block for this cohort.

- Total searches over all 125 done records: 750.
- Stop classes: found 178, size limit completed 467, combination budget used up 105.
- Searches with function cap reached: 0.
- Largest bank: 263232 (`cellwise`, L5-36) against a cap of 1500000.
- Largest search processor time: 87.26 s (`move`, LC4-36).
- Done records with at least one found expression in any search: 47. With none: 78.

### Stages and candidate sets

Primary cohort (N = 80):

- LC4-36 against L4-36: both 7, LC4-36 only 3, L4-36 only 0, neither 70.
  - LC4-36 only: `difference`, `rot270`, `rot90`.
- L5-36 against L4-36: both 7, L5-36 only 0, L4-36 only 0, neither 73.
- Operations where the four-node library search is right and the search with blocks ended by its budget without a right fit: 0.
- Library only selected by stage: stage 1: 10.
- Smaller blocks selected by stage: stage 1: 13.
- Library only candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 7.
- Smaller blocks candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 10.

All done records outside the development names (N = 108):

- LC4-36 against L4-36: both 13, LC4-36 only 17, L4-36 only 0, neither 78.
  - LC4-36 only: `argmax`, `astuple`, `branch`, `contained`, `difference`, `first`, `greater`, `initset`, `insert`, `intersection`, `interval`, `last`, `order`, `rot270`, `rot90`, `size`, `valmax`.
- L5-36 against L4-36: both 13, L5-36 only 1, L4-36 only 0, neither 94.
  - L5-36 only: `contained`.
- Operations where the four-node library search is right and the search with blocks ended by its budget without a right fit: 0.
- Library only selected by stage: stage 1: 17, stage 2: 1.
- Smaller blocks selected by stage: stage 1: 33.
- Library only candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 14.
- Smaller blocks candidate-set coverage (either of the system's two found expressions right on the final panel; this is not the system's result): 30.

### Order of sets

Note: for a selected expression that is right and whose output is a frozenset; nested sets are not compared; it does not change 'right'

Primary cohort:

Library only: 492 of 731 inputs with the same order.

| operation | same order | of |
|---|---|---|
| asobject | 114 | 353 |
| product | 378 | 378 |

Smaller blocks: 797 of 1047 inputs with the same order.

| operation | same order | of |
|---|---|---|
| asobject | 114 | 353 |
| difference | 305 | 316 |
| product | 378 | 378 |


All done records outside the development names:

Library only: 552 of 791 inputs with the same order.

| operation | same order | of |
|---|---|---|
| argmin | 24 | 24 |
| asobject | 114 | 353 |
| identity | 36 | 36 |
| product | 378 | 378 |

Smaller blocks: 1572 of 1822 inputs with the same order.

| operation | same order | of |
|---|---|---|
| argmax | 29 | 29 |
| argmin | 24 | 24 |
| asobject | 114 | 353 |
| branch | 181 | 181 |
| difference | 305 | 316 |
| first | 24 | 24 |
| identity | 36 | 36 |
| insert | 428 | 428 |
| intersection | 13 | 13 |
| last | 21 | 21 |
| product | 378 | 378 |
| valmax | 19 | 19 |


### Sizes of found expressions

Primary cohort (N = 80):

| search | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| L4-9 | 3 | 1 | 7 | 8 |  |
| LC4-9 | 4 | 1 | 9 | 8 |  |
| L4-36 | 2 |  | 2 | 6 |  |
| L5-36 | 2 |  | 2 | 6 |  |
| LC4-36 | 2 |  | 5 | 6 |  |
| C-36 | 2 |  | 3 | 1 |  |

All done records outside the development names (N = 108):

| search | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| L4-9 | 4 | 1 | 12 | 13 |  |
| LC4-9 | 6 | 5 | 19 | 14 |  |
| L4-36 | 3 |  | 5 | 9 |  |
| L5-36 | 3 |  | 5 | 9 | 1 |
| LC4-36 | 3 | 4 | 15 | 11 |  |
| C-36 | 3 | 4 | 13 | 6 |  |

### Costs

Note: subtotals of the targets' own records; nested subtotals are never added to the whole job

| block | listed | done | excluded at setup | searches (s) | final checks (s) | other (s) | targets total (s) | library only (s) | smaller blocks (s) |
|---|---|---|---|---|---|---|---|---|---|
| Longer stratum outside development | 90 | 80 | 10 | 9538.70 | 3.09 | 105.30 | 9650.80 | 4893.70 | 3499.30 |
| Short stratum outside development | 35 | 28 | 7 | 1981.80 | 0.96 | 29.40 | 2015.00 | 1294.80 | 500.00 |
| All strata outside development | 125 | 108 | 17 | 11520.50 | 4.05 | 134.70 | 11665.80 | 6188.40 | 3999.30 |
| Development names (development only) | 20 | 17 | 3 | 2020.10 | 0.07 | 27.00 | 2047.50 | 1048.20 | 702.10 |

- Each row covers every listed operation of its block, including those excluded at setup, whose setup time is in the total. For the first row: done records 9647.07 s, excluded records 3.76 s.
- The two system columns are the sums of that system's two 36-example searches only (library only: L4-36 and L5-36; smaller blocks: LC4-36 and C-36), so the nine-example searches, the final checks and other work are not in them.

- Whole job (from the process): cpu_process_s 13713.60, cpu_user_s 13572.80, cpu_system_s 143.70, wall_s 13720.10.
- Whole job (from detached_job_record/time.txt): user 13572.99 s, system 143.71 s, wall clock 3:48:44.
- Setup of the pools: 0.00 s. Targets: 13713.20 s.

### Every selected expression

| operation | stratum | role | system | expression | nodes | search | verdict | agree of n | generator | pooled |
|---|---|---|---|---|---|---|---|---|---|---|
| asobject | longer |  | library only | `merge(partition(x0))` | 3 | L4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| asobject | longer |  | smaller blocks | `merge(partition(x0))` | 3 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| difference | longer |  | smaller blocks | `c_set_difference(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| extract | longer |  | library only | `argmin(x0, flip)` | 3 | L4-36 | wrong | 283 of 292 | 30 of 30 | 253 of 262 |
| extract | longer |  | smaller blocks | `argmin(x0, flip)` | 3 | LC4-36 | wrong | 283 of 292 | 30 of 30 | 253 of 262 |
| hconcat | longer |  | library only | `papply(combine, x0, x1)` | 4 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| hconcat | longer |  | smaller blocks | `papply(combine, x0, x1)` | 4 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| leftmost | longer |  | library only | `valmin(toindices(x0), last)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| leftmost | longer |  | smaller blocks | `valmin(toindices(x0), last)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| lowermost | longer |  | library only | `valmax(toindices(x0), first)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| lowermost | longer |  | smaller blocks | `valmax(toindices(x0), first)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| paint | longer |  | library only | `x0` | 1 | L4-36 | wrong | 139 of 430 | 30 of 30 | 109 of 400 |
| paint | longer |  | smaller blocks | `x0` | 1 | LC4-36 | wrong | 139 of 430 | 30 of 30 | 109 of 400 |
| product | longer |  | library only | `prapply(astuple, x0, x1)` | 4 | L4-36 | right | 393 of 393 | 30 of 30 | 363 of 363 |
| product | longer |  | smaller blocks | `prapply(astuple, x0, x1)` | 4 | LC4-36 | right | 393 of 393 | 30 of 30 | 363 of 363 |
| rightmost | longer |  | library only | `valmax(toindices(x0), last)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| rightmost | longer |  | smaller blocks | `valmax(toindices(x0), last)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| rot270 | longer |  | smaller blocks | `c_reverse(c_zip_star(x0))` | 3 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| rot90 | longer |  | smaller blocks | `c_zip_star(c_reverse(x0))` | 3 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| underpaint | longer |  | library only | `x0` | 1 | L4-36 | wrong | 138 of 430 | 30 of 30 | 108 of 400 |
| underpaint | longer |  | smaller blocks | `x0` | 1 | LC4-36 | wrong | 138 of 430 | 30 of 30 | 108 of 400 |
| uppermost | longer |  | library only | `valmin(toindices(x0), first)` | 4 | L4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| uppermost | longer |  | smaller blocks | `valmin(toindices(x0), first)` | 4 | LC4-36 | right | 341 of 341 | 30 of 30 | 311 of 311 |
| argmax | short | control | smaller blocks | `c_max_key(x0, x1)` | 3 | LC4-36 | right | 289 of 289 | 30 of 30 | 259 of 259 |
| argmin | short | control | library only | `first(order(x0, x1))` | 4 | L4-36 | right | 333 of 333 | 30 of 30 | 303 of 303 |
| argmin | short | control | smaller blocks | `c_min_key(x0, x1)` | 3 | LC4-36 | right | 333 of 333 | 30 of 30 | 303 of 303 |
| astuple | short | control | smaller blocks | `c_pair(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| branch | short | control | smaller blocks | `c_if_else(x0, x1, x2)` | 4 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| contained | short | control | library only | `valmax(x1, matcher(identity, x0))` | 5 | L5-36 | right | 414 of 414 | 30 of 30 | 384 of 384 |
| contained | short | control | smaller blocks | `c_in(x0, x1)` | 3 | LC4-36 | right | 414 of 414 | 30 of 30 | 384 of 384 |
| equality | short | control | library only | `contained(x0, initset(x1))` | 4 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| equality | short | control | smaller blocks | `c_eq(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| first | short | control | library only | `argmax(x0, flip)` | 3 | L4-36 | wrong | 204 of 213 | 27 of 30 | 177 of 183 |
| first | short | control | smaller blocks | `c_first(x0)` | 2 | LC4-36 | right | 213 of 213 | 30 of 30 | 183 of 183 |
| greater | short | control | smaller blocks | `c_lt(x1, x0)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| identity | short | control | library only | `x0` | 1 | L4-36 | right | 99 of 99 | 30 of 30 | 69 of 69 |
| identity | short | control | smaller blocks | `x0` | 1 | LC4-36 | right | 99 of 99 | 30 of 30 | 69 of 69 |
| initset | short | control | smaller blocks | `c_set1(x0)` | 2 | LC4-36 | right | 98 of 98 | 30 of 30 | 68 of 68 |
| insert | short | control | smaller blocks | `c_union(x1, c_set1(x0))` | 4 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| intersection | short | control | smaller blocks | `c_intersection(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| interval | short | control | smaller blocks | `c_range3(x0, x1, x2)` | 4 | LC4-36 | right | 422 of 422 | 30 of 30 | 392 of 392 |
| last | short | control | smaller blocks | `c_first(c_reverse(c_tuple(x0)))` | 4 | LC4-36 | right | 214 of 214 | 30 of 30 | 184 of 184 |
| order | short | control | smaller blocks | `c_sorted_key(x0, x1)` | 3 | LC4-36 | right | 276 of 276 | 30 of 30 | 246 of 246 |
| pair | short | control | library only | `papply(astuple, x0, x1)` | 4 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| pair | short | control | smaller blocks | `c_zip(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| size | short | control | smaller blocks | `c_len(x0)` | 2 | LC4-36 | right | 214 of 214 | 30 of 30 | 184 of 184 |
| totuple | short | control | library only | `order(x0, initset)` | 3 | L4-36 | right | 70 of 70 | 30 of 30 | 40 of 40 |
| totuple | short | control | smaller blocks | `c_tuple(x0)` | 2 | LC4-36 | right | 70 of 70 | 30 of 30 | 40 of 40 |
| valmax | short | control | smaller blocks | `c_max(c_map_tuple(x1, x0))` | 4 | LC4-36 | right | 328 of 328 | 30 of 30 | 298 of 298 |
| vconcat | short | control | library only | `combine(x0, x1)` | 3 | L4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| vconcat | short | control | smaller blocks | `combine(x0, x1)` | 3 | LC4-36 | right | 430 of 430 | 30 of 30 | 400 of 400 |
| rot180 | longer | development | smaller blocks | `apply(c_reverse, c_reverse(x0))` | 4 | LC4-36 | right | 353 of 353 | 30 of 30 | 323 of 323 |
| color | short | development | library only | `first(first(x0))` | 3 | L4-36 | right | 82 of 82 | 30 of 30 | 52 of 52 |
| color | short | development | smaller blocks | `first(first(x0))` | 3 | LC4-36 | right | 82 of 82 | 30 of 30 | 52 of 52 |
| other | short | development | library only | `argmin(x0, matcher(identity, x1))` | 5 | L5-36 | wrong | 395 of 411 | 29 of 30 | 366 of 381 |

### Selected and wrong

| operation | stratum | system | expression | nodes | search | agree of n | generator | pooled |
|---|---|---|---|---|---|---|---|---|
| extract | longer | library only, smaller blocks | `argmin(x0, flip)` | 3 | L4-36, LC4-36 | 283 of 292 | 30 of 30 | 253 of 262 |
| first | short | library only | `argmax(x0, flip)` | 3 | L4-36 | 204 of 213 | 27 of 30 | 177 of 183 |
| other | short | library only | `argmin(x0, matcher(identity, x1))` | 5 | L5-36 | 395 of 411 | 29 of 30 | 366 of 381 |
| paint | longer | library only, smaller blocks | `x0` | 1 | L4-36, LC4-36 | 139 of 430 | 30 of 30 | 109 of 400 |
| underpaint | longer | library only, smaller blocks | `x0` | 1 | L4-36, LC4-36 | 138 of 430 | 30 of 30 | 108 of 400 |

### Nine examples against 36

Primary cohort (N = 80):

L4-9 against L4-36:

| L4-9 \ L4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 7 | 0 | 0 | 7 |
| wrong | 0 | 3 | 9 | 12 |
| none | 0 | 0 | 61 | 61 |
| total | 7 | 3 | 70 | 80 |

LC4-9 against LC4-36:

| LC4-9 \ LC4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 10 | 0 | 0 | 10 |
| wrong | 0 | 3 | 9 | 12 |
| none | 0 | 0 | 58 | 58 |
| total | 10 | 3 | 67 | 80 |

Operations whose nine-example first fit was wrong:

- `bordering` L4-9: `flip(square(x1))`; L4-36: none
- `dedupe` L4-9: `x0`; L4-36: none
- `extract` L4-9: `first(x0)`; L4-36: wrong `argmin(x0, flip)`
- `hline` L4-9: `equality(T, size(x0))`; L4-36: none
- `hmatching` L4-9: `portrait(totuple(x0))`; L4-36: none
- `index` L4-9: `valmin(x0, maximum)`; L4-36: none
- `mostcolor` L4-9: `minimum(palette(x0))`; L4-36: none
- `paint` L4-9: `x0`; L4-36: wrong `x0`
- `sizefilter` L4-9: `connect(UNITY, LEFT)`; L4-36: none
- `square` L4-9: `contained(size(x0), DOWN)`; L4-36: none
- `underpaint` L4-9: `x0`; L4-36: wrong `x0`
- `vmatching` L4-9: `flip(square(x0))`; L4-36: none
- `bordering` LC4-9: `flip(square(x1))`; LC4-36: none
- `dedupe` LC4-9: `x0`; LC4-36: none
- `extract` LC4-9: `first(x0)`; LC4-36: wrong `argmin(x0, flip)`
- `hline` LC4-9: `equality(T, size(x0))`; LC4-36: none
- `hmatching` LC4-9: `portrait(totuple(x0))`; LC4-36: none
- `index` LC4-9: `valmin(x0, maximum)`; LC4-36: none
- `mostcolor` LC4-9: `minimum(palette(x0))`; LC4-36: none
- `paint` LC4-9: `x0`; LC4-36: wrong `x0`
- `sizefilter` LC4-9: `EMPTY_SET`; LC4-36: none
- `square` LC4-9: `contained(size(x0), DOWN)`; LC4-36: none
- `underpaint` LC4-9: `x0`; LC4-36: wrong `x0`
- `vmatching` LC4-9: `flip(square(x0))`; LC4-36: none

All done records outside development (N = 108):

L4-9 against L4-36:

| L4-9 \ L4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 13 | 0 | 0 | 13 |
| wrong | 0 | 4 | 13 | 17 |
| none | 0 | 0 | 78 | 78 |
| total | 13 | 4 | 91 | 108 |

LC4-9 against LC4-36:

| LC4-9 \ LC4-36 | right | wrong | none | total |
|---|---|---|---|---|
| right | 29 | 0 | 0 | 29 |
| wrong | 1 | 3 | 11 | 15 |
| none | 0 | 0 | 64 | 64 |
| total | 30 | 3 | 75 | 108 |

Operations whose nine-example first fit was wrong:

- `adjacent` L4-9: `contained(TWO_BY_ZERO, x0)`; L4-36: none
- `bordering` L4-9: `flip(square(x1))`; L4-36: none
- `dedupe` L4-9: `x0`; L4-36: none
- `extract` L4-9: `first(x0)`; L4-36: wrong `argmin(x0, flip)`
- `first` L4-9: `argmax(x0, flip)`; L4-36: wrong `argmax(x0, flip)`
- `greater` L4-9: `even(divide(NINE, x0))`; L4-36: none
- `hline` L4-9: `equality(T, size(x0))`; L4-36: none
- `hmatching` L4-9: `portrait(totuple(x0))`; L4-36: none
- `index` L4-9: `valmin(x0, maximum)`; L4-36: none
- `intersection` L4-9: `sfilter(x0, flip)`; L4-36: none
- `mostcolor` L4-9: `minimum(palette(x0))`; L4-36: none
- `paint` L4-9: `x0`; L4-36: wrong `x0`
- `portrait` L4-9: `contained(SEVEN, first(x0))`; L4-36: none
- `sizefilter` L4-9: `connect(UNITY, LEFT)`; L4-36: none
- `square` L4-9: `contained(size(x0), DOWN)`; L4-36: none
- `underpaint` L4-9: `x0`; L4-36: wrong `x0`
- `vmatching` L4-9: `flip(square(x0))`; L4-36: none
- `adjacent` LC4-9: `contained(TWO_BY_ZERO, x0)`; LC4-36: none
- `bordering` LC4-9: `flip(square(x1))`; LC4-36: none
- `dedupe` LC4-9: `x0`; LC4-36: none
- `extract` LC4-9: `first(x0)`; LC4-36: wrong `argmin(x0, flip)`
- `hline` LC4-9: `equality(T, size(x0))`; LC4-36: none
- `hmatching` LC4-9: `portrait(totuple(x0))`; LC4-36: none
- `index` LC4-9: `valmin(x0, maximum)`; LC4-36: none
- `intersection` LC4-9: `EMPTY_SET`; LC4-36: right `c_intersection(x0, x1)`
- `mostcolor` LC4-9: `minimum(palette(x0))`; LC4-36: none
- `paint` LC4-9: `x0`; LC4-36: wrong `x0`
- `portrait` LC4-9: `contained(SEVEN, first(x0))`; LC4-36: none
- `sizefilter` LC4-9: `EMPTY_SET`; LC4-36: none
- `square` LC4-9: `contained(size(x0), DOWN)`; LC4-36: none
- `underpaint` LC4-9: `x0`; LC4-36: wrong `x0`
- `vmatching` LC4-9: `flip(square(x0))`; LC4-36: none

### Comparison with the earlier study

Total: 145.

| category | count |
|---|---|
| agree: both found none | 107 |
| agree: the same expression | 18 |
| not compared: excluded here | 13 |
| not compared: excluded here (the earlier study found one) | 7 |

- agree: both found none: 107 (names not listed).
- agree: the same expression (18): `argmin`, `asobject`, `color`, `equality`, `extract`, `first`, `hconcat`, `identity`, `leftmost`, `lowermost`, `paint`, `pair`, `product`, `rightmost`, `totuple`, `underpaint`, `uppermost`, `vconcat`.
- not compared: excluded here (13): `crement`, `decrement`, `dneighbors`, `double`, `even`, `halve`, `hfrontier`, `increment`, `invert`, `merge`, `rapply`, `sign`, `vfrontier`.
- not compared: excluded here (the earlier study found one) (7): `ineighbors`, `maximum`, `minimum`, `neighbors`, `positive`, `toivec`, `tojvec`.

