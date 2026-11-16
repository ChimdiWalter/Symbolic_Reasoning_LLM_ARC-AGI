# Visible-failure construction, version 1, stage A: results

Author: Chimdi Walter Ndubuisi. 13 November 2026 (UTC), corrected 14 November. **Audited:** the independent
review passed the freeze before the run and, on 14 November, gave a qualified pass to the saved outcome (every pin
verified; 5,037 checks of the journals' order; the whole summary reproduced; nothing rerun). Its qualifications are
applied below. A development comparison on a known benchmark (protocol, section 0): not an untouched confirmation
over operations, no model, invented inputs. These are constructed operation tasks, not puzzle or competition
scores. "Not demonstrated" below never means "cannot help".

## 1. The run
- One launch, after the independent review's check of the exact freeze passed. Detached job `vf1_stage_a`,
  15:54:29 to 16:31:46 UTC (37 minutes 17 seconds), exit 0. Freeze `FREEZE.json` be5c33c4..., protocol
  `PROTOCOL.md` 882df282..., commit 44dd0c544; all 26 frozen files matched after the run.
- 145 operations: 119 ran to the end, 26 were excluded at setup, none was incomplete. The setup decisions (the
  three consumers of each target, and every exclusion with its reason) are the same as in the record made before
  the run (`PREFLIGHT_SETUP_ONLY.json`). The setup metadata is not identical byte for byte: for one target
  (`combine`) the counts of usable pooled inputs differ by one (313 and 312; 382 and 381). Eligibility is
  unchanged; the cause was not established. In that record the final panel was never opened; the generator does compute
  all 66 examples at setup and their argument tuples are used to keep pooled inputs disjoint from them.
- The primary comparison's cohort is complete: all 102 eligible operations outside the development roster ran.
- Final panels of those 102: 30 generator inputs for 100 targets and 29 for 2 (`shift`, `sfilter`); pooled inputs
  34 to 400 (median 322.5); no shortage flag. Admission grid: 12 generator inputs for 113 of the 119 targets that ran (11 or 9 for the other 6).
- CPU: 2,223.1 seconds is the sum of the 119 completed episodes' own intervals. The 26 setup exclusions and the
  work outside the episodes are not in that figure (the 145 printed intervals sum to about 2,230 seconds), elapsed
  time was 2,237 seconds, and the whole process's CPU was not recorded. None of these is to be added to another.
  No GPU, no model.
- Outputs: `full_out/` (`SUMMARY.json` af2ea916..., 316 files listed in `FULL_OUT_MANIFEST.sha256` 43bea531...,
  receipt `RECEIPT_ALL_ROSTER.json` 43b07a76...).

## 2. Primary comparison: is the task solved on fresh inputs?
Exact outputs of the acquisition task on its final panel, the same panel for both arms, allowance of 10
CPU-seconds each. **V** keeps the program and searches only for the missing call. **S** solves the task from its
three examples with no old program.

| | V (failure visible) | S (ordinary synthesis) |
|---|---|---|
| tasks exact, of 102 | 9 | 6 |
| CPU spent (seconds) | 217 | 629 |

Paired by target: V alone 6 (canvas, equality, pair, product, valmax, vupscale), S alone 3 (first, llcorner,
urcorner), both 3 (argmin, outbox, vconcat), neither 90. Two-sided sign test on 6 against 3: 0.51. **The decision
rule is not met: no benefit of keeping the program and searching at the failing step is demonstrated.** The acquisition
searches cost 217 CPU-seconds for V and 629 for S in total. That is the cost of the search phase on different
sets of solved targets, not an efficiency comparison at equal outcomes.

Reading the expressions: 5 of V's 9 are candidates that match the direct finite checks against the
operation (section 3). The other 4 solve the task
without recovering the operation, because the surrounding program loses information: for example `canvas` behind
`height` is solved by `repeat(T, first(dimensions))`, which has the right height and is not a canvas.

## 3. Capability outcomes (102 operations; kept apart from the primary)
| arm | a candidate fits the 3 examples | of these, correct | admitted by the rule | of these, wrong | reused |
|---|---|---|---|---|---|
| V, failure visible | 51 | 5 | 8 | 3 | 5 |
| H, schedule of V and S | 52 | 5 | 8 | 3 | 5 |
| T, six examples of the operation itself (declared supervision) | 27 | 11 | 15 | 4 | 10 |

- **Fitting three examples through another program is weak evidence: 46 of V's 51 first fits (90%) are wrong.**
  In 17 of the 51 the task showed only two different outputs on its setup examples, and every such task got a fit.
- The rule rejects 43 of the 46 wrong first fits and keeps all 5 right ones; 3 of its 8 admissions are wrong.
- V's correct recoveries: `argmin` = `first(order(container, compfunc))`, `equality` = `contained(a, initset(b))`,
  `pair` = `papply(astuple, a, b)`, `product` = `prapply(astuple, a, b)`, `vconcat` = `combine(a, b)`.
- V's false admissions: `first` (`argmax(container, flip)`, wrong when the container holds a zero), `index`
  (`mostcolor(grid)`), `totuple` (`order(container, flip)`).
- None of the five correct candidates was rejected by any admission standard.
- With direct examples of the operation (arm T), 11 are recovered instead of 5, and 4 wrong ones are still admitted.

## 4. Which admission evidence keeps wrong repairs out
All standards on the same 51 frozen first fits of V, of which 5 are correct. Each cell: admitted (of which wrong).
Columns give the number of labelled examples a standard uses. Corrected on 14 November after the independent
review's reading: the mixed standard uses twice as many examples as the others at the same setting, and an
earlier version of this section compared them as if equal.

| standard | 3 examples | 6 | 12 | 24 |
|---|---|---|---|---|
| none (0 examples) | 51 (46) | | | |
| more of the same (same program, generated inputs) | 19 (14) | 14 (9) | 12 (7) | |
| a different program, generated inputs | 14 (9) | 10 (5) | 8 (3) | |
| a different program, differently assembled inputs | 14 (9) | 12 (7) | 8 (3) | |
| a different program, half generated and half differently assembled | | 11 (6) | **8 (3), the rule** | 6 (1) |

- **At equal numbers of examples, a check through a different program admitted fewer wrong repairs than more
  examples of the same program** (9 against 14, 5 against 9, 3 against 7). This is an observed difference on a
  small roster, not a general ordering of evidence.
- **Mixing the two kinds of input shows no benefit beyond the number of examples.** At 12 examples the mix admits
  3 wrong repairs, the same as either kind alone at 12; at 6 examples it admits 6, against 5 and 7.
- More examples helped in every row. Evidence still runs out: under the rule 3 of 8 admissions are wrong, and
  with 24 examples 1 of 6.
- None of the five right first fits was rejected by any standard. Five is too few to say how often a right
  candidate would be rejected in general.

## 5. Reuse on a different task (declared secondary)
The reuse task on its final panel, the same for every arm: retained (V's admitted operation from the sealed
library, no search) 5 exact; ordinary synthesis from the reuse task's own three examples 8 exact; no retention (a
fresh repair on those three examples) 13 exact. Retained against fresh synthesis, paired: 4 won (argmin, equality,
pair, product), 7 lost, sign test 0.55. **Retention is not shown to help.** Only 8 operations were admitted at
all, so retention could apply to few targets, while a fresh search can solve a lossy reuse task without the
operation. Where a correct operation was admitted, reuse cost 0.0003 to 0.08 CPU-seconds against up to 10 for a
search. For `pair` and `product` a projection from one measured reuse (repeated reuse was not run) puts the
break-even at the second reuse, or the third when the cost of collecting fits is counted. The larger fixed-library search
(100 CPU-seconds, conditional: only on the 8 admitted targets) was exact on 3 of 8.

