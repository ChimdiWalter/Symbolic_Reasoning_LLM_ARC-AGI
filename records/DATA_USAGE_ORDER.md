# Data-usage order, recorded 2026-09-23

Binding order for which data may be consumed at which stage. The September
delivery plan supersedes the earlier August plan, which wanted early
full-set measurements.

    v1.3 full run and nonlearned audit
      -> scorer discrimination
      -> generic ConstructiveExtensionCompiler
      -> end-to-end K plus e
      -> small fixed DEV causal pilot
      -> first clean six-leg constructive-reach witness
      -> broader DEV optimization
      -> freeze architecture and policies
      -> 1000-task training characterization
      -> 60 DEV evaluation
      -> final policy freeze
      -> 60 protected HOLDOUT
      -> final 120 and Kaggle

**The trigger for the 1000-task run is not that v1.3 passes.** Updated
2026-09-25 to state the intermediate gates explicitly, because the earlier
wording could be read as licensing the large run too early.

Before the 1000 tasks may be consumed, all of the following must hold: the
scorer must show that the correct associated failure frontier improves
construction over matched controls; the compiler must work; CORA must actually
install the extension, rerun the same reasoner, and produce at least one
credible causal rescue on a small fixed DEV set; broader DEV work must be
finished; and the architecture, policies, budgets, ranking, two-attempt policy
and fallback must be frozen.

The 1000-task run is then a large-scale system characterization, measuring
base against task-time adaptation, pass@1 and pass@2, activation counts,
rescues, harms, runtime and the failure distribution. It is the first big run
and is not the main generalization result.

The 60 DEV evaluation tasks run after that characterization and may still
inform policy-level decisions. The 60 protected holdout tasks are not touched
until code, scorer, compiler, budgets, ranking, the two-attempt policy and the
fallback are all frozen; they are the clean internal generalization test. Only
once everything is frozen may the full 120 run together as a final local
evaluation, reporting pass@1, pass@2 and attempt-two rescues under exactly the
configuration intended for submission.

The 120 is the late generalization test, never the development loop.

| stage | data | question it answers |
|---|---|---|
| now | synthetic plus a few DEV failures | can failure produce new ASTs |
| next | synthetic plus a few DEV failures | can ASTs compile and install additively |
| first scientific pilot | small fixed DEV set | can K plus e causally rescue anything |
| broad characterization | 1000 training tasks | how often the mechanism works and what it costs |
| off-distribution development | 60 evaluation DEV | does it survive the difficulty cliff |
| freeze | none | freeze code, policy, budgets, ranking |
| held-out test | 60 evaluation HOLDOUT | honest internal generalization |
| final local evaluation | all 120, once authorized | final pass@1 and pass@2 |
| competition | Kaggle hidden test | the Accuracy criterion |

## Rules

The 1000 training tasks are not run merely because a decoder can emit trees.
The trigger is an end-to-end path: failure graph, to extension, to K plus e,
to a re-run. That run is large-scale system characterization, not the main
generalization result, and the tasks are not tuned against individually.

The historical 185 of 1000 may be compared against at that point, without
presenting a training number as a Kaggle result.

The 60 HOLDOUT tasks stay untouched until the proposer, compiler, ordinary
solver, construction budget, two-attempt policy, runtime budgets and
candidate ranking are all frozen, no further DEV-driven changes are planned,
and the evaluation plan is recorded.

Runtime readiness is established on representative permitted workloads and
extrapolated conservatively. Protected evaluation inputs are never consumed
merely to test runtime.

The earlier gate ladder is preserved in spirit: engineering and runtime
readiness; then task-local construction yielding new certified solutions;
then pass@2 above 10 percent, above 20 percent, and at or above 30 percent.
The holdout is reserved for the last three. The numerical bars may prove
unrealistic; the reservation discipline stands regardless.
