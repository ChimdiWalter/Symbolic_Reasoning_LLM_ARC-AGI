#!/usr/bin/env python3
"""Write failure taxonomy and variance analysis for an inconclusive sweep."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.utils import write_json, write_text


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze variance and failure modes for a sweep.")
    parser.add_argument("--sweep-dir", required=True)
    parser.add_argument("--contrast", default="proposer_falsifier_minus_proposer_only")
    parser.add_argument("--metric", default="false_rule_accepted")
    args = parser.parse_args()

    sweep_dir = Path(args.sweep_dir)
    summary = json.load(open(sweep_dir / "sweep_summary.json", "r", encoding="utf-8"))
    contrasts = json.load(open(sweep_dir / "paired_contrasts.json", "r", encoding="utf-8"))
    stratified_path = sweep_dir / "stratified_paired_contrasts.json"
    stratified = json.load(open(stratified_path, "r", encoding="utf-8")) if stratified_path.exists() else {}
    deltas = _read_csv(sweep_dir / "paired_seed_deltas.csv")

    target = [
        row
        for row in deltas
        if row["contrast"] == args.contrast and row["metric"] == args.metric
    ]
    delta_values = [_float(row["delta"]) for row in target]
    win_count = sum(row["left_wins"] == "True" for row in target)
    tie_count = sum(row["tie"] == "True" for row in target)
    loss_count = len(target) - win_count - tie_count
    nonzero = [value for value in delta_values if value != 0.0]
    budget_metrics = [
        "runtime_seconds",
        "candidate_program_count",
        "candidates_scored",
        "candidates_falsified",
        "oracle_probe_budget",
        "oracle_probes_used",
        "passive_checks_used",
    ]
    budget_deltas = {}
    for metric in budget_metrics:
        metric_rows = [
            row
            for row in deltas
            if row["contrast"] == args.contrast and row["metric"] == metric
        ]
        values = [_float(row["delta"]) for row in metric_rows]
        if values:
            budget_deltas[metric] = {
                "n": len(values),
                "mean_delta": sum(values) / len(values),
                "max_abs_delta": max(abs(value) for value in values),
            }

    by_metric_variance = {}
    for model, metrics in summary.get("by_model", {}).items():
        by_metric_variance[model] = {
            key.removesuffix("_std"): value
            for key, value in metrics.items()
            if key.endswith("_std")
        }

    contrast_summary = contrasts.get(args.contrast, {}).get(args.metric, {})
    lower_is_better = bool(contrast_summary.get("lower_is_better", False))
    mean_delta = _float(contrast_summary.get("mean_delta"))
    ci_low = _float(contrast_summary.get("ci_low"))
    ci_high = _float(contrast_summary.get("ci_high"))
    clear_directional_result = (lower_is_better and ci_high < 0.0) or ((not lower_is_better) and ci_low > 0.0)
    count_budget_metrics = [
        "candidate_program_count",
        "candidates_scored",
        "candidates_falsified",
        "oracle_probe_budget",
        "oracle_probes_used",
        "passive_checks_used",
    ]
    compute_count_matched = all(
        metric in budget_deltas and budget_deltas[metric]["max_abs_delta"] == 0.0
        for metric in count_budget_metrics
    )
    event_counter = Counter()
    for row in target:
        if row["tie"] == "True":
            event_counter["ties"] += 1
        elif row["left_wins"] == "True":
            event_counter["left_wins"] += 1
        else:
            event_counter["left_losses"] += 1

    h2_strata = []
    for key, value in sorted(stratified.items()):
        if not key.endswith(args.contrast):
            continue
        metric_data = value.get(args.metric, {})
        h2_strata.append(
            {
                "stratum_field": value.get("stratum_field"),
                "stratum_value": value.get("stratum_value"),
                "n": value.get("n"),
                "mean_delta": metric_data.get("mean_delta"),
                "ci_low": metric_data.get("ci_low"),
                "ci_high": metric_data.get("ci_high"),
                "win_rate": metric_data.get("win_rate"),
                "effect_size_dz": metric_data.get("effect_size_dz"),
            }
        )
    positive_h2_families = [
        str(item["stratum_value"])
        for item in h2_strata
        if item.get("stratum_field") == "task_family"
        and str(item.get("stratum_value", "")).startswith("h2_")
        and (
            (_float(item.get("ci_high")) < 0.0 and lower_is_better)
            or (_float(item.get("ci_low")) > 0.0 and not lower_is_better)
        )
    ]
    family_scope = (
        ", ".join(positive_h2_families)
        if positive_h2_families
        else "the targeted constructed H2 probe families"
    )

    if clear_directional_result:
        taxonomy = [
            {
                "mode": "targeted_probe_positive_not_broad_h2_support",
                "evidence": (
                    f"{win_count}/{len(target)} paired seeds favored the left model on {args.metric}; "
                    f"mean delta {mean_delta} with 95% bootstrap CI [{ci_low}, {ci_high}]."
                ),
            },
            {
                "mode": "compute_count_matched_for_logged_budgets",
                "evidence": (
                    "Candidate/probe/check count deltas were exactly zero for logged budget metrics."
                    if compute_count_matched
                    else "At least one logged budget-count metric differed; inspect budget_delta_summary."
                ),
            },
            {
                "mode": "constructed_diagnostic_scope_limit",
                "evidence": (
                    "The positive strata are constructed train-ambiguity diagnostics "
                    f"({family_scope}); this is not broad ARC or AGI evidence."
                ),
            },
        ]
        likely_causes = [
            f"The constructed H2 families make simpler hypotheses fit training examples but fail held-out or probe cases: {family_scope}.",
            "Synthetic oracle probes expose hidden transformation, selection, or composition distinctions that are invisible in the demonstrations.",
            "The proposer-only control spends the same logged falsifier/probe budget but discards probe outcomes for selection.",
        ]
        next_experiment = {
            "name": "h2_independent_family_stress_test",
            "description": "Increase tasks_per_family and vary probe/distractor regimes for the independently designed H2 families, then re-run family-balanced compute-matched contrasts.",
        }
    else:
        taxonomy = [
            {
                "mode": "proposer_already_sufficient",
                "evidence": f"{tie_count}/{len(target)} paired seeds tied on {args.metric}; both models may already avoid the measured false-rule event.",
            },
            {
                "mode": "falsifier_budget_too_weak",
                "evidence": "If oracle/probe budget is low or not compute matched, candidate rejection may be underpowered.",
            },
            {
                "mode": "task_too_easy",
                "evidence": f"{tie_count}/{len(target)} paired seeds tied on {args.metric}.",
            },
            {
                "mode": "equivalent_rule_ambiguity",
                "evidence": "Some wrong signatures can be behaviorally equivalent on finite held-out domains.",
            },
            {
                "mode": "perturbation_set_too_weak",
                "evidence": "The falsifier may not sample perturbations that separate train-fitting candidates.",
            },
            {
                "mode": "metric_too_coarse",
                "evidence": f"{len(nonzero)}/{len(target)} paired deltas were non-zero.",
            },
            {
                "mode": "other_unresolved_variance",
                "evidence": "Remaining variance should be inspected with stratified paired deltas by family, ambiguity, distractors, composition, and budget.",
            },
        ]
        likely_causes = [
            "The diagnostic may be too easy for both models, so false-rule events are rare.",
            "Some syntactic mismatches are finite behavioral equivalences rather than actionable falsifier failures.",
            "The falsifier's probes may not be targeted enough at non-commuting compositional counterexamples.",
        ]
        next_experiment = {
            "name": "h2_noncommuting_composition_probe",
            "description": "Generate a tiny family of non-commuting compositional rules with distractors, run proposer-only versus proposer-falsifier with the same candidate depth and logged oracle-probe budget, and evaluate false-rule acceptance over 20 seeds.",
        }

    analysis = {
        "sweep_dir": str(sweep_dir),
        "contrast": args.contrast,
        "metric": args.metric,
        "n": len(target),
        "mean_delta": mean_delta,
        "std_delta": contrast_summary.get("std_delta"),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "win_count": win_count,
        "tie_count": tie_count,
        "loss_count": loss_count,
        "nonzero_delta_count": len(nonzero),
        "event_counter": dict(event_counter),
        "budget_delta_summary": budget_deltas,
        "stratified_h2_summary": h2_strata,
        "clear_directional_result": clear_directional_result,
        "compute_count_matched": compute_count_matched,
        "variance_by_model": by_metric_variance,
        "failure_taxonomy": taxonomy,
        "top_3_likely_causes": likely_causes,
        "next_minimal_experiment": next_experiment,
    }

    write_json(sweep_dir / "failure_taxonomy.json", analysis)
    boundary_text = (
        "This result can only be read as conditional H2 evidence in the reported strata and compute budget. It is not broad evidence that falsification generally improves reasoning."
        if clear_directional_result
        else "This analysis does not support broadening H2. It recommends narrower conditional diagnostics and stronger stratified compute-matched analysis before additional claims."
    )
    lines = [
        "# Failure Taxonomy And Variance Analysis",
        "",
        f"Sweep: `{sweep_dir}`",
        f"Contrast: `{args.contrast}`",
        f"Metric: `{args.metric}`",
        "",
        "## Paired Delta Summary",
        "",
        f"- n: {len(target)}",
        f"- mean delta: {contrast_summary.get('mean_delta')}",
        f"- std delta: {contrast_summary.get('std_delta')}",
        f"- 95% bootstrap CI: [{contrast_summary.get('ci_low')}, {contrast_summary.get('ci_high')}]",
        f"- wins/ties/losses: {win_count}/{tie_count}/{loss_count}",
        f"- nonzero paired deltas: {len(nonzero)}/{len(target)}",
        "",
        "## Budget Delta Summary",
        "",
    ]
    if budget_deltas:
        lines.append("|metric|n|mean_delta|max_abs_delta|")
        lines.append("|---|---|---|---|")
        for metric, values in sorted(budget_deltas.items()):
            lines.append(
                f"|{metric}|{values['n']}|{values['mean_delta']:.6f}|{values['max_abs_delta']:.6f}|"
            )
    else:
        lines.append("- No budget metrics were found in paired deltas.")
    lines.extend(
        [
            "",
            "## Stratified H2 Summary",
            "",
        ]
    )
    if h2_strata:
        lines.append("|stratum|n|mean_delta|95% CI|win_rate|dz|")
        lines.append("|---|---|---|---|---|---|")
        for item in h2_strata:
            dz = item.get("effect_size_dz")
            lines.append(
                "|{field}={value}|{n}|{mean:.6f}|[{low:.6f}, {high:.6f}]|{win:.3f}|{dz}|".format(
                    field=item.get("stratum_field"),
                    value=item.get("stratum_value"),
                    n=item.get("n"),
                    mean=float(item.get("mean_delta") or 0.0),
                    low=float(item.get("ci_low") or 0.0),
                    high=float(item.get("ci_high") or 0.0),
                    win=float(item.get("win_rate") or 0.0),
                    dz="NA" if dz is None else f"{float(dz):.3f}",
                )
            )
    else:
        lines.append("- No stratified paired contrast artifact was found.")
    lines.extend(
        [
            "",
        "## Failure Taxonomy",
        "",
        ]
    )
    for item in analysis["failure_taxonomy"]:
        lines.append(f"- `{item['mode']}`: {item['evidence']}")
    lines.extend(
        [
            "",
            "## Top 3 Likely Causes",
            "",
        ]
    )
    for cause in analysis["top_3_likely_causes"]:
        lines.append(f"- {cause}")
    lines.extend(
        [
            "",
            "## Next Minimal Experiment",
            "",
            f"- `{analysis['next_minimal_experiment']['name']}`: {analysis['next_minimal_experiment']['description']}",
            "",
            "## Boundary",
            "",
            boundary_text,
        ]
    )
    write_text(sweep_dir / "failure_taxonomy.md", "\n".join(lines) + "\n")
    print(f"wrote failure taxonomy to {sweep_dir / 'failure_taxonomy.md'}")


if __name__ == "__main__":
    main()
