# CORA: Separating Search, Hypothesis Selection, and Capability Growth in ARC-AGI-2

Authoritative technical manuscript for the ARC Prize 2026 Paper Track.
Updated 2026-10-13: the October Kaggle submissions (section 6.1), a separate
neural competition track that is not CORA (section 6.4), the pre-registered
negative result on neural view guidance (section 8.18), the leaderboard-method
survey (section 10) and new limitations (section 11). Updated 2026-10-12: results
through v1.9 (section 8.14), the real-task
reach v1 measurement (section 8.16), the adaptive leave-one-out diagnosis
with synthetic negative controls (section 8.17), the real ARC pilot status
(section 8.15) and the research trajectory (Appendix C; full map in
`docs/PROJECT_MAP.md`). No LaTeX source, compiled PDF or BibTeX file exists in
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
capability. Its base reasoner solves 185 of the 1,000 ARC-AGI-2 training
tasks with leave-one-out certificates and none of the 120 public evaluation
tasks.

A diagnostic audit found that the original test-time failure representation
observed a restricted proxy search rather than the deployed reasoner.
Instrumenting the deployed reasoner, without changing its search, exposed
task-dependent failure frontiers with executable near misses.

A chain of preregistered experiments, each frozen and reviewed before its
data existed, then asked what that failure evidence is good for. Passive
descriptions of the failure did not improve the choice between candidate
extensions beyond the demonstrations (288 independent test groups). Treating
the failure as an intervention target did: a fixed rule over each candidate's
effect on the failed reasoner, with ties passed to a demonstration selector,
chose correctly on 0.641 of ambiguous queries against 0.580 (136 groups,
p 3.8e-5). A compiler then installed a selected extension into the same
engine (6 of 6 synthetic tasks). A proposer with no access to the answer
built the extension from the engine's own failure frontier and beat
transplanted and blind failure evidence on every discordant task, but
completed only 11 of 30 end-to-end witnesses. Tracing every rejection inside
the engine found one cause, two native heuristics re-applied inside the
engine's own leave-one-out; one generic repair raised complete witnesses on
30 new synthetic tasks from 12 to 27, with 237 of 239 certified outputs
correct.

These results are synthetic. The repaired engine accepts any installed
extension that verifies, wrong ones included, so on real tasks correctness
has to come from selection, held-out checks and abstention. No real ARC task
has yet been solved by a constructed extension. On 60 real development tasks
a growth-relation proposer, built from the instances the engine memorized
instead of generalizing, installed extensions on 4 tasks (none before), and
the unchanged engine accepted and used one; none survived adaptive
leave-one-out (0 of 14 folds). Forensic analysis traced those failures to the
native engine's representation admission: on some two-demonstration subsets,
finer segmentation views become eligible and fill a fixed four-view search
cap, cutting the view that holds the correct program. The obvious repair,
forcing a view to be searched first, was harmful on synthetic negative
controls (on 24 tasks it gained none and harmed five) and was not run.
A 120-task prospective pilot on real training tasks is frozen and has not
been run. Durable semantic invention
remains under independent evaluation in the frozen Step-B experiment, which
has no verdict. We do not claim that CORA has demonstrated semantic invention
or self-improvement.

## Contributions

1. A formal and empirical separation of search improvement, hypothesis
   selection and capability growth.
2. A non-LLM ARC reasoning system with immutable leave-one-out verification
   (185 of 1,000 training tasks certified).
3. A frozen causal-witness protocol (B/P/U/L/T/A) for capability growth.
4. An architecture for failure-conditioned task-local language adaptation,
   implemented end to end on a synthetic constructive grammar: proposal from
   the reasoner's own failure, compilation into the same reasoner, and
   re-induction under its unchanged acceptance gate.
5. An empirical diagnosis showing that an earlier failure representation
   observed the wrong reasoning process, and its repair.
6. Evidence that failure is useful as an intervention target rather than as a
   passive description (sections 8.10 and 8.11).
7. A mechanistic account of why a correct extension can fail the reasoner's
   own leave-one-out, with one generic repair tested prospectively (section
   8.14).
8. Negative results showing why score gains, search gains, passive failure
   descriptors and known-operator reconstruction are insufficient evidence of
   capability growth.
9. On real development tasks: a constructed extension that the unchanged
   engine accepted and used, and a predicate-level account of why it failed
   adaptive leave-one-out (a representation-admission defect in the native
   search, not a missing capability), with synthetic negative controls that
   rejected the obvious repair before it was run (sections 8.16 and 8.17).

## 1. Introduction

### 1.1 Competition constraints this paper is written against

| item | value |
|---|---|
| ARC-AGI-2 entry deadline | 2026-10-26, 23:59 UTC |
| final prediction and code submission | 2026-11-02, 23:59 UTC |
| Paper Track final deadline | 2026-11-08 (arcprize.org, read 2026-10-07; an earlier reading gave 2026-11-09, 23:59 UTC) |
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

The constructive proposer (section 8.13), the ConstructiveExtensionCompiler
(section 8.12) and the installed-extension repair K*-4 (section 8.14) are
implemented and tested on the synthetic constructive grammar only; none has
run on a real ARC task. The growth-relation proposer of section 8.16 has run
on real training-development tasks, once and for development only. The
failure representation and its repair are diagnostic instrumentation. None of these contribute to the leaderboard
result, and the paper attributes nothing to them. Binding requirement: the
manuscript method, the writeup method and the public notebook method are the
same method for every claim about the submitted solver.

## 4. Failure-Conditioned Language Adaptation

    K -> ordinary reasoning -> failure -> typed failure graph
      -> constructive AST proposal  [implemented, synthetic grammar: 8.13]
      -> ephemeral K union {e}      [implemented, synthetic grammar: 8.12, 8.14]
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

Implemented since 2026-10-05, on the synthetic constructive grammar only: the
no-oracle extension proposer (section 8.13), the extension compiler (section
8.12) and the installed-extension re-induction repair (section 8.14). None
has run on a real ARC task and none is part of the submitted solver. Since
2026-10-11 a separate growth-relation proposer (section 8.16) has run on the
60 real training-development tasks, for development only. It is not part of
the submitted solver either.

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
freeze marker, no final output hash. A later progress report (2026-10-02)
gave 389 of 497 units and zero errors.

Step B remains ongoing and has no interpretable semantic verdict at the time
of this manuscript revision. No Step-B candidate or outcome enters the
competition solver.

## 6. Experiments: Accuracy and Controlled Comparison

### 6.1 The submitted configuration