## 6. Other controls
- A random fit among the first 20 instead of the first: the same 5 correct, 3 or 4 wrong admissions (5 seeds). The
  fits of a target showed a median of 2 different behaviours; 13 targets reached the cap of 20 collected fits
  with 20 different behaviours.
- Order of repair actions, as counterfactual schedules computed from the recorded runs (not measured runs): to the
  8 admissions that were reached, the rule (construct at the failing step first) takes 3.1 CPU-seconds, search
  first 41.1, random orders 7 to 31. Over all 102 targets the modelled totals are 735.6, 773.5 and 739.9 to 763.5.
- Names held out by the earlier study (30 ran): task exact for V 2 (argmin, valmax), for S 3; V correct 1
  (argmin); T correct 4 (argmin, lowermost, rightmost, uppermost).
- With nothing hidden and a tenth of the allowance, ordinary synthesis found a fitting program for 60 of 102
  tasks. This is journalled material for later work on telling "too little search" from "something is missing";
  no conclusion is drawn here.
- Development roster (development only): 17 ran, 0 against 0 on the primary.

## 7. What this shows and what it does not
- **Using the failure did not demonstrably help to solve the task** (9 against 6 of 102). Its recorded acquisition-search CPU was lower.
- **Evidence is a demonstrated bottleneck.** Three examples seen through another program rarely identify the missing
  operation. A check through a different program removes most wrong repairs and lost none of the five right ones, and still
  lets some through.
- **No cumulative benefit is shown.** Retained operations solved fewer later tasks than a fresh search.
- By the protocol's own section 15: no model stage before the first point is understood; work on evidence before
  growth; no claim of cumulative benefit.
- Level: at best a composition of existing primitives restoring a lost operation (5 operations here). Not a new
  capability, not a transferable procedure, not a result about puzzles.
