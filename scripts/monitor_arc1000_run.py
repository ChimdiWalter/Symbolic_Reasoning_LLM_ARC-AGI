#!/usr/bin/env python3
"""Phase A: Read-only monitor for the active ARC-1000 run (job 14020393).

Reads progress.jsonl, known_task_guard.jsonl, status.json and SLURM state.
Writes summary files to outputs/deep_project_completion/arc1000_monitor/.
Does NOT modify the running job or its output directory.
"""
import json
import csv
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = PROJECT_ROOT / "outputs" / "full_arc1000_novel_pipeline"
OUT_DIR = PROJECT_ROOT / "outputs" / "deep_project_completion" / "arc1000_monitor"

KNOWN_TASKS = {
    "2a5f8217": {"expected_position": 155, "operator": "color_transfer_recolor", "description": "same-shape color-transfer"},
    "a48eeaf7": {"expected_position": 630, "operator": "project_to_halo", "description": "project_to_halo"},
    "d89b689b": {"expected_position": 838, "operator": "quadrant_fill", "description": "quadrant_fill"},
    "e9ac8c9e": {"expected_position": 923, "operator": "quadrant_fill", "description": "multi-block quadrant_fill"},
}

JOB_ID = "14020393"


def load_progress():
    path = RUN_DIR / "progress.jsonl"
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def load_known_task_guard():
    path = RUN_DIR / "known_task_guard.jsonl"
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def load_status():
    path = RUN_DIR / "status.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def get_slurm_status():
    try:
        result = subprocess.run(
            ["scontrol", "show", "job", JOB_ID],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"slurm_available": False, "reason": "job not found or scontrol error"}
        info = {}
        for line in result.stdout.split("\n"):
            for field in line.strip().split():
                if "=" in field:
                    k, v = field.split("=", 1)
                    info[k] = v
        return {
            "slurm_available": True,
            "job_state": info.get("JobState", "UNKNOWN"),
            "run_time": info.get("RunTime", "?"),
            "time_limit": info.get("TimeLimit", "?"),
            "node": info.get("BatchHost", "?"),
            "restarts": info.get("Restarts", "?"),
            "start_time": info.get("StartTime", "?"),
            "end_time": info.get("EndTime", "?"),
        }
    except Exception as e:
        return {"slurm_available": False, "reason": str(e)}


def analyze_progress(entries):
    total = len(entries)
    solved_static = sum(1 for e in entries if e.get("solved_by_static"))
    solved_dsl = sum(1 for e in entries if e.get("solved_by_dsl"))
    solved_any = sum(1 for e in entries if e.get("final_config_that_solved"))
    operator_proposed = sum(1 for e in entries if e.get("operator_proposed"))
    operator_validated = sum(1 for e in entries if e.get("operator_validated"))
    operator_promoted = sum(1 for e in entries if e.get("operator_promoted"))
    false_positives = sum(1 for e in entries if e.get("false_positive"))
    certificates = sum(1 for e in entries if e.get("certificate_emitted"))
    near_solved = sum(1 for e in entries if e.get("near_solved_stored"))
    errors = sum(1 for e in entries if e.get("error"))

    runtimes = [e.get("runtime_seconds", 0) for e in entries if e.get("runtime_seconds")]
    avg_runtime = sum(runtimes) / len(runtimes) if runtimes else 0
    total_runtime = sum(runtimes)

    remaining = 1000 - total
    est_remaining_seconds = remaining * avg_runtime if avg_runtime > 0 else 0
    est_remaining_hours = est_remaining_seconds / 3600

    solver_counts = Counter()
    for e in entries:
        cfg = e.get("final_config_that_solved")
        if cfg:
            solver_counts[cfg] += 1

    operator_families = Counter()
    for e in entries:
        fam = e.get("operator_family")
        if fam:
            operator_families[fam] += 1

    return {
        "total_processed": total,
        "total_target": 1000,
        "percent_complete": round(100 * total / 1000, 1),
        "solved_any": solved_any,
        "solved_static": solved_static,
        "solved_dsl": solved_dsl,
        "operator_proposed": operator_proposed,
        "operator_validated": operator_validated,
        "operator_promoted": operator_promoted,
        "false_positives": false_positives,
        "certificates": certificates,
        "near_solved_stored": near_solved,
        "errors": errors,
        "avg_runtime_seconds": round(avg_runtime, 1),
        "total_runtime_seconds": round(total_runtime, 1),
        "total_runtime_hours": round(total_runtime / 3600, 2),
        "remaining_tasks": remaining,
        "est_remaining_hours": round(est_remaining_hours, 2),
        "solver_breakdown": dict(solver_counts),
        "operator_family_breakdown": dict(operator_families),
    }


