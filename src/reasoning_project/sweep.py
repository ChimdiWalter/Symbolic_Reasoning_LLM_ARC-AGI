"""Repeated-seed experiment sweeps and aggregate reporting."""

from __future__ import annotations

import copy
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from .experiment import run_experiment
from .utils import ensure_dir, read_json, utc_timestamp, write_json, write_text


CONTRAST_PAIRS = [
    ("learned_task_mlp", "direct_io_proxy"),
    ("transformation_library", "learned_task_mlp"),
    ("proposer_falsifier", "proposer_only"),
    ("integrated_scientist", "transformation_library"),
    ("integrated_scientist", "compression_selector"),
    ("integrated_scientist", "proposer_falsifier"),
    ("path_repair", "compression_selector"),
    ("transformation_library", "direct_io_proxy"),
]

LOWER_IS_BETTER = {
    "false_rule_selected",
    "false_rule_accepted",
    "runtime_seconds",
    "train_error",
}

STRATIFICATION_FIELDS = [
    "task_family",
    "designed_ambiguity_level",
    "empirical_ambiguity_level",
    "distractor_condition",
    "compositional_condition",
    "verification_budget_level",
    "compute_match_condition",
]


def _bootstrap_ci(values: Sequence[float], seed: int = 0, n_bootstrap: int = 2000) -> Dict[str, float]:
    values = [float(value) for value in values]
    if not values:
        return {"low": 0.0, "high": 0.0}
    if len(values) == 1:
        return {"low": values[0], "high": values[0]}
    rng = np.random.default_rng(seed)
    samples = []
    arr = np.asarray(values, dtype=float)
    for _ in range(n_bootstrap):
        draw = rng.choice(arr, size=len(arr), replace=True)
        samples.append(float(np.mean(draw)))
    return {
        "low": float(np.percentile(samples, 2.5)),
        "high": float(np.percentile(samples, 97.5)),
    }


def _numeric_keys(records: Sequence[Mapping[str, Any]]) -> List[str]:
    keys = sorted({key for record in records for key, value in record.items() if isinstance(value, (int, float))})
    return [key for key in keys if key not in {"seed"}]


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


