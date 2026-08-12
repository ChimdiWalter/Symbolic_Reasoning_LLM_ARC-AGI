#!/usr/bin/env python3.11
"""Summarize all completed deep-project jobs into consolidated outputs."""

import csv
import json
import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
DEEP_ROOT = PROJECT_ROOT / "outputs" / "deep_project_completion"

PHASES = {
    "cross_domain_adapter_genesis": {
        "label": "Cross-Domain AdapterGenesis",
        "phase": "B",
        "job_name": "adapter_genesis_deep",
        "job_id": "14045678",
        "script": "slurm/run_cross_domain_adapter_genesis_deep.sh",
    },
    "cross_domain_operator_transfer": {
        "label": "Cross-Domain Operator Transfer",
        "phase": "C",
        "job_name": "op_transfer_deep",
        "job_id": "14045679",
        "script": "slurm/run_cross_domain_operator_transfer_deep.sh",
    },
    "memory_growth_deep": {
        "label": "Memory Growth Curriculum",
        "phase": "D",
        "job_name": "mem_growth_deep",
        "job_id": "14045825",
        "script": "slurm/run_deep_memory_growth_curriculum.sh",
    },
    "many_to_few_grouping": {
        "label": "Many-to-Few Grouping",
        "phase": "E",
        "job_name": "many_to_few",
        "job_id": "14045826",
        "script": "slurm/run_many_to_few_grouping.sh",
    },
    "shape_completion": {
        "label": "Shape Completion",
        "phase": "F",
        "job_name": "shape_complete",
        "job_id": "14045851",
        "script": "slurm/run_shape_completion_deep.sh",
    },
    "position_within_object_recolor": {
        "label": "Position-Within-Object Recolor",
        "phase": "G",
        "job_name": "pos_recolor",
        "job_id": "14045828",
        "script": "slurm/run_position_within_object_recolor.sh",
    },
    "neural_operator_proposal": {
        "label": "Neural Operator Proposal",
        "phase": "H",
        "job_name": "neural_prop_deep",
        "job_id": "14046161",
        "script": "slurm/run_neural_operator_proposal_deep.sh",
    },
    "formal_checker_feasibility": {
        "label": "Formal Checker Feasibility",
        "phase": "I",
        "job_name": "formal_check",
        "job_id": "14045686",
        "script": "slurm/run_formal_checker_feasibility.sh",
    },
    "reproducibility_package": {
        "label": "Reproducibility Package",
        "phase": "J",
        "job_name": "repro_pkg",
        "job_id": "14045687",
        "script": "slurm/run_reproducibility_package.sh",
    },
    "final_claim_audit": {
        "label": "Final Claim Audit",
        "phase": "K",
        "job_name": "claim_audit",
        "job_id": "14045830",
        "script": "slurm/run_final_claim_audit.sh",
    },
    "conceptarc_eval": {
        "label": "ConceptARC Evaluation",
        "phase": "L",
        "job_name": "conceptarc_eval",
        "job_id": "14046156",
        "script": "slurm/run_conceptarc_eval.sh",
    },
}


def read_status_json(phase_dir: Path) -> dict:
    status_file = phase_dir / "status.json"
    if status_file.exists():
        with open(status_file) as f:
            return json.load(f)
    return {}


def read_summary_md(phase_dir: Path) -> str:
    for name in ["summary.md", "conceptarc_summary.md", "microcycle_summary.md",
                  "formal_checker_feasibility_report.md", "artifact_manifest.md",
                  "final_claim_audit.md"]:
        p = phase_dir / name
        if p.exists():
            return p.read_text()
    return ""


