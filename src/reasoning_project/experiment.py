"""Resumable end-to-end experiment runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping

from .evaluation import evaluate_prediction
from .generators import HiddenRuleWorld, generate_suite, save_suite
from .models import ModelConfig, build_model
from .reporting import write_manuscript, write_reports
from .utils import configure_matplotlib_cache, ensure_dir, read_json, set_global_seed, utc_timestamp, write_json


DEFAULT_MODELS = [
    "direct_io_proxy",
    "object_centric",
    "transformation_library",
    "proposer_only",
    "proposer_falsifier",
    "compression_selector",
    "path_repair",
    "integrated_scientist",
]


def _load_state(path: Path) -> Dict[str, Any]:
    if path.exists():
        return read_json(path)
    return {"completed_models": [], "rows": [], "predictions": [], "started_at": utc_timestamp()}


def run_experiment(config: Mapping[str, Any], output_dir: str | Path, resume: bool = False) -> Dict[str, Any]:
    run_name = str(config.get("run_name", config.get("name", "run")))
    run_dir = ensure_dir(Path(output_dir) / run_name)
    configure_matplotlib_cache(run_dir)
    set_global_seed(int(config.get("seed", 0)))
    write_json(run_dir / "config.json", dict(config))
    write_json(
        run_dir / "resume_instructions.json",
        {
            "kind": "experiment_run",
            "run_name": run_name,
            "run_dir": str(run_dir),
            "resume_command": f"python3.11 scripts/run_experiment.py --config {run_dir / 'config.json'} --output-dir {Path(output_dir)} --resume",
            "portable_resume_command": "python3.11 scripts/run_experiment.py --config <CONFIG_PATH> --output-dir <OUTPUT_DIR> --resume",
            "checkpoint_file": str(run_dir / "run_state.json"),
            "created_at": utc_timestamp(),
        },
    )

    state_path = run_dir / "run_state.json"
    state = _load_state(state_path) if resume else {"completed_models": [], "rows": [], "predictions": [], "started_at": utc_timestamp()}

    suite = generate_suite(config)
    save_suite(suite, run_dir / "dataset.json")

    colors = [int(c) for c in config.get("colors", [1, 2, 3, 4, 5, 6, 7, 8])]
    model_names = list(config.get("models", DEFAULT_MODELS))
    interactive = bool(config.get("interactive_falsification", False))
    oracle_probes = int(config.get("oracle_probes", 0)) if interactive else 0
    candidate_max_depth = int(config.get("candidate_max_depth", 1))
    falsifier_candidate_limit = int(config.get("falsifier_candidate_limit", 40))
    fixed_falsifier_budget = bool(config.get("fixed_falsifier_budget", False))
    budget_match_falsifier = bool(config.get("budget_match_falsifier", False))
    learned_hidden_dim = int(config.get("learned_hidden_dim", 64))
    learned_max_iter = int(config.get("learned_max_iter", 300))
    learned_alpha = float(config.get("learned_alpha", 1e-4))

    rows: List[Dict[str, Any]] = list(state.get("rows", []))
    predictions_json: List[Dict[str, Any]] = list(state.get("predictions", []))
    completed = set(state.get("completed_models", []))

    for model_name in model_names:
        if resume and model_name in completed:
            continue
        model_config = ModelConfig(
            candidate_max_depth=candidate_max_depth,
            colors=colors,
            oracle_probes=oracle_probes,
            seed=int(config.get("seed", 0)),
            falsifier_candidate_limit=falsifier_candidate_limit,
            fixed_falsifier_budget=fixed_falsifier_budget,
            budget_match_falsifier=budget_match_falsifier,
            learned_hidden_dim=learned_hidden_dim,
            learned_max_iter=learned_max_iter,
            learned_alpha=learned_alpha,
        )
        model = build_model(model_name, config=model_config)
        for task_index, task in enumerate(suite.tasks):
            world = HiddenRuleWorld(task, seed=int(config.get("seed", 0)) + task_index) if interactive else None
            pred = model.predict_task(task, splits=("val", "test", "ood"), world=world)
            row = evaluate_prediction(task, pred)
            row["seed"] = int(config.get("seed", 0))
            row["run_name"] = run_name
            rows.append(row)
            predictions_json.append(pred.to_dict())
        completed.add(model_name)
        state = {
            "completed_models": sorted(completed),
            "rows": rows,
            "predictions": predictions_json,
            "started_at": state.get("started_at", utc_timestamp()),
            "updated_at": utc_timestamp(),
        }
        write_json(state_path, state)
        write_json(run_dir / "results.json", rows)
        write_json(run_dir / "predictions.json", predictions_json)

    report_info = write_reports(run_dir, rows, config)
    write_manuscript(Path("paper"))
    write_json(run_dir / "manifest.json", {
        "run_name": run_name,
        "run_dir": str(run_dir),
        "artifacts": [
            "config.json",
            "resume_instructions.json",
            "dataset.json",
            "run_state.json",
            "results.json",
            "predictions.json",
            "metrics.csv",
            "summary.json",
            "hypothesis_verdicts.json",
            "figures/accuracy_by_model.png",
            "figures/rule_recovery_by_model.png",
            "tables/ablation_summary.md",
            "reports/results_summary.md",
            "reports/limitations.md",
            "reports/methods.md",
            "reports/experiments.md",
            "reports/appendix.md",
            "reports/failure_cases.md",
        ],
        "completed_at": utc_timestamp(),
    })
    return {"run_dir": str(run_dir), "rows": rows, **report_info}
