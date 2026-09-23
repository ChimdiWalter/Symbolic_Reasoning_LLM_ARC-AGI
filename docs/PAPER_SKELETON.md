# CORA: Separating Search, Hypothesis Selection, and Capability Growth in ARC-AGI-2

Status: working manuscript for the ARC Prize 2026 paper track. Updated
2026-09-23. This file is the authoritative source for this paper. No LaTeX
source, compiled PDF or bibliography file exists yet in this workspace; the
related-work list below is the bibliography stub. The separate
`kaggle/writeup.md` is a different paper, about generalization certificates,
and is not superseded by this one.

The title changes to match the measured result, never the desired one.

## Abstract

CORA studies the distinction between finding a better program inside a fixed
reasoning language and changing the reasoning language itself. We develop a
non-LLM symbolic reasoning system with immutable verification, separate
gains in search and hypothesis selection from gains in capability, and run
two independent self-extension experiments at different timescales: a
durable one under a frozen gate, and a task-local one at test time.

A diagnostic audit reported here found that the original test-time failure
channel observed a restricted proxy reasoner rather than the full ARC
engine. Over twelve prospectively fixed development tasks that channel
produced no executed near misses and no mismatch evidence at all, and its
candidate census was identical across unrelated tasks. That explains an
earlier null result in which shuffled failure evidence performed about as
well as real failure evidence: the real evidence carried almost no
task-specific information.

Instrumenting the actual reasoner, without changing its search, produced
task-dependent semantic frontiers, twelve distinct frontier operator
families instead of one, and executable near-miss candidates. A subsequent
evaluator-compatibility repair carried the mismatch evidence into the typed
failure graph, moving the channel across its preregistered threshold. The
constructive components that would consume that evidence remain unbuilt.

Durable semantic invention remains under evaluation in the independent
frozen Step-B experiment, whose verdict is unknown and uninspected. We do
not claim that CORA has invented a new semantic primitive.

## Contributions

1. A formal separation of search improvement, hypothesis-selection
   improvement and capability growth, with measurements that keep them apart.
2. An immutable-verification and causal-witness discipline under which a
   score gain is never reported as invention.
3. A protocol for durable capability growth, frozen before results, with a
   staged gate and sealed data access.
4. An architecture for task-local language adaptation that installs an
   extension for one task and resets afterwards.
5. An empirical diagnosis of a failure-observation disconnect in that
   architecture, and its repair, with before and after measurements.
6. Negative results showing why score and search improvements alone are not
   evidence of invention.

## 1. Problem

ARC-AGI-2 under a twelve-hour offline budget, two outputs per test input,
exact match. The research question is whether a task-local, executable
program construction can improve held-out predictions beyond ordinary search
over the same building blocks, under matched total compute.

The principal prospective comparison is fixed-language reasoning against
failure-driven language adaptation.

Working thesis, stated as architecture and hypothesis rather than as a
validated finding: when a fixed reasoning language fails, CORA represents the
failure mechanistically, constructs a task-local typed program, re-enters the
original reasoner with that program installed, and lets an immutable verifier
decide whether the new reasoning path survives. The constructive step of that
sentence is not yet implemented, so the sentence is a hypothesis about the
architecture, not a result.

## 2. The system, in one page

Three-layer certified induction. A program is accepted only if, rebuilt from
all demonstrations but one, it predicts the one left out, for every fold. Two
outputs per test input: attempt one certified, attempt two error-diverse. One
global time governor.

Ordinary machine adaptation changes parameters:

    theta -> theta'

CORA's question is about the language itself:

    K -> K' = K union {e}

## 3. The distinction the paper is built on

Search improvement, hypothesis-selection improvement and capability growth
are three different things. In a prior measurement every compared policy
solved the same 188 of 256 targets, so the learned system searched more
cheaply and changed some predictions without gaining reach. A score gain is
never reported as invention.

Four distinctions are used throughout:

- a new program is not a new capability;
- a new composition is not semantic invention;
- a macro is not semantic novelty;
- a score improvement is not capability growth.

## 4. Two experimental timescales

CORA tests one idea at two timescales. They share the idea and share no
evidence. Results from one are never merged into the other.

                          CORA
                            |
            +---------------+---------------+
            |                               |
      CORA-SCIENCE                      CORA-TTI
      Step B, durable                   task-time, ephemeral
            |                               |
    historical certified failures       a new task
            |                               |
    failure clustering                  K fails
            |                               |
    frozen candidate extensions         observe the real frontier
            |                               |
    K + e, exhaustive resolution        construct e  [not implemented]
            |                               |
    capability-growth gate              compile and install e  [not implemented]
            |                               |
    bounded semantic separation         reason again, verify
            |                               |
    transfer                            predict
            |                               |
    possible persistent promotion       reset to K