def check_known_tasks(entries, guard_entries):
    processed_ids = {e["task_id"] for e in entries}
    guard_ids = {g["task_id"] for g in guard_entries}

    results = []
    for tid, info in KNOWN_TASKS.items():
        row = {
            "task_id": tid,
            "expected_position": info["expected_position"],
            "expected_operator": info["operator"],
            "description": info["description"],
            "processed": tid in processed_ids,
            "guard_entry_exists": tid in guard_ids,
            "operator_promoted": False,
            "certificate_emitted": False,
            "correct": None,
            "failure_reason": None,
        }
        for g in guard_entries:
            if g["task_id"] == tid:
                row["operator_promoted"] = g.get("operator_promoted", False)
                row["certificate_emitted"] = g.get("certificate_emitted", False)
                row["correct"] = g.get("correct_if_known")
                row["failure_reason"] = g.get("failure_reason")
                break
        for e in entries:
            if e["task_id"] == tid:
                if not row["guard_entry_exists"]:
                    row["operator_promoted"] = e.get("operator_promoted", False)
                    row["certificate_emitted"] = e.get("certificate_emitted", False)
                break
        results.append(row)
    return results


def write_status_json(analysis, slurm, known_checks):
    out = {
        "generated_at": datetime.now().isoformat(),
        "job_id": JOB_ID,
        "slurm": slurm,
        "progress": analysis,
        "known_task_checkpoints": known_checks,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "status.json", "w") as f:
        json.dump(out, f, indent=2)


def write_known_task_csv(known_checks):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "known_task_checkpoints.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "task_id", "expected_position", "expected_operator", "description",
            "processed", "guard_entry_exists", "operator_promoted",
            "certificate_emitted", "correct", "failure_reason",
        ])
        writer.writeheader()
        for row in known_checks:
            writer.writerow(row)


