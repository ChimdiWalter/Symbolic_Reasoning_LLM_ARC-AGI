# Evidence across several failures (EAF1): results

Author: Chimdi Walter Ndubuisi. 14 November 2026.

**Audit status (14 November 2026).** The independent review audited the numbers and the custody of this run: both
pass, and the declared criterion is not met. It asked for qualifications of the wording, which are applied below and
listed in section 9, and it confirmed the edited text the same day: the numbers, the custody and the corrected
narrative pass its scoped review. The run is closed and is not replayed. The tables and lists marked "rendered" are
written by `results_tables_eaf.py` and `results_names_eaf.py` from `full_out/`; no number in them was typed by hand.

## 0. Summary

**The declared criterion is not met.** Both arms compared use the same nine argument tuples and one demonstrated
output for each tuple: one arm reads all nine through one surrounding program, the other reads disjoint groups of
three through three surrounding programs. Three programs gave fewer wrong first answers (first fits that fail on
fresh inputs: 14 against 19, of 95 operations) and one more right one (11 against 10). Seven operations are favourable and two unfavourable. The exact
two-sided sign test gives p = 0.18, above the declared 0.05. This run does not show the specified benefit.

What the difference consists of. Wherever both arms found an answer, they found the same expression, with one
exception. The three-wrapper arm rejected seven of the one-wrapper arm's wrong answers. In six of those it then found
nothing; in one (`asobject`) it found a right expression. In two operations it accepted a wrong expression where the
one-wrapper arm found nothing.

Two larger patterns are visible in the declared descriptive readings, and neither is the declared comparison. More
examples through one wrapper: three, six and nine examples give 44, 23 and 19 wrong first answers and 5, 9 and 10
right ones. And the search itself often comes back empty: in 45 of the 95 operations no arm found any answer, and in
69 of the 70 fruitless searches of the three-wrapper arm the implemented search exhausted its four-node enumeration
under the declared demonstrations and presets without finding a fit. That points to a practical limit of search
coverage. It does not show that those operations cannot be expressed.

All twelve checks after the run passed, no time guard can have fired, and the found expressions were read before
any count was written.

## 1. What was run

**The question.** An operation of the library is removed. A program that needs it fails. From the outputs the program
should have produced, a search builds a replacement for the missing call out of the operations that remain. The
first replacement that reproduces every output shown to it (the "first fit") is often wrong on fresh inputs. Does it
help to show the search the same nine inputs through three different surrounding programs, instead of through one?

**Terms.** A *wrapper* is the one-argument library operation around the missing call in a program
`wrapper(missing(arguments))`. An *arm* is one way of choosing which demonstrated outputs the search sees. The five
arms use the same nine argument tuples of a target:

| arm | wrappers | examples through each wrapper |
|---|---|---|
| A1x3 | one | three |
| A1x6 | one | six |
| A1x9 | one | nine |
| A2x3 | two | three each (six in all) |
| A3x3 | three | three each (nine in all) |

Both nine-example arms use the same nine argument tuples and one demonstrated output for each tuple. A1x9 applies
wrapper 1 to all nine. A3x3 applies wrappers 1, 2 and 3 to disjoint groups of three, so no wrapper of A3x3 sees all
nine tuples. It is nine observations in each arm.

A first fit is *right* when it agrees with the removed operation, as typed values, on every input of a final panel
that no search saw; *wrong* when it does not; and there is *none* when the search ends without a fit. The
*construction cohort* is every target that passes the setup step. The *admission* and *reuse* cohorts are the nested
subsets with a fourth and a fifth usable wrapper.

**Kind of study.** A development comparison on a known constructed benchmark: the operations study and stage A ran
on these same operations and their outcomes were known before this design. CPU only, invented inputs, no model.
Bottom-up enumeration of expressions of at most four nodes, 10 processor seconds per arm. Nothing new is claimed
about the method (protocol, section 10).

