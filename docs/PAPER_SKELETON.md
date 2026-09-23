# CORA: Separating Search, Hypothesis Selection, and Capability Growth in ARC-AGI-2

Authoritative technical manuscript for the ARC Prize 2026 Paper Track.
Updated 2026-09-23. No LaTeX source, compiled PDF or BibTeX file exists in
this workspace, so there is no compile step and no page count to report;
section 10 is the bibliography stub. The concise Paper Track writeup is
`kaggle/writeup.md`, at most 1,500 words, describing the same implemented
system. The title changes to match the measured result, never the desired one.

## Abstract

CORA studies the difference between searching for a program within a fixed
executable language and adapting the language itself. The system combines
non-LLM program induction with immutable leave-one-out verification and
separates, formally and empirically, three things reasoning research often
conflates: better search, better hypothesis selection, and growth in
capability.

A diagnostic audit reported here found that the original test-time failure
representation observed a restricted proxy search rather than the deployed
ARC reasoner. Over twelve prospectively fixed development tasks that channel
produced no executed near misses and no mismatch evidence, and its candidate
census was identical across structurally unrelated tasks. That explains a
previous null result in which shuffled failure evidence performed about as
well as real failure evidence.

Instrumenting the deployed reasoner, without changing its search, exposed
task-dependent candidate frontiers, successful parameter fits and executable
near misses. A subsequent compatibility repair between the real candidate
representation and the failure-graph evaluator carried that evidence into the
graph and moved the channel across its preregistered diagnostic threshold.
The constructive components that would consume the evidence remain
unimplemented, so no capability claim follows.

Durable semantic invention remains under independent evaluation in the frozen
Step-B experiment, which is ongoing and has no interpretable verdict. We do
not claim that CORA has demonstrated semantic invention.

## Contributions

1. A formal and empirical separation of search improvement, hypothesis
   selection and capability growth.
2. A non-LLM ARC reasoning system with immutable leave-one-out verification.
3. A frozen causal-witness protocol for durable capability growth.
4. An architecture for failure-conditioned task-local language adaptation.
5. An empirical diagnosis showing that an earlier failure representation
   observed the wrong reasoning process.
6. A repaired full-engine observation path exposing task-specific semantic
   frontiers and executable near misses.
7. Negative results showing why score gains, search gains and known-operator
   reconstruction are insufficient evidence of semantic invention.

## 1. Introduction

### 1.1 Competition constraints this paper is written against

| item | value |
|---|---|
| ARC-AGI-2 entry deadline | 2026-10-26, 23:59 UTC |
| final prediction and code submission | 2026-11-02, 23:59 UTC |
| Paper Track final deadline | 2026-11-09, 23:59 UTC |
| submission form | Kaggle Notebook |
| runtime limit | 12 hours CPU, or 12 hours GPU |
| internet | disabled |
| external data | freely and publicly available external data allowed |
| output | `submission.json` |
| predictions per task output | exactly two, `attempt_1` and `attempt_2` |
| coverage | every task id in the challenge JSON must appear |
| scoring | exact match; credit if either attempt matches exactly |
| Paper Track requirements | Kaggle Writeup, cover image, attached public notebook |
| Paper Track optional | public project link, which may host this PDF |
| writeup limit | 1,500 words |

A draft or unsubmitted writeup at the deadline does not count.

### 1.2 The problem

Most ARC progress is reported as a score. A score cannot distinguish three
different improvements: the search found a program faster, the selection rule
picked a better program from the same pool, or the system became able to
express something it previously could not. Conflating them makes progress
hard to interpret and makes architecture claims untestable.

This paper is organized so that each of the six Paper Track criteria is
supported by identifiable evidence together with the boundary of that
evidence. No rubric score is predicted anywhere.

## 2. Search, Selection and Capability Growth

### 2.1 The core theoretical question

Ordinary parameter learning adapts weights:

    theta -> theta'

Ordinary fixed-language reasoning searches inside a language:

    search over p in K

CORA asks whether reasoning can modify the language:

    K -> failure -> construct e -> K' = K union {e} -> search over K'

