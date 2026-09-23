# CORA: Separating Search, Hypothesis Selection, and Capability Growth in ARC-AGI-2

Authoritative technical manuscript for the ARC Prize 2026 Paper Track.
Updated 2026-09-23. No LaTeX source, compiled PDF or BibTeX file exists in
this workspace yet, so there is no compile step and no page count to report;
section 16 is the bibliography stub. The concise Paper Track writeup is
`kaggle/writeup.md`, which must stay under 1,500 words and must describe the
same implemented system as this document.

The title changes to match the measured result, never the desired one.

## Abstract

CORA studies the difference between searching for a program within a fixed
executable language and adapting the language itself. The system combines
non-LLM program induction with immutable leave-one-out verification and
separates, both formally and empirically, three things that reasoning
research often conflates: better search, better hypothesis selection, and
growth in capability.

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
unimplemented, so no capability claim follows from it.

Durable semantic invention remains under independent evaluation in the frozen
Step-B experiment, which is ongoing and has no interpretable verdict. We do
not claim that CORA has demonstrated semantic invention.

## Contributions

1. A formal and empirical separation of search improvement, hypothesis
   selection and capability growth.
2. A non-LLM ARC reasoning system with immutable leave-one-out verification.
3. A frozen causal-witness protocol for durable capability growth.
4. CORA-TTI, an architecture for failure-conditioned task-local language
   adaptation.
5. An empirical diagnosis showing that an earlier failure representation
   observed the wrong reasoning process.
6. A repaired full-engine observation path that exposes task-specific
   semantic frontiers and executable near misses.
7. Negative results showing why score gains, search gains and known-operator
   reconstruction are insufficient evidence of semantic invention.

## 1. Competition facts this paper is written against

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

The Paper Track scores six criteria with equal weight: Accuracy,
Universality, Progress, Theory, Completeness and Novelty. Accuracy is one
sixth of the score and rests on the actual leaderboard submission, so the
leaderboard is not a formality here. The remaining five sixths are where the
distinction between fixed-language search and verified language adaptation
has to be documented carefully and without overstating unfinished work. The
sections below are organized to give measured evidence for each criterion,
not to argue for them rhetorically.

## 2. Accuracy: the submitted configuration

| field | value |
|---|---|
| ARC-AGI-2 submission id | PENDING |
| public notebook URL | PENDING |
| notebook version | PENDING FINAL SUBMISSION |
| solver policy version | PENDING FINAL SUBMISSION |
| attempt_1 policy | certified output under the frozen final policy |
| attempt_2 policy | complementary uncertified candidate, chosen to maximize genuine independent probability of correctness |
| measured runtime | NOT YET MEASURED |
| public leaderboard score | NOT YET MEASURED |
| private leaderboard score | NOT YET MEASURED |

No hypothetical score appears anywhere in this paper. Training-set accuracy
is never substituted for leaderboard accuracy, and no training headline
number appears in the results sections.

## 3. Universality

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

### 3.5 Three levels of universality

- U1, architectural portability: the failure, construct, execute, verify loop
  is independent of grids.
- U2, representational portability: a new domain can supply its own typed
  entities, relations, operators and verifier while preserving the control
  architecture.
- U3, empirical cross-domain transfer: the same implementation or learned
  construction strategy succeeds in a non-ARC domain.

Current evidence supports U1 and, by construction, parts of U2. U3 is not
claimed. No cross-domain experiment has been run, and none is reported here.

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
| representational portability, U2 | supported by construction, not yet exercised |
| cross-domain empirical transfer, U3 | not demonstrated, no experiment run |
| transfer to biology, protein design or omics | not demonstrated, prospective only |

## 4. Theory: the question being asked

Ordinary learning adapts parameters:

    theta -> theta'

Ordinary fixed-language reasoning searches inside a language:

    search over p in K

CORA asks a different question:

    search over p in K -> failure -> construct e -> K' = K union {e}
      -> reason again

The theoretical hypothesis is that some reasoning failures are not merely
incorrect hypotheses but reflect inadequacy of the current executable
language, and that a capable reasoner should therefore be able to reason
about the limitations of its own language.

CORA has not proven this hypothesis. The work reported here builds and
repairs the machinery needed to test it.

## 5. Progress: the distinction this work adds

Search improvement, hypothesis-selection improvement and capability growth
are three different things, and ARC research frequently conflates them.

Two of our own prior measurements make the point empirically. In one, every
compared policy solved the same 188 of 256 targets: the learned system
searched more cheaply and changed some predictions while bounded reach stayed
identical. In another, an earlier task-time comparison turned out to be
non-additive, so activation counts could not be read as evidence of
capability; only a causal, matched comparison could settle it.

The prospective experiment that follows from this is fixed K against
failure-driven K plus e, under matched compute. It is future work and is not
presented as a completed contribution.

