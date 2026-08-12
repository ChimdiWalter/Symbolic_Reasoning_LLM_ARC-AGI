# Resume: Cumulative Reasoning Architecture

Use this file to resume work from any interruption point.

## Environment

```bash
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
python3.11 -m pytest tests/ -q  # must show 516+ passed
```

## Architecture Overview

The project implements **cumulative, verifiable reasoning** where failure states become reusable training data. The central chain:

```
failed → near-solved stored → failure cluster formed → operator invented →
counterexamples survived → task resumed → task solved → certificate emitted
```

### Core Thesis

> "Failures are not errors; failures are training data for reasoning."

### Framing (NOT an ARC solver)

This is a **cumulative reasoning architecture** with:
- Failure-memory-driven abstraction learning
- Verifiable reasoning with active falsification
- Reasoning certificates for every accepted answer
- Near-solved trajectory memory
- Cross-domain transfer with the same reasoning engine

## Module Map

### Core Reasoning
| Module | Purpose | Lines |
|--------|---------|-------|
| `reasoning_engine.py` | DomainAdapter + StructuralReasoner + GridDomainAdapter + ReasoningMemory | 93K |
| `adaptive_loop.py` | Iterative perceive→hypothesize→test→diagnose→refine→learn loop | ~900 |
| `portfolio.py` | Multi-proposer collect-all solver portfolio | ~500 |

### Event & Memory
| Module | Purpose | Lines |
|--------|---------|-------|
| `events.py` | Event-driven audit log (26 event types, query, replay, lineage) | ~230 |
| `manifold_memory.py` | Fiber bundle + geodesic solver + curvature mismatch trigger | ~1200 |
| `near_solved_memory.py` | Near-solved boundary states + failure clustering | ~400 |

### Invention & Verification
| Module | Purpose | Lines |
|--------|---------|-------|
| `operator_invention.py` | Concept/operator mining from failure clusters | 779 |
| `active_falsifier.py` | 5 counterexample probe families | 462 |
| `certificates.py` | 17-field reasoning certificates + auditor | 446 |
| `formal_verification.py` | ProofObject + TerminationProof + ConvergenceBound + LTL | ~600 |

### Domain Adapters
| Module | Purpose |
|--------|---------|
| `domain_adapters.py` | Graph + Chess + Molecule domain adapters |
| `adapter_genesis.py` | Self-synthesizing domain adapters |
| `benchmark_generator.py` | 27-task cross-domain benchmark suite |

### Solvers (10 families)
| Solver | Key Contribution |
|--------|-----------------|
| `local_rules.py` | 36 strategies, 28 unique ARC tasks |
| `separator_decompose.py` | 13 strategies, 21 unique ARC tasks |
| `fill_solver.py` | 34 strategies, 14 unique ARC tasks |
| `crop_extract.py` | 10 strategies, 7 unique ARC tasks |
| `abstract_programs.py` | 5 strategies, 5 unique ARC tasks |
| `relation_solver.py` | 17 strategies |
| `color_solver.py` | 11 strategies |
| `object_graph.py` | 6 strategies, 3 unique ARC tasks |

## Key Scripts

### Experiments
```bash
# Memory growth curriculum (6 stages, the central experiment)
python3.11 -u scripts/run_memory_growth_curriculum.py --output-dir outputs/memory_growth

# Cross-domain transfer v2
python3.11 -u scripts/run_cross_domain_v2.py --output-dir outputs/cross_domain_v2

# Oracle candidate analysis (generation vs selection bottleneck)
python3.11 -u scripts/analyze_oracle_candidates.py --output-dir outputs/oracle_candidate_analysis

# Reasoning scaling curves
python3.11 -u scripts/analyze_reasoning_scaling.py --output-dir outputs/reasoning_scaling

# Breakthrough report
python3.11 -u scripts/generate_breakthrough_report.py --output outputs/breakthrough_gap_closure_report.md
```

### Quick Smoke Tests
```bash
# 8-task quick check (< 2 min)
python3.11 -u scripts/run_memory_growth_curriculum.py --max-tasks 8 --output-dir outputs/smoke

# Cross-domain (< 1 min)
python3.11 scripts/test_cross_domain.py
```

### SLURM
```bash
# Full cumulative reasoning evaluation (24h)
sbatch slurm/run_cumulative_reasoning.sh

# Check status
squeue -u $(whoami)
sacct -u $(whoami) --starttime $(date -d 'yesterday' +%Y-%m-%d) --format=JobID,JobName,State,Elapsed -X
```

## Current Results (2026-05-13)

| Metric | Value |
|--------|-------|
| ARC training (no DSL) | 84/1000 (8.4%) |
| ARC training (with DSL) | 95/1000 (9.5%) |
| ConceptARC | 10-12/160 (6.3-7.5%) |
| Cross-domain (graph/chess/molecule) | 5/13 correct, 0 FP |
| Reasoning engine standalone | 8/1000, 0 FP |
| Conjunction search | 4 new solves from 2 invented predicates |
| Memory system | 0 regressions, 0 FP |
| Tests | 516 passed |
| H1 structural transfer | supported |
| H2 falsification | supported (conditional) |
| H3 path repair | supported (54% recovery) |
| H4 compression | inconclusive |
| H5 integrated scientist | supported |
| H6 analogical transfer | inconclusive |

## Output Artifacts

| Directory | Contents |
|-----------|----------|
| `outputs/memory_growth/` | Curriculum summary, stage metrics, promoted tasks, events, certificates |
| `outputs/cross_domain_v2/` | Domain metrics, transfer report, transfer events |
| `outputs/oracle_candidate_analysis/` | Task diagnoses, bottleneck classification |
| `outputs/reasoning_scaling/` | Scaling data, curves, summary |
| `outputs/events/` | Event log JSONL, event summary, per-task lineages |
| `outputs/certificates/` | Reasoning certificates JSON |
| `paper/manuscript_v2.md` | Current manuscript |

## Acceptance Criteria

The implementation passes if the final report shows:

1. Previously failed tasks are stored as near-solved states.
2. Near-solved states cluster into meaningful failure modes.
3. New concepts/operators are invented from those clusters.
4. At least some invented abstractions solve held-out or previously failed tasks.
5. Active falsification reduces false-rule acceptance or false positives.
6. Some tasks are promoted from near-solved to solved.
7. Certificates are emitted for accepted answers.
8. The same reasoning engine transfers across at least two non-ARC domains.
9. Gains are separated from hand-coded solver additions.
10. All claims are stated honestly with limitations.

## What NOT to Claim

- We solved AGI
- We are the next Transformer
- Manifolds alone explain reasoning
- Formal proof of intelligence
- ARC score proves AGI

## What TO Claim

- New mechanism for cumulative, verifiable reasoning
- Failure memory creates reusable abstractions
- Near-solved tasks can later become solved
- Active falsification keeps learned abstractions honest
- Same reasoning engine transfers across domains