The theoretical hypothesis is that some failures occur because the current
hypothesis is wrong, while others occur because the current executable
language cannot express an adequate hypothesis within the relevant bound. A
reasoner may therefore need to reason about the inadequacy of its own
reasoning language. CORA has not proven this hypothesis.

### 2.2 Why failure evidence should help, mechanistically

A failed search is not empty. It contains which partial programs executed,
what types were reached, where parameter fitting failed, which relations were
preserved, how near-miss outputs differed, and where verification failed.
That evidence may constrain the missing capability far more efficiently than
blind expansion of the whole program language. This remains a hypothesis
until constructive experiments test it.

### 2.3 Why verification must stay separate

Proposal and knowledge acquisition are kept apart. The constructor may
propose; only the verifier accepts. This is what prevents generated novelty
from being mistaken for useful capability. The strong causal witness requires
all six legs:

- B: the baseline language fails;
- P: the extension is produced;
- U: the winning program uses it;
- L: full adaptive leave-one-out passes;
- T: the final output is exactly correct;
- A: removing the extension destroys the gain.

The comparison must be genuinely additive, with matched solver conditions and
resource accounting.

### 2.4 Two timescales, as theory rather than implementation detail

    fast task adaptation:  K -> K union {e_j} -> solve task j -> reset
    durable learning:      K_t -> verified transferable e -> K_{t+1}

These answer different questions. The first asks whether capability
construction can run fast enough to matter at inference. The second asks
whether a candidate capability deserves to become permanent knowledge. They
share the idea and share no evidence.

### 2.5 The claim ladder

- L1, generation: a candidate or new AST was produced.
- L2, operational language extension: adding it changes bounded search reach.
- L3, bounded semantic expressivity extension: under declared bounds, the
  prior language cannot reproduce its behaviour.
- L4, bounded semantic invention: L3 with causal new reach and independent
  transfer.

Four distinctions follow: a new program is not a new capability; a new
composition is not automatically new semantics; a macro is not semantic
novelty; a score gain is not invention.

## 3. CORA Architecture

CORA is non-LLM. No language model runs at inference.

### 3.1 The complete submitted pipeline

1. ARC input format: demonstrations and test inputs are read from the
   challenge JSON. Test outputs are never read.
2. Perception: each grid is segmented into objects under several
   segmentation variants.
3. Ordinary reasoning: correspondences are built between input and output
   objects, a selector is induced for the objects a rule applies to, and
   typed parameter expressions are fitted for the action it performs.
4. Candidate generation: programs are assembled from induced rules with an
   induced default action and an output specification.
5. Parameter fitting: occurrence-scoped fitting of typed parameter
   expressions per object group.
6. Exact execution: a program is rendered on every demonstration.
7. Leave-one-out verification: the entire learning procedure is re-run from
   all demonstrations but one and must independently re-derive a program
   that solves the held-out example, for every fold.
8. Failure handling: the stage at which induction gave up is recorded.
9. Failure representation: the typed failure graph is built from the observed
   candidate lifecycle. Research instrumentation, not a solver component.
10. Candidate selection: certified programs are ranked.
11. attempt_1: the certified output under the frozen policy.
12. attempt_2: a complementary uncertified candidate chosen to be
    independently plausible rather than merely different.
13. Global budget governor: per-task budgets are rescaled against remaining
    wall clock so the run finishes inside twelve hours.
14. Fallback and submission writer: two syntactically valid attempts are
    guaranteed for every task, and `submission.json` covers every task id and
    every test-output position.

### 3.2 What is research and not part of the submitted solver

The constructive AST proposer and the ConstructiveExtensionCompiler are
specified and unimplemented. The failure representation and its repair are
diagnostic instrumentation. None of these contribute to the leaderboard
result, and the paper attributes nothing to them. Binding requirement: the
manuscript method, the writeup method and the public notebook method are the
same method for every claim about the submitted solver.

## 4. Failure-Conditioned Language Adaptation

    K -> ordinary reasoning -> failure -> typed failure graph
      -> constructive AST proposal  [specified only]
      -> ephemeral K union {e}      [specified only]
      -> ordinary re-induction -> verification -> prediction -> reset to K