**Freeze, review, launch.** The protocol, sources, tests and setup record were frozen by hash (`FREEZE_3.json`
dd959ba9...6660, setup record `SETUP_RECORD_ALL_3.json` 66712a3e...2624, protocol `PROTOCOL.md` 23c92744...cf10,
commit e8992d389). Two earlier freezes were withdrawn before any launch: the first because one operation's inputs
differed from one process to another (found by the author), the second because a timeout of the final check was
caught as an ordinary error (found by the independent review). The independent review passed the exact third
freeze, and the full roster was then launched once, at 14:24:56Z on 14 November 2026, as detached job `eaf1_full`.
It ended with exit 0 at 15:01:46Z. The receipt `RECEIPT_ALL_ROSTER.json` (f94f9878...42aa) was written before the
first target.

**The cohort, committed before the run.** 145 operations. 110 are eligible and 35 are excluded at setup: 16 have too
few usable pooled inputs, 12 fail the acquisition check, 4 have too few generator examples, 3 have fewer than three
usable wrappers. Of the 12, 7 are excluded because a wrapper does not run on one of the nine tuples, and 5 because a
trivial repair reproduces the demonstrations on the generator tuples and on every redraw. These are exclusions from
the cohort; they are not operations that the search failed to build. The primary comparison is read on the 95
eligible operations outside the 20 development names (admission cohort 87, reuse cohort 83). The nine tuples come
from the generator for 96 eligible operations and from a redraw for 14.

**The run** (rendered; the block outside the development roster).

- Targets listed 145, run 145, not yet run 0 (whole roster). In this block: 125 ran; construction cohort 95, admission cohort 87, reuse cohort 83; excluded at setup 30; incomplete 0.
- Exclusions by kind: acquisition_check 10, fewer_than_three_wrappers 3, generator 4, too_few_usable_pooled_inputs 13.
- Final panels of the 95 done targets: generator inputs median 30 (least 25); pooled inputs median 323 (least 35); short of the declared number: none.
- Roles unavailable for some targets (admission or reuse): 12 targets.
- Processor time, sum over the done targets' own intervals: 1882.9 seconds.
- Whole process (GNU time, outer measurement): user 2179.48 s, system 24.61 s, elapsed 36:50.45, exit status 0, maximum resident set 515488 kB.
- Setup of the run against the committed setup record: compared 145 targets; decisions differ 0; counts differ 0.

**Resources.** Whole job, from the outer timing record: 2,179.48 seconds of user time and 24.61 of system time, 36
minutes 50 seconds elapsed, peak memory 515,488 kB. The sum of the done targets' own intervals given above is a
subtotal inside that and is not to be added to it. No GPU, no model.

**Checks after the run** (rendered from `AFTER_RUN_CHECK.json`, written by `after_run_eaf.py`).

- All checks passed: True (12 checks). Checker sha256 ddf49bde1ee051227024cf4300087876d25b61e806fb9528b444d3d02c4e3f92.
- Failed checks: none.
- Searches that used up the allowance or found their first fit after 80% of it, per arm: A1x3 0, A1x6 0, A1x9 1, A2x3 0, A3x3 1.
- Can a CPU guard have fired? No guard can have fired for any target: True. Largest processor time outside the searches: 2.681 s (`mapply`). Not excluded by the bound: candidate wrappers at setup (10.0 s): none; checks of a candidate (30.0 s): none; streams of pooled inputs (20.0 s): none. Targets without a recorded time: none.
- Output folder: 355 files, manifest sha256 0ee43b0932ce0e5e29f4eeeb633b5fe407234b057718e717efd6d8627df01e36; SUMMARY.json sha256 77704e3b7e1ed1d3879aa7db286c0b6118614b65724aa629dca1977b7277758e.

The twelve checks: the freeze still verifies; one read-only receipt names the freeze, the setup record and the
output folder; the job started once and ended with exit 0; the run's manifest names the frozen code, the whole
roster and the allowance; there is a record for every one of the 145 targets and none is incomplete; every done
target's journal holds exactly the sealed records its path requires, in order, with one start and one end; the
library files match their records and seals; the stored summary equals one recomputed from the records; the run's
setup decisions and counts equal the committed record; the primary reading is complete.

**Could a time guard have fired?** By a conservative bound from the recorded times, no, for every target. A guard
needs its whole length (10, 20 or 30 processor seconds) inside one guarded batch, and the searches are not under
these guards. The largest processor time that a done target spent outside its searches is 2.681 seconds; for the
targets excluded at setup the largest printed interval is 2.1 seconds. Rounding margins are added before the
comparison and no target lacks a recorded time. The bound rests on the recorded times and holds for this run. It
does not make the stream filter inherited from stage A safe in general.

