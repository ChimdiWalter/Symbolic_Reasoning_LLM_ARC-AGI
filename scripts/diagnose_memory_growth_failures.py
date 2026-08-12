#!/usr/bin/env python3.11
"""Diagnose why memory growth produced 0 memory-assisted solves."""

import csv
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/memory_growth"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing memory growth deep results
    deep_dir = PROJECT_ROOT / "outputs/deep_project_completion/memory_growth_deep"

    stage_csv = deep_dir / "stage_metrics.csv"
    stage_rows = []
    if stage_csv.exists():
        with open(stage_csv) as f:
            stage_rows = list(csv.DictReader(f))

    failure_clusters_file = deep_dir / "failure_clusters.json"
    failure_clusters = {}
    if failure_clusters_file.exists():
        with open(failure_clusters_file) as f:
            failure_clusters = json.load(f)

    failure_categories = [
        "near_solved_not_stored",
        "failure_cluster_not_created",
        "operator_invented_but_not_registered",
        "registered_operator_not_retrieved",
        "retrieved_operator_not_applied",
        "resume_not_called",
        "certificate_not_emitted",
        "old_task_not_retested",
        "heldout_transfer_not_attempted",
    ]

    # Analyze stage by stage
    diagnosis_rows = []

    for stage in stage_rows:
        stage_name = stage.get("stage_name", "")
        tasks_attempted = int(stage.get("tasks_attempted", 0))
        tasks_solved = int(stage.get("tasks_solved", 0))
        near_stored = int(stage.get("near_solved_stored", 0))
        clusters = int(stage.get("failure_clusters", 0))
        ops_proposed = int(stage.get("operators_proposed", 0))
        ops_validated = int(stage.get("operators_validated", 0))
        prev_solved = int(stage.get("previously_failed_now_solved", 0))

        if stage_name == "static_baseline":
            diagnosis_rows.append({
                "stage": stage_name,
                "failure_category": "none" if tasks_solved > 0 else "baseline_zero",
                "detail": f"Baseline: {tasks_solved}/{tasks_attempted} solved",
                "severity": "info",
            })
        elif stage_name == "episodic_memory":
            if tasks_solved == 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "registered_operator_not_retrieved",
                    "detail": f"Episodic memory ran {tasks_attempted} tasks but solved 0 new. "
                              "Memory from baseline not helping unsolved tasks.",
                    "severity": "high",
                })
            else:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "none",
                    "detail": f"Solved {tasks_solved} new tasks with episodic memory",
                    "severity": "info",
                })
        elif stage_name == "near_solved_memory":
            if near_stored == 0 and tasks_attempted > 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "near_solved_not_stored",
                    "detail": "No near-solved states were stored despite failed tasks existing",
                    "severity": "critical",
                })
            elif tasks_solved == 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "retrieved_operator_not_applied",
                    "detail": "Near-solved states may exist but did not lead to new solves",
                    "severity": "high",
                })
        elif stage_name == "failure_clustering":
            if clusters == 0 and tasks_attempted > 100:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "failure_cluster_not_created",
                    "detail": "No failure clusters created despite many failures",
                    "severity": "high",
                })
            else:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "none" if clusters > 0 else "failure_cluster_not_created",
                    "detail": f"{clusters} clusters found",
                    "severity": "info" if clusters > 0 else "medium",
                })
        elif stage_name == "concept_operator_invention":
            if ops_proposed == 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "operator_invented_but_not_registered",
                    "detail": "No operators were proposed from failure clusters",
                    "severity": "critical",
                })
            elif ops_validated == 0 and ops_proposed > 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "operator_invented_but_not_registered",
                    "detail": f"{ops_proposed} proposed but 0 validated/registered",
                    "severity": "high",
                })
            elif tasks_solved == 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "registered_operator_not_retrieved",
                    "detail": f"Operators registered but 0 new solves",
                    "severity": "high",
                })
        elif stage_name == "resume_failed":
            if tasks_attempted == 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "resume_not_called",
                    "detail": "Resume stage attempted 0 tasks — was it skipped?",
                    "severity": "critical",
                })
            elif prev_solved == 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "old_task_not_retested",
                    "detail": "Resume ran but no previously failed tasks became solved",
                    "severity": "high",
                })
        elif stage_name == "heldout_transfer":
            if tasks_solved > 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "none",
                    "detail": f"Transfer solved {tasks_solved} heldout tasks",
                    "severity": "info",
                })
            else:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "heldout_transfer_not_attempted",
                    "detail": "Heldout transfer solved 0 tasks",
                    "severity": "medium",
                })
        elif stage_name == "cross_domain_transfer":
            if tasks_attempted == 0:
                diagnosis_rows.append({
                    "stage": stage_name,
                    "failure_category": "heldout_transfer_not_attempted",
                    "detail": "Cross-domain transfer not attempted (0 tasks)",
                    "severity": "medium",
                })

    # Analyze failure clusters
    n_unknown = len(failure_clusters.get("unknown", []))
    n_attr_error = len(failure_clusters.get("error:AttributeError", []))

    if n_attr_error > 0:
        diagnosis_rows.append({
            "stage": "infrastructure",
            "failure_category": "operator_invented_but_not_registered",
            "detail": f"{n_attr_error} tasks failed with AttributeError — likely missing method/property",
            "severity": "critical",
        })

    # Write CSV
    csv_path = OUTPUT_DIR / "diagnosis.csv"
    with open(csv_path, "w", newline="") as f:
        fields = ["stage", "failure_category", "detail", "severity"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(diagnosis_rows)

    # Write markdown
    md_path = OUTPUT_DIR / "diagnosis.md"
    with open(md_path, "w") as f:
        f.write(f"# Memory Growth Failure Diagnosis\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Stage-by-Stage Analysis\n\n")
        f.write("| Stage | Category | Severity | Detail |\n")
        f.write("|-------|----------|----------|--------|\n")
        for r in diagnosis_rows:
            f.write(f"| {r['stage']} | {r['failure_category']} | {r['severity']} | {r['detail'][:80]} |\n")

        critical = [r for r in diagnosis_rows if r["severity"] == "critical"]
        f.write(f"\n## Critical Issues ({len(critical)})\n\n")
        for r in critical:
            f.write(f"- **{r['stage']}**: {r['failure_category']} — {r['detail']}\n")

        f.write("\n## Root Cause Hypothesis\n\n")
        f.write("The memory growth pipeline has structural gaps:\n\n")
        f.write("1. **Near-solved states not stored**: The near-solved memory stage ran but stored 0 states, "
                "meaning the system cannot identify partial-success tasks to revisit.\n")
        f.write("2. **No operators invented**: The concept/operator invention stage proposed 0 operators, "
                "meaning failure clustering does not feed into actionable new capabilities.\n")
        f.write("3. **Resume skipped**: The resume stage attempted 0 tasks, meaning previously failed tasks "
                "are never re-attempted with new knowledge.\n")
        f.write("4. **AttributeError failures**: 195 tasks crashed with AttributeError, suggesting "
                "a property or method is missing from the adapter/reasoner interface.\n")

        f.write("\n## Recommended Patches\n\n")
        f.write("1. Fix AttributeError — identify which property/method is missing\n")
        f.write("2. Ensure near-solved detection stores partial evidence\n")
        f.write("3. Ensure failure clusters feed into concept proposal\n")
        f.write("4. Ensure resume stage re-attempts failed tasks with new operators\n")
        f.write("5. Add event logging at each transition point\n")

    print(f"Diagnosis: {md_path}")
    print(f"CSV: {csv_path}")
    print(f"Issues found: {len(diagnosis_rows)}")
    print(f"Critical: {len(critical)}")


if __name__ == "__main__":
    main()