The extension is discarded after the task.

Implemented and tested: typed failure graph infrastructure; the constructive
grammar and vocabulary; AST canonicalization; occurrence-scoped fitting;
orchestration; a Stage-A known-name proposal network; exact execution; the
leave-one-out verifier; an ablation ledger; task-local install and reset
infrastructure; scheduler and diversity; a Kaggle emulator.

Two corrections to earlier internal descriptions, recorded because they
change what may be claimed. The fallback proposer is not a constructor: it
ranks existing catalogue production names by cost and name. The constructive
vocabulary defines what a legal constructive AST is; it does not decide which
new AST to construct, and it is not a proposal mechanism.

Not implemented: the grammar-constrained unseen-AST proposer, and the
extension compiler. Neither is marked complete in any text or figure.

## 5. Durable Capability Growth

Step B is not the competition solver. It is an independent experiment asking
whether a candidate capability deserves to become durable knowledge.

    certified historical failures -> 62 failure clusters
      -> 4,784 frozen candidate extensions -> candidate installation
      -> resolution testing -> frozen capability-growth gate
      -> bounded semantic separation -> transfer -> possible promotion

Frozen inventory: 816 K2 semantic-production candidates and 3,968 K1 repair
candidates.

Latest recorded checkpoint, not a live claim and not an inspection of
semantics: K2 proposal phase at 350 of 497 units, zero recorded errors, no
freeze marker, no final output hash.

Step B remains ongoing and has no interpretable semantic verdict at the time
of this manuscript revision. No Step-B candidate or outcome enters the
competition solver.

## 6. Experiments: Accuracy and Controlled Comparison

### 6.1 The submitted configuration

| field | value |
|---|---|
| ARC-AGI-2 submission id | PENDING FINAL KAGGLE SUBMISSION |
| public notebook URL | PENDING FINAL KAGGLE SUBMISSION |
| notebook and configuration identity | PENDING FINAL KAGGLE SUBMISSION |
| leaderboard score, public | PENDING FINAL KAGGLE SUBMISSION |
| leaderboard score, private | PENDING FINAL KAGGLE SUBMISSION |
| pass@1 | NOT YET MEASURED |
| pass@2 | NOT YET MEASURED |
| attempt-2 rescues | NOT YET MEASURED |
| task outputs scored | NOT YET MEASURED |
| runtime | NOT YET MEASURED |
| timeout rate | NOT YET MEASURED |
| failed-task rate | NOT YET MEASURED |

Training accuracy, synthetic accuracy and development-split accuracy are
never substituted for the leaderboard score.

### 6.2 The controlled comparison

BASE is fixed-language CORA. TREATMENT is failure-conditioned language
adaptation, included only if implemented in the final submission. MATCHED
SEARCH gives BASE the same additional compute without constructive
adaptation. ABLATION removes a successful extension. Gains, losses, unchanged
tasks and runtime cost are reported as paired outcomes, never as a net
figure, under one fixed budget and a schedule frozen before scoring.

If the adaptation path is not ready at code freeze, none of its experimental
results are claimed as a leaderboard contribution. It is then reported only
as an independent research experiment.

### 6.3 Two-attempt accounting

Scoring credits the better of two attempts, so the second attempt is measured
as rescue rather than as diversity. Differing predictions are not reported as
a benefit. The reported categories are:

| category | value |
|---|---|
| attempt_1 correct | NOT YET MEASURED |
| attempt_2 correct where attempt_1 failed, a rescue | NOT YET MEASURED |
| both wrong | NOT YET MEASURED |
| both identical | NOT YET MEASURED |
| different but non-rescuing | NOT YET MEASURED |

Unknown quantities are never written as zero.

## 7. The Failure-Frontier Audit

### 7.1 Method

Twelve development tasks were fixed by a rule committed before any result was
computed: the first twelve task identifiers in ascending order. Only the
existing failure path was run. Nothing was proposed, constructed, installed
or scored, and no test outputs were read.

### 7.2 The negative result

| quantity | value |
|---|---|
| observer candidate events | 64,610 |
| frontier-eligible events | 32,305 |
| frontier terms | 144 |
| executed-but-non-exact candidates | 0 |
| value signatures | 0 |
| mismatch signatures | 0 |

