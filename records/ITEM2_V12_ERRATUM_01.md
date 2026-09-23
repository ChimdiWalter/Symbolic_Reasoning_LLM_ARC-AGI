# Erratum 1 to Item-2 protocol v1.2

Recorded 2026-09-23, before any v1.2 episode was generated. This clarifies
wording. It does not change the law, and the protocol document and manifest
hashes are unchanged.

## The imprecise sentence

Section 9 step 5 of the protocol reads "obtain the failure trace from that
same baseline run, through the repaired full-engine observation path".

That phrasing is wrong in one respect: the out-of-reach test and the evidence
source are two different reasoners, so they cannot be one run.

## What the law actually specifies, unchanged

Section 3 fixes the out-of-reach test as
`scoped_slot_fitting.base_search_with_scoped_fitter` over the 200 single-block
schemas of the constructive language. Section 10 fixes the evidence source as
the repaired full-engine observation path, that is the deployed ARC object
reasoner.

These are different mechanisms serving different purposes, and both sections
are explicit. The two are related by operating on the same demonstrations, not
by being the same execution.

## The corrected reading

For each prospective episode, on one set of generated demonstrations:

1. the constructive baseline runs its 200 single-block enumeration, and the
   episode is rejected if it finds an exact solution;
2. separately, the deployed ARC reasoner runs on the same demonstrations
   under the repaired observation path, and its failure produces the typed
   failure graph;
3. the informative-evidence gate is applied to that graph;
4. the target is fitted.

## Consequence recorded in advance

The deployed reasoner may succeed on a synthetic episode even when the
constructive baseline does not, because they are different reasoners over
different hypothesis spaces. An episode whose deployed-reasoner run succeeds
yields no failure graph and is rejected as `NO_INFORMATIVE_TFG`.

That rejection rate is a measured outcome of v1.2 and is not a reason to
change the law. It is recorded here before generation so that a high rate
cannot later be treated as a surprise or as grounds for relaxation.