| field | value |
|---|---|
| ARC-AGI-2 submission id | 57144804: NATIVE_BASELINE native_v1, submitted 2026-10-13T13:17Z. Status PENDING at 2026-10-13T17:00Z. Replaces nothing; the July 2026 submission 54617562, an older v10/v11 engine, scored 0.00 |
| notebook | `chimdiwalter/cora-native-v23-arc-agi-2-october-baseline`, version 1 (private; to be made public with the writeup) |
| notebook and configuration identity | dataset `chimdiwalter/arc-native-baseline-v1`, version 1. Tarball sha256 4b320ba2..., 273 files, byte-identical on Kaggle. Solver tree d7856871...; notebook.py 647594be...; the five sealed chain flags; library.json cdacd018...; learned_verbs.json b1f07ba5... (`records/KAGGLE_NATIVE_V1_DEPLOYMENT_LOG_20261012.md`) |
| leaderboard score, public | PENDING (expected at or near 0: the frozen engine scores 0 of 120 on the public evaluation set) |
| leaderboard score, private | revealed after the competition |
| pass@1 | NOT MEASURABLE before scoring (the hidden answers are Kaggle's) |
| pass@2 | the leaderboard score is pass@2 by definition; PENDING |
| attempt-2 rescues | NOT MEASURABLE from the leaderboard aggregate |
| task outputs scored | 240 hidden tasks; the public board scores a representative sample |
| runtime | committed run on the visible stand-in (240 public ARC-AGI-2 *training* tasks): 14,512 s (4.03 h) on 4 CPUs, inside the 12 h limit. The hidden re-run's runtime is obfuscated by Kaggle |
| timeout rate | committed run: the harness completed, and the hard limit was not reached |
| failed-task rate | committed run (training stand-in, no answers read): 126 of 240 tasks with no candidate; 139 real attempt_1, 45 real attempt_2, 120 fallback of 259 positions. Behaviour on training tasks, not a score |

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

### 6.4 A separate neural competition entry, which is not CORA

To obtain a stronger competition entry before 2 November, the public NVARC
pipeline is reproduced as **NEURAL_TTT_BASELINE**. It is never presented
as CORA, as capability invention, or as evidence for any claim in sections
3 to 8. NVARC is the 2025 ARC-AGI-2 winner: 24.03 private.

- **What it is.** NVARC's ARC-specialized Qwen3-4B checkpoint
  (`sorokin/qwen3_4b_grids15_sft139`, Apache-2.0), with per-task LoRA
  test-time training, augmentation, depth-first-search decoding and
  augmentation-consistency selection. It runs in the public notebook
  `sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue` with
  compatibility-only patches: 2026 data and model paths, logging, schema
  repair, a manifest. Upstream's model, training, decoding, selection and
  time guards are unchanged.
- **Deployment checks.** Each was measured on Kaggle L4x4:
  - compatibility smoke test: 4x L4, LoRA TTT 89-344 s per task, peak memory
    9.4-12.5 GB of 22 GB;
  - probe of multi-output and 30x30 tasks: valid, at 15-18 GB;
  - 30x30 tasks approach the 20-min per-task cap;
  - a full 240-task committed run started 2026-10-13T16:23Z
    (`records/KAGGLE_NEURAL_V1_LOG_20261013.md`).
- **Coverage is audited separately from validity.** Upstream fills
  unprocessed outputs with `[[0]]`, so a valid file is not coverage
  (`kaggle/neural_v1/audit_run.py`).
- **Contamination.** NVARC's own code builds its validation set from the
  ARC-AGI-2 evaluation files, test outputs included, and ranks checkpoints by
  validation loss. Its training data includes ARC-AGI-2 training tasks
  (re-verified at NVARC HEAD 846d0198). The model is competition-eligible,
  but **no generalization claim may rest on any public ARC-AGI-2 split.**
  Only fresh synthetic tasks are clean for both NVARC and CORA (the C2
  corpus, `records/CORA_NEURAL_CANDIDATE_EVIDENCE_PLAN_20261013.md`).
- **Licensing.** The rules (section 6b) deem publicly shared competition
  notebook code licensed under an OSI-approved licence. Every runtime
  dependency is OSI-licensed (section 6c). Attribution to Sorokin and Puget
  is kept.
- **Integrity.** The first smoke run's logging cell hashed the
  competition's evaluation files. It parsed nothing and used nothing, but it
  opened them. It is recorded as a protocol violation and excluded from all
  evidence. Every later run is confirmed not to open them
  (`records/INTEGRITY_INCIDENT_20261013_EVAL_HASH.md`).
- **How it relates to CORA.** In this paper the neural system is a possible
  *source of untrusted hypotheses*: candidate outputs that CORA must turn
  into its own certified programs, or reject. Whether that helps is a
  separate pre-registered experiment (section 11; the C2 plan). It is not a
  result.

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

### 3.11 A portable controller (BIOLOGICAL APPLICATION: UNTESTED)

The hypothesis is that the controller transfers, not the ARC operators. The
controller is the sequence: observe the failure, classify the limitation,
choose the justified adaptation, construct only if expressivity is missing,
verify independently, test causally, promote under a separate protocol. Its
evidence and certificate interfaces would transfer with it.

A second domain is proposed: biological perturbation response. It would need:
- typed adapters for cell states, perturbations and donors;
- failure diagnosis on training data only;
- evaluation on held-out perturbations and cell states;
- confounder controls.

It would give predictive validation only. No biological data or result
exists in this work, and no biological repository was accessed.

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

## 8.6 Measured: failure conditioning is not established

The v1.2 corpus passed its frozen gate, which licensed fitting the scorer. The
fit ran under a preregistration sealed beforehand and amended only before any
score existed. The result is negative, and it is specific.

Two gates were fixed in advance. Real associated failure evidence had to beat
another episode's evidence, and it had to beat its own evidence with the
candidate-associated features neutralized. The first passes clearly. The
second fails.

| condition | mean per-token target log-likelihood |
|---|---|
| real associated | -1.248 |
| shuffled | -1.445 |
| irrelevant | -1.442 |
| aggregate only | -1.236 |
| none | -1.299 |

Evidence identity plainly matters. Real evidence beats another episode's by
0.197 nats per token, on 23 of 32 paired episodes, and the top proposal
changes on 30 of 32 episodes when evidence is swapped. With neutral evidence
the model collapses to one proposal at zero entropy; with real evidence it
produces 22 distinct top proposals across 32 episodes.

What fails is narrower and more interesting. Removing the ten
candidate-associated features, and keeping only the demonstration statistics,
does not hurt and slightly helps. The conditioning that works is
demonstration-level. The typed failure frontier, which the observation repair
and the evaluator-compatibility repair existed to deliver, adds nothing
measurable to constructive selection.

No target was recovered in any condition. Exact-at-five is zero across all
five, which an adversarial review predicted before the run by measuring that
a probe knowing the target's token multiset recovers only 2 of 32 under this
decoder. The gate metric was changed to target log-likelihood in advance for
that reason, which is why the experiment could return a signal at all rather
than five zeros.

This does not show that failure-conditioned construction cannot work. It shows
that on this corpus, with this model, the candidate-associated channel does
not improve which program is proposed. The extension compiler stays blocked,
because a failed discrimination result does not license it.

## 8.7 Diagnosis: the corpus, not the model

A preregistered diagnostic separated three explanations for the negative
above, using only the 180 training episodes, five deterministic folds, and a
criterion fixed before any outcome.

Model capacity is not the explanation. A bounded nonlinear model with one
hidden layer does not rescue the candidate features: adding them changes
held-out target log-likelihood by -0.016, positive on one fold of five.

Compression is not the explanation either, with one recorded caveat. All 180
episodes carry distinct candidate-feature vectors, so the summary is not
merging different graphs. A richer descriptor built directly from the stored
failure graph performs worse than demonstration statistics under both models.
That test is confounded by carrying 42 features against 144 training episodes
per fold, and the confound is reported rather than resolved.

What the candidate features do is actively harm prediction. Adding them
lowers held-out likelihood under both model classes on nearly every fold, and
replacing each episode's candidate evidence with that of its nearest
neighbour by demonstration evidence improves prediction rather than degrading
it.

The obvious next reading, that demonstration statistics already determine the
target, is not supported. Predicting the target from them alone gives 0.383
accuracy on the first partition token against a majority baseline of 0.411,
and 0.183 on the first feature token against 0.161. They do not determine the
target either.

The accurate statement is narrower. On this corpus, at this readout, no
evidence group recovers the target. The corpus does contain the cases the
frontier exists to disambiguate: of the closest quartile of episode pairs by
demonstration distance, 45 of 45 have different targets. The frontier does not
distinguish them.

So the discrimination test failed for a reason located in the corpus rather
than in the scorer. That does not show a reasoning frontier can never inform
construction. It shows this corpus cannot test the question.

## 8.8 A contrastive corpus for failure-target identifiability, and its negative result

v1.2 generated diverse valid supervision, 215 admitted episodes with 215
distinct targets passing all eleven corpus gates, but its failure frontiers did
not identify the associated constructive target under bounded diagnostic
readouts.

A v1.3 corpus protocol was therefore preregistered and hashed before anything
was generated under it. It is a data identifiability repair rather than an
architecture revision: the grammar, the baseline, the fitter, the deployed
reasoner, the observer and the verifier are all unchanged.

Its design follows from the diagnosis. Episodes are generated in groups of two
targets differing in exactly one grammar position, with four independent
replicates per target, which supplies the within-target null that v1.2's one
episode per target could not. Demonstrations within a group are matched to a
fixed distance. The corpus gate is nonlearned: a within-group nearest-neighbour
test on a target-independent frontier descriptor against an exact chance level
of three sevenths. No group is filtered on any property of its frontier, since
selecting separable groups would manufacture the correlation under test. One
contrast type, adding a select, also changes the structural family, so the
primary gate must also hold with that type excluded.

Every constant was committed before the stage that uses it: the descriptor
normalisation from a separate 200-episode calibration set, then the admission
rate from a 40-slot pilot, which set the full run at its cap of 1,200 group
slots.

The full run admitted 21 groups: 14 feature contrasts, 7 select contrasts and
no partition contrasts, giving 168 episodes over 41 distinct targets. On them,
the nearest neighbour in frontier space is the same-target replicate 47.0
percent of the time against a chance level of 42.9 percent, one-sided
p = 0.16. Excluding the select contrasts gives 47.3 percent, p = 0.19. The
median separation between between-target and within-target frontier distance
is 0.025. Seven of the ten preregistered gates fail, including both
identifiability gates. Two independent runs of the sealed auditor produce
byte-identical reports.

The sample is smaller than planned, 168 instances against about 480, so the
result has to be read with its power. The exact one-sided 95 percent upper
bound on the hit rate is 0.54. The experiment was sized to detect 0.55, and an
effect of that size is excluded. A smaller effect is not. The supportable
statement is that under a demonstration-matched, replicated contrastive
design, the deployed reasoner's failure frontier does not measurably identify
which of two minimally different constructive targets produced it.

Two designs with different confounds now agree. A plausible reading, which is
interpretation rather than measurement, is a vocabulary mismatch: the frontier
records where segmentation, correspondence, selection and parameter fitting
broke, while the target is written in partitions, selects and key features,
and a minimal change in the second does not move the first systematically.
Under the programme's own ordering, no scorer is fitted to such a corpus and
no compiler is built on it.

## 8.9 Where target information lives: a counterfactual-twin localization

v1.3 failed to establish target identifiability, including on the cleaner
non-SELECT contrasts. That left two explanations with different repairs:
either the reasoner's trajectory reacts to the semantic difference and the
failure graph loses it, or the trajectory itself does not react, in which
case no encoder or scorer could recover it.

v1.4 separates them without training anything. Pairs of feature contrasts
are shown the same input grids, so the two demonstration sets differ only
through the target transformation, with four such twin replicates per group.
The reasoner's ordered candidate trajectory is kept, and each stage, from
candidate formation through selector induction, parameter fitting,
executable candidates and mismatch to the failure graph and its 42-field
summary, is tested with a nonlearned nearest-neighbour statistic. Because
each query's own twin shares its input, it is excluded, and the exact chance
level becomes one half. Target A is also run a second time on the same
input, to separate a reaction to the semantic change from timing noise in a
deadline-bound search.

The frozen run produced 42 unique groups, 336 episodes and 168 reruns. A
first audit was blocked by a preregistered integrity rule after one target
pair was admitted twice; the fix and the continuation were frozen before any
statistic existed.

The existing 42-field summary identifies which of the two targets produced a
failure at 0.565 against 0.5 (190 of 336, binomial p = 0.0094, exact
randomization p = 0.0017). The reasoner's own candidate formation, selector
induction and parameter fitting identify the target at 0.57 to 0.59, and at
these stages the twin's trajectory differs from the original far more often
than a same-input rerun does. The executable-candidate and mismatch stages
carry little information either way, because within the fixed budget the
engine forms few executable candidates.

So the v1.3 negative was at least partly instance noise: once scene
variation is balanced, the current failure summary does carry target
information, and the search does react to the semantic change. Two limits
come with that. The demonstrations alone identify the target more strongly
(0.664) than any reasoning stage, and the signal is established only under
shared inputs, not under the input variation a real selector would face.
Both bind the next experiment, a preregistered failure-conditioned selection
test that must beat a demonstration-only baseline. Nothing about selection,
construction or score is claimed here.

## 8.10 Failure-conditioned selection under input variation, and its negative result

v1.5 asks the question the constructive loop depends on. Given two legal
candidate rules that differ in one key feature, does the failure evidence of
the query improve the choice of the correct one beyond what a summary of the
demonstrations already gives, on new target pairs with ordinary, independently
rendered inputs?

The selector is the existing log-linear scorer, unchanged: it compares the
logits of the two candidate tokens at the state where they differ. It is
fitted once on the 42 v1.4 twin groups and tested on 288 new groups, the size
fixed in advance for 90.9 percent power. Three conditions are compared:
- demonstrations alone (D);
- demonstrations plus the query's own failure evidence (D+F);
- demonstrations plus the failure evidence of a matched donor query
  (D+F shuffled).

Every threshold, the decision ladder and a supplementary dependence analysis
were frozen before any score. A machine reboot interrupted the generator
once; it resumed from its saved records.

Results on the 288 test groups:
- Demonstrations alone choose correctly at 0.591.
- Adding the failure evidence gives 0.585. The increment is -0.006, with a
  95 percent interval of -0.026 to +0.014.
- Against the matched shuffle the increment is +0.005, with a 95 percent
  upper bound of 0.025.
- Both comparisons fail decisively: they are not significant, and their upper
  bounds lie below the preregistered minimum useful increment of 0.05.

The frozen classification is that the failure association is not causal for
selection. The same holds within the twin training groups under
cross-validation, and for the two explanatory channels: the search-trajectory
counts, and the summary without its value signatures.

The failure evidence is not empty. On its own it chooses correctly at 0.556,
and the evidence each query actually received fits better in likelihood than
a donor's. But it is largely predictable from the demonstrations (the field
correlation with a matched donor is 0.87). Adding it makes the scorer more
confident without making it more accurate, and it hurts on candidate pairs
absent from training.