Four distinctions are used throughout:

- a new program is not a new capability;
- a new composition is not automatically new semantics;
- a macro is not semantic novelty;
- a score gain is not invention.

## 6. Two experimental timescales

CORA tests one idea at two timescales. They share the idea and share no
evidence. Results from one are never merged into the other.

                          CORA
                            |
            +---------------+---------------+
            |                               |
      CORA-SCIENCE                      CORA-TTI
      Step B, durable                   task-time, ephemeral
            |                               |
    certified historical failures       a new task
            |                               |
    62 failure clusters                 K fails
            |                               |
    4,784 frozen candidates             observe the real frontier  [repaired]
            |                               |
    candidate installation              typed failure graph        [measured]
            |                               |
    resolution testing                  constructive AST proposal  [specified only]
            |                               |
    frozen capability-growth gate       compile and install e      [specified only]
            |                               |
    bounded semantic separation         reason again, verify
            |                               |
    transfer                            predict
            |                               |
    possible persistent promotion       reset to K

Status marks: repaired and measured components are implemented and have
numbers in section 9. Components marked specified only are not implemented
and are not part of any submitted system.

### 6.1 Durable capability growth: CORA-SCIENCE Step B

Step B is not the competition solver. It is an independent experiment asking
whether a candidate capability deserves to become durable knowledge.

    certified historical failures -> 62 failure clusters
      -> 4,784 frozen candidate extensions -> candidate installation
      -> resolution testing -> frozen capability-growth gate
      -> bounded semantic separation -> transfer -> possible promotion

Frozen candidate inventory: 816 K2 semantic-production candidates and 3,968
K1 repair candidates.

Latest recorded checkpoint, not a live claim and not an inspection of
semantics: K2 proposal phase at 350 of 497 units, zero recorded errors, no
freeze marker and no final output hash.

Step B remains ongoing and has no interpretable semantic verdict at the time
of this manuscript revision. No Step-B candidate or outcome is used by the
ARC delivery sprint.

### 6.2 Task-time language adaptation: CORA-TTI

CORA-TTI asks whether a temporary executable capability can be constructed
during inference quickly enough to improve ARC performance.

    K -> ordinary reasoning -> failure -> typed failure graph
      -> constructive AST proposal -> ephemeral K union {e}
      -> ordinary re-induction -> verification -> prediction -> reset to K

Step B produces a durable extension. CORA-TTI produces an ephemeral,
task-local extension that is discarded after the task.

## 7. Implementation status, corrected

Implemented and tested: typed failure graph infrastructure; the constructive
grammar and vocabulary; AST canonicalization; occurrence-scoped fitting; TTI
orchestration; a Stage-A known-name proposal network; exact execution; the
leave-one-out verifier; an ablation ledger; task-local install and reset
infrastructure; scheduler and diversity; a Kaggle emulator.

Two corrections to earlier internal descriptions, recorded because they
change what may be claimed.

`mdl_fallback_proposer` is not a MetaConstructor. It ranks existing catalogue
production names by cost and name and returns the top few. That is
known-operator reconstruction.

`constructive_vocabulary` defines what a legal constructive AST is. It does
not decide which new AST should be constructed from a failed trace, and it is
not a proposal mechanism.

Not implemented: the grammar-constrained unseen-AST proposer, and the
ConstructiveExtensionCompiler. Neither is marked complete anywhere in this
paper or in any figure, and neither is part of the submitted inference
system.

## 8. Diagnostic experiment: the failure-frontier audit

Twelve development tasks were fixed by a rule committed before any result was
computed: the first twelve task identifiers in ascending order. Only the
existing failure path was run. Nothing was proposed, constructed, installed
or scored, and no test outputs were read.

Original observed channel:

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
from a single root, `PaintEach`, the only primitive in that eleven-primitive
environment returning a grid.

Conclusion: the original candidate-associated evidence was effectively
invariant to the ARC task. This explains why a prior shuffled-evidence
control performed similarly to real associated evidence. There was almost no
task-specific information to destroy.

## 9. Root cause and repair

### 9.1 Root cause

The thing doing the real ARC reasoning was not the thing being observed.

The trace observer was attached to the restricted eleven-primitive blind
runtime. The full object reasoner had no equivalent trace path, so the
failure graph never exposed the semantic frontier of the deployed reasoner.
The old null result is therefore not evidence that failure-conditioned
construction is useless.

### 9.2 Full-engine observation repair

The isolated delivery copy of the real object reasoner was instrumented to
expose its candidate lifecycle: typed, then slot fitting that fails or
succeeds, then a program that executes non-exactly or exactly. The live
research engine running Step B was not modified, verified afterwards by
confirming that the shared failure-graph code and the research engine
directories were unchanged.

One engine property mattered: the reasoner assembles a program only when every
object group is explained, so its genuine near misses are the partial
programs it builds at the failure branch and then discards.