On eleven of twelve tasks the census was identical:

    {typed: 2736, slot_fit_failed: 2736}

The twelfth differed only because it hit its deadline. Three structurally
unrelated synthetic tasks, a tiling, a transpose and a crop, reproduced the
same census and the same ordered frontier programs. Every frontier term came
from a single root operator.

The candidate-associated evidence was effectively invariant to the ARC task.
This explains why a prior shuffled-evidence control performed similarly to
real associated evidence: there was almost no task-specific information to
destroy.

### 7.3 Root cause

The thing doing the real ARC reasoning was not the thing being observed. The
trace observer was attached to a restricted eleven-primitive proxy runtime,
and the deployed object reasoner had no equivalent trace path. The old null
is therefore not evidence that failure-conditioned construction is useless.

### 7.4 Full-engine observation repair

The isolated delivery copy of the real reasoner was instrumented to expose
its candidate lifecycle: typed, then parameter fitting that fails or
succeeds, then a program that executes non-exactly or exactly. The live
research engine was not modified, verified afterwards by confirming the
shared failure-graph code and the research engine directories were unchanged.

One engine property mattered: the reasoner assembles a program only when
every object group is explained, so its genuine near misses are the partial
programs it builds at the failure branch and discards.

This is instrumentation, not a new solver. Noninterference fixtures require
that the result with observation equals the result without observation,
compared on exactness, strategy, training accuracy, leave-one-out score, best
accuracy, failure stage, pixel fit and both serialized programs. They pass.

### 7.5 Repaired result

| quantity | original | repaired |
|---|---|---|
| candidate events | 64,610 | 494 |
| identical census across unrelated tasks | yes | no |
| distinct frontier operator families | 1 | 12 |
| parameter-fitting successes | 0 | 62 |
| executed-but-non-exact candidates | 0 | 36 |
| exact candidates | 0 | 7 |

Observed operator families included grow, translate, copy, copy_part,
composite, paint and keep. Three of the twelve tasks emit nothing, because
the engine gives up before rule induction.

### 7.6 Candidate-executor compatibility

The repaired producer recorded fitted, executable programs, but the consumer
still evaluated every candidate with the proxy evaluator, which cannot
execute that representation, so every value signature degraded to undefined.
The compatibility repair adds one optional evaluator parameter, defaulting to
the previous behaviour, so the builder asks which executor owns a candidate.
It changes only how an already-observed candidate is executed for diagnostic
evidence.

| quantity | before | after |
|---|---|---|
| defined value signatures in the graph | 0 | 18 |
| tasks with at least two frontier terms | 9 of 12 | 9 of 12 |
| tasks with defined candidate-associated evidence | 0 of 12 | 8 of 12 |
| tasks meeting both preregistered conditions | 0 of 12 | 8 of 12 |

The preregistered diagnostic threshold was at least eight of twelve on both
conditions jointly, so the repaired channel is classified informative. The
verdict was identical across three independent runs.

Three cautions belong with it. It sits exactly at the threshold. The
qualifying eight tasks are the same eight the producer-side probe had already
identified, so the repair transported existing evidence rather than creating
new evidence. And this classifies a diagnostic channel, not a capability.

### 7.7 The reusable lesson

Before learning from reasoning failures, verify that the failure
representation actually depends on the task and reflects the deployed
reasoner's internal near misses. A representation can be correct in format
and empty in content. That test is cheap, it is domain-independent, and in
our case it overturned the interpretation of an earlier null result.

## 8. Generalization and Universality

### 3.1 What is ARC-specific and what is not

ARC-specific: the grid representation; object segmentation; the colour
vocabulary; spatial relations; rendering operations; the executable
primitives themselves; and the Kaggle submission and output policy.

Domain-general: the executable hypothesis language as a replaceable
parameter; a mechanistic representation of reasoning failure; typed
interfaces between capabilities; failure-conditioned proposal of executable
structure; exact execution; immutable verification; adaptive leave-one-out
reconstruction; the additive comparison of K against K with e; causal
removal; the distinction between selection gain, search gain, operational
extension and semantic extension; the separation of ephemeral from
persistent capability growth; and provenance-controlled promotion.