def _aggregate_seed_model_records(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_model: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_model[str(record["model_name"])].append(record)
    numeric_keys = _numeric_keys(records)
    summary: Dict[str, Any] = {"by_model": {}, "n_seed_model_records": len(records)}
    for model, group in sorted(by_model.items()):
        model_summary: Dict[str, Any] = {"n": len(group)}
        for key in numeric_keys:
            values = [float(record.get(key, 0.0)) for record in group]
            ci = _bootstrap_ci(values, seed=stable_seed(model, key))
            model_summary[f"{key}_mean"] = float(np.mean(values)) if values else 0.0
            model_summary[f"{key}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            model_summary[f"{key}_ci_low"] = ci["low"]
            model_summary[f"{key}_ci_high"] = ci["high"]
        summary["by_model"][model] = model_summary
    return summary


def stable_seed(*parts: Any) -> int:
    text = "::".join(str(part) for part in parts)
    return sum((idx + 1) * ord(char) for idx, char in enumerate(text)) % (2**32)


def _paired_contrast_data(
    records: Sequence[Mapping[str, Any]], metric_keys: Sequence[str]
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    by_seed_model: Dict[int, Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for record in records:
        by_seed_model[int(record["seed"])][str(record["model_name"])] = record

    contrasts: Dict[str, Any] = {}
    delta_records: List[Dict[str, Any]] = []
    for left, right in CONTRAST_PAIRS:
        paired_seeds = [seed for seed, models in sorted(by_seed_model.items()) if left in models and right in models]
        if not paired_seeds:
            continue
        contrast_key = f"{left}_minus_{right}"
        contrast_summary: Dict[str, Any] = {"n": len(paired_seeds), "left": left, "right": right}
        for metric in metric_keys:
            diffs = [
                float(by_seed_model[seed][left].get(metric, 0.0))
                - float(by_seed_model[seed][right].get(metric, 0.0))
                for seed in paired_seeds
            ]
            if metric in LOWER_IS_BETTER:
                wins = [diff < 0 for diff in diffs]
            else:
                wins = [diff > 0 for diff in diffs]
            ties = [diff == 0 for diff in diffs]
            ci = _bootstrap_ci(diffs, seed=stable_seed(contrast_key, metric))
            std_delta = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
            mean_delta = float(np.mean(diffs)) if diffs else 0.0
            effect_size_dz = None if len(diffs) < 2 or std_delta < 1e-12 else mean_delta / std_delta
            contrast_summary[metric] = {
                "mean_delta": mean_delta,
                "std_delta": std_delta,
                "ci_low": ci["low"],
                "ci_high": ci["high"],
                "win_rate": float(np.mean(wins)) if wins else 0.0,
                "tie_rate": float(np.mean(ties)) if ties else 0.0,
                "lower_is_better": metric in LOWER_IS_BETTER,
                "effect_size_dz": effect_size_dz,
            }
            for seed, diff, win, tie in zip(paired_seeds, diffs, wins, ties):
                delta_records.append(
                    {
                        "contrast": contrast_key,
                        "seed": seed,
                        "metric": metric,
                        "left_model": left,
                        "right_model": right,
                        "left_value": float(by_seed_model[seed][left].get(metric, 0.0)),
                        "right_value": float(by_seed_model[seed][right].get(metric, 0.0)),
                        "delta": float(diff),
                        "left_wins": bool(win),
                        "tie": bool(tie),
                        "lower_is_better": metric in LOWER_IS_BETTER,
                    }
                )
        contrasts[contrast_key] = contrast_summary
    return contrasts, delta_records


def _write_contrasts_markdown(path: Path, contrasts: Mapping[str, Any], metric_keys: Sequence[str]) -> None:
    columns = ["contrast", "n"]
    for metric in metric_keys:
        columns.extend([f"{metric}_delta", f"{metric}_ci", f"{metric}_win_rate", f"{metric}_dz"])
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for contrast, metrics in sorted(contrasts.items()):
        values = [contrast, str(metrics.get("n", 0))]
        for metric in metric_keys:
            data = dict(metrics.get(metric, {}))
            values.append(f"{float(data.get('mean_delta', 0.0)):.3f}")
            values.append(
                f"[{float(data.get('ci_low', 0.0)):.3f}, {float(data.get('ci_high', 0.0)):.3f}]"
            )
            values.append(f"{float(data.get('win_rate', 0.0)):.3f}")
            dz = data.get("effect_size_dz")
            values.append("NA" if dz is None else f"{float(dz):.3f}")
        lines.append("|" + "|".join(values) + "|")
    write_text(path, "\n".join(lines) + "\n")


def _write_markdown(path: Path, summary: Mapping[str, Any], metric_keys: Sequence[str]) -> None:
    columns = ["model"]
    for key in metric_keys:
        columns.extend([f"{key}_mean", f"{key}_std"])
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for model, metrics in sorted(dict(summary.get("by_model", {})).items()):
        values = [model]
        for key in metric_keys:
            values.append(f"{float(metrics.get(f'{key}_mean', 0.0)):.3f}")
            values.append(f"{float(metrics.get(f'{key}_std', 0.0)):.3f}")
        lines.append("|" + "|".join(values) + "|")
    write_text(path, "\n".join(lines) + "\n")


def _write_verdict_summary(path: Path, verdicts_by_seed: Sequence[Mapping[str, Any]]) -> None:
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in verdicts_by_seed:
        for key, value in dict(record.get("verdicts", {})).items():
            counts[key][str(value)] += 1
    write_json(path, {key: dict(value) for key, value in sorted(counts.items())})


def _mean_numeric_group(records: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    numeric_keys = _numeric_keys(records)
    out: Dict[str, float] = {}
    for key in numeric_keys:
        values = [float(record.get(key, 0.0)) for record in records]
        out[key] = float(np.mean(values)) if values else 0.0
    return out


def _stratified_seed_model_records(
    rows: Sequence[Mapping[str, Any]],
    seed: int,
    run_dir: str,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for field in STRATIFICATION_FIELDS:
        grouped: Dict[tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            if field not in row:
                continue
            grouped[(str(row["model_name"]), str(row[field]))].append(row)
        for (model, value), group in sorted(grouped.items()):
            record: Dict[str, Any] = {
                "seed": int(seed),
                "run_dir": run_dir,
                "model_name": model,
                "stratum_field": field,
                "stratum_value": value,
                "n_task_rows": len(group),
            }
            record.update(_mean_numeric_group(group))
            records.append(record)
    return records


def _stratified_paired_contrast_data(
    records: Sequence[Mapping[str, Any]],
    metric_keys: Sequence[str],
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    by_stratum: Dict[tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_stratum[(str(record["stratum_field"]), str(record["stratum_value"]))].append(record)

    all_contrasts: Dict[str, Any] = {}
    all_delta_records: List[Dict[str, Any]] = []
    for (field, value), group in sorted(by_stratum.items()):
        contrasts, deltas = _paired_contrast_data(group, metric_keys)
        for contrast_key, contrast in sorted(contrasts.items()):
            key = f"{field}={value}::{contrast_key}"
            all_contrasts[key] = {
                **contrast,
                "stratum_field": field,
                "stratum_value": value,
                "contrast": contrast_key,
            }
        for delta in deltas:
            all_delta_records.append(
                {
                    **delta,
                    "stratum_field": field,
                    "stratum_value": value,
                }
            )
    return all_contrasts, all_delta_records


def _write_stratified_contrasts_markdown(
    path: Path,
    contrasts: Mapping[str, Any],
    metric_keys: Sequence[str],
) -> None:
    columns = ["stratum", "contrast", "n"]
    for metric in metric_keys:
        columns.extend([f"{metric}_delta", f"{metric}_ci", f"{metric}_win_rate", f"{metric}_dz"])
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for _key, metrics in sorted(contrasts.items()):
        values = [
            f"{metrics.get('stratum_field')}={metrics.get('stratum_value')}",
            str(metrics.get("contrast", "")),
            str(metrics.get("n", 0)),
        ]
        for metric in metric_keys:
            data = dict(metrics.get(metric, {}))
            values.append(f"{float(data.get('mean_delta', 0.0)):.3f}")
            values.append(
                f"[{float(data.get('ci_low', 0.0)):.3f}, {float(data.get('ci_high', 0.0)):.3f}]"
            )
            values.append(f"{float(data.get('win_rate', 0.0)):.3f}")
            dz = data.get("effect_size_dz")
            values.append("NA" if dz is None else f"{float(dz):.3f}")
        lines.append("|" + "|".join(values) + "|")
    write_text(path, "\n".join(lines) + "\n")


def run_seed_sweep(
    config: Mapping[str, Any],
    seeds: Iterable[int],
    output_dir: str | Path,
    sweep_name: str | None = None,
    resume: bool = True,
) -> Dict[str, Any]:
    seeds = [int(seed) for seed in seeds]
    if not seeds:
        raise ValueError("At least one seed is required")
    base_run_name = str(config.get("run_name", config.get("name", "run")))
    sweep_name = sweep_name or f"{base_run_name}_seed_sweep"
    sweep_dir = ensure_dir(Path(output_dir) / sweep_name)
    seed_text = " ".join(str(seed) for seed in seeds)
    write_json(
        sweep_dir / "resume_instructions.json",
        {
            "kind": "seed_sweep",
            "sweep_name": sweep_name,
            "sweep_dir": str(sweep_dir),
            "seeds": seeds,
            "resume_command": (
                "python3.11 scripts/run_seed_sweep.py "
                f"--config <CONFIG_PATH> --output-dir {Path(output_dir)} "
                f"--sweep-name {sweep_name} --seeds {seed_text}"
            ),
            "checkpoint_pattern": str(Path(output_dir) / f"{sweep_name}_seed_<SEED>" / "run_state.json"),
            "created_at": utc_timestamp(),
        },
    )

    seed_model_records: List[Dict[str, Any]] = []
    stratified_seed_model_records: List[Dict[str, Any]] = []
    verdicts_by_seed: List[Dict[str, Any]] = []
    child_runs: List[Dict[str, Any]] = []
    for seed in seeds:
        seed_config = copy.deepcopy(dict(config))
        seed_config["seed"] = int(seed)
        seed_config["run_name"] = f"{sweep_name}_seed_{seed}"
        result = run_experiment(seed_config, output_dir=output_dir, resume=resume)
        summary = result["summary"]
        verdicts = result["verdicts"]
        child_runs.append({"seed": seed, "run_dir": result["run_dir"], "rows": len(result["rows"])})
        verdicts_by_seed.append({"seed": seed, "run_dir": result["run_dir"], "verdicts": verdicts})
        stratified_seed_model_records.extend(
            _stratified_seed_model_records(result["rows"], seed=seed, run_dir=result["run_dir"])
        )
        for model, metrics in sorted(dict(summary.get("by_model", {})).items()):
            record: Dict[str, Any] = {
                "seed": seed,
                "run_dir": result["run_dir"],
                "model_name": model,
            }
            record.update({key: value for key, value in metrics.items() if isinstance(value, (int, float))})
            seed_model_records.append(record)

    aggregate = _aggregate_seed_model_records(seed_model_records)
    metric_keys = [
        "test_pair_accuracy",
        "ood_pair_accuracy",
        "latent_rule_recovered",
        "heldout_behavior_recovered",
        "equivalent_or_repairable_rule_selected",
        "false_rule_selected",
        "false_rule_accepted",
        "counterexample_survival_rate",
        "recovery_after_corruption",
        "runtime_seconds",
        "candidate_program_count",
        "candidates_scored",
        "candidates_falsified",
        "oracle_probe_budget",
        "oracle_probes_used",
        "passive_checks_used",
    ]
    available_metric_keys = [
        key
        for key in metric_keys
        if any(f"{key}_mean" in metrics for metrics in aggregate.get("by_model", {}).values())
    ]
    contrasts, paired_delta_records = _paired_contrast_data(seed_model_records, available_metric_keys)
    stratified_contrasts, stratified_delta_records = _stratified_paired_contrast_data(
        stratified_seed_model_records,
        available_metric_keys,
    )

    _write_csv(sweep_dir / "seed_model_metrics.csv", seed_model_records)
    _write_csv(sweep_dir / "paired_seed_deltas.csv", paired_delta_records)
    _write_csv(sweep_dir / "stratified_seed_model_metrics.csv", stratified_seed_model_records)
    _write_csv(sweep_dir / "stratified_paired_seed_deltas.csv", stratified_delta_records)
    write_json(sweep_dir / "sweep_summary.json", aggregate)
    write_json(sweep_dir / "paired_contrasts.json", contrasts)
    write_json(sweep_dir / "stratified_paired_contrasts.json", stratified_contrasts)
    write_json(sweep_dir / "child_runs.json", child_runs)
    write_json(sweep_dir / "hypothesis_verdicts_by_seed.json", verdicts_by_seed)
    _write_verdict_summary(sweep_dir / "hypothesis_verdict_counts.json", verdicts_by_seed)
    _write_markdown(sweep_dir / "sweep_summary.md", aggregate, available_metric_keys)
    _write_contrasts_markdown(sweep_dir / "paired_contrasts.md", contrasts, available_metric_keys)
    _write_stratified_contrasts_markdown(
        sweep_dir / "stratified_paired_contrasts.md",
        stratified_contrasts,
        available_metric_keys,
    )
    write_json(
        sweep_dir / "manifest.json",
        {
            "sweep_name": sweep_name,
            "sweep_dir": str(sweep_dir),
            "seeds": seeds,
            "created_at": utc_timestamp(),
            "artifacts": [
                "resume_instructions.json",
                "seed_model_metrics.csv",
                "paired_seed_deltas.csv",
                "stratified_seed_model_metrics.csv",
                "stratified_paired_seed_deltas.csv",
                "sweep_summary.json",
                "sweep_summary.md",
                "paired_contrasts.json",
                "paired_contrasts.md",
                "stratified_paired_contrasts.json",
                "stratified_paired_contrasts.md",
                "child_runs.json",
                "hypothesis_verdicts_by_seed.json",
                "hypothesis_verdict_counts.json",
            ],
        },
    )
    return {
        "sweep_dir": str(sweep_dir),
        "seeds": seeds,
        "child_runs": child_runs,
        "summary": aggregate,
        "contrasts": contrasts,
        "paired_delta_records": paired_delta_records,
        "stratified_seed_model_records": stratified_seed_model_records,
        "stratified_delta_records": stratified_delta_records,
        "stratified_contrasts": stratified_contrasts,
        "verdicts_by_seed": verdicts_by_seed,
        "seed_model_records": seed_model_records,
    }


def load_sweep_summary(path: str | Path) -> Dict[str, Any]:
    return read_json(Path(path) / "sweep_summary.json")