### 4.1 CORA-SCIENCE, Step B

Purpose: durable capability growth. It asks whether durable machine
capability growth exists at all under a frozen gate.

Step B contains 62 failure clusters and 4,784 frozen candidates, split into
816 K2 semantic-production candidates and 3,968 K1 repair candidates.

Step B is still running. No semantic result has been inspected. No Step-B
candidate is used by the ARC delivery sprint. Its verdict remains unknown.

Latest recorded checkpoint, not a live claim: K2 at 350 of 497 proposal
units, runner alive, zero recorded errors, no freeze marker and no final
output hash. Two phases follow K2, namely K1 and resolution.

### 4.2 CORA-TTI, ARC delivery

Purpose: task-local language adaptation. It asks whether failure-driven
capability construction can run fast enough at test time to improve ARC
reasoning.

    K -> reason -> fail -> typed failure graph -> construct e
      -> temporary K + e -> reason again -> verify -> predict -> reset to K

The task-local extension is discarded after the task and never becomes
permanent knowledge.

## 5. Implementation status, corrected

The architecture is largely built. The constructive path is not.

Built and tested: typed failure graph machinery; the constructive vocabulary
and legal AST grammar; AST canonicalization and token round-trip;
constructive datasets and holdout machinery; occurrence-scoped fitting; TTI
orchestration; a Stage-A known-name proposer; exact execution; leave-one-out
verification; an ablation ledger; scheduler and diversity; ephemeral
task-local install and reset; a Kaggle emulator.

Two corrections to earlier internal descriptions are recorded here because
they change what the paper may claim.

`mdl_fallback_proposer` is not a MetaConstructor. Its contract is a failure
graph and a count in, existing catalogue production names out, ranked by cost
and name. That is known-operator reconstruction.

`constructive_vocabulary` defines the law of legal constructive ASTs. It
answers what constitutes a legal new program. It does not answer which new
program to construct from a failed trace, and it is not a proposal
mechanism.

The currently implemented proposal path therefore performs failure to known
production selection, not failure to unseen executable AST.

Unfinished and specified only: the grammar-constrained constructive AST
proposer, and the ConstructiveExtensionCompiler. Neither is implemented.
Neither is presented here as implemented.

## 6. Diagnostic result: the failure-frontier audit

A negative result, reported in full.

Twelve development tasks were fixed by a selection rule committed before any
result was computed: the first twelve task identifiers in ascending order.
Only the existing failure path was run. Nothing was proposed, constructed,
installed or scored, and no test outputs were read.

On the original instrumented path:

| quantity | value |
|---|---|
| observer candidate events | 64,610 |
| frontier-eligible events | 32,305 |
| frontier terms | 144 |
| executed-but-non-exact candidates | 0 |
| value signatures | 0 |
| mismatch signatures | 0 |

On eleven of the twelve tasks the observer census was identical:

    {typed: 2736, slot_fit_failed: 2736}

The twelfth differed only because it hit its deadline. Three unrelated
synthetic tasks, a tiling, a transpose and a crop, reproduced the same census
and the same ordered list of frontier programs. Every frontier candidate used
a single root operator, `PaintEach`, which was the only primitive in the
eleven-primitive environment that returned a grid.

Interpretation: the candidate-associated failure signal was effectively a
constant of the toy language rather than a function of the ARC task.

This retrospectively explains an earlier failure-signal experiment in which
real candidate-associated evidence and shuffled candidate-associated evidence
performed about equally well. They performed equally well because the real
signal carried almost no task-specific information to destroy.

## 7. Root cause

The thing doing the reasoning was not the thing being observed.

The original trace observer was attached to an eleven-primitive blind-runtime
search. The full ARC object reasoner never emitted its internal candidate
lifecycle to the failure representation. A search of the engine, harness and
source directories for the observer returned nothing, and the real-engine
task-local install path contained no reference to the failure graph.

Classification: no near misses actually generated, with root cause the full
engine not being instrumented.

This does not show that failure-conditioned construction is ineffective. It
shows that the intended constructor had never been given the actual
full-engine reasoning frontier.

## 8. The full-engine observation repair

An instrumentation repair, not a new reasoning system. CORA's existing
reasoner was made observable to CORA's existing failure representation.

