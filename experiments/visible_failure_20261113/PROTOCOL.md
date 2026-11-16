# Visible-failure construction, version 1 (VF1), stage A: protocol

Author: Chimdi Walter Ndubuisi. 13 November 2026.

Frozen by a hash manifest (`run_stage_a.py --make-freeze`) before the one full-roster run. Model-free, CPU only,
invented inputs only. Stages B and C are outlined in section 16 and are frozen separately, later.

## 0. What kind of study this is
**A development comparison on a known benchmark.** The operations study
(`experiments/core_operations_20261113/`) ran on these same 145 operations before this protocol was written, and
its outcomes shaped this design. So this is not an untouched confirmation over operations. The names that an
earlier study held out are reported as a transfer stratum, not as an untouched family test. A confirmatory claim
about new families or new tasks needs a separately frozen split that nobody has seen.

[Two sentences about an earlier unpublished experiment are withheld from this public copy.]
This protocol asks a different question.


## 1. Question
1. When the system loses an operation and observes the resulting failure, does keeping its program and searching
   only at the failing step solve the task more often than solving the task again from nothing, at the same cost?
2. Which independent evidence keeps wrong replacements out of the library?
3. Does a replacement admitted from one task serve a different task without further search?

## 2. Setting and words
- **Library:** the 155 operations of the system-side grammar (arc-dsl, MIT licence), as source text.
- **Target:** one operation X that is taken away. **Lesion:** X's whole family is absent from the executable
  namespace, so every operation whose code reaches a member fails (the operations study's rule and code, imported
  unchanged and checked by hash at start-up).
- **Consumer:** a program of two calls, `post(X(arguments))`, where `post` is a one-argument library operation
  outside the lesion. It plays the part of a task: its inputs and final outputs are the task's examples. Each
  target has three consumers with three different `post` operations: acquisition, admission, reuse.
- **Generator inputs:** argument tuples from the operations study's seeded typed generator (66 per target; the
  first 36 are the ones that study used). **Pooled inputs:** tuples put together from values of other operations'
  examples, by type; unique, and disjoint from every generator tuple of the same target. The pooled sequence of a
  target (up to 1,600 tuples) is cut by position into five disjoint slices: setup redraw (10%), admission A (20%),
  setup usability for A (20%), final B (25%), setup usability for B (25%).
- **Evaluator only:** the true X. It produces the required final outputs of the consumers and the final checks.
  Its code and its intermediate results are never given to the system, except in arm T, where that is declared.

## 3. Five record sets per target, sealed in order
Each set's hash is journalled before the next step begins.

| set | inputs | used for | opened |
|---|---|---|---|
| setup | generator 18 to 35; three pooled setup slices | choosing the three `post` operations; redraws; the usability check; exclusions | first |
| acquisition | generator 0 to 2 | the three shown examples of the acquisition task | after setup |
| admission | generator 3 to 14; pooled slice A (12 usable) | the admission standards | after every candidate is sealed |
| reuse support | generator 15 to 17 | three examples of the reuse task for the controls that search again | after the libraries are sealed |
| final evaluation | generator 36 to 65; pooled slice B (at least 30 usable) | every final reading | last, once |

Nothing computed from the final set runs before the last step. A failure at final evaluation never causes a
redraw, an exclusion or a changed choice.

**Setup rules, all applied before any search.** A `post` is eligible when, on the setup inputs, it runs on X's
results, gives at least two different final outputs, and no trivial repair (returning one of X's own arguments,
or a constant taken from the outputs) reproduces the task. Candidates are tried in an order seeded from the
target's name, and the first three eligible ones become acquisition, admission and reuse. The acquisition task is
also checked on its own three examples: the lesioned program must fail on the missing operation, the intact one
must pass, the true X bound through the same mechanism must pass, and no trivial repair may pass; if one passes,
the three examples are redrawn from the pooled setup slice (at most 5 times). A target is excluded, with its
reason and every attempted draw on record, when the generator cannot give 66 examples, when fewer than three
eligible `post` operations exist (no padding with the identity), when the acquisition check still fails, or when
the two usability slices show too few usable pooled inputs (fewer than 12 for the admission consumer, or fewer
than 30 for the acquisition and reuse consumers together). A shortage that still appears later in slice A or B
is flagged and never excludes. Tasks are thus built so that the missing operation matters on their
examples; this uses the evaluator's knowledge of X to build the task and shows nothing of it to the system.

