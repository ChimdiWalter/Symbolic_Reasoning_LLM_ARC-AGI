# Evidence across several failures (EAF1): protocol

Author: Chimdi Walter Ndubuisi. 14 November 2026. Frozen by `FREEZE_3.json`, which lists the sha256 of this file,
of every source and test file, of the committed setup record, and of stage A's own freeze. A first freeze
(`FREEZE.json`, commit 99423f985) was withdrawn the same day, before any check or launch: a source of values that
differ from one process to another was found in the pooled inputs and removed (section 4, point 4). A second freeze
(`FREEZE_2.json`, commit f9bc9184d) was withdrawn the same day before the launch: the independent review found that
the timeout of the final check's guard was caught as an ordinary error, so the rule of section 6 could not apply; the
code was corrected and fault tests were added (section 8). Chosen by the author on
14 November among four options, on these terms: the design was read by the independent review before any code (its
amendments are in this text), and the run waits for its check of the exact freeze. CPU only, no model.

## 0. What kind of study this is
A development comparison on a known constructed benchmark. The operations study and visible-failure construction,
stage A, ran on these same operations and their outcomes are known. This is a new experiment with its own protocol,
folder and identifiers. It does not change or reinterpret stage A or [an earlier unpublished experiment].

**What was known beforehand.** Stage A's table of admission evidence already showed, on these same operations, that
a check through a different program let fewer wrong repairs through than the same number of examples of the same
program (9 against 14, 5 against 9, 3 against 7). The direction tested here was therefore suggested by data from
this benchmark. This experiment asks the next question, whether the same kind of evidence used inside the search
and at matched inputs reduces wrong first fits, with wrappers and pooled inputs drawn afresh. It is not an
untouched confirmation.

## 1. Question
**At matched acquisition inputs and number of examples, does replacing one observation wrapper by a fixed seeded
collection of wrappers reduce wrong first fits while keeping a useful yield of right ones, under the declared
search limits?** This tests whether ambiguity is reduced. It does not assume that several wrappers give strictly
stronger or equally informative constraints.

Words. A **wrapper** is the one-argument library operation `post` around the missing call in a consumer
`post(X(arguments))`. A consumer plays the part of a task that failed because the operation X is missing. A
**first fit** is the first expression, in the fixed order of the search, that reproduces every output shown to an
arm. A **target** is the operation X that was removed.

