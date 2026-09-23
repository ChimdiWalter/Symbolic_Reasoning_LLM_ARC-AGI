"""Artifact generation for experiment summaries and manuscript sections."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .evaluation import aggregate_metrics, hypothesis_verdicts
from .utils import configure_matplotlib_cache, ensure_dir, write_json, write_text


def write_metrics_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    out = Path(path)
    ensure_dir(out.parent)
    if not rows:
        write_text(out, "")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown_table(path: str | Path, summary: Mapping[str, Any]) -> None:
    by_model = summary.get("by_model", {})
    columns = [
        "model",
        "test_pair_accuracy",
        "ood_pair_accuracy",
        "latent_rule_recovered",
        "heldout_behavior_recovered",
        "causal_factor_recovery",
        "false_rule_selected",
        "false_rule_accepted",
        "counterexample_survival_rate",
        "recovery_after_corruption",
    ]
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join(["---"] * len(columns)) + "|"]
    for model, metrics in sorted(by_model.items()):
        values = [model]
        for key in columns[1:]:
            values.append(f"{float(metrics.get(key, 0.0)):.3f}")
        lines.append("|" + "|".join(values) + "|")
    write_text(path, "\n".join(lines) + "\n")


def plot_accuracy_by_model(path: str | Path, summary: Mapping[str, Any]) -> None:
    configure_matplotlib_cache(Path(path).parent)
    import matplotlib.pyplot as plt

    by_model = summary.get("by_model", {})
    models = list(sorted(by_model))
    test = [float(by_model[m].get("test_pair_accuracy", 0.0)) for m in models]
    ood = [float(by_model[m].get("ood_pair_accuracy", 0.0)) for m in models]
    x = range(len(models))
    fig, ax = plt.subplots(figsize=(max(7, len(models) * 0.9), 4))
    ax.bar([i - 0.18 for i in x], test, width=0.36, label="test")
    ax.bar([i + 0.18 for i in x], ood, width=0.36, label="ood")
    ax.set_ylabel("pair accuracy")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=35, ha="right")
    ax.legend()
    fig.tight_layout()
    ensure_dir(Path(path).parent)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_rule_recovery(path: str | Path, summary: Mapping[str, Any]) -> None:
    configure_matplotlib_cache(Path(path).parent)
    import matplotlib.pyplot as plt

    by_model = summary.get("by_model", {})
    models = list(sorted(by_model))
    values = [float(by_model[m].get("latent_rule_recovered", 0.0)) for m in models]
    fig, ax = plt.subplots(figsize=(max(7, len(models) * 0.9), 4))
    ax.plot(models, values, marker="o")
    ax.set_ylabel("latent rule recovery")
    ax.set_ylim(0, 1.05)
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    ensure_dir(Path(path).parent)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _format_verdicts(verdicts: Mapping[str, str]) -> str:
    return "\n".join(f"- `{key}`: {value}" for key, value in sorted(verdicts.items()))


def write_reports(run_dir: str | Path, rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> Dict[str, Any]:
    run_path = ensure_dir(run_dir)
    summary = aggregate_metrics(rows)
    verdicts = hypothesis_verdicts(summary)
    write_json(run_path / "summary.json", summary)
    write_json(run_path / "hypothesis_verdicts.json", verdicts)
    write_metrics_csv(run_path / "metrics.csv", rows)
    write_markdown_table(run_path / "tables" / "ablation_summary.md", summary)
    plot_accuracy_by_model(run_path / "figures" / "accuracy_by_model.png", summary)
    plot_rule_recovery(run_path / "figures" / "rule_recovery_by_model.png", summary)
    write_results_documents(run_path, summary, verdicts, config)
    return {"summary": summary, "verdicts": verdicts}


def write_results_documents(
    run_path: Path,
    summary: Mapping[str, Any],
    verdicts: Mapping[str, str],
    config: Mapping[str, Any],
) -> None:
    by_model = summary.get("by_model", {})
    lines = [
        "# Results Summary",
        "",
        "This report is generated from the current run artifacts. It should not be read as a final empirical claim unless the run is sufficiently powered. H2 is conditional: falsification is evaluated as an ambiguity-resolution mechanism, not as a broad truth guarantee.",
        "",
        "## Per-Hypothesis Verdicts",
        "",
        _format_verdicts(verdicts),
        "",
        "## Model Summary",
        "",
    ]
    for model, metrics in sorted(by_model.items()):
        lines.append(
        f"- `{model}`: test pair accuracy {float(metrics.get('test_pair_accuracy', 0.0)):.3f}, "
        f"OOD pair accuracy {float(metrics.get('ood_pair_accuracy', 0.0)):.3f}, "
        f"latent rule recovery {float(metrics.get('latent_rule_recovered', 0.0)):.3f}, "
        f"behavioral recovery {float(metrics.get('heldout_behavior_recovered', 0.0)):.3f}, "
        f"false-rule acceptance {float(metrics.get('false_rule_accepted', 0.0)):.3f}."
        )
    write_text(run_path / "reports" / "results_summary.md", "\n".join(lines) + "\n")

    limitations = """# Limitations