On 56 percent of the test queries the wrong candidate does not reproduce the
demonstrations, so plain verification already decides them. On the remaining
44 percent every condition is near 0.54.

These negatives are conditional on this selector and this training resource.
The compiler that would install a constructed rule was licensed only by a
pass, so it is not built on this result. One bounded, preregistered repair
remains, aimed at locating whichever failure channel, if any, carries the
constructive decision.

## 8.11 Failure as an intervention target: candidate-conditioned failure response

[METHOD WRITTEN 2026-10-02; RESULT SEALED 2026-10-05]

v1.5 described the failure and asked whether the description helps. The
bounded repair changes the question. It exposes each candidate extension to
the failed reasoner, temporarily, and measures what happens to the failure.

The reasoner is the constructive domain's frozen base search K. On every
admitted episode K fails by construction. For a candidate e, the probe runs
K + {e}: K's results are shared and unchanged, e is the only added
production, and it is fitted by the same fitter the gate uses. The probe
then performs the smallest legal internal counterfactual: it removes one
demonstration, re-derives e from the rest, and renders the removed input.
Both candidates see the identical probes. The comparison value is the
demonstration-visible held-out output; these episodes contain no hidden
output at all. State is hashed before and after every probe and must be
identical.

Each candidate's response is four numbers: the share of held-out
demonstrations it reproduces after re-derivation, its held-out residual, the
share of re-derivations with no consistent fit, and the size of its induced
table. A pair is represented by the difference of the two responses.