**Searches at the allowance.** One target, `crop`, ended at the allowance of 10 processor seconds with no fit, in
both A1x9 and A3x3. Every other search of the five arms ended with a fit or by exhausting its four-node enumeration. On another
machine `crop` could end differently. It can move at most one target of the primary table, and with 8 favourable
against 2, or 7 against 3, the declared test stays above 0.05 (p = 0.109 and p = 0.344).

## 2. Primary comparison (rendered)

Status of the declared criterion: **not_met** (criterion met: False).

Targets read: 95. Rows are A3x3, columns are A1x9.

| A3x3 \ A1x9 | none | right | wrong |
|---|---|---|---|
| none | 64 | 0 | 6 |
| right | 0 | 10 | 1 |
| wrong | 2 | 0 | 12 |

- Wrong first fits: A3x3 14, A1x9 19. Right first fits: A3x3 11, A1x9 10.
- Favourable targets (A1x9 wrong, A3x3 not): 7: `asobject`, `astuple`, `canvas`, `initset`, `order`, `outbox`, `rot270`.
- Unfavourable targets (A3x3 wrong, A1x9 not): 2: `difference`, `height`.
- Exact two-sided sign test over those 9 targets: p = 0.179688.
- The four conditions: 1_fewer_wrong_in_A3x3: True; 2_sign_test_below_0.05: False; 3_right_in_A3x3_not_fewer_than_in_A1x9: True; 4_at_least_one_right_in_A3x3: True. All four hold: False.
- First fits counted as wrong only because their final check ran out of time: 0: none.
- Incomplete targets: none. Missing eligible targets: none. Done targets outside the committed cohort: none. Targets whose setup differs from the committed record: none.

**Reading.** Conditions 1, 3 and 4 hold and condition 2 does not, so the declared reading "fewer wrong first fits at
matched evidence" is **not met**. The difference goes in the expected direction (14 wrong against 19; 7 favourable
targets against 2) and the declared test does not separate it from chance (p = 0.18).

By the protocol's rule the reduction is reported as reduced ambiguity, possibly by abstention. Six of the seven
favourable targets are a wrong first fit that became no fit (`astuple`, `canvas`, `initset`, `order`, `outbox`,
`rot270`), and one became right (`asobject`). Right first fits are 11 against 10. That is one target, and no claim
of more right construction is made.

The two unfavourable targets (`difference`, `height`) are wrong first fits of the three-wrapper arm where the
one-wrapper arm found nothing.

## 3. Secondary readings (rendered; descriptive, uncorrected)

### 3.1 Two wrappers against one, at six examples

Targets read: 95. Rows are A2x3, columns are A1x6.

| A2x3 \ A1x6 | none | right | wrong |
|---|---|---|---|
| none | 58 | 0 | 5 |
| right | 0 | 9 | 2 |
| wrong | 5 | 0 | 16 |

- Wrong first fits: A2x3 21, A1x6 23. Right first fits: A2x3 11, A1x6 9.
- Favourable targets (A1x6 wrong, A2x3 not): 7: `asobject`, `astuple`, `canvas`, `hconcat`, `order`, `rot270`, `sfilter`.
- Unfavourable targets (A2x3 wrong, A1x6 not): 5: `centerofmass`, `difference`, `height`, `manhattan`, `vperiod`.
- Exact two-sided sign test over those 12 targets: p = 0.774414.
- The four conditions: 1_fewer_wrong_in_A2x3: True; 2_sign_test_below_0.05: False; 3_right_in_A2x3_not_fewer_than_in_A1x6: True; 4_at_least_one_right_in_A2x3: True. All four hold: False.
- First fits counted as wrong only because their final check ran out of time: 0: none.
- Incomplete targets: none. Missing eligible targets: none. Done targets outside the committed cohort: none. Targets whose setup differs from the committed record: none.

No difference is shown: 21 wrong against 23, 11 right against 9, 7 favourable targets against 5.

### 3.2 The five arms side by side

