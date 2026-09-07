# One complete acquisition-and-transfer cycle, measured

First run of the cycle that connects the ranking work back to CORA's actual
question. It uses only components that already existed. No new solver, no new
learner, no relaxed acceptance, no architecture expansion.

Artifacts: `outputs/tti/acquisition_transfer/results.json`, sha256
`5c2b72f4d961cb7202c27459bf9c8da9eb5603816ac3da93c84a3a16ec82e6a3`.

## The question, and the measured answer

> After encountering a failure, what can the system now do that it could not do
> before, what did the system itself construct to make that possible, and does
> the benefit survive an honest test on new evidence?

**Measured answer: nothing it could not already do. It can do four things about
seventeen times more cheaply, and the cost of acquiring that ability exceeds the
savings by a factor of about fifty at this scale.**

Transfer is real and it is small. The honest claim level is OPERATIONAL and
weak: a constructed schema was reused on tasks that did not create it, reduced
search cost there, and produced correct held-out predictions on three of four.
It is not semantic expressivity growth, and it is not a capability gain.

## Design

**K0**, the identified baseline: the single-block meta-language, the complete
200-hypothesis product of the frozen terminals, enumerated exhaustively.

**A. Construct without being given the answer structure.** On each source
episode where K0 completed and failed, the system searched the two-block
constructive space and found a program fitting every demonstration. It never
received the generating target schema, its tables, its digest or its family. The
constructed extension is that program's STRUCTURE with induced tables removed,
so it is an open schema whose tables must be refitted per task from that task's
own demonstrations.

**B. Show the extension does useful work.** Three systems compared on the same
unit, one candidate fit:

| system | on the 22 targets where K0 failed |
| --- | --- |
| K0 alone | 0 solved, 200 units each, by measurement |
| K0 plus the frozen library | 4 solved, median 3 units, at most 16 |
| unlearned two-block search | 17 solved, mean 833.5 units over all targets |

**C. Test reuse beyond the source.** Leave-one-out at the level of the SOURCE
EPISODE: when episode j is the target, every library entry acquired from j is
withheld. Held-out output correctness measured on j's fresh grids.

**Ablation.** Whenever the library solved a target, the entry that solved it was
removed and the target retried with the remainder.

## Result

Library: 16 distinct constructed structures, acquired at a total cost of 10,182
candidate fits, mean 636 per entry.

| measure | value |
| --- | --- |
| targets where K0 completed and failed | 22 |
| solved by the library, source-episode withheld | 4 |
| held-out output success among those | 3 |
| benefit attributable to the specific solving entry | **1 of 4** |
| entry was the generator's schema | 0 |
| median library units when solved | 3 |
| solved by the library but NOT by unlearned search | **0** |
| solved by unlearned search but not the library | 13 |

The four successes in full:

| target | family | library units | held-out | entry came from | entry's structure | attributable |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | (1,0) | 3 | no | episodes 8, 14 | (0,0) | no |
| 8 | (1,0) | 13 | yes | episode 18 | (1,0) | **yes** |
| 12 | (0,1) | 3 | yes | episodes 8, 14 | (0,0) | no |
| 21 | (1,1) | 3 | yes | episodes 8, 14 | (0,0) | no |

## What deflates it, stated plainly

**The library never solved anything unlearned search could not.** Zero
library-only successes against 13 unlearned-only. Every transfer success was
already reachable, more slowly, by smallest-first enumeration. So this is a cost
reduction on a subset, not an extension of what the system can do.

**Three of the four successes are not attributable to the entry that produced
them.** Removing the solving entry left another entry that also solved the
target. The benefit belongs to "the library happens to contain some fitting
two-block structure", not to a specific acquired capability. Only episode 8 has
a benefit that disappears when its entry is withdrawn.

**Amortization is a heavy net loss at this scale.** Acquisition cost 10,182
units; total savings across all four successes, 190 units. Net minus 9,992. At
about 47 units saved per success, roughly 216 successful targets would be needed
to break even. That is a testable prediction about scale, not a refutation, but
at 22 targets the library does not pay for itself and it would be dishonest to
present the per-target speedup without it.

**No transferred entry was the generator's schema**, consistent with every other
result in this line: the demonstrations underdetermine the schema.

## The one genuinely interesting structural finding

Twelve of the 16 library entries are family (0,0), the simplest two-block shape,
and nine of the 16 have a structure family different from the source episode
that provoked them. The single most reusable entry, acquired from episodes 8 and
14, is a (0,0) structure and it solved targets of families (1,0), (0,1) and
(1,1).

So what transfers is a small number of simple, general structures. That is what
a useful abstraction ought to look like. It is also precisely what smallest-first
enumeration finds immediately without any acquisition, which is why the transfer
buys speed and not capability.

## Where this sits on the claim ladder

- **Search improvement**: yes, on 4 of 22 targets, roughly seventeen times
  cheaper, but net-negative once acquisition is charged.
- **Operational language growth**: weakly. A constructed schema became reusable
  and did useful work on tasks that did not create it. Only one of four cases
  survives ablation as attributable to a specific entry.
