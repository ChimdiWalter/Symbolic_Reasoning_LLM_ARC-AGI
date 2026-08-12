"""Aggregate H4 bounded-compression alignment across completed sweep child runs."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from .h4_analysis import write_h4_bounded_compression_analysis
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


def _mean(values: Iterable[float]) -> float:
    data = [float(value) for value in values]
    return float(np.mean(data)) if data else 0.0


def _summarize(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_model: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    by_family: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    by_seed_model: Dict[tuple[int, str], List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        model = str(record["model_name"])
        family = str(record["family"])
        seed = int(record["seed"])
        by_model[model].append(record)
        by_family[family].append(record)
        by_seed_model[(seed, model)].append(record)

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
            "mean_latent_rule_recovered": _mean(row.get("latent_rule_recovered", 0.0) for row in group),
        }

    seed_model_summary: List[Dict[str, Any]] = []
    for (seed, model), group in sorted(by_seed_model.items()):
        summary = summarize_group(group)
        seed_model_summary.append(
            {
                "seed": seed,
                "model_name": model,
                **summary,
            }
        )

    return {
        "n_records": len(records),
        "seed_count": len({int(record["seed"]) for record in records}),
        "by_model": {model: summarize_group(group) for model, group in sorted(by_model.items())},
        "by_family": {family: summarize_group(group) for family, group in sorted(by_family.items())},
        "seed_model_summary": seed_model_summary,
    }


def _summary_markdown(summary: Mapping[str, Any], sweep_dir: Path, output_dir: Path) -> str:
    lines = [
        "# H4 Bounded Compression Sweep Alignment",
        "",
        "Boundary: this aggregates exact bounded DSL-minimum alignment across completed paper-breadth child runs. It strengthens the bounded alignment diagnostic only; it is not causal discovery, exact algorithmic information dynamics, or a broad H4 confirmation.",
        "",
        f"- source sweep: `{sweep_dir}`",
        f"- artifact directory: `{output_dir}`",
        f"- seeds: {int(summary.get('seed_count', 0))}",
        f"- per-task records: {int(summary.get('n_records', 0))}",
        "",
        "## Model Summary",
        "",
        "|model|exact_min_available|selected_fit|selected_is_min|mean_gap_units|latent_rule|nuisance|intervention|causal_factor|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, metrics in sorted(dict(summary.get("by_model", {})).items()):
        lines.append(
            "|{model}|{available:.3f}|{fit:.3f}|{is_min:.3f}|{gap:.3f}|{latent:.3f}|{nuisance:.3f}|{intervention:.3f}|{causal:.3f}|".format(
                model=model,
                available=float(metrics.get("exact_min_available_rate", 0.0)),
                fit=float(metrics.get("selected_train_fit_rate", 0.0)),
                is_min=float(metrics.get("selected_is_exact_min_rate", 0.0)),
                gap=float(metrics.get("mean_selected_minus_exact_min_units", 0.0)),
                latent=float(metrics.get("mean_latent_rule_recovered", 0.0)),
                nuisance=float(metrics.get("mean_nuisance_robustness", 0.0)),
                intervention=float(metrics.get("mean_intervention_stability", 0.0)),
                causal=float(metrics.get("mean_causal_factor_recovery", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "## Family Summary",
            "",
            "|family|selected_is_min|mean_gap_units|causal_factor|",
            "|---|---:|---:|---:|",
        ]
    )
    for family, metrics in sorted(dict(summary.get("by_family", {})).items()):
        lines.append(
            "|{family}|{is_min:.3f}|{gap:.3f}|{causal:.3f}|".format(
                family=family,
                is_min=float(metrics.get("selected_is_exact_min_rate", 0.0)),
                gap=float(metrics.get("mean_selected_minus_exact_min_units", 0.0)),
                causal=float(metrics.get("mean_causal_factor_recovery", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "Interpretation rule: if multiple models align with exact bounded minima across seeds, that strengthens the bounded DSL-minimum diagnostic but weakens any claim that the compression selector uniquely recovers more causal rules.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_h4_sweep_analysis(
    sweep_dir: str | Path,
    output_dir: str | Path | None = None,
    command: str = "",
) -> Dict[str, Any]:
    sweep_path = Path(sweep_dir)
    out = ensure_dir(output_dir or (sweep_path / "h4_bounded_alignment"))
    child_runs = read_json(sweep_path / "child_runs.json")
    records: List[Dict[str, Any]] = []
    seed_configs: List[Mapping[str, Any]] = []
    seed_runs: List[Dict[str, Any]] = []
    child_outputs: List[str] = []

    for child in child_runs:
        seed = int(child.get("seed", 0))
        run_dir = Path(str(child["run_dir"]))
        analysis_result = write_h4_bounded_compression_analysis(run_dir)
        child_output = Path(str(analysis_result["output_dir"]))
        child_outputs.append(str(child_output))
        seed_configs.append(read_json(run_dir / "config.json"))
        per_task = read_json(child_output / "per_task_exact_mdl.json")
        for row in per_task:
            records.append(
                {
                    **row,
                    "seed": seed,
                    "run_dir": str(run_dir),
                    "h4_output_dir": str(child_output),
                }
            )
        seed_runs.append({"seed": seed, "run_dir": str(run_dir), "h4_output_dir": str(child_output)})

    summary = _summarize(records)
    write_json(out / "config_snapshot.json", {"child_configs": seed_configs})
    write_json(out / "seed_list.json", {"seeds": [int(run["seed"]) for run in seed_runs]})
    write_text(
        out / "command_log.md",
        "# Command Log\n\n```bash\n{}\n```\n".format(
            command or f"python3.11 scripts/analyze_h4_sweep.py --sweep-dir {sweep_path}"
        ),
    )
    write_json(
        out / "resume_instructions.json",
        {
            "kind": "h4_bounded_alignment_sweep",
            "resume_command": f"python3.11 scripts/analyze_h4_sweep.py --sweep-dir {sweep_path}",
            "created_at": utc_timestamp(),
        },
    )
    write_json(out / "child_h4_outputs.json", seed_runs)
    write_json(out / "per_task_exact_mdl.json", records)
    _write_csv(out / "per_task_exact_mdl.csv", records)
    write_json(out / "h4_sweep_summary.json", summary)
    write_json(out / "h4_family_summary.json", summary.get("by_family", {}))
    write_json(out / "h4_seed_model_summary.json", summary.get("seed_model_summary", []))
    _write_csv(out / "h4_seed_model_summary.csv", summary.get("seed_model_summary", []))
    write_text(out / "h4_sweep_summary.md", _summary_markdown(summary, sweep_path, out))
    write_json(
        out / "manifest.json",
        {
            "kind": "h4_bounded_alignment_sweep",
            "created_at": utc_timestamp(),
            "sweep_dir": str(sweep_path),
            "child_h4_outputs": child_outputs,
            "artifacts": [
                "config_snapshot.json",
                "seed_list.json",
                "command_log.md",
                "resume_instructions.json",
                "child_h4_outputs.json",
                "per_task_exact_mdl.json",
                "per_task_exact_mdl.csv",
                "h4_sweep_summary.json",
                "h4_sweep_summary.md",
                "h4_family_summary.json",
                "h4_seed_model_summary.json",
                "h4_seed_model_summary.csv",
            ],
        },
    )
    return {
        "output_dir": str(out),
        "summary": summary,
        "records": records,
    }