| arm | targets | none | right | wrong | incomplete | acquisition task exact through wrapper 1, 2, 3 | search CPU sum (s) | CPU to first fits, sum (s) | stops |
|---|---|---|---|---|---|---|---|---|---|
| A1x3 | 95 | 46 | 5 | 44 | 0 | 12, 8, 6 | 142.5 | 17.52 | found 49, size_exhausted 46 |
| A1x6 | 95 | 63 | 9 | 23 | 0 | 17, 11, 10 | 224.8 | 11.3 | found 32, size_exhausted 63 |
| A1x9 | 95 | 66 | 10 | 19 | 0 | 18, 12, 11 | 289.9 | 20.23 | budget_cpu 1, found 29, size_exhausted 65 |
| A2x3 | 95 | 63 | 11 | 21 | 0 | 14, 14, 10 | 225.1 | 18.34 | found 32, size_exhausted 63 |
| A3x3 | 95 | 70 | 11 | 14 | 0 | 12, 11, 10 | 297.0 | 19.46 | budget_cpu 1, found 25, size_exhausted 69 |

Function cap reached (searches): A1x3 0, A1x6 0, A1x9 0, A2x3 0, A3x3 0. Candidates tested (sum): A1x3 1522183, A1x6 1915267, A1x9 2063391, A2x3 1970914, A3x3 2147024.

The largest differences in this table are between numbers of examples, not between numbers of wrappers. Through one
wrapper, three, six and nine examples give 44, 23 and 19 wrong first fits and 5, 9 and 10 right ones. The arms are
nested (the six examples contain the three) and no test was declared for this.

The column of task exactness shows the other side of the three-wrapper arm's abstentions. The first fits of A1x9
make the acquisition task through wrapper 1 exact on the final panel for 18 targets: its 10 right ones and 8 wrong
ones. Those of A3x3 do so for 12: its 11 right ones and 1 wrong one. A wrong operation can still solve the one task
it was fitted to. Seven of those eight wrong fits are the ones that the three-wrapper arm rejected.

### 3.3 Admission

| arm | targets in the admission cohort | first fits | admitted | right and admitted | wrong and admitted | right and not admitted |
|---|---|---|---|---|---|---|
| A1x3 | 87 | 47 | 9 | 5 | 4 | 0 |
| A1x6 | 87 | 31 | 12 | 9 | 3 | 0 |
| A1x9 | 87 | 28 | 13 | 10 | 3 | 0 |
| A2x3 | 87 | 31 | 13 | 10 | 3 | 1 |
| A3x3 | 87 | 24 | 12 | 10 | 2 | 1 |

Wrong admissions under stage A's rule are 4, 3, 3, 3 and 2 across the five arms. `first` and `square` are admitted
wrongly in the three-wrapper arm too. One right first fit is not admitted (`asobject`, arms A2x3 and A3x3; see
section 4).

### 3.4 Reuse on a different task

| source | available | reuse task exact on the final panel |
|---|---|---|
| sealed library of A1x3, no search | 7 libraries | 4 |
| sealed library of A1x6, no search | 10 libraries | 8 |
| sealed library of A1x9, no search | 11 libraries | 9 |
| sealed library of A2x3, no search | 11 libraries | 9 |
| sealed library of A3x3, no search | 10 libraries | 9 |
| fresh synthesis of the whole program | 38 fits (allowance_used_up 44, fit 38, unavailable 1; unavailable 1) | 7 |
| fresh repair of the missing call | 45 fits (allowance_used_up 1, complete_negative 36, fit 45, unavailable 1; unavailable 1) | 11 |

Targets whose three reuse examples were not all usable: `centerofmass`.

The declared reading: the sealed library of A3x3, used with no search, makes the reuse task exact for 9 targets (of
its 10 libraries); the library of A1x3 for 4 (of 7); a fresh synthesis of the whole program for 7; a fresh repair of
the missing call for 11. The library and the fresh repair solve partly different targets: both are exact on 5, the
library alone on 4, the fresh repair alone on 6. The fresh repair also returns 34 fits that are not exact; the
library of A3x3 returns one (`square`). The libraries made with six or nine examples, through one, two or three
wrappers, are nearly the same set.

### 3.5 Names held out by the earlier study