Three arms are compared on the queries that plain verification cannot
settle (both candidates fit every demonstration):
- P0, pure reasoning: a fixed lexicographic rule over the response keys, in
  an order fixed before any response was read, with no fitted number;
- P1, hybrid: the demonstration summary plus the response, through the same
  small conditional logit as v1.5;
- P2, passive: the demonstration summary plus the v1.5 failure descriptor,
  fitted on the same training resource.

A second gated arm, P0 then D, applies the rule first and hands the rule's
ties to the demonstration selector. It was added after the development
evaluation showed that the rule abstains on most pairs, and before any
prospective data existed; because it uses a fitted selector on ties, a pass
by this arm is reported as hybrid.

Two controls separate a candidate's interaction with this failure from
everything else: the response of a matched donor episode (the failure
replaced), and the two candidates' responses exchanged (the identity
destroyed). Transfer is read on candidate pairs held out of training by a
fixed hash rule. Gates, thresholds, the ladder and the sample size are
frozen before the prospective corpus exists; the v1.5 test corpus served as
development data and is excluded from the new corpus by digest.

The prospective corpus has 201 groups and 1,608 queries. Plain
verification decides 951 of them. The remaining 657, in 136 groups, are the
test population, of which 65 groups use candidate pairs absent from the
training resource. Admission ran at a third of the planned rate, so the
test stopped at its slot cap below the 280-group target. The frozen rules
let a pass stand at 72 groups or more.

On the ambiguous queries the demonstration summary chooses correctly at
0.580. The pure rule P0 decides only one ambiguous pair in five, and is
right on 86.5 percent of those (the demonstration summary manages 56.4
percent on the same pairs). With half credit for its abstentions it reaches
0.574, so on its own it does not beat the demonstrations. P0 then D reaches
0.641:
- an increment of 6.1 points over the demonstrations (95 percent interval
  2.9 to 9.3, exact p 3.8e-5);
- 8.2 points on unseen candidate pairs (p 6.1e-5);
- 3.7 points over the same rule fed a matched donor episode's failure
  response (p 0.0069).

Exchanging the two candidates' responses drops it to 0.493. The hybrid
logit P1 (0.597) and the passive v1.5 channel P2 (0.578) do not beat the
demonstrations; the v1.5 negative replicates on new data.

The frozen classification is PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES,
which licenses the compiler. An independent recomputation written before
the outcome reproduces every gate and the class. Its headline is hybrid: a
deterministic intervention rule whose ties fall to the learned
demonstration selector.

The limits are part of the result:
- the test is below its powered size, and the 0.05 floor is met by the
  point estimate, not by the interval;
- the matched-control gate passes at 0.0069 against 0.01, would not survive
  a correction across the three gated arms, and its dependence-aware
  version could not be resolved;
- one structural family supplies most of the ambiguous groups;
- the domain is the synthetic constructive grammar with its single-block
  base search.

This is LEVEL 1 of the claim ladder. It does not claim self-improving
reasoning or invention; those need the B/P/U/L/T/A witness of section 2.3.

## 8.12 Compiling a selected extension into the same reasoner

[METHOD WRITTEN 2026-10-05; RESULT SEALED 2026-10-05]

Section 8.11 licensed a compiler: a generic mechanism that takes one legal
extension from the constructive grammar and makes it an executable
production of the same reasoner, the real ARC engine, without task-specific
code. The extension is still chosen by the oracle pair; this section asks
only whether the engine can use it once it exists.

Reading the engine source showed why it could not before:
- its concept route existed but was never called;
- its slot learner fits only one-block, one-Select schemas;
- its expression phase received no time on exactly the tasks where an
  extension is needed.

The compiler therefore runs the unchanged engine as K*, under three rules
applied identically in every arm:
- the expression phase receives its declared slice;
- shapes the engine does not produce are fitted by the frozen
  occurrence-scoped fitter;
- installed productions are appended to the concept list.

K* changes the baseline: the v23 count is K's, not K*'s. A test shows K*
without an extension never calls the slot learner.

The compiler's contract:
- a closed input schema with no field for a task, label, output or family;
- a typing law from the frozen signatures;
- a canonical serialization whose reload rebuilds the production from its
  body and requires identical bytes;
- a context-scoped installation verified by a state snapshot;
- attribution by name and structure;
- a paired ablation and an adaptive leave-one-out.

One adversarial review found two blocking defects before any acceptance
data existed: the environment the fixtures depend on was not enforced, and
reload could be forged. Both were fixed by erratum and re-frozen.

The acceptance test ran once, on six new synthetic two-block tasks:
**COMPILER_ACCEPTED**.
- In all six, K* + {e} was accepted by the engine's unchanged gate, the
  winner was the compiled production, and the held-out demonstration was
  exact; K* alone was not accepted, and neither was K* at three times the
  budget.
- Attribution had no residue, no disagreement under direct execution and
  no label anomaly.
- Adaptive leave-one-out passed on five of six tasks. On the sixth the
  engine accepted nothing on four of seven six-pair folds.

What this does not show:
- it is an engineering result, not a reasoning claim: the extension came
  from the oracle;
- the leave-one-out folds recompile the same oracle schema, so only one
  held-out pair per task is out of sample;
- necessity holds under K*, not K;
- the witness comparison sets were all empty, so separation from K is shown
  only at the level of the frozen fitter;
- the tasks are synthetic and two-block.

The claim stays LEVEL 1. LEVEL 2 needs an extension produced without the
oracle pair, then compiled and certified through this path.

## 8.13 Proposing the extension from the reasoner's own failure