The universality argument rests entirely on the second group.

### 3.2 The domain-general loop

    observations D
      -> reason using executable language K
      -> detect failure
      -> represent the failure mechanistically
      -> identify a missing typed capability interface A -> B
      -> construct a candidate executable capability e
      -> K' = K union {e}
      -> reason again
      -> verify
      -> retain temporarily, or promote persistently

ARC is one instantiation of this loop. The loop has not been validated
outside ARC, because no such experiment exists.

### 3.3 A formal domain abstraction

Let a reasoning domain be

    D = (X, Y, T, K, Execute, V)

where X are observations, Y are target outputs or behaviours, T is a type
system, K is the current executable capability language, Execute is the
domain executor and V is the immutable verification procedure. CORA operates
on D together with failure evidence. It does not require X and Y to be grids.

ARC is the concrete instantiation in which X are grids, T contains Grid,
Entity, Region and Relation, K is the set of ARC executable productions,
Execute is the exact renderer, and V is demonstration fit plus adaptive
leave-one-out plus external exact output scoring.

### 3.4 Why this could translate

The transferable object is not an ARC pattern. It is the pair of a typed
executable capability and a verifier. Another domain should be able to
replace Grid, Region, Object, Paint and Translate with its own executable
types and operations while retaining failure localization, typed gap
identification, construction, exact execution, verification, causal ablation
and promotion or reset.

CORA does not claim one universal object vocabulary. It proposes a
potentially reusable protocol for reasoning about and extending a domain's
executable vocabulary.

The following mappings are analogies that show how the abstraction could
translate. They are not completed experimental transfer.

| CORA abstraction | ARC instantiation | example non-ARC instantiation |
|---|---|---|
| state or observation | grid | molecule, cell state, image, graph |
| entity | object or region | protein residue, cell, lesion, gene module |
| relation | spatial relation | interaction, neighbourhood, temporal dependency |
| capability | grid transformation | geometric transformation, biological operator, analysis procedure |
| failure frontier | near-miss ARC programs | partially successful models or procedures |
| typed gap | set of regions to grid | molecular state to property, cell population to aggregate state |
| verifier | exact held-out grid | held-out measurement, simulation, or assay-compatible criterion |
| extension e | task-local ARC production | new executable analysis or transformation rule |

### 3.4a A second executable domain, and what it does and does not show

A separate project in the same research group instantiates part of this
control architecture in a different executable domain: perturbation response
prediction and decision policy over cell-line panels. It is independent work
with its own aims, and it is named here only as universality evidence.

What it shares is architecture, not implementation. It imports no code from
the ARC system. What it reproduces is the verification half of the control
loop:

- an independently re-implemented verifier, whose replay module deliberately
  does not call the routine that issued the certificate, so proposal and
  acceptance cannot collapse into each other;
- a protocol frozen before results and identified by hash;
- matched comparison arms, five decision policies scored under one protocol;
- held-out context rotation, the leave-one-out discipline applied at the
  level of cell line rather than demonstration;
- development-only calibration with outcome joining restricted to the
  evaluator, the same sealed-holdout separation used here;
- negative results reported rather than absorbed. Its one matched real trial
  reported no yield gain for the verification policy.

What it does not share is the capability-growth half. It has no typed failure
graph, no constructive extension and no comparison of a language against
itself plus an extension. It reports no official evaluator score and claims
no empirical decision benefit.

The honest reading is narrow. This raises representational portability from
by-construction to partially exercised, for the verification and
matched-comparison half of the architecture, in one other domain. It does not
establish empirical cross-domain transfer, and it is not evidence that CORA
generalizes to biology. The most informative thing it demonstrates is that
the discipline survives the move: a transferred protocol that was willing to
report a null result is behaving as intended.

### 3.5 Three levels of universality

- U1, architectural portability: the failure, construct, execute, verify loop
  is independent of grids.
- U2, representational portability: a new domain can supply its own typed
  entities, relations, operators and verifier while preserving the control
  architecture.