| arm | targets | none | right | wrong |
|---|---|---|---|---|
| A1x3 | 26 | 7 | 1 | 18 |
| A1x6 | 26 | 13 | 5 | 8 |
| A1x9 | 26 | 15 | 5 | 6 |
| A2x3 | 26 | 12 | 5 | 9 |
| A3x3 | 26 | 14 | 5 | 7 |

A3x3 against A1x9 on these names: favourable 0, unfavourable 1, p = 1.

No separate claim. The one discordant target here is `height`, unfavourable.

## 4. The found expressions, read

Every found expression of the 95 targets was read (`read_expressions.py`) before any count above was written. The
lists below are rendered from the records.

- **A1x3.** Right first fits 5: `argmin`, `equality`, `pair`, `product`, `vconcat`. Wrong first fits 44: `adjacent`, `argmax`, `asobject`, `astuple`, `bordering`, `canvas`, `center`, `centerofmass`, `colorcount`, `colorfilter`, `contained`, `delta`, `extract`, `first`, `greater`, `hconcat`, `height`, `hline`, `hmatching`, `hperiod`, `initset`, `leastcommon`, `leftmost`, `lowermost`, `lrcorner`, `manhattan`, `mostcolor`, `move`, `order`, `outbox`, `portrait`, `position`, `recolor`, `replace`, `rightmost`, `rot270`, `sfilter`, `square`, `ulcorner`, `uppermost`, `valmin`, `vline`, `vmatching`, `vperiod`.
- **A1x6.** Right first fits 9: `argmin`, `equality`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. Wrong first fits 23: `adjacent`, `asobject`, `astuple`, `bordering`, `canvas`, `extract`, `first`, `greater`, `hconcat`, `hline`, `hmatching`, `initset`, `lrcorner`, `mostcolor`, `order`, `outbox`, `portrait`, `replace`, `rot270`, `sfilter`, `square`, `vline`, `vmatching`.
- **A1x9.** Right first fits 10: `argmin`, `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. Wrong first fits 19: `adjacent`, `asobject`, `astuple`, `bordering`, `canvas`, `extract`, `first`, `greater`, `hmatching`, `initset`, `lrcorner`, `mostcolor`, `order`, `outbox`, `portrait`, `rot270`, `square`, `vline`, `vmatching`.
- **A2x3.** Right first fits 11: `argmin`, `asobject`, `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. Wrong first fits 21: `adjacent`, `bordering`, `centerofmass`, `difference`, `extract`, `first`, `greater`, `height`, `hline`, `hmatching`, `initset`, `lrcorner`, `manhattan`, `mostcolor`, `outbox`, `portrait`, `replace`, `square`, `vline`, `vmatching`, `vperiod`.
- **A3x3.** Right first fits 11: `argmin`, `asobject`, `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. Wrong first fits 14: `adjacent`, `bordering`, `difference`, `extract`, `first`, `greater`, `height`, `hmatching`, `lrcorner`, `mostcolor`, `portrait`, `square`, `vline`, `vmatching`.

**Admission, by arm** (rendered).

- **A1x3.** Wrong and admitted 4: `first`, `leastcommon`, `outbox`, `ulcorner`. Right and not admitted none. Right and admitted 5: `argmin`, `equality`, `pair`, `product`, `vconcat`.
- **A1x6.** Wrong and admitted 3: `first`, `outbox`, `square`. Right and not admitted none. Right and admitted 9: `argmin`, `equality`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`.
- **A1x9.** Wrong and admitted 3: `first`, `outbox`, `square`. Right and not admitted none. Right and admitted 10: `argmin`, `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`.
- **A2x3.** Wrong and admitted 3: `first`, `outbox`, `square`. Right and not admitted 1: `asobject`. Right and admitted 10: `argmin`, `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`.
- **A3x3.** Wrong and admitted 2: `first`, `square`. Right and not admitted 1: `asobject`. Right and admitted 10: `argmin`, `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`.

**Reuse, by source** (rendered).