## 2. Setting (stage A's modules and the operations study's are imported unchanged and checked by hash)
The 155-operation library; a target X removed with its whole family; invented inputs (the seeded typed generator,
66 examples per target; pooled inputs for checks); typed bottom-up enumeration of at most 4 nodes for the missing
call, a candidate being accepted when every consumer of the arm reproduces its demonstrated outputs (compared as
canonical typed values; a wrapper that raises on a candidate's value rejects it); the evaluator alone holds the
true X.

**This experiment's own seeds.** The order of a target's wrappers and its pooled inputs are drawn under this
experiment's seed tags (`eaf1-wrapper:` and `eaf1-seq`). Stage A's order and pooled inputs are not reused: with
them the arm with one wrapper and three examples would repeat stage A's failure-visible arm, and part of every
outcome could be computed from stage A's records. What is shared with stage A is stated here: the targets, the
library, the generator (the 66 generator examples of a target are the same, so the first three argument tuples are
the ones stage A showed), and the pool of candidate wrappers.

## 3. Arms: the one thing that changes is what the search may see
Nine argument tuples per target, fixed, and three wrappers fixed at setup.

| arm | demonstrated outputs |
|---|---|
| A1x3 (one wrapper, three examples) | tuples 0 to 2 through wrapper 1 |
| A1x6 (one wrapper, six examples) | tuples 0 to 5 through wrapper 1 |
| A1x9 (one wrapper, nine examples) | tuples 0 to 8 through wrapper 1 |
| A2x3 (two wrappers, three examples each) | tuples 0 to 2 through wrapper 1, tuples 3 to 5 through wrapper 2 |
| A3x3 (three wrappers, three examples each) | tuples 0 to 2 through wrapper 1, 3 to 5 through wrapper 2, 6 to 8 through wrapper 3 |

A1x9 and A3x3 receive the same nine tuples and nine demonstrated outputs; A1x6 and A2x3 the same six. Between
them only the wrappers differ. This changes the observation functions and their information content. It does not
add constraints to a common one-wrapper specification, isolate the use of an error message, or test whether the
system can group failures by cause on its own. Wrapper identities and the assignment of triples are fixed from
setup by the seeded order; there is no counterbalancing, and that scope is stated with every result.

Every arm has its own search state, with the same operations, order, size limit (4 nodes), caps (300
function-valued entries, 250,000 bank entries) and CPU allowance (10 process-CPU seconds). The evaluation of
wrappers is charged to that allowance. Until one of them accepts a candidate, A1x9 and A3x3 enumerate the same
candidates in the same order, because candidates are merged by their values on the same nine tuples; they differ
in which candidate is accepted. Arms with fewer tuples merge more candidates. Equal caps do not mean equal numbers of candidates tried, so stops,
candidate counts, completed levels, cap flags, CPU spent and CPU to the first fit are all reported. No arm or
target may use a component built by another arm or target.

## 4. Eligibility: nested cohorts, committed before any search
All of this is decided on setup records only, by code that runs no search.

1. **Generator.** 66 examples, or the target is excluded.
2. **Candidate wrappers.** One-argument library operations outside the removed family and everything that depends
   on it, never the identity, that run on X's result for all twelve setup examples (generator 24 to 35), give
   usable values and at least two different outputs. A candidate with the same twelve outputs as an earlier one
   is dropped (stage A's function, unchanged). The remaining names are sorted and shuffled under this experiment's
   seed.
3. **Eligible wrappers.** In that order a wrapper is eligible when, on the twelve setup inputs, the program with X
   removed fails by the missing name on every input, the intact program runs, the true operation put back passes,
   and no trivial repair (one of X's own arguments, or a constant taken from the examples) reproduces the
   outputs. The first five eligible ones are wrappers 1 to 5. Fewer than three: the target is excluded. Nothing
   is padded.
4. **Pooled inputs.** A seeded sequence of at most 1,600 unique argument tuples assembled from values of the whole
   generator pool (arguments of function type, or of a type the pool lacks, from the target's own setup and
   acquisition records only), none equal
   to any of the target's 66 generator tuples, cut by position into five disjoint slices: redraws (10%), admission
   (20%), a usability slice for admission (20%), final (25%), a usability slice for final (25%). Fewer than 30
   tuples of the usability slice for final on which X and wrappers 1 to 3 give usable values: the target is
   excluded. Before the cut, a pooled tuple in which a container argument holds a function is dropped (an argument
   that is itself a function is kept). A set that holds functions is read in an order that depends on memory
   addresses, so a result on such an input can differ between two processes. Under the first freeze the counts of
   usable inputs of one target (`combine`) changed with the memory layout of the process; this is also the likely
   cause of the one difference of that kind recorded in stage A. A residual is stated, not removed: inside a search a
   candidate can still build a set that holds functions (for example `prapply` applied to `lbind`, `compose` or
   `matcher` and two ordinary containers). The checks kept in `diagnostics/` (values of the setup roles under three
   memory layouts, whole development episodes under two) found no difference; they are finite support, not proof.
5. **Cohorts.** The **construction cohort** (the primary) is every target that passes this section. The
   **admission cohort** also needs a fourth eligible wrapper, a preservation bank with at least one successful
   entry, and 12 usable tuples for wrapper 4 in the usability slice for admission. The **reuse cohort** lies
   inside the admission cohort and also needs a fifth eligible wrapper and 30 tuples of the usability slice for
   final that are usable with wrapper 5 as well. A role that is unavailable is recorded as unavailable; it is
   never scored as a failure.
6. **Acquisition check on the nine tuples** (generator 0 to 8). Each wrapper is checked on the tuples it is used
   on in some arm (wrapper 1 on all nine, wrapper 2 on tuples 3 to 5, wrapper 3 on tuples 6 to 8): the program
   with X removed fails by the missing name, the intact program runs, the true operation put back passes, and
   every demonstrated output is a usable typed value. No trivial repair may reproduce wrapper 1 on tuples 0 to 2;
   every arm contains those three demonstrations, so no trivial repair can then pass any arm. When a trivial
   repair is the only failure, all nine tuples are redrawn from the redraw slice (tuples usable for wrappers 1 to
   3, nine at a time, at most five times) and the first set that passes is used. Any other failure, or no passing
   redraw: the target is excluded.

Cohorts, wrapper assignments and exclusions are computed by a setup-only pass over the full roster and committed
(`SETUP_RECORD_ALL_3.json`) before the run; the freeze refuses a setup record made by other code. The primary leaves
out the 20 development names and is not conditioned on what earlier studies found for any target.

## 5. Record sets, sealed in order
The evaluator computes typed arguments and X's values in advance into disjoint role records; access is restricted
by step, and a step raises an error when the records it must follow are not sealed. Setup: generator 24 to 35 and
the pooled usability and redraw slices. Acquisition: generator 0 to 8. Admission: generator 9 to 20 and the pooled
admission slice. Reuse support: generator 21 to 23. Final: generator 36 to 65 and the pooled final slice. Argument
keys of reserved records are used only to keep pooled tuples disjoint from them; reserved values never guide the
choice of wrappers or the search.

Seven records are sealed (sha256 written to the journal) in this order: the setup record; the acquisition record
(nine tuples and the fifteen demonstrated outputs); the first-fit or no-fit records of all five arms; the
admission set; the libraries of all arms; the reuse support set; the final set. Admission never triggers a
replacement candidate. The final panel is the same for every arm of a target: the final generator examples and
the tuples of the pooled final slice on which X and wrappers 1 to 3 (and wrapper 5 in the reuse cohort) give
usable values. Actual numbers of usable cases are reported, and a shortage is flagged, never used to exclude late.

## 6. Outcomes per target and arm, kept apart
- **First fit:** none within the limits, right, or wrong. "None" is reported with its kind of stop: the size limit
  was exhausted, the size limit was reached but the cap on function-valued entries was hit (not exhaustive), or
  the allowance was used up. "Right" is agreement of typed values with X on every input of the final panel,
  checked directly. It is finite evidence, not proof that the operation was recovered. A candidate that raises on
  an input is wrong there.
- **A final check that runs out of time.** Each check of a candidate on the final panel has a guard of 30 CPU
  seconds. A first fit for which no counterexample was found before the guard ended counts as wrong and is listed
  apart. If there is one in either arm of a comparison, the comparison is also read without those targets, and
  the criterion is met only if both readings agree. The guard's timeout is never treated as an ordinary error of
  one input, wherever it is delivered (in the candidate, a wrapper or the comparison): it ends the check at once,
  and the inputs not yet checked count as not agreeing. A counterexample found before it stays the counterexample;
  that first fit is wrong in the ordinary way, is not listed apart, and its record notes the timeout.
- **Admitted** (admission cohort): the sealed first fit passes stage A's rule unchanged: through wrapper 4 it is
  exact on the first 6 usable admission generator inputs and the first 6 usable tuples of the pooled admission
  slice, and every successful entry of the preservation bank keeps its value. Fewer than 6 of either kind: not
  admitted, flagged as a shortage.
- **Reuse task exact** (reuse cohort): the consumer with wrapper 5 on the final panel, with the sealed read-only
  library file and no search; an arm without an admitted library counts as not exact. Two controls use the reuse
  task's own three examples (generator 21 to 23 through wrapper 5): a fresh synthesis of the whole program (at
  most 5 nodes) and a fresh repair of the missing call (at most 4 nodes), each with the same allowance. With
  fewer than three usable examples the controls are recorded as unavailable.
- **Task exactness** of each acquisition consumer (wrappers 1, 2 and 3) on the final panel is recorded too.
An infrastructure stop (an exception, or the hard time limit of a search at its allowance plus 30 CPU seconds) is
"incomplete" and is reported apart; it is never counted as "none".

## 7. Comparisons, fixed before any outcome
**Primary (one): A3x3 against A1x9**, paired over every target of the construction cohort outside the development
roster, as committed in the setup record. The full paired table of none, right and wrong is published. The
reading "fewer wrong first fits at matched evidence" needs all four of:
1. fewer targets with a wrong first fit in A3x3;
2. an exact two-sided sign test below 0.05 on the targets where exactly one of the two arms has a wrong first fit
   (it cannot be met with fewer than six favourable targets and no unfavourable one);
3. no fewer right first fits in A3x3 than in A1x9, as observed on this panel (not a claim of non-inferiority);
4. at least one right first fit in A3x3 (a method that fits nothing is not a success).
If the reduction comes through wrong becoming none, it is reported as reduced ambiguity, possibly by abstention.
More right construction is claimed only if the number of right first fits itself rises.

**When the reading is provisional.** The table is made on the committed cohort only. The reading is called
provisional, and is neither "met" nor "not met" until the independent review has read the reason, when a committed
target has no record or an incomplete one, when a target outside the committed cohort ran as eligible, or when a
target's setup decisions in the run (status, wrappers, cohorts, kind of exclusion, source of the nine tuples)
differ from the committed record. Such targets are listed and left out of the table.

**Secondary, descriptive, uncorrected.** A2x3 against A1x6 (the same reading). The five arms side by side. Wrong
admissions under the rule, by arm, on the admission cohort. Reuse on the reuse cohort: the library of A3x3 against
the library of A1x3, the fresh synthesis and the fresh repair. Costs as in section 3. The names held out by the
earlier study, apart.

**What is expected is not assumed.** Stage A's one-task arm gave 5 right and 46 wrong first fits on its own
wrappers and cohort; that is background only. The one-task baseline here is run afresh under this protocol, on
other wrappers.

## 8. Discipline
- Development roster only until the freeze. A first development rehearsal used stage A's order of wrappers as a
  check of the code: where the wrapper and the inputs were the same, the one-wrapper three-example arm gave stage
  A's first fits. The order was then changed to this experiment's own seed (section 2) and the rehearsal repeated.
- Every command, the successful paths and the refusals, was run in fresh processes on invented fixtures and on the
  development roster. The exact path of the one launch (setup-only pass, freeze, launch, receipt, summary read
  against the committed setup record, refusals of any later launch) was executed end to end on a copy of this
  folder with a small roster of development names (`rehearse_run_once_path.py`; its log is committed).
- The setup-only pass over the full roster was run in separate processes, two of them with a deliberately
  different memory layout, and compared before it was committed as the eligibility record.
- The final check's guard is tested with invented faults and no search: a timeout raised inside the candidate, a
  wrapper and the comparison, the real CPU timer firing inside a candidate, an ordinary error as the control, a
  counterexample before a timeout, and the record and summary that follow from them (`tests/test_eaf.py`). The
  same tests fail on the code of the second freeze, except the control.
- The protocol, sources, tests, rosters, seeds, presets and the setup record are frozen by hash; the independent
  review checks the exact freeze; then the full roster is launched once.
- **One launch.** The launch writes an exclusive read-only receipt before its first target and refuses an output
  folder that is not new or empty. A receipt that exists refuses every later launch, whatever its output folder.
  If the run is interrupted it is not resumed, reset or replayed: the files are kept, the run is reported as
  incomplete, and the independent review is asked.
- After the run the frozen files are checked again by hash, the setup decisions are reconciled with the committed
  record, and the found expressions are read by a person before any count is reported. No guard is bypassed and
  no receipt is reset. CPU figures given before the run are projections.

## 9. Limits and level
At best this restores removed operations by composing existing ones (level 2 of the project's plan, as restoration).
Constructed two-call tasks on invented inputs, at most 4 nodes, one library, one generator, one seeded assignment
of wrappers, known operation families, and a direction suggested by stage A on the same operations (section 0). A
positive reading would support this form of combining supplied observations that share a cause, on this
benchmark. It would not show a new capability, autonomous grouping of failures, a cumulative library that helps,
or anything about puzzles. "Not demonstrated" never means "cannot help".

## 10. Prior work
As in stage A's protocol, section 14, checked by the independent review. Bottom-up enumerative synthesis with
observational equivalence, completing a program with a hole, and constraining a synthesised component by several
specifications at once are standard and are not claimed. The library is arc-dsl by Michael Hodel (MIT licence).

## 11. What each outcome leads to
- **Criterion not met:** diversity of evidence has not shown the specified benefit within this cohort, grammar,
  wrapper assignment, generator and budget. That does not show there is no benefit elsewhere, nor that a language
  below the library is necessary. Effect sizes, abstention and the limits of the search are reported before a next
  direction is chosen.
- **Criterion met:** the result supports this form of combining shared-cause observations on this known benchmark.
  A confirmation in a second domain, and any claim about autonomous grouping or a cumulative library, need their
  own designs.

## 12. Reproduce (from the repository root)
    P="env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B"
    E=experiments/evidence_across_failures_20261114
    $P -m pytest -q -p no:cacheprovider $E/tests
    $P $E/run_eaf.py --setup-only $E/SETUP_RECORD_ALL_3.json --roster all
    $P $E/run_eaf.py --make-freeze $E/FREEZE_3.json --setup-record $E/SETUP_RECORD_ALL_3.json
    $P $E/run_eaf.py $E/full_out --roster all --freeze $E/FREEZE_3.json --setup-record $E/SETUP_RECORD_ALL_3.json
The last command is the one launch. Per-target records: `full_out/targets/`; journals: `full_out/journal/`;
admitted operations: `full_out/library/` (read-only files); summary: `full_out/SUMMARY.json`. The files
`FREEZE.json` with `SETUP_RECORD_ALL.json` (first freeze) and `FREEZE_2.json` with `SETUP_RECORD_ALL_2.json` (second
freeze) were withdrawn and are kept as records; the runner refuses them because the code has changed since.