- U3, empirical cross-domain transfer: the same implementation or learned
  construction strategy succeeds in a non-ARC domain.

Current evidence supports U1 by architecture. U2 is supported by
construction and, as section 3.4a records, partially exercised in one other
executable domain for the verification and matched-comparison half of the
loop. U3 is not claimed: no cross-domain experiment establishes that the
method succeeds elsewhere, the one matched trial in that domain reported no
gain, and the capability-growth half was never instantiated there.

### 3.6 Why the failure representation was designed to be domain-general

The typed failure graph was deliberately built from abstract content: which
partial programs were executable, what types they produced, what type was
required, which slots failed, which relations were preserved or violated, how
partial outputs differed, and at what stage verification failed. It carries no
task identifier, no family name, no natural-language solution and no hidden
answer.

The honest qualification matters here. That domain-general representation was
connected to the wrong reasoner. As section 8 reports, the initial
implementation observed a restricted proxy search, and full-engine
instrumentation was required before the abstraction could receive meaningful
task-specific evidence at all.

That negative result strengthens rather than weakens the methodological
point: a representation is general only in the sense that it is connected to
the actual reasoning process. Generality of format is not generality of
content.

### 3.7 The two timescales as general concepts

    fast adaptation:    K -> K union {e_j} -> solve task j -> reset
    durable learning:   K_t -> verified transferable e -> K_{t+1}

Both make sense outside ARC. A system could construct a temporary analysis
procedure for one scientific problem, and separately promote a repeatedly
verified procedure into a persistent library. This is architectural
applicability, not demonstrated behaviour.

### 3.8 Four different generalization claims

These are distinct and one is never used as evidence for another:

1. generalization across ARC tasks within a structural family;
2. transfer across ARC structural families;
3. transfer of a constructed capability from one ARC task to another;
4. transfer of the architecture to a different executable domain.

Only the first is partially evidenced by ordinary ARC measurement. The third
is the subject of the transfer leg in the durable experiment. The fourth is
untested.

### 3.9 What the project refuses to do, and why that matters here

CORA rejects task-family lookup, handwritten solution operators added after
inspecting a failure, direct answer-grid invention, and success defined only
by leaderboard gain. Those shortcuts would produce a better ARC score and a
less general system. Instead the system is built to operate on generic
concepts: failure, type, executable behaviour, causal necessity and held-out
reconstruction. That refusal is part of the universality argument rather than
an aside.

### 3.10 Summary of universality boundaries

| claim | status |
|---|---|
| within-ARC generalization | partially evidenced by ordinary measurement |
| architectural portability, U1 | supported by design and by the formal abstraction |
| representational portability, U2 | partially exercised in one other domain, verification half only |
| cross-domain empirical transfer, U3 | not demonstrated; the one matched trial elsewhere reported no gain |
| the capability-growth half in another domain | never instantiated |
| transfer to biology, protein design or omics | not demonstrated, prospective only |

## 8.5 Corpus amendment required before the scorer can be fitted

The Stage-B proposer exists and demonstrates legal new-AST generation from
real failure graphs, deterministically and in about 0.03 seconds per task.
Its failure conditioning remains weak: across five prospectively fixed real
failures whose evidence differs substantially, all five share the same
rank-one candidate.

Fitting the scorer that would supply that conditioning is blocked rather than
merely unfinished. Protocol v1.1 admitted zero of 1,500 attempted targets,
and its own recorded root cause is structural: the type-keyed slot learner
collapsed multiple induced-slot occurrences onto one, so the fitting
requirement was satisfiable only for schemas that reduced to the single
triple space the baseline enumerates. Passing the fitting requirement implied
failing the out-of-baseline requirement. Separately, the only verified
admitted episodes anywhere carry empty failure frontiers, because they were
produced through the proxy runtime that the observation repair replaced.

A preregistered v1.2 corpus amendment was therefore frozen before any
generation, with the protocol document and its manifest hashed. It changes
the target and evidence side only. The baseline keeps its productions, its
depth, its budget and its ordering, and both sides use the same
occurrence-scoped fitter, with an identity mismatch between them recorded as
a fairness violation that rejects the episode. The separation is structural
rather than a fitter privilege: the baseline enumerates 200 single-block
schemas while the constructive grammar admits up to three blocks, so under
occurrence-scoped fitting a multi-block target no longer collapses onto a
single triple. Episode failure graphs now come from the repaired full-engine
path, so training and inference share evidence semantics.

