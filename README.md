# Reasoning Project

Trace-driven operator invention for abstract visual reasoning. This research
codebase implements a cumulative reasoning architecture where near-solved
failure traces are mined to invent new operators, which are validated through
leave-one-out cross-validation, active falsification, and machine-checkable
proof obligations before promotion.

## Main Results

- **4 real ARC promotions**, each verified via frozen replay audit
- **0 false positives** across all audited tasks
- **Full verification chain**: task observed -> near-solved stored -> failure clustered -> operator invented -> counterexamples survived -> task solved -> certificate emitted
- **712 tests** covering unit, integration, and smoke categories
- **Operator necessity ablation**: removing any invented operator component breaks the solve

## Architecture

The pipeline follows: ARC task -> domain adapter (perception) -> structural reasoner (hypothesis search with 81 boolean properties, LOO validation, active falsification) -> adaptive loop (iterative view switching, manifold memory retrieval, failure diagnosis) -> trace-driven operator invention (failure clustering, operator proposal, proof obligation checking, promotion gating) -> portfolio solver (multi-proposer collect-all with consensus selection). Near-solved failures are stored in boundary memory and used to invent new concepts and operators, closing the cumulative learning loop.

## Setup

```bash
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
pip install -e .
```

## Quick Validation

```bash
# Full test suite (712 tests, ~2.5 min)
python3.11 -m pytest tests/ --tb=short -q

# Promotion replay audit (4 tasks, <1s)
python3.11 scripts/audit_verified_promotions.py

# Operator necessity ablation (8 configs x 4 tasks, ~4s)
python3.11 scripts/run_operator_promotion_ablation.py

# False-positive audit
python3.11 scripts/run_final_false_positive_audit.py
```

## Key Experiments

```bash
# Full ARC-1000 trace-driven pipeline (SLURM)
sbatch slurm/run_full_arc1000_novel_pipeline.sh

# Cross-domain adaptive evaluation
python3.11 scripts/run_domain_adaptive_operator_reasoning.py --quick-smoke

# Cross-domain operator transfer
python3.11 scripts/run_cross_domain_operator_transfer.py

# Neural component audit
python3.11 scripts/audit_neural_components.py
```

## Paper

- Manuscript: `paper/manuscript_final_candidate.md`
- Paper tables: `outputs/final_paper_package/table_*.csv`
- Reproduction commands: `outputs/final_paper_package/reproduction_commands.md`
- Frozen verified state: `outputs/final_paper_package/frozen_verified_state/`

## Layout

```
src/reasoning_project/   Package code (65+ modules)
tests/                   Unit and integration tests (712 tests)
scripts/                 CLI entry points for experiments and analysis
configs/                 JSON experiment configurations
data/                    ARC-AGI files and cached datasets
slurm/                   SLURM batch scripts
outputs/                 Generated experiment artifacts
paper/                   Manuscript draft and section files
docs/                    Architecture, quickstart, module reference
```

## Documentation

- `docs/QUICKSTART.md` -- quick-start guide
- `docs/MODULE_REFERENCE.md` -- per-module reference
- `docs/ARCHITECTURE.md` -- system architecture
- `claim_traceability.md` -- maps every claim to implementation and artifact
- `limitations.md` -- honest accounting of system boundaries
- `results_summary.md` -- detailed evidence for each hypothesis
- `NEXT_STEPS.md` -- active roadmap and completed milestones
