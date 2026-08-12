#!/usr/bin/env python3
"""Phase C: Cross-domain operator transfer deep evaluation.

Tests whether operator schemas instantiate across grid, graph, chess, molecule
domains. Tests same-domain invention/verification and cross-domain zero/few-shot.
"""
import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.cross_domain_operator_semantics import (
    OPERATOR_FAMILIES, DOMAIN_REALIZATIONS, OperatorFamilyName,
    TransferMatrix, instantiate_across_domains,
)


DOMAIN_PAIRS = [
    ("grid", "graph"),
    ("grid", "chess"),
    ("grid", "molecule"),
    ("graph", "molecule"),
    ("graph", "grid"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/cross_domain_operator_transfer")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "certificates").mkdir(exist_ok=True)

    print("=== Phase C: Cross-Domain Operator Transfer Deep Eval ===")

    with open(output_dir / "status.json", "w") as f:
        json.dump({"status": "running", "started": datetime.now().isoformat()}, f)

    matrix = TransferMatrix()

    # Operator family catalog
    catalog_lines = ["# Operator Family Catalog", ""]
    catalog_rows = []
    for name, family in OPERATOR_FAMILIES.items():
        catalog_lines.append(f"## {name.name}")
        catalog_lines.append(f"\n{family.description}\n")
        catalog_lines.append("### Preconditions")
        for p in family.abstract_preconditions:
            catalog_lines.append(f"- {p}")
        catalog_lines.append("\n### Postconditions")
        for p in family.abstract_postconditions:
            catalog_lines.append(f"- {p}")
        catalog_lines.append("\n### Invariants")
        for p in family.abstract_invariants:
            catalog_lines.append(f"- {p}")
        catalog_lines.append("\n### Ambiguity Conditions")
        for p in family.ambiguity_conditions:
            catalog_lines.append(f"- {p}")
        catalog_lines.append("")

        catalog_rows.append({
            "family": name.name,
            "description": family.description,
            "n_preconditions": len(family.abstract_preconditions),
            "n_postconditions": len(family.abstract_postconditions),
            "n_invariants": len(family.abstract_invariants),
            "n_realizations": sum(1 for k in DOMAIN_REALIZATIONS if k[1] == name),
        })

    with open(output_dir / "operator_family_catalog.md", "w") as f:
        f.write("\n".join(catalog_lines) + "\n")
    with open(output_dir / "operator_family_catalog.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(catalog_rows[0].keys()))
        writer.writeheader()
        for r in catalog_rows:
            writer.writerow(r)

    # Transfer tests
    all_results = []
    for family_name in OperatorFamilyName:
        for src, tgt in DOMAIN_PAIRS:
            print(f"  {family_name.name}: {src} -> {tgt}...")
            result = instantiate_across_domains(family_name, src, tgt)
            matrix.add(result)
            all_results.append({
                "family": family_name.name,
                "source": src,
                "target": tgt,
                "schema_reuse": result.schema_reuse_success,
                "zero_shot": result.zero_shot_success,
                "few_shot": result.few_shot_success,
                "solved": result.tasks_solved,
                "attempted": result.tasks_attempted,
                "fp": result.false_positives,
                "failure": result.failure_reason or "",
            })
            status = "OK" if result.schema_reuse_success else "FAIL"
            print(f"    schema_reuse={result.schema_reuse_success}, zero_shot={result.zero_shot_success} [{status}]")

    # Write results
    with open(output_dir / "transfer_matrix.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)

    with open(output_dir / "results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)

    # Failure taxonomy
    failures = {}
    for r in all_results:
        if r["failure"]:
            failures[r["failure"]] = failures.get(r["failure"], 0) + 1
    with open(output_dir / "failure_taxonomy.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["failure_reason", "count"])
        for reason, count in sorted(failures.items(), key=lambda x: -x[1]):
            writer.writerow([reason, count])

    # Summary
    total_schema = sum(1 for r in all_results if r["schema_reuse"])
    total_zero = sum(1 for r in all_results if r["zero_shot"])
    total_tests = len(all_results)

    lines = [
        "# Cross-Domain Operator Transfer — Summary",
        f"\nGenerated: {datetime.now().isoformat()}",
        "",
        f"## Results: {total_schema}/{total_tests} schema reuse, {total_zero}/{total_tests} zero-shot",
        "",
        "| Family | Source | Target | Schema Reuse | Zero-Shot | Failure |",
        "|--------|--------|--------|-------------|-----------|---------|",
    ]
    for r in all_results:
        lines.append(f"| {r['family']} | {r['source']} | {r['target']} | {r['schema_reuse']} | {r['zero_shot']} | {r['failure'][:40]} |")

    lines += [
        "",
        "## Assessment",
        "",
    ]
    if total_schema > 0:
        lines.append(f"**Partially supported:** {total_schema} operator family×domain pairs have schema realizations in both domains.")
    else:
        lines.append("**Not supported:** No operator schemas successfully instantiated across domain pairs.")
    if total_zero > 0:
        lines.append(f"**Zero-shot transfer:** {total_zero} pairs have executable realizations.")
    else:
        lines.append("**Zero-shot transfer not demonstrated.**")

    with open(output_dir / "summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    with open(output_dir / "status.json", "w") as f:
        json.dump({"status": "completed", "finished": datetime.now().isoformat()}, f)

    print(f"\nTotal: {total_schema}/{total_tests} schema reuse, {total_zero}/{total_tests} zero-shot")
    print(f"Written to {output_dir}/")


if __name__ == "__main__":
    main()
