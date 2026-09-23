# CORA: Separating Search, Hypothesis Selection, and Capability Growth

### A non-LLM ARC-AGI-2 solver with immutable verification, and an experiment on whether a reasoner can change its own language

## 1. Problem and thesis

Most progress on ARC is reported as a score. A score cannot tell you which of
three very different things improved: the search found a program faster, the
selection rule picked a better program from the same pool, or the system
became able to express something it previously could not. These are not the
same, and conflating them makes progress hard to interpret.

CORA is built around that separation. Ordinary learning adapts parameters,
writing theta to theta prime. Ordinary program induction searches for a
program inside a fixed executable language K. CORA asks a third question:
when search inside K fails, can the system represent why it failed, construct
an executable extension e, and let a fixed verifier decide whether K together
with e gained genuinely new reach?

We do not claim to have answered that question. This writeup reports what is
built, what is measured, and what is still missing.

## 2. What CORA does

CORA is a non-LLM symbolic system. No language model runs at inference.

Perception segments each grid into objects under several segmentation
variants. Induction builds correspondences between input and output objects,
induces a selector that picks the objects a rule applies to, and fits typed
parameter expressions for the action that rule performs. Programs are
assembled from those rules and executed exactly.

Acceptance is the part that matters. A program counts as solved only if the
entire learning procedure, re-run from all demonstrations but one,
independently re-derives a program that solves the held-out example, for
every fold. This validates the learner rather than the artifact. A program
that fits by luck does not survive, because luck does not re-run.

Every task output receives two predictions. Attempt one is the certified
output under the frozen policy. Attempt two is a complementary uncertified
candidate chosen to be independently plausible rather than merely different.

## 3. Fixed-language reasoning versus language adaptation

The distinction is empirical, not rhetorical, and our own measurements are
what forced it.

In one study, several competing policies were compared. They differed in
efficiency and changed some individual predictions, but every policy solved
the same 188 of 256 targets. Bounded reach was identical. Something improved,
and it was not capability.

In a later study, an earlier version of our test-time adaptation path
appeared to activate often. When the comparison was examined it turned out
not to be additive, so activation counts could not be read as evidence of
anything. Architecture has to be tested causally, not inferred from how often
a component fires.

That is why CORA insists on a six-leg causal witness before calling anything
capability growth: the baseline language must fail, the extension must be
produced, the winning program must use it, full adaptive leave-one-out must
pass, the final output must be exactly correct, and removing the extension
must destroy the gain.

We also keep a four-rung claim ladder. Generating a new program is not a new
capability. A new composition is not automatically new semantics. A macro is
not semantic novelty. A score gain is not invention.

## 4. ARC-AGI-2 submission system

The submitted notebook runs offline within the twelve-hour limit and emits
submission.json covering every task id and every test-output position, each
with two attempts. A fallback guarantees two syntactically valid attempts for
every task, so no task id can be missing even if a solver path fails or times
out. A global time governor rescales per-task budgets against remaining wall
clock, so the run finishes inside budget rather than being cut off.

The submitted inference system is the induction, execution and verification
stack described in section 2. The failure-driven construction research
described below is not part of it, and no part of the leaderboard result may
be attributed to it.

## 5. Results

Leaderboard results are pending: submission id, notebook version, scores and
measured runtime. We do not substitute training accuracy for leaderboard
accuracy, and no hypothetical score appears here.

The results we can report are diagnostic, and one is a negative result we
consider important.

We audited the failure representation that the construction path was supposed
to consume, on twelve development tasks fixed by a rule committed before any
result was computed. That channel produced 64,610 candidate events and 144
frontier terms, but zero executed near misses, zero value signatures and zero
mismatch signatures. On eleven of the twelve tasks its candidate census was
byte-identical. Three structurally unrelated synthetic tasks reproduced the
same census and the same ordered candidates. Every frontier term came from a
single operator.

The cause was not the idea. It was a disconnect: the thing doing the real
reasoning was not the thing being observed. The trace observer was attached
to a restricted eleven-primitive proxy search, while the deployed object
reasoner had no trace path at all. This also explains an earlier null result
in which shuffled failure evidence performed about as well as real failure
evidence. There was almost no task-specific information in the real evidence
to destroy.

We then instrumented the deployed reasoner in an isolated copy, without
changing its search. Fixtures require that the result with observation equals
the result without observation, compared on exactness, strategy, training
accuracy, leave-one-out score, best accuracy, failure stage, pixel fit and
the serialized programs. Those fixtures pass.

On the same twelve tasks the repaired channel produced 494 candidate events,
twelve distinct frontier operator families instead of one, 62 successful
parameter fits, 36 executable near misses and 7 exact candidates. A final
compatibility repair let the failure graph execute the real candidate
representation instead of assuming the proxy one, which carried the mismatch
evidence into the graph: 18 defined value signatures where there had been
zero. Eight of twelve tasks met the preregistered diagnostic threshold, which
was fixed in advance at eight of twelve, and the verdict was identical across
three independent runs.

That is a diagnostic result about an evidence channel. It is not a capability
result, and nothing about reach or score follows from it.

## 6. Why it works or fails

The diagnosis categories we track are: no useful candidate generated;
candidate present but not selected; candidate fit the demonstrations but was
wrong; verification rejected it; resources exhausted; output lost in
packaging.

The audit above added a category we had not been able to see before. On three
of the twelve tasks the reasoner emits no candidates at all, because it gives
up before rule induction at segmentation or matching. No repair of the
evidence channel can help there. That is a perception and correspondence
limit, not a language limit, and it tells us where the next real work is.

## 7. Universality

CORA separates the domain-specific semantics of ARC from a domain-general
control loop. ARC supplies grids, objects and executable transformations.
CORA supplies failure localization, typed interfaces, executable
construction, exact evaluation, leave-one-out verification and causal
ablation. We formalize a reasoning domain as a tuple of observations,
targets, a type system, an executable capability language, an executor and an
immutable verifier, and define the adaptation loop over that tuple. ARC is
then one instantiation rather than the definition of the method. In another
executable domain the grid vocabulary can be replaced while the control
architecture is retained.

We claim architectural portability, not demonstrated cross-domain
performance. Three levels should not be confused: the loop is independent of
grids; a new domain could supply its own types, operators and verifier; and
the same implementation actually succeeding elsewhere is a third claim we do
not make. Empirical transfer beyond ARC remains future work.

One design choice supports this more than any argument. CORA refuses
task-family lookup, handwritten operators added after inspecting a failure,
and direct answer generation. Those would raise an ARC score and produce a
less general system. What remains are generic concepts: failure, type,
executable behaviour, causal necessity and held-out reconstruction.

## 8. Limitations

The limitations are substantial. The public ARC score is not yet measured and
may remain low. Our verification has shown poor off-distribution calibration:
40 of 42 on training against 0 of 11 on an evaluation development split. The
repaired failure evidence has not yet produced any autonomous construction.
The constructive proposer and its compiler are specified and unimplemented.
A separate durable capability-growth experiment is still running and has no
interpretable verdict, and none of its candidates or outcomes are used here.
The diagnostic classification rests on twelve tasks and sits exactly at its
threshold. ARC results alone do not establish general intelligence.

What we offer is a system that refuses to confuse a better score with a
better reasoner, and an honest account of the point at which its own
self-observation was broken and how we found it.
