# Quick Start

## Setup

```bash
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
pip install -e .
```

Verify: `python3.11 --version` should report Python 3.11.x.

## Run Tests

```bash
python3.11 -m pytest tests/ -q
```

Expected: 712 passed. All tests should pass with zero failures.

## Reproduce Main Results

```bash
# Verify all 4 real ARC promotions replay correctly
python3.11 scripts/audit_verified_promotions.py        # 4/4 promotions verified

# Confirm each operator is necessary (removing it breaks the solve)
python3.11 scripts/run_operator_promotion_ablation.py  # operator necessity ablation

# Confirm zero false positives across all audited tasks
python3.11 scripts/run_final_false_positive_audit.py   # 0 FP audit

# Full pipeline integrity check
python3.11 scripts/audit_full_reasoning_pipeline.py    # all stages pass
```

## Full ARC-1000 Experiment

```bash
sbatch slurm/run_full_arc1000_novel_pipeline.sh
```

Monitor: `squeue -u $USER`. Results appear in `outputs/` upon completion.

## Cross-Domain Evaluation

```bash
# Quick smoke test (<60s)
python3.11 scripts/run_domain_adaptive_operator_reasoning.py --quick-smoke

# Full evaluation (10 tasks per domain)
python3.11 scripts/run_domain_adaptive_operator_reasoning.py --max-tasks-per-domain 10

# Operator transfer across domains
python3.11 scripts/run_cross_domain_operator_transfer.py
```

## Neural Component Audit

```bash
python3.11 scripts/audit_neural_components.py
```

## Key Output Locations

```
outputs/final_paper_package/                    -- all paper artifacts
paper/manuscript_final_candidate.md             -- manuscript
outputs/final_paper_package/frozen_verified_state/  -- frozen baseline
outputs/final_paper_package/table_*.csv         -- paper tables
outputs/final_paper_package/reproduction_commands.md -- full reproduction guide
```

## Further Reading

- `README.md` -- project overview and main results
- `docs/MODULE_REFERENCE.md` -- per-module API reference
- `docs/ARCHITECTURE.md` -- system architecture
- `claim_traceability.md` -- claim-to-artifact mapping
- `limitations.md` -- system boundaries
- `results_summary.md` -- detailed hypothesis evidence