- **Sealed library of A1x3.** Reuse task exact 4: `equality`, `pair`, `product`, `vconcat`. With a library and not exact 3: `leastcommon`, `outbox`, `ulcorner`.
- **Sealed library of A1x6.** Reuse task exact 8: `equality`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. With a library and not exact 2: `outbox`, `square`.
- **Sealed library of A1x9.** Reuse task exact 9: `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. With a library and not exact 2: `outbox`, `square`.
- **Sealed library of A2x3.** Reuse task exact 9: `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. With a library and not exact 2: `outbox`, `square`.
- **Sealed library of A3x3.** Reuse task exact 9: `equality`, `hconcat`, `leftmost`, `lowermost`, `pair`, `product`, `rightmost`, `uppermost`, `vconcat`. With a library and not exact 1: `square`.
- **Fresh synthesis of the whole program.** Reuse task exact 7: `asindices`, `asobject`, `normalize`, `repeat`, `rightmost`, `size`, `vperiod`. Fits that are not exact: 31. Searches that used up the allowance: 44.
- **Fresh repair of the missing call.** Reuse task exact 11: `asindices`, `asobject`, `normalize`, `pair`, `product`, `repeat`, `rightmost`, `size`, `uppermost`, `vconcat`, `vperiod`. Fits that are not exact: 34. Searches that used up the allowance: 1.

**Searches that ended at the allowance, by arm** (rendered).

- A1x3: none.
- A1x6: none.
- A1x9: 1: `crop`.
- A2x3: none.
- A3x3: 1: `crop`.

**Excluded at setup, by kind** (rendered; outside the development roster).

- acquisition_check 10: `corners`, `dedupe`, `index`, `intersection`, `leastcolor`, `llcorner`, `prapply`, `sizefilter`, `totuple`, `urcorner`.
- fewer_than_three_wrappers 3: `identity`, `paint`, `underpaint`.
- generator 4: `even`, `positive`, `toivec`, `tojvec`.
- too_few_usable_pooled_inputs 13: `crement`, `decrement`, `dneighbors`, `double`, `halve`, `hfrontier`, `increment`, `ineighbors`, `invert`, `maximum`, `merge`, `minimum`, `neighbors`.

**What the reading found.**

1. *The same expression in both arms.* In the 23 targets where both A1x9 and A3x3 found a fit, the expression is the
   same in 22. The exception is `asobject`: `merge(grid)` through one wrapper (wrong) and `merge(partition(grid))`
   through three (right). Both arms try the same candidates in the same order; the wrappers decide which one is
   accepted.
2. *What three wrappers rejected.* The six fits that the three-wrapper arm rejected and did not replace are wrong
   values that wrapper 1 maps to the same result; several differ in type or structure: a set where a tuple is
   wanted (`astuple`: `insert(a, initset(b))`, read through `minimum`), a tuple where a set is wanted (`initset`:
   `repeat(value, ONE)`, read through `first`), a one-element container around the input (`rot270`:
   `repeat(grid, ONE)`, read through `width`), and `canvas` and `order` likewise. `outbox` instead has the wrong set
   of indices while preserving the dimensions seen by its first two wrappers (`height`, `width`). Another wrapper
   sees the difference.
3. *The two unfavourable targets.* For `difference` and `height` the single wrapper of the one-wrapper arm shows the
   value almost completely (`totuple`; `double`) and nine examples through it reject every candidate. The
   three-wrapper arm sees that wrapper on three examples only and two less revealing wrappers on the other six, and a
   wrong candidate passes all of them (`prapply(either, a, DOWN)`; `size(apply(flip, piece))`). Splitting nine
   examples among three wrappers gives each wrapper fewer inputs. This is my reading of two cases, not a tested
   claim.
4. *The right ones.* The eleven right first fits are compact re-expressions consistent with the source definitions
   on their intended domains, for example `hconcat` as `papply(combine, a, b)`, `product` as
   `prapply(astuple, a, b)`, `leftmost` as `valmin(toindices(patch), last)`, `argmin` as
   `first(order(container, compfunc))`, `equality` as `contained(a, initset(b))`. "Right" keeps its declared
   meaning: agreement of typed values on the finite final panel, here 25 or 30 generator inputs and 281 to 400
   pooled inputs. It is not a proof of identity. I saw none that is right for a degenerate reason.