[METHOD WRITTEN 2026-10-06; RESULT SEALED 2026-10-06]

Section 8.12 compiled an extension chosen by the oracle pair. This section
removes the oracle: the proposer receives only the demonstrations and K's
own failure, never the target schema, a candidate pair, the held-out output,
a task identity or a family label.

The mechanism follows from the frozen semantics. Every block reads the input
grid and later layers overwrite earlier ones, so on a two-layer task every
single K block fails the joint fit. A block that is consistent on its own
cells but covers only part of the change is a partial near-miss; these
near-misses are K's typed failure frontier. The proposer takes them as top
layers, asks for a lower K block that covers the residual consistently
outside the top's cells, verifies the composition on the demonstrations,
removes behavioural duplicates, and selects by the v1.6 probe, then the
frozen demonstration model D, then a declared minimum-description guess.

Controls keep the mechanism and change only the failure evidence: a
transplant of another task's frontier, and a fixed blind order of K's
blocks. One adversarial review found that the first-frozen controls could
not propose at all; an erratum replaced them before any prospective data
existed.

The prospective test ran once on 30 new synthetic tasks:
**FAILURE_SPECIFIC_BUT_NOT_END_TO_END**.
- Failure specificity passed. The failure-conditioned selection predicted
  the held-out pair on 30 of 30 tasks, the transplant on 17 and the blind
  order on 23; every discordant task favoured the failure-conditioned arm
  (13 to 0, p 0.0001; 7 to 0, p 0.008).
- The end-to-end gate failed: 11 of 30 tasks gave a complete witness, 15
  were required. The engine accepted the produced extension, used it and
  reproduced the held-out pair on 25 tasks, and K* at three times the
  budget reproduced none. Leave-one-out with the proposal rebuilt in every
  fold passed on only 11.
- The proposer did not fail in any fold. In 77 of the 81 failed folds it
  rebuilt the same program as on the full task; on 14 tasks the engine
  accepted that program with seven pairs and rejected it on six-pair folds.
  Failures concentrated where
  several verified extensions remained and selection fell back to D or the
  description-length guess.

What this does not show:
- the end-to-end path: too few produced extensions survive the same
  reasoner's acceptance under leave-one-out;
- anything about real ARC tasks;
- that finding a verifying extension is hard: on this corpus one exists in
  the search space by construction, so the evidence is in selection and
  generalization only;
- the engine-internal reason for the six-pair rejections, which was not
  examined.

The claim stays LEVEL 1. The real ARC pilot is not licensed.

## 8.14 Why the same extension was accepted with seven demonstrations and rejected with six

[METHOD WRITTEN 2026-10-06; RESULT SEALED 2026-10-07]

Section 8.13's proposer selected an extension on every task, yet the
reasoner rejected it on most six-demonstration folds. A tracing audit,
frozen before it ran, followed every rejection inside the engine on
development data. All 145 rejections had the same cause: inside the
engine's own leave-one-out re-induction, two heuristics written for its
native hypotheses displaced an extension whose fold-fitted semantics
reproduced the held-out pair. A rule requiring two witnesses per table
key, applied again inside every five-pair refit, effectively demanded a
third (86 events); and a pixel-rule program with an unpriced colour table
outranked the extension (59 events). Load, compute budget and the
proposer's choice were ruled out.

One repair, K*-4, applies while an extension is installed: the extension
is fitted with every consistent witness and ranks first in every ranking;
the engine's acceptance gate is unchanged, and nothing changes when no
extension is installed. The repair lowers the evidence the engine
requires of an installed extension from three witnesses per key to two.
With four demonstrations neither the old nor the repaired engine
discriminated right from wrong installed extensions. One adversarial
review found that the protocol had denied the threshold lowering and that
the safety gate had been loosened after development data; an erratum
stated both and added a stricter rule (the outputs the repair adds must be
at least 95 percent correct) before any prospective data.

The prospective test ran once on 30 new synthetic tasks:
**ENGINE_STABILITY_REPAIR_ACCEPTED**.
- Complete end-to-end witnesses: 27 of 30 under the repaired engine,
  against 12 under the old one; adaptive leave-one-out with the proposal
  rebuilt in every fold passed on 27 against 12 tasks (207 against 133 of
  210 folds).
- Failure specificity held against both controls (6 to 0 and 8 to 0).
- Precision over everything the system certified: 237 of 239 against
  157 of 157; the repair added 80 correct and 2 wrong certified outputs.

What this does not show:
- that the engine can tell right from wrong installed extensions: it
  accepted all 5 seven-demonstration and all 28 four-demonstration wrong
  extensions it was given; correctness rests on the proposer's selection
  and the held-out checks;
- a gain independent of the corpus: every target key has at least three
  witnesses by construction, which is what the relaxed rule needs;
- anything about real ARC tasks.

The claim is LEVEL 2 for the synthetic domain, limited to tasks whose
extension keys have at least two witnesses in each run. It licenses the
design of a real ARC causal pilot, which must carry the safety burden the
engine does not.

## 8.15 A real ARC pilot, and why it has not run

[DESIGN AND FEASIBILITY 2026-10-07; superseded 2026-10-11: after section
8.16 the feasibility rule passed and the successor pilot v2 was FROZEN with
N = 120 (c1906ee); it has NOT been run.]

Section 8.14 licensed a pilot on real ARC-AGI-2 training tasks: one
independently scored rescue with the full witness, the same reasoner, and
abstention whenever the training evidence is thin. The harness was built
first, with two processes that never share data. The reasoner sees only
demonstrations and unlabelled test inputs under opaque keys, inside an
audit hook that refuses any access to data files, answers or the key map.
A blind evaluator scores only predictions already committed to version
control. Activation needs eleven train-only gates, among them a complete
adaptive leave-one-out, agreement of every verified candidate on the test
input, and at least two demonstration witnesses for every key the test
input uses.

A feasibility rule was fixed before any real task was run: the pilot is
frozen only if at least one of 60 development tasks reaches the stage where
a proposed extension is compiled and installed. None did. The proposer
stopped on all 60 because nothing it can build fits the demonstrations. The
reasoner's own failure frontier found a consistent single block on only 13
tasks, and the change in these tasks rarely takes the form the grammar
expresses (whole regions recoloured by a feature lookup). Across 12,000
block evaluations the commonest rejections were changes outside every
selected region (4,280) and regions that change only in part (3,688). On four
synthetic tasks where the grammar applies, the same harness passed every
gate up to witness support on all four and activated, correctly, on one;
the other three abstained at the witness-support gate although their
predictions were right, so that gate is strict and costs recall.

So the bottleneck on real tasks was the proposer's reach, not the engine or
the selection. Section 8.16 addresses that reach. With 4 of 60 development
tasks at the installed stage, the unchanged feasibility rule passed, and the
versioned successor (pilot v2, `docs/CORA_REAL_ARC_GROWTH_PILOT_v2.md`) was
frozen on 120 untouched training tasks with N set by the unchanged rule. It
has not been run: while the leave-one-out blocker of section 8.17 stands, the
development data predict that it would produce no witness.

## 8.16 Reaching real tasks: growth relations from the engine's own failures

[MEASURED 2026-10-11; development only; run once; independently verified]