This is instrumentation, not a new solver. Noninterference fixtures require
that the result with observation equals the result without observation,
compared on exactness, strategy, training accuracy, leave-one-out score, best
accuracy, failure stage, pixel fit and both serialized programs. Those
fixtures passed.

### 9.3 Repaired frontier result

Same twelve tasks, same budget, same frontier cap:

| quantity | original | repaired |
|---|---|---|
| candidate events | 64,610 | 494 |
| identical census across unrelated tasks | yes | no |
| distinct frontier operator families | 1 | 12 |
| parameter-fitting successes | 0 | 62 |
| executed-but-non-exact candidates | 0 | 36 |
| exact candidates | 0 | 7 |

Observed operator families included grow, translate, copy, copy_part,
composite, paint and keep, in place of one invariant operator. Three of the
twelve tasks emit nothing, because the engine gives up before rule induction;
that is a property of the engine on those tasks, not a trace defect.

### 9.4 Candidate-executor compatibility

The repaired producer recorded fitted, executable object programs, but the
failure-graph consumer still evaluated every candidate with the blind-runtime
evaluator, which cannot execute that representation. Every value signature
degraded to undefined, so the evidence existed at the producer and did not
reach the graph. At that point the channel was classified PARTIAL.

The compatibility repair adds one optional evaluator parameter to the graph
builder, defaulting to the previous behaviour, so the builder asks which
executor owns a candidate rather than assuming every candidate belongs to the
old runtime. The adapter supplies the engine's own renderer. It changes only
how an already-observed candidate is executed for diagnostic evidence, and
changes nothing about search, candidate generation, ordering, fitting,
grammar, verifier, acceptance, budgets, Step B or the research tree. It is a
compatibility seam inside CORA-TTI, not another architecture, another solver,
another language or semantic invention.

Measured, same twelve tasks, threshold fixed in advance:

| quantity | before | after |
|---|---|---|
| defined value signatures in the graph | 0 | 18 |
| tasks with at least two frontier terms | 9 of 12 | 9 of 12 |
| tasks with defined candidate-associated evidence | 0 of 12 | 8 of 12 |
| tasks meeting both preregistered conditions | 0 of 12 | 8 of 12 |

The preregistered diagnostic threshold was at least eight of twelve on both
conditions jointly, so the repaired channel is classified INFORMATIVE. The
verdict was identical across three independent runs.

Three cautions belong with that classification. It sits exactly at the
threshold rather than comfortably above it. The qualifying eight tasks are
the same eight the producer-side probe had already identified, so the repair
transported existing evidence rather than creating new evidence. And this is
a classification of a diagnostic channel only. It is not a capability result,
and nothing about construction, reach or score follows from it.

## 10. Completeness: the submitted system end to end

The submitted ARC-AGI-2 inference system, as it stands, is:

1. input demonstrations are read from the challenge JSON;
2. perception segments each grid into objects under several segmentation
   variants;
3. ordinary induction runs three layers, building correspondences, selectors
   and parameterized actions;
4. failure detection records the stage at which induction gave up;
5. failure representation builds the typed failure graph from the observed
   candidate lifecycle;
6. candidate generation assembles programs from induced rules;
7. parameter fitting fits typed parameter expressions per object group;
8. exact execution renders a program on every demonstration;
9. leave-one-out verification re-runs the entire learning procedure from all
   demonstrations but one and requires it to re-derive a program that solves
   the held-out example, for every fold;
10. output selection ranks certified programs;
11. the two-attempt policy emits a certified attempt one and a complementary
    uncertified attempt two;
12. a global time-budget governor rescales per-task budgets against remaining
    wall clock;
13. the submission writer emits `submission.json` covering every task id and
    every test-output position;
14. a failure fallback guarantees two syntactically valid attempts for every
    task, so no task id is ever missing.

Steps 5 and the observation repair are research instrumentation. The
constructive AST proposer and the extension compiler are absent from the
notebook and are labelled ongoing research throughout. If they remain absent
at code freeze they stay labelled that way, and no part of the leaderboard
result may be attributed to them.

## 11. ARC-AGI-2 submission architecture

The notebook runs inside twelve hours on CPU or GPU with no internet, and
emits `submission.json` containing every task id, every test-output position,
and both attempts.

Attempt one carries the strongest evidence-supported output under the frozen
final policy. Attempt two is chosen to maximize genuine complementary
probability of correctness rather than to be merely syntactically different.

Reported for the final run: pass@1, pass@2, attempt-two rescue count,
runtime, task failures and resource exhaustion. All are currently unmeasured.

## 12. Claim ladder

- L1, generation: a candidate or new AST was produced.
- L2, operational language extension: adding the extension changes bounded
  search reach.
- L3, bounded semantic expressivity extension: under declared comparison
  bounds, the prior language cannot reproduce the extension's behaviour.
