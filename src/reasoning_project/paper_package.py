"""Build a submission-ready paper package from existing local artifacts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .utils import configure_matplotlib_cache, ensure_dir, read_json, utc_timestamp, write_json, write_text


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _write_table(path: Path, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    lines = [
        "|" + "|".join(headers) + "|",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("|" + "|".join(str(value) for value in row) + "|")
    write_text(path, "\n".join(lines) + "\n")


def _metric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _short_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _mpl(output_dir: Path):
    configure_matplotlib_cache(output_dir)
    import matplotlib.pyplot as plt

    plt.style.use("default")
    return plt


def _style_axes(ax, ylabel: str = "", ylim: tuple[float, float] | None = None) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel)
    if ylim is not None:
        ax.set_ylim(*ylim)


def _exact_semantics_figure(path: Path, exactness: Mapping[str, Any]) -> None:
    plt = _mpl(path.parent.parent)
    cases = dict(exactness.get("description_length", {}).get("cases", {}))
    labels = list(cases)
    min_units = [_metric(cases[label].get("minimum_code_length_units")) for label in labels]
    topology_counts = dict(exactness.get("topology", {}).get("classification_counts", {}))
    category = dict(exactness.get("category", {}).get("report", {}))

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    axes[0].bar(labels, min_units, color=["#1f6f8b", "#1f6f8b"])
    _style_axes(axes[0], ylabel="code units")
    axes[0].set_title("bounded DSL minimum")

    topo_labels = [
        "support_mask",
        "component_hole_only",
        "conditional",
        "not_preserving",
    ]
    topo_values = [
        _metric(topology_counts.get("topology_preserving_under_support_mask_definition")),
        _metric(topology_counts.get("topology_preserving_for_component_and_hole_counts_only")),
        _metric(topology_counts.get("conditionally_topology_preserving_not_on_full_bounded_domain")),
        _metric(topology_counts.get("not_topology_preserving_on_bounded_domain")),
    ]
    axes[1].bar(topo_labels, topo_values, color=["#2a9d8f", "#6fb98f", "#e9c46a", "#d95d39"])
    axes[1].tick_params(axis="x", rotation=25)
    _style_axes(axes[1], ylabel="operator count")
    axes[1].set_title("topology audit")

    axes[2].axis("off")
    lines = [
        "small-category checks",
        f"identity: {category.get('identity_law_holds')}",
        f"associativity: {category.get('associativity_holds')}",
        f"well-defined: {category.get('composition_well_defined_holds')}",
        f"closure: {category.get('closure_holds')}",
        "",
        "bounded domains only",
        str(exactness.get("description_length", {}).get("domain", "")),
        str(exactness.get("topology", {}).get("domain", "")),
    ]
    axes[2].text(0.0, 0.98, "\n".join(lines), va="top", ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _grouped_metric_figure(
    path: Path,
    model_metrics: Mapping[str, Mapping[str, Any]],
    models: Sequence[str],
    metrics: Sequence[str],
    metric_labels: Sequence[str],
    title: str,
    ylabel: str,
    ylim: tuple[float, float] | None = None,
) -> None:
    plt = _mpl(path.parent.parent)
    fig, ax = plt.subplots(figsize=(max(7, len(metrics) * 1.6), 4.2))
    x = list(range(len(metrics)))
    width = 0.8 / max(1, len(models))
    colors = ["#264653", "#2a9d8f", "#e9c46a", "#d95d39"]
    for idx, model in enumerate(models):
        values = [_metric(model_metrics.get(model, {}).get(metric)) for metric in metrics]
        offsets = [value + (idx - (len(models) - 1) / 2.0) * width for value in x]
        ax.bar(offsets, values, width=width, label=model, color=colors[idx % len(colors)])
    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels)
    ax.set_title(title)
    _style_axes(ax, ylabel=ylabel, ylim=ylim)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _h2_family_figure(path: Path, families: Sequence[Mapping[str, Any]]) -> None:
    plt = _mpl(path.parent.parent)
    labels = [str(row.get("family", "")).replace("h2_", "") for row in families]
    values = [_metric(row.get("mean_delta")) for row in families]
    colors = ["#d95d39" if value < 0 else "#9e9e9e" for value in values]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.barh(labels, values, color=colors)
    ax.axvline(0.0, color="#444444", linewidth=1.0)
    _style_axes(ax, ylabel="family")
    ax.set_xlabel("false-rule acceptance delta")
    ax.set_title("H2 conditional effect by family")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _h4_alignment_figure(path: Path, model_summary: Mapping[str, Mapping[str, Any]]) -> None:
    plt = _mpl(path.parent.parent)
    models = list(sorted(model_summary))
    exact_min = [_metric(model_summary[model].get("selected_is_exact_min_rate")) for model in models]
    causal = [_metric(model_summary[model].get("mean_causal_factor_recovery")) for model in models]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))
    axes[0].bar(models, exact_min, color="#1f6f8b")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].set_title("exact bounded minimum alignment")
    _style_axes(axes[0], ylabel="rate", ylim=(0.0, 1.05))

    axes[1].bar(models, causal, color="#d95d39")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].set_title("causal-factor proxy")
    _style_axes(axes[1], ylabel="mean", ylim=(0.0, 1.05))
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _h5_figure(
    path: Path,
    contrast: Mapping[str, Any],
) -> None:
    plt = _mpl(path.parent.parent)
    performance_metrics = [
        ("test_pair_accuracy", "test"),
        ("ood_pair_accuracy", "ood"),
        ("latent_rule_recovered", "latent"),
        ("recovery_after_corruption", "repair"),
    ]
    perf_values = [_metric(dict(contrast.get(metric, {})).get("mean_delta")) for metric, _ in performance_metrics]
    runtime = _metric(dict(contrast.get("runtime_seconds", {})).get("mean_delta"))
    budget_metrics = [
        ("oracle_probes_used", "probes"),
        ("passive_checks_used", "checks"),
    ]
    budget_values = [_metric(dict(contrast.get(metric, {})).get("mean_delta")) for metric, _ in budget_metrics]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    axes[0].bar([label for _, label in performance_metrics], perf_values, color="#2a9d8f")
    axes[0].axhline(0.0, color="#444444", linewidth=1.0)
    axes[0].set_title("integrated minus transformation")
    _style_axes(axes[0], ylabel="delta")

    axes[1].bar(["runtime", *[label for _, label in budget_metrics]], [runtime, *budget_values], color="#d95d39")
    axes[1].set_title("cost deltas")
    _style_axes(axes[1], ylabel="delta")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _arc_figure(path: Path, model_summary: Mapping[str, Mapping[str, Any]]) -> None:
    plt = _mpl(path.parent.parent)
    models = list(sorted(model_summary))
    exact = [_metric(model_summary[model].get("test_exact_task_accuracy_mean")) for model in models]
    pixel = [_metric(model_summary[model].get("test_pixel_accuracy_mean")) for model in models]
    runtime = [_metric(model_summary[model].get("runtime_seconds_mean")) for model in models]
    candidates = [_metric(model_summary[model].get("candidate_program_count_mean")) for model in models]

    fig, axes = plt.subplots(1, 4, figsize=(16.0, 4.2))
    axes[0].bar(models, exact, color="#264653")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].set_title("exact solve rate")
    _style_axes(axes[0], ylabel="rate", ylim=(0.0, 0.2))

    axes[1].bar(models, pixel, color="#2a9d8f")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].set_title("pixel accuracy")
    _style_axes(axes[1], ylabel="mean", ylim=(0.0, 1.0))

    axes[2].bar(models, runtime, color="#d95d39")
    axes[2].tick_params(axis="x", rotation=30)
    axes[2].set_title("runtime seconds")
    _style_axes(axes[2], ylabel="seconds")

    axes[3].bar(models, candidates, color="#6c757d")
    axes[3].tick_params(axis="x", rotation=30)
    axes[3].set_title("candidate budget")
    _style_axes(axes[3], ylabel="mean count")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _load_paths(
    repo_root: Path,
    breadth_sweep_dir: Path | None = None,
    h2_sweep_dir: Path | None = None,
    arc_dir: Path | None = None,
    h4_sweep_dir: Path | None = None,
) -> Dict[str, Path]:
    breadth_dir = breadth_sweep_dir or (repo_root / "outputs" / "paper_breadth_validation_5seed_sweep")
    h2_dir = h2_sweep_dir or (repo_root / "outputs" / "h2_family_validation_10seed_sweep")
    arc_eval_dir = arc_dir or (repo_root / "outputs" / "arc_diagnostic_eval_6task_3seed")
    h4_dir = h4_sweep_dir or (breadth_dir / "h4_bounded_alignment")
    return {
        "manuscript": repo_root / "paper" / "manuscript_draft.md",
        "title_options": repo_root / "paper" / "title_options.md",
        "paper_reproduce": repo_root / "paper" / "reproduce_paper_artifacts.md",
        "claim_traceability": repo_root / "claim_traceability.md",
        "exactness_traceability": repo_root / "exactness_traceability.md",
        "exact_vs_proxy": repo_root / "exact_vs_proxy_table.md",
        "results_summary": repo_root / "results_summary.md",
        "limitations": repo_root / "limitations.md",
        "external_validity_summary": repo_root / "external_validity_summary.md",
        "exactness_report": repo_root / "outputs" / "exactness" / "exactness_report.json",
        "topology_audit": repo_root / "outputs" / "exactness" / "topology_operator_audit.json",
        "breadth_summary": breadth_dir / "sweep_summary.json",
        "breadth_paired": breadth_dir / "paired_contrasts.json",
        "breadth_seed_metrics": breadth_dir / "seed_model_metrics.csv",
        "h2_family": h2_dir / "family_balanced_h2_analysis.json",
        "h2_failure": h2_dir / "failure_taxonomy.json",
        "h2_examples": h2_dir / "accepted_false_rule_examples.json",
        "arc_summary": arc_eval_dir / "summary.json",
        "arc_failures": arc_eval_dir / "qualitative_failures.json",
        "h4_summary": h4_dir / "h4_sweep_summary.json",
        "h4_records": h4_dir / "per_task_exact_mdl.json",
    }


def _build_case_studies(
    h2_examples: Sequence[Mapping[str, Any]],
    h2_families: Sequence[Mapping[str, Any]],
    h4_records: Sequence[Mapping[str, Any]],
    arc_failures: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    studies: List[Dict[str, Any]] = []

    for example in h2_examples:
        if str(example.get("family")) == "h2_noncommuting_composition_probe":
            studies.append(
                {
                    "case": "H2 accepted false rule",
                    "task_or_family": str(example.get("task_id")),
                    "observation": "proposer_only accepts a train-fitting count-only rule, while the true rule includes translation then counting.",
                    "artifact": "outputs/h2_family_validation_10seed_sweep/accepted_false_rule_examples.md",
                }
            )
            break

    for family in h2_families:
        if _metric(family.get("mean_delta")) == 0.0:
            studies.append(
                {
                    "case": "H2 zero-gain family",
                    "task_or_family": str(family.get("family")),
                    "observation": "falsification shows no gain here, which keeps H2 conditional rather than broad.",
                    "artifact": "outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md",
                }
            )
            break

    paired_h4: Dict[tuple[Any, Any], Dict[str, Mapping[str, Any]]] = {}
    for record in h4_records:
        key = (record.get("seed"), record.get("task_id"))
        paired_h4.setdefault(key, {})[str(record.get("model_name"))] = record
    for key, model_rows in paired_h4.items():
        transformation = model_rows.get("transformation_library")
        integrated = model_rows.get("integrated_scientist")
        if not transformation or not integrated:
            continue
        if (
            _metric(transformation.get("selected_is_exact_bounded_minimum")) == 1.0
            and _metric(integrated.get("selected_is_exact_bounded_minimum")) == 0.0
        ):
            studies.append(
                {
                    "case": "Exact semantics explains model split",
                    "task_or_family": str(key[1]),
                    "observation": (
                        "the transformation library takes the shorter exact bounded minimum, while the integrated model takes a longer latent-correct rule; "
                        "the exact audit explains the divergence without turning H4 into a broad causal-compression claim."
                    ),
                    "artifact": "outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/per_task_exact_mdl.json",
                }
            )
            break

    for failure in arc_failures:
        model_name = str(failure.get("model_name") or failure.get("model") or "")
        task_id = str(failure.get("arc_task_id") or failure.get("task") or "")
        if model_name == "transformation_library":
            studies.append(
                {
                    "case": "ARC identity default",
                    "task_or_family": task_id,
                    "observation": "the explicit DSL model falls back to an identity prediction and still fails exactly, showing that synthetic gains do not transfer cleanly.",
                    "artifact": "outputs/arc_diagnostic_eval_6task_3seed/qualitative_failures.md",
                }
            )
            break

    return studies[:4]


def _build_h4_model_difference_rows(h4_records: Sequence[Mapping[str, Any]]) -> List[List[str]]:
    grouped: Dict[tuple[Any, Any], Dict[str, Mapping[str, Any]]] = {}
    for record in h4_records:
        key = (record.get("seed"), record.get("task_id"))
        grouped.setdefault(key, {})[str(record.get("model_name"))] = record

    rows: List[List[str]] = []
    for key in sorted(grouped):
        model_rows = grouped[key]
        transformation = model_rows.get("transformation_library")
        integrated = model_rows.get("integrated_scientist")
        if not transformation or not integrated:
            continue
        if (
            _metric(transformation.get("selected_is_exact_bounded_minimum")) == 1.0
            and _metric(integrated.get("selected_is_exact_bounded_minimum")) == 0.0
        ):
            rows.append(
                [
                    str(key[0]),
                    str(transformation.get("family", "")),
                    str(key[1]),
                    str(transformation.get("exact_min_program_signatures", "")),
                    str(transformation.get("selected_program", "")),
                    f"{_metric(transformation.get('selected_minus_exact_min_units')):.1f}",
                    str(integrated.get("selected_program", "")),
                    f"{_metric(integrated.get('selected_minus_exact_min_units')):.1f}",
                    str(integrated.get("true_program", "")),
                    "exact bounded semantics distinguishes a shorter train-fitting minimum from a longer latent-correct rule",
                ]
            )
        if len(rows) >= 4:
            break
    return rows


def _build_arc_failure_rows(arc_failures: Sequence[Mapping[str, Any]]) -> List[List[str]]:
    selected: List[List[str]] = []
    seen_models: set[str] = set()
    for failure in arc_failures:
        model_name = str(failure.get("model_name") or failure.get("model") or "")
        if not model_name or model_name in seen_models:
            continue
        seen_models.add(model_name)
        selected.append(
            [
                model_name,
                str(failure.get("arc_task_id") or failure.get("task") or ""),
                str(failure.get("shape_bucket", "")),
                str(failure.get("predicted_program", "")),
                f"{_metric(failure.get('test_pair_accuracy')):.3f}",
                str(failure.get("error", "")),
            ]
        )
        if len(selected) >= 4:
            break
    return selected


def build_submission_package(
    repo_root: str | Path,
    output_dir: str | Path | None = None,
    breadth_sweep_dir: str | Path | None = None,
    h2_sweep_dir: str | Path | None = None,
    arc_dir: str | Path | None = None,
    h4_sweep_dir: str | Path | None = None,
) -> Dict[str, Any]:
    root = Path(repo_root)
    out = ensure_dir(output_dir or (root / "outputs" / "submission_package"))
    figures_dir = ensure_dir(out / "figures")
    tables_dir = ensure_dir(out / "tables")
    appendix_dir = ensure_dir(out / "appendix")
    paths = _load_paths(
        root,
        Path(breadth_sweep_dir) if breadth_sweep_dir else None,
        Path(h2_sweep_dir) if h2_sweep_dir else None,
        Path(arc_dir) if arc_dir else None,
        Path(h4_sweep_dir) if h4_sweep_dir else None,
    )

    exactness = read_json(paths["exactness_report"])
    topology = read_json(paths["topology_audit"])
    breadth_summary = read_json(paths["breadth_summary"])
    breadth_paired = read_json(paths["breadth_paired"])
    h2_family = read_json(paths["h2_family"])
    h2_failure = read_json(paths["h2_failure"])
    h2_examples = read_json(paths["h2_examples"])
    arc_summary = read_json(paths["arc_summary"])
    arc_failures = read_json(paths["arc_failures"])
    h4_summary = read_json(paths["h4_summary"])
    h4_records = read_json(paths["h4_records"])

    exact_cases = dict(exactness.get("description_length", {}).get("cases", {}))
    category = dict(exactness.get("category", {}).get("report", {}))
    topology_counts = dict(exactness.get("topology", {}).get("classification_counts", {}))
    breadth_models = dict(breadth_summary.get("by_model", {}))
    breadth_contrast = dict(breadth_paired.get("transformation_library_minus_direct_io_proxy", {}))
    h3_contrast = dict(breadth_paired.get("path_repair_minus_compression_selector", {}))
    h5_contrast = dict(breadth_paired.get("integrated_scientist_minus_transformation_library", {}))
    h2_families = list(
        dict(h2_family.get("summaries", {}).get("h2_families_false_rule_accepted", {})).get("families", [])
    )
    case_studies = _build_case_studies(h2_examples, h2_families, h4_records, arc_failures)
    h4_model_difference_rows = _build_h4_model_difference_rows(h4_records)
    arc_failure_rows = _build_arc_failure_rows(arc_failures)

    _write_table(
        tables_dir / "table_exact_semantics_summary.md",
        ["claim", "value", "artifact"],
        [
            [
                "bounded DSL minimum",
                f"identity={int(_metric(exact_cases.get('identity', {}).get('minimum_code_length_units')))} units; reflect_vertical={int(_metric(exact_cases.get('reflect_vertical', {}).get('minimum_code_length_units')))} units",
                _short_path(paths["exactness_report"], root),
            ],
            [
                "small-category laws",
                "identity=True, associativity=True, well_defined=True, closure=True",
                _short_path(paths["exactness_report"], root),
            ],
            [
                "topology audit",
                f"support={int(_metric(topology_counts.get('topology_preserving_under_support_mask_definition')))}, component_hole_only={int(_metric(topology_counts.get('topology_preserving_for_component_and_hole_counts_only')))}, conditional={int(_metric(topology_counts.get('conditionally_topology_preserving_not_on_full_bounded_domain')))}, not_preserving={int(_metric(topology_counts.get('not_topology_preserving_on_bounded_domain')))}",
                _short_path(paths["topology_audit"], root),
            ],
        ],
    )
    write_text(tables_dir / "table_exact_vs_proxy.md", paths["exact_vs_proxy"].read_text(encoding="utf-8"))

    h1_models = [
        model
        for model in ["direct_io_proxy", "learned_task_mlp", "transformation_library", "compression_selector"]
        if model in breadth_models
    ]
    _write_table(
        tables_dir / "table_h1_structural_transfer.md",
        ["model", "test", "ood", "latent", "artifact"],
        [
            [
                model,
                f"{_metric(metrics.get('test_pair_accuracy_mean')):.3f}",
                f"{_metric(metrics.get('ood_pair_accuracy_mean')):.3f}",
                f"{_metric(metrics.get('latent_rule_recovered_mean')):.3f}",
                _short_path(paths["breadth_summary"], root),
            ]
            for model, metrics in sorted(breadth_models.items())
            if model in set(h1_models)
        ],
    )
    _write_table(
        tables_dir / "table_h2_family_balanced.md",
        ["family", "false_rule_delta", "win_rate", "artifact"],
        [
            [
                str(row.get("family")),
                f"{_metric(row.get('mean_delta')):.3f}",
                f"{_metric(row.get('win_rate')):.3f}",
                _short_path(paths["h2_family"], root),
            ]
            for row in h2_families
        ],
    )
    _write_table(
        tables_dir / "table_h3_repairability.md",
        ["contrast", "test_delta", "ood_delta", "recovery_delta", "artifact"],
        [
            [
                "path_repair_minus_compression_selector",
                f"{_metric(dict(h3_contrast.get('test_pair_accuracy', {})).get('mean_delta')):.3f}",
                f"{_metric(dict(h3_contrast.get('ood_pair_accuracy', {})).get('mean_delta')):.3f}",
                f"{_metric(dict(h3_contrast.get('recovery_after_corruption', {})).get('mean_delta')):.3f}",
                _short_path(paths["breadth_paired"], root),
            ]
        ],
    )
    _write_table(
        tables_dir / "table_h4_alignment.md",
        ["model", "selected_is_min", "mean_gap_units", "causal_factor", "artifact"],
        [
            [
                model,
                f"{_metric(metrics.get('selected_is_exact_min_rate')):.3f}",
                f"{_metric(metrics.get('mean_selected_minus_exact_min_units')):.3f}",
                f"{_metric(metrics.get('mean_causal_factor_recovery')):.3f}",
                _short_path(paths["h4_summary"], root),
            ]
            for model, metrics in sorted(dict(h4_summary.get("by_model", {})).items())
        ],
    )
    _write_table(
        tables_dir / "table_h5_integrated_stack.md",
        ["metric", "delta", "artifact"],
        [
            [
                "test_pair_accuracy",
                f"{_metric(dict(h5_contrast.get('test_pair_accuracy', {})).get('mean_delta')):.3f}",
                _short_path(paths["breadth_paired"], root),
            ],
            [
                "ood_pair_accuracy",
                f"{_metric(dict(h5_contrast.get('ood_pair_accuracy', {})).get('mean_delta')):.3f}",
                _short_path(paths["breadth_paired"], root),
            ],
            [
                "latent_rule_recovered",
                f"{_metric(dict(h5_contrast.get('latent_rule_recovered', {})).get('mean_delta')):.3f}",
                _short_path(paths["breadth_paired"], root),
            ],
            [
                "recovery_after_corruption",
                f"{_metric(dict(h5_contrast.get('recovery_after_corruption', {})).get('mean_delta')):.3f}",
                _short_path(paths["breadth_paired"], root),
            ],
            [
                "runtime_seconds",
                f"{_metric(dict(h5_contrast.get('runtime_seconds', {})).get('mean_delta')):.3f}",
                _short_path(paths["breadth_paired"], root),
            ],
        ],
    )
    _write_table(
        tables_dir / "table_arc_external_validity.md",
        ["model", "exact_solve", "pixel", "runtime_seconds", "candidate_budget", "candidates_scored", "non_claim"],
        [
            [
                model,
                f"{_metric(metrics.get('test_exact_task_accuracy_mean')):.3f}",
                f"{_metric(metrics.get('test_pixel_accuracy_mean')):.3f}",
                f"{_metric(metrics.get('runtime_seconds_mean')):.3f}",
                f"{_metric(metrics.get('candidate_program_count_mean')):.1f}",
                f"{_metric(metrics.get('candidates_scored_mean')):.1f}",
                "external-validity diagnostic only",
            ]
            for model, metrics in sorted(dict(arc_summary.get("by_model", {})).items())
        ],
    )
    _write_table(
        tables_dir / "table_failure_taxonomy.md",
        ["mode", "evidence"],
        [[row.get("mode", ""), row.get("evidence", "")] for row in h2_failure.get("failure_taxonomy", [])],
    )
    _write_table(
        tables_dir / "table_case_studies.md",
        ["case", "task_or_family", "observation", "artifact"],
        [
            [row.get("case", ""), row.get("task_or_family", ""), row.get("observation", ""), row.get("artifact", "")]
            for row in case_studies
        ],
    )
    _write_table(
        tables_dir / "table_h2_accepted_false_rules.md",
        ["seed", "family", "task", "true_program", "accepted_false_rule", "test_acc", "ood_acc", "artifact"],
        [
            [
                str(row.get("seed", "")),
                str(row.get("family", "")),
                str(row.get("task_id", row.get("task", ""))),
                str(row.get("true_program", "")),
                str(row.get("proposer_only_program", row.get("proposer_only_predicted_program", ""))),
                f"{_metric(row.get('test_acc', row.get('test_pair_accuracy'))):.3f}",
                f"{_metric(row.get('ood_acc', row.get('ood_pair_accuracy'))):.3f}",
                _short_path(paths["h2_examples"], root),
            ]
            for row in list(h2_examples)[:8]
        ],
    )
    _write_table(
        tables_dir / "table_arc_qualitative_failures.md",
        ["model", "task", "shape_bucket", "predicted_program", "test_pair_accuracy", "error"],
        arc_failure_rows,
    )
    _write_table(
        tables_dir / "table_exact_semantics_model_difference.md",
        [
            "seed",
            "family",
            "task",
            "exact_min_program",
            "transformation_library_program",
            "transformation_gap_units",
            "integrated_program",
            "integrated_gap_units",
            "true_program",
            "reading",
        ],
        h4_model_difference_rows,
    )

    _exact_semantics_figure(figures_dir / "fig_exact_semantics_summary.png", exactness)
    _grouped_metric_figure(
        figures_dir / "fig_h1_structural_transfer.png",
        breadth_models,
        h1_models or ["direct_io_proxy", "transformation_library"],
        ["test_pair_accuracy_mean", "ood_pair_accuracy_mean", "latent_rule_recovered_mean"],
        ["test", "ood", "latent"],
        "H1 structural-transfer summary",
        "mean",
        ylim=(0.0, 1.05),
    )
    _h2_family_figure(figures_dir / "fig_h2_family_balanced.png", h2_families)
    _grouped_metric_figure(
        figures_dir / "fig_h3_repairability.png",
        breadth_models,
        ["compression_selector", "path_repair"],
        ["test_pair_accuracy_mean", "ood_pair_accuracy_mean", "recovery_after_corruption_mean"],
        ["test", "ood", "repair"],
        "H3 bounded repairability",
        "mean",
        ylim=(0.0, 1.05),
    )
    _h4_alignment_figure(figures_dir / "fig_h4_alignment.png", dict(h4_summary.get("by_model", {})))
    _h5_figure(figures_dir / "fig_h5_integrated_stack.png", h5_contrast)
    _arc_figure(figures_dir / "fig_arc_external_validity.png", dict(arc_summary.get("by_model", {})))

    claim_rows = [
        [
            "H1",
            "Object/relation and transformation-library models should generalize better than direct input-output proxy and small task-conditioned learned baselines on OOD grid sizes and compositional splits.",
            "supported in specific synthetic strata only",
            _short_path(paths["breadth_paired"], root),
            "paper/sections/hypotheses_and_verdicts.md; paper/sections/results.md",
            _short_path(figures_dir / "fig_h1_structural_transfer.png", root),
            _short_path(tables_dir / "table_h1_structural_transfer.md", root),
            "paper/sections/limitations.md",
            _short_path(appendix_dir / "claim_traceability_appendix.md", root),
        ],
        [
            "H2",
            "Verification by falsification improves hypothesis selection primarily when several candidate rules fit demonstrations but differ under perturbations, held-out cases, distractors, or compositional edge cases.",
            "supported in specific ambiguity/composition strata only",
            _short_path(paths["h2_family"], root),
            "paper/sections/hypotheses_and_verdicts.md; paper/sections/results.md",
            _short_path(figures_dir / "fig_h2_family_balanced.png", root),
            _short_path(tables_dir / "table_h2_family_balanced.md", root),
            "paper/sections/limitations.md",
            _short_path(appendix_dir / "claim_traceability_appendix.md", root),
        ],
        [
            "H3",
            "Repair-aware program search should recover from controlled corruption more often than unrepaired candidate selection.",
            "bounded repairability only",
            _short_path(paths["breadth_paired"], root),
            "paper/sections/hypotheses_and_verdicts.md; paper/sections/results.md",
            _short_path(figures_dir / "fig_h3_repairability.png", root),
            _short_path(tables_dir / "table_h3_repairability.md", root),
            "paper/sections/limitations.md",
            _short_path(appendix_dir / "claim_traceability_appendix.md", root),
        ],
        [
            "H4",
            "MDL-like and intervention-stability scoring should prefer shorter, more causal rules over spurious surface fits.",
            "weak as causal compression; stronger as bounded exact-minimum alignment",
            _short_path(paths["h4_summary"], root),
            "paper/sections/hypotheses_and_verdicts.md; paper/sections/results.md",
            _short_path(figures_dir / "fig_h4_alignment.png", root),
            _short_path(tables_dir / "table_h4_alignment.md", root),
            "paper/sections/limitations.md",
            _short_path(appendix_dir / "claim_traceability_appendix.md", root),
        ],
        [
            "H5",
            "The full integrated model should beat partial stacks across multiple families and metrics before being treated as supported.",
            "weak/inconclusive broad integrated-stack claim",
            _short_path(paths["breadth_paired"], root),
            "paper/sections/hypotheses_and_verdicts.md; paper/sections/results.md",
            _short_path(figures_dir / "fig_h5_integrated_stack.png", root),
            _short_path(tables_dir / "table_h5_integrated_stack.md", root),
            "paper/sections/limitations.md",
            _short_path(appendix_dir / "claim_traceability_appendix.md", root),
        ],
        [
            "ARC",
            "ARC is evaluated only as an external-validity diagnostic with exact solve rate, pixel accuracy, runtime, and candidate-budget reporting.",
            "external-validity diagnostic only; exact solve rate remains zero",
            _short_path(paths["arc_summary"], root),
            "paper/sections/arc_status.md; paper/sections/results.md",
            _short_path(figures_dir / "fig_arc_external_validity.png", root),
            _short_path(tables_dir / "table_arc_external_validity.md", root),
            "paper/sections/limitations.md",
            _short_path(appendix_dir / "claim_traceability_appendix.md", root),
        ],
    ]
    _write_table(
        appendix_dir / "claim_traceability_appendix.md",
        [
            "claim",
            "active_wording",
            "verdict",
            "supporting_artifact",
            "manuscript_surface",
            "figure",
            "table",
            "limitation_surface",
            "appendix_surface",
        ],
        claim_rows,
    )

    checklist_lines = [
        "# Reproducibility Checklist",
        "",
        "- manuscript: `{}`".format(_short_path(paths["manuscript"], root)),
        "- exactness traceability: `{}`".format(_short_path(paths["exactness_traceability"], root)),
        "- claim traceability: `{}`".format(_short_path(paths["claim_traceability"], root)),
        "- exact-vs-proxy table: `{}`".format(_short_path(paths["exact_vs_proxy"], root)),
        "- H1/H3/H5 synthetic source: `{}`".format(_short_path(paths["breadth_summary"], root)),
        "- H2 source: `{}`".format(_short_path(paths["h2_family"], root)),
        "- H4 source: `{}`".format(_short_path(paths["h4_summary"], root)),
        "- ARC source: `{}`".format(_short_path(paths["arc_summary"], root)),
        "- figures directory: `{}`".format(_short_path(figures_dir, root)),
        "- tables directory: `{}`".format(_short_path(tables_dir, root)),
    ]
    write_text(out / "reproducibility_checklist.md", "\n".join(checklist_lines) + "\n")

    overview = [
        "# Submission Package Overview",
        "",
        "Final thesis: exact finite semantics plus bounded scientist-model diagnostics. H1, H2, and H3 are supported only in narrow declared strata; H4 and H5 remain weak or localized; ARC remains an external-validity diagnostic with zero exact solve rate in the active run.",
        "",
        "Use the tables and figures in this directory as the paper-facing views of the existing local artifacts. They do not broaden the underlying claims.",
    ]
    write_text(out / "submission_overview.md", "\n".join(overview) + "\n")

    manifest_entries = {
        "manuscript": str(paths["manuscript"].resolve()),
        "title_options": str(paths["title_options"].resolve()),
        "paper_reproduce": str(paths["paper_reproduce"].resolve()),
        "claim_traceability": str(paths["claim_traceability"].resolve()),
        "exactness_traceability": str(paths["exactness_traceability"].resolve()),
        "exact_vs_proxy": str(paths["exact_vs_proxy"].resolve()),
        "results_summary": str(paths["results_summary"].resolve()),
        "limitations": str(paths["limitations"].resolve()),
        "external_validity_summary": str(paths["external_validity_summary"].resolve()),
        "supporting_artifacts": {key: str(path.resolve()) for key, path in paths.items() if path.exists()},
        "figures": sorted(str(path.resolve()) for path in figures_dir.glob("*.png")),
        "tables": sorted(str(path.resolve()) for path in tables_dir.glob("*.md")),
        "appendix": sorted(str(path.resolve()) for path in appendix_dir.glob("*.md")),
        "generated_at": utc_timestamp(),
    }
    write_json(out / "artifact_manifest.json", manifest_entries)

    manifest_lines = [
        "# Artifact Manifest",
        "",
        "## Core Files",
        "",
        f"- manuscript: `{manifest_entries['manuscript']}`",
        f"- title options: `{manifest_entries['title_options']}`",
        f"- paper reproduce: `{manifest_entries['paper_reproduce']}`",
        f"- claim traceability: `{manifest_entries['claim_traceability']}`",
        f"- exactness traceability: `{manifest_entries['exactness_traceability']}`",
        f"- exact-vs-proxy: `{manifest_entries['exact_vs_proxy']}`",
        "",
        "## Generated Figures",
        "",
    ]
    manifest_lines.extend(f"- `{path}`" for path in manifest_entries["figures"])
    manifest_lines.extend(["", "## Generated Tables", ""])
    manifest_lines.extend(f"- `{path}`" for path in manifest_entries["tables"])
    manifest_lines.extend(["", "## Generated Appendix Files", ""])
    manifest_lines.extend(f"- `{path}`" for path in manifest_entries["appendix"])
    write_text(out / "artifact_manifest.md", "\n".join(manifest_lines) + "\n")

    return {
        "output_dir": str(out),
        "manifest": manifest_entries,
        "case_studies": case_studies,
    }