The proposer of section 8.13 reached no real task (section 8.15). Its grammar
recolours whole regions by a feature lookup, and real changes rarely take
that form. Reach v1 starts instead from a failure trace the native object
engine already writes: when it cannot generalize a change, it memorizes it
as a constant `pattern` fallback. The memorized instances become evidence for
a growth relation (how an object grows into its output), and a frozen
grammar of 9 families and 210 settings is searched for one setting that
reproduces every memorized instance of one segmentation variant. A match is
compiled into a canonical growth extension, installed into the unchanged
engine through a reversible bridge, and judged by the engine's own gate
(train-exact plus its own leave-one-out) and then by the protocol's adaptive
leave-one-out, which removes a demonstration first and rebuilds everything
from scratch.

| stage (60 training-development tasks) | tasks |
|---|---|
| native baseline failure | 54 |
| usable failure evidence (memorized growth instances) | 31 |
| machine-generated proposal | 4 |
| canonical extension, compiled | 4 |
| installed into the native engine (0 of 60 before) | 4 |
| accepted native program that uses the extension | 1 |
| full adaptive leave-one-out | 0 (0 of 14 folds) |
| activation | 0 |

The accepted case (opaque key kf892487f1049; a `bbox_fill` relation in the
colour-layers variant S6) passed replay, attribution, prediction,
determinism, unanimity and support. Within the tested budgets it is not
reachable without the extension: the engine alone, the extension removed,
and matched compute (90 s) accept nothing. It is not a renaming (the
engine's own growth detector falls back to `pattern` on all 6 instances) and
not a cache (a 119-byte body against 83 memorized cells). No complete bounded
absence proof over the whole engine exists, so we do not label it a certified
semantic extension. Demonstrations-only construction proposes nothing on the
four tasks; shuffled failure evidence is never accepted with the extension
used. No task meets the invariant's conditions 1 to 5 together: the accepted
extension fails condition 5, adaptive leave-one-out.

Four kinds of novelty evidence are kept apart, because each needs its own
test.

| claim | status |
|---|---|
| (a) extension causality: K alone, the extension removed and matched compute accept nothing | development only; not certified |
| (b) failure-trace information causality: demonstrations-only and shuffled failure evidence give no accepted, used extension | descriptive, 4 tasks |
| (c) bounded semantic extension | not established |
| (d) later retention and reuse | untested |

## 8.17 Why the accepted extension failed leave-one-out

[DIAGNOSED 2026-10-12; development and synthetic; observation only; the
subsets examined were chosen after the failure was seen]

A frozen diagnosis (18 units, 102 engine runs, 29,828 CPU seconds) first ruled
out resources. Wall-clock and process-CPU deadlines gave identical
acceptance and stage in 23 of 23 paired arms, and matched compute up to
270 s never accepted. Forensic probes then located the mechanism in the
native engine's representation admission. The engine searches at most four
coherent segmentation variants, in a fixed trial order. Coherence requires a
consistent object-count relation across the demonstrations and pixel
coverage of at least 0.8.

In every outer fold of kf892487f1049 the engine finds the full-data program
$G$ at the top level. Its own leave-one-out then re-induces from two
demonstrations. On four of the six pairs it searches S6 first and returns
$G$. On the pairs (0,2) and (1,3) the demonstrations have identical object
counts in the fine variants, so a constant difference makes all five fine
variants coherent. Four of them fill the cap, and the strictly coarser S6
(4 against 6 and 8 against 12 objects) is never searched. The winners are
constant-class programs that are wrong on the held-out demonstration (21 to
33 cells). $G$ is train-exact on both pairs and would win on the engine's own
key (parameter class FEATURE against CONSTANT); it is simply never generated.

Across the four tasks, variant admission explains 11 of 14 failed folds and
all three full-data rejections. The remaining folds are support (2) and
identifiability from a single demonstration (1); proposer ordering co-occurs
in one. A first hypothesis, that the engine's cross-variant parsimony skip
pruned S6, was refuted.

Count consistency, all three of its clauses, is deletion-stable: each clause
is a per-pair condition or one parameter shared by all pairs, so a fold keeps
every view whose consistency the parent had. The complete eligibility test is
not monotone. Its pooled coverage can fall below 0.80 when a demonstration is
removed, and across all 60 development tasks it did so in 7 of 724
parent-fold comparisons, with consistency intact every time (Clarification 01;
an earlier count of 0 losses covered only 122 comparisons). The mechanism
here does not depend on coverage, which is 1.0 on every subset of
kf892487f1049. What fails is an invariant the engine documents for itself:
after a winner, strictly coarser variants are "still tried" so that an n-1
fold "converges on the same variant the full train set picks". The cap is
applied before that rule, to the fold's larger coherent set, and cuts the
coarser variant in exactly the case the rule was written for.

**Negative controls.** The obvious repair forces the extension's variant to
be searched first, admitting it even when incoherent. Before running it on
real tasks we tested that class on 24 seeded synthetic tasks (6 rule
families; 3 training and 2 held-out demonstrations each). Each run was
paired with the same task's native outcome (natively: 7 correct, 2 false
acceptances, 15 rejected).

| overlay | runs (tasks) | unchanged | harmful changes | gains |
|---|---|---|---|---|
| an eligible variant searched first | 131 (23) | 128 | 2 correct to rejected, 1 rejected to false acceptance | 0 |
| an ineligible variant searched first and admitted | 37 (10) | 34 | 2 correct to rejected, 1 correct to false acceptance | 0 |

At the task level, which is the honest denominator because the 168 runs are
correlated comparisons on 24 tasks: no task gained, and 5 of 24 were harmed.
Four of the 7 natively correct tasks lost their answer, and 1 natively rejected
task became a false acceptance.

Three mechanisms account for the harm:
- A coarser variant searched first prunes the finer native candidates
  through the parsimony skip.
- A forced view's program passes every engine gate but is wrong on held-out
  demonstrations.
- An incoherent forced view uses 3.5 times the native time.

The variant-first repair had already been built; it was not run. Letting the
coarser rule reach every cut variant was also rejected without a run. A
static count shows it would alter the search on 73 of 96 synthetic subsets,
mostly through the proximity variant the engine keeps as a last resort.

A narrow candidate (P2) would append, inside the engine's own leave-one-out,
the variant of the program under validation. The parent chose that variant
with the fold's held-out demonstration. P2 would therefore test whether the
program is stable given a representation selected with extra information.
That is not independent re-induction, so P2 can only be a labelled forensic
diagnostic, never a certificate. Every fold must select its representation
from its own training demonstrations.

A census of what the reasoner actually receives then showed genuine
redundancy. Equivalence was judged on typed objects, the engine's
correspondence alternatives and feature tables, not on object counts. On
(0,2) and (1,3) the four searched views are only two distinct inputs: S2 and
S5 duplicate S1. Deduplicating views from the fold's own demonstrations
would admit S6. That correction is fold-local and certification-preserving
by construction, but it is broad: it changes the search on 277 of 522
development subsets and on 4 of 6 native successes. A preregistered,
frozen synthetic safety preflight then tested it once
(`records/P3_SAFETY_PREFLIGHT_RESULT_20261012.md`), with BASE, a repeat of
BASE and P3 on 41 tasks.