- **Semantic expressivity growth**: no, and not claimed. A two-block composition
  is expressible in the evaluator language; K0 simply does not enumerate it.
- **Full-pipeline leave-one-out**: not measured. Leave-one-out here is at the
  level of the source episode for the library, not per held-out demonstration
  inside the acquisition procedure.

## What was our work and what was the system's

Ours: the occurrence-scoped fitter, the identified baseline, the observer, the
two ranking rules, the candidate space, the abstraction rule that strips tables,
and this experiment's design. All human-designed infrastructure.

The system's: which program to propose for a given task, given demonstrations
and permitted failure evidence but never the target; and therefore which
structure entered the library. That is a real but narrow act of construction,
and it is selection within a supplied space rather than growth of the space.

## Next step this suggests, proposed and not built

The library entries are fully concrete structures with only their tables free,
so each covers few targets. The obvious lever is a more general abstraction:
anti-unify several found programs so that partition and feature become slots
too, trading more fits per entry for far broader coverage. `meta_ast.anti_unify`
already exists and is unused here.

That is one bounded change to the abstraction rule, not an architecture phase.
It has a clear prediction to test: coverage per entry should rise and cost per
entry should rise, and the question is whether the product beats both K0 and
unlearned search once acquisition is charged. The break-even figure above, about
216 successful targets under the current abstraction, is the number a better
abstraction has to move.

Nothing here changes the holdout, adds a learner, trains a model, runs D3, opens
protected data, or merges into main. The frozen Step-B experiment was neither
read nor modified.

---

# Interpretation correction, appended 2026-09-07

The result artifact and commit `4894056` are unchanged. This section corrects
the interpretation above. Where the two disagree, this section governs.

## C1. The sweeping claim was wrong at the held-out level

Above I wrote that the library did "nothing it could not already do". That is
supported at the DEMONSTRATION-FIT level and not at the level that matters most.

| level | library-only successes |
| --- | --- |
| exact demonstration fit | 0 |
| held-out output correctness | **1, episode 8** |

On episode 8, expanded search fit the demonstrations at 53 units and its
selected program was **wrong** on the held-out grids. The library fit at 13
units and its program was **right** on all four. Recomputed from the artifact:
library held-out successes {8, 12, 21}, expanded-search held-out successes
{0,1,2,3,4,5,11,12,13,14,16,19,21}, so the library-only held-out set is {8}.

The narrow observation worth preserving: previously acquired structure changed
WHICH explanation was selected, and on one target that changed the outcome from
a demonstration-fitting but incorrect explanation into one that predicted the
held-out outputs correctly. Learning can improve hypothesis selection, not only
search reach. This does not establish greater expressivity, and it does not
overturn the aggregate, where expanded search has 13 held-out successes against
the library's 3.

## C2. The ablation reading was inverted in emphasis

Three demonstration fits **persist** after the particular winning entry is
removed, because another entry fits. Only episode 8 loses its fit. Correctly
stated:

- episode 8 shows dependence on one particular entry within this procedure;
- the other three have **redundant support** inside the library;
- redundancy does not establish that the library as a whole is causally
  irrelevant, which is what "not attributable" invited a reader to conclude.

A further limitation: the stored ablation records whether the remainder still
fits the demonstrations. It does **not** record whether the remainder's
replacement program is held-out correct. Entry necessity, library-level
benefit, and held-out prediction change are three different questions and only
the first was measured.

## C3. The cost figures are retrospective subtotals, not a learning cost

The 10,182-unit figure pools discoveries from all six study arms, merges
identical structures, and charges each retained structure only its CHEAPEST
recorded successful acquisition. It therefore excludes unsuccessful searches and
searches that contributed no retained entry. It is a subtotal, not the cost of
the procedure that produced the library.

The 190-unit saving is summed over the four successful library fits, including
the one whose held-out prediction was wrong, and excludes library-lookup cost on
the 18 targets where the library failed and any fallback search.

Consequently **the "216 successful targets to break even" figure is not an
established deployment prediction** and should not be cited as one. The relevant
accounting for a deployed learner is acquisition plus, for every target, library
lookup plus fallback search, reported alongside correctness. A cheap wrong
answer is not a search-efficiency success.

## C4. The source-exclusion boundary is incomplete

The prototype is retrospective: it reuses the already-inspected 24-episode study
rather than evaluating a frozen library on a separate transfer set.

The library includes structures discovered by the shuffled-trace arms. Those
arms read the NEXT episode's trace, while the entry records and excludes only
the episode whose demonstrations produced the fit. So excluding an entry's
direct `source_episode` does not establish that the target had no influence
through a shuffled trace. The code does not record that second dependency.

This does not show that any reported transfer is contaminated. It shows the
claimed exclusion boundary is incomplete, and that the next experiment must use
genuinely separate acquisition and transfer pools.

## C5. Status of this experiment

Exploratory cross-episode reuse, with one held-out prediction rescue. Not a
prospectively frozen transfer evaluation, not full-pipeline leave-one-out, and
not an integrated promotion into the ordinary engine followed by re-induction.
The script fits stored schemas directly; it is a library-only loop with no
fallback, so it measures library coverage rather than whether adding a library
helps the full reasoner.
