"""Tiny ARC smoke evaluation runner."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .arc_adapter import (
    arc_task_to_reasoning_task,
    evaluate_arc_prediction,
    load_arc_tasks,
    predictions_to_json_records,
    summarize_arc_rows,
)
from .models import ModelConfig, build_model
from .utils import ensure_dir, set_global_seed, utc_timestamp, write_json, write_text


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        write_text(path, "")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_summary_markdown(path: Path, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# ARC Smoke Summary",
        "",
        "Boundary: ARC smoke metrics validate local loader/evaluator execution only. No ARC performance claim is made.",
        "",
        f"- rows: {summary.get('n_rows', 0)}",
        f"- tasks: {summary.get('n_tasks', 0)}",
        "",
        "## Model Means",
        "",
        "|model|n|test_pair_accuracy|test_pixel_accuracy|test_shape_accuracy|runtime_seconds|",
        "|---|---|---|---|---|---|",
    ]
    for model, metrics in sorted(dict(summary.get("by_model", {})).items()):
        lines.append(
            "|{model}|{n}|{pair:.3f}|{pixel:.3f}|{shape:.3f}|{runtime:.6f}|".format(
                model=model,
                n=int(metrics.get("n", 0)),
                pair=float(metrics.get("test_pair_accuracy_mean", 0.0)),
                pixel=float(metrics.get("test_pixel_accuracy_mean", 0.0)),
                shape=float(metrics.get("test_shape_accuracy_mean", 0.0)),
                runtime=float(metrics.get("runtime_seconds_mean", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "## Artifact Note",
            "",
            "These rows omit latent-rule recovery because ARC task files do not expose ground-truth latent programs.",
            "",
            f"Evaluated rows: {len(rows)}",
        ]
    )
    write_text(path, "\n".join(lines) + "\n")


def _write_command_log(path: Path, command: str, config_path: str | None, config: Mapping[str, Any]) -> None:
    lines = [
        "# Command Log",
        "",
        "Working directory:",
        "",
        "`/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project`",
        "",
        "Environment:",
        "",
        "```bash",
        "source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate",
        "python3.11",
        "```",
        "",
        "Command:",
        "",
        "```bash",
        command or "python3.11 scripts/run_arc_smoke.py --config <CONFIG> --output-dir <OUTPUT_DIR>",
        "```",
        "",
        f"Config path: `{config_path or '<in-memory>'}`",
        f"Run name: `{config.get('run_name', config.get('name', 'arc_smoke'))}`",
        f"Seed: `{config.get('seed', 0)}`",
        "",
        "Boundary:",
        "",
        "This is a tiny local ARC adapter smoke test, not an ARC benchmark claim.",
    ]
    write_text(path, "\n".join(lines) + "\n")


def run_arc_smoke(
    config: Mapping[str, Any],
    output_dir: str | Path = "outputs",
    command: str = "",
    config_path: str | None = None,
) -> Dict[str, Any]:
    seed = int(config.get("seed", 0))
    set_global_seed(seed)
    run_name = str(config.get("run_name", config.get("name", "arc_smoke")))
    run_dir = ensure_dir(Path(output_dir) / run_name)

    arc_root = str(config.get("arc_root", "data/arc"))
    split = str(config.get("split", "evaluation"))
    max_tasks = int(config.get("max_tasks", 3))
    model_names = list(config.get("models", ["direct_io_proxy", "transformation_library"]))
    candidate_max_depth = int(config.get("candidate_max_depth", 1))
    colors = [int(c) for c in config.get("colors", list(range(1, 10)))]
    require_solutions = bool(config.get("require_solutions", True))

    write_json(run_dir / "config.json", dict(config))
    write_json(run_dir / "seed_list.json", {"seeds": [seed]})
    _write_command_log(run_dir / "command_log.md", command=command, config_path=config_path, config=config)

    tasks = load_arc_tasks(arc_root, split=split, max_tasks=max_tasks, include_solutions=True)
    if require_solutions and not all(task.has_test_solutions for task in tasks):
        missing = [task.task_id for task in tasks if not task.has_test_solutions]
        raise ValueError(f"ARC smoke requires labeled test outputs; missing for task ids: {missing[:5]}")

    rows: List[Dict[str, Any]] = []
    prediction_records: List[Dict[str, Any]] = []
    task_records = [task.to_dict() for task in tasks]

    for task in tasks:
        reasoning_task = arc_task_to_reasoning_task(task)
        for model_name in model_names:
            model = build_model(
                model_name,
                ModelConfig(
                    candidate_max_depth=candidate_max_depth,
                    colors=colors,
                    seed=seed,
                ),
            )
            prediction = model.predict_task(reasoning_task, splits=("test",), world=None)
            row = evaluate_arc_prediction(task, prediction)
            row["seed"] = seed
            row["run_name"] = run_name
            rows.append(row)
            prediction_records.append(predictions_to_json_records(task, prediction))

    summary = summarize_arc_rows(rows)
    summary.update(
        {
            "run_name": run_name,
            "arc_root": arc_root,
            "split": split,
            "max_tasks": max_tasks,
            "models": model_names,
            "seed": seed,
        }
    )

    write_json(run_dir / "arc_tasks.json", task_records)
    write_json(run_dir / "metrics.json", rows)
    _write_csv(run_dir / "metrics.csv", rows)
    write_json(run_dir / "predictions.json", prediction_records)
    write_json(run_dir / "summary.json", summary)
    _write_summary_markdown(run_dir / "summary.md", summary, rows)
    write_json(
        run_dir / "manifest.json",
        {
            "kind": "arc_smoke",
            "run_name": run_name,
            "run_dir": str(run_dir),
            "created_at": utc_timestamp(),
            "artifacts": [
                "config.json",
                "seed_list.json",
                "command_log.md",
                "arc_tasks.json",
                "metrics.json",
                "metrics.csv",
                "predictions.json",
                "summary.json",
                "summary.md",
            ],
        },
    )
    return {"run_dir": str(run_dir), "rows": rows, "summary": summary}