- The default smoke config is too small for publication-level statistical conclusions.
- The direct input-output baseline is a nearest-example proxy rather than a trained transformer.
- Synthetic oracle probes are available only in hidden-rule micro-worlds and are not passive inference.
- Compression uses MDL-like proxies, sparsity, nuisance robustness, and intervention stability. Exact description-length claims are limited to bounded DSL minimality under the declared finite coding scheme; exact Kolmogorov complexity is not computed.
- Topology is checked exactly only for declared finite support/component/hole invariants over bounded domains; broad topology theorems are not claimed.
- Larger repeated-seed experiments are needed before claiming support for any hypothesis.
- H2 should be interpreted only through compute-matched and stratified proposer-only versus proposer-falsifier contrasts.
"""
    write_text(run_path / "reports" / "limitations.md", limitations)

    methods = """# Methods

The benchmark samples colored-grid tasks with known latent programs. Each task contains train, validation, test, and OOD examples. Models infer a candidate program from training examples and predict held-out outputs.

The implemented scientist-model pipeline is:

Input grid -> deterministic object parser -> relation graph summary -> finite hypothesis proposer -> program executor -> falsifier -> compression/intervention selector -> repair diagnostic -> output renderer.

The mathematical language is operational: compositionality is a program library, verification by falsification is candidate rejection by counterexamples under explicit budgets, path equivalence is repair after controlled corruption, and causal compression is approximated by description length plus perturbation robustness. Exact bounded claims are separated into finite DSL minimality, exact small-category checks, and operator-specific topology audits.
"""
    write_text(run_path / "reports" / "methods.md", methods)

    experiments = f"""# Experiments

Run config:

```json
{config}
```

Ablations include direct input-output proxy, object-centric detector, transformation library, proposer-only, proposer-falsifier, compression selector, path repair, and integrated scientist model.
"""
    write_text(run_path / "reports" / "experiments.md", experiments)

    appendix = """# Appendix

Artifacts generated by the run:

- `dataset.json`
- `predictions.json`
- `results.json`
- `metrics.csv`
- `summary.json`
- `hypothesis_verdicts.json`
- `figures/accuracy_by_model.png`
- `figures/rule_recovery_by_model.png`
- `tables/ablation_summary.md`
"""
    write_text(run_path / "reports" / "appendix.md", appendix)

    failure = """# Failure Cases

Failure cases are listed in `results.json` by task and model. Inspect rows where `test_pair_accuracy` or `ood_pair_accuracy` is below 1.0, and compare `true_program` with `predicted_program`.
"""
    write_text(run_path / "reports" / "failure_cases.md", failure)


def write_manuscript(paper_dir: str | Path, run_summary_path: str | Path | None = None) -> None:
    paper = ensure_dir(paper_dir)

    def write_paper_text(path: Path, text: str) -> None:
        if path.exists():
            return
        write_text(path, text)

    title_options = """# Title Options

1. Scientist-Model Inductive Biases for Synthetic Hidden-Rule Discovery
2. Testing Compositional, Falsification, Repair, and Compression Biases in Colored-Grid Reasoning
3. A Reproducible Scaffold for Abstract Reasoning and Latent Program Recovery
"""
    write_paper_text(paper / "title_options.md", title_options)

    draft = """# Scientist-Model Inductive Biases for Abstract Reasoning and Hidden-Rule Discovery

## Abstract

We present a reproducible experimental scaffold for evaluating whether abstract reasoning systems benefit from four operational inductive biases: compositional transformations, conditional verification by falsification, repairable reasoning trajectories, and causal-compression style selection. The implementation uses synthetic colored-grid tasks with known latent programs, deterministic object/relation parsing, explicit transformation libraries, falsification diagnostics, bounded DSL description-length checks, and repair-after-corruption tests. The formal layer gives exact finite statements for DSL minimality, small-category laws, and operator-specific topology invariants only inside declared bounded domains. The framework is designed to support honest ablations rather than to assert that any single mathematical metaphor has been fully realized.

## Introduction

Many reasoning benchmarks reward surface input-output matching even when the intended solution is a compact hidden rule. This project asks when systems that represent candidate rules explicitly and test them against counterexamples can generalize more reliably on synthetic abstract tasks.

## Related Work Map

