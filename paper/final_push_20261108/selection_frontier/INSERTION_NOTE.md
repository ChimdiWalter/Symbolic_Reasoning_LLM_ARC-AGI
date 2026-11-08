# Insertion note: why selection is the frontier

For the paper agent, 8 Nov 2026. Sources: `mutual_information.md` and `false_acceptance.md` in this folder, both
corrected after an independent check (`verify_selection_frontier.txt`: 85 numbers re-derived with separate code,
none different; every task the two analyses touched is in the source half).

**How to use these numbers**

- Every number below is post hoc, development data: the source halves of ConceptARC, Mini-ARC and 1D-ARC, analysed
  after the fact. Keep the label "post hoc, development data" on every number in the papers. None of them is a held
  result. Do not put them in a table of held results, and do not add the held numbers behind the first question.
- "Fit" means the rule reproduces every demonstration. It does not mean correct.
- Both analyses answer open problems that Paper 2 already lists: "Why selectors ignore failure evidence" and "The
  false-discovery curve of promoted operations". Edit like for like: each item's proposed test becomes the
  sentences below, the item stays an open problem, and nothing else grows.

## 1. Why learned guidance tied a plain success-rate table

**Paper 2** (theory and open problems):

> The failure features turned out to be informative: they carried at least 2.82 of the 2.93 bits needed to say
> which kind of edit would succeed and named it in 98.1% of the 633 holes that had an exact program, but a plain
> table of past success rates already ran a working search first in 95.6% of those holes, so the learned guide, a
> linear model and the table fitted 284, 286 and 285 of the 425 development tasks at 500 operations per hole,
> against at most 289 for any possible order (297 if the eight tasks whose programs were never retried also
> fitted) (post hoc, development data). This taught us that the tie came from candidate dominance, not from a
> feature bottleneck: a few general edits almost always work when the comparison of demonstration pairs proposes
> them (gravitate in 109 of 109 holes, connect in 149 of 161), so once the language holds the right edit, choosing
> what to try first is easy and a learner has almost nothing left to win (post hoc, development data). It opens the
> harder half of the problem: 642 of the 1,275 holes had no exact program at all, so progress needs building the
> missing edit, and a fair test of learned guidance needs tasks where the right edit is rare and depends on the
> task (post hoc, development data).

**Paper 1** (one sentence):

> Learned guidance tied a plain success-rate table (284 against 285 of 425 development tasks fitted) because the
> table already tried a working edit first in 95.6% of the searches where one existed, not because the failure
> features were uninformative (they named the kind of edit that works in 98.1%), so the open problem is building
> missing edits rather than ordering existing ones (post hoc, development data).

This supports "Build before you rank" from the other side: once the right edit is offered, ranking is easy, and
where no exact program exists (642 of 1,275 holes) no order can help (post hoc, development data).

## 2. How often a rule that fits every demonstration is wrong

**Paper 2** (theory and open problems):

> Of the 4,832 constructed rules that fit every demonstration and were suggested independently by at least two of
> them, 562 (11.6%) were wrong on the task's test output, from 8.5% on 1D-ARC to 57.9% on ConceptARC, and
> rebuilding the same 277 1D-ARC tasks from fewer demonstrations raised the wrong share among fitting rules from
> 9.7% with all three to 30.3% with one (post hoc, development data). This taught us that fitting is weak evidence
> and that ranking is not where the errors are: in 25 of the 41 tasks whose first answer was wrong no right rule
> had been built, 14 of the other 16 were one rule read under two ways of cutting the grid into objects that agree
> on every demonstration, and preferring shorter descriptions changed one task each way (post hoc, development
> data). This is why selection is the frontier: what separated right rules from wrong ones was more evidence, in
> the form of more demonstrations, and the second attempt that ARC scoring allows already covered all 281 tasks
> that had a right rule, so the open problem is deciding when the evidence singles out one rule, which observation
> to ask for when it does not, and when to hold back (post hoc, development data).

**Paper 1** (one sentence):

> Even among constructed rules that fit every demonstration and were proposed by at least two of them, 11.6% were
> wrong on the test output (8.5% to 57.9% by benchmark), the wrong share among fitting rules rose as demonstrations
> were taken away (from 9.7% to 30.3% on 1D-ARC), and most wrong first answers came from a right rule that was
> never built or a tie the demonstrations could not break, not from ranking (post hoc, development data).

This supports three propositions (post hoc, development data):

- "Many explanations": 189 rules fit one demonstration of one ConceptARC task and gave 106 different answers, none
  right.
- "A limit on how many rules a few observations can single out": different answers per hole fell from 3.6 to 1.6
  as 8 ConceptARC tasks went from one to four demonstrations.
- "A bigger language can mean more ambiguity": all 46 accepted colour tables on ConceptARC were wrong (they come
  from 2 tasks), and a second way of cutting the grid into objects explains 14 of the 16 wrong first answers that
  had a right rule available.

For the item's existing "disproved if" test: keeping every right rule, the shortest description-length cut lowers
the wrong share only from 57.9% to 51.4% on ConceptARC (107 of the 208 rules it keeps) and from 47.5% to 45.5% on
Mini-ARC (35 of the 77 it keeps), and not at all on 1D-ARC (8.5%), so a description-length bar fails on 1D-ARC and
helps little elsewhere (post hoc, development data).

## Do not claim

These were corrected or ruled out by the check:

- A feature bottleneck on Mini-ARC. There are only 13 holes; the hole-level classifiers named the family in 6 of
  them, base rates in 8 and the guide's own first block in 10 (post hoc, development data).
- That more free constants make a rule wrong inside a task. Only 5 of the 31 tasks that accepted both kinds could
  show a difference (post hoc, development data).
- That dropping colour tables is a fix. The 49 always-wrong tables on ConceptARC and Mini-ARC come from 4 tasks,
  the rule was judged on the same data, and on 1D-ARC it costs 33 right first answers (post hoc, development data).
  It is a candidate for a pre-registered test.
- That 11.6% is a rate per task. It pools rules, most of them from 1D-ARC. Counted per task it is 13.9%, and 41 of
  306 first answers were wrong (post hoc, development data).
- That no file holding held data was opened. The scorer read each benchmark's single solutions file, which also
  holds the held outputs, and kept only source tasks. Nothing held was used or scored.

## Files

All in this folder: `mutual_information.md` and `false_acceptance.md` (both corrected), their tables and charts
(`mutual_information_chart.png`, `false_acceptance.png`), every script next to its output, and the check
`verify_selection_frontier.py` with `verify_selection_frontier.txt`. The check used about 24 CPU-seconds over
three runs in the shared CPU slot at nice 19; two one-line Python commands (a look at one record and a version
print), under a CPU-second, ran outside it.
Nothing was committed.