5. *Truth values.* Eight of the twelve targets where both arms are wrong return a truth value (`adjacent`,
   `bordering`, `greater`, `hmatching`, `portrait`, `square`, `vline`, `vmatching`). For a Boolean-valued candidate,
   deterministic wrappers cannot add information beyond its Boolean result on a given input. On these eight targets
   the nine demonstrations did not identify the predicate in this search. The fits are predicates such as
   `contained(TWO_BY_ZERO, a)`.
6. *Right, and still failing a task.* `merge(partition(grid))` agrees with `asobject` on all 353 final inputs as
   typed values (30 generator and 323 pooled), yet it is not admitted and its task through wrapper 3 is not exact.
   Wrapper eligibility tests runtime usability, not annotation compatibility: wrapper 3 (`partition`) and wrapper 4
   (`fgpartition`) are annotated for a grid and here receive an object, a frozenset of cells. They walk through it
   in the order in which its elements come, and two equal sets built in different orders can come in different
   orders. Typed canonical equality is therefore not contextual substitutability when the consumer observes
   iteration order. This is a localized explanation of one case, not an admitted capability.
   A post hoc diagnostic execution, after the frozen run, on 200 seeded generated-grid draws (not a regrouping of
   the frozen records and not part of the primary score; the draws are not guaranteed to be distinct;
   `diagnostics/asobject_set_order_check.py` 38d704d56a13..., output `asobject_set_order_check.json` d4fd0382639e...): the two
   expressions are equal as typed values on all 200, and each of the two wrappers gives a different result for the
   two on 84. It is exploratory evidence of the mechanism, not another frozen outcome and not a general bound. Stage
   A's record notes the same for this operation.
7. *Fits on three examples.* In 19 of the 64 targets where neither nine-example arm found a fit, an arm with fewer
   examples did, and every one of those fits is wrong.

## 5. What this shows and what it does not

On this benchmark, at nine examples, reading the missing call through three wrappers instead of one did not give a
demonstrated reduction of wrong first fits. The difference is five fewer wrong first fits of 95, in the expected
direction, and the declared test does not separate it from chance.

The expressions show how the two arms differ. Three wrappers reject wrong values that wrapper 1 maps to the same
result; several of those differ in type or structure. Each of the three wrappers also sees fewer inputs, which let
two wrong candidates through. Most of what three wrappers removed was not replaced by anything right. No advantage
of a retained library is demonstrated: reuse with no search is exact for 9 of 83 targets in both nine-example arms,
and a fresh repair for 11.

The four outcomes, kept apart, for A3x3 and A1x9. A fit to the demonstrations: 25 and 29 first fits of 95.
Independent correctness on the final panel: 11 and 10 right. Admission as a capability (cohort of 87): 12 admitted,
10 right and 2 wrong; 13 admitted, 10 right and 3 wrong. Successful reuse with no search (cohort of 83): 9 of 10
libraries exact; 9 of 11.

It does not show that several views of one failure cannot help: another assignment of wrappers, more examples for
each wrapper, a larger size limit or another library could behave differently, and "not demonstrated" never means
"cannot help". It shows nothing about grouping failures by cause without being told, about a library that grows and
helps, about a new capability, or about puzzles.

Level. At best this restores removed operations by composing existing ones. In the three-wrapper arm 11 of 95
removed operations have a right first fit, 10 of them are admitted, and 2 wrong ones are admitted with them. No rung
of the project's plan is earned by this run.

Limits that hold whatever the outcome (protocol, section 9). Constructed two-call tasks on invented inputs; at most
four nodes; one library; one generator; one seeded assignment of wrappers with no counterbalancing; known operation
families; and a direction suggested by stage A on the same operations. "Right" is agreement of typed values on a
finite panel, not proof that the operation was recovered. One run.

## 6. Declared before the run and carried here

- **Seeds.** The order of a target's wrappers and its pooled inputs are drawn under this experiment's own seed tags.
  That choice was made after a development check showed that stage A's order would have repeated stage A's arms,
  and all earlier outcomes on these operations were known. By chance, wrapper 1 equals stage A's acquisition wrapper
  on 11 of the 95 primary targets, and all three wrappers on 3. This is not an untouched benchmark.