Relevant areas include program synthesis for visual reasoning, ARC-style abstraction tasks, object-centric representation learning, causal representation learning, minimum-description-length model selection, adversarial testing, and self-repair or self-consistency methods for reasoning systems.

## Methods

Tasks are generated from finite compositions of grid transformations. Objects are same-color connected components. Relations include approximate adjacency, containment, symmetry, and component topology summaries. Candidate programs are executed exactly over grids.

For bounded formal checks, the same executable DSL is treated as a finite search space under explicit depth and color limits. Within that declared space, the implementation computes exact shortest-program length under an integer coding scheme. The formal layer also checks small-category laws exactly over enumerated finite grid domains and audits operator-specific support/component/hole invariants over bounded topology domains.

The implemented scientist-model pipeline is:

Input -> object parser -> relation graph -> hypothesis generator -> executor -> falsifier -> compression selector -> repair diagnostic -> renderer.

## What Is Implemented

- Explicit finite program library over grid transformations.
- Deterministic object and relation parser.
- Passive contradiction checks and optional synthetic hidden-world probes, interpreted as conditional verification rather than a broad truth oracle.
- MDL-like description length, sparsity, nuisance robustness, and intervention stability proxies.
- Controlled program corruption and candidate-neighborhood repair.

## What Is Approximate

- Causal compression is approximated; exact Kolmogorov complexity is not computed. Exact description-length claims are limited to bounded DSL minimality under the declared coding scheme.
- Topology preservation is represented by exact bounded support/component/hole audits, not broad topology theorems.
- Game-semantic language corresponds to proposer-falsifier interaction, not a formal game model.
- Category-theoretic language corresponds to exact small-category checks in declared finite systems, not a general categorical semantics of reasoning.

## Experiments

The ablation suite compares direct input-output proxy, object-centric baseline, transformation library, proposer-only, proposer-falsifier, compression selector, path repair, and the integrated scientist model on train/val/test/OOD examples.

## ARC Status

The project can be tested on local ARC-AGI files through the ARC adapter. ARC evaluation is treated as an external-validity diagnostic: it measures output accuracy, solve-rate proxies, runtime, and qualitative failure cases, but it does not compute latent-rule recovery because ARC files do not expose ground-truth latent programs. ARC smoke and diagnostic outputs are not ARC benchmark or leaderboard claims.

## Revised H2

H2 is tested as a conditional verification-by-falsification hypothesis: falsification should help primarily when several train-fitting hypotheses diverge under perturbations, held-out examples, distractors, or compositional edge cases. Reports should break out H2 by ambiguity level, family, distractor condition, compositional condition, verification budget, and compute-match condition.

## Results

Results must be filled from `outputs/<run>/summary.json`, `outputs/<run>/hypothesis_verdicts.json`, and for H2 from stratified paired sweep artifacts. Do not claim support for H1-H5 unless the generated metrics show it.

## Limitations

The synthetic smoke experiment and ARC smoke/diagnostic experiments are validation or external-validity runs, not powered studies. The direct baseline is a proxy rather than a trained transformer. Interactive oracle probes are synthetic diagnostics. H2 evidence must be read conditionally by stratum and compute budget. Larger repeated-seed runs are required for publication-grade empirical claims. ARC outputs must be treated as adapter/evaluator diagnostics unless a stronger pre-registered ARC protocol is run.

The exact mathematical claims are bounded. Exact DSL minimality holds only over the enumerated candidate set and declared coding scheme; exact small-category checks hold only over supplied finite domains and morphisms; exact topology claims hold only for the audited operators and bounded support/component/hole invariants. The project does not compute exact Kolmogorov complexity, provide a general categorical semantics of reasoning, or prove broad topological theorems.

## Reproducibility Statement

The repository includes configs, fixed seeds, JSON artifacts, metrics CSVs, tests, and resumable run state. All generated task examples include true latent-rule metadata for audit, while models only receive the examples specified by the experiment runner.
"""
    write_paper_text(paper / "manuscript_draft.md", draft)
    write_paper_text(
        paper / "sections" / "abstract.md",
        draft.split("## Abstract", 1)[1].split("## Introduction", 1)[0].strip() + "\n",
    )
    write_paper_text(
        paper / "sections" / "methods.md",
        draft.split("## Methods", 1)[1].split("## What Is Implemented", 1)[0].strip() + "\n",
    )
    write_paper_text(
        paper / "sections" / "limitations.md",
        draft.split("## Limitations", 1)[1].split("## Reproducibility Statement", 1)[0].strip() + "\n",
    )
    write_paper_text(
        paper / "sections" / "arc_status.md",
        draft.split("## ARC Status", 1)[1].split("## Revised H2", 1)[0].strip() + "\n",
    )