## 4. One episode
1. **Attempt.** The system runs the acquisition program, which worked before the lesion.
2. **Observe.** It stops at the call of X. Journalled: the error and its text, the failing step, the missing name,
   the arguments at that step and their types on each shown example, the required final outputs.
3. **Decide.** Fixed rule: when the failure is localised, construct at the failing step; otherwise search for a
   whole program. Both actions are run for every target so that the rule can be scored.
4. **Propose.** Typed bottom-up enumeration by size over the remaining operations (the operations study's
   enumerator; in arm V a copy with an acceptance hook). In arm V each candidate is put in place of the missing
   call and the whole consumer is checked on the three shown examples.
5. **Verify.** The first fit is frozen and sealed. It then meets the admission rule (section 6) once. If it fails,
   nothing else is tried for that arm and target.
6. **Admit.** A candidate that passes is written to a read-only library file under a new neutral name, with its
   expression, signature, the library names it uses, the hashes of the acquisition and admission records and a
   version number. The file's hash is checked before and after every use.
7. **Reuse.** With the library sealed, the reuse task is run with the admitted operation and no search.
8. **Record.** Every failure, counterexample, candidate behaviour, cost and outcome is journalled for stage B.

The failure supplies the name and place of what is missing. That is a diagnostic hint, not the autonomous setting
in which the system must infer what is missing.

## 5. Arms (same enumerator, order, type filter and caps; allowance B of process CPU time each)
- **V, failure visible.** Search for the missing call only, at most 4 nodes, from the three acquisition examples,
  accepted through the acquisition consumer.
- **S, ordinary synthesis.** The old program is not used. Whole programs of at most 5 nodes from the same three
  examples. The extra node gives syntactic inclusion of everything V can reach; it does not give equal realised
  reach under the CPU, bank, function and pruning limits.
- **H (secondary).** A predeclared schedule: half of B on V's search, half on S's, without using the error. The
  program text it holds already names the missing operation, so H is a mixture of the two budgets and not
  independent evidence of localising a failure.
- **T (secondary, declared supervision).** The missing call fitted to X's own outputs on generator inputs 0 to 5,
  supplied by the evaluator. This is extra supervision and is never described as information obtained from the
  failure. Three of its inputs are shared with the admission grid, so T's admission is reported apart.

## 6. Admission
Admission is finite evidence that a candidate is compatible with another program. It is not equality with X: a
`post` that loses information can hide a wrong intermediate result. That is why "correct" (section 7) is always
checked directly against X and kept apart.

Standards, all computed on the same frozen first fit of arm V, each with 3, 6 and 12 examples (nested):
none; more of the same (the acquisition consumer on generator inputs); the admission consumer on generator
inputs; the admission consumer on pooled inputs; both of the last two together.

**The rule that decides what enters the library:** the admission consumer on 6 generator inputs and on 6 pooled
inputs, all 12 exact, and a preservation bank of programs that do not use X, which must run and give the same
values before and after (an entry that raises does not count; at least one successful entry is required).

How the rule was set, from the development roster only: the first rehearsal used 3 pooled examples and admitted a
wrong repair; in two rehearsals the wrong repair that pooled inputs admitted was rejected on generator inputs,
while the operations study had shown the opposite blind spot. So the rule takes both kinds. The other standards
are measurements; no standard is chosen from full-roster outcomes.

