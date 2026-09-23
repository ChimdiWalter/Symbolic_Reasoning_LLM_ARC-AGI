# Real-engine event mapping, 2026-09-23

Every emitted outcome name is an EXISTING TraceObserver name used at a real
engine transition whose semantics match. No name was redefined, and no second
observer schema or graph representation was created.

Emission is through `geocat_arc/object_reasoning/_trace_hook.py`, which is
inert when no sink is installed.

## Emitted

| outcome | real-engine transition | file |
|---|---|---|
| `typed` | a delta group is formed and enters rule induction: members and delta type are fixed, parameters are not yet fitted | `inducer.py` `_induce_rules` |
| `slot_fit_failed` | `_induce_action_for_group` returned None for that group, recorded by the engine as `FailureStage.PARAMETER` | `inducer.py` `_induce_rules` |
| `slot_fit_ok` | selector and action both induced; a complete `ObjectRule` exists with fitted parameter expressions | `inducer.py` `_induce_rules` |
| `executed_not_exact` | the engine built its partially explaining `ObjectProgram` at the failure branch and is about to discard it; non-exact by construction | `inducer.py` `_attempt_from_rules` |
| `exact` | an assembled program reproduced every demonstration under `_train_perfect` | `inducer.py` `assemble_programs` |

`executed_not_exact` is also emitted in `assemble_programs` for any assembled
candidate that is not train-perfect. On the audited tasks that branch is
rarely reached, because the engine assembles a program only when no group
failed. The partial-program site is where real near misses actually appear.

## Not emitted, reported rather than redefined

| name | why no truthful counterpart |
|---|---|
| `typecheck_failed` | the object grammar constructs only well-typed rules from typed expression enumeration, so there is no program-level typecheck rejection to observe |

## Real-engine transition with no existing name

| transition | note |
|---|---|
| selector induction returned None (`failures[gkey] = "selector"`) | a genuine engine state that none of the six existing outcome names describes. Deliberately left unnamed rather than relabelled onto `typecheck_failed`. |

## Fitted programs, not skeletons

Every event after fitting carries the fitted, executable object, serialized
through the engine's own `to_dict()`: registry names and arguments only, no
closures, no grids, no test data. The operator name in the recorded AST is
the transformation vocabulary the candidate actually used, so the frontier
records what the reasoning reached for.

## Observational guarantee

The hook is a single attribute load when no sink is installed. In
`assemble_programs` the original train-perfect computation is left
byte-identical and the trace runs as a separate pass. Candidate ordering,
search depth, parameter fitting, pruning, acceptance, verifier rules,
budgets, ranking and language contents are unchanged. Proved by
`tests/test_engine_trace_repair.py::test_observation_does_not_change_the_search_result`.
