# Failure Frontier Extraction v2: repair specification and acceptance gate

Preregistered 2026-09-23, before any instrumentation was written, in the same
way as `records/FRONTIER_AUDIT_SELECTION_RULE.md`. Thresholds below are fixed
in advance and are not to be adjusted after seeing the repaired trace.

Context: `records/FRONTIER_AUDIT_20260923.md` measured the existing channel
as EMPTY_OR_UNUSABLE, loss point NO_NEAR_MISSES_ACTUALLY_GENERATED, root
cause FULL_ENGINE_NOT_INSTRUMENTED. The finding is an infrastructure
disconnect, not a refutation of failure-conditioned construction: the thing
doing the reasoning was not the thing being observed.

## 1. Scope of the repair

Exactly one change, made only in this workspace's allowlisted engine copy.
The research checkout's engine is not touched and Step B is unaffected.

    full ARC engine
      -> existing TraceObserver protocol
      -> candidate outcomes from real search
      -> existing build_tfg()
      -> the same frozen 12-task audit

Reused unchanged: `TraceObserver`, the six outcome names, `FRONTIER_OUTCOMES`,
`build_tfg`, `ConcreteTFG`, the audit harness and the frozen task set.

## 2. Instrument the candidate lifecycle, not the verdict

Instrumenting only the final accepted-or-rejected point would lose the
semantic frontier again. The whole purpose of the graph is to record how far
the current language got before it failed. Emission sites follow the
lifecycle:

    candidate generated
      -> typechecked            typecheck_failed | typed
      -> slot/parameter fit     slot_fit_failed  | slot_fit_ok
      -> executed               executed_not_exact | exact

The evidence that matters is partial: this typed bridge existed, this
parameterization failed, this candidate produced the right shape but the
wrong relation, this candidate preserved objects but lost placement.

## 3. Repair the fitted-versus-unfitted defect at the same site

Secondary defect 2 of the audit is repaired here, because it is part of the
same emission and not a new feature. The event must carry the executable
fitted program:

    observer.candidate(complete, "executed_not_exact")

not the unfitted skeleton `ast`. Otherwise `_mismatch_signature` receives
something it cannot execute and the repaired engine would still yield
undefined value evidence.

## 4. Explicitly deferred

The goal-typed-only enumeration restriction, secondary defect 1, is NOT
changed in this repair. Changing the observed engine and the enumeration
policy at once would move two variables and spoil the causal story. The
question this repair answers is whether the real engine naturally produces
informative near misses under its current reasoning policy. If the repaired
trace is informative but systematically lacks type-gap evidence, wrong-type
frontier exposure becomes a separate versioned amendment.

Also not built: the Stage-B constructive AST decoder, the
ConstructiveExtensionCompiler, any further proposer, any further verifier,
any further graph format.

## 5. Mechanical acceptance, all six required

1. The full engine emits the existing six candidate outcome classes.
2. The trace varies across unrelated tasks. The fixture equality
   `test_candidate_trace_is_identical_for_unrelated_tasks` must fail.
3. Candidates reach stages beyond mere typing: `slot_fit_ok`,
   `executed_not_exact`, or the real-engine equivalent near-miss states.
4. Where an executed near miss exists, the graph receives the fitted
   executable program, not the unfitted skeleton.
5. Value and mismatch signatures are actually defined for those near misses.
6. No test output and no protected data enters the trace.

Item 2 alone is necessary but not sufficient. Two traces can differ through
irrelevant counters, nondeterministic ordering, task size or a superficial
engine detail. A broken equality is not by itself a success.

## 6. Scientific acceptance, preregistered and unchanged

Measured on the same frozen 12 dev tasks, by the same harness.

    INFORMATIVE        >= 8 of 12 tasks each carry >= 2 candidate-associated
                       frontier terms AND non-empty candidate-associated
                       value or mismatch evidence.
    PARTIAL            frontier terms present on most tasks but a whole
                       evidence class is systematically absent.
    EMPTY_OR_UNUSABLE  most tasks carry no candidate-associated evidence.

## 7. Decision tree after the repair

**Outcome A, INFORMATIVE.** The already-specified constructive AST proposer
is then licensed: typed failure graph plus typed interface to a new
constructive AST. Only after that, the ConstructiveExtensionCompiler, kept as
a separate responsibility. Only after that, the six-leg witness on real ARC.

**Outcome B, PARTIAL.** Do not build the constructor. Name the specific
missing evidence class, one of fitted candidates absent, execution mismatches
absent, object-relation evidence absent, wrong-type frontier absent, and
repair only that.

**Outcome C, still EMPTY_OR_UNUSABLE.** This would be a deeper scientific
result: the engine does not naturally generate semantic near misses rich
enough to drive failure-conditioned language construction. The research
target would then become frontier formation inside the reasoning search
itself, not the graph and not the proposer.

## 8. What the repair is for

The intended mechanism is unchanged:

    K -> reason -> fail -> inspect its own reasoning frontier
      -> infer the missing capability -> e -> K + {e} -> reason again

The audit showed that the inspect-its-own-frontier arrow was attached to the
wrong reasoner. This repair reattaches it. No answer-grid prediction, no task
classifier, no stored solver lookup, no new DSL.