Corpus quality criteria, and the controls a fitted scorer must beat, were
fixed in the same freeze, so a non-zero admission count alone will not be
reported as success. No v1.2 episode has been generated. Nothing about a
trained scorer, construction, reach, transfer or score is claimed.

## 9. Ablations and Failure Analysis

### 9.1 Diagnosis categories

No useful candidate generated; candidate present but not selected; candidate
fit the demonstrations but was wrong; verification rejected it; resources
exhausted; output lost in packaging.

The audit added a category previously invisible. On three of twelve tasks the
reasoner emits no candidates at all, giving up before rule induction at
segmentation or matching. No repair of the evidence channel helps there. That
is a perception and correspondence limit rather than a language limit.

### 9.2 Failures that must be reported alongside successes

| quantity | value |
|---|---|
| tasks harmed relative to base | NOT YET MEASURED |
| construction failures | NOT YET MEASURED |
| verification failures | NOT YET MEASURED |
| timeouts | NOT YET MEASURED |
| resource exhaustion | NOT YET MEASURED |
| unsolved tasks | NOT YET MEASURED |
| cases where attempt 2 adds nothing | NOT YET MEASURED |

### 9.3 Preserved negative results

- A learned-prior study did not robustly beat concrete memory, and every
  compared policy had the same bounded reach: all solved the same 188 of 256
  targets. Efficiency and individual predictions changed; reach did not.
- An earlier task-time comparison was not additive, so activation counts
  could not be read as evidence. Architecture must be tested causally.
- The first proposal network performed known-name reconstruction.
- The first constructive census admitted nothing, and its own recorded root
  cause shows it cannot: the registered slot learner and the fixed base
  search enumerate the same product, so any target the learner can fit is
  already reachable by the baseline. Zero of 1,500 attempted targets were
  admitted.
- The corrected census admitted thirteen supplied candidate structures, which
  are not thirteen autonomous inventions. Every one of those thirteen carries
  an empty failure frontier, so they also predate the observation repair and
  cannot supervise a failure-conditioned proposer.
- The original failure channel carried no task-conditioned evidence.
- A five-task rehearsal of the previous library version was engineering only:
  packaging and schema worked, the governor bound but overran, the previous
  version solved none of the five, and some failures reached the
  leave-one-out or matching stages. Relational parameter fitting was
  provisionally selected after that diagnostic and is no longer the primary
  treatment; it may return later as an inner fitter.

### 9.4 Reproducibility

Another researcher should be able to reproduce the fixed-language baseline,
the task-time adaptation comparison, the failure-frontier diagnostics, the
causal ablation, the two-attempt policy and the runtime accounting. The
public notebook is intended to make the practical ARC method reusable
independently of the research components.

## 10. Related Work

CORA is not claimed to be first at program synthesis, learned libraries,
predicate invention, executable code generation, test-time adaptation,
verifier-guided search or abstraction learning. Each has prior art.

To be discussed and distinguished: DreamCoder, LILO, predicate invention and
POPPI, AlphaEvolve, program synthesis and library learning, and relevant
non-LLM ARC systems. No precedence wording is used without a current
primary-source check. This section is the bibliography stub; no formal
bibliography file exists yet.

The candidate novel contribution is the conjunction: failed reasoning, to a
mechanistic typed failure representation, to diagnosis of a capability gap,
to an executable language extension, to an additive comparison of the
language with and without it, to full adaptive leave-one-out, to a causal use
test, to removal ablation, to bounded semantic separation, to independent
transfer, to verifier-controlled promotion. The full conjunction has not been
demonstrated and is not claimed.

A second, smaller novel result stands on its own: the failure-frontier audit
is a diagnostic result about machine self-observation. A system's record of
its own reasoning failures was found to be task-invariant, which explained an
earlier control result, and instrumenting the deployed reasoner exposed
task-dependent semantic frontiers. That is not semantic invention.

