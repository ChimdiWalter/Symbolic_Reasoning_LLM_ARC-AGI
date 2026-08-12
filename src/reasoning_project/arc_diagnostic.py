"""Bounded local ARC diagnostic evaluation.

This module treats ARC as an external-validity diagnostic. It reports output
accuracy and runtime/budget fields only; ARC latent programs are not available.
"""

from __future__ import annotations

import csv
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from .arc_adapter import (
    ARCTask,
    arc_task_to_reasoning_task,
    evaluate_arc_prediction,
    load_arc_tasks,
    predictions_to_json_records,
    summarize_arc_rows,
)
from .models import ModelConfig, build_model
from .schemas import grid_to_list
from .utils import ensure_dir, set_global_seed, utc_timestamp, write_json, write_text


ARC_CONTRAST_PAIRS = [
    ("learned_task_mlp", "direct_io_proxy"),
    ("transformation_library", "learned_task_mlp"),
    ("transformation_library", "direct_io_proxy"),
    ("proposer_falsifier", "direct_io_proxy"),
    ("integrated_scientist", "direct_io_proxy"),
    ("integrated_scientist", "transformation_library"),
    ("integrated_scientist", "proposer_falsifier"),
]


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


def _bootstrap_ci(values: Sequence[float], seed: int = 0, n_bootstrap: int = 2000) -> Dict[str, float]:
    values = [float(value) for value in values]
    if not values:
        return {"low": 0.0, "high": 0.0}
    if len(values) == 1:
        return {"low": values[0], "high": values[0]}
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    samples = [float(np.mean(rng.choice(arr, size=len(arr), replace=True))) for _ in range(n_bootstrap)]
    return {"low": float(np.percentile(samples, 2.5)), "high": float(np.percentile(samples, 97.5))}


def _stable_seed(*parts: Any) -> int:
    text = "::".join(str(part) for part in parts)
    return sum((idx + 1) * ord(char) for idx, char in enumerate(text)) % (2**32)


def _grid_shapes(task: ARCTask) -> List[tuple[int, int]]:
    shapes: List[tuple[int, int]] = []
    for example in [*task.train, *task.test]:
        shapes.append(tuple(int(v) for v in example.input_grid.shape))
        if example.output_grid is not None:
            shapes.append(tuple(int(v) for v in example.output_grid.shape))
    return shapes


def arc_task_profile(task: ARCTask) -> Dict[str, Any]:
    shapes = _grid_shapes(task)
    max_dim = max(max(shape) for shape in shapes) if shapes else 0
    max_cells = max(shape[0] * shape[1] for shape in shapes) if shapes else 0
    if max_dim <= 10 and max_cells <= 100:
        bucket = "small"
    elif max_dim <= 20 and max_cells <= 400:
        bucket = "medium"
    else:
        bucket = "large"
    return {
        "arc_task_id": task.task_id,
        "arc_split": task.split,
        "shape_bucket": bucket,
        "max_dim": int(max_dim),
        "max_cells": int(max_cells),
        "n_train": len(task.train),
        "n_test": len(task.test),
        "has_test_solutions": bool(task.has_test_solutions),
        "train_shapes": [list(example.input_grid.shape) for example in task.train],
        "test_shapes": [list(example.input_grid.shape) for example in task.test],
        "inferred_task_type": "unknown_arc_grid_task",
    }


def select_arc_tasks(
    tasks: Sequence[ARCTask],
    max_tasks: int | None = None,
    max_tasks_per_bucket: int | None = None,
) -> List[ARCTask]:
    """Select a deterministic stratified ARC subset by coarse shape bucket."""

    ordered = sorted(tasks, key=lambda task: task.task_id)
    if max_tasks_per_bucket is None:
        return ordered if max_tasks is None else ordered[: int(max_tasks)]

    by_bucket: Dict[str, List[ARCTask]] = defaultdict(list)
    for task in ordered:
        by_bucket[str(arc_task_profile(task)["shape_bucket"])].append(task)
    selected: List[ARCTask] = []
    for bucket in ["small", "medium", "large"]:
        selected.extend(by_bucket.get(bucket, [])[: int(max_tasks_per_bucket)])
    selected = sorted(selected, key=lambda task: task.task_id)
    if max_tasks is not None:
        selected = selected[: int(max_tasks)]
    return selected


