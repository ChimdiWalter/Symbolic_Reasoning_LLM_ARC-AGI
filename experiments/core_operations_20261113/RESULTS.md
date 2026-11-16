# Operations from the rest of the library: results

Author: Chimdi Walter Ndubuisi. 13 November 2026 (UTC). The independent review audited the saved outcome on 13 November
(527 checks; every count below reproduced) and its qualifications are applied: this is finite-example coverage on invented inputs,
not a result about puzzles and not a proof of any identity.

One frozen run (protocol `PROTOCOL.md` c9c4cb98..., freeze `FREEZE.json` ec064346..., commit 1601b79dd). Detached
job `core_ops_full`, 10:57:39 to 11:56:12 UTC, exit 0, no GPU, no model. CPU measured inside the searches: 3,391.1
seconds (0.94 hours); set-up, generation of examples, validation and input and output are not included in that
figure, and the whole job's CPU was not measured. The job's elapsed time was 3,513 seconds; it overlaps the CPU
figure and is not to be added to it. The
eleven frozen files were unchanged after the run. Output: `full_out/` (310 files and `SUMMARY.json` d8064b92...);
every file's hash is listed in `FULL_OUT_MANIFEST.sha256`, sorted in the C locale.

## The question
If one library operation is hidden and known only through examples of its own inputs and outputs, can a short
expression over the remaining operations reproduce it? And how many examples are needed before the first
expression that fits is right? Inputs are invented. Nothing was run on real puzzles.

Words: **alone** means only the operation is hidden; **with its family** means its whole family is hidden and
every operation that depends on a hidden one fails. An expression has at most 4 nodes, for example
`first(order(container, compfunc))`.

## 1. How many operations can be rebuilt (search over all 36 examples)
Of the 155 operations, 145 were searched and 10 were left out for stated reasons (7 return a function; 3 have too
few possible inputs).

| | hidden alone | hidden with its family |
|---|---|---|
| an expression equal on all 36 examples was found | 55 of 145 | 25 of 145 |
| among the 119 operations whose family has other members | 50 | 20 |
| among the 39 searched names that the earlier study held out | 15 | 8 |
| outside the 13 operations seen before the freeze | 46 of 132 | 25 of 132 |

Hiding the family removes more than half of the reconstructions. Every search but one ended by finding an
expression or by trying everything up to 4 nodes; the one exception (`rapply`) reached the cap on function-valued
entries and is not exhaustive. Known-answer control: the 5 operations whose library text is itself a short
composition (mfilter, other, mapply, lefthalf, righthalf) were all found.

Some reconstructions are real identities that are not written anywhere in the library, for example
`ineighbors(loc) = corners(dneighbors(loc))`, `maximum(c) = first(order(c, invert))`,
`uppermost(p) = valmin(toindices(p), first)`, `hconcat(a, b) = papply(combine, a, b)`.

## 2. How many examples before the first fit is right (each search sees only its own examples)
The first fitting expression is recorded, then run on 30 fresh examples that no search saw. (The separation is
in the code path; the choice was not written to disk as a sealed file before validation, so no claim is made
about a secured order of events.)

| examples seen | 1 | 2 | 3 | 6 |
|---|---|---|---|---|
| hidden alone: a fitting expression exists | 128 | 103 | 91 | 75 |
| of these, right on the 30 fresh examples | 19 | 35 | 43 | 51 |
| of these, wrong | 109 (85%) | 68 (66%) | 48 (53%) | 24 (32%) |
| with its family: a fitting expression exists | 112 | 75 | 61 | 41 |
| of these, right | 10 | 14 | 15 | 22 |
| of these, wrong | 102 (91%) | 61 (81%) | 46 (75%) | 19 (46%) |

With three examples, about half of the first fits are wrong when the operation is hidden alone, and three
quarters when its family is hidden. Even with six, a third to a half are wrong. In 4 cases an expression equal
on all 36 examples exists but a smaller wrong one fits the six examples first (extract, greater, hline, vline).

## 3. After the run: a stress check, and what it corrects (post hoc; not part of the frozen study)
Reading the 55 expressions showed artefacts: `paint` and `underpaint` were "rebuilt" as their own grid argument,
because the generator paints an object of a grid onto that same grid, which changes nothing. So every found
expression was tested again on arguments put together differently (values pooled from all operations' examples by
type; 228 to 400 usable pooled draws per expression, not deduplicated and not kept apart from the earlier examples; script `posthoc_stress.py`, output `POSTHOC_stress.json`
75287a48...).

| | hidden alone | hidden with its family |
|---|---|---|
| found in the frozen run | 55 | 25 |
| still equal on every usable pooled draw (survivors of a finite check, not proven identities) | 46 | 21 |
| shown to differ | 9 | 4 |

- Not equivalent: `paint`, `underpaint` (the examples never exercised them), `extract` (the found expression
  ignores the condition), `first` (differs when the container holds a zero), `color` (holds only for objects of one
  colour), `hline`, `vline` (one of two conditions missing).
- Differ only on the empty input: `height`, `hperiod`. These are real counterexamples: the operation is defined on
  the empty input and the expression is not.
- The pooled inputs are not guaranteed to be unique, nor disjoint from the 36 examples of the frozen run.
- Corrected counts: 46 of 145 alone (41 of the 119 in larger families) and 21 of 145 with the family (16 of 119).
  Held-out names: 12 alone, 8 with the family (argmin, identity, leftmost, lowermost, maximum, minimum, rightmost,
  uppermost).
- **Fresh examples drawn the same way did not catch these.** Six of the expressions judged right on 30 fresh
  examples were refuted by inputs assembled differently (color, first, height, hperiod, paint, underpaint).
  Independent evidence has to differ in kind, not only in number.

## 4. How small a set regenerates the rest (a greedy upper bound)
From the frozen run's expressions: 105 operations kept as given, 50 derived from them. Counting only the
expressions that survive the stress check: 114 kept, 41 derived. This is a greedy estimate within these
expressions; the check is on the graph only, and the expressions were not run again over the final set.

## 5. What this shows and what it does not
- A minority of the library is a short composition of the rest: about a third when an operation is hidden alone,
  about a seventh when its family is hidden. For the rest, no expression was found within 4 nodes; that does not
  show that a longer program is necessary, nor that one exists.
- With few examples, fitting is a poor sign of being right, in a setting with no model at all.
  [A sentence about an earlier unpublished experiment is withheld from this public copy.]
- Restoring an operation that existed is not a new capability. In the project's plan's levels this is level 2
  (a composition of existing primitives) used for restoration.
- Limits: at most 4 nodes; invented inputs from a hand-written typed generator, which under-exercises some
  operations; equality on finite examples, and surviving the stress check, are not proof; the type filter follows
  the library's annotations and can miss valid expressions (the known-answer control has only 5 cases); acceptance
  uses a typed comparison, but merging inside the search uses Python equality and can merge states that differ
  in type; 13
  operations were seen before the freeze and are flagged; one training-free run on one library.

## 6. Reproduce
    cd <repository root> && env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B experiments/core_operations_20261113/run_all.py experiments/core_operations_20261113/full_out
    env PYTHONHASHSEED=0 python3 -s -B experiments/core_operations_20261113/posthoc_stress.py experiments/core_operations_20261113/full_out experiments/core_operations_20261113/POSTHOC_stress.json
Tests: 25 pass. Method: bottom-up enumerative synthesis with observational equivalence, a standard technique
(TRANSIT, 2013; Escher, 2013); the library is arc-dsl by Michael Hodel (MIT licence). Nothing new is claimed about
the method.