## 7. Outcomes, never merged
**Task level** (every arm): the acquisition task is exact on its final panel; the reuse task is exact on its final
panel. The final panel is the same for every arm.
**Capability level** (V, H and T only): fit (the three shown examples are reproduced); admitted (the rule);
correct (the frozen candidate equals X on every final input, checked directly); reused (the reuse task is exact
with the sealed library and no search). Fit without correct is "fits but wrong"; admitted without correct is a
false admission; correct without admitted is a false rejection. Ordinary synthesis is not scored on capability; it
is only recorded whether its program happens to contain a part that could stand in for the call.
A stop of the infrastructure is "incomplete". A search that uses up its allowance, or reaches its size limit, is
a complete negative, and a size limit reached with the cap on function-valued entries is marked as not exhaustive.

## 8. Comparisons
**Primary (one).** Exact outputs of the acquisition task on the final panel, arm V against arm S, each at
allowance B, paired by target over all targets outside the development roster that pass setup. V's first fit is
composed with the retained `post` (no admission is needed for this endpoint; with no fit, V fails the target). S's
whole program is evaluated directly and is never failed for its shape. The reading "keeping the program and
searching at the failing step helped" needs more targets exact for V, more targets won than lost, and an exact
two-sided sign test on wins against losses below 0.05 (ties left out and reported). A null or reversed result is
reported as it is.
*What this contrast is.* It includes the retained program and a smaller search space. It estimates the benefit of
that scaffold under the declared caps, not the isolated effect of an error message.

**Declared secondary, reuse.** The reuse task on its final panel: retained (V's admitted operation from the
sealed library, no search, no support examples) against S's fresh synthesis from the three reuse-support examples
at B, and against no retention (a fresh V search on the support examples). A fixed-library search with 10 B is run
only where V admitted something and is labelled a conditional comparison.

**Descriptive, uncorrected.** The admission table of section 6 with false admissions and false rejections; first
fit against a random fit among the first 20 (5 seeds) and the number of different behaviours among them; the
repair-choice rule against search-first and a random order (5 seeds) at 2 B; arms H and T; the transfer stratum
(names held out by the earlier study); a first look at diagnosis (the same task with nothing hidden, given a tenth
of B, journalled with the same signals; no claim is made from it).

## 9. Roster
All 145 operations searched in the operations study, named in the manifest. Development roster, flagged in every
output and left out of the primary comparison: the 13 operations seen before the operations study's freeze
(hmirror, rot180, width, switch, objects, lefthalf, add, mapply, ofcolor, tophalf, mfilter, other, righthalf) and
7 more drawn by a seeded hash from families that the earlier study did not hold out (vfrontier, sign, rapply,
backdrop, color, box, numcolors). The operations study's bounded-search outcomes for these operations are known
(with the family hidden, 21 expressions survived its stress check); they are observations, not proofs that other
targets cannot be rebuilt, and coverage here is not conditioned on them.

## 10. Presets
Inherited unchanged: the generator, the lesion rule, the enumerator's order, type filter and caps (300
function-valued entries, 250,000 bank entries). New: B = 10 CPU-seconds per acquisition arm; 4 nodes for the
missing call and 5 for a whole program; 3 acquisition examples; the admission grid of 12 generator and 12 pooled
inputs; 3 reuse-support examples; 30 final generator inputs and at least 30 pooled ones; 20 collected fits; 5
seeds for random controls; seeds derived from 20261113 and the target's name. The typed generator, the pools and
all these numbers are hand-set.

## 11. Costs
Reported separately: the physical CPU spent by each arm and target, and the counterfactual CPU to its first fit.
The retained lifetime cost lists its parts once (acquisition including failed attempts, admission, preservation,
library write and load, deployment at reuse); an inclusive total is never added to its own parts. Worst case for
the full roster: 15.1 B per target (V, S, T, no retention, the reuse search, the diagnosis search at a tenth of B,
and 10 B where V admitted something), 145 targets, 21,895 CPU-seconds, about 6.1 hours, under the 8-hour limit.
No GPU and no model.