Only the isolated delivery workspace copy was modified. The research engine
running Step B was untouched, verified afterwards by checking that the shared
failure-graph code and the research engine directories were unmodified.

The repair emits the existing candidate lifecycle from the actual object
reasoner: a typed candidate group, then parameter fitting that either fails
or succeeds, then an assembled or partial program that either reproduces
every demonstration or does not.

One engine property mattered. The reasoner assembles a program only when
every object group has been explained, so its genuine near misses are the
partial programs it builds at the failure branch and then discards. Those are
what had to be observed.

Observation is designed to be noninterfering. Tests verify that installing
the observer does not change the solver result, comparing exactness,
strategy, training accuracy, leave-one-out score, best accuracy, failure
stage, pixel fit and both serialized programs. Candidate ordering, search
depth, parameter fitting, pruning, acceptance, verifier rules, budgets,
ranking and language contents are unchanged.

One outcome name was not emitted. The object grammar constructs only
well-typed rules, so there is no program-level typecheck rejection to
observe, and the name was reported as unmapped rather than redefined.
Selector-induction failure is a real engine state that no existing outcome
name describes, and it was left unnamed for the same reason.

## 9. Repaired-frontier result

Across the same frozen twelve-task audit, same budget, same frontier cap,
same thresholds:

| quantity | original channel | repaired channel |
|---|---|---|
| candidate events | 64,610 | 494 |
| identical census across unrelated tasks | yes | no |
| distinct frontier operator families | 1 | 12 |
| tasks with at least two frontier terms | 12, all identical | 9 |
| parameter-fitting successes | 0 | 62 |
| executed-but-non-exact candidates | 0 | 36 |
| exact candidates | 0 | 7 |

Task-dependent frontier operators included grow, translate, copy, copy_part,
composite, paint and keep, in place of one invariant operator.

Three of the twelve tasks emit nothing. On those the engine gives up before
rule induction, at segmentation or matching, so there is no candidate to
observe. That is a property of the engine on those tasks, not a trace defect.

## 10. Candidate-executor compatibility repair

The repaired producer recorded fitted, executable object programs, but the
failure-graph consumer still evaluated every candidate with the
blind-runtime evaluator, which cannot execute them. Evaluation raised, the
exception was caught, and every value signature degraded to undefined. The
channel was therefore classified PARTIAL at that point: the evidence existed
at the producer and did not reach the graph.

The compatibility repair adds one optional evaluator parameter to the graph
builder, defaulting to the previous behaviour, so the builder asks which
executor owns a candidate instead of assuming every candidate belongs to the
old runtime. The full-engine adapter supplies the engine's own renderer. It
changes only how an already-observed candidate is executed for diagnostic
evidence. It does not change search, candidate generation, candidate
ordering, fitting, grammar, verifier, acceptance, budgets, Step B, or the
research tree. The change was made on a vendored copy inside the delivery
workspace, with the source checksum recorded, because the research worktree
is frozen.

Measured outcome, same twelve tasks, threshold fixed in advance and not
reinterpreted:

| quantity | before compatibility repair | after |
|---|---|---|
| defined value signatures in the graph | 0 | 18 |
| tasks with at least two frontier terms | 9 of 12 | 9 of 12 |
| tasks with defined candidate-associated mismatch evidence | 0 of 12 | 8 of 12 |
| tasks meeting both preregistered conditions | 0 of 12 | 8 of 12 |

The preregistered threshold for an informative channel was at least eight of
twelve tasks meeting both conditions. The repaired channel meets it at
exactly eight, and the result was identical across three independent runs.
A representative recorded signature is a candidate that matched the target
shape with 64 cells wrong, a wrong fraction of 0.16 and no extra palette
entries.

Two cautions belong with this number. It sits exactly at the threshold rather
than comfortably above it, and the qualifying set is the same eight tasks the
producer-side probe had already identified, so the repair transported
existing evidence rather than creating new evidence. The three tasks that
emit nothing cannot qualify under any repair of this kind.

## 11. What has not been tested

CORA has not demonstrated on real ARC any of the following:

- autonomous construction of an unseen AST from a real failure graph;
- a ConstructiveExtensionCompiler operating end to end;
- a clean constructive reach gain;
- bounded semantic extension from the task-time path;
- transferred semantic invention from the task-time path.

These are prospective experiments. No placeholder in this manuscript is to be
read as an observation.

## 12. Claim ladder