- L4, bounded semantic invention: L3 together with causal new reach and
  independent transfer.

## 13. Strong causal witness

All six legs are required before anything is called a strong
capability-growth witness:

- B: the baseline language fails;
- P: the extension is produced;
- U: the winning program uses it;
- L: full adaptive leave-one-out passes;
- T: the final output is exactly correct;
- A: removing the extension destroys the gain.

The comparison must be genuinely additive, with matched solver conditions and
resource accounting.

## 14. Results

### Table A: current evidence

| line of evidence | result |
|---|---|
| search and prior transfer | transfer observed; no reach gain |
| selection transfer | observed; no reach gain |
| learned-prior replication | not robustly replicated |
| bounded reach across policies | identical, 188 of 256 targets |
| previous task-time comparison | non-additive, infrastructure evidence only |
| original frontier audit | EMPTY_OR_UNUSABLE, task-invariant census |
| repaired frontier audit | INFORMATIVE, 8 of 12, stable across 3 runs |
| Step-B state | ongoing, K2 at 350 of 497 recorded, no verdict |

### Table B: final ARC submission results

| quantity | value |
|---|---|
| pass@1 | NOT YET MEASURED |
| pass@2 | NOT YET MEASURED |
| attempt-two rescues | NOT YET MEASURED |
| construction activations | NOT YET MEASURED |
| constructive reach gains | NOT YET MEASURED |
| semantic-extension witnesses | NOT YET MEASURED |
| transferred witnesses | NOT YET MEASURED |
| tasks harmed | NOT YET MEASURED |
| runtime | NOT YET MEASURED |
| timeouts and resource exhaustion | NOT YET MEASURED |

Unknown quantities are never written as zero.

## 15. Preserved negative results

- A learned-prior study did not robustly beat concrete memory, and every
  compared policy had the same bounded reach, so no reach witness existed.
- An earlier task-time comparison was not additive and is infrastructure
  evidence only.
- The first proposal network performed known-name reconstruction.
- The first constructive census admitted nothing.
- The corrected census admitted thirteen supplied candidate structures, which
  are not thirteen autonomous inventions.
- The original failure channel carried no task-conditioned evidence.
- A five-task rehearsal of the previous library version was engineering only:
  packaging and schema worked, the governor bound but overran, the previous
  version solved none of the five, and some failures reached the
  leave-one-out or matching stages. Relational parameter fitting was
  provisionally selected after that diagnostic and is no longer the primary
  scientific treatment; it may return later as an inner fitter.

## 16. Novelty and related work

CORA is not claimed to be the first program-library learner, the first
system to invent operators, the first adaptive symbolic solver or the first
self-extending system. No precedence wording is used without a current
primary-source check.

The novelty case is the conjunction: reasoning failure, to mechanistic
failure evidence, to an executable candidate extension, to an additive
comparison of the language with and without it, to adaptive leave-one-out, to
causal removal, to bounded semantic separation, to independent transfer, to
promotion controlled by an immutable verifier.

Related work to be discussed and distinguished: DreamCoder, LILO, predicate
invention and POPPI, AlphaEvolve, program synthesis and library learning, and
relevant non-LLM ARC methods. This section is the bibliography stub; no
formal bibliography file exists yet.

## 17. Limitations

- The public ARC score may remain low, and it is not yet measured.
- Verification has shown poor off-distribution calibration in previous
  measurements: 40 of 42 on training against 0 of 11 on the evaluation
  development split.
- The repaired failure evidence has not yet produced any autonomous
  unseen-AST capability.
- The constructive AST proposer is unfinished.
- The extension compiler is unfinished.
- Step B has no verdict.
- The informative classification rests on twelve tasks and sits exactly at
  its threshold.
- Three of those twelve tasks emit no candidates at all, and no repair of
  this kind can change that.
- Bounded semantic separation does not establish universal non-definability.
- ARC results alone do not establish general intelligence.

## 18. Cover figure specification

One figure. Left panel: fixed K reasoning reaching failure. Centre panel: the
semantic failure frontier and the typed failure graph. Right panel: temporary
K plus e reasoning again. Below, two paths: Step B leading to durable
promotion, and CORA-TTI leading to a task-local reset.

Every component carries a visual status label: measured, ongoing, or
specified only. Unfinished components must not appear complete. Specification
kept in `kaggle/COVER_IMAGE_SPEC.md`.

## 19. Release and open-source checklist

Prize eligibility requires appropriate open sourcing of the solution
artifacts. Before any public release: remove protected research artifacts,
remove private data, remove all Step-B sealed material, verify licenses,
verify that no secret tokens or private paths remain, and verify notebook
dependencies resolve with the internet disabled. Nothing is published
automatically.

## Out of scope

Capability-growth gate internals, the parallel verified-capability scaling
project, and biological applications.