| | result |
|---|---|
| tasks harmed | 4: two natively correct tasks became rejections, two rejected tasks became false acceptances |
| tasks gained | 1 |
| unexposed tasks | 7, byte-identical |
| native noise | none |

Every change ran through the coarse views that the freed slots admitted.
The mechanism was rejected by its kill rule. Removing duplicates is not
neutral once it admits views: the cap, the trial order and the tie-break
toward fewer objects act as an inductive bias.

Its pre-registered predictions do not rescue the screen. Three of the four
outer folds would pass. The fourth still fails, because the proposer selects
a different extension that the held-out demonstration refutes. So no
development task is predicted to reach conditions 1 to 5. Even then, the
change would be a representation correction in the native search, not
semantic invention.

The lesson is the paper's thesis in miniature. The failure looked like "the
constructed capability does not generalize". It was a defect in which
representations the existing search admits, and only typing the failure
told the two apart. That typing was done by forensic analysis; CORA's
general failure-type controller is proposed, not implemented.

## 8.18 Neural guidance of representation admission: a pre-registered negative result

**Tier: synthetic** (a private generator). This is not real ARC, not a
Kaggle score and not capability invention.

**Question.** When the frozen reasoner fails and a coherent segmentation
view was cut by its four-view cap, can a frozen neural model choose which
view to admit, given the reasoner's authentic failure trace?

**Design** (`records/CORA_NEURAL_VIEW_GUIDANCE_PLAN_20261012.md`, frozen at
7f0b17e before the single final run).
- **Arms.** The same Qwen2.5-1.5B with:
  - demonstrations only (C);
  - plus the authentic trace (D);
  - plus a shuffled trace (E);
  - plus the failure type only (F).

  Also counterfactual-transition forms, a frozen I-JEPA encoder,
  fixed-order (B1), ARGA-style (B3) and coarsest-first (B2) symbolic rules,
  and random.
- **Scoring.** Each choice is scored by the engine's own promoted-view run,
  with full leave-one-out; held-out outputs are used only by the evaluator.
- **Leakage.** Mutation tests show held-out outputs cannot change a guide's
  input.

**Result** (165 decisions, 35 warranted;
`records/CORA_NEURAL_VIEW_GUIDANCE_RESULT_20261013.md`):

| arm | useful views chosen |
|---|---|
| B1, B3 | 35 |
| C | 19 |
| F | 19, identical to C |
| D | 1 |
| E | 1, identical to D |
| I-JEPA (every condition) | 3 |
| random | 12.6 |

- No guide caused a false acceptance.
- **The authentic trace made the language model abstain more and choose
  worse,** p < 0.0001 against C. The shuffled trace did exactly the same,
  so the trace's content carried no usable signal for this model.
- I-JEPA's development advantage did not replicate.

**Limitation.** All 35 warranted decisions come from one family, in which
the useful view is the first view the cap cuts, so the fixed order is
optimal there.

**Relation to prior work.** This extends KAAR's report that LLMs choosing
abstractions from raw grids was unsatisfactory. Adding authentic failure
evidence did not rescue that choice. It also agrees with this project's
earlier finding that failure features never beat demonstration-only
controls.

The route is closed. The open question moves to neural *candidates*, not
neural rankings, as evidence of a missing capability.

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
- The failure-conditioned selector (section 8.10) added nothing beyond the
  demonstration summary on 288 independent-input test groups. It also did
  not beat a matched shuffle of the failure evidence. Both comparisons failed
  decisively at full preregistered power.
- In the bounded repair (section 8.11) the passive channel again added
  nothing on new data (P2 0.578 against 0.580). The pure intervention rule
  alone did not beat the demonstrations, because it abstains on four
  ambiguous pairs in five. The hybrid logit did not pass either.
- The no-oracle proposer (section 8.13) was failure-specific but not end to
  end: 11 of 30 complete witnesses against 15 required, because the engine
  rejected most produced extensions on six-pair leave-one-out folds.
- On real tasks the same proposer reached nothing: 0 of 60 real development
  tasks produced a verified proposal (section 8.15), so the first real ARC
  pilot was not frozen.
- The growth-relation proposer that replaced it reached the installed stage
  on 4 of 60 development tasks, but no extension survived adaptive
  leave-one-out (0 of 14 folds) and nothing activated (section 8.16).
- Forcing a segmentation variant to be searched first, eligible or not,
  gained no task and harmed 5 of 24 synthetic tasks (6 of 168 correlated
  runs; section 8.17). The built repair of that class was not run. The
  hypothesis that the parsimony skip caused the real failure was refuted.
- The complete eligibility test is not monotone in the demonstrations: 7 of
  724 development parent-fold comparisons lose a view through pooled
  coverage. An earlier statement of monotonicity rested on 122 comparisons.
- The contrastive corpus (section 8.8) failed its identifiability gate: the
  failure summary told two close targets apart at 0.470 against an exact
  null of 0.429.
- The engine does not discriminate installed extensions. With four
  demonstrations neither the original nor the repaired engine separated
  right from wrong ones, and in the v1.9 prospective test the repaired engine
  accepted all 5 seven-demonstration and all 28 four-demonstration wrong
  extensions it was given (section 8.14).

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

No precedence wording is used without a current primary-source check. This
section is the bibliography stub; no formal bibliography file exists yet.

**ARC-AGI-2 competition methods, 2025-2026** (survey with dated sources:
`records/CORA_ARC_LEADER_SURVEY_20261013.md`).
- **The best documented Kaggle-eligible systems are transductive neural
  models with per-task test-time training:** NVARC 24.03 private, the
  ARChitects' masked-diffusion LLaDA-8B 16.53, MindsAI and Tufa's CodeT5
  12.64. ARC Prize attributes the top 2024 and 2025 scores to test-time
  training.
- **Undisclosed:** the 2026 entries scoring 77-88 on the public board.
  Tufa Labs' documented 2026 work is an ARC-AGI-3 harness, which is not
  evidence for its ARC-AGI-2 entry.
- **Symbolic and induction-only systems score about 0 on ARC-AGI-2** in
  every independent report found, consistent with CORA's base reasoner.
- **CORA's distinctive element is strict program certification.**
  Augmentation agreement is the field's documented selection method, and
  selection is a documented weak point: NVARC reports correct candidates
  not always picked.

The distinctions that matter are specific rather than nominal.

DreamCoder grows a reusable symbolic library, so the claim cannot be that
this system grows a program language. The difference is what drives the
growth. There, library learning proceeds by compression and abstraction over
tasks already solved or replayed. Here the mechanism is prospective and
failure conditioned: the reasoner's own failed trajectory on the unfamiliar
task determines what gets constructed, at the moment that task is
encountered. LILO refactors learned libraries and sits in the same family, so
the same distinction applies to it.

AlphaEvolve does produce genuinely new and useful executable artifacts, so
the claim cannot be that a system generates novel code. The differences are
that no general-purpose language model proposes anything here, and that
proposal is conditioned on a typed representation of the system's own failed
inference rather than on free-form generation filtered by an evaluator.

Predicate invention from failures, POPPI in particular, is the closest prior
art and rules out the wording that would otherwise be tempting. This work
cannot claim to be the first system to invent concepts from failure. That
claim is taken.

