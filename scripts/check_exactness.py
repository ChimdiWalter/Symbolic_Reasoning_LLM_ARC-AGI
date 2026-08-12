#!/usr/bin/env python3
"""Generate bounded exactness reports for the finite DSL/category/topology layer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.formal import (
    audit_operator_topology_suite,
    bounded_exact_dsl_minimum,
    check_finite_category_laws,
    enumerate_binary_grids,
    finite_group_morphisms_for_reflections,
)
from reasoning_project.operators import apply_program
from reasoning_project.schemas import ProgramStep, TaskExample
from reasoning_project.utils import ensure_dir, utc_timestamp, write_json, write_text


def _identity_examples(domain):
    return [TaskExample(input_grid=grid, output_grid=grid.copy(), metadata={}) for grid in domain]


def _program_examples(domain, program):
    return [TaskExample(input_grid=grid, output_grid=apply_program(grid, program), metadata={}) for grid in domain]


def _topology_domain():
    domain = enumerate_binary_grids((3, 3))
    colored_singletons = []
    grid = domain[0].copy()
    grid[0, 0] = 1
    grid[2, 2] = 2
    colored_singletons.append(grid)
    adjacent = domain[0].copy()
    adjacent[1, 1] = 1
    adjacent[1, 2] = 2
    colored_singletons.append(adjacent)
    contained_like = domain[0].copy()
    contained_like[0, :] = 1
    contained_like[2, :] = 1
    contained_like[:, 0] = 1
    contained_like[:, 2] = 1
    contained_like[1, 1] = 2
    colored_singletons.append(contained_like)
    return domain + colored_singletons


def _write_exactness_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Bounded Exactness Report",
        "",
        "Boundary: all exact claims in this report are finite and bounded. None are claims of exact Kolmogorov complexity, general categorical semantics of reasoning, or broad topological theorems.",
        "",
        "## Domain",
        "",
        f"- description domain: `{report['description_length']['domain']}`",
        f"- category domain: `{report['category']['domain']}`",
        f"- topology domain: `{report['topology']['domain']}`",
        "",
        "## Exact Bounded DSL Minimum",
        "",
        "|case|candidate_count|satisfying_count|min_units|min_programs|",
        "|---|---:|---:|---:|---|",
    ]
    for case, data in report["description_length"]["cases"].items():
        lines.append(
            "|{}|{}|{}|{}|{}|".format(
                case,
                data["candidate_count"],
                data["satisfying_count"],
                data["minimum_code_length_units"],
                ", ".join(data["minimum_program_signatures"]),
            )
        )
    category = report["category"]["report"]
    lines.extend(
        [
            "",
            "## Exact Small-Category Checks",
            "",
            f"- identity law holds: `{category['identity_law_holds']}`",
            f"- associativity holds: `{category['associativity_holds']}`",
            f"- composition well-defined: `{category['composition_well_defined_holds']}`",
            f"- closure holds for supplied morphism set: `{category['closure_holds']}`",
            f"- equality notion: {category['equality_notion']}",
            "",
            "## Topology Summary",
            "",
            "|classification|count|",
            "|---|---:|",
        ]
    )
    for classification, count in sorted(report["topology"]["classification_counts"].items()):
        lines.append(f"|{classification}|{count}|")
    lines.extend(
        [
            "",
            "Counterexamples for failing operators are stored in `topology_operator_audit.json`.",
        ]
    )
    write_text(path, "\n".join(lines) + "\n")


def _write_topology_markdown(path: Path, reports: list[dict]) -> None:
    lines = [
        "# Topology Operator Audit",
        "",
        "Invariant definition: color-insensitive binary support topology, using exact support mask, 4-connected support component count, and support hole count.",
        "",
        "Domain: all binary 3x3 grids plus selected colored 3x3 probes.",
        "",
        "|operator|classification|support_mask|components|holes|counterexample_keys|",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in reports:
        lines.append(
            "|{}|{}|{}|{}|{}|{}|".format(
                item["operator_signature"],
                item["classification"],
                item["support_mask_preserved"],
                item["component_count_preserved"],
                item["hole_count_preserved"],
                ", ".join(sorted(item["counterexamples"])),
            )
        )
    write_text(path, "\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded exactness checks.")
    parser.add_argument("--output-dir", default="outputs/exactness")
    args = parser.parse_args()

    out = ensure_dir(args.output_dir)
    description_domain = enumerate_binary_grids((2, 2))
    category_domain = enumerate_binary_grids((2, 2))
    topology_domain = _topology_domain()
    colors = [1, 2]
    max_depth = 1

    identity_report = bounded_exact_dsl_minimum(
        _identity_examples(description_domain),
        max_depth=max_depth,
        colors=colors,
    )
    reflect_program = [ProgramStep("reflect_vertical")]
    reflect_report = bounded_exact_dsl_minimum(
        _program_examples(description_domain, reflect_program),
        max_depth=max_depth,
        colors=colors,
    )
    category_report = check_finite_category_laws(
        finite_group_morphisms_for_reflections(),
        category_domain,
        require_closure=True,
    )
    topology_reports = [report.to_dict() for report in audit_operator_topology_suite(topology_domain, colors=colors)]
    classification_counts = {}
    for report in topology_reports:
        classification_counts[report["classification"]] = classification_counts.get(report["classification"], 0) + 1

    exactness_report = {
        "created_at": utc_timestamp(),
        "description_length": {
            "domain": "all binary 2x2 grids",
            "max_depth": max_depth,
            "colors": colors,
            "cases": {
                "identity": identity_report.to_dict(),
                "reflect_vertical": reflect_report.to_dict(),
            },
            "non_claim": "not exact Kolmogorov complexity",
        },
        "category": {
            "domain": "all binary 2x2 grids",
            "morphism_set": [m.to_dict() for m in finite_group_morphisms_for_reflections()],
            "report": category_report.to_dict(),
            "non_claim": "not a general categorical semantics of reasoning",
        },
        "topology": {
            "domain": "all binary 3x3 grids plus selected colored 3x3 probes",
            "operator_count": len(topology_reports),
            "classification_counts": classification_counts,
            "non_claim": "not a broad topological invariant theorem",
        },
    }

    write_json(
        out / "config.json",
        {
            "output_dir": str(out),
            "description_domain": "2x2 binary",
            "topology_domain": "3x3 binary plus selected colored probes",
        },
    )
    write_json(out / "seed_list.json", {"seeds": []})
    write_text(
        out / "command_log.md",
        "# Command Log\n\n```bash\npython3.11 scripts/check_exactness.py --output-dir outputs/exactness\n```\n",
    )
    write_json(out / "resume_instructions.json", {"resume_command": "python3.11 scripts/check_exactness.py --output-dir outputs/exactness"})
    write_json(out / "exactness_report.json", exactness_report)
    write_json(out / "topology_operator_audit.json", topology_reports)
    _write_exactness_markdown(out / "exactness_report.md", exactness_report)
    _write_topology_markdown(out / "topology_operator_audit.md", topology_reports)
    write_json(
        out / "manifest.json",
        {
            "kind": "bounded_exactness",
            "created_at": utc_timestamp(),
            "artifacts": [
                "config.json",
                "seed_list.json",
                "command_log.md",
                "resume_instructions.json",
                "exactness_report.json",
                "exactness_report.md",
                "topology_operator_audit.json",
                "topology_operator_audit.md",
            ],
        },
    )
    print(f"wrote exactness reports to {out}")


if __name__ == "__main__":
    main()
