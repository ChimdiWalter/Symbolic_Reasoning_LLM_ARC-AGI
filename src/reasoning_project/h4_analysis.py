"""H4 compression analysis against exact bounded DSL minima."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from .formal import bounded_exact_dsl_minimum, program_code_length_units
from .operators import apply_program, program_description_length
from .schemas import Program, ProgramStep, TaskSuite, program_signature
from .utils import ensure_dir, read_json, utc_timestamp, write_json, write_text


def _write_csv(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not records:
        write_text(path, "")
        return
    fieldnames = sorted({key for record in records for key in record})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def _program_from_prediction(candidate: Mapping[str, Any] | None) -> Program | None:
    if not candidate:
        return None
    return [ProgramStep.from_dict(step) for step in candidate.get("program", [])]


def _train_fits(program: Program, task) -> bool:
    return all(
        np.array_equal(apply_program(example.input_grid, program), example.output_grid)
        for example in task.examples.get("train", [])
    )


def _mean(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    return float(np.mean(values)) if values else 0.0


def _summarize(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_model: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    by_family: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_model[str(record["model_name"])].append(record)
        by_family[str(record["family"])].append(record)

    def summarize_group(group: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
        available = [row for row in group if row.get("exact_min_code_length_units") is not None]
        gaps = [
            float(row["selected_minus_exact_min_units"])
            for row in group
            if row.get("selected_minus_exact_min_units") is not None
        ]
        return {
            "n": float(len(group)),
            "exact_min_available_rate": float(len(available) / len(group)) if group else 0.0,
            "selected_train_fit_rate": _mean(row.get("selected_train_fits", 0.0) for row in group),
            "selected_is_exact_min_rate": _mean(row.get("selected_is_exact_bounded_minimum", 0.0) for row in group),
            "mean_selected_minus_exact_min_units": _mean(gaps),
            "mean_selected_code_length_units": _mean(
                row["selected_code_length_units"]
                for row in group
                if row.get("selected_code_length_units") is not None
            ),
            "mean_description_length_proxy": _mean(row.get("description_length_proxy", 0.0) for row in group),
            "mean_nuisance_robustness": _mean(row.get("nuisance_robustness", 0.0) for row in group),
            "mean_intervention_stability": _mean(row.get("intervention_stability", 0.0) for row in group),
            "mean_causal_factor_recovery": _mean(row.get("causal_factor_recovery", 0.0) for row in group),
        }

    return {
        "by_model": {model: summarize_group(group) for model, group in sorted(by_model.items())},
        "by_family": {family: summarize_group(group) for family, group in sorted(by_family.items())},
        "n_records": len(records),
    }


def _summary_markdown(summary: Mapping[str, Any], run_dir: Path, output_dir: Path) -> str:
    lines = [
        "# H4 Bounded Compression Analysis",
        "",
        "Boundary: this compares MDL-style proxy selections against exact bounded DSL minima when the run's finite candidate set is tractable. It is not exact Kolmogorov complexity or causal discovery.",
        "",
        f"- source run: `{run_dir}`",
        f"- artifact directory: `{output_dir}`",
        "",
        "## Model Summary",
        "",
        "|model|n|exact_min_available|selected_fit|selected_is_min|mean_gap_units|mean_proxy_dl|nuisance|intervention|causal_factor|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, metrics in sorted(dict(summary.get("by_model", {})).items()):
        lines.append(
            "|{model}|{n:.0f}|{available:.3f}|{fit:.3f}|{is_min:.3f}|{gap:.3f}|{proxy:.3f}|{nuisance:.3f}|{intervention:.3f}|{causal:.3f}|".format(
                model=model,
                n=float(metrics.get("n", 0.0)),
                available=float(metrics.get("exact_min_available_rate", 0.0)),
                fit=float(metrics.get("selected_train_fit_rate", 0.0)),
                is_min=float(metrics.get("selected_is_exact_min_rate", 0.0)),
                gap=float(metrics.get("mean_selected_minus_exact_min_units", 0.0)),
                proxy=float(metrics.get("mean_description_length_proxy", 0.0)),
                nuisance=float(metrics.get("mean_nuisance_robustness", 0.0)),
                intervention=float(metrics.get("mean_intervention_stability", 0.0)),
                causal=float(metrics.get("mean_causal_factor_recovery", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "## Family-Balanced Reading",
            "",
            "Use `h4_family_summary.json` to check whether any H4 signal is dominated by one family. The table below reports family means before any paper claim is made.",
            "",
            "|family|n|selected_is_min|mean_gap_units|nuisance|intervention|causal_factor|",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for family, metrics in sorted(dict(summary.get("by_family", {})).items()):
        lines.append(
            "|{family}|{n:.0f}|{is_min:.3f}|{gap:.3f}|{nuisance:.3f}|{intervention:.3f}|{causal:.3f}|".format(
                family=family,
                n=float(metrics.get("n", 0.0)),
                is_min=float(metrics.get("selected_is_exact_min_rate", 0.0)),
                gap=float(metrics.get("mean_selected_minus_exact_min_units", 0.0)),
                nuisance=float(metrics.get("mean_nuisance_robustness", 0.0)),
                intervention=float(metrics.get("mean_intervention_stability", 0.0)),
                causal=float(metrics.get("mean_causal_factor_recovery", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "Interpretation rule: a low exact-minimum gap supports only the bounded DSL-compression diagnostic. It does not establish exact algorithmic information dynamics or causal discovery.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_h4_bounded_compression_analysis(
    run_dir: str | Path,
    output_dir: str | Path | None = None,
    command: str = "",
) -> Dict[str, Any]:
    run_path = Path(run_dir)
    out = ensure_dir(output_dir or (run_path / "h4_bounded_compression"))
    suite = TaskSuite.from_dict(read_json(run_path / "dataset.json"))
    config = read_json(run_path / "config.json")
    predictions = read_json(run_path / "predictions.json")
    result_rows = read_json(run_path / "results.json")
    result_by_key = {
        (str(row.get("task_id")), str(row.get("model_name"))): row
        for row in result_rows
        if isinstance(row, Mapping)
    }
    max_depth = int(config.get("candidate_max_depth", 1))
    colors = [int(color) for color in config.get("colors", [1, 2, 3, 4, 5, 6, 7, 8])]

    prediction_by_key = {
        (str(prediction.get("task_id")), str(prediction.get("model_name"))): prediction
        for prediction in predictions
        if isinstance(prediction, Mapping)
    }
    records: List[Dict[str, Any]] = []
    exact_reports: Dict[str, Any] = {}
    for task in suite.tasks:
        exact_report = bounded_exact_dsl_minimum(task.examples.get("train", []), max_depth=max_depth, colors=colors)
        exact_reports[task.task_id] = exact_report.to_dict()
        exact_min = exact_report.minimum_code_length_units
        exact_min_signatures = set(exact_report.minimum_program_signatures)
        task_models = sorted(
            model for task_id, model in prediction_by_key if task_id == task.task_id
        )
        for model in task_models:
            prediction = prediction_by_key[(task.task_id, model)]
            program = _program_from_prediction(prediction.get("candidate"))
            result_row = result_by_key.get((task.task_id, model), {})
            if program is None:
                selected_signature = None
                selected_units = None
                selected_proxy = None
                selected_train_fits = 0.0
                selected_is_min = 0.0
                gap = None
            else:
                selected_signature = program_signature(program)
                selected_units = program_code_length_units(program)
                selected_proxy = program_description_length(program)
                selected_train_fits = float(_train_fits(program, task))
                selected_is_min = float(selected_signature in exact_min_signatures)
                gap = None if exact_min is None else float(selected_units - exact_min)
            records.append(
                {
                    "task_id": task.task_id,
                    "family": task.family,
                    "model_name": model,
                    "true_program": program_signature(task.program),
                    "selected_program": selected_signature,
                    "exact_min_code_length_units": exact_min,
                    "exact_min_program_signatures": "; ".join(sorted(exact_min_signatures)),
                    "exact_min_satisfying_count": exact_report.satisfying_count,
                    "candidate_count": exact_report.candidate_count,
                    "selected_code_length_units": selected_units,
                    "selected_proxy_description_length": selected_proxy,
                    "selected_minus_exact_min_units": gap,
                    "selected_train_fits": selected_train_fits,
                    "selected_is_exact_bounded_minimum": selected_is_min,
                    "description_length_proxy": float(result_row.get("description_length_proxy", 0.0)),
                    "nuisance_robustness": float(result_row.get("nuisance_robustness", 0.0)),
                    "intervention_stability": float(result_row.get("intervention_stability", 0.0)),
                    "causal_factor_recovery": float(result_row.get("causal_factor_recovery", 0.0)),
                    "heldout_behavior_recovered": float(result_row.get("heldout_behavior_recovered", 0.0)),
                    "latent_rule_recovered": float(result_row.get("latent_rule_recovered", 0.0)),
                }
            )

    summary = _summarize(records)
    write_json(out / "config_snapshot.json", config)
    write_json(out / "seed_list.json", {"seeds": [int(config.get("seed", 0))]})
    write_text(
        out / "command_log.md",
        "# Command Log\n\n```bash\n{}\n```\n".format(
            command or f"python3.11 scripts/analyze_h4_compression.py --run-dir {run_path}"
        ),
    )
    write_json(
        out / "resume_instructions.json",
        {
            "kind": "h4_bounded_compression_analysis",
            "resume_command": f"python3.11 scripts/analyze_h4_compression.py --run-dir {run_path}",
            "created_at": utc_timestamp(),
        },
    )
    write_json(out / "per_task_exact_mdl.json", records)
    _write_csv(out / "per_task_exact_mdl.csv", records)
    write_json(out / "exact_minimum_reports.json", exact_reports)
    write_json(out / "h4_summary.json", summary)
    write_json(out / "h4_family_summary.json", summary.get("by_family", {}))
    write_text(out / "h4_bounded_compression_summary.md", _summary_markdown(summary, run_path, out))
    write_json(
        out / "manifest.json",
        {
            "kind": "h4_bounded_compression_analysis",
            "created_at": utc_timestamp(),
            "run_dir": str(run_path),
            "artifacts": [
                "config_snapshot.json",
                "seed_list.json",
                "command_log.md",
                "resume_instructions.json",
                "per_task_exact_mdl.json",
                "per_task_exact_mdl.csv",
                "exact_minimum_reports.json",
                "h4_summary.json",
                "h4_family_summary.json",
                "h4_bounded_compression_summary.md",
            ],
        },
    )
    return {"output_dir": str(out), "summary": summary, "records": records}
