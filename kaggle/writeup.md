# CORA: Separating Search, Hypothesis Selection, and Capability Growth

### A non-LLM ARC-AGI-2 solver with immutable verification, and an experiment on whether a reasoner can change its own language

## Problem and thesis

A score cannot tell you which of three things improved: the search found a
program faster, the selection rule picked a better program from the same
pool, or the system became able to express something it previously could not.
Conflating them makes progress hard to interpret.

CORA is built around that separation. Ordinary learning adapts parameters.
Ordinary induction searches inside a fixed executable language K. CORA asks a
third question: when search inside K fails, can the system represent why,
construct an executable extension e, and let a fixed verifier decide whether
K with e gained real reach? We do not claim to have answered it. This
describes what is built, what is measured, and what is missing.

## The submitted system

CORA is symbolic. No language model runs at inference.

Perception segments each grid into objects under several segmentation
variants. Induction builds correspondences between input and output objects,
induces a selector for the objects a rule applies to, and fits typed
parameter expressions for the action it performs. Programs are assembled from
those rules and executed exactly.

Acceptance is the part that matters. A program counts as solved only if the
whole learning procedure, re-run from all demonstrations but one,
independently re-derives a program that solves the held-out example, for
every fold. This validates the learner rather than the artifact. A program
that fits by luck does not survive, because luck does not re-run.

The notebook runs offline inside the twelve-hour limit. A global governor
rescales per-task budgets against remaining wall clock so the run finishes
rather than being cut off. A fallback guarantees two syntactically valid
attempts for every task, so no task id can be missing even when a solver path
fails or times out. The failure-driven construction research described below
is not part of this system, and no leaderboard result may be attributed to it.

## Accuracy and the two attempts

Leaderboard results are pending: submission id, notebook version, scores and
measured runtime. We do not substitute training, synthetic or development
accuracy for the leaderboard score, and no hypothetical number appears here.

Because scoring credits the better of two attempts, we measure the second
attempt as rescue rather than as diversity. Differing predictions are not a
benefit in themselves. The categories we report are attempt one correct,
attempt two correct where attempt one failed, both wrong, both identical, and
different but non-rescuing. Attempt one is the certified output under the
frozen policy. Attempt two is a complementary uncertified candidate chosen to
be independently plausible.

The controlled comparison is fixed-language CORA against failure-conditioned
adaptation, with a matched-compute arm that gives the baseline the same extra
budget without construction, and an ablation that removes a successful
extension. Gains, losses and unchanged tasks are reported as paired outcomes,
never as a net figure.

## Theory: fixed K versus K plus e

The hypothesis is that some failures occur because the hypothesis was wrong,
and others because the executable language cannot express an adequate
hypothesis within the relevant bound. A reasoner may therefore need to reason
about the inadequacy of its own language.

A failed search is not empty. It contains which partial programs executed,
what types were reached, where parameter fitting failed, which relations were
preserved, how near-miss outputs differed, and where verification failed.
That evidence may constrain the missing capability far more efficiently than
blind expansion of the whole language.

Proposal and acceptance stay separate. The constructor may propose; only the
verifier accepts. Before anything is called capability growth we require six
legs: the baseline fails, the extension is produced, the winning program uses
it, adaptive leave-one-out passes, the output is exactly correct, and
removing the extension destroys the gain. A new program is not a new
capability, a macro is not semantic novelty, and a score gain is not
invention.

## Progress: what another researcher can reuse

Two of our own measurements forced this discipline. In one, several policies
differed in efficiency and changed individual predictions, yet every policy
solved the same 188 of 256 targets. Reach was unchanged. In another, an
earlier adaptation path appeared to activate often, but the comparison turned
out not to be additive, so activation counts were not evidence of anything.

The third result is newer and more useful. We audited the failure
representation our construction path was meant to consume, on twelve
development tasks fixed before any result was computed. It produced 64,610
candidate events and 144 frontier terms, but zero executed near misses and
zero mismatch signatures. On eleven of twelve tasks the candidate census was
byte-identical, and three unrelated synthetic tasks reproduced it exactly.
The cause was a disconnect: the thing doing the real reasoning was not the
thing being observed. That also explained an earlier null in which shuffled
failure evidence matched real failure evidence.

Instrumenting the deployed reasoner, with fixtures proving the search result
is unchanged, produced 494 candidate events, twelve operator families instead
of one, 62 parameter fits, 36 executable near misses and 7 exact candidates.
A compatibility repair then carried mismatch evidence into the graph, 18
defined signatures where there had been none, meeting a threshold fixed in
advance at eight of twelve tasks, identically across three runs.

The reusable lesson is cheap and domain-independent: before learning from
reasoning failures, check that the failure representation actually varies
with the task. A representation can be correct in format and empty in
content.

## Universality

CORA separates the domain-specific semantics of ARC from a domain-general
control loop. ARC supplies grids, objects and transformations. CORA supplies
failure localization, typed interfaces, executable construction, exact
evaluation, leave-one-out verification and causal ablation. We formalize a
reasoning domain as a tuple of observations, targets, a type system, an
executable capability language, an executor and an immutable verifier, and
define the loop over that tuple. ARC is one instantiation rather than the
definition of the method.

We claim architectural portability, not demonstrated cross-domain
performance. Three levels should not be confused: the loop is independent of
grids; a new domain could supply its own types, operators and verifier; and
the same implementation actually succeeding elsewhere is a third claim we do
not make. Transfer beyond ARC remains future work.

One design choice supports this more than any argument. CORA refuses
task-family lookup, handwritten operators added after inspecting a failure,
and direct answer generation. Those would raise a score and produce a less
general system.

## Novelty

We do not claim first use of program synthesis, learned libraries, predicate
invention, test-time adaptation, verifier-guided search or abstraction
learning. Each has prior art, including DreamCoder, LILO, predicate invention
work such as POPPI, AlphaEvolve, and non-LLM ARC systems.

The candidate contribution is the conjunction: failed reasoning, to a typed
mechanistic failure representation, to diagnosis of a capability gap, to an
executable extension, to an additive comparison of the language with and
without it, to adaptive leave-one-out, to a causal use test, to removal
ablation, to bounded semantic separation, to independent transfer, to
verifier-controlled promotion. That conjunction has not been demonstrated and
we do not claim it.

A smaller result stands on its own. The failure-frontier audit is a
diagnostic finding about machine self-observation: a system's record of its
own failures was task-invariant, which explained an earlier control result,
and repairing the observation exposed task-dependent structure. That is not
invention.

## Limitations

The public score is not yet measured and may remain low. Our verification
showed poor off-distribution calibration, 40 of 42 on training against 0 of
11 on an evaluation development split. The repaired evidence has produced no
autonomous construction; the constructive proposer and its compiler are
specified and unimplemented. A separate durable capability-growth experiment
is still running with no interpretable verdict, and none of it is used here.
The diagnostic classification rests on twelve tasks and sits exactly at its
threshold, and three of those tasks emit no candidates at all. ARC results
alone do not establish general intelligence.