def _seed_model_records(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple[int, str], List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if float(row.get("skipped", 0.0)):
            continue
        grouped[(int(row["seed"]), str(row["model_name"]))].append(row)
    metric_keys = [
        "test_pair_accuracy",
        "test_pixel_accuracy",
        "test_exact_task_accuracy",
        "test_shape_accuracy",
        "runtime_seconds",
        "candidate_program_count",
        "candidates_scored",
        "candidates_falsified",
        "oracle_probe_budget",
        "oracle_probes_used",
        "passive_checks_used",
        "runtime_cap_exceeded",
    ]
    records: List[Dict[str, Any]] = []
    for (seed, model), group in sorted(grouped.items()):
        record: Dict[str, Any] = {"seed": seed, "model_name": model, "n_task_rows": len(group)}
        for key in metric_keys:
            record[key] = float(np.mean([float(row.get(key, 0.0)) for row in group])) if group else 0.0
        records.append(record)
    return records


def _paired_contrasts(records: Sequence[Mapping[str, Any]]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    by_seed_model: Dict[int, Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for record in records:
        by_seed_model[int(record["seed"])][str(record["model_name"])] = record

    metric_keys = [
        "test_pair_accuracy",
        "test_pixel_accuracy",
        "test_exact_task_accuracy",
        "test_shape_accuracy",
        "runtime_seconds",
    ]
    contrasts: Dict[str, Any] = {}
    deltas: List[Dict[str, Any]] = []
    for left, right in ARC_CONTRAST_PAIRS:
        seeds = [seed for seed, models in sorted(by_seed_model.items()) if left in models and right in models]
        if not seeds:
            continue
        key = f"{left}_minus_{right}"
        contrast: Dict[str, Any] = {"left": left, "right": right, "n": len(seeds)}
        for metric in metric_keys:
            diffs = [
                float(by_seed_model[seed][left].get(metric, 0.0))
                - float(by_seed_model[seed][right].get(metric, 0.0))
                for seed in seeds
            ]
            ci = _bootstrap_ci(diffs, seed=_stable_seed(key, metric))
            mean_delta = float(np.mean(diffs)) if diffs else 0.0
            std_delta = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
            contrast[metric] = {
                "mean_delta": mean_delta,
                "std_delta": std_delta,
                "ci_low": ci["low"],
                "ci_high": ci["high"],
                "effect_size_dz": None if len(diffs) < 2 or std_delta < 1e-12 else mean_delta / std_delta,
            }
            for seed, diff in zip(seeds, diffs):
                deltas.append(
                    {
                        "contrast": key,
                        "seed": seed,
                        "metric": metric,
                        "left_model": left,
                        "right_model": right,
                        "left_value": float(by_seed_model[seed][left].get(metric, 0.0)),
                        "right_value": float(by_seed_model[seed][right].get(metric, 0.0)),
                        "delta": float(diff),
                    }
                )
        contrasts[key] = contrast
    return contrasts, deltas


def _summarize_by_shape_bucket(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if float(row.get("skipped", 0.0)):
            continue
        grouped[(str(row.get("shape_bucket", "unknown")), str(row["model_name"]))].append(row)
    out: Dict[str, Any] = {}
    for (bucket, model), group in sorted(grouped.items()):
        out.setdefault(bucket, {})[model] = {
            "n": len(group),
            "test_pair_accuracy_mean": float(np.mean([float(row.get("test_pair_accuracy", 0.0)) for row in group])),
            "test_pixel_accuracy_mean": float(np.mean([float(row.get("test_pixel_accuracy", 0.0)) for row in group])),
            "test_exact_task_accuracy_mean": float(
                np.mean([float(row.get("test_exact_task_accuracy", 0.0)) for row in group])
            ),
        }
    return out


def _write_paired_markdown(path: Path, contrasts: Mapping[str, Any]) -> None:
    columns = ["contrast", "n", "pair_delta", "pair_ci", "pixel_delta", "exact_task_delta", "runtime_delta"]
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for key, data in sorted(contrasts.items()):
        pair = dict(data.get("test_pair_accuracy", {}))
        pixel = dict(data.get("test_pixel_accuracy", {}))
        exact = dict(data.get("test_exact_task_accuracy", {}))
        runtime = dict(data.get("runtime_seconds", {}))
        lines.append(
            "|{key}|{n}|{pair_delta:.3f}|[{ci_low:.3f}, {ci_high:.3f}]|{pixel_delta:.3f}|{exact_delta:.3f}|{runtime_delta:.6f}|".format(
                key=key,
                n=int(data.get("n", 0)),
                pair_delta=float(pair.get("mean_delta", 0.0)),
                ci_low=float(pair.get("ci_low", 0.0)),
                ci_high=float(pair.get("ci_high", 0.0)),
                pixel_delta=float(pixel.get("mean_delta", 0.0)),
                exact_delta=float(exact.get("mean_delta", 0.0)),
                runtime_delta=float(runtime.get("mean_delta", 0.0)),
            )
        )
    write_text(path, "\n".join(lines) + "\n")


def _write_summary_markdown(
    path: Path,
    summary: Mapping[str, Any],
    contrasts: Mapping[str, Any],
    failure_records: Sequence[Mapping[str, Any]],
) -> None:
    lines = [
        "# ARC Diagnostic Summary",
        "",
        "Boundary: this is a bounded local ARC external-validity diagnostic. It is not an ARC benchmark or leaderboard claim.",
        "",
        f"- rows: {summary.get('n_rows', 0)}",
        f"- tasks: {summary.get('n_tasks', 0)}",
        f"- seeds: {summary.get('seeds', [])}",
        f"- skipped rows: {summary.get('skipped_rows', 0)}",
        "",
        "## Model Means",
        "",
        "|model|n|test_pair_accuracy|test_pixel_accuracy|test_exact_task_accuracy|runtime_seconds|candidate_program_count|",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, metrics in sorted(dict(summary.get("by_model", {})).items()):
        lines.append(
            "|{model}|{n}|{pair:.3f}|{pixel:.3f}|{exact:.3f}|{runtime:.6f}|{candidates:.1f}|".format(
                model=model,
                n=int(metrics.get("n", 0)),
                pair=float(metrics.get("test_pair_accuracy_mean", 0.0)),
                pixel=float(metrics.get("test_pixel_accuracy_mean", 0.0)),
                exact=float(metrics.get("test_exact_task_accuracy_mean", 0.0)),
                runtime=float(metrics.get("runtime_seconds_mean", 0.0)),
                candidates=float(metrics.get("candidate_program_count_mean", 0.0)),
            )
        )
    lines.extend(["", "## Paired Seed Contrasts", ""])
    for key, data in sorted(contrasts.items()):
        pair = dict(data.get("test_pair_accuracy", {}))
        lines.append(
            "- `{}`: test_pair_accuracy delta {:.3f}, 95% bootstrap CI [{:.3f}, {:.3f}], n={}.".format(
                key,
                float(pair.get("mean_delta", 0.0)),
                float(pair.get("ci_low", 0.0)),
                float(pair.get("ci_high", 0.0)),
                int(data.get("n", 0)),
            )
        )
    lines.extend(
        [
            "",
            "## Failure Sample",
            "",
            f"Qualitative failure records written: {len(failure_records)}",
            "",
            "Interpretation: ARC diagnostics test transfer of the implemented mechanisms to local ARC-formatted tasks. They do not expose latent programs, so structural rule recovery cannot be scored directly.",
        ]
    )
    write_text(path, "\n".join(lines) + "\n")


def _failure_markdown(path: Path, failure_records: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# ARC Qualitative Failure Cases",
        "",
        "Failures are task/model rows with imperfect test-pair accuracy or execution errors. Grid contents are in `qualitative_failures.json`.",
        "",
        "|seed|model|task|shape_bucket|test_pair_accuracy|predicted_program|error|",
        "|---:|---|---|---|---:|---|---|",
    ]
    for record in failure_records[:50]:
        lines.append(
            "|{seed}|{model}|{task}|{bucket}|{acc:.3f}|{program}|{error}|".format(
                seed=int(record.get("seed", 0)),
                model=record.get("model_name", ""),
                task=record.get("arc_task_id", ""),
                bucket=record.get("shape_bucket", ""),
                acc=float(record.get("test_pair_accuracy", 0.0)),
                program=str(record.get("predicted_program", ""))[:80],
                error=str(record.get("error", ""))[:80],
            )
        )
    write_text(path, "\n".join(lines) + "\n")


def run_arc_diagnostic(
    config: Mapping[str, Any],
    output_dir: str | Path = "outputs",
    command: str = "",
    config_path: str | None = None,
) -> Dict[str, Any]:
    run_name = str(config.get("run_name", config.get("name", "arc_diagnostic")))
    run_dir = ensure_dir(Path(output_dir) / run_name)
    arc_root = str(config.get("arc_root", "data/arc"))
    split = str(config.get("split", "evaluation"))
    seeds = [int(seed) for seed in config.get("seeds", [int(config.get("seed", 0))])]
    max_tasks = config.get("max_tasks")
    max_tasks_per_bucket = config.get("max_tasks_per_bucket")
    require_solutions = bool(config.get("require_solutions", True))
    model_names = list(
        config.get(
            "models",
            ["direct_io_proxy", "transformation_library", "proposer_falsifier", "integrated_scientist"],
        )
    )
    candidate_max_depth = int(config.get("candidate_max_depth", 1))
    colors = [int(c) for c in config.get("colors", list(range(1, 10)))]
    runtime_cap_seconds = float(config.get("runtime_cap_seconds", 30.0))
    failure_limit_per_model = int(config.get("qualitative_failures_per_model", 5))
    learned_hidden_dim = int(config.get("learned_hidden_dim", 64))
    learned_max_iter = int(config.get("learned_max_iter", 300))
    learned_alpha = float(config.get("learned_alpha", 1e-4))

    write_json(run_dir / "config.json", dict(config))
    write_json(run_dir / "seed_list.json", {"seeds": seeds})
    write_json(
        run_dir / "resume_instructions.json",
        {
            "kind": "arc_diagnostic",
            "run_name": run_name,
            "run_dir": str(run_dir),
            "resume_command": (
                f"python3.11 scripts/run_arc_diagnostic.py --config {config_path or '<CONFIG>'} "
                f"--output-dir {Path(output_dir)}"
            ),
            "created_at": utc_timestamp(),
        },
    )
    write_text(
        run_dir / "command_log.md",
        "\n".join(
            [
                "# Command Log",
                "",
                "Working directory: `/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project`",
                "",
                "Environment: `source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate`; `python3.11`",
                "",
                "Command:",
                "",
                "```bash",
                command or "python3.11 scripts/run_arc_diagnostic.py --config <CONFIG> --output-dir <OUTPUT_DIR>",
                "```",
                "",
                "Boundary: bounded local ARC external-validity diagnostic; no ARC performance claim.",
            ]
        )
        + "\n",
    )

    all_tasks = load_arc_tasks(arc_root, split=split, include_solutions=True)
    if require_solutions and not all(task.has_test_solutions for task in all_tasks):
        missing = [task.task_id for task in all_tasks if not task.has_test_solutions]
        raise ValueError(f"ARC diagnostic requires labeled test outputs; missing for task ids: {missing[:5]}")
    selected_tasks = select_arc_tasks(
        all_tasks,
        max_tasks=None if max_tasks is None else int(max_tasks),
        max_tasks_per_bucket=None if max_tasks_per_bucket is None else int(max_tasks_per_bucket),
    )

    rows: List[Dict[str, Any]] = []
    predictions_json: List[Dict[str, Any]] = []
    failure_records: List[Dict[str, Any]] = []
    failure_counts: Dict[str, int] = defaultdict(int)
    task_profiles = [arc_task_profile(task) for task in selected_tasks]
    profile_by_id = {profile["arc_task_id"]: profile for profile in task_profiles}

    for seed in seeds:
        set_global_seed(seed)
        for model_name in model_names:
            model = build_model(
                model_name,
                ModelConfig(
                    candidate_max_depth=candidate_max_depth,
                    colors=colors,
                    seed=seed,
                    oracle_probes=0,
                    falsifier_candidate_limit=int(config.get("falsifier_candidate_limit", 40)),
                    fixed_falsifier_budget=False,
                    budget_match_falsifier=False,
                    learned_hidden_dim=learned_hidden_dim,
                    learned_max_iter=learned_max_iter,
                    learned_alpha=learned_alpha,
                ),
            )
            for task in selected_tasks:
                profile = profile_by_id[task.task_id]
                started = time.perf_counter()
                try:
                    reasoning_task = arc_task_to_reasoning_task(task)
                    prediction = model.predict_task(reasoning_task, splits=("test",), world=None)
                    elapsed = time.perf_counter() - started
                    row = evaluate_arc_prediction(task, prediction)
                    row.update(profile)
                    row.update(
                        {
                            "seed": seed,
                            "run_name": run_name,
                            "skipped": 0.0,
                            "error": "",
                            "wall_time_seconds": elapsed,
                            "runtime_cap_seconds": runtime_cap_seconds,
                            "runtime_cap_exceeded": float(elapsed > runtime_cap_seconds),
                        }
                    )
                    rows.append(row)
                    predictions_json.append(predictions_to_json_records(task, prediction))
                    if float(row.get("test_pair_accuracy", 0.0)) < 1.0 and failure_counts[model_name] < failure_limit_per_model:
                        preds = list(prediction.predictions.get("test", []))
                        failure_records.append(
                            {
                                **row,
                                "test_inputs": [grid_to_list(example.input_grid) for example in task.test],
                                "test_outputs": [
                                    None if example.output_grid is None else grid_to_list(example.output_grid)
                                    for example in task.test
                                ],
                                "predictions": [grid_to_list(pred) for pred in preds],
                            }
                        )
                        failure_counts[model_name] += 1
                except Exception as exc:  # pragma: no cover - exercised by malformed local data, not normal runs.
                    elapsed = time.perf_counter() - started
                    row = {
                        "model_name": model_name,
                        "arc_task_id": task.task_id,
                        "arc_split": task.split,
                        "labels_available": float(task.has_test_solutions),
                        "n_train": len(task.train),
                        "n_test": len(task.test),
                        "n_test_evaluated": 0,
                        "test_pair_accuracy": 0.0,
                        "test_pixel_accuracy": 0.0,
                        "test_exact_task_accuracy": 0.0,
                        "test_shape_accuracy": 0.0,
                        "runtime_seconds": elapsed,
                        "candidate_program_count": 0.0,
                        "candidates_scored": 0.0,
                        "candidates_falsified": 0.0,
                        "oracle_probe_budget": 0.0,
                        "oracle_probes_used": 0.0,
                        "passive_checks_used": 0.0,
                        "predicted_program": None,
                        "latent_rule_recovery_computed": 0.0,
                        **profile,
                        "seed": seed,
                        "run_name": run_name,
                        "skipped": 1.0,
                        "error": f"{type(exc).__name__}: {exc}",
                        "wall_time_seconds": elapsed,
                        "runtime_cap_seconds": runtime_cap_seconds,
                        "runtime_cap_exceeded": float(elapsed > runtime_cap_seconds),
                    }
                    rows.append(row)
                    if failure_counts[model_name] < failure_limit_per_model:
                        failure_records.append(row)
                        failure_counts[model_name] += 1

    summary = summarize_arc_rows(rows)
    summary.update(
        {
            "run_name": run_name,
            "arc_root": arc_root,
            "split": split,
            "seeds": seeds,
            "models": model_names,
            "candidate_max_depth": candidate_max_depth,
            "runtime_cap_seconds": runtime_cap_seconds,
            "skipped_rows": int(sum(float(row.get("skipped", 0.0)) for row in rows)),
            "runtime_cap_exceeded_rows": int(sum(float(row.get("runtime_cap_exceeded", 0.0)) for row in rows)),
            "by_shape_bucket": _summarize_by_shape_bucket(rows),
            "boundary": "Bounded local ARC diagnostic; no ARC benchmark or latent-rule recovery claim is made.",
        }
    )
    seed_model_records = _seed_model_records(rows)
    paired_contrasts, paired_deltas = _paired_contrasts(seed_model_records)

    write_json(run_dir / "arc_tasks.json", [task.to_dict() for task in selected_tasks])
    write_json(run_dir / "task_profiles.json", task_profiles)
    write_json(run_dir / "metrics.json", rows)
    _write_csv(run_dir / "metrics.csv", rows)
    write_json(run_dir / "predictions.json", predictions_json)
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "seed_model_metrics.json", seed_model_records)
    _write_csv(run_dir / "seed_model_metrics.csv", seed_model_records)
    write_json(run_dir / "paired_contrasts.json", paired_contrasts)
    _write_csv(run_dir / "paired_seed_deltas.csv", paired_deltas)
    _write_paired_markdown(run_dir / "paired_contrasts.md", paired_contrasts)
    write_json(run_dir / "qualitative_failures.json", failure_records)
    _failure_markdown(run_dir / "qualitative_failures.md", failure_records)
    _write_summary_markdown(run_dir / "arc_evaluation_summary.md", summary, paired_contrasts, failure_records)
    write_text(
        run_dir / "external_validity_summary.md",
        "# External Validity Summary\n\n"
        "Local ARC evaluation is available and was run as a bounded diagnostic. "
        "The run measures output accuracy, solve rate proxies, runtime, and qualitative failures. "
        "It does not measure latent-rule recovery and does not justify ARC performance claims.\n",
    )
    write_json(
        run_dir / "manifest.json",
        {
            "kind": "arc_diagnostic",
            "run_name": run_name,
            "run_dir": str(run_dir),
            "created_at": utc_timestamp(),
            "artifacts": [
                "config.json",
                "seed_list.json",
                "resume_instructions.json",
                "command_log.md",
                "arc_tasks.json",
                "task_profiles.json",
                "metrics.json",
                "metrics.csv",
                "predictions.json",
                "summary.json",
                "seed_model_metrics.json",
                "seed_model_metrics.csv",
                "paired_contrasts.json",
                "paired_contrasts.md",
                "paired_seed_deltas.csv",
                "qualitative_failures.json",
                "qualitative_failures.md",
                "arc_evaluation_summary.md",
                "external_validity_summary.md",
            ],
        },
    )
    return {
        "run_dir": str(run_dir),
        "rows": rows,
        "summary": summary,
        "seed_model_records": seed_model_records,
        "paired_contrasts": paired_contrasts,
        "failure_records": failure_records,
    }
