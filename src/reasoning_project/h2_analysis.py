"""Post-hoc H2 family-balanced analysis for seed sweeps."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np

from .utils import ensure_dir, read_json, write_json, write_text


H2_CONTRAST = "proposer_falsifier_minus_proposer_only"
H2_PREFIX = "h2_"


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _family_contrasts(stratified: Mapping[str, Any]) -> Dict[str, Any]:
    families: Dict[str, Any] = {}
    for _key, value in sorted(stratified.items()):
        if value.get("stratum_field") != "task_family":
            continue
        if value.get("contrast") != H2_CONTRAST:
            continue
        families[str(value.get("stratum_value"))] = value
    return families


def _balanced_metric_summary(families: Mapping[str, Any], metric: str, only_h2: bool = False) -> Dict[str, Any]:
    deltas: List[float] = []
    rows: List[Dict[str, Any]] = []
    for family, data in sorted(families.items()):
        if only_h2 and not family.startswith(H2_PREFIX):
            continue
        metric_data = dict(data.get(metric, {}))
        delta = _float(metric_data.get("mean_delta"))
        deltas.append(delta)
        rows.append(
            {
                "family": family,
                "n": int(data.get("n", 0)),
                "mean_delta": delta,
                "ci_low": _float(metric_data.get("ci_low")),
                "ci_high": _float(metric_data.get("ci_high")),
                "win_rate": _float(metric_data.get("win_rate")),
                "effect_size_dz": metric_data.get("effect_size_dz"),
            }
        )
    return {
        "metric": metric,
        "only_h2_families": only_h2,
        "n_families": len(rows),
        "family_balanced_mean_delta": float(np.mean(deltas)) if deltas else 0.0,
        "family_balanced_std_delta": float(np.std(deltas, ddof=1)) if len(deltas) > 1 else 0.0,
        "families": rows,
    }


def _prediction_by_key(predictions: Sequence[Mapping[str, Any]]) -> Dict[tuple[str, str], Mapping[str, Any]]:
    out: Dict[tuple[str, str], Mapping[str, Any]] = {}
    for pred in predictions:
        out[(str(pred.get("model_name")), str(pred.get("task_id")))] = pred
    return out


def _collect_examples(sweep_dir: Path, max_examples: int = 20) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    child_runs = read_json(sweep_dir / "child_runs.json") if (sweep_dir / "child_runs.json").exists() else []
    false_examples: List[Dict[str, Any]] = []
    traces: List[Dict[str, Any]] = []
    for child in child_runs:
        seed = int(child.get("seed", 0))
        run_dir = Path(str(child["run_dir"]))
        rows = read_json(run_dir / "results.json") if (run_dir / "results.json").exists() else []
        predictions = read_json(run_dir / "predictions.json") if (run_dir / "predictions.json").exists() else []
        pred_map = _prediction_by_key(predictions)
        for row in rows:
            if str(row.get("model_name")) != "proposer_only":
                continue
            if _float(row.get("false_rule_accepted")) <= 0.0:
                continue
            if len(false_examples) < max_examples:
                false_examples.append(
                    {
                        "seed": seed,
                        "run_dir": str(run_dir),
                        "task_id": row.get("task_id"),
                        "family": row.get("family"),
                        "true_program": row.get("true_program"),
                        "proposer_only_predicted_program": row.get("predicted_program"),
                        "test_pair_accuracy": _float(row.get("test_pair_accuracy")),
                        "ood_pair_accuracy": _float(row.get("ood_pair_accuracy")),
                        "designed_ambiguity_level": row.get("designed_ambiguity_level"),
                        "distractor_condition": row.get("distractor_condition"),
                        "compositional_condition": row.get("compositional_condition"),
                    }
                )
            pf_pred = pred_map.get(("proposer_falsifier", str(row.get("task_id"))), {})
            candidate = dict(pf_pred.get("candidate") or {})
            diagnostics = dict(candidate.get("diagnostics") or {})
            trace = {
                "seed": seed,
                "run_dir": str(run_dir),
                "task_id": row.get("task_id"),
                "family": row.get("family"),
                "true_program": row.get("true_program"),
                "proposer_only_predicted_program": row.get("predicted_program"),
                "proposer_falsifier_predicted_program": candidate.get("program_signature"),
                "selector": diagnostics.get("selector"),
                "accepted_falsifier_report": diagnostics.get("falsifier"),
                "reports_considered": diagnostics.get("falsifier_reports_considered", []),
                "oracle_probe_budget": diagnostics.get("oracle_probe_budget"),
                "oracle_probes_used": diagnostics.get("oracle_probes_used"),
                "passive_checks_used": diagnostics.get("passive_checks_used"),
            }
            if len(traces) < max_examples:
                traces.append(trace)
    return false_examples, traces


def write_h2_family_balanced_analysis(sweep_dir: str | Path, max_examples: int = 20) -> Dict[str, Any]:
    sweep_path = ensure_dir(sweep_dir)
    stratified = read_json(sweep_path / "stratified_paired_contrasts.json")
    families = _family_contrasts(stratified)
    summaries = {
        "all_families_false_rule_accepted": _balanced_metric_summary(
            families, "false_rule_accepted", only_h2=False
        ),
        "h2_families_false_rule_accepted": _balanced_metric_summary(
            families, "false_rule_accepted", only_h2=True
        ),
        "h2_families_heldout_behavior_recovered": _balanced_metric_summary(
            families, "heldout_behavior_recovered", only_h2=True
        ),
        "h2_families_test_pair_accuracy": _balanced_metric_summary(
            families, "test_pair_accuracy", only_h2=True
        ),
    }
    false_examples, traces = _collect_examples(sweep_path, max_examples=max_examples)
    report = {
        "sweep_dir": str(sweep_path),
        "contrast": H2_CONTRAST,
        "boundary": "Family-balanced revised H2 analysis; this does not broaden H2 beyond ambiguity/composition strata.",
        "summaries": summaries,
        "false_rule_examples_count": len(false_examples),
        "falsifier_traces_count": len(traces),
    }
    write_json(sweep_path / "family_balanced_h2_analysis.json", report)
    write_json(sweep_path / "accepted_false_rule_examples.json", false_examples)
    write_json(sweep_path / "falsifier_counterexample_traces.json", traces)
    _write_markdown(sweep_path / "family_balanced_h2_analysis.md", report)
    _write_examples_markdown(sweep_path / "accepted_false_rule_examples.md", false_examples, traces)
    return report


def _write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    summaries = dict(report.get("summaries", {}))
    lines = [
        "# Family-Balanced H2 Analysis",
        "",
        "Boundary: revised H2 remains conditional. This report asks whether falsification helps on ambiguous/compositional strata without letting a single family dominate the mean.",
        "",
        f"- sweep: `{report.get('sweep_dir')}`",
        f"- contrast: `{report.get('contrast')}`",
        f"- false-rule examples: {report.get('false_rule_examples_count', 0)}",
        f"- falsifier traces: {report.get('falsifier_traces_count', 0)}",
        "",
        "## Balanced Summaries",
        "",
        "|summary|metric|families|family_balanced_mean_delta|family_balanced_std_delta|",
        "|---|---|---:|---:|---:|",
    ]
    for name, summary in sorted(summaries.items()):
        lines.append(
            "|{}|{}|{}|{:.3f}|{:.3f}|".format(
                name,
                summary.get("metric"),
                int(summary.get("n_families", 0)),
                _float(summary.get("family_balanced_mean_delta")),
                _float(summary.get("family_balanced_std_delta")),
            )
        )
    lines.extend(["", "## Per-Family False-Rule Acceptance Delta", ""])
    h2_summary = dict(summaries.get("h2_families_false_rule_accepted", {}))
    lines.extend(["|family|n|mean_delta|ci|win_rate|", "|---|---:|---:|---|---:|"])
    for family in h2_summary.get("families", []):
        lines.append(
            "|{}|{}|{:.3f}|[{:.3f}, {:.3f}]|{:.3f}|".format(
                family.get("family"),
                int(family.get("n", 0)),
                _float(family.get("mean_delta")),
                _float(family.get("ci_low")),
                _float(family.get("ci_high")),
                _float(family.get("win_rate")),
            )
        )
    write_text(path, "\n".join(lines) + "\n")


def _write_examples_markdown(
    path: Path,
    examples: Sequence[Mapping[str, Any]],
    traces: Sequence[Mapping[str, Any]],
) -> None:
    lines = [
        "# H2 Accepted False Rules And Falsifier Traces",
        "",
        "Accepted false-rule examples are proposer-only rows whose selected train-fitting rule failed held-out behavior. Traces show the corresponding proposer-falsifier candidate diagnostics when available.",
        "",
        "## Accepted False Rules",
        "",
        "|seed|family|task|true_program|proposer_only_program|test_acc|ood_acc|",
        "|---:|---|---|---|---|---:|---:|",
    ]
    for example in examples:
        lines.append(
            "|{}|{}|{}|{}|{}|{:.3f}|{:.3f}|".format(
                int(example.get("seed", 0)),
                example.get("family", ""),
                example.get("task_id", ""),
                example.get("true_program", ""),
                example.get("proposer_only_predicted_program", ""),
                _float(example.get("test_pair_accuracy")),
                _float(example.get("ood_pair_accuracy")),
            )
        )
    lines.extend(["", "## Falsifier Trace Summary", ""])
    lines.extend(["|seed|family|task|pf_program|selector|oracle_used|passive_used|", "|---:|---|---|---|---|---:|---:|"])
    for trace in traces:
        lines.append(
            "|{}|{}|{}|{}|{}|{}|{}|".format(
                int(trace.get("seed", 0)),
                trace.get("family", ""),
                trace.get("task_id", ""),
                trace.get("proposer_falsifier_predicted_program", ""),
                trace.get("selector", ""),
                trace.get("oracle_probes_used", ""),
                trace.get("passive_checks_used", ""),
            )
        )
    write_text(path, "\n".join(lines) + "\n")
