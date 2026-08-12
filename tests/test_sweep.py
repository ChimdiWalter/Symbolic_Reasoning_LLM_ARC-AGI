from pathlib import Path

from reasoning_project.h2_analysis import write_h2_family_balanced_analysis
from reasoning_project.sweep import run_seed_sweep


def test_seed_sweep_writes_aggregate_artifacts(tmp_path: Path):
    config = {
        "name": "tiny_sweep",
        "run_name": "tiny_sweep",
        "families": ["reflection"],
        "tasks_per_family": 1,
        "examples_per_split": {"train": 2, "val": 1, "test": 1, "ood": 1},
        "grid_size": 6,
        "ood_grid_size": 8,
        "object_count": 2,
        "ood_object_count": 3,
        "colors": [1, 2, 3, 4, 5, 6, 7, 8],
        "candidate_max_depth": 1,
        "interactive_falsification": False,
        "models": ["proposer_only", "proposer_falsifier"],
    }
    result = run_seed_sweep(config, seeds=[1, 2], output_dir=tmp_path, sweep_name="tiny_seed_sweep")
    sweep_dir = Path(result["sweep_dir"])
    assert (sweep_dir / "seed_model_metrics.csv").stat().st_size > 0
    assert (sweep_dir / "sweep_summary.json").stat().st_size > 0
    assert (sweep_dir / "sweep_summary.md").stat().st_size > 0
    assert (sweep_dir / "paired_contrasts.json").stat().st_size > 0
    assert (sweep_dir / "paired_contrasts.md").stat().st_size > 0
    assert (sweep_dir / "paired_seed_deltas.csv").stat().st_size > 0
    assert (sweep_dir / "stratified_seed_model_metrics.csv").stat().st_size > 0
    assert (sweep_dir / "stratified_paired_contrasts.json").stat().st_size > 0
    assert (sweep_dir / "stratified_paired_contrasts.md").stat().st_size > 0
    assert (sweep_dir / "stratified_paired_seed_deltas.csv").stat().st_size > 0
    assert "proposer_falsifier_minus_proposer_only" in result["contrasts"]
    contrast = result["contrasts"]["proposer_falsifier_minus_proposer_only"]
    assert "ci_low" in contrast["test_pair_accuracy"]
    assert "ci_high" in contrast["test_pair_accuracy"]
    assert "effect_size_dz" in contrast["test_pair_accuracy"]
    assert result["paired_delta_records"]
    assert result["stratified_delta_records"]
    assert any(
        key.startswith("task_family=reflection::proposer_falsifier_minus_proposer_only")
        for key in result["stratified_contrasts"]
    )
    assert len(result["seed_model_records"]) == 4
    h2_report = write_h2_family_balanced_analysis(sweep_dir)
    assert h2_report["contrast"] == "proposer_falsifier_minus_proposer_only"
    assert (sweep_dir / "family_balanced_h2_analysis.md").stat().st_size > 0
    assert (sweep_dir / "accepted_false_rule_examples.json").stat().st_size > 0
    assert (sweep_dir / "falsifier_counterexample_traces.json").stat().st_size > 0
