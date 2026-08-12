#!/usr/bin/env python3.11
"""Build final claim audit for mechanism repair pass."""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass"

def read_summary(subdir, filename="microcycle_summary.md"):
    path = OUTPUT_DIR / subdir / filename
    if path.exists():
        return path.read_text()
    return ""

def count_solved(subdir, filename="microcycle_results.csv"):
    path = OUTPUT_DIR / subdir / filename
    if not path.exists():
        return 0, 0
    with open(path) as f:
        rows = list(csv.DictReader(f))
    solved = sum(1 for r in rows if r.get("solved") == "True" or r.get("solved") == True)
    return solved, len(rows)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    mechanisms = {
        "adapter_genesis": {
            "label": "AdapterGenesis Synthesis",
            "before": "0 tasks solved by synthesized adapters",
            "results_csv": "microcycle_results.csv",
            "summary_md": "microcycle_summary.md",
            "ablation_csv": "ablation_results.csv",
        },
        "memory_growth": {
            "label": "Memory-Assisted Cumulative Reasoning",
            "before": "0 memory-assisted solves",
            "results_csv": "microcycle_results.csv",
            "summary_md": "microcycle_summary.md",
        },
        "neural_vlm": {
            "label": "Neural/VLM Proposal Routing",
            "before": "0 verified promotions from neural proposals",
            "results_csv": "proposal_accuracy.csv",
            "summary_md": "microcycle_summary.md",
        },
        "cross_domain_transfer": {
            "label": "Cross-Domain Operator Transfer",
            "before": "2/20 transfers, 1 family only",
            "results_csv": "transfer_matrix.csv",
            "summary_md": "aligned_microcycle_summary.md",
        },
    }

    claim_rows = []

    for mech_key, mech_info in mechanisms.items():
        mech_dir = OUTPUT_DIR / mech_key

        # Read results
        solved, total = 0, 0
        results_path = mech_dir / mech_info["results_csv"]
        if results_path.exists():
            with open(results_path) as f:
                rows = list(csv.DictReader(f))
                total = len(rows)

                if mech_key == "adapter_genesis":
                    synth_rows = [r for r in rows if r.get("adapter_type") == "synthesized"]
                    solved = sum(1 for r in synth_rows if r.get("solved") == "True")
                elif mech_key == "memory_growth":
                    promoted = [r for r in rows if r.get("stage") == "3_primed" and r.get("solved") == "True"]
                    cold_failed = [r for r in rows if r.get("stage") == "1_cold" and r.get("solved") != "True"]
                    cold_task_names = set(r.get("task", "") for r in cold_failed)
                    solved = sum(1 for r in promoted if r.get("task", "") in cold_task_names)
                elif mech_key == "neural_vlm":
                    solved = sum(1 for r in rows if r.get("neural_helped") == "True" and r.get("loo_passed") == "True")
                elif mech_key == "cross_domain_transfer":
                    solved = sum(1 for r in rows if r.get("strategy_match") == "True" and r.get("loo_passed") == "True")

        # Count certificates
        cert_dir = mech_dir / "certificates"
        n_certs = len(list(cert_dir.glob("*.json"))) if cert_dir.exists() else 0

        # Count false positives
        fp = 0
        if results_path.exists():
            with open(results_path) as f:
                for r in csv.DictReader(f):
                    if r.get("fp") == "True":
                        fp += 1

        # Determine status
        if solved > 0 and fp == 0:
            status = "supported"
        elif solved > 0 and fp > 0:
            status = "partially_supported"
        else:
            status = "not_supported"

        # Read summary for detail
        summary = read_summary(mech_key, mech_info["summary_md"])

        after_result = f"{solved} verified solves/transfers, {n_certs} certificates, {fp} FP"

        claim_rows.append({
            "mechanism": mech_info["label"],
            "before": mech_info["before"],
            "after": after_result,
            "status": status,
            "evidence": str(results_path.relative_to(PROJECT_ROOT)),
            "certificates": n_certs,
            "false_positives": fp,
            "allowed_wording": "",
            "forbidden_wording": "",
        })

        # Set allowed/forbidden wording based on results
        if mech_key == "adapter_genesis":
            if solved > 0:
                claim_rows[-1]["allowed_wording"] = f"AdapterGenesis synthesized adapters that solved {solved} controlled task(s)"
            else:
                claim_rows[-1]["allowed_wording"] = "AdapterGenesis provides a domain-interface scaffold"
            claim_rows[-1]["forbidden_wording"] = "AdapterGenesis automatically adapts to arbitrary domains"

        elif mech_key == "memory_growth":
            if solved > 0:
                claim_rows[-1]["allowed_wording"] = f"Memory-assisted reasoning produced {solved} promotion(s) in controlled chains"
            else:
                claim_rows[-1]["allowed_wording"] = "Memory infrastructure exists but has not produced verified cumulative learning"
            claim_rows[-1]["forbidden_wording"] = "Memory growth improves broad ARC performance"

        elif mech_key == "neural_vlm":
            if solved > 0:
                claim_rows[-1]["allowed_wording"] = f"Neural routing produced {solved} verified solve(s) under symbolic verification"
            else:
                claim_rows[-1]["allowed_wording"] = "Neural modules are advisory and do not produce verified solves"
            claim_rows[-1]["forbidden_wording"] = "Neural modules solve reasoning tasks"

        elif mech_key == "cross_domain_transfer":
            if solved > 0:
                claim_rows[-1]["allowed_wording"] = f"Cross-domain transfer demonstrated {solved} certified strategy transfer(s)"
            else:
                claim_rows[-1]["allowed_wording"] = "Cross-domain transfer scaffolding tested but broad transfer unsupported"
            claim_rows[-1]["forbidden_wording"] = "Broad cross-domain reasoning is solved"

    # Write final CSV
    csv_path = OUTPUT_DIR / "final_claim_table.csv"
    fields = ["mechanism", "before", "after", "status", "evidence", "certificates",
              "false_positives", "allowed_wording", "forbidden_wording"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(claim_rows)

    # Write allowed claims
    with open(OUTPUT_DIR / "allowed_claims.md", "w") as f:
        f.write(f"# Allowed Claims After Mechanism Repair Pass\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        for row in claim_rows:
            if row["status"] in ("supported", "partially_supported"):
                f.write(f"- **{row['mechanism']}**: {row['allowed_wording']}\n")
        f.write("\n## Evidence\n\n")
        for row in claim_rows:
            if row["status"] in ("supported", "partially_supported"):
                f.write(f"- {row['mechanism']}: {row['evidence']} ({row['certificates']} certs, {row['false_positives']} FP)\n")

    # Write forbidden claims
    with open(OUTPUT_DIR / "forbidden_claims.md", "w") as f:
        f.write(f"# Forbidden Claims\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        for row in claim_rows:
            f.write(f"- **{row['mechanism']}**: Do NOT write: \"{row['forbidden_wording']}\"\n")

    # Write final summary
    with open(OUTPUT_DIR / "final_summary.md", "w") as f:
        f.write(f"# Mechanism Repair Pass — Final Summary\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Overview\n\n")
        f.write("| Mechanism | Before | After | Status | Certs | FP |\n")
        f.write("|-----------|--------|-------|--------|-------|----|\n")
        for row in claim_rows:
            f.write(f"| {row['mechanism']} | {row['before']} | {row['after']} | "
                    f"{row['status']} | {row['certificates']} | {row['false_positives']} |\n")

        n_supported = sum(1 for r in claim_rows if r["status"] == "supported")
        n_partial = sum(1 for r in claim_rows if r["status"] == "partially_supported")
        n_unsupported = sum(1 for r in claim_rows if r["status"] == "not_supported")

        f.write(f"\n## Summary: {n_supported} supported, {n_partial} partial, {n_unsupported} not supported\n\n")

        f.write("## What Changed\n\n")
        for row in claim_rows:
            f.write(f"### {row['mechanism']}\n")
            f.write(f"- **Before**: {row['before']}\n")
            f.write(f"- **After**: {row['after']}\n")
            f.write(f"- **Status**: {row['status']}\n")
            f.write(f"- **Allowed**: {row['allowed_wording']}\n")
            f.write(f"- **Forbidden**: {row['forbidden_wording']}\n\n")

        f.write("## Rule\n\n")
        f.write("This pass is about making weak mechanisms earn their claims. "
                "If they still fail, that is documented honestly. "
                "No overclaiming. No hiding negative results.\n")

    print(f"Final summary: {OUTPUT_DIR / 'final_summary.md'}")
    print(f"Claim table: {csv_path}")
    print(f"Supported: {n_supported}, Partial: {n_partial}, Unsupported: {n_unsupported}")


if __name__ == "__main__":
    main()