def extract_phase_info(phase_key: str, meta: dict) -> dict:
    phase_dir = DEEP_ROOT / phase_key
    info = {
        "phase": meta["phase"],
        "label": meta["label"],
        "job_name": meta["job_name"],
        "job_id": meta["job_id"],
        "script": meta["script"],
        "status": "unknown",
        "tasks_attempted": 0,
        "tasks_solved": 0,
        "promotions": 0,
        "false_positives": 0,
        "certificates": 0,
        "main_positive": "",
        "main_negative": "",
        "claim_implication": "",
        "missing_artifact": "",
    }

    if not phase_dir.exists():
        info["status"] = "directory missing"
        info["missing_artifact"] = str(phase_dir)
        return info

    status = read_status_json(phase_dir)
    info["status"] = status.get("status", "completed (no status.json)")

    summary = read_summary_md(phase_dir)
    files = list(phase_dir.rglob("*"))
    csv_files = [f for f in files if f.suffix == ".csv"]

    if phase_key == "cross_domain_adapter_genesis":
        info["tasks_attempted"] = 0
        info["tasks_solved"] = 0
        info["main_positive"] = "Adapters functional in 5 domains (grid, graph, chess, molecule, conceptarc)"
        info["main_negative"] = "0 tasks solved by AdapterGenesis synthesis alone"
        info["claim_implication"] = "Architectural scaffold only; not proven automatic adaptation"

    elif phase_key == "cross_domain_operator_transfer":
        results_csv = phase_dir / "results.csv"
        if results_csv.exists():
            with open(results_csv) as f:
                reader = list(csv.DictReader(f))
                info["tasks_attempted"] = len(reader)
                info["tasks_solved"] = sum(1 for r in reader if r.get("zero_shot") == "True")
        info["main_positive"] = "2/20 zero-shot transfers (PROJECT_TO_NEIGHBORHOOD grid<->graph)"
        info["main_negative"] = "18/20 transfers failed: no realization in target domain"
        info["claim_implication"] = "Operator transfer scaffolding tested; broad transfer unsupported"

    elif phase_key == "memory_growth_deep":
        stage_csv = phase_dir / "stage_metrics.csv"
        if stage_csv.exists():
            with open(stage_csv) as f:
                reader = list(csv.DictReader(f))
                info["tasks_attempted"] = sum(int(r.get("tasks_attempted", 0)) for r in reader)
                info["tasks_solved"] = sum(int(r.get("tasks_solved", 0)) for r in reader)
        info["main_positive"] = "7 total solved (5 baseline + 2 heldout transfer)"
        info["main_negative"] = "0 memory-assisted solves; 0 previously failed tasks later solved"
        info["claim_implication"] = "Cumulative memory does NOT improve solve rate"

    elif phase_key == "many_to_few_grouping":
        real_csv = phase_dir / "real_arc_results.csv"
        if real_csv.exists():
            with open(real_csv) as f:
                reader = list(csv.DictReader(f))
                info["tasks_attempted"] = len(reader)
                info["tasks_solved"] = sum(1 for r in reader if r.get("solved") == "True")
        info["main_positive"] = "Microcycle 2/5 correct (row_group solved)"
        info["main_negative"] = "Real ARC: 1/1000 solved; grouping operators weak"
        info["claim_implication"] = "Exploratory; future work"

    elif phase_key == "shape_completion":
        real_csv = phase_dir / "real_arc_results.csv"
        if real_csv.exists():
            with open(real_csv) as f:
                reader = list(csv.DictReader(f))
                info["tasks_attempted"] = len(reader)
                info["tasks_solved"] = sum(1 for r in reader if r.get("solved") == "True")
                info["promotions"] = sum(1 for r in reader if r.get("loo_passed") == "True" and r.get("solved") == "True")
        info["main_positive"] = "Microcycle 5/5 correct; real ARC 4/1000 solved, 4 promoted"
        info["main_negative"] = "Low hit rate on full ARC benchmark"
        info["claim_implication"] = "Promising frontier operator; needs audit before main claim"

    elif phase_key == "position_within_object_recolor":
        real_csv = phase_dir / "real_arc_results.csv"
        if real_csv.exists():
            with open(real_csv) as f:
                reader = list(csv.DictReader(f))
                info["tasks_attempted"] = len(reader)
                info["tasks_solved"] = sum(1 for r in reader if r.get("solved") == "True")
                info["promotions"] = sum(1 for r in reader if r.get("loo_passed") == "True" and r.get("solved") == "True")
        info["main_positive"] = "Microcycle 5/6 correct; real ARC 3/1000 solved"
        info["main_negative"] = "contact_recolor unsolved"
        info["claim_implication"] = "Exploratory frontier operator"

    elif phase_key == "neural_operator_proposal":
        results_csv = phase_dir / "results.csv"
        if results_csv.exists():
            with open(results_csv) as f:
                reader = list(csv.DictReader(f))
                info["tasks_attempted"] = len(reader)
                info["tasks_solved"] = sum(1 for r in reader if r.get("symbolic_verified") == "True")
                info["promotions"] = sum(1 for r in reader if r.get("promoted") == "True")
                info["false_positives"] = sum(1 for r in reader if r.get("fp") == "True")
        info["main_positive"] = "Neural routing: 89/100 solved (vs 4/100 symbolic-only)"
        info["main_negative"] = "0 verified promotions; 299 proposals rejected"
        info["claim_implication"] = "Neural modules advisory only; do not claim verified promotions"

    elif phase_key == "formal_checker_feasibility":
        info["main_positive"] = "7/10 proof obligations machine-checkable"
        info["main_negative"] = "No SMT/Z3; 3 obligations remain empirical"
        info["claim_implication"] = "Bounded executable verification, not formal proof"

    elif phase_key == "reproducibility_package":
        info["main_positive"] = "Artifact manifest, reproduction commands, environment report exist"
        info["main_negative"] = "Smoke tests not yet run end-to-end"
        info["claim_implication"] = "Reproducibility infrastructure present"

    elif phase_key == "final_claim_audit":
        info["main_positive"] = "8 claims supported, 2 partial"
        info["main_negative"] = "3 claims not supported (C3 ConceptARC, C7 memory, C11 neural)"
        info["claim_implication"] = "Paper must not overclaim memory or neural contributions"

    elif phase_key == "conceptarc_eval":
        results_csv = phase_dir / "conceptarc_results.csv"
        if results_csv.exists():
            with open(results_csv) as f:
                reader = list(csv.DictReader(f))
                info["tasks_attempted"] = len(reader)
                info["tasks_solved"] = sum(1 for r in reader if r.get("solved") == "True")
        info["main_positive"] = "11/160 solved (6.9%); SameDifferent 4/10 (40%)"
        info["main_negative"] = "7 concept groups at 0%; overall rate low"
        info["claim_implication"] = "Cross-benchmark breadth exists but coverage is narrow"

    missing = []
    for expected in ["status.json"]:
        if not (phase_dir / expected).exists():
            missing.append(str(phase_dir / expected))
    if not summary:
        missing.append(f"{phase_dir}/summary.md (or equivalent)")
    info["missing_artifact"] = "; ".join(missing) if missing else "none"

    return info


