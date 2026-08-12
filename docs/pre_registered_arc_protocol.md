# Pre-Registered ARC Reasoning Evaluation Protocol

## Version
- Protocol version: 1.0
- Date: 2026-05-08
- Status: Active

## Datasets and Splits

| Dataset | Count | Usage | Labels Available |
|---------|-------|-------|-----------------|
| ARC Training | 1000 tasks | Solver development, library learning, taxonomy, routing training | Yes (input+output for train+test) |
| ARC Evaluation | 120 tasks | Primary held-out evaluation | Yes (local solutions file) |
| ARC Test | 240 tasks | Prediction-only (no labels) | No |
| Synthetic families | ~19 families | H1-H5 hypothesis testing, ablation | Yes (generated with known rules) |
| Other reasoning (future) | TBD | Transfer validation | TBD |

## Allowed and Disallowed Data

### Allowed
- ARC Training: use for solver development, program library construction, taxonomy building, router training, parameter tuning
- ARC Evaluation: use for final metric reporting only; no hyperparameter tuning after first evaluation run
- Synthetic tasks: use freely for development and hypothesis testing

### Disallowed
- ARC Test outputs: never use for training, routing, model selection, or task selection
- ARC Evaluation: do not use for any form of selection, tuning, or architecture search
- Do not select solvable evaluation tasks post-hoc and claim they represent capability
- No test-time use of ground-truth outputs

## Candidate Budgets

| Solver | Max Candidates | Max Depth | Max Runtime/Task |
|--------|---------------|-----------|-----------------|
| DSL enumeration | 4,947 (arc_expanded depth-2) | 2 | 120s |
| CEGIS | 1000 refinement steps | 3 | 300s |
| Local-rule synthesis | 500 rules | N/A (neighborhoods) | 60s |
| Object-graph rewrite | 200 rewrites | 2 | 120s |
| Portfolio (total) | sum of above | varies | 600s |

## Runtime Budgets

- CPU smoke: 10 minutes per experiment
- CPU full: 4 hours per experiment
- GPU full: 24 hours per experiment (if available)
- Per-task hard timeout: 600 seconds

## Seeds
- Minimum 3 seeds for smoke/diagnostic
- Minimum 5 seeds for reported results
- Minimum 10 seeds for H2 conditional claims
- Seeds: 2052, 2053, 2054, 2055, 2056, 2057, 2058, 2059, 2060, 2061

## Solver Families

1. `transformation_library` — DSL enumeration + exact match
2. `proposer_falsifier` — DSL + counterexample filtering
3. `compression_selector` — DSL + MDL selection
4. `rule_induction` — pixel/grid local-rule learning
5. `cegis` — counterexample-guided inductive synthesis (planned)
6. `local_rule_synthesis` — extended neighborhood rule search (planned)
7. `object_graph_rewrite` — object-level graph rewrite (planned)
8. `portfolio` — routing across solver families (planned)
9. `neural_ranker` — learned program ranking
10. `integrated_scientist` — full pipeline

## Metrics

### Primary
- **Exact solve rate**: fraction of tasks where all test outputs match exactly
- **Pass@k**: fraction of tasks where at least one of top-k candidates is correct (k=1,2,5)

### Secondary
- **Pixel accuracy**: mean fraction of correct pixels across test outputs
- **DSL coverage**: fraction of tasks with at least one train-consistent candidate
- **Candidate rank**: rank of first correct program in candidate list (lower is better)
- **Runtime**: wall-clock seconds per task
- **Candidate count**: total candidates evaluated per task

### Diagnostic
- **Repair success rate**: fraction of corrupted hypotheses successfully repaired (H3)
- **Counterexample count**: mean counterexamples needed before convergence (CEGIS)
- **Abstraction reuse rate**: fraction of held-out tasks using learned macros (library)
- **Transfer gap**: synthetic exact solve minus ARC exact solve
- **Per-taxonomy-category solve rate**: broken out by task type

## Stopping Criteria

- A solver family is declared useful if it solves >=1 previously-unsolved ARC task
- A solver family is declared dominant in a category if it solves >50% of tasks in that category
- H1-H5 support requires paired statistical comparison across seeds

## What Counts as Support

| Hypothesis | Support Criterion |
|-----------|-------------------|
| H1 (structural transfer) | DSL-based solver > direct proxy on ARC exact solve, p<0.05 paired |
| H2 (falsification) | proposer_falsifier > proposer_only on false-rule rejection in ambiguity strata |
| H3 (repairability) | path_repair recovers from corruption > random baseline |
| H4 (compression) | compression_selector aligns with exact DSL minimum AND outperforms on held-out |
| H5 (integrated) | portfolio/integrated > best single solver on exact solve, statistically |

## What Counts as Failure

- H fails if paired delta is <=0 or not statistically significant after 10 seeds
- A solver family fails if it adds zero unique solves beyond existing solvers
- Neural transfer fails if ARC exact solve = 0 after full GPU training

## Leakage Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Test output leakage | Never load test solutions; no `include_solutions=True` for test split |
| Post-hoc task selection | All solvable subsets labeled as "coverage diagnostic" |
| Evaluation split tuning | Protocol freeze: no architecture/hyperparameter changes after first eval run |
| Router trained on eval | Router uses only training split labels |
| Library learned from eval | Library induction uses only training split |

## Reporting Requirements

- Every claim maps to an artifact path
- Every artifact is reproducible via config + seed
- Solvable-subset results are labeled as coverage diagnostics
- General ARC claims require evaluation split confirmation
- No ARC-AGI or AGI language without >20% evaluation solve rate
