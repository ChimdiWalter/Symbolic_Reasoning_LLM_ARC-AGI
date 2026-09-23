# Data-usage order, recorded 2026-09-23

Binding order for which data may be consumed at which stage. The September
delivery plan supersedes the earlier August plan, which wanted early
full-set measurements.

    proposer -> compiler -> small DEV pilot -> freeze mechanism
      -> 1000-task training characterization -> 60 DEV evaluation
      -> freeze final policy -> 60 HOLDOUT -> final 120, once authorized

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