## 11. Limitations

- The public ARC score is not yet measured and may remain low.
- Verification has shown poor off-distribution calibration: 40 of 42 on
  training against 0 of 11 on an evaluation development split.
- The repaired failure evidence has not produced any autonomous unseen-AST
  capability.
- The constructive AST proposer is unfinished.
- The extension compiler is unfinished.
- Step B has no verdict.
- The informative classification rests on twelve tasks and sits exactly at
  its threshold.
- Three of those twelve tasks emit no candidates at all.
- Bounded semantic separation does not establish universal non-definability.
- Empirical cross-domain transfer is not demonstrated.
- ARC results alone do not establish general intelligence.

## 12. Conclusion

CORA separates three things a score cannot separate, and holds a fixed
verifier between proposal and acceptance so that generated novelty is not
mistaken for capability. The measured contribution in this revision is a
negative result and its repair: the system's record of its own reasoning
failures was observing the wrong reasoner, which explained an earlier null,
and repairing the observation exposed task-dependent semantic frontiers with
executable near misses. The constructive step that would use them is
specified and unbuilt, and the durable-growth experiment has no verdict. We
report what is measured and mark the rest unmeasured.

## Appendix A. Evidence mapped to the six criteria

Internal coverage check, not a self-score and not for rubric prediction.

| evidence | accuracy | universality | progress | theory | completeness | novelty |
|---|---|---|---|---|---|---|
| final leaderboard submission | pending | no | no | no | yes | no |
| two-attempt rescue accounting | pending | no | yes | partly | yes | no |
| fixed versus adaptive comparison | pending | no | yes | yes | yes | partly |
| bounded-reach result, 188 of 256 | no | no | yes | yes | yes | partly |
| non-additive prior comparison | no | no | yes | yes | yes | no |
| failure-frontier audit | no | partly | yes | yes | yes | yes |
| full-engine observation repair | no | partly | yes | yes | yes | yes |
| candidate-executor compatibility repair | no | no | yes | partly | yes | partly |
| matched-compute ablation | pending | no | yes | yes | yes | no |
| constructive reach witnesses | not yet | no | not yet | yes | not yet | yes |
| bounded semantic separation | not yet | partly | not yet | yes | not yet | yes |
| independent transfer | not yet | yes | not yet | yes | not yet | yes |
| Step-B durable-growth result | no | partly | not yet | yes | partly | yes |

## Appendix B. Rubric audit

**Accuracy.** In the paper: the complete submitted pipeline, the two-attempt
policy, the budget governor, the fallback guaranteeing coverage, and the
controlled comparison design. Missing: every leaderboard number. This is the
weakest criterion until a submission exists, and no other section compensates
for it.

**Universality.** In the paper: a domain-independent formalism over the tuple
of observations, targets, types, capability language, executor and verifier;
a failure representation carrying no task id, family name or answer;
separation of verifier from proposer; both task-local and durable adaptation
mechanisms; explicit refusal of task-family lookup and direct answer
generation. Architectural rather than empirical: representational
portability is by construction and unexercised, and cross-domain transfer has
no experiment.

**Progress.** Reusable by another researcher: the distinction between search,
selection and capability growth with a concrete case where reach was
unchanged; the warning that activation counts are not causal evidence; and
the cheap domain-independent test that a failure representation must vary
with the task before anything is learned from it.

**Theory.** The paper states the hypothesis, why failure evidence should
constrain the missing capability more efficiently than blind expansion, why
proposal and acceptance must be separated, and why the two timescales answer
different questions. It does not claim the hypothesis is proven.

**Completeness.** A reader can reconstruct the submitted system from section
3.1. Research components are labelled and excluded from the leaderboard
claim. Failure categories are listed with unmeasured entries marked.

**Novelty.** After accounting for prior art, what remains is the conjunction
in section 10, which is not demonstrated, plus the self-observation
diagnostic, which is.

**Flagged weakness.** Accuracy has no evidence yet. That is stated here
rather than hidden behind the stronger sections.

## Out of scope

Capability-growth gate internals, the parallel verified-capability scaling
project, and biological applications.