- Limits: at most 4 nodes; one library and one generator; constructed two-call tasks; 26 operations excluded at
  setup, mostly those with a small universe of inputs; the operations study's outcomes were known beforehand;
  finite checks; one run. "Correct" means agreement of typed values on the final panel, not proof of recovery:
  in arm T, a candidate for `asobject` agrees with it on all 353 final cases, is admitted, and still fails its
  acquisition and reuse tasks; a possible reason is that a task can depend on the order of a set's elements.
  More examples are not the only remaining issue: bounded search, merging by observed values, representation
  and semantics limit the result too.

## 8. Reproduce
See `PROTOCOL.md` section 18. Per-target records: `full_out/targets/`; journals: `full_out/journal/`; admitted
operations: `full_out/library/` (read-only files).

## 9. Addendum of 14 November 2026: a diagnostic of the `combine` count difference
Added after the audit, with the independent review's agreement. No outcome, count or reading above is changed, and
nothing of this run was run again. The saved run remains the record of its own execution.

Section 1 records that for one operation (`combine`) the counts of usable pooled inputs differed by one between the
setup-only pass before the run and the run (313 and 312; 382 and 381), and that the cause was not established.

**What was found.** Of the 811 pooled container values, 34 hold functions. For some operations a pooled tuple then
gives a result that holds functions inside a set. A function's hash is its identity, so the order in which such a
set is read, and any operation that reads that order (first, last, totuple), can differ from one process to another.

**Reproduced sensitivity.** Stage A's own frozen setup step was used read-only for `combine` (no search, no
scoring, nothing written to this folder) in 80 diagnostic processes: four ways of starting the process, four times
each, with 0, 1, 7, 1000 and 54321 throwaway functions allocated before the library loads. The two usable counts
took values between 312 and 314 (of 320) and between 380 and 385 (of 400). Started directly, a process repeated its
own counts each time. Started through the CPU slot wrapper it did not always (three different series in four
runs). With the randomization of the address space switched off for the process it did again (four of four). The
pair recorded before the run (313, 382) was reproduced exactly. The pair recorded in the run (312, 381) was not
reproduced as a pair; each of its two values lies inside the observed range. This is consistent with a likely
explanation of the recorded difference. The memory history of the two original processes was not reconstructed, so
it is not shown to be the cause.

**Exposure, as raw counts of slices.** The diagnostic rebuilt the pooled slices of each completed target and counted,
among the tuples in which a container argument holds a function, those whose result holds a function inside a set.
Six operations have such tuples: `apply`, `combine`, `prapply`, `product`, `valmax`, `valmin`. In the final slice
(400 tuples each): 1, 12, 11, 33, 0, 0. In the admission slice (320 each): 1, 9, 5, 27, 5, 0. Twelve more operations
have tuples with such arguments and no such result. These are counts of tuples in rebuilt slices. They are not
counts of the usable inputs that were scored: the scored panels were not reconstructed.

**Three claims, kept apart.** An input that holds a function inside a container; a result that holds a function
inside a set; a changed outcome. The first two are measured above. The third was not tested: no setup, search or
scoring of this run was replayed. Nothing here shows that an outcome of stage A changed, and nothing here shows
that none could.

Scripts and reports: `experiments/evidence_across_failures_20261114/diagnostics/` at commit a250bd588:
`stage_a_layout_demo.py` (sha256 2c63607e...), `stage_a_layout_series.py` (4b96e82d...) with its report
`stage_a_layout_series.json` (30768822...), `stage_a_exposure.py` (769b0bbe...) with `stage_a_exposure.json`
(e0ca6695...).

**A second finding of the same day: the timeout of a time guard.** Found on 14 November 2026 by the independent
review in the follow-up experiment's code, and present in this run's code too (`episode.match_list`,
`consumers.stream_usable`): a timeout of a processor-time guard was caught as an ordinary error of one input, after
which the loop went on without its guard. In general such a swallowed timeout could change a count. For this run
the saved records exclude it. A guard fires only after its whole length (10, 20 or 30 processor seconds) has been
spent inside one guarded batch, and the searches are not under these guards. The processor time outside the seven
recorded searches is at most 3.529 seconds in any of the 119 completed episodes, and the printed interval is at most
1.95 seconds for any of the 26 targets excluded at setup (rounding margins included; no target lacks a recorded
time). So no guard can have fired in this run, and no record of it was affected by this defect. The statement is
specific to this run and rests on its recorded times; the independent review reproduced the bound. Script and
report: `experiments/evidence_across_failures_20261114/diagnostics/stage_a_guard_bound.py` (sha256 67ae0400...) with
`stage_a_guard_bound_with_margins.json` (d15b6f27...), commit 29e7688d5.
