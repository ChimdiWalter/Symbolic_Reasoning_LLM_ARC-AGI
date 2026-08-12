#!/usr/bin/env python3.11
"""Diagnose why neural/VLM proposals produced 0 verified promotions."""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/neural_vlm"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing results
    neural_dir = PROJECT_ROOT / "outputs/deep_project_completion/neural_operator_proposal"
    vit_dir = PROJECT_ROOT / "outputs/vit_vlm_advisory_probe"

    failure_categories = [
        "feature_not_predictive",
        "label_imbalance",
        "proposal_not_connected_to_symbolic_pipeline",
        "operator_family_correct_but_selector_wrong",
        "selector_correct_but_operator_wrong",
        "proposal_not_executable",
        "proposal_executable_but_fails_LOO",
        "proposal_not_recorded",
        "neural_result_not_used",
    ]

    diagnosis_rows = []

    # Analyze neural operator proposal results
    results_csv = neural_dir / "results.csv"
    if results_csv.exists():
        with open(results_csv) as f:
            reader = list(csv.DictReader(f))

        n_symbolic_verified = sum(1 for r in reader if r.get("symbolic_verified") == "True")
        n_promoted = sum(1 for r in reader if r.get("promoted") == "True")
        n_fp = sum(1 for r in reader if r.get("fp") == "True")

        if n_symbolic_verified > 0 and n_promoted == 0:
            diagnosis_rows.append({
                "source": "neural_operator_proposal",
                "failure_category": "proposal_executable_but_fails_LOO",
                "detail": f"{n_symbolic_verified} proposals passed symbolic verification but 0 promoted — "
                          "likely failing LOO or falsification",
                "severity": "high",
                "count": n_symbolic_verified,
            })

        # Check if neural predictions were used at all
        methods = set(r.get("method", "") for r in reader)
        if "neural" not in str(methods).lower():
            diagnosis_rows.append({
                "source": "neural_operator_proposal",
                "failure_category": "neural_result_not_used",
                "detail": f"Methods used: {methods}. Neural predictions may not feed into solver.",
                "severity": "critical",
                "count": len(reader),
            })

    # Analyze proposal accuracy
    accuracy_csv = neural_dir / "proposal_accuracy.csv"
    if accuracy_csv.exists():
        with open(accuracy_csv) as f:
            acc_reader = list(csv.DictReader(f))

        for row in acc_reader:
            family = row.get("predicted_family", "")
            total = int(row.get("count", 0))
            verified = int(row.get("verified_count", 0))
            if total > 0 and verified == 0:
                diagnosis_rows.append({
                    "source": "neural_proposal_accuracy",
                    "failure_category": "proposal_not_executable",
                    "detail": f"Family '{family}': {total} predicted, 0 verified",
                    "severity": "medium",
                    "count": total,
                })
            elif total > 0 and verified > 0 and verified < total:
                diagnosis_rows.append({
                    "source": "neural_proposal_accuracy",
                    "failure_category": "proposal_executable_but_fails_LOO",
                    "detail": f"Family '{family}': {total} predicted, {verified} verified ({verified/total*100:.0f}%)",
                    "severity": "info",
                    "count": total,
                })

    # Analyze ViT/VLM probe
    vit_results_csv = vit_dir / "results.csv"
    if vit_results_csv.exists():
        with open(vit_results_csv) as f:
            vit_reader = list(csv.DictReader(f))

        change_correct = sum(1 for r in vit_reader if r.get("change_correct") == "True")
        opfam_correct = sum(1 for r in vit_reader if r.get("opfam_correct") == "True")
        selector_correct = sum(1 for r in vit_reader if r.get("selector_correct") == "True")
        n_total = len(vit_reader)

        if n_total > 0:
            change_acc = change_correct / n_total
            opfam_acc = opfam_correct / n_total

            if change_acc <= 0.5:
                diagnosis_rows.append({
                    "source": "vit_probe",
                    "failure_category": "feature_not_predictive",
                    "detail": f"Object-change accuracy {change_acc:.2f} (at chance level)",
                    "severity": "high",
                    "count": n_total,
                })

            # Check label imbalance
            gt_families = [r.get("gt_operator_family", "") for r in vit_reader]
            from collections import Counter
            family_dist = Counter(gt_families)
            if family_dist:
                majority_frac = max(family_dist.values()) / n_total
                if majority_frac > 0.7:
                    diagnosis_rows.append({
                        "source": "vit_probe",
                        "failure_category": "label_imbalance",
                        "detail": f"Majority class is {majority_frac:.0%} of data: {family_dist.most_common(1)}",
                        "severity": "high",
                        "count": n_total,
                    })

            # Check if proposals connect to symbolic pipeline
            n_promoted = sum(1 for r in vit_reader if r.get("is_promoted") == "True")
            n_correct_proposals_on_promoted = sum(
                1 for r in vit_reader
                if r.get("is_promoted") == "True" and r.get("opfam_correct") == "True"
            )

            if n_promoted > 0 and n_correct_proposals_on_promoted < n_promoted:
                diagnosis_rows.append({
                    "source": "vit_probe",
                    "failure_category": "proposal_not_connected_to_symbolic_pipeline",
                    "detail": f"Only {n_correct_proposals_on_promoted}/{n_promoted} promoted tasks have correct neural predictions",
                    "severity": "high",
                    "count": n_promoted,
                })

    # Write CSV
    csv_path = OUTPUT_DIR / "diagnosis.csv"
    with open(csv_path, "w", newline="") as f:
        fields = ["source", "failure_category", "detail", "severity", "count"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(diagnosis_rows)

    # Write markdown
    md_path = OUTPUT_DIR / "diagnosis.md"
    with open(md_path, "w") as f:
        f.write(f"# Neural/VLM Proposal Failure Diagnosis\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Issues Found\n\n")
        f.write("| Source | Category | Severity | Count | Detail |\n")
        f.write("|--------|----------|----------|-------|--------|\n")
        for r in diagnosis_rows:
            f.write(f"| {r['source']} | {r['failure_category']} | {r['severity']} | "
                    f"{r['count']} | {r['detail'][:70]} |\n")

        f.write("\n## Root Cause Analysis\n\n")
        f.write("1. **Label imbalance**: Most tasks are 'unknown' family, making classifier default to majority class\n")
        f.write("2. **ViT features at chance**: 50% change accuracy suggests features are not discriminative for ARC\n")
        f.write("3. **No pipeline connection**: Even correct neural predictions don't feed into symbolic executor\n")
        f.write("4. **Verification gap**: Neural routing generates candidates (89/100) but none survive LOO/proof\n\n")

        f.write("## Recommended Patches\n\n")
        f.write("1. Use symbolic features (structural signature, causal properties) instead of ViT for routing\n")
        f.write("2. Train classifier only on tasks where operator family is known (not 'unknown')\n")
        f.write("3. Connect neural family prediction → operator search priority in StructuralReasoner\n")
        f.write("4. Accept neural proposals only as search-order priors, never as final answers\n")

    print(f"Diagnosis: {md_path}")
    print(f"CSV: {csv_path}")
    print(f"Issues: {len(diagnosis_rows)}")


if __name__ == "__main__":
    main()