- **Inputs.** A pooled tuple in which a container argument holds a function is dropped before the slices are cut,
  because a set that holds functions can be read in a different order by different processes. One eligibility
  decision followed from the rule (`sfilter` became eligible through a later redraw).
- **A check that runs out of time.** A first fit whose final check ran out of its 30 processor seconds before any
  counterexample counts as wrong. That is a coding convention, not evidence that the candidate is wrong. Such first
  fits are listed, the comparison is also read without them, and a positive reading needs both. There is none in
  this run.
- **Other checks under a time guard.** Admission, task exactness, reuse, and the streams of pooled inputs count a
  timed-out check as not exact or not usable without a mark, and the stream filter inherited from stage A still
  treats its timeout as an ordinary error of one input. Section 1 gives this run's bound: no guard can have fired.
- **Library files.** Each holds a processor time through its admission record, so its hash is a record of this run
  and is not expected to repeat in another run.
- **Process dependence.** Checks before the run (values of the setup step under three memory layouts for 138
  operations; whole development episodes under two more) found no difference between processes. They are finite
  support, not proof: inside a search a candidate can still build a set that holds functions.
- **Allowance.** The allowance is counted in processor seconds, so a search that used it up could end differently on
  another machine. Section 1 names the one target where that happened.

## 7. What it leads to

The protocol (section 11) fixed this in advance for a criterion that is not met: diversity of evidence has not shown
the specified benefit within this cohort, grammar, wrapper assignment, generator and budget. That does not show
there is no benefit elsewhere, nor that a language below the library is necessary. Effect sizes, abstention and the
limits of the search are to be reported before a next direction is chosen:

- **Effect size.** Five fewer wrong first fits of 95 (19 to 14); 7 favourable targets against 2. With two
  unfavourable targets the declared test would have needed ten favourable ones (p = 0.039); with none, six.
- **Abstention.** Six of the seven favourable targets are a wrong fit that became no fit. The three-wrapper arm's
  first fits solve the first task on fresh inputs less often (12 against 18 targets), because the fits it rejects
  did solve that task.
- **Limits of the search.** In 45 of the 95 operations no arm found any fit. In 69 of the 70 fruitless searches of
  the three-wrapper arm, the implemented search exhausted its four-node enumeration under the declared
  demonstrations and presets without finding a fit. That enumeration merges expressions by their observed values,
  filters by value and type, and has caps, so this is a practical bottleneck of search coverage. It supports an
  experiment on depth or on the language. It does not establish that these operations cannot be expressed, nor that
  smaller building blocks are necessary. The eleven that are rebuilt are rebuilt by the one-wrapper arm with nine
  examples too, except one.

The choice of the next direction is the author's.

## 8. Reproduce

See `PROTOCOL.md` section 12. Per-target records: `full_out/targets/`; journals: `full_out/journal/`; admitted
operations: `full_out/library/` (read-only files); summary: `full_out/SUMMARY.json` (77704e3b...758e). The 355 files
of the output folder are listed with their hashes in `FULL_OUT_MANIFEST.sha256` (0ee43b09...1e36). The checks after
the run are in `AFTER_RUN_CHECK.json` (`after_run_eaf.py`); the tables and lists above are rendered by
`results_tables_eaf.py` and `results_names_eaf.py`. The detached job's own files (outer timing record `time.txt`,
`run.status`, `stdout.log`, `cmd.txt`) are copied into `detached_job_record/`. The run was launched once and is not
run again.

## 9. Corrections to this record
- 14 November 2026, after the independent review's note on the finished run: sections 0, 1 and 7 said that the
  fruitless searches "had tried every expression of up to four nodes" and that most removed operations "cannot be
  rebuilt whatever evidence is shown". Both went beyond what was measured and are replaced by the wording now in
  those sections. No number changed.
- 14 November 2026, after the independent review's terminal audit (numbers and custody pass): the allocation of the
  nine demonstrations is defined once in sections 0 and 1; section 4 point 2 and section 5 no longer say that all
  six rejected fits have the wrong kind (`outbox` has the wrong set of indices); point 4 says "compact
  re-expressions" and keeps the finite-panel meaning of "right"; point 5 states the truth-value limit as the review
  words it; point 6 states the interface limit and labels the 200-grid check as a post hoc diagnostic. No number
  changed.