- L1, generation: a candidate or new AST was produced.
- L2, operational language extension: adding the extension changes bounded
  search reach.
- L3, bounded semantic expressivity extension: under declared comparison
  bounds, the prior language cannot reproduce the extension's behaviour.
- L4, bounded semantic invention: L3 together with causal new reach and
  independent transfer.

## 13. Six-leg causal witness

A strong capability-growth witness requires all six legs:

- B: the baseline language fails;
- P: the extension is produced;
- U: the winning reasoning path uses it;
- L: full adaptive leave-one-out passes;
- T: the final output is correct;
- A: removing the extension destroys the gain.

The comparison must be genuinely additive, with matched solver conditions and
resource accounting. This standard governs Step B and the future constructive
test-time experiment alike.

## 14. The controlled comparison

BASE, BASE_PLUS_INTERVENTION, MATCHED_EXPANDED_SEARCH and ABLATION, under one
fixed budget and a schedule frozen before scoring. Paired wins and losses are
reported, never a net figure.

## 15. Results table

Entries not yet measured say so. They are not reported as zero.

| quantity | value |
|---|---|
| BASE pass@1 | NOT YET MEASURED |
| BASE pass@2 | NOT YET MEASURED |
| TTI pass@1 | NOT YET MEASURED |
| TTI pass@2 | NOT YET MEASURED |
| second-answer rescues | NOT YET MEASURED |
| construction activations | NOT YET MEASURED |
| successful constructions | NOT YET MEASURED |
| constructive reach witnesses | NOT YET MEASURED |
| semantic-separation witnesses | NOT YET MEASURED |
| transferred witnesses | NOT YET MEASURED |
| tasks harmed | NOT YET MEASURED |
| timeout and resource failures | NOT YET MEASURED |
| end-to-end runtime | NOT YET MEASURED |

## 16. The engineering rehearsal, kept in its place

A five-task rehearsal of the previous library version was a baseline and
engineering measurement only. It established that packaging works, that the
submission schema works, that the global time governor binds but showed an
overrun, that the previous version solved none of the five, and that some
failures reached the leave-one-out or matching stages. It did not test
failure-conditioned semantic construction.

Relational parameter fitting was provisionally selected after that
diagnostic. It is no longer the primary scientific treatment and may return
later as an inner slot fitter. This history is kept rather than erased.

## 17. Preserved negative results

- A learned-prior study did not robustly beat concrete memory, and every
  compared policy had the same bounded search reach, so no reach witness was
  established there.
- An earlier development-set comparison of the task-time path was not
  additive, so it is infrastructure evidence only.
- The first proposal network performed known-name reconstruction.
- The first constructive census admitted nothing.
- The corrected census admitted thirteen supplied candidate structures, which
  are not thirteen autonomous inventions.
- The original failure channel carried no task-conditioned candidate
  evidence, as reported in section 6.

These negatives are what keep selection, search, operational extension and
semantic capability growth separate in this paper.

## 18. Why it helps or fails

The diagnosis table: no useful candidate; candidate present but not selected;
demonstration-fitting but wrong; verification rejection; resource
exhaustion; packaging loss.

## 19. Limitations

Certification does not transfer off distribution: 40 of 42 on training
against 0 of 11 on the evaluation development split. No training-set headline
number appears in the results section. The frontier audit measured twelve
tasks, which is a small and deliberately fixed sample. The informative
classification sits exactly at its threshold. The blind runtime's top-level
enumeration still admits only goal-typed candidates, so a type gap cannot be
represented there; that limitation was deliberately left unrepaired so that
only one variable moved at a time.

## 20. Related work

DreamCoder, LILO, predicate invention and POPPI, AlphaEvolve, program
synthesis and library learning, and relevant non-LLM ARC systems.

CORA is not claimed to be the first system to invent operations or to grow a
program library. The novelty case is the conjunction: reasoning failure, to
typed and mechanistic failure evidence, to an executable language extension,
to an additive comparison of the language with and without it, to adaptive
leave-one-out, to causal ablation, to bounded semantic separation, to
independent transfer, to promotion controlled by an immutable verifier. No
precedence wording is used without a fresh primary-source check.

## 21. Relationship to Step B in this paper

This manuscript stands without Step B. Step B is named as ongoing, with no
semantic verdict and no partial candidates or outcomes used. If Step B
finishes later, its result is incorporated only after its frozen gate permits
interpretation, and only as a separate durable-capability-growth section.

## Out of scope

The capability-growth gate internals, VDCG and biological applications.
