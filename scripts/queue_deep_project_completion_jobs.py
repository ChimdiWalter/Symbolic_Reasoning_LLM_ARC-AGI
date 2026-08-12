#!/usr/bin/env python3
"""Phase L: Queue orchestration — submit all deep project completion SLURM jobs.

Rules:
- Do NOT touch active ARC-1000 job 14020393
- Use separate output directories
- No shared progress files
- Priority order: B, C, D, E, F, G, H, I, J, K
"""
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SLURM_DIR = PROJECT_ROOT / "slurm"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "deep_project_completion"


JOBS = [
    {
        "name": "cross_domain_adapter_genesis_deep",
        "script": "slurm/run_cross_domain_adapter_genesis_deep.sh",
        "output_dir": "outputs/deep_project_completion/cross_domain_adapter_genesis",
        "dependency": None,
        "expected_runtime": "12h",
        "phase": "B",
        "priority": 1,
    },
    {
        "name": "cross_domain_operator_transfer_deep",
        "script": "slurm/run_cross_domain_operator_transfer_deep.sh",
        "output_dir": "outputs/deep_project_completion/cross_domain_operator_transfer",
        "dependency": None,
        "expected_runtime": "8h",
        "phase": "C",
        "priority": 2,
    },
    {
        "name": "memory_growth_deep",
        "script": "slurm/run_deep_memory_growth_curriculum.sh",
        "output_dir": "outputs/deep_project_completion/memory_growth_deep",
        "dependency": None,
        "expected_runtime": "24h",
        "phase": "D",
        "priority": 3,
    },
    {
        "name": "many_to_few_grouping",
        "script": "slurm/run_many_to_few_grouping.sh",
        "output_dir": "outputs/deep_project_completion/many_to_few_grouping",
        "dependency": None,
        "expected_runtime": "6h",
        "phase": "E",
        "priority": 4,
    },
    {
        "name": "shape_completion",
        "script": "slurm/run_shape_completion_deep.sh",
        "output_dir": "outputs/deep_project_completion/shape_completion",
        "dependency": None,
        "expected_runtime": "6h",
        "phase": "F",
        "priority": 5,
    },
    {
        "name": "position_within_object_recolor",
        "script": "slurm/run_position_within_object_recolor.sh",
        "output_dir": "outputs/deep_project_completion/position_within_object_recolor",
        "dependency": None,
        "expected_runtime": "6h",
        "phase": "G",
        "priority": 6,
    },
    {
        "name": "neural_operator_proposal_deep",
        "script": "slurm/run_neural_operator_proposal_deep.sh",
        "output_dir": "outputs/deep_project_completion/neural_operator_proposal",
        "dependency": None,
        "expected_runtime": "8h",
        "phase": "H",
        "priority": 7,
    },
    {
        "name": "formal_checker_feasibility",
        "script": "slurm/run_formal_checker_feasibility.sh",
        "output_dir": "outputs/deep_project_completion/formal_checker_feasibility",
        "dependency": None,
        "expected_runtime": "2h",
        "phase": "I",
        "priority": 8,
    },
    {
        "name": "reproducibility_package",
        "script": "slurm/run_reproducibility_package.sh",
        "output_dir": "outputs/deep_project_completion/reproducibility_package",
        "dependency": None,
        "expected_runtime": "1h",
        "phase": "J",
        "priority": 9,
    },
    {
        "name": "final_claim_audit",
        "script": "slurm/run_final_claim_audit.sh",
        "output_dir": "outputs/deep_project_completion/final_claim_audit",
        "dependency": "afterok_all_above",
        "expected_runtime": "1h",
        "phase": "K",
        "priority": 10,
    },
]


def submit_job(job, dep_job_ids=None):
    script_path = PROJECT_ROOT / job["script"]
    if not script_path.exists():
        return None, f"script not found: {script_path}"

    cmd = ["sbatch"]
    if dep_job_ids and job["dependency"] == "afterok_all_above":
        dep_str = ":".join(str(jid) for jid in dep_job_ids if jid)
        if dep_str:
            cmd.extend(["--dependency", f"afterok:{dep_str}"])
    cmd.append(str(script_path))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT))
        if result.returncode == 0:
            for word in result.stdout.strip().split():
                if word.isdigit():
                    return int(word), None
            return None, f"could not parse job id from: {result.stdout}"
        return None, f"sbatch error: {result.stderr}"
    except Exception as e:
        return None, str(e)