## 12. Guards
`--roster all` refuses without a freeze file whose every hash matches (stage A sources, this protocol, the README,
the tests, the operations study's modules and inputs), writes an exclusive receipt before the first target, and
refuses a second all-roster run into another folder. The final loader raises if called before the last step. The
found expressions are read by a person before any count is reported.

## 13. Limits and levels
- Level reached at best: a composition of existing primitives that restores a lost operation. Restoring what
  existed is not a new capability. A new primitive or representation, and a transferable procedure for
  construction, are not claimed. A deliberately removed operation is never described as an autonomous discovery.
- Only compositions of at most 4 nodes can be constructed, so most targets cannot be acquired at all here.
- Consumers are constructed tasks of two calls on invented inputs, not puzzles. All checks are finite.
- One library, one generator, hand-set budgets.
- Targets with a small universe of inputs cannot supply five disjoint sets and are excluded at setup (in the third
  rehearsal 3 of 20 development targets). The roster that reaches the comparison is therefore smaller than 145 and
  leans toward operations on grids, patches and containers.

## 14. Prior work (checked against primary sources by the independent review on 13 November 2026)
Program sketching (a partial program completed by synthesis); counterexample-guided synthesis; repair by semantic
analysis (SemFix); search guided by learned properties (DeepCoder); library learning (DreamCoder, Stitch, LILO);
decomposition by execution (ExeDec); debugging loops for language models, and the finding that repair gains can
vanish once repair cost is counted, which makes equal-budget independent search the essential control; allocation
between repairing and exploring as a bandit. Bottom-up enumerative synthesis with observational equivalence is a
standard technique (TRANSIT, 2013; Escher, 2013). The library is arc-dsl by Michael Hodel (MIT licence). A frozen
first fit followed by one rejection check is generate-and-check; a fixed response to a missing-name error is a
prescribed response, not a learned policy. None of these mechanisms is claimed. The candidate contribution is the
study design: a controlled failure, repair, admission and separate reuse comparison with measurable false
admissions and lifetime cost.

## 15. What each outcome leads to
- V does not beat S: the retained program gives no measurable benefit here; no model stage before this is
  understood.
- False admissions stay high under the rule: the admission evidence is the bottleneck; work on evidence first.
- Retained reuse does no better than fresh synthesis: no claim of cumulative benefit.

## 16. Later stages (not part of this freeze)
**Stage B** (CPU only): an ordering of operations for the enumerator, fitted from stage A's records of families
that the earlier study did not hold out, tested on the held-out names against the uniform order and an order
fitted from shuffled records, with matched caps; frozen separately; low power is expected and will be stated.
**Stage C** (inference only; needs the independent review's pass and the author's word): the review's design for
four named targets, two models and two views of the failure, with a typed transport through the sandbox.

## 17. Development record (development only; none of it is a result)
Three rehearsals on the development roster, in `dev_out/`, `dev_out2/` and `dev_out3/`. After the first: `post`
operations that hide what X does were no longer chosen; admission examples were raised from 3; a task-level
reading was added. After the independent review read the first code: the five sealed record sets, the common
task-level primary, no identity padding, the development label, the preservation bank of successful entries
only, and costs reported in parts. After the second: the admission rule takes both kinds of input, and pooled
usability is checked at setup.

## 18. Commands
    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/visible_failure_20261113/tests
    env PYTHONHASHSEED=0 python3 -s -B experiments/visible_failure_20261113/run_stage_a.py --make-freeze experiments/visible_failure_20261113/FREEZE.json
    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B experiments/visible_failure_20261113/run_stage_a.py experiments/visible_failure_20261113/full_out --roster all --freeze experiments/visible_failure_20261113/FREEZE.json