What survives those three subtractions is a conjunction rather than any
single ingredient. Several of its links are not yet demonstrated, and the
chain is what would be claimed, never the parts.

The candidate novel contribution is the conjunction: failed reasoning, to a
mechanistic typed failure representation, to diagnosis of a capability gap,
to an executable language extension, to an additive comparison of the
language with and without it, to full adaptive leave-one-out, to a causal use
test, to removal ablation, to bounded semantic separation, to independent
transfer, to verifier-controlled promotion. The full conjunction has not been
demonstrated and is not claimed.

The operational distinction the paper defends throughout is that finding a
better answer, finding a better program and acquiring a new capability are
three different things. The third is the interesting one, and only if shown
repeatedly, autonomously, and on unseen tasks.

A second, smaller novel result stands on its own: the failure-frontier audit
is a diagnostic result about machine self-observation. A system's record of
its own reasoning failures was found to be task-invariant, which explained an
earlier control result, and instrumenting the deployed reasoner exposed
task-dependent semantic frontiers. That is not semantic invention.

## 11. Limitations

- No public ARC score has been measured for CORA's constructive path, and it
  may remain low. The base reasoner scored 0.0 on Kaggle in July 2026 and 0 of
  120 on the local public evaluation.
- **Neural view guidance (section 8.18) failed on one effective family.**
  All 35 warranted synthetic decisions came from a family where the fixed
  view order is already optimal, so the test is narrow, although
  pre-registered and adequately powered by its own rule.
- **The neural competition entry (section 6.4) is a reproduction of public
  work.** Its scores, when available, measure that pipeline, not CORA. Its
  model is contaminated for every public ARC-AGI-2 split.
- Verification has shown poor off-distribution calibration: 40 of 42 on
  training against 0 of 11 on an evaluation development split.
- Every constructive result that completed a witness (sections 8.11 to
  8.14) is on the synthetic constructive grammar. The real-task results
  (sections 8.16 and 8.17) are development-only and complete no witness.
- The forensic subsets of section 8.17 were examined after the failure was
  seen. They explain a failure; they do not test a fix. The synthetic
  negative controls have limited power (7 of 24 tasks natively correct), and
  their rule families are not ARC.
- The view census of section 8.17 is static: it shows what deduplication
  would search, not what it would solve.
- The narrow correction of section 8.17 has not been run. Its own
  predictions leave every development task short of complete adaptive
  leave-one-out.
- The repaired engine does not discriminate right from wrong installed
  extensions. Correctness rests on selection, held-out checks and abstention,
  which the real pilot has to carry.
- The v1.9 gain is limited to extensions whose keys are witnessed at least
  twice in each run. The synthetic corpus guarantees this by construction;
  real tasks with two to five demonstrations often will not.
- On the synthetic corpus a verifying extension exists in the proposer's
  search space by construction, so the evidence concerns selection and
  generalization, not the difficulty of finding an extension.
- The v1.6 selection result is hybrid and below its powered size.
- Step B has no verdict.
- The informative failure-channel classification rests on twelve tasks and
  sits exactly at its threshold; three of those twelve tasks emit no
  candidates at all.
- Bounded semantic separation does not establish universal non-definability.
- Empirical cross-domain transfer is not demonstrated.
- ARC results alone do not establish general intelligence.

## 12. Conclusion

CORA separates three things a score cannot separate, and holds a fixed
verifier between proposal and acceptance so that generated novelty is not
mistaken for capability. The measured contribution in this revision is a
chain, each link frozen before its data. The system's record of its own
failures was observing the wrong reasoner and was repaired. Passive
descriptions of failure did not help choose an extension beyond the
demonstrations, but a candidate's effect on the failed reasoner did. A
selected extension can be compiled into the same reasoner, and one can be
proposed from the reasoner's own failure without an oracle. After one generic
engine repair the closed loop completed on 27 of 30 new synthetic tasks. On
real development tasks the loop now reaches the native engine, and the
unchanged engine accepted and used one constructed extension. It did not
survive adaptive leave-one-out, and the cause was a representation-admission
defect in the native search, not a missing capability. The obvious repair
was harmful on negative controls and was not run. No real ARC task has been
solved by a constructed extension, the engine accepts wrong extensions as
readily as right ones, and the durable-growth experiment has no verdict. We
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
| intervention-based selection (v1.6), hybrid | no | partly | yes | yes | yes | partly |
| extension compiler (v1.7) | no | no | yes | partly | yes | partly |
| no-oracle proposer specificity (v1.8) | no | partly | yes | yes | yes | yes |
| synthetic closed-loop witnesses (v1.9), 27 of 30 | no | partly | yes | yes | yes | yes |
| real ARC causal witness | not yet | no | not yet | yes | not yet | yes |
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
in section 10. Its synthetic links (failure-specific proposal, compilation
into the same reasoner, additive comparison, adaptive leave-one-out, use and
removal) are demonstrated in sections 8.12 to 8.14; its real-task links are
not. The self-observation diagnostic is demonstrated.

**Flagged weakness.** Accuracy has no evidence yet, and every constructive
result is synthetic. That is stated here rather than hidden behind the
stronger sections.

## Appendix C. Research trajectory, December 2025 to October 2026

The full map of the four project trees, with every step and its record, is
`docs/PROJECT_MAP.md`.

| when | what | key number |
|---|---|---|
| Dec 2025 | first prototype (program language, language-model hints, learned ranking) | prototype only |
| Apr 2026 | restart as a research program on synthetic worlds | falsification nearly eliminated false rules |
| May-Jun 2026 | real ARC, solver portfolio, module audit, object engine started | 67 of 1,000; 0 false positives in 480 audit runs |
| Jul 2026 | sealed runs with leave-one-out certificates; first Kaggle submission | 151 to 173 of 1,000; Kaggle 0.0 |
| Aug 2026 | generated rules, primitives reinvented from residuals, v23 sealed | 185 of 1,000 |
| Aug 2026 | CORA adopted; Step B frozen and launched | no verdict yet |
| Sep 2026 | test-time invention attempts; transfer and abstraction studies | DEV-60 0.0; 0 of 1,500 admitted; no reach gain |
| Sep-Oct 2026 | delivery sprint v1.2 to v1.9 (sections 8.5 to 8.14) | 27 of 30 synthetic end-to-end witnesses |
| Oct 2026 | real ARC pilot harness built; the frozen proposer reaches 0 of 60 real development tasks | pilot not frozen; proposer reach is the blocker |
| Oct 2026 | reach v1: growth relations from the engine's own memorized failures (section 8.16) | 4 of 60 installed; 1 accepted and used; 0 of 14 LOO folds |
| Oct 2026 | pilot v2 frozen on 120 untouched training tasks | not run |
| Oct 2026 | leave-one-out diagnosis and synthetic negative controls (section 8.17) | representation admission in 11 of 14 folds; variant-first repair: 0 of 24 tasks gained, 5 harmed |

Tried and dropped, each with its recorded diagnosis: language-model hints and
learned ranking policies, a world-model reranker, a vision probe, a small
recursive network, a search-guide network, a per-task compression solver,
generic test-time schemas, learned abstraction selection, abstraction
transfer, and passive failure descriptors as a selection signal.

## Out of scope

Capability-growth gate internals, the parallel verified-capability scaling
project, and biological applications.