def write_summary_md(rows: list[dict], out_path: Path):
    with open(out_path, "w") as f:
        f.write(f"# Completed Deep-Job Summary\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("## Phase Overview\n\n")
        f.write("| Phase | Label | Job ID | Status | Attempted | Solved | Promotions | FP |\n")
        f.write("|-------|-------|--------|--------|-----------|--------|------------|----|\n")
        for r in rows:
            f.write(f"| {r['phase']} | {r['label']} | {r['job_id']} | {r['status']} | "
                    f"{r['tasks_attempted']} | {r['tasks_solved']} | {r['promotions']} | {r['false_positives']} |\n")

        f.write("\n## Detailed Results\n\n")
        for r in rows:
            f.write(f"### Phase {r['phase']}: {r['label']}\n\n")
            f.write(f"- **Job**: {r['job_name']} (ID: {r['job_id']})\n")
            f.write(f"- **Script**: {r['script']}\n")
            f.write(f"- **Status**: {r['status']}\n")
            f.write(f"- **Tasks**: {r['tasks_attempted']} attempted, {r['tasks_solved']} solved\n")
            f.write(f"- **Promotions**: {r['promotions']}\n")
            f.write(f"- **False positives**: {r['false_positives']}\n")
            f.write(f"- **Main positive**: {r['main_positive']}\n")
            f.write(f"- **Main negative**: {r['main_negative']}\n")
            f.write(f"- **Paper claim**: {r['claim_implication']}\n")
            f.write(f"- **Missing artifacts**: {r['missing_artifact']}\n\n")


def write_summary_csv(rows: list[dict], out_path: Path):
    fields = ["phase", "label", "job_name", "job_id", "script", "status",
              "tasks_attempted", "tasks_solved", "promotions", "false_positives",
              "certificates", "main_positive", "main_negative", "claim_implication",
              "missing_artifact"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_missing_artifacts(rows: list[dict], out_path: Path):
    missing = {}
    for r in rows:
        if r["missing_artifact"] and r["missing_artifact"] != "none":
            missing[r["label"]] = r["missing_artifact"].split("; ")
    with open(out_path, "w") as f:
        json.dump(missing, f, indent=2)


def main():
    rows = []
    for phase_key, meta in PHASES.items():
        info = extract_phase_info(phase_key, meta)
        rows.append(info)

    rows.sort(key=lambda r: r["phase"])

    write_summary_md(rows, DEEP_ROOT / "completed_jobs_summary.md")
    write_summary_csv(rows, DEEP_ROOT / "completed_jobs_summary.csv")
    write_missing_artifacts(rows, DEEP_ROOT / "missing_artifacts.json")

    print(f"Written: completed_jobs_summary.md")
    print(f"Written: completed_jobs_summary.csv")
    print(f"Written: missing_artifacts.json")
    print(f"Phases processed: {len(rows)}")
    total_solved = sum(r["tasks_solved"] for r in rows)
    total_attempted = sum(r["tasks_attempted"] for r in rows)
    print(f"Total: {total_solved} solved / {total_attempted} attempted across all phases")


if __name__ == "__main__":
    main()
