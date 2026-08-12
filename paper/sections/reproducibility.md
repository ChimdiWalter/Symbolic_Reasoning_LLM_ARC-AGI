# Reproducibility Statement

The repository includes fixed configs, seed lists, command logs, run states, JSON summaries, CSV metrics, and markdown summaries. Key restart commands are recorded in `RESUME.md` and process details in `PROCESS_LOG.md`.

Primary commands:

```bash
python3.11 scripts/check_exactness.py --output-dir outputs/exactness
python3.11 scripts/run_experiment.py --config configs/paper_breadth_smoke.json --output-dir outputs --resume
python3.11 scripts/analyze_h4_compression.py --run-dir outputs/paper_breadth_smoke
python3.11 scripts/analyze_h4_sweep.py --sweep-dir outputs/paper_breadth_validation_5seed_sweep
python3.11 scripts/run_seed_sweep.py --config configs/h2_family_validation.json --output-dir outputs --sweep-name h2_family_validation_10seed_sweep --seeds 1300 1301 1302 1303 1304 1305 1306 1307 1308 1309
python3.11 scripts/analyze_h2_family_balance.py --sweep-dir outputs/h2_family_validation_10seed_sweep --max-examples 40
python3.11 scripts/analyze_sweep_failures.py --sweep-dir outputs/h2_family_validation_10seed_sweep --contrast proposer_falsifier_minus_proposer_only --metric false_rule_accepted
python3.11 scripts/run_seed_sweep.py --config configs/paper_breadth_validation.json --output-dir outputs --sweep-name paper_breadth_validation_5seed_sweep --seeds 2030 2031 2032 2033 2034
python3.11 scripts/run_arc_diagnostic.py --config configs/arc_diagnostic_eval.json --output-dir outputs
python3.11 scripts/audit_arc_agi2.py --arc-root data/arc --output-dir outputs/arc_status
python3.11 scripts/train_grid_jepa.py --config configs/grid_jepa_smoke.json --output-dir outputs/neural
python3.11 scripts/eval_grid_jepa.py --config configs/grid_jepa_eval_smoke.json --checkpoint outputs/neural/grid_jepa_smoke/checkpoint.pt --output-dir outputs/neural
python3.11 scripts/train_program_ranker.py --config configs/program_ranker_smoke.json --output-dir outputs/neural
python3.11 scripts/train_program_ranker.py --config configs/program_ranker_jepa_smoke.json --output-dir outputs/neural
python3.11 scripts/run_arc_refinement.py --config configs/arc_refinement_smoke.json --output-dir outputs/arc_refinement
python3.11 scripts/analyze_reasoning_manifold.py --config configs/reasoning_manifold_smoke.json
python3.11 scripts/build_submission_package.py --repo-root /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project --breadth-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep --h2-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/h2_family_validation_10seed_sweep --h4-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment
python3.11 -m pytest
```

Latest validation recorded in `RUN_HISTORY.md`: the full test suite now passes with 42 tests, and the neural smoke path writes config snapshots, command logs, seed lists, budget logs, manifests, and restart instructions under `outputs/neural` and `outputs/arc_refinement`.
