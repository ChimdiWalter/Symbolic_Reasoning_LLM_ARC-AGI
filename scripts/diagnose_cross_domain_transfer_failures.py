#!/usr/bin/env python3.11
"""Diagnose why cross-domain transfer got only 2/20."""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/cross_domain_transfer"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing transfer results
    deep_dir = PROJECT_ROOT / "outputs/deep_project_completion/cross_domain_operator_transfer"

    results_csv = deep_dir / "results.csv"
    transfer_rows = []
    if results_csv.exists():
        with open(results_csv) as f:
            transfer_rows = list(csv.DictReader(f))

    failure_taxonomy_csv = deep_dir / "failure_taxonomy.csv"
    failure_counts = {}
    if failure_taxonomy_csv.exists():
        with open(failure_taxonomy_csv) as f:
            for row in csv.DictReader(f):
                failure_counts[row.get("failure_reason", "")] = int(row.get("count", 0))

    diagnosis_categories = [
        "no_shared_operator_semantics",
        "adapter_object_mismatch",
        "property_not_mapped",
        "relation_not_mapped",
        "operator_precondition_not_ported",
        "parameter_transfer_failed",
        "domain_specific_execution_missing",
        "certificate_schema_missing",
        "task_pair_not_aligned",
    ]

    diagnosis_rows = []

    # Analyze each failed transfer
    for row in transfer_rows:
        family = row.get("family", "")
        source = row.get("source", "")
        target = row.get("target", "")
        schema_reuse = row.get("schema_reuse") == "True"
        zero_shot = row.get("zero_shot") == "True"
        failure = row.get("failure", "")

        if zero_shot:
            diagnosis_rows.append({
                "family": family,
                "source": source,
                "target": target,
                "failure_category": "none",
                "detail": "Transfer succeeded (zero-shot)",
                "severity": "info",
            })
            continue

        # Classify failure
        if "no realization" in failure:
            target_domain = failure.replace("no realization for ", "")
            diagnosis_rows.append({
                "family": family,
                "source": source,
                "target": target,
                "failure_category": "domain_specific_execution_missing",
                "detail": f"No realization defined for '{target_domain}' domain. "
                          "The adapter exists but operator-specific execution is not implemented.",
                "severity": "critical",
            })
        elif "precondition" in failure.lower():
            diagnosis_rows.append({
                "family": family,
                "source": source,
                "target": target,
                "failure_category": "operator_precondition_not_ported",
                "detail": failure,
                "severity": "high",
            })
        elif "property" in failure.lower() or "mapping" in failure.lower():
            diagnosis_rows.append({
                "family": family,
                "source": source,
                "target": target,
                "failure_category": "property_not_mapped",
                "detail": failure,
                "severity": "high",
            })
        else:
            diagnosis_rows.append({
                "family": family,
                "source": source,
                "target": target,
                "failure_category": "domain_specific_execution_missing",
                "detail": failure if failure else "No failure reason recorded",
                "severity": "high",
            })

    # Analyze which domains lack realizations
    from collections import Counter
    missing_domains = Counter()
    for row in diagnosis_rows:
        if row["failure_category"] == "domain_specific_execution_missing":
            missing_domains[row["target"]] += 1

    # Write CSV
    csv_path = OUTPUT_DIR / "diagnosis.csv"
    with open(csv_path, "w", newline="") as f:
        fields = ["family", "source", "target", "failure_category", "detail", "severity"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(diagnosis_rows)

    # Write markdown
    md_path = OUTPUT_DIR / "diagnosis.md"
    with open(md_path, "w") as f:
        f.write(f"# Cross-Domain Transfer Failure Diagnosis\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Summary\n\n")
        successes = sum(1 for r in diagnosis_rows if r["failure_category"] == "none")
        failures = len(diagnosis_rows) - successes
        f.write(f"- Successful transfers: {successes}/20\n")
        f.write(f"- Failed transfers: {failures}/20\n\n")

        f.write("## Missing Domain Realizations\n\n")
        f.write("| Target Domain | Missing Realizations |\n|------|------|\n")
        for domain, count in missing_domains.most_common():
            f.write(f"| {domain} | {count} |\n")

        f.write("\n## Per-Transfer Diagnosis\n\n")
        f.write("| Family | Source→Target | Category | Severity | Detail |\n")
        f.write("|--------|---------------|----------|----------|--------|\n")
        for r in diagnosis_rows:
            f.write(f"| {r['family']} | {r['source']}→{r['target']} | "
                    f"{r['failure_category']} | {r['severity']} | {r['detail'][:60]} |\n")

        f.write("\n## Root Cause\n\n")
        f.write("The dominant failure is **domain_specific_execution_missing**: operator families have "
                "abstract schemas (preconditions, postconditions, invariants) but only grid and graph "
                "have concrete execution implementations. Chess, molecule, and other domains have adapters "
                "(object extraction, properties) but no operator-specific execution bindings.\n\n")

        f.write("## Recommended Patches\n\n")
        f.write("1. Add concrete `realize(task, adapter)` methods for each operator family × domain\n")
        f.write("2. The realization should map abstract preconditions to domain-specific property checks\n")
        f.write("3. Start with the simplest family (PROJECT_TO_NEIGHBORHOOD) which already works grid↔graph\n")
        f.write("4. Add aligned benchmark tasks so transfer can be tested on tasks that SHOULD transfer\n")

    print(f"Diagnosis: {md_path}")
    print(f"CSV: {csv_path}")
    print(f"Successes: {successes}/20, Failures: {failures}/20")


if __name__ == "__main__":
    main()