def write_status_md(analysis, slurm, known_checks, run_status):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ARC-1000 Run Monitor Report",
        f"\nGenerated: {datetime.now().isoformat()}",
        f"\n## SLURM Job {JOB_ID}",
        "",
    ]
    if slurm.get("slurm_available"):
        lines += [
            f"| Field | Value |",
            f"|-------|-------|",
            f"| State | {slurm['job_state']} |",
            f"| Runtime | {slurm['run_time']} |",
            f"| Time Limit | {slurm['time_limit']} |",
            f"| Node | {slurm['node']} |",
            f"| Restarts | {slurm['restarts']} |",
            f"| Start | {slurm['start_time']} |",
            f"| End (limit) | {slurm['end_time']} |",
        ]
    else:
        lines.append(f"SLURM not available: {slurm.get('reason', 'unknown')}")

    lines += [
        "",
        f"## Progress",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Processed | {analysis['total_processed']} / {analysis['total_target']} ({analysis['percent_complete']}%) |",
        f"| Solved (any) | {analysis['solved_any']} |",
        f"| Solved (static) | {analysis['solved_static']} |",
        f"| Solved (DSL) | {analysis['solved_dsl']} |",
        f"| Operator proposed | {analysis['operator_proposed']} |",
        f"| Operator validated | {analysis['operator_validated']} |",
        f"| Operator promoted | {analysis['operator_promoted']} |",
        f"| False positives | {analysis['false_positives']} |",
        f"| Certificates | {analysis['certificates']} |",
        f"| Near-solved stored | {analysis['near_solved_stored']} |",
        f"| Errors | {analysis['errors']} |",
        f"| Avg runtime/task | {analysis['avg_runtime_seconds']}s |",
        f"| Total runtime | {analysis['total_runtime_hours']}h |",
        f"| Remaining tasks | {analysis['remaining_tasks']} |",
        f"| Est. remaining | {analysis['est_remaining_hours']}h |",
    ]

    if analysis["solver_breakdown"]:
        lines += ["", "### Solver Breakdown", ""]
        for solver, count in sorted(analysis["solver_breakdown"].items(), key=lambda x: -x[1]):
            lines.append(f"- {solver}: {count}")

    if analysis["operator_family_breakdown"]:
        lines += ["", "### Operator Families", ""]
        for fam, count in sorted(analysis["operator_family_breakdown"].items(), key=lambda x: -x[1]):
            lines.append(f"- {fam}: {count}")

    lines += [
        "",
        "## Known-Task Checkpoints",
        "",
        "| Task ID | Position | Operator | Processed | Promoted | Certificate | Correct | Failure |",
        "|---------|----------|----------|-----------|----------|-------------|---------|---------|",
    ]
    for kc in known_checks:
        lines.append(
            f"| {kc['task_id']} | {kc['expected_position']} | {kc['expected_operator']} "
            f"| {kc['processed']} | {kc['operator_promoted']} | {kc['certificate_emitted']} "
            f"| {kc['correct']} | {kc['failure_reason'] or '—'} |"
        )

    lines += [
        "",
        "## Run Status",
        f"",
        f"status.json: `{json.dumps(run_status)}`",
        "",
        "## Integrity",
        "",
        f"- Zero false positives: **{'YES' if analysis['false_positives'] == 0 else 'NO — ' + str(analysis['false_positives']) + ' FP detected'}**",
        f"- No errors: **{'YES' if analysis['errors'] == 0 else 'NO — ' + str(analysis['errors']) + ' errors'}**",
    ]

    with open(OUT_DIR / "status.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def write_monitor_commands():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    content = """# ARC-1000 Monitor Commands

Quick commands to check the running ARC-1000 job without modifying it.

```bash
# Job status
squeue -j 14020393

# Progress count
wc -l outputs/full_arc1000_novel_pipeline/progress.jsonl

# Operator promotions
grep '"operator_promoted": true' outputs/full_arc1000_novel_pipeline/progress.jsonl

# False positives (should be empty)
grep '"false_positive": true' outputs/full_arc1000_novel_pipeline/progress.jsonl

# Known task guard entries
cat outputs/full_arc1000_novel_pipeline/known_task_guard.jsonl

# Certificates emitted
ls outputs/full_arc1000_novel_pipeline/certificates/

# Tail live output
tail -20 outputs/full_arc1000_novel_pipeline/slurm_14020393.out

# Full monitor script
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
python3.11 scripts/monitor_arc1000_run.py
```
"""
    with open(OUT_DIR / "monitor_commands.md", "w") as f:
        f.write(content)


def main():
    print("=== ARC-1000 Run Monitor ===")
    print(f"Reading from: {RUN_DIR}")
    print(f"Writing to:   {OUT_DIR}")
    print()

    entries = load_progress()
    guard_entries = load_known_task_guard()
    run_status = load_status()
    slurm = get_slurm_status()

    analysis = analyze_progress(entries)
    known_checks = check_known_tasks(entries, guard_entries)

    write_status_json(analysis, slurm, known_checks)
    write_known_task_csv(known_checks)
    write_status_md(analysis, slurm, known_checks, run_status)
    write_monitor_commands()

    print(f"Processed: {analysis['total_processed']}/1000 ({analysis['percent_complete']}%)")
    print(f"Solved:    {analysis['solved_any']} (static={analysis['solved_static']}, dsl={analysis['solved_dsl']})")
    print(f"Promoted:  {analysis['operator_promoted']}")
    print(f"FP:        {analysis['false_positives']}")
    print(f"Certs:     {analysis['certificates']}")
    print(f"Avg time:  {analysis['avg_runtime_seconds']}s/task")
    print(f"Est remaining: {analysis['est_remaining_hours']}h")
    print()
    print("Known-task checkpoints:")
    for kc in known_checks:
        status = "PASSED" if kc["operator_promoted"] else ("PENDING" if not kc["processed"] else "FAILED")
        print(f"  {kc['task_id']} (pos {kc['expected_position']}): {status}")
    print()
    print(f"Files written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