def main():
    print("=== Phase L: Queue Deep Project Completion Jobs ===")
    print(f"Active ARC-1000 job: 14020393 (DO NOT TOUCH)")
    print()

    # Check current queue
    try:
        result = subprocess.run(["squeue", "--me", "-o", "%.10i %.30j %.8T"], capture_output=True, text=True, timeout=10)
        print("Current queue:")
        print(result.stdout)
    except Exception:
        print("Could not check queue")

    submitted = []
    dep_job_ids = []

    # Submit in priority order, limit concurrent jobs
    max_concurrent = 4
    for job in sorted(JOBS, key=lambda j: j["priority"]):
        active_count = len([s for s in submitted if s["status"] == "SUBMITTED"])
        if active_count >= max_concurrent and job["dependency"] is None:
            print(f"  {job['name']}: DEFERRED (max concurrent reached)")
            submitted.append({**job, "job_id": None, "status": "DEFERRED", "notes": "max concurrent"})
            continue

        print(f"Submitting {job['name']} (Phase {job['phase']})...")
        job_id, error = submit_job(job, dep_job_ids)
        if job_id:
            print(f"  -> Job ID: {job_id}")
            submitted.append({**job, "job_id": job_id, "status": "SUBMITTED", "notes": ""})
            dep_job_ids.append(job_id)
        else:
            print(f"  -> FAILED: {error}")
            submitted.append({**job, "job_id": None, "status": "FAILED", "notes": error or ""})

    # Write job table
    with open(OUTPUT_DIR / "master_job_table.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "job_name", "script", "output_dir", "job_id", "dependency",
            "expected_runtime", "status", "notes",
        ])
        writer.writeheader()
        writer.writerow({
            "job_name": "arc1000_novel",
            "script": "slurm/run_full_arc1000_novel_pipeline.sh",
            "output_dir": "outputs/full_arc1000_novel_pipeline",
            "job_id": 14020393,
            "dependency": "",
            "expected_runtime": "48h",
            "status": "RUNNING",
            "notes": "Do not modify",
        })
        for s in submitted:
            writer.writerow({
                "job_name": s["name"],
                "script": s["script"],
                "output_dir": s["output_dir"],
                "job_id": s.get("job_id", ""),
                "dependency": s.get("dependency", ""),
                "expected_runtime": s["expected_runtime"],
                "status": s["status"],
                "notes": s.get("notes", ""),
            })

    # Write monitoring commands
    with open(OUTPUT_DIR / "monitoring_commands.md", "w") as f:
        f.write("# Monitoring Commands\n\n")
        f.write("```bash\n")
        f.write("# All jobs\n")
        f.write("squeue --me\n\n")
        f.write("# Job history\n")
        f.write("sacct -u $(whoami) --starttime=2026-06-01 --format=JobID,JobName%30,State%15,Elapsed,ExitCode -X\n\n")
        f.write("# Monitor specific phase outputs\n")
        for s in submitted:
            if s.get("job_id"):
                f.write(f"# Phase {s['phase']}: {s['name']} (job {s['job_id']})\n")
                f.write(f"squeue -j {s['job_id']}\n")
                f.write(f"cat {s['output_dir']}/status.json\n\n")
        f.write("# ARC-1000 run (read-only)\n")
        f.write("python3.11 scripts/monitor_arc1000_run.py\n")
        f.write("```\n")

    print(f"\n=== Summary ===")
    for s in submitted:
        print(f"  {s['phase']} {s['name']}: {s['status']} (job_id={s.get('job_id')})")
    print(f"\nJob table: {OUTPUT_DIR / 'master_job_table.csv'}")
    print(f"Monitoring: {OUTPUT_DIR / 'monitoring_commands.md'}")


if __name__ == "__main__":
    main()
